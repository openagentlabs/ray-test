"""OpenTelemetry Logs SDK with optional Amazon CloudWatch Logs (PutLogEvents)."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Sequence
from typing import Final

import boto3
from botocore.exceptions import ClientError
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler, ReadableLogRecord
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    LogRecordExporter,
    LogRecordExportResult,
)
from opentelemetry.sdk.resources import Resource

from solutions_service.core import cloudwatch_logging_defaults_generated as tfdefaults
from solutions_service.observability.correlation import get_correlation_id

_MAX_EVENTS: Final[int] = 500

_initialized = False
_logger_provider: LoggerProvider | None = None


class _CorrelationIdLogFilter(logging.Filter):
    """Injects ``correlation_id`` on log records before OpenTelemetry export."""

    def filter(self, record: logging.LogRecord) -> bool:
        cid = get_correlation_id()
        record.correlation_id = cid if cid else "-"
        return True


class _CloudWatchLogRecordExporter(LogRecordExporter):
    """Ships OTel log records to CloudWatch Logs (log group must exist — Terraform)."""

    def __init__(
        self,
        *,
        region: str,
        log_group_name: str,
        log_stream_name: str,
        service_id: str,
        service_name: str,
        service_instance_id: str,
    ) -> None:
        self._client = boto3.client("logs", region_name=region)
        self._log_group_name = log_group_name
        self._log_stream_name = log_stream_name
        self._service_id = service_id
        self._service_name = service_name
        self._service_instance_id = service_instance_id
        self._sequence_token: str | None = None
        self._stream_ready = False
        self._lock = threading.Lock()

    def export(self, batch: Sequence[ReadableLogRecord]) -> LogRecordExportResult:
        if not batch:
            return LogRecordExportResult.SUCCESS
        try:
            with self._lock:
                if not self._stream_ready:
                    self._ensure_log_stream()
                    self._stream_ready = True
                for i in range(0, len(batch), _MAX_EVENTS):
                    self._put_slice(batch[i : i + _MAX_EVENTS])
        except Exception:  # noqa: S110
            pass
        return LogRecordExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def _ensure_log_stream(self) -> None:
        try:
            self._client.create_log_stream(
                logGroupName=self._log_group_name,
                logStreamName=self._log_stream_name,
            )
        except ClientError as err:
            code = err.response.get("Error", {}).get("Code", "")
            if code != "ResourceAlreadyExistsException":
                raise

    def _put_slice(self, slice_batch: Sequence[ReadableLogRecord]) -> None:
        base_ms = int(time.time() * 1000)
        events: list[dict[str, object]] = []
        for idx, data in enumerate(slice_batch):
            lr = data.log_record
            attrs_raw = getattr(lr, "attributes", None) or {}
            try:
                attrs = dict(attrs_raw)
            except TypeError:
                attrs = {}
            payload = {
                "service": {
                    "id": self._service_id,
                    "name": self._service_name,
                    "instanceId": self._service_instance_id,
                },
                "severityText": getattr(lr, "severity_text", None),
                "severityNumber": getattr(lr, "severity_number", None),
                "body": getattr(lr, "body", None),
                "attributes": attrs,
                "correlation_id": get_correlation_id() or "-",
            }
            events.append({"message": json.dumps(payload), "timestamp": base_ms + idx})
        self._put_with_retry(events)

    def _put_with_retry(self, events: list[dict[str, object]]) -> None:
        kwargs: dict[str, object] = {
            "logGroupName": self._log_group_name,
            "logStreamName": self._log_stream_name,
            "logEvents": events,
        }
        if self._sequence_token is not None:
            kwargs["sequenceToken"] = self._sequence_token
        try:
            response = self._client.put_log_events(**kwargs)
            self._sequence_token = response.get("nextSequenceToken")
        except ClientError as err:
            code = err.response.get("Error", {}).get("Code", "")
            if code == "InvalidSequenceTokenException":
                err_block = err.response.get("Error", {})
                tok: str | None = None
                if isinstance(err_block, dict):
                    exp = err_block.get("expectedSequenceToken")
                    if isinstance(exp, str):
                        tok = exp
                self._sequence_token = tok
                kwargs["sequenceToken"] = self._sequence_token
                response = self._client.put_log_events(**kwargs)
                self._sequence_token = response.get("nextSequenceToken")
                return
            if code == "ResourceNotFoundException":
                self._stream_ready = False
                self._ensure_log_stream()
                self._stream_ready = True
                self._put_with_retry(events)
                return
            raise


class _NoOpLogRecordExporter(LogRecordExporter):
    def export(self, batch: Sequence[ReadableLogRecord]) -> LogRecordExportResult:
        return LogRecordExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None or raw.strip() == "":
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    return default


def _build_log_stream_name(*, prefix: str) -> str:
    explicit = os.environ.get("CLOUDWATCH_LOG_STREAM_NAME", "").strip()
    if explicit:
        return explicit
    return f"{prefix}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def init_opentelemetry_process_logging(*, log_level_name: str) -> None:
    """Configure root logging via OpenTelemetry (no stderr StreamHandler). Idempotent."""
    global _initialized, _logger_provider
    upper = log_level_name.strip().upper()
    allowed: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
    level = getattr(logging, upper, logging.INFO) if upper in allowed else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    if _initialized and _logger_provider is not None:
        for handler in root.handlers:
            handler.setLevel(level)
        return

    region = (
        os.environ.get("CLOUDWATCH_LOGS_REGION", "").strip()
        or os.environ.get("AWS_REGION", "").strip()
        or tfdefaults.DEFAULT_AWS_REGION
    )
    cw_enabled = _parse_bool(os.environ.get("CLOUDWATCH_LOGS_ENABLED"), False)
    log_group = (
        os.environ.get("CLOUDWATCH_LOG_GROUP_NAME", "").strip() or tfdefaults.DEFAULT_LOG_GROUP
    )
    otel_service_name = (
        os.environ.get("OTEL_SERVICE_NAME", "").strip() or tfdefaults.DEFAULT_OTEL_SERVICE_NAME
    )
    service_id = os.environ.get("SERVICE_ID", "").strip() or tfdefaults.DEFAULT_SERVICE_ID
    stream_prefix = tfdefaults.LOG_STREAM_PREFIX
    instance_id = (
        os.environ.get("OTEL_SERVICE_INSTANCE_ID", "").strip()
        or os.environ.get("HOSTNAME", "").strip()
        or f"proc-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )

    resource = Resource.create(
        {
            "service.name": otel_service_name,
            "service.instance.id": instance_id,
            "service.id": service_id,
        },
    )

    exporter: LogRecordExporter
    if cw_enabled:
        exporter = _CloudWatchLogRecordExporter(
            region=region,
            log_group_name=log_group,
            log_stream_name=_build_log_stream_name(prefix=stream_prefix),
            service_id=service_id,
            service_name=otel_service_name,
            service_instance_id=instance_id,
        )
    else:
        exporter = _NoOpLogRecordExporter()

    processor = BatchLogRecordProcessor(exporter)
    provider = LoggerProvider(resource=resource)
    provider.add_log_record_processor(processor)
    set_logger_provider(provider)
    _logger_provider = provider

    handler = LoggingHandler(level=logging.NOTSET, logger_provider=provider)
    handler.addFilter(_CorrelationIdLogFilter())
    root.handlers.clear()
    root.addHandler(handler)
    handler.setLevel(level)
    logging.getLogger("grpc").setLevel(logging.WARNING)

    _initialized = True

"""AWS CloudWatch APM driver — structured performance events via CloudWatch Logs."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

import boto3

from exl_observability.apm.client import ApmClient
from exl_observability.config.models import (
    ApmInterfaceConfig,
    CloudWatchApmDriverConfig,
    ServiceIdentityConfig,
)
from exl_observability.core.async_queue import AsyncExportQueue
from exl_observability.core.correlation import get_correlation_id
from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result, Success
from exl_observability.drivers._cloudwatch_common import (
    build_stream_name,
    ensure_log_stream,
    put_log_events,
)


class CloudWatchApmDriver:
    """Ship APM events as JSON lines to a dedicated CloudWatch log group."""

    def __init__(
        self,
        *,
        identity: ServiceIdentityConfig,
        interface_config: ApmInterfaceConfig,
        driver_config: CloudWatchApmDriverConfig,
    ) -> None:
        self._identity = identity
        self._interface = interface_config
        self._config = driver_config
        self._client = boto3.client("logs", region_name=driver_config.region)
        self._stream_name = build_stream_name(prefix=driver_config.log_stream_prefix)
        self._sequence_token: str | None = None
        self._queue: AsyncExportQueue[str] | None = None

    async def init(self) -> Result[None, ObsError]:
        self._queue = AsyncExportQueue(
            max_size=self._config.queue_max_size,
            flush_handler=self._flush_lines,
        )
        await ensure_log_stream(
            client=self._client,
            log_group_name=self._config.log_group_name,
            log_stream_name=self._stream_name,
        )
        await self._queue.start()
        return Success(None)

    async def shutdown(self) -> Result[None, ObsError]:
        if self._queue is not None:
            await self._queue.stop()
            self._queue = None
        return Success(None)

    def create_client(self) -> ApmClient:
        return ApmClient(self)

    def record_event(
        self,
        *,
        event_name: str,
        duration_ms: float | None,
        attributes: dict[str, Any],
    ) -> None:
        if not self._interface.enabled or self._queue is None:
            return
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_name": event_name,
            "duration_ms": duration_ms,
            "service": {
                "id": self._identity.service_id,
                "name": self._identity.service_name,
                "version": self._identity.service_version,
                "instanceId": self._identity.instance_id,
                "environment": self._identity.environment,
            },
            "correlation_id": get_correlation_id() or "-",
            "channel": "apm",
            "attributes": attributes,
            "format": "exl-apm-v1",
        }
        self._queue.enqueue(json.dumps(payload, default=str, separators=(",", ":")))

    async def _flush_lines(self, lines: list[str]) -> None:
        if not lines:
            return
        base_ms = int(time.time() * 1000)
        events = [
            {"message": line, "timestamp": base_ms + idx} for idx, line in enumerate(lines)
        ]
        try:
            self._sequence_token = await put_log_events(
                client=self._client,
                log_group_name=self._config.log_group_name,
                log_stream_name=self._stream_name,
                events=events,
                sequence_token=self._sequence_token,
            )
        except Exception:
            logging.getLogger(__name__).debug(
                "cloudwatch_apm_flush_failed count=%s",
                len(lines),
                exc_info=True,
            )

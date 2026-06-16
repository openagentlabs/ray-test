"""AWS CloudWatch Logs driver for application logging."""

from __future__ import annotations

import logging
import time
from typing import Any

import boto3

from exl_observability.config.models import (
    CloudWatchLoggingDriverConfig,
    LoggingInterfaceConfig,
    ServiceIdentityConfig,
)
from exl_observability.core.async_queue import AsyncExportQueue
from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result, Success
from exl_observability.drivers._cloudwatch_common import (
    build_stream_name,
    ensure_log_stream,
    put_log_events,
)
from exl_observability.logging.client import LoggingClient
from exl_observability.logging.format import build_log_record

_LEVEL_ORDER = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


class CloudWatchLoggingDriver:
    """Ship EXL JSON log lines to CloudWatch Logs via async batch export."""

    def __init__(
        self,
        *,
        identity: ServiceIdentityConfig,
        interface_config: LoggingInterfaceConfig,
        driver_config: CloudWatchLoggingDriverConfig,
    ) -> None:
        self._identity = identity
        self._interface = interface_config
        self._config = driver_config
        self._min_level = _LEVEL_ORDER.get(interface_config.level, 20)
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

    def create_client(self) -> LoggingClient:
        return LoggingClient(self)

    def emit(self, *, level: str, message: str, attributes: dict[str, Any]) -> None:
        if not self._interface.enabled:
            return
        if _LEVEL_ORDER.get(level.upper(), 0) < self._min_level:
            return
        record = build_log_record(
            level=level,
            message=message,
            identity=self._identity,
            channel="application",
            attributes=attributes,
        )
        if self._queue is not None:
            self._queue.enqueue(record.to_json_line())

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
                "cloudwatch_logging_flush_failed count=%s",
                len(lines),
                exc_info=True,
            )

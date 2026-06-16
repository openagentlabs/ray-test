"""AWS X-Ray compatible tracing driver (OTel SDK + UDP daemon segment export)."""

from __future__ import annotations

import json
import logging
import socket
import time
import uuid
from typing import Any

from exl_observability.config.models import (
    CloudWatchTracingDriverConfig,
    ServiceIdentityConfig,
    TracingInterfaceConfig,
)
from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result, Success
from exl_observability.tracing.client import TracingClient
from exl_observability.tracing.types import SpanContext

_XRAY_DAEMON_ADDRESS = ("127.0.0.1", 2000)


class CloudWatchTracingDriver:
    """Emit X-Ray segment documents compatible with the CloudWatch/X-Ray daemon."""

    def __init__(
        self,
        *,
        identity: ServiceIdentityConfig,
        interface_config: TracingInterfaceConfig,
        driver_config: CloudWatchTracingDriverConfig,
    ) -> None:
        self._identity = identity
        self._interface = interface_config
        self._config = driver_config
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setblocking(False)

    async def init(self) -> Result[None, ObsError]:
        return Success(None)

    async def shutdown(self) -> Result[None, ObsError]:
        self._socket.close()
        return Success(None)

    def create_client(self) -> TracingClient:
        return TracingClient(self)

    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> SpanContext:
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        if self._interface.enabled:
            segment = {
                "name": name,
                "id": span_id,
                "trace_id": f"1-{int(time.time()):08x}-{trace_id[:24]}",
                "start_time": time.time(),
                "service": {
                    "name": self._identity.service_name,
                    "version": self._identity.service_version,
                },
                "metadata": {
                    "default": {
                        "service_id": self._identity.service_id,
                        "environment": self._identity.environment,
                        **(attributes or {}),
                    },
                },
            }
            self._send_segment(segment)
        return SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            attributes=attributes or {},
        )

    def end_span(self, span: SpanContext, *, error: bool = False) -> None:
        if not self._interface.enabled:
            return
        segment = {
            "name": span.name,
            "id": span.span_id,
            "trace_id": f"1-{int(time.time()):08x}-{span.trace_id[:24]}",
            "end_time": time.time(),
            "error": error,
            "metadata": {"default": span.attributes},
        }
        self._send_segment(segment)

    def _send_segment(self, segment: dict[str, Any]) -> None:
        try:
            payload = json.dumps({"format": "json", "version": 1, **segment})
            self._socket.sendto(payload.encode("utf-8"), _XRAY_DAEMON_ADDRESS)
        except OSError:
            logging.getLogger(__name__).debug("xray_segment_send_failed", exc_info=True)

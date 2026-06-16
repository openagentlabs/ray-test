"""No-op tracing driver."""

from __future__ import annotations

import uuid
from typing import Any

from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result, Success
from exl_observability.tracing.client import TracingClient
from exl_observability.tracing.types import SpanContext


class NoOpTracingDriver:
    async def init(self) -> Result[None, ObsError]:
        return Success(None)

    async def shutdown(self) -> Result[None, ObsError]:
        return Success(None)

    def create_client(self) -> TracingClient:
        return TracingClient(self)

    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> SpanContext:
        trace_id = uuid.uuid4().hex
        return SpanContext(
            span_id=uuid.uuid4().hex[:16],
            trace_id=trace_id,
            name=name,
            attributes=attributes or {},
        )

    def end_span(self, span: SpanContext, *, error: bool = False) -> None:
        return None

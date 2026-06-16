"""Tracing driver protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result
from exl_observability.tracing.types import SpanContext

if TYPE_CHECKING:
    from exl_observability.tracing.client import TracingClient


class TracingDriver(Protocol):
    """Pluggable distributed tracing backend."""

    async def init(self) -> Result[None, ObsError]:
        ...

    async def shutdown(self) -> Result[None, ObsError]:
        ...

    def create_client(self) -> TracingClient:
        ...

    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> SpanContext:
        ...

    def end_span(self, span: SpanContext, *, error: bool = False) -> None:
        ...

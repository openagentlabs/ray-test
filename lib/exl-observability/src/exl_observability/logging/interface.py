"""Application logging driver protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result

if TYPE_CHECKING:
    from exl_observability.logging.client import LoggingClient


class LoggingDriver(Protocol):
    """Pluggable backend for application logging."""

    async def init(self) -> Result[None, ObsError]:
        """Initialize exporter resources (streams, queues, credentials)."""
        ...

    async def shutdown(self) -> Result[None, ObsError]:
        """Flush and release exporter resources."""
        ...

    def create_client(self) -> LoggingClient:
        """Return a client bound to this driver."""
        ...

    def emit(self, *, level: str, message: str, attributes: dict[str, Any]) -> None:
        """Hot-path emit (non-blocking)."""
        ...

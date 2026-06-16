"""Security logging driver protocol — separate channel from application logs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result

if TYPE_CHECKING:
    from exl_observability.security_logging.client import SecurityLoggingClient


class SecurityLoggingDriver(Protocol):
    """Pluggable backend for security audit events."""

    async def init(self) -> Result[None, ObsError]:
        ...

    async def shutdown(self) -> Result[None, ObsError]:
        ...

    def create_client(self) -> SecurityLoggingClient:
        ...

    def emit(self, *, event_type: str, message: str, attributes: dict[str, Any]) -> None:
        ...

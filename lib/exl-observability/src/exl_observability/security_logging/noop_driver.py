"""No-op security logging driver."""

from __future__ import annotations

from typing import Any

from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result, Success
from exl_observability.security_logging.client import SecurityLoggingClient


class NoOpSecurityLoggingDriver:
    async def init(self) -> Result[None, ObsError]:
        return Success(None)

    async def shutdown(self) -> Result[None, ObsError]:
        return Success(None)

    def create_client(self) -> SecurityLoggingClient:
        return SecurityLoggingClient(self)

    def emit(self, *, event_type: str, message: str, attributes: dict[str, Any]) -> None:
        return None

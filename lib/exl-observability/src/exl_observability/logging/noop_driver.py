"""No-op application logging driver."""

from __future__ import annotations

from typing import Any

from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result, Success
from exl_observability.logging.client import LoggingClient


class NoOpLoggingDriver:
    """Discards all log records — zero network and minimal CPU cost."""

    async def init(self) -> Result[None, ObsError]:
        return Success(None)

    async def shutdown(self) -> Result[None, ObsError]:
        return Success(None)

    def create_client(self) -> LoggingClient:
        return LoggingClient(self)

    def emit(self, *, level: str, message: str, attributes: dict[str, Any]) -> None:
        return None

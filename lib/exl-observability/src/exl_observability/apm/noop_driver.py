"""No-op APM driver."""

from __future__ import annotations

from typing import Any

from exl_observability.apm.client import ApmClient
from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result, Success


class NoOpApmDriver:
    async def init(self) -> Result[None, ObsError]:
        return Success(None)

    async def shutdown(self) -> Result[None, ObsError]:
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
        return None

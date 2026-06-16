"""APM driver protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result

if TYPE_CHECKING:
    from exl_observability.apm.client import ApmClient


class ApmDriver(Protocol):
    """Pluggable application performance monitoring backend."""

    async def init(self) -> Result[None, ObsError]:
        ...

    async def shutdown(self) -> Result[None, ObsError]:
        ...

    def create_client(self) -> ApmClient:
        ...

    def record_event(
        self,
        *,
        event_name: str,
        duration_ms: float | None,
        attributes: dict[str, Any],
    ) -> None:
        ...

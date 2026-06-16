"""Metrics driver protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result
from exl_observability.metrics.types import MetricHandle

if TYPE_CHECKING:
    from exl_observability.metrics.client import MetricsClient


class MetricsDriver(Protocol):
    """Pluggable metrics backend."""

    async def init(self) -> Result[None, ObsError]:
        ...

    async def shutdown(self) -> Result[None, ObsError]:
        ...

    def create_client(self) -> MetricsClient:
        ...

    def record(self, handle: MetricHandle, value: float) -> None:
        ...

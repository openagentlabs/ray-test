"""No-op metrics driver."""

from __future__ import annotations

from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result, Success
from exl_observability.metrics.client import MetricsClient
from exl_observability.metrics.types import MetricHandle


class NoOpMetricsDriver:
    def __init__(self, *, namespace: str) -> None:
        self._namespace = namespace

    async def init(self) -> Result[None, ObsError]:
        return Success(None)

    async def shutdown(self) -> Result[None, ObsError]:
        return Success(None)

    def create_client(self) -> MetricsClient:
        return MetricsClient(self, namespace=self._namespace)

    def record(self, handle: MetricHandle, value: float) -> None:
        return None

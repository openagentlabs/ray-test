"""Metrics factory client with enum validation and Result returns."""

from __future__ import annotations

from exl_observability.core.errors import ErrorCodes, ObsError
from exl_observability.core.result import Failure, Result, Success
from exl_observability.metrics.enums import MetricGroup, MetricName, MetricType
from exl_observability.metrics.interface import MetricsDriver
from exl_observability.metrics.types import MetricHandle


class MetricsClient:
    """Factory for metric handles; records values via the bound driver."""

    def __init__(self, driver: MetricsDriver, *, namespace: str) -> None:
        self._driver = driver
        self._namespace = namespace

    def new(
        self,
        metric_type: MetricType,
        name: MetricName,
        group: MetricGroup,
    ) -> Result[MetricHandle, ObsError]:
        if not isinstance(metric_type, MetricType):
            return Failure(
                ObsError(
                    code=ErrorCodes.VALIDATION,
                    message="metric_type must be a MetricType enum value.",
                    detail=f"received={metric_type!r}",
                ),
            )
        if not isinstance(name, MetricName):
            return Failure(
                ObsError(
                    code=ErrorCodes.METRIC_UNKNOWN,
                    message="name must be a MetricName enum value.",
                    detail=f"received={name!r}",
                ),
            )
        if not isinstance(group, MetricGroup):
            return Failure(
                ObsError(
                    code=ErrorCodes.VALIDATION,
                    message="group must be a MetricGroup enum value.",
                    detail=f"received={group!r}",
                ),
            )
        return Success(
            MetricHandle(
                metric_type=metric_type,
                name=name,
                group=group,
                namespace=self._namespace,
            ),
        )

    def record(self, handle: MetricHandle, value: float) -> Result[None, ObsError]:
        if value < 0 and handle.metric_type in {MetricType.COUNTER, MetricType.GAUGE}:
            return Failure(
                ObsError(
                    code=ErrorCodes.VALIDATION,
                    message="Counter and gauge values must be non-negative.",
                    detail=f"value={value}",
                ),
            )
        self._driver.record(handle, value)
        return Success(None)

    def increment(self, handle: MetricHandle, delta: float = 1.0) -> Result[None, ObsError]:
        if handle.metric_type != MetricType.COUNTER:
            return Failure(
                ObsError(
                    code=ErrorCodes.VALIDATION,
                    message="increment is only valid for COUNTER metrics.",
                    detail=f"type={handle.metric_type.value}",
                ),
            )
        return self.record(handle, delta)

"""Metric handle types."""

from __future__ import annotations

from dataclasses import dataclass

from exl_observability.metrics.enums import MetricGroup, MetricName, MetricType


@dataclass(frozen=True, slots=True)
class MetricHandle:
    """Validated metric identity returned by the metrics factory."""

    metric_type: MetricType
    name: MetricName
    group: MetricGroup
    namespace: str

    def dimensions(self) -> dict[str, str]:
        return {
            "MetricGroup": self.group.value,
            "MetricName": self.name.value,
        }

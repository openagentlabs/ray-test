"""Tests for metrics factory validation."""

from __future__ import annotations

from exl_observability.core.result import Failure, Success
from exl_observability.metrics.client import MetricsClient
from exl_observability.metrics.enums import MetricGroup, MetricName, MetricType
from exl_observability.metrics.noop_driver import NoOpMetricsDriver


def test_metrics_new_returns_handle() -> None:
    client = MetricsClient(NoOpMetricsDriver(namespace="EXL/Test"), namespace="EXL/Test")
    result = client.new(MetricType.COUNTER, MetricName.REQUEST_COUNT, MetricGroup.GRPC)
    assert isinstance(result, Success)
    handle = result.unwrap()
    assert handle.name == MetricName.REQUEST_COUNT


def test_metrics_increment_rejects_gauge() -> None:
    client = MetricsClient(NoOpMetricsDriver(namespace="EXL/Test"), namespace="EXL/Test")
    created = client.new(MetricType.GAUGE, MetricName.ACTIVE_CONNECTIONS, MetricGroup.RUNTIME)
    assert isinstance(created, Success)
    result = client.increment(created.unwrap())
    assert isinstance(result, Failure)

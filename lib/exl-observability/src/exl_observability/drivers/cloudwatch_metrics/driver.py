"""AWS CloudWatch Metrics driver (PutMetricData)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import boto3

from exl_observability.config.models import (
    CloudWatchMetricsDriverConfig,
    MetricsInterfaceConfig,
    ServiceIdentityConfig,
)
from exl_observability.core.async_queue import AsyncExportQueue
from exl_observability.core.errors import ObsError
from exl_observability.core.result import Result, Success
from exl_observability.metrics.client import MetricsClient
from exl_observability.metrics.types import MetricHandle


class CloudWatchMetricsDriver:
    """Batch metric datapoints to CloudWatch via async queue."""

    def __init__(
        self,
        *,
        identity: ServiceIdentityConfig,
        interface_config: MetricsInterfaceConfig,
        driver_config: CloudWatchMetricsDriverConfig,
    ) -> None:
        self._identity = identity
        self._interface = interface_config
        self._config = driver_config
        self._client = boto3.client("cloudwatch", region_name=driver_config.region)
        self._queue: AsyncExportQueue[dict[str, Any]] | None = None

    async def init(self) -> Result[None, ObsError]:
        self._queue = AsyncExportQueue(
            max_size=self._config.queue_max_size,
            flush_handler=self._flush_metrics,
        )
        await self._queue.start()
        return Success(None)

    async def shutdown(self) -> Result[None, ObsError]:
        if self._queue is not None:
            await self._queue.stop()
            self._queue = None
        return Success(None)

    def create_client(self) -> MetricsClient:
        return MetricsClient(self, namespace=self._config.namespace)

    def record(self, handle: MetricHandle, value: float) -> None:
        if not self._interface.enabled or self._queue is None:
            return
        self._queue.enqueue(
            {
                "MetricName": handle.name.value,
                "Value": value,
                "Unit": "Count" if handle.metric_type.value == "counter" else "None",
                "Dimensions": [
                    {"Name": key, "Value": val}
                    for key, val in {
                        **handle.dimensions(),
                        "ServiceName": self._identity.service_name,
                        "Environment": self._identity.environment,
                    }.items()
                ],
            },
        )

    async def _flush_metrics(self, datapoints: list[dict[str, Any]]) -> None:
        if not datapoints:
            return

        def _put() -> None:
            self._client.put_metric_data(
                Namespace=self._config.namespace,
                MetricData=datapoints[:20],
            )

        try:
            await asyncio.to_thread(_put)
        except Exception:
            logging.getLogger(__name__).debug(
                "cloudwatch_metrics_flush_failed count=%s",
                len(datapoints),
                exc_info=True,
            )

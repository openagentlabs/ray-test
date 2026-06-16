"""Tests for observability runtime lifecycle."""

from __future__ import annotations

import pytest

from exl_observability.config import ObservabilityConfig
from exl_observability.core.result import Success
from exl_observability.runtime import ObservabilityRuntime, get_logging_client


@pytest.mark.asyncio
async def test_runtime_init_shutdown_noop() -> None:
    runtime = ObservabilityRuntime(ObservabilityConfig.defaults())
    init_result = await runtime.init()
    assert isinstance(init_result, Success)
    runtime.logging_client().info("test_event", component="pytest")
    shutdown_result = await runtime.shutdown()
    assert isinstance(shutdown_result, Success)


def test_get_logging_client_before_init_is_noop() -> None:
    client = get_logging_client()
    client.info("noop_safe")

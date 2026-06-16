"""Process-wide observability setup driven by ``AppConfig``."""

from __future__ import annotations

from exl_observability.config import ObservabilityConfig
from exl_observability.core.result import Failure
from exl_observability.logging.stdlib_bridge import attach_stdlib_bridge
from exl_observability.runtime import ObservabilityRuntime

_runtime: ObservabilityRuntime | None = None


async def configure_observability(*, config: ObservabilityConfig) -> ObservabilityRuntime:
    """Initialize all observability drivers and attach the stdlib logging bridge."""
    global _runtime
    runtime = ObservabilityRuntime(config)
    init_result = await runtime.init()
    if isinstance(init_result, Failure):
        err = init_result.failure()
        msg = f"observability init failed: {err.message}"
        raise RuntimeError(msg)
    attach_stdlib_bridge(level_name=config.logging.level)
    _runtime = runtime
    return runtime


async def shutdown_observability() -> None:
    """Flush and release observability drivers."""
    global _runtime
    if _runtime is None:
        return
    await _runtime.shutdown()
    _runtime = None


def get_observability_runtime() -> ObservabilityRuntime | None:
    return _runtime

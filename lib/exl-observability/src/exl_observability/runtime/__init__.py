"""Runtime bootstrap and global client accessors."""

from exl_observability.runtime.bootstrap import (
    ObservabilityRuntime,
    get_apm_client,
    get_logging_client,
    get_metrics_client,
    get_runtime,
    get_security_logging_client,
    get_tracing_client,
)

__all__ = (
    "ObservabilityRuntime",
    "get_apm_client",
    "get_logging_client",
    "get_metrics_client",
    "get_runtime",
    "get_security_logging_client",
    "get_tracing_client",
)

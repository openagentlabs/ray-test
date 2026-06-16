"""Observability integration for iam.svc."""

from exl_observability.runtime import (
    get_apm_client,
    get_logging_client,
    get_metrics_client,
    get_security_logging_client,
    get_tracing_client,
)

__all__ = (
    "get_apm_client",
    "get_logging_client",
    "get_metrics_client",
    "get_security_logging_client",
    "get_tracing_client",
)

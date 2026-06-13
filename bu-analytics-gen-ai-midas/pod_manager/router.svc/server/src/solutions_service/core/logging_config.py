"""Process-wide logging setup driven by ``AppConfig``."""

from __future__ import annotations

from solutions_service.observability.otel_process_logging import init_opentelemetry_process_logging


def configure_logging(*, level_name: str) -> None:
    """Configure OpenTelemetry-backed logging (no console StreamHandler)."""
    init_opentelemetry_process_logging(log_level_name=level_name)

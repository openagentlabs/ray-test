"""Deprecated — use ``iam_service.core.observability_config`` instead."""

from __future__ import annotations

from exl_observability.logging.stdlib_bridge import attach_stdlib_bridge


def configure_logging(*, level_name: str) -> None:
    """Attach stdlib bridge only (runtime must already be initialized)."""
    attach_stdlib_bridge(level_name=level_name)

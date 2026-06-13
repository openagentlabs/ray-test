"""Correlation id for logs (ContextVar; set from gRPC metadata in transport)."""

from __future__ import annotations

import contextvars
import uuid
from typing import Final

CORRELATION_METADATA_KEY: Final[str] = "x-correlation-id"

correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id",
    default=None,
)


def get_correlation_id() -> str | None:
    """Return the active correlation id for this task, if any."""
    return correlation_id_var.get()


def new_correlation_token(value: str | None) -> tuple[contextvars.Token[str | None], str]:
    """Resolve value (or generate UUID), return token for ``reset`` and the resolved id."""
    resolved = value if value else str(uuid.uuid4())
    token = correlation_id_var.set(resolved)
    return token, resolved


def reset_correlation_token(token: contextvars.Token[str | None]) -> None:
    """Restore previous correlation context."""
    correlation_id_var.reset(token)

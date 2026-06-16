"""Tracing span handle type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SpanContext:
    """Lightweight span handle returned by the tracing client."""

    span_id: str
    trace_id: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)

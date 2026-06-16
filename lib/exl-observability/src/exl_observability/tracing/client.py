"""Tracing client."""

from __future__ import annotations

import uuid
from typing import Any

from exl_observability.tracing.interface import TracingDriver
from exl_observability.tracing.types import SpanContext


class TracingClient:
    """Start and end spans without knowing the tracing driver."""

    def __init__(self, driver: TracingDriver) -> None:
        self._driver = driver

    def start_span(self, name: str, **attributes: Any) -> SpanContext:
        return self._driver.start_span(name, attributes)

    def end_span(self, span: SpanContext, *, error: bool = False) -> None:
        self._driver.end_span(span, error=error)

    def trace_id(self) -> str:
        return uuid.uuid4().hex

"""APM client."""

from __future__ import annotations

from typing import Any

from exl_observability.apm.interface import ApmDriver


class ApmClient:
    """Record performance events without knowing the APM driver."""

    def __init__(self, driver: ApmDriver) -> None:
        self._driver = driver

    def record_transaction(
        self,
        name: str,
        *,
        duration_ms: float,
        **attributes: Any,
    ) -> None:
        self._driver.record_event(
            event_name=name,
            duration_ms=duration_ms,
            attributes=attributes,
        )

    def record_event(self, name: str, **attributes: Any) -> None:
        self._driver.record_event(
            event_name=name,
            duration_ms=None,
            attributes=attributes,
        )

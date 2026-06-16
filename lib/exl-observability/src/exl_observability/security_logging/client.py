"""Security logging client."""

from __future__ import annotations

from typing import Any

from exl_observability.security_logging.interface import SecurityLoggingDriver


class SecurityLoggingClient:
    """Dedicated security event channel; never mixed with application logs."""

    def __init__(self, driver: SecurityLoggingDriver) -> None:
        self._driver = driver

    def auth_success(self, message: str, **attributes: Any) -> None:
        self._driver.emit(event_type="auth_success", message=message, attributes=attributes)

    def auth_failure(self, message: str, **attributes: Any) -> None:
        self._driver.emit(event_type="auth_failure", message=message, attributes=attributes)

    def access_denied(self, message: str, **attributes: Any) -> None:
        self._driver.emit(event_type="access_denied", message=message, attributes=attributes)

    def privilege_change(self, message: str, **attributes: Any) -> None:
        self._driver.emit(event_type="privilege_change", message=message, attributes=attributes)

    def security_event(self, event_type: str, message: str, **attributes: Any) -> None:
        self._driver.emit(event_type=event_type, message=message, attributes=attributes)

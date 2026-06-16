"""Application logging client — zero-impact when bound to NoOp driver."""

from __future__ import annotations

from typing import Any

from exl_observability.logging.interface import LoggingDriver


class LoggingClient:
    """Application logging facade; safe to instantiate anywhere after runtime init."""

    def __init__(self, driver: LoggingDriver) -> None:
        self._driver = driver

    def debug(self, message: str, **attributes: Any) -> None:
        self._driver.emit(level="DEBUG", message=message, attributes=attributes)

    def info(self, message: str, **attributes: Any) -> None:
        self._driver.emit(level="INFO", message=message, attributes=attributes)

    def warning(self, message: str, **attributes: Any) -> None:
        self._driver.emit(level="WARNING", message=message, attributes=attributes)

    def error(self, message: str, **attributes: Any) -> None:
        self._driver.emit(level="ERROR", message=message, attributes=attributes)

    def critical(self, message: str, **attributes: Any) -> None:
        self._driver.emit(level="CRITICAL", message=message, attributes=attributes)

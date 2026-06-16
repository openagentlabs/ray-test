"""Bridge stdlib ``logging`` to the EXL logging client."""

from __future__ import annotations

import logging
from typing import Any


class ExlLoggingHandler(logging.Handler):
    """Forwards stdlib log records to the EXL application logging client."""

    def emit(self, record: logging.LogRecord) -> None:
        from exl_observability.runtime.bootstrap import get_logging_client

        client = get_logging_client()
        message = record.getMessage()
        attributes: dict[str, Any] = {
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, "correlation_id"):
            attributes["correlation_id"] = record.correlation_id
        level = record.levelname
        if level == "DEBUG":
            client.debug(message, **attributes)
        elif level == "INFO":
            client.info(message, **attributes)
        elif level == "WARNING":
            client.warning(message, **attributes)
        elif level == "ERROR":
            client.error(message, **attributes)
        else:
            client.critical(message, **attributes)


def attach_stdlib_bridge(*, level_name: str) -> None:
    """Attach EXL handler as the sole root handler (no stderr StreamHandler)."""
    upper = level_name.strip().upper()
    allowed = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
    level = getattr(logging, upper, logging.INFO) if upper in allowed else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    handler = ExlLoggingHandler()
    handler.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
    logging.getLogger("grpc").setLevel(logging.WARNING)

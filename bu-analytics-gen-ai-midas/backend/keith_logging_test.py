"""
Debug heartbeat logger — Keith logging test.

Emits a structured JSON log line every 30 seconds so that log delivery
from the pod through the CloudWatch pipeline can be validated end-to-end.

Lifecycle
---------
Call ``start()`` once from the application startup (e.g. main.py lifespan).
Call ``stop()`` from the shutdown handler to join cleanly.

Environment variables (all optional)
-------------------------------------
KEITH_LOGGING_TEST_ENABLED   true/1/yes  — enable the thread (default: true)
KEITH_LOGGING_TEST_INTERVAL  Seconds between heartbeats (default: 30)
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Optional

from app.core.logging_config import get_logger

_logger = get_logger("keith_logging_test")

_thread: Optional[threading.Thread] = None
_stop_event: threading.Event = threading.Event()


def _enabled() -> bool:
    return os.getenv("KEITH_LOGGING_TEST_ENABLED", "true").strip().lower() not in (
        "false",
        "0",
        "no",
    )


def _interval() -> int:
    try:
        return max(1, int(os.getenv("KEITH_LOGGING_TEST_INTERVAL", "30")))
    except ValueError:
        return 30


def _run() -> None:
    interval = _interval()
    _logger.info(
        "keith_logging_test: heartbeat thread started",
        extra={"event": "keith_log_start", "interval_seconds": interval},
    )
    while not _stop_event.wait(timeout=interval):
        now = datetime.now(tz=timezone.utc)
        _logger.info(
            f"Hello from keith_logging_test — {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            extra={
                "event": "keith_log_heartbeat",
                "log_category": "debug",
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timezone": "UTC",
            },
        )
    _logger.info(
        "keith_logging_test: heartbeat thread stopped",
        extra={"event": "keith_log_stop"},
    )


def start() -> None:
    """Start the heartbeat thread if KEITH_LOGGING_TEST_ENABLED is not false."""
    global _thread
    if not _enabled():
        _logger.info(
            "keith_logging_test: disabled via KEITH_LOGGING_TEST_ENABLED",
            extra={"event": "keith_log_disabled"},
        )
        return
    if _thread is not None and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_run, name="keith-log-heartbeat", daemon=True)
    _thread.start()


def stop() -> None:
    """Signal the heartbeat thread to stop and wait for it to exit."""
    _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=5)

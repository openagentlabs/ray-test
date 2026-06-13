"""Application exit codes (``SystemExit`` argument)."""

from __future__ import annotations

from enum import IntEnum


class AppExitCode(IntEnum):
    """Exit reasons for the solutions service process."""

    SUCCESS = 0
    CONFIG_LOAD_FAILED = 10
    STARTUP_VALIDATION_FAILED = 11
    DATABASE_VALIDATION_FAILED = 12
    GRPC_SERVER_FAILED = 13
    INTERRUPTED = 143

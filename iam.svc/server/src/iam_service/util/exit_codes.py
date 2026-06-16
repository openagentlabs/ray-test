"""Application exit codes (``SystemExit`` argument)."""

from __future__ import annotations

from enum import IntEnum


class AppExitCode(IntEnum):
    """Exit reasons for the IAM service process."""

    SUCCESS = 0
    CONFIG_LOAD_FAILED = 10
    STARTUP_VALIDATION_FAILED = 11
    DATABASE_VALIDATION_FAILED = 12
    DEPLOYMENT_ADMIN_BOOTSTRAP_FAILED = 13
    GRPC_SERVER_FAILED = 14
    INTERRUPTED = 143

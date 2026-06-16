"""Log structured failures and exit with ``AppExitCode``."""

from __future__ import annotations

import logging
from typing import NoReturn

from iam_service.core.errors import AppError
from iam_service.util.exit_codes import AppExitCode


def exit_on_failure(
    *,
    code: AppExitCode,
    err: AppError,
    logger: logging.Logger,
) -> NoReturn:
    logger.error(
        "Application exit exit_code=%s (%s) error_code=%s message=%s",
        int(code),
        code.name,
        err.code,
        err.message,
    )
    if err.detail:
        logger.error("exit detail: %s", err.detail)
    raise SystemExit(int(code))

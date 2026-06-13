"""Normalize asyncpg failures into ``AppError`` for gRPC mapping."""

from __future__ import annotations

import asyncpg

from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure


def failure_from_pg_sdk(message: str, exc: BaseException) -> Failure[None, AppError]:
    """Map ``asyncpg.PostgresError`` / ``OSError`` from repositories to ``Failure``."""
    if isinstance(exc, asyncpg.PostgresError):
        detail = getattr(exc, "message", None) or str(exc)
        sqlstate = getattr(exc, "sqlstate", None)
        rendered = f"{sqlstate}: {detail}" if sqlstate else str(detail)
        return Failure(
            AppError(
                code=ErrorCodes.UPSTREAM,
                message=message,
                detail=rendered,
            ),
        )
    if isinstance(exc, OSError):
        return Failure(
            AppError(
                code=ErrorCodes.UPSTREAM,
                message=message,
                detail=str(exc),
            ),
        )
    return Failure(
        AppError(
            code=ErrorCodes.INTERNAL,
            message=message,
            detail=str(exc),
        ),
    )

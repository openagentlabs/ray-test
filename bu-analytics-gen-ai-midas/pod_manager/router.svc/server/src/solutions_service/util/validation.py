"""Startup validation (configuration and Postgres connectivity)."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

from solutions_service.core.app_config import AppConfig
from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success
from solutions_service.postgres.context import PostgresContext

logger = logging.getLogger(__name__)

DATABASE_RETRY_ATTEMPTS = 3
DATABASE_RETRY_DELAY_SEC = 1.0


async def validate(app_config: AppConfig) -> Result[None, AppError]:
    """Validate that the Postgres DSN is configured before connecting."""
    has_inline_dsn = bool(app_config.postgres.dsn.strip())
    has_rds_secret_config = bool((os.getenv("AWS_RDS_POSTGRES_SECRET_ID") or "").strip())
    if not has_inline_dsn and not has_rds_secret_config:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message=(
                    "Postgres DSN is required "
                    "(set DATABASE_URL / [postgres].dsn or AWS_RDS_POSTGRES_SECRET_ID)."
                ),
                detail=None,
            ),
        )
    logger.info(
        "startup validate: Postgres table_prefix=%s pool=%s-%s",
        app_config.postgres.table_prefix,
        app_config.postgres.pool_min,
        app_config.postgres.pool_max,
    )
    return Success(None)


async def validate_database(pg: PostgresContext) -> Result[None, AppError]:
    return await _validate_database_with_retries(pg.check_conn)


async def _validate_database_with_retries(
    check_conn: Callable[[], Awaitable[Result[None, AppError]]],
) -> Result[None, AppError]:
    last: AppError | None = None
    for attempt in range(1, DATABASE_RETRY_ATTEMPTS + 1):
        logger.info("database validation attempt %s/%s", attempt, DATABASE_RETRY_ATTEMPTS)
        result = await check_conn()
        if isinstance(result, Success):
            logger.info(
                "database validation attempt %s/%s succeeded",
                attempt,
                DATABASE_RETRY_ATTEMPTS,
            )
            return result
        last = result.failure()
        logger.warning(
            "database validation attempt %s/%s failed: %s",
            attempt,
            DATABASE_RETRY_ATTEMPTS,
            last.message,
        )
        if attempt < DATABASE_RETRY_ATTEMPTS:
            await asyncio.sleep(DATABASE_RETRY_DELAY_SEC)
    assert last is not None
    logger.error(
        "database validation failed after %s attempts: %s",
        DATABASE_RETRY_ATTEMPTS,
        last.message,
    )
    return Failure(last)

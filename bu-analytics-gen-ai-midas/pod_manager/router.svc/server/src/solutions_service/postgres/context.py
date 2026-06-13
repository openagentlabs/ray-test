"""Postgres connection pool lifecycle for repositories."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import asyncpg

from solutions_service.core.app_config import AppConfig
from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success
from solutions_service.postgres.rds_dsn import resolve_dsn_from_rds_env

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PostgresContext:
    """Holds the shared asyncpg connection pool."""

    pool: asyncpg.Pool

    @staticmethod
    async def from_app_config(app_config: AppConfig) -> Result[PostgresContext, AppError]:
        """Create the connection pool from ``[postgres]`` config.

        Args:
            app_config: Loaded application configuration.

        Returns:
            ``Success(PostgresContext)`` when the pool connects, otherwise
            ``Failure(AppError)`` (missing DSN or connection error).
        """
        dsn = app_config.postgres.dsn.strip()
        if not dsn:
            dsn = resolve_dsn_from_rds_env()
        if not dsn:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message=(
                        "Postgres DSN is required "
                        "(set DATABASE_URL / [postgres].dsn or AWS_RDS_POSTGRES_* env vars)."
                    ),
                    detail=None,
                ),
            )
        try:
            pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=app_config.postgres.pool_min,
                max_size=app_config.postgres.pool_max,
                command_timeout=app_config.postgres.command_timeout_sec,
                server_settings={"search_path": app_config.postgres.schema_name},
            )
        except (asyncpg.PostgresError, OSError) as exc:
            logger.warning("postgres_pool_create_failed: %s", exc)
            return Failure(
                AppError(
                    code=ErrorCodes.UPSTREAM,
                    message="Could not connect to Postgres.",
                    detail=str(exc),
                ),
            )
        if pool is None:  # pragma: no cover - defensive; create_pool returns a Pool
            return Failure(
                AppError(
                    code=ErrorCodes.UPSTREAM,
                    message="Postgres pool creation returned no pool.",
                    detail=None,
                ),
            )
        return Success(PostgresContext(pool=pool))

    async def check_conn(self) -> Result[None, AppError]:
        """Verify Postgres access with a trivial ``SELECT 1``."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
        except (asyncpg.PostgresError, OSError) as exc:
            logger.warning("postgres check_conn failed: %s", exc)
            return Failure(
                AppError(
                    code=ErrorCodes.UPSTREAM,
                    message="Postgres connectivity check failed.",
                    detail=str(exc),
                ),
            )
        return Success(None)

    async def close(self) -> None:
        """Close the connection pool."""
        await self.pool.close()

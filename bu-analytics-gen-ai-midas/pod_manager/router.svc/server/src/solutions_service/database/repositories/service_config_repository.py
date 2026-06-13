"""``service_config`` Postgres repository."""

from __future__ import annotations

import asyncpg
from pydantic import ValidationError

from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success
from solutions_service.core.table_names import safe_identifier
from solutions_service.database.models.service_config_records import ServiceConfigRecord
from solutions_service.database.pg_errors import failure_from_pg_sdk

_COLUMNS = "config_key, value, updated_at, description"


class ServiceConfigRepository:
    __slots__ = ("_pool", "_table")

    def __init__(self, *, pool: asyncpg.Pool, table_name: str) -> None:
        self._pool = pool
        self._table = safe_identifier(table_name)

    async def get(self, *, config_key: str) -> Result[ServiceConfigRecord | None, AppError]:
        query = f"SELECT {_COLUMNS} FROM {self._table} WHERE config_key = $1"  # noqa: S608
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, config_key)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres select failed for service_config.", exc)
        if row is None:
            return Success(None)
        try:
            return Success(ServiceConfigRecord.model_validate(dict(row)))
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Invalid service_config row in Postgres.",
                    detail=str(exc),
                ),
            )

    async def put(self, record: ServiceConfigRecord) -> Result[None, AppError]:
        query = (
            f"INSERT INTO {self._table} ({_COLUMNS}) "  # noqa: S608
            "VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (config_key) DO UPDATE SET "
            "value = EXCLUDED.value, "
            "updated_at = EXCLUDED.updated_at, "
            "description = EXCLUDED.description"
        )
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    record.config_key,
                    record.value,
                    record.updated_at,
                    record.description,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres upsert failed for service_config.", exc)
        return Success(None)

    async def delete(self, *, config_key: str) -> Result[None, AppError]:
        query = f"DELETE FROM {self._table} WHERE config_key = $1"  # noqa: S608
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(query, config_key)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres delete failed for service_config.", exc)
        return Success(None)

    async def scan_all(self) -> Result[list[ServiceConfigRecord], AppError]:
        query = f"SELECT {_COLUMNS} FROM {self._table}"  # noqa: S608
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres scan failed for service_config.", exc)
        out: list[ServiceConfigRecord] = []
        for row in rows:
            try:
                out.append(ServiceConfigRecord.model_validate(dict(row)))
            except ValidationError as exc:
                return Failure(
                    AppError(
                        code=ErrorCodes.INTERNAL,
                        message="Invalid service_config row in Postgres.",
                        detail=str(exc),
                    ),
                )
        return Success(out)

"""``user_assignments`` Postgres repository."""

from __future__ import annotations

import asyncpg
from pydantic import ValidationError

from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success
from solutions_service.core.table_names import safe_identifier
from solutions_service.database.models.pod_records import UserAssignmentRecord
from solutions_service.database.pg_errors import failure_from_pg_sdk

_COLUMNS = "sub, pod_id, pod_dns, pool, assignment_epoch, updated_at"


class UserAssignmentRepository:
    __slots__ = ("_pool", "_table")

    def __init__(self, *, pool: asyncpg.Pool, table_name: str) -> None:
        self._pool = pool
        self._table = safe_identifier(table_name)

    async def get_by_sub(self, *, sub: str) -> Result[UserAssignmentRecord | None, AppError]:
        query = f"SELECT {_COLUMNS} FROM {self._table} WHERE sub = $1"  # noqa: S608
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, sub)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres select failed for user_assignments.", exc)
        if row is None:
            return Success(None)
        try:
            return Success(UserAssignmentRecord.model_validate(dict(row)))
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Invalid user_assignments row in Postgres.",
                    detail=str(exc),
                ),
            )

    async def put(self, record: UserAssignmentRecord) -> Result[None, AppError]:
        query = (
            f"INSERT INTO {self._table} ({_COLUMNS}) "  # noqa: S608
            "VALUES ($1, $2, $3, $4, $5, $6) "
            "ON CONFLICT (sub) DO UPDATE SET "
            "pod_id = EXCLUDED.pod_id, "
            "pod_dns = EXCLUDED.pod_dns, "
            "pool = EXCLUDED.pool, "
            "assignment_epoch = EXCLUDED.assignment_epoch, "
            "updated_at = EXCLUDED.updated_at"
        )
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    record.sub,
                    record.pod_id,
                    record.pod_dns,
                    record.pool,
                    record.assignment_epoch,
                    record.updated_at,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres upsert failed for user_assignments.", exc)
        return Success(None)

    async def scan_all(self) -> Result[list[UserAssignmentRecord], AppError]:
        query = f"SELECT {_COLUMNS} FROM {self._table}"  # noqa: S608
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres scan failed for user_assignments.", exc)
        out: list[UserAssignmentRecord] = []
        for row in rows:
            try:
                out.append(UserAssignmentRecord.model_validate(dict(row)))
            except ValidationError as exc:
                return Failure(
                    AppError(
                        code=ErrorCodes.INTERNAL,
                        message="Invalid user_assignments row in Postgres.",
                        detail=str(exc),
                    ),
                )
        return Success(out)

    async def delete(self, *, sub: str) -> Result[None, AppError]:
        query = f"DELETE FROM {self._table} WHERE sub = $1"  # noqa: S608
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(query, sub)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres delete failed for user_assignments.", exc)
        return Success(None)

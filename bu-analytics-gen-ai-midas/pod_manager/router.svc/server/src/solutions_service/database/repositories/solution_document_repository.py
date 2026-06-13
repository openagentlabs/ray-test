"""Solution documents table repository (PK ``id``)."""

from __future__ import annotations

import asyncpg
from pydantic import ValidationError

from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success
from solutions_service.core.table_names import safe_identifier
from solutions_service.database.models.records import SolutionDocumentRecord
from solutions_service.database.pg_errors import failure_from_pg_sdk

_COLUMNS = (
    "id, created_at, updated_at, deleted_at, is_deleted, solution_id, name, description, path"
)
_ACTIVE_FILTER = " AND is_deleted = FALSE"


class SolutionDocumentRepository:
    """Persist solution document items in Postgres."""

    __slots__ = ("_pool", "_table")

    def __init__(self, *, pool: asyncpg.Pool, table_name: str) -> None:
        self._pool = pool
        self._table = safe_identifier(table_name)

    async def get_by_id(
        self,
        *,
        item_id: str,
        include_deleted: bool,
    ) -> Result[SolutionDocumentRecord | None, AppError]:
        query = f"SELECT {_COLUMNS} FROM {self._table} WHERE id = $1"  # noqa: S608
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, item_id)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres select failed for solution document.", exc)
        if row is None:
            return Success(None)
        try:
            rec = SolutionDocumentRecord.model_validate(dict(row))
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Stored solution document record is invalid.",
                    detail=str(exc),
                ),
            )
        if not include_deleted and rec.is_deleted:
            return Success(None)
        return Success(rec)

    async def put(self, record: SolutionDocumentRecord) -> Result[None, AppError]:
        query = (
            f"INSERT INTO {self._table} ({_COLUMNS}) "  # noqa: S608
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
            "ON CONFLICT (id) DO UPDATE SET "
            "created_at = EXCLUDED.created_at, "
            "updated_at = EXCLUDED.updated_at, "
            "deleted_at = EXCLUDED.deleted_at, "
            "is_deleted = EXCLUDED.is_deleted, "
            "solution_id = EXCLUDED.solution_id, "
            "name = EXCLUDED.name, "
            "description = EXCLUDED.description, "
            "path = EXCLUDED.path"
        )
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    record.id,
                    record.created_at,
                    record.updated_at,
                    record.deleted_at,
                    record.is_deleted,
                    record.solution_id,
                    record.name,
                    record.description,
                    record.path,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres upsert failed for solution document.", exc)
        return Success(None)

    async def soft_delete(
        self,
        *,
        item_id: str,
        now_iso: str,
    ) -> Result[SolutionDocumentRecord | None, AppError]:
        got = await self.get_by_id(item_id=item_id, include_deleted=True)
        if isinstance(got, Failure):
            return got
        existing = got.unwrap()
        if existing is None:
            return Success(None)
        updated = existing.model_copy(
            update={"is_deleted": True, "deleted_at": now_iso, "updated_at": now_iso},
        )
        put = await self.put(updated)
        if isinstance(put, Failure):
            return put
        return Success(updated)

    async def list_by_solution(
        self,
        *,
        solution_id: str,
        include_deleted: bool,
    ) -> Result[list[SolutionDocumentRecord], AppError]:
        active = "" if include_deleted else _ACTIVE_FILTER
        query = (
            f"SELECT {_COLUMNS} FROM {self._table} "  # noqa: S608
            f"WHERE solution_id = $1{active} ORDER BY updated_at DESC"
        )
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, solution_id)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres query failed for solution documents.", exc)
        out: list[SolutionDocumentRecord] = []
        for row in rows:
            try:
                out.append(SolutionDocumentRecord.model_validate(dict(row)))
            except ValidationError as exc:
                return Failure(
                    AppError(
                        code=ErrorCodes.INTERNAL,
                        message="Stored solution document record is invalid.",
                        detail=str(exc),
                    ),
                )
        return Success(out)

    async def count_by_solution(
        self,
        *,
        solution_id: str,
        include_deleted: bool,
    ) -> Result[int, AppError]:
        active = "" if include_deleted else _ACTIVE_FILTER
        query = (
            f"SELECT COUNT(*) FROM {self._table} "  # noqa: S608
            f"WHERE solution_id = $1{active}"
        )
        try:
            async with self._pool.acquire() as conn:
                total = await conn.fetchval(query, solution_id)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres count query failed for solution documents.", exc)
        return Success(int(total or 0))

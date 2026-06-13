"""Postgres repository for a pool node registry table (``pm_backend_pool`` or ``pm_login_pod_pool``)."""

from __future__ import annotations

import asyncpg
from pydantic import ValidationError

from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success
from solutions_service.core.table_names import safe_identifier
from solutions_service.database.models.pod_records import (
    NODE_STATE_FREE,
    BackendPoolNodeRecord,
)
from solutions_service.database.pg_errors import failure_from_pg_sdk

_COLUMNS = "pod_id, pod_dns, state, assigned_sub, assignment_epoch, updated_at"


class BackendPoolRepository:
    __slots__ = ("_pool", "_table")

    def __init__(self, *, pool: asyncpg.Pool, table_name: str) -> None:
        self._pool = pool
        self._table = safe_identifier(table_name)

    async def get_by_id(self, *, pod_id: str) -> Result[BackendPoolNodeRecord | None, AppError]:
        query = f"SELECT {_COLUMNS} FROM {self._table} WHERE pod_id = $1"  # noqa: S608
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, pod_id)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk(
                f"Postgres select failed for {self._table}.",
                exc,
            )
        if row is None:
            return Success(None)
        try:
            return Success(BackendPoolNodeRecord.model_validate(dict(row)))
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message=f"Invalid row in {self._table}.",
                    detail=str(exc),
                ),
            )

    async def put(self, record: BackendPoolNodeRecord) -> Result[None, AppError]:
        query = (
            f"INSERT INTO {self._table} ({_COLUMNS}) "  # noqa: S608
            "VALUES ($1, $2, $3, $4, $5, $6) "
            "ON CONFLICT (pod_id) DO UPDATE SET "
            "pod_dns = EXCLUDED.pod_dns, "
            "state = EXCLUDED.state, "
            "assigned_sub = EXCLUDED.assigned_sub, "
            "assignment_epoch = EXCLUDED.assignment_epoch, "
            "updated_at = EXCLUDED.updated_at"
        )
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    record.pod_id,
                    record.pod_dns,
                    record.state,
                    record.assigned_sub,
                    record.assignment_epoch,
                    record.updated_at,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk(
                f"Postgres upsert failed for {self._table}.",
                exc,
            )
        return Success(None)

    async def delete(self, *, pod_id: str) -> Result[None, AppError]:
        query = f"DELETE FROM {self._table} WHERE pod_id = $1"  # noqa: S608
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(query, pod_id)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk(
                f"Postgres delete failed for {self._table}.",
                exc,
            )
        return Success(None)

    async def scan_all(self) -> Result[list[BackendPoolNodeRecord], AppError]:
        query = f"SELECT {_COLUMNS} FROM {self._table}"  # noqa: S608
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk(
                f"Postgres scan failed for {self._table}.",
                exc,
            )
        return _rows_to_records(rows, table=self._table)

    async def list_free_pods(self) -> Result[list[BackendPoolNodeRecord], AppError]:
        query = f"SELECT {_COLUMNS} FROM {self._table} WHERE state = $1"  # noqa: S608
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, NODE_STATE_FREE)
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk(
                f"Postgres query failed for free nodes in {self._table}.",
                exc,
            )
        return _rows_to_records(rows, table=self._table)


def _rows_to_records(
    rows: list[asyncpg.Record],
    *,
    table: str,
) -> Result[list[BackendPoolNodeRecord], AppError]:
    records: list[BackendPoolNodeRecord] = []
    for row in rows:
        try:
            records.append(BackendPoolNodeRecord.model_validate(dict(row)))
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message=f"Invalid row in {table}.",
                    detail=str(exc),
                ),
            )
    return Success(records)


PodPoolRepository = BackendPoolRepository

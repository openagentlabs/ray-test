"""``assignment_events`` Postgres repository."""

from __future__ import annotations

import asyncpg

from solutions_service.core.errors import AppError
from solutions_service.core.results import Result, Success
from solutions_service.core.table_names import safe_identifier
from solutions_service.database.models.assignment_event_records import AssignmentEventRecord
from solutions_service.database.pg_errors import failure_from_pg_sdk

_COLUMNS = "event_id, sub, pod_id, event_type, timestamp, assignment_epoch"


class AssignmentEventsRepository:
    __slots__ = ("_pool", "_table")

    def __init__(self, *, pool: asyncpg.Pool, table_name: str) -> None:
        self._pool = pool
        self._table = safe_identifier(table_name)

    async def put(self, record: AssignmentEventRecord) -> Result[None, AppError]:
        query = (
            f"INSERT INTO {self._table} ({_COLUMNS}) "  # noqa: S608
            "VALUES ($1, $2, $3, $4, $5, $6) "
            "ON CONFLICT (event_id) DO NOTHING"
        )
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    record.event_id,
                    record.sub,
                    record.pod_id,
                    record.event_type,
                    record.timestamp,
                    record.assignment_epoch,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres insert failed for assignment_events.", exc)
        return Success(None)

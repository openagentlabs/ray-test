"""Postgres schema bootstrap for routing-tier tables (``CREATE TABLE IF NOT EXISTS``)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import asyncpg

from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Result, Success
from solutions_service.core.table_names import safe_identifier
from solutions_service.database.pg_errors import failure_from_pg_sdk

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RoutingTableNames:
    """Dedicated schema plus physical table names for the routing-tier control plane."""

    schema: str
    backend_pool: str
    login_pod_pool: str
    user_assignments: str
    assignment_events: str
    solution_documents: str
    service_config: str


_REQUIRED_TABLE_COLUMNS: dict[str, dict[str, tuple[str, bool]]] = {
    "backend_pool": {
        "pod_id": ("text", False),
        "pod_dns": ("text", False),
        "state": ("text", False),
        "assigned_sub": ("text", False),
        "assignment_epoch": ("bigint", False),
        "updated_at": ("text", False),
    },
    "login_pod_pool": {
        "pod_id": ("text", False),
        "pod_dns": ("text", False),
        "state": ("text", False),
        "assigned_sub": ("text", False),
        "assignment_epoch": ("bigint", False),
        "updated_at": ("text", False),
    },
    "user_assignments": {
        "sub": ("text", False),
        "pod_id": ("text", False),
        "pod_dns": ("text", False),
        "pool": ("text", False),
        "assignment_epoch": ("bigint", False),
        "updated_at": ("text", False),
    },
    "assignment_events": {
        "event_id": ("text", False),
        "sub": ("text", False),
        "pod_id": ("text", False),
        "event_type": ("text", False),
        "timestamp": ("text", False),
        "assignment_epoch": ("bigint", False),
    },
    "solution_documents": {
        "id": ("text", False),
        "created_at": ("text", False),
        "updated_at": ("text", False),
        "deleted_at": ("text", False),
        "is_deleted": ("boolean", False),
        "solution_id": ("text", False),
        "name": ("text", False),
        "description": ("text", False),
        "path": ("text", False),
    },
    "service_config": {
        "config_key": ("text", False),
        "value": ("text", False),
        "updated_at": ("text", False),
        "description": ("text", False),
    },
}


def _pool_table_ddl(table: str) -> tuple[str, str]:
    """Return ``(create_table, create_state_index)`` DDL for a pool registry table."""
    name = safe_identifier(table)
    create = (
        f"CREATE TABLE IF NOT EXISTS {name} ("  # noqa: S608 - name is validated
        "pod_id TEXT PRIMARY KEY, "
        "pod_dns TEXT NOT NULL, "
        "state TEXT NOT NULL DEFAULT 'free', "
        "assigned_sub TEXT NOT NULL DEFAULT '', "
        "assignment_epoch BIGINT NOT NULL DEFAULT 0, "
        "updated_at TEXT NOT NULL"
        ")"
    )
    index = f"CREATE INDEX IF NOT EXISTS {name}_state_idx ON {name} (state)"  # noqa: S608
    return create, index


def _user_assignments_ddl(table: str) -> tuple[str, str]:
    name = safe_identifier(table)
    create = (
        f"CREATE TABLE IF NOT EXISTS {name} ("  # noqa: S608 - name is validated
        "sub TEXT PRIMARY KEY, "
        "pod_id TEXT NOT NULL, "
        "pod_dns TEXT NOT NULL, "
        "pool TEXT NOT NULL DEFAULT 'backend_pool', "
        "assignment_epoch BIGINT NOT NULL, "
        "updated_at TEXT NOT NULL"
        ")"
    )
    index = f"CREATE INDEX IF NOT EXISTS {name}_pod_id_idx ON {name} (pod_id)"  # noqa: S608
    return create, index


def _assignment_events_ddl(table: str) -> str:
    name = safe_identifier(table)
    return (
        f"CREATE TABLE IF NOT EXISTS {name} ("  # noqa: S608 - name is validated
        "event_id TEXT PRIMARY KEY, "
        "sub TEXT NOT NULL, "
        "pod_id TEXT NOT NULL DEFAULT '', "
        "event_type TEXT NOT NULL, "
        "timestamp TEXT NOT NULL, "
        "assignment_epoch BIGINT NOT NULL DEFAULT 0"
        ")"
    )


def _solution_documents_ddl(table: str) -> tuple[str, str]:
    name = safe_identifier(table)
    create = (
        f"CREATE TABLE IF NOT EXISTS {name} ("  # noqa: S608 - name is validated
        "id TEXT PRIMARY KEY, "
        "created_at TEXT NOT NULL, "
        "updated_at TEXT NOT NULL, "
        "deleted_at TEXT NOT NULL DEFAULT '', "
        "is_deleted BOOLEAN NOT NULL DEFAULT FALSE, "
        "solution_id TEXT NOT NULL, "
        "name TEXT NOT NULL, "
        "description TEXT NOT NULL DEFAULT '', "
        "path TEXT NOT NULL"
        ")"
    )
    index = f"CREATE INDEX IF NOT EXISTS {name}_solution_id_idx ON {name} (solution_id)"  # noqa: S608
    return create, index


def _service_config_ddl(table: str) -> str:
    name = safe_identifier(table)
    return (
        f"CREATE TABLE IF NOT EXISTS {name} ("  # noqa: S608 - name is validated
        "config_key TEXT PRIMARY KEY, "
        "value TEXT NOT NULL DEFAULT '', "
        "updated_at TEXT NOT NULL, "
        "description TEXT NOT NULL DEFAULT ''"
        ")"
    )


async def create_schema(pool: asyncpg.Pool, tables: RoutingTableNames) -> Result[None, AppError]:
    """Create all routing-tier tables and indexes if they do not already exist.

    Args:
        pool: Connected asyncpg pool.
        tables: Physical table names to create.

    Returns:
        ``Success(None)`` once the schema exists, ``Failure(AppError)`` on a DB error.
    """
    schema = safe_identifier(tables.schema)
    backend_create, backend_index = _pool_table_ddl(tables.backend_pool)
    login_create, login_index = _pool_table_ddl(tables.login_pod_pool)
    assignments_create, assignments_index = _user_assignments_ddl(tables.user_assignments)
    documents_create, documents_index = _solution_documents_ddl(tables.solution_documents)
    statements: list[str] = [
        f"CREATE SCHEMA IF NOT EXISTS {schema}",  # noqa: S608 - schema is validated
        backend_create,
        backend_index,
        login_create,
        login_index,
        assignments_create,
        assignments_index,
        _assignment_events_ddl(tables.assignment_events),
        documents_create,
        documents_index,
        _service_config_ddl(tables.service_config),
    ]
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                for statement in statements:
                    await conn.execute(statement)
    except (asyncpg.PostgresError, OSError) as exc:
        return failure_from_pg_sdk("Failed to bootstrap Postgres schema.", exc)
    logger.info("postgres_schema_ready tables=%s", tables)
    return Success(None)


async def validate_schema_contract(pool: asyncpg.Pool, tables: RoutingTableNames) -> Result[None, AppError]:
    """Validate required tables/columns/types exist after bootstrap.

    This catches drift where a table already exists with an incompatible shape:
    ``CREATE TABLE IF NOT EXISTS`` does not alter such tables.
    """
    table_map = {
        "backend_pool": tables.backend_pool,
        "login_pod_pool": tables.login_pod_pool,
        "user_assignments": tables.user_assignments,
        "assignment_events": tables.assignment_events,
        "solution_documents": tables.solution_documents,
        "service_config": tables.service_config,
    }
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = $1
                  AND table_name = ANY($2::text[])
                """,
                tables.schema,
                list(table_map.values()),
            )
    except (asyncpg.PostgresError, OSError) as exc:
        return failure_from_pg_sdk("Failed to read Postgres schema metadata.", exc)

    actual: dict[str, dict[str, tuple[str, bool]]] = {}
    for row in rows:
        table_name = str(row["table_name"])
        column_name = str(row["column_name"])
        data_type = str(row["data_type"])
        nullable = str(row["is_nullable"]) == "YES"
        actual.setdefault(table_name, {})[column_name] = (data_type, nullable)

    mismatches: list[str] = []
    for logical_table, required_columns in _REQUIRED_TABLE_COLUMNS.items():
        physical_table = table_map[logical_table]
        actual_columns = actual.get(physical_table, {})
        if not actual_columns:
            mismatches.append(f"{physical_table}: missing table")
            continue
        for column_name, expected_spec in required_columns.items():
            expected_data_type, expected_nullable = expected_spec
            observed_spec = actual_columns.get(column_name)
            if observed_spec is None:
                mismatches.append(f"{physical_table}.{column_name}: missing column")
                continue
            observed_data_type, observed_nullable = observed_spec
            if observed_data_type != expected_data_type:
                mismatches.append(
                    f"{physical_table}.{column_name}: type={observed_data_type} expected={expected_data_type}"
                )
            if observed_nullable != expected_nullable:
                observed_text = "nullable" if observed_nullable else "not-null"
                expected_text = "nullable" if expected_nullable else "not-null"
                mismatches.append(
                    f"{physical_table}.{column_name}: nullability={observed_text} expected={expected_text}"
                )

    if mismatches:
        detail = "; ".join(mismatches)
        return asyncpg_compat_validation_error(
            "Postgres schema contract mismatch for routing-tier tables.",
            detail,
        )

    logger.info("postgres_schema_contract_validated tables=%s", table_map)
    return Success(None)


def asyncpg_compat_validation_error(message: str, detail: str) -> AppError:
    """Build a validation AppError without DB-driver specific formatting."""
    return AppError(code=ErrorCodes.VALIDATION, message=message, detail=detail)

"""Postgres ``AssignmentStoreDriver`` — wraps routing repositories with SQL transactions."""

from __future__ import annotations

import logging

import asyncpg

from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success
from solutions_service.core.table_names import safe_identifier
from solutions_service.database.models.pod_records import (
    NODE_STATE_CLAIMED,
    NODE_STATE_FREE,
    BackendPoolNodeRecord,
    UserAssignmentRecord,
)
from solutions_service.database.models.pool_kind import BACKEND_POOL, LOGIN_POD_POOL
from solutions_service.database.pg_errors import failure_from_pg_sdk
from solutions_service.database.repositories.backend_pool_repository import BackendPoolRepository
from solutions_service.database.repositories.user_assignment_repository import (
    UserAssignmentRepository,
)

logger = logging.getLogger(__name__)


class _ConflictSignal(Exception):
    """Internal marker raised inside a transaction to force a rollback on conflict."""


class PostgresAssignmentStoreDriver:
    """Production store driver delegating to repositories + atomic SQL transactions."""

    __slots__ = (
        "_pool",
        "_pool_tables",
        "_assignments_table",
        "_pool_repos",
        "_assignments",
    )

    def __init__(
        self,
        *,
        pool: asyncpg.Pool,
        backend_pool_table: str,
        login_pod_pool_table: str,
        user_assignments_table: str,
        backend_pool_repository: BackendPoolRepository,
        login_pod_pool_repository: BackendPoolRepository,
        user_assignment_repository: UserAssignmentRepository,
    ) -> None:
        self._pool = pool
        self._pool_tables = {
            BACKEND_POOL: safe_identifier(backend_pool_table),
            LOGIN_POD_POOL: safe_identifier(login_pod_pool_table),
        }
        self._assignments_table = safe_identifier(user_assignments_table)
        self._pool_repos = {
            BACKEND_POOL: backend_pool_repository,
            LOGIN_POD_POOL: login_pod_pool_repository,
        }
        self._assignments = user_assignment_repository

    def _repo(self, pool: str) -> BackendPoolRepository:
        repo = self._pool_repos.get(pool)
        if repo is None:
            msg = f"Unknown pool: {pool}"
            raise ValueError(msg)
        return repo

    def _table(self, pool: str) -> str:
        table = self._pool_tables.get(pool)
        if table is None:
            msg = f"Unknown pool: {pool}"
            raise ValueError(msg)
        return table

    async def get_assignment_by_sub(
        self,
        *,
        sub: str,
    ) -> Result[UserAssignmentRecord | None, AppError]:
        return await self._assignments.get_by_sub(sub=sub)

    async def put_assignment(self, record: UserAssignmentRecord) -> Result[None, AppError]:
        return await self._assignments.put(record)

    async def delete_assignment(self, *, sub: str) -> Result[None, AppError]:
        return await self._assignments.delete(sub=sub)

    async def get_pod_by_id(
        self,
        *,
        pool: str,
        pod_id: str,
    ) -> Result[BackendPoolNodeRecord | None, AppError]:
        return await self._repo(pool).get_by_id(pod_id=pod_id)

    async def put_pod(
        self,
        *,
        pool: str,
        record: BackendPoolNodeRecord,
    ) -> Result[None, AppError]:
        return await self._repo(pool).put(record)

    async def delete_pod(self, *, pool: str, pod_id: str) -> Result[None, AppError]:
        return await self._repo(pool).delete(pod_id=pod_id)

    async def list_free_pods(self, *, pool: str) -> Result[list[BackendPoolNodeRecord], AppError]:
        return await self._repo(pool).list_free_pods()

    async def scan_all_pods(self, *, pool: str) -> Result[list[BackendPoolNodeRecord], AppError]:
        return await self._repo(pool).scan_all()

    async def transact_claim(
        self,
        *,
        assignment: UserAssignmentRecord,
        claimed_pod: BackendPoolNodeRecord,
    ) -> Result[None, AppError]:
        if claimed_pod.state != NODE_STATE_CLAIMED:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="transact_claim requires claimed pod state.",
                    detail=None,
                ),
            )
        pool_table = self._table(assignment.pool)
        insert_assignment = (
            f"INSERT INTO {self._assignments_table} "  # noqa: S608
            "(sub, pod_id, pod_dns, pool, assignment_epoch, updated_at) "
            "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (sub) DO NOTHING"
        )
        claim_pod = (
            f"UPDATE {pool_table} SET "  # noqa: S608
            "state = $1, assigned_sub = $2, assignment_epoch = $3, updated_at = $4 "
            "WHERE pod_id = $5 AND state = $6"
        )
        try:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    inserted = await conn.execute(
                        insert_assignment,
                        assignment.sub,
                        assignment.pod_id,
                        assignment.pod_dns,
                        assignment.pool,
                        assignment.assignment_epoch,
                        assignment.updated_at,
                    )
                    if inserted == "INSERT 0 0":
                        raise _ConflictSignal
                    updated = await conn.execute(
                        claim_pod,
                        NODE_STATE_CLAIMED,
                        claimed_pod.assigned_sub,
                        claimed_pod.assignment_epoch,
                        claimed_pod.updated_at,
                        claimed_pod.pod_id,
                        NODE_STATE_FREE,
                    )
                    if updated == "UPDATE 0":
                        raise _ConflictSignal
        except _ConflictSignal:
            return Failure(
                AppError(
                    code=ErrorCodes.CONFLICT,
                    message="Assignment transaction conflict.",
                    detail=None,
                ),
            )
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres claim transaction failed.", exc)
        return Success(None)

    async def transact_release(
        self,
        *,
        sub: str,
        pool: str,
        freed_pod: BackendPoolNodeRecord | None,
    ) -> Result[None, AppError]:
        delete_assignment = (
            f"DELETE FROM {self._assignments_table} WHERE sub = $1"  # noqa: S608
        )
        free_pod = (
            f"INSERT INTO {self._table(pool)} "  # noqa: S608
            "(pod_id, pod_dns, state, assigned_sub, assignment_epoch, updated_at) "
            "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (pod_id) DO UPDATE SET "
            "pod_dns = EXCLUDED.pod_dns, state = EXCLUDED.state, "
            "assigned_sub = EXCLUDED.assigned_sub, "
            "assignment_epoch = EXCLUDED.assignment_epoch, updated_at = EXCLUDED.updated_at"
        )
        try:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    deleted = await conn.execute(delete_assignment, sub)
                    if deleted == "DELETE 0":
                        raise _ConflictSignal
                    if freed_pod is not None:
                        await conn.execute(
                            free_pod,
                            freed_pod.pod_id,
                            freed_pod.pod_dns,
                            freed_pod.state,
                            freed_pod.assigned_sub,
                            freed_pod.assignment_epoch,
                            freed_pod.updated_at,
                        )
        except _ConflictSignal:
            return Failure(
                AppError(
                    code=ErrorCodes.CONFLICT,
                    message="Assignment transaction conflict.",
                    detail=None,
                ),
            )
        except (asyncpg.PostgresError, OSError) as exc:
            return failure_from_pg_sdk("Postgres release transaction failed.", exc)
        return Success(None)

"""Assignment store driver protocol — routing tables (DB-1)."""

from __future__ import annotations

from typing import Protocol

from solutions_service.core.errors import AppError
from solutions_service.core.results import Result
from solutions_service.database.models.pod_records import BackendPoolNodeRecord, UserAssignmentRecord


class AssignmentStoreDriver(Protocol):
    """Backend pool, login pod pool registry, and user assignment persistence."""

    async def get_assignment_by_sub(
        self,
        *,
        sub: str,
    ) -> Result[UserAssignmentRecord | None, AppError]:
        ...

    async def put_assignment(self, record: UserAssignmentRecord) -> Result[None, AppError]:
        ...

    async def delete_assignment(self, *, sub: str) -> Result[None, AppError]:
        ...

    async def get_pod_by_id(
        self,
        *,
        pool: str,
        pod_id: str,
    ) -> Result[BackendPoolNodeRecord | None, AppError]:
        ...

    async def put_pod(
        self,
        *,
        pool: str,
        record: BackendPoolNodeRecord,
    ) -> Result[None, AppError]:
        ...

    async def delete_pod(self, *, pool: str, pod_id: str) -> Result[None, AppError]:
        ...

    async def list_free_pods(self, *, pool: str) -> Result[list[BackendPoolNodeRecord], AppError]:
        ...

    async def scan_all_pods(self, *, pool: str) -> Result[list[BackendPoolNodeRecord], AppError]:
        ...

    async def transact_claim(
        self,
        *,
        assignment: UserAssignmentRecord,
        claimed_pod: BackendPoolNodeRecord,
    ) -> Result[None, AppError]:
        """Atomic claim (FR-3); writes assignment + node in ``assignment.pool`` table."""

    async def transact_release(
        self,
        *,
        sub: str,
        pool: str,
        freed_pod: BackendPoolNodeRecord | None,
    ) -> Result[None, AppError]:
        """Atomic release (FR-3, FR-7)."""

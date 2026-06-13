"""In-memory assignment store for unit tests."""

from __future__ import annotations

from copy import deepcopy

from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success
from solutions_service.database.models.pool_kind import BACKEND_POOL, LOGIN_POD_POOL
from solutions_service.database.models.pod_records import (
    NODE_STATE_FREE,
    BackendPoolNodeRecord,
    UserAssignmentRecord,
)


class FakeAssignmentStoreDriver:
    """Dict-backed backend_pool, login_pod_pool registry, and assignments."""

    __slots__ = ("_pods_by_pool", "_assignments")

    def __init__(self) -> None:
        self._pods_by_pool: dict[str, dict[str, BackendPoolNodeRecord]] = {
            BACKEND_POOL: {},
            LOGIN_POD_POOL: {},
        }
        self._assignments: dict[str, UserAssignmentRecord] = {}

    async def get_assignment_by_sub(
        self,
        *,
        sub: str,
    ) -> Result[UserAssignmentRecord | None, AppError]:
        return Success(self._assignments.get(sub))

    async def put_assignment(self, record: UserAssignmentRecord) -> Result[None, AppError]:
        self._assignments[record.sub] = deepcopy(record)
        return Success(None)

    async def delete_assignment(self, *, sub: str) -> Result[None, AppError]:
        self._assignments.pop(sub, None)
        return Success(None)

    async def get_pod_by_id(
        self,
        *,
        pool: str,
        pod_id: str,
    ) -> Result[BackendPoolNodeRecord | None, AppError]:
        pod = self._pods_by_pool.get(pool, {}).get(pod_id)
        return Success(deepcopy(pod) if pod else None)

    async def put_pod(
        self,
        *,
        pool: str,
        record: BackendPoolNodeRecord,
    ) -> Result[None, AppError]:
        self._pods_by_pool.setdefault(pool, {})[record.pod_id] = deepcopy(record)
        return Success(None)

    async def delete_pod(self, *, pool: str, pod_id: str) -> Result[None, AppError]:
        self._pods_by_pool.get(pool, {}).pop(pod_id, None)
        return Success(None)

    async def list_free_pods(self, *, pool: str) -> Result[list[BackendPoolNodeRecord], AppError]:
        pods = self._pods_by_pool.get(pool, {})
        return Success([deepcopy(p) for p in pods.values() if p.state == NODE_STATE_FREE])

    async def scan_all_pods(self, *, pool: str) -> Result[list[BackendPoolNodeRecord], AppError]:
        pods = self._pods_by_pool.get(pool, {})
        return Success([deepcopy(p) for p in pods.values()])

    async def transact_claim(
        self,
        *,
        assignment: UserAssignmentRecord,
        claimed_pod: BackendPoolNodeRecord,
    ) -> Result[None, AppError]:
        if assignment.sub in self._assignments:
            return Failure(
                AppError(
                    code=ErrorCodes.CONFLICT,
                    message="Assignment already exists.",
                    detail=None,
                ),
            )
        pods = self._pods_by_pool.setdefault(assignment.pool, {})
        pod = pods.get(claimed_pod.pod_id)
        if pod is None or pod.state != NODE_STATE_FREE:
            return Failure(
                AppError(
                    code=ErrorCodes.CONFLICT,
                    message="Pod not free for claim.",
                    detail=None,
                ),
            )
        self._assignments[assignment.sub] = deepcopy(assignment)
        pods[claimed_pod.pod_id] = deepcopy(claimed_pod)
        return Success(None)

    async def transact_release(
        self,
        *,
        sub: str,
        pool: str,
        freed_pod: BackendPoolNodeRecord | None,
    ) -> Result[None, AppError]:
        if sub not in self._assignments:
            return Success(None)
        del self._assignments[sub]
        if freed_pod is not None:
            self._pods_by_pool.setdefault(pool, {})[freed_pod.pod_id] = deepcopy(freed_pod)
        return Success(None)

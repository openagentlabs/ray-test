"""Acquire/release lease, pool status, and heartbeat RPC handlers."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from pod_manager.v1 import pool_pb2
from returns.result import Success

from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result
from solutions_service.database.models.assignment_event_records import AssignmentEventRecord
from solutions_service.database.models.pool_kind import ALL_POOL_KINDS, BACKEND_POOL
from solutions_service.database.models.pod_records import (
    NODE_STATE_CLAIMED,
    NODE_STATE_FREE,
    BackendPoolNodeRecord,
    UserAssignmentRecord,
)
from solutions_service.database.repositories.assignment_events_repository import (
    AssignmentEventsRepository,
)
from solutions_service.drivers.store.protocol import AssignmentStoreDriver
from solutions_service.ext_authz.assignment_cache import AssignmentRouteCache

logger = logging.getLogger(__name__)


class PoolRpcHandler:
    """Backend pool leases and pool registry operations."""

    __slots__ = ("_store", "_events", "_route_cache")

    def __init__(
        self,
        *,
        assignment_store: AssignmentStoreDriver,
        assignment_events_repository: AssignmentEventsRepository | None = None,
        route_cache: AssignmentRouteCache | None = None,
    ) -> None:
        self._store = assignment_store
        self._events = assignment_events_repository
        self._route_cache = route_cache

    async def acquire_lease(
        self,
        *,
        sub: str,
    ) -> Result[pool_pb2.AcquireLeaseResponse, AppError]:
        acquired = await self._acquire_backend_lease(sub=sub)
        if isinstance(acquired, Failure):
            return acquired
        pod_id, pod_dns, epoch, already_leased = acquired.unwrap()
        return Success(
            pool_pb2.AcquireLeaseResponse(
                pod_id=pod_id,
                pod_dns=pod_dns,
                assignment_epoch=epoch,
                already_leased=already_leased,
            ),
        )

    async def get_lease(
        self,
        *,
        sub: str,
    ) -> Result[pool_pb2.GetLeaseResponse, AppError]:
        if not sub.strip():
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="sub is required.",
                    detail=None,
                ),
            )
        existing = await self._store.get_assignment_by_sub(sub=sub)
        if isinstance(existing, Failure):
            return existing
        rec = existing.unwrap()
        if rec is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="No backend lease for subject.",
                    detail=None,
                ),
            )
        return Success(
            pool_pb2.GetLeaseResponse(
                pod_id=rec.pod_id,
                pod_dns=rec.pod_dns,
                assignment_epoch=rec.assignment_epoch,
            ),
        )

    async def release_lease(
        self,
        *,
        sub: str,
    ) -> Result[pool_pb2.ReleaseLeaseResponse, AppError]:
        released = await self._release_backend_lease(sub=sub)
        if isinstance(released, Failure):
            return released
        return Success(pool_pb2.ReleaseLeaseResponse())

    async def get_backend_pool_availability(
        self,
    ) -> Result[pool_pb2.GetBackendPoolAvailabilityResponse, AppError]:
        listed = await self._store.scan_all_pods(pool=BACKEND_POOL)
        if isinstance(listed, Failure):
            return listed
        pods = listed.unwrap()
        free_count = sum(1 for p in pods if p.state == NODE_STATE_FREE)
        total_count = len(pods)
        return Success(
            pool_pb2.GetBackendPoolAvailabilityResponse(
                free_count=free_count,
                total_count=total_count,
                has_capacity=free_count > 0,
            ),
        )

    async def _acquire_backend_lease(
        self,
        *,
        sub: str,
    ) -> Result[tuple[str, str, int, bool], AppError]:
        if not sub.strip():
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="sub is required.",
                    detail=None,
                ),
            )
        existing = await self._store.get_assignment_by_sub(sub=sub)
        if isinstance(existing, Failure):
            return existing
        if existing.unwrap() is not None:
            rec = existing.unwrap()
            assert rec is not None
            logger.info("acquire_lease sub=%s pod_id=%s new=false", sub, rec.pod_id)
            return Success((rec.pod_id, rec.pod_dns, rec.assignment_epoch, True))

        free = await self._store.list_free_pods(pool=BACKEND_POOL)
        if isinstance(free, Failure):
            return free
        pods = free.unwrap()
        if not pods:
            return Failure(
                AppError(
                    code=ErrorCodes.RESOURCE_EXHAUSTED,
                    message="No free backend pool pods available for lease.",
                    detail=None,
                ),
            )

        pod = pods[0]
        now = datetime.now(tz=UTC).isoformat()
        epoch = int(datetime.now(tz=UTC).timestamp())
        assignment = UserAssignmentRecord(
            sub=sub,
            pod_id=pod.pod_id,
            pod_dns=pod.pod_dns,
            pool=BACKEND_POOL,
            assignment_epoch=epoch,
            updated_at=now,
        )
        claimed_pod = BackendPoolNodeRecord(
            pod_id=pod.pod_id,
            pod_dns=pod.pod_dns,
            state=NODE_STATE_CLAIMED,
            assigned_sub=sub,
            assignment_epoch=epoch,
            updated_at=now,
        )
        claimed = await self._store.transact_claim(
            assignment=assignment,
            claimed_pod=claimed_pod,
        )
        if isinstance(claimed, Failure):
            err = claimed.failure()
            if err.code == ErrorCodes.CONFLICT:
                return Failure(
                    AppError(
                        code=ErrorCodes.RESOURCE_EXHAUSTED,
                        message="No free backend pool pods available for lease.",
                        detail=None,
                    ),
                )
            return claimed

        if self._route_cache is not None:
            self._route_cache.set(sub=sub, pod_dns=pod.pod_dns, epoch=epoch)
        await self._record_event(
            sub=sub,
            pod_id=pod.pod_id,
            event_type="acquire_lease",
            assignment_epoch=epoch,
        )
        logger.info("acquire_lease sub=%s pod_id=%s new=true", sub, pod.pod_id)
        return Success((pod.pod_id, pod.pod_dns, epoch, False))

    async def _release_backend_lease(self, *, sub: str) -> Result[None, AppError]:
        if not sub.strip():
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="sub is required.",
                    detail=None,
                ),
            )
        assignment_result = await self._store.get_assignment_by_sub(sub=sub)
        if isinstance(assignment_result, Failure):
            return assignment_result
        assignment = assignment_result.unwrap()
        if assignment is None:
            return Success(None)

        now = datetime.now(tz=UTC).isoformat()
        pod_result = await self._store.get_pod_by_id(
            pool=BACKEND_POOL,
            pod_id=assignment.pod_id,
        )
        if isinstance(pod_result, Failure):
            return pod_result
        pod = pod_result.unwrap()
        freed: BackendPoolNodeRecord | None = None
        if pod is not None:
            freed = BackendPoolNodeRecord(
                pod_id=pod.pod_id,
                pod_dns=pod.pod_dns,
                state=NODE_STATE_FREE,
                assigned_sub="",
                assignment_epoch=0,
                updated_at=now,
            )

        released = await self._store.transact_release(
            sub=sub,
            pool=BACKEND_POOL,
            freed_pod=freed,
        )
        if isinstance(released, Failure):
            return released

        if self._route_cache is not None:
            self._route_cache.invalidate(sub=sub)
        await self._record_event(
            sub=sub,
            pod_id=assignment.pod_id,
            event_type="release_lease",
            assignment_epoch=assignment.assignment_epoch,
        )
        logger.info("release_lease sub=%s pod_id=%s", sub, assignment.pod_id)
        return Success(None)

    async def get_pool_status(
        self,
        *,
        pool_filter: str = "",
    ) -> Result[pool_pb2.GetPoolStatusResponse, AppError]:
        pools_result = _pools_for_filter(pool_filter)
        if isinstance(pools_result, Failure):
            return pools_result

        summaries: list[pool_pb2.PodSummary] = []
        free_count = 0
        claimed_count = 0
        for pool in pools_result.unwrap():
            listed = await self._store.scan_all_pods(pool=pool)
            if isinstance(listed, Failure):
                return listed
            for p in listed.unwrap():
                summaries.append(
                    pool_pb2.PodSummary(
                        pod_id=p.pod_id,
                        pod_dns=p.pod_dns,
                        state=p.state,
                        assigned_sub=p.assigned_sub,
                        pool=pool,
                    ),
                )
                if p.state == NODE_STATE_FREE:
                    free_count += 1
                elif p.state == NODE_STATE_CLAIMED:
                    claimed_count += 1

        from solutions_service.observability.metrics import log_pool_gauges

        log_pool_gauges(free_count=free_count, claimed_count=claimed_count)
        return Success(
            pool_pb2.GetPoolStatusResponse(
                pods=summaries,
                free_count=free_count,
                claimed_count=claimed_count,
            ),
        )

    async def heartbeat(
        self,
        *,
        sub: str,
        assignment_epoch: int,
    ) -> Result[pool_pb2.HeartbeatResponse, AppError]:
        if not sub.strip():
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="sub is required.",
                    detail=None,
                ),
            )
        assignment_result = await self._store.get_assignment_by_sub(sub=sub)
        if isinstance(assignment_result, Failure):
            return assignment_result
        assignment = assignment_result.unwrap()
        if assignment is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="No assignment for subject.",
                    detail=None,
                ),
            )
        if assignment.assignment_epoch != assignment_epoch:
            return Failure(
                AppError(
                    code=ErrorCodes.CONFLICT,
                    message="assignment_epoch mismatch.",
                    detail=None,
                ),
            )
        now = datetime.now(tz=UTC).isoformat()
        updated = UserAssignmentRecord(
            sub=assignment.sub,
            pod_id=assignment.pod_id,
            pod_dns=assignment.pod_dns,
            pool=BACKEND_POOL,
            assignment_epoch=assignment.assignment_epoch,
            updated_at=now,
        )
        put = await self._store.put_assignment(updated)
        if isinstance(put, Failure):
            return put
        return Success(
            pool_pb2.HeartbeatResponse(assignment_epoch=assignment.assignment_epoch),
        )

    async def _record_event(
        self,
        *,
        sub: str,
        pod_id: str,
        event_type: str,
        assignment_epoch: int,
    ) -> None:
        if self._events is None:
            return
        now = datetime.now(tz=UTC).isoformat()
        record = AssignmentEventRecord(
            event_id=str(uuid.uuid4()),
            sub=sub,
            pod_id=pod_id,
            event_type=event_type,
            timestamp=now,
            assignment_epoch=assignment_epoch,
        )
        result = await self._events.put(record)
        if isinstance(result, Failure):
            logger.warning(
                "assignment_event_write_failed sub=%s type=%s: %s",
                sub,
                event_type,
                result.failure().message,
            )


def _pools_for_filter(pool_filter: str) -> Result[list[str], AppError]:
    if not pool_filter:
        return Success(list(ALL_POOL_KINDS))
    if pool_filter not in ALL_POOL_KINDS:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message=f"pool must be one of {ALL_POOL_KINDS}.",
                detail=pool_filter,
            ),
        )
    return Success([pool_filter])

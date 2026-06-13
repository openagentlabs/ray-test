"""Idle assignment reaper (OP-4)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from solutions_service.core.app_config import ReaperConfig
from solutions_service.core.results import Failure
from solutions_service.database.models.assignment_event_records import AssignmentEventRecord
from solutions_service.database.models.pod_records import POD_STATE_FREE, BackendPoolNodeRecord
from solutions_service.database.repositories.assignment_events_repository import (
    AssignmentEventsRepository,
)
from solutions_service.database.repositories.user_assignment_repository import (
    UserAssignmentRepository,
)
from solutions_service.drivers.store.protocol import AssignmentStoreDriver
from solutions_service.ext_authz.assignment_cache import AssignmentRouteCache

logger = logging.getLogger(__name__)


class AssignmentReaper:
    """Releases assignments idle longer than configured TTL."""

    __slots__ = (
        "_cfg",
        "_store",
        "_assignments",
        "_events",
        "_route_cache",
        "_interval_sec",
    )

    def __init__(
        self,
        *,
        reaper_config: ReaperConfig,
        assignment_store: AssignmentStoreDriver,
        user_assignment_repository: UserAssignmentRepository,
        assignment_events_repository: AssignmentEventsRepository | None = None,
        route_cache: AssignmentRouteCache | None = None,
    ) -> None:
        self._cfg = reaper_config
        self._store = assignment_store
        self._assignments = user_assignment_repository
        self._events = assignment_events_repository
        self._route_cache = route_cache
        self._interval_sec = reaper_config.interval_sec

    async def run_until_stopped(self, stop: asyncio.Event) -> None:
        logger.info("assignment_reaper_started interval_sec=%s", self._interval_sec)
        while not stop.is_set():
            try:
                await self.reap_once()
            except Exception:
                logger.exception("reaper_unexpected_error")
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._interval_sec)
            except TimeoutError:
                continue
        logger.info("assignment_reaper_stopped")

    async def reap_once(self) -> None:
        if not self._cfg.enabled:
            return
        listed = await self._assignments.scan_all()
        if isinstance(listed, Failure):
            logger.warning("reaper_skipped scan_failed: %s", listed.failure().message)
            return
        cutoff = datetime.now(tz=UTC) - timedelta(seconds=self._cfg.idle_ttl_sec)
        released = 0
        for assignment in listed.unwrap():
            try:
                updated = datetime.fromisoformat(assignment.updated_at)
            except ValueError:
                continue
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=UTC)
            if updated > cutoff:
                continue
            pod_result = await self._store.get_pod_by_id(
                pool=assignment.pool,
                pod_id=assignment.pod_id,
            )
            if isinstance(pod_result, Failure):
                continue
            pod = pod_result.unwrap()
            now = datetime.now(tz=UTC).isoformat()
            freed: BackendPoolNodeRecord | None = None
            if pod is not None:
                freed = BackendPoolNodeRecord(
                    pod_id=pod.pod_id,
                    pod_dns=pod.pod_dns,
                    state=POD_STATE_FREE,
                    assigned_sub="",
                    assignment_epoch=0,
                    updated_at=now,
                )
            result = await self._store.transact_release(
                sub=assignment.sub,
                pool=assignment.pool,
                freed_pod=freed,
            )
            if isinstance(result, Failure):
                logger.warning(
                    "reaper_release_failed sub=%s: %s",
                    assignment.sub,
                    result.failure().message,
                )
                continue
            if self._route_cache is not None:
                self._route_cache.invalidate(sub=assignment.sub)
            if self._events is not None:
                _ = await self._events.put(
                    AssignmentEventRecord(
                        event_id=str(uuid.uuid4()),
                        sub=assignment.sub,
                        pod_id=assignment.pod_id,
                        event_type="reaper_release",
                        timestamp=now,
                        assignment_epoch=assignment.assignment_epoch,
                    ),
                )
            released += 1
            logger.info("reaper_released sub=%s pod_id=%s", assignment.sub, assignment.pod_id)
        if released:
            logger.info("reaper_complete released=%d", released)

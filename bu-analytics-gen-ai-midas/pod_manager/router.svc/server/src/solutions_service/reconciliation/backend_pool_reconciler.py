"""Background coroutine: sync ``backend_pool`` with ready backend pool nodes from Kubernetes."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from solutions_service.core.app_config import AppConfig
from solutions_service.core.errors import AppError
from solutions_service.core.results import Failure
from solutions_service.database.models.pod_records import (
    NODE_STATE_CLAIMED,
    NODE_STATE_FREE,
    BackendPoolNodeRecord,
)
from solutions_service.database.repositories.backend_pool_repository import (
    BackendPoolRepository,
)
from solutions_service.drivers.eks.protocol import DiscoveredBackendPod, EksClusterDriver
from solutions_service.observability.metrics import observe_reconcile_cycle

logger = logging.getLogger(__name__)


class BackendPoolReconciler:
    """Async loop; one task in the main process (no separate worker process)."""

    __slots__ = ("_app_config", "_cluster", "_repo", "_interval_sec")

    def __init__(
        self,
        *,
        app_config: AppConfig,
        cluster_driver: EksClusterDriver,
        backend_pool_repository: BackendPoolRepository,
    ) -> None:
        self._app_config = app_config
        self._cluster = cluster_driver
        self._repo = backend_pool_repository
        self._interval_sec = app_config.reconciliation.interval_sec

    async def run_until_stopped(self, stop: asyncio.Event) -> None:
        """Run reconcile cycles until ``stop`` is set."""
        logger.info(
            "backend_pool_reconciler_started interval_sec=%s namespace=%s",
            self._interval_sec,
            self._app_config.kubernetes.namespace,
        )
        while not stop.is_set():
            try:
                await self.reconcile_once()
            except Exception:
                logger.exception("reconcile_unexpected_error")
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._interval_sec)
            except TimeoutError:
                continue
        logger.info("backend_pool_reconciler_stopped")

    async def reconcile_once(self) -> None:
        """Single reconcile pass: cluster ready nodes ↔ Postgres ``backend_pool``."""
        with observe_reconcile_cycle():
            await self._reconcile_once_inner()

    async def _reconcile_once_inner(self) -> None:
        discovered = await self._cluster.list_ready_backend_pods()
        if isinstance(discovered, Failure):
            err = discovered.failure()
            logger.warning(
                "reconcile_skipped discovery_failed: %s (%s)",
                err.message,
                err.code,
            )
            return

        cluster_pods: dict[str, DiscoveredBackendPod] = {
            p.pod_id: p for p in discovered.unwrap()
        }
        listed = await self._repo.scan_all()
        if isinstance(listed, Failure):
            err = listed.failure()
            logger.warning("reconcile_skipped scan_failed: %s", err.message)
            return

        db_by_id = {r.pod_id: r for r in listed.unwrap()}
        cluster_ids = set(cluster_pods)
        db_ids = set(db_by_id)

        removed = 0
        added = 0
        updated = 0

        for pod_id in db_ids - cluster_ids:
            rec = db_by_id[pod_id]
            if rec.state == NODE_STATE_CLAIMED:
                logger.info(
                    "reconcile_keep_missing_claimed pod_id=%s sub=%s",
                    pod_id,
                    rec.assigned_sub,
                )
                continue
            deleted = await self._repo.delete(pod_id=pod_id)
            if isinstance(deleted, Failure):
                logger.warning(
                    "reconcile_delete_failed pod_id=%s: %s",
                    pod_id,
                    deleted.failure().message,
                )
                continue
            removed += 1

        now = datetime.now(tz=UTC).isoformat()
        for pod_id in cluster_ids - db_ids:
            pod = cluster_pods[pod_id]
            put = await self._repo.put(
                BackendPoolNodeRecord(
                    pod_id=pod.pod_id,
                    pod_dns=pod.pod_dns,
                    state=NODE_STATE_FREE,
                    assigned_sub="",
                    assignment_epoch=0,
                    updated_at=now,
                ),
            )
            if isinstance(put, Failure):
                logger.warning(
                    "reconcile_put_failed pod_id=%s: %s",
                    pod_id,
                    put.failure().message,
                )
                continue
            added += 1

        for pod_id in cluster_ids & db_ids:
            pod = cluster_pods[pod_id]
            rec = db_by_id[pod_id]
            if rec.pod_dns == pod.pod_dns:
                continue
            if rec.state == NODE_STATE_CLAIMED:
                patched = await self._repo.put(
                    rec.model_copy(update={"pod_dns": pod.pod_dns, "updated_at": now}),
                )
            else:
                patched = await self._repo.put(
                    BackendPoolNodeRecord(
                        pod_id=pod.pod_id,
                        pod_dns=pod.pod_dns,
                        state=rec.state,
                        assigned_sub=rec.assigned_sub,
                        assignment_epoch=rec.assignment_epoch,
                        updated_at=now,
                    ),
                )
            if isinstance(patched, Failure):
                logger.warning(
                    "reconcile_update_failed pod_id=%s: %s",
                    pod_id,
                    patched.failure().message,
                )
                continue
            updated += 1

        logger.info(
            "reconcile_complete cluster=%d db=%d added=%d removed=%d updated=%d",
            len(cluster_ids),
            len(db_ids),
            added,
            removed,
            updated,
        )


PodPoolReconciler = BackendPoolReconciler

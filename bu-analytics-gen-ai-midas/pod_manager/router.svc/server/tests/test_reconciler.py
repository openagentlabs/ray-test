"""Reconciler tests with fake EKS driver."""

from __future__ import annotations

import pytest

from solutions_service.core.app_config import AppConfig
from solutions_service.database.models.pool_kind import BACKEND_POOL
from solutions_service.database.models.pod_records import POD_STATE_CLAIMED, POD_STATE_FREE, BackendPoolNodeRecord
from solutions_service.database.repositories.backend_pool_repository import BackendPoolRepository
from solutions_service.drivers.eks.fake import FakeEksClusterDriver
from solutions_service.drivers.store.fake import FakeAssignmentStoreDriver
from solutions_service.reconciliation.backend_pool_reconciler import BackendPoolReconciler


class _InMemoryPodPoolRepo:
    """Minimal repo backed by fake store for reconciler tests."""

    def __init__(self, store: FakeAssignmentStoreDriver) -> None:
        self._store = store

    async def scan_all(self):  # noqa: ANN201
        return await self._store.scan_all_pods(pool=BACKEND_POOL)

    async def delete(self, *, pod_id: str):  # noqa: ANN201
        return await self._store.delete_pod(pool=BACKEND_POOL, pod_id=pod_id)

    async def put(self, record: BackendPoolNodeRecord):  # noqa: ANN201
        return await self._store.put_pod(pool=BACKEND_POOL, record=record)


@pytest.mark.asyncio
async def test_reconcile_keeps_claimed_missing_pod() -> None:
    store = FakeAssignmentStoreDriver()
    await store.put_pod(
        pool=BACKEND_POOL,
        record=BackendPoolNodeRecord(
            pod_id="gone",
            pod_dns="gone:8080",
            state=POD_STATE_CLAIMED,
            assigned_sub="alice",
            assignment_epoch=1,
            updated_at="2026-01-01T00:00:00+00:00",
        ),
    )
    eks = FakeEksClusterDriver(pods=[])
    reconciler = BackendPoolReconciler(
        app_config=AppConfig.default(),
        cluster_driver=eks,
        backend_pool_repository=_InMemoryPodPoolRepo(store),  # type: ignore[arg-type]
    )
    await reconciler.reconcile_once()
    listed = await store.scan_all_pods(pool=BACKEND_POOL)
    assert listed.unwrap()[0].pod_id == "gone"


@pytest.mark.asyncio
async def test_reconcile_skips_on_k8s_failure() -> None:
    store = FakeAssignmentStoreDriver()

    class _FailEks(FakeEksClusterDriver):
        async def list_ready_backend_pods(self):  # noqa: ANN201
            from solutions_service.core.errors import AppError, ErrorCodes
            from solutions_service.core.results import Failure

            return Failure(
                AppError(code=ErrorCodes.UPSTREAM, message="k8s down", detail=None),
            )

    reconciler = BackendPoolReconciler(
        app_config=AppConfig.default(),
        cluster_driver=_FailEks(),
        backend_pool_repository=_InMemoryPodPoolRepo(store),  # type: ignore[arg-type]
    )
    await reconciler.reconcile_once()
    assert await store.scan_all_pods(pool=BACKEND_POOL)
    assert reconciler  # no exception

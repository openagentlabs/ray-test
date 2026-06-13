"""Pool handler edge cases (robustness)."""

from __future__ import annotations

import pytest
from returns.result import Success

from solutions_service.core.errors import ErrorCodes
from solutions_service.core.results import Failure
from solutions_service.database.models.pool_kind import BACKEND_POOL, LOGIN_POD_POOL
from solutions_service.database.models.pod_records import POD_STATE_FREE, BackendPoolNodeRecord
from solutions_service.drivers.store.fake import FakeAssignmentStoreDriver
from solutions_service.handlers.pool.pool_handler import PoolRpcHandler


@pytest.mark.asyncio
async def test_acquire_lease_idempotent() -> None:
    store = FakeAssignmentStoreDriver()
    await store.put_pod(
        pool=BACKEND_POOL,
        record=BackendPoolNodeRecord(
            pod_id="p0",
            pod_dns="p0:8080",
            state=POD_STATE_FREE,
            assigned_sub="",
            assignment_epoch=0,
            updated_at="2026-01-01T00:00:00+00:00",
        ),
    )
    handler = PoolRpcHandler(assignment_store=store)
    first = await handler.acquire_lease(sub="alice@example.com")
    assert isinstance(first, Success)
    assert first.unwrap().already_leased is False
    second = await handler.acquire_lease(sub="alice@example.com")
    assert isinstance(second, Success)
    assert second.unwrap().already_leased is True
    assert first.unwrap().pod_id == second.unwrap().pod_id


@pytest.mark.asyncio
async def test_get_lease_found() -> None:
    store = FakeAssignmentStoreDriver()
    await store.put_pod(
        pool=BACKEND_POOL,
        record=BackendPoolNodeRecord(
            pod_id="p0",
            pod_dns="p0:8080",
            state=POD_STATE_FREE,
            assigned_sub="",
            assignment_epoch=0,
            updated_at="2026-01-01T00:00:00+00:00",
        ),
    )
    handler = PoolRpcHandler(assignment_store=store)
    _ = await handler.acquire_lease(sub="alice@example.com")
    result = await handler.get_lease(sub="alice@example.com")
    assert isinstance(result, Success)
    assert result.unwrap().pod_id == "p0"


@pytest.mark.asyncio
async def test_get_lease_not_found() -> None:
    handler = PoolRpcHandler(assignment_store=FakeAssignmentStoreDriver())
    result = await handler.get_lease(sub="alice@example.com")
    assert isinstance(result, Failure)
    assert result.failure().code == ErrorCodes.NOT_FOUND


@pytest.mark.asyncio
async def test_acquire_lease_resource_exhausted() -> None:
    handler = PoolRpcHandler(assignment_store=FakeAssignmentStoreDriver())
    result = await handler.acquire_lease(sub="alice@example.com")
    assert isinstance(result, Failure)
    assert result.failure().code == ErrorCodes.RESOURCE_EXHAUSTED


@pytest.mark.asyncio
async def test_release_lease_idempotent() -> None:
    store = FakeAssignmentStoreDriver()
    await store.put_pod(
        pool=BACKEND_POOL,
        record=BackendPoolNodeRecord(
            pod_id="p0",
            pod_dns="p0:8080",
            state=POD_STATE_FREE,
            assigned_sub="",
            assignment_epoch=0,
            updated_at="2026-01-01T00:00:00+00:00",
        ),
    )
    handler = PoolRpcHandler(assignment_store=store)
    _ = await handler.acquire_lease(sub="alice@example.com")
    released = await handler.release_lease(sub="alice@example.com")
    assert isinstance(released, Success)
    again = await handler.release_lease(sub="alice@example.com")
    assert isinstance(again, Success)


@pytest.mark.asyncio
async def test_get_pool_status_lists_both_pools() -> None:
    store = FakeAssignmentStoreDriver()
    await store.put_pod(
        pool=BACKEND_POOL,
        record=BackendPoolNodeRecord(
            pod_id="b0",
            pod_dns="b0:8080",
            state=POD_STATE_FREE,
            assigned_sub="",
            assignment_epoch=0,
            updated_at="2026-01-01T00:00:00+00:00",
        ),
    )
    await store.put_pod(
        pool=LOGIN_POD_POOL,
        record=BackendPoolNodeRecord(
            pod_id="login-pod",
            pod_dns="login-pod:8080",
            state="available",
            assigned_sub="",
            assignment_epoch=0,
            updated_at="2026-01-01T00:00:00+00:00",
        ),
    )
    handler = PoolRpcHandler(assignment_store=store)
    result = await handler.get_pool_status()
    assert isinstance(result, Success)
    resp = result.unwrap()
    pools = {p.pool for p in resp.pods}
    assert pools == {BACKEND_POOL, LOGIN_POD_POOL}


@pytest.mark.asyncio
async def test_get_backend_pool_availability() -> None:
    store = FakeAssignmentStoreDriver()
    await store.put_pod(
        pool=BACKEND_POOL,
        record=BackendPoolNodeRecord(
            pod_id="b0",
            pod_dns="b0:8080",
            state=POD_STATE_FREE,
            assigned_sub="",
            assignment_epoch=0,
            updated_at="2026-01-01T00:00:00+00:00",
        ),
    )
    handler = PoolRpcHandler(assignment_store=store)
    result = await handler.get_backend_pool_availability()
    assert isinstance(result, Success)
    resp = result.unwrap()
    assert resp.free_count == 1
    assert resp.has_capacity is True

"""ext_authz Check handler tests."""

from __future__ import annotations

import pytest

from envoy.service.auth.v3 import external_auth_pb2
from solutions_service.core.app_config import AppConfig
from solutions_service.database.models.pod_records import BackendPoolNodeRecord, UserAssignmentRecord
from solutions_service.database.models.pool_kind import BACKEND_POOL
from solutions_service.drivers.store.fake import FakeAssignmentStoreDriver
from solutions_service.ext_authz.assignment_cache import AssignmentRouteCache
from solutions_service.ext_authz.check_handler import ExtAuthzCheckHandler, ROUTE_UPSTREAM_HEADER


def _check_request(*, headers: dict[str, str]) -> external_auth_pb2.CheckRequest:
    request = external_auth_pb2.CheckRequest()
    for key, value in headers.items():
        request.attributes.request.http.headers[key] = value
    return request


@pytest.mark.asyncio
async def test_ext_authz_no_assignment_routes_to_login_pool() -> None:
    cfg = AppConfig.default()
    handler = ExtAuthzCheckHandler(
        app_config=cfg,
        assignment_store=FakeAssignmentStoreDriver(),
    )
    resp = await handler.check(
        _check_request(headers={"x-test-sub": "alice@example.com"}),
    )
    assert resp.status.code == 0
    upstream = _header_value(resp, ROUTE_UPSTREAM_HEADER)
    assert upstream == cfg.login_pod_pool.routing_upstream


@pytest.mark.asyncio
async def test_ext_authz_no_assignment_denies_without_identity() -> None:
    handler = ExtAuthzCheckHandler(
        app_config=AppConfig.default(),
        assignment_store=FakeAssignmentStoreDriver(),
    )
    resp = await handler.check(_check_request(headers={}))
    assert resp.status.code != 0


@pytest.mark.asyncio
async def test_ext_authz_allow_sets_upstream_for_lease() -> None:
    store = FakeAssignmentStoreDriver()
    await store.put_assignment(
        UserAssignmentRecord(
            sub="alice@example.com",
            pod_id="p0",
            pod_dns="p0:8080",
            pool=BACKEND_POOL,
            assignment_epoch=1,
            updated_at="2026-01-01T00:00:00+00:00",
        ),
    )
    await store.put_pod(
        pool=BACKEND_POOL,
        record=BackendPoolNodeRecord(
            pod_id="p0",
            pod_dns="p0:8080",
            state="claimed",
            assigned_sub="alice@example.com",
            assignment_epoch=1,
            updated_at="2026-01-01T00:00:00+00:00",
        ),
    )
    handler = ExtAuthzCheckHandler(
        app_config=AppConfig.default(),
        assignment_store=store,
        route_cache=AssignmentRouteCache(),
    )
    resp = await handler.check(
        _check_request(headers={"x-test-sub": "alice@example.com"}),
    )
    assert resp.status.code == 0
    assert _header_value(resp, ROUTE_UPSTREAM_HEADER) == "p0:8080"


@pytest.mark.asyncio
async def test_ext_authz_cookie_identity() -> None:
    store = FakeAssignmentStoreDriver()
    handler = ExtAuthzCheckHandler(app_config=AppConfig.default(), assignment_store=store)
    resp = await handler.check(
        _check_request(headers={"cookie": "pod_manager_user=bob@example.com"}),
    )
    assert resp.status.code == 0


def _header_value(resp: external_auth_pb2.CheckResponse, key: str) -> str:
    for h in resp.ok_response.headers:
        if h.header.key.lower() == key.lower():
            return h.header.value
    return ""

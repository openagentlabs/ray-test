"""HTTP routing: unleased 403 and leased 200."""

from __future__ import annotations

import httpx
from returns.result import Failure, Result, Success

from dev_testing.config import EndpointProfile
from dev_testing.results_ext import Reporter
from pod_manager_client import PodManagerClient, PodManagerClientError


async def run(profile: EndpointProfile, report: Reporter) -> Result[None, str]:
    sub = profile.test_sub
    url = f"{profile.envoy_url}/api/v1/me"
    headers = {"x-test-sub": sub}
    leased_ok = False

    async with httpx.AsyncClient(timeout=10.0) as client:
        unleased = await client.get(url, headers=headers)
        if unleased.status_code != 403 or "no_backend_lease" not in unleased.text:
            report(False, f"unleased expected 403 no_backend_lease got {unleased.status_code}")
            return Failure("unleased routing")
        report(True, "unleased GET /api/v1/me → 403 no_backend_lease")

    try:
        async with PodManagerClient(
            host=profile.pod_manager_host,
            port=profile.pod_manager_port,
        ) as grpc:
            await grpc.acquire_lease(sub)
            leased_ok = True
    except PodManagerClientError as exc:
        report(False, f"AcquireLease for routing test: {exc}")
        return Failure(str(exc))

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            leased = await client.get(url, headers=headers)
            if leased.status_code != 200 or "backend_pool_node" not in leased.text:
                report(False, f"leased expected 200 JSON got {leased.status_code}")
                return Failure("leased routing")
            report(True, "leased GET /api/v1/me → 200")
    finally:
        if leased_ok:
            try:
                async with PodManagerClient(
                    host=profile.pod_manager_host,
                    port=profile.pod_manager_port,
                ) as grpc:
                    await grpc.release_lease(sub)
            except PodManagerClientError as exc:
                report(False, f"ReleaseLease cleanup: {exc}")
                return Failure(str(exc))

    return Success(None)

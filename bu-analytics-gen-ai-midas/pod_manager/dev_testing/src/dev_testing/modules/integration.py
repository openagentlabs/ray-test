"""Full end-to-end integration test."""

from __future__ import annotations

import httpx
from returns.result import Failure, Result, Success

from dev_testing.config import EndpointProfile
from dev_testing.modules import grpc_lease, grpc_pool, health, http_login, http_routing, postgres
from dev_testing.results_ext import Reporter, collect_results
from pod_manager_client import PodManagerClient, PodManagerClientError


async def run(profile: EndpointProfile, report: Reporter) -> Result[None, str]:
    steps = [
        ("health", await health.run(profile, report)),
        ("postgres", await postgres.run(profile, report)),
        ("grpc_pool", await grpc_pool.run(profile, report)),
        ("http_login", await http_login.run(profile, report)),
        ("http_routing", await http_routing.run(profile, report)),
        ("grpc_lease", await grpc_lease.run(profile, report)),
    ]
    collected = collect_results([(name, result) for name, result in steps])
    if isinstance(collected, Failure):
        return collected

    sub = profile.test_sub
    url = f"{profile.envoy_url}/api/v1/me"
    seen: set[str] = set()
    try:
        async with PodManagerClient(
            host=profile.pod_manager_host,
            port=profile.pod_manager_port,
        ) as client:
            await client.acquire_lease(sub)
            async with httpx.AsyncClient(timeout=10.0) as http:
                for _ in range(2):
                    resp = await http.get(url, headers={"x-test-sub": sub})
                    if resp.status_code != 200:
                        report(False, f"e2e sticky HTTP {resp.status_code}")
                        await client.release_lease(sub)
                        return Failure("e2e sticky")
                    body = resp.text
                    for token in ("backend-pool-node-0", "backend-pool-node-1", "backend-pool-node-2"):
                        if token in body:
                            seen.add(token)
                            break
            await client.release_lease(sub)
    except PodManagerClientError as exc:
        report(False, f"e2e gRPC: {exc}")
        return Failure(str(exc))

    if len(seen) != 1:
        report(False, f"e2e not sticky: {seen}")
        return Failure("not sticky")
    report(True, f"e2e sticky routing OK ({seen.pop()})")
    return Success(None)

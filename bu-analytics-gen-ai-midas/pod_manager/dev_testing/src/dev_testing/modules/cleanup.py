"""Release stale dev-test leases before integration runs."""

from __future__ import annotations

from returns.result import Result, Success

from dev_testing.config import EndpointProfile
from dev_testing.results_ext import Reporter
from pod_manager_client import PodManagerClient, PodManagerClientError


async def run(profile: EndpointProfile, report: Reporter) -> Result[None, str]:
    prefixes = ("dev-test", "test-local")
    released = 0
    async with PodManagerClient(
        host=profile.pod_manager_host,
        port=profile.pod_manager_port,
    ) as client:
        status = await client.get_pool_status()
        for pod in status.pods:
            sub = pod.assigned_sub
            if not sub:
                continue
            if not any(sub.startswith(prefix) for prefix in prefixes):
                continue
            try:
                await client.release_lease(sub)
                released += 1
            except PodManagerClientError:
                continue
    report(True, f"released {released} stale dev-test lease(s)")
    return Success(None)

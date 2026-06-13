"""gRPC pool status tests."""

from __future__ import annotations

from returns.result import Failure, Result, Success

from dev_testing.config import EndpointProfile
from dev_testing.results_ext import Reporter
from pod_manager_client import PodManagerClient, PodManagerClientError


async def run(profile: EndpointProfile, report: Reporter) -> Result[None, str]:
    try:
        async with PodManagerClient(
            host=profile.pod_manager_host,
            port=profile.pod_manager_port,
        ) as client:
            status = await client.get_pool_status()
    except PodManagerClientError as exc:
        report(False, f"GetPoolStatus failed: {exc}")
        return Failure(str(exc))

    report(True, f"GetPoolStatus free={status.free_count} claimed={status.claimed_count}")
    if not status.pods:
        report(False, "pool has zero pods")
        return Failure("empty pool")
    report(True, f"pool pods={len(status.pods)}")
    return Success(None)

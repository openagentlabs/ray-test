"""gRPC lease acquire, get, release tests."""

from __future__ import annotations

import grpc
from returns.result import Failure, Result, Success

from dev_testing.config import EndpointProfile
from dev_testing.results_ext import Reporter
from pod_manager_client import PodManagerClient, PodManagerClientError


async def run(profile: EndpointProfile, report: Reporter) -> Result[None, str]:
    sub = profile.test_sub
    acquired_pod: str | None = None
    try:
        async with PodManagerClient(
            host=profile.pod_manager_host,
            port=profile.pod_manager_port,
        ) as client:
            acquired = await client.acquire_lease(sub)
            acquired_pod = acquired.pod_id
            report(
                True,
                f"AcquireLease pod_id={acquired.pod_id} already={acquired.already_leased}",
            )
            try:
                current = await client.get_lease(sub)
                report(True, f"GetLease pod_id={current.pod_id}")
            except PodManagerClientError as exc:
                if exc.code == grpc.StatusCode.UNIMPLEMENTED:
                    report(True, "GetLease skipped (UNIMPLEMENTED on server)")
                else:
                    raise
            await client.release_lease(sub)
            report(True, "ReleaseLease ok")
    except PodManagerClientError as exc:
        report(False, f"lease RPC failed: {exc}")
        if acquired_pod is not None:
            try:
                async with PodManagerClient(
                    host=profile.pod_manager_host,
                    port=profile.pod_manager_port,
                ) as cleanup:
                    await cleanup.release_lease(sub)
            except PodManagerClientError:
                pass
        return Failure(str(exc))
    return Success(None)

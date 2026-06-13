"""Envoy and pod health checks."""

from __future__ import annotations

import httpx
from returns.result import Failure, Result, Success

from dev_testing.config import DeployTarget, EndpointProfile
from dev_testing.results_ext import Reporter


async def run(profile: EndpointProfile, report: Reporter) -> Result[None, str]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        if profile.deploy_target == DeployTarget.LOCAL:
            health_url = f"{profile.envoy_health_url}/healthz"
            try:
                health = await client.get(health_url)
            except httpx.HTTPError as exc:
                report(False, f"Envoy health GET failed: {exc}")
                return Failure(str(exc))
            if health.status_code != 200:
                report(False, f"Envoy health expected 200 got {health.status_code}")
                return Failure(f"health status {health.status_code}")
            report(True, f"Envoy health {health_url} → 200")

        root = await client.get(f"{profile.envoy_url}/", headers={"x-test-sub": profile.test_sub})
        if root.status_code not in {200, 403, 404}:
            report(False, f"Envoy traffic GET / unexpected {root.status_code}")
            return Failure(f"traffic status {root.status_code}")
        report(True, f"Envoy traffic GET / → {root.status_code}")

    return Success(None)

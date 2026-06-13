"""HTTP login via Envoy."""

from __future__ import annotations

import httpx
from returns.result import Failure, Result, Success

from dev_testing.config import EndpointProfile
from dev_testing.results_ext import Reporter


async def run(profile: EndpointProfile, report: Reporter) -> Result[None, str]:
    url = f"{profile.envoy_url}/login"
    headers = {"x-test-sub": profile.test_sub, "Content-Type": "application/json"}
    payload = {"user_name": profile.test_sub, "user_password": ""}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            report(False, f"POST /login failed: {exc}")
            return Failure(str(exc))
    if resp.status_code != 200:
        report(False, f"POST /login expected 200 got {resp.status_code}")
        return Failure(f"login status {resp.status_code}")
    report(True, "POST /login via Envoy → 200")
    return Success(None)

"""Auth guard helpers used across integration tests."""

from __future__ import annotations

import pytest
import httpx


def skip_on_auth_reject(response: httpx.Response) -> None:
    """Call pytest.skip if the server rejected the Bearer token (401)."""
    if response.status_code == 401:
        pytest.skip(
            "Bearer token rejected — refresh MIDAS_ACCESS_TOKEN or re-run Playwright SSO."
        )

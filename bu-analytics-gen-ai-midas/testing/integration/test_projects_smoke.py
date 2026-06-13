"""Tier-B smoke: authenticated project list (requires valid session)."""

from __future__ import annotations

import json

import pytest


def test_projects_list_returns_json_array(midas_client) -> None:
    """``GET /api/v1/projects`` returns JSON (array or wrapped list) for an authenticated user."""
    r = midas_client.request("GET", "/api/v1/projects")
    if r.status_code == 401:
        pytest.skip("Bearer token rejected — refresh MIDAS_ACCESS_TOKEN or SSO.")
    assert r.status_code in (200, 403), r.text
    if r.status_code != 200:
        return
    data = json.loads(r.text)
    assert isinstance(data, (list, dict)), type(data).__name__

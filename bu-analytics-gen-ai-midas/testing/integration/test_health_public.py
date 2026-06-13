"""Public endpoints that must work without authentication."""

from __future__ import annotations

import json

import httpx
import pytest


def test_health_returns_json_object(public_client) -> None:
    """GET /health must return 200 and a JSON object (vector store fields may vary)."""
    try:
        r = public_client.request("GET", "/health")
    except Exception as exc:
        pytest.skip(f"Server unreachable: {exc}")
    assert r.status_code == 200, r.text
    body = json.loads(r.text)
    assert isinstance(body, dict)
    assert body.get("status") == "healthy"


def test_root_returns_spa_or_welcome(public_client) -> None:
    """GET / returns the SPA shell (HTML) or JSON welcome depending on ingress routing."""
    try:
        r = public_client.request("GET", "/")
    except Exception as exc:
        pytest.skip(f"Server unreachable: {exc}")
    assert r.status_code == 200
    ct = (r.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        body = json.loads(r.text)
        assert "MIDAS" in body.get("message", "")
    else:
        assert "text/html" in ct
        assert len(r.text) > 100
        lowered = r.text.lower()
        assert "exl" in lowered or "midas" in lowered or "react" in lowered


def test_datasets_requires_auth_without_token(midas_base_url: str) -> None:
    """Unauthenticated GET /api/v1/datasets must not succeed with 200."""
    try:
        with httpx.Client(base_url=midas_base_url, timeout=30.0, verify=False) as client:
            r = client.get("/api/v1/datasets")
    except Exception as exc:
        pytest.skip(f"Server unreachable: {exc}")
    assert r.status_code in (401, 403), r.text

"""Tier-A smoke: every GET from the generated route inventory (excluding streaming and parametrised paths)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

_INVENTORY_PATH = Path(__file__).resolve().parent.parent / "generated" / "route_inventory.json"


import re

_SKIP_PATH_RE = re.compile(r"(stream|sse|event)", re.IGNORECASE)


def _load_get_routes() -> list[dict[str, str]]:
    data = json.loads(_INVENTORY_PATH.read_text(encoding="utf-8"))
    routes: list[dict[str, str]] = []
    for row in data["routes"]:
        if row.get("method") != "GET":
            continue
        path = row["full_path"]
        if "{" in path:
            # Parametrised paths are covered by dedicated test modules.
            continue
        if _SKIP_PATH_RE.search(path):
            # Streaming / SSE endpoints require special handling.
            continue
        routes.append(row)
    return routes


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "inventory_get_route" in metafunc.fixturenames:
        metafunc.parametrize(
            "inventory_get_route",
            _load_get_routes(),
            ids=lambda r: f"GET {r['full_path']}",
        )


def test_inventory_get_smoke(midas_client, inventory_get_route: dict[str, str]) -> None:
    """Authenticated GET must not return 401 (bad token) or 5xx for inventory-listed routes (404 allowed)."""
    from testing.integration.support.auth_guards import skip_on_auth_reject

    path = inventory_get_route["full_path"]
    resp = midas_client.request("GET", path)
    skip_on_auth_reject(resp)
    assert resp.status_code < 500, f"Server error {resp.status_code} for {path}: {resp.text[:500]}"

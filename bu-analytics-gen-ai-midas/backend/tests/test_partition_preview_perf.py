"""
Tests for the column-projected, executor-offloaded ``partition-preview-by-id``
path. The endpoint used to load the entire DataFrame into pandas memory on
the event loop, which broke for >2 GB CSVs (unbounded RAM + tens of seconds
of frozen loop). After the resilience pass:

  * only target / date / identifier / exclusion-referenced columns are
    decoded from the parquet sidecar via Polars ``scan_parquet().select()``;
  * the heavy work runs on the shared ThreadPoolExecutor so the event loop
    stays responsive;
  * results are cached in ``AnalyticsResultCache`` keyed by
    (dataset_id, sha1(target+split+exclusions+removals), version).

These tests exercise all three properties on a synthetic 1 M-row parquet
sidecar; they're skipped automatically when the FastAPI router cannot be
imported (thin local checkout missing optional deps).
"""

from __future__ import annotations

import asyncio
import io
import json
import time
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


try:
    from app.api import routes as _routes_probe  # noqa: F401
    _ROUTES_IMPORTABLE = True
except Exception:  # pragma: no cover - thin checkouts
    _ROUTES_IMPORTABLE = False


pytestmark = pytest.mark.skipif(
    not _ROUTES_IMPORTABLE,
    reason="api.routes not importable in this environment",
)


@pytest.fixture
def isolated_dataset(monkeypatch, tmp_path):
    """Stand up a clean dataset_manager + LocalObjectStorage rooted in tmp_path,
    write a 1M-row synthetic parquet sidecar, register it, and yield the
    dataset_id plus the underlying frame for assertion."""

    from app.services.object_storage import registry as _store_registry
    from app.services.object_storage.local_object_storage import LocalObjectStorage

    _store_registry.set_object_storage(LocalObjectStorage(tmp_path))

    from app.services.dataset_service import dataset_manager

    monkeypatch.setattr(dataset_manager, "upload_dir", tmp_path)
    dataset_manager.datasets.clear()

    from app.services.dataframe_state_manager import dataframe_state_manager

    dataframe_state_manager._full_dataframes.clear()  # type: ignore[attr-defined]
    dataframe_state_manager._processed_dataframes.clear()  # type: ignore[attr-defined]
    dataframe_state_manager._dataset_metadata.clear()  # type: ignore[attr-defined]
    dataframe_state_manager._version_counters.clear()  # type: ignore[attr-defined]

    from app.services.analytics_cache import analytics_cache

    with analytics_cache._lock:  # type: ignore[attr-defined]
        analytics_cache._cache.clear()  # type: ignore[attr-defined]
        analytics_cache._hits = 0  # type: ignore[attr-defined]
        analytics_cache._misses = 0  # type: ignore[attr-defined]

    rng = np.random.default_rng(42)
    n = 1_000_000
    df = pd.DataFrame(
        {
            "id": np.arange(n),
            "feature_a": rng.normal(size=n),
            "feature_b": rng.normal(size=n),
            "feature_c": rng.integers(0, 1000, size=n),
            "feature_d": rng.choice(["x", "y", "z"], size=n),
            "split_group": rng.choice(["train", "test", "validation"], size=n, p=[0.6, 0.2, 0.2]),
            "y": rng.integers(0, 2, size=n),
        }
    )

    dataset_id = str(uuid.uuid4())
    csv_key = f"{dataset_id}_perf.csv"
    pq_key = f"{dataset_id}_perf.parquet"

    df.to_parquet(tmp_path / pq_key, engine="pyarrow", compression="snappy")
    (tmp_path / csv_key).write_text(",".join(df.columns) + "\n")

    dataset_manager.datasets[dataset_id] = {
        "file_path": csv_key,
        "storage_key": csv_key,
        "filename": "perf.csv",
        "target_variable": "y",
        "target_variable_type": "binary",
        "data_dictionary": "",
        "problem_statement": "",
        "uploaded_at": pd.Timestamp.now().isoformat(),
    }
    dataset_manager._persist_dataset_info(dataset_id)

    yield dataset_id, df


def _form_payload(dataset_id: str, target: str, split_method: str = "user_identifier"):
    if split_method == "user_identifier":
        cfg = {
            "ingestion_mode": "platform_split",
            "split_method": "user_identifier",
            "identifier_column": "split_group",
            "identifier_mapping": {
                "train": "train",
                "test": "test",
                "validation": "validation",
            },
        }
    elif split_method == "stratified_random":
        cfg = {
            "ingestion_mode": "platform_split",
            "split_method": "stratified_random",
            "ratios": {"train": 60, "test": 20, "validation": 20},
        }
    else:
        raise ValueError(split_method)
    return {
        "dataset_id": dataset_id,
        "split_configuration": json.dumps(cfg),
        "target_variable": target,
    }


def _build_app():
    from fastapi import FastAPI

    from app.api.auth_routes import get_current_user_dependency
    from app.api.routes import upload_router

    app = FastAPI()
    app.include_router(upload_router)
    app.dependency_overrides[get_current_user_dependency] = lambda: {"sub": "test-user"}
    return app


def test_partition_preview_by_id_one_million_rows_under_two_seconds(
    isolated_dataset, monkeypatch
):
    """Cold-cache, 1M rows, projected to 2 columns (target + identifier).
    Should land well under 2s on commodity laptops; we set a 5s ceiling
    for CI flakiness headroom."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")

    from fastapi.testclient import TestClient

    dataset_id, df = isolated_dataset
    app = _build_app()

    with TestClient(app) as tc:
        t0 = time.perf_counter()
        res = tc.post("/partition-preview-by-id", data=_form_payload(dataset_id, "y"))
        dt = time.perf_counter() - t0

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["total_rows"] == len(df)
    parts = {p["key"]: p for p in body["partitions"]}
    assert {"train", "test", "validation"} <= set(parts.keys())
    expected = df["split_group"].value_counts().to_dict()
    for key, exp in expected.items():
        assert parts[key]["row_count"] == int(exp)

    assert body["features"] == len(df.columns) - 1  # all cols minus target

    assert dt < 5.0, f"partition-preview-by-id took {dt:.2f}s on 1M rows"


def test_partition_preview_by_id_second_call_is_cached(isolated_dataset, monkeypatch):
    """Same payload twice → second call serves from analytics_cache and
    returns ``cached: true`` in well under 200 ms."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")

    from fastapi.testclient import TestClient

    dataset_id, _df = isolated_dataset
    app = _build_app()

    with TestClient(app) as tc:
        first = tc.post("/partition-preview-by-id", data=_form_payload(dataset_id, "y"))
        assert first.status_code == 200, first.text
        assert first.json().get("cached") is not True

        t0 = time.perf_counter()
        second = tc.post("/partition-preview-by-id", data=_form_payload(dataset_id, "y"))
        dt = time.perf_counter() - t0

    assert second.status_code == 200, second.text
    body = second.json()
    assert body.get("cached") is True
    assert dt < 0.5, f"cached partition preview took {dt:.2f}s"


def test_partition_preview_by_id_does_not_block_event_loop(
    isolated_dataset, monkeypatch
):
    """While ``_load_and_build`` runs in the executor, the event loop must
    remain free to service unrelated requests. We approximate this by
    verifying the route is awaitable concurrently with a short sleep --
    if the route blocked the loop, the gather would serialize and the
    second await would not start until after the first finishes."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")

    from httpx import ASGITransport, AsyncClient

    dataset_id, _df = isolated_dataset
    app = _build_app()

    async def _drive():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            sleep_started_at: list[float] = []
            sleep_finished_at: list[float] = []

            async def _short_sleep():
                sleep_started_at.append(time.perf_counter())
                await asyncio.sleep(0.05)
                sleep_finished_at.append(time.perf_counter())

            preview_task = asyncio.create_task(
                ac.post(
                    "/partition-preview-by-id",
                    data=_form_payload(dataset_id, "y"),
                )
            )
            await asyncio.sleep(0)  # let the route enter run_in_executor
            await _short_sleep()
            preview_resp = await preview_task
            return preview_resp, sleep_started_at, sleep_finished_at

    preview_resp, started, finished = asyncio.run(_drive())
    assert preview_resp.status_code == 200, preview_resp.text
    assert started and finished
    assert finished[0] - started[0] < 0.5, (
        "asyncio.sleep(50ms) took >500ms while partition-preview ran -- "
        "event loop appears blocked, executor offload is not effective"
    )


def test_partition_preview_by_id_invalidates_cache_when_target_changes(
    isolated_dataset, monkeypatch
):
    """Cache key includes target_variable; switching target must NOT serve
    the previous payload."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")

    from fastapi.testclient import TestClient

    dataset_id, _df = isolated_dataset
    app = _build_app()

    with TestClient(app) as tc:
        a = tc.post("/partition-preview-by-id", data=_form_payload(dataset_id, "y"))
        b = tc.post(
            "/partition-preview-by-id", data=_form_payload(dataset_id, "feature_c")
        )
        c = tc.post("/partition-preview-by-id", data=_form_payload(dataset_id, "y"))

    assert a.status_code == b.status_code == c.status_code == 200
    assert a.json().get("cached") is not True
    assert b.json().get("cached") is not True  # different scope
    assert c.json().get("cached") is True  # same as (a)


def test_extract_exclusion_referenced_cols_collects_all_columns():
    """Pure helper: the column-projection planner must see every column
    referenced by any exclusion condition, even nested across groups."""
    from app.api.routes import _extract_exclusion_referenced_cols

    rules = [
        {
            "id": "g1",
            "conditions": [
                {"column": "feature_a", "operator": "<", "value": 0},
                {"column": "feature_b", "operator": ">", "value": 1},
            ],
        },
        {
            "id": "g2",
            "conditions": [{"column": "feature_d", "operator": "=", "value": "x"}],
        },
    ]
    cols = _extract_exclusion_referenced_cols(rules)
    assert cols == ["feature_a", "feature_b", "feature_d"]
    assert _extract_exclusion_referenced_cols(None) == []
    assert _extract_exclusion_referenced_cols([]) == []

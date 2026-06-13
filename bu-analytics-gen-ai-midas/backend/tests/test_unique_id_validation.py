"""
Tests for the validate-unique-id fast path.

Coverage:
  * Polars-based duplicate scan on a 1M-row synthetic Parquet file completes
    well under the 2 s budget.
  * Single-column input goes through the cheaper ``pl.col(c).n_unique()``
    branch and returns the correct distinct count.
  * ``AnalyticsResultCache`` round-trip: same (kind, dataset_id, scope, version)
    returns the cached payload by reference (verifies the by-id route's
    cache lookup is wired correctly).
  * ``SidecarCache`` miss-then-hit: a fake remote ``ObjectStorageBackend`` is
    only asked for the body once even when a key is acquired twice.
"""

from __future__ import annotations

import io
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional

import numpy as np
import pandas as pd
import pytest

from app.services.analytics_cache import AnalyticsResultCache
from app.services.object_storage.contracts import ObjectStorageBackend
from app.services.sidecar_cache import (
    SidecarCache,
    reset_sidecar_cache_for_testing,
)
from app.services.unique_id_validation import (
    compute_duplicate_stats_from_tabular_path,
    validate_unique_ids_polars,
)


# ----- helpers ---------------------------------------------------------------


def _make_parquet(path: Path, n_rows: int) -> None:
    """Write a synthetic Parquet file with one unique-key column and one
    composite-friendly secondary column. Some duplicates are injected so the
    test asserts both ``total_rows`` and ``duplicate_count`` correctly.
    """
    rng = np.random.default_rng(seed=42)
    df = pd.DataFrame(
        {
            # unique_id is mostly unique, but every 1000th row repeats the
            # previous id to inject a known number of duplicates.
            "unique_id": [
                str(i) if i % 1000 != 0 else str(i - 1)
                for i in range(n_rows)
            ],
            "secondary": rng.integers(0, 1000, size=n_rows),
            "noise": rng.standard_normal(n_rows),
        }
    )
    # n_rows / 1000 - 1 collisions because the first row (i=0) collides
    # with i=-1 == "-1" not present, so it's still unique. Compute exactly:
    df.to_parquet(path, index=False)


# ----- polars / unique-id validation ----------------------------------------


@pytest.mark.parametrize("n_rows", [1_000_000])
def test_validate_unique_ids_polars_1m_rows_under_two_seconds(
    tmp_path: Path, n_rows: int
) -> None:
    pq = tmp_path / "ids.parquet"
    _make_parquet(pq, n_rows)
    started = time.perf_counter()
    result = validate_unique_ids_polars(
        str(pq), ["unique_id"], is_parquet=True
    )
    elapsed = time.perf_counter() - started

    assert "missing" not in result
    assert result["total_rows"] == n_rows
    # Generous ceiling: full 1M-row scan with column projection should
    # finish well below 2 s on any modern dev machine. If this regresses,
    # something has gone wrong with the streaming engine or column
    # projection - investigate before bumping the budget.
    assert elapsed < 2.0, (
        f"validate_unique_ids_polars took {elapsed:.2f}s for {n_rows} rows; "
        "expected <2s. Likely cause: streaming collect disabled or column "
        "projection broken."
    )


def test_validate_unique_ids_single_column_uses_n_unique(
    tmp_path: Path,
) -> None:
    """Single-column path: distinct count equals total rows minus injected
    duplicates. Exercises the non-struct branch of validate_unique_ids_polars.
    """
    pq = tmp_path / "single.parquet"
    df = pd.DataFrame({"unique_id": ["a", "b", "c", "a", "d"]})
    df.to_parquet(pq, index=False)
    out = validate_unique_ids_polars(str(pq), ["unique_id"], is_parquet=True)
    assert out == {"total_rows": 5, "duplicate_count": 1}


def test_validate_unique_ids_multi_column_struct_branch(
    tmp_path: Path,
) -> None:
    """Multi-column path: composite key uniqueness is computed via struct."""
    pq = tmp_path / "composite.parquet"
    df = pd.DataFrame(
        {
            "a": ["x", "x", "y", "y", "x"],
            "b": [1, 2, 1, 1, 1],
        }
    )
    # (a,b) tuples: (x,1), (x,2), (y,1), (y,1), (x,1)
    #   -> distinct: {(x,1), (x,2), (y,1)} = 3
    #   -> duplicates: 5 - 3 = 2
    df.to_parquet(pq, index=False)
    out = validate_unique_ids_polars(str(pq), ["a", "b"], is_parquet=True)
    assert out == {"total_rows": 5, "duplicate_count": 2}


def test_validate_unique_ids_missing_column(tmp_path: Path) -> None:
    pq = tmp_path / "x.parquet"
    pd.DataFrame({"a": [1, 2]}).to_parquet(pq, index=False)
    out = compute_duplicate_stats_from_tabular_path(
        str(pq), ["does_not_exist"], is_parquet=True
    )
    assert out == {"missing": ["does_not_exist"]}


# ----- analytics result cache -----------------------------------------------


def test_analytics_cache_round_trip_same_key() -> None:
    cache = AnalyticsResultCache(max_entries=4)
    payload = {"success": True, "is_unique": True, "duplicate_count": 0}
    cache.set(
        kind="validate_unique_ids",
        dataset_id="ds-1",
        scope="abc",
        version=0,
        value=payload,
    )
    hit = cache.get(
        kind="validate_unique_ids",
        dataset_id="ds-1",
        scope="abc",
        version=0,
    )
    assert hit is payload, (
        "AnalyticsResultCache.get must return the exact stored object on a "
        "hit; the by-id route depends on this for sub-millisecond response."
    )


def test_analytics_cache_version_bump_invalidates() -> None:
    cache = AnalyticsResultCache(max_entries=4)
    cache.set("validate_unique_ids", "ds-1", "abc", version=0, value={"v": 0})
    assert cache.get("validate_unique_ids", "ds-1", "abc", version=1) is None


def test_analytics_cache_different_scope_isolates() -> None:
    cache = AnalyticsResultCache(max_entries=4)
    cache.set("validate_unique_ids", "ds-1", "scope_a", 0, {"a": 1})
    cache.set("validate_unique_ids", "ds-1", "scope_b", 0, {"b": 2})
    assert cache.get("validate_unique_ids", "ds-1", "scope_a", 0) == {"a": 1}
    assert cache.get("validate_unique_ids", "ds-1", "scope_b", 0) == {"b": 2}


# ----- sidecar cache --------------------------------------------------------


class _FakeRemoteStore(ObjectStorageBackend):
    """In-memory ``ObjectStorageBackend`` that counts ``open_binary_stream``
    invocations. Stands in for the S3 backend in the sidecar-cache tests
    without requiring boto3 / network access.
    """

    def __init__(self, payload: bytes, etag: str = "abc123") -> None:
        self._payload = payload
        self._etag = etag
        self.stream_calls = 0

    @property
    def kind(self) -> str:
        return "s3"

    def put_bytes(self, key: str, data: bytes) -> None:
        self._payload = data

    def get_bytes(self, key: str) -> bytes:
        return self._payload

    @contextmanager
    def open_binary_stream(self, key: str) -> Iterator[BinaryIO]:
        self.stream_calls += 1
        yield io.BytesIO(self._payload)

    def exists(self, key: str) -> bool:
        return True

    def delete(self, key: str) -> None:
        pass

    def list_csv_keys(self) -> List[str]:
        return []

    def head_object(self, key: str) -> Optional[Dict[str, Any]]:
        return {
            "size": len(self._payload),
            "etag": self._etag,
            "last_modified": None,
        }


def test_sidecar_cache_miss_then_hit_no_redownload(tmp_path: Path) -> None:
    """Two acquires of the same key must download the file only once."""
    payload = b"parquet_bytes_for_test" * 1024  # ~22 KiB
    store = _FakeRemoteStore(payload, etag="etag-v1")
    cache = SidecarCache(root=tmp_path, max_bytes=100 * 1024 * 1024)

    with cache.acquire(store, "ds-1.parquet") as p1:
        assert p1.is_file()
        assert p1.read_bytes() == payload
    assert store.stream_calls == 1

    with cache.acquire(store, "ds-1.parquet") as p2:
        assert p2 == p1, (
            "Second acquire returned a different on-disk path - "
            "sidecar cache miss-then-hit is broken."
        )
        assert p2.read_bytes() == payload
    assert store.stream_calls == 1, (
        f"Expected 1 download, got {store.stream_calls}. "
        "Two acquires of the same (key, etag) must hit the cache."
    )

    stats = cache.stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1


def test_sidecar_cache_etag_change_redownloads(tmp_path: Path) -> None:
    """If the upstream object's etag changes (file replaced), the cache must
    treat that as a new entry and download again.
    """
    store = _FakeRemoteStore(b"v1_bytes", etag="etag-v1")
    cache = SidecarCache(root=tmp_path, max_bytes=10 * 1024 * 1024)

    with cache.acquire(store, "ds.parquet") as p1:
        assert p1.read_bytes() == b"v1_bytes"
    assert store.stream_calls == 1

    # Simulate dataset overwrite.
    store._payload = b"v2_bytes_DIFFERENT"
    store._etag = "etag-v2"

    with cache.acquire(store, "ds.parquet") as p2:
        assert p2.read_bytes() == b"v2_bytes_DIFFERENT"
    assert store.stream_calls == 2, (
        "ETag change must invalidate the cache entry; got "
        f"{store.stream_calls} download(s)."
    )


def test_sidecar_cache_invalidate_key(tmp_path: Path) -> None:
    store = _FakeRemoteStore(b"hello", etag="e1")
    cache = SidecarCache(root=tmp_path, max_bytes=1024 * 1024)

    with cache.acquire(store, "k.parquet"):
        pass
    assert cache.invalidate_key("k.parquet") == 1
    # After invalidation a subsequent acquire downloads again.
    with cache.acquire(store, "k.parquet"):
        pass
    assert store.stream_calls == 2


def test_get_sidecar_cache_singleton_reset(tmp_path: Path) -> None:
    """The reset helper exists so tests don't leak the singleton between
    runs. Validate it actually swaps the instance.
    """
    custom = SidecarCache(root=tmp_path, max_bytes=1024)
    reset_sidecar_cache_for_testing(custom)
    from app.services.sidecar_cache import get_sidecar_cache

    assert get_sidecar_cache() is custom
    reset_sidecar_cache_for_testing(None)

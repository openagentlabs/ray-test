"""Tests for ``DatasetManager.read_csv_for_upload``.

The interesting behaviour under test is the Parquet-sidecar fast path that
makes ``/api/v1/upload`` fast enough on multi-GB CSVs to stay inside the
ALB's 60 s idle timeout. Specifically:

1. When a Parquet sidecar exists alongside the CSV (e.g. written by the
   chunked-upload finalize background job), the function reads from
   Parquet and never calls ``store.get_bytes`` against the CSV. This is
   what avoids the ~2 GB allocation + slow pandas parse that previously
   produced 504 Gateway Time-out responses.

2. When only the CSV exists, the function streams the CSV body to a temp
   file via ``store.open_binary_stream`` rather than buffering it in
   process memory via ``store.get_bytes``. We assert that ``get_bytes``
   is **not** called, so peak RAM stays bounded by the per-chunk read
   size (4 MiB) rather than the full file size.

3. When the Parquet sidecar exists but is corrupt, the function falls
   back to the CSV streaming path so that a bad sidecar never breaks
   uploads.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import pandas as pd
import pytest


@pytest.fixture
def isolated_dataset_manager(monkeypatch, tmp_path):
    """Rebind global object storage + DatasetManager to a clean tmp dir.

    Mirrors the pattern already used in ``test_chunked_upload.py`` so the
    test starts with no datasets and an empty bucket.
    """
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    from app.core import config as core_config

    monkeypatch.setattr(core_config.settings, "UPLOAD_DIR", str(tmp_path))

    from app.services.object_storage import registry as _store_registry
    from app.services.object_storage.local_object_storage import LocalObjectStorage

    store = LocalObjectStorage(tmp_path)
    _store_registry.set_object_storage(store)

    from app.services.dataset_service import dataset_manager

    monkeypatch.setattr(dataset_manager, "upload_dir", tmp_path)
    dataset_manager.datasets.clear()

    return dataset_manager, store, tmp_path


def _write_csv(path: Path, rows: int = 8) -> pd.DataFrame:
    """Write a small CSV and return the canonical DataFrame."""
    df = pd.DataFrame(
        {
            "id": range(rows),
            "label": [f"row-{i}" for i in range(rows)],
            "value": [float(i) * 1.5 for i in range(rows)],
        }
    )
    df.to_csv(path, index=False)
    return df


def test_read_csv_for_upload_prefers_parquet_sidecar_when_present(
    isolated_dataset_manager,
):
    dataset_manager, store, tmp_path = isolated_dataset_manager

    csv_key = "abc123_data.csv"
    csv_path = tmp_path / csv_key
    expected = _write_csv(csv_path, rows=12)

    pyarrow = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    table = pyarrow.Table.from_pandas(expected, preserve_index=False)
    pq_path = tmp_path / "abc123_data.parquet"
    pq.write_table(table, pq_path)

    get_bytes_calls: List[str] = []
    real_get_bytes = store.get_bytes

    def _spy_get_bytes(key: str) -> bytes:
        get_bytes_calls.append(key)
        return real_get_bytes(key)

    store.get_bytes = _spy_get_bytes  # type: ignore[assignment]

    df = dataset_manager.read_csv_for_upload(csv_key)

    assert df.shape == expected.shape
    assert list(df.columns) == list(expected.columns)
    pd.testing.assert_frame_equal(
        df.reset_index(drop=True),
        expected.reset_index(drop=True),
        check_dtype=False,
    )
    assert csv_key not in get_bytes_calls, (
        "parquet path must not call store.get_bytes on the CSV "
        f"(saw: {get_bytes_calls})"
    )


def test_read_csv_for_upload_csv_fallback_streams_without_get_bytes(
    isolated_dataset_manager,
):
    dataset_manager, store, tmp_path = isolated_dataset_manager

    csv_key = "def456_data.csv"
    csv_path = tmp_path / csv_key
    expected = _write_csv(csv_path, rows=6)

    assert not (tmp_path / "def456_data.parquet").exists()

    get_bytes_calls: List[str] = []
    real_get_bytes = store.get_bytes

    def _spy_get_bytes(key: str) -> bytes:
        get_bytes_calls.append(key)
        return real_get_bytes(key)

    store.get_bytes = _spy_get_bytes  # type: ignore[assignment]

    df = dataset_manager.read_csv_for_upload(csv_key)

    assert df.shape == expected.shape
    assert list(df.columns) == list(expected.columns)
    assert csv_key not in get_bytes_calls, (
        "csv fallback must stream via open_binary_stream, not buffer via "
        f"store.get_bytes (saw: {get_bytes_calls})"
    )


def test_read_csv_for_upload_falls_back_when_parquet_corrupt(
    isolated_dataset_manager,
):
    dataset_manager, store, tmp_path = isolated_dataset_manager

    csv_key = "ghi789_data.csv"
    csv_path = tmp_path / csv_key
    expected = _write_csv(csv_path, rows=4)

    (tmp_path / "ghi789_data.parquet").write_bytes(b"not a parquet file")

    df = dataset_manager.read_csv_for_upload(csv_key)

    assert df.shape == expected.shape
    assert list(df.columns) == list(expected.columns)


def test_read_csv_for_upload_handles_legacy_absolute_path(
    isolated_dataset_manager,
):
    """Legacy callers pass an absolute filesystem path instead of a key."""
    dataset_manager, _store, tmp_path = isolated_dataset_manager

    csv_path = tmp_path / "legacy_dataset.csv"
    expected = _write_csv(csv_path, rows=5)

    df = dataset_manager.read_csv_for_upload(str(csv_path))

    assert df.shape == expected.shape
    assert list(df.columns) == list(expected.columns)


def test_read_csv_for_upload_csv_fallback_uses_polars_first(
    isolated_dataset_manager, monkeypatch,
):
    """When parquet is unavailable, the CSV fallback prefers Polars's
    multithreaded reader over ``pd.read_csv`` because Polars is ~3-5x faster
    on multi-GB CSVs (which is exactly the case where the chunked-finalize
    background parquet job hasn't finished by the time the user clicks
    Submit). We assert this by counting calls to ``pd.read_csv`` -- if Polars
    handled the read, pandas's reader is never invoked."""
    dataset_manager, _store, tmp_path = isolated_dataset_manager
    pytest.importorskip("polars")

    csv_key = "polars_test_data.csv"
    csv_path = tmp_path / csv_key
    expected = _write_csv(csv_path, rows=20)

    assert not (tmp_path / "polars_test_data.parquet").exists()

    pd_read_csv_calls: List[str] = []
    real_pd_read_csv = pd.read_csv

    def _spy_pd_read_csv(*args, **kwargs):
        pd_read_csv_calls.append(str(args[0]) if args else "<no-arg>")
        return real_pd_read_csv(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", _spy_pd_read_csv)

    df = dataset_manager.read_csv_for_upload(csv_key)

    assert df.shape == expected.shape
    assert list(df.columns) == list(expected.columns)
    assert pd_read_csv_calls == [], (
        "Polars must own the CSV fallback path on a healthy file; "
        f"pd.read_csv was called {len(pd_read_csv_calls)} time(s): "
        f"{pd_read_csv_calls}"
    )


def test_read_csv_for_upload_falls_back_to_pandas_when_polars_raises(
    isolated_dataset_manager, monkeypatch,
):
    """If Polars raises (encoding hiccup, schema surprise, missing dep), the
    code must still produce a valid DataFrame via the legacy pandas multi-
    encoding loop. Lock that in so the new fast path doesn't degrade
    correctness on quirky CSVs."""
    dataset_manager, _store, tmp_path = isolated_dataset_manager

    csv_key = "polars_fail_data.csv"
    csv_path = tmp_path / csv_key
    expected = _write_csv(csv_path, rows=6)

    try:
        import polars as pl  # noqa: WPS433
    except ImportError:
        pytest.skip("polars not installed in this venv")

    real_pl_read_csv = pl.read_csv

    def _broken_pl_read_csv(*_args, **_kwargs):
        raise RuntimeError("simulated polars failure")

    monkeypatch.setattr(pl, "read_csv", _broken_pl_read_csv)

    df = dataset_manager.read_csv_for_upload(csv_key)

    assert df.shape == expected.shape
    assert list(df.columns) == list(expected.columns)

    # restore so other tests in the same session see the real reader
    monkeypatch.setattr(pl, "read_csv", real_pl_read_csv)

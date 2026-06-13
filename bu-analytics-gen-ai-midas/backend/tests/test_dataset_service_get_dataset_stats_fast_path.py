"""Tests for ``DatasetManager.get_dataset_stats`` cheap-path flags.

These flags exist because ``df.duplicated().sum()`` and ``df.isnull().sum()``
on a 2 GB / ~5 M-row pandas DataFrame each take 30-60 s, and that was
keeping the ``/api/v1/upload`` request well past the AWS ALB's 60 s
default idle timeout, returning 504 Gateway Time-out at the load
balancer. On the ``existing_dataset_id`` path the response payload
those scans populate is not consumed by the frontend, so the caller
opts out via ``skip_missing_summary`` / ``skip_duplicate_count``.

We assert behavior, not wall-clock: the flags must return correct
shape information AND must not invoke the expensive pandas full-frame
operations.
"""

from __future__ import annotations

import pandas as pd
import pytest


def _make_df_with_dups_and_missing() -> pd.DataFrame:
    """Small frame with both duplicates and missing values to assert the flag
    semantics flip the populated counters."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 3, 4, 5, 5, 5],
            "label": ["a", "b", None, "c", "c", None, "d", "d"],
            "value": [10.0, 20.0, 30.0, 30.0, 40.0, 50.0, 60.0, 60.0],
        }
    )


@pytest.fixture
def dataset_manager_singleton(monkeypatch, tmp_path):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    from app.core import config as core_config

    monkeypatch.setattr(core_config.settings, "UPLOAD_DIR", str(tmp_path))

    from app.services.dataset_service import dataset_manager

    monkeypatch.setattr(dataset_manager, "upload_dir", tmp_path)
    return dataset_manager


def test_get_dataset_stats_default_computes_full_summaries(dataset_manager_singleton):
    df = _make_df_with_dups_and_missing()
    stats = dataset_manager_singleton.get_dataset_stats(df, target_variable="value")

    assert stats.rows == 8
    assert stats.columns == 3
    assert stats.duplicate_rows >= 1
    assert stats.missing_values, "default path must populate missing_values"


def test_get_dataset_stats_skip_flags_avoid_expensive_calls(dataset_manager_singleton):
    df = _make_df_with_dups_and_missing()

    isnull_calls = {"count": 0}
    duplicated_calls = {"count": 0}

    real_isnull = pd.DataFrame.isnull
    real_duplicated = pd.DataFrame.duplicated

    def _spy_isnull(self):
        isnull_calls["count"] += 1
        return real_isnull(self)

    def _spy_duplicated(self, *a, **kw):
        duplicated_calls["count"] += 1
        return real_duplicated(self, *a, **kw)

    pd.DataFrame.isnull = _spy_isnull
    pd.DataFrame.duplicated = _spy_duplicated
    try:
        stats = dataset_manager_singleton.get_dataset_stats(
            df,
            target_variable="value",
            skip_missing_summary=True,
            skip_duplicate_count=True,
        )
    finally:
        pd.DataFrame.isnull = real_isnull
        pd.DataFrame.duplicated = real_duplicated

    assert stats.rows == 8
    assert stats.columns == 3
    assert stats.missing_values == {}
    assert stats.duplicate_rows == 0
    assert isnull_calls["count"] == 0, (
        "skip_missing_summary must avoid pd.DataFrame.isnull() (O(rows*cols), "
        "~5-15 s on a 2 GB frame)"
    )
    assert duplicated_calls["count"] == 0, (
        "skip_duplicate_count must avoid pd.DataFrame.duplicated() (O(rows), "
        "~30-60 s on a 2 GB frame)"
    )


def test_get_dataset_stats_uses_shallow_memory_usage(dataset_manager_singleton):
    """``deep=True`` walks every Python string in every object column and on
    a 2 GB frame can itself take ~30 s. The implementation must call
    ``memory_usage(deep=False)`` on the hot path."""
    df = _make_df_with_dups_and_missing()

    deep_calls: list = []
    real_memory_usage = pd.DataFrame.memory_usage

    def _spy_memory_usage(self, *args, **kwargs):
        deep_calls.append(kwargs.get("deep", args[0] if args else None))
        return real_memory_usage(self, *args, **kwargs)

    pd.DataFrame.memory_usage = _spy_memory_usage
    try:
        dataset_manager_singleton.get_dataset_stats(df, target_variable="value")
    finally:
        pd.DataFrame.memory_usage = real_memory_usage

    assert deep_calls, "expected get_dataset_stats to call df.memory_usage()"
    assert all(d is False for d in deep_calls), (
        f"get_dataset_stats must use memory_usage(deep=False); saw deep={deep_calls}"
    )


def test_get_dataset_stats_passed_duplicate_rows_skips_recompute(
    dataset_manager_singleton,
):
    """When the caller already knows the duplicate count it must NOT be
    recomputed; ``df.duplicated()`` is the slowest single op on a 2 GB
    frame."""
    df = _make_df_with_dups_and_missing()

    duplicated_calls = {"count": 0}
    real_duplicated = pd.DataFrame.duplicated

    def _spy_duplicated(self, *a, **kw):
        duplicated_calls["count"] += 1
        return real_duplicated(self, *a, **kw)

    pd.DataFrame.duplicated = _spy_duplicated
    try:
        stats = dataset_manager_singleton.get_dataset_stats(
            df, target_variable="value", duplicate_rows=42
        )
    finally:
        pd.DataFrame.duplicated = real_duplicated

    assert stats.duplicate_rows == 42
    assert duplicated_calls["count"] == 0, (
        "passing duplicate_rows must short-circuit the df.duplicated() scan"
    )

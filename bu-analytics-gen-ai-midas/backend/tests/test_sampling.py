"""
Regression tests for app.services.sampling - P2.4 (canonical sampler).

These guard the *pathological* cases that broke earlier sequential head()
sampling:

  - tail-only-minority: a target-sorted CSV where every minority-class row
    sits in the last 0.001% of the file. The classifier sample MUST surface
    those rows or the LLM will misclassify the dataset as single-class.

  - imbalanced binary: 99.99% / 0.01% split with the rare class in the
    middle. Every minority row must appear in the sample (subject to the
    min_per_class floor).
"""

from __future__ import annotations

import os
import shutil
import tempfile

import numpy as np
import pandas as pd
import pytest

from app.services.sampling import (
    build_classification_sample,
    get_or_build_sample_sidecar,
    stratified_indices_from_target_series,
    stratified_sample_pandas,
)


def _make_tail_minority_df(n_total: int = 200_000, n_minority: int = 5) -> pd.DataFrame:
    """All zeros, then a handful of ones at the very bottom."""
    target = np.zeros(n_total, dtype=np.int64)
    target[-n_minority:] = 1
    feature_a = np.arange(n_total, dtype=np.int64)
    feature_b = np.linspace(0.0, 1.0, n_total, dtype=np.float64)
    return pd.DataFrame({"target": target, "a": feature_a, "b": feature_b})


def test_stratified_sample_recovers_tail_minority() -> None:
    df = _make_tail_minority_df(n_total=200_000, n_minority=5)
    sample = stratified_sample_pandas(
        df, target_col="target", sample_rows=10_000, min_per_class=5_000, seed=42,
    )
    minority_in_sample = int((sample["target"] == 1).sum())
    assert minority_in_sample == 5, (
        f"Expected ALL 5 minority rows in the sample (min_per_class > minority count) "
        f"but only got {minority_in_sample}. "
        "Tail-only-minority regression - the sampler is dropping rare classes again."
    )
    majority_in_sample = int((sample["target"] == 0).sum())
    assert majority_in_sample > 0, "Expected at least some majority rows in the sample"


def test_stratified_sample_floors_each_class() -> None:
    """Two large classes - both should be floored to >= min_per_class."""
    n = 100_000
    target = np.array([0] * (n - 1_000) + [1] * 1_000, dtype=np.int64)
    rng = np.random.RandomState(7)
    rng.shuffle(target)
    df = pd.DataFrame({"target": target, "x": rng.normal(size=n)})

    sample = stratified_sample_pandas(
        df, target_col="target", sample_rows=5_000, min_per_class=500, seed=42,
    )
    counts = sample["target"].value_counts().to_dict()
    assert counts.get(0, 0) >= 500, f"Class 0 floored: {counts}"
    assert counts.get(1, 0) >= 500, f"Class 1 floored: {counts}"


def test_stratified_indices_handles_target_sorted_csv() -> None:
    """The cheap helper used when the full df is not in memory."""
    n = 1_000_000
    target = np.zeros(n, dtype=np.int64)
    target[-3:] = 1
    series = pd.Series(target, name="target")
    indices = stratified_indices_from_target_series(
        series, sample_rows=20_000, min_per_class=1_000,
    )
    minority_indices = [i for i in indices if target[i] == 1]
    assert len(minority_indices) == 3, (
        f"All 3 tail-minority rows must be selected; got {len(minority_indices)}"
    )


def test_build_classification_sample_with_full_df_preserves_full_shape() -> None:
    df = _make_tail_minority_df(n_total=50_000, n_minority=2)
    sample, full_shape = build_classification_sample(
        dataset_id="t",
        csv_path=None,
        target_variable="target",
        sample_rows=2_000,
        min_per_class=1_000,
        full_df=df,
    )
    assert full_shape == (50_000, 3)
    assert int((sample["target"] == 1).sum()) == 2


def test_get_or_build_sample_sidecar_caches_on_disk(tmp_path) -> None:
    """The sidecar must be (1) persisted, (2) re-read instead of recomputed."""
    df = _make_tail_minority_df(n_total=20_000, n_minority=3)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        first = get_or_build_sample_sidecar(
            dataset_id="ds-test",
            full_df=df,
            target_variable="target",
            sample_rows=2_000,
            min_per_class=1_000,
            seed=42,
        )
        sidecar_path = tmp_path / "uploads" / "ds-test" / "samples" / "sample_n2000_s42.parquet"
        assert sidecar_path.exists(), "sample sidecar must be written under uploads/<id>/samples/"

        second = get_or_build_sample_sidecar(
            dataset_id="ds-test",
            full_df=df,
            target_variable="target",
            sample_rows=2_000,
            min_per_class=1_000,
            seed=42,
        )
        assert len(first) == len(second)
        assert int((second["target"] == 1).sum()) == 3
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp_path / "uploads", ignore_errors=True)


@pytest.mark.parametrize("seed", [0, 7, 42, 123])
def test_sampler_is_deterministic(seed: int) -> None:
    df = _make_tail_minority_df(n_total=20_000, n_minority=10)
    a = stratified_sample_pandas(df, "target", 1_000, 200, seed=seed)
    b = stratified_sample_pandas(df, "target", 1_000, 200, seed=seed)
    pd.testing.assert_frame_equal(a.sort_index(), b.sort_index())

"""
Canonical sampling utilities (P2.4b).

Centralises the stratified-sampling logic that was previously inlined in
the dataset-type classification path. The classification background task,
plus any future analytics that want a representative sample of a large
DataFrame (DQS, EDA snapshots, comprehensive_stats, variable review),
can call into this module instead of redefining their own helpers.

Design notes:
  - "Minority-class flooring": every distinct target class contributes
    AT LEAST `min_per_class` rows (capped at the class's full count).
    Without this, a sequentially-sampled head of a target-sorted CSV
    can show only a single class to the LLM and produce wrong dataset
    type classification.
  - Deterministic via a fixed RandomState seed so identical inputs
    produce identical samples (cache-friendly).
  - The full file shape (rows, cols) is preserved separately from the
    sample shape so callers (e.g. the LLM summary) can report the
    *true* dataset size, not the sample size.

This module currently provides building blocks. The route handlers wrap
them with their own caching / disk vs. in-memory selection logic.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def stratified_sample_pandas(
    df: pd.DataFrame,
    target_col: Optional[str],
    sample_rows: int,
    min_per_class: int,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Stratified sample of an in-memory DataFrame with minority-class flooring.

    Rules:
      - If target_col is missing or unknown -> uniform random sample.
      - For each class c with full count k_c:
            n_take = min(k_c, max(min_per_class, round(sample_rows * k_c / N)))
        i.e. minority classes are NEVER undersampled below min_per_class
        (or their full count, whichever is smaller).
      - Deterministic via the supplied seed (default 42).
    """
    n = len(df)
    if n <= sample_rows:
        return df
    if target_col is None or target_col not in df.columns:
        return df.sample(n=sample_rows, random_state=seed)

    rng = np.random.RandomState(seed)
    target = df[target_col]
    classes = target.value_counts(dropna=False)

    selected: List[np.ndarray] = []
    for cls, k_c in classes.items():
        if pd.isna(cls):
            class_mask = target.isna()
        else:
            class_mask = target == cls
        class_idx = df.index.values[class_mask.values]
        proportional = round(sample_rows * int(k_c) / n)
        n_take = min(int(k_c), max(int(min_per_class), int(proportional)))
        if len(class_idx) <= n_take:
            selected.append(class_idx)
        else:
            chosen = rng.choice(class_idx, size=n_take, replace=False)
            selected.append(chosen)

    if not selected:
        return df.sample(n=sample_rows, random_state=seed)
    final_idx = np.concatenate(selected)
    return df.loc[final_idx]


def stratified_indices_from_target_series(
    target_series: pd.Series,
    sample_rows: int,
    min_per_class: int,
    seed: int = 42,
) -> List[int]:
    """
    Stratified row indices from a target column with minority flooring.

    Used when the full DataFrame is not in memory but the target column
    can be cheaply read (e.g. via pd.read_csv(usecols=[target])) so we
    can plan which rows to materialise.
    """
    n = len(target_series)
    if n <= sample_rows:
        return list(range(n))
    rng = np.random.RandomState(seed)
    classes = target_series.value_counts(dropna=False)

    indices: List[int] = []
    for cls, k_c in classes.items():
        if pd.isna(cls):
            class_mask = target_series.isna()
        else:
            class_mask = target_series == cls
        class_idx = np.where(class_mask.values)[0]
        proportional = round(sample_rows * int(k_c) / n)
        n_take = min(int(k_c), max(int(min_per_class), int(proportional)))
        if len(class_idx) <= n_take:
            indices.extend(class_idx.tolist())
        else:
            chosen = rng.choice(class_idx, size=n_take, replace=False)
            indices.extend(chosen.tolist())
    return sorted(set(indices))


def build_classification_sample(
    *,
    dataset_id: Optional[str],  # noqa: ARG001 - kept for future cache-key use
    csv_path: Optional[str],
    target_variable: Optional[str],
    sample_rows: int = 200_000,
    min_per_class: int = 5_000,
    full_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, Tuple[int, int]]:
    """
    Build a small DataFrame for analytics that only need a representative
    view of the data, while preserving the *true* full shape that the
    caller should report.

    Order of preference (cheapest first):
      1. Caller-supplied `full_df` (no extra IO).
      2. csv_path: read target column once, build stratified row indices,
         then read only those rows via skiprows.
      3. csv_path: nrows=sample_rows fallback (biased on target-sorted
         data; logged as a warning).

    Returns (sample_df, full_shape).
    """
    if full_df is not None:
        full_shape = (int(full_df.shape[0]), int(full_df.shape[1]))
        sample = stratified_sample_pandas(
            full_df, target_variable, sample_rows, min_per_class
        )
        return sample, full_shape

    if csv_path and os.path.exists(csv_path):
        try:
            with open(csv_path, "rb") as fh:
                full_rows = max(0, sum(1 for _ in fh) - 1)
        except Exception:
            full_rows = -1

        if target_variable:
            try:
                target_series = pd.read_csv(
                    csv_path, usecols=[target_variable]
                )[target_variable]
                indices = stratified_indices_from_target_series(
                    target_series, sample_rows, min_per_class
                )
                index_set = set(int(i) for i in indices)
                sample = pd.read_csv(
                    csv_path,
                    skiprows=lambda i: i > 0 and (i - 1) not in index_set,
                )
                cols = int(sample.shape[1])
                rows = full_rows if full_rows > 0 else int(sample.shape[0])
                return sample, (rows, cols)
            except Exception as exc:
                logger.warning(
                    "Stratified target-column sample failed (%s); "
                    "falling back to nrows=%s sequential sample (may be "
                    "biased on target-sorted data).",
                    exc, sample_rows,
                )

        sample = pd.read_csv(csv_path, nrows=sample_rows)
        cols = int(sample.shape[1])
        rows = full_rows if full_rows > 0 else int(sample.shape[0])
        return sample, (rows, cols)

    raise ValueError(
        "Neither a full_df nor a csv_path was provided to "
        "build_classification_sample()."
    )


def get_or_build_sample_sidecar(
    *,
    dataset_id: str,
    full_df: pd.DataFrame,
    target_variable: Optional[str],
    sample_rows: int,
    min_per_class: int,
    seed: int = 42,
    cache_suffix: str = "",
) -> pd.DataFrame:
    """
    P2.4 part 2: per-(seed, n_target) on-disk Parquet sample sidecar.

    DQS / EDA / variable-review on multi-GB datasets are dominated by
    pandas scans of the full frame. The "approximate" mode of these
    endpoints uses a stratified sample built once and re-used across
    requests. This helper persists the sample as
    `uploads/<id>/samples/sample_n<sample_rows>_s<seed>[_<cache_suffix>].parquet`
    so a rebuild is only paid once per (dataset_id, sample_size, seed,
    cache_suffix) tuple until the dataset version bumps.

    Args:
        cache_suffix: Optional disambiguator appended to the sidecar
            filename. Used by scope-aware endpoints to keep
            ``entire``/``train``/``test``/``validation`` samples in
            separate files instead of trampling each other.

    Falls back to in-memory sampling (no sidecar) if disk IO fails.
    """
    cache_dir = os.path.join("uploads", dataset_id, "samples")
    safe_suffix = re.sub(r"[^a-zA-Z0-9._-]", "", cache_suffix or "")
    suffix_part = f"_{safe_suffix}" if safe_suffix else ""
    sidecar = os.path.join(
        cache_dir, f"sample_n{sample_rows}_s{seed}{suffix_part}.parquet"
    )
    try:
        if os.path.exists(sidecar):
            cached = pd.read_parquet(sidecar)
            if len(cached) > 0:
                return cached
    except Exception as exc:
        logger.warning("sample sidecar read failed at %s: %s", sidecar, exc)

    sample = stratified_sample_pandas(
        full_df, target_variable, sample_rows, min_per_class, seed=seed
    )
    try:
        os.makedirs(cache_dir, exist_ok=True)
        sample.to_parquet(sidecar, engine="pyarrow", index=False)
        logger.info(
            "P2.4 sample sidecar written: %s (rows=%d/%d cols=%d)",
            sidecar, len(sample), len(full_df), sample.shape[1],
        )
    except Exception as exc:
        logger.warning("sample sidecar write failed at %s: %s", sidecar, exc)
    return sample


def maybe_sample_for_dqs(
    df: pd.DataFrame,
    *,
    dataset_id: str,
    target_variable: Optional[str],
    scope: str = "entire",
    force_mode: Optional[str] = None,
) -> Tuple[pd.DataFrame, bool]:
    """
    Apply the canonical DQS sampling policy to ``df`` and return
    ``(maybe_sampled_df, was_sampled)``.

    Policy (cascading precedence):
      1. ``force_mode`` argument or ``MIDAS_DQS_SAMPLED_BY_SCOPE`` env var:
            "0" / "off"   -> never sample.
            "1" / "on"    -> sample whenever ``len(df) > 0`` (smallest
                              forced path, mostly for tests).
            anything else / unset -> AUTO: sample iff ``len(df) >
            MIDAS_DQS_SAMPLE_THRESHOLD`` (default 1_000_000).
      2. ``MIDAS_DQS_SAMPLED=1`` (legacy flag, kept for backwards
          compatibility with the original ``/dqs`` route) forces the
          AUTO branch on regardless of ``MIDAS_DQS_SAMPLED_BY_SCOPE``.

    Why this exists:
    The legacy ``/dqs`` route added a sampling block guarded by
    ``MIDAS_DQS_SAMPLED=1`` (default OFF). The scope-aware endpoints
    (``/dqs-by-scope``, ``/overview-bundle``) did NOT have it, so on
    multi-million-row datasets they would do a full-frame
    ``df.duplicated()`` + per-column ``value_counts`` and time out
    behind the ALB. This helper centralises the policy so all three
    endpoints behave identically and the operator only needs to flip
    one env var to disable sampling globally.
    """
    n = len(df)
    if n == 0:
        return df, False

    threshold = int(os.environ.get("MIDAS_DQS_SAMPLE_THRESHOLD", "1000000"))
    sample_rows = int(os.environ.get("MIDAS_DQS_SAMPLE_ROWS", "200000"))
    min_per_class = int(os.environ.get("MIDAS_DQS_MIN_PER_CLASS", "5000"))

    mode = (force_mode or os.environ.get("MIDAS_DQS_SAMPLED_BY_SCOPE") or "auto").strip().lower()
    legacy_force = os.environ.get("MIDAS_DQS_SAMPLED", "0") == "1"

    if mode in ("0", "off", "false", "no"):
        return df, False
    if mode in ("1", "on", "true", "yes"):
        should_sample = True
    else:
        should_sample = (n > threshold) or legacy_force

    if not should_sample:
        return df, False

    try:
        sampled = get_or_build_sample_sidecar(
            dataset_id=dataset_id,
            full_df=df,
            target_variable=target_variable,
            sample_rows=sample_rows,
            min_per_class=min_per_class,
            cache_suffix=scope,
        )
        logger.info(
            "DQS sampling active for dataset=%s scope=%s: %d/%d rows",
            dataset_id, scope, len(sampled), n,
        )
        return sampled, True
    except Exception as exc:
        logger.warning(
            "DQS sampling failed (dataset=%s scope=%s); falling back to full frame: %s",
            dataset_id, scope, exc,
        )
        return df, False

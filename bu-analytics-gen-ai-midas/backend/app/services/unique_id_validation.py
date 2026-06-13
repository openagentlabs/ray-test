"""
Fast unique-ID duplicate checks for very large CSV/Parquet files.

Uses Polars lazy scans (streaming collect when available) so we only read
the requested identifier columns and avoid building a full-row boolean mask
like ``pandas.DataFrame.duplicated`` on tens of millions of rows.

Duplicate *row* count is ``total_rows - n_distinct_composite_keys``, matching
``df.duplicated(subset=cols).sum()`` for non-null keys.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


def _collect_lazy_agg(lf: Any) -> Any:
    import polars as pl  # noqa: F401

    try:
        return lf.collect(engine="streaming")
    except Exception as exc:
        logger.debug("polars engine=streaming collect failed: %s", exc)
    try:
        return lf.collect(streaming=True)
    except Exception as exc:
        logger.debug("polars streaming=True collect failed: %s", exc)
    return lf.collect()


def _polars_available_columns(path: str, *, is_parquet: bool) -> List[str]:
    import polars as pl

    if is_parquet:
        return list(pl.scan_parquet(path).collect_schema().names())
    return list(pl.read_csv(path, n_rows=0, infer_schema_length=0).columns)


def validate_unique_ids_polars(path: str, requested_cols: List[str], *, is_parquet: bool) -> Dict[str, Any]:
    import polars as pl

    avail = set(_polars_available_columns(path, is_parquet=is_parquet))
    missing = [c for c in requested_cols if c not in avail]
    if missing:
        return {"missing": missing}

    _str = getattr(pl, "String", pl.Utf8)
    if is_parquet:
        lf = pl.scan_parquet(path).select([pl.col(c) for c in requested_cols])
    else:
        # ``select`` after ``scan_csv`` enables column pruning in Polars so only
        # identifier columns are decoded from the CSV.
        lf = pl.scan_csv(
            path,
            try_parse_dates=False,
            infer_schema_length=10_000,
        ).select([pl.col(c).cast(_str, strict=False) for c in requested_cols])

    # Single-column: skip the struct() wrapper - polars then uses a much
    # tighter hash kernel (no per-row struct construction). Multi-column
    # composite keys still need struct so all column values participate
    # in the distinct-count.
    if len(requested_cols) == 1:
        col = requested_cols[0]
        agg_lf = lf.select(
            pl.len().alias("total"),
            pl.col(col).n_unique().alias("n_distinct"),
        )
    else:
        exprs = [pl.col(c) for c in requested_cols]
        agg_lf = lf.select(
            pl.len().alias("total"),
            pl.struct(exprs).n_unique().alias("n_distinct"),
        )
    out = _collect_lazy_agg(agg_lf)
    total = int(out["total"][0])
    n_distinct = int(out["n_distinct"][0])
    duplicate_count = max(0, total - n_distinct)
    return {"total_rows": total, "duplicate_count": duplicate_count}


def validate_unique_ids_pandas(path: str, requested_cols: List[str]) -> Dict[str, Any]:
    header_df = pd.read_csv(path, nrows=0)
    missing = [c for c in requested_cols if c not in header_df.columns]
    if missing:
        return {"missing": missing}
    df_subset = pd.read_csv(path, usecols=requested_cols, low_memory=False)
    total_rows = int(len(df_subset))
    duplicate_count = int(df_subset.duplicated(subset=requested_cols).sum())
    return {"total_rows": total_rows, "duplicate_count": duplicate_count}


def compute_duplicate_stats_from_tabular_path(
    path: str, requested_cols: List[str], *, is_parquet: bool
) -> Dict[str, Any]:
    """
    Return ``{"missing": [...]}`` or ``{"total_rows": int, "duplicate_count": int}``.
    Tries Polars first, then pandas.
    """
    try:
        return validate_unique_ids_polars(path, requested_cols, is_parquet=is_parquet)
    except Exception as exc:
        logger.warning("Polars unique-id validation failed, using pandas: %s", exc)
    return validate_unique_ids_pandas(path, requested_cols)

"""
TrainingDataProvider - the single gateway for reading the training partition.

Rule (Steps 1-4): every metric, every fit, every SHAP call reads from the
**whole training partition only**, regardless of segmentation or
train/test/validation splits. The frontend may (accidentally) pass a
`segment_id`; we log a warning and ignore it. This is the only place where
the rule is enforced, so it can't be bypassed downstream.

Distributed-worker mode: when `train_parquet_available=True` in the job config,
we read `train.parquet` from the job folder in shared storage (written by the
API pod at /rfe/start time). Otherwise we fall back to the local in-process
DataFrameStateManager. This means:
  - Local mode: no parquet, we read directly from DFSM - zero copies.
  - Redis/multi-worker mode: API serialises train partition once per job; all
    workers read that parquet.
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.logging_config import get_logger
from app.services.dataframe_state_manager import dataframe_state_manager

from .storage.base import StorageBackend

_logger = get_logger(__name__)

# System columns that must never be fed to XGBoost as features, regardless of
# what the frontend sent in the working set.
_SYSTEM_COLUMNS = {"split_tag", "__row_id__", "__index__"}


def _coerce_features_for_xgboost(
    X: pd.DataFrame,
) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    XGBoost only accepts int/float/bool/category columns. In practice we see
    string/object columns (IDs like `msno`, raw categoricals like `gender`,
    system tags like `split_tag`) slip through Step 2. We:
      - Drop any column that is all-null after coercion.
      - Label-encode string/object columns to int codes (preserves column name,
        which keeps downstream SHAP / RFE tracking stable).
      - Leave numeric/bool columns alone.

    Returns (coerced_df, encoded_columns, dropped_columns).
    """
    encoded: List[str] = []
    dropped: List[str] = []
    out = X.copy()
    for col in list(out.columns):
        s = out[col]
        if pd.api.types.is_bool_dtype(s):
            out[col] = s.astype("int8")
            continue
        if pd.api.types.is_numeric_dtype(s):
            # Ensure no pandas nullable-int types that xgboost rejects.
            if str(s.dtype).startswith("Int") or str(s.dtype).startswith("UInt") or str(s.dtype) == "Float64":
                out[col] = pd.to_numeric(s, errors="coerce").astype("float64")
            continue
        if pd.api.types.is_datetime64_any_dtype(s) or pd.api.types.is_timedelta64_dtype(s):
            # Use seconds-since-epoch so the signal survives; safer than dropping.
            out[col] = pd.to_numeric(s.view("int64"), errors="coerce").astype("float64")
            encoded.append(col)
            continue
        # Everything else (object, string, category): label-encode to int codes.
        try:
            codes = pd.Categorical(s.astype("string"), ordered=False).codes
            coerced = pd.Series(codes, index=s.index, dtype="int32")
            # -1 in codes means NaN - convert to float NaN so xgboost treats as missing.
            coerced = coerced.astype("float64")
            coerced[coerced == -1] = np.nan
            out[col] = coerced
            encoded.append(col)
        except Exception:
            dropped.append(col)

    if dropped:
        out = out.drop(columns=dropped, errors="ignore")
    return out, encoded, dropped


class TrainingDataProvider:
    def __init__(self, storage: Optional[StorageBackend] = None):
        self._storage = storage

    @staticmethod
    def _warn_and_discard_segment(segment_id: Optional[str]) -> None:
        if segment_id:
            _logger.warning(
                "RFE pipeline ignored segment_id=%s - Steps 1-4 must run on the whole "
                "train partition per architectural rule.",
                segment_id,
            )

    def materialize_train_parquet(
        self,
        *,
        dataset_id: str,
        target: str,
        feature_cols: List[str],
        weight_col: Optional[str],
        job_id: str,
    ) -> bool:
        """
        Called by the API pod on /rfe/start. Serialises the current train
        partition to `<job_folder>/train.parquet` so worker pods can read it
        without access to the in-memory DFSM. Returns True on success.
        """
        if self._storage is None:
            return False
        try:
            df = self._fetch_train_dataframe(dataset_id)
            if df is None:
                return False
            safe_feature_cols = [c for c in feature_cols if c not in _SYSTEM_COLUMNS]
            cols = [
                c
                for c in [target] + list(safe_feature_cols) + ([weight_col] if weight_col else [])
                if c in df.columns
            ]
            subset = df[cols].copy()
            # Parquet serialisation via pandas/pyarrow (pyarrow already in requirements).
            import io

            buf = io.BytesIO()
            subset.to_parquet(buf, index=False)
            self._storage.put_bytes(job_id, "train.parquet", buf.getvalue())
            _logger.info(
                "Persisted train.parquet for job %s (shape=%s)", job_id, subset.shape
            )
            return True
        except Exception as e:
            _logger.warning("Could not persist train.parquet for job %s: %s", job_id, e)
            return False

    def get_xy(
        self,
        *,
        dataset_id: str,
        target: str,
        feature_cols: List[str],
        weight_col: Optional[str] = None,
        segment_id: Optional[str] = None,
        job_id: Optional[str] = None,
        prefer_parquet: bool = False,
    ) -> Tuple[pd.DataFrame, pd.Series, Optional[pd.Series]]:
        """
        Single entrypoint.

        If `prefer_parquet=True` (worker context) and the storage layer has
        `train.parquet` for this job, read that. Else use DFSM locally.
        """
        self._warn_and_discard_segment(segment_id)

        df = None
        if prefer_parquet and self._storage is not None and job_id is not None:
            df = self._read_parquet(job_id)
            if df is None:
                _logger.warning(
                    "Worker prefer_parquet=True but no train.parquet for job %s; "
                    "falling back to DataFrameStateManager.",
                    job_id,
                )
        if df is None:
            df = self._fetch_train_dataframe(dataset_id)
        if df is None:
            raise RuntimeError(
                "No train partition available for dataset_id=%s. Make sure Step 1 "
                "split was configured before launching RFE." % dataset_id
            )

        # Filter out system columns defensively - they must never be features
        # even if the frontend accidentally included them in the screener output.
        safe_feature_cols = [c for c in feature_cols if c not in _SYSTEM_COLUMNS]
        removed_system = sorted(set(feature_cols) - set(safe_feature_cols))
        if removed_system:
            _logger.info(
                "RFE dropped system columns from working set: %s", removed_system
            )

        missing = [c for c in safe_feature_cols if c not in df.columns]
        if missing:
            raise ValueError(
                f"Feature columns not present in train partition: {missing[:10]}"
                + (" ... (truncated)" if len(missing) > 10 else "")
            )
        if target not in df.columns:
            raise ValueError(f"Target column '{target}' not present in train partition.")

        X_raw = df[safe_feature_cols].copy()
        X, encoded_cols, dropped_cols = _coerce_features_for_xgboost(X_raw)
        if encoded_cols:
            _logger.info(
                "RFE label-encoded %d non-numeric features to int codes: %s",
                len(encoded_cols),
                encoded_cols[:20] + (["..."] if len(encoded_cols) > 20 else []),
            )
        if dropped_cols:
            _logger.warning(
                "RFE dropped %d un-coercible features: %s",
                len(dropped_cols),
                dropped_cols[:20] + (["..."] if len(dropped_cols) > 20 else []),
            )

        # Target must be numeric/bool for binary classification. Coerce string
        # labels via a single factorize call.
        y_raw = df[target].copy()
        if pd.api.types.is_numeric_dtype(y_raw) or pd.api.types.is_bool_dtype(y_raw):
            y = y_raw.astype("int64" if pd.api.types.is_bool_dtype(y_raw) else y_raw.dtype)
        else:
            codes, _ = pd.factorize(y_raw.astype("string"), use_na_sentinel=True)
            y = pd.Series(codes, index=y_raw.index, dtype="int64")
            _logger.info("RFE factorized string target '%s' to int labels", target)

        w = df[weight_col].copy() if weight_col and weight_col in df.columns else None
        return X, y, w

    def get_test_xy(
        self,
        *,
        dataset_id: str,
        target: str,
        feature_cols: List[str],
    ) -> Optional[Tuple[pd.DataFrame, pd.Series]]:
        """
        Load the held-out **test** partition for a real Test AUC measurement
        during the RFE loop. Mirrors ``get_xy`` (same coercion rules) but:

          * Uses DFSM scope="test".
          * Returns ``None`` when the test partition is empty / missing so
            callers can gracefully fall back to CV AUC.
          * Does not apply the weight column (weights are a train-only concept
            for the RFE loop).
          * Only keeps columns that are both in ``feature_cols`` and present
            in the test frame. Callers must further subset to the retained
            cols per iteration.
        """
        df = self._fetch_test_dataframe(dataset_id)
        if df is None or len(df) == 0:
            return None

        safe_feature_cols = [c for c in feature_cols if c not in _SYSTEM_COLUMNS]
        present = [c for c in safe_feature_cols if c in df.columns]
        if not present:
            _logger.info(
                "RFE: test partition has none of the requested features; falling back to CV-only."
            )
            return None
        if target not in df.columns:
            _logger.info(
                "RFE: target '%s' not present in test partition; falling back to CV-only.",
                target,
            )
            return None

        X_raw = df[present].copy()
        X, _, _ = _coerce_features_for_xgboost(X_raw)

        y_raw = df[target].copy()
        if pd.api.types.is_numeric_dtype(y_raw) or pd.api.types.is_bool_dtype(y_raw):
            y = y_raw.astype("int64" if pd.api.types.is_bool_dtype(y_raw) else y_raw.dtype)
        else:
            codes, _ = pd.factorize(y_raw.astype("string"), use_na_sentinel=True)
            y = pd.Series(codes, index=y_raw.index, dtype="int64")

        # Guard against a degenerate test partition with only one class — ROC
        # AUC is undefined there, so treat like "no test partition" and let
        # the caller fall back to CV AUC.
        if y.nunique(dropna=True) < 2:
            _logger.info(
                "RFE: test partition has a single target class; falling back to CV-only."
            )
            return None

        return X, y

    # ------- helpers -------

    def _fetch_train_dataframe(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """Switch DFSM scope to train and return a copy."""
        try:
            dataframe_state_manager.set_scope(dataset_id, scope="train")
        except Exception as e:
            _logger.warning("set_scope(train) failed for %s: %s", dataset_id, e)
        return dataframe_state_manager.get_dataframe(dataset_id)

    def _fetch_test_dataframe(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """Switch DFSM scope to test and return a copy (None if unavailable)."""
        try:
            dataframe_state_manager.set_scope(dataset_id, scope="test")
        except Exception as e:
            _logger.info(
                "set_scope(test) failed for %s: %s (test partition will be skipped)",
                dataset_id,
                e,
            )
            return None
        try:
            return dataframe_state_manager.get_dataframe(dataset_id)
        except Exception as e:
            _logger.info(
                "get_dataframe(test) failed for %s: %s (test partition will be skipped)",
                dataset_id,
                e,
            )
            return None
        finally:
            # Reset scope so later train reads are not disturbed.
            try:
                dataframe_state_manager.set_scope(dataset_id, scope="train")
            except Exception:
                pass

    def _read_parquet(self, job_id: str) -> Optional[pd.DataFrame]:
        if self._storage is None:
            return None
        try:
            if not self._storage.exists(job_id, "train.parquet"):
                return None
            raw = self._storage.get_bytes(job_id, "train.parquet")
            if not raw:
                return None
            import io

            return pd.read_parquet(io.BytesIO(raw))
        except Exception as e:
            _logger.warning("Failed to read train.parquet for job %s: %s", job_id, e)
            return None

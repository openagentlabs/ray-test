"""
ShapRanker - mean(|shap|) plus native feature_importances_ side-by-side.

Uses `shap.TreeExplainer(model).shap_values(X)` exactly once per iteration on
the whole training partition (guide Section 4.5).

Robustness features (so a slow / broken SHAP never freezes RFE):

* ``mode`` selects the ranking signal. Possible values:
    - ``"shap"``  (default): SHAP mean|shap|, fall back to native on failure/timeout.
    - ``"native"``: XGBoost gain-based feature_importances_ only. Always fast.
    - ``"auto"`` : identical to ``"shap"`` but downgrades silently on timeout.
  Environment override: ``RFE_RANKING_MODE=shap|native|auto``.

* ``timeout_seconds`` (default 30) wraps the SHAP call in a background thread.
  If SHAP exceeds the budget we return native importance for that iteration
  instead of hanging the whole RFE loop.

* ``n_explain_rows`` caps the number of rows passed to the TreeExplainer.
  SHAP evaluation scales ~O(rows * trees * depth^2), so on a 24k-row partition
  with 500 trees the explainer alone can dominate wall time. We sample 2000
  rows by default (configurable via ``RFE_SHAP_EXPLAIN_ROWS``) - this is more
  than enough to get a stable mean|shap| ranking.
"""

from __future__ import annotations

import os
import threading
import time
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.logging_config import get_logger

_logger = get_logger(__name__)


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(lo, min(int(raw), hi))
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = (os.environ.get(name) or "").strip().lower()
    return raw if raw else default


def rfe_ranking_mode() -> str:
    m = _env_str("RFE_RANKING_MODE", "shap")
    return m if m in {"shap", "native", "auto"} else "shap"


def rfe_shap_timeout_seconds() -> int:
    return _env_int("RFE_SHAP_TIMEOUT_SECONDS", 30, 5, 600)


def rfe_shap_explain_rows() -> int:
    return _env_int("RFE_SHAP_EXPLAIN_ROWS", 2000, 100, 50_000)


def _normalize_shap_array(shap_values, n_features: int) -> np.ndarray:
    """Flatten SHAP output to a 2D (n_rows, n_features) array for binary XGBoost."""
    arr = np.asarray(shap_values)
    if arr.ndim == 3:
        if arr.shape[0] == 2:
            arr = arr[1]
        elif arr.shape[-1] == 2:
            arr = arr[..., 1]
    if arr.ndim != 2:
        arr = np.asarray(getattr(shap_values, "values", shap_values))
        if arr.ndim == 3 and arr.shape[-1] == 2:
            arr = arr[..., 1]
    if arr.ndim != 2 or arr.shape[1] != n_features:
        raise ValueError(f"SHAP values have unexpected shape {arr.shape}, expected (*, {n_features})")
    return arr


def _native_pairs(model, X: pd.DataFrame) -> List[Tuple[str, float, float]]:
    native = np.asarray(getattr(model, "feature_importances_", np.zeros(len(X.columns))))
    if native.shape != (len(X.columns),):
        native = np.zeros(len(X.columns))
    pairs = [
        (col, float(native[i]), float(native[i]))
        for i, col in enumerate(X.columns)
    ]
    pairs.sort(key=lambda t: t[1], reverse=True)
    return pairs


class ShapRanker:
    def __init__(
        self,
        mode: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        explain_rows: Optional[int] = None,
    ) -> None:
        self.mode = (mode or rfe_ranking_mode()).lower()
        self.timeout_seconds = int(timeout_seconds if timeout_seconds is not None else rfe_shap_timeout_seconds())
        self.explain_rows = int(explain_rows if explain_rows is not None else rfe_shap_explain_rows())

    def rank(self, model, X: pd.DataFrame) -> List[Tuple[str, float, float]]:
        """
        Returns list of (variable_name, mean_abs_shap_or_gain, native_importance)
        sorted by the primary signal descending. Callers use this to pick the
        bottom-X percent for elimination.
        """
        if self.mode == "native":
            _logger.info("RFE ranker: native-importance mode (SHAP skipped)")
            return _native_pairs(model, X)

        shap_values, err = self._shap_with_timeout(model, X)
        if shap_values is None:
            if err:
                _logger.warning(
                    "RFE ranker: SHAP unavailable (%s) - falling back to native XGBoost importance",
                    err,
                )
            else:
                _logger.warning(
                    "RFE ranker: SHAP exceeded %ds timeout - falling back to native XGBoost importance",
                    self.timeout_seconds,
                )
            return _native_pairs(model, X)

        try:
            arr = _normalize_shap_array(shap_values, n_features=X.shape[1])
        except Exception as exc:
            _logger.warning("RFE ranker: unexpected SHAP array shape (%s) - falling back to native", exc)
            return _native_pairs(model, X)

        mean_abs = np.mean(np.abs(arr), axis=0)
        native = np.asarray(getattr(model, "feature_importances_", np.zeros(len(X.columns))))
        if native.shape != mean_abs.shape:
            native = np.zeros_like(mean_abs)
        pairs = [
            (col, float(mean_abs[i]), float(native[i]))
            for i, col in enumerate(X.columns)
        ]
        pairs.sort(key=lambda t: t[1], reverse=True)
        return pairs

    # ------------------------------------------------------------------

    def _sample_for_explain(self, X: pd.DataFrame) -> pd.DataFrame:
        if self.explain_rows <= 0 or len(X) <= self.explain_rows:
            return X
        return X.sample(n=self.explain_rows, random_state=42)

    def _shap_with_timeout(self, model, X: pd.DataFrame):
        """
        Run SHAP inside a daemon thread with a wall-clock timeout.

        If SHAP fails to import (e.g. libomp missing), the OpenMP hint is
        surfaced in the returned error string so the caller can log it; the
        RFE loop itself continues with native importance instead of crashing.
        """
        X_explain = self._sample_for_explain(X)
        result: dict = {"values": None, "error": None}

        def _worker() -> None:
            try:
                import shap  # type: ignore
                explainer = shap.TreeExplainer(model)
                result["values"] = explainer.shap_values(X_explain)
            except Exception as exc:
                msg = str(exc)
                if "libomp" in msg or "OpenMP" in msg or "vcomp" in msg or "libgomp" in msg:
                    from .xgb_trainer import _openmp_hint
                    result["error"] = (
                        "SHAP could not load the OpenMP runtime. "
                        + _openmp_hint()
                        + " Original error: "
                        + msg
                    )
                else:
                    result["error"] = f"{type(exc).__name__}: {exc}"

        thread = threading.Thread(target=_worker, name="rfe-shap", daemon=True)
        t0 = time.time()
        thread.start()
        thread.join(timeout=self.timeout_seconds)
        elapsed = time.time() - t0
        if thread.is_alive():
            return None, None  # timeout
        if result["error"] is not None:
            return None, result["error"]
        _logger.info(
            "RFE ranker: SHAP computed on %d rows x %d cols in %.2fs",
            len(X_explain), X_explain.shape[1], elapsed,
        )
        return result["values"], None

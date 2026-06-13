"""
XGBoostRfeTrainer - fixed-hyperparameter XGBoost wrapper for RFE.

Guide Section 4.1 / Table 3 lists reference hyperparameters. The **RFE** path uses
``rfe_xgb_params()`` which defaults to fewer trees (``RFE_XGB_N_ESTIMATORS``, default 128)
and ``tree_method="hist"`` so Step 3 completes in reasonable time on large train sets.
Set env vars to match Table 3 exactly if needed (e.g. ``RFE_XGB_N_ESTIMATORS=500``).

Guide Section 4.3 test-AUC note: during RFE the "test AUC" is an internal
CV-split AUC on the **train partition only** - we never touch the real test
partition here. This class exposes `cv_auc(X, y)` that implements that split.

We intentionally do not expose hyperparameter tuning from this class. Step 6
owns HPO (Optuna). Our job is a stable, reproducible ranking signal.

XGBoost is imported lazily (inside methods) so that importing this module
never triggers loading of libxgboost.dylib / libxgboost.so / vcomp140.dll.
That keeps the FastAPI backend bootable on developer machines where OpenMP
(libomp on macOS, vcomp on Windows, libgomp on Linux) is missing; the error
only surfaces when a user actually tries to run Step 3 (RFE), and we surface
it with a clear remediation message.
"""

from __future__ import annotations

import os
import platform
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from app.core.logging_config import get_logger

_logger = get_logger(__name__)

# Base defaults (guide Table 3). RFE path overrides several of these for **speed** so
# Step 3 finishes on a laptop; full 500-tree “exact” training would run 5–15+ minutes
# per iteration (5-fold CV × 500 trees ≈ 25 heavy fits before SHAP). Override via env:
#   RFE_XGB_N_ESTIMATORS  (default 128)
#   RFE_XGB_N_JOBS        (default 1 — avoids OpenMP thread oversubscription on macOS;
#                          set to -1 to use all cores)
#   RFE_XGB_MAX_DEPTH, RFE_XGB_LEARNING_RATE, RFE_XGB_TREE_METHOD
# CV folds for RFE:
#   RFE_CV_FOLDS (default 3; use 5 for stricter CV at the cost of ~67% more wall time)
_BASE_HYPERPARAMS = dict(
    objective="binary:logistic",
    learning_rate=0.1,
    n_estimators=500,
    max_depth=4,
    colsample_bytree=0.8,
    reg_lambda=10,
    gamma=1,
    tree_method="hist",
    random_state=42,
    n_jobs=-1,
    eval_metric="auc",
)


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(lo, min(int(raw), hi))
    except ValueError:
        return default


def _env_float(name: str, default: float, lo: float, hi: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        v = float(raw)
        return max(lo, min(v, hi))
    except ValueError:
        return default


def rfe_xgb_params() -> Dict[str, Any]:
    """
    Hyperparameters for the RFE loop only (faster than guide Table 3 by default).
    Intention: reproducible ranking + finishes in minutes, not hours, on 20k+ rows.
    """
    p: Dict[str, Any] = dict(_BASE_HYPERPARAMS)
    p["n_estimators"] = _env_int("RFE_XGB_N_ESTIMATORS", 128, 20, 2000)
    p["max_depth"] = _env_int("RFE_XGB_MAX_DEPTH", 4, 2, 16)
    p["learning_rate"] = _env_float("RFE_XGB_LEARNING_RATE", 0.1, 0.01, 0.5)
    # Default to -1 (all cores) so XGBoost fully uses the box when the user
    # asks for real train-partition CV. The previous default of 1 existed to
    # work around a macOS libomp + joblib/loky deadlock when we still used
    # cross_val_score; we no longer do, so the guard is unnecessary.
    nj_raw = (os.environ.get("RFE_XGB_N_JOBS") or "-1").strip()
    try:
        p["n_jobs"] = int(nj_raw)
    except ValueError:
        p["n_jobs"] = -1
    tm = (os.environ.get("RFE_XGB_TREE_METHOD") or "hist").strip().lower()
    if tm in ("hist", "exact", "approx", "auto"):
        p["tree_method"] = tm
    return p


def rfe_cv_folds() -> int:
    # 5-fold CV on the full train partition is the statistically defensible
    # default (guide Section 4.3). Override with RFE_CV_FOLDS.
    return _env_int("RFE_CV_FOLDS", 5, 2, 10)


def rfe_subsample_rows() -> int:
    """
    Max rows passed to XGBoost during RFE CV.

    Default -1 (disabled): run CV on the full train partition so Test AUC
    and CV AUC are computed on the modeler's real data. Override with the
    env var RFE_SUBSAMPLE_ROWS (e.g. ``5000``) on slow machines where the
    full-partition fit is too expensive.
    """
    return _env_int("RFE_SUBSAMPLE_ROWS", -1, -1, 200_000)


def _openmp_hint() -> str:
    """Return a platform-specific OpenMP install hint."""
    sysname = platform.system().lower()
    if sysname == "darwin":
        return "On macOS, install the OpenMP runtime with Homebrew: `brew install libomp`."
    if sysname == "windows":
        return (
            "On Windows, install the Microsoft Visual C++ Redistributable "
            "(vcomp140.dll). Latest version: "
            "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist"
        )
    return (
        "On Linux, install the GNU OpenMP runtime, e.g. `sudo apt-get install "
        "libgomp1` (Debian/Ubuntu) or `sudo yum install libgomp` (RHEL/CentOS)."
    )


def _import_xgb_classifier() -> Any:
    """
    Import XGBClassifier lazily with a friendly error when the OpenMP runtime
    is missing. Called by every method that needs xgboost so the backend can
    still boot when libomp/vcomp/libgomp is not installed.
    """
    try:
        from xgboost import XGBClassifier  # type: ignore

        return XGBClassifier
    except Exception as exc:
        msg = str(exc)
        if "libomp" in msg or "OpenMP" in msg or "vcomp" in msg or "libgomp" in msg:
            raise RuntimeError(
                "XGBoost failed to load because the OpenMP runtime is missing "
                "on this machine, so Step 3 (Iterative Feature Elimination) "
                "cannot run here. " + _openmp_hint() + " "
                "The rest of the application is unaffected and still runs "
                "normally. Original error: " + msg
            ) from exc
        raise


class XGBoostRfeTrainer:
    def __init__(self) -> None:
        self.model: Any = None

    def _new_model(self) -> Any:
        # early_stopping_rounds is supplied via fit() so it can be disabled for pure CV runs.
        XGBClassifier = _import_xgb_classifier()
        return XGBClassifier(**rfe_xgb_params())

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        sample_weight: Optional[pd.Series] = None,
        monotone_constraints: Optional[dict] = None,
    ) -> Any:
        model = self._new_model()
        if monotone_constraints:
            # XGBoost expects a tuple in the column order of X.
            tup = tuple(int(monotone_constraints.get(c, 0)) for c in X.columns)
            model.set_params(monotone_constraints=tup)
        fit_kwargs: dict = {}
        if sample_weight is not None:
            fit_kwargs["sample_weight"] = np.asarray(sample_weight)
        model.fit(X, y, **fit_kwargs)
        self.model = model
        return model

    def cv_auc(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        folds: int = 5,
        sample_weight: Optional[pd.Series] = None,
        on_fold: Optional[Callable[[int, int, float], None]] = None,
        on_fold_start: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[float, float]:
        """
        Returns (cv_auc_mean, cv_auc_std) using StratifiedKFold on the training partition.

        Implemented as a manual fold loop (not ``cross_val_score``) for two reasons:
          1. ``cross_val_score`` with ``n_jobs=-1`` spawns joblib/loky subprocesses,
             which deadlock on macOS Python 3.13 when combined with XGBoost's
             OpenMP threading (the "leaked semlock objects" warnings we saw).
             Running folds sequentially in-thread avoids this entirely and lets
             XGBoost's thread pool (``RFE_XGB_N_JOBS``, default ``1`` for macOS
             stability; set ``-1`` to use all cores).
          2. A manual loop lets us invoke ``on_fold`` after each fold so the
             caller can publish live progress events to the SSE bus. With
             500-tree XGBoost on a laptop, a single iteration's CV can take
             30+ seconds; without intra-iteration progress the UI looks frozen.

        The "test AUC" that Step 3 UI displays is the mean held-out fold AUC,
        matching guide Section 4.3.
        """
        folds = max(2, min(folds, 10))
        skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
        y_arr = np.asarray(y)
        w_arr = np.asarray(sample_weight) if sample_weight is not None else None
        fold_aucs: list[float] = []
        for fold_idx, (tr_idx, va_idx) in enumerate(skf.split(X, y_arr), start=1):
            _logger.info(
                "RFE XGB CV: starting fold %d/%d (train rows=%d, val rows=%d, cols=%d)",
                fold_idx,
                folds,
                len(tr_idx),
                len(va_idx),
                X.shape[1],
            )
            if on_fold_start is not None:
                try:
                    on_fold_start(fold_idx, folds)
                except Exception:
                    pass
            X_tr = X.iloc[tr_idx]
            X_va = X.iloc[va_idx]
            y_tr = y_arr[tr_idx]
            y_va = y_arr[va_idx]
            model = self._new_model()
            fit_kwargs: dict = {}
            if w_arr is not None:
                fit_kwargs["sample_weight"] = w_arr[tr_idx]
            model.fit(X_tr, y_tr, **fit_kwargs)
            preds = model.predict_proba(X_va)[:, 1]
            auc = float(roc_auc_score(y_va, preds))
            fold_aucs.append(auc)
            if on_fold is not None:
                try:
                    on_fold(fold_idx, folds, auc)
                except Exception:
                    # Progress callback failures must not break the CV run.
                    pass
        return float(np.mean(fold_aucs)), float(np.std(fold_aucs))

    def fit_and_cv(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        sample_weight: Optional[pd.Series] = None,
        folds: int = 5,
        monotone_constraints: Optional[dict] = None,
        on_fold: Optional[Callable[[int, int, float], None]] = None,
        on_fold_start: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[Any, float, float]:
        """Convenience wrapper: return (fitted_model, cv_auc_mean, cv_auc_std)."""
        cv_auc, cv_std = self.cv_auc(
            X,
            y,
            folds=folds,
            sample_weight=sample_weight,
            on_fold=on_fold,
            on_fold_start=on_fold_start,
        )
        model = self.fit(X, y, sample_weight=sample_weight, monotone_constraints=monotone_constraints)
        return model, cv_auc, cv_std

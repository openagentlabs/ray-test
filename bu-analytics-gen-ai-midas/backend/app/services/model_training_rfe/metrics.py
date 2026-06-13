"""
MetricEngine - IV, VIF, |Corr|, Missing %.

Design:
- Only called from `RfeService` with data that already came from
  `TrainingDataProvider`, so all metrics are computed on the **whole training
  partition** (guide rule for Steps 1-4).
- When `precomputed_metrics` from the frontend payload already contains a
  value, we reuse it rather than re-deriving. This matches guide Section 3.4
  paragraph on "use upstream metrics where available".
- IV uses equal-frequency (decile) bins with a small-positive laplace smoothing
  to avoid infinities, matching the standard Weight-of-Evidence practice.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class MetricEngine:
    def __init__(self, *, iv_bins: int = 10) -> None:
        self._iv_bins = iv_bins

    # ---- Missing ----
    def compute_missing_pct(self, series: pd.Series) -> float:
        if len(series) == 0:
            return 0.0
        return float(series.isna().mean())

    # ---- IV (binary target) ----
    def compute_iv(self, feature: pd.Series, y: pd.Series) -> Optional[float]:
        """
        Information Value using equal-frequency binning (10 bins by default).
        Small laplace smoothing (0.5 pseudo-count) prevents divide-by-zero for
        all-zero / all-one bins.
        """
        if feature is None or y is None or len(feature) == 0:
            return None
        try:
            s = pd.Series(feature).reset_index(drop=True)
            t = pd.Series(y).reset_index(drop=True).astype(float)
            if s.dtype.kind in "OSU" or str(s.dtype) == "category":
                # Categorical: use each level as a bin.
                df = pd.DataFrame({"x": s.astype(str).fillna("__NA__"), "y": t})
                grouped = df.groupby("x")["y"]
                counts = grouped.agg(["count", "sum"])
            else:
                try:
                    bins = pd.qcut(s.rank(method="first"), q=self._iv_bins, duplicates="drop")
                except ValueError:
                    return None
                df = pd.DataFrame({"x": bins.astype(str), "y": t})
                grouped = df.groupby("x")["y"]
                counts = grouped.agg(["count", "sum"])
            counts.columns = ["n", "events"]
            counts["non_events"] = counts["n"] - counts["events"]
            total_events = counts["events"].sum() + 0.5
            total_non = counts["non_events"].sum() + 0.5
            dist_e = (counts["events"] + 0.5) / total_events
            dist_n = (counts["non_events"] + 0.5) / total_non
            woe = np.log(dist_e / dist_n)
            iv = float(((dist_e - dist_n) * woe).sum())
            return iv
        except Exception:
            return None

    # ---- |Corr| with target ----
    def compute_abs_corr_with_target(self, feature: pd.Series, y: pd.Series) -> Optional[float]:
        try:
            s = pd.to_numeric(pd.Series(feature), errors="coerce")
            t = pd.to_numeric(pd.Series(y), errors="coerce")
            mask = s.notna() & t.notna()
            if mask.sum() < 10:
                return None
            return float(abs(s[mask].corr(t[mask])))
        except Exception:
            return None

    # ---- Signed corr (for suggested monotone direction) ----
    def compute_signed_corr_with_target(self, feature: pd.Series, y: pd.Series) -> Optional[float]:
        try:
            s = pd.to_numeric(pd.Series(feature), errors="coerce")
            t = pd.to_numeric(pd.Series(y), errors="coerce")
            mask = s.notna() & t.notna()
            if mask.sum() < 10:
                return None
            return float(s[mask].corr(t[mask]))
        except Exception:
            return None

    # ---- VIF ----
    _VIF_CAP = 999.0  # cap infinities so JSON serialisation and UI display stay clean

    def compute_vif(self, X: pd.DataFrame) -> Dict[str, float]:
        """VIF per feature with guardrails so every starting-set column yields a value.

        Strategy:
        - Median-impute per numeric column (instead of a global ``dropna`` that
          can collapse the design matrix when any single column has missingness).
          This guarantees the retained + dropped universe all get a VIF.
        - Primary path: statsmodels' ``variance_inflation_factor``.
        - Fallback (per column) when the primary path raises / returns NaN:
          per-column OLS R^2 against the remaining numerics, VIF = 1/(1-R^2).
        - Cap infinities at ``_VIF_CAP`` so JSON / UI don't see infinities or NaNs
          for columns where VIF is genuinely huge.
        """
        try:
            from statsmodels.stats.outliers_influence import variance_inflation_factor
        except Exception:
            variance_inflation_factor = None  # type: ignore[assignment]

        out: Dict[str, float] = {}
        Xn = X.select_dtypes(include=[np.number]).copy()
        # Non-numeric columns: VIF is undefined; leave as NaN (ensure_metrics
        # converts to None for the API contract).
        for col in X.columns:
            if col not in Xn.columns:
                out[col] = float("nan")

        if Xn.shape[0] == 0 or Xn.shape[1] == 0:
            return out

        # Median-impute per column so a single-column NaN doesn't wipe rows.
        for col in Xn.columns:
            if Xn[col].isna().any():
                median = Xn[col].median()
                if pd.isna(median):
                    median = 0.0
                Xn[col] = Xn[col].fillna(median)

        # Constant-column guard: VIF is undefined for zero-variance columns.
        constant_cols = [c for c in Xn.columns if Xn[c].nunique(dropna=True) <= 1]
        for c in constant_cols:
            out[c] = 1.0  # convention: no collinearity information -> baseline 1
        work_cols = [c for c in Xn.columns if c not in set(constant_cols)]
        if not work_cols:
            return out

        Xn_work = Xn[work_cols]
        Xn_const = Xn_work.copy()
        Xn_const.insert(0, "__const__", 1.0)
        values = Xn_const.values
        for i, col in enumerate(work_cols, start=1):
            val: float = float("nan")
            if variance_inflation_factor is not None:
                try:
                    val = float(variance_inflation_factor(values, i))
                except Exception:
                    val = float("nan")
            if not np.isfinite(val):
                # Fallback: single-column OLS R^2 on the remaining numerics.
                val = self._vif_ols_fallback(Xn_work, col)
            if val is None or not np.isfinite(val):
                val = float("nan")
            elif val > self._VIF_CAP:
                val = self._VIF_CAP
            out[col] = float(val)
        return out

    @staticmethod
    def _vif_ols_fallback(X: pd.DataFrame, col: str) -> float:
        """Compute VIF as 1/(1-R^2) from an OLS regression of `col` on the rest.

        Returns ``_VIF_CAP`` (capped) when R^2 is effectively 1, NaN on failure.
        """
        try:
            others = [c for c in X.columns if c != col]
            if not others:
                return 1.0
            y = X[col].to_numpy(dtype=float)
            Xo = X[others].to_numpy(dtype=float)
            # Add intercept column.
            Xo_const = np.column_stack([np.ones(Xo.shape[0]), Xo])
            coef, *_ = np.linalg.lstsq(Xo_const, y, rcond=None)
            y_hat = Xo_const @ coef
            ss_res = float(np.sum((y - y_hat) ** 2))
            ss_tot = float(np.sum((y - y.mean()) ** 2))
            if ss_tot <= 0:
                return 1.0
            r2 = 1.0 - ss_res / ss_tot
            if r2 >= 0.999999:
                return MetricEngine._VIF_CAP
            if r2 <= 0:
                return 1.0
            vif = 1.0 / (1.0 - r2)
            if not np.isfinite(vif):
                return MetricEngine._VIF_CAP
            return float(min(vif, MetricEngine._VIF_CAP))
        except Exception:
            return float("nan")

    def ensure_metrics(
        self,
        *,
        X: pd.DataFrame,
        y: pd.Series,
        feature_cols: List[str],
        precomputed: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Returns a dict keyed by variable name with {iv, missing_pct, abs_corr, orig_vif, signed_corr}
        per feature. Uses precomputed values when available; computes what's missing locally.
        """
        precomputed = precomputed or {}
        vif_map = self.compute_vif(X[feature_cols])
        out: Dict[str, Dict[str, float]] = {}
        for col in feature_cols:
            series = X[col] if col in X.columns else pd.Series(dtype=float)
            pc = precomputed.get(col, {})
            iv = pc.get("iv") or self.compute_iv(series, y)
            miss = pc.get("missing_pct") if pc.get("missing_pct") is not None else self.compute_missing_pct(series)
            abs_corr = pc.get("abs_corr") or self.compute_abs_corr_with_target(series, y)
            orig_vif = pc.get("orig_vif") if pc.get("orig_vif") is not None else vif_map.get(col)
            signed_corr = pc.get("signed_corr") or self.compute_signed_corr_with_target(series, y)
            out[col] = {
                "iv": float(iv) if iv is not None else None,
                "missing_pct": float(miss) if miss is not None else None,
                "abs_corr": float(abs_corr) if abs_corr is not None else None,
                "orig_vif": float(orig_vif) if orig_vif is not None and not np.isnan(orig_vif) else None,
                "signed_corr": float(signed_corr) if signed_corr is not None else None,
            }
        return out

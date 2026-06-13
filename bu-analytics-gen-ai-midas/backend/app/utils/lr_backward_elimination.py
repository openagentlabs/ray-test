"""
Logistic Regression backward elimination audit (developer guide §7.2).

Two passes: (1) VIF until all <= threshold — locked variables never removed;
(2) p-value until all <= threshold — same lock rule. No minimum feature floor.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

try:
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    from statsmodels.tools.tools import add_constant
    import statsmodels.api as sm

    _STATSMODELS = True
except ImportError:  # pragma: no cover
    _STATSMODELS = False


def _is_binary_classification(y: pd.Series) -> bool:
    try:
        return int(pd.Series(y).nunique(dropna=True)) == 2
    except Exception:
        return False


def _fit_test_auc_lr(
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    X_te: Optional[pd.DataFrame],
    y_te: Optional[pd.Series],
    *,
    random_state: int = 42,
) -> Optional[float]:
    if X_te is None or y_te is None or not _is_binary_classification(y_tr):
        return None
    if X_tr.shape[1] == 0:
        return None
    clf = LogisticRegression(max_iter=4000, random_state=random_state, solver="lbfgs")
    clf.fit(X_tr, y_tr)
    proba = clf.predict_proba(X_te)[:, 1]
    return float(roc_auc_score(y_te, proba))


def _fit_train_auc_lr(
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    *,
    random_state: int = 42,
) -> Optional[float]:
    """In-sample AUC on train — shown when holdout test AUC is unavailable."""
    if not _is_binary_classification(y_tr):
        return None
    if X_tr.shape[1] == 0:
        return None
    clf = LogisticRegression(max_iter=4000, random_state=random_state, solver="lbfgs")
    clf.fit(X_tr, y_tr)
    proba = clf.predict_proba(X_tr)[:, 1]
    return float(roc_auc_score(y_tr, proba))


def _format_locked_flags(locked_note: str, locked: Set[str]) -> str:
    note = (locked_note or "").strip()
    if note == "locked_vif_violation":
        return "Skip: highest VIF is on a locked variable"
    if note == "locked_p_violation":
        return "Skip: highest p-value is on a locked variable"
    if not locked:
        return "No locked variables"
    names = sorted(locked)[:5]
    suffix = "…" if len(locked) > 5 else ""
    return f"{len(locked)} locked — {', '.join(names)}{suffix}"


def _vif_series(X: pd.DataFrame) -> pd.Series:
    if not _STATSMODELS:
        raise ImportError("statsmodels is required for LR VIF backward elimination")
    Xn = X.astype(float)
    Xc = add_constant(Xn, has_constant="add")
    names = list(X.columns)
    out: List[float] = []
    for i in range(1, Xc.shape[1]):
        out.append(float(variance_inflation_factor(Xc.values, i)))
    return pd.Series(out, index=names, dtype=float)


def _pvalues_logit(X: pd.DataFrame, y: pd.Series) -> pd.Series:
    if not _STATSMODELS:
        raise ImportError("statsmodels is required for LR p-value backward elimination")
    Xn = X.astype(float)
    Xc = sm.add_constant(Xn, has_constant="add")
    res = sm.Logit(y, Xc).fit(disp=False, maxiter=300)
    p = res.pvalues.drop("const", errors="ignore")
    return p.reindex(X.columns).astype(float)


def run_lr_backward_elimination(
    *,
    X_train: pd.DataFrame,
    X_test: Optional[pd.DataFrame],
    y_train: pd.Series,
    y_test: Optional[pd.Series],
    locked_features: Sequence[str],
    vif_threshold: float = 5.0,
    p_value_threshold: float = 0.05,
    max_rounds: int = 500,
) -> Dict[str, Any]:
    """
    Returns dict with:
      - iterations: audit rows (iter 0 baseline, then removals)
      - summary: counts and narrative fields
      - final_features: ordered list of retained column names
      - config: thresholds echoed back
    """
    if not _STATSMODELS:
        return {
            "iterations": [],
            "summary": {"status": "skipped", "reason": "statsmodels_not_installed"},
            "final_features": list(X_train.columns),
            "config": {"vif_threshold": vif_threshold, "p_value_threshold": p_value_threshold},
        }

    locked: Set[str] = {str(x) for x in (locked_features or ()) if x is not None}
    locked &= set(X_train.columns)

    feats = [c for c in X_train.columns]
    start_n = len(feats)
    iterations: List[Dict[str, Any]] = []
    vif_removals = 0
    p_removals = 0

    def row(
        iteration: int,
        phase: str,
        removed: Optional[str],
        reason: str,
        offending: Optional[float],
        threshold_label: Optional[str],
        n_remain: int,
        auc_te: Optional[float],
        auc_tr: Optional[float],
        locked_note: str = "",
    ) -> Dict[str, Any]:
        return {
            "iteration": iteration,
            "phase": phase,
            "variable_removed": removed,
            "reason": reason,
            "offending_value": None if offending is None else float(offending),
            "threshold": threshold_label,
            "remaining_features": int(n_remain),
            "test_auc": None if auc_te is None else float(auc_te),
            "train_auc": None if auc_tr is None else float(auc_tr),
            "locked_flags": _format_locked_flags(locked_note, locked),
        }

    it = 0
    X_cur = X_train[feats].copy()
    X_te_cur = X_test[feats].copy() if X_test is not None else None
    auc0 = _fit_test_auc_lr(X_cur, y_train, X_te_cur, y_test)
    tr0 = _fit_train_auc_lr(X_cur, y_train)
    iterations.append(
        row(it, "baseline", None, "Baseline", None, None, len(feats), auc0, tr0, "")
    )
    it += 1

    # -------- Pass 1: VIF --------
    rounds = 0
    while rounds < max_rounds and len(feats) > 0:
        rounds += 1
        X_cur = X_train[feats].copy()
        X_te_cur = X_test[feats].copy() if X_test is not None else None
        try:
            vif_s = _vif_series(X_cur)
        except Exception:
            break
        viol = vif_s[vif_s > float(vif_threshold)].sort_values(ascending=False)
        if viol.empty:
            break
        removable = [c for c in viol.index.tolist() if c not in locked]
        if not removable:
            iterations.append(
                row(
                    it,
                    "vif_pass",
                    None,
                    "Highest VIF among locked-only violators — cannot remove locked variables",
                    float(viol.iloc[0]),
                    f"≤ {float(vif_threshold)}",
                    len(feats),
                    _fit_test_auc_lr(X_cur, y_train, X_te_cur, y_test),
                    _fit_train_auc_lr(X_cur, y_train),
                    "locked_vif_violation",
                )
            )
            it += 1
            break
        drop = max(removable, key=lambda c: float(vif_s[c]))
        off = float(vif_s[drop])
        feats = [c for c in feats if c != drop]
        vif_removals += 1
        X_cur = X_train[feats].copy()
        X_te_cur = X_test[feats].copy() if X_test is not None else None
        auc = _fit_test_auc_lr(X_cur, y_train, X_te_cur, y_test)
        auc_tr = _fit_train_auc_lr(X_cur, y_train)
        iterations.append(
            row(
                it,
                "vif_pass",
                drop,
                "Highest VIF",
                off,
                f"≤ {float(vif_threshold)}",
                len(feats),
                auc,
                auc_tr,
                "",
            )
        )
        it += 1

    # -------- Pass 2: p-values --------
    rounds = 0
    while rounds < max_rounds and len(feats) > 0:
        rounds += 1
        X_cur = X_train[feats].copy()
        X_te_cur = X_test[feats].copy() if X_test is not None else None
        try:
            p_s = _pvalues_logit(X_cur, y_train)
        except Exception:
            break
        viol = p_s[p_s > float(p_value_threshold)].sort_values(ascending=False)
        if viol.empty:
            break
        removable = [c for c in viol.index.tolist() if c not in locked]
        if not removable:
            iterations.append(
                row(
                    it,
                    "p_value_pass",
                    None,
                    "Highest p-value among locked-only violators — cannot remove locked variables",
                    float(viol.iloc[0]),
                    f"≤ {float(p_value_threshold)}",
                    len(feats),
                    _fit_test_auc_lr(X_cur, y_train, X_te_cur, y_test),
                    _fit_train_auc_lr(X_cur, y_train),
                    "locked_p_violation",
                )
            )
            it += 1
            break
        drop = max(removable, key=lambda c: float(p_s[c]))
        off = float(p_s[drop])
        feats = [c for c in feats if c != drop]
        p_removals += 1
        X_cur = X_train[feats].copy()
        X_te_cur = X_test[feats].copy() if X_test is not None else None
        auc = _fit_test_auc_lr(X_cur, y_train, X_te_cur, y_test)
        auc_tr = _fit_train_auc_lr(X_cur, y_train)
        iterations.append(
            row(
                it,
                "p_value_pass",
                drop,
                "Highest p-value",
                off,
                f"≤ {float(p_value_threshold)}",
                len(feats),
                auc,
                auc_tr,
                "",
            )
        )
        it += 1

    auc_first = iterations[0].get("test_auc") if iterations else None
    auc_last = iterations[-1].get("test_auc") if iterations else None
    rel = None
    if (
        auc_first is not None
        and auc_last is not None
        and isinstance(auc_first, (int, float))
        and isinstance(auc_last, (int, float))
        and float(auc_first) != 0
    ):
        rel = float((float(auc_last) - float(auc_first)) / abs(float(auc_first)) * 100.0)

    narrative = (
        f"Backward elimination completed in {max(0, len(iterations) - 1)} removal step(s). "
        f"{start_n} variables reduced to {len(feats)}. "
        f"VIF removals: {vif_removals}, p-value removals: {p_removals}."
    )
    if rel is not None:
        narrative += f" Test AUC moved from {float(auc_first):.4f} to {float(auc_last):.4f} ({rel:+.2f}% relative)."

    summary = {
        "status": "converged",
        "starting_features": int(start_n),
        "final_features": int(len(feats)),
        "locked_count": int(len(locked)),
        "vif_removals": int(vif_removals),
        "p_value_removals": int(p_removals),
        "elimination_iterations": int(max(0, len(iterations) - 1)),
        "test_auc_baseline": auc_first,
        "test_auc_final": auc_last,
        "test_auc_relative_change_pct": rel,
        "narrative": narrative,
    }

    return {
        "iterations": iterations,
        "summary": summary,
        "final_features": list(feats),
        "config": {"vif_threshold": float(vif_threshold), "p_value_threshold": float(p_value_threshold)},
    }

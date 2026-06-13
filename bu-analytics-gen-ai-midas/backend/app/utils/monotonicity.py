"""
Utilities for monotonic XGBoost training and rank-order validation.

Includes:
- AUC/Gini computation for rank ordering checks.
- Convenience helpers to train an XGBoost model with monotonic constraints.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve
from scipy.stats import spearmanr

try:
    import xgboost as xgb
except ImportError:  # pragma: no cover
    xgb = None  # type: ignore

try:
    import shap  # type: ignore
except ImportError:  # pragma: no cover
    shap = None  # type: ignore


def compute_auc_gini(
    y_true: Union[Sequence[int], np.ndarray],
    y_pred_proba: Union[Sequence[float], np.ndarray],
) -> Tuple[float, float]:
    """
    Compute AUC and Gini coefficient for rank ordering checks.

    Returns:
        (auc, gini)
    """
    y_true_arr = np.asarray(y_true)
    y_pred_arr = np.asarray(y_pred_proba)
    auc = roc_auc_score(y_true_arr, y_pred_arr)
    gini = 2 * auc - 1
    return auc, gini


def roc_points(
    y_true: Union[Sequence[int], np.ndarray],
    y_pred_proba: Union[Sequence[float], np.ndarray],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return false-positive rates, true-positive rates, and thresholds."""
    return roc_curve(np.asarray(y_true), np.asarray(y_pred_proba))


def train_xgboost_with_monotonicity(
    X_train,
    y_train,
    monotone_constraints: Optional[Iterable[int]] = None,
    params: Optional[Mapping[str, Union[str, float, int]]] = None,
    eval_set: Optional[List[Tuple]] = None,
):
    """
    Train an XGBoost binary classifier with optional monotonic constraints.

    Args:
        X_train: Feature matrix.
        y_train: Binary labels.
        monotone_constraints: Sequence of ints, one per feature, using
            1 for increasing, -1 for decreasing, 0 for no constraint.
        params: Additional booster params (objective, max_depth, etc.).
        eval_set: Optional evaluation set list of (X, y) tuples.

    Returns:
        Trained XGBClassifier instance.
    """
    if xgb is None:
        raise ImportError("xgboost is required for training with monotonicity.")

    base_params = {
        "objective": "binary:logistic",
        "eval_metric": "auc",
    }
    if params:
        base_params.update(params)

    if monotone_constraints is not None:
        base_params["monotone_constraints"] = tuple(monotone_constraints)

    model = xgb.XGBClassifier(**base_params)
    model.fit(X_train, y_train, eval_set=eval_set, verbose=False)
    return model


def example_rank_order_check(model, X_test, y_test) -> str:
    """
    Quick helper to compute and format AUC/Gini for an existing model.
    """
    y_pred = model.predict_proba(X_test)[:, 1]
    auc, gini = compute_auc_gini(y_test, y_pred)
    return f"AUC: {auc:.4f}, Gini: {gini:.4f}"


def decile_table(
    y_true: Union[Sequence[int], np.ndarray],
    y_pred_proba: Union[Sequence[float], np.ndarray],
    q: int = 10,
) -> pd.DataFrame:
    """
    Build a decile table for credit risk rank-order analysis.

    Args:
        y_true: Binary labels.
        y_pred_proba: Predicted probabilities or scores.
        q: Number of quantile buckets (default 10).
    """
    df = pd.DataFrame({"actual": y_true, "predicted": y_pred_proba})
    df["decile"] = pd.qcut(df["predicted"], q=q, labels=False, duplicates="drop")

    decile_stats = (
        df.groupby("decile")
        .agg({"actual": ["count", "sum", "mean"], "predicted": "mean"})
        .reset_index()
    )

    decile_stats.columns = ["Decile", "Count", "Bads", "Bad_Rate", "Avg_Score"]
    decile_stats["Goods"] = decile_stats["Count"] - decile_stats["Bads"]

    total_count = decile_stats["Count"].sum()
    total_bads = decile_stats["Bads"].sum()
    total_goods = decile_stats["Goods"].sum()

    decile_stats["Pct_Population"] = decile_stats["Count"] / total_count
    decile_stats["Pct_Bads"] = decile_stats["Bads"] / total_bads
    decile_stats["Pct_Goods"] = decile_stats["Goods"] / total_goods

    decile_stats["Cum_Bads"] = decile_stats["Bads"].cumsum()
    decile_stats["Cum_Goods"] = decile_stats["Goods"].cumsum()
    decile_stats["Cum_Bad_Rate"] = decile_stats["Cum_Bads"] / total_bads
    decile_stats["Cum_Good_Rate"] = decile_stats["Cum_Goods"] / total_goods

    overall_bad_rate = total_bads / total_count if total_count else 0
    decile_stats["Lift"] = decile_stats["Bad_Rate"] / overall_bad_rate if overall_bad_rate else np.nan
    return decile_stats


def create_decile_table(df: pd.DataFrame, score_col: str = "predicted_score", label_col: str = "actual", q: int = 10) -> pd.DataFrame:
    """
    Convenience wrapper to build a decile table from a dataframe with score/label cols.
    """
    return decile_table(df[label_col], df[score_col], q=q)


def calculate_ks(
    y_true: Union[Sequence[int], np.ndarray],
    y_pred_proba: Union[Sequence[float], np.ndarray],
    sample_weight: Optional[np.ndarray] = None,
) -> Tuple[float, float]:
    """
    Compute Kolmogorov-Smirnov statistic and its cutoff threshold.
    Optionally weighted using sample_weight.
    """
    fpr, tpr, thresholds = roc_curve(y_true, y_pred_proba, sample_weight=sample_weight)
    ks_values = tpr - fpr
    best_idx = int(np.argmax(ks_values))
    ks = float(ks_values[best_idx])
    ks_threshold = float(thresholds[best_idx])
    return ks, ks_threshold


def calculate_ks_detailed(
    y_true: Union[Sequence[int], np.ndarray],
    y_pred_proba: Union[Sequence[float], np.ndarray],
    sample_weight: Optional[np.ndarray] = None,
) -> Tuple[float, float, float, float]:
    """
    Calculate KS with the optimal threshold and corresponding TPR/FPR.
    Optionally weighted using sample_weight.
    """
    fpr, tpr, thresholds = roc_curve(y_true, y_pred_proba, sample_weight=sample_weight)
    ks_values = tpr - fpr
    best_idx = int(np.argmax(ks_values))
    ks = float(ks_values[best_idx])
    ks_threshold = float(thresholds[best_idx])
    tpr_best = float(tpr[best_idx])
    fpr_best = float(fpr[best_idx])

    print(f"KS Statistic: {ks:.4f}")
    print(f"KS Threshold: {ks_threshold:.4f}")
    print("At this threshold:")
    print(f"  - True Positive Rate: {tpr_best:.4f}")
    print(f"  - False Positive Rate: {fpr_best:.4f}")
    return ks, ks_threshold, tpr_best, fpr_best


def ks_from_deciles(decile_stats: pd.DataFrame) -> Tuple[float, float]:
    """
    Calculate KS from decile table (requires Bads and Goods columns).
    """
    total_bads = decile_stats["Bads"].sum()
    total_goods = decile_stats["Goods"].sum()

    decile_stats = decile_stats.copy()
    decile_stats["Cum_Bads_Pct"] = decile_stats["Bads"].cumsum() / total_bads
    decile_stats["Cum_Goods_Pct"] = decile_stats["Goods"].cumsum() / total_goods
    decile_stats["KS"] = decile_stats["Cum_Goods_Pct"] - decile_stats["Cum_Bads_Pct"]

    ks_value = decile_stats["KS"].max()
    ks_decile = decile_stats.loc[decile_stats["KS"].idxmax(), "Decile"]

    print(f"KS Statistic: {ks_value:.4f}")
    print(f"Occurs at Decile: {ks_decile}")
    return float(ks_value), float(ks_decile)


def xgboost_feature_importance(model, top_n: int = 20, plot: bool = True) -> pd.DataFrame:
    """
    Compute XGBoost feature importance (gain/weight/cover) and optionally plot top_n gain.
    """
    if xgb is None:
        raise ImportError("xgboost is required for feature importance.")

    booster = model.get_booster()
    importance_gain = booster.get_score(importance_type="gain")
    importance_weight = booster.get_score(importance_type="weight")
    importance_cover = booster.get_score(importance_type="cover")

    feat_imp = pd.DataFrame(
        {
            "feature": list(importance_gain.keys()),
            "gain": list(importance_gain.values()),
            "weight": [importance_weight.get(k, 0) for k in importance_gain.keys()],
            "cover": [importance_cover.get(k, 0) for k in importance_gain.keys()],
        }
    ).sort_values("gain", ascending=False)

    if plot and not feat_imp.empty:
        import matplotlib.pyplot as plt

        feat_imp.head(top_n).plot(
            x="feature", y="gain", kind="barh", figsize=(10, 8), legend=False
        )
        plt.xlabel("Gain")
        plt.title("Feature Importance - Gain")
        plt.tight_layout()
    return feat_imp


def shap_global_importance(model, X, plot: bool = True):
    """
    Compute global SHAP values and optional summary bar plot.

    Returns:
        (shap_values, feature_importance_df)
    """
    if shap is None:
        raise ImportError("shap is required for SHAP analysis.")

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    if isinstance(shap_values, list):  # handle multiclass list output
        shap_array = np.array(shap_values[0])
    else:
        shap_array = np.array(shap_values)

    feature_importance = pd.DataFrame(
        {"feature": getattr(X, "columns", range(shap_array.shape[1])), "importance": np.abs(shap_array).mean(axis=0)}
    ).sort_values("importance", ascending=False)

    if plot:
        import matplotlib.pyplot as plt

        shap.summary_plot(shap_values, X, plot_type="bar", show=False)
        plt.tight_layout()

    return shap_values, feature_importance


def calculate_iv(df: pd.DataFrame, feature: str, target: str, q: int = 10) -> Tuple[float, pd.DataFrame]:
    """
    Calculate Information Value (IV) and return per-bin detail.
    """
    df_iv = df.copy()
    df_iv["bin"] = pd.qcut(df_iv[feature], q=q, duplicates="drop")

    iv_table = df_iv.groupby("bin").agg({target: ["count", "sum"]})
    iv_table.columns = ["Total", "Bads"]
    iv_table["Goods"] = iv_table["Total"] - iv_table["Bads"]

    total_goods = iv_table["Goods"].sum()
    total_bads = iv_table["Bads"].sum()

    iv_table["Dist_Good"] = iv_table["Goods"] / total_goods
    iv_table["Dist_Bad"] = iv_table["Bads"] / total_bads
    iv_table["WOE"] = np.log(iv_table["Dist_Good"] / iv_table["Dist_Bad"])
    iv_table["IV"] = (iv_table["Dist_Good"] - iv_table["Dist_Bad"]) * iv_table["WOE"]

    total_iv = iv_table["IV"].sum()
    return float(total_iv), iv_table


def combine_feature_rankings(
    shap_importance: pd.DataFrame,
    xgb_feature_importance: pd.DataFrame,
    iv_ranking: pd.DataFrame,
    plot_corr: bool = False,
):
    """
    Combine SHAP, XGB gain, and IV rankings; optionally plot rank correlations.

    Args:
        shap_importance: DataFrame with columns ['feature', 'importance'].
        xgb_feature_importance: DataFrame with columns incl. ['feature', 'gain'].
        iv_ranking: DataFrame indexed by feature with column ['IV'].
        plot_corr: Whether to plot correlation heatmap of rank columns.
    """
    ranking_comparison = pd.DataFrame(
        {
            "SHAP": shap_importance.set_index("feature")["importance"],
            "XGB_Gain": xgb_feature_importance.set_index("feature")["gain"],
            "IV": iv_ranking["IV"],
        }
    ).fillna(0)

    for col in ranking_comparison.columns:
        ranking_comparison[f"{col}_rank"] = ranking_comparison[col].rank(ascending=False)

    if plot_corr and not ranking_comparison.empty:
        import seaborn as sns  # type: ignore
        import matplotlib.pyplot as plt

        rank_cols = [c for c in ranking_comparison.columns if c.endswith("_rank")]
        corr = ranking_comparison[rank_cols].corr()
        sns.heatmap(corr, annot=True, cmap="coolwarm")
        plt.title("Correlation of Feature Ranking Methods")
        plt.tight_layout()

    return ranking_comparison


def check_decile_monotonicity(decile_stats: pd.DataFrame) -> bool:
    """
    Verify that bad rates are monotonically increasing across deciles.
    Prints violations with details; returns True if no violations.
    """
    bad_rates = decile_stats["Bad_Rate"].to_numpy()
    violations = []
    for i in range(1, len(bad_rates)):
        if bad_rates[i] < bad_rates[i - 1]:
            violations.append(
                {
                    "decile": i + 1,  # 1-based decile index
                    "current_rate": bad_rates[i],
                    "previous_rate": bad_rates[i - 1],
                    "difference": bad_rates[i] - bad_rates[i - 1],
                }
            )

    if not violations:
        print("✓ Perfect monotonicity - no violations detected.")
        return True

    print(f"✗ Found {len(violations)} monotonicity violation(s):")
    for v in violations:
        print(
            f"  Decile {v['decile']}: {v['current_rate']:.2%} < "
            f"{v['previous_rate']:.2%} (Δ = {v['difference']:.2%})"
        )
    return False


def check_monotonicity(decile_stats: pd.DataFrame) -> bool:
    """
    Verbose monotonicity check across adjacent deciles with status printing.
    """
    print("\n" + "=" * 60)
    print("MONOTONICITY CHECK")
    print("=" * 60)

    violations = []
    bad_rates = decile_stats["Bad_Rate"].to_numpy()
    for i in range(1, len(bad_rates)):
        current_rate = bad_rates[i]
        previous_rate = bad_rates[i - 1]
        status = "✓" if current_rate >= previous_rate else "✗"
        print(f"Decile {i} → {i+1}: {previous_rate:.2%} → {current_rate:.2%}  {status}")
        if current_rate < previous_rate:
            violations.append(
                {
                    "from_decile": i,
                    "to_decile": i + 1,
                    "drop": previous_rate - current_rate,
                }
            )

    print("=" * 60)
    if not violations:
        print("✓ PERFECT MONOTONICITY - No violations")
        if len(decile_stats) >= 2:
            print(f"  Decile 1: {bad_rates[0]:.2%}")
            print(f"  Decile {len(decile_stats)}: {bad_rates[-1]:.2%}")
            ratio = bad_rates[-1] / bad_rates[0] if bad_rates[0] else np.nan
            print(f"  Range: {ratio:.1f}x")
        return True

    print(f"✗ FOUND {len(violations)} VIOLATION(S):")
    for v in violations:
        print(f"  Decile {v['from_decile']} → {v['to_decile']}: Drop of {v['drop']:.2%}")
    return False


def monotonicity_score(decile_stats: pd.DataFrame) -> float:
    """
    Compute percent of adjacent decile pairs that are correctly ordered (non-decreasing).
    """
    bad_rates = decile_stats["Bad_Rate"].to_numpy()
    if len(bad_rates) < 2:
        return 1.0
    correct = sum(bad_rates[i] >= bad_rates[i - 1] for i in range(1, len(bad_rates)))
    return correct / (len(bad_rates) - 1)


def plot_rank_ordering(decile_stats: pd.DataFrame, overall_bad_rate: float):
    """
    Plot bad rate by decile and cumulative capture rate.
    """
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].plot(
        decile_stats["Decile"],
        decile_stats["Bad_Rate"] * 100,
        marker="o",
        linewidth=2,
        label="Decile Bad Rate",
    )
    axes[0].axhline(y=overall_bad_rate * 100, color="r", linestyle="--", label="Overall Bad Rate")
    axes[0].set_xlabel("Decile (1=Lowest Risk, 10=Highest Risk)")
    axes[0].set_ylabel("Bad Rate (%)")
    axes[0].set_title("Rank Ordering: Bad Rate by Score Decile")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(
        decile_stats["Decile"],
        decile_stats["Cum_Bad_Rate"] * 100,
        marker="s",
        linewidth=2,
        label="Cumulative Bad Capture",
    )
    axes[1].plot([decile_stats["Decile"].min(), decile_stats["Decile"].max()], [10, 100], "r--", label="Random Model")
    axes[1].set_xlabel("Decile (1=Lowest Risk, 10=Highest Risk)")
    axes[1].set_ylabel("Cumulative % of Bads Captured")
    axes[1].set_title("Cumulative Capture Rate")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    return fig, axes


def plot_decile_analysis(decile_stats: pd.DataFrame):
    """
    Create a 4-panel decile visualization: bad rate, lift, cumulative capture, population split.
    """
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    overall_rate = decile_stats["Bads"].sum() / decile_stats["Count"].sum()

    # Bad Rate by Decile
    axes[0, 0].bar(decile_stats["Decile"], decile_stats["Bad_Rate"] * 100, color="steelblue", alpha=0.7)
    axes[0, 0].plot(
        decile_stats["Decile"],
        decile_stats["Bad_Rate"] * 100,
        "ro-",
        linewidth=2,
        markersize=8,
    )
    axes[0, 0].axhline(y=overall_rate * 100, color="red", linestyle="--", label=f"Overall: {overall_rate:.1%}")
    axes[0, 0].set_xlabel("Decile (1=Lowest Risk, 10=Highest Risk)")
    axes[0, 0].set_ylabel("Bad Rate (%)")
    axes[0, 0].set_title("Bad Rate by Decile")
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    # Lift
    axes[0, 1].bar(decile_stats["Decile"], decile_stats["Lift"], color="coral", alpha=0.7)
    axes[0, 1].axhline(y=1.0, color="red", linestyle="--", label="Baseline (1.0)")
    axes[0, 1].set_xlabel("Decile")
    axes[0, 1].set_ylabel("Lift")
    axes[0, 1].set_title("Lift by Decile")
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

    # Cumulative capture
    axes[1, 0].plot(
        decile_stats["Decile"],
        decile_stats["Cum_Bad_Rate"] * 100,
        "bo-",
        linewidth=2,
        markersize=8,
        label="Model",
    )
    axes[1, 0].plot([1, 10], [10, 100], "r--", linewidth=2, label="Random")
    axes[1, 0].fill_between(
        decile_stats["Decile"],
        decile_stats["Cum_Bad_Rate"] * 100,
        np.linspace(10, 100, len(decile_stats)),
        alpha=0.2,
        color="green",
    )
    axes[1, 0].set_xlabel("Decile")
    axes[1, 0].set_ylabel("Cumulative % Bads Captured")
    axes[1, 0].set_title("Cumulative Capture Rate")
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)

    # Population distribution
    x = np.arange(len(decile_stats))
    width = 0.35
    axes[1, 1].bar(x - width / 2, decile_stats["Pct_Goods"] * 100, width, label="Goods", color="green", alpha=0.7)
    axes[1, 1].bar(x + width / 2, decile_stats["Pct_Bads"] * 100, width, label="Bads", color="red", alpha=0.7)
    axes[1, 1].set_xlabel("Decile")
    axes[1, 1].set_ylabel("% of Population")
    axes[1, 1].set_title("Distribution of Goods vs Bads")
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(decile_stats["Decile"])
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.show()
    return fig, axes


def plot_ks_chart(
    y_true: Union[Sequence[int], np.ndarray],
    y_pred_proba: Union[Sequence[float], np.ndarray],
):
    """
    Plot KS chart showing cumulative distributions and the KS gap.
    """
    import matplotlib.pyplot as plt

    fpr, tpr, thresholds = roc_curve(y_true, y_pred_proba)
    ks_values = tpr - fpr
    best_idx = int(np.argmax(ks_values))
    ks = float(ks_values[best_idx])

    plt.figure(figsize=(10, 6))
    plt.plot(thresholds, tpr, label="Cumulative % Bads (TPR)", linewidth=2)
    plt.plot(thresholds, fpr, label="Cumulative % Goods (FPR)", linewidth=2)
    plt.axvline(
        x=thresholds[best_idx],
        color="red",
        linestyle="--",
        label=f"KS = {ks:.3f}",
    )
    plt.plot(
        [thresholds[best_idx], thresholds[best_idx]],
        [fpr[best_idx], tpr[best_idx]],
        "r-",
        linewidth=3,
        label="KS Distance",
    )
    plt.xlabel("Model Score Threshold")
    plt.ylabel("Cumulative %")
    plt.title("KS Statistic - Cumulative Distribution Comparison")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    return ks, thresholds[best_idx]


def print_summary_metrics(decile_stats: pd.DataFrame):
    """
    Print key decile summary metrics.
    """
    print("\n" + "=" * 60)
    print("DECILE ANALYSIS SUMMARY")
    print("=" * 60)

    overall_bad_rate = decile_stats["Bads"].sum() / decile_stats["Count"].sum()

    print("\nOverall Statistics:")
    print(f"  Total Population: {decile_stats['Count'].sum():,}")
    print(f"  Total Bads: {decile_stats['Bads'].sum():,}")
    print(f"  Total Goods: {decile_stats['Goods'].sum():,}")
    print(f"  Overall Bad Rate: {overall_bad_rate:.2%}")

    first = decile_stats.iloc[0]
    last = decile_stats.iloc[-1]

    print("\nDecile 1 (Lowest Risk):")
    print(f"  Bad Rate: {first['Bad_Rate']:.2%}")
    print(f"  Lift: {first['Lift']:.2f}x")

    print("\nDecile {decile} (Highest Risk):".format(decile=int(last["Decile"]) if "Decile" in last else len(decile_stats)))
    print(f"  Bad Rate: {last['Bad_Rate']:.2%}")
    print(f"  Lift: {last['Lift']:.2f}x")
    print(f"  Concentration: {last['Pct_Bads']:.1%} of all bads")

    print("\nSeparation Power:")
    ratio = last["Bad_Rate"] / first["Bad_Rate"] if first["Bad_Rate"] else np.nan
    print(f"  Decile {int(last['Decile']) if 'Decile' in last else len(decile_stats)} / Decile 1: {ratio:.1f}x")
    top3_bads = decile_stats.tail(3)["Pct_Bads"].sum()
    print(f"  Top 3 deciles capture: {top3_bads:.1%} of all bads")
    print("=" * 60)


def full_decile_analysis(
    y_true: Union[Sequence[int], np.ndarray],
    y_pred_proba: Union[Sequence[float], np.ndarray],
    q: int = 10,
    plot: bool = True,
):
    """
    End-to-end decile analysis: table, monotonicity, summary, optional plots.
    """
    df = pd.DataFrame({"actual": y_true, "predicted_score": y_pred_proba})
    df["decile"] = pd.qcut(df["predicted_score"], q=q, labels=range(1, q + 1), duplicates="drop")

    deciles = create_decile_table(df, score_col="predicted_score", label_col="actual", q=q)
    print(deciles.to_string(index=False))

    is_monotonic = check_monotonicity(deciles)
    print_summary_metrics(deciles)
    if plot:
        plot_decile_analysis(deciles)
    return deciles, is_monotonic


def compute_auc_overfit_pct(
    train_auc: Optional[float],
    test_auc: Optional[float],
) -> Optional[float]:
    """
    Train vs test generalization gap as a percentage of train AUC (Step 6 / G1 gate).

    Formula: (train_auc - test_auc) / |train_auc| * 100
    """
    if train_auc is None or test_auc is None:
        return None
    try:
        tr = float(train_auc)
        te = float(test_auc)
    except (TypeError, ValueError):
        return None
    if tr == 0:
        return None
    return float(((tr - te) / abs(tr)) * 100.0)


def _inner_sklearn_estimator(model: Any) -> Any:
    """Use the final estimator from a Pipeline when counting importances."""
    try:
        from sklearn.pipeline import Pipeline

        if isinstance(model, Pipeline):
            steps = getattr(model, "steps", None) or []
            if steps:
                return steps[-1][1]
    except Exception:
        pass
    return model


def nonzero_feature_slot_count(model: Any, eps: float = 1e-12) -> int:
    """
    Count input features with positive tree importance or non-zero |coefficient|.
    For multiclass linear models, a feature counts if max_j |coef[j, k]| > eps.

    ``HistGradientBoostingClassifier`` / ``HistGradientBoostingRegressor`` do not
    expose ``feature_importances_`` (as of sklearn 1.6); after fit, use
    ``n_features_in_`` so UI counts match other gradient-boosting estimators.
    """
    if model is None:
        return 0
    try:
        est = _inner_sklearn_estimator(model)

        if hasattr(est, "feature_importances_"):
            fi = getattr(est, "feature_importances_", None)
            if fi is not None:
                imp = np.asarray(fi, dtype=float)
                if imp.size > 0:
                    return int(np.sum(imp > eps))

        cls_name = type(est).__name__
        if cls_name in ("HistGradientBoostingClassifier", "HistGradientBoostingRegressor"):
            nfi = getattr(est, "n_features_in_", None)
            if nfi is not None:
                return int(nfi)

        if hasattr(est, "coef_"):
            coef = np.asarray(est.coef_, dtype=float)
            if coef.ndim == 1:
                per = np.abs(coef)
            else:
                per = np.max(np.abs(coef), axis=0)
            return int(np.sum(per > eps))
    except Exception:
        return 0
    return 0


def gini_stability(
    model,
    X_train,
    y_train,
    X_test,
    y_test,
    y_pred_test: Optional[Union[Sequence[float], np.ndarray]] = None,
) -> Tuple[float, float, float]:
    """
    Compute train/test Gini and stability ratio (test/train).
    """
    train_pred = model.predict_proba(X_train)[:, 1]
    test_pred = (
        np.asarray(y_pred_test) if y_pred_test is not None else model.predict_proba(X_test)[:, 1]
    )
    train_gini = 2 * roc_auc_score(y_train, train_pred) - 1
    test_gini = 2 * roc_auc_score(y_test, test_pred) - 1
    stability = test_gini / train_gini if train_gini != 0 else np.nan
    return float(train_gini), float(test_gini), float(stability)


def feature_importance_stability(
    train_shap_values: Union[np.ndarray, list],
    test_shap_values: Union[np.ndarray, list],
) -> float:
    """
    Compute Spearman correlation between train/test SHAP mean absolute importances.
    """
    train_arr = np.array(train_shap_values[0]) if isinstance(train_shap_values, list) else np.array(train_shap_values)
    test_arr = np.array(test_shap_values[0]) if isinstance(test_shap_values, list) else np.array(test_shap_values)
    train_importance = np.abs(train_arr).mean(axis=0)
    test_importance = np.abs(test_arr).mean(axis=0)
    corr, _ = spearmanr(train_importance, test_importance)
    return float(corr)


def calculate_psi(
    expected_scores: Union[Sequence[float], np.ndarray],
    actual_scores: Union[Sequence[float], np.ndarray],
    q: int = 10,
) -> float:
    """
    Calculate Population Stability Index (PSI) to measure distribution shift.
    
    PSI measures how much the distribution of scores has shifted between two populations
    (typically training/expected vs test/actual). It's commonly used in credit risk modeling
    to monitor model stability over time.
    
    Formula:
        PSI = Σ[(Actual% - Expected%) × ln(Actual% / Expected%)]
    
    Where:
        - Expected% = percentage of observations in each bin for the expected (reference) distribution
        - Actual% = percentage of observations in each bin for the actual (current) distribution
        - The sum is over all bins
    
    Interpretation:
        - PSI < 0.1: No significant population shift (Stable)
        - 0.1 ≤ PSI < 0.25: Moderate population shift (Some change)
        - PSI ≥ 0.25: Significant population shift (Major change - investigate)
    
    Args:
        expected_scores: Reference distribution scores (typically training set predictions)
        actual_scores: Current distribution scores (typically test set predictions)
        q: Number of quantile bins to use (default: 10)
    
    Returns:
        PSI value as a float
    """
    expected_arr = np.asarray(expected_scores)
    actual_arr = np.asarray(actual_scores)
    
    # Create bins based on expected distribution (quantile-based)
    try:
        _, bin_edges = pd.qcut(expected_arr, q=q, retbins=True, duplicates="drop")
    except ValueError:
        # If quantile binning fails (e.g., too many duplicates), use equal-width bins
        min_val = min(expected_arr.min(), actual_arr.min())
        max_val = max(expected_arr.max(), actual_arr.max())
        bin_edges = np.linspace(min_val, max_val, q + 1)
    
    # Adjust bin edges to cover both distributions
    min_val = min(expected_arr.min(), actual_arr.min())
    max_val = max(expected_arr.max(), actual_arr.max())
    bin_edges[0] = min_val - 1e-6
    bin_edges[-1] = max_val + 1e-6
    
    # Calculate distributions
    expected_counts, _ = np.histogram(expected_arr, bins=bin_edges)
    actual_counts, _ = np.histogram(actual_arr, bins=bin_edges)
    
    # Convert to percentages
    expected_pct = expected_counts / len(expected_arr)
    actual_pct = actual_counts / len(actual_arr)
    
    # Avoid division by zero (replace zeros with small epsilon for PSI calculation)
    expected_pct_psi = np.where(expected_pct == 0, 1e-6, expected_pct)
    actual_pct_psi = np.where(actual_pct == 0, 1e-6, actual_pct)
    
    # Calculate PSI: (Actual% - Expected%) × ln(Actual% / Expected%)
    psi_contributions = (actual_pct_psi - expected_pct_psi) * np.log(actual_pct_psi / expected_pct_psi)
    
    # Sum all contributions
    total_psi = float(np.sum(psi_contributions))
    
    return total_psi


def calculate_psi_detailed(
    expected_scores: Union[Sequence[float], np.ndarray],
    actual_scores: Union[Sequence[float], np.ndarray],
    q: int = 10,
) -> Tuple[float, pd.DataFrame]:
    """
    Calculate PSI with detailed bin-by-bin breakdown.
    
    Returns both the total PSI value and a DataFrame with per-bin details.
    
    Args:
        expected_scores: Reference distribution scores (typically training set predictions)
        actual_scores: Current distribution scores (typically test set predictions)
        q: Number of quantile bins to use (default: 10)
    
    Returns:
        Tuple of (total_psi, breakdown_dataframe)
        The DataFrame contains columns:
        - Bin: Bin number (1-based)
        - Bin_Range: String representation of bin edges
        - Expected_Count: Number of observations in bin for expected distribution
        - Expected_Pct: Percentage of observations in bin for expected distribution
        - Actual_Count: Number of observations in bin for actual distribution
        - Actual_Pct: Percentage of observations in bin for actual distribution
        - Difference_Pct: Actual_Pct - Expected_Pct
        - PSI_Contribution: PSI contribution from this bin
    """
    expected_arr = np.asarray(expected_scores)
    actual_arr = np.asarray(actual_scores)
    
    # Create bins based on expected distribution (quantile-based)
    try:
        _, bin_edges = pd.qcut(expected_arr, q=q, retbins=True, duplicates="drop")
    except ValueError:
        # If quantile binning fails (e.g., too many duplicates), use equal-width bins
        min_val = min(expected_arr.min(), actual_arr.min())
        max_val = max(expected_arr.max(), actual_arr.max())
        bin_edges = np.linspace(min_val, max_val, q + 1)
    
    # Adjust bin edges to cover both distributions
    min_val = min(expected_arr.min(), actual_arr.min())
    max_val = max(expected_arr.max(), actual_arr.max())
    bin_edges[0] = min_val - 1e-6
    bin_edges[-1] = max_val + 1e-6
    
    # Calculate distributions
    expected_counts, _ = np.histogram(expected_arr, bins=bin_edges)
    actual_counts, _ = np.histogram(actual_arr, bins=bin_edges)
    
    # Convert to percentages
    expected_pct = expected_counts / len(expected_arr)
    actual_pct = actual_counts / len(actual_arr)
    
    # Avoid division by zero (replace zeros with small epsilon for PSI calculation)
    expected_pct_psi = np.where(expected_pct == 0, 1e-6, expected_pct)
    actual_pct_psi = np.where(actual_pct == 0, 1e-6, actual_pct)
    
    # Calculate PSI: (Actual% - Expected%) × ln(Actual% / Expected%)
    psi_contributions = (actual_pct_psi - expected_pct_psi) * np.log(actual_pct_psi / expected_pct_psi)
    
    # Calculate differences
    differences = actual_pct - expected_pct
    
    # Create detailed breakdown DataFrame
    table_data = []
    for i in range(len(expected_counts)):
        table_data.append({
            'Bin': i + 1,
            'Bin_Range': f"[{bin_edges[i]:.4f}, {bin_edges[i+1]:.4f})",
            'Bin_Start': float(bin_edges[i]),
            'Bin_End': float(bin_edges[i+1]),
            'Expected_Count': int(expected_counts[i]),
            'Expected_Pct': float(expected_pct[i]),
            'Actual_Count': int(actual_counts[i]),
            'Actual_Pct': float(actual_pct[i]),
            'Difference_Pct': float(differences[i]),
            'PSI_Contribution': float(psi_contributions[i])
        })
    
    breakdown_df = pd.DataFrame(table_data)
    
    # Sum all contributions
    total_psi = float(np.sum(psi_contributions))
    
    return total_psi, breakdown_df


def calculate_csi(
    expected_values: Union[Sequence[float], np.ndarray],
    actual_values: Union[Sequence[float], np.ndarray],
    q: int = 10,
) -> float:
    """
    Calculate Characteristic Stability Index (CSI) for a single variable/feature.
    
    CSI is similar to PSI but measures distribution shift for individual features
    rather than model predictions. It uses the same formula as PSI.
    
    Formula:
        CSI = Σ[(Actual% - Expected%) × ln(Actual% / Expected%)]
    
    Where:
        - Expected% = percentage of observations in each bin for the expected (training) distribution
        - Actual% = percentage of observations in each bin for the actual (test) distribution
        - The sum is over all bins
    
    Interpretation:
        - CSI < 0.1: No significant shift (Stable)
        - 0.1 ≤ CSI < 0.25: Moderate shift (Some change)
        - CSI ≥ 0.25: Significant shift (Major change - investigate)
    
    Args:
        expected_values: Reference distribution values (typically training set feature values)
        actual_values: Current distribution values (typically test set feature values)
        q: Number of quantile bins to use (default: 10)
    
    Returns:
        CSI value as a float
    """
    # CSI uses the same calculation as PSI
    return calculate_psi(expected_values, actual_values, q=q)


def calculate_csi_for_variables(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    q: int = 10,
    max_variables: Optional[int] = None,
) -> pd.DataFrame:
    """
    Calculate CSI (Characteristic Stability Index) for all variables/features.
    
    Args:
        X_train: Training feature DataFrame
        X_test: Test feature DataFrame
        q: Number of quantile bins to use (default: 10)
        max_variables: Optional limit on number of variables to process (for performance)
    
    Returns:
        DataFrame with columns: ['Variable', 'CSI', 'Status']
        - Variable: Feature name
        - CSI: CSI value for the variable
        - Status: 'Stable', 'Moderate', or 'Significant' based on CSI value
    """
    csi_results = []
    
    # Get common variables between train and test
    common_vars = [var for var in X_train.columns if var in X_test.columns]
    
    if max_variables is not None:
        common_vars = common_vars[:max_variables]
    
    for var in common_vars:
        try:
            train_vals = X_train[var].dropna()
            test_vals = X_test[var].dropna()
            
            # Skip if not enough data or all values are the same
            if len(train_vals) < 2 or len(test_vals) < 2:
                continue
            
            if train_vals.nunique() < 2 and test_vals.nunique() < 2:
                continue
            
            # Only process numeric variables
            if not pd.api.types.is_numeric_dtype(train_vals):
                continue
            
            # Calculate CSI
            csi_value = calculate_csi(train_vals.values, test_vals.values, q=q)
            
            # Determine status
            if csi_value < 0.1:
                status = 'Stable'
            elif csi_value < 0.25:
                status = 'Moderate'
            else:
                status = 'Significant'
            
            csi_results.append({
                'Variable': var,
                'CSI': float(csi_value),
                'Status': status
            })
        except Exception as e:
            # Skip variables that fail (e.g., too many duplicates, non-numeric after encoding)
            continue
    
    if not csi_results:
        return pd.DataFrame(columns=['Variable', 'CSI', 'Status'])
    
    csi_df = pd.DataFrame(csi_results)
    csi_df = csi_df.sort_values('CSI', ascending=False)
    
    return csi_df




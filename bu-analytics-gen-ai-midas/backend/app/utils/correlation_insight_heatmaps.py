"""Numeric / categorical correlation heatmap payloads (shared by routes and insight jobs)."""

from __future__ import annotations

import base64
import io
import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from app.services.dataframe_state_manager import dataframe_state_manager
from app.services.dataset_service import dataset_manager

logger = logging.getLogger(__name__)


def heatmap_top_n(top_n: Any) -> int:
    """UI allows 5, 10, 15, 20; coerce query param to nearest allowed value."""
    allowed = (5, 10, 15, 20)
    if top_n is None:
        return 20
    try:
        n = int(top_n)
    except (TypeError, ValueError):
        return 20
    if n in allowed:
        return n
    if n < 5:
        return 5
    if n > 20:
        return 20
    for a in reversed(allowed):
        if n >= a:
            return a
    return 5


def cramers_v_pair(s1: pd.Series, s2: pd.Series) -> float:
    """Pairwise Cramér's V (0–1) for two categorical series."""
    from scipy.stats import chi2_contingency

    sub = pd.DataFrame({"a": s1, "b": s2}).dropna()
    if len(sub) < 2:
        return 0.0
    ct = pd.crosstab(sub["a"], sub["b"])
    r, k = int(ct.shape[0]), int(ct.shape[1])
    if r < 2 or k < 2:
        return 0.0
    try:
        chi2, _, _, _ = chi2_contingency(ct)
    except ValueError:
        return 0.0
    if chi2 is None or (isinstance(chi2, float) and np.isnan(chi2)):
        return 0.0
    n = float(ct.to_numpy().sum())
    if n <= 0:
        return 0.0
    min_dim = min(r - 1, k - 1)
    if min_dim <= 0:
        return 0.0
    v = float(np.sqrt((chi2 / n) / min_dim))
    return float(min(1.0, max(0.0, v)))


def build_numeric_correlation_heatmap_payload(
    dataset_id: str,
    target_variable: Optional[str],
    dark_mode: bool,
    top_n: Any,
) -> Dict[str, Any]:
    """Return dict with success, image_base64, image_data_uri (same shape as API route)."""
    k = heatmap_top_n(top_n)
    df = dataframe_state_manager.get_dataframe(dataset_id)
    if df is None:
        df = dataset_manager.load_dataset(dataset_id)
    if df is None:
        raise ValueError(f"Dataset {dataset_id} not found")

    numeric_df = df.select_dtypes(include="number")
    numeric_df = numeric_df.replace([np.inf, -np.inf], np.nan).dropna(axis=1, how="all")

    try:
        n_rows = numeric_df.shape[0]
        nunique_all = numeric_df.nunique(dropna=True)
        id_like_cols = nunique_all[nunique_all == n_rows].index.tolist()
        if id_like_cols:
            logger.info("Dropping ID-like columns from correlation: %s", id_like_cols)
            numeric_df = numeric_df.drop(columns=id_like_cols)
    except Exception as exc:
        logger.warning("Failed to drop ID-like columns: %s", exc)

    nunique_series = numeric_df.nunique(dropna=True)
    cols_with_variance = nunique_series[nunique_series > 1].index.tolist()
    numeric_df = numeric_df[cols_with_variance]

    if target_variable and target_variable in numeric_df.columns:
        try:
            numeric_df = numeric_df.drop(columns=[target_variable])
        except Exception as exc:
            logger.warning("Could not drop target_variable '%s': %s", target_variable, exc)

    if numeric_df.shape[1] == 0:
        raise ValueError("No usable numeric columns found after removing empty columns")

    corr = numeric_df.corr()
    corr_no_diag = corr.copy()
    for idx in range(len(corr_no_diag)):
        corr_no_diag.iat[idx, idx] = 0.0
    top_cols = (
        corr_no_diag.abs()
        .max(axis=1)
        .sort_values(ascending=False)
        .head(k)
        .index.tolist()
    )
    if not top_cols:
        raise ValueError("Not enough correlated features to display")
    corr_subset = corr.loc[top_cols, top_cols]

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    if dark_mode:
        plt.style.use("dark_background")
        fig_bg = "#1f2937"
        text_color = "#e5e7eb"
        title_color = "#f3f4f6"
    else:
        plt.style.use("default")
        fig_bg = "white"
        text_color = "#374151"
        title_color = "#111827"

    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor(fig_bg)
    ax.set_facecolor(fig_bg)
    sns.heatmap(corr_subset, annot=False, cmap="coolwarm", ax=ax, cbar_kws={"shrink": 0.8})
    ax.set_title(
        "Correlation Heatmap For Numerical Features",
        color=title_color,
        fontsize=14,
        fontweight="bold",
        pad=15,
    )
    ax.tick_params(colors=text_color, labelsize=9)
    cbar = ax.collections[0].colorbar
    if cbar:
        cbar.ax.tick_params(colors=text_color)
        cbar.outline.set_edgecolor(text_color)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor=fig_bg, edgecolor="none")
    plt.close()
    plt.style.use("default")
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode("utf-8")
    data_uri = f"data:image/png;base64,{image_base64}"

    return {
        "success": True,
        "image_base64": image_base64,
        "image_data_uri": data_uri,
    }


def build_categorical_association_heatmap_payload(
    dataset_id: str,
    target_variable: Optional[str],
    dark_mode: bool,
    top_n: Any,
) -> Dict[str, Any]:
    """Cramér's V association heatmap (same response shape as API route)."""
    k = heatmap_top_n(top_n)
    df = dataframe_state_manager.get_dataframe(dataset_id)
    if df is None:
        df = dataset_manager.load_dataset(dataset_id)
    if df is None:
        raise ValueError(f"Dataset {dataset_id} not found")

    cat_df = df.select_dtypes(include=["object", "category", "bool", "string"]).copy()
    if cat_df.shape[1] == 0:
        raise ValueError(
            "No categorical columns found for association heatmap",
        )

    n_rows = cat_df.shape[0]
    try:
        nunique_all = cat_df.nunique(dropna=True)
        id_like = nunique_all[nunique_all == n_rows].index.tolist()
        if id_like:
            logger.info("Dropping ID-like categorical columns: %s", id_like)
            cat_df = cat_df.drop(columns=id_like)
    except Exception as exc:
        logger.warning("Failed to drop ID-like categorical columns: %s", exc)

    if target_variable and target_variable in cat_df.columns:
        try:
            cat_df = cat_df.drop(columns=[target_variable])
        except Exception as exc:
            logger.warning("Could not drop target_variable '%s': %s", target_variable, exc)

    max_levels = 35
    min_levels = 2
    usable = []
    for c in cat_df.columns:
        nu = cat_df[c].nunique(dropna=True)
        if min_levels <= nu <= max_levels:
            usable.append(c)
    cat_df = cat_df[usable]

    if cat_df.shape[1] < 2:
        raise ValueError(
            "Need at least two categorical columns with 2–35 distinct values "
            "(after excluding ID-like columns and target).",
        )

    cols = cat_df.columns.tolist()
    n = len(cols)
    vmat = pd.DataFrame(np.eye(n), index=cols, columns=cols)
    for i in range(n):
        for j in range(i + 1, n):
            v = cramers_v_pair(cat_df[cols[i]], cat_df[cols[j]])
            vmat.iat[i, j] = vmat.iat[j, i] = v

    v_no_diag = vmat.copy()
    for idx in range(len(v_no_diag)):
        v_no_diag.iat[idx, idx] = 0.0
    top_cols = (
        v_no_diag.abs()
        .max(axis=1)
        .sort_values(ascending=False)
        .head(k)
        .index.tolist()
    )
    if not top_cols:
        raise ValueError("Could not rank categorical associations")
    subset = vmat.loc[top_cols, top_cols]

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    if dark_mode:
        plt.style.use("dark_background")
        fig_bg = "#1f2937"
        text_color = "#e5e7eb"
        title_color = "#f3f4f6"
    else:
        plt.style.use("default")
        fig_bg = "white"
        text_color = "#374151"
        title_color = "#111827"

    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor(fig_bg)
    ax.set_facecolor(fig_bg)
    sns.heatmap(subset, annot=False, cmap="coolwarm", ax=ax, cbar_kws={"shrink": 0.8})
    ax.set_title(
        "Categorical association (Cramér's V)",
        color=title_color,
        fontsize=14,
        fontweight="bold",
        pad=15,
    )
    ax.tick_params(colors=text_color, labelsize=9)
    cbar = ax.collections[0].colorbar
    if cbar:
        cbar.ax.tick_params(colors=text_color)
        cbar.outline.set_edgecolor(text_color)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(
        buf,
        format="png",
        dpi=300,
        bbox_inches="tight",
        facecolor=fig_bg,
        edgecolor="none",
    )
    plt.close()
    plt.style.use("default")
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode("utf-8")
    data_uri = f"data:image/png;base64,{image_base64}"

    return {
        "success": True,
        "image_base64": image_base64,
        "image_data_uri": data_uri,
    }

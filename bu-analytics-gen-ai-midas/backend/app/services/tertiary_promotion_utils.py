"""
Shared Section 3.4 tertiary promotion logic (depth-1 significance gate).

Used by the sequential auto pipeline and variable-driven (C2) unified segmentation
so both paths apply the same chi-squared / binning test when secondary fails.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

logger = logging.getLogger("midas.app.services.tertiary_promotion_utils")


@dataclass
class SplitterSelectionResult:
    """Result of testing a variable as a splitter within parent segments."""

    variable: str
    depth: int
    is_significant: bool
    p_values: Dict[str, float] = field(default_factory=dict)
    min_p_value: float = 1.0
    segments_significant: int = 0
    quality_score: float = 0.0


@dataclass
class PromotionSuggestion:
    """Section 3.4: guidance when secondary fails the significance gate."""

    suggestion_type: str  # promote_tertiary | stop_at_primary | stop_at_secondary
    message: str
    failed_variable: Optional[str] = None
    suggested_variable: Optional[str] = None
    suggested_p_value: Optional[float] = None


def chi_squared_split_test(
    df: pd.DataFrame,
    variable: str,
    target: str,
    n_bins: int = 5,
) -> float:
    """Chi-squared p-value: variable bins vs target (same logic as auto pipeline)."""
    if variable not in df.columns or target not in df.columns:
        return 1.0

    if np.issubdtype(df[variable].dtype, np.number):
        try:
            bins = pd.qcut(df[variable].fillna(df[variable].median()), q=n_bins, duplicates="drop")
        except Exception:
            bins = pd.cut(df[variable].fillna(df[variable].median()), bins=n_bins)
    else:
        bins = df[variable].fillna("__MISSING__")

    contingency = pd.crosstab(bins, df[target])

    if contingency.shape[0] < 2 or contingency.shape[1] < 2:
        return 1.0

    _, p_value, _, _ = chi2_contingency(contingency)
    return float(p_value)


def test_splitter_significance(
    df: pd.DataFrame,
    candidate_variable: str,
    target_variable: str,
    parent_segments: List[Dict[str, Any]],
    segment_column: str,
    significance_threshold: float = 0.05,
) -> SplitterSelectionResult:
    """Test whether candidate_variable splits significantly within each parent segment."""
    result = SplitterSelectionResult(
        variable=candidate_variable,
        depth=len(parent_segments),
        is_significant=False,
        p_values={},
        min_p_value=1.0,
        segments_significant=0,
    )

    if candidate_variable not in df.columns:
        return result

    for seg in parent_segments:
        seg_name = seg.get("segment_name", str(seg.get("segment_id", "unknown")))

        if segment_column in df.columns:
            seg_mask = df[segment_column].astype(str) == str(seg_name)
        else:
            continue

        seg_df = df[seg_mask]

        if len(seg_df) < 100:
            result.p_values[seg_name] = 1.0
            continue

        try:
            p_value = chi_squared_split_test(seg_df, candidate_variable, target_variable)
            result.p_values[seg_name] = p_value

            if p_value < result.min_p_value:
                result.min_p_value = p_value

            if p_value < significance_threshold:
                result.segments_significant += 1

        except Exception as e:
            logger.debug("Chi-squared test failed for %s in %s: %s", candidate_variable, seg_name, e)
            result.p_values[seg_name] = 1.0

    result.is_significant = result.segments_significant > 0
    return result


def check_tertiary_promotion(
    df: pd.DataFrame,
    target_variable: str,
    primary_segments: List[Dict[str, Any]],
    segment_column: str,
    failed_secondary: str,
    tertiary_candidate: Optional[str],
    significance_threshold: float = 0.05,
) -> PromotionSuggestion:
    """
    Section 3.4: when secondary fails, test tertiary at depth 1 (same gate as auto).
    """
    if not tertiary_candidate:
        return PromotionSuggestion(
            suggestion_type="stop_at_primary",
            message=(
                f"Secondary variable '{failed_secondary}' was not significant at depth 1. "
                f"No tertiary variable specified. Segmentation uses only the primary variable."
            ),
            failed_variable=failed_secondary,
        )

    tertiary_result = test_splitter_significance(
        df=df,
        candidate_variable=tertiary_candidate,
        target_variable=target_variable,
        parent_segments=primary_segments,
        segment_column=segment_column,
        significance_threshold=significance_threshold,
    )

    if tertiary_result.is_significant:
        return PromotionSuggestion(
            suggestion_type="promote_tertiary",
            message=(
                f"Secondary variable '{failed_secondary}' was not significant at depth 1. "
                f"However, tertiary variable '{tertiary_candidate}' shows significant separation "
                f"(p = {tertiary_result.min_p_value:.4f}). "
                f"Consider promoting it to Secondary Splitter and re-running."
            ),
            failed_variable=failed_secondary,
            suggested_variable=tertiary_candidate,
            suggested_p_value=tertiary_result.min_p_value,
        )

    return PromotionSuggestion(
        suggestion_type="stop_at_primary",
        message=(
            f"Neither the secondary variable '{failed_secondary}' nor tertiary variable "
            f"'{tertiary_candidate}' produced significant splits within the primary segments. "
            f"The segmentation uses only the primary variable."
        ),
        failed_variable=failed_secondary,
    )

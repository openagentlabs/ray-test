"""Shared VIF table → frontend payload helpers (used by API routes and insight jobs)."""

from __future__ import annotations

import math
from typing import Any, Dict, List

import pandas as pd


def parse_vif_result_value(vif_raw: Any) -> float | None:
    """Coerce VIF cell to float, ``inf``, or ``None`` if calculation failed."""
    if vif_raw == "Error":
        return None
    if vif_raw == "∞" or (
        isinstance(vif_raw, str) and vif_raw.strip() in ("∞", "inf", "Inf", "INF")
    ):
        return float("inf")
    if isinstance(vif_raw, bool):
        return float(vif_raw)
    if isinstance(vif_raw, (int, float)):
        x = float(vif_raw)
        return None if math.isnan(x) else x
    if isinstance(vif_raw, str):
        try:
            x = float(vif_raw.strip())
            return None if math.isnan(x) else x
        except (TypeError, ValueError):
            return None
    return None


def build_vif_frontend_analysis_payload(
    df: pd.DataFrame, vif_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Build ``analysis_results`` + ``dataset_summary`` for VIF API responses."""
    vif_json_cap = 99999.0
    analysis_results: Dict[str, Any] = {}
    for result in vif_results:
        variable_name = result.get("Variable", "")
        interpretation = result.get("Interpretation", "")
        vif_raw = result.get("VIF", 0)
        vif_num = parse_vif_result_value(vif_raw)

        if vif_num is None:
            analysis_results[variable_name] = {
                "variable_name": variable_name,
                "variable_type": "numerical",
                "vif_value": 0.0,
                "multicollinearity_level": "low",
                "error": "VIF calculation failed for this variable",
                "analysis_result": {
                    "insights": [
                        interpretation or "VIF could not be computed for this variable."
                    ],
                    "visualization_data": {"chart_type": "bar", "data": {}},
                },
                "summary": {
                    "key_insight": "VIF: error",
                    "multicollinearity_level": "low",
                    "recommendation": interpretation or "Calculation failed",
                },
            }
            continue

        is_infinite = vif_num == float("inf")
        vif_for_json = vif_json_cap if is_infinite else float(vif_num)

        if is_infinite or vif_for_json >= 20:
            multicollinearity_level = "very_high"
        elif vif_for_json >= 10:
            multicollinearity_level = "high"
        elif vif_for_json >= 5:
            multicollinearity_level = "moderate"
        else:
            multicollinearity_level = "low"

        vif_label = "∞ (capped for display)" if is_infinite else f"{vif_for_json:.4f}"
        analysis_results[variable_name] = {
            "variable_name": variable_name,
            "variable_type": "numerical",
            "vif_value": vif_for_json,
            "multicollinearity_level": multicollinearity_level,
            "analysis_result": {
                "insights": [
                    f"VIF: {vif_label} ({multicollinearity_level} multicollinearity)"
                ],
                "visualization_data": {"chart_type": "bar", "data": {}},
            },
            "summary": {
                "key_insight": f"VIF: {vif_label} ({multicollinearity_level})",
                "multicollinearity_level": multicollinearity_level,
                "recommendation": interpretation,
            },
        }

    return {
        "total_variables_analyzed": len(vif_results),
        "analysis_results": analysis_results,
        "dataset_summary": {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024**2,
        },
    }

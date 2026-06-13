"""Module-level insight job functions for ``background_job_manager`` (picklable, CPU-heavy)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from app.services.analytics_cache import analytics_cache
from app.utils.correlation_insight_heatmaps import (
    build_categorical_association_heatmap_payload,
    build_numeric_correlation_heatmap_payload,
)
from app.utils.helpers import clean_nan_values, safe_json_serialize
from app.utils.vif_insight_payload import build_vif_frontend_analysis_payload

logger = logging.getLogger(__name__)


def _cache_scope_key(base_scope: str, extra: Optional[Dict[str, Any]] = None) -> str:
    if not extra:
        return base_scope
    tail = json.dumps(extra, sort_keys=True, default=str)
    return f"{base_scope}|{tail}"


def run_insight_vif_analysis_job(params: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.dataframe_state_manager import dataframe_state_manager
    from app.services.dataset_service import dataset_manager
    from app.services.job_locks import dataset_job_lock
    from app.utils.helpers import generate_vif_analysis_tables

    dataset_id = params["dataset_id"]
    target_variable = params["target_variable"]
    scope_key = params["scope_key"]
    version = int(params["version"])

    with dataset_job_lock(dataset_id, job_label="insight_vif_analysis"):
        df = dataframe_state_manager.get_dataframe(dataset_id)
        if df is None:
            df = dataset_manager.load_dataset(dataset_id)
        if df is None:
            raise ValueError(f"Dataset {dataset_id} not found")
        if target_variable not in df.columns:
            raise ValueError(f"Target variable '{target_variable}' not found")

        vif_sections = generate_vif_analysis_tables(dataset_id, target_variable)
        if not vif_sections:
            raise ValueError("Failed to generate VIF analysis")
        vif_section = vif_sections[0]
        vif_rows = vif_section.get("rows", [])
        vif_payload = build_vif_frontend_analysis_payload(df, vif_rows)

        body: Dict[str, Any] = {
            "success": True,
            "message": f"VIF analysis completed for dataset {dataset_id}",
            "dataset_id": dataset_id,
            "target_variable": target_variable,
            "total_variables_analyzed": vif_payload["total_variables_analyzed"],
            "vif_analysis": {
                "columns": vif_section["columns"],
                "rows": vif_rows,
                "title": vif_section["title"],
                "thresholds": vif_section["thresholds"],
            },
            "analysis_results": vif_payload["analysis_results"],
            "dataset_summary": vif_payload["dataset_summary"],
        }

    analytics_cache.set("insight_vif_analysis", dataset_id, scope_key, version, body)
    return body


def run_insight_iv_analysis_job(params: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.dataframe_state_manager import dataframe_state_manager
    from app.services.dataset_service import dataset_manager
    from app.services.job_locks import dataset_job_lock
    from app.utils.helpers import generate_iv_analysis_tables_pipeline_style

    dataset_id = params["dataset_id"]
    target_variable = params["target_variable"]
    bins = int(params.get("bins") or 10)
    scope_key = params["scope_key"]
    version = int(params["version"])

    with dataset_job_lock(dataset_id, job_label="insight_iv_analysis"):
        df = dataframe_state_manager.get_dataframe(dataset_id)
        if df is None:
            df = dataset_manager.load_dataset(dataset_id)
        if df is None:
            raise ValueError(f"Dataset {dataset_id} not found")
        if target_variable not in df.columns:
            raise ValueError(f"Target variable '{target_variable}' not found")

        iv_sections = generate_iv_analysis_tables_pipeline_style(
            dataset_id=dataset_id,
            target_variable=target_variable,
            bins=bins,
        )
        if not iv_sections:
            raise ValueError("Failed to generate IV analysis")
        summary_section = next(
            (s for s in iv_sections if s.get("analysis_kind") == "iv_analysis_summary"),
            None,
        )
        if not summary_section:
            raise ValueError("IV analysis summary not found")
        iv_rows = summary_section.get("rows", [])

        analysis_results: Dict[str, Any] = {}
        for row in iv_rows:
            feature_name = row.get("Feature Name", "")
            try:
                iv_value = float(row.get("IV", 0) or 0)
            except (TypeError, ValueError):
                iv_value = 0.0
            if iv_value < 0.02:
                iv_strength = "weak"
            elif iv_value < 0.1:
                iv_strength = "medium"
            elif iv_value < 0.3:
                iv_strength = "strong"
            else:
                iv_strength = "very_strong"
            analysis_results[feature_name] = {
                "variable_name": feature_name,
                "variable_type": "numerical",
                "iv_value": iv_value,
                "iv_strength": iv_strength,
                "analysis_result": {
                    "insights": [f"IV value: {iv_value:.4f} ({iv_strength} predictive power)"],
                    "visualization_data": {"chart_type": "bar", "data": {}},
                },
                "summary": {
                    "key_insight": f"IV: {iv_value:.4f} ({iv_strength})",
                    "iv_strength": iv_strength,
                    "predictive_power": f"{iv_strength.capitalize()} predictive power",
                },
            }

        body = {
            "success": True,
            "message": f"IV analysis completed for dataset {dataset_id}",
            "dataset_id": dataset_id,
            "target_variable": target_variable,
            "total_variables_analyzed": len(iv_rows),
            "analysis_results": analysis_results,
            "dataset_summary": {
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024**2,
            },
        }

    analytics_cache.set("insight_iv_analysis", dataset_id, scope_key, version, body)
    return body


def run_insight_correlation_ratio_job(params: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.dataframe_state_manager import dataframe_state_manager
    from app.services.job_locks import dataset_job_lock
    from app.utils.helpers import generate_correlation_ratio_analysis_tables

    dataset_id = params["dataset_id"]
    target_variable = params["target_variable"]
    requested_categorical_vars = params.get("requested_categorical_vars")
    requested_numerical_vars = params.get("requested_numerical_vars")
    scope_key = params["scope_key"]
    version = int(params["version"])

    with dataset_job_lock(dataset_id, job_label="insight_correlation_ratio"):
        _df = dataframe_state_manager.get_dataframe_readonly(dataset_id)
        if _df is None:
            raise ValueError(f"Dataset {dataset_id} not found")
        if target_variable not in _df.columns:
            raise ValueError(f"Target variable '{target_variable}' not found")

        sections = generate_correlation_ratio_analysis_tables(
            dataset_id=dataset_id,
            target_variable=target_variable,
            categorical_variables=requested_categorical_vars,
            numerical_variables=requested_numerical_vars,
        )

        response_data = {
            "success": True,
            "message": f"Correlation ratio (η) analysis completed for dataset {dataset_id}",
            "dataset_id": dataset_id,
            "target_variable": target_variable,
            "sections": sections or [],
            "analysis_timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        clean_response = clean_nan_values(response_data, replace_with=None)
        safe_response = safe_json_serialize(clean_response)

    analytics_cache.set("insight_correlation_ratio", dataset_id, scope_key, version, safe_response)
    return safe_response


def run_insight_correlation_matrix_job(params: Dict[str, Any]) -> Dict[str, Any]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import seaborn as sns

    from app.services.dataframe_state_manager import dataframe_state_manager
    from app.services.dataset_service import dataset_manager
    from app.services.job_locks import dataset_job_lock

    dataset_id = params["dataset_id"]
    target_variable = params["target_variable"]
    correlation_method = params.get("correlation_method") or "pearson"
    scope_key = params["scope_key"]
    version = int(params["version"])

    with dataset_job_lock(dataset_id, job_label="insight_correlation_matrix"):
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
                numeric_df = numeric_df.drop(columns=id_like_cols)
        except Exception:
            pass

        nunique_series = numeric_df.nunique(dropna=True)
        cols_with_variance = nunique_series[nunique_series > 1].index.tolist()
        numeric_df = numeric_df[cols_with_variance]

        if numeric_df.shape[1] == 0:
            raise ValueError("No usable numeric columns found for correlation matrix")

        corr_matrix = numeric_df.corr(method=correlation_method)

        corr_dict = corr_matrix.to_dict()
        variables = list(corr_matrix.columns)
        top_correlations = []
        for i, var1 in enumerate(variables):
            for j, var2 in enumerate(variables):
                if i < j:
                    corr_val = corr_matrix.iloc[i, j]
                    if not np.isnan(corr_val):
                        top_correlations.append(
                            {
                                "variable_1": var1,
                                "variable_2": var2,
                                "correlation": float(corr_val),
                                "abs_correlation": abs(float(corr_val)),
                            }
                        )
        top_correlations.sort(key=lambda x: x["abs_correlation"], reverse=True)
        top_correlations = top_correlations[:20]

        heatmap_data = None
        if len(variables) > 1:
            n_top = min(15, len(variables))
            top_vars = variables[:n_top]
            corr_subset = corr_matrix.loc[top_vars, top_vars]

            fig, ax = plt.subplots(figsize=(12, 10))
            sns.heatmap(
                corr_subset,
                annot=True,
                fmt=".2f",
                cmap="coolwarm",
                center=0,
                square=True,
                linewidths=0.5,
                cbar_kws={"shrink": 0.8},
                ax=ax,
            )
            ax.set_title(
                f"Correlation Matrix Heatmap ({correlation_method.title()}) - Top {n_top} Variables"
            )
            buf = __import__("io").BytesIO()
            plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            plt.close()
            buf.seek(0)
            image_base64 = __import__("base64").b64encode(buf.read()).decode("utf-8")
            heatmap_data = f"data:image/png;base64,{image_base64}"

        response_data = {
            "success": True,
            "dataset_id": dataset_id,
            "target_variable": target_variable,
            "correlation_method": correlation_method,
            "total_variables": len(variables),
            "variables": variables,
            "correlation_matrix": corr_dict,
            "top_correlations": top_correlations,
            "heatmap_image": heatmap_data,
            "analysis_timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": f"Correlation matrix analysis completed for {len(variables)} variables",
        }

        clean_response = clean_nan_values(response_data, replace_with=None)
        safe_response = safe_json_serialize(clean_response)

    analytics_cache.set("insight_correlation_matrix", dataset_id, scope_key, version, safe_response)
    return safe_response


def run_insight_bivariate_all_job(params: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.dataframe_state_manager import dataframe_state_manager
    from app.services.job_locks import dataset_job_lock
    from app.utils.helpers import (
        analyze_categorical_vs_target,
        analyze_numerical_vs_target,
        generate_dataset_summary,
        generate_variable_summary,
    )

    dataset_id = params["dataset_id"]
    target_variable = params["target_variable"]
    binning_method = params.get("binning_method") or "quantile"
    top_categories = int(params.get("top_categories") or 10)
    bins = int(params.get("bins") or 10)
    scope_key = params["scope_key"]
    version = int(params["version"])

    with dataset_job_lock(dataset_id, job_label="insight_bivariate_all"):
        df = dataframe_state_manager.get_dataframe_readonly(dataset_id)
        if df is None:
            raise ValueError(f"No dataframe found for dataset {dataset_id}")
        if target_variable not in df.columns:
            raise ValueError(f"Target variable '{target_variable}' not found")

        dataset_summary = generate_dataset_summary(df)

        def _run_all_bivariate() -> Dict[str, Any]:
            results: Dict[str, Any] = {}
            for col in dataset_summary.get("categorical_columns", []):
                if col == target_variable:
                    continue
                try:
                    result = analyze_categorical_vs_target(
                        df,
                        target_variable,
                        col,
                        dataset_summary,
                        top_categories,
                        dataset_id,
                    )
                    results[col] = {
                        "variable_name": col,
                        "variable_type": "categorical",
                        "analysis_result": result,
                        "summary": generate_variable_summary(result, "categorical"),
                    }
                except Exception as exc:
                    logger.warning("Failed to analyze categorical variable %s: %s", col, exc)
                    results[col] = {
                        "variable_name": col,
                        "variable_type": "categorical",
                        "error": str(exc),
                        "summary": f"Analysis failed: {exc}",
                    }
            for col in dataset_summary.get("numeric_columns", []):
                if col == target_variable:
                    continue
                try:
                    result = analyze_numerical_vs_target(
                        df,
                        target_variable,
                        col,
                        dataset_summary,
                        binning_method,
                        bins,
                        dataset_id,
                    )
                    results[col] = {
                        "variable_name": col,
                        "variable_type": "numerical",
                        "analysis_result": result,
                        "summary": generate_variable_summary(result, "numerical"),
                    }
                except Exception as exc:
                    logger.warning("Failed to analyze numerical variable %s: %s", col, exc)
                    results[col] = {
                        "variable_name": col,
                        "variable_type": "numerical",
                        "error": str(exc),
                        "summary": f"Analysis failed: {exc}",
                    }
            return results

        all_analysis_results = _run_all_bivariate()
        response_payload = {
            "success": True,
            "message": f"Bivariate analysis completed for all variables in dataset {dataset_id}",
            "dataset_id": dataset_id,
            "target_variable": target_variable,
            "total_variables_analyzed": len(all_analysis_results),
            "analysis_results": all_analysis_results,
            "dataset_summary": {
                "total_rows": dataset_summary["shape"][0],
                "total_columns": dataset_summary["shape"][1],
                "memory_usage_mb": dataset_summary["memory_usage_mb"],
            },
        }

    analytics_cache.set("insight_bivariate_all", dataset_id, scope_key, version, response_payload)
    return response_payload


def run_insight_correlation_heatmap_basic_job(params: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.job_locks import dataset_job_lock

    dataset_id = params["dataset_id"]
    target_variable = params.get("target_variable")
    dark_mode = bool(params.get("dark_mode"))
    top_n = params.get("top_n")
    scope_key = params["scope_key"]
    version = int(params["version"])

    with dataset_job_lock(dataset_id, job_label="insight_corr_heatmap_basic"):
        body = build_numeric_correlation_heatmap_payload(
            dataset_id, target_variable, dark_mode, top_n
        )

    analytics_cache.set("insight_correlation_heatmap_basic", dataset_id, scope_key, version, body)
    return body


def run_insight_correlation_heatmap_categorical_job(params: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.job_locks import dataset_job_lock

    dataset_id = params["dataset_id"]
    target_variable = params.get("target_variable")
    dark_mode = bool(params.get("dark_mode"))
    top_n = params.get("top_n")
    scope_key = params["scope_key"]
    version = int(params["version"])

    with dataset_job_lock(dataset_id, job_label="insight_corr_heatmap_cat"):
        body = build_categorical_association_heatmap_payload(
            dataset_id, target_variable, dark_mode, top_n
        )

    analytics_cache.set(
        "insight_correlation_heatmap_categorical", dataset_id, scope_key, version, body
    )
    return body

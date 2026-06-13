"""
Rebuild ValidationSuiteResult from an in-memory segmentation payload (merge/cutoff/edit).

Same outputs as unified /segmentation/run: chi-squared, merge recommendations,
OOS validation, bootstrap stability, recommendation_category — by materializing
`_segment_assignment` and calling the shared validation suite (routes helpers).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.core.logging_config import get_logger
from app.models.schemas import ManualSegmentRule, SegmentDetail, ValidationSuiteResult
from app.services.dataset_service import dataset_manager

logger = get_logger(__name__)


def _resolve_min_segment_size_for_validation(
    total_records: int, parameters: Optional[Dict[str, Any]], segmentation_result: Dict[str, Any]
) -> int:
    params = parameters or segmentation_result.get("parameters") or {}
    mode = params.get("min_segment_size_mode")
    if mode == "percentage":
        pct = float(params.get("min_segment_size_pct", 5.0))
        return max(1, int(total_records * pct / 100.0))
    ms = params.get("min_segment_size")
    if ms is not None:
        try:
            return max(1, int(ms))
        except (TypeError, ValueError):
            pass
    return 1000


def rebuild_validation_from_segmentation_result(
    dataset_id: str,
    df: pd.DataFrame,
    segmentation_result: Dict[str, Any],
    segment_dicts: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Optional[ValidationSuiteResult]]:
    """
    Recompute segment stats from rules, assign `_segment_assignment`, and run
    the full validation suite (same path as post-edit refresh in routes).

    Returns:
        (serialized_segment_dicts, validation_or_none)
    """
    # Late import avoids circular import at app startup (routes imports this module).
    from app.api.routes import (
        _calculate_wilson_score_ci,
        _calculate_woe_iv,
        _run_validation_suite,
        _segmentation_rule_mask,
        _manual_rules_assign_labels,
        _flatten_or_rule_to_leaves,
    )

    params = segmentation_result.get("parameters") or {}
    target_var = params.get("target_variable") or segmentation_result.get("target_variable")
    if (not target_var or target_var not in df.columns) and dataset_id:
        try:
            info = dataset_manager.get_dataset_info(dataset_id)
            tv = (info or {}).get("target_variable")
            if tv and tv in df.columns:
                target_var = tv
        except Exception:
            pass
    if not target_var or target_var not in df.columns:
        logger.warning("Skipping full validation rebuild: target variable missing on dataframe")
        return segment_dicts, None

    try:
        overall_er = segmentation_result.get("overall_event_rate")
        if overall_er is None:
            overall_er = float(df[target_var].mean() * 100)
    except Exception:
        overall_er = 10.0

    min_seg = _resolve_min_segment_size_for_validation(len(df), params, segmentation_result)
    total_records = len(df)
    ordered = sorted(segment_dicts, key=lambda x: x.get("segment_id", 0))

    mode_str = str(segmentation_result.get("mode") or "").lower()
    mr_raw = segmentation_result.get("manual_rules")
    labels_from_manual: Optional[pd.Series] = None
    if mode_str == "manual_rules" and isinstance(mr_raw, list) and len(mr_raw) > 0:
        try:
            rules = [ManualSegmentRule.model_validate(x) for x in mr_raw]
            labels_from_manual = _manual_rules_assign_labels(df, rules)
        except Exception as e:
            logger.warning("manual_rules rebuild failed, using rule_definition masks: %s", e)
            labels_from_manual = None

    masks_by_name: Dict[str, pd.Series] = {}
    if labels_from_manual is not None:
        for seg in ordered:
            name = seg.get("segment_name") or f"Segment {seg.get('segment_id', 0)}"
            masks_by_name[name] = (labels_from_manual == name).fillna(False)
    else:
        # Merged segments use (R1) OR (R2). Assign those *before* atomic rules so
        # first-wins `& ~assigned` does not strip rows that belong in the OR union
        # (e.g. another segment processed earlier matching a strict subset/parse edge).
        or_first: List[Dict[str, Any]] = []
        rest: List[Dict[str, Any]] = []
        for seg in ordered:
            rule = (seg.get("rule_definition") or "").strip()
            if not rule:
                rest.append(seg)
                continue
            try:
                n_or = len(_flatten_or_rule_to_leaves(rule))
            except Exception:
                n_or = 1
            (or_first if n_or > 1 else rest).append(seg)
        or_first.sort(key=lambda x: x.get("segment_id", 0))
        rest.sort(key=lambda x: x.get("segment_id", 0))
        processing_order = or_first + rest

        assigned = pd.Series([False] * len(df), index=df.index)
        for seg in processing_order:
            name = seg.get("segment_name") or f"Segment {seg.get('segment_id', 0)}"
            rule = seg.get("rule_definition") or ""
            try:
                m = _segmentation_rule_mask(df, rule) & ~assigned
            except Exception as e:
                logger.warning("Rule mask failed for segment '%s': %s", name, e)
                m = pd.Series([False] * len(df), index=df.index)
            masks_by_name[name] = m
            assigned = assigned | m

    col = "_segment_assignment"
    df_ws = df.copy()
    df_ws[col] = "Unassigned"
    for name, m in masks_by_name.items():
        df_ws.loc[m, col] = name

    if "split_tag" in df.columns and "split_tag" not in df_ws.columns:
        df_ws["split_tag"] = df["split_tag"].values

    segment_details: List[SegmentDetail] = []
    for seg in ordered:
        name = seg.get("segment_name") or f"Segment {seg.get('segment_id', 0)}"
        m = masks_by_name.get(name, pd.Series([False] * len(df), index=df.index))
        seg_df = df.loc[m]
        record_count = int(len(seg_df))
        event_count = 0
        event_rate = 0.0
        if target_var in seg_df.columns and record_count > 0:
            try:
                event_count = int(seg_df[target_var].sum())
                event_rate = float(seg_df[target_var].mean() * 100)
            except Exception:
                pass
        woe, iv_contrib = _calculate_woe_iv(seg_df, df, target_var, record_count, total_records, event_count)
        ci_lower, ci_upper = _calculate_wilson_score_ci(record_count, event_count)
        segment_details.append(
            SegmentDetail(
                segment_id=int(seg.get("segment_id", len(segment_details) + 1)),
                segment_name=name,
                rule_definition=seg.get("rule_definition", "") or "",
                record_count=record_count,
                pct_of_population=round(record_count / total_records * 100, 2) if total_records else 0.0,
                event_count=event_count,
                event_rate=round(event_rate, 4),
                event_rate_ci_lower=ci_lower,
                event_rate_ci_upper=ci_upper,
                woe=round(woe, 4),
                iv_contribution=round(iv_contrib, 4),
            )
        )

    segment_details.sort(key=lambda x: x.segment_id)

    any_rows_labeled = any(m.any() for m in masks_by_name.values())
    has_assignments = any_rows_labeled and df_ws[col].nunique() > 1
    validation = _run_validation_suite(
        segments=segment_details,
        df=df_ws,
        target_var=target_var,
        total_records=total_records,
        overall_event_rate=float(overall_er) if overall_er is not None else 10.0,
        min_segment_size=min_seg,
        dataset_id=dataset_id,
        segment_column=col if has_assignments else None,
        run_stability=bool(has_assignments),
        run_oos_validation=bool(has_assignments),
    )

    seg_out: List[Dict[str, Any]] = []
    for d in segment_details:
        dumped = d.model_dump() if hasattr(d, "model_dump") else d.dict()
        seg_out.append(json.loads(json.dumps(dumped, default=str)))

    return seg_out, validation

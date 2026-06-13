"""
Segmentation Validation Module

Implements the Three-Condition Merge Framework and Validation Suite
for the Segmentation Agent as specified in the implementation plan.

Three Conditions for keeping segments separate:
1. Reliability: Both segments meet minimum size/events thresholds
2. Practical Separation: Event rate difference exceeds adaptive threshold
3. Validation Support: Separation holds on out-of-sample data (when available)
"""

import os
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from scipy import stats
from dataclasses import dataclass
from enum import Enum

from app.core.logging_config import get_logger
from app.services.segmentation_stability import _segment_mean_target_pct
from app.models.schemas import (
    SegmentDetail, SegmentFlag, MergeRecommendation,
    ValidationSuiteResult, BootstrapStabilityResult, OutOfSampleValidation,
    VariableRelevanceMatrix
)

logger = get_logger(__name__)

# Late import to avoid circular dependency
_stability_analyzer = None


def _json_safe_float(value: Any, default: float = 0.0) -> float:
    """Starlette/FastAPI JSON rejects NaN/inf — coerce for API payloads."""
    try:
        x = float(value)
        if not np.isfinite(x):
            return float(default)
        return float(x)
    except (TypeError, ValueError):
        return float(default)


def _chi2_survival_pvalue(chi2: float, dof: int) -> float:
    """
    SciPy's chi2_contingency returns p=0.0 when the true p underflows float64.
    Use the log survival function; when logsf hits -inf, return a small positive
    float so JSON/UI can still show a numeric p (e.g. 1e-200).
    """
    if dof <= 0 or chi2 <= 0 or not np.isfinite(chi2):
        return 1.0
    try:
        log_p = stats.chi2.logsf(float(chi2), int(dof))
        if not np.isfinite(log_p):
            return 1e-200
        tiny_log = np.log(np.finfo(float).tiny)
        if log_p <= tiny_log:
            return 1e-200
        return float(np.exp(log_p))
    except Exception:
        return 1e-200

def _get_stability_analyzer():
    """Get or create stability analyzer (lazy loading to avoid circular imports)."""
    global _stability_analyzer
    if _stability_analyzer is None:
        from app.services.segmentation_stability import BootstrapStabilityAnalyzer
        _stability_analyzer = BootstrapStabilityAnalyzer()
    return _stability_analyzer


# =============================================================================
# Configuration Constants (as specified in plan Section 16)
# =============================================================================

class SegmentationConfig:
    """Configuration constants for segmentation validation."""
    
    # Reliability thresholds
    DEFAULT_MIN_EVENTS = 200
    DEFAULT_MIN_SEGMENT_ABS = 1000
    DEFAULT_MIN_SEGMENT_PCT = 5.0
    
    # Practical separation thresholds
    PRACTICAL_SEP_MIN_PP = 2.0  # Minimum 2 percentage points
    PRACTICAL_SEP_RATIO = 0.20  # 20% of overall event rate
    
    # Statistical thresholds
    SIGNIFICANCE_LEVEL = 0.05
    
    # IV thresholds
    IV_STRONG = 0.10
    IV_MODERATE = 0.05
    IV_SUSPICIOUS = 0.50
    
    # Cramer's V threshold
    CRAMERS_V_THRESHOLD = 0.10
    
    # Bootstrap stability thresholds
    BOOTSTRAP_RUNS = 30
    RANK_ORDER_STRONG = 0.80
    RANK_ORDER_EXPLORATORY = 0.60
    
    # Tree constraints
    MAX_DEPTH = 3
    MAX_SEGMENTS_DEFAULT = 7
    MAX_SEGMENTS_UPPER = 10
    
    # Out-of-sample thresholds
    OOS_EVENT_RATE_DRIFT = 3.0  # percentage points
    OOS_SIZE_DRIFT = 5.0  # percentage points
    
    # WoE calculation
    WOE_EPSILON = 0.5


def refresh_segmentation_config_from_environment() -> None:
    """
    Override SegmentationConfig class attributes from environment (plan Section 16).
    Variables: MIDAS_SEGMENTATION_<CONSTANT_NAME> e.g. MIDAS_SEGMENTATION_DEFAULT_MIN_EVENTS=250
    """
    try:
        import app.core.config  # noqa: F401 — loads `.env` into os.environ when available
    except Exception:
        pass

    prefix = "MIDAS_SEGMENTATION_"
    int_keys = {
        "DEFAULT_MIN_EVENTS",
        "DEFAULT_MIN_SEGMENT_ABS",
        "BOOTSTRAP_RUNS",
        "MAX_DEPTH",
        "MAX_SEGMENTS_DEFAULT",
        "MAX_SEGMENTS_UPPER",
    }
    float_keys = {
        "DEFAULT_MIN_SEGMENT_PCT",
        "PRACTICAL_SEP_MIN_PP",
        "PRACTICAL_SEP_RATIO",
        "SIGNIFICANCE_LEVEL",
        "IV_STRONG",
        "IV_MODERATE",
        "IV_SUSPICIOUS",
        "CRAMERS_V_THRESHOLD",
        "RANK_ORDER_STRONG",
        "RANK_ORDER_EXPLORATORY",
        "OOS_EVENT_RATE_DRIFT",
        "OOS_SIZE_DRIFT",
        "WOE_EPSILON",
    }
    for name in int_keys | float_keys:
        raw = os.getenv(f"{prefix}{name}")
        if raw is None or str(raw).strip() == "":
            continue
        try:
            if name in int_keys:
                setattr(SegmentationConfig, name, int(raw))
            else:
                setattr(SegmentationConfig, name, float(raw))
        except ValueError:
            logger.warning("Ignoring invalid %s%s=%r", prefix, name, raw)


def apply_segmentation_config_overrides_from_json_file() -> None:
    """
    Optional JSON overrides (plan §16): set MIDAS_SEGMENTATION_CONFIG_FILE to a path
    whose JSON object maps SegmentationConfig attribute names to numbers.
    Applied after environment overrides.
    """
    path = (os.getenv("MIDAS_SEGMENTATION_CONFIG_FILE") or "").strip()
    if not path:
        return
    try:
        import json
        from pathlib import Path

        p = Path(path)
        if not p.is_file():
            logger.warning("MIDAS_SEGMENTATION_CONFIG_FILE is not a file: %s", path)
            return
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning("MIDAS_SEGMENTATION_CONFIG_FILE must contain a JSON object")
            return
        for name, raw in data.items():
            if not hasattr(SegmentationConfig, name) or name.startswith("_"):
                continue
            if raw is None or str(raw).strip() == "":
                continue
            cur = getattr(SegmentationConfig, name)
            try:
                if isinstance(cur, bool):
                    setattr(SegmentationConfig, name, bool(raw))
                elif isinstance(cur, int) and not isinstance(cur, bool):
                    setattr(SegmentationConfig, name, int(raw))
                else:
                    setattr(SegmentationConfig, name, float(raw))
            except (TypeError, ValueError):
                logger.warning("Ignoring invalid config file entry %s=%r", name, raw)
    except Exception as e:
        logger.warning("Failed to load MIDAS_SEGMENTATION_CONFIG_FILE: %s", e)


refresh_segmentation_config_from_environment()
apply_segmentation_config_overrides_from_json_file()


class FailedCondition(str, Enum):
    """Enum for merge condition failures."""
    RELIABILITY = "reliability"
    PRACTICAL_SEPARATION = "practical_separation"
    VALIDATION = "validation"


@dataclass
class SegmentPair:
    """Represents a pair of segments for merge evaluation."""
    segment_a: SegmentDetail
    segment_b: SegmentDetail
    event_rate_diff: float
    practical_threshold: float


# =============================================================================
# Three-Condition Merge Framework
# =============================================================================

class ThreeConditionMergeFramework:
    """
    Implements the three-condition merge framework from Section 4.3 of the plan.
    
    A pair should be kept separate only if ALL three conditions hold.
    If any condition fails, the pair is flagged as a merge candidate.
    """
    
    def __init__(self, config: SegmentationConfig = None):
        self.config = config or SegmentationConfig()
    
    def evaluate_pair(
        self,
        seg_a: SegmentDetail,
        seg_b: SegmentDetail,
        overall_event_rate: float,
        min_segment_size: int,
        oos_data: Optional[Dict[str, Any]] = None
    ) -> Optional[MergeRecommendation]:
        """
        Evaluate a segment pair against all three conditions.
        
        Returns MergeRecommendation if any condition fails, None if all pass.
        """
        # Calculate practical threshold
        practical_threshold = max(
            self.config.PRACTICAL_SEP_MIN_PP,
            overall_event_rate * self.config.PRACTICAL_SEP_RATIO
        )
        
        event_rate_diff = abs(seg_a.event_rate - seg_b.event_rate)
        
        # Check Condition 1: Reliability
        reliability_failure = self._check_reliability(seg_a, seg_b, min_segment_size)
        if reliability_failure:
            return self._create_recommendation(
                seg_a, seg_b, FailedCondition.RELIABILITY,
                event_rate_diff, practical_threshold,
                reliability_failure,
            )
        
        # Check Condition 2: Practical Separation
        if event_rate_diff < practical_threshold:
            return self._create_recommendation(
                seg_a, seg_b, FailedCondition.PRACTICAL_SEPARATION,
                event_rate_diff, practical_threshold,
                f"{event_rate_diff:.2f}pp < {practical_threshold:.2f}pp — rates too close to treat as distinct.",
            )
        
        # Check Condition 3: Validation Support (if OOS data available)
        if oos_data:
            validation_failure = self._check_validation(seg_a, seg_b, oos_data, practical_threshold)
            if validation_failure:
                return self._create_recommendation(
                    seg_a, seg_b, FailedCondition.VALIDATION,
                    event_rate_diff, practical_threshold,
                    validation_failure
                )
        
        # All conditions pass - segments should be kept separate
        return None
    
    def _check_reliability(
        self,
        seg_a: SegmentDetail,
        seg_b: SegmentDetail,
        min_segment_size: int
    ) -> Optional[str]:
        """
        Check Condition 1: Reliability.
        Both segments must meet minimum reliability thresholds.
        """
        snippets: List[str] = []
        for seg in (seg_a, seg_b):
            rec_ok = seg.record_count >= min_segment_size
            evt_ok = seg.event_count >= self.config.DEFAULT_MIN_EVENTS
            if rec_ok and evt_ok:
                continue
            name = (seg.segment_name or "?").strip() or "?"
            parts: List[str] = []
            if not rec_ok:
                parts.append(f"{int(seg.record_count)} rec")
            if not evt_ok:
                parts.append(f"{int(seg.event_count)} evt")
            snippets.append(f"{name}: {', '.join(parts)}")
        if not snippets:
            return None
        return (
            " · ".join(snippets)
            + f" — need ≥{int(min_segment_size)} rec & ≥{int(self.config.DEFAULT_MIN_EVENTS)} evt"
        )
    
    def _check_validation(
        self,
        seg_a: SegmentDetail,
        seg_b: SegmentDetail,
        oos_data: Dict[str, Any],
        practical_threshold: float
    ) -> Optional[str]:
        """
        Check Condition 3: Validation Support.
        The separation must hold on out-of-sample data.
        """
        oos_rates = oos_data.get("segment_event_rates", {})
        
        oos_rate_a = oos_rates.get(seg_a.segment_name)
        oos_rate_b = oos_rates.get(seg_b.segment_name)
        
        if oos_rate_a is None or oos_rate_b is None:
            return None  # Cannot validate, skip this condition
        
        oos_diff = abs(oos_rate_a - oos_rate_b)
        
        # Check if separation shrinks below threshold
        if oos_diff < practical_threshold:
            return f"OOS: {oos_diff:.2f}pp < {practical_threshold:.2f}pp (separation does not hold out-of-sample)."
        
        # Check for rank order reversal
        train_order = seg_a.event_rate < seg_b.event_rate
        oos_order = oos_rate_a < oos_rate_b
        
        if train_order != oos_order:
            return (
                f"OOS rank flip: {seg_a.segment_name} vs {seg_b.segment_name} "
                f"(train {seg_a.event_rate:.1f}% / {seg_b.event_rate:.1f}% → "
                f"OOS {oos_rate_a:.1f}% / {oos_rate_b:.1f}%)."
            )
        
        return None
    
    def _create_recommendation(
        self,
        seg_a: SegmentDetail,
        seg_b: SegmentDetail,
        failed_condition: FailedCondition,
        event_rate_diff: float,
        practical_threshold: float,
        explanation: str,
        is_bootstrap_borderline: bool = False,
    ) -> MergeRecommendation:
        """Create a merge recommendation for a failed segment pair."""
        merged_records = seg_a.record_count + seg_b.record_count
        merged_events = seg_a.event_count + seg_b.event_count
        merged_event_rate = (merged_events / merged_records * 100) if merged_records > 0 else 0
        
        iv_before = seg_a.iv_contribution + seg_b.iv_contribution
        
        return MergeRecommendation(
            segment_a=seg_a.segment_name,
            segment_b=seg_b.segment_name,
            failed_condition=failed_condition.value,
            is_bootstrap_borderline=is_bootstrap_borderline,
            event_rate_a=seg_a.event_rate,
            event_rate_b=seg_b.event_rate,
            event_rate_diff=round(event_rate_diff, 4),
            practical_threshold=round(practical_threshold, 4),
            merged_record_count=merged_records,
            merged_event_rate=round(merged_event_rate, 4),
            iv_before=round(iv_before, 4),
            iv_after=0.0,  # Would need full recalculation
            iv_change_pct=0.0,
            explanation=explanation
        )
    
    def evaluate_all_pairs(
        self,
        segments: List[SegmentDetail],
        overall_event_rate: float,
        min_segment_size: int,
        oos_data: Optional[Dict[str, Any]] = None
    ) -> List[MergeRecommendation]:
        """
        Evaluate all adjacent segment pairs (sorted by event rate).
        Returns list of merge recommendations for failing pairs.
        """
        recommendations = []
        
        # Sort segments by event rate
        sorted_segments = sorted(segments, key=lambda s: s.event_rate)
        
        # Check adjacent pairs
        for i in range(len(sorted_segments) - 1):
            seg_a = sorted_segments[i]
            seg_b = sorted_segments[i + 1]
            
            recommendation = self.evaluate_pair(
                seg_a, seg_b, overall_event_rate, min_segment_size, oos_data
            )
            
            if recommendation:
                recommendations.append(recommendation)
        
        return recommendations


# =============================================================================
# Validation Suite
# =============================================================================

class ValidationSuite:
    """
    Complete validation suite for segmentation schemes.
    Implements Section 8 of the plan.
    """
    
    def __init__(self, config: SegmentationConfig = None):
        self.config = config or SegmentationConfig()
        self.merge_framework = ThreeConditionMergeFramework(self.config)

    def _total_iv_with_breakdown(
        self,
        segments: List[SegmentDetail],
        df: Optional[pd.DataFrame] = None,
        target_var: Optional[str] = None,
    ) -> Tuple[float, List[Tuple[float, float]]]:
        """
        Compute total IV and per-segment (WoE, iv_contribution) from raw counts.

        Same logic as legacy ``_total_iv_from_segment_counts`` but returns the
        per-segment breakdown so we can align ``SegmentDetail`` with
        ``validation.total_iv`` (routes sometimes leave iv_contribution/woe at 0).
        """
        if not segments:
            return 0.0, []
        calc = WoEIVCalculator(self.config.WOE_EPSILON)
        stats = [
            {"events": int(s.event_count), "non_events": int(s.record_count) - int(s.event_count)}
            for s in segments
        ]
        # Pool totals from segment rows (same basis as the UI / chi-squared).
        # Summing the target column breaks for non-binary encodings (e.g. 0–100 %, multi-class),
        # which made validation.total_iv 0 while segment counts still supported a real IV.
        total_events = sum(int(s.event_count) for s in segments)
        total_non_events = sum(max(0, int(s.record_count) - int(s.event_count)) for s in segments)
        if total_events <= 0 or total_non_events <= 0:
            tiv = float(sum(s.iv_contribution for s in segments))
            breakdown = [(float(s.woe), float(s.iv_contribution)) for s in segments]
            return tiv, breakdown
        total_iv, results = calc.calculate_total_iv(stats, total_events, total_non_events)
        return float(total_iv), results

    def _total_iv_from_segment_counts(
        self,
        segments: List[SegmentDetail],
        df: Optional[pd.DataFrame] = None,
        target_var: Optional[str] = None,
    ) -> float:
        """Compute total IV only (see ``_total_iv_with_breakdown``)."""
        tiv, _ = self._total_iv_with_breakdown(segments, df=df, target_var=target_var)
        return tiv

    def run_validation(
        self,
        segments: List[SegmentDetail],
        df: pd.DataFrame,
        target_var: Optional[str],
        total_records: int,
        overall_event_rate: Optional[float],
        min_segment_size: int,
        oos_df: Optional[pd.DataFrame] = None,
        segment_column: Optional[str] = None,
        run_stability: bool = False,
        stability_bootstrap_runs: Optional[int] = None,
        oos_partition: str = "holdout"
    ) -> ValidationSuiteResult:
        """
        Run the complete validation suite.
        
        Args:
            segments: List of segment details
            df: Training dataframe
            target_var: Target variable name
            total_records: Total number of records
            overall_event_rate: Overall event rate (percentage)
            min_segment_size: Minimum segment size threshold
            oos_df: Out-of-sample dataframe (optional)
            segment_column: Name of segment column in dataframes
            run_stability: Whether to run bootstrap stability diagnostics
            stability_bootstrap_runs: Number of bootstrap runs (default: SegmentationConfig.BOOTSTRAP_RUNS)
            oos_partition: Name of partition used for OOS validation ("holdout" or "test")
        
        Returns:
            ValidationSuiteResult with all validation metrics
        """
        bootstrap_runs = (
            stability_bootstrap_runs
            if stability_bootstrap_runs is not None
            else self.config.BOOTSTRAP_RUNS
        )
        logger.info(f"Running validation suite on {len(segments)} segments")
        
        # Total IV from counts (not sum of rounded per-segment iv_contribution from routes).
        # Also refresh per-segment WoE / iv_contribution so API segments match validation.total_iv.
        total_iv, iv_breakdown = self._total_iv_with_breakdown(segments, df=df, target_var=target_var)
        if iv_breakdown and len(iv_breakdown) == len(segments):
            for i, seg in enumerate(segments):
                woe, ivc = iv_breakdown[i]
                segments[i] = seg.model_copy(
                    update={
                        "woe": round(float(woe), 4),
                        "iv_contribution": round(float(ivc), 4),
                    }
                )
        iv_category = self._categorize_iv(total_iv)
        
        # Chi-squared test
        chi_squared_p, chi_squared_significant = self._chi_squared_test(segments, target_var)
        
        # Cramer's V
        cramers_v = self._calculate_cramers_v(segments)
        cramers_v_meaningful = cramers_v > self.config.CRAMERS_V_THRESHOLD
        
        # Segment flags
        segment_flags = self._generate_segment_flags(segments, min_segment_size)
        
        # Per-segment OOS event rates for merge framework Condition 3 (Section 4.3 / 5.3)
        oos_merge_data: Optional[Dict[str, Any]] = None
        if oos_df is not None and segment_column and target_var and target_var in oos_df.columns:
            rates: Dict[str, float] = {}
            for seg in segments:
                oos_mask = oos_df[segment_column].astype(str) == str(seg.segment_name)
                oos_seg_df = oos_df[oos_mask]
                er = 0.0
                if len(oos_seg_df) > 0:
                    try:
                        er = float(_segment_mean_target_pct(oos_seg_df, target_var))
                    except Exception:
                        pass
                rates[str(seg.segment_name)] = er
            oos_merge_data = {"segment_event_rates": rates}
        
        # Merge recommendations (three-condition framework; Condition 3 uses OOS when available)
        merge_recommendations = self.merge_framework.evaluate_all_pairs(
            segments=segments,
            overall_event_rate=overall_event_rate or 10.0,
            min_segment_size=min_segment_size,
            oos_data=oos_merge_data
        )
        
        # Out-of-sample validation
        oos_validation = None
        if oos_df is not None and segment_column:
            oos_validation = self._validate_out_of_sample(
                segments, oos_df, target_var, segment_column, oos_partition
            )
        
        # Bootstrap stability diagnostics
        stability = None
        stability_rank_preservation = None
        if run_stability and segment_column and target_var:
            try:
                stability = self._run_stability_analysis(
                    df=df,
                    segments=segments,
                    target_var=target_var,
                    segment_column=segment_column,
                    bootstrap_runs=bootstrap_runs
                )
                stability_rank_preservation = stability.rank_order_preservation_rate
            except Exception as e:
                logger.warning(f"Stability analysis failed: {e}")

        # Plan §9.4: adjacent pairs that pass point practical separation but have overlapping
        # bootstrap event-rate bands → borderline merge hints (feed rule engine, not hard fails).
        if stability and stability.confidence_bands:
            try:
                borderline = self._bootstrap_practical_borderline_recommendations(
                    segments=segments,
                    confidence_bands=stability.confidence_bands,
                    overall_event_rate=overall_event_rate or 10.0,
                    existing=merge_recommendations,
                )
                merge_recommendations = list(merge_recommendations) + borderline
            except Exception as e:
                logger.warning(f"Bootstrap CI borderline pairing failed: {e}")

        # Plan §9.4: OOS validation failures with overlapping bootstrap event-rate bands → borderline
        # (soften hard merge flags before the rule engine aggregates).
        if stability and stability.confidence_bands:
            try:
                merge_recommendations = self._annotate_validation_merge_recs_ci_overlap(
                    merge_recommendations, stability.confidence_bands
                )
            except Exception as e:
                logger.warning(f"Bootstrap CI overlap annotation on merge recs failed: {e}")
        
        # Determine recommendation category (now considers stability)
        recommendation_category, recommendation_explanation = self._determine_recommendation(
            chi_squared_significant=chi_squared_significant,
            chi_squared_p=chi_squared_p,
            total_iv=total_iv,
            cramers_v=cramers_v,
            cramers_v_meaningful=cramers_v_meaningful,
            segments=segments,
            segment_flags=segment_flags,
            merge_recommendations=merge_recommendations,
            min_segment_size=min_segment_size,
            oos_validation=oos_validation,
            stability_rank_preservation=stability_rank_preservation,
            stability=stability,
        )
        
        return ValidationSuiteResult(
            # Do not round p-values: round(..., 6) collapses tiny p (e.g. ~1e-200) to 0.0.
            chi_squared_p=_json_safe_float(chi_squared_p, 1.0),
            chi_squared_significant=chi_squared_significant,
            # Keep full float for IV; UI used toFixed(3) — rounding here to 4 decimals hid small IV.
            total_iv=_json_safe_float(total_iv, 0.0),
            iv_category=iv_category,
            cramers_v=round(_json_safe_float(cramers_v, 0.0), 4),
            cramers_v_meaningful=cramers_v_meaningful,
            recommendation_category=recommendation_category,
            recommendation_explanation=recommendation_explanation,
            segment_flags=segment_flags,
            merge_recommendations=merge_recommendations,
            stability=stability,
            oos_validation=oos_validation
        )
    
    def _run_stability_analysis(
        self,
        df: pd.DataFrame,
        segments: List[SegmentDetail],
        target_var: str,
        segment_column: str,
        bootstrap_runs: int = 30
    ) -> BootstrapStabilityResult:
        """Run bootstrap stability analysis."""
        analyzer = _get_stability_analyzer()
        
        # Configure for the requested number of runs
        from app.services.segmentation_stability import StabilityConfig
        analyzer.config = StabilityConfig(bootstrap_runs=bootstrap_runs)
        
        return analyzer.analyze_with_segment_column(
            df=df,
            segments=segments,
            target_var=target_var,
            segment_column=segment_column
        )
    
    def _categorize_iv(self, total_iv: float) -> str:
        """Categorize total IV value."""
        if total_iv > self.config.IV_SUSPICIOUS:
            return "suspicious"
        elif total_iv >= self.config.IV_STRONG:
            return "strong"
        elif total_iv >= self.config.IV_MODERATE:
            return "moderate"
        else:
            return "weak"
    
    def _chi_squared_test(
        self,
        segments: List[SegmentDetail],
        target_var: Optional[str]
    ) -> Tuple[float, bool]:
        """
        Perform chi-squared test across segments.
        Tests if event rates are significantly different.
        """
        if len(segments) < 2:
            return 1.0, False
        
        try:
            # Build contingency table: events vs non-events per segment
            observed = np.array([
                [s.event_count, s.record_count - s.event_count]
                for s in segments
            ])
            
            # Ensure no zero rows/columns
            if observed.sum() == 0 or (observed.sum(axis=1) == 0).any():
                return 1.0, False
            
            chi2, p_value, dof, expected = stats.chi2_contingency(observed)
            chi2 = float(chi2)
            p_value = float(p_value)
            if not np.isfinite(chi2) or not np.isfinite(p_value):
                return 1.0, False
            if p_value == 0.0 or not np.isfinite(p_value):
                p_value = _chi2_survival_pvalue(chi2, int(dof))
            p_value = _json_safe_float(p_value, 1.0)
            return p_value, p_value < self.config.SIGNIFICANCE_LEVEL
            
        except Exception as e:
            logger.warning(f"Chi-squared test failed: {e}")
            return 1.0, False
    
    def _calculate_cramers_v(self, segments: List[SegmentDetail]) -> float:
        """
        Calculate Cramer's V for association strength.
        Independent of sample size.
        """
        if len(segments) < 2:
            return 0.0
        
        try:
            observed = np.array([
                [s.event_count, s.record_count - s.event_count]
                for s in segments
            ])
            
            if observed.sum() == 0:
                return 0.0
            
            chi2, _, _, _ = stats.chi2_contingency(observed)
            chi2 = float(chi2)
            if not np.isfinite(chi2):
                return 0.0
            n = observed.sum()
            min_dim = min(observed.shape) - 1
            
            if min_dim > 0 and n > 0:
                v = float(np.sqrt(chi2 / (n * min_dim)))
                return v if np.isfinite(v) else 0.0
            
            return 0.0
        
        except Exception as e:
            logger.warning(f"Cramer's V calculation failed: {e}")
            return 0.0
    
    def _generate_segment_flags(
        self,
        segments: List[SegmentDetail],
        min_segment_size: int
    ) -> List[SegmentFlag]:
        """Generate quality flags for each segment."""
        flags = []
        
        for seg in segments:
            # Low observations
            if seg.record_count < min_segment_size:
                flags.append(SegmentFlag(
                    segment_name=seg.segment_name,
                    flag_type="low_observations",
                    severity="amber",
                    message=f"'{seg.segment_name}' has {seg.record_count} records, "
                           f"below minimum threshold of {min_segment_size}"
                ))
            
            # Low events
            if seg.event_count < self.config.DEFAULT_MIN_EVENTS:
                flags.append(SegmentFlag(
                    segment_name=seg.segment_name,
                    flag_type="low_events",
                    severity="red",
                    message=f"'{seg.segment_name}' has only {seg.event_count} events. "
                           f"Model training may produce unstable coefficients."
                ))
            
            # Dominant segment
            if seg.pct_of_population > 60:
                flags.append(SegmentFlag(
                    segment_name=seg.segment_name,
                    flag_type="dominant",
                    severity="amber",
                    message=f"'{seg.segment_name}' dominates with {seg.pct_of_population:.1f}% "
                           f"of population. Segmentation may not be splitting meaningfully."
                ))
            
            # Tiny segment
            if seg.record_count < 100:
                flags.append(SegmentFlag(
                    segment_name=seg.segment_name,
                    flag_type="tiny",
                    severity="red",
                    message=f"'{seg.segment_name}' is too small ({seg.record_count} records) "
                           f"for any modeling purpose."
                ))
        
        return flags
    
    def _validate_out_of_sample(
        self,
        segments: List[SegmentDetail],
        oos_df: pd.DataFrame,
        target_var: str,
        segment_column: str,
        partition_used: str = "holdout"
    ) -> OutOfSampleValidation:
        """
        Validate segmentation on out-of-sample data.
        Checks event rate preservation, size proportion, and rank order.
        
        Per Section 11:
        - Event rate preservation: Flag if drift > 3pp (OOS_EVENT_RATE_DRIFT)
        - Size proportion preservation: Flag if drift > 5pp (OOS_SIZE_DRIFT)
        - Rank order preservation: Red flag if ordering changes
        - Statistical significance preservation: Flag if chi-squared p > 0.05 on OOS
        """
        
        segment_comparison = []
        oos_event_rates = {}
        max_event_rate_drift = 0.0
        max_size_drift = 0.0
        
        total_oos_records = len(oos_df)
        
        for seg in segments:
            oos_mask = oos_df[segment_column].astype(str) == str(seg.segment_name)
            oos_seg_df = oos_df[oos_mask]
            
            oos_count = len(oos_seg_df)
            oos_pct = (oos_count / total_oos_records * 100) if total_oos_records > 0 else 0
            
            oos_event_rate = 0.0
            if target_var in oos_df.columns and oos_count > 0:
                try:
                    oos_event_rate = float(_segment_mean_target_pct(oos_seg_df, target_var))
                except Exception:
                    pass
            
            oos_event_rates[seg.segment_name] = oos_event_rate
            
            # Calculate drifts
            event_rate_drift = abs(oos_event_rate - seg.event_rate)
            size_drift = abs(oos_pct - seg.pct_of_population)
            
            max_event_rate_drift = max(max_event_rate_drift, event_rate_drift)
            max_size_drift = max(max_size_drift, size_drift)
            
            segment_comparison.append({
                "segment_name": seg.segment_name,
                "train_records": seg.record_count,
                "train_pct": seg.pct_of_population,
                "train_event_rate": seg.event_rate,
                "oos_records": oos_count,
                "oos_pct": round(oos_pct, 2),
                "oos_event_rate": round(oos_event_rate, 4),
                "event_rate_drift": round(event_rate_drift, 4),
                "size_drift": round(size_drift, 4)
            })
        
        # Check rank order preservation
        train_order = [s.segment_name for s in sorted(segments, key=lambda x: x.event_rate)]
        oos_order = sorted(segments, key=lambda x: oos_event_rates.get(x.segment_name, 0))
        oos_order = [s.segment_name for s in oos_order]
        
        rank_order_preserved = train_order == oos_order
        
        # Chi-squared on OOS data
        chi_squared_oos_p = 1.0
        try:
            observed_oos = []
            for seg in segments:
                oos_mask = oos_df[segment_column].astype(str) == str(seg.segment_name)
                oos_seg_df = oos_df[oos_mask]
                if target_var in oos_df.columns:
                    events = int(oos_seg_df[target_var].sum())
                    non_events = len(oos_seg_df) - events
                    observed_oos.append([events, non_events])
            
            if observed_oos:
                observed_oos = np.array(observed_oos)
                if observed_oos.sum() > 0:
                    chi2, p_val, dof_oos, _ = stats.chi2_contingency(observed_oos)
                    chi2 = float(chi2)
                    p_val = float(p_val)
                    if not np.isfinite(chi2) or not np.isfinite(p_val):
                        chi_squared_oos_p = 1.0
                    else:
                        if p_val == 0.0 or not np.isfinite(p_val):
                            p_val = _chi2_survival_pvalue(chi2, int(dof_oos))
                        chi_squared_oos_p = _json_safe_float(p_val, 1.0)
        except Exception as e:
            logger.warning(f"OOS chi-squared failed: {e}")
        
        # Determine flags per Section 11 thresholds
        event_rate_drift_flagged = max_event_rate_drift > self.config.OOS_EVENT_RATE_DRIFT
        size_drift_flagged = max_size_drift > self.config.OOS_SIZE_DRIFT
        chi_squared_significant = chi_squared_oos_p < self.config.SIGNIFICANCE_LEVEL
        
        return OutOfSampleValidation(
            partition_used=partition_used,
            rank_order_preserved=rank_order_preserved,
            max_event_rate_drift=round(_json_safe_float(max_event_rate_drift, 0.0), 4),
            max_size_drift=round(_json_safe_float(max_size_drift, 0.0), 4),
            event_rate_drift_flagged=event_rate_drift_flagged,
            size_drift_flagged=size_drift_flagged,
            chi_squared_p=_json_safe_float(chi_squared_oos_p, 1.0),
            chi_squared_significant=chi_squared_significant,
            segment_comparison=segment_comparison
        )

    def _bootstrap_practical_borderline_recommendations(
        self,
        segments: List[SegmentDetail],
        confidence_bands: Dict[str, Dict[str, float]],
        overall_event_rate: float,
        existing: List[MergeRecommendation],
    ) -> List[MergeRecommendation]:
        """
        Plan §9.4: pairs that pass point practical separation but have overlapping
        bootstrap event-rate bands → borderline (is_bootstrap_borderline=True).
        """
        cfg = self.merge_framework.config
        practical_threshold = max(
            cfg.PRACTICAL_SEP_MIN_PP,
            float(overall_event_rate) * cfg.PRACTICAL_SEP_RATIO,
        )
        practical_val = FailedCondition.PRACTICAL_SEPARATION.value
        strict_practical_pairs = {
            tuple(sorted([r.segment_a, r.segment_b]))
            for r in existing
            if r.failed_condition == practical_val and not getattr(r, "is_bootstrap_borderline", False)
        }
        sorted_segs = sorted(segments, key=lambda s: s.event_rate)
        out: List[MergeRecommendation] = []
        for i in range(len(sorted_segs) - 1):
            lo, hi = sorted_segs[i], sorted_segs[i + 1]
            pk = tuple(sorted([lo.segment_name, hi.segment_name]))
            if pk in strict_practical_pairs:
                continue
            diff = abs(lo.event_rate - hi.event_rate)
            if diff < practical_threshold:
                continue
            band_lo = confidence_bands.get(lo.segment_name) or {}
            band_hi = confidence_bands.get(hi.segment_name) or {}
            upper_lo = band_lo.get("upper_95pct")
            lower_hi = band_hi.get("lower_5pct")
            if upper_lo is None or lower_hi is None:
                continue
            if upper_lo >= lower_hi:
                expl = (
                    f"Bootstrap CIs overlap ({lo.segment_name} ~{upper_lo:.1f}% vs {hi.segment_name} "
                    f"~{lower_hi:.1f}%): borderline separation (§9.4)."
                )
                out.append(
                    self.merge_framework._create_recommendation(
                        lo,
                        hi,
                        FailedCondition.PRACTICAL_SEPARATION,
                        diff,
                        practical_threshold,
                        expl,
                        is_bootstrap_borderline=True,
                    )
                )
        return out

    @staticmethod
    def _bootstrap_rate_interval_for_segment(
        confidence_bands: Dict[str, Dict[str, float]], segment_name: str
    ) -> Optional[Tuple[float, float]]:
        b = confidence_bands.get(str(segment_name))
        if not b:
            return None
        lo = b.get("lower_5pct")
        hi = b.get("upper_95pct")
        if lo is None or hi is None:
            return None
        lo_f, hi_f = float(lo), float(hi)
        return (min(lo_f, hi_f), max(lo_f, hi_f))

    @staticmethod
    def _closed_intervals_overlap(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
        la, ua = a
        lb, ub = b
        return max(la, lb) <= min(ua, ub)

    def _annotate_validation_merge_recs_ci_overlap(
        self,
        merge_recommendations: List[MergeRecommendation],
        confidence_bands: Dict[str, Dict[str, float]],
    ) -> List[MergeRecommendation]:
        """
        When Condition 3 (OOS validation) fails but bootstrap event-rate bands overlap,
        treat the pair as bootstrap borderline (plan §9.4) so the rule engine downgrades
        like other CI-overlap cases instead of counting a hard validation failure only.
        """
        val = FailedCondition.VALIDATION.value
        out: List[MergeRecommendation] = []
        for r in merge_recommendations:
            if r.failed_condition != val or getattr(r, "is_bootstrap_borderline", False):
                out.append(r)
                continue
            ia = self._bootstrap_rate_interval_for_segment(confidence_bands, r.segment_a)
            ib = self._bootstrap_rate_interval_for_segment(confidence_bands, r.segment_b)
            if ia is None or ib is None or not self._closed_intervals_overlap(ia, ib):
                out.append(r)
                continue
            out.append(
                r.model_copy(
                    update={
                        "is_bootstrap_borderline": True,
                        "explanation": (r.explanation + " Bootstrap CIs overlap (§9.4)."),
                    }
                )
            )
        return out
    
    def _determine_recommendation(
        self,
        chi_squared_significant: bool,
        chi_squared_p: float,
        total_iv: float,
        cramers_v: float,
        cramers_v_meaningful: bool,
        segments: List[SegmentDetail],
        segment_flags: List[SegmentFlag],
        merge_recommendations: List[MergeRecommendation],
        min_segment_size: int,
        oos_validation: Optional[OutOfSampleValidation],
        stability_rank_preservation: Optional[float] = None,
        stability: Optional[BootstrapStabilityResult] = None,
    ) -> Tuple[str, str]:
        """
        Determine recommendation category based on rule engine criteria.
        Returns (category, explanation).
        
        Per Section 8.6:
        - Strong: chi-squared p<0.05, IV>0.10, Cramer's V>0.10, all reliable, 
                  all pairs pass separation, OOS preserved, bootstrap >= 80%
        - Exploratory: chi-squared p<0.05, IV>0.05, some borderline pairs or 
                       60-80% bootstrap or no OOS data
        - Weak: chi-squared p>=0.05, IV<0.05, multiple merge failures, 
                bootstrap <60%, rank reversal on OOS
        """
        hard_recs = [r for r in merge_recommendations if not getattr(r, "is_bootstrap_borderline", False)]
        soft_recs = [r for r in merge_recommendations if getattr(r, "is_bootstrap_borderline", False)]
        stability_band_overlap = bool(stability and stability.confidence_bands_overlap)

        # Check all reliability conditions
        all_reliable = all(
            s.record_count >= min_segment_size and 
            s.event_count >= self.config.DEFAULT_MIN_EVENTS
            for s in segments
        )
        
        # Count critical flags
        red_flags = [f for f in segment_flags if f.severity == "red"]
        
        # Check OOS validation
        oos_valid = True
        if oos_validation:
            oos_valid = oos_validation.rank_order_preserved
        
        # Check bootstrap stability
        stability_strong = True
        stability_exploratory = True
        if stability_rank_preservation is not None:
            stability_strong = stability_rank_preservation >= self.config.RANK_ORDER_STRONG
            stability_exploratory = stability_rank_preservation >= self.config.RANK_ORDER_EXPLORATORY
        
        # Strong candidate criteria (per Section 8.6)
        if (chi_squared_significant and 
            total_iv >= self.config.IV_STRONG and 
            cramers_v_meaningful and 
            all_reliable and 
            len(hard_recs) == 0 and
            len(soft_recs) == 0 and
            not stability_band_overlap and
            len(red_flags) == 0 and
            oos_valid and
            stability_strong):
            
            stability_note = ""
            if stability_rank_preservation is not None:
                stability_note = f" Bootstrap rank preservation: {stability_rank_preservation:.0%}."
            
            return (
                "strong",
                f"Strong segmentation candidate. Chi-squared p={chi_squared_p:.4f} (significant), "
                f"Total IV={total_iv:.3f} (strong), Cramer's V={cramers_v:.3f} (meaningful). "
                f"All {len(segments)} segments meet reliability thresholds with no merge concerns.{stability_note} "
                f"Proceed to segment-specific model training with confidence."
            )
        
        # Exploratory candidate criteria
        elif (chi_squared_significant and 
              total_iv >= self.config.IV_MODERATE and
              len(hard_recs) <= 2 and
              len(soft_recs) <= 2 and
              stability_exploratory):
            
            merge_note = ""
            if hard_recs or soft_recs:
                pairs = [f"({r.segment_a}, {r.segment_b})" for r in (hard_recs + soft_recs)[:4]]
                merge_note = f" Flagged pairs: {', '.join(pairs)}."
            
            stability_note = ""
            if stability_rank_preservation is not None and stability_rank_preservation < self.config.RANK_ORDER_STRONG:
                stability_note = f" Bootstrap rank preservation: {stability_rank_preservation:.0%} (moderate)."
            if stability_band_overlap:
                stability_note += " Adjacent bootstrap event-rate bands overlap (plan §9.4)."
            
            return (
                "exploratory",
                f"Exploratory candidate. Chi-squared p={chi_squared_p:.4f}, "
                f"Total IV={total_iv:.3f}, Cramer's V={cramers_v:.3f}. "
                f"Segmentation shows promise but has areas of uncertainty.{merge_note}{stability_note} "
                f"Review flagged segments, consider merging borderline pairs, "
                f"and monitor closely in model training."
            )
        
        # Weak/unsupported
        else:
            issues = []
            if not chi_squared_significant:
                issues.append(f"chi-squared not significant (p={chi_squared_p:.4f})")
            if total_iv < self.config.IV_MODERATE:
                issues.append(f"low IV ({total_iv:.3f})")
            if len(hard_recs) > 2:
                issues.append(f"{len(hard_recs)} pairs fail separation checks")
            if len(soft_recs) > 2:
                issues.append(f"{len(soft_recs)} bootstrap borderline segment pairs (CI overlap)")
            if not oos_valid:
                issues.append("rank order reverses on OOS data")
            if stability_rank_preservation is not None and not stability_exploratory:
                issues.append(f"unstable bootstrap ({stability_rank_preservation:.0%} rank preservation)")
            
            return (
                "weak",
                f"Weak/unsupported segmentation. Issues: {'; '.join(issues)}. "
                f"Segmentation does not provide meaningful separation. "
                f"A global model is likely to perform comparably. "
                f"Consider adding to data for experimental purposes only."
            )


# =============================================================================
# WoE/IV Calculator
# =============================================================================

class WoEIVCalculator:
    """
    Calculate Weight of Evidence and Information Value.
    Uses epsilon smoothing to prevent division by zero.
    """
    
    def __init__(self, epsilon: float = SegmentationConfig.WOE_EPSILON):
        self.epsilon = epsilon
    
    def calculate(
        self,
        segment_events: int,
        segment_non_events: int,
        total_events: int,
        total_non_events: int
    ) -> Tuple[float, float]:
        """
        Calculate WoE and IV contribution for a segment.
        
        Returns:
            Tuple of (woe, iv_contribution)
        """
        if total_events == 0 or total_non_events == 0:
            return 0.0, 0.0
        
        # Distribution of events/non-events with epsilon smoothing
        dist_events = (segment_events + self.epsilon) / (total_events + self.epsilon)
        dist_non_events = (segment_non_events + self.epsilon) / (total_non_events + self.epsilon)
        
        # WoE calculation
        if dist_events > 0 and dist_non_events > 0:
            woe = np.log(dist_non_events / dist_events)
        else:
            woe = 0.0
        
        # IV contribution
        iv_contrib = (dist_non_events - dist_events) * woe
        
        return woe, iv_contrib
    
    def calculate_total_iv(
        self,
        segment_stats: List[Dict[str, int]],
        total_events: int,
        total_non_events: int
    ) -> Tuple[float, List[Tuple[float, float]]]:
        """
        Calculate total IV and individual segment WoE/IV.
        
        Args:
            segment_stats: List of dicts with 'events' and 'non_events' keys
            total_events: Total events across all segments
            total_non_events: Total non-events across all segments
        
        Returns:
            Tuple of (total_iv, list of (woe, iv_contribution) per segment)
        """
        results = []
        total_iv = 0.0
        
        for seg in segment_stats:
            woe, iv_contrib = self.calculate(
                seg.get("events", 0),
                seg.get("non_events", 0),
                total_events,
                total_non_events
            )
            results.append((woe, iv_contrib))
            total_iv += iv_contrib
        
        return total_iv, results


# =============================================================================
# Variable Relevance Matrix Calculator
# =============================================================================

class VariableRelevanceCalculator:
    """
    Calculates IV (Information Value) for each variable within each segment.
    Returns top 10 variables by IV per segment for the Variable Relevance Matrix.
    """
    
    def __init__(self, epsilon: float = 0.5):
        self.epsilon = epsilon
    
    def compute_variable_iv_per_segment(
        self,
        df: pd.DataFrame,
        segment_column: str,
        target_variable: str,
        candidate_variables: Optional[List[str]] = None,
        top_n: int = 10,
        max_segments: int = 20
    ) -> VariableRelevanceMatrix:
        """
        Compute IV for each variable within each segment.
        
        Args:
            df: DataFrame with segment assignments and target
            segment_column: Column containing segment assignments
            target_variable: Binary target variable (0/1)
            candidate_variables: Variables to analyze (defaults to all numeric)
            top_n: Number of top variables to return per segment
            max_segments: Maximum number of segments to process (for performance)
            
        Returns:
            VariableRelevanceMatrix with top variables by IV per segment
        """
        try:
            logger.info(f"Computing variable IV per segment | segment_col={segment_column} target={target_variable}")
            
            # Identify candidate variables - limit to 30 for performance
            if candidate_variables is None:
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                candidate_variables = [
                    col for col in numeric_cols 
                    if col not in [segment_column, target_variable]
                ]
            
            # Limit candidate variables for performance
            candidate_variables = candidate_variables[:30]
            
            if not candidate_variables:
                logger.warning("No candidate variables found for IV calculation")
                return VariableRelevanceMatrix(
                    variables=[],
                    overall_iv={},
                    segment_iv={}
                )
            
            # Get unique segments - limit for performance
            segments = df[segment_column].unique()
            if len(segments) > max_segments:
                logger.warning(f"Too many segments ({len(segments)}), limiting to top {max_segments} by size")
                # Get top segments by size
                segment_counts = df[segment_column].value_counts().head(max_segments)
                segments = segment_counts.index.tolist()
            
            logger.info(f"Processing {len(segments)} segments with {len(candidate_variables)} variables")
            
            # Calculate overall IV for each variable
            overall_iv = {}
            for var in candidate_variables:
                try:
                    iv = self._calculate_variable_iv(df, var, target_variable)
                    overall_iv[var] = round(_json_safe_float(iv, 0.0), 6)
                except Exception as e:
                    logger.debug(f"Could not calculate IV for {var}: {e}")
                    overall_iv[var] = 0.0
            
            # Calculate IV per segment for each variable
            segment_iv = {}
            for segment in segments:
                segment_name = f"Segment {segment}" if isinstance(segment, (int, float)) else str(segment)
                segment_df = df[df[segment_column] == segment]
                
                if len(segment_df) < 50:  # Skip very small segments
                    logger.debug(f"Skipping segment {segment_name} - too small ({len(segment_df)} records)")
                    continue
                
                segment_var_iv = {}
                for var in candidate_variables:
                    try:
                        iv = self._calculate_variable_iv(segment_df, var, target_variable)
                        segment_var_iv[var] = round(_json_safe_float(iv, 0.0), 6)
                    except Exception:
                        segment_var_iv[var] = 0.0
                
                # Sort and keep top N
                sorted_vars = sorted(segment_var_iv.items(), key=lambda x: x[1], reverse=True)
                segment_iv[segment_name] = dict(sorted_vars[:top_n])
            
            # Get top N overall variables
            sorted_overall = sorted(overall_iv.items(), key=lambda x: x[1], reverse=True)
            top_variables = [v[0] for v in sorted_overall[:top_n]]
            top_overall_iv = dict(sorted_overall[:top_n])
            
            logger.info(f"Variable relevance computed | {len(top_variables)} top vars, {len(segment_iv)} segments")
            
            return VariableRelevanceMatrix(
                variables=top_variables,
                overall_iv=top_overall_iv,
                segment_iv=segment_iv
            )
            
        except Exception as e:
            logger.error(f"Error computing variable IV per segment: {e}")
            return VariableRelevanceMatrix(
                variables=[],
                overall_iv={},
                segment_iv={}
            )
    
    def _calculate_variable_iv(
        self,
        df: pd.DataFrame,
        variable: str,
        target: str,
        n_bins: int = 10
    ) -> float:
        """
        Calculate IV for a single variable using binning.
        
        Uses equal-frequency binning for continuous variables.
        """
        try:
            if variable not in df.columns or target not in df.columns:
                return 0.0
            
            # Clean data
            valid_mask = df[variable].notna() & df[target].notna()
            valid_df = df.loc[valid_mask, [variable, target]].copy()
            
            if len(valid_df) < 50:
                return 0.0
            
            total_events = valid_df[target].sum()
            total_non_events = len(valid_df) - total_events
            
            if total_events == 0 or total_non_events == 0:
                return 0.0
            
            # Create bins based on variable type
            if valid_df[variable].nunique() <= n_bins:
                # Categorical-like: use actual values
                bins = valid_df[variable]
            else:
                # Continuous: use quantile binning
                try:
                    bins = pd.qcut(valid_df[variable], q=n_bins, duplicates='drop')
                except ValueError:
                    # Fallback to cut if qcut fails
                    bins = pd.cut(valid_df[variable], bins=n_bins, duplicates='drop')
            
            # Calculate IV for each bin
            total_iv = 0.0
            for bin_val in bins.unique():
                if pd.isna(bin_val):
                    continue
                    
                bin_mask = bins == bin_val
                bin_events = valid_df.loc[bin_mask, target].sum()
                bin_non_events = bin_mask.sum() - bin_events
                
                # Distribution of events/non-events (with smoothing)
                dist_events = (bin_events + self.epsilon) / (total_events + self.epsilon)
                dist_non_events = (bin_non_events + self.epsilon) / (total_non_events + self.epsilon)
                
                # WoE and IV contribution
                if dist_events > 0:
                    woe = np.log(dist_non_events / dist_events)
                    iv_contrib = (dist_non_events - dist_events) * woe
                    total_iv += iv_contrib
            
            out = max(0.0, float(total_iv))
            return _json_safe_float(out, 0.0)
            
        except Exception as e:
            logger.debug(f"IV calculation failed for {variable}: {e}")
            return 0.0


# =============================================================================
# Factory Functions
# =============================================================================

def create_variable_relevance_calculator(epsilon: float = 0.5) -> VariableRelevanceCalculator:
    """Create a VariableRelevanceCalculator instance."""
    return VariableRelevanceCalculator(epsilon)


def create_validation_suite(config: SegmentationConfig = None) -> ValidationSuite:
    """Create a ValidationSuite instance."""
    return ValidationSuite(config)


def create_merge_framework(config: SegmentationConfig = None) -> ThreeConditionMergeFramework:
    """Create a ThreeConditionMergeFramework instance."""
    return ThreeConditionMergeFramework(config)


def create_woe_calculator(epsilon: float = SegmentationConfig.WOE_EPSILON) -> WoEIVCalculator:
    """Create a WoEIVCalculator instance."""
    return WoEIVCalculator(epsilon)


# =============================================================================
# LLM Narrative Generator for Segmentation
# =============================================================================

class SegmentationNarrativeGenerator:
    """
    Generates LLM-powered narratives and explanations for segmentation results.
    Provides human-readable insights for:
    - Merge recommendations
    - Validation summaries
    - Variable relevance commentary
    """
    
    def __init__(self):
        self._llm_service = None
    
    def _get_llm_service(self):
        """Lazy load LLM service to avoid circular imports."""
        if self._llm_service is None:
            try:
                from app.services.llm_service import llm_service
                self._llm_service = llm_service
            except Exception as e:
                logger.warning(f"Failed to load LLM service: {e}")
                self._llm_service = None
        return self._llm_service
    
    def generate_merge_explanation(
        self,
        segment_a: Dict[str, Any],
        segment_b: Dict[str, Any],
        merge_reason: str,
        combined_stats: Dict[str, Any]
    ) -> str:
        """
        Generate an LLM explanation for why two segments should be merged.
        
        Args:
            segment_a: First segment details (name, event_rate, size, etc.)
            segment_b: Second segment details
            merge_reason: Technical reason (e.g., "overlapping_ci", "similar_event_rate")
            combined_stats: What the merged segment would look like
            
        Returns:
            Human-readable explanation string
        """
        llm = self._get_llm_service()
        if not llm:
            return self._fallback_merge_explanation(segment_a, segment_b, merge_reason)
        
        try:
            prompt = f"""You are a senior data scientist explaining segmentation results to a business analyst.

Two customer segments have been identified as candidates for merging:

Segment A: "{segment_a.get('name', 'Segment A')}"
- Records: {segment_a.get('record_count', 'N/A'):,}
- Event Rate: {segment_a.get('event_rate', 0) * 100:.2f}%
- IV Contribution: {segment_a.get('iv_contribution', 0):.4f}

Segment B: "{segment_b.get('name', 'Segment B')}"
- Records: {segment_b.get('record_count', 'N/A'):,}
- Event Rate: {segment_b.get('event_rate', 0) * 100:.2f}%
- IV Contribution: {segment_b.get('iv_contribution', 0):.4f}

Technical Merge Reason: {merge_reason}

If Merged:
- Combined Records: {combined_stats.get('combined_records', 'N/A'):,}
- Combined Event Rate: {combined_stats.get('combined_event_rate', 0) * 100:.2f}%
- IV Change: {combined_stats.get('iv_change', 0):+.4f}

Write a concise 2-3 sentence explanation for why merging these segments makes sense from a business and statistical perspective. Focus on practical implications for risk segmentation or customer treatment strategies."""

            response = llm.get_response_route(prompt, [])
            return response.strip() if response else self._fallback_merge_explanation(segment_a, segment_b, merge_reason)
            
        except Exception as e:
            logger.warning(f"LLM merge explanation failed: {e}")
            return self._fallback_merge_explanation(segment_a, segment_b, merge_reason)
    
    def _fallback_merge_explanation(
        self,
        segment_a: Dict[str, Any],
        segment_b: Dict[str, Any],
        merge_reason: str
    ) -> str:
        """Generate a template-based fallback explanation when LLM is unavailable."""
        rate_diff = abs((segment_a.get('event_rate', 0) - segment_b.get('event_rate', 0)) * 100)
        
        if "overlapping" in merge_reason.lower() or "ci" in merge_reason.lower():
            return f"These segments have overlapping confidence intervals (event rate difference: {rate_diff:.1f}pp), suggesting they may not be statistically distinguishable. Merging would create a larger, more stable segment with better statistical power."
        elif "similar" in merge_reason.lower() or "event_rate" in merge_reason.lower():
            return f"The event rates are very similar ({rate_diff:.1f}pp difference), indicating comparable risk profiles. A combined segment would simplify the model while maintaining predictive accuracy."
        else:
            return f"Based on the validation analysis, these segments share similar characteristics. Merging would reduce model complexity without significant loss of predictive power."
    
    def generate_recommendation_narrative(
        self,
        validation_result: Dict[str, Any],
        num_segments: int,
        total_iv: float,
        recommendation_category: str
    ) -> str:
        """
        Generate an LLM narrative summarizing the segmentation validation results.
        
        Args:
            validation_result: Full validation suite result
            num_segments: Number of segments in the scheme
            total_iv: Total Information Value
            recommendation_category: "strong", "acceptable", "weak", etc.
            
        Returns:
            Human-readable summary narrative
        """
        llm = self._get_llm_service()
        if not llm:
            return self._fallback_recommendation_narrative(num_segments, total_iv, recommendation_category)
        
        try:
            chi_squared_p = validation_result.get('chi_squared_p', 'N/A')
            cramers_v = validation_result.get('cramers_v', 'N/A')
            oos = validation_result.get('oos_validation')
            if oos is None:
                oos = {}
            rank_order = oos.get('rank_order_preserved', 'N/A') if isinstance(oos, dict) else 'N/A'
            segment_flags = validation_result.get('segment_flags') or []
            
            prompt = f"""You are a senior data scientist summarizing segmentation quality for a credit risk team.

Segmentation Scheme Summary:
- Number of Segments: {num_segments}
- Total IV: {total_iv:.4f} ({recommendation_category})
- Chi-squared p-value: {chi_squared_p if isinstance(chi_squared_p, str) else f'{chi_squared_p:.4f}'}
- Cramer's V: {cramers_v if isinstance(cramers_v, str) else f'{cramers_v:.3f}'}
- Out-of-sample rank order preserved: {rank_order}
- Segments with warnings: {len([f for f in segment_flags if isinstance(f, dict) and f.get('flag_type') in ['small_segment', 'low_events']])}

IV Interpretation:
- < 0.02: Not useful
- 0.02-0.10: Weak
- 0.10-0.30: Medium
- 0.30-0.50: Strong
- > 0.50: Suspicious (possible overfitting)

Output rules (strict):
- Reply with ONLY a bullet list: 5 to 8 lines, each starting with "- " (hyphen + space).
- Each bullet must be one short sentence (aim under 100 characters; absolute max ~140).
- No opening paragraph, no closing paragraph, no numbered lists, no markdown headers or bold.
- Cover, in order when relevant: (1) IV / discriminatory strength, (2) chi-squared vs practical separation (Cramer's V), (3) OOS rank-order stability, (4) segment warnings if any, (5) production use recommendation, (6) one concrete next step.
- Be direct; avoid filler words like "Additionally" or "It is important to note"."""

            response = llm.get_response_route(prompt, [])
            return response.strip() if response else self._fallback_recommendation_narrative(num_segments, total_iv, recommendation_category)
            
        except Exception as e:
            logger.warning(f"LLM recommendation narrative failed: {e}")
            return self._fallback_recommendation_narrative(num_segments, total_iv, recommendation_category)
    
    def _fallback_recommendation_narrative(
        self,
        num_segments: int,
        total_iv: float,
        recommendation_category: str
    ) -> str:
        """Generate a template-based fallback narrative when LLM is unavailable (bullet list)."""
        if recommendation_category == "strong":
            return (
                f"- {num_segments} segments; total IV {total_iv:.4f} (strong discriminatory signal).\n"
                "- Chi-squared likely significant; confirm Cramer's V for practical effect size.\n"
                "- Check out-of-sample rank order and segment flags before sign-off.\n"
                "- Suitable for production with standard monitoring and periodic refresh."
            )
        elif recommendation_category == "acceptable":
            return (
                f"- {num_segments} segments; total IV {total_iv:.4f} (acceptable / moderate signal).\n"
                "- Segments are somewhat distinguishable; watch stability on holdout or test data.\n"
                "- Consider merging near-duplicate segments to simplify the scheme.\n"
                "- Production use OK with enhanced monitoring and merge rules documented."
            )
        elif recommendation_category == "weak":
            return (
                f"- {num_segments} segments; total IV {total_iv:.4f} (weak signal vs typical IV bands).\n"
                "- Limited practical separation; validate whether segments add value over a single rate.\n"
                "- Try different drivers, depth, or minimum segment size before relying on this split.\n"
                "- Not recommended for production without a redesign and stronger validation."
            )
        else:
            return (
                f"- {num_segments} segments; total IV {total_iv:.4f} (category: {recommendation_category}).\n"
                "- Review validation metrics, OOS behaviour, and business interpretation jointly.\n"
                "- Address any segment warnings before treating the scheme as decision-ready.\n"
                "- Treat as exploratory until stability and lift are confirmed on holdout data."
            )
    
    def generate_variable_commentary(
        self,
        variable_relevance: Dict[str, Any],
        segment_name: str,
        top_variables: List[Tuple[str, float]]
    ) -> str:
        """
        Generate an LLM commentary on variable importance within a segment.
        
        Args:
            variable_relevance: Full variable relevance matrix
            segment_name: Name of the segment being analyzed
            top_variables: List of (variable_name, iv_value) tuples
            
        Returns:
            Human-readable commentary on what drives this segment
        """
        llm = self._get_llm_service()
        if not llm:
            return self._fallback_variable_commentary(segment_name, top_variables)
        
        try:
            vars_str = "\n".join([f"- {var}: IV = {iv:.4f}" for var, iv in top_variables[:5]])
            overall_top = list(variable_relevance.get('overall_iv', {}).items())[:3]
            overall_str = ", ".join([f"{v[0]} (IV: {v[1]:.4f})" for v in overall_top])
            
            prompt = f"""You are a senior data scientist explaining variable importance to a business stakeholder.

Segment: "{segment_name}"

Top Predictive Variables in This Segment:
{vars_str}

Overall Top Variables (across all segments): {overall_str}

Write a concise 2-3 sentence commentary explaining:
1. What variables most strongly differentiate this segment
2. Whether this segment has different key drivers compared to overall
3. Any actionable insight for treatment strategy

Keep it business-focused and avoid technical jargon."""

            response = llm.get_response_route(prompt, [])
            return response.strip() if response else self._fallback_variable_commentary(segment_name, top_variables)
            
        except Exception as e:
            logger.warning(f"LLM variable commentary failed: {e}")
            return self._fallback_variable_commentary(segment_name, top_variables)
    
    def _fallback_variable_commentary(
        self,
        segment_name: str,
        top_variables: List[Tuple[str, float]]
    ) -> str:
        """Generate a template-based fallback commentary when LLM is unavailable."""
        if not top_variables:
            return f"No significant predictive variables identified for {segment_name}."
        
        top_var, top_iv = top_variables[0]
        strength = "strongly" if top_iv >= 0.1 else "moderately" if top_iv >= 0.05 else "weakly"
        
        return f"This segment is {strength} characterized by {top_var} (IV: {top_iv:.4f}). " + \
               f"Other key differentiators include {', '.join([v[0] for v in top_variables[1:3]])}." if len(top_variables) > 1 else ""


def create_narrative_generator() -> SegmentationNarrativeGenerator:
    """Create a SegmentationNarrativeGenerator instance."""
    return SegmentationNarrativeGenerator()


# =============================================================================
# Module-level instances for convenience
# =============================================================================

validation_suite = ValidationSuite()
merge_framework = ThreeConditionMergeFramework()
woe_calculator = WoEIVCalculator()
variable_relevance_calculator = VariableRelevanceCalculator()
narrative_generator = SegmentationNarrativeGenerator()

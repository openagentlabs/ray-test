"""
Segmentation Stability Diagnostics Module

Implements Bootstrap Stability Diagnostics for the Segmentation Agent
as specified in Section 9 of the implementation plan.

Purpose: Without model training, stability is the most credible evidence
that a segmentation is real and not an artifact of one particular sample.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import time

from app.core.logging_config import get_logger
from app.models.schemas import (
    SegmentDetail, BootstrapStabilityResult
)

logger = get_logger(__name__)

# Decimals for comparing segment event-rate ranks across bootstrap draws (float noise).
_STABILITY_RATE_RANK_DECIMALS = 4


def _stability_rate_rank_key(rate: float, label: str) -> Tuple[float, str]:
    return (round(float(rate), _STABILITY_RATE_RANK_DECIMALS), str(label))


def _segment_mean_target_pct(seg_df: pd.DataFrame, target_var: str) -> float:
    """Mean target on a segment slice; binary 0/1 → percent scale like SegmentDetail.event_rate."""
    if seg_df is None or len(seg_df) == 0 or target_var not in seg_df.columns:
        return 0.0
    col = pd.to_numeric(seg_df[target_var], errors="coerce")
    if col.notna().sum() == 0:
        return 0.0
    m = float(col.mean())
    vmax = float(np.nanmax(col.to_numpy(dtype=float)))
    if vmax <= 1.0 + 1e-9:
        return m * 100.0
    return m


def _build_segment_column_label_map(
    df: pd.DataFrame,
    segment_column: str,
    target_var: str,
    segments: List[SegmentDetail],
) -> Dict[str, str]:
    """
    Map raw ``df[segment_column]`` string forms to canonical ``SegmentDetail.segment_name``.

    Tree assignments often stringify as ``0``, ``1``, ``1.0`` while ``segment_name`` is
    ``Segment 1`` — masks never matched and rank stability stayed 0%.
    """
    out: Dict[str, str] = {}
    if segment_column not in df.columns or not segments:
        return out
    raw_series = df[segment_column]
    for s in segments:
        out[str(s.segment_name).strip()] = s.segment_name
    try:
        keys = pd.Series(raw_series, dtype=object).dropna().astype(str).str.strip().unique().tolist()
    except Exception:
        keys = []
    for v in keys:
        if v in out or v == "" or v.lower() == "nan":
            continue
        mask = pd.Series(raw_series, dtype=object).astype(str).str.strip() == v
        if mask.sum() == 0:
            continue
        rate = _segment_mean_target_pct(df.loc[mask], target_var)
        best_name: Optional[str] = None
        best_err = float("inf")
        for seg in segments:
            try:
                err = abs(float(seg.event_rate) - rate)
            except Exception:
                err = float("inf")
            if err < best_err:
                best_err = err
                best_name = seg.segment_name
        if best_name is not None and best_err < 25.0:
            out[v] = best_name
    alias: Dict[str, str] = {}
    for k, v in out.items():
        try:
            fk = float(k)
        except (TypeError, ValueError):
            continue
        if fk == int(fk):
            alias[str(int(fk))] = v
        g = f"{fk:g}"
        if g != k:
            alias[g] = v
    out.update(alias)
    return out


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class StabilityConfig:
    """Configuration for bootstrap stability diagnostics."""
    bootstrap_runs: int = 30
    confidence_lower_pct: float = 5.0
    confidence_upper_pct: float = 95.0
    rank_order_strong_threshold: float = 0.80
    rank_order_exploratory_threshold: float = 0.60
    max_workers: int = 4
    random_seed: Optional[int] = None
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300  # 5 minutes


# =============================================================================
# Bootstrap Stability Analyzer
# =============================================================================

class BootstrapStabilityAnalyzer:
    """
    Performs bootstrap stability diagnostics on segmentation schemes.
    
    Method (from plan Section 9.2):
    - Draw 20-30 bootstrap samples from training data (same size, with replacement)
    - For each sample, apply finalized segment rules and compute event rates
    - The rules do NOT change across bootstrap runs - only records in each resample change
    
    Metrics Computed:
    1. Event Rate Confidence Bands: 5th and 95th percentile per segment
    2. Rank Order Preservation Rate: How often segment ordering by event rate stays identical
    """
    
    def __init__(self, config: StabilityConfig = None):
        self.config = config or StabilityConfig()
        self._cache: Dict[str, Tuple[BootstrapStabilityResult, float]] = {}
    
    def analyze(
        self,
        df: pd.DataFrame,
        segments: List[SegmentDetail],
        target_var: str,
        segment_assignment_func: Callable[[pd.DataFrame], pd.Series],
        cache_key: Optional[str] = None
    ) -> BootstrapStabilityResult:
        """
        Run bootstrap stability analysis on a segmentation scheme.
        
        Args:
            df: Training dataframe
            segments: List of segment details (defines the original ordering)
            target_var: Target variable name
            segment_assignment_func: Function that assigns segment labels to rows
                                    Takes DataFrame, returns Series of segment names
            cache_key: Optional cache key for result caching
        
        Returns:
            BootstrapStabilityResult with confidence bands and rank preservation
        """
        # Check cache
        if cache_key and self.config.cache_enabled:
            cached = self._get_cached(cache_key)
            if cached:
                logger.info(f"Returning cached stability result for key: {cache_key[:20]}...")
                return cached
        
        logger.info(f"Running bootstrap stability analysis: {self.config.bootstrap_runs} runs")
        start_time = time.time()
        
        n_samples = len(df)
        original_order = [
            s.segment_name
            for s in sorted(
                segments,
                key=lambda x: _stability_rate_rank_key(x.event_rate, x.segment_name),
            )
        ]
        
        # Store event rates from each bootstrap run
        bootstrap_event_rates: Dict[str, List[float]] = {s.segment_name: [] for s in segments}
        rank_order_matches = 0
        
        # Set random seed if specified
        rng = np.random.RandomState(self.config.random_seed)
        
        # Run bootstrap samples
        for run_idx in range(self.config.bootstrap_runs):
            # Sample with replacement
            bootstrap_indices = rng.choice(n_samples, size=n_samples, replace=True)
            bootstrap_df = df.iloc[bootstrap_indices].reset_index(drop=True)
            
            # Apply segment rules to get assignments
            try:
                segment_labels = segment_assignment_func(bootstrap_df)
            except Exception as e:
                logger.warning(f"Bootstrap run {run_idx} failed: {e}")
                continue
            
            # Compute event rates per segment
            run_event_rates = {}
            labels_cmp = (
                segment_labels.astype(str).str.strip()
                if hasattr(segment_labels, "astype")
                else pd.Series(segment_labels).astype(str).str.strip()
            )
            for seg in segments:
                seg_mask = labels_cmp == str(seg.segment_name).strip()
                seg_df = bootstrap_df[seg_mask]
                
                if len(seg_df) > 0 and target_var in bootstrap_df.columns:
                    try:
                        event_rate = float(_segment_mean_target_pct(seg_df, target_var))
                    except Exception:
                        event_rate = 0.0
                else:
                    event_rate = 0.0
                
                run_event_rates[seg.segment_name] = event_rate
                bootstrap_event_rates[seg.segment_name].append(event_rate)
            
            # Check rank order preservation (rate + label tie-break; rounded rates)
            run_order = sorted(
                run_event_rates.keys(),
                key=lambda x: _stability_rate_rank_key(run_event_rates[x], x),
            )
            if run_order == original_order:
                rank_order_matches += 1
        
        # Compute confidence bands
        confidence_bands = {}
        for seg_name, rates in bootstrap_event_rates.items():
            if rates:
                lower = float(np.percentile(rates, self.config.confidence_lower_pct))
                upper = float(np.percentile(rates, self.config.confidence_upper_pct))
                confidence_bands[seg_name] = {
                    "lower_5pct": round(lower, 4),
                    "upper_95pct": round(upper, 4),
                    "median": round(float(np.median(rates)), 4),
                    "std": round(float(np.std(rates)), 4)
                }
            else:
                confidence_bands[seg_name] = {
                    "lower_5pct": 0.0,
                    "upper_95pct": 0.0,
                    "median": 0.0,
                    "std": 0.0
                }
        
        # Check for overlapping confidence bands between adjacent segments
        bands_overlap = self._check_confidence_band_overlap(segments, confidence_bands)
        
        # Calculate rank order preservation rate
        successful_runs = sum(len(rates) > 0 for rates in bootstrap_event_rates.values())
        if successful_runs > 0:
            # Use the minimum number of successful runs across all segments
            min_runs = min(len(rates) for rates in bootstrap_event_rates.values() if rates)
            rank_preservation_rate = rank_order_matches / min_runs if min_runs > 0 else 0.0
        else:
            rank_preservation_rate = 0.0
        
        elapsed = time.time() - start_time
        logger.info(f"Bootstrap analysis completed in {elapsed:.2f}s. "
                   f"Rank preservation: {rank_preservation_rate:.1%}")
        
        result = BootstrapStabilityResult(
            bootstrap_runs=self.config.bootstrap_runs,
            rank_order_preservation_rate=round(rank_preservation_rate, 4),
            confidence_bands=confidence_bands,
            confidence_bands_overlap=bands_overlap
        )
        
        # Cache result
        if cache_key and self.config.cache_enabled:
            self._set_cached(cache_key, result)
        
        return result
    
    def analyze_with_segment_column(
        self,
        df: pd.DataFrame,
        segments: List[SegmentDetail],
        target_var: str,
        segment_column: str,
        cache_key: Optional[str] = None
    ) -> BootstrapStabilityResult:
        """
        Convenience method when segments are defined by a column in the dataframe.
        
        This is the common case for C1 (pre-existing identifier) mode.
        """
        label_map = _build_segment_column_label_map(
            df, segment_column, target_var, segments
        )

        def assignment_func(bootstrap_df: pd.DataFrame) -> pd.Series:
            # For pre-existing identifiers, the segment column values are preserved
            # We need to map bootstrap indices back to original segment assignments
            raw = bootstrap_df[segment_column].astype(str).str.strip()
            if label_map:
                return raw.map(lambda x: label_map.get(x, x))
            return raw

        return self.analyze(
            df=df,
            segments=segments,
            target_var=target_var,
            segment_assignment_func=assignment_func,
            cache_key=cache_key
        )
    
    def analyze_with_rules(
        self,
        df: pd.DataFrame,
        segments: List[SegmentDetail],
        target_var: str,
        segment_rules: Dict[str, Callable[[pd.DataFrame], pd.Series]],
        cache_key: Optional[str] = None
    ) -> BootstrapStabilityResult:
        """
        Analyze stability when segments are defined by rule functions.
        
        Args:
            segment_rules: Dict mapping segment_name to a function that returns
                          a boolean mask for that segment
        """
        def assignment_func(bootstrap_df: pd.DataFrame) -> pd.Series:
            labels = pd.Series(["Unassigned"] * len(bootstrap_df), index=bootstrap_df.index)
            
            for seg_name, rule_func in segment_rules.items():
                try:
                    mask = rule_func(bootstrap_df)
                    labels[mask] = seg_name
                except Exception as e:
                    logger.warning(f"Rule application failed for {seg_name}: {e}")
            
            return labels
        
        return self.analyze(
            df=df,
            segments=segments,
            target_var=target_var,
            segment_assignment_func=assignment_func,
            cache_key=cache_key
        )
    
    def _check_confidence_band_overlap(
        self,
        segments: List[SegmentDetail],
        confidence_bands: Dict[str, Dict[str, float]]
    ) -> bool:
        """
        Check if adjacent segments (by event rate) have overlapping confidence bands.
        
        Overlapping bands suggest segments may not be genuinely separable.
        """
        sorted_segments = sorted(
            segments,
            key=lambda s: _stability_rate_rank_key(s.event_rate, s.segment_name),
        )
        
        for i in range(len(sorted_segments) - 1):
            seg_a = sorted_segments[i]
            seg_b = sorted_segments[i + 1]
            
            band_a = confidence_bands.get(seg_a.segment_name, {})
            band_b = confidence_bands.get(seg_b.segment_name, {})
            
            upper_a = band_a.get("upper_95pct", 0)
            lower_b = band_b.get("lower_5pct", 0)
            
            # Check if band_a's upper overlaps with band_b's lower
            if upper_a >= lower_b:
                logger.info(f"Confidence bands overlap: {seg_a.segment_name} "
                           f"(upper: {upper_a:.2f}) vs {seg_b.segment_name} "
                           f"(lower: {lower_b:.2f})")
                return True
        
        return False
    
    def _get_cached(self, cache_key: str) -> Optional[BootstrapStabilityResult]:
        """Get cached result if still valid."""
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self.config.cache_ttl_seconds:
                return result
            else:
                del self._cache[cache_key]
        return None
    
    def _set_cached(self, cache_key: str, result: BootstrapStabilityResult):
        """Cache a result with timestamp."""
        self._cache[cache_key] = (result, time.time())
    
    def clear_cache(self):
        """Clear the result cache."""
        self._cache.clear()
    
    def get_stability_assessment(self, result: BootstrapStabilityResult) -> str:
        """
        Get a stability assessment category based on the result.
        
        Returns: "stable", "moderately_stable", or "unstable"
        """
        rate = result.rank_order_preservation_rate
        
        if rate >= self.config.rank_order_strong_threshold:
            return "stable"
        elif rate >= self.config.rank_order_exploratory_threshold:
            return "moderately_stable"
        else:
            return "unstable"
    
    def generate_stability_narrative(self, result: BootstrapStabilityResult) -> str:
        """
        Generate a plain-language narrative about the stability results.
        """
        rate = result.rank_order_preservation_rate
        runs = result.bootstrap_runs
        assessment = self.get_stability_assessment(result)
        
        if assessment == "stable":
            narrative = (
                f"Segmentation is stable. Rank order was preserved in {rate:.0%} "
                f"of {runs} bootstrap runs, exceeding the 80% threshold for strong stability. "
                f"The segment structure is likely to hold on new data."
            )
        elif assessment == "moderately_stable":
            narrative = (
                f"Segmentation shows moderate stability. Rank order was preserved in {rate:.0%} "
                f"of {runs} bootstrap runs, between 60% and 80%. "
                f"Some segments may swap positions occasionally. Monitor closely."
            )
        else:
            narrative = (
                f"Segmentation is unstable. Rank order was preserved in only {rate:.0%} "
                f"of {runs} bootstrap runs, below the 60% threshold. "
                f"Segments frequently change relative positions, suggesting the structure "
                f"may not hold on new data. Consider merging borderline segments."
            )
        
        if result.confidence_bands_overlap:
            narrative += (
                " Additionally, confidence bands overlap between adjacent segments, "
                "indicating they may not be genuinely separable."
            )
        
        return narrative


# =============================================================================
# Parallel Bootstrap Analyzer (for large datasets)
# =============================================================================

class ParallelBootstrapAnalyzer(BootstrapStabilityAnalyzer):
    """
    Parallel version of bootstrap analyzer for better performance on large datasets.
    """
    
    def analyze(
        self,
        df: pd.DataFrame,
        segments: List[SegmentDetail],
        target_var: str,
        segment_assignment_func: Callable[[pd.DataFrame], pd.Series],
        cache_key: Optional[str] = None
    ) -> BootstrapStabilityResult:
        """Run bootstrap analysis using parallel execution."""
        
        # Check cache
        if cache_key and self.config.cache_enabled:
            cached = self._get_cached(cache_key)
            if cached:
                return cached
        
        logger.info(f"Running parallel bootstrap stability analysis: "
                   f"{self.config.bootstrap_runs} runs with {self.config.max_workers} workers")
        start_time = time.time()
        
        n_samples = len(df)
        original_order = [
            s.segment_name
            for s in sorted(
                segments,
                key=lambda x: _stability_rate_rank_key(x.event_rate, x.segment_name),
            )
        ]
        segment_names = [s.segment_name for s in segments]
        
        # Prepare bootstrap indices
        rng = np.random.RandomState(self.config.random_seed)
        all_indices = [
            rng.choice(n_samples, size=n_samples, replace=True)
            for _ in range(self.config.bootstrap_runs)
        ]
        
        # Run bootstrap samples in parallel
        def process_bootstrap(run_idx: int, indices: np.ndarray) -> Dict[str, Any]:
            bootstrap_df = df.iloc[indices].reset_index(drop=True)
            
            try:
                segment_labels = segment_assignment_func(bootstrap_df)
            except Exception as e:
                return {"success": False, "error": str(e)}
            
            event_rates = {}
            labels_cmp = (
                segment_labels.astype(str).str.strip()
                if hasattr(segment_labels, "astype")
                else pd.Series(segment_labels).astype(str).str.strip()
            )
            for seg_name in segment_names:
                seg_mask = labels_cmp == str(seg_name).strip()
                seg_df = bootstrap_df[seg_mask]
                
                if len(seg_df) > 0 and target_var in bootstrap_df.columns:
                    try:
                        event_rates[seg_name] = float(_segment_mean_target_pct(seg_df, target_var))
                    except Exception:
                        event_rates[seg_name] = 0.0
                else:
                    event_rates[seg_name] = 0.0
            
            run_order = sorted(
                event_rates.keys(),
                key=lambda x: _stability_rate_rank_key(event_rates[x], x),
            )
            order_preserved = run_order == original_order
            
            return {
                "success": True,
                "event_rates": event_rates,
                "order_preserved": order_preserved
            }
        
        results = []
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(process_bootstrap, i, indices): i
                for i, indices in enumerate(all_indices)
            }
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Bootstrap worker failed: {e}")
        
        # Aggregate results
        bootstrap_event_rates: Dict[str, List[float]] = {name: [] for name in segment_names}
        rank_order_matches = 0
        successful_runs = 0
        
        for res in results:
            if res.get("success"):
                successful_runs += 1
                if res.get("order_preserved"):
                    rank_order_matches += 1
                for seg_name, rate in res.get("event_rates", {}).items():
                    bootstrap_event_rates[seg_name].append(rate)
        
        # Compute confidence bands
        confidence_bands = {}
        for seg_name, rates in bootstrap_event_rates.items():
            if rates:
                confidence_bands[seg_name] = {
                    "lower_5pct": round(float(np.percentile(rates, 5)), 4),
                    "upper_95pct": round(float(np.percentile(rates, 95)), 4),
                    "median": round(float(np.median(rates)), 4),
                    "std": round(float(np.std(rates)), 4)
                }
            else:
                confidence_bands[seg_name] = {
                    "lower_5pct": 0.0, "upper_95pct": 0.0, "median": 0.0, "std": 0.0
                }
        
        bands_overlap = self._check_confidence_band_overlap(segments, confidence_bands)
        rank_preservation_rate = rank_order_matches / successful_runs if successful_runs > 0 else 0.0
        
        elapsed = time.time() - start_time
        logger.info(f"Parallel bootstrap analysis completed in {elapsed:.2f}s. "
                   f"Rank preservation: {rank_preservation_rate:.1%}")
        
        result = BootstrapStabilityResult(
            bootstrap_runs=self.config.bootstrap_runs,
            rank_order_preservation_rate=round(rank_preservation_rate, 4),
            confidence_bands=confidence_bands,
            confidence_bands_overlap=bands_overlap
        )
        
        if cache_key and self.config.cache_enabled:
            self._set_cached(cache_key, result)
        
        return result


# =============================================================================
# Background Stability Runner
# =============================================================================

class BackgroundStabilityRunner:
    """
    Manages background execution of stability diagnostics.
    
    Per plan Section 9.5: Results run automatically in background after every
    segmentation run. Results are cached and recomputed only when segmentation changes.
    """
    
    def __init__(self, analyzer: BootstrapStabilityAnalyzer = None):
        self.analyzer = analyzer or BootstrapStabilityAnalyzer()
        self._pending_jobs: Dict[str, Dict[str, Any]] = {}
        self._completed_results: Dict[str, BootstrapStabilityResult] = {}
    
    def submit(
        self,
        job_id: str,
        df: pd.DataFrame,
        segments: List[SegmentDetail],
        target_var: str,
        segment_column: str
    ):
        """Submit a background stability analysis job."""
        self._pending_jobs[job_id] = {
            "status": "pending",
            "submitted_at": time.time()
        }
        
        # In a real implementation, this would use a task queue like Celery
        # For now, we run synchronously but mark as background-capable
        try:
            result = self.analyzer.analyze_with_segment_column(
                df=df,
                segments=segments,
                target_var=target_var,
                segment_column=segment_column,
                cache_key=job_id
            )
            self._completed_results[job_id] = result
            self._pending_jobs[job_id]["status"] = "completed"
        except Exception as e:
            self._pending_jobs[job_id]["status"] = "failed"
            self._pending_jobs[job_id]["error"] = str(e)
            logger.error(f"Background stability job {job_id} failed: {e}")
    
    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of a background job."""
        if job_id in self._pending_jobs:
            status = self._pending_jobs[job_id].copy()
            if status.get("status") == "completed" and job_id in self._completed_results:
                status["result"] = self._completed_results[job_id]
            return status
        return {"status": "not_found"}
    
    def get_result(self, job_id: str) -> Optional[BootstrapStabilityResult]:
        """Get the result of a completed job."""
        return self._completed_results.get(job_id)


# =============================================================================
# Utility Functions
# =============================================================================

def generate_cache_key(
    dataset_id: str,
    segment_names: List[str],
    segment_rules: Optional[List[str]] = None
) -> str:
    """Generate a unique cache key for stability results."""
    key_data = {
        "dataset_id": dataset_id,
        "segments": sorted(segment_names),
        "rules": sorted(segment_rules) if segment_rules else []
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


def create_analyzer(
    bootstrap_runs: int = 30,
    parallel: bool = False,
    max_workers: int = 4
) -> BootstrapStabilityAnalyzer:
    """Factory function to create appropriate analyzer."""
    config = StabilityConfig(
        bootstrap_runs=bootstrap_runs,
        max_workers=max_workers
    )
    
    if parallel:
        return ParallelBootstrapAnalyzer(config)
    return BootstrapStabilityAnalyzer(config)


# =============================================================================
# Module-level instances
# =============================================================================

stability_analyzer = BootstrapStabilityAnalyzer()
parallel_stability_analyzer = ParallelBootstrapAnalyzer()
background_runner = BackgroundStabilityRunner()

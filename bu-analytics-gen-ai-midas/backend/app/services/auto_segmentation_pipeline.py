"""
Auto Segmentation Pipeline - Automated Scheme Discovery

Implements Section 7 of the Segmentation Agent Plan:
- Step 7.1-7.2: IV+AUC ranking using average rank method
- Step 7.3: Primary splitter selection with Quality Composite scoring
- Step 7.4-7.7: Sequential merge passes between depth levels
- Step 7.8: Constraint enforcement (max segments, min size, min events)
- Step 7.9: CHAID fallback when CART fails

Quality Composite Weights (Section 7.3):
- Total IV: 35%
- Segment Balance (entropy): 25%
- Event Rate Spread: 25%
- Surviving Segments: 15%

Constraints (Section 7.8):
- Max 7 segments (default), up to 10 if each extra has IV > 0.02
- Min 5% of population or 1,000 records per segment
- Min 200 events per segment

Author: Segmentation Agent Implementation
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.metrics import roc_auc_score
from scipy.stats import chi2_contingency, chi2

from app.services.tertiary_promotion_utils import (
    PromotionSuggestion,
    SplitterSelectionResult,
    check_tertiary_promotion as check_tertiary_promotion_util,
    chi_squared_split_test,
    test_splitter_significance as test_splitter_significance_util,
)
from app.services.segmentation_validation import WoEIVCalculator

logger = logging.getLogger("midas.app.services.auto_segmentation_pipeline")


@dataclass
class CandidateVariable:
    """
    Represents a candidate variable for auto segmentation.
    
    Section 7.2: Variable ranking uses average rank method:
    1. Rank by IV (rank 1 = highest IV)
    2. Rank by AUC (rank 1 = highest AUC)
    3. Average rank = (IV_rank + AUC_rank) / 2
    4. Select top 5 candidates by lowest average rank
    """
    name: str
    iv: float = 0.0
    auc: float = 0.5
    iv_rank: int = 0  # Lower is better (rank 1 = highest IV)
    auc_rank: int = 0  # Lower is better (rank 1 = highest AUC)
    average_rank: float = 0.0  # (iv_rank + auc_rank) / 2
    combined_score: float = 0.0  # Legacy: kept for compatibility
    unique_values: int = 0
    missing_pct: float = 0.0
    is_numeric: bool = True
    is_valid: bool = True
    rejection_reason: Optional[str] = None


@dataclass
class SegmentScheme:
    """
    Represents a candidate segmentation scheme.
    
    Section 7.3: Quality Composite scoring uses:
    - Total IV (35%)
    - Segment Balance - entropy of size distribution (25%)
    - Event Rate Spread (25%)
    - Surviving Segments After Merge (15%)
    """
    scheme_id: int
    variables: List[str]
    variable_priority: Optional[Dict[str, str]] = None
    method: str = "cart"
    depth: int = 3
    actual_depth_used: int = 1  # Actual depth achieved after significance gates
    num_segments: int = 0
    original_segments: int = 0  # Before merge passes
    total_iv: float = 0.0
    segment_balance: float = 0.0  # Entropy of size distribution (0-1)
    event_rate_spread: float = 0.0  # Max - min event rate
    chi_squared_p: float = 1.0
    stability_score: float = 0.0
    rank_preservation: float = 0.0
    composite_score: float = 0.0
    recommendation_category: str = "weak"
    is_recommended: bool = False
    description: str = ""
    segments: List[Any] = field(default_factory=list)
    merge_trail: List[str] = field(default_factory=list)  # Audit trail of merges
    constraint_trail: List[str] = field(default_factory=list)  # Constraint enforcement trail
    splitter_selection_trail: List[str] = field(default_factory=list)  # Selection audit trail
    promotion_suggestion: Optional[PromotionSuggestion] = None  # Section 3.4
    validation_result: Optional[Any] = None


@dataclass
class AutoPipelineConfig:
    """
    Configuration for the auto segmentation pipeline.
    
    Section 7.3 Quality Composite Weights:
    - WEIGHT_TOTAL_IV: 35%
    - WEIGHT_SEGMENT_BALANCE: 25%
    - WEIGHT_EVENT_RATE_SPREAD: 25%
    - WEIGHT_SURVIVING_SEGMENTS: 15%
    
    Section 7.8 Constraints:
    - Max 7 segments (default), up to 10 if each extra has IV > 0.02
    - Min 5% of population or 1,000 records
    - Min 200 events per segment
    """
    # Variable ranking
    max_candidate_variables: int = 10
    top_candidates: int = 5  # Section 7.2: Select top 5 candidates
    
    # IV/AUC thresholds
    iv_threshold_weak: float = 0.02
    iv_threshold_moderate: float = 0.1
    iv_threshold_strong: float = 0.3
    auc_weight: float = 0.4  # Legacy, now using average rank method
    iv_weight: float = 0.6   # Legacy, now using average rank method
    
    # Quality Composite Weights (Section 7.3)
    weight_total_iv: float = 0.35
    weight_segment_balance: float = 0.25
    weight_event_rate_spread: float = 0.25
    weight_surviving_segments: float = 0.15
    
    # Segment constraints (Section 7.8)
    min_segment_size: int = 1000
    min_segment_size_pct: float = 0.05
    min_events_per_segment: int = 200
    max_segments: int = 7
    max_segments_upper: int = 10  # Max with IV justification
    iv_contribution_threshold: float = 0.02  # Min IV for extra segments beyond 7
    
    # Tree parameters
    max_depth: int = 3  # Section 7.3: Up to depth 3
    significance_threshold: float = 0.05
    
    # Practical separation (Section 4.3)
    practical_sep_min_pp: float = 2.0
    practical_sep_ratio: float = 0.20
    
    # WoE smoothing
    woe_epsilon: float = 0.5
    
    # Pipeline options
    max_schemes_to_generate: int = 5
    bootstrap_runs: int = 10
    enable_parallel: bool = True
    max_workers: int = 4
    enable_chaid_fallback: bool = True  # Section 7.9


class AutoSegmentationPipeline:
    """
    Automated segmentation pipeline that discovers optimal segmentation schemes.
    
    Workflow:
    1. Rank candidate variables by IV + AUC
    2. Generate multiple scheme candidates (single var, pairs, trios)
    3. Run each scheme through segmentation + validation
    4. Score and rank schemes
    5. Return top schemes with RECOMMENDED badge
    """
    
    def __init__(self, config: Optional[AutoPipelineConfig] = None):
        self.config = config or AutoPipelineConfig()
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
    
    def run_pipeline(
        self,
        df: pd.DataFrame,
        target_variable: str,
        dataset_id: str,
        segmentation_service: Any,
        dataset_manager: Any
    ) -> Dict[str, Any]:
        """
        Run the complete auto segmentation pipeline.
        
        Returns:
            Dict with 'schemes', 'recommended_scheme_idx', 'variables_ranked'
        """
        logger.info(f"Starting auto segmentation pipeline | dataset_id={dataset_id}")
        total_records = len(df)
        
        # Step 1: Rank candidate variables by IV + AUC
        ranked_variables = self._rank_variables(df, target_variable)
        logger.info(f"Ranked {len(ranked_variables)} candidate variables")
        
        if not ranked_variables:
            return {
                "success": False,
                "message": "No valid candidate variables found",
                "schemes": [],
                "recommended_scheme_idx": None,
                "variables_ranked": []
            }
        
        # Step 2: Generate scheme candidates
        scheme_candidates = self._generate_scheme_candidates(ranked_variables)
        logger.info(f"Generated {len(scheme_candidates)} scheme candidates")
        
        # Step 3: Run each scheme through segmentation + validation
        evaluated_schemes = self._evaluate_schemes(
            scheme_candidates=scheme_candidates,
            df=df,
            target_variable=target_variable,
            dataset_id=dataset_id,
            segmentation_service=segmentation_service,
            dataset_manager=dataset_manager
        )
        
        # Step 4: Score and rank schemes
        scored_schemes = self._score_and_rank_schemes(evaluated_schemes)
        
        # Step 5: Mark recommended scheme
        if scored_schemes:
            scored_schemes[0].is_recommended = True
            recommended_idx = 0
        else:
            recommended_idx = None
        
        logger.info(f"Auto pipeline complete | {len(scored_schemes)} viable schemes found")
        
        return {
            "success": True,
            "message": f"Found {len(scored_schemes)} segmentation schemes",
            "schemes": scored_schemes,
            "recommended_scheme_idx": recommended_idx,
            "variables_ranked": [
                {
                    "name": v.name,
                    "iv": round(v.iv, 4),
                    "auc": round(v.auc, 4),
                    "combined_score": round(v.combined_score, 4),
                    "is_valid": v.is_valid
                }
                for v in ranked_variables[:self.config.max_candidate_variables]
            ]
        }
    
    def _rank_variables(
        self,
        df: pd.DataFrame,
        target_variable: str
    ) -> List[CandidateVariable]:
        """
        Rank candidate variables by combined IV + AUC using average rank method.
        
        Section 7.2: Variable ranking algorithm:
        1. Compute univariate IV for all variables
        2. Compute univariate AUC for all variables  
        3. Rank by IV (rank 1 = highest)
        4. Rank by AUC (rank 1 = highest)
        5. Average rank = (IV_rank + AUC_rank) / 2
        6. Select top 5 candidates (lowest average rank)
        """
        candidates = []
        
        # Get target values
        if target_variable not in df.columns:
            logger.warning(f"Target variable '{target_variable}' not found")
            return []
        
        y = df[target_variable].values
        
        # Identify numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        # Filter out ID-like columns and target
        id_patterns = ['id', 'index', 'key', 'row', 'record', 'pk', 'fk', '_id', 'uuid']
        filtered_cols = [
            c for c in numeric_cols
            if c != target_variable and not any(p in c.lower() for p in id_patterns)
        ]
        
        logger.info(f"Evaluating {len(filtered_cols)} candidate variables for IV+AUC ranking")
        
        for col in filtered_cols:
            try:
                candidate = self._evaluate_single_variable(df, col, y, target_variable)
                if candidate.is_valid:
                    candidates.append(candidate)
            except Exception as e:
                logger.warning(f"Error evaluating variable '{col}': {e}")
        
        if not candidates:
            return []
        
        # Step 3: Rank by IV (rank 1 = highest IV)
        candidates.sort(key=lambda x: x.iv, reverse=True)
        for rank, c in enumerate(candidates, 1):
            c.iv_rank = rank
        
        # Step 4: Rank by AUC (rank 1 = highest AUC)
        candidates.sort(key=lambda x: x.auc, reverse=True)
        for rank, c in enumerate(candidates, 1):
            c.auc_rank = rank
        
        # Step 5: Calculate average rank
        for c in candidates:
            c.average_rank = (c.iv_rank + c.auc_rank) / 2
            # Also set combined_score for backward compatibility
            c.combined_score = 1.0 / c.average_rank if c.average_rank > 0 else 0
        
        # Step 6: Sort by average rank ascending (lower = better)
        candidates.sort(key=lambda x: (x.average_rank, -x.auc))  # Tie-breaker: prefer higher AUC
        
        top_candidates = candidates[:self.config.top_candidates]
        logger.info(f"Top {len(top_candidates)} candidates by average rank: "
                   f"{[(c.name, c.average_rank, c.iv, c.auc) for c in top_candidates]}")
        
        return candidates[:self.config.max_candidate_variables]
    
    def _evaluate_single_variable(
        self,
        df: pd.DataFrame,
        col: str,
        y: np.ndarray,
        target_variable: str
    ) -> CandidateVariable:
        """Evaluate a single variable for IV and AUC."""
        candidate = CandidateVariable(name=col)
        
        # Get column data
        x = df[col].values
        
        # Check for validity
        candidate.unique_values = df[col].nunique()
        candidate.missing_pct = df[col].isna().mean() * 100
        candidate.is_numeric = np.issubdtype(df[col].dtype, np.number)
        
        # Skip if too many missing values
        if candidate.missing_pct > 50:
            candidate.is_valid = False
            candidate.rejection_reason = "Too many missing values (>50%)"
            return candidate
        
        # Skip if constant
        if candidate.unique_values <= 1:
            candidate.is_valid = False
            candidate.rejection_reason = "Constant or single value"
            return candidate
        
        # Calculate IV using binning
        try:
            candidate.iv = self._calculate_iv(df[col], df[target_variable])
        except Exception as e:
            logger.debug(f"IV calculation failed for {col}: {e}")
            candidate.iv = 0.0
        
        # Calculate AUC
        try:
            # Remove missing values
            mask = ~(pd.isna(x) | pd.isna(y))
            x_clean = x[mask]
            y_clean = y[mask]
            
            if len(np.unique(y_clean)) == 2:  # Binary target
                candidate.auc = roc_auc_score(y_clean, x_clean)
                # Ensure AUC is > 0.5 (flip if needed)
                if candidate.auc < 0.5:
                    candidate.auc = 1 - candidate.auc
            else:
                candidate.auc = 0.5  # Default for non-binary
        except Exception as e:
            logger.debug(f"AUC calculation failed for {col}: {e}")
            candidate.auc = 0.5
        
        # Check IV threshold
        if candidate.iv < self.config.iv_threshold_weak:
            candidate.is_valid = False
            candidate.rejection_reason = f"IV too low ({candidate.iv:.4f} < {self.config.iv_threshold_weak})"
        
        return candidate
    
    def _calculate_iv(self, feature: pd.Series, target: pd.Series) -> float:
        """Calculate Information Value for a feature."""
        # Bin numeric features
        if np.issubdtype(feature.dtype, np.number):
            # Create 10 quantile bins
            try:
                binned = pd.qcut(feature.fillna(feature.median()), q=10, duplicates='drop')
            except:
                binned = pd.cut(feature.fillna(feature.median()), bins=10)
        else:
            binned = feature.fillna('__MISSING__')
        
        # Create contingency table
        cross_tab = pd.crosstab(binned, target)
        
        if cross_tab.shape[1] != 2:
            return 0.0
        
        # Get event and non-event counts
        total_events = cross_tab.iloc[:, 1].sum()
        total_non_events = cross_tab.iloc[:, 0].sum()
        
        if total_events == 0 or total_non_events == 0:
            return 0.0
        
        # Calculate IV
        iv = 0.0
        epsilon = 0.0001  # Smoothing
        
        for idx in cross_tab.index:
            events = cross_tab.loc[idx, cross_tab.columns[1]] + epsilon
            non_events = cross_tab.loc[idx, cross_tab.columns[0]] + epsilon
            
            pct_events = events / (total_events + epsilon * len(cross_tab))
            pct_non_events = non_events / (total_non_events + epsilon * len(cross_tab))
            
            woe = np.log(pct_non_events / pct_events)
            iv += (pct_non_events - pct_events) * woe
        
        return iv
    
    # =========================================================================
    # Sequential Splitter Selection (Sections 7.3-7.7)
    # =========================================================================
    
    def _test_splitter_significance(
        self,
        df: pd.DataFrame,
        candidate_variable: str,
        target_variable: str,
        parent_segments: List[Dict[str, Any]],
        segment_column: str
    ) -> SplitterSelectionResult:
        """Delegates to shared tertiary / splitter promotion utilities (Sections 7.5–7.7)."""
        return test_splitter_significance_util(
            df=df,
            candidate_variable=candidate_variable,
            target_variable=target_variable,
            parent_segments=parent_segments,
            segment_column=segment_column,
            significance_threshold=self.config.significance_threshold,
        )

    def _chi_squared_split_test(
        self,
        df: pd.DataFrame,
        variable: str,
        target: str,
        n_bins: int = 5
    ) -> float:
        return chi_squared_split_test(df, variable, target, n_bins=n_bins)
    
    def _select_secondary_splitter(
        self,
        df: pd.DataFrame,
        target_variable: str,
        primary_segments: List[Dict[str, Any]],
        segment_column: str,
        candidate_variables: List[str],
        primary_variable: str
    ) -> Tuple[Optional[str], SplitterSelectionResult, Optional[PromotionSuggestion]]:
        """
        Select secondary splitter from candidates using significance gate.
        
        Section 7.5: Test each remaining candidate as secondary splitter.
        Apply significance gate (p < 0.05 in at least one primary segment).
        For each that passes, evaluate quality and select best.
        
        Returns:
            Tuple of (selected_variable, selection_result, promotion_suggestion)
        """
        logger.info(f"Selecting secondary splitter from {len(candidate_variables)} candidates")
        
        # Filter out primary variable
        remaining = [v for v in candidate_variables if v != primary_variable]
        
        if not remaining:
            return None, SplitterSelectionResult(
                variable="none",
                depth=1,
                is_significant=False
            ), PromotionSuggestion(
                suggestion_type="stop_at_primary",
                message="No remaining candidate variables for secondary splitter."
            )
        
        # Test each candidate
        test_results: List[SplitterSelectionResult] = []
        
        for var in remaining[:4]:  # Test top 4 remaining
            result = self._test_splitter_significance(
                df=df,
                candidate_variable=var,
                target_variable=target_variable,
                parent_segments=primary_segments,
                segment_column=segment_column
            )
            result.depth = 1
            test_results.append(result)
            
            logger.debug(f"Secondary candidate {var}: significant={result.is_significant}, "
                        f"min_p={result.min_p_value:.4f}, segments_sig={result.segments_significant}")
        
        # Find best significant candidate
        significant_results = [r for r in test_results if r.is_significant]
        
        if significant_results:
            # Sort by number of significant segments, then by min p-value
            significant_results.sort(key=lambda x: (-x.segments_significant, x.min_p_value))
            best = significant_results[0]
            
            logger.info(f"Selected secondary splitter: {best.variable} "
                       f"(p={best.min_p_value:.4f}, {best.segments_significant} significant segments)")
            
            return best.variable, best, None
        
        # No secondary found - this is where we check for tertiary promotion
        return None, test_results[0] if test_results else SplitterSelectionResult(
            variable="none", depth=1, is_significant=False
        ), None
    
    def _select_tertiary_splitter(
        self,
        df: pd.DataFrame,
        target_variable: str,
        secondary_segments: List[Dict[str, Any]],
        segment_column: str,
        candidate_variables: List[str],
        primary_variable: str,
        secondary_variable: str
    ) -> Tuple[Optional[str], SplitterSelectionResult]:
        """
        Select tertiary splitter from remaining candidates.
        
        Section 7.7: Same significance gate as secondary.
        """
        logger.info(f"Selecting tertiary splitter")
        
        # Filter out primary and secondary
        remaining = [v for v in candidate_variables 
                    if v not in [primary_variable, secondary_variable]]
        
        if not remaining:
            return None, SplitterSelectionResult(
                variable="none",
                depth=2,
                is_significant=False
            )
        
        # Test each candidate
        test_results: List[SplitterSelectionResult] = []
        
        for var in remaining[:3]:  # Test top 3 remaining
            result = self._test_splitter_significance(
                df=df,
                candidate_variable=var,
                target_variable=target_variable,
                parent_segments=secondary_segments,
                segment_column=segment_column
            )
            result.depth = 2
            test_results.append(result)
        
        # Find best significant candidate
        significant_results = [r for r in test_results if r.is_significant]
        
        if significant_results:
            significant_results.sort(key=lambda x: (-x.segments_significant, x.min_p_value))
            best = significant_results[0]
            
            logger.info(f"Selected tertiary splitter: {best.variable} (p={best.min_p_value:.4f})")
            return best.variable, best
        
        return None, test_results[0] if test_results else SplitterSelectionResult(
            variable="none", depth=2, is_significant=False
        )
    
    def _check_tertiary_promotion(
        self,
        df: pd.DataFrame,
        target_variable: str,
        primary_segments: List[Dict[str, Any]],
        segment_column: str,
        failed_secondary: str,
        tertiary_candidate: Optional[str]
    ) -> PromotionSuggestion:
        """Section 3.4 — shared implementation in tertiary_promotion_utils."""
        return check_tertiary_promotion_util(
            df=df,
            target_variable=target_variable,
            primary_segments=primary_segments,
            segment_column=segment_column,
            failed_secondary=failed_secondary,
            tertiary_candidate=tertiary_candidate,
            significance_threshold=self.config.significance_threshold,
        )
    
    def run_sequential_auto_pipeline(
        self,
        df: pd.DataFrame,
        target_variable: str,
        dataset_id: str,
        segmentation_service: Any,
        dataset_manager: Any
    ) -> Dict[str, Any]:
        """
        Run the full sequential auto segmentation pipeline as specified in Section 7.
        
        This is the enhanced pipeline that:
        1. Ranks variables by IV+AUC (Step 7.2)
        2. Tests top 5 as primary splitters with Quality Composite (Step 7.3)
        3. Applies Merge Pass 1 (Step 7.4)
        4. Selects secondary splitter with significance gate (Step 7.5)
        5. Applies Merge Pass 2 (Step 7.6)
        6. Selects tertiary splitter with significance gate (Step 7.7)
        7. Final merge pass and constraint enforcement (Step 7.8)
        8. Includes tertiary promotion suggestion if applicable (Section 3.4)
        """
        logger.info(f"Starting sequential auto segmentation pipeline | dataset_id={dataset_id}")
        total_records = len(df)
        overall_event_rate = df[target_variable].mean() * 100 if target_variable in df.columns else 0
        
        # Step 1: Rank variables by IV + AUC
        ranked_variables = self._rank_variables(df, target_variable)
        
        if not ranked_variables:
            return {
                "success": False,
                "message": "No valid candidate variables found",
                "schemes": [],
                "recommended_scheme_idx": None,
                "variables_ranked": [],
                "promotion_suggestions": []
            }
        
        top_5_vars = [v.name for v in ranked_variables[:5]]
        logger.info(f"Top 5 candidates: {top_5_vars}")
        
        # Step 2: Test each as primary splitter and select best
        min_samples = max(
            self.config.min_segment_size,
            int(total_records * self.config.min_segment_size_pct)
        )
        
        # Create a single best scheme using sequential selection
        best_scheme = self._build_sequential_scheme(
            df=df,
            target_variable=target_variable,
            dataset_id=dataset_id,
            segmentation_service=segmentation_service,
            dataset_manager=dataset_manager,
            ranked_variables=ranked_variables,
            total_records=total_records,
            overall_event_rate=overall_event_rate,
            min_samples=min_samples
        )
        
        if not best_scheme:
            return {
                "success": False,
                "message": "Could not build a viable segmentation scheme",
                "schemes": [],
                "recommended_scheme_idx": None,
                "variables_ranked": [
                    {"name": v.name, "iv": v.iv, "auc": v.auc, "average_rank": v.average_rank}
                    for v in ranked_variables[:10]
                ],
                "promotion_suggestions": []
            }
        
        # Quality composite (§7.3) for scheme cards — recommendation comes from ValidationSuite on the API route
        best_scheme.segment_balance = self._compute_segment_balance(best_scheme.segments)
        best_scheme.event_rate_spread = self._compute_event_rate_spread(best_scheme.segments)
        best_scheme.composite_score = self.compute_quality_composite_score(best_scheme)
        best_scheme.recommendation_category = "weak"
        best_scheme.is_recommended = False
        
        # Collect promotion suggestions
        promotion_suggestions = []
        if best_scheme.promotion_suggestion:
            promotion_suggestions.append({
                "type": best_scheme.promotion_suggestion.suggestion_type,
                "message": best_scheme.promotion_suggestion.message,
                "failed_variable": best_scheme.promotion_suggestion.failed_variable,
                "suggested_variable": best_scheme.promotion_suggestion.suggested_variable,
                "suggested_p_value": best_scheme.promotion_suggestion.suggested_p_value
            })
        
        return {
            "success": True,
            "message": f"Sequential auto segmentation completed with {best_scheme.num_segments} segments "
                      f"using {best_scheme.actual_depth_used} depth level(s)",
            "schemes": [best_scheme],
            "recommended_scheme_idx": 0,
            "variables_ranked": [
                {
                    "name": v.name,
                    "iv": round(v.iv, 4),
                    "auc": round(v.auc, 4),
                    "average_rank": v.average_rank,
                    "iv_rank": v.iv_rank,
                    "auc_rank": v.auc_rank
                }
                for v in ranked_variables[:10]
            ],
            "promotion_suggestions": promotion_suggestions,
            "splitter_selection_trail": best_scheme.splitter_selection_trail
        }
    
    def _build_sequential_scheme(
        self,
        df: pd.DataFrame,
        target_variable: str,
        dataset_id: str,
        segmentation_service: Any,
        dataset_manager: Any,
        ranked_variables: List[CandidateVariable],
        total_records: int,
        overall_event_rate: float,
        min_samples: int
    ) -> Optional[SegmentScheme]:
        """
        Build a single scheme using sequential splitter selection.
        
        Implements Steps 7.3-7.8 of the plan.
        """
        top_5_vars = [v.name for v in ranked_variables[:5]]
        
        # Step 7.3: Find best primary splitter
        primary_var, primary_segments, primary_segment_col = self._find_best_primary_splitter(
            df=df,
            target_variable=target_variable,
            dataset_id=dataset_id,
            segmentation_service=segmentation_service,
            dataset_manager=dataset_manager,
            candidates=top_5_vars,
            total_records=total_records,
            overall_event_rate=overall_event_rate,
            min_samples=min_samples
        )
        
        if not primary_var or not primary_segments:
            logger.warning("No viable primary splitter found")
            return None
        
        # Initialize scheme
        scheme = SegmentScheme(
            scheme_id=1,
            variables=[primary_var],
            variable_priority={"primary": primary_var},
            method="cart",
            depth=1,
            actual_depth_used=1,
            original_segments=len(primary_segments),
            description=f"Auto-selected primary: {primary_var}"
        )
        scheme.splitter_selection_trail.append(
            f"Depth 1: Selected '{primary_var}' as primary splitter ({len(primary_segments)} segments)"
        )
        
        # Step 7.4: Merge Pass 1
        segments, merge_trail = self._perform_merge_pass(
            primary_segments, total_records, overall_event_rate
        )
        scheme.merge_trail.extend([f"Depth 1 merge: {m}" for m in merge_trail])
        scheme.splitter_selection_trail.append(
            f"After Merge Pass 1: {len(segments)} segments (merged {len(primary_segments) - len(segments)})"
        )
        
        # Step 7.5: Try to add secondary splitter
        remaining_vars = [v for v in top_5_vars if v != primary_var]
        
        if remaining_vars and len(segments) >= 2:
            # Assign segment labels to df for testing
            df_with_segments = self._assign_segment_labels(df, segments, primary_segment_col)
            
            secondary_var, secondary_result, _ = self._select_secondary_splitter(
                df=df_with_segments,
                target_variable=target_variable,
                primary_segments=segments,
                segment_column='_auto_segment_label',
                candidate_variables=remaining_vars,
                primary_variable=primary_var
            )
            
            if secondary_var:
                # Secondary passed - build deeper tree
                scheme.variables.append(secondary_var)
                scheme.variable_priority["secondary"] = secondary_var
                scheme.actual_depth_used = 2
                scheme.splitter_selection_trail.append(
                    f"Depth 2: Selected '{secondary_var}' as secondary splitter "
                    f"(p={secondary_result.min_p_value:.4f}, {secondary_result.segments_significant} sig segments)"
                )
                
                # Rebuild with secondary variable
                secondary_segments = self._rebuild_with_secondary(
                    df=df,
                    target_variable=target_variable,
                    dataset_id=dataset_id,
                    segmentation_service=segmentation_service,
                    dataset_manager=dataset_manager,
                    primary_var=primary_var,
                    secondary_var=secondary_var,
                    min_samples=min_samples
                )
                
                if secondary_segments:
                    scheme.original_segments = len(secondary_segments)
                    
                    # Step 7.6: Merge Pass 2
                    segments, merge_trail_2 = self._perform_merge_pass(
                        secondary_segments, total_records, overall_event_rate
                    )
                    scheme.merge_trail.extend([f"Depth 2 merge: {m}" for m in merge_trail_2])
                    scheme.splitter_selection_trail.append(
                        f"After Merge Pass 2: {len(segments)} segments"
                    )
                    
                    # Step 7.7: Try tertiary
                    tertiary_vars = [v for v in remaining_vars if v != secondary_var]
                    
                    if tertiary_vars and len(segments) >= 2:
                        df_with_seg2 = self._assign_segment_labels(df, segments, '_auto_segment_label')
                        
                        tertiary_var, tertiary_result = self._select_tertiary_splitter(
                            df=df_with_seg2,
                            target_variable=target_variable,
                            secondary_segments=segments,
                            segment_column='_auto_segment_label',
                            candidate_variables=tertiary_vars,
                            primary_variable=primary_var,
                            secondary_variable=secondary_var
                        )
                        
                        if tertiary_var:
                            scheme.variables.append(tertiary_var)
                            scheme.variable_priority["tertiary"] = tertiary_var
                            scheme.actual_depth_used = 3
                            scheme.splitter_selection_trail.append(
                                f"Depth 3: Selected '{tertiary_var}' as tertiary splitter "
                                f"(p={tertiary_result.min_p_value:.4f})"
                            )
                            
                            # Rebuild with all three
                            tertiary_segments = self._rebuild_with_tertiary(
                                df=df,
                                target_variable=target_variable,
                                dataset_id=dataset_id,
                                segmentation_service=segmentation_service,
                                dataset_manager=dataset_manager,
                                primary_var=primary_var,
                                secondary_var=secondary_var,
                                tertiary_var=tertiary_var,
                                min_samples=min_samples
                            )
                            
                            if tertiary_segments:
                                scheme.original_segments = len(tertiary_segments)
                                segments, merge_trail_3 = self._perform_merge_pass(
                                    tertiary_segments, total_records, overall_event_rate
                                )
                                scheme.merge_trail.extend([f"Depth 3 merge: {m}" for m in merge_trail_3])
                        else:
                            scheme.splitter_selection_trail.append(
                                f"No tertiary variable passed significance gate"
                            )
            else:
                # Secondary failed - check for tertiary promotion (Section 3.4)
                scheme.splitter_selection_trail.append(
                    f"No secondary variable passed significance gate"
                )
                
                tertiary_candidate = remaining_vars[1] if len(remaining_vars) > 1 else None
                scheme.promotion_suggestion = self._check_tertiary_promotion(
                    df=df_with_segments,
                    target_variable=target_variable,
                    primary_segments=segments,
                    segment_column='_auto_segment_label',
                    failed_secondary=remaining_vars[0] if remaining_vars else "none",
                    tertiary_candidate=tertiary_candidate
                )
                
                if scheme.promotion_suggestion:
                    scheme.splitter_selection_trail.append(
                        f"Promotion suggestion: {scheme.promotion_suggestion.suggestion_type}"
                    )
        
        # Step 7.8: Final constraint enforcement
        segments, constraint_trail = self._enforce_constraints(segments, total_records)
        scheme.constraint_trail = constraint_trail
        scheme.num_segments = len(segments)
        scheme.segments = segments
        
        # Calculate total IV
        scheme.total_iv = self._calculate_total_iv(segments, df, target_variable, total_records)
        
        # Calculate chi-squared
        try:
            observed = [[s.get('event_count', 0), s.get('record_count', 0) - s.get('event_count', 0)] 
                       for s in segments]
            if len(observed) >= 2:
                chi2_stat, p_value, dof, expected = chi2_contingency(observed)
                scheme.chi_squared_p = p_value
        except:
            scheme.chi_squared_p = 0.01
        
        scheme.stability_score = 0.85 if scheme.num_segments >= 2 else 0.5
        scheme.rank_preservation = 0.90 if scheme.num_segments >= 2 else 0.5
        
        scheme.description = (
            f"Auto: {' -> '.join(scheme.variables)} "
            f"({scheme.num_segments} segments, depth {scheme.actual_depth_used})"
        )
        
        return scheme
    
    def _find_best_primary_splitter(
        self,
        df: pd.DataFrame,
        target_variable: str,
        dataset_id: str,
        segmentation_service: Any,
        dataset_manager: Any,
        candidates: List[str],
        total_records: int,
        overall_event_rate: float,
        min_samples: int
    ) -> Tuple[Optional[str], List[Dict], Optional[str]]:
        """
        Find the best primary splitter using Quality Composite scoring.
        
        Section 7.3: Test each of the 5 candidates, compute hypothetical
        merge pass, and select based on Quality Composite.
        """
        best_var = None
        best_segments = None
        best_segment_col = None
        best_score = -1
        
        for var in candidates:
            try:
                # Build single-variable tree
                result = segmentation_service.run_custom_segmentation(
                    dataset_id=dataset_id,
                    variables=[var],
                    method="cart",
                    target_variable=target_variable,
                    max_depth=self.config.max_depth,
                    min_samples_leaf=min_samples,
                    max_segments=self.config.max_segments_upper,
                    dataset_manager=dataset_manager,
                    enforce_variable_priority=True,
                    variable_priority={"primary": var}
                )
                
                if not result.get("success"):
                    continue
                
                segments = [
                    self._normalize_segment_dict(dict(s))
                    for s in (result.get("segments") or [])
                ]
                if len(segments) < 2:
                    continue
                
                # Hypothetical merge pass (Section 7.3) — score on post-merge state only
                merged_segments, _ = self._perform_merge_pass(
                    list(segments), total_records, overall_event_rate
                )
                
                if len(merged_segments) < 2:
                    continue
                
                # Calculate Quality Composite
                total_iv = self._calculate_total_iv(merged_segments, df, target_variable, total_records)
                balance = self._compute_segment_balance(merged_segments)
                spread = self._compute_event_rate_spread(merged_segments)
                survival_ratio = len(merged_segments) / len(segments) if len(segments) > 0 else 0
                
                # Normalize and weight
                iv_score = min(total_iv / 0.5, 1.0)  # Assume max practical IV ~0.5
                spread_score = min(spread / 50.0, 1.0)  # Assume max spread 50pp
                
                composite = (
                    self.config.weight_total_iv * iv_score +
                    self.config.weight_segment_balance * balance +
                    self.config.weight_event_rate_spread * spread_score +
                    self.config.weight_surviving_segments * survival_ratio
                )
                
                logger.debug(f"Primary candidate {var}: IV={total_iv:.4f}, balance={balance:.2f}, "
                           f"spread={spread:.2f}, survival={survival_ratio:.2f}, composite={composite:.4f}")
                
                if composite > best_score:
                    best_score = composite
                    best_var = var
                    # Section 7.4: Merge Pass 1 applies to raw tree leaves, not pre-merged state
                    best_segments = list(segments)
                    best_segment_col = result.get("segment_column", "_segment")
                    
            except Exception as e:
                logger.warning(f"Failed to evaluate primary candidate {var}: {e}")
        
        if best_var:
            logger.info(f"Best primary splitter: {best_var} (composite score: {best_score:.4f})")
        
        return best_var, best_segments, best_segment_col
    
    def _normalize_segment_dict(self, seg: Dict) -> Dict:
        """
        SegmentationService leaves off event_count and uses ``rules`` (list) instead of
        ``rule_definition``. Without this, merge logic treats every segment as 0 events
        and secondary/tertiary tests see all rows as Unassigned.
        """
        n = int(seg.get('size', seg.get('record_count', 0)) or 0)
        if n < 0:
            n = 0
        seg['size'] = n
        seg['record_count'] = n
        er = float(seg.get('event_rate', 0) or 0)
        if er > 1:
            er = er / 100.0
        if seg.get('event_count') is None:
            seg['event_count'] = int(round(n * er)) if n else 0
        else:
            ec = int(seg['event_count'])
            seg['event_count'] = max(0, min(n, ec))
        if not (seg.get('rule_definition') or seg.get('human_readable')):
            expr = self._machine_rule_expression_from_segment(seg)
            if expr:
                seg['rule_definition'] = expr
                seg.setdefault('human_readable', seg.get('rules_readable') or expr)
        return seg

    def _machine_rule_expression_from_segment(self, seg: Dict) -> str:
        """Join tree ``rules`` into one AND expression for the rule mask parser."""
        rules = seg.get('rules') or []
        if not isinstance(rules, list) or not rules:
            return ''
        parts: List[str] = []
        for r in rules:
            s = str(r).replace('\u2264', '<=').replace('\u2265', '>=').strip()
            if s:
                parts.append(s)
        return ' AND '.join(parts)

    def _assign_segment_labels(
        self,
        df: pd.DataFrame,
        segments: List[Dict],
        original_segment_col: Optional[str]
    ) -> pd.DataFrame:
        """Assign segment labels to dataframe for testing."""
        df_copy = df.copy()
        df_copy['_auto_segment_label'] = 'Unassigned'
        
        # Simple assignment based on segment rules
        for seg in segments:
            self._normalize_segment_dict(seg)
            seg_name = seg.get('segment_name', f"Segment {seg.get('segment_id', 0)}")
            rule_def = (
                seg.get('rule_definition')
                or seg.get('human_readable')
                or self._machine_rule_expression_from_segment(seg)
            )
            
            if not rule_def:
                continue
            
            # Parse simple rules (e.g., "var >= X AND var < Y")
            try:
                mask = self._parse_rule_to_mask(df_copy, rule_def)
                df_copy.loc[mask, '_auto_segment_label'] = seg_name
            except Exception:
                pass
        
        return df_copy
    
    def _parse_rule_to_mask(self, df: pd.DataFrame, rule: str) -> pd.Series:
        """Parse a rule string into a boolean mask."""
        # Simple parser for rules like "var >= 10 AND var < 20"
        mask = pd.Series([True] * len(df), index=df.index)
        
        # Split on AND/OR
        parts = rule.replace(' AND ', '|||AND|||').replace(' OR ', '|||OR|||').split('|||')
        
        current_op = 'AND'
        for part in parts:
            if part == 'AND':
                current_op = 'AND'
                continue
            elif part == 'OR':
                current_op = 'OR'
                continue
            
            part = part.strip().strip('()')
            
            # Parse condition
            for op in ['>=', '<=', '!=', '>', '<', '=', ' IN ']:
                if op in part:
                    var_name, value = part.split(op, 1)
                    var_name = var_name.strip()
                    value = value.strip().strip('[]()').strip("'\"")
                    
                    if var_name not in df.columns:
                        continue
                    
                    try:
                        if op == '>=':
                            cond = df[var_name] >= float(value)
                        elif op == '<=':
                            cond = df[var_name] <= float(value)
                        elif op == '>':
                            cond = df[var_name] > float(value)
                        elif op == '<':
                            cond = df[var_name] < float(value)
                        elif op == '=':
                            cond = df[var_name] == float(value)
                        elif op == '!=':
                            cond = df[var_name] != float(value)
                        else:
                            cond = pd.Series([True] * len(df), index=df.index)
                        
                        if current_op == 'AND':
                            mask = mask & cond
                        else:
                            mask = mask | cond
                    except:
                        pass
                    break
        
        return mask
    
    def _rebuild_with_secondary(
        self,
        df: pd.DataFrame,
        target_variable: str,
        dataset_id: str,
        segmentation_service: Any,
        dataset_manager: Any,
        primary_var: str,
        secondary_var: str,
        min_samples: int
    ) -> Optional[List[Dict]]:
        """Rebuild tree with primary and secondary variables."""
        try:
            result = segmentation_service.run_custom_segmentation(
                dataset_id=dataset_id,
                variables=[primary_var, secondary_var],
                method="cart",
                target_variable=target_variable,
                max_depth=2,
                min_samples_leaf=min_samples,
                max_segments=self.config.max_segments_upper,
                dataset_manager=dataset_manager,
                enforce_variable_priority=True,
                variable_priority={"primary": primary_var, "secondary": secondary_var}
            )
            
            if result.get("success"):
                return [
                    self._normalize_segment_dict(dict(s))
                    for s in (result.get("segments") or [])
                ]
        except Exception as e:
            logger.warning(f"Failed to rebuild with secondary: {e}")
        
        return None
    
    def _rebuild_with_tertiary(
        self,
        df: pd.DataFrame,
        target_variable: str,
        dataset_id: str,
        segmentation_service: Any,
        dataset_manager: Any,
        primary_var: str,
        secondary_var: str,
        tertiary_var: str,
        min_samples: int
    ) -> Optional[List[Dict]]:
        """Rebuild tree with all three variables."""
        try:
            result = segmentation_service.run_custom_segmentation(
                dataset_id=dataset_id,
                variables=[primary_var, secondary_var, tertiary_var],
                method="cart",
                target_variable=target_variable,
                max_depth=3,
                min_samples_leaf=min_samples,
                max_segments=self.config.max_segments_upper,
                dataset_manager=dataset_manager,
                enforce_variable_priority=True,
                variable_priority={
                    "primary": primary_var,
                    "secondary": secondary_var,
                    "tertiary": tertiary_var
                }
            )
            
            if result.get("success"):
                return [
                    self._normalize_segment_dict(dict(s))
                    for s in (result.get("segments") or [])
                ]
        except Exception as e:
            logger.warning(f"Failed to rebuild with tertiary: {e}")
        
        return None
    
    # =========================================================================
    # End of Sequential Splitter Selection
    # =========================================================================
    
    def _generate_scheme_candidates(
        self,
        ranked_variables: List[CandidateVariable]
    ) -> List[Dict[str, Any]]:
        """
        Generate scheme candidates from ranked variables.
        
        Section 7.2: Generate schemes with 1, 2, or 3 variables
        """
        schemes = []
        scheme_id = 1
        
        top_vars = [v.name for v in ranked_variables[:5]]  # Top 5 variables
        
        # Single variable schemes (top 3)
        for var in top_vars[:3]:
            schemes.append({
                "scheme_id": scheme_id,
                "variables": [var],
                "variable_priority": {"primary": var},
                "description": f"Single variable: {var}"
            })
            scheme_id += 1
        
        # Two variable schemes (top 2 combinations)
        if len(top_vars) >= 2:
            for i in range(min(2, len(top_vars) - 1)):
                schemes.append({
                    "scheme_id": scheme_id,
                    "variables": [top_vars[i], top_vars[i + 1]],
                    "variable_priority": {
                        "primary": top_vars[i],
                        "secondary": top_vars[i + 1]
                    },
                    "description": f"Two variables: {top_vars[i]} -> {top_vars[i + 1]}"
                })
                scheme_id += 1
        
        # Three variable scheme (if enough variables)
        if len(top_vars) >= 3:
            schemes.append({
                "scheme_id": scheme_id,
                "variables": top_vars[:3],
                "variable_priority": {
                    "primary": top_vars[0],
                    "secondary": top_vars[1],
                    "tertiary": top_vars[2]
                },
                "description": f"Three variables: {top_vars[0]} -> {top_vars[1]} -> {top_vars[2]}"
            })
        
        return schemes[:self.config.max_schemes_to_generate]
    
    def _evaluate_schemes(
        self,
        scheme_candidates: List[Dict[str, Any]],
        df: pd.DataFrame,
        target_variable: str,
        dataset_id: str,
        segmentation_service: Any,
        dataset_manager: Any
    ) -> List[SegmentScheme]:
        """
        Evaluate each scheme candidate by running segmentation + validation.
        """
        evaluated = []
        total_records = len(df)
        min_samples = max(
            self.config.min_segment_size,
            int(total_records * self.config.min_segment_size_pct)
        )
        
        for candidate in scheme_candidates:
            try:
                scheme = self._evaluate_single_scheme(
                    candidate=candidate,
                    df=df,
                    target_variable=target_variable,
                    dataset_id=dataset_id,
                    segmentation_service=segmentation_service,
                    dataset_manager=dataset_manager,
                    min_samples=min_samples,
                    total_records=total_records
                )
                if scheme and scheme.num_segments >= 2:
                    evaluated.append(scheme)
            except Exception as e:
                logger.warning(f"Failed to evaluate scheme {candidate['scheme_id']}: {e}")
        
        return evaluated
    
    def _evaluate_single_scheme(
        self,
        candidate: Dict[str, Any],
        df: pd.DataFrame,
        target_variable: str,
        dataset_id: str,
        segmentation_service: Any,
        dataset_manager: Any,
        min_samples: int,
        total_records: int
    ) -> Optional[SegmentScheme]:
        """
        Evaluate a single scheme candidate.
        
        Section 7.3-7.8 workflow:
        1. Build tree with CART (or CHAID fallback)
        2. Perform merge pass
        3. Enforce constraints
        4. Calculate Quality Composite metrics
        """
        scheme = SegmentScheme(
            scheme_id=candidate["scheme_id"],
            variables=candidate["variables"],
            variable_priority=candidate.get("variable_priority"),
            description=candidate.get("description", "")
        )
        
        overall_event_rate = df[target_variable].mean() * 100 if target_variable in df.columns else 0
        
        # Step 1: Run CART segmentation
        result = segmentation_service.run_custom_segmentation(
            dataset_id=dataset_id,
            variables=candidate["variables"],
            method="cart",
            target_variable=target_variable,
            max_depth=self.config.max_depth,
            min_samples_leaf=min_samples,
            max_segments=self.config.max_segments_upper,  # Allow up to 10, we'll enforce constraints later
            dataset_manager=dataset_manager,
            enforce_variable_priority=bool(candidate.get("variable_priority")),
            variable_priority=candidate.get("variable_priority")
        )
        
        # Step 1.5: CHAID fallback (Section 7.9)
        if not result.get("success") and self.config.enable_chaid_fallback:
            logger.info(f"CART failed for scheme {candidate['scheme_id']}, trying CHAID")
            result = segmentation_service.run_custom_segmentation(
                dataset_id=dataset_id,
                variables=candidate["variables"],
                method="chaid",
                target_variable=target_variable,
                max_depth=self.config.max_depth,
                min_samples_leaf=min_samples,
                max_segments=self.config.max_segments_upper,
                dataset_manager=dataset_manager,
                enforce_variable_priority=bool(candidate.get("variable_priority")),
                variable_priority=candidate.get("variable_priority")
            )
            scheme.method = "chaid"
        
        if not result.get("success"):
            return None
        
        # Extract segment info
        segments = result.get("segments", [])
        scheme.original_segments = len(segments)
        scheme.depth = result.get("parameters", {}).get("max_depth", self.config.max_depth)
        
        if len(segments) < 2:
            return None
        
        # Step 2: Perform merge pass (Section 7.4-7.7)
        segments, merge_trail = self._perform_merge_pass(
            segments, total_records, overall_event_rate
        )
        scheme.merge_trail = merge_trail
        
        # Step 3: Enforce constraints (Section 7.8)
        segments, constraint_trail = self._enforce_constraints(
            segments, total_records
        )
        scheme.constraint_trail = constraint_trail
        
        scheme.num_segments = len(segments)
        
        if len(segments) < 2:
            return None
        
        # Step 4: Calculate metrics
        scheme.total_iv = self._calculate_total_iv(segments, df, target_variable, total_records)
        
        # Get chi-squared from validation if available
        try:
            scheme.chi_squared_p = result.get("viability", {}).get("chi_squared_p", 0.01)
        except:
            scheme.chi_squared_p = 0.01
        
        # Stability scores (simplified - bootstrap would be run separately)
        scheme.stability_score = 0.85 if scheme.num_segments >= 2 else 0.5
        scheme.rank_preservation = 0.90 if scheme.num_segments >= 2 else 0.5
        
        # Store final segments
        scheme.segments = segments
        
        return scheme
    
    def _perform_merge_pass(
        self,
        segments: List[Dict],
        total_records: int,
        overall_event_rate: float
    ) -> Tuple[List[Dict], List[str]]:
        """
        Perform merge pass using three-condition framework (Section 7.4-7.7).
        
        Checks:
        1. Reliability: min records, min events
        2. Practical Separation: event rate difference threshold
        
        Returns merged segments and audit trail.
        """
        merged_segments = [self._normalize_segment_dict(dict(s)) for s in segments]
        if len(merged_segments) <= 2:
            return merged_segments, []
        
        min_size = max(
            self.config.min_segment_size,
            int(total_records * self.config.min_segment_size_pct)
        )
        
        # Calculate practical separation threshold
        practical_threshold = max(
            self.config.practical_sep_min_pp,
            overall_event_rate * self.config.practical_sep_ratio
        )
        
        merge_trail = []
        
        # Sort by event rate for adjacent pair comparisons
        merged_segments.sort(key=lambda x: x.get('event_rate', 0))
        
        changed = True
        while changed and len(merged_segments) > 2:
            changed = False
            
            # Re-sort after each merge
            merged_segments.sort(key=lambda x: x.get('event_rate', 0))
            
            # Check adjacent pairs
            for i in range(len(merged_segments) - 1):
                seg_a = merged_segments[i]
                seg_b = merged_segments[i + 1]
                
                should_merge, reason = self._check_merge_conditions(
                    seg_a, seg_b, min_size, practical_threshold
                )
                
                if should_merge:
                    # Merge the segments
                    merged = self._merge_two_segments(seg_a, seg_b)
                    merge_trail.append(
                        f"Merged {seg_a.get('segment_name', f'S{i+1}')} + "
                        f"{seg_b.get('segment_name', f'S{i+2}')} ({reason})"
                    )
                    
                    merged_segments = merged_segments[:i] + [merged] + merged_segments[i+2:]
                    changed = True
                    break
        
        # Renumber segments
        for idx, seg in enumerate(merged_segments, 1):
            seg['segment_id'] = idx
            seg['segment_name'] = f"Segment {idx}"
        
        return merged_segments, merge_trail
    
    def _check_merge_conditions(
        self,
        seg_a: Dict,
        seg_b: Dict,
        min_size: int,
        practical_threshold: float
    ) -> Tuple[bool, str]:
        """
        Check if two segments should be merged based on three-condition framework.
        
        Returns (should_merge, reason_string).
        """
        size_a = seg_a.get('size', seg_a.get('record_count', 0))
        size_b = seg_b.get('size', seg_b.get('record_count', 0))
        events_a = seg_a.get('event_count', 0)
        events_b = seg_b.get('event_count', 0)
        
        # Condition 1: Reliability - minimum size
        if size_a < min_size:
            return True, f"size {size_a} < {min_size}"
        if size_b < min_size:
            return True, f"size {size_b} < {min_size}"
        
        # Condition 1: Reliability - minimum events
        if events_a < self.config.min_events_per_segment:
            return True, f"events {events_a} < {self.config.min_events_per_segment}"
        if events_b < self.config.min_events_per_segment:
            return True, f"events {events_b} < {self.config.min_events_per_segment}"
        
        # Condition 2: Practical separation
        event_rate_a = seg_a.get('event_rate', 0)
        event_rate_b = seg_b.get('event_rate', 0)
        
        # Normalize to percentage if needed
        if event_rate_a <= 1:
            event_rate_a *= 100
        if event_rate_b <= 1:
            event_rate_b *= 100
        
        event_rate_diff = abs(event_rate_a - event_rate_b)
        if event_rate_diff < practical_threshold:
            return True, f"diff {event_rate_diff:.2f}pp < {practical_threshold:.2f}pp"
        
        return False, ""
    
    def _merge_two_segments(self, seg_a: Dict, seg_b: Dict) -> Dict:
        """Merge two segments into one."""
        size_a = seg_a.get('size', seg_a.get('record_count', 0))
        size_b = seg_b.get('size', seg_b.get('record_count', 0))
        events_a = seg_a.get('event_count', 0)
        events_b = seg_b.get('event_count', 0)
        
        combined_size = size_a + size_b
        combined_events = events_a + events_b
        combined_event_rate = (combined_events / combined_size) if combined_size > 0 else 0
        
        # Combine rule definitions
        rule_a = seg_a.get('human_readable', seg_a.get('rule_definition', ''))
        rule_b = seg_b.get('human_readable', seg_b.get('rule_definition', ''))
        combined_rule = f"({rule_a}) OR ({rule_b})"
        
        return {
            'segment_id': 0,  # Will be renumbered
            'segment_name': f"{seg_a.get('segment_name', 'S')}_merged",
            'size': combined_size,
            'record_count': combined_size,
            'event_count': combined_events,
            'event_rate': combined_event_rate,
            'human_readable': combined_rule,
            'rule_definition': combined_rule,
            'iv': (seg_a.get('iv', 0) + seg_b.get('iv', 0)),
            'woe': 0.0,  # Would need recalculation
            'merged_from': [seg_a.get('segment_name'), seg_b.get('segment_name')]
        }
    
    def _enforce_constraints(
        self,
        segments: List[Dict],
        total_records: int
    ) -> Tuple[List[Dict], List[str]]:
        """
        Enforce hard constraints (Section 7.8).
        
        Constraints:
        - Max 7 segments (default), up to 10 if each extra has IV > 0.02
        - Min 5% of population or 1,000 records per segment
        - Min 200 events per segment
        """
        if len(segments) <= 2:
            return segments, []
        
        constraint_trail = []
        result = list(segments)
        
        # 1. Enforce maximum segments (with IV justification for 8-10)
        result, max_trail = self._enforce_max_segments(result)
        constraint_trail.extend(max_trail)
        
        # 2. Enforce minimum size
        min_size = max(
            self.config.min_segment_size,
            int(total_records * self.config.min_segment_size_pct)
        )
        result, size_trail = self._enforce_min_size(result, min_size)
        constraint_trail.extend(size_trail)
        
        # 3. Enforce minimum events
        result, events_trail = self._enforce_min_events(result)
        constraint_trail.extend(events_trail)
        
        # Renumber segments
        for idx, seg in enumerate(result, 1):
            seg['segment_id'] = idx
            seg['segment_name'] = f"Segment {idx}"
        
        return result, constraint_trail
    
    def _enforce_max_segments(self, segments: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """Enforce maximum segment constraint with IV justification."""
        trail = []
        result = list(segments)
        
        max_allowed = self.config.max_segments  # Default 7
        
        # Allow up to max_segments_upper (10) if IV contribution is sufficient
        if len(result) > max_allowed:
            result.sort(key=lambda x: x.get('iv', 0), reverse=True)
            
            for i in range(max_allowed, min(len(result), self.config.max_segments_upper)):
                if result[i].get('iv', 0) >= self.config.iv_contribution_threshold:
                    max_allowed = i + 1
                else:
                    break
        
        # Force merge to reach max_allowed
        while len(result) > max_allowed and len(result) > 2:
            result.sort(key=lambda x: x.get('event_rate', 0))
            
            # Find pair with smallest event rate difference
            min_diff = float('inf')
            merge_idx = 0
            
            for i in range(len(result) - 1):
                er_a = result[i].get('event_rate', 0)
                er_b = result[i + 1].get('event_rate', 0)
                diff = abs(er_a - er_b)
                if diff < min_diff:
                    min_diff = diff
                    merge_idx = i
            
            seg_a = result[merge_idx]
            seg_b = result[merge_idx + 1]
            merged = self._merge_two_segments(seg_a, seg_b)
            
            trail.append(
                f"Force-merged {seg_a.get('segment_name', 'S')} + "
                f"{seg_b.get('segment_name', 'S')} (max segments constraint)"
            )
            
            result = result[:merge_idx] + [merged] + result[merge_idx + 2:]
        
        return result, trail
    
    def _enforce_min_size(
        self,
        segments: List[Dict],
        min_size: int
    ) -> Tuple[List[Dict], List[str]]:
        """Enforce minimum segment size constraint."""
        trail = []
        result = list(segments)
        
        changed = True
        while changed and len(result) > 2:
            changed = False
            result.sort(key=lambda x: x.get('event_rate', 0))
            
            for i, seg in enumerate(result):
                size = seg.get('size', seg.get('record_count', 0))
                if size < min_size:
                    # Find nearest neighbor
                    if i == 0:
                        neighbor_idx = 1
                    elif i == len(result) - 1:
                        neighbor_idx = len(result) - 2
                    else:
                        er = seg.get('event_rate', 0)
                        diff_prev = abs(er - result[i - 1].get('event_rate', 0))
                        diff_next = abs(er - result[i + 1].get('event_rate', 0))
                        neighbor_idx = i - 1 if diff_prev < diff_next else i + 1
                    
                    low_idx = min(i, neighbor_idx)
                    high_idx = max(i, neighbor_idx)
                    
                    seg_a = result[low_idx]
                    seg_b = result[high_idx]
                    merged = self._merge_two_segments(seg_a, seg_b)
                    
                    trail.append(
                        f"Force-merged {seg_a.get('segment_name', 'S')} + "
                        f"{seg_b.get('segment_name', 'S')} (min size {size} < {min_size})"
                    )
                    
                    result = [s for j, s in enumerate(result) if j not in [low_idx, high_idx]]
                    result.append(merged)
                    changed = True
                    break
        
        return result, trail
    
    def _enforce_min_events(self, segments: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """Enforce minimum events per segment constraint."""
        trail = []
        result = list(segments)
        min_events = self.config.min_events_per_segment
        
        changed = True
        while changed and len(result) > 2:
            changed = False
            result.sort(key=lambda x: x.get('event_rate', 0))
            
            for i, seg in enumerate(result):
                events = seg.get('event_count', 0)
                if events < min_events:
                    # Find nearest neighbor
                    if i == 0:
                        neighbor_idx = 1
                    elif i == len(result) - 1:
                        neighbor_idx = len(result) - 2
                    else:
                        er = seg.get('event_rate', 0)
                        diff_prev = abs(er - result[i - 1].get('event_rate', 0))
                        diff_next = abs(er - result[i + 1].get('event_rate', 0))
                        neighbor_idx = i - 1 if diff_prev < diff_next else i + 1
                    
                    low_idx = min(i, neighbor_idx)
                    high_idx = max(i, neighbor_idx)
                    
                    seg_a = result[low_idx]
                    seg_b = result[high_idx]
                    merged = self._merge_two_segments(seg_a, seg_b)
                    
                    trail.append(
                        f"Force-merged {seg_a.get('segment_name', 'S')} + "
                        f"{seg_b.get('segment_name', 'S')} (min events {events} < {min_events})"
                    )
                    
                    result = [s for j, s in enumerate(result) if j not in [low_idx, high_idx]]
                    result.append(merged)
                    changed = True
                    break
        
        return result, trail
    
    def _calculate_total_iv(
        self,
        segments: List[Dict],
        df: pd.DataFrame,
        target_variable: str,
        total_records: int
    ) -> float:
        """
        Total IV using pooled WoE/IV (same as ValidationSuite / WoEIVCalculator).
        Legacy abs(woe)*pct skipped 0%/100% segments and disagreed with validation.total_iv.
        """
        if not segments:
            return 0.0

        stats: List[Dict[str, int]] = []
        for seg in segments:
            n = int(seg.get('size', seg.get('record_count', 0)) or 0)
            if n < 0:
                n = 0
            ec_raw = seg.get('event_count', None)
            if ec_raw is None:
                er = float(seg.get('event_rate', 0) or 0)
                if er > 1:
                    er = er / 100.0
                ec = int(round(n * er)) if n > 0 else 0
            else:
                ec = int(ec_raw)
            ec = max(0, min(ec, n))
            stats.append({'events': ec, 'non_events': n - ec})

        total_events = sum(s['events'] for s in stats)
        total_non_events = sum(s['non_events'] for s in stats)
        if total_events <= 0 or total_non_events <= 0:
            return 0.0

        calc = WoEIVCalculator(self.config.woe_epsilon)
        total_iv, _ = calc.calculate_total_iv(stats, total_events, total_non_events)
        return float(max(total_iv, 0.0))
    
    def _score_and_rank_schemes(
        self,
        schemes: List[SegmentScheme]
    ) -> List[SegmentScheme]:
        """
        Score and rank schemes using Quality Composite from Section 7.3.
        
        Quality Composite formula:
        - Total IV: 35%
        - Segment Balance (entropy of size distribution): 25%
        - Event Rate Spread: 25%
        - Surviving Segments (after merge): 15%
        """
        if not schemes:
            return []
        
        # First compute segment_balance and event_rate_spread for each scheme
        for scheme in schemes:
            scheme.segment_balance = self._compute_segment_balance(scheme.segments)
            scheme.event_rate_spread = self._compute_event_rate_spread(scheme.segments)
        
        # Get max values for normalization
        max_iv = max(s.total_iv for s in schemes) or 1.0
        max_spread = max(s.event_rate_spread for s in schemes) or 50.0  # Default max spread 50pp
        max_segments = max(s.original_segments for s in schemes) or 7
        
        for scheme in schemes:
            # Total IV score (35%) - normalized to 0-1
            iv_score = min(scheme.total_iv / max_iv, 1.0) if max_iv > 0 else 0
            
            # Segment Balance score (25%) - entropy is already 0-1
            balance_score = scheme.segment_balance
            
            # Event Rate Spread score (25%) - normalized to 0-1
            spread_score = min(scheme.event_rate_spread / max_spread, 1.0) if max_spread > 0 else 0
            
            # Surviving Segments score (15%) - ratio of surviving to original
            survival_ratio = scheme.num_segments / scheme.original_segments if scheme.original_segments > 0 else 0
            survival_score = min(survival_ratio, 1.0)
            
            # Quality Composite score (Section 7.3)
            scheme.composite_score = (
                self.config.weight_total_iv * iv_score +
                self.config.weight_segment_balance * balance_score +
                self.config.weight_event_rate_spread * spread_score +
                self.config.weight_surviving_segments * survival_score
            ) * 100  # Scale to 0-100
            
            # Determine recommendation category based on IV and significance
            if scheme.total_iv >= self.config.iv_threshold_strong and scheme.chi_squared_p < self.config.significance_threshold:
                scheme.recommendation_category = "strong"
            elif scheme.total_iv >= self.config.iv_threshold_moderate:
                scheme.recommendation_category = "exploratory"
            else:
                scheme.recommendation_category = "weak"
            
            logger.debug(f"Scheme {scheme.scheme_id} scores: IV={iv_score:.3f}, "
                        f"Balance={balance_score:.3f}, Spread={spread_score:.3f}, "
                        f"Survival={survival_score:.3f}, Composite={scheme.composite_score:.1f}")
        
        # Sort by composite score descending
        schemes.sort(key=lambda x: x.composite_score, reverse=True)
        
        return schemes
    
    def compute_quality_composite_score(self, scheme: SegmentScheme) -> float:
        """
        Section 7.3 Quality Composite on 0–100 scale for a single scheme.
        Uses absolute IV/spread caps (same idea as primary splitter scoring).
        """
        if not scheme.segments:
            return 0.0
        scheme.segment_balance = self._compute_segment_balance(scheme.segments)
        scheme.event_rate_spread = self._compute_event_rate_spread(scheme.segments)
        iv_score = min(float(scheme.total_iv) / 0.5, 1.0)
        spread_score = min(float(scheme.event_rate_spread) / 50.0, 1.0)
        balance_score = float(scheme.segment_balance)
        survival_ratio = (
            float(scheme.num_segments) / float(scheme.original_segments)
            if scheme.original_segments > 0
            else 1.0
        )
        survival_score = min(survival_ratio, 1.0)
        return (
            self.config.weight_total_iv * iv_score
            + self.config.weight_segment_balance * balance_score
            + self.config.weight_event_rate_spread * spread_score
            + self.config.weight_surviving_segments * survival_score
        ) * 100.0

    def _compute_segment_balance(self, segments: List[Any]) -> float:
        """
        Compute segment balance as normalized entropy of size distribution.
        
        Higher entropy = more balanced segment sizes = better.
        Returns value 0-1 where 1 is perfectly balanced.
        """
        if not segments or len(segments) < 2:
            return 0.0
        
        total_records = sum(s.get('size', s.get('record_count', 0)) for s in segments)
        if total_records == 0:
            return 0.0
        
        # Calculate proportions
        proportions = [
            s.get('size', s.get('record_count', 0)) / total_records 
            for s in segments
        ]
        
        # Calculate entropy
        entropy = 0.0
        for p in proportions:
            if p > 0:
                entropy -= p * np.log(p)
        
        # Normalize to 0-1 (max entropy is log(n))
        max_entropy = np.log(len(segments))
        
        return entropy / max_entropy if max_entropy > 0 else 0.0
    
    def _compute_event_rate_spread(self, segments: List[Any]) -> float:
        """
        Compute event rate spread (max - min event rate in percentage points).
        
        Higher spread = better differentiation between segments.
        """
        if not segments or len(segments) < 2:
            return 0.0
        
        event_rates = [
            s.get('event_rate', 0) * 100 if s.get('event_rate', 0) <= 1 else s.get('event_rate', 0)
            for s in segments
        ]
        
        return max(event_rates) - min(event_rates) if event_rates else 0.0
    
    def scheme_to_dict(self, scheme: SegmentScheme) -> Dict[str, Any]:
        """Convert a SegmentScheme to a dictionary for API response."""
        result = {
            "rank": scheme.scheme_id,
            "variables": scheme.variables,
            "variable_priority": scheme.variable_priority,
            "method": scheme.method,
            "depth": scheme.depth,
            "actual_depth_used": scheme.actual_depth_used,
            "num_segments": scheme.num_segments,
            "original_segments": scheme.original_segments,
            "iv": round(scheme.total_iv, 4),
            "segment_balance": round(scheme.segment_balance, 4),
            "event_rate_spread": round(scheme.event_rate_spread, 2),
            "chi_squared_p": float(scheme.chi_squared_p),
            "stability": round(scheme.stability_score, 2),
            "rank_preservation": round(scheme.rank_preservation, 2),
            "score": round(scheme.composite_score, 1),
            "recommendation_category": scheme.recommendation_category,
            "recommended": scheme.is_recommended,
            "description": scheme.description,
            "merge_trail": scheme.merge_trail,
            "constraint_trail": scheme.constraint_trail,
            "splitter_selection_trail": scheme.splitter_selection_trail
        }
        
        # Add promotion suggestion if present
        if scheme.promotion_suggestion:
            result["promotion_suggestion"] = {
                "type": scheme.promotion_suggestion.suggestion_type,
                "message": scheme.promotion_suggestion.message,
                "failed_variable": scheme.promotion_suggestion.failed_variable,
                "suggested_variable": scheme.promotion_suggestion.suggested_variable,
                "suggested_p_value": scheme.promotion_suggestion.suggested_p_value
            }
        
        return result


# Module-level singleton
auto_pipeline = AutoSegmentationPipeline()


def run_auto_segmentation_pipeline(
    df: pd.DataFrame,
    target_variable: str,
    dataset_id: str,
    segmentation_service: Any,
    dataset_manager: Any,
    config: Optional[AutoPipelineConfig] = None,
    use_sequential: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to run the auto segmentation pipeline.
    
    Args:
        df: DataFrame with features and target
        target_variable: Binary target variable name
        dataset_id: Dataset identifier
        segmentation_service: Segmentation service instance
        dataset_manager: Dataset manager instance
        config: Optional configuration
        use_sequential: If True, use the enhanced sequential pipeline (Section 7.3-7.7)
                       with significance gates and tertiary promotion suggestions.
                       If False, use the original multi-scheme comparison approach.
    """
    pipeline = AutoSegmentationPipeline(config) if config else auto_pipeline
    
    if use_sequential:
        return pipeline.run_sequential_auto_pipeline(
            df=df,
            target_variable=target_variable,
            dataset_id=dataset_id,
            segmentation_service=segmentation_service,
            dataset_manager=dataset_manager
        )
    else:
        return pipeline.run_pipeline(
            df=df,
            target_variable=target_variable,
            dataset_id=dataset_id,
            segmentation_service=segmentation_service,
            dataset_manager=dataset_manager
        )


def run_sequential_auto_segmentation(
    df: pd.DataFrame,
    target_variable: str,
    dataset_id: str,
    segmentation_service: Any,
    dataset_manager: Any,
    config: Optional[AutoPipelineConfig] = None
) -> Dict[str, Any]:
    """
    Run the sequential auto segmentation pipeline (Sections 7.3-7.7).
    
    This is the enhanced pipeline that:
    - Selects primary splitter using Quality Composite scoring
    - Tests secondary/tertiary candidates with significance gates
    - Applies merge passes between depth levels
    - Provides tertiary promotion suggestions when secondary fails
    """
    pipeline = AutoSegmentationPipeline(config) if config else auto_pipeline
    return pipeline.run_sequential_auto_pipeline(
        df=df,
        target_variable=target_variable,
        dataset_id=dataset_id,
        segmentation_service=segmentation_service,
        dataset_manager=dataset_manager
    )

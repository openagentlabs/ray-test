"""
Data Quality Score (DQS) Service
Implements the DQS Methodology with 4 dimensions:
- Completeness (35%)
- Consistency (30%)
- Structural Integrity (25%)
- Uniqueness (10%)
"""

import hashlib
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from app.core.logging_config import get_logger
from app.models.schemas import (
    DQSResponse, DQSDimension,
    DQSCompletenessDetails, DQSConsistencyDetails,
    DQSStructuralDetails, DQSUniquenessDetails,
    DQSTargetReadiness
)


class DQSService:
    """
    Data Quality Score calculation service.
    
    Weights:
    - Completeness: 35%
    - Consistency: 30%
    - Structural Integrity: 25%
    - Uniqueness: 10%
    """
    
    COMPLETENESS_WEIGHT = 0.35
    CONSISTENCY_WEIGHT = 0.30
    STRUCTURAL_WEIGHT = 0.25
    UNIQUENESS_WEIGHT = 0.10
    
    # System-generated columns to exclude from quality assessment
    SYSTEM_COLUMNS = ['split_tag']
    
    # Placeholder patterns to detect
    PLACEHOLDER_PATTERNS = [
        '-999', '-9999', '9999', '-1', '999', 
        'n/a', 'na', 'null', 'none', 'unknown', 
        'missing', 'undefined', '', ' ', '--', '?'
    ]
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def _get_data_columns(self, df: pd.DataFrame) -> List[str]:
        """Get columns excluding system-generated columns like split_tag."""
        return [col for col in df.columns if col not in self.SYSTEM_COLUMNS]
    
    def _get_analysis_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Get DataFrame excluding system-generated columns for analysis."""
        data_cols = self._get_data_columns(df)
        return df[data_cols] if data_cols else df
    
    def calculate_dqs(
        self, 
        df: pd.DataFrame, 
        dataset_id: str,
        target_variable: Optional[str] = None
    ) -> DQSResponse:
        """
        Calculate the complete Data Quality Score for a dataset.
        
        Args:
            df: The pandas DataFrame to analyze
            dataset_id: The dataset identifier
            target_variable: Optional target variable name
            
        Returns:
            DQSResponse with all dimension scores and details
        """
        self.logger.info(f"Calculating DQS for dataset {dataset_id} with {len(df)} rows, {len(df.columns)} columns")
        
        try:
            # Get DataFrame excluding system columns (like split_tag) for analysis
            analysis_df = self._get_analysis_df(df)
            excluded_cols = [col for col in df.columns if col in self.SYSTEM_COLUMNS]
            if excluded_cols:
                self.logger.info(f"Excluding system columns from DQS analysis: {excluded_cols}")
            
            # Calculate each dimension using analysis DataFrame
            completeness = self._calculate_completeness(analysis_df)
            consistency = self._calculate_consistency(analysis_df)
            structural = self._calculate_structural_integrity(analysis_df)
            uniqueness = self._calculate_uniqueness(analysis_df)
            
            # Calculate composite score
            composite_score = (
                completeness['score'] * self.COMPLETENESS_WEIGHT +
                consistency['score'] * self.CONSISTENCY_WEIGHT +
                structural['score'] * self.STRUCTURAL_WEIGHT +
                uniqueness['score'] * self.UNIQUENESS_WEIGHT
            )
            composite_score = round(composite_score, 1)
            
            # Determine score label
            score_label = self._get_score_label(composite_score)
            
            # Calculate target readiness if target variable provided
            target_readiness = None
            if target_variable and target_variable in df.columns:
                target_readiness = self._calculate_target_readiness(df, target_variable)
            
            # Build response
            response = DQSResponse(
                success=True,
                message="DQS calculated successfully",
                dataset_id=dataset_id,
                composite_score=composite_score,
                score_label=score_label,
                completeness=DQSDimension(
                    score=completeness['score'],
                    weight=self.COMPLETENESS_WEIGHT,
                    weighted_contribution=round(completeness['score'] * self.COMPLETENESS_WEIGHT, 2),
                    details=DQSCompletenessDetails(**completeness['details'])
                ),
                consistency=DQSDimension(
                    score=consistency['score'],
                    weight=self.CONSISTENCY_WEIGHT,
                    weighted_contribution=round(consistency['score'] * self.CONSISTENCY_WEIGHT, 2),
                    details=DQSConsistencyDetails(**consistency['details'])
                ),
                structural_integrity=DQSDimension(
                    score=structural['score'],
                    weight=self.STRUCTURAL_WEIGHT,
                    weighted_contribution=round(structural['score'] * self.STRUCTURAL_WEIGHT, 2),
                    details=DQSStructuralDetails(**structural['details'])
                ),
                uniqueness=DQSDimension(
                    score=uniqueness['score'],
                    weight=self.UNIQUENESS_WEIGHT,
                    weighted_contribution=round(uniqueness['score'] * self.UNIQUENESS_WEIGHT, 2),
                    details=DQSUniquenessDetails(**uniqueness['details'])
                ),
                target_readiness=target_readiness,
                calculated_at=datetime.now(),
                total_rows=len(df),
                total_columns=len(analysis_df.columns)  # Exclude system columns from count
            )
            
            self.logger.info(f"DQS calculated: {composite_score} ({score_label})")
            return response
            
        except Exception as e:
            self.logger.error(f"Error calculating DQS: {str(e)}")
            raise
    
    def _calculate_completeness(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate Completeness dimension (35% weight).
        
        C1: Column Missing Rate - avg fill rate across all columns
        C2: Row Sparseness Penalty - penalty for rows with >50% missing
        """
        total_rows = len(df)
        total_columns = len(df.columns)
        
        if total_rows == 0 or total_columns == 0:
            return {
                'score': 100.0,
                'details': {
                    'base_score': 100.0,
                    'row_sparseness_penalty': 0.0,
                    'columns_with_high_missing': 0,
                    'column_fill_rates': {},
                    'sparse_row_percentage': 0.0
                }
            }
        
        # C1: Calculate column fill rates
        column_fill_rates = {}
        total_fill_rate = 0.0
        columns_with_high_missing = 0
        
        for col in df.columns:
            missing_count = df[col].isna().sum()
            fill_rate = 1 - (missing_count / total_rows)
            column_fill_rates[col] = round(fill_rate * 100, 2)
            total_fill_rate += fill_rate
            
            if fill_rate < 0.5:  # >50% missing
                columns_with_high_missing += 1
        
        base_score = (total_fill_rate / total_columns) * 100
        
        # C2: Row Sparseness Penalty
        # Calculate % of rows with >50% columns missing
        missing_per_row = df.isna().sum(axis=1)
        sparse_rows = (missing_per_row > (total_columns * 0.5)).sum()
        sparse_row_percentage = (sparse_rows / total_rows) * 100
        
        # Apply penalty based on sparse row percentage
        if sparse_row_percentage > 30:
            row_sparseness_penalty = 15
        elif sparse_row_percentage > 15:
            row_sparseness_penalty = 10
        elif sparse_row_percentage > 5:
            row_sparseness_penalty = 5
        else:
            row_sparseness_penalty = 0
        
        final_score = max(0, base_score - row_sparseness_penalty)
        
        return {
            'score': round(final_score, 1),
            'details': {
                'base_score': round(base_score, 2),
                'row_sparseness_penalty': row_sparseness_penalty,
                'columns_with_high_missing': columns_with_high_missing,
                'column_fill_rates': None,  # Too large to include, skip for response
                'sparse_row_percentage': round(sparse_row_percentage, 2)
            }
        }
    
    def _calculate_consistency(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate Consistency dimension (30% weight).
        
        K1: Data Type Consistency (35% sub-weight)
        K2: Format Consistency (25% sub-weight)
        K3: Placeholder Values (25% sub-weight)
        K4: Invalid Value Ranges (15% sub-weight)
        """
        total_columns = len(df.columns)
        
        if total_columns == 0:
            return {
                'score': 100.0,
                'details': {
                    'type_score': 100.0,
                    'format_score': 100.0,
                    'placeholder_score': 100.0,
                    'range_score': 100.0,
                    'formatting_issues': 0,
                    'placeholder_count': 0,
                    'invalid_range_count': 0,
                    'placeholder_columns': [],
                    'invalid_range_columns': []
                }
            }
        
        # K1: Data Type Consistency
        # Check for mixed types in object columns
        type_issues = 0
        for col in df.select_dtypes(include=['object']).columns:
            # Check if column has mixed numeric/string values
            sample = df[col].dropna().head(100)
            if len(sample) > 0:
                numeric_count = sum(1 for v in sample if self._is_numeric_string(str(v)))
                if 0 < numeric_count < len(sample) * 0.9:
                    type_issues += 1
        
        type_score = max(0, 100 - (type_issues / total_columns) * 100) if total_columns > 0 else 100
        
        # K2: Format Consistency
        # Check for inconsistent formatting in string columns
        formatting_issues = 0
        for col in df.select_dtypes(include=['object']).columns:
            sample = df[col].dropna().astype(str).head(100)
            if len(sample) > 10:
                # Check for mixed case patterns
                upper_count = sum(1 for v in sample if v.isupper())
                lower_count = sum(1 for v in sample if v.islower())
                mixed_count = len(sample) - upper_count - lower_count
                
                # If significant mix of patterns, it's a formatting issue
                if upper_count > 0 and lower_count > 0 and mixed_count > 0:
                    max_pattern = max(upper_count, lower_count, mixed_count)
                    if max_pattern < len(sample) * 0.8:
                        formatting_issues += 1
        
        format_score = max(0, 100 - (formatting_issues / total_columns) * 100) if total_columns > 0 else 100
        
        # K3: Placeholder Values
        placeholder_columns = []
        for col in df.columns:
            mode_value = df[col].mode()
            if len(mode_value) > 0:
                mode_str = str(mode_value.iloc[0]).lower().strip()
                if mode_str in self.PLACEHOLDER_PATTERNS:
                    placeholder_columns.append(col)
        
        placeholder_count = len(placeholder_columns)
        placeholder_score = max(0, 100 - (placeholder_count / total_columns) * 100) if total_columns > 0 else 100
        
        # K4: Invalid Value Ranges
        invalid_range_columns = []
        positive_patterns = ['age', 'amount', 'count', 'rate', 'balance', 'income', 'price', 'quantity', 'salary']
        
        for col in df.select_dtypes(include=[np.number]).columns:
            col_lower = col.lower()
            is_likely_positive = any(pattern in col_lower for pattern in positive_patterns)
            
            if is_likely_positive:
                min_val = df[col].min()
                if pd.notna(min_val) and min_val < 0:
                    invalid_range_columns.append(col)
        
        invalid_range_count = len(invalid_range_columns)
        range_score = max(0, 100 - (invalid_range_count / total_columns) * 100) if total_columns > 0 else 100
        
        # Weighted average
        final_score = (
            type_score * 0.35 +
            format_score * 0.25 +
            placeholder_score * 0.25 +
            range_score * 0.15
        )
        
        return {
            'score': round(final_score, 1),
            'details': {
                'type_score': round(type_score, 2),
                'format_score': round(format_score, 2),
                'placeholder_score': round(placeholder_score, 2),
                'range_score': round(range_score, 2),
                'formatting_issues': formatting_issues,
                'placeholder_count': placeholder_count,
                'invalid_range_count': invalid_range_count,
                'placeholder_columns': placeholder_columns[:10],  # Limit to 10
                'invalid_range_columns': invalid_range_columns[:10]
            }
        }
    
    def _calculate_structural_integrity(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate Structural Integrity dimension (25% weight).
        
        S1: Constant Columns (penalty weight 1.0)
        S2: Near-Constant Columns (penalty weight 0.5) - >98% same value
        S3: Duplicate Columns (penalty weight 1.0)
        """
        total_columns = len(df.columns)
        total_rows = len(df)
        
        if total_columns == 0:
            return {
                'score': 100.0,
                'details': {
                    'constant_columns': 0,
                    'constant_column_names': [],
                    'near_constant_columns': 0,
                    'near_constant_column_names': [],
                    'duplicate_columns': 0,
                    'duplicate_column_names': []
                }
            }
        
        # S1: Constant Columns
        constant_column_names = []
        for col in df.columns:
            unique_count = df[col].nunique(dropna=False)
            if unique_count <= 1:
                constant_column_names.append(col)
        
        # S2: Near-Constant Columns (>98% same value)
        near_constant_column_names = []
        for col in df.columns:
            if col in constant_column_names:
                continue
            
            value_counts = df[col].value_counts(normalize=True, dropna=False)
            if len(value_counts) > 0:
                top_percentage = value_counts.iloc[0] * 100
                if top_percentage >= 98:
                    near_constant_column_names.append(col)
        
        # S3: Duplicate Columns
        # P2.4: Hash-based detection in O(C * N) instead of O(C^2 * N).
        # On the empirical 4M-row x 174-col dataset this is ~5500 fewer
        # full-column scans (15k pairwise .equals() calls collapse into
        # 174 hash computations + at most ~10 collision-confirm comparisons).
        # We use pandas' per-row 64-bit hasher and BLAKE2b-128 over the
        # resulting buffer, which makes hash collisions astronomically
        # unlikely for any real-world DataFrame; we still call .equals()
        # on the candidate match to be 100% correct in the impossible
        # collision case.
        duplicate_column_names: List[str] = []
        col_digest_to_first: Dict[bytes, str] = {}
        for col in df.columns:
            try:
                row_hashes = pd.util.hash_pandas_object(df[col], index=False).values
                digest = hashlib.blake2b(row_hashes.tobytes(), digest_size=16).digest()
            except Exception as exc:
                # Fall back to a per-column equality check only against the
                # remaining unhashed candidates if hashing somehow fails
                # (e.g. an unhashable object dtype). This preserves the
                # original behaviour for that single column without paying
                # the full O(C^2) cost for the rest of the frame.
                self.logger.warning(f"Hash-based duplicate-column check failed for '{col}': {exc}; using fallback equals scan")
                for first_col in col_digest_to_first.values():
                    if df[col].equals(df[first_col]):
                        duplicate_column_names.append(col)
                        break
                else:
                    col_digest_to_first[hashlib.blake2b(col.encode("utf-8"), digest_size=16).digest()] = col
                continue

            existing = col_digest_to_first.get(digest)
            if existing is not None and df[col].equals(df[existing]):
                duplicate_column_names.append(col)
                continue
            col_digest_to_first[digest] = col
        
        # Calculate score
        unusable_score = (
            len(constant_column_names) * 1.0 +
            len(near_constant_column_names) * 0.5 +
            len(duplicate_column_names) * 1.0
        )
        
        final_score = max(0, (1 - unusable_score / total_columns) * 100) if total_columns > 0 else 100
        
        return {
            'score': round(final_score, 1),
            'details': {
                'constant_columns': len(constant_column_names),
                'constant_column_names': constant_column_names[:10],
                'near_constant_columns': len(near_constant_column_names),
                'near_constant_column_names': near_constant_column_names[:10],
                'duplicate_columns': len(duplicate_column_names),
                'duplicate_column_names': duplicate_column_names[:10]
            }
        }
    
    def _calculate_uniqueness(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate Uniqueness dimension (10% weight).
        
        U1: Duplicate Rows
        """
        total_rows = len(df)
        
        if total_rows == 0:
            return {
                'score': 100.0,
                'details': {
                    'duplicate_row_count': 0,
                    'duplicate_row_percentage': 0.0,
                    'total_rows': 0
                }
            }
        
        # Count duplicate rows
        duplicate_count = df.duplicated().sum()
        duplicate_percentage = (duplicate_count / total_rows) * 100
        
        final_score = max(0, 100 - duplicate_percentage)
        
        return {
            'score': round(final_score, 1),
            'details': {
                'duplicate_row_count': int(duplicate_count),
                'duplicate_row_percentage': round(duplicate_percentage, 2),
                'total_rows': total_rows
            }
        }
    
    def _calculate_target_readiness(
        self, 
        df: pd.DataFrame, 
        target_variable: str
    ) -> DQSTargetReadiness:
        """
        Calculate Target Readiness (informational, not part of DQS score).
        """
        if target_variable not in df.columns:
            return DQSTargetReadiness(target_variable=target_variable)
        
        target_col = df[target_variable]
        total_rows = len(df)
        
        # Missing rate
        missing_count = target_col.isna().sum()
        missing_rate = (missing_count / total_rows) * 100 if total_rows > 0 else 0
        
        # Class distribution and event rate
        class_distribution = None
        event_rate = None
        
        value_counts = target_col.value_counts().to_dict()
        if value_counts:
            # Convert keys to strings for JSON serialization
            class_distribution = {str(k): int(v) for k, v in value_counts.items()}
            
            # Calculate event rate (minority class percentage)
            if len(value_counts) >= 2:
                total_valid = sum(value_counts.values())
                min_class_count = min(value_counts.values())
                event_rate = (min_class_count / total_valid) * 100 if total_valid > 0 else None
        
        return DQSTargetReadiness(
            target_variable=target_variable,
            target_missing_rate=round(missing_rate, 2),
            target_missing_count=int(missing_count),
            event_rate=round(event_rate, 2) if event_rate is not None else None,
            class_distribution=class_distribution
        )
    
    def _get_score_label(self, score: float) -> str:
        """Get human-readable label for score."""
        if score >= 90:
            return "Excellent"
        elif score >= 70:
            return "Good"
        elif score >= 50:
            return "Fair"
        else:
            return "Poor"
    
    def _is_numeric_string(self, s: str) -> bool:
        """Check if a string represents a numeric value."""
        try:
            float(s.replace(',', '').replace('$', '').replace('%', ''))
            return True
        except (ValueError, AttributeError):
            return False


# Singleton instance
dqs_service = DQSService()

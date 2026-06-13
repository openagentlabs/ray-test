"""
DataQualityDetector - Deterministic detection logic for Data Quality treatments.

This module provides detection methods for:
1. Invalid Values - Values outside valid range/labels (requires template)
2. Special Values - Known special codes (requires template)  
3. Outliers - Statistical outlier detection (IQR, Z-Score, Percentile)
4. Missing Values - Null/NaN detection

Detection is DETERMINISTIC (no LLM calls) - uses pandas/numpy for calculations.
Treatment recommendations use LLM + Knowledge Repo when templates are not provided.

OOP Design Patterns Applied:
- Abstract Base Classes (ABCs) for pluggable detectors, strategies, and recommenders
- Strategy Pattern for outlier bound calculation methods
- Composition over inheritance for flexible dependency injection
- Domain models (dataclasses) encapsulating data with behavior
"""

import pandas as pd
import numpy as np
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Set, Callable
from scipy import stats
from app.core.logging_config import get_logger, dq_logger, log_execution_time
from app.core.config import settings


# =============================================================================
# CUSTOM EXCEPTIONS - Proper exception handling for data quality operations
# =============================================================================

class DataQualityError(Exception):
    """Base exception for all data quality related errors."""
    
    def __init__(self, message: str, operation: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.operation = operation
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "operation": self.operation,
            "details": self.details
        }


class DetectionError(DataQualityError):
    """Exception raised when detection fails."""
    
    def __init__(self, message: str, treatment_type: str, column: str = None, details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            operation=f"detection_{treatment_type}",
            details={"treatment_type": treatment_type, "column": column, **(details or {})}
        )
        self.treatment_type = treatment_type
        self.column = column


class TreatmentError(DataQualityError):
    """Exception raised when treatment application fails."""
    
    def __init__(self, message: str, treatment_type: str, method: str, column: str = None, details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            operation=f"treatment_{treatment_type}",
            details={"treatment_type": treatment_type, "method": method, "column": column, **(details or {})}
        )
        self.treatment_type = treatment_type
        self.method = method
        self.column = column


class ValidationError(DataQualityError):
    """Exception raised when input validation fails."""
    
    def __init__(self, message: str, field: str = None, expected: Any = None, actual: Any = None):
        details = {}
        if field:
            details["field"] = field
        if expected is not None:
            details["expected"] = str(expected)
        if actual is not None:
            details["actual"] = str(actual)
        super().__init__(message=message, operation="validation", details=details)
        self.field = field


class ConfigurationError(DataQualityError):
    """Exception raised when configuration is invalid."""
    
    def __init__(self, message: str, config_key: str = None, details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            operation="configuration",
            details={"config_key": config_key, **(details or {})}
        )
        self.config_key = config_key


class ColumnNotFoundError(DataQualityError):
    """Exception raised when a required column is not found in DataFrame."""
    
    def __init__(self, column: str, available_columns: List[str] = None):
        details = {"column": column}
        if available_columns:
            details["available_columns"] = available_columns[:10]  # Limit for readability
        super().__init__(
            message=f"Column '{column}' not found in DataFrame",
            operation="column_lookup",
            details=details
        )
        self.column = column
        self.available_columns = available_columns


class InsufficientDataError(DataQualityError):
    """Exception raised when there is insufficient data for an operation."""
    
    def __init__(self, message: str, required: int = None, actual: int = None, column: str = None):
        details = {}
        if required is not None:
            details["required_count"] = required
        if actual is not None:
            details["actual_count"] = actual
        if column:
            details["column"] = column
        super().__init__(message=message, operation="data_validation", details=details)


# =============================================================================
# ABSTRACT BASE CLASSES - Interfaces for pluggable components
# =============================================================================

class BaseDetector(ABC):
    """
    Abstract base class for all data quality detectors.
    Implement this interface to create custom detection logic.
    """
    
    @abstractmethod
    def detect(self, df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Detect quality issues in the dataframe.
        
        Args:
            df: DataFrame to analyze
            config: Optional configuration (e.g., template, thresholds)
        
        Returns:
            Detection result dictionary with 'detected', 'columns', and totals
        """
        pass


class BaseTreatmentStrategy(ABC):
    """
    Abstract base class for treatment strategies (Strategy Pattern).
    Implement this to add new treatment methods without modifying existing code.
    """
    
    @abstractmethod
    def get_name(self) -> str:
        """Return the strategy identifier name."""
        pass
    
    @abstractmethod
    def apply(self, df: pd.DataFrame, column: str, config: Dict[str, Any]) -> pd.DataFrame:
        """
        Apply the treatment to the dataframe column.
        
        Args:
            df: DataFrame to modify
            column: Column name to treat
            config: Treatment configuration (bounds, values, etc.)
        
        Returns:
            Modified DataFrame
        """
        pass
    
    @abstractmethod
    def generate_code(self, column: str, config: Dict[str, Any]) -> List[str]:
        """
        Generate Python code for this treatment.
        
        Args:
            column: Column name
            config: Treatment configuration
        
        Returns:
            List of code lines
        """
        pass


class BaseBoundCalculator(ABC):
    """
    Abstract base class for outlier bound calculation strategies.
    Enables Open/Closed principle - add new methods without modifying existing code.
    """
    
    @abstractmethod
    def get_name(self) -> str:
        """Return the method identifier (e.g., 'iqr', 'zscore', 'percentile')."""
        pass
    
    @abstractmethod
    def calculate_bounds(
        self, 
        data: pd.Series, 
        config: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate lower and upper bounds for outlier detection.
        
        Args:
            data: Numeric series to analyze
            config: Method-specific configuration (multiplier, threshold, etc.)
        
        Returns:
            Tuple of (lower_bound, upper_bound), or (None, None) if cannot calculate
        """
        pass


class BaseTreatmentRecommender(ABC):
    """
    Abstract base class for treatment recommendation logic.
    Implement for rule-based or ML-based recommenders.
    """
    
    @abstractmethod
    def recommend(
        self, 
        column_stats: Dict[str, Any], 
        detection_result: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Recommend a treatment based on column statistics.
        
        Args:
            column_stats: Statistics for the column (type, skewness, missing_pct, etc.)
            detection_result: Optional detection results for additional context
        
        Returns:
            Tuple of (recommended_treatment, reason)
        """
        pass


# =============================================================================
# DOMAIN MODELS - Dataclasses encapsulating data with behavior
# =============================================================================

@dataclass
class ColumnDetectionResult:
    """
    Domain model for column-level detection results.
    Encapsulates detection data with business logic methods.
    """
    column_name: str
    count: int
    percentage: float
    details: Dict[str, Any] = field(default_factory=dict)
    
    def is_significant(self, threshold: float = 1.0) -> bool:
        """Business rule: is this detection significant enough to warrant treatment?"""
        return self.percentage >= threshold
    
    def needs_treatment(self) -> bool:
        """Business rule: does this column need treatment?"""
        return self.count > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "count": self.count,
            "percentage": self.percentage,
        }
        result.update(self.details)
        return result


@dataclass
class DetectionResult:
    """
    Domain model for overall detection results.
    Aggregates column results with computed properties.
    """
    treatment_type: str
    detected: bool
    columns: Dict[str, ColumnDetectionResult] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_issues(self) -> int:
        """Total count of issues across all columns."""
        return sum(col.count for col in self.columns.values())
    
    @property
    def affected_column_count(self) -> int:
        """Number of columns with detected issues."""
        return len([col for col in self.columns.values() if col.needs_treatment()])
    
    @property
    def affected_columns(self) -> List[str]:
        """List of column names that need treatment."""
        return [name for name, col in self.columns.items() if col.needs_treatment()]
    
    def get_column(self, column_name: str) -> Optional[ColumnDetectionResult]:
        """Safely get column result."""
        return self.columns.get(column_name)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization (backward compatible)."""
        total_key = f"total_{self.treatment_type.replace('_values', '')}"
        if self.treatment_type == "outliers":
            total_key = "total_outliers"
        elif self.treatment_type == "missing_values":
            total_key = "total_missing"
        
        result = {
            "detected": self.detected,
            "columns": {name: col.to_dict() for name, col in self.columns.items()},
            total_key: self.total_issues,
        }
        result.update(self.metadata)
        return result


@dataclass
class ColumnStatistics:
    """
    Domain model for comprehensive column statistics.
    Encapsulates statistical data with recommendation logic.
    """
    column_name: str
    column_type: str  # 'Numerical' or 'Categorical'
    total_observations: int
    missing_count: int
    missing_percentage: float
    distinct_value_count: int
    stats: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_numeric(self) -> bool:
        """Check if column is numeric type."""
        return self.column_type.lower() == "numerical"
    
    @property
    def is_categorical(self) -> bool:
        """Check if column is categorical type."""
        return self.column_type.lower() == "categorical"
    
    @property
    def skewness(self) -> Optional[float]:
        """Get skewness if available."""
        return self.stats.get('skewness')
    
    @property
    def has_high_missing(self) -> bool:
        """Business rule: >80% missing is considered high."""
        return self.missing_percentage > 80
    
    @property
    def has_moderate_missing(self) -> bool:
        """Business rule: 10-80% missing is moderate."""
        return 10 <= self.missing_percentage <= 80
    
    @property
    def has_low_missing(self) -> bool:
        """Business rule: <10% missing is low."""
        return self.missing_percentage < 10
    
    def get_stat(self, key: str, default: Any = None) -> Any:
        """Safely get a statistic value."""
        return self.stats.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "variable": self.column_name,
            "type": self.column_type,
            "total_observations": self.total_observations,
            "missing_count": self.missing_count,
            "missing_percentage": self.missing_percentage,
            "distinct_value_count": self.distinct_value_count,
        }
        result.update(self.stats)
        return result


# =============================================================================
# CONCRETE BOUND CALCULATOR STRATEGIES (Strategy Pattern)
# =============================================================================

class IQRBoundCalculator(BaseBoundCalculator):
    """IQR-based outlier bound calculation strategy."""
    
    def get_name(self) -> str:
        return "iqr"
    
    def calculate_bounds(
        self, 
        data: pd.Series, 
        config: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[float], Optional[float]]:
        config = config or {}
        Q1 = data.quantile(0.25)
        Q3 = data.quantile(0.75)
        IQR = Q3 - Q1
        if IQR == 0:
            return None, None
        multiplier = config.get("multiplier", 1.5)
        lower = Q1 - multiplier * IQR
        upper = Q3 + multiplier * IQR
        return float(lower), float(upper)


class ZScoreBoundCalculator(BaseBoundCalculator):
    """Z-Score based outlier bound calculation strategy."""
    
    def get_name(self) -> str:
        return "zscore"
    
    def calculate_bounds(
        self, 
        data: pd.Series, 
        config: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[float], Optional[float]]:
        config = config or {}
        threshold = config.get("threshold", 3.0)
        mean = data.mean()
        std = data.std()
        if std == 0:
            return None, None
        lower = mean - threshold * std
        upper = mean + threshold * std
        return float(lower), float(upper)


class PercentileBoundCalculator(BaseBoundCalculator):
    """Percentile-based outlier bound calculation strategy."""
    
    def get_name(self) -> str:
        return "percentile"
    
    def calculate_bounds(
        self, 
        data: pd.Series, 
        config: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[float], Optional[float]]:
        config = config or {}
        lower_pct = config.get("lower_percentile", 1)
        upper_pct = config.get("upper_percentile", 99)
        lower = data.quantile(lower_pct / 100)
        upper = data.quantile(upper_pct / 100)
        return float(lower), float(upper)


# =============================================================================
# BOUND CALCULATOR REGISTRY - Open for extension
# =============================================================================

class BoundCalculatorRegistry:
    """
    Registry for outlier bound calculation strategies.
    Supports Open/Closed principle - add new strategies without modifying existing code.
    """
    
    def __init__(self):
        self._calculators: Dict[str, BaseBoundCalculator] = {}
        self._register_defaults()
    
    def _register_defaults(self):
        """Register default bound calculators."""
        self.register(IQRBoundCalculator())
        self.register(ZScoreBoundCalculator())
        self.register(PercentileBoundCalculator())
    
    def register(self, calculator: BaseBoundCalculator):
        """Register a new bound calculator."""
        self._calculators[calculator.get_name()] = calculator
    
    def get(self, name: str) -> Optional[BaseBoundCalculator]:
        """Get calculator by name."""
        return self._calculators.get(name.lower())
    
    def get_or_default(self, name: str, default: str = "iqr") -> BaseBoundCalculator:
        """Get calculator by name, falling back to default."""
        calculator = self.get(name)
        if calculator is None:
            calculator = self.get(default)
        return calculator
    
    def available_methods(self) -> List[str]:
        """List all available methods."""
        return list(self._calculators.keys())


# =============================================================================
# CONCRETE RECOMMENDER IMPLEMENTATIONS
# =============================================================================

class DefaultOutlierRecommender(BaseTreatmentRecommender):
    """
    Rule-based outlier treatment recommender based on skewness.
    
    Logic:
    - Low skewness (|skew| < 0.5): Z-Score method
    - Moderate skewness (0.5 <= |skew| < 1.0): IQR method  
    - High skewness (|skew| >= 1.0): Percentile capping
    """
    
    def recommend(
        self, 
        column_stats: Dict[str, Any], 
        detection_result: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        skewness = column_stats.get('skewness', 0)
        abs_skew = abs(skewness) if skewness is not None else 0
        
        if abs_skew < 0.5:
            return "Z-Score", "Z > 3 or Z < -3"
        elif abs_skew < 1.0:
            return "IQR", "< Q1 - 1.5*IQR or > Q3 + 1.5*IQR"
        else:
            return "Percentile", "< P1 or > P99"
    
    def recommend_detailed(
        self, 
        skewness: float, 
        sample_weight: Optional[float] = None
    ) -> Tuple[str, str, str]:
        """
        Detailed recommendation with method, criteria, and treatment.
        """
        abs_skew = abs(skewness) if skewness is not None else 0
        
        if abs_skew < 0.5:
            return "Z-Score", "Z > 3 or Z < -3", "Winsorize to Z = ±3"
        elif abs_skew < 1.0:
            return "IQR", "< Q1 - 1.5*IQR or > Q3 + 1.5*IQR", "Cap at IQR bounds"
        else:
            return "Percentile", "< P1 or > P99", "Cap at P1/P99"


class DefaultMissingRecommender(BaseTreatmentRecommender):
    """
    Rule-based missing value treatment recommender.
    
    Logic (based on % missing and column type):
    - 0-5% (Low): Numeric (Mean for symmetric, Median for skewed), Categorical (Mode)
    - 5-10% (Low-Moderate): Numeric (Median), Categorical (Mode)
    - 10-80% (Moderate): Numeric (Median), Categorical (Mode)
    - >80% (Very High): Drop for both
    """
    
    def recommend(
        self, 
        column_stats: Dict[str, Any], 
        detection_result: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        missing_pct = column_stats.get('missing_percentage', 0)
        col_type = column_stats.get('type', 'Unknown')
        skewness = column_stats.get('skewness')
        
        if missing_pct > 80:
            return "Drop Column", "Very high missing percentage (>80%) - column should be dropped"
        
        if col_type.lower() == "numerical":
            if missing_pct <= 5:
                if skewness is not None and abs(skewness) < 0.5:
                    return "Mean", "Low missing % (0-5%), symmetric distribution"
                else:
                    return "Median", "Low missing % (0-5%), skewed distribution"
            elif missing_pct <= 10:
                return "Median", "Low-Moderate missing % (5-10%)"
            else:
                return "Median", "Moderate missing % (10-80%)"
        else:
            severity = 'Low' if missing_pct <= 5 else 'Low-Moderate' if missing_pct <= 10 else 'Moderate'
            return "Mode", f"{severity} missing %"


# =============================================================================
# SINGLETON REGISTRIES - Pre-initialized for module-level access
# =============================================================================

bound_calculator_registry = BoundCalculatorRegistry()


# =============================================================================
# DATA QUALITY CONFIGURATION - Centralized settings with validation
# =============================================================================

@dataclass
class DataQualityConfig:
    """
    Centralized configuration for Data Quality operations.
    Loads from settings with validation and defaults.
    """
    # Outlier detection thresholds
    iqr_multiplier: float = field(default_factory=lambda: settings.DQ_OUTLIER_IQR_MULTIPLIER)
    zscore_threshold: float = field(default_factory=lambda: settings.DQ_OUTLIER_ZSCORE_THRESHOLD)
    percentile_lower: int = field(default_factory=lambda: settings.DQ_OUTLIER_PERCENTILE_LOWER)
    percentile_upper: int = field(default_factory=lambda: settings.DQ_OUTLIER_PERCENTILE_UPPER)
    
    # Missing value thresholds
    missing_high_threshold: float = field(default_factory=lambda: settings.DQ_MISSING_HIGH_THRESHOLD)
    missing_moderate_threshold: float = field(default_factory=lambda: settings.DQ_MISSING_MODERATE_THRESHOLD)
    
    # Detection settings
    significance_threshold: float = field(default_factory=lambda: settings.DQ_DETECTION_SIGNIFICANCE_THRESHOLD)
    default_outlier_method: str = field(default_factory=lambda: settings.DQ_DEFAULT_OUTLIER_METHOD)
    
    # Logging settings
    enable_detailed_logging: bool = field(default_factory=lambda: settings.DQ_ENABLE_DETAILED_LOGGING)
    
    def __post_init__(self):
        """Validate configuration values."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate configuration values and raise ConfigurationError if invalid."""
        if self.iqr_multiplier <= 0:
            raise ConfigurationError(
                f"IQR multiplier must be positive, got {self.iqr_multiplier}",
                config_key="DQ_OUTLIER_IQR_MULTIPLIER"
            )
        if self.zscore_threshold <= 0:
            raise ConfigurationError(
                f"Z-score threshold must be positive, got {self.zscore_threshold}",
                config_key="DQ_OUTLIER_ZSCORE_THRESHOLD"
            )
        if not (0 <= self.percentile_lower < self.percentile_upper <= 100):
            raise ConfigurationError(
                f"Percentile bounds invalid: lower={self.percentile_lower}, upper={self.percentile_upper}",
                config_key="DQ_OUTLIER_PERCENTILE_*"
            )
        if not (0 < self.missing_high_threshold <= 100):
            raise ConfigurationError(
                f"Missing high threshold must be 0-100, got {self.missing_high_threshold}",
                config_key="DQ_MISSING_HIGH_THRESHOLD"
            )
        if self.default_outlier_method not in ["iqr", "zscore", "percentile"]:
            raise ConfigurationError(
                f"Invalid default outlier method: {self.default_outlier_method}",
                config_key="DQ_DEFAULT_OUTLIER_METHOD",
                details={"valid_methods": ["iqr", "zscore", "percentile"]}
            )
    
    def get_outlier_config(self, method: str = None) -> Dict[str, Any]:
        """Get configuration dict for outlier detection method."""
        method = method or self.default_outlier_method
        if method == "iqr":
            return {"multiplier": self.iqr_multiplier}
        elif method == "zscore":
            return {"threshold": self.zscore_threshold}
        elif method == "percentile":
            return {"lower_percentile": self.percentile_lower, "upper_percentile": self.percentile_upper}
        return {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for logging/serialization."""
        return {
            "iqr_multiplier": self.iqr_multiplier,
            "zscore_threshold": self.zscore_threshold,
            "percentile_lower": self.percentile_lower,
            "percentile_upper": self.percentile_upper,
            "missing_high_threshold": self.missing_high_threshold,
            "missing_moderate_threshold": self.missing_moderate_threshold,
            "significance_threshold": self.significance_threshold,
            "default_outlier_method": self.default_outlier_method,
            "enable_detailed_logging": self.enable_detailed_logging
        }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: _convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(_convert_numpy_types(item) for item in obj)
    else:
        return obj


class DataQualityDetector:
    """
    Deterministic data quality detector for Invalid Values, Special Values,
    Outliers, and Missing Values.
    
    Detection Methods:
    - Invalid Values: Template-based validation (values outside valid range/labels)
    - Special Values: Template-based detection (predefined special codes like -999, 9999)
    - Outliers: Statistical detection (IQR, Z-Score, Percentile methods)
    - Missing Values: Standard null/NaN detection
    
    Design Principles:
    - Composition over inheritance: Uses injected recommenders and bound calculators
    - Strategy Pattern: Pluggable outlier detection methods via registry
    - Dependency Inversion: Depends on abstractions (BaseTreatmentRecommender)
    """
    
    def __init__(
        self,
        outlier_recommender: Optional[BaseTreatmentRecommender] = None,
        missing_recommender: Optional[BaseTreatmentRecommender] = None,
        bound_calc_registry: Optional[BoundCalculatorRegistry] = None
    ):
        """
        Initialize detector with optional dependency injection.
        
        Args:
            outlier_recommender: Recommender for outlier treatments (default: DefaultOutlierRecommender)
            missing_recommender: Recommender for missing value treatments (default: DefaultMissingRecommender)
            bound_calc_registry: Registry for bound calculation strategies (default: global registry)
        """
        self.logger = get_logger(__name__)
        
        # Composition: inject dependencies or use defaults
        self._outlier_recommender = outlier_recommender or DefaultOutlierRecommender()
        self._missing_recommender = missing_recommender or DefaultMissingRecommender()
        self._bound_calculators = bound_calc_registry or bound_calculator_registry
        
        # Load configuration from centralized settings
        self._config = DataQualityConfig()
    
    def _validate_dataframe(self, df: pd.DataFrame, operation: str) -> None:
        """Validate DataFrame input for operations."""
        if df is None:
            raise ValidationError("DataFrame cannot be None", field="df")
        if not isinstance(df, pd.DataFrame):
            raise ValidationError(
                f"Expected pandas DataFrame, got {type(df).__name__}",
                field="df",
                expected="pd.DataFrame",
                actual=type(df).__name__
            )
        if df.empty:
            raise InsufficientDataError(
                f"DataFrame is empty - cannot perform {operation}",
                required=1,
                actual=0
            )
    
    def _validate_column_exists(self, df: pd.DataFrame, column: str) -> None:
        """Validate that a column exists in the DataFrame."""
        if column not in df.columns:
            raise ColumnNotFoundError(column, list(df.columns))
    
    # =========================================================================
    # INVALID VALUES DETECTION (Template Required)
    # =========================================================================
    
    @log_execution_time("detect_invalid_values")
    def detect_invalid_values(
        self,
        df: pd.DataFrame,
        template: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Detect invalid values based on template-defined valid ranges/labels.
        
        Template format expected:
        {
            "column_name": {
                "type": "Numerical" | "Categorical",
                "valid_range": [min, max],  # For numerical
                "valid_labels": ["A", "B", "C"]  # For categorical
            }
        }
        
        Returns:
            {
                "detected": True/False,
                "columns": {
                    "col_name": {
                        "invalid_count": int,
                        "invalid_percentage": float,
                        "invalid_values": list,
                        "valid_range": str or None,
                        "type": str
                    }
                },
                "total_invalid": int,
                "requires_template": True if no template provided
            }
        
        Raises:
            ValidationError: If DataFrame is invalid
            DetectionError: If detection fails unexpectedly
        """
        operation_id = f"invalid_{time.time()}"
        dq_logger.start_operation(operation_id, "detect_invalid_values", row_count=len(df) if df is not None else 0)
        
        try:
            self._validate_dataframe(df, "invalid values detection")
            
            result = {
                "detected": False,
                "columns": {},
                "total_invalid": 0,
                "requires_template": template is None
            }
            
            if template is None:
                dq_logger.info("Invalid values detection skipped - no template provided")
                dq_logger.end_operation(operation_id, "detect_invalid_values", success=True, skipped=True)
                return result
            
            total_invalid = 0
            
            for col_name, rules in template.items():
                if col_name not in df.columns:
                    dq_logger.warning(f"Column '{col_name}' from template not found in DataFrame", column=col_name)
                    continue
                
                col_data = df[col_name]
                col_type = rules.get("type", "").lower()
                invalid_mask = pd.Series([False] * len(df), index=df.index)
                
                if col_type == "numerical" and "valid_range" in rules:
                    valid_range = rules["valid_range"]
                    if len(valid_range) == 2:
                        min_val, max_val = valid_range
                        numeric_col = pd.to_numeric(col_data, errors='coerce')
                        invalid_mask = (
                            (numeric_col < min_val) | (numeric_col > max_val)
                        ) & ~numeric_col.isna()
                        
                elif col_type == "categorical" and "valid_labels" in rules:
                    valid_labels = set(str(v).lower() for v in rules["valid_labels"])
                    invalid_mask = ~col_data.astype(str).str.lower().isin(valid_labels) & ~col_data.isna()
                
                invalid_count = int(invalid_mask.sum())
                if invalid_count > 0:
                    result["detected"] = True
                    total_invalid += invalid_count
                    
                    invalid_values = col_data[invalid_mask].unique().tolist()[:10]
                    percentage = round((invalid_count / len(df)) * 100, 2)
                    
                    result["columns"][col_name] = {
                        "invalid_count": invalid_count,
                        "invalid_percentage": percentage,
                        "invalid_values": invalid_values,
                        "valid_range": str(rules.get("valid_range") or rules.get("valid_labels")),
                        "type": col_type
                    }
                    
                    dq_logger.log_detection(
                        "invalid_values", col_name, True, invalid_count, percentage,
                        valid_range=str(rules.get("valid_range") or rules.get("valid_labels"))
                    )
            
            result["total_invalid"] = total_invalid
            dq_logger.end_operation(
                operation_id, "detect_invalid_values", success=True,
                total_invalid=total_invalid, columns_checked=len(template)
            )
            return _convert_numpy_types(result)
            
        except (ValidationError, DataQualityError):
            dq_logger.end_operation(operation_id, "detect_invalid_values", success=False)
            raise
        except Exception as e:
            dq_logger.log_error("detect_invalid_values", e, {"template_columns": list(template.keys()) if template else []})
            dq_logger.end_operation(operation_id, "detect_invalid_values", success=False)
            raise DetectionError(
                f"Unexpected error during invalid values detection: {str(e)}",
                treatment_type="invalid_values",
                details={"original_error": str(e)}
            ) from e
    
    # =========================================================================
    # SPECIAL VALUES DETECTION (Template Required)
    # =========================================================================
    
    @log_execution_time("detect_special_values")
    def detect_special_values(
        self,
        df: pd.DataFrame,
        template: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Detect special values (placeholder codes) based on template.
        
        Template format expected:
        {
            "column_name": {
                "type": "Numerical" | "Categorical",
                "special_values": [-999, 9999, "NA", "Unknown"]
            }
        }
        
        Returns:
            {
                "detected": True/False,
                "columns": {
                    "col_name": {
                        "special_count": int,
                        "special_percentage": float,
                        "special_values_found": dict (value: count),
                        "type": str
                    }
                },
                "total_special": int,
                "requires_template": True if no template provided
            }
        
        Raises:
            ValidationError: If DataFrame is invalid
            DetectionError: If detection fails unexpectedly
        """
        operation_id = f"special_{time.time()}"
        dq_logger.start_operation(operation_id, "detect_special_values", row_count=len(df) if df is not None else 0)
        
        try:
            self._validate_dataframe(df, "special values detection")
            
            result = {
                "detected": False,
                "columns": {},
                "total_special": 0,
                "requires_template": template is None
            }
            
            if template is None:
                dq_logger.info("Special values detection skipped - no template provided")
                dq_logger.end_operation(operation_id, "detect_special_values", success=True, skipped=True)
                return result
            
            total_special = 0
            
            for col_name, rules in template.items():
                if col_name not in df.columns:
                    dq_logger.warning(f"Column '{col_name}' from template not found in DataFrame", column=col_name)
                    continue
                
                special_values = rules.get("special_values", [])
                if not special_values:
                    continue
                
                col_data = df[col_name]
                special_values_set = set()
                
                for sv in special_values:
                    if isinstance(sv, (int, float)):
                        special_values_set.add(sv)
                        special_values_set.add(str(sv))
                    else:
                        special_values_set.add(str(sv).lower())
                
                # P2.4: vectorized replacement for the per-row Python lambda.
                # The original three OR-branches collapse to two vectorized masks:
                #   1) raw value membership (handles numeric and exact string match).
                #      pandas .isin() uses equality semantics that match the
                #      original `x in special_values_set` test for both numeric
                #      and string special values, including the previously-explicit
                #      "isinstance(x, (int, float))" branch which was redundant.
                #   2) lowercased string-form membership (handles cells like
                #      "NA"/"NULL"/"None" matched by lowercase entries in the set).
                # The OR semantics, dtype handling, and NaN flagging behaviour
                # are identical to the original lambda.
                raw_mask = col_data.isin(special_values_set)
                str_lower_mask = col_data.astype(str).str.lower().isin(special_values_set)
                special_mask = raw_mask | str_lower_mask
                
                special_count = int(special_mask.sum())
                if special_count > 0:
                    result["detected"] = True
                    total_special += special_count
                    
                    special_values_found = col_data[special_mask].value_counts().to_dict()
                    special_values_found = {str(k): int(v) for k, v in list(special_values_found.items())[:10]}
                    percentage = round((special_count / len(df)) * 100, 2)
                    
                    result["columns"][col_name] = {
                        "special_count": special_count,
                        "special_percentage": percentage,
                        "special_values_found": special_values_found,
                        "type": rules.get("type", "unknown")
                    }
                    
                    dq_logger.log_detection(
                        "special_values", col_name, True, special_count, percentage,
                        special_values_found=list(special_values_found.keys())
                    )
            
            result["total_special"] = total_special
            dq_logger.end_operation(
                operation_id, "detect_special_values", success=True,
                total_special=total_special, columns_checked=len(template)
            )
            return _convert_numpy_types(result)
            
        except (ValidationError, DataQualityError):
            dq_logger.end_operation(operation_id, "detect_special_values", success=False)
            raise
        except Exception as e:
            dq_logger.log_error("detect_special_values", e, {"template_columns": list(template.keys()) if template else []})
            dq_logger.end_operation(operation_id, "detect_special_values", success=False)
            raise DetectionError(
                f"Unexpected error during special values detection: {str(e)}",
                treatment_type="special_values",
                details={"original_error": str(e)}
            ) from e
    
    # =========================================================================
    # OUTLIERS DETECTION (Statistical Methods)
    # =========================================================================
    
    @log_execution_time("detect_outliers")
    def detect_outliers(
        self,
        df: pd.DataFrame,
        method: str = None,
        template: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Detect outliers using statistical methods.
        
        Methods:
        - "iqr": Interquartile Range (Q1 - 1.5*IQR, Q3 + 1.5*IQR)
        - "zscore": Z-Score (|z| > 3)
        - "percentile": Percentile capping (< P1 or > P99)
        
        Template format (optional - per-column method override):
        {
            "column_name": {
                "method": "iqr" | "zscore" | "percentile",
                "threshold": float (optional - for zscore)
            }
        }
        
        Returns:
            {
                "detected": True/False,
                "method": str,
                "columns": {
                    "col_name": {
                        "outlier_count": int,
                        "outlier_percentage": float,
                        "lower_bound": float,
                        "upper_bound": float,
                        "method_used": str,
                        "skewness": float
                    }
                },
                "total_outliers": int
            }
        
        Raises:
            ValidationError: If DataFrame is invalid
            ConfigurationError: If method is invalid
            DetectionError: If detection fails unexpectedly
        """
        # Use config default if method not specified
        method = method or self._config.default_outlier_method
        operation_id = f"outliers_{time.time()}"
        dq_logger.start_operation(
            operation_id, "detect_outliers", 
            row_count=len(df) if df is not None else 0,
            method=method
        )
        
        try:
            self._validate_dataframe(df, "outlier detection")
            
            # Validate method
            valid_methods = bound_calculator_registry.available_methods()
            if method.lower() not in valid_methods:
                raise ConfigurationError(
                    f"Invalid outlier detection method: {method}",
                    config_key="method",
                    details={"valid_methods": valid_methods}
                )
            
            result = {
                "detected": False,
                "method": method,
                "columns": {},
                "total_outliers": 0
            }
            
            if columns is None:
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            else:
                numeric_cols = [c for c in columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
            
            if not numeric_cols:
                dq_logger.info("No numeric columns found for outlier detection")
                dq_logger.end_operation(operation_id, "detect_outliers", success=True, skipped=True)
                return result
            
            total_outliers = 0
            
            for col in numeric_cols:
                col_data = df[col].dropna()
                
                if len(col_data) < 4:
                    dq_logger.debug(f"Skipping column '{col}' - insufficient data", column=col, data_count=len(col_data))
                    continue
                
                col_method = method
                col_config = self._config.get_outlier_config(method)
                
                if template and col in template:
                    col_method = template[col].get("method", method)
                    col_config.update(template.get(col, {}))
                
                lower_bound, upper_bound = self._calculate_outlier_bounds(
                    col_data, col_method, col_config
                )
                
                if lower_bound is None or upper_bound is None:
                    continue
                
                outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
                outlier_count = int(outlier_mask.sum())
                
                try:
                    skewness = float(col_data.skew())
                except Exception:
                    skewness = 0.0
                
                if outlier_count > 0:
                    result["detected"] = True
                    total_outliers += outlier_count
                    percentage = round((outlier_count / len(df)) * 100, 2)
                    
                    result["columns"][col] = {
                        "outlier_count": outlier_count,
                        "outlier_percentage": percentage,
                        "lower_bound": round(float(lower_bound), 4),
                        "upper_bound": round(float(upper_bound), 4),
                        "method_used": col_method,
                        "skewness": round(skewness, 4)
                    }
                    
                    if self._config.enable_detailed_logging:
                        dq_logger.log_detection(
                            "outliers", col, True, outlier_count, percentage,
                            method=col_method, lower_bound=lower_bound, upper_bound=upper_bound
                        )
            
            result["total_outliers"] = total_outliers
            dq_logger.end_operation(
                operation_id, "detect_outliers", success=True,
                total_outliers=total_outliers, method=method, columns_analyzed=len(numeric_cols)
            )
            return _convert_numpy_types(result)
            
        except (ValidationError, ConfigurationError, DataQualityError):
            dq_logger.end_operation(operation_id, "detect_outliers", success=False)
            raise
        except Exception as e:
            dq_logger.log_error("detect_outliers", e, {"method": method, "columns": columns})
            dq_logger.end_operation(operation_id, "detect_outliers", success=False)
            raise DetectionError(
                f"Unexpected error during outlier detection: {str(e)}",
                treatment_type="outliers",
                details={"method": method, "original_error": str(e)}
            ) from e
    
    def _calculate_outlier_bounds(
        self,
        data: pd.Series,
        method: str,
        config: Dict[str, Any] = None
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate outlier bounds using Strategy Pattern.
        
        Delegates to registered bound calculators for extensibility.
        New methods can be added without modifying this code.
        """
        config = config or {}
        
        # Use strategy pattern via registry
        calculator = bound_calculator_registry.get_or_default(method, "iqr")
        
        if calculator is None:
            self.logger.warning(f"No calculator found for method: {method}, defaulting to IQR")
            calculator = bound_calculator_registry.get("iqr")
        
        try:
            return calculator.calculate_bounds(data, config)
        except Exception as e:
            self.logger.error(f"Error calculating bounds with {method}: {e}")
            return None, None
    
    def recommend_outlier_treatment(
        self,
        col_name: str,
        detection_result: Dict[str, Any]
    ) -> str:
        """
        Recommend outlier treatment based on skewness and distribution.
        
        Uses injected recommender for flexibility (Dependency Inversion Principle).
        Used when: Auto QC OR Manual QC without template AND without UI dropdown selection.
        """
        col_info = detection_result.get("columns", {}).get(col_name, {})
        skewness = col_info.get("skewness", 0)
        
        # Delegate to recommender (composition)
        method, _ = self._outlier_recommender.recommend({"skewness": skewness}, col_info)
        
        # Format for display
        if method == "Z-Score":
            return "winsorize (IQR bounds)"
        elif method == "IQR":
            return "cap at 95th/5th percentile"
        else:
            return f"cap at 99th/1st percentile (high skewness: {skewness:.2f})"
    
    # =========================================================================
    # MISSING VALUES DETECTION
    # =========================================================================
    
    @log_execution_time("detect_missing_values")
    def detect_missing_values(
        self,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Detect missing values (NaN, None, empty strings).
        
        Returns:
            {
                "detected": True/False,
                "columns": {
                    "col_name": {
                        "missing_count": int,
                        "missing_percentage": float,
                        "dtype": str,
                        "non_null_count": int
                    }
                },
                "total_missing": int,
                "total_cells": int
            }
        
        Raises:
            ValidationError: If DataFrame is invalid
            DetectionError: If detection fails unexpectedly
        """
        operation_id = f"missing_{time.time()}"
        dq_logger.start_operation(operation_id, "detect_missing_values", row_count=len(df) if df is not None else 0)
        
        try:
            self._validate_dataframe(df, "missing values detection")
            
            result = {
                "detected": False,
                "columns": {},
                "total_missing": 0,
                "total_cells": len(df) * len(df.columns)
            }
            
            check_cols = columns if columns else df.columns.tolist()
            total_missing = 0
            
            for col in check_cols:
                if col not in df.columns:
                    continue
                
                missing_mask = df[col].isna()
                if df[col].dtype == 'object':
                    missing_mask = missing_mask | (df[col].astype(str).str.strip() == '')
                
                missing_count = int(missing_mask.sum())
                
                if missing_count > 0:
                    result["detected"] = True
                    total_missing += missing_count
                    percentage = round((missing_count / len(df)) * 100, 2)
                    
                    result["columns"][col] = {
                        "missing_count": missing_count,
                        "missing_percentage": percentage,
                        "dtype": str(df[col].dtype),
                        "non_null_count": int(len(df) - missing_count)
                    }
                    
                    if self._config.enable_detailed_logging:
                        dq_logger.log_detection(
                            "missing_values", col, True, missing_count, percentage,
                            dtype=str(df[col].dtype)
                        )
            
            result["total_missing"] = total_missing
            dq_logger.end_operation(
                operation_id, "detect_missing_values", success=True,
                total_missing=total_missing, columns_checked=len(check_cols)
            )
            return _convert_numpy_types(result)
            
        except (ValidationError, DataQualityError):
            dq_logger.end_operation(operation_id, "detect_missing_values", success=False)
            raise
        except Exception as e:
            dq_logger.log_error("detect_missing_values", e, {"columns": columns})
            dq_logger.end_operation(operation_id, "detect_missing_values", success=False)
            raise DetectionError(
                f"Unexpected error during missing values detection: {str(e)}",
                treatment_type="missing_values",
                details={"original_error": str(e)}
            ) from e
    
    # =========================================================================
    # COMPREHENSIVE STATISTICS COMPUTATION
    # =========================================================================
    
    def compute_comprehensive_stats(
        self,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
        weight_column: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compute comprehensive statistics for all columns including:
        - Total observations, missing count/percentage
        - For numeric: Min, Max, Mean, Median (P50), Mode, P1, P5, P25, P75, P95, P99
        - Std Deviation, Variance, Skewness
        - For categorical: Distinct value count, Mode, Top/Lowest category %
        
        Args:
            df: DataFrame to analyze
            columns: Optional list of columns to analyze (defaults to all)
            weight_column: Optional column name for sample weights
        
        Returns:
            Dictionary with column names as keys and stats dictionaries as values
        """
        check_cols = columns if columns else df.columns.tolist()
        stats_result = {}
        total_rows = len(df)
        
        for col in check_cols:
            if col not in df.columns or col == weight_column:
                continue
            
            col_data = df[col]
            missing_mask = col_data.isna()
            if col_data.dtype == 'object':
                missing_mask = missing_mask | (col_data.astype(str).str.strip() == '')
            
            missing_count = int(missing_mask.sum())
            missing_pct = round((missing_count / total_rows) * 100, 2) if total_rows > 0 else 0
            non_null_data = col_data.dropna()
            
            # Determine column type
            is_numeric = pd.api.types.is_numeric_dtype(col_data)
            
            if is_numeric:
                # Numeric column statistics
                stats = {
                    "variable": col,
                    "type": "Numerical",
                    "total_observations": total_rows,
                    "missing_count": missing_count,
                    "missing_percentage": missing_pct,
                    "distinct_value_count": int(non_null_data.nunique()),
                }
                
                if len(non_null_data) > 0:
                    stats.update({
                        "min": round(float(non_null_data.min()), 4),
                        "max": round(float(non_null_data.max()), 4),
                        "mean": round(float(non_null_data.mean()), 4),
                        "median": round(float(non_null_data.median()), 4),
                        "p1": round(float(non_null_data.quantile(0.01)), 4),
                        "p5": round(float(non_null_data.quantile(0.05)), 4),
                        "p25": round(float(non_null_data.quantile(0.25)), 4),
                        "p50": round(float(non_null_data.quantile(0.50)), 4),
                        "p75": round(float(non_null_data.quantile(0.75)), 4),
                        "p95": round(float(non_null_data.quantile(0.95)), 4),
                        "p99": round(float(non_null_data.quantile(0.99)), 4),
                        "std_deviation": round(float(non_null_data.std()), 4),
                        "variance": round(float(non_null_data.var()), 4),
                    })
                    
                    # Skewness
                    try:
                        stats["skewness"] = round(float(non_null_data.skew()), 4)
                    except Exception:
                        stats["skewness"] = 0.0
                    
                    # Mode (take first if multiple)
                    mode_result = non_null_data.mode()
                    stats["mode"] = round(float(mode_result.iloc[0]), 4) if len(mode_result) > 0 else None
                    
                    # Weighted missing percentage if weight column provided
                    if weight_column and weight_column in df.columns:
                        weights = df[weight_column].fillna(0)
                        total_weight = weights.sum()
                        missing_weight = weights[missing_mask].sum()
                        stats["weighted_missing_pct"] = round((missing_weight / total_weight) * 100, 2) if total_weight > 0 else 0
                        stats["sample_weight_sum"] = round(float(total_weight), 4)
                else:
                    # All values missing
                    stats.update({
                        "min": None, "max": None, "mean": None, "median": None,
                        "p1": None, "p5": None, "p25": None, "p50": None, 
                        "p75": None, "p95": None, "p99": None,
                        "std_deviation": None, "variance": None, "skewness": None, "mode": None
                    })
            else:
                # Categorical column statistics
                stats = {
                    "variable": col,
                    "type": "Categorical",
                    "total_observations": total_rows,
                    "missing_count": missing_count,
                    "missing_percentage": missing_pct,
                    "distinct_value_count": int(non_null_data.nunique()),
                }
                
                if len(non_null_data) > 0:
                    value_counts = non_null_data.value_counts()
                    total_non_null = len(non_null_data)
                    
                    # Mode
                    stats["mode"] = str(value_counts.index[0]) if len(value_counts) > 0 else None
                    
                    # Top category percentage
                    stats["top_category_pct"] = round((value_counts.iloc[0] / total_non_null) * 100, 2) if len(value_counts) > 0 else 0
                    
                    # Lowest category percentage
                    stats["lowest_category_pct"] = round((value_counts.iloc[-1] / total_non_null) * 100, 2) if len(value_counts) > 0 else 0
                    
                    # Weighted missing percentage if weight column provided
                    if weight_column and weight_column in df.columns:
                        weights = df[weight_column].fillna(0)
                        total_weight = weights.sum()
                        missing_weight = weights[missing_mask].sum()
                        stats["weighted_missing_pct"] = round((missing_weight / total_weight) * 100, 2) if total_weight > 0 else 0
                else:
                    stats.update({
                        "mode": None,
                        "top_category_pct": None,
                        "lowest_category_pct": None
                    })
            
            stats_result[col] = stats
        
        return _convert_numpy_types(stats_result)
    
    def recommend_missing_treatment_detailed(
        self,
        missing_pct: float,
        col_type: str,
        skewness: Optional[float] = None
    ) -> Tuple[str, str]:
        """
        Recommend missing value treatment based on % missing and column type.
        
        Delegates to the injected missing value recommender (Dependency Inversion).
        
        Returns:
            Tuple of (recommended_action, reason)
        """
        # Build column stats for recommender
        column_stats = {
            "missing_percentage": missing_pct,
            "type": col_type,
            "skewness": skewness
        }
        
        # Delegate to recommender (composition)
        return self._missing_recommender.recommend(column_stats, {})
    
    def recommend_outlier_treatment_detailed(
        self,
        skewness: float,
        sample_weight: Optional[float] = None
    ) -> Tuple[str, str, str]:
        """
        Recommend outlier identification method, criteria, and treatment based on skewness.
        
        Delegates to the injected outlier recommender (Dependency Inversion).
        
        Returns:
            Tuple of (method, criteria, treatment)
        """
        # Use the recommender's detailed method if available (duck typing)
        if hasattr(self._outlier_recommender, 'recommend_detailed'):
            return self._outlier_recommender.recommend_detailed(skewness, sample_weight)
        
        # Fallback to basic recommend and construct detailed response
        method, criteria = self._outlier_recommender.recommend({"skewness": skewness}, {})
        treatment_map = {
            "Z-Score": "Winsorize to Z = ±3",
            "IQR": "Cap at IQR bounds",
            "Percentile": "Cap at P1/P99"
        }
        treatment = treatment_map.get(method, "Cap at bounds")
        return method, criteria, treatment
    
    def recommend_missing_treatment(
        self,
        df: pd.DataFrame,
        col_name: str,
        template: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Recommend missing value treatment based on column type and distribution.
        
        Priority:
        1. Template (if provided)
        2. AI Recommendation based on dtype and skewness
        
        Returns treatment string.
        """
        if template and col_name in template:
            return template[col_name].get("imputation_method", "median imputation")
        
        if col_name not in df.columns:
            return "mode imputation"
        
        col = df[col_name]
        dtype = col.dtype
        
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return "forward fill then backward fill"
        
        if pd.api.types.is_numeric_dtype(dtype):
            try:
                skewness = col.dropna().skew()
                if abs(skewness) < 1.0:
                    return "mean imputation"
                else:
                    return "median imputation (skewed distribution)"
            except Exception:
                return "median imputation"
        
        if dtype == 'object' or pd.api.types.is_categorical_dtype(dtype):
            return "mode imputation"
        
        return "drop rows"
    
    # =========================================================================
    # UNIFIED DETECTION METHOD
    # =========================================================================
    
    def run_detection(
        self,
        df: pd.DataFrame,
        treatment_type: str,
        template: Optional[Dict[str, Any]] = None,
        method: str = None,
        columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Unified detection method that routes to specific detector.
        
        Args:
            df: DataFrame to analyze
            treatment_type: One of "invalid_values", "special_values", "outliers", "missing_values"
            template: Optional template for detection rules
            method: Method for outlier detection ("iqr", "zscore", "percentile")
            columns: Optional list of columns to check
        
        Returns:
            Detection result dictionary specific to treatment type
        """
        if treatment_type == "invalid_values":
            return self.detect_invalid_values(df, template)
        elif treatment_type == "special_values":
            return self.detect_special_values(df, template)
        elif treatment_type == "outliers":
            return self.detect_outliers(df, method or "iqr", template, columns)
        elif treatment_type == "missing_values":
            return self.detect_missing_values(df, columns)
        else:
            raise ValueError(f"Unknown treatment type: {treatment_type}")
    
    # =========================================================================
    # TEMPLATE PARSING UTILITIES
    # =========================================================================
    
    def parse_uploaded_template(
        self,
        file_content: str,
        template_type: str
    ) -> Dict[str, Any]:
        """
        Parse uploaded CSV/Excel template into detection rules.
        
        Expected CSV columns:
        - invalid_values: Var Name, Type, Valid Range / Valid Labels
        - special_values: Var Name, Type, Special Values
        - outliers: Var Name, Type, Choose Detection Method
        - missing_values: Var Name, Type, Choose Imputation Method
        
        Returns parsed template dictionary.
        """
        import io
        
        try:
            if file_content.strip().startswith('{'):
                import json
                return json.loads(file_content)
            
            df_template = pd.read_csv(io.StringIO(file_content))
            
            result = {}
            
            for _, row in df_template.iterrows():
                var_name = str(row.iloc[0]).strip()
                if not var_name or var_name.lower() == 'nan':
                    continue
                
                var_type = str(row.iloc[1]).strip().lower() if len(row) > 1 else "unknown"
                value_col = row.iloc[2] if len(row) > 2 else None
                
                if template_type == "invalid_values":
                    if var_type == "numerical" and value_col:
                        try:
                            range_parts = str(value_col).replace('[', '').replace(']', '').split(',')
                            if len(range_parts) == 2:
                                result[var_name] = {
                                    "type": "numerical",
                                    "valid_range": [float(range_parts[0]), float(range_parts[1])]
                                }
                        except Exception:
                            pass
                    elif var_type == "categorical" and value_col:
                        labels = [v.strip() for v in str(value_col).split(',')]
                        result[var_name] = {
                            "type": "categorical",
                            "valid_labels": labels
                        }
                
                elif template_type == "special_values":
                    if value_col:
                        special_vals = []
                        for v in str(value_col).split(','):
                            v = v.strip()
                            try:
                                special_vals.append(float(v) if '.' in v else int(v))
                            except ValueError:
                                special_vals.append(v)
                        result[var_name] = {
                            "type": var_type,
                            "special_values": special_vals
                        }
                
                elif template_type == "outliers":
                    method_map = {
                        "z-score": "zscore",
                        "zscore": "zscore",
                        "iqr": "iqr",
                        "iqr (interquartile range)": "iqr",
                        "percentile capping": "percentile",
                        "percentile": "percentile"
                    }
                    if value_col:
                        method = method_map.get(str(value_col).lower().strip(), "iqr")
                        result[var_name] = {
                            "type": var_type,
                            "method": method
                        }
                
                elif template_type == "missing_values":
                    if value_col:
                        result[var_name] = {
                            "type": var_type,
                            "imputation_method": str(value_col).strip()
                        }
            
            self.logger.info(f"Parsed {template_type} template with {len(result)} columns")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to parse template: {e}")
            return {}


data_quality_detector = DataQualityDetector()

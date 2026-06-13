"""
Unit tests for DataQualityDetector and related components.

Tests cover:
- Detection methods (invalid values, special values, outliers, missing values)
- Bound calculation strategies (IQR, Z-Score, Percentile)
- Treatment recommenders
- Domain models (dataclasses)
- Configuration validation
- Exception handling
"""

import pytest
import pandas as pd
import numpy as np
from typing import Dict, Any

from app.services.data_quality_detector import (
    DataQualityDetector,
    DataQualityConfig,
    IQRBoundCalculator,
    ZScoreBoundCalculator,
    PercentileBoundCalculator,
    BoundCalculatorRegistry,
    DefaultOutlierRecommender,
    DefaultMissingRecommender,
    ColumnDetectionResult,
    DetectionResult,
    ColumnStatistics,
    DataQualityError,
    DetectionError,
    ValidationError,
    ConfigurationError,
    ColumnNotFoundError,
    InsufficientDataError,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_numeric_df():
    """Create a sample DataFrame with numeric data including outliers."""
    np.random.seed(42)
    normal_data = np.random.normal(50, 10, 95)
    outliers = np.array([150, 160, -50, 200, 250])
    data = np.concatenate([normal_data, outliers])
    return pd.DataFrame({
        'numeric_col': data,
        'numeric_col_2': np.random.uniform(0, 100, 100)
    })


@pytest.fixture
def sample_mixed_df():
    """Create a sample DataFrame with mixed data types."""
    return pd.DataFrame({
        'numeric': [1, 2, 3, np.nan, 5, 6, 7, 8, 9, 10],
        'categorical': ['A', 'B', 'C', None, 'A', 'B', '', 'C', 'A', 'D'],
        'with_special': [1, 2, -999, 9999, 5, -999, 7, 8, 9999, 10],
        'invalid_numeric': [10, 20, 150, 40, 50, -10, 70, 80, 90, 100],
    })


@pytest.fixture
def invalid_values_template():
    """Template for invalid values detection."""
    return {
        'invalid_numeric': {
            'type': 'Numerical',
            'valid_range': [0, 100]
        }
    }


@pytest.fixture
def special_values_template():
    """Template for special values detection."""
    return {
        'with_special': {
            'type': 'Numerical',
            'special_values': [-999, 9999]
        }
    }


@pytest.fixture
def detector():
    """Create a DataQualityDetector instance."""
    return DataQualityDetector()


# =============================================================================
# BOUND CALCULATOR STRATEGY TESTS
# =============================================================================

class TestIQRBoundCalculator:
    """Tests for IQR-based bound calculation."""
    
    def test_get_name(self):
        calc = IQRBoundCalculator()
        assert calc.get_name() == "iqr"
    
    def test_calculate_bounds_default_multiplier(self):
        data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        calc = IQRBoundCalculator()
        lower, upper = calc.calculate_bounds(data)
        
        assert lower is not None
        assert upper is not None
        assert lower < upper
    
    def test_calculate_bounds_custom_multiplier(self):
        data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        calc = IQRBoundCalculator()
        
        lower_default, upper_default = calc.calculate_bounds(data, {"multiplier": 1.5})
        lower_wide, upper_wide = calc.calculate_bounds(data, {"multiplier": 3.0})
        
        assert lower_wide < lower_default
        assert upper_wide > upper_default
    
    def test_calculate_bounds_zero_iqr(self):
        """When all values are the same, IQR is 0."""
        data = pd.Series([5, 5, 5, 5, 5])
        calc = IQRBoundCalculator()
        lower, upper = calc.calculate_bounds(data)
        
        assert lower is None
        assert upper is None


class TestZScoreBoundCalculator:
    """Tests for Z-Score based bound calculation."""
    
    def test_get_name(self):
        calc = ZScoreBoundCalculator()
        assert calc.get_name() == "zscore"
    
    def test_calculate_bounds_default_threshold(self):
        data = pd.Series(np.random.normal(0, 1, 100))
        calc = ZScoreBoundCalculator()
        lower, upper = calc.calculate_bounds(data)
        
        assert lower is not None
        assert upper is not None
        assert lower < 0 < upper  # For normalized data centered at 0
    
    def test_calculate_bounds_custom_threshold(self):
        data = pd.Series(np.random.normal(50, 10, 100))
        calc = ZScoreBoundCalculator()
        
        lower_tight, upper_tight = calc.calculate_bounds(data, {"threshold": 2.0})
        lower_wide, upper_wide = calc.calculate_bounds(data, {"threshold": 3.0})
        
        assert lower_wide < lower_tight
        assert upper_wide > upper_tight
    
    def test_calculate_bounds_zero_std(self):
        """When all values are the same, std is 0."""
        data = pd.Series([5, 5, 5, 5, 5])
        calc = ZScoreBoundCalculator()
        lower, upper = calc.calculate_bounds(data)
        
        assert lower is None
        assert upper is None


class TestPercentileBoundCalculator:
    """Tests for Percentile-based bound calculation."""
    
    def test_get_name(self):
        calc = PercentileBoundCalculator()
        assert calc.get_name() == "percentile"
    
    def test_calculate_bounds_default_percentiles(self):
        data = pd.Series(range(1, 101))  # 1 to 100
        calc = PercentileBoundCalculator()
        lower, upper = calc.calculate_bounds(data)
        
        assert lower is not None
        assert upper is not None
        assert lower == pytest.approx(1.99, abs=0.1)  # P1
        assert upper == pytest.approx(99.01, abs=0.1)  # P99
    
    def test_calculate_bounds_custom_percentiles(self):
        data = pd.Series(range(1, 101))
        calc = PercentileBoundCalculator()
        lower, upper = calc.calculate_bounds(data, {"lower_percentile": 5, "upper_percentile": 95})
        
        assert lower == pytest.approx(5.95, abs=0.5)
        assert upper == pytest.approx(95.05, abs=0.5)


class TestBoundCalculatorRegistry:
    """Tests for BoundCalculatorRegistry."""
    
    def test_default_calculators_registered(self):
        registry = BoundCalculatorRegistry()
        assert "iqr" in registry.available_methods()
        assert "zscore" in registry.available_methods()
        assert "percentile" in registry.available_methods()
    
    def test_get_calculator(self):
        registry = BoundCalculatorRegistry()
        calc = registry.get("iqr")
        assert isinstance(calc, IQRBoundCalculator)
    
    def test_get_nonexistent_returns_none(self):
        registry = BoundCalculatorRegistry()
        calc = registry.get("nonexistent")
        assert calc is None
    
    def test_get_or_default(self):
        registry = BoundCalculatorRegistry()
        calc = registry.get_or_default("nonexistent", "iqr")
        assert isinstance(calc, IQRBoundCalculator)


# =============================================================================
# RECOMMENDER TESTS
# =============================================================================

class TestDefaultOutlierRecommender:
    """Tests for DefaultOutlierRecommender."""
    
    def test_recommend_low_skewness(self):
        recommender = DefaultOutlierRecommender()
        method, criteria = recommender.recommend({"skewness": 0.3})
        assert method == "Z-Score"
    
    def test_recommend_moderate_skewness(self):
        recommender = DefaultOutlierRecommender()
        method, criteria = recommender.recommend({"skewness": 0.7})
        assert method == "IQR"
    
    def test_recommend_high_skewness(self):
        recommender = DefaultOutlierRecommender()
        method, criteria = recommender.recommend({"skewness": 1.5})
        assert method == "Percentile"
    
    def test_recommend_none_skewness(self):
        recommender = DefaultOutlierRecommender()
        method, criteria = recommender.recommend({"skewness": None})
        assert method == "Z-Score"  # abs(0) < 0.5


class TestDefaultMissingRecommender:
    """Tests for DefaultMissingRecommender."""
    
    def test_recommend_high_missing(self):
        recommender = DefaultMissingRecommender()
        method, reason = recommender.recommend({"missing_percentage": 85, "type": "Numerical"})
        assert method == "Drop"
    
    def test_recommend_low_missing_symmetric(self):
        recommender = DefaultMissingRecommender()
        method, reason = recommender.recommend({
            "missing_percentage": 3, 
            "type": "Numerical",
            "skewness": 0.2
        })
        assert method == "Mean"
    
    def test_recommend_low_missing_skewed(self):
        recommender = DefaultMissingRecommender()
        method, reason = recommender.recommend({
            "missing_percentage": 3, 
            "type": "Numerical",
            "skewness": 1.5
        })
        assert method == "Median"
    
    def test_recommend_categorical(self):
        recommender = DefaultMissingRecommender()
        method, reason = recommender.recommend({
            "missing_percentage": 15, 
            "type": "Categorical"
        })
        assert method == "Mode"


# =============================================================================
# DOMAIN MODEL TESTS
# =============================================================================

class TestColumnDetectionResult:
    """Tests for ColumnDetectionResult dataclass."""
    
    def test_is_significant_above_threshold(self):
        result = ColumnDetectionResult("col1", 50, 5.0)
        assert result.is_significant(threshold=1.0) is True
    
    def test_is_significant_below_threshold(self):
        result = ColumnDetectionResult("col1", 5, 0.5)
        assert result.is_significant(threshold=1.0) is False
    
    def test_needs_treatment(self):
        result = ColumnDetectionResult("col1", 10, 1.0)
        assert result.needs_treatment() is True
        
        result_none = ColumnDetectionResult("col2", 0, 0.0)
        assert result_none.needs_treatment() is False
    
    def test_to_dict(self):
        result = ColumnDetectionResult("col1", 10, 1.0, {"extra": "value"})
        d = result.to_dict()
        assert d["count"] == 10
        assert d["percentage"] == 1.0
        assert d["extra"] == "value"


class TestDetectionResult:
    """Tests for DetectionResult dataclass."""
    
    def test_total_issues(self):
        columns = {
            "col1": ColumnDetectionResult("col1", 10, 1.0),
            "col2": ColumnDetectionResult("col2", 20, 2.0),
        }
        result = DetectionResult("outliers", True, columns)
        assert result.total_issues == 30
    
    def test_affected_column_count(self):
        columns = {
            "col1": ColumnDetectionResult("col1", 10, 1.0),
            "col2": ColumnDetectionResult("col2", 0, 0.0),
            "col3": ColumnDetectionResult("col3", 5, 0.5),
        }
        result = DetectionResult("outliers", True, columns)
        assert result.affected_column_count == 2
    
    def test_affected_columns(self):
        columns = {
            "col1": ColumnDetectionResult("col1", 10, 1.0),
            "col2": ColumnDetectionResult("col2", 0, 0.0),
        }
        result = DetectionResult("outliers", True, columns)
        assert result.affected_columns == ["col1"]


class TestColumnStatistics:
    """Tests for ColumnStatistics dataclass."""
    
    def test_is_numeric(self):
        stats = ColumnStatistics("col1", "Numerical", 100, 5, 5.0, 10)
        assert stats.is_numeric is True
        assert stats.is_categorical is False
    
    def test_missing_thresholds(self):
        high = ColumnStatistics("col1", "Numerical", 100, 85, 85.0, 10)
        assert high.has_high_missing is True
        
        moderate = ColumnStatistics("col2", "Numerical", 100, 50, 50.0, 10)
        assert moderate.has_moderate_missing is True
        
        low = ColumnStatistics("col3", "Numerical", 100, 5, 5.0, 10)
        assert low.has_low_missing is True


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================

class TestDataQualityConfig:
    """Tests for DataQualityConfig."""
    
    def test_default_values(self):
        config = DataQualityConfig()
        assert config.iqr_multiplier > 0
        assert config.zscore_threshold > 0
        assert 0 <= config.percentile_lower < config.percentile_upper <= 100
    
    def test_get_outlier_config_iqr(self):
        config = DataQualityConfig()
        outlier_config = config.get_outlier_config("iqr")
        assert "multiplier" in outlier_config
    
    def test_get_outlier_config_zscore(self):
        config = DataQualityConfig()
        outlier_config = config.get_outlier_config("zscore")
        assert "threshold" in outlier_config
    
    def test_get_outlier_config_percentile(self):
        config = DataQualityConfig()
        outlier_config = config.get_outlier_config("percentile")
        assert "lower_percentile" in outlier_config
        assert "upper_percentile" in outlier_config
    
    def test_to_dict(self):
        config = DataQualityConfig()
        d = config.to_dict()
        assert "iqr_multiplier" in d
        assert "default_outlier_method" in d


# =============================================================================
# EXCEPTION TESTS
# =============================================================================

class TestExceptions:
    """Tests for custom exceptions."""
    
    def test_data_quality_error_to_dict(self):
        error = DataQualityError("Test error", "test_op", {"key": "value"})
        d = error.to_dict()
        assert d["error_type"] == "DataQualityError"
        assert d["message"] == "Test error"
        assert d["operation"] == "test_op"
        assert d["details"]["key"] == "value"
    
    def test_detection_error(self):
        error = DetectionError("Detection failed", "outliers", "col1")
        assert error.treatment_type == "outliers"
        assert error.column == "col1"
    
    def test_validation_error(self):
        error = ValidationError("Invalid input", "df", "DataFrame", "None")
        assert error.field == "df"
    
    def test_column_not_found_error(self):
        error = ColumnNotFoundError("missing_col", ["col1", "col2"])
        assert error.column == "missing_col"
        assert "col1" in error.available_columns


# =============================================================================
# DATA QUALITY DETECTOR TESTS
# =============================================================================

class TestDataQualityDetector:
    """Tests for DataQualityDetector main class."""
    
    def test_detect_invalid_values_with_template(self, detector, sample_mixed_df, invalid_values_template):
        result = detector.detect_invalid_values(sample_mixed_df, invalid_values_template)
        
        assert result["detected"] is True
        assert "invalid_numeric" in result["columns"]
        assert result["columns"]["invalid_numeric"]["invalid_count"] > 0
    
    def test_detect_invalid_values_no_template(self, detector, sample_mixed_df):
        result = detector.detect_invalid_values(sample_mixed_df, None)
        
        assert result["requires_template"] is True
        assert result["detected"] is False
    
    def test_detect_special_values_with_template(self, detector, sample_mixed_df, special_values_template):
        result = detector.detect_special_values(sample_mixed_df, special_values_template)
        
        assert result["detected"] is True
        assert "with_special" in result["columns"]
        assert result["columns"]["with_special"]["special_count"] == 4
    
    def test_detect_outliers_iqr(self, detector, sample_numeric_df):
        result = detector.detect_outliers(sample_numeric_df, method="iqr")
        
        assert "method" in result
        assert result["method"] == "iqr"
        assert "columns" in result
    
    def test_detect_outliers_zscore(self, detector, sample_numeric_df):
        result = detector.detect_outliers(sample_numeric_df, method="zscore")
        
        assert result["method"] == "zscore"
    
    def test_detect_outliers_percentile(self, detector, sample_numeric_df):
        result = detector.detect_outliers(sample_numeric_df, method="percentile")
        
        assert result["method"] == "percentile"
    
    def test_detect_missing_values(self, detector, sample_mixed_df):
        result = detector.detect_missing_values(sample_mixed_df)
        
        assert result["detected"] is True
        assert "numeric" in result["columns"]
        assert "categorical" in result["columns"]
    
    def test_detect_missing_values_specific_columns(self, detector, sample_mixed_df):
        result = detector.detect_missing_values(sample_mixed_df, columns=["numeric"])
        
        assert "numeric" in result["columns"]
        assert "categorical" not in result["columns"]
    
    def test_validation_error_on_none_df(self, detector):
        with pytest.raises(ValidationError):
            detector.detect_outliers(None)
    
    def test_validation_error_on_empty_df(self, detector):
        empty_df = pd.DataFrame()
        with pytest.raises(InsufficientDataError):
            detector.detect_outliers(empty_df)
    
    def test_detect_outliers_with_outliers_found(self, detector, sample_numeric_df):
        result = detector.detect_outliers(sample_numeric_df, method="iqr")
        
        assert result["detected"] is True
        assert result["total_outliers"] > 0
        assert "numeric_col" in result["columns"]
        assert "outlier_count" in result["columns"]["numeric_col"]
        assert "lower_bound" in result["columns"]["numeric_col"]
        assert "upper_bound" in result["columns"]["numeric_col"]
    
    def test_recommend_outlier_treatment(self, detector, sample_numeric_df):
        detection = detector.detect_outliers(sample_numeric_df)
        
        if "numeric_col" in detection["columns"]:
            recommendation = detector.recommend_outlier_treatment("numeric_col", detection)
            assert recommendation in ["Z-Score", "IQR", "Percentile"]


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for the full detection pipeline."""
    
    def test_full_detection_pipeline(self, detector, sample_mixed_df):
        """Test running all detection methods in sequence."""
        invalid_template = {
            'invalid_numeric': {'type': 'Numerical', 'valid_range': [0, 100]}
        }
        special_template = {
            'with_special': {'type': 'Numerical', 'special_values': [-999, 9999]}
        }
        
        invalid_result = detector.detect_invalid_values(sample_mixed_df, invalid_template)
        special_result = detector.detect_special_values(sample_mixed_df, special_template)
        outlier_result = detector.detect_outliers(sample_mixed_df)
        missing_result = detector.detect_missing_values(sample_mixed_df)
        
        assert all(r is not None for r in [invalid_result, special_result, outlier_result, missing_result])
        assert all("detected" in r for r in [invalid_result, special_result, outlier_result, missing_result])
    
    def test_compute_comprehensive_stats(self, detector, sample_mixed_df):
        """Test comprehensive statistics computation."""
        stats = detector.compute_comprehensive_stats(sample_mixed_df)
        
        assert isinstance(stats, dict)
        assert "numeric" in stats
        assert "categorical" in stats

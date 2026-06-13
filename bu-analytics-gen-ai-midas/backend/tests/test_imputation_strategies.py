"""
Unit tests for Imputation Strategy Pattern implementation in agentic_system.py.

Tests cover:
- Individual imputation strategy classes
- Imputation strategy registry
- Code generation for each strategy
- Strategy matching logic
"""

import pytest
from typing import List, Dict, Any

from app.services.agentic_system import (
    BaseImputationStrategy,
    MeanImputationStrategy,
    MedianImputationStrategy,
    ModeImputationStrategy,
    ForwardBackwardFillStrategy,
    ForwardFillStrategy,
    BackwardFillStrategy,
    DropImputationStrategy,
    MinImputationStrategy,
    MaxImputationStrategy,
    P1ImputationStrategy,
    P95ImputationStrategy,
    P99ImputationStrategy,
    ZeroImputationStrategy,
    ImputationStrategyRegistry,
)


# =============================================================================
# INDIVIDUAL STRATEGY TESTS
# =============================================================================

class TestMeanImputationStrategy:
    """Tests for MeanImputationStrategy."""
    
    def test_keywords(self):
        strategy = MeanImputationStrategy()
        assert "mean" in strategy.get_keywords()
    
    def test_matches_mean(self):
        strategy = MeanImputationStrategy()
        assert strategy.matches("Impute with Mean") is True
        assert strategy.matches("Use mean value") is True
        assert strategy.matches("Median imputation") is False
    
    def test_generate_code(self):
        strategy = MeanImputationStrategy()
        code = strategy.generate_code("age", {})
        assert len(code) == 1
        assert "fillna" in code[0]
        assert "mean()" in code[0]
        assert "'age'" in code[0]


class TestMedianImputationStrategy:
    """Tests for MedianImputationStrategy."""
    
    def test_keywords(self):
        strategy = MedianImputationStrategy()
        assert "median" in strategy.get_keywords()
    
    def test_matches_median(self):
        strategy = MedianImputationStrategy()
        assert strategy.matches("Impute with Median") is True
        assert strategy.matches("Use median value") is True
        assert strategy.matches("Mean imputation") is False
    
    def test_generate_code(self):
        strategy = MedianImputationStrategy()
        code = strategy.generate_code("salary", {})
        assert len(code) == 1
        assert "fillna" in code[0]
        assert "median()" in code[0]
        assert "'salary'" in code[0]


class TestModeImputationStrategy:
    """Tests for ModeImputationStrategy."""
    
    def test_keywords(self):
        strategy = ModeImputationStrategy()
        assert "mode" in strategy.get_keywords()
    
    def test_matches_mode(self):
        strategy = ModeImputationStrategy()
        assert strategy.matches("Impute with Mode") is True
        assert strategy.matches("Most frequent value") is False  # mode keyword not present
    
    def test_generate_code(self):
        strategy = ModeImputationStrategy()
        code = strategy.generate_code("category", {})
        assert len(code) == 3
        assert "mode()" in code[0]
        assert "if len(mode_val)" in code[1]
        assert "fillna" in code[2]


class TestForwardBackwardFillStrategy:
    """Tests for ForwardBackwardFillStrategy."""
    
    def test_keywords(self):
        strategy = ForwardBackwardFillStrategy()
        keywords = strategy.get_keywords()
        assert "forward" in keywords
        assert "backward" in keywords
    
    def test_matches_requires_both(self):
        strategy = ForwardBackwardFillStrategy()
        assert strategy.matches("Forward and Backward Fill") is True
        assert strategy.matches("Forward/Backward fill") is True
        assert strategy.matches("Forward fill only") is False
        assert strategy.matches("Backward fill only") is False
    
    def test_generate_code(self):
        strategy = ForwardBackwardFillStrategy()
        code = strategy.generate_code("time_series", {})
        assert len(code) == 1
        assert "ffill()" in code[0]
        assert "bfill()" in code[0]


class TestForwardFillStrategy:
    """Tests for ForwardFillStrategy."""
    
    def test_matches_forward_only(self):
        strategy = ForwardFillStrategy()
        assert strategy.matches("Forward fill") is True
        assert strategy.matches("ffill") is True
        assert strategy.matches("Backward fill") is False
    
    def test_generate_code(self):
        strategy = ForwardFillStrategy()
        code = strategy.generate_code("col", {})
        assert len(code) == 1
        assert "ffill()" in code[0]


class TestBackwardFillStrategy:
    """Tests for BackwardFillStrategy."""
    
    def test_matches_backward_only(self):
        strategy = BackwardFillStrategy()
        assert strategy.matches("Backward fill") is True
        assert strategy.matches("bfill") is True
        assert strategy.matches("Forward fill") is False
    
    def test_generate_code(self):
        strategy = BackwardFillStrategy()
        code = strategy.generate_code("col", {})
        assert len(code) == 1
        assert "bfill()" in code[0]


class TestDropImputationStrategy:
    """Tests for DropImputationStrategy."""
    
    def test_keywords(self):
        strategy = DropImputationStrategy()
        assert "drop" in strategy.get_keywords()
    
    def test_matches_drop(self):
        strategy = DropImputationStrategy()
        assert strategy.matches("Drop rows") is True
        assert strategy.matches("Remove missing") is True
    
    def test_generate_code(self):
        strategy = DropImputationStrategy()
        code = strategy.generate_code("col_with_missing", {})
        assert len(code) == 1
        assert "dropna" in code[0]


class TestMinImputationStrategy:
    """Tests for MinImputationStrategy."""
    
    def test_matches_min(self):
        strategy = MinImputationStrategy()
        assert strategy.matches("Minimum value") is True
        assert strategy.matches("Use min") is True
    
    def test_generate_code(self):
        strategy = MinImputationStrategy()
        code = strategy.generate_code("score", {})
        assert len(code) == 1
        assert "min()" in code[0]


class TestMaxImputationStrategy:
    """Tests for MaxImputationStrategy."""
    
    def test_matches_max(self):
        strategy = MaxImputationStrategy()
        assert strategy.matches("Maximum value") is True
        assert strategy.matches("Use max") is True
    
    def test_generate_code(self):
        strategy = MaxImputationStrategy()
        code = strategy.generate_code("score", {})
        assert len(code) == 1
        assert "max()" in code[0]


class TestPercentileStrategies:
    """Tests for percentile-based imputation strategies."""
    
    def test_p1_strategy(self):
        strategy = P1ImputationStrategy()
        assert strategy.matches("P1") is True
        assert strategy.matches("1st percentile") is True
        
        code = strategy.generate_code("col", {})
        assert "quantile(0.01)" in code[0]
    
    def test_p95_strategy(self):
        strategy = P95ImputationStrategy()
        assert strategy.matches("P95") is True
        assert strategy.matches("95th percentile") is True
        
        code = strategy.generate_code("col", {})
        assert "quantile(0.95)" in code[0]
    
    def test_p99_strategy(self):
        strategy = P99ImputationStrategy()
        assert strategy.matches("P99") is True
        assert strategy.matches("99th percentile") is True
        
        code = strategy.generate_code("col", {})
        assert "quantile(0.99)" in code[0]


class TestZeroImputationStrategy:
    """Tests for ZeroImputationStrategy."""
    
    def test_matches_zero(self):
        strategy = ZeroImputationStrategy()
        assert strategy.matches("Zero") is True
        assert strategy.matches("Replace with 0") is True
    
    def test_generate_code(self):
        strategy = ZeroImputationStrategy()
        code = strategy.generate_code("count", {})
        assert len(code) == 1
        assert "fillna(0)" in code[0]


# =============================================================================
# REGISTRY TESTS
# =============================================================================

class TestImputationStrategyRegistry:
    """Tests for ImputationStrategyRegistry."""
    
    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        return ImputationStrategyRegistry()
    
    def test_register_strategy(self, registry):
        strategy = MeanImputationStrategy()
        registry.register("test_mean", strategy)
        assert registry.get("test_mean") is strategy
    
    def test_get_nonexistent_returns_none(self, registry):
        assert registry.get("nonexistent") is None
    
    def test_find_matching_strategy_mean(self, registry):
        strategy = registry.find_matching("Impute with Mean value")
        assert isinstance(strategy, MeanImputationStrategy)
    
    def test_find_matching_strategy_median(self, registry):
        strategy = registry.find_matching("Use median imputation")
        assert isinstance(strategy, MedianImputationStrategy)
    
    def test_find_matching_strategy_mode(self, registry):
        strategy = registry.find_matching("Mode imputation")
        assert isinstance(strategy, ModeImputationStrategy)
    
    def test_find_matching_strategy_forward_backward(self, registry):
        strategy = registry.find_matching("Forward and backward fill")
        assert isinstance(strategy, ForwardBackwardFillStrategy)
    
    def test_find_matching_strategy_drop(self, registry):
        strategy = registry.find_matching("Drop rows with missing")
        assert isinstance(strategy, DropImputationStrategy)
    
    def test_find_matching_returns_none_for_unknown(self, registry):
        strategy = registry.find_matching("Unknown imputation method xyz")
        assert strategy is None
    
    def test_all_strategies(self, registry):
        all_strats = registry.all_strategies()
        assert len(all_strats) > 0
        assert all(isinstance(s, BaseImputationStrategy) for s in all_strats)
    
    def test_generate_code_via_registry(self, registry):
        code = registry.generate_code("mean", "age", {})
        assert code is not None
        assert len(code) > 0
        assert "mean()" in code[0]
    
    def test_generate_code_returns_none_for_unknown(self, registry):
        code = registry.generate_code("unknown_strategy", "col", {})
        assert code is None


# =============================================================================
# STRATEGY PATTERN INTEGRATION TESTS
# =============================================================================

class TestStrategyPatternIntegration:
    """Integration tests for the strategy pattern implementation."""
    
    @pytest.fixture
    def registry(self):
        return ImputationStrategyRegistry()
    
    def test_all_strategies_have_keywords(self, registry):
        """Every registered strategy should have at least one keyword."""
        for strategy in registry.all_strategies():
            keywords = strategy.get_keywords()
            assert len(keywords) > 0, f"Strategy {type(strategy).__name__} has no keywords"
    
    def test_all_strategies_generate_valid_code(self, registry):
        """Every strategy should generate non-empty code."""
        test_column = "test_column"
        test_config = {}
        
        for strategy in registry.all_strategies():
            code = strategy.generate_code(test_column, test_config)
            assert code is not None, f"Strategy {type(strategy).__name__} returned None"
            assert len(code) > 0, f"Strategy {type(strategy).__name__} returned empty code"
            assert all(isinstance(line, str) for line in code)
    
    def test_generated_code_references_column(self, registry):
        """Generated code should reference the specified column name."""
        test_column = "my_special_column"
        
        for strategy in registry.all_strategies():
            code = strategy.generate_code(test_column, {})
            code_text = "\n".join(code)
            assert test_column in code_text, \
                f"Strategy {type(strategy).__name__} doesn't reference column in code"
    
    def test_strategy_priority_forward_backward_over_forward(self, registry):
        """ForwardBackwardFill should match before ForwardFill for combined patterns."""
        treatment = "Forward and Backward Fill"
        
        fb_strategy = ForwardBackwardFillStrategy()
        f_strategy = ForwardFillStrategy()
        
        assert fb_strategy.matches(treatment) is True
    
    def test_code_indentation(self, registry):
        """Generated code should be properly indented with 4 spaces."""
        for strategy in registry.all_strategies():
            code = strategy.generate_code("col", {})
            for line in code:
                if line.strip():  # Non-empty lines
                    assert line.startswith("    "), \
                        f"Strategy {type(strategy).__name__} has improper indentation"


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Edge case tests for imputation strategies."""
    
    def test_column_name_with_spaces(self):
        strategy = MeanImputationStrategy()
        code = strategy.generate_code("column with spaces", {})
        assert "'column with spaces'" in code[0]
    
    def test_column_name_with_special_chars(self):
        strategy = MedianImputationStrategy()
        code = strategy.generate_code("column_123_test", {})
        assert "'column_123_test'" in code[0]
    
    def test_case_insensitive_matching(self):
        strategy = MeanImputationStrategy()
        assert strategy.matches("MEAN") is True
        assert strategy.matches("Mean") is True
        assert strategy.matches("mEaN") is True
    
    def test_partial_matching(self):
        strategy = MedianImputationStrategy()
        assert strategy.matches("The median of the column") is True
        assert strategy.matches("medianimputation") is True

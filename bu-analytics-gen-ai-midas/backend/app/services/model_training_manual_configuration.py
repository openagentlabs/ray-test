import pandas as pd
import numpy as np
import pandas as pd

# Helper to safely compute median on series with mixed types
def safe_median(series: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    return float(numeric.median()) if not numeric.empty else 0.0
import ast
import json
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import logging
from joblib import Parallel, delayed
import joblib

from app.core.logging_config import get_logger
from app.utils.monotonicity import (
    calculate_ks,
    compute_auc_gini,
    compute_auc_overfit_pct,
    nonzero_feature_slot_count,
)

logger = get_logger(__name__)

# Try to import VIF calculation library
try:
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    try:
        from statsmodels.tools.tools import add_constant
    except Exception:
        add_constant = None  # Fallback - we'll proceed without an explicit constant if unavailable
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    logger.warning("statsmodels not available, VIF calculation will be disabled")


class ModelTrainingManualConfigurationService:
    """Service for manual configuration of model training"""

    # Preprocessing cache: {(dataset_id, frozenset(variables), target): (result_dict, last_updated)}
    _preprocess_cache: Dict[tuple, tuple] = {}

    def __init__(self):
        self.logger = logger
        self.target_encoder = None
    
    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        """
        Convert value to int, returning default when value is None, blank, or invalid.
        """
        if value is None:
            return default
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "":
                return default
            try:
                return int(stripped)
            except ValueError:
                return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _extract_primary_metric(self, metrics: Dict[str, Any], problem_type: str) -> Optional[float]:
        if not isinstance(metrics, dict):
            return None

        if problem_type == "classification":
            for key in ("test_auc", "auc", "test_f1_score", "f1"):
                value = self._safe_float(metrics.get(key))
                if value is not None:
                    return value
        else:
            for key in ("test_r2", "r2", "train_r2"):
                value = self._safe_float(metrics.get(key))
                if value is not None:
                    return value
        return None

    def _extract_train_metric(self, metrics: Dict[str, Any], problem_type: str) -> Optional[float]:
        if not isinstance(metrics, dict):
            return None
        key = "train_auc" if problem_type == "classification" else "train_r2"
        return self._safe_float(metrics.get(key))

    @staticmethod
    def _calculate_overfit_pct(train_score: Optional[float], test_score: Optional[float]) -> Optional[float]:
        return compute_auc_overfit_pct(
            ModelTrainingManualConfigurationService._safe_float(train_score),
            ModelTrainingManualConfigurationService._safe_float(test_score),
        )

    @staticmethod
    def _apply_binary_rank_order_metrics(
        metrics: Dict[str, Any],
        *,
        y_train: Optional[np.ndarray] = None,
        p_train: Optional[np.ndarray] = None,
        y_test: Optional[np.ndarray] = None,
        p_test: Optional[np.ndarray] = None,
    ) -> None:
        """Populate KS, Gini, and overfit_pct using ``app.utils.monotonicity`` (binary classification)."""
        try:
            if y_test is not None and p_test is not None:
                y_te = np.asarray(y_test).ravel()
                s_te = np.asarray(p_test, dtype=float).ravel()
                ks_te, _ = calculate_ks(y_te, s_te)
                metrics["test_ks_statistic"] = float(ks_te)
                metrics["ks_statistic"] = float(ks_te)
                _, g_te = compute_auc_gini(y_te, s_te)
                metrics["test_gini"] = float(g_te)
            if y_train is not None and p_train is not None:
                y_tr = np.asarray(y_train).ravel()
                s_tr = np.asarray(p_train, dtype=float).ravel()
                ks_tr, _ = calculate_ks(y_tr, s_tr)
                metrics["train_ks_statistic"] = float(ks_tr)
                _, g_tr = compute_auc_gini(y_tr, s_tr)
                metrics["train_gini"] = float(g_tr)
            ofp = compute_auc_overfit_pct(
                ModelTrainingManualConfigurationService._safe_float(metrics.get("train_auc")),
                ModelTrainingManualConfigurationService._safe_float(metrics.get("test_auc")),
            )
            if ofp is not None:
                metrics["overfit_pct"] = float(ofp)
        except Exception as ex:
            logger.warning("_apply_binary_rank_order_metrics: %s", ex)

    def _compute_bivariate_correlation_map(
        self,
        df: pd.DataFrame,
        target_column: str,
        feature_names: List[str],
    ) -> Dict[str, Optional[float]]:
        corr_map: Dict[str, Optional[float]] = {}
        if target_column not in df.columns:
            return corr_map

        y_raw = df[target_column]
        if pd.api.types.is_numeric_dtype(y_raw):
            y_num = pd.to_numeric(y_raw, errors="coerce")
        else:
            try:
                y_num = pd.Series(pd.factorize(y_raw.astype(str))[0], index=y_raw.index, dtype=float)
            except Exception:
                y_num = pd.to_numeric(y_raw, errors="coerce")

        for feature in feature_names or []:
            if feature not in df.columns:
                corr_map[feature] = None
                continue
            try:
                x_num = pd.to_numeric(df[feature], errors="coerce")
                pair = pd.concat([x_num, y_num], axis=1).dropna()
                if len(pair) < 3:
                    corr_map[feature] = None
                    continue
                corr_val = pair.iloc[:, 0].corr(pair.iloc[:, 1])
                corr_map[feature] = float(corr_val) if pd.notna(corr_val) else None
            except Exception:
                corr_map[feature] = None
        return corr_map

    def _build_step6_views(
        self,
        *,
        results: List[Dict[str, Any]],
        problem_type: str,
        optimization_method: str,
        cv_folds: int,
        optuna_trials: Optional[int],
        early_stopping_rounds: Optional[int],
        target_metric: Optional[str],
        correlation_map: Optional[Dict[str, Optional[float]]] = None,
    ) -> Dict[str, Any]:
        base_model_results: List[Dict[str, Any]] = []
        bayesian_summary: List[Dict[str, Any]] = []
        recommendations_g1: List[Dict[str, Any]] = []
        recommendations_g2: List[Dict[str, Any]] = []
        lr_sign_validation: List[Dict[str, Any]] = []
        lr_backward_report: Optional[Dict[str, Any]] = None

        for model_result in results:
            if not isinstance(model_result, dict) or model_result.get("error"):
                continue

            algorithm = model_result.get("algorithm")
            _algo_compact = str(algorithm or "").lower().replace(" ", "").replace("-", "").replace("_", "")
            is_lr_algo = _algo_compact in ("logisticregression", "lr")
            metrics = model_result.get("metrics", {}) if isinstance(model_result.get("metrics"), dict) else {}
            history = model_result.get("iteration_history", []) if isinstance(model_result.get("iteration_history"), list) else []

            base_iteration = history[0] if history else None
            base_metrics: Dict[str, Any] = dict(base_iteration.get("metrics", {}) if isinstance(base_iteration, dict) else {})
            used_feats = model_result.get("used_features", []) or []
            if isinstance(base_iteration, dict) and base_iteration.get("feature_importance_count") is not None:
                try:
                    base_metrics["feature_importance_count"] = int(base_iteration["feature_importance_count"])
                except (TypeError, ValueError):
                    pass
            base_metrics["feature_count"] = len(used_feats)
            base_model_results.append({
                "algorithm": algorithm,
                "model_id": model_result.get("model_id"),
                "base_iteration": 1 if base_iteration else None,
                "base_score": self._safe_float(base_iteration.get("score")) if isinstance(base_iteration, dict) else None,
                "base_metrics": base_metrics,
            })

            om_resolved = model_result.get("optimization_method") or optimization_method
            if str(om_resolved).lower() in ("bayesian", "bayesian_optimization"):
                trial_scores = [
                    self._safe_float(it.get("score"))
                    for it in history
                    if isinstance(it, dict) and self._safe_float(it.get("score")) is not None
                ]
                first_score = trial_scores[0] if trial_scores else None
                best_score = max(trial_scores) if trial_scores else None
                mean_score = float(np.mean(trial_scores)) if trial_scores else None
                std_score = float(np.std(trial_scores)) if len(trial_scores) > 1 else 0.0 if trial_scores else None
                bayesian_summary.append({
                    "algorithm": algorithm,
                    "trials_run": len(history),
                    "configured_trials": optuna_trials if optuna_trials is not None else len(history),
                    "best_iteration": model_result.get("best_iteration"),
                    "best_score": self._extract_primary_metric(metrics, problem_type),
                    "target_metric": target_metric or ("auc" if problem_type == "classification" else "r2"),
                    "cv_folds": cv_folds,
                    "early_stopping_rounds": early_stopping_rounds,
                    "trial_score_min": min(trial_scores) if trial_scores else None,
                    "trial_score_max": best_score,
                    "trial_score_mean": mean_score,
                    "trial_score_std": std_score,
                    "improvement_from_first_trial": (best_score - first_score) if (best_score is not None and first_score is not None) else None,
                })

            train_score = self._extract_train_metric(metrics, problem_type)
            test_score = self._extract_primary_metric(metrics, problem_type)
            overfit_pct = self._calculate_overfit_pct(train_score, test_score)
            fin_m = model_result.get("metrics", {}) if isinstance(model_result.get("metrics"), dict) else {}
            nz_fin = fin_m.get("feature_importance_count")
            try:
                nz_fin = int(nz_fin) if nz_fin is not None else None
            except (TypeError, ValueError):
                nz_fin = None
            model_key = {
                "algorithm": algorithm,
                "model_id": model_result.get("model_id"),
                "score": test_score,
                "train_score": train_score,
                "overfit_pct": overfit_pct,
                "feature_count": len(model_result.get("used_features", []) or []),
                "feature_importance_count": nz_fin,
            }
            recommendations_g2.append(model_key)

            if overfit_pct is None or overfit_pct <= 10.0:
                recommendations_g1.append(model_key)

            if is_lr_algo:
                coeff_rows = model_result.get("coefficient_signs", [])
                details = []
                matched = 0
                mismatched = 0
                unknown = 0
                for coeff in coeff_rows if isinstance(coeff_rows, list) else []:
                    feature = coeff.get("feature")
                    coef_sign = coeff.get("sign")
                    corr_val = (correlation_map or {}).get(feature) if isinstance(feature, str) else None
                    corr_sign = 1 if (corr_val is not None and corr_val > 0) else -1 if (corr_val is not None and corr_val < 0) else 0
                    if coef_sign == 0 or corr_sign == 0:
                        status = "unknown"
                        unknown += 1
                    elif coef_sign == corr_sign:
                        status = "match"
                        matched += 1
                    else:
                        status = "mismatch"
                        mismatched += 1
                    details.append({
                        "feature": feature,
                        "coefficient": coeff.get("coefficient"),
                        "coefficient_sign": coef_sign,
                        "bivariate_correlation": corr_val,
                        "bivariate_sign": corr_sign,
                        "status": status,
                    })
                lr_sign_validation.append({
                    "algorithm": algorithm,
                    "model_id": model_result.get("model_id"),
                    "status": "validated" if coeff_rows else "no_coefficients",
                    "matched_count": matched,
                    "mismatched_count": mismatched,
                    "unknown_count": unknown,
                    "overall_pass": mismatched == 0 if coeff_rows else None,
                    "details": details,
                })

            if is_lr_algo and lr_backward_report is None:
                el = model_result.get("lr_backward_elimination")
                if isinstance(el, dict) and el.get("iterations"):
                    lr_backward_report = {
                        "algorithm": algorithm,
                        "model_id": model_result.get("model_id"),
                        "iterations": el.get("iterations") or [],
                        "summary": el.get("summary") or {},
                        "config": el.get("config") or {},
                        "final_features": el.get("final_features") or [],
                    }

        recommendations_g2 = sorted(recommendations_g2, key=lambda x: (x.get("score") is None, -(x.get("score") or -1e12)))
        recommendations_g1 = sorted(
            recommendations_g1,
            key=lambda x: (
                x.get("score") is None,
                -(x.get("score") or -1e12),
                x.get("feature_count") if x.get("feature_count") is not None else 10**9,
            ),
        )

        for idx, row in enumerate(recommendations_g1, start=1):
            row["rank"] = idx
            row["is_recommended"] = idx == 1
        for idx, row in enumerate(recommendations_g2, start=1):
            row["rank"] = idx
            row["is_recommended"] = idx == 1

        return {
            "base_model_results": base_model_results,
            "bayesian_summary": bayesian_summary,
            "lr_backward_elimination_report": lr_backward_report,
            "recommendations": {
                "g1_overfit_aware": recommendations_g1,
                "g2_test_only": recommendations_g2,
                "lr_sign_validation": lr_sign_validation,
            },
        }
    
    def detect_class_imbalance(self, y: pd.Series) -> Dict[str, Any]:
        """Detect if dataset is imbalanced"""
        value_counts = y.value_counts()
        total = len(y)
        majority_class_ratio = value_counts.iloc[0] / total
        
        is_imbalanced = majority_class_ratio > 0.7  # More than 70% in one class
        
        return {
            'is_imbalanced': is_imbalanced,
            'majority_class_ratio': float(majority_class_ratio),
            'class_distribution': {str(k): int(v) for k, v in value_counts.to_dict().items()},
            'imbalance_ratio': float(value_counts.iloc[0] / value_counts.iloc[-1]) if len(value_counts) > 1 else 1.0
        }
    
    def detect_problem_type_from_data(self, df: pd.DataFrame, target_column: str) -> Dict[str, Any]:
        """
        Detect problem type (classification or regression) from target variable
        
        Args:
            df: DataFrame containing the data
            target_column: Name of the target column
            
        Returns:
            Dictionary with problem_type and metadata
        """
        try:
            if target_column not in df.columns:
                raise ValueError(f"Target column '{target_column}' not found in dataset")
            
            y = df[target_column]
            
            # Check if target is non-numeric or boolean
            if not pd.api.types.is_numeric_dtype(y):
                return {
                    'problem_type': 'classification',
                    'reason': 'Target variable is non-numeric',
                    'unique_values': int(y.nunique()),
                    'description': 'Predicting discrete categories or classes'
                }
            
            # Check if target is boolean
            if y.dtype == bool:
                return {
                    'problem_type': 'classification',
                    'reason': 'Target variable is boolean',
                    'unique_values': int(y.nunique()),
                    'description': 'Predicting discrete categories or classes'
                }
            
            # For numeric targets, check unique values
            unique_count = y.nunique()
            total_count = len(y)
            unique_ratio = unique_count / total_count
            
            # Binary classification (0/1)
            if unique_count == 2:
                unique_vals = sorted(y.dropna().unique())
                if (unique_vals[0] == 0 and unique_vals[1] == 1) or \
                   (unique_vals[0] == 0.0 and unique_vals[1] == 1.0):
                    return {
                        'problem_type': 'classification',
                        'reason': 'Binary target variable (0/1)',
                        'unique_values': int(unique_count),
                        'description': 'Predicting discrete categories or classes'
                    }
            
            # Categorical classification (few unique values)
            if unique_count <= 20 and unique_ratio <= 0.05:
                # Check if values are mostly integers
                integer_count = sum(1 for val in y.dropna().unique() 
                                  if isinstance(val, (int, np.integer)) or 
                                  (isinstance(val, float) and val.is_integer()))
                if integer_count / len(y.dropna().unique()) > 0.8:
                    return {
                        'problem_type': 'classification',
                        'reason': f'Low unique value ratio ({unique_ratio:.2%})',
                        'unique_values': int(unique_count),
                        'description': 'Predicting discrete categories or classes'
                    }
            
            # Continuous regression (many unique values)
            if unique_count > 50:
                return {
                    'problem_type': 'regression',
                    'reason': f'High unique value count ({unique_count})',
                    'unique_values': int(unique_count),
                    'description': 'Predicting continuous numerical values'
                }
            
            # Default to regression for numeric variables
            return {
                'problem_type': 'regression',
                'reason': 'Numeric target with moderate unique values',
                'unique_values': int(unique_count),
                'description': 'Predicting continuous numerical values'
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting problem type: {str(e)}")
            raise
    
    def get_available_variables(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get list of available variables from dataset
        
        Args:
            df: DataFrame containing the data
            
        Returns:
            Dictionary with variable lists and metadata
        """
        try:
            columns = df.columns.tolist()
            
            # Identify common non-feature columns
            non_feature_columns = ['ID', 'MEMBER_ID', 'SEGMENT', 'segment', 'id', 'member_id']
            
            # Identify numerical and categorical columns
            numerical_columns = df.select_dtypes(include=[np.number]).columns.tolist()
            categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
            
            # Suggest target variables (typically numeric or binary categorical)
            suggested_targets = []
            for col in columns:
                if col.upper() in ['TARGET', 'TARGET_FLAG', 'TARGET_VARIABLE', 'LABEL', 'Y']:
                    suggested_targets.append(col)
            
            # Default independent variables (exclude non-feature and target-like columns)
            default_independent = [col for col in columns 
                                  if col.upper() not in [c.upper() for c in non_feature_columns]
                                  and col.upper() not in ['TARGET', 'TARGET_FLAG', 'TARGET_VARIABLE', 'LABEL', 'Y']]
            
            return {
                'all_columns': columns,
                'numerical_columns': numerical_columns,
                'categorical_columns': categorical_columns,
                'suggested_targets': suggested_targets,
                'default_independent': default_independent,
                'non_feature_columns': non_feature_columns,
                'total_columns': len(columns),
                'total_rows': len(df)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting available variables: {str(e)}")
            raise
    
    def validate_variable_selection(self, df: pd.DataFrame, target_column: str, 
                                   independent_variables: List[str]) -> Dict[str, Any]:
        """
        Validate variable selection.

        On multi-GB datasets the row-wise checks below (full correlation matrix,
        per-column ``nunique``) take minutes and used to time the request out.
        We therefore run those checks on a representative sample (capped at
        ``VALIDATION_SAMPLE_ROWS``); column-existence and target-vs-independent
        checks still use the full frame's metadata, which is O(1) on size.

        Args:
            df: DataFrame containing the data
            target_column: Selected target column
            independent_variables: Selected independent variables

        Returns:
            Dictionary with validation results
        """
        VALIDATION_SAMPLE_ROWS = 100_000
        try:
            errors = []
            warnings = []

            # Cheap, metadata-only checks against the full frame.
            if target_column not in df.columns:
                errors.append(f"Target column '{target_column}' not found in dataset")

            missing_vars = [var for var in independent_variables if var not in df.columns]
            if missing_vars:
                errors.append(f"Independent variables not found: {', '.join(missing_vars)}")

            if target_column in independent_variables:
                errors.append("Target variable cannot be in independent variables")

            if len(independent_variables) < 1:
                errors.append("At least one independent variable must be selected")

            # Sample once for the row-wise checks. ``df.sample`` returns a view
            # without copying for ``n >= len(df)``.
            total_rows = len(df)
            if total_rows > VALIDATION_SAMPLE_ROWS:
                df_sample = df.sample(n=VALIDATION_SAMPLE_ROWS, random_state=42)
                self.logger.info(
                    f"validate_variable_selection: sampled {VALIDATION_SAMPLE_ROWS} of "
                    f"{total_rows} rows for correlation / constant-variable checks"
                )
            else:
                df_sample = df

            # High-correlation warning (sample-based; threshold is 0.9 so a
            # 100k sample is statistically more than enough).
            if not errors and target_column in df_sample.columns:
                try:
                    numeric_independent = [col for col in independent_variables 
                                         if pd.api.types.is_numeric_dtype(df_sample[col])]
                    
                    if numeric_independent and pd.api.types.is_numeric_dtype(df_sample[target_column]):
                        correlations = df_sample[numeric_independent + [target_column]].corr()[target_column].drop(target_column)
                        high_corr = correlations[correlations.abs() > 0.9]
                        
                        if len(high_corr) > 0:
                            warnings.append(f"High correlation detected between target and variables: {', '.join(high_corr.index.tolist())}")
                except Exception as corr_error:
                    self.logger.warning(f"Could not calculate correlations: {str(corr_error)}")

            # Constant-variable warning (sample-based; if a column is constant
            # in 100k random rows it is constant in practice).
            if not errors:
                constant_vars = []
                for var in independent_variables:
                    if var in df_sample.columns and df_sample[var].nunique(dropna=False) <= 1:
                        constant_vars.append(var)
                
                if constant_vars:
                    warnings.append(f"Constant variables detected (will be automatically removed): {', '.join(constant_vars)}")
            
            return {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'summary': {
                    'target_column': target_column,
                    'num_independent_variables': len(independent_variables),
                    'total_features': len(independent_variables)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error validating variable selection: {str(e)}")
            return {
                'is_valid': False,
                'errors': [f"Validation error: {str(e)}"],
                'warnings': [],
                'summary': {}
            }

    def apply_variable_locking(
        self,
        independent_variables: List[str],
        selected_variables: Optional[List[str]] = None,
        locked_variables: Optional[List[str]] = None,
        selection_mode: str = "manual",
    ) -> Dict[str, Any]:
        """
        Apply Step 1 variable locking for manual training flow.
        """
        try:
            available_set = set(independent_variables or [])
            requested_selected = list(selected_variables or [])
            requested_locked = list(locked_variables or [])

            valid_selected: List[str] = []
            invalid_selected: List[str] = []
            for var in requested_selected:
                if var in available_set and var not in valid_selected:
                    valid_selected.append(var)
                elif var not in available_set:
                    invalid_selected.append(var)

            valid_locked: List[str] = []
            invalid_locked: List[str] = []
            for var in requested_locked:
                if var in available_set and var not in valid_locked:
                    valid_locked.append(var)
                elif var not in available_set:
                    invalid_locked.append(var)

            if not requested_selected:
                valid_selected = list(independent_variables)

            final_selected = list(dict.fromkeys(valid_locked + valid_selected))
            forced_locked = [var for var in valid_locked if var not in valid_selected]
            filtered_out = [var for var in independent_variables if var not in final_selected]

            criteria: List[Dict[str, Any]] = []
            for var in final_selected:
                if var in valid_locked:
                    reason = "Locked by modeler (must-have)"
                elif selected_variables:
                    reason = f"Pre-selected from Variable Analysis ({selection_mode} mode)"
                else:
                    reason = "No explicit selection provided - fallback include"
                criteria.append({"variable": var, "reason": reason})

            return {
                "selected_variables": final_selected,
                "locked_variables": valid_locked,
                "unlocked_selected_variables": [v for v in final_selected if v not in valid_locked],
                "invalid_locked_variables": invalid_locked,
                "invalid_selected_variables": invalid_selected,
                "filtered_out_variables": filtered_out,
                "selection_criteria": criteria,
                "summary": {
                    "total_analyzed": len(independent_variables),
                    "requested_selected_count": len(requested_selected),
                    "selected_count": len(final_selected),
                    "locked_count": len(valid_locked),
                    "forced_locked_count": len(forced_locked),
                    "filtered_count": len(filtered_out),
                    "selection_method": f"{selection_mode}_with_locking",
                },
            }
        except Exception as e:
            self.logger.error(f"Error applying manual variable locking: {str(e)}")
            raise
    
    def get_recommended_metrics(self, problem_type: str) -> Dict[str, Any]:
        """
        Get recommended optimization metrics based on problem type
        
        Args:
            problem_type: 'classification' or 'regression'
            
        Returns:
            Dictionary with recommended metrics and their configurations
        """
        try:
            if problem_type == 'classification':
                return {
                    'recommended_metrics': [
                        {
                            'name': 'auc',
                            'display_name': 'AUC-ROC',
                            'description': 'Recommended for imbalanced data',
                            'min': 0.0,
                            'max': 1.0,
                            'default': 0.85,
                            'is_recommended': True
                        },
                        {
                            'name': 'f1',
                            'display_name': 'F1-Score',
                            'description': 'Balanced precision/recall',
                            'min': 0.0,
                            'max': 1.0,
                            'default': 0.80,
                            'is_recommended': True
                        },
                        {
                            'name': 'precision',
                            'display_name': 'Precision',
                            'description': 'High precision focus',
                            'min': 0.0,
                            'max': 1.0,
                            'default': 0.75,
                            'is_recommended': False
                        },
                        {
                            'name': 'recall',
                            'display_name': 'Recall',
                            'description': 'High recall focus',
                            'min': 0.0,
                            'max': 1.0,
                            'default': 0.70,
                            'is_recommended': False
                        },
                        {
                            'name': 'accuracy',
                            'display_name': 'Accuracy',
                            'description': 'Overall correctness',
                            'min': 0.0,
                            'max': 1.0,
                            'default': 0.85,
                            'is_recommended': False
                        }
                    ]
                }
            else:  # regression
                return {
                    'recommended_metrics': [
                        {
                            'name': 'r2',
                            'display_name': 'R²',
                            'description': 'Coefficient of determination',
                            'min': 0.0,
                            'max': 1.0,
                            'default': 0.80,
                            'is_recommended': True
                        },
                        {
                            'name': 'adjusted_r2',
                            'display_name': 'Adjusted R²',
                            'description': 'R² with penalty for complexity',
                            'min': 0.0,
                            'max': 1.0,
                            'default': 0.75,
                            'is_recommended': True
                        },
                        {
                            'name': 'mae',
                            'display_name': 'MAE',
                            'description': 'Mean Absolute Error',
                            'min': 0.0,
                            'max': 1000.0,
                            'default': 10.0,
                            'is_recommended': False
                        },
                        {
                            'name': 'mse',
                            'display_name': 'MSE',
                            'description': 'Mean Squared Error',
                            'min': 0.0,
                            'max': 10000.0,
                            'default': 100.0,
                            'is_recommended': False
                        },
                        {
                            'name': 'rmse',
                            'display_name': 'RMSE',
                            'description': 'Root Mean Squared Error',
                            'min': 0.0,
                            'max': 100.0,
                            'default': 10.0,
                            'is_recommended': False
                        }
                    ]
                }
            
        except Exception as e:
            self.logger.error(f"Error getting recommended metrics: {str(e)}")
            raise
    
    def calculate_vif_and_correlation(self, df: pd.DataFrame, target_column: str,
                                     independent_variables: List[str]) -> Dict[str, Any]:
        """
        Calculate VIF and correlation for each independent variable
        
        Args:
            df: DataFrame containing the data
            target_column: Name of the target column
            independent_variables: List of independent variable names
            
        Returns:
            Dictionary with variable statistics including VIF and correlation
        """
        try:
            if target_column not in df.columns:
                raise ValueError(f"Target column '{target_column}' not found in dataset")
            
            # Filter to only include variables that exist in the dataframe
            valid_independent = [var for var in independent_variables if var in df.columns]
            
            if not valid_independent:
                raise ValueError("No valid independent variables found")
            
            # MEMORY OPTIMIZATION 1: Filter out high-cardinality categoricals that might cause memory issues
            # COMMENTED OUT: User wants all variables to be considered for VIF calculation
            # MAX_UNIQUE_VALUES = 1000  # Skip variables with more than 1000 unique values
            # filtered_independent = []
            # for var in valid_independent:
            #     if var in df.columns:
            #         unique_count = df[var].nunique()
            #         if unique_count <= MAX_UNIQUE_VALUES:
            #             filtered_independent.append(var)
            #         else:
            #             self.logger.warning(f"Skipping {var} for VIF calculation (too many unique values: {unique_count})")
            # 
            # valid_independent = filtered_independent if filtered_independent else valid_independent
            if not valid_independent:
                raise ValueError("No valid independent variables found after filtering high-cardinality columns")

            # MEMORY/PERF OPTIMIZATION: Sample once at the top so imputation,
            # correlation, and VIF all run on a random 100k-row subset for
            # large frames (e.g. 4M+ rows). Documented bottleneck — see
            # backend/docs/midas-4m-row-performance-analysis 1.md. VIF and
            # corrwith are stable on this sample size for typical MIDAS data.
            VIF_CORR_SAMPLE_SIZE = 100_000
            _df_work = df[valid_independent + [target_column]]
            if len(_df_work) > VIF_CORR_SAMPLE_SIZE:
                self.logger.info(
                    f"VIF/correlation: sampling {VIF_CORR_SAMPLE_SIZE} rows from {len(_df_work)} for performance",
                    extra={
                        "event": "vif_corr_sampling",
                        "sample_size": VIF_CORR_SAMPLE_SIZE,
                        "full_size": len(_df_work),
                    },
                )
                df_numeric = _df_work.sample(n=VIF_CORR_SAMPLE_SIZE, random_state=42).copy()
            else:
                df_numeric = _df_work.copy()
            
            # Handle missing values
            for col in df_numeric.columns:
                if df_numeric[col].dtype in ['object', 'category']:
                    # For categorical, fill with mode
                    mode_value = df_numeric[col].mode()
                    fill_value = mode_value[0] if len(mode_value) > 0 else 'Unknown'
                    df_numeric[col] = df_numeric[col].fillna(fill_value)
                else:
                    # For numeric, fill with median
                    df_numeric[col] = df_numeric[col].fillna(safe_median(df_numeric[col]))
            
            # Convert categorical variables to numeric using one-hot encoding or label encoding
            categorical_columns = df_numeric.select_dtypes(include=['object', 'category']).columns.tolist()
            if target_column in categorical_columns:
                categorical_columns.remove(target_column)
            
            # Simple label encoding for categorical variables
            from sklearn.preprocessing import LabelEncoder
            label_encoders = {}
            for col in categorical_columns:
                le = LabelEncoder()
                df_numeric[col] = le.fit_transform(df_numeric[col].astype(str))
                label_encoders[col] = le
            
            # Encode target if categorical
            if df_numeric[target_column].dtype in ['object', 'category']:
                le_target = LabelEncoder()
                df_numeric[target_column] = le_target.fit_transform(df_numeric[target_column].astype(str))
            
            # Calculate correlation with target - vectorised single corrwith() call
            self.logger.info(f"Starting correlation calculation for {len(valid_independent)} variables with target '{target_column}'")
            try:
                corr_series = df_numeric[valid_independent].corrwith(df_numeric[target_column])
                correlations = {
                    var: float(corr_series[var]) if not pd.isna(corr_series[var]) else 0.0
                    for var in valid_independent
                }
            except Exception as e:
                self.logger.warning(f"Vectorised corrwith failed, falling back to per-variable: {e}")
                correlations = {}
                for var in valid_independent:
                    try:
                        corr = df_numeric[var].corr(df_numeric[target_column])
                        correlations[var] = float(corr) if not pd.isna(corr) else 0.0
                    except Exception:
                        correlations[var] = 0.0

            successful_correlations = len([c for c in correlations.values() if c != 0.0])
            self.logger.info(f"Correlation calculation completed: {successful_correlations}/{len(valid_independent)} variables")
            
            # Calculate VIF for independent variables
            self.logger.info(f"Starting VIF calculation for {len(valid_independent)} independent variables")
            vif_data = {}
            if STATSMODELS_AVAILABLE and len(valid_independent) > 1:
                try:
                    # Prepare a clean numeric feature matrix
                    X_df = df_numeric[valid_independent].copy()
                    
                    # MEMORY OPTIMIZATION 2: Sample rows for VIF calculation (VIF doesn't need all rows)
                    # CHANGED: Match helpers.py - use 100k sample size instead of 5k
                    max_rows_for_vif = 100000  # Changed from 5000 to match helpers.py
                    if X_df.shape[0] > max_rows_for_vif:
                        self.logger.info(f"Sampling {max_rows_for_vif} rows from {X_df.shape[0]} for VIF calculation")
                        X_df = X_df.sample(n=max_rows_for_vif, random_state=42)
                    
                    # MEMORY OPTIMIZATION 3: Limit number of variables if too many
                    # COMMENTED OUT: User wants all variables to be considered for VIF calculation
                    # max_vars_for_vif = 200  # Maximum 200 variables for VIF
                    # if X_df.shape[1] > max_vars_for_vif:
                    #     self.logger.warning(f"Too many variables ({X_df.shape[1]}). Calculating VIF for top {max_vars_for_vif} variables.")
                    #     X_df = X_df.iloc[:, :max_vars_for_vif]
                    #     # Update valid_independent to match
                    #     valid_independent = valid_independent[:max_vars_for_vif]
                    
                    # MEMORY OPTIMIZATION 4: Estimate memory requirement before processing
                    estimated_memory_gb = (X_df.shape[0] * X_df.shape[1] * 8) / (1024**3)  # 8 bytes per float64
                    max_memory_gb = 1.5  # Maximum 1.5 GB for VIF calculation
                    
                    if estimated_memory_gb > max_memory_gb:
                        self.logger.warning(f"Estimated memory requirement ({estimated_memory_gb:.2f} GB) exceeds limit ({max_memory_gb} GB). Skipping VIF calculation.")
                        for var in valid_independent:
                            vif_data[var] = None
                    else:
                        # Ensure strictly float dtype columns (coerce if needed)
                        for col in X_df.columns:
                            if not pd.api.types.is_numeric_dtype(X_df[col]):
                                X_df[col] = pd.to_numeric(X_df[col], errors='coerce')
                            # REMOVED: Don't fill NaN here - we'll handle it separately for VIF to match helpers.py

                        # Drop constant/near-constant columns to avoid singular matrices
                        nunique = X_df.nunique(dropna=False)
                        constant_cols = nunique[nunique <= 1].index.tolist()
                        if constant_cols:
                            self.logger.warning(f"Dropping constant columns for VIF: {constant_cols}")
                            X_df = X_df.drop(columns=constant_cols, errors='ignore')

                        if X_df.shape[1] <= 1:
                            # Not enough columns to compute VIF
                            for var in valid_independent:
                                vif_data[var] = None
                        else:
                            # FAST VIF CALCULATION: Using correlation matrix approach (10-30x faster)
                            # Replaces slow regression-based variance_inflation_factor method
                            try:
                                # Prepare clean numeric data for VIF (MATCH helpers.py methodology)
                                X_df_clean = X_df.copy()
                                
                                # Remove infinite values (same as helpers.py)
                                X_df_clean = X_df_clean.replace([np.inf, -np.inf], np.nan)
                                
                                # CHANGED: Match helpers.py - Filter valid columns (min 100 rows or 10% of data)
                                non_null_counts = X_df_clean.notna().sum()
                                min_valid_rows = min(100, len(X_df_clean) * 0.1)
                                valid_vif_cols = non_null_counts[non_null_counts >= min_valid_rows].index.tolist()
                                
                                if len(valid_vif_cols) < 2:
                                    self.logger.warning(f"Not enough valid columns for VIF calculation: {len(valid_vif_cols)} < 2")
                                    for var in valid_independent:
                                        vif_data[var] = None
                                else:
                                    # Use only valid columns (matching helpers.py)
                                    X_df_clean = X_df_clean[valid_vif_cols]
                                    
                                    # CHANGED: DO NOT fill NaN - match helpers.py pairwise deletion behavior
                                    # This ensures VIF values match data insights calculation
                                    
                                    # FAST METHOD: Calculate correlation matrix once (O(p²) instead of O(n*p³))
                                    self.logger.info(f"Calculating VIF using fast correlation matrix method for {X_df_clean.shape[1]} variables (matching helpers.py methodology)")
                                
                                    try:
                                        # Compute correlation matrix once (vectorized, much faster)
                                        # This will use pairwise deletion for NaN values (matching helpers.py)
                                        corr_matrix = X_df_clean.corr()
                                        
                                        # Calculate VIF for each variable using correlation approximation
                                        for var in X_df_clean.columns:
                                            try:
                                                # Get all other columns
                                                other_cols = [c for c in X_df_clean.columns if c != var]
                                                
                                                if not other_cols:
                                                    vif_value = 1.0
                                                else:
                                                    # Get maximum correlation with other columns
                                                    corr_with_others = corr_matrix.loc[var, other_cols].abs()
                                                    max_corr = corr_with_others.max()
                                                    
                                                    # Approximate VIF: VIF ≈ 1/(1-r²) where r is max correlation
                                                    if pd.isna(max_corr) or max_corr >= 0.999:
                                                        vif_value = float('inf')
                                                    else:
                                                        vif_value = 1 / (1 - max_corr**2)
                                                    
                                                    # Cap extremely large values (same as before)
                                                    if vif_value > 1e6:
                                                        vif_value = 1e6
                                                
                                                vif_data[var] = float(vif_value) if vif_value != float('inf') else None
                                                
                                            except Exception as ve:
                                                self.logger.warning(f"VIF calculation failed for {var}: {str(ve)}")
                                                vif_data[var] = None
                                        
                                        # Map back for all variables (including dropped/constant ones)
                                        for var in valid_independent:
                                            if var not in vif_data:
                                                vif_data[var] = None
                                        
                                        successful_vifs = len([v for v in vif_data.values() if v is not None])
                                        self.logger.info(f"VIF calculation completed successfully: {successful_vifs}/{len(valid_independent)} variables calculated (matching helpers.py methodology)")
                                    
                                    except MemoryError as me:
                                        self.logger.error(f"Memory error during fast VIF calculation: {str(me)}. Skipping VIF for all variables.")
                                        for var in valid_independent:
                                            vif_data[var] = None
                                    except Exception as e:
                                        self.logger.warning(f"Fast VIF calculation failed: {str(e)}. Falling back to None values.")
                                        for var in valid_independent:
                                            vif_data[var] = None
                                    
                            except MemoryError as me:
                                self.logger.error(f"Memory error during VIF calculation: {str(me)}. Skipping VIF for all variables.")
                                for var in valid_independent:
                                    vif_data[var] = None
                except MemoryError as me:
                    self.logger.error(f"Memory error in VIF calculation: {str(me)}")
                    for var in valid_independent:
                        vif_data[var] = None
                except Exception as e:
                    self.logger.warning(f"VIF calculation failed: {str(e)}")
                    for var in valid_independent:
                        vif_data[var] = None
            else:
                # If statsmodels not available or only 1 variable
                self.logger.warning("VIF calculation not available")
                for var in valid_independent:
                    vif_data[var] = None
            
            # Calculate Information Value (IV)
            self.logger.info(f"Starting IV (Information Value) calculation for {len(valid_independent)} variables")
            iv_values: Dict[str, Optional[float]] = {}
            iv_event_label: Dict[str, Optional[str]] = {}
            try:
                # IV is defined for classification problems. If binary, compute directly.
                nunique_target = df_numeric[target_column].nunique(dropna=True)
                is_binary_target = nunique_target == 2
                is_continuous_target = nunique_target > 20  # Threshold for continuous target
                
                # Handle continuous target by binning into binary (High/Low)
                target_series_for_iv = df_numeric[target_column].copy()
                if is_continuous_target:
                    self.logger.info(f"Target is continuous ({nunique_target} unique values). Binning into High/Low for IV calculation.")
                    try:
                        median_val = safe_median(target_series_for_iv)
                        # Check if all values are same
                        if target_series_for_iv.nunique() == 1:
                            self.logger.warning("All target values are same. Skipping IV calculation.")
                            for var in valid_independent:
                                iv_values[var] = None
                                iv_event_label[var] = None
                        else:
                            target_series_for_iv = (target_series_for_iv > median_val).astype(int)
                            is_binary_target = True  # Treat as binary after binning
                    except Exception as e:
                        self.logger.warning(f"Error binning continuous target: {str(e)}. Skipping IV calculation.")
                        for var in valid_independent:
                            iv_values[var] = None
                            iv_event_label[var] = None
                        is_binary_target = False  # Skip IV calculation
                
                if is_binary_target:
                    # Define event as the class with label 1 if available, else the max label
                    if is_continuous_target:
                        # For continuous binned target, events are High (1)
                        event_label = 1
                        total_events = int(target_series_for_iv.sum())
                        total_non_events = len(target_series_for_iv) - total_events
                    else:
                        # Original binary target
                        event_label = 1 if 1 in set(df_numeric[target_column].unique()) else df_numeric[target_column].max()
                        total_events = (df_numeric[target_column] == event_label).sum()
                        total_non_events = len(df_numeric) - total_events
                    epsilon = 1e-10

                    for var in valid_independent:
                        try:
                            series = df_numeric[var]
                            # For numeric variables, create quantile bins; for categorical, use categories
                            if pd.api.types.is_numeric_dtype(series):
                                try:
                                    bins = pd.qcut(series, q=min(10, series.nunique()), duplicates='drop')
                                except Exception:
                                    bins = pd.cut(series, bins=min(10, series.nunique()))
                            else:
                                bins = series.astype(str)

                            # Use binned target if continuous, otherwise use original
                            if is_continuous_target:
                                target_for_iv = target_series_for_iv
                            else:
                                target_for_iv = (df_numeric[target_column] == event_label).astype(int)
                            
                            grouped = pd.DataFrame({
                                'bin': bins,
                                'is_event': target_for_iv
                            })
                            grp = grouped.groupby('bin')['is_event'].agg(['sum', 'count']).reset_index()
                            grp.rename(columns={'sum': 'events', 'count': 'total'}, inplace=True)
                            grp['non_events'] = grp['total'] - grp['events']
                            # Distributions
                            grp['dist_event'] = grp['events'] / max(total_events, 1)
                            grp['dist_non_event'] = grp['non_events'] / max(total_non_events, 1)
                            # WOE with stability additions
                            grp['woe'] = np.log((grp['dist_event'] + epsilon) / (grp['dist_non_event'] + epsilon))
                            grp['iv_component'] = (grp['dist_event'] - grp['dist_non_event']) * grp['woe']
                            iv = float(grp['iv_component'].replace([np.inf, -np.inf], 0).fillna(0).sum())
                            # Clip unusually high values for safety
                            iv_values[var] = iv if np.isfinite(iv) else None
                            iv_event_label[var] = 'High' if is_continuous_target else str(event_label)
                        except Exception:
                            iv_values[var] = None
                            iv_event_label[var] = None
                else:
                    # For multi-class targets, compute one-vs-rest IV per class and keep the maximum IV per variable
                    # This provides a useful signal while keeping semantics clear (stored in iv_event_label)
                    classes = list(pd.unique(df_numeric[target_column]))[:10]  # safety cap at 10 classes
                    epsilon = 1e-10
                    for var in valid_independent:
                        best_iv = None
                        best_label = None
                        series = df_numeric[var]
                        # Prepare binning once per variable
                        if pd.api.types.is_numeric_dtype(series):
                            try:
                                base_bins = pd.qcut(series, q=min(10, max(2, series.nunique())), duplicates='drop')
                            except Exception:
                                base_bins = pd.cut(series, bins=min(10, max(2, series.nunique())))
                        else:
                            base_bins = series.astype(str)
                        for cls in classes:
                            try:
                                grouped = pd.DataFrame({
                                    'bin': base_bins,
                                    'is_event': (df_numeric[target_column] == cls).astype(int)
                                })
                                grp = grouped.groupby('bin')['is_event'].agg(['sum', 'count']).reset_index()
                                grp.rename(columns={'sum': 'events', 'count': 'total'}, inplace=True)
                                grp['non_events'] = grp['total'] - grp['events']
                                total_events = int(grp['events'].sum())
                                total_non_events = int(grp['non_events'].sum())
                                if total_events == 0 or total_non_events == 0:
                                    continue
                                grp['dist_event'] = grp['events'] / max(total_events, 1)
                                grp['dist_non_event'] = grp['non_events'] / max(total_non_events, 1)
                                grp['woe'] = np.log((grp['dist_event'] + epsilon) / (grp['dist_non_event'] + epsilon))
                                grp['iv_component'] = (grp['dist_event'] - grp['dist_non_event']) * grp['woe']
                                iv = float(grp['iv_component'].replace([np.inf, -np.inf], 0).fillna(0).sum())
                                if np.isfinite(iv):
                                    if best_iv is None or iv > best_iv:
                                        best_iv = iv
                                        best_label = cls
                            except Exception:
                                continue
                        iv_values[var] = best_iv
                        iv_event_label[var] = None if best_label is None else str(best_label)
                
                successful_ivs = len([v for v in iv_values.values() if v is not None])
                self.logger.info(f"IV calculation completed successfully: {successful_ivs}/{len(valid_independent)} variables calculated")
            except Exception:
                for var in valid_independent:
                    iv_values[var] = None
                    iv_event_label[var] = None
                self.logger.warning("IV calculation failed for all variables")

            # VARIANCE CALCULATION: Calculate variance/std and single-value percentage for each variable
            # This helps identify zero/near-zero variance variables (E01 - Technical Eligibility)
            self.logger.info(f"Starting Variance calculation for {len(valid_independent)} variables")
            variance_data: Dict[str, Dict[str, Any]] = {}
            try:
                for var in valid_independent:
                    s = df_numeric[var]
                    # Calculate standard deviation
                    try:
                        std_val = float(s.std()) if pd.api.types.is_numeric_dtype(s) else None
                    except Exception:
                        std_val = None
                    
                    # Calculate single value percentage (what % of rows have the most common value)
                    try:
                        value_counts = s.value_counts(dropna=False)
                        max_count = value_counts.iloc[0] if len(value_counts) > 0 else 0
                        single_val_pct = float(max_count / len(s)) if len(s) > 0 else 0.0
                    except Exception:
                        single_val_pct = 0.0
                    
                    # Get unique count
                    try:
                        unique_count = int(s.nunique(dropna=True))
                    except Exception:
                        unique_count = 0
                    
                    # Determine if variable has zero/near-zero variance
                    # Near-zero variance: >95% of values are the same OR std < 0.01
                    is_zero_variance = unique_count <= 1
                    is_near_zero_variance = single_val_pct > 0.95 or (std_val is not None and std_val < 0.01 and pd.api.types.is_numeric_dtype(s))
                    
                    variance_data[var] = {
                        'std': std_val,
                        'single_value_pct': single_val_pct,
                        'unique_count': unique_count,
                        'is_zero_variance': is_zero_variance,
                        'is_near_zero_variance': is_near_zero_variance,
                        'variance_status': 'zero' if is_zero_variance else ('near_zero' if is_near_zero_variance else 'ok')
                    }
                
                successful_variance = len([v for v in variance_data.values() if v.get('std') is not None])
                self.logger.info(f"Variance calculation completed successfully: {successful_variance}/{len(valid_independent)} variables calculated")
            except Exception as e:
                self.logger.warning(f"Variance calculation failed: {str(e)}")
                for var in valid_independent:
                    variance_data[var] = {
                        'std': None,
                        'single_value_pct': None,
                        'unique_count': None,
                        'is_zero_variance': None,
                        'is_near_zero_variance': None,
                        'variance_status': 'unknown'
                    }

            # Feature metadata for Step 1 lock grid
            def _infer_feature_type_and_source(var_name: str, original_series: pd.Series):
                v = str(var_name).lower()
                # FE agent generated transformations
                if 'transform_woe' in v or v.endswith('_woe') or '_woe_' in v:
                    return 'WoE', 'FE Agent'
                if 'transform_ohe' in v or '_ohe_' in v:
                    return 'OHE', 'FE Agent'
                if 'transform_log' in v or v.endswith('_log') or '_log_' in v:
                    return 'LOG', 'FE Agent'

                # Original feature typing
                if pd.api.types.is_datetime64_any_dtype(original_series):
                    return 'Date', 'Original'
                if pd.api.types.is_bool_dtype(original_series):
                    return 'Ordinal', 'Original'
                if pd.api.types.is_numeric_dtype(original_series):
                    clean = pd.to_numeric(original_series, errors='coerce').dropna()
                    is_integer_like = bool(((clean % 1) == 0).all()) if len(clean) > 0 else False
                    unique_count = int(clean.nunique()) if len(clean) > 0 else 0
                    if is_integer_like and unique_count <= 10:
                        return 'Ordinal', 'Original'
                    return 'Continuous', 'Original'
                return 'Categorical', 'Original'

            missing_pct_map: Dict[str, float] = {}
            for var in valid_independent:
                try:
                    missing_pct_map[var] = float(round((df[var].isna().mean() * 100.0), 2))
                except Exception:
                    missing_pct_map[var] = 0.0

            # Compile results
            variable_stats = []
            for var in valid_independent:
                var_variance = variance_data.get(var, {})
                feature_type, feature_source = _infer_feature_type_and_source(var, df[var])
                stats = {
                    'variable': var,
                    'type': feature_type,
                    'source': feature_source,
                    'correlation': correlations.get(var, 0.0),
                    'vif': vif_data.get(var),
                    'iv': iv_values.get(var),
                    'iv_event': iv_event_label.get(var),
                    'abs_correlation': abs(correlations.get(var, 0.0)),
                    'missing_pct': missing_pct_map.get(var, 0.0),
                    # Variance statistics
                    'std': var_variance.get('std'),
                    'single_value_pct': var_variance.get('single_value_pct'),
                    'unique_count': var_variance.get('unique_count'),
                    'variance_status': var_variance.get('variance_status', 'unknown')
                }
                variable_stats.append(stats)
            
            # Sort by absolute correlation (descending)
            variable_stats.sort(key=lambda x: x['abs_correlation'], reverse=True)
            
            # Categorize variables based on selection criteria thresholds only
            # Selection criteria: |Correlation| ≥ 0.05, VIF ≤ 10, IV ≥ 0.02, good variance
            high_corr_vars = [v['variable'] for v in variable_stats if abs(v['correlation']) >= 0.05]
            good_vif_vars = [v['variable'] for v in variable_stats if v['vif'] and v['vif'] <= 10]
            strong_iv_vars = [v['variable'] for v in variable_stats if v.get('iv') is not None and v.get('iv') >= 0.02]
            
            # Variance-based categorization
            zero_variance_vars = [v['variable'] for v in variable_stats if v.get('variance_status') == 'zero']
            near_zero_variance_vars = [v['variable'] for v in variable_stats if v.get('variance_status') == 'near_zero']
            good_variance_vars = [v['variable'] for v in variable_stats if v.get('variance_status') == 'ok']
            
            return {
                'variable_statistics': variable_stats,
                'summary': {
                    'total_variables': len(valid_independent),
                    'high_correlation_count': len(high_corr_vars),  # |Correlation| ≥ 0.05
                    'good_vif_count': len(good_vif_vars),  # VIF ≤ 10
                    'strong_iv_count': len(strong_iv_vars),  # IV ≥ 0.02
                    'good_variance_count': len(good_variance_vars),  # Variance OK
                    'zero_variance_count': len(zero_variance_vars),  # Zero variance (should be excluded)
                    'near_zero_variance_count': len(near_zero_variance_vars),  # Near-zero variance (caution)
                    'high_correlation_variables': high_corr_vars,
                    'good_vif_variables': good_vif_vars,
                    'strong_iv_variables': strong_iv_vars,
                    'good_variance_variables': good_variance_vars,
                    'zero_variance_variables': zero_variance_vars,
                    'near_zero_variance_variables': near_zero_variance_vars
                },
                'interpretation': {
                    'vif_threshold': 10.0,
                    'vif_interpretation': 'VIF ≤ 10 indicates acceptable multicollinearity',
                    'correlation_threshold_high': 0.05,
                    'correlation_interpretation': 'Higher absolute correlation indicates stronger relationship with target',
                    'iv_threshold': 0.02,
                    'iv_guideline': 'IV < 0.02 (useless), 0.02-0.1 (weak), 0.1-0.3 (medium), >0.3 (strong)',
                    'variance_interpretation': 'Zero variance = only 1 unique value (exclude), Near-zero variance = >95% same value or std<0.01 (caution)',
                    'variance_guideline': 'Variables with zero or near-zero variance have little predictive power and may cause model issues'
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating VIF and correlation: {str(e)}")
            raise

    def _preprocess(self, df: pd.DataFrame, target_column: str, independent_variables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Lightweight preprocessing similar to main service - skips if already preprocessed.
        - selects features (all except target if independent_variables is None/empty)
        - fills missing values (median for numeric, mode for categorical)
        - label-encodes categorical
        - standardizes numeric columns
        Returns: dict with X, y, encoders, scaler, preprocessing_summary
        """
        feature_columns: List[str]
        if not independent_variables:
            # Use all columns except target by default
            excluded = {target_column}
            feature_columns = [c for c in df.columns if c not in excluded]
        else:
            feature_columns = [c for c in independent_variables if c in df.columns]

        # Include feature engineered columns by default so FE results flow into training
        transform_cols = [c for c in df.columns if "transform" in c and c != target_column]
        for c in transform_cols:
            if c not in feature_columns:
                feature_columns.append(c)
        if target_column not in df.columns:
            raise ValueError(f"Target column '{target_column}' not found in dataset")

        X = df[feature_columns].copy()
        y = df[target_column].copy()
        
        # Initialize preprocessing summary
        preprocessing_summary = {
            'is_already_preprocessed': False,
            'variables': [],
            'dropped_variables': [],
            'total_processed': 0,
            'total_dropped': 0
        }
        
        # Store original X for comparison
        X_original = X.copy()
        
        # CHECK: Is data already preprocessed?
        has_nan = X.isna().any().any() or y.isna().any()
        has_categorical = len(X.select_dtypes(include=['object', 'category']).columns) > 0
        numerical_cols = X.select_dtypes(include=[np.number]).columns
        has_inf = False
        if len(numerical_cols) > 0:
            has_inf = np.isinf(X[numerical_cols].values).any()
        
        is_already_preprocessed = not has_nan and not has_categorical and not has_inf
        
        if is_already_preprocessed:
            self.logger.info("Data appears to be already preprocessed. Skipping preprocessing steps.")
            preprocessing_summary['is_already_preprocessed'] = True
            # Only do minimal verification
            # Verify all columns are numerical
            non_numeric_cols = X.select_dtypes(exclude=[np.number]).columns
            if len(non_numeric_cols) > 0:
                self.logger.warning(f"Found non-numeric columns in preprocessed data: {non_numeric_cols.tolist()}")
                # Force convert to numeric
                for col in non_numeric_cols:
                    X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)
            
            # Final safety check - fill any NaN that might have appeared
            if X.isna().any().any():
                self.logger.warning("Found NaN values in preprocessed data, filling with 0")
                X = X.fillna(0)
            
            # Initialize empty encoders/scaler since we skipped preprocessing
            from sklearn.preprocessing import LabelEncoder, StandardScaler
            
            # Check if target needs encoding (even if data is preprocessed)
            if y.dtype in ['object', 'category']:
                self.logger.info("Target column is categorical in preprocessed data. Encoding to numeric.")
                le_target = LabelEncoder()
                y = pd.Series(le_target.fit_transform(y.astype(str)), index=y.index, name=y.name)
                self.target_encoder = le_target
                self.logger.info(f"Target classes: {dict(zip(le_target.classes_, range(len(le_target.classes_))))}")
            else:
                self.target_encoder = None
            
            return {"X": X, "y": y, "encoders": {}, "scaler": None, "X_before_scaling": X.copy(), "preprocessing_summary": preprocessing_summary}
        
        # DATA NOT PREPROCESSED - DO FULL PREPROCESSING
        self.logger.info("Data not preprocessed. Starting full preprocessing pipeline.")
        
        # Import LabelEncoder and StandardScaler at the start (needed for target encoding and later steps)
        from sklearn.preprocessing import LabelEncoder, StandardScaler
        
        # Track dropped columns
        dropped_columns = []
        
        # STEP 1: Drop entirely NaN columns
        columns_before = set(X.columns)
        X = X.dropna(axis=1, how='all')
        columns_after = set(X.columns)
        dropped_all_nan = list(columns_before - columns_after)
        if dropped_all_nan:
            dropped_columns.extend(dropped_all_nan)
            for col in dropped_all_nan:
                preprocessing_summary['dropped_variables'].append({
                    'variable': col,
                    'reason': 'All values are missing (NaN)',
                    'details': 'Column had no valid values'
                })
        self.logger.info(f"After dropping entirely NaN columns: {X.shape[1]} features remaining")
        
        # STEP 2: Handle target column NaN - drop rows with NaN target
        rows_before = len(X)
        if y.isna().any():
            nan_mask = y.isna()
            self.logger.warning(f"Dropping {nan_mask.sum()} rows with NaN target values")
            X = X[~nan_mask]
            y = y[~nan_mask]
        rows_after = len(X)
        
        # STEP 2.5: Encode categorical target to numeric (if needed)
        if y.dtype in ['object', 'category']:
            self.logger.info(f"Target column is categorical. Encoding to numeric.")
            le_target = LabelEncoder()
            y = pd.Series(le_target.fit_transform(y.astype(str)), index=y.index, name=y.name)
            # Store target encoder for later use (if needed for predictions)
            self.target_encoder = le_target
            self.logger.info(f"Target classes: {dict(zip(le_target.classes_, range(len(le_target.classes_))))}")
        else:
            self.target_encoder = None

        # STEP 3: Handle missing values in features and track preprocessing
        # OPTIMIZED: Vectorized operations instead of per-column loop for better performance
        missing_value_details = {}
        sparse_ohe_columns = []  # Track sparse OHE columns to skip scaling
        
        # Vectorized detection of sparse and OHE columns
        all_columns = list(X.columns)
        sparse_cols_set = set()
        ohe_cols_set = set()
        for col in all_columns:
            try:
                if isinstance(X[col].dtype, pd.SparseDtype):
                    sparse_cols_set.add(col)
            except Exception:
                pass
            if '_transform_OHE' in col:
                ohe_cols_set.add(col)
        sparse_ohe_columns = list(sparse_cols_set | ohe_cols_set)
        
        # Vectorized missing value detection - compute all at once
        missing_counts = X.isna().sum()
        total_count = len(X)
        cols_with_missing = missing_counts[missing_counts > 0].index.tolist()
        
        # Separate columns by type for batch processing
        cat_cols = X.select_dtypes(include=['object', 'category']).columns.tolist()
        num_cols = X.select_dtypes(include=[np.number]).columns.tolist()
        
        # Batch fill categorical columns with mode
        cat_cols_with_missing = [c for c in cols_with_missing if c in cat_cols]
        if cat_cols_with_missing:
            for col in cat_cols_with_missing:
                mode_val = X[col].mode()
                fill_value = mode_val.iloc[0] if not mode_val.empty else 'Unknown'
                X[col] = X[col].fillna(fill_value)
                missing_count = int(missing_counts[col])
                missing_pct = (missing_count / total_count * 100)
                missing_value_details[col] = {
                    'variable': col,
                    'missing_imputation': {
                        'method': 'mode',
                        'value': str(fill_value),
                        'missing_count': missing_count,
                        'missing_percentage': round(missing_pct, 2),
                        'reason': f'{missing_count} missing values ({missing_pct:.2f}%) found → Filled with mode'
                    },
                    'encoding': None,
                    'scaling': None
                }
        
        # Batch fill sparse OHE columns with 0
        sparse_cols_with_missing = [c for c in cols_with_missing if c in sparse_ohe_columns and c not in cat_cols]
        if sparse_cols_with_missing:
            for col in sparse_cols_with_missing:
                try:
                    fill_val = X[col].dtype.fill_value if isinstance(X[col].dtype, pd.SparseDtype) else 0
                except Exception:
                    fill_val = 0
                X[col] = X[col].fillna(fill_val)
                missing_count = int(missing_counts[col])
                missing_pct = (missing_count / total_count * 100)
                missing_value_details[col] = {
                    'variable': col,
                    'missing_imputation': {
                        'method': 'sparse_fill',
                        'value': int(fill_val),
                        'missing_count': missing_count,
                        'missing_percentage': round(missing_pct, 2),
                        'reason': f'{missing_count} missing values ({missing_pct:.2f}%) found → Filled with sparse fill_value'
                    },
                    'encoding': None,
                    'scaling': None
                }
        
        # Batch fill numeric columns with median - VECTORIZED (single .median() call for all columns)
        num_cols_with_missing = [c for c in cols_with_missing if c in num_cols and c not in sparse_ohe_columns]
        if num_cols_with_missing:
            medians = X[num_cols_with_missing].median()
            for col in num_cols_with_missing:
                median_val = medians[col]
                fill_value = 0.0 if pd.isna(median_val) else float(median_val)
                X[col] = X[col].fillna(fill_value)
                missing_count = int(missing_counts[col])
                missing_pct = (missing_count / total_count * 100)
                missing_value_details[col] = {
                    'variable': col,
                    'missing_imputation': {
                        'method': 'median',
                        'value': fill_value,
                        'missing_count': missing_count,
                        'missing_percentage': round(missing_pct, 2),
                        'reason': f'{missing_count} missing values ({missing_pct:.2f}%) found → Filled with median'
                    },
                    'encoding': None,
                    'scaling': None
                }
        
        # Initialize missing_value_details for columns without missing values
        for col in all_columns:
            if col not in missing_value_details:
                missing_value_details[col] = {
                    'variable': col,
                    'missing_imputation': None,
                    'encoding': None,
                    'scaling': None
                }

        # STEP 4: Encode categoricals
        # LabelEncoder and StandardScaler already imported above
        label_encoders: Dict[str, Any] = {}
        # CRITICAL: Store original data BEFORE encoding for granular accuracy
        X_before_encoding = X.copy()  # Store original categorical values (strings like "RENT", "OWN", etc.)
        
        categorical_columns = X.select_dtypes(include=['object', 'category']).columns
        for col in categorical_columns:
            le = LabelEncoder()
            original_values = X[col].unique()[:10]  # Sample of original values
            X[col] = le.fit_transform(X[col].astype(str))
            encoded_values = X[col].unique()[:10]  # Sample of encoded values
            
            # Create mapping for display
            class_mapping = dict(zip(le.classes_, range(len(le.classes_))))
            mapping_sample = {str(k): int(v) for k, v in list(class_mapping.items())[:5]}
            
            label_encoders[col] = le
            if col in missing_value_details:
                missing_value_details[col]['encoding'] = {
                    'method': 'label_encoding',
                    'mapping_sample': mapping_sample,
                    'unique_values_count': len(le.classes_),
                    'reason': 'Categorical text cannot be used by ML models'
                }
            else:
                missing_value_details[col] = {
                    'variable': col,
                    'missing_imputation': None,
                    'encoding': {
                        'method': 'label_encoding',
                        'mapping_sample': mapping_sample,
                        'unique_values_count': len(le.classes_),
                        'reason': 'Categorical text cannot be used by ML models'
                    },
                    'scaling': None
                }

        # STEP 5: Scale numeric and track scaling
        # Store data before scaling for continuous variable intervals
        X_before_scaling = X.copy()
        
        numeric_cols = X.select_dtypes(include=[np.number]).columns
        
        # OPTIMIZATION: Skip scaling for sparse/binary OHE columns
        # OHE columns are already 0/1 binary - scaling them is unnecessary and can hurt performance
        cols_to_scale = [col for col in numeric_cols if col not in sparse_ohe_columns]
        skipped_ohe_cols = [col for col in numeric_cols if col in sparse_ohe_columns]
        
        if skipped_ohe_cols:
            self.logger.info(f"Skipping scaling for {len(skipped_ohe_cols)} OHE columns (already binary 0/1)")
        
        if len(cols_to_scale) > 0:
            scaler = StandardScaler()
            # Store original ranges before scaling
            original_stats = {}
            for col in cols_to_scale:
                original_stats[col] = {
                    'min': float(X[col].min()),
                    'max': float(X[col].max()),
                    'mean': float(X[col].mean()),
                    'std': float(X[col].std())
                }
            X[cols_to_scale] = scaler.fit_transform(X[cols_to_scale])
            # Store scaled ranges
            for col in cols_to_scale:
                scaled_min = float(X[col].min())
                scaled_max = float(X[col].max())
                scaled_mean = float(X[col].mean())
                scaled_std = float(X[col].std())
                orig = original_stats[col]
                if col in missing_value_details:
                    missing_value_details[col]['scaling'] = {
                        'method': 'standard_scaling',
                        'original_range': [orig['min'], orig['max']],
                        'scaled_range': [scaled_min, scaled_max],
                        'original_mean': orig['mean'],
                        'original_std': orig['std'],
                        'reason': 'Numeric feature needs normalization for ML models'
                    }
                else:
                    missing_value_details[col] = {
                        'variable': col,
                        'missing_imputation': None,
                        'encoding': None,
                        'scaling': {
                            'method': 'standard_scaling',
                            'original_range': [orig['min'], orig['max']],
                            'scaled_range': [scaled_min, scaled_max],
                            'original_mean': orig['mean'],
                            'original_std': orig['std'],
                            'reason': 'Numeric feature needs normalization for ML models'
                        }
                    }
            
            # Mark OHE columns as not scaled (for transparency)
            for col in skipped_ohe_cols:
                if col in missing_value_details:
                    missing_value_details[col]['scaling'] = {
                        'method': 'none',
                        'reason': 'Binary OHE column - scaling not required'
                    }
                else:
                    missing_value_details[col] = {
                        'variable': col,
                        'missing_imputation': None,
                        'encoding': None,
                        'scaling': {
                            'method': 'none',
                            'reason': 'Binary OHE column - scaling not required'
                        }
                    }
        else:
            scaler = None

        # Check for constant variables (should be dropped but might have been missed)
        for col in X.columns:
            if col not in dropped_columns:
                unique_count = X[col].nunique()
                if unique_count <= 1:
                    dropped_columns.append(col)
                    preprocessing_summary['dropped_variables'].append({
                        'variable': col,
                        'reason': 'Only 1 unique value (no predictive power)',
                        'details': f'All rows have the same value'
                    })

        # STEP 6: Final NaN check - fill any remaining NaN with 0
        if X.isna().any().any():
            self.logger.warning("Found NaN values after preprocessing, filling with 0")
            X = X.fillna(0)
        
        # STEP 7: Verify all data is numerical
        non_numeric_cols = X.select_dtypes(exclude=[np.number]).columns
        if len(non_numeric_cols) > 0:
            self.logger.warning(f"Found non-numeric columns after preprocessing: {non_numeric_cols.tolist()}")
            # Force convert to numeric
            for col in non_numeric_cols:
                X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)

        # Build final preprocessing summary
        for col in X.columns:
            if col not in dropped_columns and col in missing_value_details:
                preprocessing_summary['variables'].append(missing_value_details[col])
        
        preprocessing_summary['total_processed'] = len(preprocessing_summary['variables'])
        preprocessing_summary['total_dropped'] = len(preprocessing_summary['dropped_variables'])

        return {"X": X, "y": y, "encoders": label_encoders, "scaler": scaler, "X_before_scaling": X_before_scaling, "X_before_encoding": X_before_encoding, "preprocessing_summary": preprocessing_summary}

    def train_multiple_models(self, df: pd.DataFrame, target_column: str,
                              independent_variables: Optional[List[str]],
                              algorithms: List[str],
                              algorithm_params: Optional[Dict[str, Any]] = None,
                              max_iterations: int = 3,
                              dataset_id: Optional[str] = None,
                              algorithm_param_ranges: Optional[Dict[str, Any]] = None,
                              optimization_method: str = 'random',
                              weight_variable: Optional[str] = None,
                              locked_variables: Optional[List[str]] = None,
                              target_metric: Optional[str] = None,
                              cv_folds: Optional[int] = None,
                              optuna_trials: Optional[int] = None,
                              early_stopping_rounds: Optional[int] = None,
                              lr_backward_elimination: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:  # Optimized: Reduced from 5 to 3 for faster training
        """Train and evaluate multiple specified algorithms.
        Returns a list of result dicts with metrics for comparison.
        
        Args:
            df: DataFrame containing the data
            target_column: Name of the target column
            independent_variables: List of independent variables
            algorithms: List of algorithms to train
            algorithm_params: Optional algorithm parameters (for backward compatibility)
            max_iterations: Maximum number of training iterations
            dataset_id: Optional dataset ID to save preprocessed data to state manager
            algorithm_param_ranges: Optional user-defined hyperparameter ranges {algo: {param: {min, max}}}
            weight_variable: Optional column name for sample weights (passed to model.fit as sample_weight)
        """
        # Densify any sparse columns - pandas cannot compute std/mean/quantile on Sparse dtypes
        # and sklearn estimators may also reject them.  This is a no-op for dense DataFrames.
        sparse_cols = [c for c in df.columns if isinstance(df[c].dtype, pd.SparseDtype)]
        if sparse_cols:
            self.logger.info(f"Densifying {len(sparse_cols)} sparse column(s) before training")
            df = df.copy()
            for c in sparse_cols:
                df[c] = df[c].sparse.to_dense()

        resolved_cv_folds = self._safe_int(cv_folds, 3)
        resolved_cv_folds = max(2, min(10, resolved_cv_folds))
        resolved_optuna_trials = self._safe_int(optuna_trials, 0)
        resolved_optuna_trials = resolved_optuna_trials if resolved_optuna_trials > 0 else None
        resolved_early_stopping = self._safe_int(early_stopping_rounds, 0)
        resolved_early_stopping = resolved_early_stopping if resolved_early_stopping > 0 else None

        # Apply lock-aware variable selection before training.
        available_vars = self.get_available_variables(df)
        candidate_independent = available_vars.get('default_independent', [])
        if target_column in candidate_independent:
            candidate_independent.remove(target_column)
        variable_selection = self.apply_variable_locking(
            independent_variables=candidate_independent,
            selected_variables=independent_variables,
            locked_variables=locked_variables,
            selection_mode='manual',
        )
        independent_variables = variable_selection.get('selected_variables', [])
        if not independent_variables:
            raise ValueError("No independent variables available after applying manual locks/selection")
        correlation_map = self._compute_bivariate_correlation_map(df, target_column, independent_variables)

        # Generate column_stats BEFORE preprocessing (to get original data types)
        from app.services.model_training_auto_training import generate_column_stats
        column_stats = generate_column_stats(df, independent_variables or [])
        self.logger.info(f"Generated column_stats for {len(column_stats)} features")
        
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score, f1_score,
            roc_auc_score, log_loss, r2_score, mean_squared_error, mean_absolute_error,
        )
        import joblib, os, uuid
        from app.services.dataframe_state_manager import dataframe_state_manager

        # Extract sample weights BEFORE preprocessing (weight column is NOT a feature)
        sample_weights = None
        if weight_variable and weight_variable in df.columns:
            sample_weights = df[weight_variable].values.copy()
            self.logger.info(f"Extracted sample weights from '{weight_variable}' column ({len(sample_weights)} values)")
            # Ensure weight variable is excluded from independent variables
            if independent_variables and weight_variable in independent_variables:
                independent_variables = [v for v in independent_variables if v != weight_variable]
                self.logger.info(f"Removed weight variable '{weight_variable}' from independent variables")

        # Preprocess - use cache when dataset/variables/target haven't changed
        _cache_key = (dataset_id, frozenset(independent_variables or []), target_column)
        _cached = self._preprocess_cache.get(_cache_key)
        _cache_valid = False
        if _cached is not None and dataset_id:
            try:
                from app.services.dataframe_state_manager import dataframe_state_manager as _dsm_c
                _meta_c = _dsm_c.get_dataset_info(dataset_id)
                if _meta_c and _meta_c.get("last_updated") == _cached[1]:
                    pp = _cached[0]
                    _cache_valid = True
                    self.logger.info(f"Preprocessing cache hit for dataset={dataset_id}")
            except Exception:
                pass

        if not _cache_valid:
            pp = self._preprocess(df, target_column, independent_variables)
            if dataset_id:
                try:
                    from app.services.dataframe_state_manager import dataframe_state_manager as _dsm_c2
                    _meta_c2 = _dsm_c2.get_dataset_info(dataset_id)
                    _last_upd_c = _meta_c2.get("last_updated") if _meta_c2 else None
                    self._preprocess_cache[_cache_key] = (pp, _last_upd_c)
                except Exception:
                    pass

        X, y = pp['X'], pp['y']
        X_before_scaling = pp.get('X_before_scaling')  # Get original data before scaling
        X_before_encoding = pp.get('X_before_encoding')  # Get original data before encoding (for categorical)
        
        # Save preprocessed data back to state manager if dataset_id is provided
        if dataset_id:
            try:
                # Start with original full dataframe to preserve all columns
                preprocessed_df = df.copy()
                
                # Create NEW columns for preprocessed features (preserve originals)
                # Naming pattern:
                # - {col}_le_model (LabelEncoder - for categorical columns)
                # - {col}_ss_model (StandardScaler - for numerical columns)
                # If columns already exist, they will be updated (overwritten)
                preprocessed_column_mapping = {}
                
                # Check which columns were encoded (categorical)
                # pp['encoders'] contains the label_encoders dict
                encoded_columns = set(pp.get('encoders', {}).keys()) if pp.get('encoders') else set()
                
                for col in X.columns:
                    # Determine naming based on preprocessing method applied
                    # Use _manual suffix to distinguish from auto training
                    if col in encoded_columns:
                        # Categorical: LabelEncoder applied (also scaled, but named for encoding)
                        new_col_name = f"{col}_le_manual"
                    else:
                        # Numerical: StandardScaler applied
                        new_col_name = f"{col}_ss_manual"
                    
                    # Update existing column or create new one (pandas handles this automatically)
                    preprocessed_df[new_col_name] = X[col]
                    preprocessed_column_mapping[col] = new_col_name
                
                # Store mapping for later use (will be saved in model metadata)
                self.preprocessed_column_mapping = preprocessed_column_mapping
                
                # Save to state manager with force_scope='entire' to ensure it's saved as master dataset
                dataframe_state_manager.update_dataframe(
                    dataset_id=dataset_id,
                    df=preprocessed_df,
                    force_scope='entire'
                )
                
                # Apply preprocessing to test/validation data using TRAIN encoders/scalers
                for scope_name in ['test', 'validation']:
                    scope_idx = dataframe_state_manager._split_indices.get(dataset_id, {}).get(scope_name)
                    if scope_idx is not None and len(scope_idx) > 0:
                        try:
                            master_df = dataframe_state_manager._full_dataframes.get(dataset_id)
                            if master_df is not None:
                                scope_df_raw = master_df.iloc[scope_idx].copy()
                                if target_column in scope_df_raw.columns:
                                    # Ensure we use exactly the columns seen during training (after dropping NaN cols)
                                    X_scope_raw = pd.DataFrame(index=scope_df_raw.index)
                                    for col in X_before_scaling.columns:
                                        if col in scope_df_raw.columns:
                                            X_scope_raw[col] = scope_df_raw[col]
                                        else:
                                            X_scope_raw[col] = pd.NA
                                    
                                    # Fill missing values using TRAIN statistics
                                    for col in X_scope_raw.columns:
                                        if X_scope_raw[col].dtype in ['object', 'category']:
                                            mode_val = X_scope_raw[col].mode()
                                            X_scope_raw[col] = X_scope_raw[col].fillna(mode_val[0] if len(mode_val) > 0 else 'Unknown')
                                        else:
                                            X_scope_raw[col] = X_scope_raw[col].fillna(X_scope_raw[col].median())
                                    
                                    # Apply label encoding using TRAIN encoders
                                    if pp.get('encoders'):
                                        for col in X_scope_raw.columns:
                                            if col in pp['encoders']:
                                                le = pp['encoders'][col]
                                                X_scope_raw[col] = X_scope_raw[col].astype(str)
                                                known = set(le.classes_)
                                                X_scope_raw[col] = X_scope_raw[col].apply(
                                                    lambda x: le.transform([x])[0] if x in known else -1
                                                )
                                    
                                    # Apply scaling using TRAIN scaler
                                    if pp.get('scaler') is not None:
                                        X_scope_scaled = pp['scaler'].transform(X_scope_raw)
                                        X_scope_preprocessed = pd.DataFrame(X_scope_scaled, columns=X_scope_raw.columns, index=X_scope_raw.index)
                                    else:
                                        X_scope_preprocessed = X_scope_raw
                                    
                                    # Create preprocessed dataframe with new columns
                                    scope_df_preprocessed = scope_df_raw.copy()
                                    for col in X_scope_preprocessed.columns:
                                        new_col_name = preprocessed_column_mapping.get(col)
                                        if new_col_name:
                                            scope_df_preprocessed[new_col_name] = X_scope_preprocessed[col].values
                                    
                                    # Update in transformed_copies
                                    if dataset_id not in dataframe_state_manager._transformed_copies:
                                        dataframe_state_manager._transformed_copies[dataset_id] = {}
                                    dataframe_state_manager._transformed_copies[dataset_id][scope_name] = scope_df_preprocessed
                                    self.logger.info(f"✅ Applied preprocessing to {scope_name} data: {scope_df_preprocessed.shape}")
                        except Exception as scope_err:
                            self.logger.warning(f"Failed to preprocess {scope_name} data: {str(scope_err)}")
                
                # Log summary
                le_count = sum(1 for col in X.columns if col in encoded_columns)
                ss_count = len(X.columns) - le_count
                self.logger.info(f"Saved preprocessed data to state manager for dataset: {dataset_id}, shape: {preprocessed_df.shape}")
                self.logger.info(f"Created/updated {len(preprocessed_column_mapping)} preprocessed columns (manual training):")
                self.logger.info(f"  - {le_count} columns with LabelEncoder: {{col}}_le_manual")
                self.logger.info(f"  - {ss_count} columns with StandardScaler: {{col}}_ss_manual")
                if preprocessed_column_mapping:
                    example_cols = list(preprocessed_column_mapping.values())[:3]
                    self.logger.info(f"Example columns: {example_cols}...")
                self.logger.info(f"Original columns preserved. Existing model columns updated if present.")
            except Exception as e:
                self.logger.warning(f"Failed to save preprocessed data to state manager: {str(e)}")
                # Continue with training even if save fails
                self.preprocessed_column_mapping = {}

        # Determine problem type using existing method
        problem_type = self.detect_problem_type_from_data(df, target_column)['problem_type']

        # DEBUG: Check class distribution before split
        self.logger.info(f"Target distribution in full dataset: {pd.Series(y).value_counts().to_dict()}")
        
        # Get active_scope and split_indices from dataframe_state_manager if dataset_id is provided
        active_scope = 'entire'
        existing_split_indices = None
        if dataset_id:
            try:
                from app.services.dataframe_state_manager import dataframe_state_manager
                active_scope = dataframe_state_manager._active_scope.get(dataset_id, 'entire')
                existing_split_indices = dataframe_state_manager._split_indices.get(dataset_id)
                if existing_split_indices:
                    self.logger.info(f"Found existing split indices for {dataset_id}: dev={len(existing_split_indices.get('dev', []))} rows, hold={len(existing_split_indices.get('hold', []))} rows")
            except Exception as e:
                self.logger.warning(f"Failed to get split info from state manager: {e}")
                pass  # Use default if unable to get scope
        
        # Split data based on active_scope and existing split indices
        # If active_scope == 'entire': No split, train on entire dataset
        # If active_scope == 'train': Train on train data, evaluate on test data
        train_indices = None
        test_indices = None
        split_params = None
        
        if active_scope == 'entire':
            # No train/test split - use entire dataset for training
            self.logger.info("active_scope='entire': Training on entire dataset (no test split)")
            self.logger.info(
                "[SCOPE_DATA_TRACE][manual] dataset_id=%s active_scope=%s train_source=entire holdout_source=none rows_train=%s",
                dataset_id,
                active_scope,
                len(X),
            )
            X_train = X.copy()
            y_train = y.copy()
            w_train = sample_weights  # Use all weights for training
            X_test = None
            y_test = None
            w_test = None
            # FIX: Store POSITIONAL indices (0, 1, 2...) for .iloc[] indexing, not actual index values
            train_indices = list(range(len(X)))
            test_indices = []
            split_params = {
                'test_size': 0.0,
                'random_state': None,
                'stratify': False,
                'no_split': True
            }
        else:
            # active_scope == 'train': Train on train data, evaluate on test data
            # NO INTERNAL SPLIT - user already defined train/test split in Step 1 Objectives
            self.logger.info(f"active_scope='{active_scope}': Training on train data, evaluating on test data")
            self.logger.info(
                "[SCOPE_DATA_TRACE][manual] dataset_id=%s active_scope=%s train_source=%s rows_train=%s",
                dataset_id,
                active_scope,
                active_scope,
                len(X),
            )
            X_train = X.copy()
            y_train = y.copy()
            w_train = sample_weights  # Use all weights for training (entire train scope)
            w_test = None  # Will be extracted from test data if available
            # FIX: Store POSITIONAL indices (0, 1, 2...) for .iloc[] indexing, not actual index values
            train_indices = list(range(len(X)))
            
            # Get test data from DataFrameStateManager for evaluation
            X_test = None
            y_test = None
            test_indices = []
            
            if dataset_id:
                try:
                    from app.services.dataframe_state_manager import dataframe_state_manager as _dsm
                    previous_scope = _dsm._active_scope.get(dataset_id, 'entire')
                    test_df = None
                    holdout_scope_used = None
                    # Scope-driven retrieval with strict fallback chain for evaluation:
                    # test -> validation -> train -> entire
                    try:
                        for scope_name in ('test', 'validation', 'train', 'entire'):
                            self.logger.info(
                                "[SCOPE_DATA_TRACE][manual] dataset_id=%s holdout_probe_scope=%s previous_scope=%s",
                                dataset_id,
                                scope_name,
                                previous_scope,
                            )
                            _dsm.set_scope(dataset_id, scope=scope_name)
                            candidate_df = _dsm.get_dataframe(dataset_id)
                            candidate_rows = len(candidate_df) if candidate_df is not None else 0
                            if candidate_df is not None and candidate_rows > 0 and target_column in candidate_df.columns:
                                test_df = candidate_df
                                holdout_scope_used = scope_name
                                break
                            self.logger.info(
                                "[SCOPE_DATA_TRACE][manual] dataset_id=%s holdout_scope=%s rows=%s has_target=%s continuing_fallback",
                                dataset_id,
                                scope_name,
                                candidate_rows,
                                bool(candidate_df is not None and target_column in candidate_df.columns),
                            )
                    finally:
                        try:
                            _dsm.set_scope(dataset_id, scope=previous_scope)
                            self.logger.info(
                                "[SCOPE_DATA_TRACE][manual] dataset_id=%s scope_restored=%s",
                                dataset_id,
                                previous_scope,
                            )
                        except Exception:
                            self.logger.warning(
                                f"Could not restore scope '{previous_scope}' for dataset {dataset_id} after holdout retrieval"
                            )
                    
                    if test_df is not None and len(test_df) > 0 and target_column in test_df.columns:
                        # Use preprocessed column mapping to get the encoded column names
                        # independent_variables contains original names, but we need the encoded versions
                        if hasattr(self, 'preprocessed_column_mapping') and self.preprocessed_column_mapping:
                            # Map original column names to preprocessed column names (_le_manual or _ss_manual)
                            test_features = []
                            for orig_col in independent_variables:
                                preprocessed_col = self.preprocessed_column_mapping.get(orig_col)
                                if preprocessed_col and preprocessed_col in test_df.columns:
                                    test_features.append(preprocessed_col)
                            
                            if test_features:
                                X_test = test_df[test_features].copy()
                                # CRITICAL: Rename columns back to original names to match X_train
                                # Model is trained with original column names, so X_test must have same names
                                reverse_mapping = {v: k for k, v in self.preprocessed_column_mapping.items()}
                                X_test.columns = [reverse_mapping.get(col, col) for col in X_test.columns]
                                y_test = test_df[target_column].copy()
                                # Encode y_test if target encoder exists (for categorical targets)
                                if hasattr(self, 'target_encoder') and self.target_encoder is not None:
                                    y_test = y_test.astype(str)
                                    known_classes = set(self.target_encoder.classes_)
                                    y_test = y_test.apply(lambda x: self.target_encoder.transform([x])[0] if x in known_classes else -1)
                                # FIX: Store POSITIONAL indices (0, 1, 2...) for .iloc[] indexing, not actual index values
                                test_indices = list(range(len(X_test)))
                                
                                # CRITICAL: Store original test data BEFORE encoding for X_test_original
                                # This is needed for test granular accuracy with categorical features
                                # Get original columns from test_df (not preprocessed columns)
                                original_test_features = [col for col in independent_variables if col in test_df.columns]
                                if original_test_features:
                                    self.X_test_original = test_df[original_test_features].copy()
                                    self.logger.info(f"✅ Stored X_test_original for test granular accuracy: {self.X_test_original.shape}")
                                    self.logger.info(f"   X_test_original columns: {list(self.X_test_original.columns)[:5]}...")
                                
                                # Extract test weights if weight_variable is available
                                if weight_variable and weight_variable in test_df.columns:
                                    w_test = test_df[weight_variable].values.copy()
                                    self.logger.info(f"✅ Extracted test weights from '{weight_variable}': {len(w_test)} values")
                                
                                self.logger.info(f"✅ Test data for evaluation (using preprocessed columns): X_test={X_test.shape}, y_test={len(y_test)}")
                                self.logger.info(f"   X_test columns (renamed to match X_train): {list(X_test.columns)[:5]}...")
                                self.logger.info(
                                    "[SCOPE_DATA_TRACE][manual] dataset_id=%s holdout_source=%s rows_test=%s cols_test=%s",
                                    dataset_id,
                                    holdout_scope_used or 'unknown',
                                    len(y_test) if y_test is not None else 0,
                                    X_test.shape[1] if X_test is not None else 0,
                                )
                            else:
                                self.logger.warning(f"⚠️ No preprocessed features found in test data")
                                X_test = None
                                y_test = None
                                test_indices = []
                    else:
                        self.logger.warning(f"⚠️ No test data available for dataset_id={dataset_id}")
                        self.logger.warning(
                            "[SCOPE_DATA_TRACE][manual] dataset_id=%s holdout_source=%s rows_test=0 reason=no_test_dataframe_or_target_missing",
                            dataset_id,
                            holdout_scope_used or 'none',
                        )
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to get test data: {str(e)}")
            
            split_params = {
                'test_size': len(test_indices) / (len(train_indices) + len(test_indices)) if test_indices else 0.0,
                'random_state': None,
                'stratify': False,
                'user_split': True
            }
            self.logger.info(f"📊 Dev (train): {len(y_train)} rows | Hold (test): {len(y_test) if y_test is not None else 0} rows")
            self.logger.info(
                "[SCOPE_DATA_TRACE][manual] dataset_id=%s final_rows train=%s test=%s active_scope=%s",
                dataset_id,
                len(y_train) if y_train is not None else 0,
                len(y_test) if y_test is not None else 0,
                active_scope,
            )
        
        # Detect class imbalance for classification problems
        imbalance_info = None
        if problem_type == 'classification':
            imbalance_info = self.detect_class_imbalance(y_train)
            if imbalance_info['is_imbalanced']:
                self.logger.info(f"Detected imbalanced dataset (ratio: {imbalance_info['imbalance_ratio']:.2f})")

        # Build model factory
        models: Dict[str, Any] = {}
        try:
            from xgboost import XGBClassifier, XGBRegressor
        except Exception:
            XGBClassifier = XGBRegressor = None
        try:
            from lightgbm import LGBMClassifier, LGBMRegressor
        except Exception:
            LGBMClassifier = LGBMRegressor = None
        try:
            from catboost import CatBoostClassifier, CatBoostRegressor
        except Exception:
            CatBoostClassifier = CatBoostRegressor = None

        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
        from sklearn.linear_model import LogisticRegression, LinearRegression

        algorithm_params = algorithm_params or {}
        
        # Build models dict first (needed for parallelization)
        models: Dict[str, Any] = {}
        for algo in algorithms:
            algo_lower = algo.lower()
            model = None
            # NOTE: n_jobs=1 for all models to avoid nested parallelism
            # The outer Parallel(n_jobs=-1) handles algorithm-level parallelism
            if problem_type == 'classification':
                if algo_lower in ['xgboost', 'xgb'] and XGBClassifier is not None:
                    params = algorithm_params.get('xgboost', {})
                    model_params = {
                        'eval_metric': 'logloss',
                        'random_state': 42,
                        'n_jobs': 1,  # Avoid nested parallelism
                        'max_depth': int(params.get('max_depth', 6)),
                        'min_child_weight': float(params.get('min_child_weight', 1)),
                        'gamma': float(params.get('gamma', 0)),
                        'learning_rate': float(params.get('learning_rate', 0.3)),  # Keep 0.3 for fast training
                        'n_estimators': int(params.get('n_estimators', 50))  # Optimized: Reduced from 100 to 50
                    }
                    # Add scale_pos_weight for imbalanced data
                    if imbalance_info and imbalance_info['is_imbalanced'] and len(imbalance_info['class_distribution']) == 2:
                        class_counts = imbalance_info['class_distribution']
                        classes = list(class_counts.keys())
                        scale_pos_weight = class_counts[classes[0]] / class_counts[classes[1]]
                        model_params['scale_pos_weight'] = float(scale_pos_weight)
                        self.logger.info(f"XGBoost: Added scale_pos_weight={scale_pos_weight:.2f} for imbalanced data")
                    model = XGBClassifier(**model_params)
                elif algo_lower in ['lightgbm','lgbm'] and LGBMClassifier is not None:
                    params = algorithm_params.get('lightgbm', {})
                    model_params = {
                        'random_state': 42,
                        'n_jobs': 1,  # Avoid nested parallelism
                        'max_depth': int(params.get('max_depth', -1)),
                        'num_leaves': int(params.get('num_leaves', 31)),
                        'min_child_samples': int(params.get('min_child_samples', 20)),
                        'min_child_weight': float(params.get('min_child_weight', 1e-3)),
                        'learning_rate': float(params.get('learning_rate', 0.3)),  # Optimized: Increased from 0.1 to 0.3
                        'n_estimators': int(params.get('n_estimators', 50))  # Optimized: Reduced from 100 to 50
                    }
                    # Add class_weight for imbalanced data
                    if imbalance_info and imbalance_info['is_imbalanced']:
                        model_params['class_weight'] = 'balanced'
                        self.logger.info(f"LightGBM: Added class_weight='balanced' for imbalanced data")
                    model = LGBMClassifier(**model_params)
                elif algo_lower in ['catboost','cat'] and CatBoostClassifier is not None:
                    params = algorithm_params.get('catboost', {})
                    model_params = {
                        'verbose': 0,
                        'random_state': 42,
                        'thread_count': 1,  # Avoid nested parallelism
                        'depth': int(params.get('depth', 6)),
                        'learning_rate': float(params.get('learning_rate', 0.1)),  # Optimized: Increased from 0.03 to 0.1
                        'iterations': int(params.get('iterations', 50))  # Optimized: Reduced from 100 to 50
                    }
                    # Add class_weights for imbalanced data
                    if imbalance_info and imbalance_info['is_imbalanced']:
                        class_counts = imbalance_info['class_distribution']
                        total = sum(class_counts.values())
                        class_weights = {int(k): total / (len(class_counts) * v) for k, v in class_counts.items()}
                        model_params['class_weights'] = class_weights
                        self.logger.info(f"CatBoost: Added class_weights for imbalanced data")
                    model = CatBoostClassifier(**model_params)
                elif algo_lower in ['randomforest','random_forest','rf']:
                    params = algorithm_params.get('random_forest', {})
                    model_params = {
                        'random_state': 42,
                        'n_jobs': 1,  # Avoid nested parallelism
                        'max_depth': self._safe_int(params.get('max_depth'), 5),
                        'min_samples_split': int(params.get('min_samples_split', 2)),
                        'min_samples_leaf': int(params.get('min_samples_leaf', 1)),
                        'max_leaf_nodes': self._safe_int(params.get('max_leaf_nodes'), 5),
                        'n_estimators': int(params.get('n_estimators', 50)),  # Optimized: Reduced from 100 to 50
                        'max_features': params.get('max_features', 'sqrt')
                    }
                    # Add class_weight for imbalanced data
                    if imbalance_info and imbalance_info['is_imbalanced']:
                        model_params['class_weight'] = 'balanced'
                        self.logger.info(f"RandomForest: Added class_weight='balanced' for imbalanced data")
                    model = RandomForestClassifier(**model_params)
                elif algo_lower in ['logistic','logisticregression','logistic_regression']:
                    params = algorithm_params.get('logistic_regression', {})
                    model_params = {
                        'random_state': 42,
                        'n_jobs': 1,  # Avoid nested parallelism
                        'max_iter': int(params.get('max_iter', 200)), # Optimized: Reduced from 500 to 200
                        'solver': params.get('solver', 'liblinear'),
                        'C': float(params.get('C', 1.0))
                    }
                    # Add class_weight for imbalanced data
                    if imbalance_info and imbalance_info['is_imbalanced']:
                        model_params['class_weight'] = 'balanced'
                        self.logger.info(f"LogisticRegression: Added class_weight='balanced' for imbalanced data")
                    model = LogisticRegression(**model_params)
                elif algo_lower in ['gradientboosting','gb','gradient_boosting']:
                    params = algorithm_params.get('gradient_boosting', {})
                    model_params = {
                        'random_state': 42,
                        'max_iter': int(params.get('max_iter', 100)),
                        'learning_rate': float(params.get('learning_rate', 0.1)),
                        'max_depth': self._safe_int(params.get('max_depth'), None),
                        'max_leaf_nodes': self._safe_int(params.get('max_leaf_nodes'), 31),
                        'early_stopping': True,
                        'n_iter_no_change': 10,
                    }
                    model = HistGradientBoostingClassifier(**model_params)
            else:
                # Regression models - also use n_jobs=1 to avoid nested parallelism
                if algo_lower in ['xgboost','xgb'] and XGBRegressor is not None:
                    params = algorithm_params.get('xgboost', {})
                    model = XGBRegressor(
                        random_state=42,
                        n_jobs=1,  # Avoid nested parallelism
                        max_depth=int(params.get('max_depth', 6)),
                        min_child_weight=float(params.get('min_child_weight', 1)),
                        gamma=float(params.get('gamma', 0)),
                        learning_rate=float(params.get('learning_rate', 0.3)),  # Keep 0.3 for fast training
                        n_estimators=int(params.get('n_estimators', 50))  # Optimized: Reduced from 100 to 50
                    )
                elif algo_lower in ['lightgbm','lgbm'] and LGBMRegressor is not None:
                    params = algorithm_params.get('lightgbm', {})
                    model = LGBMRegressor(
                        random_state=42,
                        n_jobs=1,  # Avoid nested parallelism
                        max_depth=int(params.get('max_depth', -1)),
                        num_leaves=int(params.get('num_leaves', 31)),
                        min_child_samples=int(params.get('min_child_samples', 20)),
                        min_child_weight=float(params.get('min_child_weight', 1e-3)),
                        learning_rate=float(params.get('learning_rate', 0.3)),  # Optimized: Increased from 0.1 to 0.3
                        n_estimators=int(params.get('n_estimators', 50))  # Optimized: Reduced from 100 to 50
                    )
                elif algo_lower in ['catboost','cat'] and CatBoostRegressor is not None:
                    params = algorithm_params.get('catboost', {})
                    model = CatBoostRegressor(
                        verbose=0, random_state=42,
                        thread_count=1,  # Avoid nested parallelism
                        depth=int(params.get('depth', 6)),
                        learning_rate=float(params.get('learning_rate', 0.1)),  # Optimized: Increased from 0.03 to 0.1
                        iterations=int(params.get('iterations', 50))  # Optimized: Reduced from 100 to 50
                    )
                elif algo_lower in ['randomforest','random_forest','rf']:
                    params = algorithm_params.get('random_forest', {})
                    model = RandomForestRegressor(
                        random_state=42,
                        n_jobs=1,  # Avoid nested parallelism
                        max_depth=self._safe_int(params.get('max_depth'), 5),
                        min_samples_split=int(params.get('min_samples_split', 2)),
                        min_samples_leaf=int(params.get('min_samples_leaf', 1)),
                        max_leaf_nodes=self._safe_int(params.get('max_leaf_nodes'), 5),
                        n_estimators=int(params.get('n_estimators', 50)),  # Optimized: Reduced from 100 to 50
                        max_features=params.get('max_features', 1.0)
                    )
                elif algo_lower in ['linear','linearregression','linear_regression']:
                    model = LinearRegression()
                elif algo_lower in ['gradientboosting','gb','gradient_boosting']:
                    params = algorithm_params.get('gradient_boosting', {})
                    model = HistGradientBoostingRegressor(
                        random_state=42,
                        max_iter=int(params.get('max_iter', 100)),
                        learning_rate=float(params.get('learning_rate', 0.1)),
                        max_depth=self._safe_int(params.get('max_depth'), None),
                        max_leaf_nodes=self._safe_int(params.get('max_leaf_nodes'), 31),
                        early_stopping=True,
                        n_iter_no_change=10,
                    )

            if model is not None:
                models[algo] = model

        results: List[Dict[str, Any]] = []
        os.makedirs('models', exist_ok=True)

        # Industry-standard hyperparameter configuration: steps and bounds
        # Enforces realistic ranges to prevent overfitting and computational waste
        HYPERPARAMETER_CONFIG = {
            'xgboost': {
                'max_depth': {'step': 1, 'min': 1, 'max': 15},
                'min_child_weight': {'step': 0.5, 'min': 0.1, 'max': 10},
                'gamma': {'step': 0.1, 'min': 0, 'max': 5},
                'learning_rate': {'step': 0.01, 'min': 0.001, 'max': 0.5},
                'n_estimators': {'step': 10, 'min': 10, 'max': 500},
                'subsample': {'step': 0.1, 'min': 0.5, 'max': 1.0},
                'colsample_bytree': {'step': 0.1, 'min': 0.5, 'max': 1.0},
                'reg_alpha': {'step': 0.01, 'min': 0, 'max': 10},
                'reg_lambda': {'step': 0.01, 'min': 0, 'max': 10},
            },
            'lightgbm': {
                'max_depth': {'step': 1, 'min': 1, 'max': 15},
                'num_leaves': {'step': 5, 'min': 10, 'max': 255},
                'learning_rate': {'step': 0.01, 'min': 0.001, 'max': 0.5},
                'n_estimators': {'step': 10, 'min': 10, 'max': 500},
                'min_child_samples': {'step': 1, 'min': 1, 'max': 50},
                'subsample': {'step': 0.1, 'min': 0.5, 'max': 1.0},
                'colsample_bytree': {'step': 0.1, 'min': 0.5, 'max': 1.0},
                'reg_alpha': {'step': 0.01, 'min': 0, 'max': 10},
                'reg_lambda': {'step': 0.01, 'min': 0, 'max': 10},
            },
            'random_forest': {
                'max_depth': {'step': 1, 'min': 1, 'max': 30},
                'min_samples_split': {'step': 1, 'min': 2, 'max': 50},
                'min_samples_leaf': {'step': 1, 'min': 1, 'max': 20},
                'n_estimators': {'step': 10, 'min': 10, 'max': 500},
                'max_features': {'step': 0.1, 'min': 0.1, 'max': 1.0},
            },
            'gradient_boosting': {
                # HistGradientBoosting params (replaces legacy GradientBoosting)
                'max_depth': {'step': 1, 'min': 3, 'max': 8},
                'learning_rate': {'step': 0.05, 'min': 0.05, 'max': 0.3},
                'max_iter': {'step': 25, 'min': 50, 'max': 200},
                'max_leaf_nodes': {'step': 10, 'min': 20, 'max': 60},
                'l2_regularization': {'step': 0.1, 'min': 0.0, 'max': 1.0},
            },
            'catboost': {
                'depth': {'step': 1, 'min': 1, 'max': 12},
                'learning_rate': {'step': 0.01, 'min': 0.001, 'max': 0.5},
                'iterations': {'step': 10, 'min': 10, 'max': 500},
                'l2_leaf_reg': {'step': 0.1, 'min': 0.1, 'max': 10},
                'min_data_in_leaf': {'step': 1, 'min': 1, 'max': 50},
            },
            'logistic_regression': {
                'C': {'step': 0.1, 'min': 0.001, 'max': 1000},
                'max_iter': {'step': 50, 'min': 100, 'max': 5000},
            }
        }

        # Define hyperparameter search spaces for each algorithm
        def get_hyperparameter_space(algo_name: str, problem_type: str, user_ranges: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            """
            Define search space for hyperparameters based on algorithm type.
            
            If user_ranges is provided, validates and converts min/max ranges to discrete search space
            using industry-standard steps AND enforces reasonable bounds.
            
            Args:
                algo_name: Algorithm name
                problem_type: 'classification' or 'regression'
                user_ranges: Optional dict of {param: {min: value, max: value}}
                
            Returns:
                Dict mapping parameter names to lists of values
            """
            import random

            # Default fixed search spaces (fallback when user doesn't provide ranges)
            default_spaces = {
                'xgboost': {
                    'classification': {
                        'max_depth': [4, 5, 6],
                        'min_child_weight': [1, 2, 3],
                        'learning_rate': [0.2, 0.3],
                        'n_estimators': [30, 40, 50],
                        'subsample': [0.8, 0.9, 1.0],
                        'colsample_bytree': [0.8, 0.9, 1.0]
                    },
                    'regression': {
                        'max_depth': [4, 5, 6],
                        'min_child_weight': [1, 2, 3],
                        'learning_rate': [0.2, 0.3],
                        'n_estimators': [30, 40, 50],
                        'subsample': [0.8, 0.9, 1.0],
                        'colsample_bytree': [0.8, 0.9, 1.0]
                    }
                },
                'lightgbm': {
                    'classification': {
                        'max_depth': [4, 5, 6, -1],
                        'num_leaves': [20, 30, 40],
                        'learning_rate': [0.2, 0.3],
                        'n_estimators': [50, 75, 100],
                        'min_child_samples': [10, 15, 20],
                        'subsample': [0.8, 0.9, 1.0]
                    },
                    'regression': {
                        'max_depth': [4, 5, 6, -1],
                        'num_leaves': [20, 30, 40],
                        'learning_rate': [0.2, 0.3],
                        'n_estimators': [50, 75, 100],
                        'min_child_samples': [10, 15, 20],
                        'subsample': [0.8, 0.9, 1.0]
                    }
                },
                'random_forest': {
                    'classification': {
                        'max_depth': [5, 6, 7],
                        'min_samples_split': [2, 5, 10],
                        'min_samples_leaf': [1, 2, 4],
                        'n_estimators': [30, 40, 50],
                        'max_features': ['sqrt', 'log2']
                    },
                    'regression': {
                        'max_depth': [5, 6, 7],
                        'min_samples_split': [2, 5, 10],
                        'min_samples_leaf': [1, 2, 4],
                        'n_estimators': [30, 40, 50],
                        'max_features': ['sqrt', 'log2']
                    }
                },
                'linear': {
                    'classification': {},
                    'regression': {}
                },
                'logistic': {
                    'classification': {
                        'C': [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
                        'max_iter': [100, 200, 300],
                        'solver': ['liblinear', 'lbfgs']  # saga excluded: 20-100x slower on scaled dense data
                    },
                    'regression': {}
                },
                'gradientboosting': {
                    # HistGradientBoosting params
                    'classification': {
                        'max_depth': [3, 5, 7],
                        'learning_rate': [0.05, 0.1, 0.2],
                        'max_iter': [50, 100, 150],
                        'max_leaf_nodes': [20, 31, 50],
                    },
                    'regression': {
                        'max_depth': [3, 5, 7],
                        'learning_rate': [0.05, 0.1, 0.2],
                        'max_iter': [50, 100, 150],
                        'max_leaf_nodes': [20, 31, 50],
                    }
                }
            }

            # Normalize algorithm name for lookup
            normalized_name = algo_name.lower()
            if normalized_name in ['logisticregression', 'logistic_regression']:
                normalized_name = 'logistic'
            elif normalized_name in ['randomforest', 'random_forest', 'rf']:
                normalized_name = 'random_forest'
            elif normalized_name in ['gradientboosting', 'gb', 'gradient_boosting']:
                normalized_name = 'gradientboosting'
            elif normalized_name in ['xgb']:
                normalized_name = 'xgboost'
            elif normalized_name in ['lgbm']:
                normalized_name = 'lightgbm'

            # If user provided ranges, convert them to discrete search space with bounds validation
            if user_ranges and normalized_name in user_ranges:
                try:
                    param_ranges = user_ranges[normalized_name]
                    config = HYPERPARAMETER_CONFIG.get(normalized_name, {})
                    search_space = {}
                    
                    for param_name, range_config in param_ranges.items():
                        # Handle dict-based ranges {min: X, max: Y}
                        if isinstance(range_config, dict) and 'min' in range_config and 'max' in range_config:
                            user_min = range_config['min']
                            user_max = range_config['max']
                            
                            # Get param config (step, min bound, max bound)
                            param_config = config.get(param_name, {})
                            step = param_config.get('step', 1)
                            bound_min = param_config.get('min', float('-inf'))
                            bound_max = param_config.get('max', float('inf'))
                            
                            # VALIDATE AND CLAMP user input within bounds
                            if user_min < bound_min or user_max > bound_max:
                                self.logger.warning(
                                    f"User range for {normalized_name}.{param_name} "
                                    f"({user_min}-{user_max}) exceeds bounds ({bound_min}-{bound_max}). "
                                    f"Clamping to valid range."
                                )
                                # Clamp values to bounds
                                clamped_min = max(user_min, bound_min)
                                clamped_max = min(user_max, bound_max)
                            else:
                                clamped_min = user_min
                                clamped_max = user_max
                            
                            # Generate list of values from min to max with step
                            try:
                                if isinstance(clamped_min, int) and isinstance(clamped_max, int) and isinstance(step, int):
                                    # Integer range
                                    search_space[param_name] = list(range(int(clamped_min), int(clamped_max) + 1, int(step)))
                                else:
                                    # Float range - generate evenly spaced values
                                    clamped_min = float(clamped_min)
                                    clamped_max = float(clamped_max)
                                    step = float(step)
                                    
                                    num_steps = int((clamped_max - clamped_min) / step) + 1
                                    values = [round(clamped_min + i * step, 8) for i in range(num_steps)]
                                    # Ensure max_val is included
                                    if values[-1] < clamped_max:
                                        values.append(clamped_max)
                                    search_space[param_name] = values
                                    
                                self.logger.info(
                                    f"Generated search space for {normalized_name}.{param_name}: "
                                    f"min={clamped_min}, max={clamped_max}, step={step}, "
                                    f"values_count={len(search_space[param_name])}, values={search_space[param_name][:5]}..."
                                )
                            except Exception as gen_error:
                                self.logger.warning(
                                    f"Error generating range for {param_name} in {normalized_name}: {str(gen_error)}. "
                                    f"Using default space instead."
                                )
                                search_space[param_name] = default_spaces.get(normalized_name, {}).get(problem_type, {}).get(param_name, [])
                        
                        # Handle list-based ranges (backward compatibility)
                        elif isinstance(range_config, list):
                            search_space[param_name] = range_config
                    
                    if search_space:
                        self.logger.info(f"Using user-provided hyperparameter ranges for {normalized_name}")
                        return search_space
                
                except Exception as e:
                    self.logger.warning(
                        f"Error processing user ranges for {normalized_name}: {str(e)}. "
                        f"Falling back to default hyperparameter space."
                    )

            # Return default space if no user ranges or on error
            return default_spaces.get(normalized_name, {}).get(problem_type, {})
        
        def bayesian_optimization_with_optuna(
            hyperparam_space: Dict[str, Any],
            train_func: callable,
            n_trials: int = 10,
            random_state: int = 42
        ) -> Dict[str, Any]:
            """
            Bayesian Optimization using Optuna (TPE sampler).
            Uses Tree-structured Parzen Estimator (Bayesian method) for smart hyperparameter search.
            
            Args:
                hyperparam_space: Dict of parameter names → list of values
                train_func: Function(params) → returns score
                n_trials: Number of optimization trials (total)
                random_state: Reproducibility seed
                
            Returns:
                {'best_params': {...}, 'best_score': float, 'history': [...]}
            """
            try:
                import optuna  # pyright: ignore[reportMissingImports](This will work at runtime)
                from optuna.samplers import TPESampler    # pyright: ignore[reportMissingImports]
                from optuna.pruners import MedianPruner  # pyright: ignore[reportMissingImports]
                
                # Calculate 20% random + 80% learned split
                n_startup_trials = max(1, int(n_trials * 0.2))  # 20% random
                n_learned_trials = n_trials - n_startup_trials  # 80% learned
                
                self.logger.info(f"Bayesian optimization: {n_trials} total trials ({n_startup_trials} random + {n_learned_trials} learned)")
                
                def objective(trial):
                    trial_num = trial.number + 1
                    self.logger.info(f"Trial {trial_num}/{n_trials}: {'Random exploration' if trial_num <= n_startup_trials else 'Learned optimization'}")
                    
                    params = {}
                    for param, values in hyperparam_space.items():
                        if isinstance(values, list):
                            if all(isinstance(v, int) for v in values):
                                params[param] = trial.suggest_int(param, min(values), max(values))
                            elif all(isinstance(v, float) for v in values):
                                params[param] = trial.suggest_float(param, min(values), max(values))
                            else:
                                params[param] = trial.suggest_categorical(param, values)
                        else:
                            params[param] = values
                    
                    self.logger.info(f"Trial {trial_num}: Suggested hyperparameters: {params}")
                    
                    score = train_func(params)
                    
                    self.logger.info(f"Trial {trial_num}: Score = {score:.4f}")

                    # Report score so MedianPruner can prune unpromising trials
                    trial.report(score, step=trial_num)
                    if trial.should_prune():
                        self.logger.info(f"Trial {trial_num}: Pruned by MedianPruner (score={score:.4f})")
                        raise optuna.TrialPruned()

                    return score
                
                study = optuna.create_study(
                    direction="maximize",
                    sampler=TPESampler(seed=random_state, n_startup_trials=n_startup_trials),  # 20% random
                    pruner=MedianPruner(n_warmup_steps=2)
                )
                
                self.logger.info(f"Starting Optuna optimization with {n_trials} trials...")
                study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
                
                self.logger.info(f"✅ Bayesian optimization completed. Best trial: {study.best_trial.number + 1}, Best score: {study.best_value:.4f}")
                
                return {
                    'best_params': study.best_params,
                    'best_score': study.best_value,
                    'history': [{'trial': i, 'value': t.value} for i, t in enumerate(study.trials)],
                    'method': 'bayesian_optuna'
                }
            except ImportError:
                raise ImportError("Optuna required for Bayesian Optimization: pip install optuna")
            except Exception as e:
                self.logger.error(f"Bayesian Optimization failed: {str(e)}")
                raise Exception(f"Bayesian Optimization failed: {str(e)}")

        def sample_hyperparameters(space: Dict[str, Any]) -> Dict[str, Any]:
            """Randomly sample hyperparameters from the search space."""
            import random

            sampled = {}
            for param, values in space.items():
                if isinstance(values, list):
                    sampled[param] = random.choice(values)
                else:
                    sampled[param] = values

            return sampled

        # Helper function for parallel algorithm training
        def train_single_algorithm_with_iterations(algo_model_tuple, X_train=X_train, X_test=X_test):
            """Train a single algorithm with iterations - used for parallelization"""
            algo, model = algo_model_tuple
            
            # --- CatBoost Raw Categorical Branch ---
            cat_features_list = []
            algo_name_lower = str(algo).lower()
            if algo_name_lower in ['catboost', 'cat'] and hasattr(self, 'X_before_encoding') and self.X_before_encoding is not None:
                _cand_cols = list(self.X_before_encoding.select_dtypes(include=['object', 'category', 'string']).columns)
                cat_features_names = [c for c in _cand_cols if c in X_train.columns]
                cat_features_list = [list(X_train.columns).index(c) for c in cat_features_names]
                if cat_features_names:
                    try:
                        if hasattr(model, 'set_params'):
                            model.set_params(cat_features=cat_features_list)
                            
                        X_train = X_train.copy()
                        for c in cat_features_names:
                            X_train[c] = self.X_before_encoding.loc[X_train.index, c].astype(str)
                        if X_test is not None:
                            X_test = X_test.copy()
                            for c in cat_features_names:
                                if hasattr(self, 'X_test_original') and self.X_test_original is not None and c in self.X_test_original.columns:
                                    X_test[c] = self.X_test_original.loc[X_test.index, c].astype(str)
                                else:
                                    X_test[c] = self.X_before_encoding.loc[X_test.index, c].astype(str)
                        self.logger.info(f"CatBoost: Injecting raw categoricals {cat_features_names} at indices {cat_features_list}")
                    except Exception as e:
                        self.logger.warning(f"Failed to inject raw categoricals for CatBoost: {e}")
                        cat_features_list = []
            # ---------------------------------------
            
            try:
                X_train_eff = X_train
                X_test_eff = X_test
                lr_elimination_audit = None
                _al = str(algo).lower().replace(" ", "").replace("-", "_")
                if (
                    problem_type == "classification"
                    and lr_backward_elimination
                    and _al in ("logisticregression", "logistic_regression", "logistic", "lr")
                    and y.nunique() == 2
                ):
                    try:
                        from app.utils.lr_backward_elimination import run_lr_backward_elimination

                        locked = variable_selection.get("locked_variables") or []
                        lr_elimination_audit = run_lr_backward_elimination(
                            X_train=X_train,
                            X_test=X_test,
                            y_train=y_train,
                            y_test=y_test,
                            locked_features=locked,
                            vif_threshold=float(lr_backward_elimination.get("vif_threshold", 5)),
                            p_value_threshold=float(lr_backward_elimination.get("p_value_threshold", 0.05)),
                        )
                        cols = lr_elimination_audit.get("final_features") or list(X_train.columns)
                        X_train_eff = X_train.loc[:, cols]
                        X_test_eff = X_test.loc[:, cols] if X_test is not None else None
                        self.logger.info(
                            "%s - LR backward elimination: %d -> %d features",
                            algo,
                            X_train.shape[1],
                            len(cols),
                        )
                    except Exception as lr_ex:
                        logger.warning("LR backward elimination skipped for %s: %s", algo, lr_ex)
                        X_train_eff = X_train
                        X_test_eff = X_test
                        lr_elimination_audit = None

                # Initialize iteration history
                iteration_history = []
                best_score = 0.0
                best_iteration = 0

                # Get hyperparameter search space for this algorithm
                hyperparam_space = get_hyperparameter_space(
                    algo, 
                    problem_type,
                    user_ranges=algorithm_param_ranges
                )
                self.logger.info(f"Algorithm: {algo}, Problem type: {problem_type}, Hyperparameter space: {hyperparam_space}")

                # Determine optimization method (from parameter, default to 'random')
                use_bayesian = (optimization_method == 'bayesian' or optimization_method == 'bayesian_optimization')
                self.logger.info(f"{algo} - Optimization method: {'Bayesian Optimization' if use_bayesian else 'Random Search'}")
                
                if use_bayesian and hyperparam_space:
                    self.logger.info(f"{algo} - Starting Bayesian optimization with {max_iterations} iterations")
                    
                    # Track iterations for history
                    bayesian_iterations = []
                    best_bayesian_score = 0.0
                    best_bayesian_params = None
                    best_bayesian_model = None
                    best_bayesian_iteration = 0
                    
                    def train_and_score(params):
                        nonlocal best_bayesian_score, best_bayesian_params, best_bayesian_model, best_bayesian_iteration, bayesian_iterations
                        
                        try:
                            # Inherit base parameters from original model
                            model_params = model.get_params().copy()
                            model_params.update(params)
                            if hasattr(model, 'random_state'):
                                model_params['random_state'] = 42
                            
                            iteration_model = type(model)(**model_params)
                            # Pass sample weights if available (weight variable support)
                            if w_train is not None:
                                iteration_model.fit(X_train_eff, y_train, sample_weight=w_train)
                            else:
                                iteration_model.fit(X_train_eff, y_train)
                            
                            # Handle case when there's no test set (active_scope == 'entire')
                            if X_test_eff is None or y_test is None:
                                # Use cross-validation on train set for hyperparameter optimization
                                # NOTE: n_jobs=1 to avoid nested parallelism (outer Parallel handles algorithm-level parallelism)
                                from sklearn.model_selection import cross_val_score
                                try:
                                    if problem_type == 'classification':
                                        if hasattr(iteration_model, 'predict_proba'):
                                            cv_scores = cross_val_score(iteration_model, X_train_eff, y_train,
                                                                        cv=resolved_cv_folds, scoring='roc_auc', n_jobs=1)
                                        else:
                                            cv_scores = cross_val_score(iteration_model, X_train_eff, y_train,
                                                                        cv=resolved_cv_folds, scoring='f1_weighted', n_jobs=1)
                                    else:
                                        cv_scores = cross_val_score(iteration_model, X_train_eff, y_train,
                                                                    cv=resolved_cv_folds, scoring='r2', n_jobs=1)
                                    current_score = float(np.mean(cv_scores))
                                    
                                    # Calculate train predictions for metrics
                                    y_pred_train = iteration_model.predict(X_train_eff)
                                    y_proba_train = iteration_model.predict_proba(X_train_eff) if hasattr(iteration_model, 'predict_proba') else None
                                    
                                    # Create dummy metrics using train set
                                    metrics: Dict[str, float] = {}
                                    if problem_type == 'classification':
                                        metrics['train_accuracy'] = float(accuracy_score(y_train, y_pred_train))
                                        metrics['train_precision'] = float(precision_score(y_train, y_pred_train, average='weighted', zero_division=0))
                                        metrics['train_recall'] = float(recall_score(y_train, y_pred_train, average='weighted', zero_division=0))
                                        metrics['train_f1_score'] = float(f1_score(y_train, y_pred_train, average='weighted', zero_division=0))
                                        
                                        if y.nunique() == 2 and y_proba_train is not None:
                                            metrics['train_auc'] = float(roc_auc_score(y_train, y_proba_train[:, 1]))
                                            metrics['train_log_loss'] = float(log_loss(y_train, y_proba_train))
                                            self._apply_binary_rank_order_metrics(
                                                metrics,
                                                y_train=np.asarray(y_train),
                                                p_train=y_proba_train[:, 1],
                                                y_test=None,
                                                p_test=None,
                                            )
                                        
                                        # Test metrics are None
                                        metrics['test_accuracy'] = None
                                        metrics['test_precision'] = None
                                        metrics['test_recall'] = None
                                        metrics['test_f1_score'] = None
                                        metrics['test_auc'] = None
                                        metrics['test_log_loss'] = None
                                        # Aliases expected by frontend (use train metrics when no test set)
                                        try:
                                            metrics['accuracy'] = metrics.get('train_accuracy')
                                            metrics['precision'] = metrics.get('train_precision')
                                            metrics['recall'] = metrics.get('train_recall')
                                            metrics['f1'] = metrics.get('train_f1_score')
                                            if 'train_auc' in metrics:
                                                metrics['auc'] = metrics.get('train_auc')
                                                metrics['log_loss'] = metrics.get('train_log_loss')
                                                metrics['ks_statistic'] = metrics.get('train_ks_statistic', 0.0)
                                        except Exception:
                                            pass
                                    else:
                                        metrics['train_r2'] = float(r2_score(y_train, y_pred_train))
                                        metrics['train_rmse'] = float(np.sqrt(mean_squared_error(y_train, y_pred_train)))
                                        metrics['train_mae'] = float(mean_absolute_error(y_train, y_pred_train))
                                        
                                        # Test metrics are None
                                        metrics['test_r2'] = None
                                        metrics['test_rmse'] = None
                                        metrics['test_mae'] = None
                                        # Aliases expected by frontend (use train metrics when no test set)
                                        try:
                                            metrics['r2'] = metrics.get('train_r2')
                                            metrics['rmse'] = metrics.get('train_rmse')
                                            metrics['mae'] = metrics.get('train_mae')
                                            metrics['mse'] = metrics.get('train_mse')
                                        except Exception:
                                            pass
                                    
                                    y_pred = None
                                    y_proba = None
                                except Exception as cv_e:
                                    self.logger.warning(f"Cross-validation failed: {str(cv_e)}")
                                    return 0.0
                            else:
                                y_pred = iteration_model.predict(X_test_eff)
                                y_proba = iteration_model.predict_proba(X_test_eff) if hasattr(iteration_model, 'predict_proba') else None
                                y_pred_train = iteration_model.predict(X_train_eff)
                                y_proba_train = iteration_model.predict_proba(X_train_eff) if hasattr(iteration_model, 'predict_proba') else None
                                
                                # Calculate full metrics (same as random search)
                                metrics: Dict[str, float] = {}
                                if problem_type == 'classification':
                                    metrics['test_accuracy'] = float(accuracy_score(y_test, y_pred))
                                    metrics['test_precision'] = float(precision_score(y_test, y_pred, average='weighted', zero_division=0))
                                    metrics['test_recall'] = float(recall_score(y_test, y_pred, average='weighted', zero_division=0))
                                    metrics['test_f1_score'] = float(f1_score(y_test, y_pred, average='weighted', zero_division=0))
                                    metrics['accuracy'] = metrics['test_accuracy']
                                    metrics['precision'] = metrics['test_precision']
                                    metrics['recall'] = metrics['test_recall']
                                    metrics['f1'] = metrics['test_f1_score']
                                    
                                    if y.nunique() == 2 and y_proba is not None:
                                        metrics['test_auc'] = float(roc_auc_score(y_test, y_proba[:, 1]))
                                        metrics['test_log_loss'] = float(log_loss(y_test, y_proba))
                                        metrics['auc'] = metrics['test_auc']
                                        metrics['log_loss'] = metrics['test_log_loss']
                                        
                                        current_score = metrics['auc']
                                    else:
                                        current_score = metrics['f1']
                                    
                                    metrics['train_accuracy'] = float(accuracy_score(y_train, y_pred_train))
                                    metrics['train_precision'] = float(precision_score(y_train, y_pred_train, average='weighted', zero_division=0))
                                    metrics['train_recall'] = float(recall_score(y_train, y_pred_train, average='weighted', zero_division=0))
                                    metrics['train_f1_score'] = float(f1_score(y_train, y_pred_train, average='weighted', zero_division=0))
                                    
                                    if y.nunique() == 2 and y_proba_train is not None:
                                        metrics['train_auc'] = float(roc_auc_score(y_train, y_proba_train[:, 1]))
                                        metrics['train_log_loss'] = float(log_loss(y_train, y_proba_train))

                                    if y.nunique() == 2:
                                        self._apply_binary_rank_order_metrics(
                                            metrics,
                                            y_train=np.asarray(y_train),
                                            p_train=y_proba_train[:, 1] if y_proba_train is not None else None,
                                            y_test=np.asarray(y_test),
                                            p_test=y_proba[:, 1] if y_proba is not None else None,
                                        )
                                else:
                                    metrics['test_r2'] = float(r2_score(y_test, y_pred))
                                    metrics['test_rmse'] = float(np.sqrt(mean_squared_error(y_test, y_pred)))
                                    metrics['test_mae'] = float(mean_absolute_error(y_test, y_pred))
                                    metrics['r2'] = metrics['test_r2']
                                    metrics['rmse'] = metrics['test_rmse']
                                    metrics['mae'] = metrics['test_mae']
                                    current_score = metrics['r2']
                                    
                                    metrics['train_r2'] = float(r2_score(y_train, y_pred_train))
                                    metrics['train_rmse'] = float(np.sqrt(mean_squared_error(y_train, y_pred_train)))
                                    metrics['train_mae'] = float(mean_absolute_error(y_train, y_pred_train))
                            
                            # Track iteration
                            iteration_num = len(bayesian_iterations) + 1
                            improvement = current_score - best_bayesian_score if iteration_num > 1 else 0.0
                            
                            if current_score > best_bayesian_score:
                                old_score = best_bayesian_score
                                best_bayesian_score = current_score
                                best_bayesian_params = params.copy()
                                best_bayesian_model = iteration_model
                                best_bayesian_iteration = iteration_num
                                if iteration_num > 1:
                                    self.logger.info(f"{algo} - Trial {iteration_num}: 🎯 NEW BEST SCORE! {old_score:.4f} → {best_bayesian_score:.4f} (improvement: {improvement:+.4f})")
                                else:
                                    self.logger.info(f"{algo} - Trial {iteration_num}: 🎯 Initial best score: {best_bayesian_score:.4f}")
                            
                            feature_importance_count = nonzero_feature_slot_count(iteration_model)
                            
                            bayesian_iterations.append({
                                'iteration': iteration_num,
                                'score': current_score,
                                'improvement': improvement,
                                'hyperparameters': params.copy(),
                                'status': 'Best Score' if iteration_num == best_bayesian_iteration else 'Completed',
                                'metrics': metrics,
                                'feature_importance_count': feature_importance_count
                            })
                            
                            return current_score
                        except Exception as e:
                            self.logger.warning(f"Trial failed: {str(e)}")
                            return 0.0
                    
                    bayesian_iterations_to_run = resolved_optuna_trials if resolved_optuna_trials is not None else max_iterations
                    bayesian_result = bayesian_optimization_with_optuna(hyperparam_space, train_and_score, bayesian_iterations_to_run)
                    
                    # Use best model from Bayesian optimization
                    iteration_history = bayesian_iterations
                    best_score = best_bayesian_score
                    best_iteration = best_bayesian_iteration
                    model = best_bayesian_model
                    
                    self.logger.info(f"{algo} - Bayesian optimization completed. Best iteration: {best_iteration}, Best score: {best_score:.4f}")
                else:
                    # Random Search
                    random_iterations_to_run = max_iterations
                    self.logger.info(f"{algo} - Starting Random Search with {random_iterations_to_run} iterations")
                    for iteration in range(1, random_iterations_to_run + 1):
                        self.logger.info(f"{algo} - Random Search iteration {iteration}/{random_iterations_to_run}")
                        # Sample different hyperparameters for this iteration (if space is available)
                        if hyperparam_space:
                            sampled_params = sample_hyperparameters(hyperparam_space)
                        else:
                            # For algorithms without hyperparameters (like LinearRegression), use default params
                            sampled_params = {}

                        # Create a fresh model instance with the sampled parameters
                        # This ensures each iteration uses different hyperparameters (when available)
                        try:
                            # Inherit base parameters from original model
                            model_params = model.get_params().copy()
                            model_params.update(sampled_params)
                            if hasattr(model, 'random_state'):
                                model_params['random_state'] = 42
                            
                            # Remove n_jobs for algorithms that don't support it (e.g., GradientBoosting)
                            algo_lower = algo.lower()
                            if algo_lower in ['gradientboosting', 'gb', 'gradient_boosting']:
                                model_params.pop('n_jobs', None)
                            
                            iteration_model = type(model)(**model_params)
                            self.logger.info(f"Iteration {iteration} for {algo}: Using hyperparameters {model_params}")
                        except Exception as e:
                            self.logger.warning(f"Failed to create model with sampled params for {algo} iteration {iteration}: {str(e)}")
                            # Fallback to original model if parameter combination fails
                            try:
                                iteration_model = type(model)(random_state=42)
                            except:
                                iteration_model = type(model)()

                        # Fit the model for this iteration (pass sample weights if available)
                        if w_train is not None:
                            iteration_model.fit(X_train_eff, y_train, sample_weight=w_train)
                        else:
                            iteration_model.fit(X_train_eff, y_train)
                        
                        # Handle case when there's no test set (active_scope == 'entire')
                        if X_test_eff is None or y_test is None:
                            # Use cross-validation on train set for hyperparameter optimization
                            # NOTE: n_jobs=1 to avoid nested parallelism (outer Parallel handles algorithm-level parallelism)
                            from sklearn.model_selection import cross_val_score
                            try:
                                if problem_type == 'classification':
                                    if hasattr(iteration_model, 'predict_proba'):
                                        cv_scores = cross_val_score(iteration_model, X_train_eff, y_train,
                                                                    cv=resolved_cv_folds, scoring='roc_auc', n_jobs=1)
                                    else:
                                        cv_scores = cross_val_score(iteration_model, X_train_eff, y_train,
                                                                    cv=resolved_cv_folds, scoring='f1_weighted', n_jobs=1)
                                else:
                                    cv_scores = cross_val_score(iteration_model, X_train_eff, y_train,
                                                                cv=resolved_cv_folds, scoring='r2', n_jobs=1)
                                current_score = float(np.mean(cv_scores))
                                
                                # Calculate train predictions for metrics
                                y_pred_train = iteration_model.predict(X_train_eff)
                                y_proba_train = iteration_model.predict_proba(X_train_eff) if hasattr(iteration_model, 'predict_proba') else None
                                
                                # Create dummy metrics using train set
                                metrics: Dict[str, float] = {}
                                if problem_type == 'classification':
                                    metrics['train_accuracy'] = float(accuracy_score(y_train, y_pred_train))
                                    metrics['train_precision'] = float(precision_score(y_train, y_pred_train, average='weighted', zero_division=0))
                                    metrics['train_recall'] = float(recall_score(y_train, y_pred_train, average='weighted', zero_division=0))
                                    metrics['train_f1_score'] = float(f1_score(y_train, y_pred_train, average='weighted', zero_division=0))
                                    
                                    if y.nunique() == 2 and y_proba_train is not None:
                                        metrics['train_auc'] = float(roc_auc_score(y_train, y_proba_train[:, 1]))
                                        metrics['train_log_loss'] = float(log_loss(y_train, y_proba_train))
                                        self._apply_binary_rank_order_metrics(
                                            metrics,
                                            y_train=np.asarray(y_train),
                                            p_train=y_proba_train[:, 1],
                                            y_test=None,
                                            p_test=None,
                                        )
                                    
                                    # Test metrics are None
                                    metrics['test_accuracy'] = None
                                    metrics['test_precision'] = None
                                    metrics['test_recall'] = None
                                    metrics['test_f1_score'] = None
                                    metrics['test_auc'] = None
                                    metrics['test_log_loss'] = None
                                    # Aliases expected by frontend (use train metrics when no test set)
                                    try:
                                        metrics['accuracy'] = metrics.get('train_accuracy')
                                        metrics['precision'] = metrics.get('train_precision')
                                        metrics['recall'] = metrics.get('train_recall')
                                        metrics['f1'] = metrics.get('train_f1_score')
                                        if 'train_auc' in metrics:
                                            metrics['auc'] = metrics.get('train_auc')
                                            metrics['log_loss'] = metrics.get('train_log_loss')
                                            metrics['ks_statistic'] = metrics.get('train_ks_statistic', 0.0)
                                    except Exception:
                                        pass
                                else:
                                    metrics['train_r2'] = float(r2_score(y_train, y_pred_train))
                                    metrics['train_rmse'] = float(np.sqrt(mean_squared_error(y_train, y_pred_train)))
                                    metrics['train_mae'] = float(mean_absolute_error(y_train, y_pred_train))
                                    
                                    # Test metrics are None
                                    metrics['test_r2'] = None
                                    metrics['test_rmse'] = None
                                    metrics['test_mae'] = None
                                    # Aliases expected by frontend (use train metrics when no test set)
                                    try:
                                        metrics['r2'] = metrics.get('train_r2')
                                        metrics['rmse'] = metrics.get('train_rmse')
                                        metrics['mae'] = metrics.get('train_mae')
                                        metrics['mse'] = metrics.get('train_mse')
                                    except Exception:
                                        pass
                                
                                y_pred = None
                                y_proba = None
                            except Exception as cv_e:
                                self.logger.warning(f"Cross-validation failed: {str(cv_e)}")
                                continue
                        else:
                            # Test predictions
                            y_pred = iteration_model.predict(X_test_eff)
                            y_proba = iteration_model.predict_proba(X_test_eff) if hasattr(iteration_model, 'predict_proba') else None
                            # NEW: Train predictions
                            y_pred_train = iteration_model.predict(X_train_eff)
                            y_proba_train = iteration_model.predict_proba(X_train_eff) if hasattr(iteration_model, 'predict_proba') else None
                            
                            # DEBUG: Log predictions and class distribution (only for first iteration to avoid spam)
                            if iteration == 1:
                                self.logger.info(f"{algo} - Unique class predictions: {np.unique(y_pred, return_counts=True)}")
                                self.logger.info(f"{algo} - Prediction distribution: {pd.Series(y_pred).value_counts().to_dict()}")
                                self.logger.info(f"{algo} - Actual y_test distribution: {pd.Series(y_test).value_counts().to_dict()}")
                                if y_proba is not None and y_proba.shape[1] == 2:
                                    self.logger.info(f"{algo} - Probability range for class 1: [{y_proba[:, 1].min():.4f}, {y_proba[:, 1].max():.4f}]")

                            # Calculate metrics for this iteration
                            metrics: Dict[str, float] = {}
                            current_score = 0.0

                            try:
                                if problem_type == 'classification':
                                    # ---------------- TEST METRICS ----------------
                                    metrics['test_accuracy'] = float(accuracy_score(y_test, y_pred))
                                    metrics['test_precision'] = float(precision_score(y_test, y_pred, average='weighted', zero_division=0))
                                    metrics['test_recall'] = float(recall_score(y_test, y_pred, average='weighted', zero_division=0))
                                    metrics['test_f1_score'] = float(f1_score(y_test, y_pred, average='weighted', zero_division=0))

                                # Backward-compatible aliases
                                metrics['accuracy'] = metrics['test_accuracy']
                                metrics['precision'] = metrics['test_precision']
                                metrics['recall'] = metrics['test_recall']
                                metrics['f1'] = metrics['test_f1_score']

                                if y.nunique() == 2 and y_proba is not None:
                                    metrics['test_auc'] = float(roc_auc_score(y_test, y_proba[:, 1]))
                                    metrics['test_log_loss'] = float(log_loss(y_test, y_proba))

                                    # Aliases
                                    metrics['auc'] = metrics['test_auc']
                                    metrics['log_loss'] = metrics['test_log_loss']
                                        
                                    current_score = metrics['auc']  # Use AUC as primary score for classification
                                else:
                                    current_score = metrics['f1']  # Use F1 as primary score for multiclass

                                # ---------------- TRAIN METRICS ----------------
                                metrics['train_accuracy'] = float(accuracy_score(y_train, y_pred_train))
                                metrics['train_precision'] = float(precision_score(y_train, y_pred_train, average='weighted', zero_division=0))
                                metrics['train_recall'] = float(recall_score(y_train, y_pred_train, average='weighted', zero_division=0))
                                metrics['train_f1_score'] = float(f1_score(y_train, y_pred_train, average='weighted', zero_division=0))

                                if y.nunique() == 2 and y_proba_train is not None:
                                    metrics['train_auc'] = float(roc_auc_score(y_train, y_proba_train[:, 1]))
                                    metrics['train_log_loss'] = float(log_loss(y_train, y_proba_train))

                                if y.nunique() == 2:
                                    self._apply_binary_rank_order_metrics(
                                        metrics,
                                        y_train=np.asarray(y_train),
                                        p_train=y_proba_train[:, 1] if y_proba_train is not None else None,
                                        y_test=np.asarray(y_test),
                                        p_test=y_proba[:, 1] if y_proba is not None else None,
                                    )

                                elif problem_type != 'classification':
                                    # ---------------- TEST METRICS (REGRESSION) ----------------
                                    metrics['test_r2'] = float(r2_score(y_test, y_pred))
                                    metrics['test_mae'] = float(mean_absolute_error(y_test, y_pred))
                                    metrics['test_mse'] = float(mean_squared_error(y_test, y_pred))
                                    metrics['test_rmse'] = float(np.sqrt(mean_squared_error(y_test, y_pred)))

                                    # Backward-compatible aliases
                                    metrics['r2'] = metrics['test_r2']
                                    metrics['mae'] = metrics['test_mae']
                                    metrics['mse'] = metrics['test_mse']
                                    metrics['rmse'] = metrics['test_rmse']

                                    current_score = metrics['r2']  # Use R2 as primary score for regression

                                    # ---------------- TRAIN METRICS (REGRESSION) ----------------
                                    metrics['train_r2'] = float(r2_score(y_train, y_pred_train))
                                    metrics['train_mae'] = float(mean_absolute_error(y_train, y_pred_train))
                                    metrics['train_mse'] = float(mean_squared_error(y_train, y_pred_train))
                                    metrics['train_rmse'] = float(np.sqrt(mean_squared_error(y_train, y_pred_train)))

                            except Exception as e:
                                self.logger.warning(f"Error calculating initial metrics for iteration {iteration}: {str(e)}")
                                # Set default values if calculation fails
                                if problem_type == 'classification':
                                    metrics['accuracy'] = 0.0
                                    metrics['precision'] = 0.0
                                    metrics['recall'] = 0.0
                                    metrics['f1'] = 0.0
                                    metrics['test_accuracy'] = 0.0
                                    metrics['test_precision'] = 0.0
                                    metrics['test_recall'] = 0.0
                                    metrics['test_f1_score'] = 0.0
                                    metrics['train_accuracy'] = 0.0
                                    metrics['train_precision'] = 0.0
                                    metrics['train_recall'] = 0.0
                                    metrics['train_f1_score'] = 0.0
                                    metrics['test_ks_statistic'] = 0.0
                                    metrics['train_ks_statistic'] = 0.0
                                    metrics['ks_statistic'] = 0.0
                                    current_score = 0.0
                                else:
                                    metrics['r2'] = 0.0
                                    metrics['mae'] = 0.0
                                    metrics['mse'] = 0.0
                                    metrics['rmse'] = 0.0
                                    metrics['test_r2'] = 0.0
                                    metrics['test_mae'] = 0.0
                                    metrics['test_mse'] = 0.0
                                    metrics['test_rmse'] = 0.0
                                    metrics['train_r2'] = 0.0
                                    metrics['train_mae'] = 0.0
                                    metrics['train_mse'] = 0.0
                                    metrics['train_rmse'] = 0.0
                                    current_score = 0.0

                        # Calculate improvement from previous iteration
                        improvement = current_score - best_score if iteration > 1 else 0.0

                        # Update best score if current is better
                        if current_score > best_score:
                            best_score = current_score
                            best_iteration = iteration
                            # Keep the best performing model
                            model = iteration_model

                        # Get current model parameters for tracking (use the sampled params, not model.get_params())
                        current_params = sampled_params

                        feature_importance_count = nonzero_feature_slot_count(iteration_model)

                        # Add iteration to history with all calculated metrics
                        iteration_metrics = metrics.copy()
                        
                        iteration_history.append({
                            'iteration': iteration,
                            'score': current_score,
                            'improvement': improvement,
                            'hyperparameters': current_params,  # Store as dict, not string
                            'status': 'Best Score' if iteration == best_iteration else 'Completed',
                            'metrics': iteration_metrics,
                            'feature_importance_count': feature_importance_count
                        })

                # Calculate final cross-validation scores
                cv_metric = 'accuracy' if problem_type == 'classification' else 'r2'
                try:
                    # Optimized: Reduced cv from 5 to 3 for faster training
                    cv_scores = cross_val_score(model, X_train_eff, y_train, cv=resolved_cv_folds, scoring=cv_metric)
                except Exception:
                    cv_scores = np.array([])

                # Calculate final metrics for the best model
                final_model = model  # This is the best performing model from all iterations

                # Recalculate metrics for the final best model to ensure accuracy
                # Handle case when there's no test set (active_scope == 'entire')
                if X_test_eff is None or y_test is None:
                    self.logger.info(f"{algo} (FINAL) - No test set available (active_scope='entire'), skipping test predictions")
                    y_pred_final = None
                    y_proba_final = None
                else:
                    y_pred_final = final_model.predict(X_test_eff)
                    y_proba_final = final_model.predict_proba(X_test_eff) if hasattr(final_model, 'predict_proba') else None
                    
                    # DEBUG: Log final predictions
                    self.logger.info(f"{algo} (FINAL) - Unique class predictions: {np.unique(y_pred_final, return_counts=True)}")
                    self.logger.info(f"{algo} (FINAL) - Prediction distribution: {pd.Series(y_pred_final).value_counts().to_dict()}")
                    if y_proba_final is not None and y_proba_final.shape[1] == 2:
                        self.logger.info(f"{algo} (FINAL) - Probability range for class 1: [{y_proba_final[:, 1].min():.4f}, {y_proba_final[:, 1].max():.4f}]")
                
                # NEW: Train predictions for final model
                y_pred_train_final = final_model.predict(X_train_eff)
                y_proba_train_final = final_model.predict_proba(X_train_eff) if hasattr(final_model, 'predict_proba') else None

                final_metrics: Dict[str, float] = {}

                if problem_type == 'classification':
                    # ---------------- TEST METRICS ----------------
                    if X_test_eff is None or y_test is None:
                        # No test set - set test metrics to None
                        final_metrics['test_accuracy'] = None
                        final_metrics['test_precision'] = None
                        final_metrics['test_recall'] = None
                        final_metrics['test_f1_score'] = None
                        final_metrics['test_auc'] = None
                        final_metrics['test_log_loss'] = None
                        final_metrics['test_ks_statistic'] = None
                        
                        # Backward-compatible aliases (use train metrics)
                        final_metrics['accuracy'] = None
                        final_metrics['precision'] = None
                        final_metrics['recall'] = None
                        final_metrics['f1'] = None
                        final_metrics['auc'] = None
                        final_metrics['log_loss'] = None
                        final_metrics['ks_statistic'] = None
                    else:
                        final_metrics['test_accuracy'] = float(accuracy_score(y_test, y_pred_final))
                        final_metrics['test_precision'] = float(precision_score(y_test, y_pred_final, average='weighted'))
                        final_metrics['test_recall'] = float(recall_score(y_test, y_pred_final, average='weighted'))
                        final_metrics['test_f1_score'] = float(f1_score(y_test, y_pred_final, average='weighted'))

                        # Backward-compatible aliases
                        final_metrics['accuracy'] = final_metrics['test_accuracy']
                        final_metrics['precision'] = final_metrics['test_precision']
                        final_metrics['recall'] = final_metrics['test_recall']
                        final_metrics['f1'] = final_metrics['test_f1_score']

                        if y.nunique() == 2 and y_proba_final is not None:
                            final_metrics['test_auc'] = float(roc_auc_score(y_test, y_proba_final[:, 1]))
                            final_metrics['test_log_loss'] = float(log_loss(y_test, y_proba_final))

                            final_metrics['auc'] = final_metrics['test_auc']
                            final_metrics['log_loss'] = final_metrics['test_log_loss']

                    # ---------------- TRAIN METRICS ----------------
                    final_metrics['train_accuracy'] = float(accuracy_score(y_train, y_pred_train_final))
                    final_metrics['train_precision'] = float(precision_score(y_train, y_pred_train_final, average='weighted'))
                    final_metrics['train_recall'] = float(recall_score(y_train, y_pred_train_final, average='weighted'))
                    final_metrics['train_f1_score'] = float(f1_score(y_train, y_pred_train_final, average='weighted'))

                    if y.nunique() == 2 and y_proba_train_final is not None:
                        final_metrics['train_auc'] = float(roc_auc_score(y_train, y_proba_train_final[:, 1]))
                        final_metrics['train_log_loss'] = float(log_loss(y_train, y_proba_train_final))
                        # If no test set was available, expose primary metric aliases from train metrics
                        if X_test_eff is None or y_test is None:
                            try:
                                final_metrics['accuracy'] = final_metrics.get('train_accuracy')
                                final_metrics['precision'] = final_metrics.get('train_precision')
                                final_metrics['recall'] = final_metrics.get('train_recall')
                                final_metrics['f1'] = final_metrics.get('train_f1_score')
                                if 'train_auc' in final_metrics:
                                    final_metrics['auc'] = final_metrics.get('train_auc')
                                    final_metrics['log_loss'] = final_metrics.get('train_log_loss')
                            except Exception:
                                pass

                    if y.nunique() == 2:
                        self._apply_binary_rank_order_metrics(
                            final_metrics,
                            y_train=np.asarray(y_train),
                            p_train=y_proba_train_final[:, 1] if y_proba_train_final is not None else None,
                            y_test=np.asarray(y_test) if X_test_eff is not None and y_test is not None else None,
                            p_test=y_proba_final[:, 1] if y_proba_final is not None and X_test_eff is not None and y_test is not None else None,
                        )
                        if X_test_eff is None or y_test is None:
                            try:
                                final_metrics['ks_statistic'] = final_metrics.get('train_ks_statistic', 0.0)
                            except Exception:
                                pass

                    final_metrics['feature_importance_count'] = nonzero_feature_slot_count(final_model)
                    try:
                        final_metrics['feature_count'] = int(getattr(X_train_eff, "shape", (0,))[1] or 0)
                    except Exception:
                        pass
                else:
                    # ---------------- TEST METRICS (REGRESSION) ----------------
                    if X_test_eff is None or y_test is None:
                        # No test set - set test metrics to None
                        final_metrics['test_r2'] = None
                        final_metrics['test_mae'] = None
                        final_metrics['test_mse'] = None
                        final_metrics['test_rmse'] = None
                        
                        # Backward-compatible aliases
                        final_metrics['r2'] = None
                        final_metrics['mae'] = None
                        final_metrics['mse'] = None
                        final_metrics['rmse'] = None
                    else:
                        final_metrics['test_r2'] = float(r2_score(y_test, y_pred_final))
                        final_metrics['test_mae'] = float(mean_absolute_error(y_test, y_pred_final))
                        final_metrics['test_mse'] = float(mean_squared_error(y_test, y_pred_final))
                        final_metrics['test_rmse'] = float(np.sqrt(mean_squared_error(y_test, y_pred_final)))

                        final_metrics['r2'] = final_metrics['test_r2']
                        final_metrics['mae'] = final_metrics['test_mae']
                        final_metrics['mse'] = final_metrics['test_mse']
                        final_metrics['rmse'] = final_metrics['test_rmse']

                    # ---------------- TRAIN METRICS (REGRESSION) ----------------
                    final_metrics['train_r2'] = float(r2_score(y_train, y_pred_train_final))
                    final_metrics['train_mae'] = float(mean_absolute_error(y_train, y_pred_train_final))
                    final_metrics['train_mse'] = float(mean_squared_error(y_train, y_pred_train_final))
                    final_metrics['train_rmse'] = float(np.sqrt(mean_squared_error(y_train, y_pred_train_final)))

                    # If no test set was available, expose primary metric aliases from train metrics
                    if X_test_eff is None or y_test is None:
                        try:
                            final_metrics['r2'] = final_metrics.get('train_r2')
                            final_metrics['mae'] = final_metrics.get('train_mae')
                            final_metrics['mse'] = final_metrics.get('train_mse')
                            final_metrics['rmse'] = final_metrics.get('train_rmse')
                        except Exception:
                            pass
                    # Calculate adjusted R2 for regression (based on TEST set if available, else TRAIN set)
                    if X_test_eff is None or y_test is None:
                        # No test set - calculate adjusted R2 based on train set
                        if 'train_r2' in final_metrics and final_metrics['train_r2'] is not None:
                            n = len(y_train)  # Number of samples in train set
                            p = X_train_eff.shape[1]  # Number of features
                            if n > p + 1:  # Avoid division by zero
                                final_metrics['adjusted_r2'] = 1 - (1 - final_metrics['train_r2']) * (n - 1) / (n - p - 1)
                            else:
                                final_metrics['adjusted_r2'] = final_metrics['train_r2']
                        else:
                            final_metrics['adjusted_r2'] = None
                    else:
                        # Test set available - calculate based on test set
                        if 'r2' in final_metrics and final_metrics['r2'] is not None:
                            n = len(y_test)  # Number of samples in test set
                            p = X_test_eff.shape[1]  # Number of features
                            if n > p + 1:  # Avoid division by zero
                                final_metrics['adjusted_r2'] = 1 - (1 - final_metrics['r2']) * (n - 1) / (n - p - 1)
                            else:
                                final_metrics['adjusted_r2'] = final_metrics['r2']
                        else:
                            final_metrics['adjusted_r2'] = None

                model_id = f"MDL_MULTI_{uuid.uuid4().hex[:8].upper()}"
                artifact_path = os.path.join('models', f"{model_id}.pkl")
                joblib.dump(final_model, artifact_path)

                # Extract best hyperparameters from the best iteration
                best_hyperparameters = {}
                if iteration_history and len(iteration_history) >= best_iteration:
                    best_iteration_data = iteration_history[best_iteration - 1]  # Convert to 0-based index
                    hyperparams = best_iteration_data.get('hyperparameters', {})
                    
                    # Handle both dict (current) and string (legacy) formats
                    if isinstance(hyperparams, dict):
                        best_hyperparameters = hyperparams
                    elif isinstance(hyperparams, str):
                        try:
                            import ast
                            best_hyperparameters = ast.literal_eval(hyperparams)
                        except:
                            best_hyperparameters = {}
                    else:
                        best_hyperparameters = {}

                # Comprehensive model evaluation (MEEA integration)
                # Deferred to background task - store args and return immediately so training
                # results reach the UI without waiting for the expensive MEEA computation.
                _meea_args = None  # default; set inside try block below
                try:
                    # Get preprocessed column mapping if available
                    preprocessed_columns = getattr(self, 'preprocessed_column_mapping', {})

                    # Extract category mappings from label encoders for reverse-encoding
                    category_mappings = {}
                    label_encoders = pp.get('encoders', {}) if pp else {}
                    if label_encoders:
                        for feature_name, label_encoder in label_encoders.items():
                            if hasattr(label_encoder, 'classes_'):
                                category_mappings[feature_name] = {
                                    i: str(class_name) for i, class_name in enumerate(label_encoder.classes_)
                                }

                    feature_names = list(X_train_eff.columns)

                    # Extract original (pre-encoding) test/train data for MEEA
                    X_test_original = None
                    X_train_original = None
                    
                    # For train scope: use X_test_original (stored during test data extraction)
                    # This is the correct approach - X_before_encoding is from train data only, not test data
                    if active_scope == 'train' and hasattr(self, 'X_test_original') and self.X_test_original is not None:
                        X_test_original = self.X_test_original.copy()
                        self.logger.info(f"✅ Using X_test_original for test granular accuracy: {X_test_original.shape}")
                        self.logger.info(f"   Columns: {list(X_test_original.columns)[:10]}")
                    elif X_before_encoding is not None and test_indices is not None:
                        try:
                            X_test_original = X_before_encoding.loc[test_indices].copy()
                            self.logger.info(f"✅✅✅ Extracted original test data BEFORE encoding: {X_test_original.shape}")
                            self.logger.info(f"   Columns: {list(X_test_original.columns)[:10]}")
                        except Exception as e:
                            self.logger.warning(f"Failed to extract original test data from X_before_encoding: {str(e)}")

                    if X_test_original is None and X_before_scaling is not None and test_indices is not None:
                        try:
                            if active_scope == 'train':
                                X_test_original = X_before_scaling.iloc[test_indices].copy()
                            else:
                                X_test_original = X_before_scaling.loc[test_indices].copy()
                            self.logger.warning(f"⚠️ Using X_before_scaling (encoded values) instead of X_before_encoding for X_test_original")
                        except Exception as e:
                            self.logger.warning(f"Failed to extract from X_before_scaling: {str(e)}")

                    if X_before_encoding is not None and train_indices is not None:
                        try:
                            if active_scope == 'train':
                                X_train_original = X_before_encoding.iloc[train_indices].copy()
                            else:
                                X_train_original = X_before_encoding.loc[train_indices].copy()
                            self.logger.info(f"✅✅✅ SUCCESS: Extracted X_train_original from X_before_encoding: shape {X_train_original.shape}")
                        except Exception as e:
                            self.logger.error(f"❌❌❌ FAILED to extract original train data from X_before_encoding: {str(e)}")
                            X_train_original = None
                    if X_train_original is None and X_before_scaling is not None and train_indices is not None:
                        try:
                            if active_scope == 'train':
                                X_train_original = X_before_scaling.iloc[train_indices].copy()
                            else:
                                X_train_original = X_before_scaling.loc[train_indices].copy()
                            self.logger.warning(f"⚠️⚠️⚠️ Using X_before_scaling (encoded values) instead of X_before_encoding for X_train_original: shape {X_train_original.shape}")
                        except Exception as e:
                            self.logger.error(f"❌❌❌ Failed to extract X_train_original from X_before_scaling: {str(e)}")

                    # Store MEEA args as part of the result dict so they survive the loky
                    # subprocess boundary.  The parent process will extract these after
                    # Parallel() returns and register them in _pending_meea_jobs there.
                    _meea_args = {
                        'model': final_model,
                        'model_id': model_id,
                        'algorithm_name': algo,
                        'X_train': X_train_eff,
                        'X_test': X_test_eff,
                        'y_train': y_train,
                        'y_test': y_test,
                        'problem_type': problem_type,
                        'feature_names': feature_names,
                        'dataset_id': dataset_id,
                        'active_scope': active_scope,
                        'target_column': target_column,
                        'split_params': split_params,
                        'preprocessed_columns': preprocessed_columns,
                        'train_indices': train_indices,
                        'test_indices': test_indices,
                        'category_mappings': category_mappings,
                        'X_test_original': X_test_original,
                        'X_train_original': X_train_original,
                        'scaler': pp.get('scaler') if pp else None,
                        'column_stats': column_stats,
                    }
                    self.logger.info(f"Prepared MEEA args for {algo} ({model_id}) - will register in parent process")
                except Exception as eval_error:
                    _meea_args = None
                    self.logger.warning(f"Failed to prepare MEEA args for {algo}: {str(eval_error)}")
                    import traceback
                    self.logger.warning(traceback.format_exc())

                # Extract category mappings from label encoders for saving
                category_mappings_to_save = {}
                if hasattr(pp, 'label_encoders') and pp.get('label_encoders'):
                    for feature_name, label_encoder in pp['label_encoders'].items():
                        if hasattr(label_encoder, 'classes_'):
                            # Create mapping: {encoded_value: original_category_name}
                            category_mappings_to_save[feature_name] = {
                                int(i): str(class_name) for i, class_name in enumerate(label_encoder.classes_)
                            }
                    logger.info(f"💾 Saving category_mappings for {len(category_mappings_to_save)} features to training_results.json")
                
                # Save comprehensive training results as JSON
                coefficient_signs: List[Dict[str, Any]] = []
                try:
                    if hasattr(final_model, 'coef_'):
                        coef_array = np.asarray(final_model.coef_)
                        if coef_array.ndim > 1:
                            coef_values = np.max(np.abs(coef_array), axis=0)
                        else:
                            coef_values = coef_array
                        for idx, feature in enumerate(list(X_train_eff.columns)):
                            coef_val = float(coef_values[idx]) if idx < len(coef_values) else 0.0
                            sign_val = 1 if coef_val > 0 else -1 if coef_val < 0 else 0
                            coefficient_signs.append({
                                "feature": feature,
                                "coefficient": coef_val,
                                "sign": sign_val,
                            })
                except Exception as coef_err:
                    self.logger.warning(f"Failed to extract coefficient signs for {algo}: {coef_err}")

                training_results = {
                    'model_id': model_id,
                    'algorithm': algo,
                    'problem_type': problem_type,
                    'metrics': final_metrics,
                    'cv_scores': cv_scores.tolist() if cv_scores.size else [],
                    'artifact_path': artifact_path,
                    'iteration_history': iteration_history,
                    'hyperparameters': best_hyperparameters,
                    'best_iteration': best_iteration,
                    'training_time_seconds': 0,  # Could be calculated if needed
                    'used_features': list(X_train_eff.columns),
                    'lr_backward_elimination': lr_elimination_audit,
                    'coefficient_signs': coefficient_signs,
                    'column_stats': column_stats,  # Save column_stats with variable types
                    'category_mappings': category_mappings_to_save  # Save category mappings for granular accuracy
                }

                # Save training results as JSON file
                results_json_path = os.path.join('models', f"{model_id}_training_results.json")
                with open(results_json_path, 'w') as f:
                    json.dump(training_results, f, indent=2, default=str)

                return {
                    'model_id': model_id,
                    'algorithm': algo,
                    'metrics': final_metrics,
                    'cv_scores': cv_scores.tolist() if cv_scores.size else [],
                    'artifact_path': artifact_path,
                    'iteration_history': iteration_history,
                    'coefficient_signs': coefficient_signs,
                    'used_features': list(X_train_eff.columns),
                    'lr_backward_elimination': lr_elimination_audit,
                    # Carry MEEA args back to the parent process (loky IPC fix)
                    '_meea_args': _meea_args,
                }
            except Exception as e:
                logger.warning(f"Training failed for {algo}: {str(e)}")
                return {
                    'algorithm': algo,
                    'error': str(e),
                    '_meea_args': None,
                }

        # Use parallel processing with n_jobs=2 for Azure (limited cores)
        self.logger.info(f"Training {len(models)} algorithms in parallel...")
        results_list = Parallel(n_jobs=-1, backend='loky', verbose=1, batch_size='auto', pre_dispatch='2*n_jobs')(
            delayed(train_single_algorithm_with_iterations)((algo, model)) for algo, model in models.items()
        )

        # Extract MEEA args from child-process results and register them in the
        # parent process _pending_meea_jobs dict (fixes the loky IPC issue).
        from app.services.model_training_auto_training import ModelTrainingAutoTrainingService
        for r in results_list:
            if r is not None and r.get('_meea_args'):
                meea_args = r.pop('_meea_args')
                mid = meea_args.get('model_id')
                if mid:
                    ModelTrainingAutoTrainingService._pending_meea_jobs[mid] = meea_args
                    self.logger.info(f"Registered MEEA background job for {meea_args.get('algorithm_name')} ({mid}) in parent process")
            elif r is not None:
                r.pop('_meea_args', None)

        # Filter out None results
        results = [r for r in results_list if r is not None]

        step6_views = self._build_step6_views(
            results=results,
            problem_type=problem_type,
            optimization_method=optimization_method,
            cv_folds=resolved_cv_folds,
            optuna_trials=resolved_optuna_trials,
            early_stopping_rounds=resolved_early_stopping,
            target_metric=target_metric,
            correlation_map=correlation_map,
        )

        return {
            'problem_type': problem_type,
            'results': results,
            'used_features': list(X.columns),
            'variable_selection': variable_selection,
            'training_configuration': {
                'optimization_method': optimization_method,
                'target_metric': target_metric,
                'cv_folds': resolved_cv_folds,
                'optuna_trials': resolved_optuna_trials,
                'early_stopping_rounds': resolved_early_stopping,
                'lr_backward_elimination': lr_backward_elimination or {},
            },
            'step6_views': step6_views,
            'preprocessing_summary': pp.get('preprocessing_summary', {
                'is_already_preprocessed': False,
                'variables': [],
                'dropped_variables': [],
                'total_processed': 0,
                'total_dropped': 0
            })
        }

    def run_lr_backward_elimination_interactive(
        self,
        df: pd.DataFrame,
        *,
        target_column: str,
        independent_variables: Optional[List[str]],
        locked_variables: Optional[List[str]] = None,
        dataset_id: Optional[str] = None,
        weight_variable: Optional[str] = None,
        vif_threshold: float = 5.0,
        p_value_threshold: float = 0.05,
        segment_id: Optional[Union[str, int, float]] = None,
        segment_column: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build train/test matrices the same way as manual training, then run §7.2 LR backward elimination.
        Used when the user selects the Logistic Regression path in Step 6 (on-demand audit).
        """
        from app.utils.lr_backward_elimination import run_lr_backward_elimination

        work_df = df
        if segment_id is not None and str(segment_id).strip() != "" and str(segment_id).lower() != "all":
            seg_col = segment_column
            if not seg_col:
                for cand in ("segment", "SEGMENT", "segment_id", "SEGMENT_ID"):
                    if cand in work_df.columns:
                        seg_col = cand
                        break
            if not seg_col or seg_col not in work_df.columns:
                return {
                    "success": False,
                    "error": "segment_id was provided but no segment column was found on the dataframe",
                    "lr_backward_elimination": None,
                }
            work_df = work_df[work_df[seg_col] == segment_id].copy()
            if len(work_df) < 10:
                return {
                    "success": False,
                    "error": f"Segment filter produced too few rows ({len(work_df)}); need a usable train set",
                    "lr_backward_elimination": None,
                }

        sparse_cols = [c for c in work_df.columns if isinstance(work_df[c].dtype, pd.SparseDtype)]
        if sparse_cols:
            work_df = work_df.copy()
            for c in sparse_cols:
                work_df[c] = work_df[c].sparse.to_dense()

        available_vars = self.get_available_variables(work_df)
        candidate_independent = available_vars.get("default_independent", [])
        if target_column in candidate_independent:
            candidate_independent.remove(target_column)
        variable_selection = self.apply_variable_locking(
            independent_variables=candidate_independent,
            selected_variables=independent_variables,
            locked_variables=locked_variables,
            selection_mode="manual",
        )
        ind_vars = variable_selection.get("selected_variables", [])
        if not ind_vars:
            return {
                "success": False,
                "error": "No independent variables available after applying manual locks/selection",
                "lr_backward_elimination": None,
            }

        sample_weights = None
        if weight_variable and weight_variable in work_df.columns:
            sample_weights = work_df[weight_variable].values.copy()
            if weight_variable in ind_vars:
                ind_vars = [v for v in ind_vars if v != weight_variable]

        _cache_key = (dataset_id, frozenset(ind_vars or []), target_column)
        _cached = self._preprocess_cache.get(_cache_key)
        _cache_valid = False
        if _cached is not None and dataset_id:
            try:
                from app.services.dataframe_state_manager import dataframe_state_manager as _dsm_c

                _meta_c = _dsm_c.get_dataset_info(dataset_id)
                if _meta_c and _meta_c.get("last_updated") == _cached[1]:
                    pp = _cached[0]
                    _cache_valid = True
            except Exception:
                pass

        if not _cache_valid:
            pp = self._preprocess(work_df, target_column, ind_vars)
            if dataset_id:
                try:
                    from app.services.dataframe_state_manager import dataframe_state_manager as _dsm_c2

                    _meta_c2 = _dsm_c2.get_dataset_info(dataset_id)
                    _last_upd_c = _meta_c2.get("last_updated") if _meta_c2 else None
                    self._preprocess_cache[_cache_key] = (pp, _last_upd_c)
                except Exception:
                    pass

        X, y = pp["X"], pp["y"]
        encoded_columns = set(pp.get("encoders", {}).keys()) if pp.get("encoders") else set()
        preprocessed_column_mapping: Dict[str, str] = {}
        for col in X.columns:
            if col in encoded_columns:
                preprocessed_column_mapping[col] = f"{col}_le_manual"
            else:
                preprocessed_column_mapping[col] = f"{col}_ss_manual"
        self.preprocessed_column_mapping = preprocessed_column_mapping

        problem_type = self.detect_problem_type_from_data(work_df, target_column)["problem_type"]
        if problem_type != "classification" or int(pd.Series(y).nunique(dropna=True)) != 2:
            return {
                "success": False,
                "error": "LR backward elimination (§7.2) applies only to binary classification",
                "lr_backward_elimination": None,
            }

        active_scope = "entire"
        if dataset_id:
            try:
                from app.services.dataframe_state_manager import dataframe_state_manager

                active_scope = dataframe_state_manager._active_scope.get(dataset_id, "entire")
            except Exception:
                active_scope = "entire"

        if active_scope == "entire":
            X_train = X.copy()
            y_train = y.copy()
            X_test = None
            y_test = None
            self.logger.info(
                "[SCOPE_DATA_TRACE][manual_lr_interactive] dataset_id=%s active_scope=%s train_source=entire holdout_source=none rows_train=%s",
                dataset_id,
                active_scope,
                len(X),
            )
        else:
            X_train = X.copy()
            y_train = y.copy()
            X_test = None
            y_test = None
            if dataset_id:
                try:
                    from app.services.dataframe_state_manager import dataframe_state_manager as _dsm
                    previous_scope = _dsm._active_scope.get(dataset_id, "entire")
                    test_df = None
                    holdout_scope_used = None
                    try:
                        for scope_name in ("test", "validation", "train", "entire"):
                            self.logger.info(
                                "[SCOPE_DATA_TRACE][manual_lr_interactive] dataset_id=%s holdout_probe_scope=%s previous_scope=%s",
                                dataset_id,
                                scope_name,
                                previous_scope,
                            )
                            _dsm.set_scope(dataset_id, scope=scope_name)
                            candidate_df = _dsm.get_dataframe(dataset_id)
                            candidate_rows = len(candidate_df) if candidate_df is not None else 0
                            if candidate_df is not None and candidate_rows > 0 and target_column in candidate_df.columns:
                                test_df = candidate_df
                                holdout_scope_used = scope_name
                                break
                            self.logger.info(
                                "[SCOPE_DATA_TRACE][manual_lr_interactive] dataset_id=%s holdout_scope=%s rows=%s has_target=%s continuing_fallback",
                                dataset_id,
                                scope_name,
                                candidate_rows,
                                bool(candidate_df is not None and target_column in candidate_df.columns),
                            )
                    finally:
                        try:
                            _dsm.set_scope(dataset_id, scope=previous_scope)
                            self.logger.info(
                                "[SCOPE_DATA_TRACE][manual_lr_interactive] dataset_id=%s scope_restored=%s",
                                dataset_id,
                                previous_scope,
                            )
                        except Exception:
                            self.logger.warning(
                                "Interactive LR elimination: could not restore scope '%s' for dataset %s",
                                previous_scope,
                                dataset_id,
                            )

                    if test_df is not None and len(test_df) > 0 and target_column in test_df.columns:
                        if self.preprocessed_column_mapping:
                            test_features = []
                            for orig_col in ind_vars:
                                preprocessed_col = self.preprocessed_column_mapping.get(orig_col)
                                if preprocessed_col and preprocessed_col in test_df.columns:
                                    test_features.append(preprocessed_col)
                            if test_features:
                                X_test = test_df[test_features].copy()
                                reverse_mapping = {v: k for k, v in self.preprocessed_column_mapping.items()}
                                X_test.columns = [reverse_mapping.get(col, col) for col in X_test.columns]
                                y_test = test_df[target_column].copy()
                                if hasattr(self, "target_encoder") and self.target_encoder is not None:
                                    y_test = y_test.astype(str)
                                    known_classes = set(self.target_encoder.classes_)
                                    y_test = y_test.apply(
                                        lambda x: self.target_encoder.transform([x])[0] if x in known_classes else -1
                                    )
                                self.logger.info(
                                    "[SCOPE_DATA_TRACE][manual_lr_interactive] dataset_id=%s holdout_source=%s rows_test=%s cols_test=%s",
                                    dataset_id,
                                    holdout_scope_used or "unknown",
                                    len(y_test) if y_test is not None else 0,
                                    X_test.shape[1] if X_test is not None else 0,
                                )
                except Exception as ex:
                    self.logger.warning("Interactive LR elimination: failed to load holdout test: %s", ex)

        locked = variable_selection.get("locked_variables") or []
        audit = run_lr_backward_elimination(
            X_train=X_train,
            X_test=X_test,
            y_train=y_train,
            y_test=y_test,
            locked_features=locked,
            vif_threshold=float(vif_threshold),
            p_value_threshold=float(p_value_threshold),
        )
        return {"success": True, "error": None, "lr_backward_elimination": audit}


# Create singleton instance
manual_config_service = ModelTrainingManualConfigurationService()


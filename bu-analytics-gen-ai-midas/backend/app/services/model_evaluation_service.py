"""
Model Evaluation Service - Comprehensive model evaluation and analysis
Integrates with MEEA (Model Evaluation and Error Analysis) system
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, log_loss,
    confusion_matrix, roc_curve, precision_recall_curve,
    mean_squared_error, mean_absolute_error, r2_score
)
from sklearn.inspection import permutation_importance
import uuid
from datetime import datetime
import json
from pathlib import Path

# Monotonicity utilities (deciles, KS, AUC/Gini)
# Store import error for frontend display
_monotonicity_import_error = None

def _import_monotonicity():
    """
    Import monotonicity utilities from app.utils.monotonicity.
    Works both on localhost and Azure RI since files are now in backend folder.
    Tries multiple import strategies to ensure compatibility.
    """
    global _monotonicity_import_error
    _monotonicity_import_error = None
    
    import sys
    import traceback
    
    # Strategy 1: Try absolute import from app.utils.monotonicity
    try:
        from app.utils.monotonicity import (
            decile_table as mono_decile_table,
            monotonicity_score as mono_score,
            calculate_ks_detailed,
            ks_from_deciles,
            compute_auc_gini,
            calculate_psi,
            calculate_psi_detailed,
            calculate_csi_for_variables,
        )
        return mono_decile_table, mono_score, calculate_ks_detailed, ks_from_deciles, compute_auc_gini, calculate_psi, calculate_psi_detailed, calculate_csi_for_variables
    except Exception as e1:
        error1 = f"Strategy 1 (app.utils.monotonicity) failed: {str(e1)}"
        
        # Strategy 2: Try relative import
        try:
            from ..utils.monotonicity import (
                decile_table as mono_decile_table,
                monotonicity_score as mono_score,
                calculate_ks_detailed,
                ks_from_deciles,
                compute_auc_gini,
                calculate_psi,
                calculate_psi_detailed,
                calculate_csi_for_variables,
            )
            return mono_decile_table, mono_score, calculate_ks_detailed, ks_from_deciles, compute_auc_gini, calculate_psi, calculate_psi_detailed, calculate_csi_for_variables
        except Exception as e2:
            error2 = f"Strategy 2 (relative import) failed: {str(e2)}"
            
            # Strategy 3: Try adding backend path to sys.path and importing
            try:
                # Find backend folder (where app/ directory is located)
                current_file = Path(__file__).resolve()
                # Navigate: services -> app -> backend
                backend_path = current_file.parent.parent.parent  # backend folder
                app_path = current_file.parent.parent  # app folder
                
                # Try adding both backend and app paths
                paths_to_add = [str(backend_path), str(app_path)]
                for path_to_add in paths_to_add:
                    if path_to_add not in sys.path:
                        sys.path.insert(0, path_to_add)
                
                from app.utils.monotonicity import (
                    decile_table as mono_decile_table,
                    monotonicity_score as mono_score,
                    calculate_ks_detailed,
                    ks_from_deciles,
                    compute_auc_gini,
                    calculate_psi,
                    calculate_psi_detailed,
                    calculate_csi_for_variables,
                )
                return mono_decile_table, mono_score, calculate_ks_detailed, ks_from_deciles, compute_auc_gini, calculate_psi, calculate_psi_detailed, calculate_csi_for_variables
            except Exception as e3:
                error3 = f"Strategy 3 (sys.path manipulation) failed: {str(e3)}"
                
                # Strategy 4: Try direct file import
                try:
                    import importlib.util
                    utils_path = Path(__file__).resolve().parent.parent / "utils" / "monotonicity.py"
                    if utils_path.exists():
                        spec = importlib.util.spec_from_file_location("monotonicity", utils_path)
                        monotonicity_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(monotonicity_module)
                        
                        mono_decile_table = monotonicity_module.decile_table
                        mono_score = monotonicity_module.monotonicity_score
                        calculate_ks_detailed = monotonicity_module.calculate_ks_detailed
                        ks_from_deciles = monotonicity_module.ks_from_deciles
                        compute_auc_gini = monotonicity_module.compute_auc_gini
                        calculate_psi = monotonicity_module.calculate_psi
                        calculate_psi_detailed = monotonicity_module.calculate_psi_detailed
                        calculate_csi_for_variables = monotonicity_module.calculate_csi_for_variables
                        
                        return mono_decile_table, mono_score, calculate_ks_detailed, ks_from_deciles, compute_auc_gini, calculate_psi, calculate_psi_detailed, calculate_csi_for_variables
                    else:
                        error4 = f"Strategy 4 (direct file import) failed: File not found at {utils_path}. Current file: {Path(__file__).resolve()}"
                except Exception as e4:
                    error4 = f"Strategy 4 (direct file import) failed: {str(e4)}"
                
                # All strategies failed - store detailed error message for frontend
                current_file = Path(__file__).resolve()
                utils_path_check = current_file.parent.parent / "utils" / "monotonicity.py"
                sys_path_info = f"sys.path: {sys.path[:5]}..." if len(sys.path) > 5 else f"sys.path: {sys.path}"
                _monotonicity_import_error = (
                    f"Monotonicity import failed after trying 4 strategies. "
                    f"Current file: {current_file}. "
                    f"Expected utils path: {utils_path_check} (exists: {utils_path_check.exists()}). "
                    f"{sys_path_info}. "
                    f"Errors: 1) {error1}; 2) {error2}; 3) {error3}; 4) {error4}"
                )
                return None, None, None, None, None, None, None, None


mono_decile_table, mono_score, calculate_ks_detailed, ks_from_deciles, compute_auc_gini, calculate_psi, calculate_psi_detailed, calculate_csi_for_variables = _import_monotonicity()

def safe_float(val):
    """Convert value to float, replacing NaN/Inf with 0.0"""
    if val is None:
        return 0.0
    if isinstance(val, (float, np.floating)):
        if np.isnan(val) or np.isinf(val):
            return 0.0
        return float(val)
    try:
        result = float(val)
        if np.isnan(result) or np.isinf(result):
            return 0.0
        return result
    except (ValueError, TypeError):
        return 0.0


def safe_scaler_transform(scaler, X, feature_names=None):
    """
    Safely apply scaler.transform() ensuring feature names match.
    
    Args:
        scaler: Fitted sklearn scaler
        X: DataFrame or array to transform
        feature_names: Optional list of feature names expected by scaler
    
    Returns:
        Transformed data with matching feature names
    """
    import pandas as pd
    
    # Get feature names that scaler expects
    scaler_feature_names = None
    if hasattr(scaler, 'feature_names_in_'):
        scaler_feature_names = scaler.feature_names_in_
    elif hasattr(scaler, 'get_feature_names_out'):
        try:
            scaler_feature_names = scaler.get_feature_names_out()
        except:
            pass
    
    # If X is a DataFrame and scaler has feature names, ensure they match
    if isinstance(X, pd.DataFrame) and scaler_feature_names is not None:
        # Find common features
        common_features = [f for f in scaler_feature_names if f in X.columns]
        
        if len(common_features) == 0:
            raise ValueError(f"No common features between scaler and X. Scaler expects: {list(scaler_feature_names)[:10]}, X has: {list(X.columns)[:10]}")
        
        # Reorder X columns to match scaler's expected order
        X_for_scaler = X[common_features].copy()
        
        # Transform
        transformed = scaler.transform(X_for_scaler)
        
        # Return as DataFrame with same structure
        if isinstance(transformed, np.ndarray):
            return pd.DataFrame(transformed, columns=common_features, index=X.index)
        return transformed
    else:
        # No feature names or X is not DataFrame - try direct transform
        return scaler.transform(X)


class ModelEvaluationService:
    """Service for comprehensive model evaluation and analysis"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def evaluate_model_comprehensive(
        self,
        model: Any,
        model_id: str,
        model_name: str,
        X_train: pd.DataFrame,
        X_test: pd.DataFrame,
        y_train: pd.Series,
        y_test: pd.Series,
        problem_type: str,
        feature_names: List[str],
        dataset_id: Optional[str] = None,  # NEW: For train/test toggle
        active_scope: str = 'entire',  # NEW: For train/test toggle
        target_column: Optional[str] = None,  # NEW: For train/test toggle
        split_params: Optional[Dict[str, Any]] = None,  # NEW: For train/test toggle
        preprocessed_columns: Optional[Dict[str, str]] = None,  # NEW: Preprocessed column mapping ({original: preprocessed})
        train_indices: Optional[List[int]] = None,  # NEW: Train indices for exact split recreation
        test_indices: Optional[List[int]] = None,  # NEW: Test indices for exact split recreation
        include_explainability: bool = False,  # Skip expensive explainability calculation during training
        category_mappings: Optional[Dict[str, Dict[int, str]]] = None,  # NEW: Category mappings {feature_name: {encoded_value: original_name}}
        X_test_original: Optional[pd.DataFrame] = None,  # NEW: Original unscaled test data for continuous variables
        X_train_original: Optional[pd.DataFrame] = None,  # NEW: Original unscaled train data for continuous variables (before encoding)
        scaler: Optional[Any] = None,  # NEW: Scaler to reverse-transform continuous variables
        column_stats: Optional[Dict[str, Any]] = None,  # NEW: Column statistics with data types (from training)
        sample_weight_train: Optional[np.ndarray] = None,  # NEW: Sample weights for train set (weighted metrics)
        sample_weight_test: Optional[np.ndarray] = None  # NEW: Sample weights for test set (weighted metrics)
    ) -> Dict[str, Any]:
        """
        Perform comprehensive model evaluation including:
        - Performance metrics
        - Feature importance
        - Fairness analysis
        - Explainability data (only if include_explainability=True)
        - Granular accuracy
        - Error patterns
        - Prediction confidence
        
        Args:
            model: Trained model instance
            model_id: Unique model identifier
            model_name: Model name/algorithm
            X_train: Training features
            X_test: Test features
            y_train: Training target
            y_test: Test target
            problem_type: 'classification' or 'regression'
            feature_names: List of feature names
            dataset_id: Dataset identifier (for train/test toggle)
            active_scope: Active scope (for train/test toggle)
            target_column: Target column name (for train/test toggle)
            split_params: Split parameters (for train/test toggle)
            preprocessed_columns: Preprocessed column mapping ({original: preprocessed}) for explainability
            train_indices: Train indices for exact split recreation (compressed and stored in DB)
            test_indices: Test indices for exact split recreation (compressed and stored in DB)
            include_explainability: If False, skips expensive SHAP/PDP calculations (default: False)
                                   Explainability will be calculated on-demand when user requests it
        
        Returns:
            Dictionary with comprehensive evaluation results
        """
        try:
            evaluation_results = {
                'model_id': model_id,
                'model_name': model_name,
                'problem_type': problem_type,
                'evaluation_timestamp': datetime.utcnow().isoformat(),
                # NEW: Store metadata for train/test toggle
                'dataset_id': dataset_id,
                'active_scope': active_scope,
                'target_column': target_column,
                'split_params': split_params or {
                    'test_size': 0.2,
                    'random_state': 42,
                    'stratify': False
                },
                # NEW: Store preprocessed column mapping for explainability
                'preprocessed_columns': preprocessed_columns or {},
                # NEW: Store train/test indices for exact split recreation
                'train_indices': train_indices,
                'test_indices': test_indices,
                # NEW: Store original feature names used in training
                'used_features': feature_names
            }
            
            # Check if test set exists (active_scope == 'entire' means no test set)
            has_test_set = X_test is not None and y_test is not None

            # For large datasets, sample the training data to speed up evaluation.
            # Metrics computed on a 50 K-row stratified sample are statistically equivalent
            # to full-data metrics for datasets > 100 K rows.
            _TRAIN_SAMPLE_CAP = 50_000
            _TEST_SAMPLE_CAP  = 50_000

            X_train_eval, y_train_eval = X_train, y_train
            X_test_eval,  y_test_eval  = X_test,  y_test
            _train_sample_idx = None  # indices used when training data was sampled
            _test_sample_idx  = None  # indices used when test data was sampled

            if len(X_train) > _TRAIN_SAMPLE_CAP:
                import numpy as _np
                _rng = _np.random.default_rng(42)
                _train_sample_idx = _rng.choice(len(X_train), size=_TRAIN_SAMPLE_CAP, replace=False)
                _train_sample_idx.sort()
                X_train_eval = X_train.iloc[_train_sample_idx]
                y_train_eval = y_train.iloc[_train_sample_idx]
                self.logger.info(
                    f"Large training set ({len(X_train):,} rows) - using stratified sample of "
                    f"{_TRAIN_SAMPLE_CAP:,} rows for evaluation metrics"
                )

            if has_test_set and X_test is not None and len(X_test) > _TEST_SAMPLE_CAP:
                import numpy as _np2
                _rng2 = _np2.random.default_rng(42)
                _test_sample_idx = _rng2.choice(len(X_test), size=_TEST_SAMPLE_CAP, replace=False)
                _test_sample_idx.sort()
                X_test_eval = X_test.iloc[_test_sample_idx]
                y_test_eval = y_test.iloc[_test_sample_idx]
                self.logger.info(
                    f"Large test set ({len(X_test):,} rows) - using sample of "
                    f"{_TEST_SAMPLE_CAP:,} rows for evaluation metrics"
                )

            # 1. Make predictions on TEST data (only if test set exists)
            y_pred_test = None
            y_pred_proba_test = None
            if has_test_set:
                y_pred_test = model.predict(X_test_eval)
                if problem_type == 'classification' and hasattr(model, 'predict_proba'):
                    y_pred_proba_test = model.predict_proba(X_test_eval)
            else:
                self.logger.info("No test set available (active_scope='entire') - skipping test predictions")
            
            # 2. Make predictions on TRAIN data so we can show train/test scores in UI
            try:
                y_pred_train = model.predict(X_train_eval)
                y_pred_proba_train = None
                if problem_type == 'classification' and hasattr(model, 'predict_proba'):
                    y_pred_proba_train = model.predict_proba(X_train_eval)
                self.logger.info(f"✅✅✅ TRAIN predictions computed: y_pred_train length={len(y_pred_train) if y_pred_train is not None else 'None'}, problem_type={problem_type}")
            except Exception as e:
                # If for some reason train predictions fail, log and continue with test-only metrics
                self.logger.warning(f"Failed to compute train predictions for evaluation: {e}")
                y_pred_train = None
                y_pred_proba_train = None
            
            # 3. Performance Metrics (TEST) - only if test set exists
            test_metrics = {}
            if has_test_set and y_pred_test is not None:
                test_metrics = self._calculate_performance_metrics(
                    y_test_eval, y_pred_test, y_pred_proba_test, problem_type,
                    sample_weight=sample_weight_test[_test_sample_idx] if (sample_weight_test is not None and _test_sample_idx is not None) else sample_weight_test
                )
            else:
                self.logger.info("No test metrics calculated (active_scope='entire' or test predictions unavailable)")
            
            # 4. Performance Metrics (TRAIN) - always calculate if train predictions available
            train_metrics = None
            if y_pred_train is not None:
                try:
                    train_metrics = self._calculate_performance_metrics(
                        y_train_eval, y_pred_train, y_pred_proba_train, problem_type,
                        sample_weight=sample_weight_train[_train_sample_idx] if (sample_weight_train is not None and _train_sample_idx is not None) else sample_weight_train
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to calculate train performance metrics: {e}")
                    train_metrics = None
            
            # 5. Merge into a single performance_metrics dict
            #    - If test set exists, use test_metrics as base (for backward compatibility)
            #    - If no test set, use train_metrics as base
            if has_test_set and test_metrics:
                performance_metrics: Dict[str, Any] = dict(test_metrics)
            elif train_metrics:
                performance_metrics: Dict[str, Any] = dict(train_metrics)
            else:
                performance_metrics: Dict[str, Any] = {}
            
            #    - Add explicit train_*/test_* fields for UI
            if problem_type == 'classification':
                scalar_keys = ['accuracy', 'precision', 'recall', 'f1_score', 'auc_roc', 'auc_pr', 'log_loss']
                for key in scalar_keys:
                    if train_metrics and key in train_metrics:
                        performance_metrics[f"train_{key}"] = train_metrics.get(key)
                for key in scalar_keys:
                    if has_test_set and test_metrics and key in test_metrics:
                        performance_metrics[f"test_{key}"] = test_metrics.get(key)

                # Also expose train/test confusion matrices for UI (especially confusion matrix comparison)
                if train_metrics and 'confusion_matrix' in train_metrics:
                    performance_metrics['train_confusion_matrix'] = train_metrics.get('confusion_matrix')
                if has_test_set and test_metrics and 'confusion_matrix' in test_metrics:
                    performance_metrics['test_confusion_matrix'] = test_metrics.get('confusion_matrix')
            else:  # regression
                scalar_keys = ['mse', 'rmse', 'mae', 'r2', 'mape', 'max_error']
                for key in scalar_keys:
                    if train_metrics and key in train_metrics:
                        performance_metrics[f"train_{key}"] = train_metrics.get(key)
                for key in scalar_keys:
                    if has_test_set and test_metrics and key in test_metrics:
                        performance_metrics[f"test_{key}"] = test_metrics.get(key)
            
            evaluation_results['performance_metrics'] = performance_metrics
            
            # 6. Feature Importance (use sampled data for speed on large datasets)
            feature_importance = self._calculate_feature_importance(
                model, X_train_eval, y_train_eval, X_test_eval, y_test_eval, feature_names, problem_type
            )
            evaluation_results['feature_importance'] = feature_importance
            
            # 7. ROC and PR Curves (classification only)
            # TEST data curves (only if test set exists)
            if has_test_set and problem_type == 'classification' and y_pred_proba_test is not None:
                roc_data_test = self._calculate_roc_curve_data(y_test_eval, y_pred_proba_test)
                pr_data_test = self._calculate_pr_curve_data(y_test_eval, y_pred_proba_test)
                evaluation_results['roc_curve'] = roc_data_test
                evaluation_results['pr_curve'] = pr_data_test

                # 7a. Decile/monotonicity/KS analysis (TEST)
                monotonicity_results = self._build_decile_monotonicity_results(
                    y_test_eval, y_pred_proba_test, y_pred_proba_train=y_pred_proba_train,
                    X_train=X_train_eval, X_test=X_test_eval,
                    sample_weight=sample_weight_test[_test_sample_idx] if (sample_weight_test is not None and _test_sample_idx is not None) else sample_weight_test
                )
                if monotonicity_results:
                    # Store results even if there's an error (so frontend can display it)
                    evaluation_results['monotonicity_results'] = monotonicity_results
            elif not has_test_set:
                self.logger.info("Skipping test ROC/PR curves (no test set)")
                # Calculate monotonicity using TRAIN data when no test set exists
                if problem_type == 'classification' and y_pred_proba_train is not None:
                    self.logger.info("Calculating monotonicity using train data (no test set - active_scope='entire')")
                    try:
                        monotonicity_results = self._build_decile_monotonicity_results(
                            y_train_eval, y_pred_proba_train, y_pred_proba_train=y_pred_proba_train,
                            X_train=X_train_eval, X_test=None,
                            sample_weight=sample_weight_train[_train_sample_idx] if (sample_weight_train is not None and _train_sample_idx is not None) else sample_weight_train
                        )
                        if monotonicity_results:
                            evaluation_results['monotonicity_results'] = monotonicity_results
                            self.logger.info("Monotonicity results calculated successfully using train data")
                    except Exception as e:
                        self.logger.warning(f"Failed to calculate monotonicity using train data: {str(e)}")

            # 7b. ROC Curve (TRAIN data) - used for train/test ROC comparison in UI
            if problem_type == 'classification' and y_pred_proba_train is not None:
                try:
                    roc_data_train = self._calculate_roc_curve_data(y_train_eval, y_pred_proba_train)
                    evaluation_results['roc_curve_train'] = roc_data_train
                except Exception as e:
                    self.logger.warning(f"Failed to calculate train ROC curve: {e}")
            
            # 8. Granular Accuracy Analysis (TEST data)
            # Get column_stats and category_mappings from training results if available
            column_stats = None
            category_mappings_from_file = None
            try:
                models_dir = Path("models")
                training_results_path = models_dir / f"{model_id}_training_results.json"
                if training_results_path.exists():
                    with open(training_results_path, 'r') as f:
                        training_results = json.load(f)
                        column_stats = training_results.get('column_stats', {}) or {}
                        if column_stats:
                            self.logger.info(f"✅ Loaded column_stats from training results: {len(column_stats)} features")
                        else:
                            self.logger.warning(f"⚠️ Training results file exists but column_stats is missing or empty for {model_id}. This may happen if the model was trained before column_stats was added to the codebase.")
                        
                        # Load category_mappings from training results
                        category_mappings_from_file = training_results.get('category_mappings', {}) or {}
                        if category_mappings_from_file:
                            # Convert string keys to int (JSON stores dict keys as strings)
                                category_mappings_from_file = {
                                    feature_name: {
                                        int(k): str(v) for k, v in mapping.items()
                                    }
                                    for feature_name, mapping in category_mappings_from_file.items()
                                }
                                self.logger.info(f"✅ Loaded category_mappings from training results: {len(category_mappings_from_file)} features")
                                self.logger.info(f"   Features with mappings: {list(category_mappings_from_file.keys())}")
                        else:
                            self.logger.warning(f"⚠️ Training results file exists but category_mappings is missing or empty for {model_id}. Will use category_mappings passed as parameter.")
                        
                        # Load X_train_original_info from training results (for train granular accuracy fallback)
                        X_train_original_info_from_file = training_results.get('X_train_original_info', None)
                        if X_train_original_info_from_file:
                            self.logger.info(f"✅ Loaded X_train_original_info from training results")
                            if X_train_original_info_from_file.get('has_home_ownership'):
                                self.logger.info(f"   ✅ home_ownership found in X_train_original_info")
                        else:
                            X_train_original_info_from_file = None
                            self.logger.warning(f"⚠️ X_train_original_info not found in training results for {model_id}")
                else:
                    # Check if file exists with different case or extension
                    import os
                    models_dir_path = Path(models_dir)
                    if models_dir_path.exists():
                        # Try to find file with case-insensitive search
                        found_file = None
                        for file in models_dir_path.glob(f"{model_id}_training_results.*"):
                            if file.suffix.lower() in ['.json', '.jsson']:  # Handle typo in filename
                                found_file = file
                                break
                        
                        if found_file:
                            self.logger.info(f"📄 Found training results file with different name: {found_file.name}")
                            try:
                                with open(found_file, 'r') as f:
                                    training_results = json.load(f)
                                    column_stats = training_results.get('column_stats', {}) or {}
                                    category_mappings_from_file = training_results.get('category_mappings', {}) or {}
                                    X_train_original_info_from_file = training_results.get('X_train_original_info', None)
                                    if column_stats:
                                        self.logger.info(f"✅ Loaded column_stats from alternate file: {len(column_stats)} features")
                                    if category_mappings_from_file:
                                        self.logger.info(f"✅ Loaded category_mappings from alternate file: {len(category_mappings_from_file)} features")
                            except Exception as e:
                                self.logger.warning(f"Failed to load from alternate file {found_file}: {str(e)}")
                                X_train_original_info_from_file = None
                        else:
                            self.logger.warning(f"⚠️ Training results file not found: {training_results_path}. column_stats and category_mappings will be generated on-the-fly if possible. This may happen if the model was trained before these were added to the codebase.")
                            X_train_original_info_from_file = None
                    else:
                        self.logger.warning(f"⚠️ Models directory not found: {models_dir}. column_stats and category_mappings will be generated on-the-fly if possible.")
                        X_train_original_info_from_file = None
            except Exception as e:
                self.logger.warning(f"Failed to load column_stats/category_mappings for {model_id}: {str(e)}")
                import traceback
                self.logger.debug(f"Traceback: {traceback.format_exc()}")
                X_train_original_info_from_file = None
            
            # Use category_mappings from file if available, otherwise use the parameter
            if category_mappings_from_file:
                # Merge with parameter category_mappings (parameter takes precedence if both exist)
                if category_mappings:
                    self.logger.info(f"Merging category_mappings: {len(category_mappings_from_file)} from file, {len(category_mappings)} from parameter")
                    category_mappings = {**category_mappings_from_file, **category_mappings}
                else:
                    category_mappings = category_mappings_from_file
                    self.logger.info(f"Using category_mappings from training results file: {len(category_mappings)} features")
            
            # Fallback: Generate column_stats on-the-fly if missing (for backward compatibility)
            if not column_stats:
                try:
                    from app.services.model_training_auto_training import generate_column_stats
                    
                    # Try to reconstruct original data for column_stats generation
                    # Priority: X_train_original > X_test_original > combined X_train+X_test > X_test
                    df_for_stats = None
                    if X_train_original is not None and len(X_train_original.columns) > 0:
                        # X_train_original has original feature names before preprocessing - BEST option
                        df_for_stats = X_train_original.copy()
                        self.logger.info(f"🔄 Generating column_stats from X_train_original ({df_for_stats.shape[0]} rows, {df_for_stats.shape[1]} cols)")
                    elif X_test_original is not None and len(X_test_original.columns) > 0:
                        # X_test_original has original feature names before preprocessing
                        df_for_stats = X_test_original.copy()
                        self.logger.info(f"🔄 Generating column_stats from X_test_original ({df_for_stats.shape[0]} rows, {df_for_stats.shape[1]} cols)")
                    else:
                        # Fallback: combine train and test data (if test set exists)
                        if X_test is not None:
                            try:
                                df_for_stats = pd.concat([X_train, X_test], axis=0, ignore_index=True)
                                self.logger.info(f"🔄 Generating column_stats from combined X_train+X_test ({df_for_stats.shape[0]} rows, {df_for_stats.shape[1]} cols)")
                            except Exception as e2:
                                self.logger.warning(f"Failed to combine train/test data for column_stats: {str(e2)}")
                                df_for_stats = X_test.copy()
                                if df_for_stats is not None:
                                    self.logger.info(f"🔄 Generating column_stats from X_test only ({df_for_stats.shape[0]} rows, {df_for_stats.shape[1]} cols)")
                        else:
                            # No test set, use train data only
                            df_for_stats = X_train.copy()
                            self.logger.info(f"🔄 Generating column_stats from X_train only (no test set - active_scope='entire') ({df_for_stats.shape[0]} rows, {df_for_stats.shape[1]} cols)")
                    
                    if df_for_stats is not None and len(df_for_stats.columns) > 0:
                        # Generate column_stats for all features in feature_names
                        # Map preprocessed feature names back to original if needed
                        features_to_analyze = feature_names.copy()
                        
                        # If we have preprocessed_columns mapping, try to find original names
                        if preprocessed_columns:
                            # preprocessed_columns format: {original_name: preprocessed_name}
                            # Reverse it to find original names
                            reverse_mapping = {v: k for k, v in preprocessed_columns.items()}
                            features_to_analyze = []
                            for feat in feature_names:
                                if feat in reverse_mapping:
                                    features_to_analyze.append(reverse_mapping[feat])
                                elif feat in df_for_stats.columns:
                                    features_to_analyze.append(feat)
                                else:
                                    # Try to find by case-insensitive match
                                    found = False
                                    for col in df_for_stats.columns:
                                        if col.lower() == feat.lower():
                                            features_to_analyze.append(col)
                                            found = True
                                            break
                                    if not found:
                                        features_to_analyze.append(feat)
                        
                        # Filter to only features that exist in df_for_stats
                        features_to_analyze = [f for f in features_to_analyze if f in df_for_stats.columns]
                        
                        if features_to_analyze:
                            column_stats = generate_column_stats(df_for_stats, features_to_analyze)
                            if column_stats:
                                self.logger.info(f"✅ Generated column_stats on-the-fly for {len(column_stats)} features: {list(column_stats.keys())[:5]}...")
                            else:
                                self.logger.warning(f"⚠️ Failed to generate column_stats for features: {features_to_analyze[:5]}...")
                        else:
                            self.logger.warning(f"⚠️ No matching features found in data for column_stats generation. feature_names: {feature_names[:5]}..., df columns: {list(df_for_stats.columns)[:5]}...")
                except Exception as e:
                    self.logger.warning(f"Failed to generate column_stats on-the-fly: {str(e)}")
                    import traceback
                    self.logger.debug(f"Traceback: {traceback.format_exc()}")
            
            # Fallback: Generate category_mappings on-the-fly if missing (for backward compatibility)
            # This is especially important for categorical features like home_ownership
            if not category_mappings or len(category_mappings) == 0:
                try:
                    # Try to extract category mappings from original data
                    # Use X_train_original first (best), then X_test_original, then combined data
                    df_for_mappings = None
                    if X_train_original is not None and len(X_train_original.columns) > 0:
                        df_for_mappings = X_train_original.copy()
                        self.logger.info(f"🔄 Generating category_mappings from X_train_original")
                    elif X_test_original is not None and len(X_test_original.columns) > 0:
                        df_for_mappings = X_test_original.copy()
                        self.logger.info(f"🔄 Generating category_mappings from X_test_original")
                    else:
                        # Try to combine train and test (if test set exists)
                        if X_test is not None:
                            try:
                                df_for_mappings = pd.concat([X_train, X_test], axis=0, ignore_index=True)
                                self.logger.info(f"🔄 Generating category_mappings from combined data")
                            except:
                                df_for_mappings = X_test.copy()
                        else:
                            # No test set, use train data only
                            df_for_mappings = X_train.copy()
                            self.logger.info(f"🔄 Generating category_mappings from X_train only (no test set - active_scope='entire')")
                    
                    if df_for_mappings is not None and len(df_for_mappings.columns) > 0:
                        # Check column_stats to identify categorical features
                        categorical_features = []
                        if column_stats:
                            categorical_features = [
                                feat for feat, stats in column_stats.items() 
                                if stats.get('variable_type') in ['categorical', 'category']
                            ]
                        
                        # If no column_stats, try to infer from data
                        if not categorical_features:
                            # Check features that are object/string type and have low unique count
                            for feat in feature_names:
                                if feat in df_for_mappings.columns:
                                    col_data = df_for_mappings[feat]
                                    if pd.api.types.is_object_dtype(col_data) or pd.api.types.is_string_dtype(col_data):
                                        unique_count = col_data.nunique()
                                        if unique_count <= 20:  # Likely categorical if <= 20 unique values
                                            categorical_features.append(feat)
                        
                        # Generate mappings for categorical features
                        generated_mappings = {}
                        for feat in categorical_features:
                            if feat in df_for_mappings.columns:
                                col_data = df_for_mappings[feat].dropna()
                                if len(col_data) > 0:
                                    unique_vals = sorted(col_data.unique())
                                    # Create mapping: {index: category_name}
                                    # Note: This assumes the data is in original form (not encoded)
                                    # If the data is already encoded, we'll need to handle it differently
                                    mapping = {i: str(val) for i, val in enumerate(unique_vals)}
                                    generated_mappings[feat] = mapping
                                    self.logger.info(f"✅ Generated category_mapping for {feat}: {len(mapping)} categories - {list(mapping.values())[:5]}...")
                            else:
                                # Try to find original feature name if it's been preprocessed
                                original_feat = None
                                if preprocessed_columns:
                                    # Find original name from preprocessed_columns mapping
                                    for orig_name, preproc_name in preprocessed_columns.items():
                                        if preproc_name == feat or orig_name == feat:
                                            original_feat = orig_name
                                            break
                                
                                if original_feat and original_feat in df_for_mappings.columns:
                                    col_data = df_for_mappings[original_feat].dropna()
                                    if len(col_data) > 0:
                                        unique_vals = sorted(col_data.unique())
                                        mapping = {i: str(val) for i, val in enumerate(unique_vals)}
                                        generated_mappings[feat] = mapping  # Use feat (preprocessed name) as key
                                        self.logger.info(f"✅ Generated category_mapping for {feat} (original: {original_feat}): {len(mapping)} categories")
                        
                        if generated_mappings:
                            # Merge with existing category_mappings (if any)
                            if category_mappings:
                                category_mappings = {**generated_mappings, **category_mappings}
                            else:
                                category_mappings = generated_mappings
                            self.logger.info(f"✅ Generated category_mappings on-the-fly for {len(generated_mappings)} features: {list(generated_mappings.keys())}")
                except Exception as e:
                    self.logger.warning(f"Failed to generate category_mappings on-the-fly: {str(e)}")
                    import traceback
                    self.logger.debug(f"Traceback: {traceback.format_exc()}")
            
            # 8. Granular Accuracy Analysis (TEST data) - only if test set exists
            granular_accuracy_test = []
            if has_test_set:
                # Enhanced logging for test granular accuracy with home_ownership focus
                self.logger.info(f"🔍 Starting TEST granular accuracy calculation...")
                self.logger.info(f"   📋 Parameters check:")
                self.logger.info(f"      - problem_type: {problem_type}")
                self.logger.info(f"      - X_test shape: {X_test.shape if X_test is not None else 'None'}")
                self.logger.info(f"      - y_test length: {len(y_test) if y_test is not None else 'None'}")
                self.logger.info(f"      - y_pred_test length: {len(y_pred_test) if y_pred_test is not None else 'None'}")
                self.logger.info(f"      - feature_names count: {len(feature_names) if feature_names else 0}")
                self.logger.info(f"      - category_mappings: {'Available' if category_mappings else 'None'} ({len(category_mappings) if category_mappings else 0} features)")
                self.logger.info(f"      - column_stats: {'Available' if column_stats else 'None'} ({len(column_stats) if column_stats else 0} features)")
                self.logger.info(f"      - scaler: {'Available' if scaler is not None else 'None'}")
                
                if X_test_original is not None:
                    self.logger.info(f"   X_test_original shape: {X_test_original.shape}, columns: {list(X_test_original.columns)[:10]}")
                    if 'home_ownership' in X_test_original.columns:
                        ho_col = X_test_original['home_ownership']
                        self.logger.info(f"   ✅ home_ownership found in X_test_original! Unique values: {sorted(ho_col.dropna().unique().astype(str))}")
                    else:
                        self.logger.warning(f"   ⚠️ home_ownership NOT found in X_test_original columns: {list(X_test_original.columns)[:10]}")
                else:
                    self.logger.warning(f"   ⚠️ X_test_original is None - test granular accuracy may not work properly for categorical features like home_ownership")
                
                self.logger.info(f"   🚀 Calling _calculate_granular_accuracy for TEST data...")
                try:
                    # Use sampled test data for granular accuracy to avoid OOM on large datasets
                    _X_test_ga = X_test_eval
                    _y_test_ga = y_test_eval
                    _X_test_orig_ga = X_test_original
                    if X_test_original is not None and _test_sample_idx is not None:
                        # Align original data to the same sample indices used above
                        try:
                            _X_test_orig_ga = X_test_original.iloc[_test_sample_idx]
                        except Exception:
                            _X_test_orig_ga = X_test_original
                    granular_accuracy_test = self._calculate_granular_accuracy(
                        _X_test_ga, _y_test_ga, y_pred_test, y_pred_proba_test, feature_names, problem_type, category_mappings,
                        X_test_original=_X_test_orig_ga, scaler=scaler, column_stats=column_stats,
                        preprocessed_columns=preprocessed_columns or {},
                        is_train_data=False  # Explicitly mark as TEST data
                    )
                    self.logger.info(f"   ✅ _calculate_granular_accuracy returned: {len(granular_accuracy_test) if granular_accuracy_test else 0} segments")
                except Exception as e:
                    self.logger.error(f"   ❌ ERROR in _calculate_granular_accuracy: {str(e)}")
                    import traceback
                    self.logger.error(f"   Traceback: {traceback.format_exc()}")
                    granular_accuracy_test = []
                # Add model_id to all TEST granular accuracy segments
                if granular_accuracy_test:
                    for item in granular_accuracy_test:
                        item['model_id'] = model_id
                
                # Log summary for debugging
                if granular_accuracy_test:
                    self.logger.info(f"✅ Granular accuracy (TEST) calculated: {len(granular_accuracy_test)} segments")
                    variables = set(item.get('variable') for item in granular_accuracy_test if item.get('variable'))
                    self.logger.info(f"   Variables with segments: {sorted(list(variables))}")
                    # Check for home_ownership specifically
                    home_ownership_segments = [item for item in granular_accuracy_test if item.get('variable') == 'home_ownership']
                    if home_ownership_segments:
                        self.logger.info(f"   ✅ home_ownership: {len(home_ownership_segments)} segments created")
                    else:
                        self.logger.warning(f"   ⚠️ home_ownership: NO segments found in granular_accuracy_test")
                else:
                    self.logger.warning(f"⚠️ Granular accuracy (TEST) is empty or None")
            else:
                self.logger.info("Skipping test granular accuracy calculation (no test set - active_scope='entire')")
            
            evaluation_results['granular_accuracy'] = granular_accuracy_test  # Keep for backward compatibility
            
            # 8b. Granular Accuracy Analysis (TRAIN data) - for toggle in UI
            granular_accuracy_train = None
            self.logger.info(f"🔍 [TRAIN GRANULAR ACCURACY CHECK] y_pred_train is not None: {y_pred_train is not None}, problem_type: {problem_type}, condition met: {y_pred_train is not None and problem_type == 'classification'}")
            if y_pred_train is not None and problem_type == 'classification':
                try:
                    # CRITICAL FIX: Pass X_train_original instead of None for train granular accuracy
                    # This ensures home_ownership and other categorical features can be properly segmented
                    self.logger.info(f"🔍 Starting TRAIN granular accuracy calculation...")
                    # X_train_original is a parameter to this function - check if it was passed
                    x_train_orig = X_train_original if X_train_original is not None else None
                    self.logger.info(f"   X_train_original parameter: {'Available' if x_train_orig is not None else 'None/Not passed'}")
                    if x_train_orig is not None:
                        self.logger.info(f"   X_train_original shape: {x_train_orig.shape}, columns: {list(x_train_orig.columns)[:10]}")
                        if 'home_ownership' in x_train_orig.columns:
                            ho_col = x_train_orig['home_ownership']
                            self.logger.info(f"   ✅ home_ownership found in X_train_original! Unique values: {sorted(ho_col.dropna().unique().astype(str))}")
                        else:
                            self.logger.warning(f"   ⚠️ home_ownership NOT found in X_train_original columns: {list(x_train_orig.columns)[:10]}")
                    else:
                        self.logger.warning(f"   ⚠️ X_train_original is None - train granular accuracy may not work properly for categorical features like home_ownership")
                    
                    # CRITICAL: Only use TRAIN-ONLY pipeline if X_train_original is available
                    # Without X_train_original, granular accuracy cannot be calculated properly
                    if x_train_orig is not None and len(x_train_orig) > 0:
                        self.logger.info(f"   🚀 Calling TRAIN-ONLY pipeline (_calculate_granular_accuracy_train_only)...")
                        try:
                            # Align X_train_original to the same sample if training data was sampled
                            _x_train_orig_ga = x_train_orig
                            if x_train_orig is not None and _train_sample_idx is not None:
                                try:
                                    _x_train_orig_ga = x_train_orig.iloc[_train_sample_idx]
                                except Exception:
                                    _x_train_orig_ga = x_train_orig
                            # USE SEPARATE TRAIN-ONLY PIPELINE - Does NOT touch test data
                            granular_accuracy_train = self._calculate_granular_accuracy_train_only(
                                X_train=X_train_eval,
                                y_train=y_train_eval,
                                y_pred_train=y_pred_train,
                                y_pred_proba_train=y_pred_proba_train,
                                feature_names=feature_names,
                                problem_type=problem_type,
                                X_train_original=_x_train_orig_ga,
                                category_mappings=category_mappings,
                                column_stats=column_stats,
                                preprocessed_columns=preprocessed_columns or {},
                                model_id=model_id
                            )
                            self.logger.info(f"   ✅ TRAIN-ONLY pipeline returned: {len(granular_accuracy_train) if granular_accuracy_train else 0} segments")
                        except Exception as e:
                            self.logger.error(f"   ❌ ERROR in TRAIN-ONLY pipeline: {str(e)}")
                            import traceback
                            self.logger.error(f"   Traceback: {traceback.format_exc()}")
                            # Don't raise - set to empty list to continue
                            granular_accuracy_train = []
                    else:
                        self.logger.warning(f"   ⚠️ X_train_original not available - cannot calculate train granular accuracy.")
                        self.logger.warning(f"   ⚠️ This usually means X_train_original was not passed from the training service.")
                        self.logger.warning(f"   ⚠️ Train granular accuracy requires original (unprocessed) data to segment categorical features correctly.")
                        granular_accuracy_train = []
                    
                    # Add model_id to all TRAIN granular accuracy segments
                    if granular_accuracy_train:
                        for item in granular_accuracy_train:
                            item['model_id'] = model_id
                    
                    # Log results for home_ownership
                    if granular_accuracy_train:
                        home_ownership_segments = [item for item in granular_accuracy_train if item.get('variable') == 'home_ownership']
                        if home_ownership_segments:
                            self.logger.info(f"   ✅ home_ownership: {len(home_ownership_segments)} segments created in TRAIN data")
                        else:
                            self.logger.warning(f"   ⚠️ home_ownership: NO segments found in TRAIN granular_accuracy_train")
                    
                    evaluation_results['granular_accuracy_train'] = granular_accuracy_train if granular_accuracy_train else []
                except Exception as e:
                    self.logger.error(f"❌ Failed to calculate train granular accuracy: {str(e)}")
                    import traceback
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
                    evaluation_results['granular_accuracy_train'] = []  # Set to empty list instead of None for frontend compatibility
            
            # 9. Error Patterns (classification only, TEST data) - only if test set exists
            if has_test_set and problem_type == 'classification':
                error_patterns = self._analyze_error_patterns(
                    y_test, y_pred_test, y_pred_proba_test
                )
                evaluation_results['error_patterns'] = error_patterns
            else:
                evaluation_results['error_patterns'] = []
            
            # 10. Prediction Confidence Analysis (TEST data) - only if test set exists
            if has_test_set and y_pred_proba_test is not None:
                confidence_analysis = self._analyze_prediction_confidence(
                    y_test, y_pred_test, y_pred_proba_test
                )
                evaluation_results['prediction_confidence'] = confidence_analysis
            else:
                evaluation_results['prediction_confidence'] = []
            
            # 7. SHAP Analysis (only if requested - skip during training for performance)
            # Note: SHAP/PDP are typically calculated on test data, but can use train data if no test set
            waterfall_data = None
            if include_explainability:
                # Import explainability service only when needed
                from app.services.explainability_service import explainability_service
                
                # Use test data if available, otherwise use train data
                shap_X = X_test if has_test_set else X_train
                shap_sample_weight = sample_weight_test if has_test_set else sample_weight_train
                
                if shap_X is not None:
                    try:
                        import shap
                        self.logger.info(f"SHAP library found, calculating SHAP values on {'test' if has_test_set else 'train'} data...")
                        shap_data, waterfall_data = explainability_service.calculate_shap_analysis(
                            model, X_train, shap_X, feature_names, problem_type,
                            sample_weight=shap_sample_weight  # Pass sample weights for weighted SHAP aggregation
                        )
                        if shap_data:
                            evaluation_results['shap_analysis'] = shap_data
                            evaluation_results['waterfall_data'] = waterfall_data
                            self.logger.info("SHAP analysis completed successfully")
                        else:
                            self.logger.warning("SHAP calculation returned None, skipping SHAP analysis")
                            evaluation_results['shap_analysis'] = None
                            evaluation_results['waterfall_data'] = None
                    except ImportError:
                        self.logger.warning("SHAP library not installed. Install with: pip install shap>=0.42.0")
                        self.logger.info("Continuing evaluation without SHAP analysis...")
                        evaluation_results['shap_analysis'] = None
                        evaluation_results['waterfall_data'] = None
                    except Exception as e:
                        self.logger.warning(f"Error calculating SHAP values: {str(e)}")
                        self.logger.info("Continuing evaluation without SHAP analysis...")
                        import traceback
                        self.logger.debug(f"SHAP error traceback: {traceback.format_exc()}")
                        evaluation_results['shap_analysis'] = None
                        evaluation_results['waterfall_data'] = None
                    
                    # 8. Partial Dependence Plot Data (only if requested - skip during training for performance)
                    try:
                        pdp_data = explainability_service.calculate_pdp_analysis(
                            model, shap_X, feature_names, problem_type  # All features, not just top 5
                        )
                        evaluation_results['partial_dependence'] = pdp_data
                    except Exception as e:
                        self.logger.warning(f"Error calculating partial dependence: {str(e)}")
                        evaluation_results['partial_dependence'] = None
                else:
                    self.logger.info("Skipping explainability analysis (no data available)")
                    evaluation_results['shap_analysis'] = None
                    evaluation_results['waterfall_data'] = None
                    evaluation_results['partial_dependence'] = None
            else:
                self.logger.info("Skipping explainability analysis (include_explainability=False) - will be calculated on-demand")
                evaluation_results['shap_analysis'] = None
                evaluation_results['waterfall_data'] = None
                evaluation_results['partial_dependence'] = None
            
            # 9. Monotonicity Analysis - only if test set exists
            if has_test_set:
                monotonicity_analysis = self._analyze_monotonicity(
                    model, X_test, feature_names, problem_type
                )
            else:
                monotonicity_analysis = {}
            evaluation_results['monotonicity_analysis'] = monotonicity_analysis
            
            self.logger.info(f"Comprehensive evaluation completed for model {model_id}")
            return evaluation_results
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive evaluation: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise

    # ------------------------------------------------------------------
    # PHASED EVALUATION - Phase 1 / 2 / 3
    # Each phase is independent and writes its own partial JSON file so
    # the frontend can render each tab as soon as its phase completes,
    # without waiting for the other phases.
    #
    # Phase 1 - Performance (predictions + metrics + ROC/PR + feature importance)
    # Phase 2 - Monotonicity (decile analysis, KS, AUC/Gini)
    # Phase 3 - Granular Accuracy (segment-level accuracy per feature)
    #
    # Predictions are computed once in Phase 1 and cached in
    # _prediction_cache[model_id] so Phase 2 and 3 can reuse them without
    # re-running the model.
    # ------------------------------------------------------------------

    # Class-level prediction cache - keyed by model_id, holds prediction
    # arrays and sampled DataFrames so later phases don't re-run the model.
    _prediction_cache: dict = {}

    def evaluate_phase1_performance(
        self,
        model: Any,
        model_id: str,
        model_name: str,
        X_train: pd.DataFrame,
        X_test: Optional[pd.DataFrame],
        y_train: pd.Series,
        y_test: Optional[pd.Series],
        problem_type: str,
        feature_names: List[str],
        dataset_id: Optional[str] = None,
        active_scope: str = 'entire',
        target_column: Optional[str] = None,
        split_params: Optional[Dict[str, Any]] = None,
        preprocessed_columns: Optional[Dict[str, str]] = None,
        train_indices: Optional[List[int]] = None,
        test_indices: Optional[List[int]] = None,
        category_mappings: Optional[Dict[str, Dict[int, str]]] = None,
        X_test_original: Optional[pd.DataFrame] = None,
        X_train_original: Optional[pd.DataFrame] = None,
        scaler: Optional[Any] = None,
        column_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Phase 1: Performance metrics, ROC/PR curves, feature importance.
        Caches predictions so Phase 2 and 3 can skip re-running the model."""
        try:
            has_test_set = X_test is not None and y_test is not None

            _TRAIN_SAMPLE_CAP = 50_000
            _TEST_SAMPLE_CAP = 50_000

            X_train_eval, y_train_eval = X_train, y_train
            X_test_eval, y_test_eval = X_test, y_test
            _train_sample_idx = None
            _test_sample_idx = None

            if len(X_train) > _TRAIN_SAMPLE_CAP:
                import numpy as _np
                _rng = _np.random.default_rng(42)
                _train_sample_idx = _rng.choice(len(X_train), size=_TRAIN_SAMPLE_CAP, replace=False)
                _train_sample_idx.sort()
                X_train_eval = X_train.iloc[_train_sample_idx]
                y_train_eval = y_train.iloc[_train_sample_idx]
                self.logger.info(f"[Phase1] Large train set - sampling {_TRAIN_SAMPLE_CAP:,} rows for {model_id}")

            if has_test_set and X_test is not None and len(X_test) > _TEST_SAMPLE_CAP:
                import numpy as _np2
                _rng2 = _np2.random.default_rng(42)
                _test_sample_idx = _rng2.choice(len(X_test), size=_TEST_SAMPLE_CAP, replace=False)
                _test_sample_idx.sort()
                X_test_eval = X_test.iloc[_test_sample_idx]
                y_test_eval = y_test.iloc[_test_sample_idx]
                self.logger.info(f"[Phase1] Large test set - sampling {_TEST_SAMPLE_CAP:,} rows for {model_id}")

            # Predictions
            y_pred_test = None
            y_pred_proba_test = None
            if has_test_set:
                y_pred_test = model.predict(X_test_eval)
                if problem_type == 'classification' and hasattr(model, 'predict_proba'):
                    y_pred_proba_test = model.predict_proba(X_test_eval)

            y_pred_train = None
            y_pred_proba_train = None
            try:
                y_pred_train = model.predict(X_train_eval)
                if problem_type == 'classification' and hasattr(model, 'predict_proba'):
                    y_pred_proba_train = model.predict_proba(X_train_eval)
            except Exception as e:
                self.logger.warning(f"[Phase1] Train predictions failed for {model_id}: {e}")

            # Cache predictions for later phases
            ModelEvaluationService._prediction_cache[model_id] = {
                'X_train_eval': X_train_eval,
                'X_test_eval': X_test_eval,
                'y_train_eval': y_train_eval,
                'y_test_eval': y_test_eval,
                'y_pred_test': y_pred_test,
                'y_pred_proba_test': y_pred_proba_test,
                'y_pred_train': y_pred_train,
                'y_pred_proba_train': y_pred_proba_train,
                'has_test_set': has_test_set,
                '_train_sample_idx': _train_sample_idx,
                '_test_sample_idx': _test_sample_idx,
                'X_test_original': X_test_original,
                'X_train_original': X_train_original,
                'category_mappings': category_mappings,
                'column_stats': column_stats,
                'preprocessed_columns': preprocessed_columns,
                'scaler': scaler,
            }

            result: Dict[str, Any] = {
                'model_id': model_id,
                'model_name': model_name,
                'problem_type': problem_type,
                'evaluation_timestamp': datetime.utcnow().isoformat(),
                'dataset_id': dataset_id,
                'active_scope': active_scope,
                'target_column': target_column,
                'split_params': split_params or {'test_size': 0.2, 'random_state': 42, 'stratify': False},
                'preprocessed_columns': preprocessed_columns or {},
                'train_indices': train_indices,
                'test_indices': test_indices,
                'used_features': feature_names,
                '_phase': 1,
                '_phase1_ready': True,
            }

            # Performance metrics
            test_metrics: Dict[str, Any] = {}
            if has_test_set and y_pred_test is not None:
                test_metrics = self._calculate_performance_metrics(y_test_eval, y_pred_test, y_pred_proba_test, problem_type)

            train_metrics: Optional[Dict[str, Any]] = None
            if y_pred_train is not None:
                try:
                    train_metrics = self._calculate_performance_metrics(y_train_eval, y_pred_train, y_pred_proba_train, problem_type)
                except Exception as e:
                    self.logger.warning(f"[Phase1] Train metrics failed for {model_id}: {e}")

            if has_test_set and test_metrics:
                performance_metrics: Dict[str, Any] = dict(test_metrics)
            elif train_metrics:
                performance_metrics = dict(train_metrics)
            else:
                performance_metrics = {}

            if problem_type == 'classification':
                scalar_keys = ['accuracy', 'precision', 'recall', 'f1_score', 'auc_roc', 'auc_pr', 'log_loss']
                for key in scalar_keys:
                    if train_metrics and key in train_metrics:
                        performance_metrics[f"train_{key}"] = train_metrics.get(key)
                    if has_test_set and test_metrics and key in test_metrics:
                        performance_metrics[f"test_{key}"] = test_metrics.get(key)
                if train_metrics and 'confusion_matrix' in train_metrics:
                    performance_metrics['train_confusion_matrix'] = train_metrics.get('confusion_matrix')
                if has_test_set and test_metrics and 'confusion_matrix' in test_metrics:
                    performance_metrics['test_confusion_matrix'] = test_metrics.get('confusion_matrix')
            else:
                scalar_keys = ['mse', 'rmse', 'mae', 'r2', 'mape', 'max_error']
                for key in scalar_keys:
                    if train_metrics and key in train_metrics:
                        performance_metrics[f"train_{key}"] = train_metrics.get(key)
                    if has_test_set and test_metrics and key in test_metrics:
                        performance_metrics[f"test_{key}"] = test_metrics.get(key)

            result['performance_metrics'] = performance_metrics

            # Feature importance
            try:
                result['feature_importance'] = self._calculate_feature_importance(
                    model, X_train_eval, y_train_eval, X_test_eval, y_test_eval, feature_names, problem_type
                )
            except Exception as e:
                self.logger.warning(f"[Phase1] Feature importance failed for {model_id}: {e}")
                result['feature_importance'] = []

            # ROC / PR curves
            if has_test_set and problem_type == 'classification' and y_pred_proba_test is not None:
                try:
                    result['roc_curve'] = self._calculate_roc_curve_data(y_test_eval, y_pred_proba_test)
                    result['pr_curve'] = self._calculate_pr_curve_data(y_test_eval, y_pred_proba_test)
                except Exception as e:
                    self.logger.warning(f"[Phase1] ROC/PR failed for {model_id}: {e}")
            if problem_type == 'classification' and y_pred_proba_train is not None:
                try:
                    result['roc_curve_train'] = self._calculate_roc_curve_data(y_train_eval, y_pred_proba_train)
                    result['pr_curve_train'] = self._calculate_pr_curve_data(y_train_eval, y_pred_proba_train)
                except Exception as e:
                    self.logger.warning(f"[Phase1] Train ROC/PR failed for {model_id}: {e}")

            # Error patterns & confidence
            if has_test_set and problem_type == 'classification':
                try:
                    result['error_patterns'] = self._analyze_error_patterns(y_test_eval, y_pred_test, y_pred_proba_test)
                except Exception:
                    result['error_patterns'] = []
            else:
                result['error_patterns'] = []

            if has_test_set and y_pred_proba_test is not None:
                try:
                    result['prediction_confidence'] = self._analyze_prediction_confidence(y_test_eval, y_pred_test, y_pred_proba_test)
                except Exception:
                    result['prediction_confidence'] = []
            else:
                result['prediction_confidence'] = []

            # Stub out phase 2 & 3 keys so frontend knows they are pending
            result['monotonicity_results'] = None
            result['monotonicity_analysis'] = {}
            result['granular_accuracy'] = None
            result['granular_accuracy_train'] = None
            result['shap_analysis'] = None
            result['waterfall_data'] = None
            result['partial_dependence'] = None

            # Model metadata
            result['model'] = {
                'model_id': model_id,
                'algorithm_name': model_name,
                'dataset_id': dataset_id,
                'target_column': target_column,
                'problem_type': problem_type,
                'active_scope': active_scope,
                'training_date': datetime.utcnow().isoformat(),
            }

            try:
                from app.services.model_training_row_dump_service import model_training_row_dump_service

                model_training_row_dump_service.dump_phase1_row_artifacts(
                    model_id=model_id,
                    algorithm_name=model_name,
                    dataset_id=dataset_id,
                    target_column=target_column,
                    problem_type=problem_type,
                    y_train=y_train_eval,
                    y_pred_train=y_pred_train,
                    y_proba_train=y_pred_proba_train,
                    y_test=y_test_eval,
                    y_pred_test=y_pred_test,
                    y_proba_test=y_pred_proba_test,
                    performance_metrics=performance_metrics,
                )
            except Exception as dump_exc:
                self.logger.warning(f"[Phase1] Row dump failed for {model_id}: {dump_exc}")

            self.logger.info(f"[Phase1] Performance evaluation complete for {model_id}")
            return result
        except Exception as e:
            self.logger.error(f"[Phase1] Failed for {model_id}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise

    def evaluate_phase2_monotonicity(
        self,
        model: Any,
        model_id: str,
        problem_type: str,
        feature_names: List[str],
    ) -> Dict[str, Any]:
        """Phase 2: Monotonicity / decile analysis.
        Reuses cached predictions from Phase 1."""
        try:
            cache = ModelEvaluationService._prediction_cache.get(model_id, {})
            X_test_eval = cache.get('X_test_eval')
            X_train_eval = cache.get('X_train_eval')
            y_test_eval = cache.get('y_test_eval')
            y_train_eval = cache.get('y_train_eval')
            y_pred_proba_test = cache.get('y_pred_proba_test')
            y_pred_proba_train = cache.get('y_pred_proba_train')
            has_test_set = cache.get('has_test_set', False)

            result: Dict[str, Any] = {
                'model_id': model_id,
                '_phase': 2,
                '_phase2_ready': True,
                'monotonicity_results': None,
                'monotonicity_analysis': {},
            }

            if has_test_set and problem_type == 'classification' and y_pred_proba_test is not None:
                try:
                    monotonicity_results = self._build_decile_monotonicity_results(
                        y_test_eval, y_pred_proba_test,
                        y_pred_proba_train=y_pred_proba_train,
                        X_train=X_train_eval, X_test=X_test_eval,
                    )
                    result['monotonicity_results'] = monotonicity_results
                except Exception as e:
                    self.logger.warning(f"[Phase2] Monotonicity failed for {model_id}: {e}")
            elif not has_test_set and problem_type == 'classification' and y_pred_proba_train is not None:
                try:
                    monotonicity_results = self._build_decile_monotonicity_results(
                        y_train_eval, y_pred_proba_train,
                        y_pred_proba_train=y_pred_proba_train,
                        X_train=X_train_eval, X_test=None,
                    )
                    result['monotonicity_results'] = monotonicity_results
                except Exception as e:
                    self.logger.warning(f"[Phase2] Train monotonicity failed for {model_id}: {e}")

            # Legacy monotonicity_analysis key
            if has_test_set and X_test_eval is not None:
                try:
                    result['monotonicity_analysis'] = self._analyze_monotonicity(model, X_test_eval, feature_names, problem_type)
                except Exception as e:
                    self.logger.warning(f"[Phase2] Monotonicity analysis failed for {model_id}: {e}")

            self.logger.info(f"[Phase2] Monotonicity complete for {model_id}")
            return result
        except Exception as e:
            self.logger.error(f"[Phase2] Failed for {model_id}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise

    def evaluate_phase3_granular(
        self,
        model_id: str,
        problem_type: str,
        feature_names: List[str],
    ) -> Dict[str, Any]:
        """Phase 3: Granular accuracy (segment-level accuracy per feature).
        Reuses cached predictions from Phase 1."""
        try:
            cache = ModelEvaluationService._prediction_cache.get(model_id, {})
            X_test_eval = cache.get('X_test_eval')
            X_train_eval = cache.get('X_train_eval')
            y_test_eval = cache.get('y_test_eval')
            y_train_eval = cache.get('y_train_eval')
            y_pred_test = cache.get('y_pred_test')
            y_pred_proba_test = cache.get('y_pred_proba_test')
            y_pred_train = cache.get('y_pred_train')
            y_pred_proba_train = cache.get('y_pred_proba_train')
            has_test_set = cache.get('has_test_set', False)
            _test_sample_idx = cache.get('_test_sample_idx')
            _train_sample_idx = cache.get('_train_sample_idx')
            X_test_original = cache.get('X_test_original')
            X_train_original = cache.get('X_train_original')
            category_mappings = cache.get('category_mappings')
            column_stats = cache.get('column_stats')
            preprocessed_columns = cache.get('preprocessed_columns') or {}
            scaler = cache.get('scaler')

            result: Dict[str, Any] = {
                'model_id': model_id,
                '_phase': 3,
                '_phase3_ready': True,
                'granular_accuracy': [],
                'granular_accuracy_train': [],
            }

            # Align original data to sample indices
            _X_test_orig_ga = X_test_original
            if X_test_original is not None and _test_sample_idx is not None:
                try:
                    _X_test_orig_ga = X_test_original.iloc[_test_sample_idx]
                except Exception:
                    pass

            _x_train_orig_ga = X_train_original
            if X_train_original is not None and _train_sample_idx is not None:
                try:
                    _x_train_orig_ga = X_train_original.iloc[_train_sample_idx]
                except Exception:
                    pass

            # TEST granular accuracy
            if has_test_set and X_test_eval is not None and y_pred_test is not None:
                try:
                    granular_accuracy_test = self._calculate_granular_accuracy(
                        X_test_eval, y_test_eval, y_pred_test, y_pred_proba_test,
                        feature_names, problem_type, category_mappings,
                        X_test_original=_X_test_orig_ga, scaler=scaler,
                        column_stats=column_stats,
                        preprocessed_columns=preprocessed_columns,
                        is_train_data=False,
                    )
                    if granular_accuracy_test:
                        for item in granular_accuracy_test:
                            item['model_id'] = model_id
                    result['granular_accuracy'] = granular_accuracy_test or []
                except Exception as e:
                    self.logger.warning(f"[Phase3] Test granular accuracy failed for {model_id}: {e}")
                    result['granular_accuracy'] = []

            # TRAIN granular accuracy
            if X_train_eval is not None and y_pred_train is not None and _x_train_orig_ga is not None:
                try:
                    granular_accuracy_train = self._calculate_granular_accuracy_train_only(
                        X_train=X_train_eval,
                        y_train=y_train_eval,
                        y_pred_train=y_pred_train,
                        y_pred_proba_train=y_pred_proba_train,
                        feature_names=feature_names,
                        problem_type=problem_type,
                        X_train_original=_x_train_orig_ga,
                        category_mappings=category_mappings,
                        column_stats=column_stats,
                        preprocessed_columns=preprocessed_columns,
                        model_id=model_id,
                    )
                    if granular_accuracy_train:
                        for item in granular_accuracy_train:
                            item['model_id'] = model_id
                    result['granular_accuracy_train'] = granular_accuracy_train or []
                except Exception as e:
                    self.logger.warning(f"[Phase3] Train granular accuracy failed for {model_id}: {e}")
                    result['granular_accuracy_train'] = []

            # Free prediction cache for this model to release memory
            ModelEvaluationService._prediction_cache.pop(model_id, None)
            self.logger.info(f"[Phase3] Granular accuracy complete for {model_id}")
            return result
        except Exception as e:
            self.logger.error(f"[Phase3] Failed for {model_id}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise

    def _calculate_performance_metrics(
        self,
        y_true: pd.Series,
        y_pred: np.ndarray,
        y_pred_proba: Optional[np.ndarray],
        problem_type: str,
        sample_weight: Optional[np.ndarray] = None  # NEW: Sample weights for weighted metrics
    ) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics (with weighted variants when sample_weight provided)"""
        metrics = {}
        
        if problem_type == 'classification':
            # Basic metrics (unweighted - always shown for reference)
            metrics['accuracy'] = float(accuracy_score(y_true, y_pred))
            metrics['precision'] = float(precision_score(y_true, y_pred, average='weighted', zero_division=0))
            metrics['recall'] = float(recall_score(y_true, y_pred, average='weighted', zero_division=0))
            metrics['f1_score'] = float(f1_score(y_true, y_pred, average='weighted', zero_division=0))
            
            # Weighted metrics (primary when sample_weight is available)
            if sample_weight is not None:
                metrics['weighted_accuracy'] = float(accuracy_score(y_true, y_pred, sample_weight=sample_weight))
                metrics['weighted_precision'] = float(precision_score(y_true, y_pred, average='weighted', zero_division=0, sample_weight=sample_weight))
                metrics['weighted_recall'] = float(recall_score(y_true, y_pred, average='weighted', zero_division=0, sample_weight=sample_weight))
                metrics['weighted_f1_score'] = float(f1_score(y_true, y_pred, average='weighted', zero_division=0, sample_weight=sample_weight))
                metrics['has_sample_weights'] = True
            else:
                metrics['has_sample_weights'] = False
            
            # Confusion matrix (always unweighted)
            cm = confusion_matrix(y_true, y_pred)
            metrics['confusion_matrix'] = cm.tolist()
            
            # Class-specific metrics
            unique_classes = sorted(y_true.unique())
            class_metrics = {}
            
            for cls in unique_classes:
                binary_true = (y_true == cls).astype(int)
                binary_pred = (y_pred == cls).astype(int)
                
                class_metrics[str(cls)] = {
                    'precision': float(precision_score(binary_true, binary_pred, zero_division=0)),
                    'recall': float(recall_score(binary_true, binary_pred, zero_division=0)),
                    'f1_score': float(f1_score(binary_true, binary_pred, zero_division=0)),
                    'support': int(np.sum(binary_true))
                }
            
            metrics['class_metrics'] = class_metrics
            
            # Probability-based metrics
            if y_pred_proba is not None:
                try:
                    # AUC-ROC (unweighted)
                    if len(unique_classes) == 2:
                        metrics['auc_roc'] = float(roc_auc_score(y_true, y_pred_proba[:, 1]))
                        metrics['auc_pr'] = float(average_precision_score(y_true, y_pred_proba[:, 1]))
                        # Weighted AUC-ROC
                        if sample_weight is not None:
                            metrics['weighted_auc_roc'] = float(roc_auc_score(y_true, y_pred_proba[:, 1], sample_weight=sample_weight))
                            metrics['weighted_auc_pr'] = float(average_precision_score(y_true, y_pred_proba[:, 1], sample_weight=sample_weight))
                    else:
                        metrics['auc_roc'] = float(roc_auc_score(y_true, y_pred_proba, 
                                                                 multi_class='ovr', average='weighted'))
                        metrics['auc_pr'] = float(average_precision_score(y_true, y_pred_proba, average='weighted'))
                        # Weighted AUC-ROC for multiclass
                        if sample_weight is not None:
                            metrics['weighted_auc_roc'] = float(roc_auc_score(y_true, y_pred_proba, 
                                                                              multi_class='ovr', average='weighted',
                                                                              sample_weight=sample_weight))
                    
                    # Log loss (unweighted)
                    metrics['log_loss'] = float(log_loss(y_true, y_pred_proba))
                    # Weighted log loss
                    if sample_weight is not None:
                        metrics['weighted_log_loss'] = float(log_loss(y_true, y_pred_proba, sample_weight=sample_weight))
                except Exception as e:
                    self.logger.warning(f"Error calculating probability-based metrics: {str(e)}")
                    metrics['auc_roc'] = None
                    metrics['auc_pr'] = None
                    metrics['log_loss'] = None
            else:
                metrics['auc_roc'] = None
                metrics['auc_pr'] = None
                metrics['log_loss'] = None
        
        else:  # regression
            # Unweighted metrics
            metrics['mse'] = float(mean_squared_error(y_true, y_pred))
            metrics['rmse'] = float(np.sqrt(mean_squared_error(y_true, y_pred)))
            metrics['mae'] = float(mean_absolute_error(y_true, y_pred))
            metrics['r2'] = float(r2_score(y_true, y_pred))
            
            # Weighted regression metrics
            if sample_weight is not None:
                metrics['weighted_mse'] = float(mean_squared_error(y_true, y_pred, sample_weight=sample_weight))
                metrics['weighted_rmse'] = float(np.sqrt(mean_squared_error(y_true, y_pred, sample_weight=sample_weight)))
                metrics['weighted_mae'] = float(mean_absolute_error(y_true, y_pred, sample_weight=sample_weight))
                metrics['weighted_r2'] = float(r2_score(y_true, y_pred, sample_weight=sample_weight))
                metrics['has_sample_weights'] = True
            else:
                metrics['has_sample_weights'] = False
            
            # Additional regression metrics (unweighted)
            metrics['mape'] = float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100) if not (y_true == 0).any() else None
            metrics['max_error'] = float(np.max(np.abs(y_true - y_pred)))
        
        return metrics
    
    def _calculate_feature_importance(
        self,
        model: Any,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        feature_names: List[str],
        problem_type: str
    ) -> List[Dict[str, Any]]:
        """Calculate feature importance using multiple methods"""
        importance_data = []
        
        try:
            # Method 1: Model-specific importance (gain/weight)
            gain_importance = self._get_model_feature_importance(model, feature_names)
            
            # Method 2: Permutation importance (use test set if available, otherwise use train set)
            # OPTIMIZATION: Reduced n_repeats from 10 to 5 for faster computation with minimal accuracy loss
            perm_importance = np.zeros(len(feature_names))
            n_perm_repeats = 5  # Reduced from 10 for better latency
            if X_test is not None and y_test is not None:
                try:
                    perm_result = permutation_importance(
                        model, X_test, y_test, n_repeats=n_perm_repeats, random_state=42, n_jobs=-1
                    )
                    perm_importance = perm_result.importances_mean
                except Exception as e:
                    self.logger.warning(f"Error calculating permutation importance on test set: {str(e)}")
                    # Fallback to train set if test set fails
                    try:
                        perm_result = permutation_importance(
                            model, X_train, y_train, n_repeats=n_perm_repeats, random_state=42, n_jobs=-1
                        )
                        perm_importance = perm_result.importances_mean
                        self.logger.info("Using train set for permutation importance (test set unavailable)")
                    except Exception as e2:
                        self.logger.warning(f"Error calculating permutation importance on train set: {str(e2)}")
                        perm_importance = np.zeros(len(feature_names))
            else:
                # No test set available, use train set
                try:
                    perm_result = permutation_importance(
                        model, X_train, y_train, n_repeats=n_perm_repeats, random_state=42, n_jobs=-1
                    )
                    perm_importance = perm_result.importances_mean
                    self.logger.info("Using train set for permutation importance (no test set - active_scope='entire')")
                except Exception as e:
                    self.logger.warning(f"Error calculating permutation importance: {str(e)}")
                    perm_importance = np.zeros(len(feature_names))
            
            # Normalize importances
            gain_importance_norm = self._normalize_importance(gain_importance)
            perm_importance_norm = self._normalize_importance(perm_importance)
            
            # Combine and rank
            for idx, feature in enumerate(feature_names):
                importance_data.append({
                    'feature_name': feature,
                    'gain_importance': float(gain_importance_norm[idx]),
                    'permutation_importance': float(perm_importance_norm[idx]),
                    'shap_importance': 0.0,  # Will be updated if SHAP is available
                    'rank': 0  # Will be calculated after sorting
                })
            
            # Calculate average importance for ranking
            for item in importance_data:
                item['avg_importance'] = (
                    item['gain_importance'] + item['permutation_importance']
                ) / 2
            
            # Sort by average importance and assign ranks
            importance_data.sort(key=lambda x: x['avg_importance'], reverse=True)
            for rank, item in enumerate(importance_data, 1):
                item['rank'] = rank
            
        except Exception as e:
            self.logger.error(f"Error calculating feature importance: {str(e)}")
            # Return default values
            importance_data = [
                {
                    'feature_name': feature,
                    'gain_importance': 0.0,
                    'permutation_importance': 0.0,
                    'shap_importance': 0.0,
                    'rank': idx + 1
                }
                for idx, feature in enumerate(feature_names)
            ]
        
        return importance_data
    
    def _get_model_feature_importance(self, model: Any, feature_names: List[str]) -> np.ndarray:
        """Extract feature importance from model"""
        try:
            if hasattr(model, 'feature_importances_'):
                return model.feature_importances_
            elif hasattr(model, 'coef_'):
                # For linear models, use absolute coefficient values
                coef = model.coef_
                if len(coef.shape) > 1:  # Multi-class
                    return np.abs(coef).mean(axis=0)
                return np.abs(coef)
            else:
                return np.zeros(len(feature_names))
        except Exception:
            return np.zeros(len(feature_names))
    
    def _normalize_importance(self, importance: np.ndarray) -> np.ndarray:
        """Normalize importance values to 0-1 range"""
        if importance.sum() == 0:
            return importance
        return importance / importance.sum()
    
    def _calculate_roc_curve_data(
        self,
        y_true: pd.Series,
        y_pred_proba: np.ndarray
    ) -> Dict[str, Any]:
        """Calculate ROC curve data"""
        try:
            unique_classes = sorted(y_true.unique())
            
            if len(unique_classes) == 2:
                # Binary classification
                fpr, tpr, thresholds = roc_curve(y_true, y_pred_proba[:, 1])
                auc = roc_auc_score(y_true, y_pred_proba[:, 1])
                
                return {
                    'fpr': fpr.tolist(),
                    'tpr': tpr.tolist(),
                    'thresholds': thresholds.tolist(),
                    'auc': float(auc)
                }
            else:
                # Multi-class - calculate for each class
                roc_data = {}
                for idx, cls in enumerate(unique_classes):
                    binary_true = (y_true == cls).astype(int)
                    fpr, tpr, thresholds = roc_curve(binary_true, y_pred_proba[:, idx])
                    auc = roc_auc_score(binary_true, y_pred_proba[:, idx])
                    
                    roc_data[str(cls)] = {
                        'fpr': fpr.tolist(),
                        'tpr': tpr.tolist(),
                        'thresholds': thresholds.tolist(),
                        'auc': float(auc)
                    }
                
                return roc_data
        except Exception as e:
            self.logger.error(f"Error calculating ROC curve: {str(e)}")
            return {}
    
    def _calculate_pr_curve_data(
        self,
        y_true: pd.Series,
        y_pred_proba: np.ndarray
    ) -> Dict[str, Any]:
        """Calculate Precision-Recall curve data"""
        try:
            unique_classes = sorted(y_true.unique())
            
            if len(unique_classes) == 2:
                # Binary classification
                precision, recall, thresholds = precision_recall_curve(y_true, y_pred_proba[:, 1])
                avg_precision = average_precision_score(y_true, y_pred_proba[:, 1])
                
                return {
                    'precision': precision.tolist(),
                    'recall': recall.tolist(),
                    'thresholds': thresholds.tolist(),
                    'avg_precision': float(avg_precision)
                }
            else:
                # Multi-class
                pr_data = {}
                for idx, cls in enumerate(unique_classes):
                    binary_true = (y_true == cls).astype(int)
                    precision, recall, thresholds = precision_recall_curve(
                        binary_true, y_pred_proba[:, idx]
                    )
                    avg_precision = average_precision_score(binary_true, y_pred_proba[:, idx])
                    
                    pr_data[str(cls)] = {
                        'precision': precision.tolist(),
                        'recall': recall.tolist(),
                        'thresholds': thresholds.tolist(),
                        'avg_precision': float(avg_precision)
                    }
                
                return pr_data
        except Exception as e:
            self.logger.error(f"Error calculating PR curve: {str(e)}")
            return {}
    
    def _generate_train_data_excel(
        self,
        X_train_original: pd.DataFrame,
        X_train: pd.DataFrame,
        category_mappings: Optional[Dict[str, Dict[int, str]]] = None,
        column_stats: Optional[Dict[str, Any]] = None,
        preprocessed_columns: Optional[Dict[str, str]] = None,
        feature_names: Optional[List[str]] = None,
        model_id: str = None,
        output_dir: str = "backend/data",
        return_dataframe: bool = False
    ) -> str:
        """
        Generate Excel file with original vs decoded data for train data segmentation.
        This Excel file will be used as reference for train-only segmentation pipeline.
        
        Args:
            return_dataframe: If True, returns tuple (path, DataFrame) for in-memory usage
        
        Returns:
            Path to the generated Excel file, or tuple (path, DataFrame) if return_dataframe=True
        """
        try:
            import pandas as pd
            from pathlib import Path
            import os
            
            self.logger.info(f"📊 Generating train data Excel file for model: {model_id}")
            
            # Create output directory if it doesn't exist
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Excel file path
            excel_filename = f"{model_id}_train_data_reference.xlsx" if model_id else "train_data_reference.xlsx"
            excel_path = output_path / excel_filename
            
            # Prepare data for Excel
            excel_data = []
            
            # Process each feature - only include features that are in feature_names or are relevant
            features_to_process = []
            if feature_names:
                # Only process features that are in feature_names or their original names
                for feature in X_train_original.columns:
                    # Check if feature is in feature_names or if it's the original name of a preprocessed feature
                    if feature in feature_names:
                        features_to_process.append(feature)
                    elif preprocessed_columns:
                        # Check if this is the original name of a preprocessed feature
                        # preprocessed_columns format: {original_name: preprocessed_name}
                        if feature in preprocessed_columns.keys():
                            # This is an original feature name that was preprocessed
                            features_to_process.append(feature)
                        elif feature in preprocessed_columns.values():
                            # This is a preprocessed name, find the original
                            for orig_name, preproc_name in preprocessed_columns.items():
                                if preproc_name == feature:
                                    # Use original name instead
                                    if orig_name not in features_to_process:
                                        features_to_process.append(orig_name)
                                    break
                    # CRITICAL: Always include home_ownership if it exists in X_train_original
                    if 'home_ownership' in feature.lower() and feature not in features_to_process:
                        features_to_process.append(feature)
            else:
                # If no feature_names provided, process all features
                features_to_process = list(X_train_original.columns)
            
            # CRITICAL: Ensure home_ownership is always included if it exists
            if 'home_ownership' in X_train_original.columns and 'home_ownership' not in features_to_process:
                features_to_process.append('home_ownership')
                self.logger.info(f"   ✅ Added 'home_ownership' to features_to_process (was missing)")
            
            self.logger.info(f"   Processing {len(features_to_process)} features for Excel file")
            
            # Process each feature
            for feature in features_to_process:
                # Get original values (not encoded)
                original_values = X_train_original[feature]
                
                # Try to find decoded/encoded values from X_train
                decoded_values = None
                feature_name_in_train = feature
                
                # Check if feature is preprocessed
                if preprocessed_columns:
                    for orig_name, preproc_name in preprocessed_columns.items():
                        if orig_name == feature:
                            feature_name_in_train = preproc_name
                            break
                
                # Get decoded values from X_train if available
                if feature_name_in_train in X_train.columns:
                    decoded_values = X_train[feature_name_in_train]
                else:
                    # Try to find by removing common suffixes
                    for suffix in ['_le_auto', '_le_manual', '_le_model', '_transform_OHE']:
                        if feature_name_in_train.endswith(suffix):
                            potential_name = feature_name_in_train[:-len(suffix)]
                            if potential_name in X_train.columns:
                                decoded_values = X_train[potential_name]
                                break
                
                # Get variable type from column_stats
                variable_type = "unknown"
                if column_stats:
                    if feature in column_stats:
                        variable_type = column_stats[feature].get('variable_type', 'unknown')
                    else:
                        # Try case-insensitive match
                        for key in column_stats.keys():
                            if key.lower() == feature.lower():
                                variable_type = column_stats[key].get('variable_type', 'unknown')
                                break
                
                # If still unknown, infer from data
                if variable_type == "unknown":
                    if pd.api.types.is_numeric_dtype(original_values):
                        # Check if it's categorical (low cardinality) or continuous
                        unique_count = original_values.nunique()
                        if unique_count <= 20 and unique_count > 0:
                            variable_type = "categorical"
                        else:
                            variable_type = "continuous"
                    elif pd.api.types.is_string_dtype(original_values) or pd.api.types.is_object_dtype(original_values):
                        variable_type = "categorical"
                    else:
                        variable_type = "continuous"
                
                # Get category count for categorical features
                num_categories = 0
                if variable_type == "categorical":
                    num_categories = original_values.nunique()
                    
                    # Create row for each category
                    unique_categories = sorted(original_values.dropna().unique().astype(str))
                    for category in unique_categories:
                        # Find the encoded value for this category (numeric value from X_train)
                        encoded_value_str = "N/A"  # Default if not found
                        
                        if decoded_values is not None:
                            # Try to find the encoded value for this category
                            # Create a mask for rows where original value equals this category
                            category_mask = original_values.astype(str) == category
                            
                            # Get corresponding encoded values from X_train
                            if len(category_mask) == len(decoded_values):
                                # Align indices
                                if not category_mask.index.equals(decoded_values.index):
                                    category_mask = category_mask.reindex(decoded_values.index, fill_value=False)
                                
                                encoded_vals = decoded_values[category_mask].dropna().unique()
                                if len(encoded_vals) > 0:
                                    # Get the most common encoded value for this category
                                    encoded_value_str = str(encoded_vals[0])
                                    if len(encoded_vals) > 1:
                                        # Multiple encoded values - show the most common one
                                        from collections import Counter
                                        most_common = Counter(encoded_vals).most_common(1)[0][0]
                                        encoded_value_str = str(most_common)
                        elif category_mappings:
                            # Try to find encoded value from category_mappings
                            # Check both feature name and preprocessed name
                            mapping = None
                            if feature in category_mappings:
                                mapping = category_mappings[feature]
                            elif preprocessed_columns:
                                # Try to find via preprocessed name
                                for orig_name, preproc_name in preprocessed_columns.items():
                                    if orig_name == feature and preproc_name in category_mappings:
                                        mapping = category_mappings[preproc_name]
                                        break
                            
                            if mapping:
                                # Reverse lookup: find encoded value for this category
                                # category_mappings format: {encoded_value: original_name}
                                for encoded_val, orig_val in mapping.items():
                                    if str(orig_val) == category:
                                        encoded_value_str = str(encoded_val)
                                        break
                        
                        # CRITICAL: Use original feature name for Variable column (not preprocessed name)
                        # This ensures home_ownership is always 'home_ownership' in Excel, not 'home_ownership_le_auto'
                        variable_name_for_excel = feature
                        
                        # If feature was preprocessed, use the original name from preprocessed_columns
                        if preprocessed_columns:
                            for orig_name, preproc_name in preprocessed_columns.items():
                                if preproc_name == feature or feature == preproc_name:
                                    variable_name_for_excel = orig_name
                                    break
                        
                        # CRITICAL: For home_ownership, always use 'home_ownership' as variable name
                        if 'home_ownership' in feature.lower():
                            variable_name_for_excel = 'home_ownership'
                        
                        # Create row with Variable, Original_Value, and {variable_name}_ede column
                        row_data = {
                            'Variable': variable_name_for_excel,  # Use original name, not preprocessed
                            'Variable_Type': variable_type,
                            'Original_Value': category,
                            f'{variable_name_for_excel}_ede': encoded_value_str,  # Encoded numeric value from X_train (e.g., 0, 1, 2, 3)
                            'Category_Index': unique_categories.index(category),
                            'Num_Categories': num_categories,
                            'Segment_Number': unique_categories.index(category) + 1
                        }
                        excel_data.append(row_data)
                else:
                    # For continuous, create one row
                    # CRITICAL: Use original feature name for Variable column (not preprocessed name)
                    variable_name_for_excel = feature
                    if preprocessed_columns:
                        for orig_name, preproc_name in preprocessed_columns.items():
                            if preproc_name == feature or feature == preproc_name:
                                variable_name_for_excel = orig_name
                                break
                    
                    # CRITICAL: For home_ownership, always use 'home_ownership' as variable name
                    if 'home_ownership' in feature.lower():
                        variable_name_for_excel = 'home_ownership'
                    
                    row_data = {
                        'Variable': variable_name_for_excel,  # Use original name, not preprocessed
                        'Variable_Type': variable_type,
                        'Original_Value': f"{original_values.min()} to {original_values.max()}",
                        f'{variable_name_for_excel}_ede': f"{decoded_values.min()} to {decoded_values.max()}" if decoded_values is not None else "N/A",
                        'Category_Index': 0,
                        'Num_Categories': 0,
                        'Segment_Number': 0
                    }
                    excel_data.append(row_data)
            
            # Create DataFrame
            df_excel = pd.DataFrame(excel_data)
            
            # OPTIMIZATION: Only write to Excel file if not returning DataFrame directly
            # This saves significant I/O time for in-memory processing
            if not return_dataframe:
                df_excel.to_excel(excel_path, index=False, engine='openpyxl')
                self.logger.info(f"✅ Generated train data Excel file: {excel_path}")
            else:
                self.logger.info(f"✅ Generated train data in-memory (skipped Excel I/O for performance)")
            
            self.logger.info(f"   Total rows: {len(df_excel)}")
            self.logger.info(f"   Variables: {df_excel['Variable'].nunique()}")
            
            # Log home_ownership data if present
            if 'home_ownership' in df_excel['Variable'].values:
                ho_data = df_excel[df_excel['Variable'] == 'home_ownership']
                self.logger.info(f"   ✅ home_ownership in Excel: {len(ho_data)} rows")
                self.logger.info(f"      Categories: {ho_data['Original_Value'].tolist()}")
                self.logger.info(f"      Segment numbers: {ho_data['Segment_Number'].tolist()}")
            else:
                # Check case-insensitive
                var_lower = df_excel['Variable'].str.lower()
                if 'home_ownership' in var_lower.values:
                    ho_var = df_excel[var_lower == 'home_ownership']['Variable'].iloc[0]
                    ho_data = df_excel[df_excel['Variable'] == ho_var]
                    self.logger.info(f"   ✅ home_ownership found as '{ho_var}' in Excel: {len(ho_data)} rows")
                else:
                    self.logger.warning(f"   ⚠️ home_ownership NOT in Excel variables: {df_excel['Variable'].unique()[:10]}")
            
            # OPTIMIZATION: Return DataFrame directly for in-memory processing
            if return_dataframe:
                return str(excel_path), df_excel
            return str(excel_path)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to generate train data Excel file: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _calculate_granular_accuracy_train_only(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        y_pred_train: np.ndarray,
        y_pred_proba_train: Optional[np.ndarray],
        feature_names: List[str],
        problem_type: str,
        X_train_original: Optional[pd.DataFrame] = None,
        category_mappings: Optional[Dict[str, Dict[int, str]]] = None,
        column_stats: Optional[Dict[str, Any]] = None,
        preprocessed_columns: Optional[Dict[str, str]] = None,
        model_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        SEPARATE PIPELINE FOR TRAIN DATA ONLY - Uses Excel file reference.
        This function is ONLY called for train data and does NOT affect test data.
        
        Creates segments based on:
        1. Excel file with original vs decoded data
        2. Variable type from Column Details table
        3. Number of categories = number of segments for categorical features
        """
        try:
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
            import pandas as pd
            import numpy as np
            
            # OPTIMIZATION: Define batch metric calculation helper to reduce sklearn overhead
            def _compute_segment_metrics(y_true, y_pred_seg):
                """Compute all metrics for a segment in one pass - reduces sklearn call overhead"""
                acc = accuracy_score(y_true, y_pred_seg)
                prec = precision_score(y_true, y_pred_seg, average='weighted', zero_division=0)
                rec = recall_score(y_true, y_pred_seg, average='weighted', zero_division=0)
                f1 = f1_score(y_true, y_pred_seg, average='weighted', zero_division=0)
                cm = confusion_matrix(y_true, y_pred_seg)
                return acc, prec, rec, f1, cm
            
            self.logger.info(f"🚀 [TRAIN-ONLY PIPELINE] Starting train granular accuracy calculation for model: {model_id}")
            
            # Step 1: Generate reference data - OPTIMIZATION: Use in-memory DataFrame to avoid Excel I/O
            result = self._generate_train_data_excel(
                X_train_original=X_train_original,
                X_train=X_train,
                category_mappings=category_mappings,
                column_stats=column_stats,
                preprocessed_columns=preprocessed_columns,
                feature_names=feature_names,
                model_id=model_id,
                return_dataframe=True  # OPTIMIZATION: Skip Excel file I/O
            )
            
            # Step 2: Use in-memory DataFrame - STRICTLY USE THIS TABLE FOR ALL SEGMENTATION
            excel_path, df_excel = result
            self.logger.info(f"✅ Using in-memory reference table: {len(df_excel)} rows, {df_excel['Variable'].nunique()} variables")
            self.logger.info(f"   Excel columns: {list(df_excel.columns)}")
            
            # Log home_ownership data if present
            if 'home_ownership' in df_excel['Variable'].values:
                ho_rows = df_excel[df_excel['Variable'] == 'home_ownership']
                self.logger.info(f"   🔍 home_ownership found in Excel table: {len(ho_rows)} rows")
                self.logger.info(f"   home_ownership categories: {ho_rows['Original_Value'].tolist()}")
                self.logger.info(f"   home_ownership segment numbers: {ho_rows['Segment_Number'].tolist()}")
            else:
                # Check case-insensitive
                var_lower = df_excel['Variable'].str.lower()
                if 'home_ownership' in var_lower.values:
                    ho_var = df_excel[var_lower == 'home_ownership']['Variable'].iloc[0]
                    ho_rows = df_excel[df_excel['Variable'] == ho_var]
                    self.logger.info(f"   🔍 home_ownership found as '{ho_var}' in Excel table: {len(ho_rows)} rows")
                else:
                    self.logger.warning(f"   ⚠️ home_ownership NOT found in Excel table variables: {df_excel['Variable'].unique()[:10]}")
            
            # Step 3: STRICTLY USE EXCEL TABLE DATA - Create segments based ONLY on Excel table rows
            granular_data = []
            processed_continuous_vars = set()  # Track processed continuous variables to avoid duplicates
            
            # OPTIMIZATION: Pre-compute column name mappings once (instead of searching for each row)
            # This avoids O(n*m) lookups where n=rows in Excel, m=columns in X_train_original
            _column_name_cache = {}
            _lowercase_columns = {col.lower(): col for col in X_train_original.columns}
            for var in df_excel['Variable'].unique():
                var_str = str(var)
                if var_str in X_train_original.columns:
                    _column_name_cache[var_str] = var_str
                elif var_str.lower() in _lowercase_columns:
                    _column_name_cache[var_str] = _lowercase_columns[var_str.lower()]
                elif 'home_ownership' in var_str.lower():
                    for col in X_train_original.columns:
                        if 'home_ownership' in col.lower():
                            _column_name_cache[var_str] = col
                            break
            
            # OPTIMIZATION: Pre-convert categorical columns to strings once
            _original_values_str_cache = {}
            for col in X_train_original.columns:
                if X_train_original[col].dtype == 'object' or X_train_original[col].nunique() < 50:
                    _original_values_str_cache[col] = X_train_original[col].astype(str)
            
            self.logger.info(f"✅ Pre-computed {len(_column_name_cache)} column mappings and {len(_original_values_str_cache)} string conversions")
            
            # OPTIMIZATION: Use itertuples() instead of iterrows() - much faster
            for row in df_excel.itertuples(index=True):
                idx = row.Index
                variable = str(row.Variable)
                variable_type = str(row.Variable_Type)
                original_value = str(row.Original_Value)
                segment_num = int(row.Segment_Number)
                num_categories = int(row.Num_Categories)
                
                # Skip continuous variables that are already processed
                if variable_type == "continuous" and variable in processed_continuous_vars:
                    continue
                
                # Skip if segment number is 0 (usually for continuous variables with single row)
                if segment_num == 0 and variable_type == "continuous":
                    # For continuous, we'll handle it in the elif block below
                    pass
                
                self.logger.debug(f"📊 Processing Excel row {idx}: Variable='{variable}', Type='{variable_type}', Original_Value='{original_value}', Segment={segment_num}")
                
                # OPTIMIZATION: Use pre-computed column name mapping
                actual_column_name = _column_name_cache.get(variable)
                
                if actual_column_name is None:
                    self.logger.warning(f"   ⚠️ Variable '{variable}' from Excel table not found in X_train_original columns: {list(X_train_original.columns)[:10]}, skipping row {idx}")
                    continue
                
                # Get original values from X_train_original for masking
                original_values = X_train_original[actual_column_name]
                
                if variable_type == "categorical":
                    # STRICTLY USE Excel table: Create segment for this specific Original_Value from Excel
                    # OPTIMIZATION: Use pre-cached string conversion if available
                    original_values_str = _original_values_str_cache.get(actual_column_name)
                    if original_values_str is None:
                        original_values_str = original_values.astype(str)
                    
                    # Log for home_ownership debugging
                    if 'home_ownership' in variable.lower():
                        unique_vals = sorted(original_values_str.dropna().unique())
                        self.logger.info(f"   🔍 home_ownership DEBUG: Excel Original_Value='{original_value}', Actual unique values in data: {unique_vals}")
                        self.logger.info(f"   🔍 home_ownership DEBUG: Total rows in data: {len(original_values_str)}, Non-null: {original_values_str.notna().sum()}")
                    
                    # CRITICAL: Match Original_Value with case-insensitive and whitespace-tolerant comparison
                    # Excel might have different formatting than actual data
                    original_value_clean = str(original_value).strip()
                    mask = original_values_str.str.strip().str.lower() == original_value_clean.lower()
                    
                    # If no match with case-insensitive, try exact match
                    if mask.sum() == 0:
                        mask = original_values_str.str.strip() == original_value_clean
                        if mask.sum() == 0:
                            # Try without strip
                            mask = original_values_str == original_value
                    
                    # Log match result for home_ownership
                    if 'home_ownership' in variable.lower():
                        match_count = int(mask.sum())
                        self.logger.info(f"   🔍 home_ownership DEBUG: Matching '{original_value_clean}': found {match_count} matches")
                        if match_count == 0:
                            # Try to find similar values
                            similar_vals = [v for v in unique_vals if original_value_clean.lower() in str(v).lower() or str(v).lower() in original_value_clean.lower()]
                            if similar_vals:
                                self.logger.warning(f"   ⚠️ No exact match for '{original_value_clean}', but found similar values: {similar_vals}")
                    
                    # Align mask with y_train indices
                    if not mask.index.equals(y_train.index):
                        mask = mask.reindex(y_train.index, fill_value=False)
                    
                    sample_count = int(mask.sum())
                    
                    # Enhanced logging for home_ownership
                    if 'home_ownership' in variable.lower():
                        self.logger.info(f"   🔍 home_ownership DEBUG: Segment {segment_num} for '{original_value}': sample_count={sample_count}")
                        if sample_count < 2:
                            self.logger.warning(f"   ⚠️ home_ownership Segment {segment_num} SKIPPED: only {sample_count} samples for '{original_value}'")
                            # Check if the value exists at all
                            value_exists = (original_values_str == original_value).any()
                            self.logger.warning(f"   ⚠️ Value '{original_value}' exists in data: {value_exists}")
                    
                    if sample_count < 2:
                        self.logger.debug(f"   Skipping Excel row {idx} (Segment {segment_num}): only {sample_count} samples for '{original_value}'")
                        continue
                    
                    try:
                        # Calculate metrics using masked data
                        y_train_segment = y_train[mask]
                        y_pred_segment = y_pred_train[mask] if isinstance(y_pred_train, (pd.Series, np.ndarray)) else np.array(y_pred_train)[mask.values if hasattr(mask, 'values') else mask]
                        
                        if len(y_train_segment) < 2:
                            continue
                        
                        # OPTIMIZATION: Use batch metric calculation helper
                        segment_accuracy, segment_precision, segment_recall, segment_f1, segment_cm = _compute_segment_metrics(y_train_segment, y_pred_segment)
                        
                        # Create segment label using Excel table data
                        category_str = original_value
                        if len(category_str) > 30:
                            category_str = category_str[:27] + "..."
                        
                        segment_label = f"Segment {segment_num} ({category_str})"
                        
                        # CRITICAL: For home_ownership, always use 'home_ownership' as variable name
                        # This ensures the UI can find segments even if Excel has different name
                        variable_name_for_segment = 'home_ownership' if 'home_ownership' in variable.lower() else variable
                        
                        granular_data.append({
                            'variable': variable_name_for_segment,  # Use 'home_ownership' for UI matching
                            'segment': segment_label,  # Using Segment_Number from Excel
                            'granularity_level': f'{num_categories}_segments',  # From Excel table
                            'accuracy': float(segment_accuracy),
                            'precision': float(segment_precision),
                            'recall': float(segment_recall),
                            'f1_score': float(segment_f1),
                            'sample_count': sample_count,
                            'confusion_matrix': segment_cm.tolist(),
                            'category_value': original_value,  # From Excel table Original_Value
                            'is_continuous': False
                        })
                        
                        self.logger.info(f"   ✅ Created segment {segment_num} from Excel table for '{variable}' (variable_name='{variable_name_for_segment}'): '{original_value}' ({sample_count} samples)")
                        
                    except Exception as e:
                        self.logger.warning(f"   Error creating segment from Excel row {idx} for {variable}={original_value}: {str(e)}")
                
                elif variable_type == "continuous":
                    # For continuous variables, Excel table has one row with range
                    # Parse the range from Original_Value (format: "min to max")
                    try:
                        if " to " in original_value:
                            range_parts = original_value.split(" to ")
                            min_val = float(range_parts[0])
                            max_val = float(range_parts[1])
                            
                            # Create 5 bins from the range in Excel table
                            num_segments = 5
                            if min_val == max_val:
                                bin_edges = np.linspace(min_val - 0.5, max_val + 0.5, num_segments + 1)
                            else:
                                bin_edges = np.linspace(min_val, max_val, num_segments + 1)
                            
                            for segment_idx in range(num_segments):
                                seg_min = float(bin_edges[segment_idx])
                                seg_max = float(bin_edges[segment_idx + 1])
                                
                                # Create mask using original values
                                mask = (original_values >= seg_min) & (original_values < seg_max)
                                if segment_idx == num_segments - 1:  # Include max value in last segment
                                    mask = (original_values >= seg_min) & (original_values <= seg_max)
                                
                                # Align mask with y_train indices
                                if not mask.index.equals(y_train.index):
                                    mask = mask.reindex(y_train.index, fill_value=False)
                                
                                sample_count = int(mask.sum())
                                
                                if sample_count < 2:
                                    continue
                                
                                try:
                                    y_train_segment = y_train[mask]
                                    y_pred_segment = y_pred_train[mask] if isinstance(y_pred_train, (pd.Series, np.ndarray)) else np.array(y_pred_train)[mask.values if hasattr(mask, 'values') else mask]
                                    
                                    if len(y_train_segment) < 2:
                                        continue
                                    
                                    # OPTIMIZATION: Use batch metric calculation helper
                                    segment_accuracy, segment_precision, segment_recall, segment_f1, segment_cm = _compute_segment_metrics(y_train_segment, y_pred_segment)
                                    
                                    if seg_min == int(seg_min) and seg_max == int(seg_max):
                                        range_str = f"{int(seg_min)} to {int(seg_max)}"
                                    else:
                                        range_str = f"{seg_min:.2f} to {seg_max:.2f}"
                                    
                                    segment_label = f"Segment {segment_idx + 1} (lies between {range_str})"
                                    
                                    granular_data.append({
                                        'variable': variable,  # From Excel table
                                        'segment': segment_label,
                                        'granularity_level': f'{num_segments}_segments',
                                        'accuracy': float(segment_accuracy),
                                        'precision': float(segment_precision),
                                        'recall': float(segment_recall),
                                        'f1_score': float(segment_f1),
                                        'sample_count': sample_count,
                                        'confusion_matrix': segment_cm.tolist(),
                                        'value_range': range_str,
                                        'min_value': float(seg_min),
                                        'max_value': float(seg_max),
                                        'is_continuous': True
                                    })
                                    
                                    self.logger.info(f"   ✅ Created segment {segment_idx + 1} from Excel table for '{variable}': {range_str} ({sample_count} samples)")
                                    
                                except Exception as e:
                                    self.logger.warning(f"   Error creating segment for {variable} range {seg_min}-{seg_max}: {str(e)}")
                            
                            # Mark continuous variable as processed
                            processed_continuous_vars.add(variable)
                        else:
                            self.logger.warning(f"   ⚠️ Could not parse range from Excel Original_Value '{original_value}' for continuous variable '{variable}'")
                    except Exception as e:
                        self.logger.error(f"   Failed to process continuous variable '{variable}' from Excel table: {str(e)}")
            
            self.logger.info(f"✅ [TRAIN-ONLY PIPELINE] Created {len(granular_data)} segments total")
            
            # Final verification: Check for home_ownership segments
            home_ownership_segments = [item for item in granular_data if item.get('variable') == 'home_ownership' or 'home_ownership' in str(item.get('variable', '')).lower()]
            if home_ownership_segments:
                self.logger.info(f"   ✅ home_ownership segments created: {len(home_ownership_segments)}")
                for seg in home_ownership_segments:
                    self.logger.info(f"      - {seg.get('segment')} (variable: '{seg.get('variable')}', samples: {seg.get('sample_count')}, category: '{seg.get('category_value')}')")
            else:
                self.logger.error(f"   ❌❌❌ NO home_ownership segments found in granular_data!")
                self.logger.error(f"   Total segments created: {len(granular_data)}")
                self.logger.error(f"   Available variables in granular_data: {sorted(set(item.get('variable') for item in granular_data))}")
                
                # Check Excel table for home_ownership
                ho_excel_rows = df_excel[df_excel['Variable'].str.lower().str.contains('home_ownership', na=False)]
                if len(ho_excel_rows) > 0:
                    self.logger.error(f"   ⚠️ home_ownership found in Excel table with {len(ho_excel_rows)} rows:")
                    # OPTIMIZATION: Use itertuples instead of iterrows
                    for excel_row in ho_excel_rows.itertuples():
                        self.logger.error(f"      Excel row: Variable='{excel_row.Variable}', Original_Value='{excel_row.Original_Value}', Segment={excel_row.Segment_Number}")
                else:
                    self.logger.error(f"   ⚠️ home_ownership NOT found in Excel table!")
            
            return granular_data
            
        except Exception as e:
            self.logger.error(f"❌ [TRAIN-ONLY PIPELINE] Failed: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def _calculate_granular_accuracy(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        y_pred: np.ndarray,
        y_pred_proba: Optional[np.ndarray],
        feature_names: List[str],
        problem_type: str,
        category_mappings: Optional[Dict[str, Dict[int, str]]] = None,  # {feature_name: {encoded_value: original_name}}
        X_test_original: Optional[pd.DataFrame] = None,  # Original unscaled test data for continuous variables (or train data when called for train)
        scaler: Optional[Any] = None,  # Scaler to reverse-transform continuous variables
        column_stats: Optional[Dict[str, Any]] = None,  # Column statistics with data types {feature_name: {variable_type: 'categorical'|'continuous'|'date'}}
        preprocessed_columns: Optional[Dict[str, str]] = None,  # Preprocessed column mapping {original_name: preprocessed_name}
        X_train_original_info: Optional[Dict[str, Any]] = None,  # NEW: Metadata about X_train_original from training_results.json
        is_train_data: Optional[bool] = None  # NEW: Explicit flag to indicate if this is TRAIN data (True) or TEST data (False)
    ) -> List[Dict[str, Any]]:
        """
        Calculate accuracy for different segments of each feature.
        The dataset is divided into 2, 3, 4 and 5 segments for the selected variable
        so the frontend can present segment-wise accuracy as per user selection.
        """
        granular_data: List[Dict[str, Any]] = []
        skipped_features: Dict[str, str] = {}  # Track why features were skipped
        processed_categorical_features = []  # Track which categorical features were processed
        
        # OPTIMIZATION: Define batch metric calculation helper to reduce sklearn overhead
        def _compute_segment_metrics_main(y_true, y_pred_seg):
            """Compute all metrics for a segment in one pass - reduces sklearn call overhead"""
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
            acc = accuracy_score(y_true, y_pred_seg)
            prec = precision_score(y_true, y_pred_seg, average='weighted', zero_division=0)
            rec = recall_score(y_true, y_pred_seg, average='weighted', zero_division=0)
            f1 = f1_score(y_true, y_pred_seg, average='weighted', zero_division=0)
            cm = confusion_matrix(y_true, y_pred_seg)
            return acc, prec, rec, f1, cm
        
        # Log category mappings for debugging
        if category_mappings:
            self.logger.info(f"✅ Category mappings available for {len(category_mappings)} categorical features: {list(category_mappings.keys())}")
            for feat_name, mapping in list(category_mappings.items())[:3]:  # Log first 3
                sample_mapping = {k: v for k, v in list(mapping.items())[:5]}  # First 5 entries
                self.logger.debug(f"  {feat_name}: {sample_mapping}")
        else:
            self.logger.warning("⚠️ No category_mappings provided - categorical features will be skipped")
        
        # Log column_stats availability once (not per feature)
        if not column_stats:
            self.logger.info("ℹ️ No column_stats available - will infer variable types from data for all features")
        else:
            self.logger.info(f"✅ Column_stats available for {len(column_stats)} features")
            # Log sample column_stats for debugging
            sample_stats = list(column_stats.items())[:3]
            for feat_name, stats in sample_stats:
                self.logger.debug(f"  {feat_name}: variable_type={stats.get('variable_type', 'unknown')}, unique_count={stats.get('unique_count', 'unknown')}")
        
        # CRITICAL: Check problem_type first
        if problem_type != 'classification':
            self.logger.warning(f"⚠️ Granular accuracy only supported for classification, got: {problem_type}")
            return granular_data
        
        # Log initial state for debugging
        # CRITICAL: Use explicit flag if provided, otherwise try to detect
        if is_train_data is None:
            # Fallback detection: Check if X_test_original might actually be X_train_original
            # This is less reliable, so explicit flag is preferred
            is_train_data = X_test_original is not None and 'home_ownership' in X_test_original.columns and X_test is not None and len(X_test) > 0
            if is_train_data:
                # Check if indices match - if not, it's likely TRAIN data
                if X_test.index.equals(X_test_original.index):
                    is_train_data = False  # Indices match, likely TEST data
                else:
                    # Check if lengths match but indices differ - likely TRAIN data
                    if len(X_test) == len(X_test_original):
                        is_train_data = True
                    else:
                        is_train_data = False
        else:
            # Explicit flag provided - use it
            is_train_data = bool(is_train_data)
        
        data_type_label = "TRAIN" if is_train_data else "TEST"
        self.logger.info(f"🔍 Starting granular accuracy calculation ({data_type_label} data):")
        self.logger.info(f"   - X_test shape: {X_test.shape if X_test is not None else 'None'}")
        self.logger.info(f"   - X_test columns: {list(X_test.columns)[:10] if X_test is not None else 'None'}")
        self.logger.info(f"   - X_test index range: {X_test.index.min() if X_test is not None and len(X_test) > 0 else 'N/A'} to {X_test.index.max() if X_test is not None and len(X_test) > 0 else 'N/A'}")
        self.logger.info(f"   - feature_names: {feature_names[:10] if feature_names else 'None'}")
        self.logger.info(f"   - y_test length: {len(y_test) if y_test is not None else 'None'}")
        self.logger.info(f"   - y_test index range: {y_test.index.min() if y_test is not None and len(y_test) > 0 else 'N/A'} to {y_test.index.max() if y_test is not None and len(y_test) > 0 else 'N/A'}")
        self.logger.info(f"   - y_pred length: {len(y_pred) if y_pred is not None else 'None'}")
        self.logger.info(f"   - X_test_original: {'Available' if X_test_original is not None else 'None'}")
        
        # CRITICAL FIX: For TRAIN data, ensure X_test, y_test, and X_test_original have aligned indices
        # This is crucial because train data might have different index structures
        if is_train_data and X_test_original is not None and X_test is not None:
            # Check if indices need alignment
            common_indices = X_test.index.intersection(X_test_original.index)
            if len(common_indices) == 0 or len(common_indices) < len(X_test) * 0.5:
                # Indices don't match - use positional alignment
                self.logger.warning(f"   ⚠️ [{data_type_label}] Index mismatch detected - using positional alignment")
                self.logger.warning(f"   ⚠️ X_test length: {len(X_test)}, X_test_original length: {len(X_test_original)}, common indices: {len(common_indices)}")
                
                # Reset indices to ensure positional alignment
                if len(X_test) == len(X_test_original) and len(X_test) == len(y_test):
                    # All have same length - safe to reset indices
                    X_test_original = X_test_original.reset_index(drop=True)
                    X_test_original.index = X_test.index.copy()  # Use X_test's index
                    self.logger.info(f"   ✅ [{data_type_label}] Reset X_test_original indices to match X_test for positional alignment")
                else:
                    self.logger.error(f"   ❌ [{data_type_label}] Length mismatch: X_test={len(X_test)}, X_test_original={len(X_test_original)}, y_test={len(y_test)}")
        
        if X_test_original is not None:
            self.logger.info(f"   - X_test_original shape: {X_test_original.shape}")
            self.logger.info(f"   - X_test_original columns: {list(X_test_original.columns)[:10]}")
            self.logger.info(f"   - X_test_original index range: {X_test_original.index.min() if len(X_test_original) > 0 else 'N/A'} to {X_test_original.index.max() if len(X_test_original) > 0 else 'N/A'}")
            # CRITICAL: Check index alignment for TRAIN data
            if is_train_data:
                common_indices = X_test.index.intersection(X_test_original.index)
                self.logger.info(f"   - Common indices between X_test and X_test_original: {len(common_indices)} / {len(X_test)}")
                if len(common_indices) == 0:
                    self.logger.warning(f"   ⚠️ NO common indices! Will use positional alignment for TRAIN data")
                elif len(common_indices) < len(X_test) * 0.9:
                    self.logger.warning(f"   ⚠️ Only {len(common_indices)/len(X_test)*100:.1f}% indices match - will use positional alignment for TRAIN data")
                else:
                    self.logger.info(f"   ✅ {len(common_indices)/len(X_test)*100:.1f}% indices match - should work with reindex")
        
        try:
            
            # CRITICAL FIX: Handle feature name mismatches
            # If feature_names don't match X_test.columns, try to use X_test.columns directly
            available_features = list(X_test.columns) if X_test is not None and len(X_test.columns) > 0 else []
            features_to_process = []
            
            # Enhanced feature matching: handle preprocessed feature names
            # For example: "home_ownership_le_auto" should match "home_ownership" in X_test_original
            for feature in feature_names:
                matched = False
                
                # Strategy 1: Direct match
                if feature in X_test.columns:
                    features_to_process.append(feature)
                    matched = True
                else:
                    # Strategy 2: Case-insensitive match
                    for col in X_test.columns:
                        if col.lower() == feature.lower():
                            self.logger.warning(f"Feature name mismatch: '{feature}' not found, using '{col}' (case-insensitive match)")
                            features_to_process.append(col)
                            matched = True
                            break
                    
                    # Strategy 3: Try removing encoding suffixes (e.g., _le_auto, _le_manual)
                    if not matched:
                        for suffix in ['_le_auto', '_le_manual', '_le_model', '_ss_auto', '_ss_manual', '_transform_OHE']:
                            if feature.endswith(suffix):
                                potential_orig = feature[:-len(suffix)]
                                # Check if original name exists in X_test
                                if potential_orig in X_test.columns:
                                    features_to_process.append(potential_orig)
                                    self.logger.info(f"✅ Matched preprocessed feature '{feature}' to '{potential_orig}' in X_test")
                                    matched = True
                                    break
                                # Also check X_test_original for original column name
                                elif X_test_original is not None and potential_orig in X_test_original.columns:
                                    # Use the preprocessed name in X_test but track original name
                                    if feature in X_test.columns:
                                        features_to_process.append(feature)
                                        self.logger.info(f"✅ Matched preprocessed feature '{feature}' (original: '{potential_orig}' in X_test_original)")
                                        matched = True
                                        break
                    
                    # Strategy 4: Try reverse preprocessed_columns lookup
                    if not matched and preprocessed_columns:
                        # preprocessed_columns: {original: preprocessed}
                        for orig_name, preproc_name in preprocessed_columns.items():
                            if preproc_name == feature:
                                # Found original name, check if it exists in X_test or X_test_original
                                if orig_name in X_test.columns:
                                    features_to_process.append(orig_name)
                                    self.logger.info(f"✅ Matched via preprocessed_columns: '{feature}' -> '{orig_name}' in X_test")
                                    matched = True
                                    break
                                elif X_test_original is not None and orig_name in X_test_original.columns:
                                    # Original exists in X_test_original, use preprocessed name in X_test
                                    if feature in X_test.columns:
                                        features_to_process.append(feature)
                                        self.logger.info(f"✅ Matched via preprocessed_columns: '{feature}' -> '{orig_name}' (in X_test_original)")
                                        matched = True
                                        break
                
                    if not matched:
                        skipped_features[feature] = 'not_in_test_data'
                    self.logger.debug(f"⚠️ Feature '{feature}' not matched to any column in X_test")
            
            # FALLBACK: If no features matched, use X_test columns directly (with warning)
            if len(features_to_process) == 0 and len(available_features) > 0:
                self.logger.warning(f"⚠️ No features from feature_names matched X_test.columns. Using X_test columns directly as fallback.")
                self.logger.warning(f"   feature_names: {feature_names[:5]}...")
                self.logger.warning(f"   X_test.columns: {list(available_features)[:5]}...")
                features_to_process = available_features[:20]  # Limit to first 20 to avoid performance issues
            
            # CRITICAL: Ensure home_ownership is included if it exists in X_test_original
            # This is especially important for both TEST and TRAIN data granular accuracy
            if X_test_original is not None and 'home_ownership' in X_test_original.columns:
                # Check if home_ownership or any variant is already in features_to_process
                home_ownership_found = any('home_ownership' in feat.lower() for feat in features_to_process)
                if not home_ownership_found:
                    # Try to find the preprocessed version in X_test.columns
                    home_ownership_variants = [col for col in X_test.columns if 'home_ownership' in col.lower()]
                    if home_ownership_variants:
                        # Use the preprocessed version that exists in X_test
                        features_to_process.append(home_ownership_variants[0])
                        self.logger.info(f"✅✅✅ Added home_ownership variant '{home_ownership_variants[0]}' to features_to_process (for TEST/TRAIN)")
                    else:
                        # CRITICAL FIX: Even if no preprocessed version exists in X_test.columns,
                        # we should still process it if it's in X_test_original
                        # We'll use a special marker to indicate this feature should be processed
                        # by looking it up directly in X_test_original
                        features_to_process.append('home_ownership')  # Add original name
                        self.logger.info(f"✅✅✅ Added 'home_ownership' to features_to_process (exists in X_test_original, will lookup directly)")
                else:
                    self.logger.info(f"✅ home_ownership already in features_to_process")

            if len(features_to_process) == 0:
                self.logger.error(f"❌ No features available for granular accuracy calculation!")
                self.logger.error(f"   feature_names: {feature_names}")
                self.logger.error(f"   X_test.columns: {list(X_test.columns) if X_test is not None else 'None'}")
                return granular_data
            
            self.logger.info(f"📊 Processing {len(features_to_process)} features for granular accuracy")
            self.logger.info(f"   Features to process: {features_to_process[:10]}")
            if X_test_original is not None:
                self.logger.info(f"   X_test_original columns: {list(X_test_original.columns)[:10]}")
                if 'home_ownership' in X_test_original.columns:
                    self.logger.info(f"   ✅ home_ownership available in X_test_original for lookup")
            
            # OPTIMIZATION: Pre-compute inverse-transformed data ONCE to avoid repeated scaler calls
            # This is a major latency optimization - scaler.inverse_transform is expensive
            _cached_inverse_transformed_data = None
            if scaler is not None and hasattr(scaler, 'inverse_transform') and X_test is not None:
                try:
                    scaler_feature_names = None
                    if hasattr(scaler, 'feature_names_in_'):
                        scaler_feature_names = scaler.feature_names_in_
                    elif hasattr(scaler, 'get_feature_names_out'):
                        try:
                            scaler_feature_names = scaler.get_feature_names_out()
                        except:
                            pass
                    
                    if scaler_feature_names is not None:
                        common_features = [f for f in scaler_feature_names if f in X_test.columns]
                        if len(common_features) > 0:
                            X_test_for_scaler = X_test[common_features].copy()
                            _cached_inverse_transformed_data = pd.DataFrame(
                                scaler.inverse_transform(X_test_for_scaler),
                                columns=common_features,
                                index=X_test.index
                            )
                            self.logger.info(f"✅ Pre-computed inverse transform for {len(common_features)} features (cached)")
                    else:
                        _cached_inverse_transformed_data = pd.DataFrame(
                            scaler.inverse_transform(X_test),
                            columns=X_test.columns,
                            index=X_test.index
                        )
                        self.logger.info(f"✅ Pre-computed inverse transform for all {len(X_test.columns)} features (cached)")
                except Exception as e:
                    self.logger.warning(f"Failed to pre-compute inverse transform: {str(e)}")
                    _cached_inverse_transformed_data = None
            
            # Helper function to get original/unscaled values for a feature (defined once, outside loop)
            def get_original_feature_values(feat_name: str, is_cat: bool) -> Optional[pd.Series]:
                """
                Get original values for a feature.
                For categorical: returns original category values (before encoding)
                For continuous: returns original unscaled values (before scaling)
                Uses cached inverse-transformed data for performance.
                """
                # Priority 1: Use X_test_original if directly available
                if X_test_original is not None and feat_name in X_test_original.columns:
                    orig_vals = X_test_original[feat_name]
                    self.logger.debug(f"✅ Using X_test_original for {feat_name} (is_categorical={is_cat})")
                    return orig_vals
                
                # Priority 2: For categorical, try to get original name from preprocessed_columns
                if is_cat and preprocessed_columns:
                    original_feature_name = None
                    for orig_name, preproc_name in preprocessed_columns.items():
                        if preproc_name == feat_name:
                            original_feature_name = orig_name
                            break
                    
                    if original_feature_name:
                        # Found original name, try to get it from X_test_original
                        if X_test_original is not None and original_feature_name in X_test_original.columns:
                            orig_vals = X_test_original[original_feature_name]
                            self.logger.info(f"✅ Using original name '{original_feature_name}' from X_test_original for categorical '{feat_name}' ({len(orig_vals)} values)")
                            return orig_vals
                        else:
                            self.logger.debug(f"⚠️ Original feature '{original_feature_name}' not found in X_test_original (available: {list(X_test_original.columns)[:5] if X_test_original is not None else 'None'})")
                    
                    # Also try direct lookup if feature name suggests it's encoded (e.g., ends with _le_auto)
                    if not original_feature_name:
                        # Try removing common encoding suffixes
                        for suffix in ['_le_auto', '_le_manual', '_le_model', '_transform_OHE']:
                            if feat_name.endswith(suffix):
                                potential_orig = feat_name[:-len(suffix)]
                                if X_test_original is not None and potential_orig in X_test_original.columns:
                                    orig_vals = X_test_original[potential_orig]
                                    self.logger.info(f"✅ Found original feature '{potential_orig}' by removing suffix '{suffix}' from '{feat_name}' ({len(orig_vals)} values)")
                                    return orig_vals
                                break
                
                # Priority 3: Use CACHED inverse-transformed data (for continuous features)
                # OPTIMIZATION: This uses the pre-computed cache instead of calling scaler.inverse_transform each time
                if not is_cat and _cached_inverse_transformed_data is not None:
                    if feat_name in _cached_inverse_transformed_data.columns:
                        orig_vals = _cached_inverse_transformed_data[feat_name]
                        self.logger.debug(f"✅ Using cached inverse-transform for continuous {feat_name}")
                        return orig_vals
                
                # Priority 4: For categorical with category_mappings, try to reconstruct from mappings
                if is_cat and category_mappings:
                    # Check if feature or its original name has mappings
                    mapping_key = feat_name
                    if preprocessed_columns:
                        for orig_name, preproc_name in preprocessed_columns.items():
                            if preproc_name == feat_name and orig_name in category_mappings:
                                mapping_key = orig_name
                                break
                    
                    if mapping_key in category_mappings:
                        # We have mappings, but we need the actual values
                        # Use X_test values and map them back using reverse lookup
                        # This is a fallback - ideally we'd have X_test_original
                        self.logger.debug(f"⚠️ Using category_mappings for {feat_name}, but original values not available - will use mappings for labels only")
                        return None  # Will use mappings for labels but not for actual values
                
                return None
            
            # Generate segments for every feature so the frontend can pick the base variable
            for feature in features_to_process:
                # CRITICAL: Check if this is home_ownership (for special handling) - MUST be defined at start of loop
                is_home_ownership = 'home_ownership' in feature.lower() or feature == 'home_ownership'
                if is_home_ownership:
                    self.logger.info(f"🏠 Processing home_ownership feature: '{feature}'")
                
                # CRITICAL FIX: Allow features that exist in X_test_original even if not in X_test.columns
                # This handles cases like 'home_ownership' which might only be in X_test_original
                feature_in_test = feature in X_test.columns
                feature_in_original = X_test_original is not None and feature in X_test_original.columns
                
                if not feature_in_test and not feature_in_original:
                    skipped_features[feature] = 'not_in_test_data_or_original'
                    self.logger.warning(f"⚠️ Skipping feature '{feature}' - not found in X_test.columns or X_test_original.columns")
                    continue
                
                # Initialize variables for this feature iteration
                lookup_col_for_variable = None
                original_column_name = None
                original_feature_values = None  # Initialize to None
                found_in_x_test_original = False  # Initialize to False
                
                # If feature is in X_test_original but not in X_test, we'll use X_test_original directly
                if not feature_in_test and feature_in_original:
                    data_type = "TRAIN" if is_train_data else "TEST"
                    self.logger.info(f"📌 [{data_type}] Feature '{feature}' found in X_test_original but not in X_test.columns - will use X_test_original directly")
                    # Use X_test_original directly for this feature
                    # CRITICAL: Align indices with X_test to ensure mask alignment with y_test/y_pred
                    # Try multiple strategies for index alignment
                    original_feature_series = X_test_original[feature]
                    
                    # Strategy 1: Try reindex with X_test.index
                    feature_values = original_feature_series.reindex(X_test.index, fill_value=None)
                    reindex_success_rate = (1 - feature_values.isna().sum() / len(feature_values)) * 100 if len(feature_values) > 0 else 0
                    
                    # Strategy 2: If reindex failed (all NaN or <50% success), try positional alignment
                    if feature_values.isna().all() or reindex_success_rate < 50:
                        self.logger.warning(f"⚠️ [{data_type}] Reindex failed for '{feature}' (success rate: {reindex_success_rate:.1f}%) - trying positional alignment")
                        # Reset indices and align by position
                        original_reset = original_feature_series.reset_index(drop=True)
                        test_reset = X_test.reset_index(drop=True)
                        if len(original_reset) == len(test_reset):
                            feature_values = original_reset.copy()
                            feature_values.index = X_test.index  # Use X_test.index to align with y_test/y_pred
                            self.logger.info(f"✅ [{data_type}] Used positional alignment for '{feature}' (lengths match: {len(original_reset)})")
                        else:
                            self.logger.warning(f"⚠️ [{data_type}] Length mismatch: original={len(original_reset)}, test={len(test_reset)}")
                            # Strategy 3: Try to find common indices
                            common_indices = X_test.index.intersection(original_feature_series.index)
                            if len(common_indices) > 0:
                                feature_values = original_feature_series.loc[common_indices].reindex(X_test.index)
                                self.logger.info(f"✅ [{data_type}] Used common indices alignment for '{feature}' ({len(common_indices)} common indices)")
                            else:
                                self.logger.warning(f"⚠️ [{data_type}] Feature '{feature}' from X_test_original has no matching indices with X_test - skipping")
                                skipped_features[feature] = 'index_mismatch'
                                continue
                    else:
                        self.logger.info(f"✅ [{data_type}] Reindex successful for '{feature}' (success rate: {reindex_success_rate:.1f}%)")
                    
                    # Final check: if still mostly NaN, skip
                    non_null_count = feature_values.dropna().count()
                    if non_null_count < len(feature_values) * 0.1:
                        self.logger.warning(f"⚠️ [{data_type}] Feature '{feature}' from X_test_original has <10% non-null after alignment ({non_null_count}/{len(feature_values)}) - skipping")
                        skipped_features[feature] = 'index_mismatch'
                        continue
                    
                    # CRITICAL: Verify mask alignment with y_test
                    if len(feature_values) != len(y_test):
                        self.logger.error(f"❌ [{data_type}] CRITICAL: feature_values length ({len(feature_values)}) != y_test length ({len(y_test)}) - this will cause mask errors!")
                        # For train data, try to fix by resetting indices if they don't match
                        if is_train_data and len(X_test) == len(y_test):
                            # Reset both to positional indices to ensure alignment
                            feature_values = feature_values.reset_index(drop=True)
                            feature_values.index = X_test.reset_index(drop=True).index
                            self.logger.warning(f"⚠️ [{data_type}] Fixed index alignment for '{feature}' by resetting indices")
                            if len(feature_values) != len(y_test):
                                skipped_features[feature] = 'length_mismatch'
                                continue
                        else:
                            skipped_features[feature] = 'length_mismatch'
                            continue
                    
                    # CRITICAL: Set lookup_col_for_variable so it's available for variable name assignment
                    lookup_col_for_variable = feature
                    original_column_name = feature
                    # CRITICAL: Also set original_feature_values since we're using X_test_original directly
                    # This ensures the direct path logic can use it later
                    original_feature_values = feature_values.copy()
                    # CRITICAL: Mark that we found this feature in X_test_original
                    # This is especially important for home_ownership in TRAIN data
                    if is_home_ownership:
                        self.logger.info(f"✅✅✅ [{data_type}] home_ownership taken from X_test_original - will use direct path for segmentation")
                    self.logger.info(f"✅ [{data_type}] Set lookup_col_for_variable='{lookup_col_for_variable}' and original_feature_values for feature '{feature}' (from X_test_original, {non_null_count} non-null values, aligned with y_test)")
                else:
                    # Normal case: feature is in X_test.columns
                    feature_values = X_test[feature]
                
                # CRITICAL: Check column_stats FIRST to identify date columns before processing
                # This ensures we handle date columns properly even if they're already numeric
                is_date_from_stats = False
                if column_stats:
                    # Try to find feature in column_stats (check both original and preprocessed names)
                    original_feature_name_for_stats = feature
                    if preprocessed_columns:
                        for orig_name, preproc_name in preprocessed_columns.items():
                            if preproc_name == feature:
                                original_feature_name_for_stats = orig_name
                                break
                    
                    # Check column_stats for date type
                    if original_feature_name_for_stats in column_stats:
                        variable_type = column_stats[original_feature_name_for_stats].get('variable_type')
                        if variable_type == 'date':
                            is_date_from_stats = True
                            self.logger.info(f"✅ Feature {feature} identified as DATE from column_stats")
                    elif feature in column_stats:
                        variable_type = column_stats[feature].get('variable_type')
                        if variable_type == 'date':
                            is_date_from_stats = True
                            self.logger.info(f"✅ Feature {feature} identified as DATE from column_stats")
                
                # Handle date/datetime columns - but try to get original date values first
                is_datetime_dtype = pd.api.types.is_datetime64_any_dtype(feature_values)
                original_date_values = None
                
                # Try to get original date values from X_test_original if available
                if (is_date_from_stats or is_datetime_dtype) and X_test_original is not None:
                    # Try to find original date column
                    date_lookup_col = None
                    if feature in X_test_original.columns:
                        date_lookup_col = feature
                    elif preprocessed_columns:
                        for orig_name, preproc_name in preprocessed_columns.items():
                            if preproc_name == feature and orig_name in X_test_original.columns:
                                date_lookup_col = orig_name
                                break
                    
                    if date_lookup_col:
                        original_date_values = X_test_original[date_lookup_col]
                        self.logger.info(f"✅ Found original date values for {feature} in X_test_original (column: '{date_lookup_col}')")
                
                # If we have datetime64 dtype, convert to numeric for processing, but keep original for segmentation
                if is_datetime_dtype and original_date_values is None:
                    try:
                        min_date = feature_values.min()
                        feature_values = (feature_values - min_date).dt.days.astype(float)
                        self.logger.info(f"Converted date column {feature} to numeric (days since {min_date})")
                    except Exception as e:
                        skipped_features[feature] = f'date_conversion_failed: {str(e)}'
                        continue
                
                # Try to convert object columns that look like dates OR use original date values if available
                # CRITICAL: Process date columns if identified from column_stats OR detected from data
                if is_date_from_stats or feature_values.dtype == 'object':
                    is_date_column = is_date_from_stats  # Start with column_stats result
                    
                    if not is_date_column:
                        # Check if column name suggests it's a date
                        date_indicators = ['_d', '_date', 'date_', '_dt', 'issue', 'pymnt', 'credit_pull', 'cr_line']
                        if any(ind in feature.lower() for ind in date_indicators):
                            is_date_column = True
                        
                        # Also check sample values for date-like patterns (Mon-YY, DD-Mon, etc.)
                        sample_values = feature_values.dropna().head(10).astype(str)
                        date_patterns = [
                            r'^\d{1,2}-[A-Za-z]{3}$',  # "16-Jan"
                            r'^[A-Za-z]{3}-\d{2}$',    # "May-88"
                            r'^\d{1,2}/\d{1,2}/\d{2,4}$',  # "1/15/2020"
                        ]
                        import re
                        for val in sample_values:
                            for pattern in date_patterns:
                                if re.match(pattern, val):
                                    is_date_column = True
                                    break
                    
                    if is_date_column:
                        try:
                            # CRITICAL: Use original_date_values if available (from X_test_original)
                            # Otherwise, try to parse feature_values
                            parsed_dates = None
                            
                            if original_date_values is not None:
                                # Use original date values from X_test_original
                                if pd.api.types.is_datetime64_any_dtype(original_date_values):
                                    parsed_dates = original_date_values
                                    self.logger.info(f"✅ Using original datetime64 values from X_test_original for {feature}")
                                else:
                                    # Try to parse original date values
                                    for fmt in [None, '%d-%b', '%b-%y', '%d-%b-%y', '%m/%d/%Y', '%Y-%m-%d']:
                                        try:
                                            if fmt:
                                                parsed_dates = pd.to_datetime(original_date_values, format=fmt, errors='coerce')
                                            else:
                                                parsed_dates = pd.to_datetime(original_date_values, errors='coerce')
                                            
                                            valid_count = parsed_dates.notna().sum()
                                            if valid_count > len(original_date_values) * 0.3:  # >30% valid dates
                                                self.logger.info(f"✅ Parsed original date values for {feature} using format {fmt if fmt else 'auto'}")
                                                break
                                        except:
                                            continue
                            
                            # Fallback: Try to parse feature_values if original_date_values not available or parsing failed
                            if parsed_dates is None or parsed_dates.notna().sum() <= len(feature_values) * 0.3:
                                for fmt in [None, '%d-%b', '%b-%y', '%d-%b-%y', '%m/%d/%Y', '%Y-%m-%d']:
                                    try:
                                        if fmt:
                                            parsed_dates = pd.to_datetime(feature_values, format=fmt, errors='coerce')
                                        else:
                                            parsed_dates = pd.to_datetime(feature_values, errors='coerce')
                                        
                                        valid_count = parsed_dates.notna().sum()
                                        if valid_count > len(feature_values) * 0.3:  # >30% valid dates
                                            break
                                    except:
                                        continue
                            
                            # CRITICAL: Lower threshold for date columns identified from column_stats
                            # If column_stats says it's a date, we should trust it even if parsing is imperfect
                            min_valid_threshold = 0.1 if is_date_from_stats else 0.3  # 10% for stats-identified dates, 30% for detected
                            
                            if parsed_dates is not None and parsed_dates.notna().sum() > len(feature_values) * min_valid_threshold:
                                # SEGMENT BY MONTH GROUPS based on number of segments
                                # 2 segments = 6 months each (Jan-Jun, Jul-Dec)
                                # 3 segments = 4 months each (Jan-Apr, May-Aug, Sep-Dec)
                                # 4 segments = 3 months each (Jan-Mar, Apr-Jun, Jul-Sep, Oct-Dec)
                                # 5 segments = ~2-3 months each
                                
                                month_num = parsed_dates.dt.month.fillna(0).astype(int)  # 1-12
                                
                                month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                                
                                self.logger.info(f"Date column {feature}: creating month-based segments for 2-5 divisions")
                                
                                # Create segments for 2, 3, 4, 5 divisions
                                for num_segments in [2, 3, 4, 5]:
                                    months_per_segment = 12 // num_segments
                                    
                                    for segment_idx in range(num_segments):
                                        start_month = segment_idx * months_per_segment + 1
                                        end_month = (segment_idx + 1) * months_per_segment
                                        if segment_idx == num_segments - 1:
                                            end_month = 12  # Last segment includes remaining months
                                        
                                        mask = (month_num >= start_month) & (month_num <= end_month)
                                        sample_count = int(mask.sum())
                                        
                                        if sample_count < 2:
                                            continue
                                        
                                        try:
                                            # OPTIMIZATION: Use batch metric calculation
                                            segment_accuracy, segment_precision, segment_recall, segment_f1, segment_cm = _compute_segment_metrics_main(y_test[mask], y_pred[mask])
                                            
                                            # Create readable label like "Jan-Jun" or "Jul-Dec"
                                            start_name = month_order[start_month - 1]
                                            end_name = month_order[end_month - 1]
                                            if start_month == end_month:
                                                month_range = start_name
                                            else:
                                                month_range = f"{start_name}-{end_name}"
                                            
                                            segment_label = f"Segment {segment_idx + 1} ({month_range})"
                                            
                                            granular_data.append({
                                                'variable': feature,
                                                'segment': segment_label,
                                                'granularity_level': f'{num_segments}_segments',
                                                'accuracy': safe_float(segment_accuracy),
                                                'precision': safe_float(segment_precision),
                                                'recall': safe_float(segment_recall),
                                                'f1_score': safe_float(segment_f1),
                                                'sample_count': sample_count,
                                                'confusion_matrix': segment_cm.tolist(),
                                                'month_range': month_range
                                            })
                                        except Exception as e:
                                            self.logger.warning(f"Error calculating metrics for {feature} segment {segment_idx}: {str(e)}")
                                
                                # Skip the normal processing for this date column
                                continue
                            else:
                                # If date parsing fails, treat as categorical with the string values
                                self.logger.info(f"Date column {feature} couldn't be parsed, treating as categorical")
                        except Exception as e:
                            self.logger.warning(f"Error parsing date column {feature}: {str(e)}")
                            # Continue with categorical treatment
                
                # Determine if this is truly continuous or categorical
                # PRIORITY ORDER (most authoritative first):
                # 1. category_mappings - if feature has mappings, it's DEFINITELY categorical (even if numeric after encoding)
                # 2. column_stats - authoritative source from original data (before encoding)
                # 3. Infer from current data type (fallback)
                
                is_numeric = pd.api.types.is_numeric_dtype(feature_values)
                is_bool = pd.api.types.is_bool_dtype(feature_values)
                is_object = feature_values.dtype == 'object' or pd.api.types.is_string_dtype(feature_values)
                unique_count = feature_values.nunique()
                
                # PRIORITY 1: Check category_mappings FIRST (strongest signal)
                # If a feature has category_mappings, it's DEFINITELY categorical (even if numeric after encoding)
                has_category_mappings = category_mappings and feature in category_mappings
                if not has_category_mappings and category_mappings:
                    # Also check if any preprocessed column maps to this feature
                    # preprocessed_columns format: {original_name: preprocessed_name}
                    if preprocessed_columns:
                        for orig_name, preproc_name in preprocessed_columns.items():
                            if preproc_name == feature and orig_name in category_mappings:
                                has_category_mappings = True
                                self.logger.debug(f"Found category_mappings for {feature} via original name {orig_name}")
                                break
                    
                    # Also check if feature name suggests it's encoded (e.g., ends with _le_auto, _le_manual)
                    # In that case, try to find the original name by removing the suffix
                    if not has_category_mappings:
                        for suffix in ['_le_auto', '_le_manual', '_le_model', '_transform_OHE']:
                            if feature.endswith(suffix):
                                potential_orig = feature[:-len(suffix)]
                                if potential_orig in category_mappings:
                                    has_category_mappings = True
                                    self.logger.debug(f"Found category_mappings for {feature} by removing suffix {suffix} -> {potential_orig}")
                                    break
                
                # PRIORITY 2: Check column_stats for authoritative data type
                # Feature name might be preprocessed, so check both original and preprocessed names
                variable_type_from_stats = None
                original_feature_name = feature
                
                # Try to find original feature name if preprocessed
                if preprocessed_columns:
                    # preprocessed_columns format: {original_name: preprocessed_name}
                    for orig_name, preproc_name in preprocessed_columns.items():
                        if preproc_name == feature:
                            original_feature_name = orig_name
                            break
                
                # Check column_stats with both original and preprocessed feature names
                if column_stats:
                    if original_feature_name in column_stats:
                        variable_type_from_stats = column_stats[original_feature_name].get('variable_type')
                        self.logger.debug(f"✅ Feature {feature} (original: {original_feature_name}): Found variable_type in column_stats: {variable_type_from_stats}")
                    elif feature in column_stats:
                        variable_type_from_stats = column_stats[feature].get('variable_type')
                        self.logger.debug(f"✅ Feature {feature}: Found variable_type in column_stats: {variable_type_from_stats}")
                    else:
                        # Try case-insensitive and partial matching
                        found_match = False
                        for key in column_stats.keys():
                            if key.lower() == original_feature_name.lower() or key.lower() == feature.lower():
                                variable_type_from_stats = column_stats[key].get('variable_type')
                                self.logger.debug(f"✅ Feature {feature} (original: {original_feature_name}): Found case-insensitive match '{key}' with variable_type: {variable_type_from_stats}")
                                found_match = True
                                break
                        
                        if not found_match:
                            self.logger.debug(f"❌ Feature {feature} (original: {original_feature_name}): NOT found in column_stats. Available keys: {list(column_stats.keys())[:10] if column_stats else 'None'}")
                # Note: If column_stats is None/empty, we already logged a single message before the loop
                
                # DECISION LOGIC: Use priority order
                # IMPORTANT: column_stats is MORE authoritative than category_mappings for determining if a feature is truly categorical
                # Some numeric features might accidentally get category_mappings, but column_stats knows the original type
                if variable_type_from_stats:
                    # PRIORITY 1: Use authoritative data type from column_stats (most reliable)
                    if variable_type_from_stats in ['continuous', 'numeric']:
                        is_categorical = False
                        self.logger.info(f"✅ Feature {feature}: column_stats says CONTINUOUS - treating as CONTINUOUS (will create 5 bins on original values)")
                        # Override category_mappings if present - this is a numeric feature, not categorical
                        if has_category_mappings:
                            self.logger.warning(f"⚠️ Feature {feature}: Has category_mappings but column_stats says CONTINUOUS - ignoring mappings (likely numeric feature)")
                    elif variable_type_from_stats in ['categorical', 'category']:
                        is_categorical = True
                        self.logger.info(f"✅ Feature {feature}: column_stats says CATEGORICAL - treating as CATEGORICAL")
                    elif variable_type_from_stats == 'date':
                        is_categorical = True  # Dates are handled specially but treated as categorical for segmentation
                        self.logger.info(f"✅ Feature {feature}: column_stats says DATE - treating as CATEGORICAL (date segments)")
                    else:
                        # Unknown type in column_stats, fall back to category_mappings
                        if has_category_mappings:
                            is_categorical = True
                            self.logger.warning(f"Feature {feature}: Unknown variable_type '{variable_type_from_stats}' in column_stats, using category_mappings -> CATEGORICAL")
                        else:
                            is_categorical = not is_numeric
                            self.logger.warning(f"Feature {feature}: Unknown variable_type '{variable_type_from_stats}' in column_stats, inferring from data")
                elif has_category_mappings:
                    # PRIORITY 2: category_mappings (only if column_stats not available)
                    # If feature has mappings, it's likely categorical (even if numeric after encoding)
                    is_categorical = True
                    self.logger.info(f"✅ Feature {feature}: Has category_mappings (no column_stats) - treating as CATEGORICAL (encoded categorical feature)")
                else:
                    # PRIORITY 3: No column_stats available - infer from data type
                    # STRICT RULE: 
                    # - Object/string dtype -> categorical (like home_ownership)
                    # - Numeric dtype -> continuous (but be careful - encoded categoricals might be numeric)
                    if is_object or is_bool:
                        is_categorical = True
                        self.logger.info(f"✅ Feature {feature}: OBJECT/STRING dtype (no column_stats) - treating as CATEGORICAL, unique={unique_count}")
                    elif is_numeric:
                        # Numeric but no category_mappings and no column_stats
                        # Use unique count as heuristic: low cardinality might be categorical
                        if unique_count <= 20 and unique_count > 0:
                            # Low cardinality numeric - might be categorical, but we can't be sure
                            # Default to continuous unless we have more info
                            is_categorical = False
                            self.logger.info(f"Feature {feature}: NUMERIC dtype, low cardinality ({unique_count} unique) - treating as CONTINUOUS (no mappings/stats), unique={unique_count}")
                        else:
                            is_categorical = False
                            self.logger.info(f"Feature {feature}: NUMERIC dtype (no column_stats) - treating as CONTINUOUS (will create 5 bins on original values), unique={unique_count}")
                    else:
                        # Default: non-numeric is categorical
                        is_categorical = True
                        self.logger.info(f"Feature {feature}: UNKNOWN dtype (no column_stats) - treating as CATEGORICAL, unique={unique_count}")
                
                # Get original values based on feature type
                # CRITICAL: Enhanced logic similar to date columns - check column_stats first, use X_test_original
                original_feature_values = None
                is_categorical_from_stats = variable_type_from_stats in ['categorical', 'category'] if variable_type_from_stats else False
                is_continuous_from_stats = variable_type_from_stats in ['continuous', 'numeric'] if variable_type_from_stats else False
                
                if is_categorical:
                    # For categorical: get original category values (before encoding)
                    # CRITICAL: Try multiple strategies to get original values, similar to date columns
                    
                    # Strategy 1: Use get_original_feature_values helper
                    original_feature_values = get_original_feature_values(feature, is_cat=True)
                    
                    # Strategy 2: If helper failed, try direct lookup in X_test_original (similar to date columns)
                    if original_feature_values is None and X_test_original is not None:
                        # Try to find original categorical column
                        cat_lookup_col = None
                        if feature in X_test_original.columns:
                            cat_lookup_col = feature
                        elif preprocessed_columns:
                            for orig_name, preproc_name in preprocessed_columns.items():
                                if preproc_name == feature and orig_name in X_test_original.columns:
                                    cat_lookup_col = orig_name
                                    break
                        elif feature.endswith('_le_auto') or feature.endswith('_le_manual') or feature.endswith('_le_model'):
                            potential_orig = feature.rsplit('_le_', 1)[0] if '_le_' in feature else feature
                            if potential_orig in X_test_original.columns:
                                cat_lookup_col = potential_orig
                        
                        if cat_lookup_col:
                            original_feature_values = X_test_original[cat_lookup_col]
                            self.logger.info(f"✅ Found original categorical values for {feature} in X_test_original (column: '{cat_lookup_col}')")
                    
                    # Strategy 3: Fallback to current values if original not found
                    if original_feature_values is None:
                        # CRITICAL: For categorical from column_stats, we should still try to create segments
                        # even if original values aren't found - use current values as fallback
                        if is_categorical_from_stats:
                            self.logger.warning(f"⚠️ Categorical feature {feature} identified from column_stats but original values not found, using current values as fallback")
                        else:
                            self.logger.debug(f"⚠️ Using current values for categorical {feature} (original not available)")
                        original_feature_values = feature_values
                else:
                    # For continuous: get original unscaled values (before scaling)
                    # CRITICAL: Try multiple strategies similar to date columns
                    
                    # Strategy 1: Use get_original_feature_values helper
                    original_feature_values = get_original_feature_values(feature, is_cat=False)
                    
                    # Strategy 2: If helper failed, try direct lookup in X_test_original
                    if original_feature_values is None and X_test_original is not None:
                        # Try to find original continuous column
                        cont_lookup_col = None
                        if feature in X_test_original.columns:
                            cont_lookup_col = feature
                        elif preprocessed_columns:
                            for orig_name, preproc_name in preprocessed_columns.items():
                                if preproc_name == feature and orig_name in X_test_original.columns:
                                    cont_lookup_col = orig_name
                                    break
                        
                        if cont_lookup_col:
                            original_feature_values = X_test_original[cont_lookup_col]
                            self.logger.info(f"✅ Found original continuous values for {feature} in X_test_original (column: '{cont_lookup_col}')")
                    
                    # Strategy 3: Try reverse transform with scaler
                    if original_feature_values is None and scaler is not None and hasattr(scaler, 'inverse_transform'):
                        try:
                            if feature in X_test.columns:
                                # Inverse transform all features, then extract the one we need
                                X_test_original_full = pd.DataFrame(
                                    scaler.inverse_transform(X_test),
                                    columns=X_test.columns,
                                    index=X_test.index
                                )
                                original_feature_values = X_test_original_full[feature]
                                self.logger.info(f"✅ Reverse-transformed scaled values for continuous {feature}")
                        except Exception as e:
                            self.logger.warning(f"Failed to reverse-transform {feature}: {str(e)}")
                    
                    # Strategy 4: Fallback to current values if numeric
                    if original_feature_values is None:
                        # CRITICAL: For continuous from column_stats, we should still try to create segments
                        # even if original values aren't found - use current values as fallback
                        if pd.api.types.is_numeric_dtype(feature_values):
                            if is_continuous_from_stats:
                                self.logger.warning(f"⚠️ Continuous feature {feature} identified from column_stats but original unscaled values not found, using current values as fallback")
                            else:
                                self.logger.warning(f"⚠️ No original unscaled data available for continuous {feature}, using current values as fallback")
                            original_feature_values = feature_values
                        else:
                            # No way to get original values and current values aren't numeric - skip this continuous feature
                            self.logger.error(f"❌ No original unscaled data available for continuous {feature} and current values are not numeric - cannot create intervals. Skipping.")
                            skipped_features[feature] = 'no_original_unscaled_data'
                            continue
                    else:
                        self.logger.info(f"✅ Using original unscaled values for continuous feature {feature} (min={original_feature_values.min():.2f}, max={original_feature_values.max():.2f})")
                
                if not is_categorical:
                    # Truly continuous feature: STRICTLY divide into exactly 5 intervals using ORIGINAL unscaled values
                    # NEVER SKIP - always process continuous variables
                    num_segments = 5  # Always create exactly 5 intervals
                    
                    # ALWAYS process continuous variables - even if few unique values, create intervals anyway
                    unique_count = original_feature_values.nunique()
                    if unique_count < num_segments:
                        self.logger.info(f"Continuous feature {feature}: only {unique_count} unique values, but creating {num_segments} intervals anyway (some may be empty)")
                    
                    # STRICTLY create exactly 5 equal-width intervals using ORIGINAL unscaled values
                    try:
                        min_val = float(original_feature_values.min())
                        max_val = float(original_feature_values.max())
                        
                        # Handle edge case: if min == max, create intervals around that value
                        if min_val == max_val:
                            # All values are the same - create intervals around this value
                            self.logger.info(f"Continuous feature {feature}: all values are {min_val}, creating intervals around this value")
                            bin_edges = np.linspace(min_val - 0.5, max_val + 0.5, num_segments + 1)
                        else:
                            # Create exactly 5 bin edges (6 edges for 5 intervals) from ORIGINAL values
                            bin_edges = np.linspace(min_val, max_val, num_segments + 1)
                        
                        # Assign each ORIGINAL value to an interval (0-4)
                        segment_indices = np.digitize(original_feature_values, bin_edges[1:], right=True)
                        # Ensure indices are strictly 0-4
                        segment_indices = np.clip(segment_indices, 0, num_segments - 1)
                        
                        # Create exactly 5 segments - one for each interval (even if empty)
                        for segment_idx in range(num_segments):
                            # Get mask for this interval
                            mask = segment_indices == segment_idx
                            
                            # Get interval boundaries from bin_edges
                            seg_min = float(bin_edges[segment_idx])
                            seg_max = float(bin_edges[segment_idx + 1])
                            
                            sample_count = int(mask.sum())
                            
                            if sample_count == 0:
                                # Empty interval - set metrics to 0
                                segment_accuracy = 0.0
                                segment_precision = 0.0
                                segment_recall = 0.0
                                segment_f1 = 0.0
                                segment_cm = np.array([[0, 0], [0, 0]])
                                self.logger.debug(f"  Segment {segment_idx + 1} for {feature}: empty interval [{seg_min:.2f}, {seg_max:.2f}]")
                            else:
                                # OPTIMIZATION: Use batch metric calculation
                                segment_accuracy, segment_precision, segment_recall, segment_f1, segment_cm = _compute_segment_metrics_main(y_test[mask], y_pred[mask])
                                self.logger.debug(f"  Segment {segment_idx + 1} for {feature}: [{seg_min:.2f}, {seg_max:.2f}], {sample_count} samples")
                            
                            # Format range string for display (interval format)
                            if seg_min == int(seg_min) and seg_max == int(seg_max):
                                range_str = f"{int(seg_min)} to {int(seg_max)}"
                            else:
                                range_str = f"{seg_min:.2f} to {seg_max:.2f}"
                            # Format as "Segment X lies between [min, max]"
                            segment_label = f"Segment {segment_idx + 1} (lies between {range_str})"
                            
                            granular_data.append({
                                'variable': feature,
                                'segment': segment_label,
                                'granularity_level': f'{num_segments}_segments',
                                'accuracy': safe_float(segment_accuracy),
                                'precision': safe_float(segment_precision),
                                'recall': safe_float(segment_recall),
                                'f1_score': safe_float(segment_f1),
                                'sample_count': sample_count,
                                'confusion_matrix': segment_cm.tolist() if hasattr(segment_cm, 'tolist') else segment_cm,
                                'value_range': range_str,
                                'min_value': safe_float(seg_min),
                                'max_value': safe_float(seg_max),
                                'is_continuous': True
                            })
                        
                        self.logger.info(f"✅ Continuous feature {feature}: Created exactly {num_segments} intervals (min={min_val:.2f}, max={max_val:.2f})")
                    except Exception as e:
                        # Even on error, try to create basic intervals
                        self.logger.error(f"Error creating intervals for {feature}: {str(e)}, creating basic intervals")
                        import traceback
                        self.logger.error(traceback.format_exc())
                        
                        # Fallback: create simple intervals
                        try:
                            min_val = float(original_feature_values.min())
                            max_val = float(original_feature_values.max())
                            if min_val == max_val:
                                bin_edges = np.linspace(min_val - 0.5, max_val + 0.5, num_segments + 1)
                            else:
                                bin_edges = np.linspace(min_val, max_val, num_segments + 1)
                            
                            for segment_idx in range(num_segments):
                                seg_min = float(bin_edges[segment_idx])
                                seg_max = float(bin_edges[segment_idx + 1])
                                
                                if seg_min == int(seg_min) and seg_max == int(seg_max):
                                    range_str = f"{int(seg_min)} to {int(seg_max)}"
                                else:
                                    range_str = f"{seg_min:.2f} to {seg_max:.2f}"
                                
                                granular_data.append({
                                    'variable': feature,
                                    'segment': f"Segment {segment_idx + 1} (lies between {range_str})",
                                    'granularity_level': f'{num_segments}_segments',
                                    'accuracy': 0.0,
                                    'precision': 0.0,
                                    'recall': 0.0,
                                    'f1_score': 0.0,
                                    'sample_count': 0,
                                    'confusion_matrix': [[0, 0], [0, 0]],
                                    'value_range': range_str,
                                    'min_value': safe_float(seg_min),
                                    'max_value': safe_float(seg_max),
                                    'is_continuous': True
                                })
                            self.logger.info(f"✅ Continuous feature {feature}: Created {num_segments} intervals (fallback mode)")
                        except Exception as e2:
                            self.logger.error(f"Failed to create fallback intervals for {feature}: {str(e2)}")
                            # Don't skip - create at least one segment with the range
                            min_val_str = f"{int(original_feature_values.min())}" if original_feature_values.min() == int(original_feature_values.min()) else f"{original_feature_values.min():.2f}"
                            max_val_str = f"{int(original_feature_values.max())}" if original_feature_values.max() == int(original_feature_values.max()) else f"{original_feature_values.max():.2f}"
                            range_str = f"{min_val_str} to {max_val_str}"
                            granular_data.append({
                                'variable': feature,
                                'segment': f"Segment 1 (lies between {range_str})",
                                'granularity_level': f'{num_segments}_segments',
                                'accuracy': 0.0,
                                'precision': 0.0,
                                'recall': 0.0,
                                'f1_score': 0.0,
                                'sample_count': len(original_feature_values),
                                'confusion_matrix': [[0, 0], [0, 0]],
                                'value_range': f"{original_feature_values.min():.2f} to {original_feature_values.max():.2f}",
                                'min_value': safe_float(original_feature_values.min()),
                                'max_value': safe_float(original_feature_values.max()),
                                'is_continuous': True
                            })
                
                if is_categorical:
                    # Categorical feature handling - WORK WITH ORIGINAL CATEGORIES ONLY
                    # Use original_feature_values if available (contains original category names before encoding)
                    # Initialize category_mappings if None
                    if category_mappings is None:
                        category_mappings = {}
                    
                    # Initialize variables to ensure they exist even if processing fails
                    num_categories = 0
                    original_categories_list = []
                    scaled_to_original = {}
                    use_direct_original_values = False
                    
                    # Find the correct key to use for category_mappings lookup AND for variable name in segments
                    # This might be the original feature name, not the preprocessed one
                    # CRITICAL: Use original name for variable in segments so UI can find them
                    category_mapping_key = feature  # Default to feature name
                    variable_name_for_segments = feature  # Will be updated to original name if found
                    has_category_mappings = category_mappings and feature in category_mappings
                    
                    # If not found, try to find via preprocessed_columns mapping
                    if not has_category_mappings and category_mappings and preprocessed_columns:
                        # preprocessed_columns format: {original_name: preprocessed_name}
                        for orig_name, preproc_name in preprocessed_columns.items():
                            if preproc_name == feature:
                                # Found original name - check if it's in category_mappings
                                if orig_name in category_mappings:
                                    category_mapping_key = orig_name
                                    variable_name_for_segments = orig_name  # Use original name for segments
                                    has_category_mappings = True
                                    self.logger.info(f"✅ Found category_mappings for '{feature}' using original name '{orig_name}'")
                                    break
                    
                    # Also check if feature name suggests it's encoded (e.g., ends with _le_auto)
                    if not has_category_mappings and category_mappings:
                        for suffix in ['_le_auto', '_le_manual', '_le_model', '_transform_OHE']:
                            if feature.endswith(suffix):
                                potential_orig = feature[:-len(suffix)]
                                if potential_orig in category_mappings:
                                    category_mapping_key = potential_orig
                                    variable_name_for_segments = potential_orig  # Use original name for segments
                                    has_category_mappings = True
                                    self.logger.info(f"✅ Found category_mappings for '{feature}' by removing suffix '{suffix}' -> '{potential_orig}'")
                                    break

                    # If we have original_feature_values, use them directly (they contain original category names)
                    if original_feature_values is not None and not original_feature_values.equals(feature_values):
                        # We have original values - use them for segmentation
                        self.logger.info(f"✅ Using original category values for categorical feature {feature} (before encoding)")
                        categorical_values_to_use = original_feature_values
                    else:
                        # Use current values (encoded) but we'll map them back using category_mappings
                        categorical_values_to_use = feature_values
                        self.logger.debug(f"Using encoded values for {feature}, will map back using category_mappings")
                    
                    # For numeric categorical variables (like counts with few unique values),
                    # if no category mappings exist, use the numeric values themselves as categories
                    if not has_category_mappings:
                        if is_numeric:
                            # Numeric categorical without mappings - use ORIGINAL numeric values as categories
                            self.logger.info(f"📊 Numeric categorical feature '{feature}' has no category mappings - using ORIGINAL numeric values as categories")
                            
                            # Use original_feature_values if available (already obtained above)
                            original_categorical_values = original_feature_values if original_feature_values is not None else None
                            
                            if original_categorical_values is not None:
                                # Use ORIGINAL values to create category mappings
                                unique_original_values = sorted(original_categorical_values.dropna().unique())
                                # Create mapping: scaled_value -> original_value (as string)
                                # We need to map scaled values (from feature_values) to original values
                                unique_scaled_values = sorted(feature_values.dropna().unique())
                                
                                if len(unique_scaled_values) == len(unique_original_values):
                                    # Perfect match: create direct mapping
                                    category_mappings[category_mapping_key] = {
                                        float(scaled): str(orig) 
                                        for scaled, orig in zip(unique_scaled_values, unique_original_values)
                                    }
                                    self.logger.info(f"Created category mapping for {feature} (key: {category_mapping_key}): {len(category_mappings[category_mapping_key])} categories using original values")
                                    has_category_mappings = True
                                else:
                                    # Mismatch: use original values directly, map by position
                                    self.logger.warning(f"Scaled/original value count mismatch for {feature}: {len(unique_scaled_values)} scaled vs {len(unique_original_values)} original")
                                    # Fallback: use original values indexed by position
                                    category_mappings[category_mapping_key] = {
                                        i: str(orig) for i, orig in enumerate(unique_original_values)
                                    }
                                    has_category_mappings = True
                            else:
                                # No original values available - use scaled values as fallback (not ideal but better than skipping)
                                self.logger.warning(f"⚠️ No original values available for {feature}, using scaled values as categories (not ideal)")
                                unique_values = sorted(feature_values.dropna().unique())
                                category_mappings[category_mapping_key] = {float(v): str(v) for v in unique_values}
                                has_category_mappings = True
                        else:
                            # Non-numeric categorical without mappings - try to get original values from X_test_original
                            # Try both feature name and original feature name
                            original_feature_name_for_lookup = category_mapping_key if category_mapping_key != feature else feature
                            
                            # Try to find original feature in X_test_original
                            found_in_original = False
                            lookup_col = None
                            if X_test_original is not None:
                                # Try original feature name first
                                if original_feature_name_for_lookup in X_test_original.columns:
                                    found_in_original = True
                                    lookup_col = original_feature_name_for_lookup
                                elif feature in X_test_original.columns:
                                    found_in_original = True
                                    lookup_col = feature
                                elif preprocessed_columns:
                                    # Try reverse lookup
                                    for orig_name, preproc_name in preprocessed_columns.items():
                                        if preproc_name == feature and orig_name in X_test_original.columns:
                                            found_in_original = True
                                            lookup_col = orig_name
                                            category_mapping_key = orig_name
                                            variable_name_for_segments = orig_name  # Use original name for segments
                                            break
                            
                            if found_in_original:
                                # Use original string values directly as categories
                                self.logger.info(f"📊 Non-numeric categorical feature '{feature}' has no category mappings - using ORIGINAL string values from X_test_original (column: '{lookup_col}')")
                                original_categorical_values = X_test_original[lookup_col].astype(str)
                                unique_original_values = sorted(original_categorical_values.dropna().unique())
                                
                                # Create mapping: scaled_value -> original_string_value
                                # Since we don't have direct mapping, we'll use the unique scaled values and map them by position
                                unique_scaled_values = sorted(feature_values.dropna().unique())
                                
                                if len(unique_scaled_values) == len(unique_original_values):
                                    # Perfect match: create direct mapping
                                    category_mappings[category_mapping_key] = {
                                        float(scaled): str(orig) 
                                        for scaled, orig in zip(unique_scaled_values, unique_original_values)
                                    }
                                    self.logger.info(f"Created category mapping for {feature} (key: {category_mapping_key}): {len(category_mappings[category_mapping_key])} categories from original string values")
                                    has_category_mappings = True
                                else:
                                    # Mismatch: use original values indexed by position
                                    self.logger.warning(f"Scaled/original value count mismatch for {feature}: {len(unique_scaled_values)} scaled vs {len(unique_original_values)} original")
                                    category_mappings[category_mapping_key] = {
                                        i: str(orig) for i, orig in enumerate(unique_original_values)
                                    }
                                    has_category_mappings = True
                            else:
                                # FALLBACK: Create category mappings from current values (even if scaled)
                                # This ensures we still generate data even without perfect mappings
                                self.logger.warning(f"⚠️ No original values available for '{feature}', creating fallback category mappings from current values")
                                unique_values = sorted(feature_values.dropna().unique())
                                if len(unique_values) > 0:
                                    # Create simple mapping: value -> str(value)
                                    category_mappings[category_mapping_key] = {
                                        float(val) if pd.api.types.is_numeric_dtype(type(val)) else val: str(val)
                                        for val in unique_values
                                    }
                                    has_category_mappings = True
                                    self.logger.info(f"Created fallback category mapping for {feature} (key: {category_mapping_key}): {len(category_mappings[category_mapping_key])} categories")
                                else:
                                    # Don't skip - let final fallback handle this
                                    self.logger.warning(f"⚠️ No unique values for '{feature}', will use final fallback")
                                    # Set a flag to indicate we need to use final fallback
                                    has_category_mappings = False
                                    # Skip to final fallback by setting num_categories to 0
                                    num_categories = 0
                                    original_categories_list = []
                    
                    # CRITICAL: If we have original_feature_values with actual category names, use them DIRECTLY
                    # This bypasses the need for category_mappings and creates segments immediately
                    # Also try X_test_original directly if original_feature_values wasn't found OR if it equals feature_values
                    # CRITICAL FIX: For test data, always try X_test_original lookup for categorical variables, especially home_ownership
                    if (original_feature_values is None or (original_feature_values is not None and original_feature_values.equals(feature_values))) and X_test_original is not None and is_categorical:
                        # DIAGNOSTIC: Log what's in X_test_original for home_ownership
                        if 'home_ownership' in feature.lower():
                            self.logger.info(f"🔍 DIAGNOSTIC for {feature}:")
                            self.logger.info(f"   X_test_original is not None: {X_test_original is not None}")
                            if X_test_original is not None:
                                self.logger.info(f"   X_test_original columns: {list(X_test_original.columns)[:10]}")
                                if 'home_ownership' in X_test_original.columns:
                                    unique_vals = X_test_original['home_ownership'].unique()[:5]
                                    self.logger.info(f"   ✅ home_ownership in X_test_original! Sample values: {unique_vals}")
                                else:
                                    self.logger.warning(f"   ⚠️ home_ownership NOT in X_test_original columns!")
                        # Try to get original values directly from X_test_original
                        # Enhanced lookup with multiple strategies, especially for home_ownership
                        lookup_col = None
                        
                        # Strategy 1: Direct match with feature name
                        if feature in X_test_original.columns:
                            lookup_col = feature
                            self.logger.debug(f"✅ Found {feature} directly in X_test_original")
                        
                        # Strategy 2: Match with category_mapping_key (original name)
                        elif category_mapping_key and category_mapping_key in X_test_original.columns:
                            lookup_col = category_mapping_key
                            self.logger.debug(f"✅ Found {category_mapping_key} in X_test_original (original name)")
                        
                        # Strategy 3: For home_ownership specifically, try exact match
                        elif is_home_ownership and 'home_ownership' in X_test_original.columns:
                            lookup_col = 'home_ownership'
                            self.logger.info(f"✅ Found 'home_ownership' directly in X_test_original columns")
                        
                        # Strategy 4: Preprocessed columns reverse lookup
                        elif preprocessed_columns:
                            for orig_name, preproc_name in preprocessed_columns.items():
                                if preproc_name == feature and orig_name in X_test_original.columns:
                                    lookup_col = orig_name
                                    self.logger.debug(f"✅ Found {orig_name} via preprocessed_columns reverse lookup")
                                    break
                        
                        # Strategy 5: Remove encoding suffixes
                        elif feature.endswith('_le_auto') or feature.endswith('_le_manual') or feature.endswith('_le_model'):
                            potential_orig = feature.rsplit('_le_', 1)[0] if '_le_' in feature else feature
                            if potential_orig in X_test_original.columns:
                                lookup_col = potential_orig
                                self.logger.debug(f"✅ Found {potential_orig} by removing suffix from {feature}")
                        
                        # Strategy 6: Case-insensitive search for home_ownership
                        elif is_home_ownership:
                            for col in X_test_original.columns:
                                if 'home_ownership' in col.lower():
                                    lookup_col = col
                                    self.logger.info(f"✅ Found home_ownership via case-insensitive match: '{col}'")
                                    break
                        
                        if lookup_col:
                            # CRITICAL: Align indices with X_test to ensure mask alignment with y_test/y_pred
                            original_feature_series = X_test_original[lookup_col]
                            
                            # Try to align indices with X_test
                            if len(original_feature_series) == len(X_test):
                                # Same length - try positional alignment first
                                original_feature_values = original_feature_series.reset_index(drop=True)
                                original_feature_values.index = X_test.index
                                self.logger.debug(f"✅ Used positional alignment for lookup_col '{lookup_col}' (lengths match)")
                            else:
                                # Try reindex
                                original_feature_values = original_feature_series.reindex(X_test.index, fill_value=None)
                                if original_feature_values.isna().all():
                                    # Fallback: try common indices
                                    common_indices = X_test.index.intersection(original_feature_series.index)
                                    if len(common_indices) > 0:
                                        original_feature_values = original_feature_series.loc[common_indices].reindex(X_test.index)
                                        self.logger.warning(f"⚠️ Used common indices alignment for '{lookup_col}' ({len(common_indices)} common indices)")
                                    else:
                                        self.logger.warning(f"⚠️ Could not align indices for '{lookup_col}' - using as-is (may cause issues)")
                                        original_feature_values = original_feature_series
                            
                            original_column_name = lookup_col  # Store original column name
                            lookup_col_for_variable = lookup_col  # Store for use in variable name assignment
                            # CRITICAL: Mark that we found this feature in X_test_original
                            # This is especially important for home_ownership in TRAIN data
                            found_in_x_test_original = True
                            self.logger.info(f"✅✅✅ Found original values for {feature} in X_test_original (column: '{lookup_col}', {len(original_feature_values)} values, {len(original_feature_values.dropna())} non-null)")
                            # Log sample values for categorical variables
                            unique_vals = original_feature_values.dropna().unique()[:5]
                            self.logger.info(f"   Sample original values: {unique_vals}")
                            # Special logging for home_ownership
                            if is_home_ownership:
                                unique_count = original_feature_values.nunique()
                                value_counts = original_feature_values.value_counts(dropna=False)
                                self.logger.info(f"   ✅✅✅ home_ownership: Found in X_test_original, dtype={original_feature_values.dtype}")
                                self.logger.info(f"   DISTINCT VALUES COUNT: {unique_count}")
                                self.logger.info(f"   All unique values: {sorted(original_feature_values.dropna().unique().astype(str))}")
                                self.logger.info(f"   Value distribution (count per category):")
                                for val, count in value_counts.items():
                                    self.logger.info(f"      '{val}': {count} ({count/len(original_feature_values)*100:.1f}%)")
                                if is_train_data:
                                    self.logger.info(f"   ✅✅✅ TRAIN DATA: home_ownership found in X_test_original - will use direct path")
                        else:
                            # Log warning for any categorical variable that can't be found
                            self.logger.warning(f"⚠️ Could not find lookup column for {feature} (category_mapping_key: {category_mapping_key}) in X_test_original")
                            if X_test_original is not None:
                                self.logger.warning(f"   Available columns: {list(X_test_original.columns)}")
                            # If we couldn't find it in X_test_original and original_feature_values is None, set fallback
                            if original_feature_values is None:
                                original_feature_values = feature_values
                                self.logger.debug(f"⚠️ Using current values for categorical {feature} as fallback (original not found in X_test_original)")
                    
                    # CRITICAL FIX: For train data and home_ownership, use direct path even if values appear the same
                    # Check if we have original_feature_values with category names (object/string dtype)
                    # Ensure found_in_x_test_original is True if lookup_col_for_variable is set
                    if lookup_col_for_variable is not None:
                        found_in_x_test_original = True
                    
                    # CRITICAL: If home_ownership was taken directly from X_test_original (not in X_test.columns),
                    # we already set lookup_col_for_variable and original_feature_values above.
                    # But we need to ensure found_in_x_test_original is True in that case.
                    # Check if lookup_col_for_variable was set when feature was taken from X_test_original
                    if lookup_col_for_variable is not None and lookup_col_for_variable == feature:
                        # This feature was taken from X_test_original directly (see line 1199)
                        found_in_x_test_original = True
                        if is_home_ownership:
                            self.logger.info(f"✅✅✅ home_ownership was taken from X_test_original directly (lookup_col='{lookup_col_for_variable}') - setting found_in_x_test_original=True")
                    
                    # CRITICAL FIX FOR TRAIN DATA: If home_ownership is in X_test_original but we haven't found it yet,
                    # try to find it directly (this handles cases where feature name doesn't match)
                    # OR if is_train_data=True, always try to get home_ownership from X_test_original
                    if is_home_ownership and X_test_original is not None and (not found_in_x_test_original or original_feature_values is None or is_train_data):
                        if 'home_ownership' in X_test_original.columns:
                            # We found home_ownership in X_test_original - use it directly
                            lookup_col_for_variable = 'home_ownership'
                            found_in_x_test_original = True
                            # Get the values with proper index alignment
                            original_feature_series = X_test_original['home_ownership']
                            if len(original_feature_series) == len(X_test):
                                original_feature_values = original_feature_series.reset_index(drop=True)
                                original_feature_values.index = X_test.index
                                self.logger.info(f"✅✅✅ CRITICAL FIX: Found home_ownership directly in X_test_original for TRAIN data (positional alignment, {len(original_feature_values)} values, is_train_data={is_train_data})")
                            else:
                                original_feature_values = original_feature_series.reindex(X_test.index, fill_value=None)
                                reindex_success = (1 - original_feature_values.isna().sum() / len(original_feature_values)) * 100 if len(original_feature_values) > 0 else 0
                                self.logger.info(f"✅✅✅ CRITICAL FIX: Found home_ownership directly in X_test_original for TRAIN data (reindex alignment, {len(original_feature_values)} values, {reindex_success:.1f}% success, is_train_data={is_train_data})")
                            
                            # Log the values we found
                            if original_feature_values is not None:
                                unique_vals = sorted(original_feature_values.dropna().unique().astype(str))
                                self.logger.info(f"   ✅✅✅ home_ownership unique values: {unique_vals}")
                                if is_train_data:
                                    self.logger.info(f"   ✅✅✅ TRAIN DATA: home_ownership will use direct path for segmentation")
                    
                    if original_feature_values is not None:
                        # Check if original values are strings/objects (category names)
                        is_object_dtype = original_feature_values.dtype == 'object' or pd.api.types.is_string_dtype(original_feature_values)
                        # CRITICAL: For TRAIN data, feature_values might be the same as original_feature_values (both from X_test_original)
                        # So we can't rely on values_different. Instead, check if we found it in X_test_original
                        try:
                            # Reset indices for comparison to avoid index mismatch issues
                            orig_reset = original_feature_values.reset_index(drop=True)
                            feat_reset = feature_values.reset_index(drop=True)
                            values_different = not orig_reset.equals(feat_reset)
                        except:
                            # If equals() fails, assume they're different
                            values_different = True
                        
                        # CRITICAL: If we found the column in X_test_original (lookup_col_for_variable is set),
                        # we should ALWAYS use direct path for categorical variables, regardless of value differences
                        # This is especially important for train data where values might appear the same
                        # Also handle numeric original values for categorical features (convert to string)
                        should_use_direct_path = found_in_x_test_original or values_different or (is_object_dtype or not pd.api.types.is_numeric_dtype(original_feature_values))
                        
                        # Special handling for home_ownership: always use direct path if found in X_test_original OR if is_train_data
                        # This ensures home_ownership segments are created for TRAIN data even if values appear the same
                        if is_home_ownership and (found_in_x_test_original or is_train_data):
                            should_use_direct_path = True
                            self.logger.info(f"✅✅✅ Using direct path for home_ownership because found_in_x_test_original={found_in_x_test_original} OR is_train_data={is_train_data} (lookup_col='{lookup_col_for_variable}')")
                        
                        # CRITICAL: For TRAIN data and home_ownership, if we have original_feature_values, ALWAYS use direct path
                        # This is a final safeguard to ensure segments are created
                        if is_home_ownership and is_train_data and original_feature_values is not None:
                            should_use_direct_path = True
                            self.logger.info(f"✅✅✅ FINAL SAFEGUARD: Forcing direct path for home_ownership in TRAIN data (original_feature_values available)")
                        
                        if should_use_direct_path:
                            # We have original category names - use them directly!
                            # Convert to string to handle numeric categorical values
                            unique_original_cats = sorted(original_feature_values.dropna().astype(str).unique())
                            if len(unique_original_cats) > 0:
                                log_prefix = "🔍 DIRECT PATH for home_ownership" if is_home_ownership else f"🔍 DIRECT PATH for categorical {feature}"
                                self.logger.info(f"{log_prefix}:")
                                self.logger.info(f"   unique_original_cats: {len(unique_original_cats)} categories")
                                self.logger.info(f"   is_train_data: {is_train_data}")
                                self.logger.info(f"   original_feature_values length: {len(original_feature_values)}")
                                self.logger.info(f"   y_test length: {len(y_test)}")
                                self.logger.info(f"   y_pred length: {len(y_pred)}")
                                if is_home_ownership:
                                    self.logger.info(f"   ✅✅✅ home_ownership categories: {unique_original_cats}")
                                
                                # CRITICAL: For home_ownership, ALWAYS use 'home_ownership' as variable name
                                if is_home_ownership:
                                    variable_name_for_segment = 'home_ownership'
                                else:
                                    variable_name_for_segment = lookup_col_for_variable if lookup_col_for_variable else (category_mapping_key if category_mapping_key != feature else feature)
                                
                                num_cats = len(unique_original_cats)
                                
                                # Create 5 segments by grouping categories (like continuous variables)
                                # This matches the auto training behavior
                                num_segments = 5
                                if num_cats < num_segments:
                                    num_segments = num_cats
                                
                                self.logger.info(f"✅✅✅ DIRECT PATH: Creating {num_segments} grouped segments for {feature} ({num_cats} categories)")
                                
                                # Calculate how many categories per segment
                                cats_per_segment = num_cats / num_segments
                                
                                for segment_idx in range(num_segments):
                                    # Calculate which categories belong to this segment
                                    start_cat_idx = int(segment_idx * cats_per_segment)
                                    end_cat_idx = int((segment_idx + 1) * cats_per_segment) if segment_idx < num_segments - 1 else num_cats
                                    segment_categories = unique_original_cats[start_cat_idx:end_cat_idx]
                                    
                                    if not segment_categories:
                                        continue
                                    
                                    # Create mask for all categories in this segment
                                    mask = original_feature_values.astype(str).isin([str(c) for c in segment_categories])
                                    
                                    # TRAIN DATA FIX ONLY: Align mask indices with y_test for train data
                                    if is_train_data and not mask.index.equals(y_test.index):
                                        mask = mask.reindex(y_test.index, fill_value=False)
                                    
                                    sample_count = int(mask.sum())
                                    
                                    if sample_count < 2:
                                        self.logger.debug(f"Skipping segment {segment_idx + 1} for {feature}: only {sample_count} samples")
                                        continue
                                    
                                    try:
                                        if is_train_data:
                                            y_test_segment = y_test[mask]
                                            y_pred_segment = y_pred[mask] if isinstance(y_pred, (pd.Series, np.ndarray)) else np.array(y_pred)[mask.values if hasattr(mask, 'values') else mask]
                                        else:
                                            y_test_segment = y_test[mask]
                                            y_pred_segment = y_pred[mask]
                                        
                                        if len(y_test_segment) < 2:
                                            continue
                                        
                                        segment_accuracy = accuracy_score(y_test_segment, y_pred_segment)
                                        segment_precision = precision_score(
                                            y_test_segment, y_pred_segment, average='weighted', zero_division=0
                                        )
                                        segment_recall = recall_score(
                                            y_test_segment, y_pred_segment, average='weighted', zero_division=0
                                        )
                                        segment_f1 = f1_score(
                                            y_test_segment, y_pred_segment, average='weighted', zero_division=0
                                        )
                                        segment_cm = confusion_matrix(y_test_segment, y_pred_segment)
                                        
                                        # Create range label like continuous variables (e.g., "A to C" instead of "A, B, C")
                                        first_cat = str(segment_categories[0])
                                        last_cat = str(segment_categories[-1])
                                        if first_cat == last_cat:
                                            range_str = first_cat
                                        else:
                                            range_str = f"{first_cat} to {last_cat}"
                                        
                                        segment_label = f"Segment {segment_idx + 1}"
                                        
                                        self.logger.info(f"  ✅ Created segment {segment_idx + 1}: '{range_str}' ({sample_count} samples)")
                                        
                                        granular_data.append({
                                            'variable': variable_name_for_segment,
                                            'segment': segment_label,
                                            'granularity_level': f'{num_segments}_segments',
                                            'accuracy': safe_float(segment_accuracy),
                                            'precision': safe_float(segment_precision),
                                            'recall': safe_float(segment_recall),
                                            'f1_score': safe_float(segment_f1),
                                            'sample_count': sample_count,
                                            'confusion_matrix': segment_cm.tolist(),
                                            'value_range': range_str,  # Use value_range like continuous variables
                                            'is_continuous': False
                                        })
                                        
                                        self.logger.info(f"  ✅✅✅ Created segment for variable '{variable_name_for_segment}': {range_str} ({sample_count} samples)")
                                    except Exception as e:
                                        self.logger.warning(f"Error creating segment for {feature}: {str(e)}")
                                
                                # Skip the normal processing since we already created segments
                                continue
                            else:
                                self.logger.warning(f"⚠️ DIRECT PATH triggered for {feature} but no unique categories found! original_feature_values length: {len(original_feature_values) if original_feature_values is not None else 0}")
                        else:
                            if is_home_ownership:
                                self.logger.warning(f"⚠️ DIRECT PATH NOT triggered for home_ownership! should_use_direct_path={should_use_direct_path}, found_in_x_test_original={found_in_x_test_original}, values_different={values_different}, is_object_dtype={is_object_dtype if 'is_object_dtype' in locals() else 'N/A'}, is_train_data={is_train_data}")
                    
                    # Only proceed with normal processing if we have category mappings
                    # Use category_mapping_key (which might be the original feature name) to look up mappings
                    if has_category_mappings and category_mapping_key in category_mappings:
                        # Mark that we're processing this categorical feature
                        processed_categorical_features.append(feature)
                        self.logger.info(f"📊 Processing categorical feature '{feature}' (mapping key: '{category_mapping_key}') with original category names")
                        
                        # Get all original category names from category_mappings (these are the TRUE categories)
                        # category_mappings format: {encoded_int: original_name} or {numeric_value: string_value}
                        original_categories_list = sorted([str(cat) for cat in category_mappings[category_mapping_key].values()])
                        num_categories = len(original_categories_list)
                    
                        self.logger.info(f"Categorical feature {feature}: {num_categories} original categories from mappings: {original_categories_list}")
                        
                        if num_categories < 1:
                            # FALLBACK: Try to use unique values directly as categories
                            unique_vals = feature_values.dropna().unique()
                            if len(unique_vals) > 0:
                                self.logger.warning(f"⚠️ No categories from mappings for '{feature}', using unique values directly as fallback")
                                original_categories_list = [str(v) for v in sorted(unique_vals)]
                                num_categories = len(original_categories_list)
                                # Create temporary mapping (use category_mapping_key if available, otherwise feature)
                                category_mappings[category_mapping_key] = {i: str(v) for i, v in enumerate(sorted(unique_vals))}
                                has_category_mappings = True
                            else:
                                # No unique values - will use final fallback
                                self.logger.warning(f"⚠️ No categories for '{feature}', will use final fallback")
                                num_categories = 0
                                original_categories_list = []
                        
                        # Only proceed with scaled value mapping if we have categories
                        if num_categories > 0:
                            # Get unique scaled values in the data
                            value_counts = feature_values.value_counts()
                            if value_counts.empty:
                                # Empty value_counts - will use final fallback
                                self.logger.warning(f"⚠️ Empty value_counts for '{feature}', will use final fallback")
                                num_categories = 0
                                original_categories_list = []
                            else:
                                unique_scaled_values = list(value_counts.index)
                                num_unique_scaled = len(unique_scaled_values)
                        else:
                            # num_categories is 0 - skip to final fallback
                            unique_scaled_values = []
                            num_unique_scaled = 0
                    
                    # Only proceed with scaled-to-original mapping if we have categories and scaled values
                    scaled_to_original = {}
                    if num_categories > 0 and num_unique_scaled > 0:
                        # Map scaled values to original categories
                        # Strategy: Since StandardScaler centers data, encoded integers (0,1,2...) when scaled
                        # will be distributed in order. We'll sort the unique scaled values and assign them
                        # to categories in the order they appear in category_mappings
                        sorted_scaled = sorted(unique_scaled_values)
                        
                        # Create mapping: scaled_value -> original_category
                        
                        # Check if category_mappings keys are scaled values (for numeric categorical) or encoded ints (for label-encoded)
                        # Use category_mapping_key (which might be the original feature name)
                        mapping_keys = list(category_mappings[category_mapping_key].keys())
                        first_key = mapping_keys[0] if mapping_keys else None
                        
                        # If keys are floats (scaled values), use direct mapping
                        if isinstance(first_key, (float, np.floating)) and not isinstance(first_key, (int, np.integer)):
                            # Numeric categorical: keys are scaled values, values are original values (as strings)
                            for scaled_val in unique_scaled_values:
                                # Find closest key (scaled value) in category_mappings
                                closest_key = min(mapping_keys, key=lambda k: abs(float(k) - float(scaled_val)))
                                original_cat = category_mappings[category_mapping_key][closest_key]
                                scaled_to_original[scaled_val] = original_cat
                        else:
                            # Label-encoded categorical: keys are encoded ints, need to map scaled values to encoded ints first
                            encoded_ints = sorted(category_mappings[category_mapping_key].keys())
                            
                            # Assign each unique scaled value to the closest encoded integer
                            # Then map that to the original category
                            for scaled_val in unique_scaled_values:
                                # Find which encoded integer this scaled value most likely corresponds to
                                # We'll use the index in the sorted list as a proxy
                                if num_unique_scaled == num_categories:
                                    # Perfect match: same number of unique values as categories
                                    idx = sorted_scaled.index(scaled_val)
                                    if idx < len(encoded_ints):
                                        encoded_int = encoded_ints[idx]
                                        original_cat = category_mappings[category_mapping_key][encoded_int]
                                        scaled_to_original[scaled_val] = original_cat
                                else:
                                    # More complex: need to cluster scaled values
                                    # Use the fact that scaled values are distributed around encoded integers
                                    # Find the closest encoded integer by checking the distribution
                                    best_encoded = encoded_ints[0]
                                    min_distance = float('inf')
                                    
                                    # Calculate mean/std of scaled values to help with mapping
                                    scaled_mean = np.mean(sorted_scaled)
                                    scaled_std = np.std(sorted_scaled) if len(sorted_scaled) > 1 else 1.0
                                    
                                    # Map scaled value to encoded integer based on position in distribution
                                    for i, encoded_int in enumerate(encoded_ints):
                                        # Expected scaled value would be around (i - mean) / std
                                        # But we'll use percentile-based mapping instead
                                        percentile = (i + 0.5) / len(encoded_ints)
                                        expected_scaled = np.percentile(sorted_scaled, percentile * 100)
                                        distance = abs(scaled_val - expected_scaled)
                                        
                                        if distance < min_distance:
                                            min_distance = distance
                                            best_encoded = encoded_int
                                    
                                    original_cat = category_mappings[category_mapping_key][best_encoded]
                                    scaled_to_original[scaled_val] = original_cat
                        
                        self.logger.info(f"Mapped {len(scaled_to_original)} scaled values to original categories: {set(scaled_to_original.values())}")
                    else:
                        self.logger.warning(f"⚠️ Cannot create scaled-to-original mapping for {feature}: num_categories={num_categories}, num_unique_scaled={num_unique_scaled}")
                    
                    # ALWAYS create ONE SEGMENT PER ORIGINAL CATEGORY for categorical variables
                    # Each category becomes its own segment
                    self.logger.info(f"Categorical feature {feature}: {num_categories} original categories (one segment per category)")
                    
                    # Create segments based on ORIGINAL categories only - one segment per category
                    # CRITICAL: If we have original_feature_values with actual category names, use them directly
                    # Check if original_feature_values contains actual category names (not encoded/scaled values)
                    use_direct_original_values = False
                    if original_feature_values is not None:
                        # Check if original values are different from current values (not encoded/scaled)
                        values_different = not original_feature_values.equals(feature_values)
                        # Check if original values are strings/objects (category names) or if they're numeric but different
                        is_object_dtype = original_feature_values.dtype == 'object' or pd.api.types.is_string_dtype(original_feature_values)
                        
                        if values_different and is_object_dtype:
                            use_direct_original_values = True
                            self.logger.info(f"✅ Will use direct original values for {feature} (object dtype, different from encoded values)")
                        elif values_different and not pd.api.types.is_numeric_dtype(original_feature_values):
                            # Non-numeric and different - likely original category names
                            use_direct_original_values = True
                            self.logger.info(f"✅ Will use direct original values for {feature} (non-numeric, different from encoded values)")
                        else:
                            self.logger.debug(f"Not using direct original values for {feature}: values_different={values_different}, is_object={is_object_dtype}, dtype={original_feature_values.dtype}")
                    
                    # FALLBACK: If scaled_to_original mapping is empty, try to use original_feature_values directly
                    if len(scaled_to_original) == 0 and original_feature_values is not None:
                        # Check if we should use direct original values (even if dtype check failed)
                        if not use_direct_original_values:
                            self.logger.warning(f"⚠️ scaled_to_original mapping is empty for {feature}, trying to use original_feature_values directly")
                            # Try to create segments from original values directly
                            unique_original_vals = original_feature_values.dropna().unique()
                            if len(unique_original_vals) > 0:
                                # Create a simple mapping: use original values as categories
                                original_categories_list = [str(v) for v in sorted(unique_original_vals)]
                                num_categories = len(original_categories_list)
                                self.logger.info(f"✅ Using {num_categories} unique original values as categories for {feature}")
                                # Mark that we should use direct original values
                                use_direct_original_values = True
                    
                    # Only try to create segments if we have categories
                    if use_direct_original_values and len(original_categories_list) > 0:
                        self.logger.info(f"✅ Using direct original category values for {feature} - will create segments directly from original values")
                        # Use original values directly - much simpler and more reliable
                        for segment_idx, original_category in enumerate(original_categories_list):
                            # Create mask directly from original values
                            mask = original_feature_values == original_category
                            sample_count = int(mask.sum())
                            
                            if sample_count < 2:
                                self.logger.warning(f"Skipping {original_category} for {feature}: only {sample_count} samples")
                                continue
                            
                            try:
                                segment_accuracy = accuracy_score(y_test[mask], y_pred[mask])
                                segment_precision = precision_score(
                                    y_test[mask], y_pred[mask], average='weighted', zero_division=0
                                )
                                segment_recall = recall_score(
                                    y_test[mask], y_pred[mask], average='weighted', zero_division=0
                                )
                                segment_f1 = f1_score(
                                    y_test[mask], y_pred[mask], average='weighted', zero_division=0
                                )
                                segment_cm = confusion_matrix(y_test[mask], y_pred[mask])
                                
                                category_str = original_category
                                if len(category_str) > 30:
                                    category_str = category_str[:27] + "..."
                                segment_label = f"Segment {segment_idx + 1} ({category_str})"
                                
                                self.logger.info(f"  Segment {segment_idx + 1}: '{original_category}' (from original values, {sample_count} samples)")
                                
                                granular_data.append({
                                    'variable': variable_name_for_segments,  # Use original name so UI can find it
                                    'segment': segment_label,
                                    'granularity_level': f'{num_categories}_segments',
                                    'accuracy': safe_float(segment_accuracy),
                                    'precision': safe_float(segment_precision),
                                    'recall': safe_float(segment_recall),
                                    'f1_score': safe_float(segment_f1),
                                    'sample_count': sample_count,
                                    'confusion_matrix': segment_cm.tolist(),
                                    'category_value': original_category,  # Store original category name (not encoded/scaled)
                                    'is_continuous': False  # Explicitly mark as categorical
                                })
                                
                                self.logger.info(f"  ✅ Created segment for variable '{variable_name_for_segments}' (feature: '{feature}'): '{original_category}' ({sample_count} samples)")
                            except Exception as e:
                                self.logger.warning(f"Error calculating metrics for {feature}={original_category}: {str(e)}")
                                import traceback
                                self.logger.debug(f"Traceback: {traceback.format_exc()}")
                    elif len(original_categories_list) > 0:
                        # Fallback: Use scaled value mapping (for encoded categoricals)
                        self.logger.info(f"Using scaled value mapping for {feature} (encoded categorical)")
                        for segment_idx, original_category in enumerate(original_categories_list):
                            # Find all scaled values that map to this original category
                            scaled_values_for_category = [
                                scaled_val for scaled_val, orig_cat in scaled_to_original.items()
                                if orig_cat == original_category
                            ]
                            
                            if not scaled_values_for_category:
                                # FALLBACK: If no mapping found, try to use original_feature_values if available
                                if original_feature_values is not None and not original_feature_values.equals(feature_values):
                                    # Try direct match with original values
                                    try:
                                        mask = original_feature_values.astype(str) == str(original_category)
                                        sample_count = int(mask.sum())
                                        if sample_count >= 2:
                                            self.logger.info(f"✅ Found {sample_count} samples for '{original_category}' using direct original value match")
                                        else:
                                            self.logger.warning(f"No samples found for '{original_category}' in {feature} (tried direct match)")
                                            continue
                                    except:
                                        self.logger.warning(f"No scaled values mapped to '{original_category}' for {feature} and direct match failed")
                                        continue
                                else:
                                    self.logger.warning(f"No scaled values mapped to '{original_category}' for {feature}")
                                    continue
                            else:
                                # Create mask using scaled values
                                mask = feature_values.isin(scaled_values_for_category)
                                sample_count = int(mask.sum())
                            
                            if sample_count < 2:
                                self.logger.warning(f"Skipping {original_category} for {feature}: only {sample_count} samples")
                                continue
                        
                            try:
                                segment_accuracy = accuracy_score(y_test[mask], y_pred[mask])
                                segment_precision = precision_score(
                                    y_test[mask], y_pred[mask], average='weighted', zero_division=0
                                )
                                segment_recall = recall_score(
                                    y_test[mask], y_pred[mask], average='weighted', zero_division=0
                                )
                                segment_f1 = f1_score(
                                    y_test[mask], y_pred[mask], average='weighted', zero_division=0
                                )
                                segment_cm = confusion_matrix(y_test[mask], y_pred[mask])
                                
                                category_str = original_category
                                if len(category_str) > 30:
                                    category_str = category_str[:27] + "..."
                                segment_label = f"Segment {segment_idx + 1} ({category_str})"
                                
                                if use_direct_original_values:
                                    self.logger.info(f"  Segment {segment_idx + 1}: '{original_category}' (from original values, {sample_count} samples)")
                                else:
                                    scaled_vals_str = str(scaled_values_for_category[:3]) if 'scaled_values_for_category' in locals() else 'N/A'
                                    self.logger.info(f"  Segment {segment_idx + 1}: '{original_category}' (from scaled values: {scaled_vals_str}, {sample_count} samples)")
                                
                                granular_data.append({
                                    'variable': feature,
                                    'segment': segment_label,
                                    'granularity_level': f'{num_categories}_segments',
                                    'accuracy': safe_float(segment_accuracy),
                                    'precision': safe_float(segment_precision),
                                    'recall': safe_float(segment_recall),
                                    'f1_score': safe_float(segment_f1),
                                    'sample_count': sample_count,
                                    'confusion_matrix': segment_cm.tolist(),
                                    'category_value': original_category,  # Store original category name (not encoded/scaled)
                                    'is_continuous': False  # Explicitly mark as categorical
                                })
                            except Exception as e:
                                self.logger.warning(f"Error calculating metrics for {feature}={original_category}: {str(e)}")
                                import traceback
                                self.logger.debug(f"Traceback: {traceback.format_exc()}")
                    
                    # FINAL FALLBACK: If no segments were created for this feature (categorical or continuous), try using unique values directly
                    # This MUST run for every feature, even if normal processing failed
                    # CRITICAL: Enhanced fallback similar to date columns - always try to create segments
                    feature_segments = [item for item in granular_data if item['variable'] == feature or item.get('variable') == feature]
                    if len(feature_segments) == 0:
                        # Try fallback for both categorical and continuous
                        if is_categorical:
                            self.logger.warning(f"⚠️⚠️⚠️ FINAL FALLBACK TRIGGERED for categorical {feature}: No segments created")
                            self.logger.warning(f"   num_categories={num_categories if 'num_categories' in locals() else 'N/A'}, original_categories_list length={len(original_categories_list) if 'original_categories_list' in locals() and original_categories_list else 0}")
                            self.logger.warning(f"   feature_values shape={feature_values.shape if hasattr(feature_values, 'shape') else 'N/A'}, unique count={feature_values.nunique() if hasattr(feature_values, 'nunique') else 'N/A'}")
                            self.logger.warning(f"   original_feature_values: {'Available' if original_feature_values is not None else 'None'}")
                            
                            try:
                                # CRITICAL: Try to use original_feature_values first if available (similar to date columns)
                                values_to_use = None
                                if original_feature_values is not None and not original_feature_values.equals(feature_values):
                                    values_to_use = original_feature_values
                                    self.logger.info(f"   Using original_feature_values for fallback ({len(values_to_use)} values)")
                                else:
                                    values_to_use = feature_values
                                    self.logger.info(f"   Using feature_values for fallback ({len(values_to_use)} values)")
                                
                                # Get unique values
                                unique_vals = values_to_use.dropna().unique()
                                self.logger.info(f"   Found {len(unique_vals)} unique values: {unique_vals[:10]}")
                                
                                if len(unique_vals) > 0:
                                    # Limit to reasonable number of segments (max 20)
                                    unique_vals_to_process = sorted(unique_vals)[:20] if len(unique_vals) > 20 else sorted(unique_vals)
                                    self.logger.info(f"Creating segments from {len(unique_vals_to_process)} unique values for {feature}")
                                    
                                    segments_created = 0
                                    for segment_idx, val in enumerate(unique_vals_to_process):
                                        # Create mask using the values we're using
                                        mask = values_to_use == val if values_to_use is not None else feature_values == val
                                        
                                        # TRAIN DATA FIX ONLY: Align mask indices with y_test for train data
                                        # DO NOT TOUCH TEST DATA - only apply this fix when is_train_data=True
                                        if is_train_data and not mask.index.equals(y_test.index):
                                            # For train data, reindex mask to match y_test indices
                                            mask = mask.reindex(y_test.index, fill_value=False)
                                            self.logger.debug(f"TRAIN DATA FALLBACK: Reindexed mask for {val} to match y_test indices")
                                        
                                        sample_count = int(mask.sum())
                                        
                                        if sample_count < 2:
                                            continue
                                        
                                        try:
                                            # For train data, ensure we use aligned data
                                            if is_train_data:
                                                # Ensure mask aligns with y_test and y_pred
                                                y_test_segment = y_test[mask]
                                                y_pred_segment = y_pred[mask] if isinstance(y_pred, (pd.Series, np.ndarray)) else np.array(y_pred)[mask.values if hasattr(mask, 'values') else mask]
                                            else:
                                                # TEST DATA: Use original approach (DO NOT CHANGE)
                                                y_test_segment = y_test[mask]
                                                y_pred_segment = y_pred[mask]
                                            
                                            # Verify we have enough samples
                                            if len(y_test_segment) < 2:
                                                continue
                                            
                                            segment_accuracy = accuracy_score(y_test_segment, y_pred_segment)
                                            segment_precision = precision_score(
                                                y_test_segment, y_pred_segment, average='weighted', zero_division=0
                                            )
                                            segment_recall = recall_score(
                                                y_test_segment, y_pred_segment, average='weighted', zero_division=0
                                            )
                                            segment_f1 = f1_score(
                                                y_test_segment, y_pred_segment, average='weighted', zero_division=0
                                            )
                                            segment_cm = confusion_matrix(y_test_segment, y_pred_segment)
                                            
                                            # Use value as category name
                                            category_str = str(val)
                                            if len(category_str) > 30:
                                                category_str = category_str[:27] + "..."
                                            segment_label = f"Segment {segment_idx + 1} ({category_str})"
                                            
                                            # Use original feature name if available from lookup
                                            # CRITICAL: For home_ownership, always use 'home_ownership' as variable name
                                            if is_home_ownership:
                                                variable_name = 'home_ownership'
                                            else:
                                                variable_name = lookup_col_for_variable if 'lookup_col_for_variable' in locals() and lookup_col_for_variable else feature
                                            
                                            granular_data.append({
                                                'variable': variable_name,
                                                'segment': segment_label,
                                                'granularity_level': f'{len(unique_vals_to_process)}_segments',
                                                'accuracy': safe_float(segment_accuracy),
                                                'precision': safe_float(segment_precision),
                                                'recall': safe_float(segment_recall),
                                                'f1_score': safe_float(segment_f1),
                                                'sample_count': sample_count,
                                                'confusion_matrix': segment_cm.tolist(),
                                                'category_value': category_str,
                                                'is_continuous': False
                                            })
                                            segments_created += 1
                                            self.logger.info(f"✅ Created fallback segment for {feature}: {category_str} ({sample_count} samples)")
                                        except Exception as e:
                                            self.logger.warning(f"Error creating fallback segment for {feature}={val}: {str(e)}")
                                    
                                    if segments_created > 0:
                                        self.logger.info(f"✅✅✅ Created {segments_created} fallback segments for categorical {feature}")
                                    else:
                                        self.logger.error(f"❌ Final fallback for categorical {feature}: No segments created (all had <2 samples)")
                                else:
                                    self.logger.error(f"❌ Final fallback for categorical {feature}: No unique values found")
                            except Exception as e:
                                self.logger.error(f"Final fallback failed for categorical {feature}: {str(e)}")
                                import traceback
                                self.logger.debug(f"Traceback: {traceback.format_exc()}")
                        elif not is_categorical:
                            # FINAL FALLBACK for continuous: Use feature_values directly to create segments
                            # CRITICAL: Enhanced fallback similar to date columns - always try to create segments
                            self.logger.warning(f"⚠️⚠️⚠️ FINAL FALLBACK TRIGGERED for continuous {feature}: No segments created")
                            self.logger.warning(f"   original_feature_values: {'Available' if original_feature_values is not None else 'None'}")
                            self.logger.warning(f"   feature_values dtype: {feature_values.dtype if hasattr(feature_values, 'dtype') else 'N/A'}")
                            
                            try:
                                # CRITICAL: Try to use original_feature_values first, fallback to feature_values
                                values_to_use = None
                                if original_feature_values is not None and len(original_feature_values) > 0:
                                    values_to_use = original_feature_values
                                    self.logger.info(f"   Using original_feature_values for continuous fallback")
                                elif pd.api.types.is_numeric_dtype(feature_values):
                                    values_to_use = feature_values
                                    self.logger.info(f"   Using feature_values for continuous fallback (original not available)")
                                
                                if values_to_use is not None:
                                    min_val = float(values_to_use.min())
                                    max_val = float(values_to_use.max())
                                    num_segments = 5
                                    
                                    self.logger.info(f"   Creating {num_segments} segments from values: min={min_val:.2f}, max={max_val:.2f}")
                                    
                                    if min_val == max_val:
                                        # All values are the same - create intervals around that value
                                        bin_edges = np.linspace(min_val - 0.5, max_val + 0.5, num_segments + 1)
                                        self.logger.info(f"   All values are {min_val}, creating intervals around this value")
                                    else:
                                        bin_edges = np.linspace(min_val, max_val, num_segments + 1)
                                    
                                    # Assign each value to an interval
                                    segment_indices = np.digitize(values_to_use, bin_edges[1:], right=True)
                                    segment_indices = np.clip(segment_indices, 0, num_segments - 1)
                                    
                                    segments_created = 0
                                    for segment_idx in range(num_segments):
                                        mask = segment_indices == segment_idx
                                        sample_count = int(mask.sum())
                                        
                                        if sample_count < 2:
                                            continue
                                        
                                        try:
                                            segment_accuracy = accuracy_score(y_test[mask], y_pred[mask])
                                            segment_precision = precision_score(
                                                y_test[mask], y_pred[mask], average='weighted', zero_division=0
                                            )
                                            segment_recall = recall_score(
                                                y_test[mask], y_pred[mask], average='weighted', zero_division=0
                                            )
                                            segment_f1 = f1_score(
                                                y_test[mask], y_pred[mask], average='weighted', zero_division=0
                                            )
                                            segment_cm = confusion_matrix(y_test[mask], y_pred[mask])
                                            
                                            # Create range label
                                            seg_min = float(bin_edges[segment_idx])
                                            seg_max = float(bin_edges[segment_idx + 1] if segment_idx < num_segments - 1 else max_val)
                                            
                                            if segment_idx == 0:
                                                value_range = f"≤{bin_edges[1]:.2f}"
                                            elif segment_idx == num_segments - 1:
                                                value_range = f">{bin_edges[segment_idx]:.2f}"
                                            else:
                                                if seg_min == int(seg_min) and seg_max == int(seg_max):
                                                    value_range = f"{int(seg_min)} to {int(seg_max)}"
                                                else:
                                                    value_range = f"{seg_min:.2f} to {seg_max:.2f}"
                                            
                                            segment_label = f"Segment {segment_idx + 1} ({value_range})"
                                            
                                            granular_data.append({
                                                'variable': feature,
                                                'segment': segment_label,
                                                'granularity_level': f'{num_segments}_segments',
                                                'accuracy': safe_float(segment_accuracy),
                                                'precision': safe_float(segment_precision),
                                                'recall': safe_float(segment_recall),
                                                'f1_score': safe_float(segment_f1),
                                                'sample_count': sample_count,
                                                'confusion_matrix': segment_cm.tolist(),
                                                'value_range': value_range,
                                                'min_value': safe_float(seg_min),
                                                'max_value': safe_float(seg_max),
                                                'is_continuous': True
                                            })
                                            segments_created += 1
                                            self.logger.info(f"✅ Created fallback continuous segment for {feature}: {value_range} ({sample_count} samples)")
                                        except Exception as e:
                                            self.logger.warning(f"Error creating fallback continuous segment for {feature} segment {segment_idx}: {str(e)}")
                                    
                                    if segments_created > 0:
                                        self.logger.info(f"✅✅✅ Created {segments_created} fallback segments for continuous {feature}")
                                    else:
                                        self.logger.error(f"❌ Final fallback for continuous {feature}: No segments created (all had <2 samples)")
                                else:
                                    self.logger.error(f"❌ Final fallback for continuous {feature}: No usable values available")
                            except Exception as e:
                                self.logger.error(f"Final fallback failed for continuous {feature}: {str(e)}")
                                import traceback
                                self.logger.debug(f"Traceback: {traceback.format_exc()}")
        
        except Exception as e:
            self.logger.error(f"❌ CRITICAL ERROR in _calculate_granular_accuracy: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            # Don't return empty - try to return whatever we have
        
        # FINAL SUMMARY: Log results for verification (especially for TRAIN data)
        data_type_label = "TRAIN" if is_train_data else "TEST"
        self.logger.info(f"📊 [{data_type_label}] Granular accuracy calculation complete:")
        self.logger.info(f"   - Total segments created: {len(granular_data)}")
        if granular_data:
            variables = set(item.get('variable') for item in granular_data if item.get('variable'))
            self.logger.info(f"   - Variables with segments: {sorted(list(variables))}")
            
            # Check for home_ownership specifically
            home_ownership_segments = [item for item in granular_data if item.get('variable') == 'home_ownership']
            if home_ownership_segments:
                self.logger.info(f"   ✅✅✅ [{data_type_label}] home_ownership: {len(home_ownership_segments)} segments created!")
                for seg in home_ownership_segments[:3]:  # Log first 3
                    self.logger.info(f"      - {seg.get('segment')}: {seg.get('sample_count')} samples, accuracy={seg.get('accuracy', 0):.3f}")
            else:
                self.logger.warning(f"   ⚠️⚠️⚠️ [{data_type_label}] home_ownership: NO segments found!")
                # Debug: check what variables were actually created
                if 'home_ownership' in str(variables).lower():
                    self.logger.warning(f"      (Note: Found similar variable names but not exact 'home_ownership')")
        else:
            self.logger.warning(f"   ⚠️ [{data_type_label}] No segments created at all!")
            if skipped_features:
                self.logger.warning(f"   - Skipped features: {list(skipped_features.keys())[:10]}")
        
        # Emergency fallback: if no segments created due to error, try to create at least one
        if len(granular_data) == 0:
            self.logger.warning(f"⚠️ No segments created, attempting emergency fallback")
            # Emergency fallback: create at least one segment from first feature
            if X_test is not None and len(X_test.columns) > 0 and len(y_test) > 0 and len(y_pred) > 0:
                try:
                    emergency_feature = X_test.columns[0]
                    emergency_values = X_test[emergency_feature]
                    if pd.api.types.is_numeric_dtype(emergency_values):
                        median_val = emergency_values.median()
                        mask = emergency_values <= median_val
                        if mask.sum() >= 2 and (~mask).sum() >= 2:
                            segment_accuracy_low = accuracy_score(y_test[mask], y_pred[mask])
                            segment_accuracy_high = accuracy_score(y_test[~mask], y_pred[~mask])
                            
                            for segment_idx, (m, label, acc) in enumerate([
                                (mask, "Low", segment_accuracy_low),
                                (~mask, "High", segment_accuracy_high)
                            ]):
                                granular_data.append({
                                    'variable': emergency_feature,
                                    'segment': f'Segment {segment_idx + 1} ({label})',
                                    'granularity_level': '2_segments',
                                    'accuracy': safe_float(acc),
                                    'precision': safe_float(0),
                                    'recall': safe_float(0),
                                    'f1_score': safe_float(0),
                                    'sample_count': int(m.sum()),
                                    'confusion_matrix': [[0, 0], [0, 0]],
                                    'is_continuous': True
                                })
                            self.logger.warning(f"✅ Created {len(granular_data)} emergency fallback segments for {emergency_feature}")
                except Exception as e2:
                    self.logger.error(f"Emergency fallback also failed: {str(e2)}")
        
        # Log summary of what was processed
        processed_features = set(item['variable'] for item in granular_data)
        continuous_features = set(item['variable'] for item in granular_data if item.get('is_continuous'))
        
        # Log skipped features if any
        if skipped_features:
            self.logger.warning(f"⚠️ Skipped {len(skipped_features)} features: {dict(list(skipped_features.items())[:5])}")
            if len(skipped_features) > 5:
                self.logger.warning(f"   ... and {len(skipped_features) - 5} more features were skipped")
        
        if len(granular_data) == 0:
            self.logger.error(f"❌ [{data_type_label}] No granular accuracy data generated! Reasons:")
            self.logger.error(f"   - Problem type: {problem_type} (only 'classification' is supported)")
            self.logger.error(f"   - Features in feature_names: {len(feature_names)}")
            self.logger.error(f"   - Features in X_test: {len(X_test.columns) if X_test is not None else 0}")
            self.logger.error(f"   - Features processed: {len(features_to_process) if 'features_to_process' in locals() else 0}")
            self.logger.error(f"   - Features skipped: {len(skipped_features)}")
            if skipped_features:
                self.logger.error(f"   - Skip reasons: {dict(list(skipped_features.items())[:10])}")
            self.logger.error(f"   - Category mappings available: {len(category_mappings) if category_mappings else 0}")
            self.logger.error(f"   - Column stats available: {len(column_stats) if column_stats else 0}")
            self.logger.error(f"   - X_test_original available: {X_test_original is not None}")
            if X_test_original is not None:
                self.logger.error(f"   - X_test_original shape: {X_test_original.shape}")
                self.logger.error(f"   - X_test_original columns: {list(X_test_original.columns)[:10]}")
            self.logger.error(f"   - y_test length: {len(y_test) if y_test is not None else 'None'}")
            self.logger.error(f"   - y_pred length: {len(y_pred) if y_pred is not None else 'None'}")
            
            # LAST RESORT: Try to generate at least one segment from any available feature
            if X_test is not None and len(X_test.columns) > 0:
                self.logger.warning(f"🔄 Attempting last-resort fallback: generating segments from first available feature")
                try:
                    fallback_feature = X_test.columns[0]
                    fallback_values = X_test[fallback_feature]
                    
                    # Create simple 2-segment split
                    if pd.api.types.is_numeric_dtype(fallback_values):
                        median_val = fallback_values.median()
                        mask_low = fallback_values <= median_val
                        mask_high = fallback_values > median_val
                        
                        for segment_idx, (mask, label) in enumerate([(mask_low, "Low"), (mask_high, "High")]):
                            if mask.sum() > 0:
                                try:
                                    segment_accuracy = accuracy_score(y_test[mask], y_pred[mask])
                                    segment_precision = precision_score(y_test[mask], y_pred[mask], average='weighted', zero_division=0)
                                    segment_recall = recall_score(y_test[mask], y_pred[mask], average='weighted', zero_division=0)
                                    segment_f1 = f1_score(y_test[mask], y_pred[mask], average='weighted', zero_division=0)
                                    segment_cm = confusion_matrix(y_test[mask], y_pred[mask])
                                    
                                    granular_data.append({
                                        'variable': fallback_feature,
                                        'segment': f"Segment {segment_idx + 1} ({label})",
                                        'granularity_level': '2_segments',
                                        'accuracy': safe_float(segment_accuracy),
                                        'precision': safe_float(segment_precision),
                                        'recall': safe_float(segment_recall),
                                        'f1_score': safe_float(segment_f1),
                                        'sample_count': int(mask.sum()),
                                        'confusion_matrix': segment_cm.tolist(),
                                        'is_continuous': True,
                                        'value_range': f"≤{median_val:.2f}" if segment_idx == 0 else f">{median_val:.2f}"
                                    })
                                    self.logger.info(f"✅ Generated fallback segment for {fallback_feature}: {label} ({mask.sum()} samples)")
                                except Exception as e:
                                    self.logger.warning(f"Failed to generate fallback segment: {str(e)}")
                    
                    if len(granular_data) > 0:
                        self.logger.info(f"✅ Generated {len(granular_data)} fallback segments from {fallback_feature}")
                except Exception as e:
                    self.logger.error(f"Failed to generate fallback segments: {str(e)}")
                    import traceback
                    self.logger.debug(f"Fallback traceback: {traceback.format_exc()}")
        else:
            self.logger.info(f"✅ Granular accuracy calculated for {len(processed_features)} features, {len(granular_data)} total segments")
            
            # Log summary by variable name (not feature name) for better debugging
            variables_summary = {}
            for item in granular_data:
                var_name = item.get('variable', 'unknown')
                if var_name not in variables_summary:
                    variables_summary[var_name] = {'count': 0, 'segments': []}
                variables_summary[var_name]['count'] += 1
                variables_summary[var_name]['segments'].append(item.get('segment', 'unknown'))
            
            self.logger.info(f"📊 Granular accuracy summary by variable:")
            for var_name, info in sorted(variables_summary.items()):
                self.logger.info(f"  • {var_name}: {info['count']} segments - {info['segments'][:3]}...")
            
            # Also check specifically for home_ownership
            home_ownership_data = [item for item in granular_data if 'home_ownership' in item.get('variable', '').lower()]
            if home_ownership_data:
                self.logger.info(f"✅✅✅ Found {len(home_ownership_data)} segments for home_ownership:")
                for item in home_ownership_data[:5]:
                    self.logger.info(f"    - Variable: '{item.get('variable')}', Segment: '{item.get('segment')}', Samples: {item.get('sample_count')}")
            else:
                self.logger.warning(f"⚠️⚠️⚠️ NO segments found for home_ownership in granular_data!")
                self.logger.warning(f"   Available variables: {list(set(item.get('variable') for item in granular_data))[:10]}")
            
            if continuous_features:
                self.logger.info(f"📈 Processed {len(continuous_features)} continuous features: {list(continuous_features)}")
                for feat in continuous_features:
                    feat_data = [item for item in granular_data if item['variable'] == feat]
                    granularity_levels = set(item.get('granularity_level') for item in feat_data)
                    self.logger.info(f"  • {feat}: {len(feat_data)} segments, granularity levels: {granularity_levels}")
        
        # Log categorical features summary
        if processed_categorical_features:
            categorical_segments = {}
            for item in granular_data:
                if item['variable'] in processed_categorical_features:
                    if item['variable'] not in categorical_segments:
                        categorical_segments[item['variable']] = []
                    if 'category_value' in item:
                        categorical_segments[item['variable']].append(item['category_value'])
                    elif 'grouped_categories' in item:
                        categorical_segments[item['variable']].append(item['grouped_categories'])
            
            self.logger.info(f"📊 Processed {len(processed_categorical_features)} categorical features with original category names:")
            for feat in processed_categorical_features:
                if feat in categorical_segments:
                    categories_shown = set()
                    for cat_list in categorical_segments[feat]:
                        if isinstance(cat_list, list):
                            categories_shown.update(cat_list)
                        else:
                            categories_shown.add(cat_list)
                    self.logger.info(f"  • {feat}: {len(categories_shown)} original categories shown: {sorted(list(categories_shown))[:5]}")
        
        return granular_data
    
    def _analyze_error_patterns(
        self,
        y_test: pd.Series,
        y_pred: np.ndarray,
        y_pred_proba: Optional[np.ndarray]
    ) -> List[Dict[str, Any]]:
        """Analyze error patterns (FP, FN, high confidence errors)"""
        error_patterns = []
        
        try:
            # Calculate confusion matrix elements
            cm = confusion_matrix(y_test, y_pred)
            
            # False Positives
            fp_count = int(cm.sum() - cm.diagonal().sum() - cm.sum(axis=1)[0] + cm[0, 0]) if cm.shape[0] > 1 else 0
            
            # False Negatives
            fn_count = int(cm.sum() - cm.diagonal().sum() - cm.sum(axis=0)[0] + cm[0, 0]) if cm.shape[0] > 1 else 0
            
            total_samples = len(y_test)
            
            # Calculate average confidence for errors
            if y_pred_proba is not None:
                # Get confidence for predicted class
                predicted_probs = np.max(y_pred_proba, axis=1)
                
                # Identify errors
                errors_mask = y_test.values != y_pred
                
                if errors_mask.sum() > 0:
                    avg_error_confidence = float(predicted_probs[errors_mask].mean())
                    
                    # High confidence errors (confidence > 0.8 but wrong)
                    high_conf_errors = (predicted_probs > 0.8) & errors_mask
                    high_conf_error_count = int(high_conf_errors.sum())
                    
                    error_patterns.append({
                        'error_type': 'high_confidence_error',
                        'count': high_conf_error_count,
                        'percentage': float(high_conf_error_count / total_samples * 100),
                        'avg_confidence': float(predicted_probs[high_conf_errors].mean()) if high_conf_error_count > 0 else 0.0
                    })
                else:
                    avg_error_confidence = 0.0
            else:
                avg_error_confidence = None
            
            # Add FP and FN patterns
            error_patterns.extend([
                {
                    'error_type': 'false_positive',
                    'count': fp_count,
                    'percentage': float(fp_count / total_samples * 100),
                    'avg_confidence': avg_error_confidence
                },
                {
                    'error_type': 'false_negative',
                    'count': fn_count,
                    'percentage': float(fn_count / total_samples * 100),
                    'avg_confidence': avg_error_confidence
                }
            ])
        
        except Exception as e:
            self.logger.error(f"Error analyzing error patterns: {str(e)}")
        
        return error_patterns
    
    def _analyze_prediction_confidence(
        self,
        y_test: pd.Series,
        y_pred: np.ndarray,
        y_pred_proba: np.ndarray
    ) -> List[Dict[str, Any]]:
        """Analyze relationship between prediction confidence and accuracy"""
        confidence_analysis = []
        
        try:
            # Get confidence for predicted class
            predicted_probs = np.max(y_pred_proba, axis=1)
            
            # Create confidence bins
            bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
            
            for i in range(len(bins) - 1):
                bin_start = bins[i]
                bin_end = bins[i + 1]
                
                # Find predictions in this confidence bin
                mask = (predicted_probs >= bin_start) & (predicted_probs < bin_end if i < len(bins) - 2 else predicted_probs <= bin_end)
                
                if mask.sum() == 0:
                    continue
                
                # Calculate accuracy for this bin
                bin_accuracy = accuracy_score(y_test[mask], y_pred[mask])
                avg_confidence = float(predicted_probs[mask].mean())
                
                confidence_analysis.append({
                    'bin_start': bin_start,
                    'bin_end': bin_end,
                    'count': int(mask.sum()),
                    'accuracy': float(bin_accuracy),
                    'avg_confidence': avg_confidence
                })
        
        except Exception as e:
            self.logger.error(f"Error analyzing prediction confidence: {str(e)}")
        
        return confidence_analysis
    
    def _analyze_monotonicity(
        self,
        model: Any,
        X_test: pd.DataFrame,
        feature_names: List[str],
        problem_type: str
    ) -> Dict[str, Any]:
        """Analyze monotonicity of features"""
        monotonicity_results = {}
        
        try:
            # Analyze top 5 numerical features
            for feature in feature_names[:5]:
                if feature not in X_test.columns:
                    continue
                
                if not pd.api.types.is_numeric_dtype(X_test[feature]):
                    continue
                
                # Create test data with feature varied
                X_varied = X_test.copy()
                feature_range = np.linspace(
                    X_test[feature].min(),
                    X_test[feature].max(),
                    20
                )
                
                predictions = []
                for value in feature_range:
                    X_varied[feature] = value
                    if hasattr(model, 'predict_proba'):
                        pred = model.predict_proba(X_varied)[:, 1].mean()
                    else:
                        pred = model.predict(X_varied).mean()
                    predictions.append(float(pred))
                
                # Check monotonicity
                diffs = np.diff(predictions)
                is_increasing = np.all(diffs >= -0.01)  # Allow small violations
                is_decreasing = np.all(diffs <= 0.01)
                
                monotonicity_results[feature] = {
                    'feature_name': feature,
                    'is_monotonic': bool(is_increasing or is_decreasing),
                    'direction': 'increasing' if is_increasing else ('decreasing' if is_decreasing else 'non-monotonic'),
                    'feature_range': feature_range.tolist(),
                    'predictions': predictions
                }
        
        except Exception as e:
            self.logger.warning(f"Error analyzing monotonicity: {str(e)}")
        
        return monotonicity_results

    def _build_decile_monotonicity_results(
        self,
        y_true: pd.Series,
        y_pred_proba: Optional[np.ndarray],
        y_pred_proba_train: Optional[np.ndarray] = None,
        X_train: Optional[pd.DataFrame] = None,
        X_test: Optional[pd.DataFrame] = None,
        sample_weight: Optional[np.ndarray] = None,  # NEW: Sample weights for weighted KS
    ) -> Optional[Dict[str, Any]]:
        """
        Compute decile table, monotonicity score, KS, PSI, and related metrics.
        
        When X_test is None (active_scope='entire'), this uses train data for analysis.
        When sample_weight is provided, weighted KS is also computed.
        """
        """Compute decile table, monotonicity score, KS, PSI, and related metrics."""
        if (
            mono_decile_table is None
            or mono_score is None
            or calculate_ks_detailed is None
            or ks_from_deciles is None
            or compute_auc_gini is None
            or y_pred_proba is None
        ):
            # Return error info for frontend instead of just logging
            error_info = {
                "error": "Monotonicity utilities not available",
                "message": _monotonicity_import_error or "Failed to import monotonicity utilities. Please check backend logs.",
                "details": "The monotonicity.py module could not be imported. This may be a deployment issue on Azure RI."
            }
            self.logger.warning(f"Monotonicity utilities not available; skipping decile/KS computation. Error: {_monotonicity_import_error}")
            # Return error info so frontend can display it
            return {"error": error_info}

        try:
            # Handle binary probas shaped (n, 2) or (n,)
            scores = y_pred_proba[:, 1] if len(y_pred_proba.shape) > 1 else y_pred_proba
            deciles_df = mono_decile_table(y_true, scores)

            # Make a display-friendly copy with 1-based decile labels
            deciles_df = deciles_df.copy()
            deciles_df["Decile"] = deciles_df["Decile"].astype(int) + 1

            # Monotonicity score and violations
            score = float(mono_score(deciles_df))
            bad_rates = deciles_df["Bad_Rate"].to_numpy()
            violations = []
            for i in range(1, len(bad_rates)):
                if bad_rates[i] < bad_rates[i - 1]:
                    violations.append(
                        {
                            "from_decile": int(deciles_df.loc[i - 1, "Decile"]),
                            "to_decile": int(deciles_df.loc[i, "Decile"]),
                            "drop": float(bad_rates[i - 1] - bad_rates[i]),
                        }
                    )

            ks, ks_threshold, ks_tpr, ks_fpr = calculate_ks_detailed(y_true, scores)
            ks_from_dec, ks_decile = ks_from_deciles(deciles_df.copy())
            auc, gini = compute_auc_gini(y_true, scores)
            
            # Calculate weighted KS if sample weights are provided
            weighted_ks = None
            weighted_ks_threshold = None
            if sample_weight is not None:
                try:
                    weighted_ks, weighted_ks_threshold, _, _ = calculate_ks_detailed(y_true, scores, sample_weight=sample_weight)
                except Exception as e:
                    self.logger.warning(f"Failed to calculate weighted KS: {e}")

            overall_bad_rate = float(deciles_df["Bads"].sum() / deciles_df["Count"].sum()) if deciles_df["Count"].sum() else 0.0
            lift_top = float(deciles_df["Lift"].iloc[-1]) if "Lift" in deciles_df.columns and len(deciles_df) > 0 else None

            # Calculate PSI (Population Stability Index) if train predictions are available
            psi_value = None
            psi_breakdown = None
            if y_pred_proba_train is not None and calculate_psi_detailed is not None:
                try:
                    # Extract probability scores for class 1 (binary classification)
                    train_scores = y_pred_proba_train[:, 1] if len(y_pred_proba_train.shape) > 1 else y_pred_proba_train
                    test_scores = scores  # Already extracted above
                    psi_value, psi_breakdown_df = calculate_psi_detailed(train_scores, test_scores, q=10)
                    psi_value = float(psi_value)
                    # Convert breakdown DataFrame to list of dicts for JSON serialization
                    psi_breakdown = psi_breakdown_df.to_dict(orient="records")
                except Exception as e:
                    self.logger.warning(f"Failed to calculate PSI: {e}")
                    psi_value = None
                    psi_breakdown = None

            # Calculate CSI (Characteristic Stability Index) for variables if train/test data available
            csi_results = None
            if X_train is not None and X_test is not None and calculate_csi_for_variables is not None:
                try:
                    csi_df = calculate_csi_for_variables(X_train, X_test, q=10, max_variables=50)
                    if not csi_df.empty:
                        csi_results = csi_df.to_dict(orient="records")
                except Exception as e:
                    self.logger.warning(f"Failed to calculate CSI: {e}")
                    csi_results = None

            summary = {
                "deciles": deciles_df.to_dict(orient="records"),
                "monotonicity_score": score,
                "monotonicity_pass": len(violations) == 0,
                "monotonicity_violations": violations,
                "psi": psi_value,
                "psi_breakdown": psi_breakdown,
                "csi": csi_results,
                "ks": float(ks),
                "ks_threshold": float(ks_threshold),
                "ks_tpr": float(ks_tpr),
                "ks_fpr": float(ks_fpr),
                "ks_decile": float(ks_decile),
                "ks_from_deciles": float(ks_from_dec),
                "auc": float(auc),
                "gini": float(gini),
                "overall_bad_rate": overall_bad_rate,
                "lift_top_decile": lift_top,
            }
            
            # Add weighted KS if available
            if weighted_ks is not None:
                summary["weighted_ks"] = float(weighted_ks)
                summary["weighted_ks_threshold"] = float(weighted_ks_threshold)
                summary["has_sample_weights"] = True
            else:
                summary["has_sample_weights"] = False

            return summary
        except Exception as e:  # pragma: no cover
            self.logger.warning(f"Failed to compute decile/monotonicity results: {e}")
            return None
    
    def format_for_database(self, evaluation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Format evaluation results for database storage (MEEA format)"""
        try:
            model_id = evaluation_results['model_id']
            
            # Format model metadata
            model_data = {
                'id': model_id,
                'name': evaluation_results['model_name'],
                'model_type': evaluation_results['model_name'],
                'task_type': evaluation_results['problem_type'],
                'training_date': evaluation_results['evaluation_timestamp'],
                'status': 'completed',
                'color': self._generate_model_color(model_id),
                'description': f"{evaluation_results['model_name']} model trained with auto-training",
                # NEW: Store metadata for train/test toggle
                'dataset_id': evaluation_results.get('dataset_id'),
                'active_scope': evaluation_results.get('active_scope', 'entire'),
                'target_column': evaluation_results.get('target_column'),
                'split_params': evaluation_results.get('split_params', {
                    'test_size': 0.2,
                    'random_state': 42,
                    'stratify': False
                }),
                # NEW: Store preprocessed column mapping for explainability
                'preprocessed_columns': evaluation_results.get('preprocessed_columns', {}),
                # NEW: Store train/test indices for exact split recreation
                'train_indices': evaluation_results.get('train_indices'),
                'test_indices': evaluation_results.get('test_indices'),
                # NEW: Store original feature names used in training
                'used_features': evaluation_results.get('used_features', [])
            }
            
            # Format performance metrics
            perf_metrics = evaluation_results['performance_metrics']
            
            # Extract optional train/test metrics into a separate dict for compact storage
            train_test_metrics = {
                k: v for k, v in perf_metrics.items()
                if k.startswith('train_') or k.startswith('test_')
            }
            
            performance_data = {
                'model_id': model_id,
                'accuracy': safe_float(perf_metrics.get('accuracy')),
                'precision': safe_float(perf_metrics.get('precision')),
                'recall': safe_float(perf_metrics.get('recall')),
                'f1_score': safe_float(perf_metrics.get('f1_score')),
                'auc_roc': safe_float(perf_metrics.get('auc_roc')),
                'auc_pr': safe_float(perf_metrics.get('auc_pr')),
                'log_loss': safe_float(perf_metrics.get('log_loss')),
                'confusion_matrix': perf_metrics.get('confusion_matrix'),
                'class_metrics': perf_metrics.get('class_metrics'),
                # NEW: store all train_*/test_* metrics as JSON blob to avoid schema bloat
                'train_test_metrics': train_test_metrics or None
            }
            # Persist monotonicity/decile results in train_test_metrics blob
            if evaluation_results.get('monotonicity_results'):
                if performance_data['train_test_metrics'] is None:
                    performance_data['train_test_metrics'] = {}
                performance_data['train_test_metrics']['monotonicity_results'] = evaluation_results['monotonicity_results']
            
            # Clean train_test_metrics as well
            if performance_data['train_test_metrics']:
                cleaned_train_test = {}
                for k, v in performance_data['train_test_metrics'].items():
                    if isinstance(v, (int, float, np.floating, np.integer)):
                        cleaned_train_test[k] = safe_float(v)
                    else:
                        cleaned_train_test[k] = v
                performance_data['train_test_metrics'] = cleaned_train_test
            
            # Format feature importance
            feature_importance_data = [
                {
                    'model_id': model_id,
                    **feature
                }
                for feature in evaluation_results['feature_importance']
            ]
            
            # Format granular accuracy (TEST)
            granular_accuracy_data = [
                {
                    'model_id': model_id,
                    **granular
                }
                for granular in evaluation_results.get('granular_accuracy', [])
            ]
            
            # Log for debugging
            if granular_accuracy_data:
                self.logger.info(f"📊 Formatting {len(granular_accuracy_data)} granular accuracy segments for database")
                variables = set(item.get('variable') for item in granular_accuracy_data if item.get('variable'))
                self.logger.info(f"   Variables: {sorted(list(variables))}")
                home_ownership_count = len([item for item in granular_accuracy_data if item.get('variable') == 'home_ownership'])
                if home_ownership_count > 0:
                    self.logger.info(f"   ✅ home_ownership: {home_ownership_count} segments will be saved to database")
            else:
                self.logger.warning(f"⚠️ No granular accuracy data to format for database")
            
            # Format granular accuracy (TRAIN)
            granular_accuracy_train_raw = evaluation_results.get('granular_accuracy_train', [])
            self.logger.info(f"📊 Formatting TRAIN granular accuracy: {len(granular_accuracy_train_raw) if granular_accuracy_train_raw else 0} segments from evaluation_results")
            
            # CRITICAL DEBUG: Check if granular_accuracy_train exists in evaluation_results
            if 'granular_accuracy_train' not in evaluation_results:
                self.logger.error(f"❌❌❌ CRITICAL: 'granular_accuracy_train' key NOT FOUND in evaluation_results!")
                self.logger.error(f"   Available keys: {list(evaluation_results.keys())}")
            elif not granular_accuracy_train_raw:
                self.logger.warning(f"⚠️ 'granular_accuracy_train' exists but is empty: {granular_accuracy_train_raw}")
            else:
                self.logger.info(f"✅ 'granular_accuracy_train' found with {len(granular_accuracy_train_raw)} segments")
            
            granular_accuracy_train_data = [
                {
                    'model_id': model_id,
                    **granular
                }
                for granular in (granular_accuracy_train_raw if granular_accuracy_train_raw else [])
            ]
            
            # Log for debugging
            if granular_accuracy_train_data:
                self.logger.info(f"📊 Formatted {len(granular_accuracy_train_data)} TRAIN granular accuracy segments for database")
                variables = set(item.get('variable') for item in granular_accuracy_train_data if item.get('variable'))
                self.logger.info(f"   TRAIN Variables: {sorted(list(variables))}")
                
                # Check specifically for home_ownership
                ho_segments = [item for item in granular_accuracy_train_data if item.get('variable') == 'home_ownership' or 'home_ownership' in str(item.get('variable', '')).lower()]
                if ho_segments:
                    self.logger.info(f"   ✅ home_ownership TRAIN segments in formatted data: {len(ho_segments)}")
                    for seg in ho_segments[:3]:
                        self.logger.info(f"      - Variable: '{seg.get('variable')}', Segment: '{seg.get('segment')}', Samples: {seg.get('sample_count')}")
                else:
                    self.logger.warning(f"   ⚠️ NO home_ownership TRAIN segments in formatted data!")
                    self.logger.warning(f"   All variables in formatted data: {sorted(list(variables))}")
            else:
                self.logger.warning(f"⚠️ No TRAIN granular accuracy data to format for database (raw data: {granular_accuracy_train_raw})")
            
            # Format error patterns
            error_patterns_data = [
                {
                    'model_id': model_id,
                    **error
                }
                for error in evaluation_results.get('error_patterns', [])
            ]
            
            # Format prediction confidence
            prediction_confidence_data = [
                {
                    'model_id': model_id,
                    **conf
                }
                for conf in evaluation_results.get('prediction_confidence', [])
            ]
            
            # Format explainability data
            explainability_data = []
            
            # ROC curve data (TEST)
            if evaluation_results.get('roc_curve'):
                explainability_data.append({
                    'model_id': model_id,
                    'data_type': 'roc_curve',
                    'data_source': 'test',
                    'feature_name': None,
                    'values': evaluation_results['roc_curve'],
                    'metadata': {}
                })

            # ROC curve data (TRAIN)
            if evaluation_results.get('roc_curve_train'):
                explainability_data.append({
                    'model_id': model_id,
                    'data_type': 'roc_curve',
                    'data_source': 'train',
                    'feature_name': None,
                    'values': evaluation_results['roc_curve_train'],
                    'metadata': {}
                })
            
            # Use explainability service to format SHAP and PDP data (only if they exist)
            shap_data = evaluation_results.get('shap_analysis')
            pdp_data = evaluation_results.get('partial_dependence')
            waterfall_data = evaluation_results.get('waterfall_data')
            
            # Format explainability data using the service (only if explainability was calculated)
            if shap_data or pdp_data or waterfall_data:
                from app.services.explainability_service import explainability_service
                explainability_data.extend(
                    explainability_service.format_explainability_for_database(
                        shap_data, pdp_data, waterfall_data, model_id, data_source='test'
                    )
                )
            else:
                # No explainability data - will be calculated on-demand when user clicks explainability tab
                self.logger.debug("No explainability data to save - will be calculated on-demand")
            
            # Clean NaN values before returning (for JSON serialization)
            from app.utils.helpers import clean_nan_values
            
            formatted_data = {
                'model': model_data,
                'performance_metrics': performance_data,
                'feature_importance': feature_importance_data,
                'granular_accuracy': granular_accuracy_data,
                'granular_accuracy_train': granular_accuracy_train_data,
                'error_patterns': error_patterns_data,
                'prediction_confidence': prediction_confidence_data,
                'explainability_data': explainability_data
            }
            
            # Clean all NaN values (replace with None for JSON compatibility)
            cleaned_data = clean_nan_values(formatted_data, replace_with=None)
            
            return cleaned_data
        
        except Exception as e:
            self.logger.error(f"Error formatting for database: {str(e)}")
            raise
    
    def _generate_model_color(self, model_id: str) -> str:
        """Generate a consistent color for a model based on its ID"""
        colors = [
            '#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6',
            '#EC4899', '#14B8A6', '#F97316', '#6366F1', '#84CC16'
        ]
        # Use hash of model_id to select color
        hash_val = sum(ord(c) for c in model_id)
        return colors[hash_val % len(colors)]


# Create singleton instance
model_evaluation_service = ModelEvaluationService()


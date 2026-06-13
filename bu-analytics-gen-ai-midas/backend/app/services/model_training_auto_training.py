import pandas as pd
import numpy as np
import pandas as pd
# import ast
import json
from typing import Callable, Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
import joblib
from joblib import Parallel, delayed
import os
import uuid
# gc is used to reclaim the large per-model MEEA DataFrames (X_train/X_test/
# X_*_original) as soon as they are no longer needed. Auto-training holds up to
# ~5 models x 4 frames simultaneously, so an explicit collect after we drop the
# references measurably lowers peak pod memory rather than waiting for the next
# generational GC pass.
import gc
# from fastapi.encoders import jsonable_encoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, log_loss, mean_squared_error, r2_score,
    mean_absolute_error,
)
import warnings
warnings.filterwarnings('ignore')

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

# Try to import Optuna for Bayesian optimization
try:
    import optuna
    from optuna.samplers import TPESampler
    from optuna.pruners import MedianPruner
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    optuna = None
    TPESampler = None
    MedianPruner = None

from app.core.logging_config import get_logger
from app.utils.monotonicity import (
    calculate_ks,
    compute_auc_gini,
    compute_auc_overfit_pct,
    nonzero_feature_slot_count,
)

# Apply the Copy-on-Write setting at module import so it also takes effect inside
# loky/joblib worker processes (which import this module fresh and never execute
# main.py). Gated by MIDAS_PANDAS_COW. Without this, the per-model X_train/X_test
# copies made inside train_single_algorithm in each worker would still be eager.
try:
    from app.utils.helpers import configure_pandas_copy_on_write as _configure_pandas_cow
    _configure_pandas_cow()
except Exception:
    pass
from app.services.llm_service import llm_service

# Safe median helper to coerce non-numeric values before median reduction
def safe_median(series: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    return float(numeric.median()) if not numeric.empty else 0.0

logger = get_logger(__name__)

def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    else:
        return obj

def make_json_serializable(data):
    """Make data structure JSON serializable by converting numpy types and handling complex objects"""
    try:
        # First convert numpy types
        data = convert_numpy_types(data)

        # Handle pandas DataFrame/Tensor conversion if needed
        if hasattr(data, 'to_dict'):
            try:
                return data.to_dict()
            except:
                pass

        # Handle any remaining non-serializable objects
        if isinstance(data, dict):
            return {k: make_json_serializable(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [make_json_serializable(item) for item in data]
        elif isinstance(data, (int, float, str, bool)) or data is None:
            return data
        else:
            # For any other object, try to convert to string
            return str(data)

    except Exception as e:
        logger.warning(f"Error making object serializable: {str(e)}, converting to string")


# --- Variance / Technical Eligibility helpers ---
def _single_value_pct(series: pd.Series) -> float:
    """
    Share of the dominant value among non-null rows (0..1).
    Used for zero/near-zero variance checks (E01).
    """
    s = series.dropna()
    n = len(s)
    if n == 0:
        return 0.0
    return float(s.value_counts(dropna=False).iloc[0] / n)

def _safe_std(series: pd.Series) -> float:
    try:
        if isinstance(series.dtype, pd.SparseDtype):
            if series.isna().any():
                try:
                    return float(series.sparse.to_dense().std())
                except Exception:
                    return 0.0

            arr = series.array
            n = int(len(series))
            if n <= 1:
                return 0.0

            fill = float(getattr(arr, "fill_value", 0.0))
            sp_vals = np.asarray(getattr(arr, "sp_values", []), dtype=float)
            nnz = int(len(sp_vals))
            mean = float(series.mean())

            ss_sp = float(np.sum((sp_vals - mean) ** 2)) if nnz else 0.0
            ss_fill = float((n - nnz) * ((fill - mean) ** 2))
            var = (ss_sp + ss_fill) / float(n - 1)
            return float(np.sqrt(var))

        return float(series.std()) if len(series) > 1 else 0.0
    except Exception:
        return 0.0

def generate_column_stats(df: pd.DataFrame, feature_names: List[str]) -> Dict[str, Any]:
    """
    Generate column statistics similar to pandas .describe() for each feature.
    
    Returns dtype and classification (categorical vs continuous) for each column.
    
    Args:
        df: DataFrame containing the data
        feature_names: List of feature column names to analyze
        
    Returns:
        Dictionary with column stats including dtype and variable_type (categorical/continuous)
    """
    column_stats = {}

    # Hoist date detection outside the loop - calling identify_date_columns() per column
    # would scan the full DataFrame once per feature (O(n*k) instead of O(n)).
    from app.utils.helpers import identify_date_columns
    date_detection_results = identify_date_columns(df)

    for col in feature_names:
        if col not in df.columns:
            continue
            
        col_data = df[col]
        # Densify sparse columns - pandas cannot compute std/mean/quantile on Sparse dtypes
        if isinstance(col_data.dtype, pd.SparseDtype):
            col_data = col_data.sparse.to_dense()
        dtype_str = str(col_data.dtype)
        unique_count = int(col_data.nunique())
        total_count = len(col_data)
        missing_count = int(col_data.isna().sum())
        
        # Determine if categorical or continuous
        # USE THE SAME LOGIC AS calculate_column_info (Column Details table)
        # This ensures consistency between Column Details UI and granular accuracy
        
        is_numeric = pd.api.types.is_numeric_dtype(col_data)
        is_bool = pd.api.types.is_bool_dtype(col_data)
        is_object = col_data.dtype == 'object' or pd.api.types.is_string_dtype(col_data)
        column_name_lower = col.lower()
        
        # Check for date columns first (same as calculate_column_info)
        date_meta = date_detection_results.get(str(col), {})
        is_date_like = date_meta.get('is_date', False)
        
        if is_date_like:
            variable_type = 'date'
        elif is_object or is_bool:
            # Object/string dtype -> categorical
            variable_type = 'categorical'
        elif is_numeric:
            # Numeric columns: determine if categorical or continuous
            # IMPROVED LOGIC: Be more conservative about classifying numeric as categorical
            # Only classify as categorical if it's clearly categorical (very low cardinality AND integer values)
            
            is_target_like = any(keyword in column_name_lower for keyword in ['target', 'label', 'class', 'flag', 'outcome'])
            
            # Check if values are integers (categorical indicators are usually integers)
            # Vectorized: avoid row-by-row .apply() on large columns
            if pd.api.types.is_integer_dtype(col_data):
                is_integer_type = True
            elif pd.api.types.is_float_dtype(col_data):
                _clean = col_data.dropna()
                is_integer_type = len(_clean) > 0 and bool((_clean % 1 == 0).all())
            else:
                is_integer_type = False
            
            # Calculate range and distribution
            if not col_data.isna().all():
                numeric_data = col_data.dropna()
                if len(numeric_data) > 0:
                    data_min = float(numeric_data.min())
                    data_max = float(numeric_data.max())
                    data_range = data_max - data_min
                    data_mean = float(numeric_data.mean())
                    data_std = _safe_std(numeric_data)
                    
                    # STRICT RULES for categorical:
                    # 1. Must be integer type
                    # 2. Must have <= 20 unique values
                    # 3. Must NOT be target-like
                    # 4. Must have small range relative to mean (or mean is small)
                    # 5. Values should be sequential integers starting from 0 or 1 (typical encoding pattern)
                    
                    # Check if values look like encoded categories (0, 1, 2, ... or 1, 2, 3, ...)
                    unique_vals_sorted = sorted(numeric_data.unique())
                    looks_like_encoding = False
                    if len(unique_vals_sorted) <= 20:
                        # Check if values are sequential integers starting from 0 or 1
                        if len(unique_vals_sorted) > 0:
                            first_val = unique_vals_sorted[0]
                            if first_val in [0, 1] and all(unique_vals_sorted[i] == first_val + i for i in range(len(unique_vals_sorted))):
                                looks_like_encoding = True
                    
                    # Check if it's a count/measurement variable (likely continuous)
                    # Variables with names like "last_6mths", "count", "total", "sum", "avg" are likely continuous
                    is_count_like = any(keyword in column_name_lower for keyword in [
                        'count', 'total', 'sum', 'avg', 'average', 'mean', 'max', 'min',
                        'last_', 'prev_', 'previous', 'mths', 'months', 'days', 'years',
                        'inq_', 'num_', 'amt_', 'amount', 'balance', 'limit', 'rate'
                    ])
                    
                    # Decision logic
                    if is_count_like:
                        # Variables with count/measurement names are ALWAYS continuous
                        variable_type = 'continuous'
                    elif unique_count <= 10 and is_integer_type and looks_like_encoding and not is_target_like:
                        # Very low cardinality integer that looks like encoding -> categorical
                        variable_type = 'categorical'
                    elif unique_count <= 5 and is_integer_type and not is_target_like:
                        # Extremely low cardinality integer -> categorical
                        variable_type = 'categorical'
                    else:
                        # Default: treat as continuous (safer for numeric variables)
                        variable_type = 'continuous'
                else:
                    variable_type = 'continuous'
            else:
                variable_type = 'continuous'
        else:
            # Default to categorical for unknown types
            variable_type = 'categorical'
        
        col_stats = {
            'dtype': dtype_str,
            'variable_type': variable_type,
            'unique_count': unique_count,
            'total_count': total_count,
            'missing_count': missing_count,
            'missing_pct': round(missing_count / total_count * 100, 2) if total_count > 0 else 0
        }
        
        # Add descriptive stats for numeric columns
        if is_numeric and not is_bool:
            clean_data = col_data.dropna()
            if len(clean_data) > 0:
                col_stats['min'] = float(clean_data.min())
                col_stats['max'] = float(clean_data.max())
                col_stats['mean'] = float(clean_data.mean())
                col_stats['std'] = _safe_std(clean_data) if len(clean_data) > 1 else 0.0
                # Coerce to numeric for median calculation to avoid string dtype errors
                numeric_vals = pd.to_numeric(clean_data, errors='coerce').dropna()
                col_stats['median'] = safe_median(clean_data)
                
                # Percentiles
                try:
                    col_stats['q25'] = float(clean_data.quantile(0.25))
                    col_stats['q75'] = float(clean_data.quantile(0.75))
                except:
                    pass
        
        # Add top categories for categorical columns
        if variable_type == 'categorical':
            try:
                value_counts = col_data.value_counts().head(10)
                col_stats['top_categories'] = [
                    {'value': str(val), 'count': int(cnt)} 
                    for val, cnt in value_counts.items()
                ]
                col_stats['num_categories'] = unique_count
            except:
                pass
        
        column_stats[col] = col_stats
    
    return column_stats


class ModelTrainingAutoTrainingService:
    """Service for automatic model training with intelligent algorithm selection and hyperparameter optimization"""

    # Preprocessing cache: {(dataset_id, frozenset(variables), target): (X, y, summary, last_updated)}
    _preprocess_cache: Dict[tuple, tuple] = {}

    # Pending MEEA jobs: {model_id: {args dict}} - populated during training, consumed by background MEEA task
    _pending_meea_jobs: Dict[str, Dict] = {}

    def __init__(self):
        self.logger = logger
        self.model_storage_path = "models/"
        self.ensure_model_directory()

    def ensure_model_directory(self):
        """Ensure model storage directory exists"""
        if not os.path.exists(self.model_storage_path):
            os.makedirs(self.model_storage_path)

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

            # MEMORY/PERF OPTIMIZATION: Sample once at the top so imputation,
            # label encoding, correlation, and VIF all run on a random 100k-row
            # subset for large frames (e.g. 4M+ rows). Documented bottleneck —
            # see backend/docs/midas-4m-row-performance-analysis 1.md. VIF and
            # corrwith are stable on this sample size for typical MIDAS data.
            VIF_CORR_SAMPLE_SIZE = 100_000
            work_cols = valid_independent + [target_column]
            _df_work = df[work_cols]
            if len(_df_work) > VIF_CORR_SAMPLE_SIZE:
                self.logger.info(
                    f"VIF/correlation: sampling {VIF_CORR_SAMPLE_SIZE} rows from {len(_df_work)} for performance",
                    extra={
                        "event": "vif_corr_sampling",
                        "sample_size": VIF_CORR_SAMPLE_SIZE,
                        "full_size": len(_df_work),
                    },
                )
                df_num = _df_work.sample(n=VIF_CORR_SAMPLE_SIZE, random_state=42).copy()
            else:
                df_num = _df_work.copy()
            for c in df_num.columns:
                # Check if column is categorical/string type (handles object, category, string, StringDtype, etc.)
                is_string_or_cat = (
                    df_num[c].dtype in ['object', 'category'] or
                    pd.api.types.is_string_dtype(df_num[c]) or
                    str(df_num[c].dtype).startswith('string')
                )
                
                if is_string_or_cat:
                    mode_val = df_num[c].mode()
                    df_num[c] = df_num[c].fillna(mode_val[0] if len(mode_val)>0 else 'Unknown')
                else:
                    # pandas SparseArray does not support median() directly
                    try:
                        is_sparse = isinstance(df_num[c].dtype, pd.SparseDtype)
                    except Exception:
                        is_sparse = False

                    if is_sparse:
                        # For OHE columns we create Sparse[int8, 0] (fill_value=0)
                        # Median is 0; avoid densifying.
                        fill_val = 0
                        try:
                            fill_val = (
                                df_num[c].dtype.fill_value
                                if isinstance(df_num[c].dtype, pd.SparseDtype)
                                else 0
                            )
                        except Exception:
                            fill_val = 0

                        if fill_val == 0:
                            df_num[c] = df_num[c].fillna(0)
                        else:
                            dense_s = df_num[c].sparse.to_dense()
                            df_num[c] = df_num[c].fillna(dense_s.median())
                    else:
                        # Ensure column is numeric before calling median
                        numeric_series = pd.to_numeric(df_num[c], errors='coerce')
                        median_val = numeric_series.median()
                        df_num[c] = numeric_series.fillna(median_val if pd.notna(median_val) else 0)
    
            # Label-encode categoricals (not target if numeric already handled above)
            cat_cols = [c for c in df_num.columns if df_num[c].dtype in ['object','category']]
            if target_column in cat_cols:
                cat_cols.remove(target_column)
            from sklearn.preprocessing import LabelEncoder
            label_encoders = {}
            for col in cat_cols:
                le = LabelEncoder()
                df_num[col] = le.fit_transform(df_num[col].astype(str))
                label_encoders[col] = le
            if df_num[target_column].dtype in ['object','category']:
                le_t = LabelEncoder()
                df_num[target_column] = le_t.fit_transform(df_num[target_column].astype(str))
    
            # OPTIMIZED: Vectorized correlation calculation
            correlations: Dict[str, float] = {}
            try:
                # Calculate all correlations with target at once
                target_series = df_num[target_column]
                all_corrs = df_num[valid_independent].corrwith(target_series)
                for var in valid_independent:
                    corr = all_corrs.get(var, 0.0)
                    correlations[var] = float(corr) if pd.notna(corr) else 0.0
            except Exception:
                # Fallback to per-column calculation
                for var in valid_independent:
                    try:
                        corr = df_num[var].corr(df_num[target_column])
                        correlations[var] = float(corr) if not pd.isna(corr) else 0.0
                    except Exception:
                        correlations[var] = 0.0
    
            # OPTIMIZED: VIF via correlation matrix approximation with chunked processing
            # VIF ~= 1/(1-max_r^2) - chunked for large feature sets
            vif_data: Dict[str, Optional[float]] = {v: None for v in valid_independent}
            try:
                X = df_num[valid_independent].copy()
                X = X.replace([np.inf, -np.inf], np.nan)
                # Drop constant columns
                nunique = X.nunique(dropna=False)
                const_cols = nunique[nunique<=1].index.tolist()
                if const_cols:
                    X = X.drop(columns=const_cols)
                
                n_features = X.shape[1]
                if n_features >= 2:
                    # Compute full correlation matrix once - O(p²) - then read per-column max |r|.
                    # This replaces the old large-p branch that computed chunk_corr (dead code)
                    # and then ran a separate per-variable corrwith loop anyway (O(p²) × p).
                    self.logger.info(f"Computing VIF via single corr() call for {n_features} features")
                    corr_m = X.corr()
                    for v in X.columns:
                        others = [c for c in X.columns if c != v]
                        if not others:
                            vif_data[v] = 1.0
                        else:
                            mc = corr_m.loc[v, others].abs().max()
                            if pd.isna(mc) or mc >= 0.999:
                                vif_val = None
                            else:
                                vif_val = float(1.0 / (1.0 - float(mc) ** 2))
                            vif_data[v] = None if vif_val is None or vif_val > 1e6 else vif_val
            except Exception:
                # keep None if anything fails
                pass
    
            # OPTIMIZED: Information Value (IV) calculation with pre-computed event mask
            # Pre-compute event mask once and reuse for all variables
            iv_values: Dict[str, Optional[float]] = {v: None for v in valid_independent}
            iv_event_label: Dict[str, Optional[str]] = {v: None for v in valid_independent}
            try:
                nunique_t = df_num[target_column].nunique(dropna=True)
                is_binary = (nunique_t == 2)
                is_continuous_target = (nunique_t > 20)
                target_for_iv = df_num[target_column].copy()
                # Ensure target is numeric before median calculation
                if not pd.api.types.is_numeric_dtype(target_for_iv):
                    target_for_iv = pd.to_numeric(target_for_iv, errors='coerce').fillna(0)
                if is_continuous_target:
                    med = target_for_iv.median()
                    target_for_iv = (target_for_iv > med).astype(int)
                    is_binary = True
    
                if is_binary:
                    event_label = 1 if 1 in set(target_for_iv.unique()) else target_for_iv.max()
                    # Pre-compute event mask once (optimization)
                    is_event_mask = (target_for_iv == event_label).astype(int)
                    total_events = int(is_event_mask.sum())
                    total_non_events = int(len(target_for_iv) - total_events)
                    epsilon = 1e-10
                    
                    # Pre-compute numeric dtype check for all columns
                    numeric_vars = [v for v in valid_independent if pd.api.types.is_numeric_dtype(df_num[v])]
                    cat_vars = [v for v in valid_independent if v not in numeric_vars]
                    
                    def compute_iv_for_var(var, s, is_event_mask, total_events, total_non_events, epsilon):
                        """Compute IV for a single variable - optimized"""
                        try:
                            if var in numeric_vars:
                                try:
                                    bins = pd.qcut(s, q=min(10, s.nunique()), duplicates='drop')
                                except Exception:
                                    bins = pd.cut(s, bins=min(10, max(2, s.nunique())))
                            else:
                                bins = s.astype(str)
                            
                            # Use numpy for faster aggregation
                            bin_codes, bin_uniques = pd.factorize(bins)
                            n_bins = len(bin_uniques)
                            
                            events_per_bin = np.zeros(n_bins)
                            counts_per_bin = np.zeros(n_bins)
                            
                            for i in range(n_bins):
                                mask = bin_codes == i
                                counts_per_bin[i] = mask.sum()
                                events_per_bin[i] = is_event_mask.values[mask].sum()
                            
                            non_events_per_bin = counts_per_bin - events_per_bin
                            
                            if total_events == 0 or total_non_events == 0:
                                return None
                            
                            dist_event = events_per_bin / max(total_events, 1)
                            dist_non_event = non_events_per_bin / max(total_non_events, 1)
                            woe = np.log((dist_event + epsilon) / (dist_non_event + epsilon))
                            iv_component = (dist_event - dist_non_event) * woe
                            
                            # Replace inf and sum
                            iv_component = np.where(np.isinf(iv_component), 0, iv_component)
                            iv_component = np.nan_to_num(iv_component, 0)
                            iv = float(iv_component.sum())
                            
                            return iv if np.isfinite(iv) else None
                        except Exception:
                            return None
                    
                    # Compute IV for all variables in parallel (thread-safe: read-only on df_num)
                    from joblib import Parallel as _Parallel, delayed as _delayed
                    from app.core.config import settings as _settings
                    _n_jobs = getattr(_settings, "TRAINING_MAX_WORKERS", -1)
                    iv_results = _Parallel(n_jobs=_n_jobs, prefer="threads")(
                        _delayed(compute_iv_for_var)(
                            var, df_num[var], is_event_mask, total_events, total_non_events, epsilon
                        )
                        for var in valid_independent
                    )
                    for var, iv in zip(valid_independent, iv_results):
                        iv_values[var] = iv
                        iv_event_label[var] = 'High' if is_continuous_target else str(event_label)
    
            except Exception:
                for var in valid_independent:
                    iv_values[var] = None
                    iv_event_label[var] = None
                self.logger.warning("IV calculation failed for all variables")

            # VARIANCE CALCULATION: Calculate variance/std and single-value percentage for each variable
            variance_data: Dict[str, Dict[str, Any]] = {}
            try:
                def _compute_variance_stats(var):
                    s = df_num[var]
                    std_val = _safe_std(s)
                    single_val_pct = _single_value_pct(s)
                    unique_count = int(s.nunique(dropna=True))
                    is_zero_variance = unique_count <= 1
                    is_near_zero_variance = single_val_pct > 0.95 or (std_val < 0.01 and pd.api.types.is_numeric_dtype(s))
                    return var, {
                        'std': float(std_val) if pd.notna(std_val) else None,
                        'single_value_pct': float(single_val_pct),
                        'unique_count': unique_count,
                        'is_zero_variance': is_zero_variance,
                        'is_near_zero_variance': is_near_zero_variance,
                        'variance_status': 'zero' if is_zero_variance else ('near_zero' if is_near_zero_variance else 'ok')
                    }

                from joblib import Parallel as _Parallel2, delayed as _delayed2
                from app.core.config import settings as _settings2
                _n_jobs2 = getattr(_settings2, "TRAINING_MAX_WORKERS", -1)
                var_results = _Parallel2(n_jobs=_n_jobs2, prefer="threads")(
                    _delayed2(_compute_variance_stats)(var) for var in valid_independent
                )
                variance_data = dict(var_results)
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
            def _infer_feature_type_and_source(var_name: str, original_series: pd.Series) -> Tuple[str, str]:
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
                    'correlation': float(correlations.get(var, 0.0)),
                    'vif': float(vif_data.get(var)) if vif_data.get(var) is not None else None,
                    'iv': float(iv_values.get(var)) if iv_values.get(var) is not None else None,
                    'iv_event': iv_event_label.get(var),
                    'abs_correlation': float(abs(correlations.get(var, 0.0))),
                    'missing_pct': missing_pct_map.get(var, 0.0),
                    # Variance statistics
                    'std': var_variance.get('std'),
                    'single_value_pct': var_variance.get('single_value_pct'),
                    'unique_count': var_variance.get('unique_count'),
                    'variance_status': var_variance.get('variance_status', 'unknown')
                }
                variable_stats.append(make_json_serializable(stats))

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

            result = {
                'variable_statistics': variable_stats,
                'summary': {
                    'total_variables': int(len(valid_independent)),
                    'high_correlation_count': int(len(high_corr_vars)),  # |Correlation| ≥ 0.05
                    'good_vif_count': int(len(good_vif_vars)),  # VIF ≤ 10
                    'strong_iv_count': int(len(strong_iv_vars)),  # IV ≥ 0.02
                    'good_variance_count': int(len(good_variance_vars)),  # Variance OK
                    'zero_variance_count': int(len(zero_variance_vars)),  # Zero variance (should be excluded)
                    'near_zero_variance_count': int(len(near_zero_variance_vars)),  # Near-zero variance (caution)
                    'high_correlation_variables': high_corr_vars,
                    'good_vif_variables': good_vif_vars,
                    'strong_iv_variables': strong_iv_vars,
                    'good_variance_variables': good_variance_vars,
                    'zero_variance_variables': zero_variance_vars,
                    'near_zero_variance_variables': near_zero_variance_vars
                },
                'interpretation': {
                    'vif_threshold': float(10.0),
                    'vif_interpretation': 'VIF ≤ 10 indicates acceptable multicollinearity',
                    'correlation_threshold_high': float(0.05),
                    'correlation_interpretation': 'Higher absolute correlation indicates stronger relationship with target',
                    'iv_threshold': float(0.02),
                    'iv_guideline': 'IV < 0.02 (useless), 0.02-0.1 (weak), 0.1-0.3 (medium), >0.3 (strong)',
                    'variance_interpretation': 'Zero variance = only 1 unique value (exclude), Near-zero variance = >95% same value or std<0.01 (caution)',
                    'variance_guideline': 'Variables with zero or near-zero variance have little predictive power and may cause model issues'
                }
            }

            # Ensure entire result is JSON serializable
            return make_json_serializable(result)

        except MemoryError as me:
            error_msg = str(me)
            self.logger.error(f"Memory allocation error calculating VIF and correlation: {error_msg}")
            # Return partial results without VIF if memory error occurs
            if 'valid_independent' in locals() and 'correlations' in locals():
                return {
                    'variables': valid_independent,
                    'correlations': correlations,
                    'vif_data': {},  # Empty VIF data due to memory error
                    'iv_values': iv_values if 'iv_values' in locals() else {},
                    'error': 'Memory allocation failed. Dataset too large for VIF calculation. Correlation values are still available.',
                    'memory_error': True
                }
            else:
                raise
        except Exception as e:
            error_msg = str(e)
            if "Unable to allocate" in error_msg or "MemoryError" in error_msg:
                self.logger.error(f"Memory allocation error calculating VIF and correlation: {error_msg}")
                # Return partial results without VIF if memory error occurs
                if 'valid_independent' in locals() and 'correlations' in locals():
                    return {
                        'variables': valid_independent,
                        'correlations': correlations,
                        'vif_data': {},  # Empty VIF data due to memory error
                        'iv_values': iv_values if 'iv_values' in locals() else {},
                        'error': 'Memory allocation failed. Dataset too large for VIF calculation. Correlation values are still available.',
                        'memory_error': True
                    }
                else:
                    raise
            else:
                self.logger.error(f"Error calculating VIF and correlation: {error_msg}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                raise

    def auto_select_variables(self, vif_correlation_data: Dict[str, Any],
                             problem_type: str) -> Dict[str, Any]:
        """
        Automatically select the best variables based on VIF, correlation, and IV analysis

        Args:
            vif_correlation_data: Results from calculate_vif_and_correlation
            problem_type: 'classification' or 'regression'

        Returns:
            Dictionary with selected variables and reasoning
        """
        try:
            variable_stats = vif_correlation_data['variable_statistics']
            summary = vif_correlation_data['summary']

            # Start with all variables
            selected_variables = []
            filtered_out_variables = []
            selection_criteria = []

            for var in variable_stats:
                var_name = var['variable']
                correlation = abs(var['correlation'])
                vif = var['vif']
                iv = var['iv']

                # Check exclusion criteria
                exclude_reasons = []

                # High VIF (multicollinearity)
                if vif is not None and vif > 10:
                    exclude_reasons.append(f"High VIF ({vif:.2f}) - multicollinearity")

                # Very low correlation
                if correlation < 0.05:
                    exclude_reasons.append(f"Very low correlation ({correlation:.4f})")

                # For classification, check IV
                if problem_type == 'classification' and iv is not None:
                    if iv < 0.02:
                        exclude_reasons.append(f"Low IV ({iv:.4f}) - not predictive")

                if exclude_reasons:
                    filtered_out_variables.append({
                        'variable': var_name,
                        'reasons': exclude_reasons
                    })
                    continue

                # Include variable
                selected_variables.append(var_name)
                selection_criteria.append({
                    'variable': var_name,
                    'correlation': correlation,
                    'vif': vif,
                    'iv': iv,
                    'reason': 'Passes all quality criteria'
                })

            # Ensure we have at least 2 variables for meaningful modeling
            if len(selected_variables) < 2:
                # If we filtered out too many, relax criteria
                self.logger.warning("Too few variables selected, relaxing criteria")
                for var in variable_stats:
                    if var['variable'] not in selected_variables:
                        var_name = var['variable']
                        correlation = abs(var['correlation'])

                        # Relaxed criteria: only exclude very high VIF and very low correlation
                        if var['vif'] is None or var['vif'] <= 20:  # Relaxed from 10 to 20
                            if correlation >= 0.01:  # Relaxed from 0.05 to 0.01
                                selected_variables.append(var_name)
                                selection_criteria.append({
                                    'variable': var_name,
                                    'correlation': correlation,
                                    'vif': var['vif'],
                                    'iv': var['iv'],
                                    'reason': 'Relaxed criteria - acceptable quality'
                                })
                                break

            # Final check - ensure we have variables
            if len(selected_variables) == 0:
                # Last resort: select top variables by correlation
                sorted_vars = sorted(variable_stats, key=lambda x: abs(x['correlation']), reverse=True)
                selected_variables = [v['variable'] for v in sorted_vars[:5]]  # Top 5 by correlation
                selection_criteria = [{
                    'variable': v['variable'],
                    'correlation': abs(v['correlation']),
                    'vif': v['vif'],
                    'iv': v['iv'],
                    'reason': 'Fallback selection - top by correlation'
                } for v in sorted_vars[:5]]

            return {
                'selected_variables': selected_variables,
                'filtered_out_variables': filtered_out_variables,
                'selection_criteria': selection_criteria,
                'summary': {
                    'total_analyzed': len(variable_stats),
                    'selected_count': len(selected_variables),
                    'filtered_count': len(filtered_out_variables),
                    'selection_method': 'automatic_statistical_criteria'
                }
            }

        except Exception as e:
            self.logger.error(f"Error in automatic variable selection: {str(e)}")
            raise

    def apply_variable_locking(
        self,
        independent_variables: List[str],
        selected_variables: Optional[List[str]] = None,
        locked_variables: Optional[List[str]] = None,
        selection_mode: str = "auto",
    ) -> Dict[str, Any]:
        """
        Apply Step 1 lock behavior.

        Locked variables are always included in the final selected set.
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
            self.logger.error(f"Error applying variable locking: {str(e)}")
            raise

    def auto_select_algorithms(self, problem_type: str, dataset_size: int,
                              num_features: int, feature_types: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        """
        Automatically select the best algorithms based on comprehensive problem characteristics

        Args:
            problem_type: 'classification' or 'regression'
            dataset_size: Number of rows in dataset
            num_features: Number of features
            feature_types: Optional dict with counts of numerical vs categorical features

        Returns:
            Dictionary with selected algorithms and reasoning
        """
        try:
            algorithms = []

            # Analyze feature characteristics
            num_numerical = feature_types.get('numerical', 0) if feature_types else num_features
            num_categorical = feature_types.get('categorical', 0) if feature_types else 0
            categorical_ratio = num_categorical / max(num_features, 1)

            # Determine dataset complexity
            is_small_dataset = dataset_size < 1000
            is_medium_dataset = dataset_size < 10000
            is_large_dataset = dataset_size >= 10000
            is_high_dimensional = num_features > 50
            has_many_categorical = categorical_ratio > 0.3

            if problem_type == 'classification':
                # Binary classification vs multi-class considerations
                if is_small_dataset:
                    # Small datasets: prioritize interpretability and speed
                    algorithms = [
                        {
                            'name': 'LogisticRegression',
                            'display_name': 'Logistic Regression',
                            'reason': 'Highly interpretable baseline for small datasets',
                            'priority': 1,
                            'characteristics': ['interpretable', 'fast', 'baseline']
                        },
                        {
                            'name': 'RandomForest',
                            'display_name': 'Random Forest',
                            'reason': 'Robust ensemble method, handles mixed data types well',
                            'priority': 2,
                            'characteristics': ['robust', 'mixed_data', 'ensemble']
                        }
                    ]
                    # Add SVM for very small, clean datasets
                    # if num_features < 10:
                    #     algorithms.append({
                    #         'name': 'SVM',
                    #         'display_name': 'Support Vector Machine',
                    #         'reason': 'Excellent for small, clean datasets with clear decision boundaries',
                    #         'priority': 3,
                    #         'characteristics': ['non_linear', 'clean_data', 'accurate']
                    #     })

                elif is_medium_dataset:
                    # Medium datasets: balance performance and efficiency
                    algorithms = [
                        {
                            'name': 'XGBoost',
                            'display_name': 'XGBoost',
                            'reason': 'Excellent balance of performance and speed for medium datasets',
                            'priority': 1,
                            'characteristics': ['gradient_boosting', 'regularized', 'fast']
                        },
                        {
                            'name': 'LightGBM',
                            'display_name': 'LightGBM',
                            'reason': 'Memory efficient with high accuracy for growing datasets',
                            'priority': 2,
                            'characteristics': ['lightweight', 'fast_training', 'memory_efficient']
                        }
                    ]

                    # Add traditional ML algorithms for diversity and interpretability
                    algorithms.append({
                        'name': 'LogisticRegression',
                        'display_name': 'Logistic Regression',
                        'reason': 'Interpretable baseline for classification problems',
                        'priority': 3,
                        'characteristics': ['interpretable', 'baseline', 'fast']
                    })

                    algorithms.append({
                        'name': 'RandomForest',
                        'display_name': 'Random Forest',
                        'reason': 'Reliable baseline, handles outliers and mixed data types',
                        'priority': 4,
                        'characteristics': ['robust', 'baseline', 'mixed_data']
                    })

                    # Add GradientBoosting for ensemble diversity
                    algorithms.append({
                        'name': 'GradientBoosting',
                        'display_name': 'Gradient Boosting',
                        'reason': 'Traditional gradient boosting for comparison with modern variants',
                        'priority': 5,
                        'characteristics': ['gradient_boosting', 'traditional', 'interpretable']
                    })

                    # Add CatBoost if significant categorical features
                    # COMMENTED OUT: User wants all 6 algorithms by default
                    # if has_many_categorical:
                    algorithms.append({
                        'name': 'CatBoost',
                        'display_name': 'CatBoost',
                        'reason': 'Native categorical feature handling with excellent performance',
                        'priority': 3,
                        'characteristics': ['categorical_native', 'automatic_encoding', 'accurate']
                    })

                else:  # Large datasets
                    # Large datasets: prioritize scalability and performance
                    algorithms = [
                        {
                            'name': 'XGBoost',
                            'display_name': 'XGBoost',
                            'reason': 'Industry standard for large-scale classification with regularization',
                            'priority': 1,
                            'characteristics': ['scalable', 'regularized', 'industry_standard']
                        },
                        {
                            'name': 'LightGBM',
                            'display_name': 'LightGBM',
                            'reason': 'Optimized for large datasets with minimal memory footprint',
                            'priority': 2,
                            'characteristics': ['memory_efficient', 'large_scale', 'optimized']
                        },
                        {
                            'name': 'CatBoost',
                            'display_name': 'CatBoost',
                            'reason': 'Handles large categorical datasets with automatic feature processing',
                            'priority': 3,
                            'characteristics': ['categorical_expert', 'automatic', 'large_scale']
                        }
                    ]

                    # Add traditional algorithms for comparison and robustness
                    algorithms.append({
                        'name': 'RandomForest',
                        'display_name': 'Random Forest',
                        'reason': 'Robust ensemble method for large-scale classification',
                        'priority': 4,
                        'characteristics': ['scalable', 'robust', 'ensemble']
                    })

                    algorithms.append({
                        'name': 'LogisticRegression',
                        'display_name': 'Logistic Regression',
                        'reason': 'Fast baseline for large classification problems',
                        'priority': 5,
                        'characteristics': ['fast', 'scalable', 'baseline']
                    })

                    # Add ensemble stacking for very large datasets
                    # COMMENTED OUT: User wants all 6 algorithms by default
                    # if dataset_size > 50000 or is_high_dimensional:
                    algorithms.append({
                        'name': 'GradientBoosting',
                        'display_name': 'Gradient Boosting',
                        'reason': 'Alternative gradient boosting implementation for ensemble diversity',
                        'priority': 4,
                        'characteristics': ['alternative_gb', 'diversity', 'ensemble']
                    })

            else:  # regression
                if is_small_dataset:
                    # Small datasets: simple, interpretable models
                    algorithms = [
                        {
                            'name': 'LinearRegression',
                            'display_name': 'Linear Regression',
                            'reason': 'Highly interpretable and fast for small regression problems',
                            'priority': 1,
                            'characteristics': ['interpretable', 'fast', 'baseline']
                        }
                    ]

                    # Add polynomial features for non-linear small datasets
                    if num_features < 5:
                        algorithms.append({
                            'name': 'PolynomialRegression',
                            'display_name': 'Polynomial Regression',
                            'reason': 'Captures non-linear relationships in small datasets',
                            'priority': 2,
                            'characteristics': ['non_linear', 'small_data', 'flexible']
                        })

                    algorithms.append({
                        'name': 'RandomForest',
                        'display_name': 'Random Forest',
                        'reason': 'Robust non-linear regression for small datasets',
                        'priority': 3,
                        'characteristics': ['robust', 'non_linear', 'ensemble']
                    })

                elif is_medium_dataset:
                    # Medium datasets: performance-focused
                    algorithms = [
                        {
                            'name': 'XGBoost',
                            'display_name': 'XGBoost',
                            'reason': 'Superior regression performance with regularization',
                            'priority': 1,
                            'characteristics': ['gradient_boosting', 'regularized', 'accurate']
                        },
                        {
                            'name': 'LightGBM',
                            'display_name': 'LightGBM',
                            'reason': 'Fast training with excellent regression accuracy',
                            'priority': 2,
                            'characteristics': ['fast_training', 'memory_efficient', 'accurate']
                        },
                        {
                            'name': 'RandomForest',
                            'display_name': 'Random Forest',
                            'reason': 'Reliable baseline for regression problems',
                            'priority': 3,
                            'characteristics': ['robust', 'baseline', 'reliable']
                        }
                    ]

                    # Add traditional algorithms for diversity
                    algorithms.append({
                        'name': 'GradientBoosting',
                        'display_name': 'Gradient Boosting',
                        'reason': 'Traditional gradient boosting for regression comparison',
                        'priority': 4,
                        'characteristics': ['gradient_boosting', 'traditional', 'reliable']
                    })

                    # Add CatBoost for mixed data types
                    if has_many_categorical:
                        algorithms.append({
                            'name': 'CatBoost',
                            'display_name': 'CatBoost',
                            'reason': 'Handles mixed numerical and categorical features seamlessly',
                            'priority': 3,
                            'characteristics': ['mixed_features', 'categorical', 'seamless']
                        })

                else:  # Large datasets
                    # Large datasets: scalable algorithms
                    algorithms = [
                        {
                            'name': 'XGBoost',
                            'display_name': 'XGBoost',
                            'reason': 'Proven performance for large-scale regression with regularization',
                            'priority': 1,
                            'characteristics': ['scalable', 'regularized', 'proven']
                        },
                        {
                            'name': 'LightGBM',
                            'display_name': 'LightGBM',
                            'reason': 'Optimized for large regression problems with memory efficiency',
                            'priority': 2,
                            'characteristics': ['memory_optimized', 'large_scale', 'efficient']
                        },
                        {
                            'name': 'CatBoost',
                            'display_name': 'CatBoost',
                            'reason': 'Excellent for large datasets with categorical features',
                            'priority': 3,
                            'characteristics': ['categorical_large', 'automatic', 'robust']
                        }
                    ]

                    # Add traditional algorithms for diversity in ensemble stacking
                    algorithms.append({
                        'name': 'RandomForest',
                        'display_name': 'Random Forest',
                        'reason': 'Provides ensemble diversity for large regression problems',
                        'priority': 4,
                        'characteristics': ['diversity', 'ensemble', 'robust']
                    })

                    algorithms.append({
                        'name': 'GradientBoosting',
                        'display_name': 'Gradient Boosting',
                        'reason': 'Alternative gradient boosting for large-scale regression',
                        'priority': 5,
                        'characteristics': ['traditional', 'gradient_boosting', 'large_scale']
                    })

            # Sort by priority and ensure we don't have too many algorithms
            algorithms.sort(key=lambda x: x['priority'])
            # Limit to top 6 algorithms to avoid excessive computation (changed from 5 to 6)
            algorithms = algorithms[:6]

            # Generate comprehensive selection reasoning
            reasoning = self._generate_algorithm_selection_reasoning(
                problem_type, dataset_size, num_features, categorical_ratio, algorithms
            )

            return {
                'selected_algorithms': algorithms,
                'selection_criteria': {
                    'dataset_size': dataset_size,
                    'num_features': num_features,
                    'categorical_ratio': categorical_ratio,
                    'problem_type': problem_type,
                    'selection_method': 'comprehensive_characteristics_analysis',
                    'dataset_complexity': {
                        'is_small': is_small_dataset,
                        'is_medium': is_medium_dataset,
                        'is_large': is_large_dataset,
                        'is_high_dimensional': is_high_dimensional,
                        'has_many_categorical': has_many_categorical
                    }
                },
                'selection_reasoning': reasoning
            }

        except Exception as e:
            self.logger.error(f"Error in automatic algorithm selection: {str(e)}")
            raise

    def _generate_algorithm_selection_reasoning(self, problem_type: str, dataset_size: int,
                                               num_features: int, categorical_ratio: float,
                                               selected_algorithms: List[Dict[str, Any]]) -> str:
        """Generate detailed reasoning for algorithm selection"""
        reasoning_parts = []

        # Dataset characteristics analysis
        size_category = "small" if dataset_size < 1000 else "medium" if dataset_size < 10000 else "large"
        reasoning_parts.append(f"Dataset size ({dataset_size} rows) classified as {size_category}")

        if num_features > 0:
            reasoning_parts.append(f"Feature count ({num_features}) classified as {'high-dimensional' if num_features > 50 else 'moderate-dimensional'}")

        if categorical_ratio > 0.5:
            reasoning_parts.append(f"High categorical feature ratio ({categorical_ratio:.1%}) - prioritizing categorical-aware algorithms")
        elif categorical_ratio > 0.2:
            reasoning_parts.append(f"Moderate categorical features ({categorical_ratio:.1%}) - considering categorical handling")

        # Algorithm-specific reasoning
        for algo in selected_algorithms[:3]:  # Top 3 algorithms
            characteristics = algo.get('characteristics', [])
            if 'interpretable' in characteristics:
                reasoning_parts.append(f"{algo['display_name']}: Selected for interpretability")
            elif 'scalable' in characteristics:
                reasoning_parts.append(f"{algo['display_name']}: Selected for scalability on {size_category} datasets")
            elif 'memory_efficient' in characteristics:
                reasoning_parts.append(f"{algo['display_name']}: Selected for memory efficiency")
            elif 'categorical' in characteristics:
                reasoning_parts.append(f"{algo['display_name']}: Selected for categorical feature handling")

        return "; ".join(reasoning_parts)

    # DEPRECATED: auto_configure_hyperparameters - NOT USED IN REAL TRAINING
    # Real training uses _get_hyperparameter_space() + _sample_hyperparameters() instead
    # This function was designed to configure hyperparameters based on dataset size,
    # but the actual implementation uses a search space with random sampling (10 iterations)
    # 
    # def auto_configure_hyperparameters(self, algorithm: str, problem_type: str,
    #                                  dataset_size: int, num_features: int,
    #                                  y_train: Optional[pd.Series] = None) -> Dict[str, Any]:
    #     """
    #     Automatically configure optimal hyperparameters based on algorithm and dataset characteristics
    # 
    #     Args:
    #         algorithm: Name of the algorithm
    #         problem_type: 'classification' or 'regression'
    #         dataset_size: Number of rows
    #         num_features: Number of features
    #         y_train: Training target variable (optional, for class imbalance detection)
    # 
    #     Returns:
    #         Dictionary with optimized hyperparameters
    #     """
    #     try:
    #         # Base config varies by algorithm since some don't support all parameters
    #         catboost_base = {
    #             'random_state': 42,
    #             'verbose': 0
    #         }
    # 
    #         sklearn_base = {
    #             'random_state': 42,
    #             'n_jobs': -1,
    #             'verbose': 0
    #         }
    # 
    #         if algorithm == 'XGBoost':
    #             if problem_type == 'classification':
    #                 config = {
    #                     'max_depth': min(6, max(3, int(np.log2(dataset_size) / 2))),
    #                     'min_child_weight': max(1, int(dataset_size / 1000)),
    #                     'learning_rate': 0.3,  # Optimized: Increased for faster training
    #                     'n_estimators': min(50, max(30, int(dataset_size / 50))),  # Optimized: Reduced from 50-200 to 30-50
    #                     'subsample': 0.8 if dataset_size > 1000 else 1.0,
    #                     'colsample_bytree': min(0.8, max(0.5, num_features / 20))
    #                 }
    #                 # Add scale_pos_weight for imbalanced data
    #                 if y_train is not None:
    #                     imbalance_info = self.detect_class_imbalance(y_train)
    #                     if imbalance_info['is_imbalanced'] and len(imbalance_info['class_distribution']) == 2:
    #                         class_counts = imbalance_info['class_distribution']
    #                         classes = list(class_counts.keys())
    #                         scale_pos_weight = class_counts[classes[0]] / class_counts[classes[1]]
    #                         config['scale_pos_weight'] = float(scale_pos_weight)
    #                         self.logger.info(f"XGBoost: Added scale_pos_weight={scale_pos_weight:.2f} for imbalanced data (ratio: {imbalance_info['imbalance_ratio']:.2f})")
    #             else:  # regression
    #                 config = {
    #                     'max_depth': min(6, max(3, int(np.log2(dataset_size) / 2))),
    #                     'min_child_weight': max(1, int(dataset_size / 1000)),
    #                     'learning_rate': 0.3,  # Optimized: Increased for faster training
    #                     'n_estimators': min(50, max(30, int(dataset_size / 50))),  # Optimized: Reduced from 50-200 to 30-50
    #                     'subsample': 0.8 if dataset_size > 1000 else 1.0,
    #                     'colsample_bytree': min(0.8, max(0.5, num_features / 20))
    #                 }
    # 
    #         elif algorithm == 'LightGBM':
    #             if problem_type == 'classification':
    #                 config = {
    #                     'max_depth': min(8, max(-1, int(np.log2(dataset_size)))),
    #                     'num_leaves': min(64, max(16, int(2 ** (np.log2(dataset_size) / 3)))),
    #                     'learning_rate': 0.3,  # Optimized: Increased for faster training
    #                     'n_estimators': min(100, max(50, int(dataset_size / 20))),  # Optimized: Reduced from 100-300 to 50-100
    #                     'min_child_samples': max(10, int(dataset_size / 100)),
    #                     'subsample': 0.8 if dataset_size > 2000 else 1.0
    #                 }
    #                 # Add class_weight for imbalanced data
    #                 if y_train is not None:
    #                     imbalance_info = self.detect_class_imbalance(y_train)
    #                     if imbalance_info['is_imbalanced']:
    #                         config['class_weight'] = 'balanced'
    #                         self.logger.info(f"LightGBM: Added class_weight='balanced' for imbalanced data (ratio: {imbalance_info['imbalance_ratio']:.2f})")
    #             else:  # regression
    #                 config = {
    #                     'max_depth': min(8, max(-1, int(np.log2(dataset_size)))),
    #                     'num_leaves': min(64, max(16, int(2 ** (np.log2(dataset_size) / 3)))),
    #                     'learning_rate': 0.3,  # Optimized: Increased for faster training
    #                     'n_estimators': min(100, max(50, int(dataset_size / 20))),  # Optimized: Reduced from 100-300 to 50-100
    #                     'min_child_samples': max(10, int(dataset_size / 100)),
    #                     'subsample': 0.8 if dataset_size > 2000 else 1.0
    #                 }
    # 
    #         elif algorithm == 'RandomForest':
    #             # Calculate max_features as a fraction, but ensure it's reasonable
    #             max_features_fraction = max(0.1, min(0.8, num_features / 10))
    #             config = {
    #                 'n_estimators': min(50, max(30, int(dataset_size / 50))),  # Optimized: Reduced from 50-200 to 30-50
    #                 'max_depth': min(15, max(5, int(np.log2(dataset_size)))),
    #                 'min_samples_split': max(2, int(dataset_size / 200)),
    #                 'min_samples_leaf': max(1, int(dataset_size / 500)),
    #                 'max_features': 'sqrt' if num_features > 10 else max_features_fraction,
    #                 'bootstrap': True
    #             }
    #             # Add class_weight for imbalanced data (only for classification)
    #             if problem_type == 'classification' and y_train is not None:
    #                 imbalance_info = self.detect_class_imbalance(y_train)
    #                 if imbalance_info['is_imbalanced']:
    #                     config['class_weight'] = 'balanced'
    #                     self.logger.info(f"RandomForest: Added class_weight='balanced' for imbalanced data (ratio: {imbalance_info['imbalance_ratio']:.2f})")
    # 
    #         elif algorithm == 'LogisticRegression':
    #             config = {
    #                 'C': 1.0 if dataset_size > 1000 else 0.1,
    #                 'max_iter': 200,  # Optimized: Reduced from 1000 to 200 for faster training
    #                 'solver': 'liblinear' if dataset_size < 10000 else 'lbfgs'
    #             }
    # 
    #         elif algorithm == 'LinearRegression':
    #             config = {}  # No hyperparameters to tune
    # 
    #         elif algorithm == 'LogisticRegression':
    #             config = {
    #                 'C': 1.0 if dataset_size > 1000 else 0.1,
    #                 'max_iter': 200,  # Optimized: Reduced from 1000 to 200 for faster training
    #                 'solver': 'liblinear' if dataset_size < 10000 else 'lbfgs'
    #             }
    #             # Add class_weight for imbalanced data
    #             if problem_type == 'classification' and y_train is not None:
    #                 imbalance_info = self.detect_class_imbalance(y_train)
    #                 if imbalance_info['is_imbalanced']:
    #                     config['class_weight'] = 'balanced'
    #                     self.logger.info(f"LogisticRegression: Added class_weight='balanced' for imbalanced data (ratio: {imbalance_info['imbalance_ratio']:.2f})")
    # 
    #         elif algorithm == 'GradientBoosting':
    #             if problem_type == 'classification':
    #                 config = {
    #                     'n_estimators': min(200, max(50, int(dataset_size / 20))),
    #                     'max_depth': min(6, max(3, int(np.log2(dataset_size) / 3))),
    #                     'min_samples_split': max(2, int(dataset_size / 1000)),
    #                     'min_samples_leaf': max(1, int(dataset_size / 2000)),
    #                     'learning_rate': 0.1 if dataset_size > 5000 else 0.2,
    #                     'subsample': 0.8 if dataset_size > 1000 else 1.0
    #                 }
    #                 # Add class_weight for imbalanced data
    #                 if y_train is not None:
    #                     imbalance_info = self.detect_class_imbalance(y_train)
    #                     if imbalance_info['is_imbalanced']:
    #                         config['class_weight'] = 'balanced'
    #                         self.logger.info(f"GradientBoosting: Added class_weight='balanced' for imbalanced data (ratio: {imbalance_info['imbalance_ratio']:.2f})")
    #             else:  # regression
    #                 config = {
    #                     'n_estimators': min(200, max(50, int(dataset_size / 20))),
    #                     'max_depth': min(6, max(3, int(np.log2(dataset_size) / 3))),
    #                     'min_samples_split': max(2, int(dataset_size / 1000)),
    #                     'min_samples_leaf': max(1, int(dataset_size / 2000)),
    #                     'learning_rate': 0.1 if dataset_size > 5000 else 0.2,
    #                     'subsample': 0.8 if dataset_size > 1000 else 1.0
    #                 }
    # 
    #         elif algorithm == 'CatBoost':
    #             config = {
    #                 'depth': min(6, max(3, int(np.log2(dataset_size) / 2))),
    #                 'learning_rate': 0.03 if dataset_size > 5000 else 0.1,
    #                 'iterations': min(500, max(100, int(dataset_size / 20))),
    #                 'verbose': 0
    #             }
    #             # Add class_weights for imbalanced data (CatBoost supports this)
    #             if problem_type == 'classification' and y_train is not None:
    #                 imbalance_info = self.detect_class_imbalance(y_train)
    #                 if imbalance_info['is_imbalanced']:
    #                     # Calculate class weights: inverse of class frequency
    #                     class_counts = imbalance_info['class_distribution']
    #                     total = sum(class_counts.values())
    #                     class_weights = {int(k): total / (len(class_counts) * v) for k, v in class_counts.items()}
    #                     config['class_weights'] = class_weights
    #                     self.logger.info(f"CatBoost: Added class_weights for imbalanced data (ratio: {imbalance_info['imbalance_ratio']:.2f})")
    # 
    #         elif algorithm == 'SVM':
    #             if problem_type == 'classification':
    #                 config = {
    #                     'C': 1.0 if dataset_size > 1000 else 0.1,
    #                     'kernel': 'rbf' if num_features < 10 else 'linear',
    #                     'gamma': 'scale' if num_features < 5 else 'auto',
    #                     'probability': True  # Enable probability estimation for metrics
    #                 }
    #             else:  # regression
    #                 config = {
    #                     'C': 1.0 if dataset_size > 1000 else 0.1,
    #                     'kernel': 'rbf' if num_features < 10 else 'linear',
    #                     'gamma': 'scale' if num_features < 5 else 'auto'
    #                 }
    # 
    #         else:
    #             config = {}
    # 
    #         # Use appropriate base config based on algorithm
    #         if algorithm in ['CatBoost']:
    #             final_config = {**catboost_base, **config}
    #         else:
    #             final_config = {**sklearn_base, **config}
    # 
    #         # Return only the parameters that should be passed to the model
    #         # Filter out logging/debugging parameters that aren't model parameters
    #         model_params = {k: v for k, v in final_config.items()
    #                        if k not in ['configuration_method', 'dataset_size', 'num_features']}
    #         
    #         # Remove n_jobs for algorithms that don't support it
    #         if algorithm == 'GradientBoosting':
    #             model_params.pop('n_jobs', None)
    # 
    #         return model_params
    # 
    #     except Exception as e:
    #         self.logger.error(f"Error configuring hyperparameters for {algorithm}: {str(e)}")
    #         return {'random_state': 42}

    def preprocess_data(self, df: pd.DataFrame, target_column: str,
                       independent_variables: List[str]) -> Tuple[pd.DataFrame, pd.Series]:
        """Preprocess data for machine learning - skips if already preprocessed"""
        try:
            # Select only required columns
            feature_columns = [col for col in independent_variables if col in df.columns]

            # Include feature engineered columns by default so FE results flow into training
            # (FE creates columns like *_transform_log, *_transform_woe, *_transform_OHE_*).
            transform_cols = [c for c in df.columns if "transform" in c and c != target_column]
            for c in transform_cols:
                if c not in feature_columns:
                    feature_columns.append(c)
            if target_column not in df.columns:
                raise ValueError(f"Target column '{target_column}' not found in dataset")

            # Prepare features and target
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
                self.label_encoders = {}
                self.scaler = None
                self.scaler_columns = []
                self.sparse_ohe_columns = [col for col in X.columns if '_transform_OHE' in col]
                self.pre_encoding_feature_columns = list(X.columns)
                self.model_feature_columns = list(X.columns)
                # X is not mutated in this path - no copy needed; share the reference
                self.X_before_scaling = X
                self.X_before_encoding = X
                
                # Check if target needs encoding (even if data is preprocessed)
                # Handle object, category, and string dtypes (including StringDtype, string[pyarrow], etc.)
                is_target_string_or_cat = (
                    y.dtype in ['object', 'category'] or
                    pd.api.types.is_string_dtype(y) or
                    str(y.dtype).startswith('string')
                )
                if is_target_string_or_cat:
                    self.logger.info("Target column is categorical in preprocessed data. Encoding to numeric.")
                    le_target = LabelEncoder()
                    y = pd.Series(le_target.fit_transform(y.astype(str)), index=y.index, name=y.name)
                    self.target_encoder = le_target
                    self.logger.info(f"Target classes: {dict(zip(le_target.classes_, range(len(le_target.classes_))))}")
                else:
                    self.target_encoder = None
                
                # Store preprocessing summary
                self.preprocessing_summary = preprocessing_summary
                
                self.logger.info(f"Using preprocessed data: {X.shape[0]} samples, {X.shape[1]} features")
                return X, y
            
            # DATA NOT PREPROCESSED - DO FULL PREPROCESSING
            self.logger.info("Data not preprocessed. Starting full preprocessing pipeline.")
            
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
            if y.isna().any():
                nan_mask = y.isna()
                self.logger.warning(f"Dropping {nan_mask.sum()} rows with NaN target values")
                X = X[~nan_mask]
                y = y[~nan_mask]
            
            # STEP 2.5: Encode categorical target to numeric (if needed)
            # Handle object, category, and string dtypes (including StringDtype, string[pyarrow], etc.)
            is_target_string_or_cat = (
                y.dtype in ['object', 'category'] or
                pd.api.types.is_string_dtype(y) or
                str(y.dtype).startswith('string')
            )
            if is_target_string_or_cat:
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
            
            # Batch fill numeric columns with median - VECTORIZED
            num_cols_with_missing = [c for c in cols_with_missing if c in num_cols and c not in sparse_ohe_columns]
            if num_cols_with_missing:
                # Compute all medians at once
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

            # STEP 4: Encode categorical variables (convert to numerical)
            # CRITICAL: Store original data BEFORE encoding for granular accuracy
            X_before_encoding = X.copy()  # Store original categorical values (strings like "RENT", "OWN", etc.)
            
            categorical_columns = X.select_dtypes(include=['object', 'category']).columns
            label_encoders = {}
            for col in categorical_columns:
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))
                label_encoders[col] = le
                
                # Create mapping for display
                class_mapping = dict(zip(le.classes_, range(len(le.classes_))))
                mapping_sample = {str(k): int(v) for k, v in list(class_mapping.items())[:5]}
                
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

            # STEP 5: Scale numerical features
            # Capture pre-scaling stats BEFORE transforming (avoids an extra full copy of X)
            numerical_columns = X.select_dtypes(include=[np.number]).columns
            
            # OPTIMIZATION: Skip scaling for sparse/binary OHE columns
            # OHE columns are already 0/1 binary - scaling them is unnecessary and can hurt performance
            cols_to_scale = [col for col in numerical_columns if col not in sparse_ohe_columns]
            skipped_ohe_cols = [col for col in numerical_columns if col in sparse_ohe_columns]
            
            if skipped_ohe_cols:
                self.logger.info(f"Skipping scaling for {len(skipped_ohe_cols)} OHE columns (already binary 0/1)")
            
            if len(cols_to_scale) > 0:
                scaler = StandardScaler()
                # Store original ranges before scaling (vectorized - no copy needed)
                original_ranges = {}
                if cols_to_scale:
                    _desc = X[cols_to_scale].agg(['min', 'max', 'mean', 'std'])
                    for col in cols_to_scale:
                        original_ranges[col] = {
                            'min': float(_desc.loc['min', col]),
                            'max': float(_desc.loc['max', col]),
                            'mean': float(_desc.loc['mean', col]),
                            'std': float(_desc.loc['std', col]) if not pd.isna(_desc.loc['std', col]) else 0.0,
                        }
                # Store pre-scaling snapshot (needed as fallback for granular accuracy)
                X_before_scaling = X.copy()
                X[cols_to_scale] = scaler.fit_transform(X[cols_to_scale])
                # Vectorized scaled-range computation (avoids per-column Python loop)
                _scaled_desc = X[cols_to_scale].agg(['min', 'max', 'mean', 'std'])
                for col in cols_to_scale:
                    scaled_min = float(_scaled_desc.loc['min', col])
                    scaled_max = float(_scaled_desc.loc['max', col])
                    scaled_mean = float(_scaled_desc.loc['mean', col])
                    scaled_std = float(_scaled_desc.loc['std', col]) if not pd.isna(_scaled_desc.loc['std', col]) else 0.0
                    
                    if col in missing_value_details:
                        missing_value_details[col]['scaling'] = {
                            'method': 'standard_scaling',
                            'original_range': [original_ranges[col]['min'], original_ranges[col]['max']],
                            'scaled_range': [scaled_min, scaled_max],
                            'original_mean': original_ranges[col]['mean'],
                            'original_std': original_ranges[col]['std'],
                            'reason': 'Numeric feature needs normalization for ML models'
                        }
                    else:
                        missing_value_details[col] = {
                            'variable': col,
                            'missing_imputation': None,
                            'encoding': None,
                            'scaling': {
                                'method': 'standard_scaling',
                                'original_range': [original_ranges[col]['min'], original_ranges[col]['max']],
                                'scaled_range': [scaled_min, scaled_max],
                                'original_mean': original_ranges[col]['mean'],
                                'original_std': original_ranges[col]['std'],
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

            # Check for constant variables
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

            # Store preprocessing objects for later use
            self.label_encoders = label_encoders
            self.scaler = scaler
            self.scaler_columns = list(cols_to_scale)
            self.sparse_ohe_columns = list(sparse_ohe_columns)
            self.pre_encoding_feature_columns = list(X_before_encoding.columns)
            self.model_feature_columns = list(X.columns)
            self.X_before_scaling = X_before_scaling  # Store data before scaling for continuous variables
            self.X_before_encoding = X_before_encoding  # Store data before encoding for categorical variables (original string values)
            self.preprocessing_summary = preprocessing_summary

            self.logger.info(f"Data preprocessed: {X.shape[0]} samples, {X.shape[1]} features (all numerical)")
            return X, y

        except Exception as e:
            self.logger.error(f"Error preprocessing data: {str(e)}")
            raise

    # DEPRECATED: generate_training_iterations - NOT CALLED ANYWHERE IN CODEBASE
    # This function was designed to generate demo/visualization data for UI showing training iterations
    # However, the actual training happens in train_single_algorithm() (Line 2219) which uses real model.fit()
    # This function only uses simulated scoring (_simulate_model_performance) so it's not used in production
    # 
    # def generate_training_iterations(self, algorithm: str, problem_type: str,
    #                                dataset_size: int, num_features: int) -> Dict[str, Any]:
    #     """
    #     Generate detailed training iterations with hyperparameter evolution
    # 
    #     Args:
    #         algorithm: Name of the algorithm
    #         problem_type: 'classification' or 'regression'
    #         dataset_size: Number of rows
    #         num_features: Number of features
    # 
    #     Returns:
    #         Dictionary with iteration history and hyperparameter evolution
    #     """
    #     try:
    #         # Define hyperparameter search space based on algorithm
    #         hyperparam_space = self._get_hyperparameter_space(algorithm, problem_type, dataset_size, num_features)
    # 
    #         # Simulate multiple iterations with different hyperparameters
    #         iterations = []
    #         best_score = 0
    #         best_params = {}
    # 
    #         num_iterations = min(10, max(3, dataset_size // 100))  # Adaptive number of iterations
    # 
    #         for iteration in range(1, num_iterations + 1):
    #             # Sample hyperparameters
    #             params = self._sample_hyperparameters(hyperparam_space)
    # 
    #             # Simulate performance (in real implementation, this would be actual training)
    #             score = self._simulate_model_performance(algorithm, params, dataset_size, num_features, iteration)
    # 
    #             # Track improvement
    #             improvement = score - best_score if iteration > 1 else 0
    # 
    #             # Update best if improved
    #             if score > best_score:
    #                 best_score = score
    #                 best_params = make_json_serializable(params.copy())
    # 
    #             # Calculate detailed metrics for this iteration
    #             iteration_metrics = make_json_serializable(self._calculate_iteration_metrics(score, algorithm, problem_type))
    # 
    #             iterations.append({
    #                 'iteration': int(iteration),
    #                 'score': float(score),
    #                 'improvement': float(improvement),
    #                 'hyperparameters': make_json_serializable(params),
    #                 'status': 'Best Score' if score == best_score else 'Completed',
    #                 'metrics': iteration_metrics,
    #                 'timestamp': datetime.now().strftime("%H:%M:%S")
    #             })
    # 
    #         return {
    #             'iterations': make_json_serializable(iterations),
    #             'best_score': float(best_score),
    #             'best_hyperparameters': make_json_serializable(best_params),
    #             'total_iterations': int(num_iterations),
    #             'convergence_iteration': int(self._find_convergence_iteration(iterations)),
    #             'hyperparameter_evolution': make_json_serializable(self._track_hyperparameter_evolution(iterations))
    #         }
    # 
    #     except Exception as e:
    #         self.logger.error(f"Error generating training iterations: {str(e)}")
    #         return {'iterations': [], 'best_score': 0, 'best_hyperparameters': {}}

    def _get_hyperparameter_space(self, algorithm: str, problem_type: str,
                                dataset_size: int, num_features: int) -> Dict[str, Any]:
        """Get hyperparameter search space for the algorithm"""
        # HYPERPARAMETER_CONFIG - OPTIMIZED for faster training
        # CRITICAL: Reduced n_estimators/iterations for hyperparameter search phase
        # Final model will be retrained with optimal params if needed
        HYPERPARAMETER_CONFIG = {
            'xgboost': {
                'max_depth': {'step': 1, 'min': 3, 'max': 10},  # Reduced from 1-15 to 3-10
                'min_child_weight': {'step': 1, 'min': 1, 'max': 7},  # Simplified
                'gamma': {'step': 0.1, 'min': 0, 'max': 2},  # Reduced from 0-5
                'learning_rate': {'step': 0.01, 'min': 0.01, 'max': 0.3},  # Narrowed range
                'n_estimators': {'step': 25, 'min': 50, 'max': 200},  # CRITICAL: Reduced from 10-500 to 50-200
                'subsample': {'step': 0.1, 'min': 0.6, 'max': 1.0},
                'colsample_bytree': {'step': 0.1, 'min': 0.6, 'max': 1.0},
            },
            'lightgbm': {
                'max_depth': {'step': 1, 'min': 3, 'max': 10},  # Reduced from 1-15
                'num_leaves': {'step': 10, 'min': 20, 'max': 100},  # Reduced from 10-255
                'learning_rate': {'step': 0.01, 'min': 0.01, 'max': 0.3},
                'n_estimators': {'step': 25, 'min': 50, 'max': 200},  # CRITICAL: Reduced from 10-500
                'min_child_samples': {'step': 5, 'min': 5, 'max': 30},
                'subsample': {'step': 0.1, 'min': 0.6, 'max': 1.0},
            },
            'random_forest': {
                'max_depth': {'step': 2, 'min': 5, 'max': 20},  # Reduced from 1-30
                'min_samples_split': {'step': 2, 'min': 2, 'max': 20},  # Reduced from 2-50
                'min_samples_leaf': {'step': 1, 'min': 1, 'max': 10},  # Reduced from 1-20
                'n_estimators': {'step': 25, 'min': 50, 'max': 200},  # CRITICAL: Reduced from 10-500
                'max_features': {'step': 0.1, 'min': 0.3, 'max': 1.0},
            },
            'gradient_boosting': {
                # HistGradientBoosting params (replaces legacy GradientBoosting)
                'max_depth': {'step': 1, 'min': 3, 'max': 8},
                'learning_rate': {'step': 0.05, 'min': 0.05, 'max': 0.3},
                'max_iter': {'step': 25, 'min': 50, 'max': 200},  # max_iter replaces n_estimators
                'max_leaf_nodes': {'step': 10, 'min': 20, 'max': 60},
                'l2_regularization': {'step': 0.1, 'min': 0.0, 'max': 1.0},
            },
            'catboost': {
                'depth': {'step': 1, 'min': 4, 'max': 8},  # Reduced from 1-12
                'learning_rate': {'step': 0.01, 'min': 0.01, 'max': 0.3},
                'iterations': {'step': 25, 'min': 50, 'max': 200},  # CRITICAL: Reduced from 10-500
                'l2_leaf_reg': {'step': 0.5, 'min': 1, 'max': 5},
            },
            'logistic_regression': {
                'C': {'step': 0.5, 'min': 0.01, 'max': 10},  # Reduced from 0.001-1000 (log scale is better)
                'max_iter': {'step': 50, 'min': 100, 'max': 300},  # Capped: 300 is sufficient for scaled data; saga removed
            }
        }
        
        def generate_values_from_config(param_config: Dict[str, Any], reasonable_count: int = 10) -> List[Any]:
            """Generate reasonable discrete values from HYPERPARAMETER_CONFIG"""
            step = param_config.get('step', 1)
            min_val = param_config.get('min', 0)
            max_val = param_config.get('max', 100)
            
            # For very large ranges, sample reasonable values instead of exhaustive
            total_possible = int((max_val - min_val) / step) + 1
            
            if total_possible <= reasonable_count:
                # Small range - generate all values
                if isinstance(min_val, int) and isinstance(max_val, int) and isinstance(step, int):
                    return list(range(int(min_val), int(max_val) + 1, int(step)))
                else:
                    num_steps = int((max_val - min_val) / step) + 1
                    values = [round(float(min_val) + i * float(step), 8) for i in range(num_steps)]
                    if values[-1] < max_val:
                        values.append(max_val)
                    return values
            else:
                # Large range - sample reasonable values
                if isinstance(min_val, int) and isinstance(max_val, int):
                    # Sample evenly spaced integers
                    step_size = max(1, (max_val - min_val) // reasonable_count)
                    return list(range(int(min_val), int(max_val) + 1, step_size))
                else:
                    # Sample evenly spaced floats
                    step_size = (max_val - min_val) / reasonable_count
                    return [round(float(min_val) + i * step_size, 8) for i in range(reasonable_count + 1)]
        
        # Normalize algorithm name for lookup (matching manual training)
        normalized_name = algorithm.lower()
        if normalized_name in ['logisticregression', 'logistic_regression']:
            normalized_name = 'logistic_regression'
        elif normalized_name in ['randomforest', 'random_forest', 'rf']:
            normalized_name = 'random_forest'
        elif normalized_name in ['gradientboosting', 'gb', 'gradient_boosting']:
            normalized_name = 'gradient_boosting'
        elif normalized_name in ['xgb']:
            normalized_name = 'xgboost'
        elif normalized_name in ['lgbm']:
            normalized_name = 'lightgbm'
        
        # Handle SVM separately (not in HYPERPARAMETER_CONFIG)
        if normalized_name == 'svm':
            return {
                'C': [0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
                'kernel': ['linear', 'rbf', 'poly', 'sigmoid'],
                'gamma': ['scale', 'auto', 0.001, 0.01, 0.1, 1.0]
            }
        
        # Get config for this algorithm
        config = HYPERPARAMETER_CONFIG.get(normalized_name, {})
        
        if not config:
            return {}
        
        # Generate search space from HYPERPARAMETER_CONFIG
        search_space = {}
        
        # Define which parameters to include for each algorithm (matching manual training style)
        param_selection = {
            'xgboost': ['max_depth', 'min_child_weight', 'learning_rate', 'n_estimators', 'subsample', 'colsample_bytree'],
            'lightgbm': ['max_depth', 'num_leaves', 'learning_rate', 'n_estimators', 'min_child_samples', 'subsample'],
            'random_forest': ['max_depth', 'min_samples_split', 'min_samples_leaf', 'n_estimators', 'max_features'],
            'gradient_boosting': ['max_depth', 'learning_rate', 'max_iter', 'max_leaf_nodes', 'l2_regularization'],
            'catboost': ['depth', 'learning_rate', 'iterations', 'l2_leaf_reg'],
            'logistic_regression': ['C', 'max_iter', 'solver']
        }
        
        # Generate values for selected parameters
        selected_params = param_selection.get(normalized_name, list(config.keys()))
        
        for param_name in selected_params:
            # Special handling for categorical parameters (not in HYPERPARAMETER_CONFIG)
            if param_name == 'max_features':
                search_space[param_name] = ['sqrt', 'log2']
            elif param_name == 'solver':
                # saga excluded: on scaled dense data it is 20-100x slower than lbfgs/liblinear
                search_space[param_name] = ['liblinear', 'lbfgs']
            elif param_name == 'kernel':
                search_space[param_name] = ['linear', 'rbf', 'poly', 'sigmoid']
            elif param_name == 'gamma' and normalized_name == 'svm':
                search_space[param_name] = ['scale', 'auto', 0.001, 0.01, 0.1, 1.0]
            elif param_name in config:
                # Generate discrete values from config
                param_config = config[param_name]
                search_space[param_name] = generate_values_from_config(param_config)
        
        return search_space

    def _sample_hyperparameters(self, space: Dict[str, Any]) -> Dict[str, Any]:
        """Sample random hyperparameters from the search space"""
        sampled = {}
        for param, values in space.items():
            if isinstance(values, list) and len(values) > 0:
                sampled[param] = np.random.choice(values)
            else:
                sampled[param] = values
        return sampled
    
    def _create_model_instance(self, algorithm_name: str, problem_type: str, params: Dict[str, Any]) -> Any:
        """Create model instance with given parameters"""
        # Import models (same as in train_single_algorithm)
        try:
            from xgboost import XGBClassifier, XGBRegressor
        except ImportError:
            XGBClassifier = None
            XGBRegressor = None
        
        try:
            from lightgbm import LGBMClassifier, LGBMRegressor
        except ImportError:
            LGBMClassifier = None
            LGBMRegressor = None
        
        try:
            from catboost import CatBoostClassifier, CatBoostRegressor
        except ImportError:
            CatBoostClassifier = None
            CatBoostRegressor = None
        
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
        from sklearn.linear_model import LogisticRegression, LinearRegression
        from sklearn.svm import SVC, SVR

        import os as _os
        _total_cores = _os.cpu_count() or 4
        _per_model_jobs = max(1, min(8, _total_cores // 2))

        if problem_type == 'classification':
            if algorithm_name == 'XGBoost' and XGBClassifier:
                params['n_jobs'] = _per_model_jobs
                params['tree_method'] = 'hist'
                params['eval_metric'] = 'auc'
                return XGBClassifier(**params)
            elif algorithm_name == 'LightGBM' and LGBMClassifier:
                params['n_jobs'] = _per_model_jobs
                params['verbose'] = -1
                return LGBMClassifier(**params)
            elif algorithm_name == 'CatBoost' and CatBoostClassifier:
                params['thread_count'] = _per_model_jobs
                return CatBoostClassifier(**params, verbose=False)
            elif algorithm_name == 'SVM':
                return SVC(**params)
            elif algorithm_name == 'RandomForest':
                params['n_jobs'] = _per_model_jobs
                return RandomForestClassifier(**params)
            elif algorithm_name == 'LogisticRegression':
                params['n_jobs'] = _per_model_jobs
                if 'solver' not in params:
                    params['solver'] = 'lbfgs'
                return LogisticRegression(**params)
            elif algorithm_name == 'GradientBoosting':
                # HistGradientBoosting: histogram-based, multi-threaded, 10-20x faster than legacy GradientBoosting
                _hgb_params = {k: v for k, v in params.items() if k in (
                    'max_iter', 'max_depth', 'learning_rate', 'l2_regularization',
                    'max_leaf_nodes', 'min_samples_leaf', 'random_state'
                )}
                return HistGradientBoostingClassifier(early_stopping=True, n_iter_no_change=10, **_hgb_params)
        else:  # regression
            if algorithm_name == 'XGBoost' and XGBRegressor:
                params['n_jobs'] = _per_model_jobs
                params['tree_method'] = 'hist'
                return XGBRegressor(**params)
            elif algorithm_name == 'LightGBM' and LGBMRegressor:
                params['n_jobs'] = _per_model_jobs
                params['verbose'] = -1
                return LGBMRegressor(**params)
            elif algorithm_name == 'CatBoost' and CatBoostRegressor:
                params['thread_count'] = _per_model_jobs
                return CatBoostRegressor(**params, verbose=False)
            elif algorithm_name == 'SVM':
                return SVR(**params)
            elif algorithm_name == 'RandomForest':
                params['n_jobs'] = _per_model_jobs
                return RandomForestRegressor(**params)
            elif algorithm_name == 'LinearRegression':
                return LinearRegression(**params)
            elif algorithm_name == 'GradientBoosting':
                _hgb_params = {k: v for k, v in params.items() if k in (
                    'max_iter', 'max_depth', 'learning_rate', 'l2_regularization',
                    'max_leaf_nodes', 'min_samples_leaf', 'random_state'
                )}
                return HistGradientBoostingRegressor(early_stopping=True, n_iter_no_change=10, **_hgb_params)
        return None

    # DEPRECATED: _simulate_model_performance - ONLY USED FOR VISUALIZATION IN generate_training_iterations()
    # NOT USED IN REAL TRAINING (train_single_algorithm uses actual model.fit() instead)
    # This function generates fake scores for demo/UI purposes only
    # 
    # def _simulate_model_performance(self, algorithm: str, params: Dict[str, Any],
    #                               dataset_size: int, num_features: int, iteration: int) -> float:
    #     """Simulate model performance for visualization (replace with actual training)"""
    #     # In real implementation, this would be actual model training and evaluation
    #     base_score = float(0.7 + (0.2 * np.random.random()))  # Base score between 0.7-0.9
    # 
    #     # Add some algorithmic bias
    #     algorithm_bias = {
    #         'xgboost': 0.05,
    #         'lightgbm': 0.03,
    #         'randomforest': 0.0,
    #         'catboost': 0.04,
    #         'svm': 0.02
    #     }
    #     base_score += algorithm_bias.get(algorithm.lower(), 0)
    # 
    #     # Add iteration-based improvement (diminishing returns)
    #     improvement_factor = min(0.1, 0.05 * (1 / (iteration * 0.5)))
    #     base_score += improvement_factor
    # 
    #     # Add hyperparameter quality effect (ensure params values are converted to float)
    #     if params:
    #         try:
    #             param_values = [float(v) for v in params.values() if isinstance(v, (int, float))]
    #             param_quality = sum(param_values) / len(param_values) if param_values else 1.0
    #             base_score += (param_quality - 1) * 0.02
    #         except (ValueError, TypeError):
    #             param_quality = 1.0
    # 
    #     return float(min(0.99, max(0.5, base_score)))

    # DEPRECATED: _calculate_iteration_metrics - ONLY USED FOR VISUALIZATION IN generate_training_iterations()
    # NOT USED IN REAL TRAINING (train_single_algorithm uses actual calculate_metrics instead)
    # This function generates simulated metrics for demo/UI purposes only
    # 
    # def _calculate_iteration_metrics(self, score: float, algorithm: str, problem_type: str) -> Dict[str, float]:
    #     """Calculate comprehensive metrics for an iteration"""
    #     # Simulate realistic metric relationships
    #     if problem_type == 'classification':
    #         metrics = {
    #             'accuracy': float(score + np.random.normal(0, 0.02)),
    #             'precision': float(score + np.random.normal(0, 0.03)),
    #             'recall': float(score + np.random.normal(0, 0.025)),
    #             'f1': float(score + np.random.normal(0, 0.02)),
    #             'auc': float(score + np.random.normal(0, 0.01)) if score > 0.6 else float(score - 0.1),
    #             'log_loss': float(max(0.1, 1 - score + np.random.normal(0, 0.1)))
    #         }
    #     else:  # regression
    #         metrics = {
    #             'r2': float(score),
    #             'mae': float(max(0.01, (1 - score) * 0.5 + np.random.normal(0, 0.05))),
    #             'mse': float(max(0.001, (1 - score) ** 2 + np.random.normal(0, 0.01))),
    #             'rmse': float(max(0.01, np.sqrt((1 - score) ** 2 + np.random.normal(0, 0.01)))),
    #             'adjusted_r2': float(max(0.1, score - 0.05 + np.random.normal(0, 0.02)))
    #         }
    # 
    #     # Ensure all metrics are JSON serializable
    #     return make_json_serializable(metrics)

    def _find_convergence_iteration(self, iterations: List[Dict[str, Any]]) -> int:
        """Find when the model converged (best score achieved)"""
        if not iterations:
            return 0

        best_score = max(float(iter['score']) for iter in iterations) # finds the best score
        for i, iter in enumerate(iterations):
            if float(iter['score']) == best_score: #based on the best score, find the iteration number
                return int(i + 1)
        return int(len(iterations))

    # DEPRECATED: _track_hyperparameter_evolution - ONLY USED FOR VISUALIZATION IN generate_training_iterations()
    # NOT USED IN REAL TRAINING (train_single_algorithm uses actual model.fit() instead)
    # This function tracks parameter changes for demo/UI purposes only
    # 
    # def _track_hyperparameter_evolution(self, iterations: List[Dict[str, Any]]) -> Dict[str, Any]:
    #     """Track how hyperparameters evolved across iterations"""
    #     if not iterations:
    #         return {}
    # 
    #     evolution = {}
    #     for iter in iterations:
    #         for param, value in iter['hyperparameters'].items():
    #             if param not in evolution:
    #                 evolution[param] = []
    #             evolution[param].append({
    #                 'iteration': int(iter['iteration']),
    #                 'value': make_json_serializable(value),
    #                 'score': float(iter['score'])
    #             })
    # 
    #     return make_json_serializable(evolution)

    def train_models_with_iterations(self, df: pd.DataFrame, target_column: str,
                                   selected_variables: List[str],
                                   algorithm_config: Dict[str, Any],
                                   independent_variables: List[str] = None,
                                   selection_mode: str = "auto",
                                   variable_selection: Dict[str, Any] = None,
                                   vif_correlation_data: Dict[str, Any] = None,
                                   dataset_id: Optional[str] = None,  # NEW: For storing metadata
                                   active_scope: str = 'entire',
                                   weight_variable: Optional[str] = None,
                                   cancel_check: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:  # Weight variable for sample_weight
        """
        Train multiple models with detailed iteration tracking

        Args:
            df: DataFrame containing the data
            target_column: Name of the target column
            selected_variables: List of selected independent variables
            algorithm_config: Configuration for algorithms to train
            independent_variables: List of all independent variables analyzed (optional)
            selection_mode: Variable selection mode (default: "auto")
            variable_selection: Variable selection configuration (optional)
            vif_correlation_data: VIF and correlation analysis data (optional)
            dataset_id: Optional dataset ID to save preprocessed data to state manager
            weight_variable: Optional column name for sample weights (passed to model.fit as sample_weight)

        Returns:
            Dictionary with training results including iterations
        """
        try:
            _cancel_marker = "__AUTO_TRAINING_CANCELLED__"

            def _raise_if_cancelled(where: str) -> None:
                if cancel_check and cancel_check():
                    self.logger.info("Auto training cancellation detected at %s", where)
                    raise RuntimeError(_cancel_marker)

            _raise_if_cancelled("train_models_with_iterations.start")
            # Extract sample weights BEFORE preprocessing (weight column is NOT a feature)
            sample_weights = None
            if weight_variable and weight_variable in df.columns:
                sample_weights = df[weight_variable].values.copy()
                self.logger.info(f"Extracted sample weights from '{weight_variable}' column ({len(sample_weights)} values)")
                # Ensure weight variable is excluded from selected variables
                if weight_variable in selected_variables:
                    selected_variables = [v for v in selected_variables if v != weight_variable]
                    self.logger.info(f"Removed weight variable '{weight_variable}' from selected variables")
            
            # Generate column_stats BEFORE preprocessing (to get original data types)
            column_stats = generate_column_stats(df, selected_variables)
            self.logger.info(f"Generated column_stats for {len(column_stats)} features")
            
            # Preprocess data - use cache when dataset/variables/target haven't changed
            _cache_key = (dataset_id, frozenset(selected_variables), target_column)
            _cached = self._preprocess_cache.get(_cache_key)
            _cache_valid = False
            if _cached is not None and dataset_id:
                try:
                    from app.services.dataframe_state_manager import dataframe_state_manager as _dsm
                    _meta = _dsm.get_dataset_info(dataset_id)
                    if _meta and _meta.get("last_updated") == _cached[3]:
                        X, y = _cached[0], _cached[1]
                        _cache_valid = True
                        self.logger.info(f"Preprocessing cache hit for dataset={dataset_id}")
                except Exception:
                    pass

            if not _cache_valid:
                X, y = self.preprocess_data(df, target_column, selected_variables)
                if dataset_id:
                    try:
                        from app.services.dataframe_state_manager import dataframe_state_manager as _dsm2
                        _meta2 = _dsm2.get_dataset_info(dataset_id)
                        _last_upd = _meta2.get("last_updated") if _meta2 else None
                        self._preprocess_cache[_cache_key] = (X, y, {}, _last_upd)
                    except Exception:
                        pass

            # Save preprocessed data back to state manager if dataset_id is provided
            if dataset_id:
                try:
                    # Build only the new preprocessed columns (avoid copying the full ~1 GB DataFrame).
                    # We assign the new *_le_auto / *_ss_auto columns directly onto df so the
                    # state manager receives the augmented master DataFrame without an extra full copy.
                    encoded_columns = set(self.label_encoders.keys()) if hasattr(self, 'label_encoders') and self.label_encoders else set()
                    preprocessed_column_mapping = {}

                    new_cols: dict = {}
                    for col in X.columns:
                        if col in encoded_columns:
                            new_col_name = f"{col}_le_auto"
                        else:
                            new_col_name = f"{col}_ss_auto"
                        new_cols[new_col_name] = X[col]
                        preprocessed_column_mapping[col] = new_col_name

                    # Assign all new columns at once (single copy, not per-column)
                    preprocessed_df = df.assign(**new_cols)

                    # Store mapping for later use (will be saved in model metadata)
                    self.preprocessed_column_mapping = preprocessed_column_mapping
                    
                    # Save to state manager with force_scope='entire' to ensure it's saved as master dataset
                    from app.services.dataframe_state_manager import dataframe_state_manager
                    dataframe_state_manager.update_dataframe(
                        dataset_id=dataset_id,
                        df=preprocessed_df,
                        force_scope='entire'
                    )
                    
                    # Log summary
                    le_count = sum(1 for col in X.columns if col in encoded_columns)
                    ss_count = len(X.columns) - le_count
                    self.logger.info(f"Saved preprocessed data to state manager for dataset: {dataset_id}, shape: {preprocessed_df.shape}")
                    self.logger.info(f"Created/updated {len(preprocessed_column_mapping)} preprocessed columns (auto training):")
                    self.logger.info(f"  - {le_count} columns with LabelEncoder: {{col}}_le_auto")
                    self.logger.info(f"  - {ss_count} columns with StandardScaler: {{col}}_ss_auto")
                    if preprocessed_column_mapping:
                        example_cols = list(preprocessed_column_mapping.values())[:3]
                        self.logger.info(f"Example columns: {example_cols}...")
                    self.logger.info(f"Original columns preserved. Existing model columns updated if present.")
                except Exception as e:
                    self.logger.warning(f"Failed to save preprocessed data to state manager: {str(e)}")
                    # Continue with training even if save fails
                    self.preprocessed_column_mapping = {}

            # Detect problem type
            problem_type = self.detect_problem_type_from_data(df, target_column)['problem_type']

            # DEBUG: Check class distribution before split
            self.logger.info(f"Target distribution in full dataset: {pd.Series(y).value_counts().to_dict()}")
            
            # Get existing split indices from dataframe_state_manager if dataset_id is provided
            existing_split_indices = None
            if dataset_id:
                try:
                    from app.services.dataframe_state_manager import dataframe_state_manager
                    existing_split_indices = dataframe_state_manager._split_indices.get(dataset_id)
                    if existing_split_indices:
                        self.logger.info(f"Found existing split indices for {dataset_id}: dev={len(existing_split_indices.get('dev', []))} rows, hold={len(existing_split_indices.get('hold', []))} rows")
                except Exception as e:
                    self.logger.warning(f"Failed to get split indices from state manager: {e}")
            
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
                    "[SCOPE_DATA_TRACE][auto] dataset_id=%s active_scope=%s train_source=entire holdout_source=none rows_train=%s",
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
                train_indices = list(X.index)
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
                    "[SCOPE_DATA_TRACE][auto] dataset_id=%s active_scope=%s train_source=%s rows_train=%s",
                    dataset_id,
                    active_scope,
                    active_scope,
                    len(X),
                )
                X_train = X.copy()
                y_train = y.copy()
                w_train = sample_weights  # Use all weights for training (entire train scope)
                w_test = None  # Will be extracted from test data if available
                train_indices = list(X.index)
                
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
                        # Always restore the previous scope after retrieval to avoid global side effects.
                        try:
                            for scope_name in ('test', 'validation', 'train', 'entire'):
                                self.logger.info(
                                    "[SCOPE_DATA_TRACE][auto] dataset_id=%s holdout_probe_scope=%s previous_scope=%s",
                                    dataset_id,
                                    scope_name,
                                    previous_scope,
                                )
                                _dsm.set_scope(dataset_id, scope=scope_name)
                                # MEMORY OPTIMIZATION (#4 - avoid defensive copy during probe):
                                # get_dataframe() returns a full .copy() of the scoped view.
                                # This probe iterates up to 4 scopes purely to find a usable
                                # holdout, and the chosen frame is only ever READ below
                                # (X_test_raw / y_test_raw take their own .copy() of the needed
                                # slices). Using the readonly reference removes up to 4 transient
                                # full-frame copies per training run, trimming the memory spike
                                # at the start of evaluation. Do NOT mutate candidate_df.
                                candidate_df = _dsm.get_dataframe_readonly(dataset_id)
                                candidate_rows = len(candidate_df) if candidate_df is not None else 0
                                if candidate_df is not None and candidate_rows > 0 and target_column in candidate_df.columns:
                                    test_df = candidate_df
                                    holdout_scope_used = scope_name
                                    break
                                self.logger.info(
                                    "[SCOPE_DATA_TRACE][auto] dataset_id=%s holdout_scope=%s rows=%s has_target=%s continuing_fallback",
                                    dataset_id,
                                    scope_name,
                                    candidate_rows,
                                    bool(candidate_df is not None and target_column in candidate_df.columns),
                                )
                        finally:
                            try:
                                _dsm.set_scope(dataset_id, scope=previous_scope)
                                self.logger.info(
                                    "[SCOPE_DATA_TRACE][auto] dataset_id=%s scope_restored=%s",
                                    dataset_id,
                                    previous_scope,
                                )
                            except Exception:
                                self.logger.warning(
                                    f"Could not restore scope '{previous_scope}' for dataset {dataset_id} after holdout retrieval"
                                )
                        
                        if test_df is not None and len(test_df) > 0 and target_column in test_df.columns:
                            test_features = [col for col in selected_variables if col in test_df.columns]
                            if test_features:
                                X_test_raw = test_df[test_features].copy()
                                y_test_raw = test_df[target_column].copy()
                                
                                # CRITICAL: Store original test data BEFORE encoding for X_test_original
                                # This is needed for test granular accuracy with categorical features
                                X_test_original = X_test_raw.copy()
                                
                                sparse_ohe_columns = set(getattr(self, 'sparse_ohe_columns', []))
                                cat_cols = set(getattr(self, 'label_encoders', {}).keys())

                                # --- VECTORIZED missing-value imputation ---
                                # Partition columns by type once; avoid per-row Python calls.
                                ohe_cols_hold = [c for c in X_test_raw.columns if c in sparse_ohe_columns or '_transform_OHE' in c]
                                str_cat_cols_hold = [
                                    c for c in X_test_raw.columns
                                    if c not in ohe_cols_hold and (
                                        c in cat_cols or
                                        X_test_raw[c].dtype in ['object', 'category'] or
                                        pd.api.types.is_string_dtype(X_test_raw[c]) or
                                        str(X_test_raw[c].dtype).startswith('string')
                                    )
                                ]
                                num_cols_hold = [c for c in X_test_raw.columns if c not in ohe_cols_hold and c not in str_cat_cols_hold]

                                # OHE / sparse columns → fill with 0
                                if ohe_cols_hold:
                                    X_test_raw[ohe_cols_hold] = X_test_raw[ohe_cols_hold].fillna(0)

                                # Categorical string columns → fill with mode (per-col, but only a few)
                                for col in str_cat_cols_hold:
                                    mode_val = X_test_raw[col].mode()
                                    X_test_raw[col] = X_test_raw[col].fillna(mode_val.iloc[0] if not mode_val.empty else 'Unknown')

                                # Numeric columns → batch median fill (single vectorized call)
                                if num_cols_hold:
                                    X_test_raw[num_cols_hold] = X_test_raw[num_cols_hold].apply(
                                        pd.to_numeric, errors='coerce'
                                    )
                                    medians_hold = X_test_raw[num_cols_hold].median()
                                    medians_hold = medians_hold.fillna(0)
                                    X_test_raw[num_cols_hold] = X_test_raw[num_cols_hold].fillna(medians_hold)

                                # --- VECTORIZED label encoding (replaces row-by-row .apply) ---
                                # Build a dict-map per encoder and use pandas .map() - O(n) instead of O(n*k).
                                if hasattr(self, 'label_encoders') and self.label_encoders:
                                    for col, le in self.label_encoders.items():
                                        if col in X_test_raw.columns:
                                            le_mapping = {cls: int(idx) for idx, cls in enumerate(le.classes_)}
                                            X_test_raw[col] = (
                                                X_test_raw[col].astype(str)
                                                .map(le_mapping)
                                                .fillna(-1)
                                                .astype(int)
                                            )

                                # Ensure any still-unprocessed columns are numeric (batch coerce).
                                # num_cols_hold (already coerced + median-filled above), ohe_cols_hold
                                # (already 0-filled and numeric), and cat_cols (just label-encoded)
                                # do not need a second pass — see
                                # backend/docs/midas-4m-row-performance-analysis 1.md Fix 5.
                                _already_numeric = set(num_cols_hold) | set(ohe_cols_hold) | set(cat_cols)
                                non_cat_cols = [c for c in X_test_raw.columns if c not in _already_numeric]
                                if non_cat_cols:
                                    X_test_raw[non_cat_cols] = X_test_raw[non_cat_cols].apply(
                                        pd.to_numeric, errors='coerce'
                                    ).fillna(0)

                                # Rebuild hold feature matrix using the exact train-time schema
                                X_test = X_test_raw.copy()
                                scaler_columns = [col for col in getattr(self, 'scaler_columns', []) if col in X_test.columns]
                                if hasattr(self, 'scaler') and self.scaler is not None and scaler_columns:
                                    X_test.loc[:, scaler_columns] = self.scaler.transform(X_test[scaler_columns])

                                model_feature_columns = list(getattr(self, 'model_feature_columns', [])) or list(X_train.columns)
                                X_test = X_test.reindex(columns=model_feature_columns, fill_value=0)

                                # --- VECTORIZED target encoding (replaces row-by-row .apply) ---
                                if hasattr(self, 'target_encoder') and self.target_encoder is not None:
                                    target_mapping = {cls: int(idx) for idx, cls in enumerate(self.target_encoder.classes_)}
                                    y_test = (
                                        y_test_raw.astype(str)
                                        .map(target_mapping)
                                        .fillna(-1)
                                        .astype(int)
                                    )
                                else:
                                    # We don't overwrite X_test here since X_test was just computed correctly above
                                    pass
                                
                                y_test = y_test_raw
                                test_indices = list(test_df.index)
                                # Store X_test_original as instance variable for later extraction
                                self.X_test_original = X_test_original
                                # Extract test weights if weight_variable is available
                                if weight_variable and weight_variable in test_df.columns:
                                    w_test = test_df[weight_variable].values.copy()
                                    self.logger.info(f"✅ Extracted test weights from '{weight_variable}': {len(w_test)} values")
                                self.logger.info(f"✅ Test data for evaluation: X_test={X_test.shape}, y_test={len(y_test)}")
                                self.logger.info(f"✅ Stored X_test_original for test granular accuracy: {X_test_original.shape}")
                                self.logger.info(
                                    "[SCOPE_DATA_TRACE][auto] dataset_id=%s holdout_source=%s rows_test=%s cols_test=%s",
                                    dataset_id,
                                    holdout_scope_used or 'unknown',
                                    len(y_test) if y_test is not None else 0,
                                    X_test.shape[1] if X_test is not None else 0,
                                )
                            else:
                                self.logger.warning(f"⚠️ No matching features in test data")
                        else:
                            self.logger.warning(f"⚠️ No test data available for dataset_id={dataset_id}")
                            self.logger.warning(
                                "[SCOPE_DATA_TRACE][auto] dataset_id=%s holdout_source=%s rows_test=0 reason=no_test_dataframe_or_target_missing",
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
                self.logger.info(f"📊 Train: {len(y_train)} rows | Test: {len(y_test) if y_test is not None else 0} rows")
                self.logger.info(
                    "[SCOPE_DATA_TRACE][auto] dataset_id=%s final_rows train=%s test=%s active_scope=%s",
                    dataset_id,
                    len(y_train) if y_train is not None else 0,
                    len(y_test) if y_test is not None else 0,
                    active_scope,
                )

            results = []
            selected_algorithms = algorithm_config['selected_algorithms']

            # Import models
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
            from sklearn.svm import SVC, SVR

            # Define helper function for parallel training
            def train_single_algorithm(algo_info, X_train=X_train, X_test=X_test):
                """Train a single algorithm - used for parallelization"""
                _raise_if_cancelled("train_single_algorithm.start")
                algorithm_name = algo_info['name']
                
                # --- CatBoost Raw Categorical Branch ---
                cat_features_list = []
                if algorithm_name == 'CatBoost' and hasattr(self, 'X_before_encoding') and self.X_before_encoding is not None:
                    _cand_cols = list(self.X_before_encoding.select_dtypes(include=['object', 'category', 'string']).columns)
                    cat_features_names = [c for c in _cand_cols if c in X_train.columns]
                    cat_features_list = [list(X_train.columns).index(c) for c in cat_features_names]
                    if cat_features_names:
                        try:
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
                    
                    hyperparam_space = self._get_hyperparameter_space(
                        algorithm_name, problem_type, len(df), len(selected_variables)
                    )

                    # Add class imbalance handling to base params
                    base_params = {}
                    if y_train is not None:
                        imbalance_info = self.detect_class_imbalance(y_train)
                        if imbalance_info['is_imbalanced']:
                            if algorithm_name in ['XGBoost'] and len(imbalance_info['class_distribution']) == 2:
                                class_counts = imbalance_info['class_distribution']
                                classes = list(class_counts.keys())
                                base_params['scale_pos_weight'] = float(class_counts[classes[0]] / class_counts[classes[1]])
                            elif algorithm_name in ['LightGBM', 'RandomForest', 'LogisticRegression']:
                                base_params['class_weight'] = 'balanced'

                    if algorithm_name == 'CatBoost' and cat_features_list:
                        base_params['cat_features'] = cat_features_list

                    # Create base model instance
                    import os as _os2
                    _total_cores2 = _os2.cpu_count() or 4
                    _per_model_jobs2 = max(1, min(8, _total_cores2 // 2))

                    model = None
                    if problem_type == 'classification':
                        if algorithm_name == 'XGBoost' and XGBClassifier:
                            model = XGBClassifier(tree_method='hist', n_jobs=_per_model_jobs2, **base_params)
                        elif algorithm_name == 'LightGBM' and LGBMClassifier:
                            model = LGBMClassifier(n_jobs=_per_model_jobs2, verbose=-1, **base_params)
                        elif algorithm_name == 'CatBoost' and CatBoostClassifier:
                            model = CatBoostClassifier(thread_count=_per_model_jobs2, verbose=False, **base_params)
                        elif algorithm_name == 'SVM':
                            model = SVC(**base_params)
                        elif algorithm_name == 'RandomForest':
                            model = RandomForestClassifier(n_jobs=_per_model_jobs2, **base_params)
                        elif algorithm_name == 'LogisticRegression':
                            model = LogisticRegression(n_jobs=_per_model_jobs2, **base_params)
                        elif algorithm_name == 'GradientBoosting':
                            _gb_base = {k: v for k, v in base_params.items() if k not in ('n_jobs',)}
                            model = HistGradientBoostingClassifier(early_stopping=True, n_iter_no_change=10, **_gb_base)
                    else:  # regression
                        if algorithm_name == 'XGBoost' and XGBRegressor:
                            model = XGBRegressor(tree_method='hist', n_jobs=_per_model_jobs2, **base_params)
                        elif algorithm_name == 'LightGBM' and LGBMRegressor:
                            model = LGBMRegressor(n_jobs=_per_model_jobs2, verbose=-1, **base_params)
                        elif algorithm_name == 'CatBoost' and CatBoostRegressor:
                            model = CatBoostRegressor(thread_count=_per_model_jobs2, verbose=False, **base_params)
                        elif algorithm_name == 'SVM':
                            model = SVR(**base_params)
                        elif algorithm_name == 'RandomForest':
                            model = RandomForestRegressor(**base_params)
                        elif algorithm_name == 'LinearRegression':
                            model = LinearRegression(**base_params)
                        elif algorithm_name == 'GradientBoosting':
                            _gb_base = {k: v for k, v in base_params.items() if k not in ('n_jobs',)}
                            model = HistGradientBoostingRegressor(early_stopping=True, n_iter_no_change=10, **_gb_base)

                    if model is None:
                        self.logger.warning(f"Model {algorithm_name} not available, skipping")
                        return {
                            'algorithm': algorithm_name,
                            'error': 'Model not available',
                            'reason': algo_info['reason']
                        }

                    # Bayesian Optimization using Optuna
                    iterations_list = []
                    best_score = 0.0
                    best_params = None
                    best_model = None
                    best_iteration = 0
                    optimization_method = 'default'  # Will be set based on which path is taken
                    
                    # Determine score type for logging
                    score_type = 'AUC' if problem_type == 'classification' else 'R²'

                    # Determine CV folds (event-count-driven for classification, else fallback)
                    if problem_type == 'classification':
                        import pandas as pd
                        min_event_count = int(pd.Series(y_train).value_counts().min())
                        if min_event_count < 200:
                            _cv_folds = 2
                        elif min_event_count <= 500:
                            _cv_folds = 3
                        elif min_event_count <= 2000:
                            _cv_folds = 4
                        else:
                            _cv_folds = 5
                    else:
                        _cv_folds = 2 if len(X_train) > 100_000 else 3

                    if OPTUNA_AVAILABLE and hyperparam_space:
                        try:
                            def objective(trial):
                                nonlocal best_score, best_params, best_model, best_iteration, iterations_list
                                _raise_if_cancelled(f"{algorithm_name}.optuna.objective")
                                
                                iteration_num = trial.number + 1
                                
                                # LOGGER: Start of trial (use dynamic n_trials)
                                self.logger.info(f"{algorithm_name} - Starting Bayesian optimization trial {iteration_num}/{n_trials}")
                                
                                # Suggest hyperparameters from search space
                                suggested_params = {}
                                for param, values in hyperparam_space.items():
                                    if isinstance(values, list) and len(values) > 0:
                                        if all(isinstance(v, int) for v in values):
                                            suggested_params[param] = trial.suggest_int(param, min(values), max(values))
                                        elif all(isinstance(v, float) for v in values):
                                            suggested_params[param] = trial.suggest_float(param, min(values), max(values))
                                        else:
                                            # Categorical or mixed types
                                            suggested_params[param] = trial.suggest_categorical(param, values)
                                    else:
                                        suggested_params[param] = values
                                
                                # LOGGER: Suggested hyperparameters for this trial
                                self.logger.info(f"{algorithm_name} - Trial {iteration_num}: Suggested hyperparameters: {suggested_params}")
                                
                                # Combine with base params
                                iter_params = {**base_params, **suggested_params}
                                
                                # Create model instance
                                iter_model = self._create_model_instance(algorithm_name, problem_type, iter_params)
                                
                                if iter_model is None:
                                    self.logger.warning(f"{algorithm_name} - Trial {iteration_num}: Model creation failed")
                                    return 0.0
                                
                                # Train model - use early stopping for boosting models when a holdout set is available
                                try:
                                    _raise_if_cancelled(f"{algorithm_name}.optuna.before_fit")
                                    self.logger.info(f"{algorithm_name} - Trial {iteration_num}: Training model...")
                                    _es_fit_kwargs: dict = {}
                                    if w_train is not None:
                                        _es_fit_kwargs['sample_weight'] = w_train
                                    if X_test is not None and y_test is not None:
                                        if algorithm_name == 'XGBoost' and XGBClassifier is not None and hasattr(iter_model, 'set_params'):
                                            _es_fit_kwargs.update({
                                                'eval_set': [(X_test, y_test)],
                                                'verbose': False,
                                            })
                                            iter_model.set_params(early_stopping_rounds=20)
                                        elif algorithm_name == 'LightGBM' and LGBMClassifier is not None and hasattr(iter_model, 'set_params'):
                                            _es_fit_kwargs.update({
                                                'eval_set': [(X_test, y_test)],
                                                'callbacks': [],
                                            })
                                            iter_model.set_params(early_stopping_round=20)
                                        elif algorithm_name == 'CatBoost' and CatBoostClassifier is not None:
                                            from catboost import Pool as _CatPool
                                            _es_fit_kwargs.update({
                                                'eval_set': _CatPool(X_test, y_test, cat_features=cat_features_list) if cat_features_list else _CatPool(X_test, y_test),
                                                'early_stopping_rounds': 20,
                                                'verbose': False,
                                            })

                                    from app.services.keith_log_matrics_test import run_with_heartbeat
                                    with run_with_heartbeat(
                                        self.logger,
                                        f"{algorithm_name} - Trial {iteration_num}: still fitting…",
                                    ):
                                        iter_model.fit(X_train, y_train, **_es_fit_kwargs)
                                    self.logger.info(f"{algorithm_name} - Trial {iteration_num}: Model training completed")
                                except Exception as e:
                                    self.logger.warning(f"{algorithm_name} - Trial {iteration_num}: Model training failed: {str(e)}")
                                    return 0.0
                                
                                # Handle case when there's no test set (active_scope == 'entire')
                                if X_test is None or y_test is None:
                                    _raise_if_cancelled(f"{algorithm_name}.optuna.before_cv")
                                    # Use cross-validation on train set for hyperparameter optimization
                                    # _cv_folds = 2 for large datasets (>100K rows), 3 otherwise
                                    self.logger.info(f"{algorithm_name} - Trial {iteration_num}: No test set available, using {_cv_folds}-fold CV on train set")
                                    try:
                                        # NOTE: n_jobs=1 to avoid nested parallelism (outer Parallel handles algorithm-level parallelism)
                                        # Heartbeat during CV (can be silent for many minutes on large data)
                                        from app.services.keith_log_matrics_test import run_with_heartbeat
                                        with run_with_heartbeat(
                                            self.logger,
                                            f"{algorithm_name} - Trial {iteration_num}: cross-validation running…",
                                        ):
                                            if problem_type == 'classification':
                                                if hasattr(iter_model, 'predict_proba'):
                                                    cv_scores = cross_val_score(iter_model, X_train, y_train,
                                                                              cv=_cv_folds, scoring='roc_auc', n_jobs=1)
                                                else:
                                                    cv_scores = cross_val_score(iter_model, X_train, y_train,
                                                                              cv=_cv_folds, scoring='f1_weighted', n_jobs=1)
                                            else:
                                                cv_scores = cross_val_score(iter_model, X_train, y_train,
                                                                          cv=_cv_folds, scoring='r2', n_jobs=1)
                                        current_score = float(np.mean(cv_scores))
                                        self.logger.info(f"{algorithm_name} - Trial {iteration_num}: CV score = {current_score:.4f}")
                                        
                                        # Calculate train predictions for metrics
                                        iter_y_pred_train = iter_model.predict(X_train)
                                        iter_y_pred_proba_train = None
                                        if hasattr(iter_model, 'predict_proba') and problem_type == 'classification':
                                            iter_y_pred_proba_train = iter_model.predict_proba(X_train)
                                        
                                        # Create dummy metrics using train set (for logging purposes)
                                        iter_metrics = self.calculate_metrics(
                                            y_train, iter_y_pred_train, iter_y_pred_proba_train,
                                            y_pred_train=iter_y_pred_train,
                                            y_pred_proba_train=iter_y_pred_proba_train,
                                            y_train=y_train
                                        )
                                    except Exception as cv_e:
                                        self.logger.warning(f"{algorithm_name} - Trial {iteration_num}: Cross-validation failed: {str(cv_e)}")
                                        return 0.0
                                else:
                                    # Normal case: use test set
                                    # Predict on test set
                                    iter_y_pred = iter_model.predict(X_test)
                                    iter_y_pred_proba = None
                                    if hasattr(iter_model, 'predict_proba') and problem_type == 'classification':
                                        iter_y_pred_proba = iter_model.predict_proba(X_test)
                                    
                                    # Calculate train predictions and metrics for iteration
                                    iter_y_pred_train = iter_model.predict(X_train)
                                    iter_y_pred_proba_train = None
                                    if hasattr(iter_model, 'predict_proba') and problem_type == 'classification':
                                        iter_y_pred_proba_train = iter_model.predict_proba(X_train)
                                    
                                    # Calculate metrics for this iteration
                                    iter_metrics = self.calculate_metrics(
                                        y_test, iter_y_pred, iter_y_pred_proba,
                                        y_pred_train=iter_y_pred_train,
                                        y_pred_proba_train=iter_y_pred_proba_train,
                                        y_train=y_train
                                    )
                                    
                                    # Get score (AUC for classification, R2 for regression)
                                    if problem_type == 'classification':
                                        current_score = iter_metrics.get('auc', iter_metrics.get('f1', 0.0))
                                    else:
                                        current_score = iter_metrics.get('r2', 0.0)
                                
                                # Report intermediate score for pruning (enables MedianPruner to cut bad trials early)
                                trial.report(current_score, step=iteration_num)
                                if trial.should_prune():
                                    self.logger.info(f"{algorithm_name} - Trial {iteration_num}: Pruned by MedianPruner (score={current_score:.4f})")
                                    raise optuna.TrialPruned()

                                # Calculate improvement
                                improvement = current_score - best_score if iteration_num > 1 else 0.0
                                
                                # LOGGER: Trial results
                                self.logger.info(f"{algorithm_name} - Trial {iteration_num}: {score_type} = {current_score:.4f}, Improvement = {improvement:+.4f}")
                                
                                # Update best if better - MUST happen BEFORE pruning check
                                if current_score > best_score:
                                    old_best_score = best_score
                                    best_score = current_score
                                    best_params = suggested_params.copy()
                                    best_model = iter_model
                                    best_iteration = iteration_num
                                    
                                    # LOGGER: New best score found
                                    if iteration_num > 1:
                                        self.logger.info(f"{algorithm_name} - Trial {iteration_num}: 🎯 NEW BEST SCORE! {score_type}: {old_best_score:.4f} → {best_score:.4f} (improvement: {improvement:+.4f})")
                                    else:
                                        self.logger.info(f"{algorithm_name} - Trial {iteration_num}: 🎯 Initial best score: {score_type} = {best_score:.4f}")
                                
                                feature_importance_count = nonzero_feature_slot_count(iter_model)
                                
                                # Add to iterations list with full metrics
                                iterations_list.append({
                                    'iteration': iteration_num,
                                    'score': current_score,
                                    'improvement': improvement,
                                    'hyperparameters': suggested_params.copy(),
                                    'status': 'Best Score' if iteration_num == best_iteration else 'Completed',
                                    'metrics': make_json_serializable(iter_metrics),
                                    'feature_importance_count': feature_importance_count
                                })
                                
                                return current_score  # Optuna maximizes this
                            
                            # Create Optuna study with Bayesian optimization
                            # OPTIMIZED: Dynamic trial count based on feature count
                            # More features = fewer trials to keep training time reasonable
                            n_features = len(selected_variables)
                            if n_features > 500:
                                n_trials = 5  # Minimum trials for very large feature sets
                                n_startup = 1
                            elif n_features > 200:
                                n_trials = 7
                                n_startup = 2
                            elif n_features > 100:
                                n_trials = 8
                                n_startup = 2
                            else:
                                n_trials = 10  # Full trials for smaller feature sets
                                n_startup = 2
                            
                            self.logger.info(f"{algorithm_name} - Starting Bayesian optimization with Optuna ({n_trials} trials: {n_startup} random + {n_trials - n_startup} learned) [Features: {n_features}]")
                            
                            from optuna.pruners import MedianPruner
                            study = optuna.create_study(
                                direction="maximize",
                                sampler=TPESampler(seed=42, n_startup_trials=n_startup),
                                pruner=MedianPruner(n_startup_trials=n_startup, n_warmup_steps=1),
                            )
                            
                            # Run optimization
                            self.logger.info(f"{algorithm_name} - Running Optuna optimization...")
                            study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
                            
                            # LOGGER: Optimization completed
                            self.logger.info(f"{algorithm_name} - ✅ Optuna optimization completed. Best trial: {study.best_trial.number + 1}, Best {score_type}: {best_score:.4f}")
                            
                            # Mark that Bayesian optimization was used
                            optimization_method = 'bayesian_optimization'
                            
                            # Use best model (already stored in best_model)
                            model = best_model
                            params = best_params
                            
                        except Exception as e:
                            self.logger.error(f"Optuna optimization failed for {algorithm_name}: {str(e)}. Falling back to random search.")
                            import traceback
                            self.logger.error(traceback.format_exc())
                            
                            # Fallback to random search if Optuna fails
                            iterations_list = []
                            best_score = 0.0
                            best_params = None
                            best_model = None
                            best_iteration = 0
                            optimization_method = 'random_search'  # Mark that random search was used (fallback)
                            
                            # OPTIMIZED: Use same dynamic trial count for random search fallback
                            n_random_trials = n_trials if 'n_trials' in dir() else 10
                            for iteration in range(1, n_random_trials + 1):
                                _raise_if_cancelled(f"{algorithm_name}.random_search.iteration_{iteration}")
                                if hyperparam_space:
                                    sampled_params = self._sample_hyperparameters(hyperparam_space)
                                else:
                                    sampled_params = {}
                                
                                iter_params = {**base_params, **sampled_params}
                                iter_model = self._create_model_instance(algorithm_name, problem_type, iter_params)
                                
                                if iter_model is None:
                                    continue
                                
                                # Pass sample weights if available
                                if w_train is not None:
                                    iter_model.fit(X_train, y_train, sample_weight=w_train)
                                else:
                                    iter_model.fit(X_train, y_train)
                                
                                # Handle case when there's no test set (active_scope == 'entire')
                                if X_test is None or y_test is None:
                                    # _cv_folds = 2 for large datasets (>100K rows), 3 otherwise
                                    self.logger.info(f"{algorithm_name} - Iteration {iteration}: No test set available, using {_cv_folds}-fold CV on train set")
                                    try:
                                        # NOTE: n_jobs=1 to avoid nested parallelism (outer Parallel handles algorithm-level parallelism)
                                        if problem_type == 'classification':
                                            if hasattr(iter_model, 'predict_proba'):
                                                cv_scores = cross_val_score(iter_model, X_train, y_train,
                                                                          cv=_cv_folds, scoring='roc_auc', n_jobs=1)
                                            else:
                                                cv_scores = cross_val_score(iter_model, X_train, y_train,
                                                                          cv=_cv_folds, scoring='f1_weighted', n_jobs=1)
                                        else:
                                            cv_scores = cross_val_score(iter_model, X_train, y_train,
                                                                      cv=_cv_folds, scoring='r2', n_jobs=1)
                                        current_score = float(np.mean(cv_scores))
                                        
                                        # Calculate train predictions for metrics
                                        iter_y_pred_train = iter_model.predict(X_train)
                                        iter_y_pred_proba_train = None
                                        if hasattr(iter_model, 'predict_proba') and problem_type == 'classification':
                                            iter_y_pred_proba_train = iter_model.predict_proba(X_train)
                                        
                                        # Create dummy metrics using train set (for logging purposes)
                                        iter_metrics = self.calculate_metrics(
                                            y_train, iter_y_pred_train, iter_y_pred_proba_train,
                                            y_pred_train=iter_y_pred_train,
                                            y_pred_proba_train=iter_y_pred_proba_train,
                                            y_train=y_train
                                        )
                                    except Exception as cv_e:
                                        self.logger.warning(f"{algorithm_name} - Iteration {iteration}: Cross-validation failed: {str(cv_e)}")
                                        continue
                                else:
                                    # Normal case: use test set
                                    iter_y_pred = iter_model.predict(X_test)
                                    iter_y_pred_proba = None
                                    if hasattr(iter_model, 'predict_proba') and problem_type == 'classification':
                                        iter_y_pred_proba = iter_model.predict_proba(X_test)
                                    
                                    iter_y_pred_train = iter_model.predict(X_train)
                                    iter_y_pred_proba_train = None
                                    if hasattr(iter_model, 'predict_proba') and problem_type == 'classification':
                                        iter_y_pred_proba_train = iter_model.predict_proba(X_train)
                                    
                                    iter_metrics = self.calculate_metrics(
                                        y_test, iter_y_pred, iter_y_pred_proba,
                                        y_pred_train=iter_y_pred_train,
                                        y_pred_proba_train=iter_y_pred_proba_train,
                                        y_train=y_train
                                    )
                                    
                                    if problem_type == 'classification':
                                        current_score = iter_metrics.get('auc', iter_metrics.get('f1', 0.0))
                                    else:
                                        current_score = iter_metrics.get('r2', 0.0)
                                
                                improvement = current_score - best_score if iteration > 1 else 0.0
                                
                                if current_score > best_score:
                                    best_score = current_score
                                    best_params = sampled_params
                                    best_model = iter_model
                                    best_iteration = iteration
                                
                                feature_importance_count = nonzero_feature_slot_count(iter_model)
                                
                                iterations_list.append({
                                    'iteration': iteration,
                                    'score': current_score,
                                    'improvement': improvement,
                                    'hyperparameters': sampled_params,
                                    'status': 'Best Score' if iteration == best_iteration else 'Completed',
                                    'metrics': make_json_serializable(iter_metrics),
                                    'feature_importance_count': feature_importance_count
                                })
                            
                            model = best_model
                            params = best_params
                    else:
                        # No hyperparameter space or Optuna not available - use default model
                        self.logger.info(f"{algorithm_name} - No hyperparameter space or Optuna not available. Using default model.")
                        optimization_method = 'default'
                        iterations_list = []
                        model = self._create_model_instance(algorithm_name, problem_type, base_params)
                        if model:
                            _raise_if_cancelled(f"{algorithm_name}.default_model.before_fit")
                            # Pass sample weights if available
                            if w_train is not None:
                                model.fit(X_train, y_train, sample_weight=w_train)
                            else:
                                model.fit(X_train, y_train)
                            params = {}
                            # Create single iteration entry
                            # Handle case when there's no test set (active_scope == 'entire')
                            if X_test is None or y_test is None:
                                # Use cross-validation on train set
                                # OPTIMIZED: Use cv=3 instead of cv=5 for faster default model evaluation
                                # NOTE: n_jobs=1 to avoid nested parallelism (outer Parallel handles algorithm-level parallelism)
                                self.logger.info(f"{algorithm_name} - No test set available, using {_cv_folds}-fold CV on train set")
                                try:
                                    if problem_type == 'classification':
                                        if hasattr(model, 'predict_proba'):
                                            cv_scores = cross_val_score(model, X_train, y_train,
                                                                      cv=_cv_folds, scoring='roc_auc', n_jobs=1)
                                        else:
                                            cv_scores = cross_val_score(model, X_train, y_train,
                                                                      cv=_cv_folds, scoring='f1_weighted', n_jobs=1)
                                    else:
                                        cv_scores = cross_val_score(model, X_train, y_train,
                                                                  cv=_cv_folds, scoring='r2', n_jobs=1)
                                    best_score = float(np.mean(cv_scores))
                                    
                                    iter_y_pred_train = model.predict(X_train)
                                    iter_y_pred_proba_train = None
                                    if hasattr(model, 'predict_proba') and problem_type == 'classification':
                                        iter_y_pred_proba_train = model.predict_proba(X_train)
                                    
                                    iter_metrics = self.calculate_metrics(
                                        y_train, iter_y_pred_train, iter_y_pred_proba_train,
                                        y_pred_train=iter_y_pred_train,
                                        y_pred_proba_train=iter_y_pred_proba_train,
                                        y_train=y_train
                                    )
                                except Exception as cv_e:
                                    self.logger.warning(f"{algorithm_name} - Cross-validation failed: {str(cv_e)}")
                                    best_score = 0.0
                                    iter_metrics = {}
                            else:
                                iter_y_pred = model.predict(X_test)
                                iter_y_pred_proba = None
                                if hasattr(model, 'predict_proba') and problem_type == 'classification':
                                    iter_y_pred_proba = model.predict_proba(X_test)
                                
                                iter_y_pred_train = model.predict(X_train)
                                iter_y_pred_proba_train = None
                                if hasattr(model, 'predict_proba') and problem_type == 'classification':
                                    iter_y_pred_proba_train = model.predict_proba(X_train)
                                
                                iter_metrics = self.calculate_metrics(
                                    y_test, iter_y_pred, iter_y_pred_proba,
                                    y_pred_train=iter_y_pred_train,
                                    y_pred_proba_train=iter_y_pred_proba_train,
                                    y_train=y_train
                                )
                                
                                if problem_type == 'classification':
                                    best_score = iter_metrics.get('auc', iter_metrics.get('f1', 0.0))
                                else:
                                    best_score = iter_metrics.get('r2', 0.0)
                            
                            iterations_list.append({
                                'iteration': 1,
                                'score': best_score,
                                'improvement': 0.0,
                                'hyperparameters': {},
                                'status': 'Completed',
                                'metrics': make_json_serializable(iter_metrics),
                                'feature_importance_count': 0
                            })
                            best_iteration = 1
                        else:
                            return {'algorithm': algorithm_name, 'error': 'Model creation failed'}
                    
                    # Use best model - validate it's not None
                    model = best_model
                    params = best_params
                    
                    # CRITICAL: Check if we have a valid model before proceeding
                    if model is None:
                        self.logger.error(f"{algorithm_name} - No valid model was trained. All trials may have failed.")
                        return {
                            'algorithm': algorithm_name,
                            'error': 'Training failed: No valid model was produced. All training trials may have failed.',
                            'reason': algo_info.get('reason', 'Unknown')
                        }
                    
                    # Find convergence iteration
                    convergence_iteration = self._find_convergence_iteration(iterations_list)
                    
                    # Use dynamic trial count if defined, otherwise default to length of iterations_list
                    actual_total_iterations = n_trials if 'n_trials' in dir() else len(iterations_list) if iterations_list else 10
                    iterations_data = {
                        'iterations': iterations_list,
                        'best_score': best_score,
                        'best_hyperparameters': params,
                        'total_iterations': actual_total_iterations,
                        'convergence_iteration': convergence_iteration
                    }
                    
                    # Make predictions with best model (for consistency and logging)
                    # Handle case when there's no test set (active_scope == 'entire')
                    if X_test is None or y_test is None:
                        self.logger.info(f"{algorithm_name} - No test set available (active_scope='entire'), skipping test predictions")
                        y_pred = None
                        y_pred_proba = None
                    else:
                        y_pred = model.predict(X_test)
                        y_pred_proba = None
                        if hasattr(model, 'predict_proba') and problem_type == 'classification':
                            y_pred_proba = model.predict_proba(X_test)

                        # DEBUG: Log predictions and class distribution
                        self.logger.info(f"{algorithm_name} - Unique class predictions: {np.unique(y_pred, return_counts=True)}")
                        self.logger.info(f"{algorithm_name} - Prediction distribution: {pd.Series(y_pred).value_counts().to_dict()}")
                        self.logger.info(f"{algorithm_name} - Actual y_test distribution: {pd.Series(y_test).value_counts().to_dict()}")

                        # Get prediction probabilities for classification
                        if y_pred_proba is not None:
                            self.logger.info(f"{algorithm_name} - Probability shape: {y_pred_proba.shape}")
                            if y_pred_proba.shape[1] == 2:
                                self.logger.info(f"{algorithm_name} - Probability range for class 1: [{y_pred_proba[:, 1].min():.4f}, {y_pred_proba[:, 1].max():.4f}]")

                    # Calculate train predictions and metrics for comparison
                    y_pred_train = model.predict(X_train)
                    y_pred_proba_train = None
                    if hasattr(model, 'predict_proba') and problem_type == 'classification':
                        y_pred_proba_train = model.predict_proba(X_train)

                    # Calculate metrics with both train and test for complete analysis
                    # Handle case when there's no test set (active_scope == 'entire')
                    if X_test is None or y_test is None:
                        # Use train set for metrics when no test set available
                        metrics = self.calculate_metrics(
                            y_train, y_pred_train, y_pred_proba_train,
                            y_pred_train=y_pred_train,
                            y_pred_proba_train=y_pred_proba_train,
                            y_train=y_train
                        )
                    else:
                        metrics = self.calculate_metrics(
                            y_test, y_pred, y_pred_proba,
                            y_pred_train=y_pred_train,
                            y_pred_proba_train=y_pred_proba_train,
                            y_train=y_train
                        )

                    metrics['feature_importance_count'] = nonzero_feature_slot_count(model)
                    try:
                        metrics['feature_count'] = int(getattr(X_train, "shape", (0,))[1] or 0)
                    except Exception:
                        pass

                    # Cross-validation scores (Optimized: Reduced cv from 5 to 3 for faster training)
                    cv_metric = 'accuracy' if problem_type == 'classification' else 'r2'
                    # Reset early stopping params before CV - cross_val_score does not pass eval_set,
                    # so XGBoost/LightGBM would raise "Must have at least 1 validation dataset".
                    _cv_model = model
                    if algorithm_name == 'XGBoost' and hasattr(model, 'set_params'):
                        try:
                            _cv_model = model.set_params(early_stopping_rounds=None)
                        except Exception:
                            pass
                    elif algorithm_name == 'LightGBM' and hasattr(model, 'set_params'):
                        try:
                            _cv_model = model.set_params(early_stopping_round=None)
                        except Exception:
                            pass
                    # Determine CV folds (event-count-driven for classification, else fallback)
                    if problem_type == 'classification':
                        import pandas as pd
                        min_event_count = int(pd.Series(y_train).value_counts().min())
                        if min_event_count < 200:
                            _cv_folds_final = 2
                        elif min_event_count <= 500:
                            _cv_folds_final = 3
                        elif min_event_count <= 2000:
                            _cv_folds_final = 4
                        else:
                            _cv_folds_final = 5
                    else:
                        _cv_folds_final = 2 if len(X_train) > 100_000 else 3
                    cv_scores = cross_val_score(_cv_model, X_train, y_train, cv=_cv_folds_final, scoring=cv_metric)

                    # Generate model ID and save
                    model_id = f"MDL_AUTO_{uuid.uuid4().hex[:8].upper()}"
                    artifact_path = os.path.join(self.model_storage_path, f"{model_id}.pkl")
                    joblib.dump(model, artifact_path)

                    # Comprehensive model evaluation (MEEA integration)
                    # Deferred to background task - store args and return immediately so training
                    # results reach the UI without waiting for the expensive MEEA computation.
                    _meea_args = None  # default; set inside try block below
                    try:
                        # Get preprocessed column mapping if available
                        preprocessed_columns = getattr(self, 'preprocessed_column_mapping', {})
                        
                        # Extract category mappings from label encoders for reverse-encoding
                        category_mappings = {}
                        if hasattr(self, 'label_encoders') and self.label_encoders:
                            for feature_name, label_encoder in self.label_encoders.items():
                                if hasattr(label_encoder, 'classes_'):
                                    category_mappings[feature_name] = {
                                        i: str(class_name) for i, class_name in enumerate(label_encoder.classes_)
                                    }
                        else:
                            self.logger.warning("No label_encoders found - category mappings will be empty")
                        
                        # Extract original (pre-encoding) test/train data for MEEA
                        X_test_original = None
                        
                        # For train scope: use X_test_original (stored during test data preprocessing)
                        if hasattr(self, 'X_test_original') and self.X_test_original is not None:
                            X_test_original = self.X_test_original.copy()
                            self.logger.info(f"✅ Using X_test_original for test granular accuracy: {X_test_original.shape}")
                            self.logger.info(f"   Columns: {list(X_test_original.columns)[:10]}")
                        # For entire scope or fallback: extract from X_before_encoding
                        elif hasattr(self, 'X_before_encoding') and self.X_before_encoding is not None:
                            if test_indices is not None and len(test_indices) > 0:
                                try:
                                    X_test_original = self.X_before_encoding.loc[test_indices].copy()
                                except Exception:
                                    try:
                                        idx_positions = [self.X_before_encoding.index.get_loc(idx) for idx in test_indices]
                                        X_test_original = self.X_before_encoding.iloc[idx_positions].copy()
                                    except Exception:
                                        pass
                        if X_test_original is None and hasattr(self, 'X_before_scaling') and self.X_before_scaling is not None:
                            if test_indices is not None and len(test_indices) > 0:
                                try:
                                    X_test_original = self.X_before_scaling.loc[test_indices].copy()
                                except Exception:
                                    pass

                        X_train_original = None
                        if hasattr(self, 'X_before_encoding') and self.X_before_encoding is not None:
                            if train_indices is not None:
                                try:
                                    X_train_original = self.X_before_encoding.loc[train_indices].copy()
                                except Exception:
                                    try:
                                        idx_positions = [self.X_before_encoding.index.get_loc(idx) for idx in train_indices]
                                        X_train_original = self.X_before_encoding.iloc[idx_positions].copy()
                                    except Exception:
                                        pass
                        if X_train_original is None and hasattr(self, 'X_before_scaling') and self.X_before_scaling is not None:
                            if train_indices is not None:
                                try:
                                    X_train_original = self.X_before_scaling.loc[train_indices].copy()
                                except Exception:
                                    pass

                        # Store MEEA args as part of the result dict so they survive the loky
                        # subprocess boundary.  The parent process will extract these after
                        # Parallel() returns and register them in _pending_meea_jobs there.
                        _meea_args = {
                            'model': model,
                            'model_id': model_id,
                            'algorithm_name': algorithm_name,
                            'X_train': X_train,
                            'X_test': X_test,
                            'y_train': y_train,
                            'y_test': y_test,
                            'problem_type': problem_type,
                            'feature_names': list(X.columns),
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
                            'scaler': getattr(self, 'scaler', None),
                            'column_stats': column_stats,
                        }
                        self.logger.info(f"Prepared MEEA args for {algorithm_name} ({model_id}) - will register in parent process")
                    except Exception as eval_error:
                        self.logger.warning(f"Failed to queue MEEA job for {algorithm_name}: {str(eval_error)}")
                        import traceback
                        self.logger.warning(traceback.format_exc())

                    # Ensure all data is JSON serializable
                    serializable_metrics = make_json_serializable(metrics)
                    serializable_cv_scores = make_json_serializable(cv_scores.tolist())
                    serializable_params = make_json_serializable(params)
                    serializable_iterations = make_json_serializable(iterations_data['iterations'])
                    serializable_best_score = make_json_serializable(iterations_data['best_score'])
                    serializable_convergence = make_json_serializable(iterations_data['convergence_iteration'])

                    # Extract category mappings from label encoders for saving
                    # IMPORTANT: Use ORIGINAL feature names (before preprocessing), not preprocessed names
                    category_mappings_to_save = {}
                    if hasattr(self, 'label_encoders') and self.label_encoders:
                        # Get preprocessed column mapping to find original names
                        preprocessed_column_mapping = getattr(self, 'preprocessed_column_mapping', {})
                        # Reverse mapping: {preprocessed_name: original_name}
                        reverse_mapping = {v: k for k, v in preprocessed_column_mapping.items()}
                        
                        for feature_name, label_encoder in self.label_encoders.items():
                            if hasattr(label_encoder, 'classes_'):
                                # Find original feature name (before preprocessing)
                                original_feature_name = reverse_mapping.get(feature_name, feature_name)
                                
                                # Create mapping: {encoded_value: original_category_name}
                                category_mappings_to_save[original_feature_name] = {
                                    int(i): str(class_name) for i, class_name in enumerate(label_encoder.classes_)
                                }
                                self.logger.debug(f"  Created mapping for '{original_feature_name}' (preprocessed: '{feature_name}'): {len(category_mappings_to_save[original_feature_name])} categories")
                        
                        if category_mappings_to_save:
                            self.logger.info(f"💾 Saving category_mappings for {len(category_mappings_to_save)} features to training_results.json")
                            self.logger.info(f"   Features: {list(category_mappings_to_save.keys())}")
                        else:
                            self.logger.warning(f"⚠️ No category_mappings to save - label_encoders may be empty or invalid")
                    
                    # NEW: Create reverse mapping JSON file (original_value -> encoded_value)
                    # This is useful for mapping original values back to encoded values
                    original_to_encoded_mapping = {}
                    for feature_name, encoded_to_original in category_mappings_to_save.items():
                        # Reverse the mapping: {original_value: encoded_value}
                        original_to_encoded_mapping[feature_name] = {
                            str(original_val): int(encoded_val) 
                            for encoded_val, original_val in encoded_to_original.items()
                        }
                        # Special handling for home_ownership: also check if original values are numeric
                        if feature_name == 'home_ownership':
                            self.logger.info(f"🔍 home_ownership mapping analysis:")
                            self.logger.info(f"   Encoded->Original: {encoded_to_original}")
                            self.logger.info(f"   Original->Encoded: {original_to_encoded_mapping[feature_name]}")
                            # Check if original values are numeric
                            original_values = list(encoded_to_original.values())
                            numeric_count = sum(1 for v in original_values if str(v).replace('.', '').replace('-', '').isdigit())
                            if numeric_count > 0:
                                self.logger.warning(f"   ⚠️ home_ownership has {numeric_count} numeric original values (out of {len(original_values)} total)")
                                self.logger.warning(f"   This is a categorical feature with numeric labels - will handle in segmentation")
                    
                    # Save original_to_encoded mapping to separate JSON file
                    if original_to_encoded_mapping:
                        try:
                            mapping_json_path = os.path.join(self.model_storage_path, f"{model_id}_original_to_encoded_mapping.json")
                            with open(mapping_json_path, 'w') as f:
                                json.dump(original_to_encoded_mapping, f, indent=2, default=str)
                            self.logger.info(f"💾 Saved original_to_encoded mapping to: {mapping_json_path}")
                            if 'home_ownership' in original_to_encoded_mapping:
                                self.logger.info(f"   ✅ home_ownership mapping saved: {len(original_to_encoded_mapping['home_ownership'])} entries")
                        except Exception as e:
                            self.logger.warning(f"⚠️ Failed to save original_to_encoded mapping: {str(e)}")
                    
                    # Save training results as JSON
                    training_results = {
                        'model_id': model_id,
                        'algorithm': algorithm_name,
                        'problem_type': problem_type,
                        'metrics': serializable_metrics,
                        'cv_scores': serializable_cv_scores,
                        'artifact_path': artifact_path,
                        'hyperparameters': serializable_params,
                        'training_time_seconds': 0,
                        'used_features': selected_variables,
                        'iteration_history': serializable_iterations,
                        'column_stats': column_stats,  # Save column_stats with variable types
                        'category_mappings': category_mappings_to_save  # Save category mappings for granular accuracy
                    }

                    results_json_path = os.path.join(self.model_storage_path, f"{model_id}_training_results.json")
                    with open(results_json_path, 'w') as f:
                        json.dump(training_results, f, indent=2, default=str)

                    # Convert hyperparameter search space to frontend-friendly format used for Documentation Agent
                    hyperparameter_search_space = []
                    if hyperparam_space:
                        for param_name, param_values in hyperparam_space.items():
                            if isinstance(param_values, list):
                                min_val = min(param_values) if param_values and isinstance(param_values[0], (int, float)) else param_values[0]
                                max_val = max(param_values) if param_values and isinstance(param_values[0], (int, float)) else param_values[-1]
                                if isinstance(min_val, (int, float)) and isinstance(max_val, (int, float)):
                                    hyperparameter_search_space.append({
                                        'name': param_name.replace('_', ' ').title(),
                                        'range': f'{min_val} - {max_val}'
                                    })
                                else:
                                    # For non-numeric params, show all values
                                    hyperparameter_search_space.append({
                                        'name': param_name.replace('_', ' ').title(),
                                        'range': ', '.join(str(v) for v in param_values[:5])  # Show first 5
                                    })
                    
                    result = {
                        'model_id': model_id,
                        'algorithm': algorithm_name,
                        'metrics': serializable_metrics,
                        'cv_scores': serializable_cv_scores,
                        'artifact_path': artifact_path,
                        'hyperparameters': serializable_params,
                        'hyperparameter_search_space': hyperparameter_search_space,
                        'iteration_history': serializable_iterations,
                        'best_score': serializable_best_score,
                        'convergence_iteration': serializable_convergence,
                        'optimization_method': optimization_method,
                        'reason': algo_info['reason'],
                        # Carry MEEA args back to the parent process (loky spawns child
                        # processes whose writes to class-level dicts are invisible to the
                        # parent).  The parent extracts this key after Parallel() returns.
                        '_meea_args': _meea_args,
                    }

                    self.logger.info(f"Successfully trained {algorithm_name} model: {model_id}")
                    return result

                except Exception as e:
                    if str(e) == _cancel_marker:
                        raise
                    self.logger.error(f"Error training {algorithm_name}: {str(e)}")
                    import traceback
                    self.logger.error(f"Traceback for {algorithm_name}: {traceback.format_exc()}")
                    return {
                        'algorithm': algorithm_name,
                        'error': str(e),
                        'reason': algo_info['reason'],
                        '_meea_args': None,
                    }

           
            self.logger.info(f"Training {len(selected_algorithms)} algorithms in parallel...")
            _raise_if_cancelled("parallel.dispatch")
            results_list = Parallel(n_jobs=-1, backend='loky', verbose=1, batch_size='auto', pre_dispatch='2*n_jobs', max_nbytes='100M')(
                delayed(train_single_algorithm)(algo_info) for algo_info in selected_algorithms
            )
            _raise_if_cancelled("parallel.completed")
            
            # Extract MEEA args from child-process results and register them in the
            # parent process _pending_meea_jobs dict (fixes the loky IPC issue where
            # child-process writes to class-level dicts are invisible to the parent).
            #
            # MEMORY OPTIMIZATION (#1 - deduplicate identical *_original frames):
            # Every model independently '.copy()'-ed X_train_original and
            # X_test_original from the SAME source (self.X_before_encoding sliced by
            # the SAME train_indices/test_indices). After the loky round-trip the
            # parent therefore ends up holding N distinct-but-identical copies of
            # each (e.g. 5 models -> 10 redundant full-size frames). These frames are
            # read-only inside MEEA Phase 1, so we collapse them to a single shared
            # reference: the first job's frame becomes canonical and all subsequent
            # jobs point at it, letting the duplicates be garbage-collected.
            # Impact: drops peak DataFrame count from ~5x2 to ~2 for the originals,
            # which is the single largest contributor to the 21-frame peak.
            # NOTE: X_train/X_test are intentionally NOT shared here because the
            # CatBoost branch injects raw categoricals into them, so they can differ
            # per algorithm.
            _shared_x_train_original = None
            _shared_x_test_original = None
            for r in results_list:
                if r is not None and r.get('_meea_args'):
                    meea_args = r.pop('_meea_args')
                    mid = meea_args.get('model_id')
                    if mid:
                        if meea_args.get('X_train_original') is not None:
                            if _shared_x_train_original is None:
                                _shared_x_train_original = meea_args['X_train_original']
                            else:
                                meea_args['X_train_original'] = _shared_x_train_original
                        if meea_args.get('X_test_original') is not None:
                            if _shared_x_test_original is None:
                                _shared_x_test_original = meea_args['X_test_original']
                            else:
                                meea_args['X_test_original'] = _shared_x_test_original
                        ModelTrainingAutoTrainingService._pending_meea_jobs[mid] = meea_args
                        self.logger.info(f"Registered MEEA background job for {meea_args.get('algorithm_name')} ({mid}) in parent process")
                elif r is not None:
                    r.pop('_meea_args', None)  # clean up None entries

            # MEMORY OPTIMIZATION (#3 - release full-size preprocessing frames):
            # self.X_before_encoding / self.X_before_scaling are full-dataset copies
            # kept only as the source for the *_original slices built above, and
            # self.X_test_original is the per-run holdout snapshot. None of them are
            # read again after this point (MEEA receives explicit args and runs in a
            # separate service), yet they previously lived on the singleton for the
            # whole process lifetime and were overwritten - not freed - on the next
            # training run. Dropping the references now frees 2-3 full-size frames
            # immediately instead of leaking them across runs. (The collect is
            # deferred to after results_list is dropped below so a single pass
            # reclaims everything.)
            self.X_before_encoding = None
            self.X_before_scaling = None
            self.X_test_original = None

            # Filter out None results and flatten
            results = [r for r in results_list if r is not None]

            # MEMORY OPTIMIZATION (#5 - cut the train->MEEA handoff transient):
            # results_list is the container loky/joblib returns from Parallel(),
            # holding the unpickled per-model result dicts (and transitively any
            # frames joblib still references). Logs showed a ~28 DataFrame spike at
            # exactly this handoff that fell back to ~16 a few seconds later once
            # GC ran - i.e. these were collectable leftovers, not steady state.
            # `results` already holds everything callers need (the heavy frames
            # live only in _pending_meea_jobs now), so we drop results_list and
            # force one collect here to flatten that transient peak deterministically
            # rather than waiting for the next generational GC.
            del results_list
            gc.collect()

            return {
                'problem_type': problem_type,
                'results': results,
                'used_features': selected_variables,
                'auto_selection_summary': {
                    'total_variables_analyzed': len(independent_variables),
                    'variables_selected': len(selected_variables),
                    'algorithms_selected': len(algorithm_config['selected_algorithms']),
                    'num_models_trained': len([r for r in results if 'model_id' in r]),
                    'training_method': 'fully_automatic',
                    'variable_selection_mode': selection_mode
                },
                'algorithm_selection': algorithm_config,
                'variable_selection': variable_selection or {},
                'variable_analysis': vif_correlation_data or {},
                'preprocessing_summary': getattr(self, 'preprocessing_summary', {
                    'is_already_preprocessed': False,
                    'variables': [],
                    'dropped_variables': [],
                    'total_processed': 0,
                    'total_dropped': 0
                })
            }

        except Exception as e:
            if str(e) == "__AUTO_TRAINING_CANCELLED__":
                raise RuntimeError("Auto training cancelled by user")
            self.logger.error(f"Error in auto training with iterations: {str(e)}")
            raise

    def detect_class_imbalance(self, y: pd.Series) -> Dict[str, Any]:
        """Detect if dataset is imbalanced"""
        value_counts = y.value_counts()
        total = len(y)
        majority_class_ratio = value_counts.iloc[0] / total
        
        is_imbalanced = majority_class_ratio > 0.7  # More than 70% in one class (consistent with manual training)
        
        return {
            'is_imbalanced': is_imbalanced,
            'majority_class_ratio': float(majority_class_ratio),
            'class_distribution': {str(k): int(v) for k, v in value_counts.to_dict().items()},
            'imbalance_ratio': float(value_counts.iloc[0] / value_counts.iloc[-1]) if len(value_counts) > 1 else 1.0
        }

    def calculate_metrics(self, y_true: pd.Series, y_pred: np.ndarray,
                         y_pred_proba: Optional[np.ndarray] = None,
                         y_pred_train: Optional[np.ndarray] = None,
                         y_pred_proba_train: Optional[np.ndarray] = None,
                         y_train: Optional[pd.Series] = None) -> Dict[str, float]:
        """Calculate comprehensive metrics including KS statistic and train-test difference %"""
        metrics = {}

        try:
            # Classification metrics (TEST SET)
            if len(y_true.unique()) <= 10:  # Classification
                metrics['test_accuracy'] = float(accuracy_score(y_true, y_pred))
                metrics['test_precision'] = float(precision_score(y_true, y_pred, average='weighted', zero_division=0))
                metrics['test_recall'] = float(recall_score(y_true, y_pred, average='weighted', zero_division=0))
                metrics['test_f1'] = float(f1_score(y_true, y_pred, average='weighted', zero_division=0))

                # Backward-compatible aliases
                metrics['accuracy'] = metrics['test_accuracy']
                metrics['precision'] = metrics['test_precision']
                metrics['recall'] = metrics['test_recall']
                metrics['f1'] = metrics['test_f1']

                if y_pred_proba is not None and len(y_true.unique()) == 2:
                    metrics['test_auc'] = float(roc_auc_score(y_true, y_pred_proba[:, 1]))
                    metrics['test_log_loss'] = float(log_loss(y_true, y_pred_proba))
                    metrics['auc'] = metrics['test_auc']
                    metrics['log_loss'] = metrics['test_log_loss']
                    
                    try:
                        y_true_test_ks = np.asarray(y_true).ravel()
                        y_score_test_ks = np.asarray(y_pred_proba[:, 1], dtype=float).ravel()
                        ks_stat_test, _ = calculate_ks(y_true_test_ks, y_score_test_ks)
                        metrics['test_ks_statistic'] = float(ks_stat_test)
                        metrics['ks_statistic'] = float(ks_stat_test)
                        _, metrics['test_gini'] = compute_auc_gini(y_true_test_ks, y_score_test_ks)
                    except Exception as ks_e:
                        self.logger.warning(f"Error calculating test KS statistic: {str(ks_e)}")
                        metrics['test_ks_statistic'] = 0.0
                        metrics['ks_statistic'] = 0.0

                # TRAIN SET metrics (if provided)
                if y_train is not None and y_pred_train is not None:
                    metrics['train_accuracy'] = float(accuracy_score(y_train, y_pred_train))
                    metrics['train_precision'] = float(precision_score(y_train, y_pred_train, average='weighted', zero_division=0))
                    metrics['train_recall'] = float(recall_score(y_train, y_pred_train, average='weighted', zero_division=0))
                    metrics['train_f1'] = float(f1_score(y_train, y_pred_train, average='weighted', zero_division=0))

                    if y_pred_proba_train is not None and len(y_true.unique()) == 2:
                        metrics['train_auc'] = float(roc_auc_score(y_train, y_pred_proba_train[:, 1]))
                        metrics['train_log_loss'] = float(log_loss(y_train, y_pred_proba_train))
                        
                        try:
                            y_train_ks = np.asarray(y_train).ravel()
                            y_score_train_ks = np.asarray(y_pred_proba_train[:, 1], dtype=float).ravel()
                            ks_stat_train, _ = calculate_ks(y_train_ks, y_score_train_ks)
                            metrics['train_ks_statistic'] = float(ks_stat_train)
                            _, metrics['train_gini'] = compute_auc_gini(y_train_ks, y_score_train_ks)
                        except Exception as ks_e:
                            self.logger.warning(f"Error calculating train KS statistic: {str(ks_e)}")
                            metrics['train_ks_statistic'] = 0.0

                        ofp = compute_auc_overfit_pct(
                            metrics.get('train_auc'),
                            metrics.get('test_auc'),
                        )
                        if ofp is not None:
                            metrics['overfit_pct'] = float(ofp)

                        # Calculate KS statistic difference percentage
                        if 'train_ks_statistic' in metrics and 'test_ks_statistic' in metrics:
                            try:
                                if metrics['test_ks_statistic'] > 0:
                                    metrics['ks_statistic_difference_percent'] = ((metrics['train_ks_statistic'] - metrics['test_ks_statistic']) / metrics['test_ks_statistic']) * 100
                            except Exception as ks_diff_e:
                                self.logger.warning(f"Error calculating KS statistic difference: {str(ks_diff_e)}")

                    # Calculate train-test difference percentages for key metrics
                    try:
                        if metrics['test_accuracy'] > 0:
                            metrics['accuracy_difference_percent'] = ((metrics['train_accuracy'] - metrics['test_accuracy']) / metrics['test_accuracy']) * 100
                        if metrics['test_precision'] > 0:
                            metrics['precision_difference_percent'] = ((metrics['train_precision'] - metrics['test_precision']) / metrics['test_precision']) * 100
                        if metrics['test_recall'] > 0:
                            metrics['recall_difference_percent'] = ((metrics['train_recall'] - metrics['test_recall']) / metrics['test_recall']) * 100
                        if metrics['test_f1'] > 0:
                            metrics['f1_difference_percent'] = ((metrics['train_f1'] - metrics['test_f1']) / metrics['test_f1']) * 100
                        if 'test_auc' in metrics and metrics['test_auc'] > 0:
                            metrics['auc_difference_percent'] = ((metrics['train_auc'] - metrics['test_auc']) / metrics['test_auc']) * 100
                    except Exception as diff_e:
                        self.logger.warning(f"Error calculating train-test difference percentages: {str(diff_e)}")

            # Regression metrics
            else:
                metrics['test_r2'] = float(r2_score(y_true, y_pred))
                metrics['test_mae'] = float(mean_absolute_error(y_true, y_pred))
                metrics['test_mse'] = float(mean_squared_error(y_true, y_pred))
                metrics['test_rmse'] = float(np.sqrt(mean_squared_error(y_true, y_pred)))

                # Backward-compatible aliases
                metrics['r2'] = metrics['test_r2']
                metrics['mae'] = metrics['test_mae']
                metrics['mse'] = metrics['test_mse']
                metrics['rmse'] = metrics['test_rmse']

                # TRAIN SET metrics (if provided)
                if y_train is not None and y_pred_train is not None:
                    metrics['train_r2'] = float(r2_score(y_train, y_pred_train))
                    metrics['train_mae'] = float(mean_absolute_error(y_train, y_pred_train))
                    metrics['train_mse'] = float(mean_squared_error(y_train, y_pred_train))
                    metrics['train_rmse'] = float(np.sqrt(mean_squared_error(y_train, y_pred_train)))

                    # Calculate train-test difference percentages for regression
                    try:
                        if metrics['test_r2'] > 0:
                            metrics['r2_difference_percent'] = ((metrics['train_r2'] - metrics['test_r2']) / metrics['test_r2']) * 100
                        if metrics['test_mae'] > 0:
                            metrics['mae_difference_percent'] = ((metrics['train_mae'] - metrics['test_mae']) / metrics['test_mae']) * 100
                        if metrics['test_rmse'] > 0:
                            metrics['rmse_difference_percent'] = ((metrics['train_rmse'] - metrics['test_rmse']) / metrics['test_rmse']) * 100
                    except Exception as diff_e:
                        self.logger.warning(f"Error calculating train-test difference percentages for regression: {str(diff_e)}")

            # Ensure all metrics are JSON serializable
            metrics = make_json_serializable(metrics)

        except Exception as e:
            self.logger.error(f"Error calculating metrics: {str(e)}")
            # Return basic metrics if detailed calculation fails
            metrics = {'accuracy': 0.0}

        return metrics

    def _format_model_comparison_data(self, results: List[Dict], problem_type: str) -> str:
        """
        Format all model metadata into structured text for LLM analysis
        
        Args:
            results: List of model training results
            problem_type: 'classification' or 'regression'
            
        Returns:
            Formatted string with all model comparison data
        """
        primary_metric = "AUC" if problem_type == "classification" else "R²"
        
        model_data = []
        
        for idx, result in enumerate(results, 1):
            if 'error' in result:
                continue
                
            model_id = result.get('model_id', f'Model_{idx}')
            algorithm = result.get('algorithm', 'Unknown')
            metrics = result.get('metrics', {})
            cv_scores = result.get('cv_scores', [])
            hyperparameters = result.get('hyperparameters', {})
            iteration_history = result.get('iteration_history', {})
            
            # Handle both dict and list formats for iteration_history
            if isinstance(iteration_history, dict):
                iterations_list = iteration_history.get('iterations', [])
            else:
                iterations_list = iteration_history if isinstance(iteration_history, list) else []
            
            best_score = result.get('best_score', 0.0)
            convergence_iter = result.get('convergence_iteration', 0)
            
            # Calculate CV statistics
            cv_mean = float(np.mean(cv_scores)) if cv_scores else 0.0
            cv_std = float(np.std(cv_scores)) if cv_scores else 0.0
            
            # Extract key metrics based on problem type
            if problem_type == 'classification':
                key_metrics = {
                    'AUC': metrics.get('test_auc', metrics.get('auc', 0.0)),
                    'F1': metrics.get('test_f1', metrics.get('f1', 0.0)),
                    'Accuracy': metrics.get('test_accuracy', metrics.get('accuracy', 0.0)),
                    'Precision': metrics.get('test_precision', metrics.get('precision', 0.0)),
                    'Recall': metrics.get('test_recall', metrics.get('recall', 0.0)),
                    'KS Statistic': metrics.get('test_ks_statistic', metrics.get('ks_statistic', 0.0)),
                    'Log Loss': metrics.get('test_log_loss', metrics.get('log_loss', 0.0))
                }
                
                # Train-test differences
                train_metrics = {}
                if metrics.get('train_auc') is not None:
                    train_metrics['Train AUC'] = metrics.get('train_auc')
                if metrics.get('train_f1') is not None:
                    train_metrics['Train F1'] = metrics.get('train_f1')
                if metrics.get('train_accuracy') is not None:
                    train_metrics['Train Accuracy'] = metrics.get('train_accuracy')
                
                gap_metrics = {}
                if metrics.get('auc_difference_percent') is not None:
                    gap_metrics['AUC Gap %'] = metrics.get('auc_difference_percent')
                if metrics.get('f1_difference_percent') is not None:
                    gap_metrics['F1 Gap %'] = metrics.get('f1_difference_percent')
                if metrics.get('accuracy_difference_percent') is not None:
                    gap_metrics['Accuracy Gap %'] = metrics.get('accuracy_difference_percent')
            else:  # regression
                key_metrics = {
                    'R²': metrics.get('test_r2', metrics.get('r2', 0.0)),
                    'RMSE': metrics.get('test_rmse', metrics.get('rmse', 0.0)),
                    'MAE': metrics.get('test_mae', metrics.get('mae', 0.0)),
                    'MSE': metrics.get('test_mse', metrics.get('mse', 0.0))
                }
                
                train_metrics = {}
                if metrics.get('train_r2') is not None:
                    train_metrics['Train R²'] = metrics.get('train_r2')
                if metrics.get('train_rmse') is not None:
                    train_metrics['Train RMSE'] = metrics.get('train_rmse')
                
                gap_metrics = {}
                if metrics.get('r2_difference_percent') is not None:
                    gap_metrics['R² Gap %'] = metrics.get('r2_difference_percent')
                if metrics.get('rmse_difference_percent') is not None:
                    gap_metrics['RMSE Gap %'] = metrics.get('rmse_difference_percent')
            
            # Format iteration history
            iteration_summary = []
            for iter_data in iterations_list[:5]:  # Show first 5 iterations
                iter_num = iter_data.get('iteration', 0)
                iter_score = iter_data.get('score', 0.0)
                iter_improvement = iter_data.get('improvement', 0.0)
                iter_status = iter_data.get('status', 'Completed')
                iter_metrics = iter_data.get('metrics', {})
                
                # Get primary metric from iteration
                if problem_type == 'classification':
                    iter_primary = iter_metrics.get('test_auc', iter_metrics.get('auc', iter_score))
                else:
                    iter_primary = iter_metrics.get('test_r2', iter_metrics.get('r2', iter_score))
                
                iteration_summary.append(
                    f"  Iteration {iter_num}: {primary_metric}={iter_primary:.4f}, "
                    f"Improvement={iter_improvement:+.4f}, Status={iter_status}"
                )
            
            if len(iterations_list) > 5:
                iteration_summary.append(f"  ... ({len(iterations_list) - 5} more iterations)")
            
            # Format hyperparameters (show key ones)
            hyperparams_str = ", ".join([f"{k}={v}" for k, v in list(hyperparameters.items())[:5]])
            if len(hyperparameters) > 5:
                hyperparams_str += f" ... ({len(hyperparameters) - 5} more)"
            
            # Build model description
            model_text = f"""
MODEL #{idx}: {algorithm}
Model ID: {model_id}

FINAL PERFORMANCE METRICS:
{chr(10).join([f"  {k}: {v:.4f}" for k, v in key_metrics.items() if v is not None])}

TRAIN METRICS (for overfitting analysis):
{chr(10).join([f"  {k}: {v:.4f}" for k, v in train_metrics.items() if v is not None]) if train_metrics else "  N/A"}

TRAIN-TEST GAP ANALYSIS:
{chr(10).join([f"  {k}: {v:.2f}%" for k, v in gap_metrics.items() if v is not None]) if gap_metrics else "  N/A"}

CROSS-VALIDATION:
  Mean: {cv_mean:.4f}
  Std: {cv_std:.4f}
  Scores: {[round(s, 4) for s in cv_scores[:5]]}{'...' if len(cv_scores) > 5 else ''}

HYPERPARAMETERS:
  {hyperparams_str if hyperparams_str else 'Default parameters'}

ITERATION HISTORY (Training Trajectory):
{chr(10).join(iteration_summary) if iteration_summary else '  Single iteration (no hyperparameter tuning)'}

CONVERGENCE:
  Best Score: {best_score:.4f}
  Convergence Iteration: {convergence_iter}
  Total Iterations: {len(iterations_list)}

FEATURE IMPORTANCE:
  Features with non-zero importance: {metrics.get('feature_importance_count', 'N/A')}
"""
            model_data.append(model_text)
        
        return "\n".join(model_data)

    def _parse_llm_response(self, llm_response: str, valid_model_ids: List[str]) -> Dict[str, Any]:
        """
        Parse LLM JSON response and validate model_id
        
        Args:
            llm_response: Raw LLM response string (should be JSON)
            valid_model_ids: List of valid model IDs to validate against
            
        Returns:
            Parsed and validated response dict
        """
        try:
            # Try to extract JSON from response (in case LLM adds markdown or extra text)
            import re
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = llm_response
            
            parsed = json.loads(json_str)
            
            # Validate model_id exists
            best_model_id = parsed.get('best_model_id', '')
            if best_model_id not in valid_model_ids:
                self.logger.warning(f"LLM returned invalid model_id: {best_model_id}. Valid IDs: {valid_model_ids}")
                return None
            
            return parsed
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM JSON response: {str(e)}")
            self.logger.debug(f"LLM response: {llm_response[:500]}")
            return None
        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {str(e)}")
            return None

    def select_best_model(self, training_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Select the best model from training results using LLM-based analysis
        
        Args:
            training_results: Complete training results with all models
            
        Returns:
            Dictionary with best model information and detailed reasoning
        """
        try:
            results = training_results.get('results', [])
            problem_type = training_results.get('problem_type', 'classification')
            
            if not results:
                return {
                    'best_model': None,
                    'reasoning': 'No models available for comparison',
                    'metrics_comparison': []
                }
            
            # Filter out error results
            valid_results = [r for r in results if 'error' not in r and 'model_id' in r]
            
            if not valid_results:
                return {
                    'best_model': None,
                    'reasoning': 'No valid models with metrics available',
                    'metrics_comparison': []
                }
            
            # Get valid model IDs for validation
            valid_model_ids = [r.get('model_id') for r in valid_results]
            
            # Determine primary metric
            primary_metric = "AUC" if problem_type == "classification" else "R²"
            
            # Format model comparison data
            model_comparison_data = self._format_model_comparison_data(valid_results, problem_type)
            
            # Build combined LLM prompt (system + user)
            COMBINED_PROMPT = f"""You are an expert machine learning model evaluator with deep expertise in:
- Model performance evaluation and comparison
- Understanding training dynamics and convergence patterns
- Identifying overfitting and generalization issues
- Balancing model complexity with performance
- Interpreting hyperparameter sensitivity and optimization trajectories

Your role is to analyze multiple trained machine learning models and select the best one based on comprehensive evaluation criteria. You must provide clear, data-driven reasoning for your selection.

DECISION-MAKING CRITERIA (in priority order):

1. **Generalization Performance (Highest Priority)**
   - Primary metric performance (AUC for binary classification, F1 for multiclass, R² for regression)
   - Cross-validation stability (lower CV std = more stable)
   - Train-test gap analysis (smaller gap = better generalization)
   - Overfitting indicators (large train-test difference = potential overfitting)

2. **Training Stability & Convergence**
   - Smooth convergence pattern (steady improvement vs erratic)
   - Early convergence (reached best performance quickly) vs late convergence
   - Variance across iterations (lower variance = more stable)
   - Hyperparameter sensitivity (stable performance across hyperparameter changes)

3. **Model Robustness**
   - Consistent performance across all metrics (not just one metric)
   - Feature importance patterns (models using diverse features are often more robust)
   - Cross-validation consistency (low variance in CV scores)

4. **Performance Balance**
   - For Classification: Balance between AUC, F1, Precision, Recall, and KS Statistic
   - For Regression: Balance between R², RMSE, MAE (considering all together)
   - Avoid models that excel in one metric but fail in others

5. **Hyperparameter Optimization Quality**
   - Evidence of effective hyperparameter search (clear improvement trajectory)
   - Best hyperparameters are reasonable (not extreme values)


RED FLAGS (avoid these models):
- Large train-test gap (>15% difference in primary metric)
- High CV variance (std > 0.05 for primary metric)
- Erratic iteration history (wild swings in performance)
- Overfitting indicators (train >> test performance)
- Models with missing critical metrics

OUTPUT REQUIREMENTS:
- Must return valid JSON with exact model_id from provided models
- Provide short reasoning citing specific metrics and patterns
- List key factors that influenced the decision
- Mention alternatives considered and why they were not selected
- Be objective and data-driven, not speculative

---

Analyze the following trained machine learning models and select the best performing model.

PROBLEM TYPE: {problem_type}
PRIMARY METRIC: {primary_metric}

=== MODEL COMPARISON ===

{model_comparison_data}

=== DECISION TASK ===

Based on the comprehensive analysis above, select the BEST model considering:
1. Overall generalization performance (primary metric + all supporting metrics)
2. Training stability and convergence behavior
3. Model robustness (consistent across metrics)
4. Train-test gap (overfitting indicators)
5. Cross-validation stability
6. Hyperparameter optimization quality
7. Performance balance across all metrics

Provide your analysis in the following JSON format:
{{
  "best_model_id": "exact_model_id_from_above",
  "reasoning": "Detailed explanation (3-5 sentences) citing specific metrics, patterns, and observations that led to this selection. Reference specific iteration numbers, metric values, and convergence patterns.",
  "key_factors": [
    "Factor 1: e.g., 'Highest AUC (0.92) with stable CV scores (std=0.02)'",
    "Factor 2: e.g., 'Converged early at iteration 3 with consistent improvement'",
    "Factor 3: e.g., 'Minimal train-test gap (2.1%) indicating good generalization'",
    "Factor 4: e.g., 'Balanced performance across all metrics (AUC, F1, Precision, Recall)'"
  ],
  "alternatives_considered": [
    {{
      "model_id": "alternative_model_id",
      "why_not_selected": "Brief reason (1 sentence)"
    }}
  ],
  "performance_summary": {{
    "primary_metric_value": 0.92,
    "train_test_gap_percent": 2.1,
    "cv_stability": "low_variance",
    "convergence_quality": "early_and_stable"
  }},
  "confidence_level": "high|medium|low"
}}

IMPORTANT:
- The model_id must match exactly one of the provided model IDs
- Be specific in your reasoning - cite actual metric values and iteration numbers
- If models are very close in performance (<1% difference), explain why you chose one over others
- Consider the full training trajectory, not just final metrics"""

            # Call LLM
            self.logger.info("Calling LLM for best model selection...")
            try:
                llm_response = llm_service.get_response_route(COMBINED_PROMPT, [])
                
                # Log the raw LLM response
                self.logger.info("=" * 80)
                self.logger.info("LLM RESPONSE FOR BEST MODEL SELECTION:")
                self.logger.info("=" * 80)
                self.logger.info(f"Raw LLM Response:\n{llm_response}")
                self.logger.info("=" * 80)
                
                # Parse LLM response
                parsed_response = self._parse_llm_response(llm_response, valid_model_ids)
                
                if parsed_response is None:
                    self.logger.error("Failed to parse LLM response or invalid model_id")
                    raise Exception("Failed to parse LLM response or invalid model_id")
                
                # Log the parsed response
                self.logger.info("Parsed LLM Response:")
                self.logger.info(f"  - Best Model ID: {parsed_response.get('best_model_id', 'N/A')}")
                self.logger.info(f"  - Reasoning: {parsed_response.get('reasoning', 'N/A')[:200]}...")  # First 200 chars
                self.logger.info(f"  - Key Factors: {len(parsed_response.get('key_factors', []))} factors")
                self.logger.info(f"  - Confidence: {parsed_response.get('confidence_level', 'N/A')}")
                self.logger.info("=" * 80)
                
                best_model_id = parsed_response.get('best_model_id')
                llm_reasoning = parsed_response.get('reasoning', 'LLM selected best model')
                key_factors = parsed_response.get('key_factors', [])
                alternatives = parsed_response.get('alternatives_considered', [])
                performance_summary = parsed_response.get('performance_summary', {})
                confidence = parsed_response.get('confidence_level', 'medium')
                
                # Find the best model result
                best_model_result = None
                for result in valid_results:
                    if result.get('model_id') == best_model_id:
                        best_model_result = result
                        break
                
                if best_model_result is None:
                    raise Exception(f"Best model {best_model_id} not found in results")
                
                # Build metrics comparison table (for frontend compatibility)
                metrics_comparison = []
                for idx, result in enumerate(valid_results, 1):
                    metrics = result.get('metrics', {})
                    algorithm = result.get('algorithm', 'Unknown')
                    model_id = result.get('model_id', '')
                    
                    # Extract key metrics for comparison
                    if problem_type == 'classification':
                        comparison_metrics = {
                            'auc': metrics.get('test_auc', metrics.get('auc', 0.0)),
                            'f1': metrics.get('test_f1', metrics.get('f1', 0.0)),
                            'accuracy': metrics.get('test_accuracy', metrics.get('accuracy', 0.0)),
                            'precision': metrics.get('test_precision', metrics.get('precision', 0.0)),
                            'recall': metrics.get('test_recall', metrics.get('recall', 0.0))
                        }
                    else:
                        comparison_metrics = {
                            'r2': metrics.get('test_r2', metrics.get('r2', 0.0)),
                            'rmse': metrics.get('test_rmse', metrics.get('rmse', 0.0)),
                            'mae': metrics.get('test_mae', metrics.get('mae', 0.0)),
                            'mse': metrics.get('test_mse', metrics.get('mse', 0.0))
                        }
                    
                    metrics_comparison.append({
                        'rank': idx,
                        'algorithm': algorithm,
                        'model_id': model_id,
                        'metrics': comparison_metrics,
                        'is_best': model_id == best_model_id
                    })
                
                # Sort by primary metric for ranking
                if problem_type == 'classification':
                    metrics_comparison.sort(key=lambda x: x['metrics'].get('auc', 0), reverse=True)
                else:
                    metrics_comparison.sort(key=lambda x: x['metrics'].get('r2', 0), reverse=True)
                
                # Update ranks after sorting
                for idx, entry in enumerate(metrics_comparison, 1):
                    entry['rank'] = idx
                
                self.logger.info(f"LLM selected best model: {best_model_id} (confidence: {confidence})")
                
                return make_json_serializable({
                    'best_model': best_model_result,
                    'best_model_id': best_model_id,
                    'best_algorithm': best_model_result.get('algorithm', 'Unknown'),
                    'reasoning': llm_reasoning,
                    'reasoning_details': {
                        'key_factors': key_factors,
                        'alternatives_considered': alternatives,
                        'performance_summary': performance_summary,
                        'confidence_level': confidence,
                        'selection_method': 'llm_based',
                        'total_models_compared': len(valid_results)
                    },
                    'metrics_comparison': metrics_comparison,
                    'problem_type': problem_type
                })
                
            except Exception as llm_error:
                self.logger.error(f"LLM-based model selection failed: {str(llm_error)}")
                self.logger.warning("Falling back to simple metric-based selection")
                
                # Fallback: Select by primary metric
                if problem_type == 'classification':
                    best_result = max(valid_results, key=lambda x: x.get('metrics', {}).get('test_auc', x.get('metrics', {}).get('auc', 0.0)))
                    primary_value = best_result.get('metrics', {}).get('test_auc', best_result.get('metrics', {}).get('auc', 0.0))
                else:
                    best_result = max(valid_results, key=lambda x: x.get('metrics', {}).get('test_r2', x.get('metrics', {}).get('r2', 0.0)))
                    primary_value = best_result.get('metrics', {}).get('test_r2', best_result.get('metrics', {}).get('r2', 0.0))
                
                best_model_id = best_result.get('model_id')
                
                # Build simple metrics comparison
                metrics_comparison = []
                for idx, result in enumerate(valid_results, 1):
                    metrics = result.get('metrics', {})
                    algorithm = result.get('algorithm', 'Unknown')
                    model_id = result.get('model_id', '')
                    
                    if problem_type == 'classification':
                        comparison_metrics = {
                            'auc': metrics.get('test_auc', metrics.get('auc', 0.0)),
                            'f1': metrics.get('test_f1', metrics.get('f1', 0.0)),
                            'accuracy': metrics.get('test_accuracy', metrics.get('accuracy', 0.0))
                        }
                    else:
                        comparison_metrics = {
                            'r2': metrics.get('test_r2', metrics.get('r2', 0.0)),
                            'rmse': metrics.get('test_rmse', metrics.get('rmse', 0.0)),
                            'mae': metrics.get('test_mae', metrics.get('mae', 0.0))
                        }
                    
                    metrics_comparison.append({
                        'rank': idx,
                        'algorithm': algorithm,
                        'model_id': model_id,
                        'metrics': comparison_metrics,
                        'is_best': model_id == best_model_id
                    })
                
                # Sort and update ranks
                if problem_type == 'classification':
                    metrics_comparison.sort(key=lambda x: x['metrics'].get('auc', 0), reverse=True)
                else:
                    metrics_comparison.sort(key=lambda x: x['metrics'].get('r2', 0), reverse=True)
                
                for idx, entry in enumerate(metrics_comparison, 1):
                    entry['rank'] = idx
                
                return make_json_serializable({
                    'best_model': best_result,
                    'best_model_id': best_model_id,
                    'best_algorithm': best_result.get('algorithm', 'Unknown'),
                    'reasoning': f'Selected {best_result.get("algorithm")} with {primary_metric}={primary_value:.4f} (fallback selection - LLM unavailable)',
                    'reasoning_details': {
                        'selection_method': 'fallback_metric_based',
                        'total_models_compared': len(valid_results),
                        'llm_error': str(llm_error)
                    },
                    'metrics_comparison': metrics_comparison,
                    'problem_type': problem_type
                })
            
        except Exception as e:
            self.logger.error(f"Error selecting best model: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {
                'best_model': None,
                'reasoning': f'Error during model selection: {str(e)}',
                'metrics_comparison': []
            }
    
    def _get_algorithm_reasoning(self, algorithm: str, problem_type: str) -> str:
        """Get specific reasoning for why an algorithm might be the best choice"""
        reasoning_map = {
            'XGBoost': f"XGBoost is known for excellent {problem_type} performance with gradient boosting",
            'LightGBM': "LightGBM offers fast training with high accuracy",
            'CatBoost': "CatBoost excels at handling categorical features automatically",
            'RandomForest': "Random Forest provides robust ensemble predictions",
            'LogisticRegression': "Logistic Regression offers high interpretability",
            'LinearRegression': "Linear Regression provides clear interpretable relationships",
            'GradientBoosting': "Gradient Boosting delivers strong predictive performance",
            'SVM': "Support Vector Machine is effective for complex decision boundaries"
        }
        return reasoning_map.get(algorithm, "")

    def run_pending_meea_jobs(self, dataset_id: str) -> None:
        """
        Run phased model evaluation (MEEA) for all models trained for *dataset_id*.

        Evaluation is split into 3 sequential phases executed across ALL models in
        parallel within each phase.  This means the user sees Performance results for
        every model before Monotonicity starts, and Monotonicity for every model before
        Granular Accuracy starts - giving the fastest possible time-to-first-result.

        Phase 1 - Performance (predictions + metrics + ROC/PR + feature importance)
        Phase 2 - Monotonicity (decile analysis, KS, AUC/Gini)
        Phase 3 - Granular Accuracy (segment-level accuracy per feature)

        Each phase writes its own partial JSON file so the frontend can fetch and
        render each tab independently as soon as it is ready.
        """
        try:
            from app.services.model_evaluation_service import model_evaluation_service
            from app.models.model_evaluation_database import model_evaluation_db
        except Exception as import_err:
            self.logger.error(f"MEEA background: failed to import evaluation services: {import_err}")
            return

        # Collect jobs that belong to this dataset
        jobs_to_run = {
            mid: args
            for mid, args in list(ModelTrainingAutoTrainingService._pending_meea_jobs.items())
            if args.get('dataset_id') == dataset_id
        }

        if not jobs_to_run:
            self.logger.info(f"MEEA background: no pending jobs for dataset {dataset_id}")
            return

        n_models = len(jobs_to_run)
        self.logger.info(f"MEEA background: starting phased evaluation for {n_models} model(s) - dataset {dataset_id}")

        from concurrent.futures import ThreadPoolExecutor, as_completed

        # ------------------------------------------------------------------
        # Helper: write a phase JSON file and merge into the comprehensive JSON
        # ------------------------------------------------------------------
        def _write_phase_json(model_id: str, phase_data: dict, phase_num: int) -> None:
            phase_path = os.path.join(self.model_storage_path, f"{model_id}_eval_phase{phase_num}.json")
            try:
                with open(phase_path, 'w') as fh:
                    json.dump(phase_data, fh, indent=2, default=str)
                self.logger.info(f"MEEA background: wrote phase{phase_num} JSON for {model_id}")
            except Exception as e:
                self.logger.warning(f"MEEA background: failed to write phase{phase_num} JSON for {model_id}: {e}")

            # Also merge into the comprehensive JSON so the existing /model-evaluation/{id}
            # endpoint continues to work for callers that haven't switched to phased endpoints.
            comp_path = os.path.join(self.model_storage_path, f"{model_id}_comprehensive_evaluation.json")
            try:
                existing: dict = {}
                if os.path.exists(comp_path):
                    with open(comp_path, 'r') as fh:
                        existing = json.load(fh)
                existing.update({k: v for k, v in phase_data.items() if not k.startswith('_phase')})
                with open(comp_path, 'w') as fh:
                    json.dump(existing, fh, indent=2, default=str)
            except Exception as e:
                self.logger.warning(f"MEEA background: failed to merge phase{phase_num} into comprehensive JSON for {model_id}: {e}")

        # ------------------------------------------------------------------
        # PHASE 1 - Performance (all models in parallel)
        # ------------------------------------------------------------------
        self.logger.info(f"MEEA background: === PHASE 1 (Performance) starting for {n_models} model(s) ===")
        phase1_results: dict = {}  # model_id -> phase1 data

        def _run_phase1(model_id: str, args: dict) -> None:
            try:
                self.logger.info(f"MEEA Phase1: evaluating {args.get('algorithm_name')} ({model_id})")
                p1 = model_evaluation_service.evaluate_phase1_performance(
                    model=args['model'],
                    model_id=model_id,
                    model_name=args['algorithm_name'],
                    X_train=args['X_train'],
                    X_test=args['X_test'],
                    y_train=args['y_train'],
                    y_test=args['y_test'],
                    problem_type=args['problem_type'],
                    feature_names=args['feature_names'],
                    dataset_id=args['dataset_id'],
                    active_scope=args['active_scope'],
                    target_column=args['target_column'],
                    split_params=args['split_params'],
                    preprocessed_columns=args['preprocessed_columns'],
                    train_indices=args['train_indices'],
                    test_indices=args['test_indices'],
                    category_mappings=args['category_mappings'],
                    X_test_original=args['X_test_original'],
                    X_train_original=args['X_train_original'],
                    scaler=args['scaler'],
                    column_stats=args['column_stats'],
                )
                phase1_results[model_id] = p1
                _write_phase_json(model_id, p1, 1)
                self.logger.info(f"MEEA Phase1: completed for {args.get('algorithm_name')} ({model_id})")
            except Exception as e:
                self.logger.error(f"MEEA Phase1: failed for {model_id}: {e}")
                import traceback
                self.logger.error(traceback.format_exc())

        max_workers = min(n_models, 4)
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="meea_p1") as executor:
            futures = {executor.submit(_run_phase1, mid, args): mid for mid, args in jobs_to_run.items()}
            for future in as_completed(futures):
                mid = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    self.logger.error(f"MEEA Phase1: unhandled exception for {mid}: {exc}")

        self.logger.info(f"MEEA background: === PHASE 1 complete - {len(phase1_results)}/{n_models} succeeded ===")

        # MEMORY OPTIMIZATION (#2 - drop heavy frames once Phase 1 is done):
        # The large DataFrames (X_train, X_test, X_train_original, X_test_original)
        # are consumed ONLY by Phase 1. Phase 2 (Monotonicity) and Phase 3 (Granular
        # Accuracy) read just the fitted model, model_id, problem_type and
        # feature_names. Previously every job kept all four frames alive until it
        # was popped at the end of Phase 3, so up to ~5 models x 4 frames stayed
        # resident through two more phases. Nulling them here (and forcing a
        # collect) releases the bulk of the peak DataFrame memory for the entire
        # duration of Phases 2 and 3.
        for _args in jobs_to_run.values():
            for _heavy_key in ('X_train', 'X_test', 'X_train_original', 'X_test_original'):
                if _heavy_key in _args:
                    _args[_heavy_key] = None
        gc.collect()

        # ------------------------------------------------------------------
        # PHASE 2 - Monotonicity (all models in parallel)
        # ------------------------------------------------------------------
        self.logger.info(f"MEEA background: === PHASE 2 (Monotonicity) starting ===")

        def _run_phase2(model_id: str, args: dict) -> None:
            try:
                p2 = model_evaluation_service.evaluate_phase2_monotonicity(
                    model=args['model'],
                    model_id=model_id,
                    problem_type=args['problem_type'],
                    feature_names=args['feature_names'],
                )
                _write_phase_json(model_id, p2, 2)
                self.logger.info(f"MEEA Phase2: completed for {args.get('algorithm_name')} ({model_id})")
            except Exception as e:
                self.logger.error(f"MEEA Phase2: failed for {model_id}: {e}")
                import traceback
                self.logger.error(traceback.format_exc())

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="meea_p2") as executor:
            futures = {executor.submit(_run_phase2, mid, args): mid for mid, args in jobs_to_run.items()}
            for future in as_completed(futures):
                mid = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    self.logger.error(f"MEEA Phase2: unhandled exception for {mid}: {exc}")

        self.logger.info(f"MEEA background: === PHASE 2 complete ===")

        # ------------------------------------------------------------------
        # PHASE 3 - Granular Accuracy (all models in parallel)
        # ------------------------------------------------------------------
        self.logger.info(f"MEEA background: === PHASE 3 (Granular Accuracy) starting ===")

        def _run_phase3(model_id: str, args: dict) -> None:
            try:
                p3 = model_evaluation_service.evaluate_phase3_granular(
                    model_id=model_id,
                    problem_type=args['problem_type'],
                    feature_names=args['feature_names'],
                )
                _write_phase_json(model_id, p3, 3)
                self.logger.info(f"MEEA Phase3: completed for {args.get('algorithm_name')} ({model_id})")
            except Exception as e:
                self.logger.error(f"MEEA Phase3: failed for {model_id}: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            finally:
                # Remove from pending only after all 3 phases are done
                ModelTrainingAutoTrainingService._pending_meea_jobs.pop(model_id, None)

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="meea_p3") as executor:
            futures = {executor.submit(_run_phase3, mid, args): mid for mid, args in jobs_to_run.items()}
            for future in as_completed(futures):
                mid = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    self.logger.error(f"MEEA Phase3: unhandled exception for {mid}: {exc}")
                    ModelTrainingAutoTrainingService._pending_meea_jobs.pop(mid, None)

        self.logger.info(f"MEEA background: === PHASE 3 complete - all phases done for dataset {dataset_id} ===")

        # Persist final comprehensive evaluation to DB (best-effort)
        for model_id in list(jobs_to_run.keys()):
            comp_path = os.path.join(self.model_storage_path, f"{model_id}_comprehensive_evaluation.json")
            if not os.path.exists(comp_path):
                continue
            try:
                with open(comp_path, 'r') as fh:
                    comprehensive_evaluation = json.load(fh)
                db_formatted_data = model_evaluation_service.format_for_database(comprehensive_evaluation)
                model_evaluation_db.save_evaluation_results(db_formatted_data)
                self.logger.info(f"MEEA background: saved comprehensive evaluation to DB for {model_id}")
            except Exception as db_err:
                self.logger.warning(f"MEEA background: DB save failed for {model_id} (non-fatal): {db_err}")

        self.logger.info(f"MEEA background: all phases completed for dataset {dataset_id}")

    def run_complete_auto_training(self, dataset_id: str, target_column: str,
                                  selected_variables: Optional[List[str]] = None,
                                  selection_mode: str = "auto",
                                  selected_algorithms: Optional[List[str]] = None,
                                  weight_variable: Optional[str] = None,
                                  locked_variables: Optional[List[str]] = None,
                                  job_id: Optional[str] = None) -> Dict[str, Any]: #<-- user selected algos are passed here
        """
        Run the complete automatic training pipeline

        Args:
            dataset_id: ID of the dataset to use
            target_column: Name of the target column
            weight_variable: Optional weight column for sample_weight

        Returns:
            Dictionary with complete training results
        """
        try:
            def _is_job_cancelled() -> bool:
                if not job_id:
                    return False
                try:
                    """
                    Poll the status of a /train-global-model background job.

                    Phase-1 stateless-API fix: reads from ``background_job_manager``
                    first (S3-mirrored snapshot, works across EKS replicas). Falls back
                    to the legacy in-process ``training_jobs`` dict so any job that was
                    enqueued before this deploy can still complete its lifecycle.
                    """
                    from app.services.background_jobs import background_job_manager as _bjm
                    snap = _bjm.get_job_status(job_id)
                    if not snap:
                        return False
                    status = str(snap.get("status") or "").lower()
                    error = str(snap.get("error") or "").lower()
                    return status == "failed" and "cancel" in error
                except Exception:
                    return False

            def _raise_if_cancelled(where: str) -> None:
                if _is_job_cancelled():
                    self.logger.info("Auto training cancellation detected at %s for job_id=%s", where, job_id)
                    raise RuntimeError("Auto training cancelled by user")

            self.logger.info(f"Starting complete auto training for dataset {dataset_id} with target {target_column}")
            _raise_if_cancelled("run_complete_auto_training.start")

            # Step 1: Load dataset
            try:
                from app.services.dataset_service import dataset_manager
                from app.services.dataframe_state_manager import dataframe_state_manager
                
                # Load data based on active scope to respect user's train/test split
                active_scope_for_load = dataframe_state_manager._active_scope.get(dataset_id, 'entire')
                self.logger.info(f"Active scope for dataset {dataset_id}: {active_scope_for_load}")
                
                if active_scope_for_load == 'dev':
                    # Use set_scope to get the correctly filtered dev view.
                    # Pass the persisted ratio/seed so that after an Azure restart the
                    # same split is recreated (set_scope also rehydrates from disk, but
                    # passing it explicitly here is a belt-and-suspenders safeguard).
                    try:
                        from app.api.routes import get_split_config as _get_split_cfg
                        _scfg = _get_split_cfg(dataset_id)
                    except Exception:
                        _scfg = {}
                    _ratio = _scfg.get("ratio", 0.7)
                    _seed = _scfg.get("seed", 42)
                    _sv = _scfg.get("sampling_variable", None)
                    self.logger.info(
                        f"📊 set_scope('dev') for training with ratio={_ratio}, seed={_seed}, "
                        f"sampling_variable={_sv} (from persisted config: {bool(_scfg)})"
                    )
                    scope_result = dataframe_state_manager.set_scope(
                        dataset_id, scope='dev', ratio=_ratio, seed=_seed,
                        sampling_variable=_sv
                    )
                    df = dataframe_state_manager.get_dataframe(dataset_id)
                    self.logger.info(f"✅ Using TRAIN data for training, shape: {df.shape if df is not None else 'None'}")
                elif active_scope_for_load in ('train', 'test', 'validation'):
                    dataframe_state_manager.set_scope(dataset_id, scope=active_scope_for_load)
                    df = dataframe_state_manager.get_dataframe(dataset_id)
                    self.logger.info(
                        f"✅ Using {active_scope_for_load} scope (TTV) for training, "
                        f"shape: {df.shape if df is not None else 'None'}"
                    )
                else:
                    df = dataframe_state_manager._transformed_copies.get(dataset_id, {}).get('entire')
                    if df is None:
                        df = dataframe_state_manager.get_dataframe(dataset_id)
                    self.logger.info(f"✅ Using ENTIRE dataset for training, shape: {df.shape if df is not None else 'None'}")
                
                # If still not found in state manager, try loading from file system
                if df is None:
                    df = dataset_manager.load_dataset(dataset_id)

                if df is None or df.empty:
                    raise ValueError(f"Dataset {dataset_id} not found or could not be loaded")

                # Densify any sparse columns - pandas cannot compute std/mean/quantile on Sparse dtypes
                # and sklearn estimators may also reject them.  This is a no-op for dense DataFrames.
                sparse_cols = [c for c in df.columns if isinstance(df[c].dtype, pd.SparseDtype)]
                if sparse_cols:
                    self.logger.info(f"Densifying {len(sparse_cols)} sparse column(s) before training")
                    df = df.copy()
                    for c in sparse_cols:
                        df[c] = df[c].sparse.to_dense()

                self.logger.info(f"Successfully loaded dataset with shape: {df.shape} (scope: {active_scope_for_load})")
            except Exception as e:
                self.logger.error(f"Failed to load dataset {dataset_id}: {str(e)}")
                raise ValueError(f"Failed to load dataset: {str(e)}")

            # Step 2: Detect problem type
            try:
                problem_type_info = self.detect_problem_type_from_data(df, target_column)
                problem_type = problem_type_info['problem_type']
                self.logger.info(f"Detected problem type: {problem_type}")
            except Exception as e:
                self.logger.error(f"Failed to detect problem type for target {target_column}: {str(e)}")
                raise ValueError(f"Failed to detect problem type: {str(e)}")

            # Step 3: Get available variables and calculate VIF/correlation
            try:
                available_vars = self.get_available_variables(df)
                independent_variables = available_vars['default_independent']

                # Remove target from independent variables if present
                if target_column in independent_variables:
                    independent_variables.remove(target_column)

                self.logger.info(f"Available independent variables: {len(independent_variables)}")
            except Exception as e:
                self.logger.error(f"Failed to get available variables: {str(e)}")
                raise ValueError(f"Failed to get available variables: {str(e)}")

            # Step 4: Calculate VIF and correlation analysis
            # COMMENTED OUT: VIF already calculated in Variable Analysis step, selected_variables are passed directly
            # No need to recalculate VIF - variables are already selected (auto or manual) from Variable Analysis step
            # try:
            #     vif_correlation_data = self.calculate_vif_and_correlation(df, target_column, independent_variables)
            #     self.logger.info("VIF and correlation analysis completed")
            # except Exception as e:
            #     self.logger.error(f"Failed to calculate VIF and correlation: {str(e)}")
            #     raise ValueError(f"Failed to calculate variable statistics: {str(e)}")

            # VIF data not needed - variables already selected in Variable Analysis step
            vif_correlation_data = {}  # Empty dict for results storage
            self.logger.info(f"✅ Skipping VIF calculation - using {len(selected_variables) if selected_variables else 0} pre-selected variables from Variable Analysis step")

            # Step 5: Handle variable selection + Step 1 lock enforcement
            try:
                variable_selection = self.apply_variable_locking(
                    independent_variables=independent_variables,
                    selected_variables=selected_variables,
                    locked_variables=locked_variables,
                    selection_mode=selection_mode,
                )
                selected_variables = variable_selection['selected_variables']
                locked_variables = variable_selection.get('locked_variables', [])
            except Exception as e:
                self.logger.error(f"Failed to select variables: {str(e)}")
                raise ValueError(f"Failed to select variables: {str(e)}")

            # Step 6: Auto-select algorithms
            try:
                # Get feature type information for better algorithm selection
                feature_types = {
                    'numerical': len([col for col in selected_variables if col in df.columns and pd.api.types.is_numeric_dtype(df[col])]),
                    'categorical': len([col for col in selected_variables if col in df.columns and not pd.api.types.is_numeric_dtype(df[col])])
                }

                algorithm_config = self.auto_select_algorithms(
                    problem_type, len(df), len(selected_variables), feature_types
                )

                # Output of algorithm_config
                # Returns:
                # {
                #   "selected_algorithms": [
                #     {"name": "XGBoost", "display_name": "XGBoost", ...},
                #     {"name": "LightGBM", "display_name": "LightGBM", ...},
                #     {"name": "CatBoost", "display_name": "CatBoost", ...},
                #     {"name": "RandomForest", "display_name": "Random Forest", ...},
                #     {"name": "LogisticRegression", "display_name": "Logistic Regression", ...},
                #     {"name": "GradientBoosting", "display_name": "Gradient Boosting", ...}
                #   ],
                #   "selection_reasoning": "..."
                # }
                #
                # 6 algorithms returned!

                # Optional: filter algorithms based on user-selected subset
                if selected_algorithms:
                    allowed = {a.lower() for a in selected_algorithms}
                    filtered = [
                        a
                        for a in algorithm_config["selected_algorithms"]
                        if a.get("name", "").lower() in allowed
                        or a.get("display_name", "").lower() in allowed
                    ]
                    if filtered:
                        self.logger.info(
                            f"Filtering auto-selected algorithms based on user choice: "
                            f"{len(filtered)} of {len(algorithm_config['selected_algorithms'])} kept"
                        )
                        algorithm_config["selected_algorithms"] = filtered #this is how it is passed: eg -> algorithm_config["selected_algorithms"] = [XGBoost, LightGBM, CatBoost, RandomForest]
                    else:
                        self.logger.warning(
                            f"No algorithms matched user selection {selected_algorithms}; "
                            "falling back to full auto-selected set."
                        )

                self.logger.info(f"Selected algorithms: {len(algorithm_config['selected_algorithms'])}")
                self.logger.info(f"Selection reasoning: {algorithm_config.get('selection_reasoning', 'N/A')}")
            except Exception as e:
                self.logger.error(f"Failed to select algorithms: {str(e)}")
                raise ValueError(f"Failed to select algorithms: {str(e)}")

            # Step 7: Train models with detailed iterations
            try:
                # Get active scope from dataframe_state_manager
                active_scope = dataframe_state_manager._active_scope.get(dataset_id, 'entire')
                self.logger.info(f"Training with active scope: {active_scope}")
                if weight_variable:
                    self.logger.info(f"Using weight variable: {weight_variable}")
                
                training_results = self.train_models_with_iterations(
                    df, target_column, selected_variables, algorithm_config, independent_variables,
                    selection_mode, variable_selection, vif_correlation_data,
                    dataset_id=dataset_id,  # NEW: Pass dataset_id
                    active_scope=active_scope,  # NEW: Pass active_scope
                    weight_variable=weight_variable,  # Pass weight variable for sample_weight
                    cancel_check=_is_job_cancelled
                )
                self.logger.info(f"Training completed: {training_results['auto_selection_summary']['num_models_trained']} models trained successfully")
            except Exception as e:
                self.logger.error(f"Failed to train models: {str(e)}")
                raise ValueError(f"Failed to train models: {str(e)}")

            # Step 7.5: Generate column stats for all used features (for granular accuracy)
            try:
                column_stats = generate_column_stats(df, selected_variables)
                self.logger.info(f"Generated column stats for {len(column_stats)} features")
            except Exception as e:
                self.logger.warning(f"Failed to generate column stats: {str(e)}")
                column_stats = {}

            # Step 8: Compile complete results in format expected by frontend
            # Match the structure expected by the frontend (similar to manual configuration)
            complete_results = {
                'dataset_info': {
                    'dataset_id': dataset_id,
                    'shape': (int(df.shape[0]), int(df.shape[1])),  # Convert to native Python types
                    'target_column': target_column,
                    'problem_type': problem_type
                },
                'variable_analysis': make_json_serializable(vif_correlation_data),
                'variable_selection': make_json_serializable(variable_selection),
                'algorithm_selection': make_json_serializable(algorithm_config),
                'training_results': make_json_serializable(training_results),
                'column_stats': make_json_serializable(column_stats),
                'auto_selection_summary': {
                    'total_variables_analyzed': int(len(independent_variables)),
                    'variables_selected': int(len(selected_variables)),
                    'variables_locked': int(len(locked_variables) if locked_variables else 0),
                    'algorithms_selected': int(len(algorithm_config['selected_algorithms'])),
                    'num_models_trained': int(training_results['auto_selection_summary']['num_models_trained']),
                    'training_method': 'fully_automatic',
                    'variable_selection_mode': selection_mode
                }
            }

            # Select best model from results
            best_model_selection = self.select_best_model({
                'results': training_results['results'],
                'problem_type': problem_type
            })
            
            # Return flattened structure that matches frontend expectations
            flattened_results = {
                'problem_type': problem_type,
                'results': training_results['results'],  # Flatten the results array
                'used_features': training_results['used_features'],
                'dataset_info': {
                    'dataset_id': dataset_id,
                    'shape': (int(df.shape[0]), int(df.shape[1])),  # Convert to native Python types
                    'target_column': target_column,
                    'problem_type': problem_type
                },
                'auto_selection_summary': {
                    'total_variables_analyzed': int(len(independent_variables)),
                    'variables_selected': int(len(selected_variables)),
                    'variables_locked': int(len(locked_variables) if locked_variables else 0),
                    'algorithms_selected': int(len(algorithm_config['selected_algorithms'])),
                    'num_models_trained': int(training_results['auto_selection_summary']['num_models_trained']),
                    'training_method': 'fully_automatic',
                    'variable_selection_mode': selection_mode
                },
                'algorithm_selection': make_json_serializable(algorithm_config),
                'variable_selection': make_json_serializable(variable_selection),
                'variable_analysis': make_json_serializable(vif_correlation_data),
                'best_model_selection': make_json_serializable(best_model_selection),
                'column_stats': make_json_serializable(column_stats),
                'preprocessing_summary': make_json_serializable(training_results.get('preprocessing_summary', {
                    'is_already_preprocessed': False,
                    'variables': [],
                    'dropped_variables': [],
                    'total_processed': 0,
                    'total_dropped': 0
                }))
            }

            # Step 6 training insights (same payload shape as manual multi-model training)
            try:
                from app.services.model_training_manual_configuration import manual_config_service

                corr_map = manual_config_service._compute_bivariate_correlation_map(
                    df, target_column, list(selected_variables or [])
                )
                ufs = list(training_results.get("used_features") or selected_variables or [])
                step6_input_results: List[Dict[str, Any]] = []
                for r in training_results.get("results") or []:
                    if not isinstance(r, dict) or r.get("error"):
                        continue
                    row = dict(r)
                    if not row.get("used_features"):
                        row["used_features"] = ufs
                    step6_input_results.append(row)
                if step6_input_results:
                    step6_views = manual_config_service._build_step6_views(
                        results=step6_input_results,
                        problem_type=problem_type,
                        optimization_method="bayesian_optimization",
                        cv_folds=3,
                        optuna_trials=None,
                        early_stopping_rounds=None,
                        target_metric=None,
                        correlation_map=corr_map,
                    )
                    flattened_results["step6_views"] = make_json_serializable(step6_views)
            except Exception as step6_exc:
                self.logger.warning(f"Failed to build step6_views for auto training: {step6_exc}")

            self.logger.info(f"Auto training completed successfully for dataset {dataset_id}")
            self.logger.info(f"Best model selected: {best_model_selection.get('best_algorithm', 'N/A')}")
            return flattened_results

        except Exception as e:
            self.logger.error(f"Error in complete auto training for dataset {dataset_id}: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise


# Create singleton instance
auto_training_service = ModelTrainingAutoTrainingService()

import json
import pandas as pd
from typing import Dict, Any, List, Optional
from app.services.dataframe_state_manager import dataframe_state_manager
from app.core.logging_config import get_logger
from pathlib import Path
import numpy as np
from scipy.stats import pearsonr, spearmanr, chi2_contingency
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from joblib import Parallel, delayed
import math
import re
from datetime import datetime
import gc
import os
import pandas as pd
from collections import defaultdict


# Tracks the most recent Copy-on-Write decision so callers/logs can introspect
# it without re-reading the environment. None until configure_* is first called.
_PANDAS_COW_ENABLED: Optional[bool] = None


def configure_pandas_copy_on_write() -> bool:
    """Enable or disable pandas Copy-on-Write (CoW) based on ``MIDAS_PANDAS_COW``.

    WHY: The auto-training / DataFrameStateManager paths perform many *defensive*
    ``df.copy()`` and ``.loc[...]`` slice operations (set_scope, get_dataframe,
    per-model X_train/X_test/X_*_original copies). Without CoW each of those
    eagerly materialises a full duplicate, which is the bulk of the 16-28
    DataFrames seen at peak. With CoW (pandas >= 2.0) a ``.copy()`` / slice
    returns a lazy view that only allocates real memory if it is *mutated*, so
    the never-mutated defensive copies stop costing RAM.

    IMPACT: Lowers peak DataFrame memory across the whole process (and any loky
    worker that imports a module which calls this). CoW also changes semantics -
    mutating a slice no longer propagates to its parent - so the
    ``MIDAS_PANDAS_COW`` env var is provided as a kill switch:
        MIDAS_PANDAS_COW=1 (default) -> CoW enabled
        MIDAS_PANDAS_COW=0           -> CoW disabled (legacy eager-copy behaviour)

    Safe to call multiple times and from multiple processes; it only flips a
    global pandas option and never raises (older pandas without the option just
    logs a warning and is left untouched).

    Returns:
        The boolean CoW state that was applied (or the prior state on failure).
    """
    global _PANDAS_COW_ENABLED
    raw = os.environ.get("MIDAS_PANDAS_COW", "1").strip().lower()
    enabled = raw not in ("0", "false", "no", "off", "")
    logger = get_logger(__name__)
    try:
        pd.set_option("mode.copy_on_write", enabled)
        _PANDAS_COW_ENABLED = enabled
        logger.info(
            "pandas Copy-on-Write %s (MIDAS_PANDAS_COW=%s)",
            "ENABLED" if enabled else "DISABLED",
            raw or "<unset>",
        )
    except Exception as exc:
        # Old pandas (<1.5) lacks the option; leave default behaviour untouched.
        logger.warning(
            "Could not set pandas Copy-on-Write (MIDAS_PANDAS_COW=%s): %s", raw, exc
        )
    return _PANDAS_COW_ENABLED if _PANDAS_COW_ENABLED is not None else False


#  this function calculates the count of dataframes in the memory
def count_dataframes(label=""):

    df_count = 0
    total_objects = 0
    type_counts = defaultdict(int)

    for obj in gc.get_objects():
        total_objects += 1
        if isinstance(obj, pd.DataFrame):
            df_count += 1
        type_counts[type(obj).__name__] += 1

    print(f"[{label}] Pandas DataFrames alive: {df_count}")

    return df_count

 
def dataframe_report(label=""):
    #Count DataFrames + show their memory
    gc.collect() 

    dfs = []
    total_df_memory = 0

    for obj in gc.get_objects():
        if isinstance(obj, pd.DataFrame):
            try:
                # find memory usage in MB
                memory_bytes = obj.memory_usage(deep=True).sum()
                memory_mb = memory_bytes / (1024 * 1024)

                dfs.append({
                    'shape': obj.shape,
                    'memory_mb': round(memory_mb, 2),
                    'columns': len(obj.columns),
                    'id': id(obj)  # to identify unique objects
                })
                total_df_memory += memory_mb
            except:
                pass  # skip if  error

    # Sort by size desc - lagest on top
    dfs.sort(key=lambda x: x['memory_mb'], reverse=True)

    logger = get_logger(__name__)
    logger.info(f"\n=== DataFrame Memory Report [{label}] ===")
    logger.info(f"Total Pandas DataFrames : {len(dfs)}")
    logger.info(f"Total DataFrame Memory  : {total_df_memory:.2f} MB\n")

    # WHY: the count/total alone cannot tell us WHICH frames make up a spike
    # (e.g. the transient 28 vs steady 16 at the train->MEEA handoff). The
    # per-frame shape + memory was already collected above but never emitted;
    # logging the top entries lets us attribute a peak to its owners (DFSM scope
    # caches vs per-model X_train/X_test vs loky result leftovers) without a
    # debugger. Capped at 15 rows so a large cache cannot flood the log.
    # for _i, _d in enumerate(dfs[:15], start=1):
    #     logger.info(
    #         "  #%02d shape=%s cols=%s mem=%.2fMB id=%s",
    #         _i, _d['shape'], _d['columns'], _d['memory_mb'], _d['id'],
    #     )
    if len(dfs) > 15:
        logger.info("  ... %d more DataFrame(s) not shown", len(dfs) - 15)
    log_pod_memory_usage(label)

def log_pod_memory_usage(label: str = "") -> float:
    """Calculate the current process / POD resident memory (RSS) in MB and log it.
    Reports the live memory footprint of the running process (what a Kubernetes
    pod is billed against), not just pandas objects. Reads the value without
    requiring any extra dependency: it prefers psutil when present, otherwise
    falls back to ``/proc/self/status`` (Linux containers / EKS pods), and
    finally to the stdlib ``resource`` module on other Unix platforms.
    Args:
        label: Optional tag to identify the call site in the log line.
    Returns:
        Resident memory in MB (``0.0`` if it could not be determined).
    Note:
        Safe to call from anywhere in the application and never raises.
    """
    logger = get_logger(__name__)
    pod_memory_mb = 0.0

    try:
        # Preferred: psutil gives accurate cross-platform RSS when installed.
        try:
            import psutil
            _proc = psutil.Process()
            _rss_bytes = _proc.memory_info().rss
            # Include child processes (e.g. loky/joblib training workers) so the
            # reported figure reflects the true pod footprint, not just the parent.
            # Each worker holds its own pickled copy of the training frames, so the
            # parent-only RSS materially under-reports memory during auto-training.
            for _child in _proc.children(recursive=True):
                try:
                    _rss_bytes += _child.memory_info().rss
                except Exception:
                    pass  # child may have exited between enumeration and read
            pod_memory_mb = _rss_bytes / (1024 * 1024)
        except Exception:
            # No psutil: read VmRSS from /proc (works inside Linux containers).
            try:
                with open("/proc/self/status", "r") as status_file:
                    for line in status_file:
                        if line.startswith("VmRSS:"):
                            pod_memory_mb = int(line.split()[1]) / 1024  # kB -> MB
                            break
            except Exception:
                # Last resort for non-Linux Unix: peak RSS via the resource module.
                import resource
                import sys
                ru_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                # ru_maxrss is kB on Linux but bytes on macOS.
                pod_memory_mb = (
                    ru_maxrss / (1024 * 1024)
                    if sys.platform == "darwin"
                    else ru_maxrss / 1024
                )
    except Exception as exc:
        logger.warning(f"Could not read POD memory usage: {exc}")
        return 0.0

    suffix = f" [{label}]" if label else ""
    logger.info(f"POD Memory usage{suffix} : {pod_memory_mb:.2f} MB\n")
    return pod_memory_mb

def validate_csv_file(file_path: str) -> bool:
    """Validate if file is a valid CSV"""
    try:
        df = pd.read_csv(file_path, nrows=5)  # Read first 5 rows to validate
        return True
    except Exception:
        return False

def generate_dataset_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Generate a comprehensive dataset summary"""
    summary = {
        "shape": df.shape,
        "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024**2,
        "dtypes": df.dtypes.to_dict(),
        "missing_values": df.isnull().sum().to_dict(),
        "duplicate_rows": df.duplicated().sum(),
        "numeric_columns": df.select_dtypes(include=['number']).columns.tolist(),
        "categorical_columns": df.select_dtypes(include=['object', 'category']).columns.tolist(),
        "date_columns": df.select_dtypes(include=['datetime64']).columns.tolist()
    }
    
    # Add sample data
    summary["sample_data"] = df.head(3).to_dict('records')
    
    return summary


def _looks_like_date_name(column_name: str) -> bool:
    """
    Heuristic check: does the column name suggest it represents a date?
    Examples: 'order_date', 'DOB', 'joining_dt', 'update_timestamp', etc.
    """
    name = str(column_name).lower()

    explicit_patterns = [
        r"date",
        r"\bdt\b",
        r"\bdob\b",
        r"\bdoj\b",
    ]

    if any(re.search(pattern, name) for pattern in explicit_patterns):
        return True

    fallback_keywords = [
        
    ]

    return any(keyword in name for keyword in fallback_keywords)


def _try_parse_with_formats(value: str, formats: Dict[str, str]) -> Optional[datetime]:
    """
    Try parsing a string with one of the provided datetime formats.
    Returns the first successfully parsed datetime or None.
    """
    value_str = str(value).strip()

    for fmt in formats.keys():
        try:
            parsed = datetime.strptime(value_str, fmt)
            if 1900 <= parsed.year <= 2100:
                return parsed
        except Exception:
            continue

    return None


def identify_date_columns(
    df: pd.DataFrame,
    sample_size: int = 200,
    threshold: float = 0.7,
) -> Dict[str, Dict[str, Any]]:
    """
    Identify date-like columns in a DataFrame using both value patterns and
    column-name heuristics.

    This is intentionally lightweight so it can be reused by multiple APIs
    (analyze-dataset, execute-code column info, etc.) without a big
    performance penalty.

    Returns a dictionary keyed by column name:
        {
          "col_name": {
             "is_date": bool,
             "reason": str,
             "detected_format": Optional[str],
             "confidence": float,
             "has_year": bool,  # True if format includes year component
          },
          ...
        }
    """
    logger = get_logger(__name__)

    # Common 8-digit integer/string formats like 20080211
    eight_digit_formats: Dict[str, str] = {
        "%Y%m%d": "YYYYMMDD (e.g. 20080211)",
        "%m%d%Y": "MMDDYYYY (e.g. 02112008)",
        "%d%m%Y": "DDMMYYYY (e.g. 11022008)",
    }

    # Simple regex -> formats mapping for other common patterns
    # Each entry includes "has_year" flag to indicate if the format contains year information
    pattern_format_map: List[Dict[str, Any]] = [
        {
            "pattern": r"^\d{4}-\d{2}-\d{2}$",
            "formats": {"%Y-%m-%d": "YYYY-MM-DD (ISO date)"},
            "has_year": True,
        },
        {
            # Day-Month abbreviation without year (e.g. 16-Jan, 3-Feb)
            # Year will default to 1900 when parsed, which is fine for detection.
            "pattern": r"^\d{1,2}-[A-Za-z]{3,}$",
            "formats": {
                "%d-%b": "DD-Mon (e.g. 16-Jan)",
                "%d-%B": "DD-Month (e.g. 16-January)",
            },
            "has_year": False,
        },
        {
            # Month abbreviation followed by year (e.g. May-88, Jan-2010)
            "pattern": r"^[A-Za-z]{3,}-\d{1,4}$",
            "formats": {
                "%b-%y": "Mon-YY (e.g. May-88)",
                "%B-%y": "Month-YY (e.g. January-88)",
                "%b-%Y": "Mon-YYYY (e.g. May-1988)",
                "%B-%Y": "Month-YYYY (e.g. January-1988)",
            },
            "has_year": True,
        },
        {
            "pattern": r"^\d{1,2}/\d{1,2}/\d{4}$",
            "formats": {
                "%m/%d/%Y": "MM/DD/YYYY",
                "%d/%m/%Y": "DD/MM/YYYY",
            },
            "has_year": True,
        },
        {
            "pattern": r"^\d{1,2}/\d{1,2}/\d{2}$",
            "formats": {
                "%m/%d/%y": "MM/DD/YY",
                "%d/%m/%y": "DD/MM/YY",
            },
            "has_year": True,
        },
        {
            "pattern": r"^[A-Za-z]+\s+\d{1,2},\s+\d{4}$",
            "formats": {
                "%B %d, %Y": "Month D, YYYY",
                "%b %d, %Y": "Mon D, YYYY",
            },
            "has_year": True,
        },
    ]

    results: Dict[str, Dict[str, Any]] = {}

    for column_name in df.columns:
        series = df[column_name]
        col_name_str = str(column_name)

        # If already a datetime dtype, treat as a date column with full confidence.
        if pd.api.types.is_datetime64_any_dtype(series):
            results[col_name_str] = {
                "is_date": True,
                "reason": "dtype_datetime",
                "detected_format": "pandas_datetime",
                "confidence": 1.0,
                "has_year": True,
            }
            continue

        # Prepare sample values
        sample = series.dropna().head(sample_size)
        if sample.empty:
            results[col_name_str] = {
                "is_date": False,
                "reason": "no_values",
                "detected_format": None,
                "confidence": 0.0,
                "has_year": True,
            }
            continue

        # Convert to string for pattern matching
        sample_str = sample.astype(str).str.strip()
        n = len(sample_str)

        best_confidence = 0.0
        detected_format: Optional[str] = None
        reason: str = "no_pattern"
        has_year: bool = True  # Default to True, set to False for year-less formats

        # Helpers for later decisions
        numeric_only = sample_str.str.fullmatch(r"\d+").all()
        name_looks_like_date = _looks_like_date_name(col_name_str)

        # 1) Check for 8-digit integer/string formats (e.g. 20080211)
        eight_digit_mask = sample_str.str.fullmatch(r"\d{8}")
        if eight_digit_mask.sum() / n >= threshold:
            parsed_count = 0
            for value in sample_str:
                if not re.fullmatch(r"\d{8}", value):
                    continue
                parsed = _try_parse_with_formats(value, eight_digit_formats)
                if parsed is not None:
                    parsed_count += 1
            confidence = parsed_count / n
            if confidence >= threshold:
                # We do not distinguish which specific 8-digit format here;
                # we only need to know that it reliably parses as a date.
                best_confidence = confidence
                detected_format = "8_digit_numeric_date"
                reason = "eight_digit_pattern"
                has_year = True  # 8-digit formats always include year

        # 2) Check for other simple regex-based patterns if not already high confidence
        if detected_format is None or best_confidence < threshold:
            for entry in pattern_format_map:
                pattern = re.compile(entry["pattern"])
                parsed_count = 0
                for value in sample_str:
                    if not pattern.fullmatch(value):
                        continue
                    parsed = _try_parse_with_formats(value, entry["formats"])
                    if parsed is not None:
                        parsed_count += 1
                confidence = parsed_count / n
                if confidence > best_confidence:
                    best_confidence = confidence
                    if confidence >= threshold:
                        # Use a generic description; exact format is less important for flagging
                        detected_format = list(entry["formats"].values())[0]
                        reason = "pattern_match"
                        has_year = entry.get("has_year", True)

        # 3) Fallback: use pandas' flexible parser if we still have low confidence.
        # Skip this for purely numeric columns unless the name clearly looks like a date,
        # to avoid misclassifying simple integer ID/count columns as dates.
        if detected_format is None or best_confidence < threshold:
            if not (numeric_only and not name_looks_like_date):
                try:
                    parsed = pd.to_datetime(sample_str, errors="coerce", infer_datetime_format=True)
                    valid_count = parsed.notna().sum()
                    confidence = valid_count / n
                    if confidence > best_confidence and confidence >= threshold:
                        best_confidence = confidence
                        detected_format = "pandas_inferred"
                        reason = "pandas_inferred"
                        has_year = True  # Pandas inference typically includes year
                except Exception:
                    logger.debug(f"Date inference failed for column '{col_name_str}'", exc_info=True)

        # 4) Name-based heuristic override

        if detected_format is not None and best_confidence >= threshold:
            final_is_date = True
            final_reason = "values_and_name" if name_looks_like_date else reason
        else:
            # No strong value signal - rely on column name if it looks like a date
            if name_looks_like_date:
                final_is_date = True
                final_reason = "name_only"
                best_confidence = max(best_confidence, 0.5)
                has_year = True  # Assume year present when only name-based detection
            else:
                final_is_date = False
                final_reason = reason

        results[col_name_str] = {
            "is_date": final_is_date,
            "reason": final_reason,
            "detected_format": detected_format,
            "confidence": float(best_confidence),
            "has_year": has_year,
        }

    return results

def safe_json_loads(data: str) -> Optional[Dict[str, Any]]:
    """Safely parse JSON string"""
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None

def safe_json_serialize(data: Any) -> Any:
    """Safely serialize data to JSON-compatible format, handling NumPy/Pandas types"""
    try:
        import numpy as np
        import pandas as pd
        import math
        
        if isinstance(data, dict):
            return {key: safe_json_serialize(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [safe_json_serialize(item) for item in data]
        elif isinstance(data, np.integer):
            return int(data)
        elif isinstance(data, np.floating):
            value = float(data)
            return value if math.isfinite(value) else None
        elif isinstance(data, (float, int)):
            return data if (not isinstance(data, float) or math.isfinite(data)) else None
        elif isinstance(data, np.ndarray):
            return [safe_json_serialize(item) for item in data.tolist()]
        elif isinstance(data, pd.Series):
            return [safe_json_serialize(item) for item in data.tolist()]
        elif isinstance(data, pd.DataFrame):
            return [safe_json_serialize(row) for row in data.to_dict('records')]
        elif isinstance(data, (np.bool_, bool)):
            return bool(data)
        elif isinstance(data, (np.str_, str)):
            return str(data)
        elif hasattr(data, 'item'):  # Handle other numpy scalar types
            return safe_json_serialize(data.item())
        else:
            return data
    except Exception:
        # If serialization fails, return a string representation
        return str(data)

def format_error_response(error: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Format error response"""
    response = {
        "error": error,
        "message": message
    }
    if details:
        response["details"] = details
    return response

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    import re
    # Remove or replace unsafe characters
    safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    return safe_filename

def get_file_extension(filename: str) -> str:
    """Get file extension from filename"""
    return Path(filename).suffix.lower()

def validate_target_variable(df: pd.DataFrame, target_variable: str) -> bool:
    """Validate if target variable exists in dataset"""
    return target_variable in df.columns

# ============================================================================
# CORRELATION ANALYSIS HELPERS
# ============================================================================

def correlation_ratio(categories, values) -> float:
    """
    Compute the correlation ratio (eta) between a categorical variable
    and a continuous variable for inter-variable association analysis.

    Parameters
    ----------
    categories : array-like
        Categorical predictor (strings, ints, or mixed).
    values : array-like
        Continuous numeric predictor.

    Returns
    -------
    float
        Correlation ratio in [0, 1]. Returns NaN for empty input,
        0.0 when the numeric variable has zero variance.
    """
    categories = pd.Series(categories).reset_index(drop=True)
    values = pd.Series(values).reset_index(drop=True)

    mask = categories.notna() & values.notna()
    categories = categories[mask].to_numpy()
    values = values[mask].to_numpy(dtype=float)

    if len(values) == 0:
        return float("nan")

    grand_mean = values.mean()
    ss_total = ((values - grand_mean) ** 2).sum()

    if ss_total == 0:
        return 0.0

    ss_between = 0.0
    for cat in np.unique(categories):
        group = values[categories == cat]
        ss_between += len(group) * (group.mean() - grand_mean) ** 2

    return float(np.sqrt(ss_between / ss_total))


def _cramers_v_from_contingency(table: np.ndarray) -> float:
    """Compute bias-corrected Cramér's V from a contingency table."""
    chi2, _, _, _ = chi2_contingency(table)
    n = table.sum()
    if n == 0:
        return 0.0
    r, k = table.shape
    phi2 = chi2 / n
    phi2_corr = max(0.0, phi2 - ((k - 1) * (r - 1)) / (n - 1))
    r_corr = r - ((r - 1) ** 2) / (n - 1)
    k_corr = k - ((k - 1) ** 2) / (n - 1)
    denom = min((k_corr - 1), (r_corr - 1))
    if denom <= 0:
        return 0.0
    return float(np.sqrt(phi2_corr / denom))


def generate_correlation_ratio_analysis_tables(
    dataset_id: str,
    target_variable: str,
    max_category_cardinality: int = 100,
    max_features: int = 200,
    categorical_variables: Optional[List[str]] = None,
    numerical_variables: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Correlation ratio (η) as a single heatmap: categorical / low-cardinality rows (Y),
    numeric columns (X), values η(category → numeric), seaborn-style coolwarm in the UI.

    Legacy multi-section tables (categorical vs target bar, numeric vs binary bar) are no longer returned.
    """
    logger = get_logger(__name__)
    logger.info(f"Generating correlation ratio (η) analysis for dataset={dataset_id}")

    df = dataframe_state_manager.get_dataframe(dataset_id)
    if df is None or target_variable not in df.columns:
        logger.warning("No DataFrame or missing target for correlation ratio analysis")
        return []

    target_series = df[target_variable]
    tgt_nu = int(target_series.nunique(dropna=True))
    is_two_level_numeric_target = (
        pd.api.types.is_numeric_dtype(target_series) and tgt_nu == 2
    )
    is_target_binary = (
        (target_series.dtype == "bool")
        or (
            pd.api.types.is_numeric_dtype(target_series)
            and tgt_nu == 2
            and set(pd.Series(target_series.dropna().unique()).tolist()).issubset({0, 1, 0.0, 1.0, True, False})
        )
    )
    is_target_numeric = pd.api.types.is_numeric_dtype(target_series) or is_target_binary
    strict_non_numeric_target = (
        target_series.dtype == "object"
        or pd.api.types.is_categorical_dtype(target_series)
        or pd.api.types.is_bool_dtype(target_series)
    )

    heatmap_section: Optional[Dict[str, Any]] = None

    def _is_datetime_col(name: str) -> bool:
        return pd.api.types.is_datetime64_any_dtype(df[name])

    def _dedupe_keep_order(values: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for v in values:
            if not v or v in seen:
                continue
            seen.add(v)
            out.append(v)
        return out

    def _prune_empty_eta_axes(
        row_labels: List[str],
        column_labels: List[str],
        matrix: List[List[Any]],
    ) -> tuple[List[str], List[str], List[List[Any]]]:
        if not row_labels or not column_labels or not matrix:
            return [], [], []

        n_rows = len(row_labels)
        n_cols = len(column_labels)

        normalized: List[List[Any]] = []
        for ri in range(n_rows):
            src = matrix[ri] if ri < len(matrix) and isinstance(matrix[ri], list) else []
            normalized.append([src[ci] if ci < len(src) else None for ci in range(n_cols)])

        def _is_missing(val: Any) -> bool:
            if val is None:
                return True
            try:
                return bool(pd.isna(val))
            except Exception:
                return False

        keep_rows = [ri for ri in range(n_rows) if any(not _is_missing(v) for v in normalized[ri])]
        if not keep_rows:
            return [], [], []

        keep_cols = [
            ci
            for ci in range(n_cols)
            if any(not _is_missing(normalized[ri][ci]) for ri in keep_rows)
        ]
        if not keep_cols:
            return [], [], []

        pruned_rows = [row_labels[ri] for ri in keep_rows]
        pruned_cols = [column_labels[ci] for ci in keep_cols]
        pruned_matrix = [
            [normalized[ri][ci] for ci in keep_cols]
            for ri in keep_rows
        ]
        return pruned_rows, pruned_cols, pruned_matrix

    if categorical_variables is not None or numerical_variables is not None:
        requested_cats = _dedupe_keep_order([str(v) for v in (categorical_variables or [])])
        requested_nums = _dedupe_keep_order([str(v) for v in (numerical_variables or [])])

        requested_cats = [
            c for c in requested_cats
            if c in df.columns and c != target_variable and not _is_datetime_col(c)
        ]
        requested_nums = [
            n for n in requested_nums
            if n in df.columns
            and n != target_variable
            and not _is_datetime_col(n)
            and pd.api.types.is_numeric_dtype(df[n])
        ]

        if requested_cats and requested_nums:
            matrix: List[List[Any]] = []
            for c in requested_cats:
                row_cells: List[Any] = []
                nu_c = int(df[c].nunique(dropna=True))
                for n in requested_nums:
                    if nu_c <= 1 or nu_c > max_category_cardinality:
                        row_cells.append(None)
                        continue
                    try:
                        vals_n = pd.to_numeric(df[n], errors="coerce")
                        eta = correlation_ratio(df[c], vals_n)
                        if eta is None or (isinstance(eta, float) and np.isnan(eta)):
                            row_cells.append(None)
                        else:
                            row_cells.append(round(float(eta), 4))
                    except Exception as e:
                        logger.debug(f"Skip explicit η pair ({c}, {n}): {e}")
                        row_cells.append(None)
                matrix.append(row_cells)

            pruned_rows, pruned_cols, pruned_matrix = _prune_empty_eta_axes(
                requested_cats,
                requested_nums,
                matrix,
            )
            if not pruned_rows or not pruned_cols:
                logger.info("Correlation ratio explicit matrix has no non-null η values after pruning")
                return []

            return [{
                "analysis_kind": "correlation_ratio_categorical_numeric_heatmap",
                "title": "Correlation ratio η — categorical (rows) vs numeric (columns)",
                "row_labels": pruned_rows,
                "column_labels": pruned_cols,
                "matrix": pruned_matrix,
                "columns": [],
                "rows": [],
            }]

    def _low_cardinality_numeric_candidates() -> List[str]:
        """Integer/float columns with few distinct values behave like categoricals for η."""
        out: List[str] = []
        for c in df.columns:
            if c == target_variable or _is_datetime_col(c):
                continue
            s = df[c]
            if not pd.api.types.is_numeric_dtype(s):
                continue
            nu = int(s.nunique(dropna=True))
            if nu <= 1 or nu > max_category_cardinality:
                continue
            out.append(c)
        return out[:max_features]

    if is_target_numeric:
        target_vals = pd.to_numeric(target_series, errors="coerce")
        cat_cols_explicit = [
            c
            for c in df.columns
            if c != target_variable
            and not _is_datetime_col(c)
            and (
                df[c].dtype == "object"
                or pd.api.types.is_categorical_dtype(df[c])
                or pd.api.types.is_bool_dtype(df[c])
            )
        ]
        low_card_num = _low_cardinality_numeric_candidates()
        seen = set()
        cat_cols: List[str] = []
        for c in cat_cols_explicit + low_card_num:
            if c not in seen:
                seen.add(c)
                cat_cols.append(c)
        if len(cat_cols) > max_features:
            cat_cols = cat_cols[:max_features]

        # Pairwise η: matrix[cat_row][num_col] = η(cat → num). UI: categorical on Y, numeric on X (coolwarm).
        num_cols_hm = [
            c
            for c in df.select_dtypes(include=["number"]).columns
            if c != target_variable and not _is_datetime_col(c)
        ]
        cat_rows_hm = cat_cols
        mat_by_num_rows: List[List[Any]] = []
        for n in num_cols_hm:
            row_cells: List[Any] = []
            vals_n = pd.to_numeric(df[n], errors="coerce")
            for c in cat_rows_hm:
                if n == c:
                    row_cells.append(None)
                    continue
                try:
                    nu_c = int(df[c].nunique(dropna=True))
                    if nu_c <= 1 or nu_c > max_category_cardinality:
                        row_cells.append(None)
                        continue
                    eta = correlation_ratio(df[c], vals_n)
                    if eta is None or (isinstance(eta, float) and np.isnan(eta)):
                        row_cells.append(None)
                    else:
                        row_cells.append(round(float(eta), 4))
                except Exception as e:
                    logger.debug(f"Skip η pair ({c}, {n}): {e}")
                    row_cells.append(None)
            mat_by_num_rows.append(row_cells)

        if cat_rows_hm and num_cols_hm and any(any(v is not None for v in row) for row in mat_by_num_rows):
            # Transpose: rows = categoricals, columns = numerics
            mat_t = [list(col) for col in zip(*mat_by_num_rows)]
            heatmap_section = {
                "analysis_kind": "correlation_ratio_categorical_numeric_heatmap",
                "title": (
                    "Correlation ratio η — categorical (rows) vs numeric (columns)"
                ),
                "row_labels": list(cat_rows_hm),
                "column_labels": list(num_cols_hm),
                "matrix": mat_t,
                "columns": [],
                "rows": [],
            }

        rows_out: List[Dict[str, Any]] = []
        for col in cat_cols:
            try:
                nu = int(df[col].nunique(dropna=True))
                if nu <= 1 or nu > max_category_cardinality:
                    continue
                cats = df[col]
                eta = correlation_ratio(cats, target_vals)
                if eta is None or (isinstance(eta, float) and np.isnan(eta)):
                    continue
                rows_out.append(
                    {
                        "Categorical variable": col,
                        "Eta (correlation ratio)": round(float(eta), 4),
                        "Categories (n)": int(nu),
                    }
                )
            except Exception as e:
                logger.debug(f"Skip correlation ratio for {col}: {e}")
                continue

        if heatmap_section is None and rows_out:
            ro = sorted(
                rows_out, key=lambda r: r.get("Eta (correlation ratio)") or 0.0, reverse=True
            )[:40]
            # Y = each categorical, X = numeric target (one column)
            heatmap_section = {
                "analysis_kind": "correlation_ratio_categorical_numeric_heatmap",
                "title": (
                    f"Correlation ratio η — categorical predictors (rows) vs numeric target ({target_variable})"
                ),
                "row_labels": [str(r.get("Categorical variable", "")) for r in ro],
                "column_labels": [target_variable],
                "matrix": [[r.get("Eta (correlation ratio)")] for r in ro],
                "columns": [],
                "rows": [],
            }

        # Two-level numeric target (e.g. 0/1): one row (target groups), columns = other numerics
        if is_two_level_numeric_target and heatmap_section is None:
            cats_t = target_series.astype(str)
            num_others = [
                c
                for c in df.select_dtypes(include=["number"]).columns
                if c != target_variable and not _is_datetime_col(c) and c not in seen
            ]
            if len(num_others) > max_features:
                num_others = num_others[:max_features]
            rows_bin: List[Dict[str, Any]] = []
            for col in num_others:
                try:
                    vals = pd.to_numeric(df[col], errors="coerce")
                    eta = correlation_ratio(cats_t, vals)
                    if eta is None or (isinstance(eta, float) and np.isnan(eta)):
                        continue
                    rows_bin.append(
                        {
                            "Numeric variable": col,
                            "Eta (correlation ratio)": round(float(eta), 4),
                            "Target categories (n)": int(tgt_nu),
                        }
                    )
                except Exception as e:
                    logger.debug(f"Skip correlation ratio binary path for {col}: {e}")
                    continue
            if rows_bin:
                rows_bin.sort(key=lambda r: r.get("Eta (correlation ratio)") or 0.0, reverse=True)
                rb = rows_bin[:60]
                heatmap_section = {
                    "analysis_kind": "correlation_ratio_categorical_numeric_heatmap",
                    "title": (
                        f"Correlation ratio η — two-level target ({target_variable}) vs numeric features (columns)"
                    ),
                    "row_labels": [f"{target_variable} (groups)"],
                    "column_labels": [str(r.get("Numeric variable", "")) for r in rb],
                    "matrix": [[r.get("Eta (correlation ratio)") for r in rb]],
                    "columns": [],
                    "rows": [],
                }

    # --- Numeric predictors vs categorical target (object/category/bool only; not 0/1 int) ---
    if strict_non_numeric_target:
        cats = target_series.astype(str)
        nu_t = cats.nunique(dropna=True)
        if nu_t > max_category_cardinality:
            logger.info(
                f"Target cardinality {nu_t} exceeds {max_category_cardinality}; skipping η(numeric vs target)"
            )
        else:
            num_cols = [
                c
                for c in df.select_dtypes(include=["number"]).columns
                if c != target_variable and not _is_datetime_col(c)
            ]
            if len(num_cols) > max_features:
                num_cols = num_cols[:max_features]

            rows_out2: List[Dict[str, Any]] = []
            for col in num_cols:
                try:
                    vals = pd.to_numeric(df[col], errors="coerce")
                    eta = correlation_ratio(cats, vals)
                    if eta is None or (isinstance(eta, float) and np.isnan(eta)):
                        continue
                    rows_out2.append(
                        {
                            "Numeric variable": col,
                            "Eta (correlation ratio)": round(float(eta), 4),
                            "Target categories (n)": int(nu_t),
                        }
                    )
                except Exception as e:
                    logger.debug(f"Skip correlation ratio for {col}: {e}")
                    continue

            if rows_out2:
                rows_out2.sort(key=lambda r: r.get("Eta (correlation ratio)") or 0.0, reverse=True)
                if heatmap_section is None:
                    r2 = rows_out2[:60]
                    # Y = categorical target (single row label), X = numeric features
                    heatmap_section = {
                        "analysis_kind": "correlation_ratio_categorical_numeric_heatmap",
                        "title": (
                            f"Correlation ratio η — categorical target ({target_variable}) vs numeric columns"
                        ),
                        "row_labels": [target_variable],
                        "column_labels": [str(r.get("Numeric variable", "")) for r in r2],
                        "matrix": [[r.get("Eta (correlation ratio)") for r in r2]],
                        "columns": [],
                        "rows": [],
                    }

    if heatmap_section is not None:
        raw_rows = [str(v) for v in (heatmap_section.get("row_labels") or [])]
        raw_cols = [str(v) for v in (heatmap_section.get("column_labels") or [])]
        raw_matrix = heatmap_section.get("matrix") or []
        pruned_rows, pruned_cols, pruned_matrix = _prune_empty_eta_axes(
            raw_rows,
            raw_cols,
            raw_matrix,
        )
        if not pruned_rows or not pruned_cols:
            logger.info("Correlation ratio heatmap became empty after pruning all-null variables")
            return []
        heatmap_section["row_labels"] = pruned_rows
        heatmap_section["column_labels"] = pruned_cols
        heatmap_section["matrix"] = pruned_matrix
        logger.info("Correlation ratio: returning single η heatmap section")
        return [heatmap_section]

    logger.info("Correlation ratio sections generated: 0")
    return []


def generate_correlation_analysis_tables(
    dataset_id: str,
    target_variable: str,
    r_threshold: float = 0.05,
    max_columns: int = None  # Will be auto-determined
) -> List[Dict[str, Any]]:
    """
    Generate correlation analysis sections using VECTORIZED pandas operations.
    Much faster for large datasets (400k+ rows, 1000+ columns).

    Returns list of sections with schemas tailored for UI rendering:
    - correlation_numeric: columns + rows including Pearson, Spearman, and a highlight flag
    - correlation_categorical: columns + rows including Chi-Square statistic and Cramér's V
    """
    logger = get_logger(__name__)
    logger.info(f"Generating Correlation Analysis for dataset: {dataset_id}")

    current_df = dataframe_state_manager.get_dataframe(dataset_id)
    if current_df is None:
        logger.warning("No DataFrame for correlation analysis")
        return []
    df = dataframe_state_manager.get_latest_dataframe_for_planning(current_df, dataset_id)
    if df is None or target_variable not in df.columns:
        logger.warning("No DataFrame or missing target for correlation analysis")
        return []

    # ADAPTIVE: Determine limits based on dataset size
    num_cols = len(df.columns)
    if max_columns is None:
        if num_cols > 1000:
            max_columns = 100
        elif num_cols > 500:
            max_columns = 200
        elif num_cols > 200:
            max_columns = 300
        else:
            max_columns = 500

    target_series = df[target_variable]
    # Check if target is binary (0/1 or True/False) - treat as both numeric and categorical
    is_target_binary = (
        (target_series.dtype == "bool") or 
        (pd.api.types.is_numeric_dtype(target_series) and target_series.nunique() == 2 and set(target_series.dropna().unique()).issubset({0, 1}))
    )
    is_target_numeric = pd.api.types.is_numeric_dtype(target_series) or is_target_binary
    is_target_categorical = not pd.api.types.is_numeric_dtype(target_series) or is_target_binary

    sections: List[Dict[str, Any]] = []

    # VECTORIZED Numeric correlations when target is numeric (including binary 0/1)
    if is_target_numeric:
        numeric_cols = [c for c in df.select_dtypes(include=["number", "bool"]).columns if c != target_variable]
        
        # Limit columns for performance
        if len(numeric_cols) > max_columns:
            logger.warning(f"Dataset has {len(numeric_cols)} numeric columns, limiting to {max_columns} for performance")
            numeric_cols = numeric_cols[:max_columns]
        
        if len(numeric_cols) > 0:
            try:
                # VECTORIZED: Compute all correlations at once using pandas
                df_numeric = df[numeric_cols + [target_variable]].copy()
                # Convert boolean columns to int for correlation
                bool_cols = df_numeric.select_dtypes(include=['bool']).columns
                df_numeric[bool_cols] = df_numeric[bool_cols].astype(int)
                
                # VECTORIZED: Compute Pearson correlations (all at once)
                pearson_corr = df_numeric[numeric_cols].corrwith(df_numeric[target_variable], method='pearson')
                
                # VECTORIZED: Compute Spearman correlations (all at once)
                spearman_corr = df_numeric[numeric_cols].corrwith(df_numeric[target_variable], method='spearman')
                
                # Create results in vectorized way
                numeric_rows = pd.DataFrame({
                    "Variable Name": numeric_cols,
                    "Type of Variable": "Numerical",
                    "Pearson Coefficient": pearson_corr.round(4),
                    "Spearman Coefficient": spearman_corr.round(4)
                }).to_dict('records')
                
                # Replace NaN with None for JSON serialization
                for row in numeric_rows:
                    if pd.isna(row["Pearson Coefficient"]):
                        row["Pearson Coefficient"] = None
                    if pd.isna(row["Spearman Coefficient"]):
                        row["Spearman Coefficient"] = None
                
                if numeric_rows:
                    sections.append({
                        "analysis_kind": "correlation_numeric",
                        "title": f"Correlation (Numerical vs Target, threshold={r_threshold})",
                        "columns": [
                            "Variable Name",
                            "Type of Variable",
                            "Pearson Coefficient",
                            "Spearman Coefficient"
                        ],
                        "rows": numeric_rows,
                    })
                    
            except Exception as e:
                logger.error(f"Vectorized numeric correlation failed: {e}", exc_info=True)
                # Fallback to per-column if vectorized fails
                numeric_rows = []
                for col in numeric_cols[:100]:  # Limit fallback
                    try:
                        s = df[col]
                        if s.dtype == "bool":
                            s = s.astype(int)
                        mask = s.notna() & target_series.notna()
                        s_clean = s[mask]
                        t_clean = target_series[mask]
                        pear = spear = None
                        if len(s_clean) >= 3 and s_clean.nunique() >= 2 and t_clean.nunique() >= 2:
                            pear = pearsonr(s_clean, t_clean).statistic
                            spear = spearmanr(s_clean, t_clean).correlation
                        numeric_rows.append({
                            "Variable Name": col,
                            "Type of Variable": "Numerical",
                            "Pearson Coefficient": None if pear is None else round(float(pear), 4),
                            "Spearman Coefficient": None if spear is None else round(float(spear), 4)
                        })
                    except:
                        continue
                
                if numeric_rows:
                    sections.append({
                        "analysis_kind": "correlation_numeric",
                        "title": f"Correlation (Numerical vs Target, threshold={r_threshold})",
                        "columns": [
                            "Variable Name",
                            "Type of Variable",
                            "Pearson Coefficient",
                            "Spearman Coefficient"
                        ],
                        "rows": numeric_rows,
                    })

    # VECTORIZED Categorical associations when target is categorical or binary (0/1)
    if is_target_categorical:
        cat_cols = [c for c in df.select_dtypes(include=["object", "category", "bool"]).columns if c != target_variable]
        
        # Limit columns for performance
        if len(cat_cols) > max_columns:
            logger.warning(f"Dataset has {len(cat_cols)} categorical columns, limiting to {max_columns} for performance")
            cat_cols = cat_cols[:max_columns]
        
        from concurrent.futures import ThreadPoolExecutor as _TPE
        from app.core.config import settings as _settings
        _cat_workers = min(getattr(_settings, "INSIGHTS_MAX_WORKERS", 4), max(1, len(cat_cols)))

        def _compute_cat_assoc(col):
            try:
                contingency = pd.crosstab(df[col], df[target_variable]).values
                if contingency.size and contingency.shape[0] > 1 and contingency.shape[1] > 1:
                    chi2, _, _, _ = chi2_contingency(contingency)
                    chi_stat = round(float(chi2), 4)
                    cv = round(_cramers_v_from_contingency(contingency), 4)
                else:
                    chi_stat = None
                    cv = None
            except Exception as e:
                logger.warning(f"Categorical association failed for {col}: {e}")
                chi_stat = None
                cv = None
            return {
                "Variable Name": col,
                "Type of Variable": "Categorical",
                "Chi-Square test of Independence": chi_stat,
                "Cramér's V": cv,
            }

        with _TPE(max_workers=_cat_workers) as pool:
            categorical_rows = list(pool.map(_compute_cat_assoc, cat_cols))

        if categorical_rows:
            sections.append({
                "analysis_kind": "correlation_categorical",
                "title": "Association (Categorical vs Target)",
                "columns": [
                    "Variable Name",
                    "Type of Variable",
                    "Chi-Square test of Independence",
                    "Cramér's V"
                ],
                "rows": categorical_rows,
            })

    logger.info(f"Correlation Analysis generated sections: {len(sections)}")
    return sections

# ============================================================================
# CORRELATION MATRIX ANALYSIS HELPERS
# ============================================================================

def generate_correlation_matrix_analysis(df: pd.DataFrame, target_variable: str, 
                                       high_corr_threshold: float = 0.8,
                                       moderate_corr_threshold: float = 0.5) -> Dict[str, Any]:
    """
    Generate comprehensive correlation matrix analysis using VECTORIZED operations.
    
    Args:
        df: DataFrame containing the data
        target_variable: Name of the target variable
        high_corr_threshold: Threshold for high correlation (default 0.8)
        moderate_corr_threshold: Threshold for moderate correlation (default 0.5)
    
    Returns:
        Dictionary containing correlation matrix analysis results
    """
    logger = get_logger(__name__)
    logger.info(f"Generating correlation matrix analysis for target: {target_variable}")
    
    try:
        # Get numeric columns only
        numeric_cols = [col for col in df.select_dtypes(include=['number']).columns if col != target_variable]
        
        if len(numeric_cols) < 2:
            logger.warning("Need at least 2 numeric variables for correlation matrix analysis")
            return {"error": "Insufficient numeric variables for correlation matrix analysis"}
        
        # ADAPTIVE: Determine limits based on dataset size
        num_total_cols = len(df.columns)
        if num_total_cols > 1000:
            max_columns = 50
        elif num_total_cols > 500:
            max_columns = 100
        elif num_total_cols > 200:
            max_columns = 150
        else:
            max_columns = 200
        
        # Limit columns for performance
        if len(numeric_cols) > max_columns:
            logger.warning(f"Dataset has {len(numeric_cols)} numeric columns, limiting to {max_columns} for correlation matrix")
            numeric_cols = numeric_cols[:max_columns]
        
        # Sample rows if dataset is very large
        if len(df) > 50000:
            logger.info(f"Sampling 50k rows from {len(df)} for correlation matrix")
            df_sample = df.sample(n=50000, random_state=42)
        else:
            df_sample = df
        
        # VECTORIZED: Calculate correlation matrix (already vectorized in pandas)
        corr_matrix = df_sample[numeric_cols].corr()
        
        # VECTORIZED: Find high correlations using numpy operations
        # Create mask for upper triangle (avoid duplicates and diagonal)
        upper_triangle_mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
        abs_corr_matrix = corr_matrix.abs()
        
        # Find high correlations (vectorized)
        high_corr_mask = (abs_corr_matrix >= high_corr_threshold) & upper_triangle_mask
        moderate_corr_mask = (abs_corr_matrix >= moderate_corr_threshold) & (abs_corr_matrix < high_corr_threshold) & upper_triangle_mask
        
        # Extract high correlation pairs (vectorized)
        high_corr_pairs = np.argwhere(high_corr_mask.values)
        moderate_corr_pairs = np.argwhere(moderate_corr_mask.values)
        
        # Convert to list of dicts
        high_correlations = []
        for i, j in high_corr_pairs:
            var1, var2 = numeric_cols[i], numeric_cols[j]
            corr_value = corr_matrix.iloc[i, j]
            high_correlations.append({
                "variable_1": var1,
                "variable_2": var2,
                "correlation": round(float(corr_value), 4),
                "strength": "very_high" if abs(corr_value) >= 0.9 else "high",
                "direction": "positive" if corr_value > 0 else "negative"
            })
        
        moderate_correlations = []
        for i, j in moderate_corr_pairs:
            var1, var2 = numeric_cols[i], numeric_cols[j]
            corr_value = corr_matrix.iloc[i, j]
            moderate_correlations.append({
                "variable_1": var1,
                "variable_2": var2,
                "correlation": round(float(corr_value), 4),
                "strength": "moderate",
                "direction": "positive" if corr_value > 0 else "negative"
            })
        
        # VECTORIZED: Target correlations
        target_correlations = []
        if target_variable in df_sample.columns and pd.api.types.is_numeric_dtype(df_sample[target_variable]):
            # Vectorized: compute all correlations with target at once
            target_corr = df_sample[numeric_cols].corrwith(df_sample[target_variable])
            target_correlations = [
                {
                    "variable": col,
                    "correlation_with_target": round(float(corr_value), 4),
                    "strength": "very_high" if abs(corr_value) >= 0.8 else 
                               "high" if abs(corr_value) >= 0.6 else
                               "moderate" if abs(corr_value) >= 0.4 else "weak"
                }
                for col, corr_value in target_corr.items()
                if not pd.isna(corr_value)
            ]
            # Sort by absolute value
            target_correlations.sort(key=lambda x: abs(x["correlation_with_target"]), reverse=True)
        
        # VECTORIZED: Multicollinearity groups using graph approach
        # Build adjacency matrix from high correlations
        adj_matrix = (abs_corr_matrix >= high_corr_threshold).astype(int)
        # Ensure we work on a writable copy before modifying the diagonal
        adj_matrix_values = (
            adj_matrix.to_numpy(copy=True)
            if isinstance(adj_matrix, pd.DataFrame)
            else np.array(adj_matrix, copy=True)
        )
        np.fill_diagonal(adj_matrix_values, 0)  # Remove self-connections
        if isinstance(adj_matrix, pd.DataFrame):
            adj_matrix = pd.DataFrame(
                adj_matrix_values,
                index=adj_matrix.index,
                columns=adj_matrix.columns,
            )
        else:
            adj_matrix = adj_matrix_values
        
        # Find connected components (multicollinearity groups)
        multicollinearity_groups = []
        try:
            from scipy.sparse.csgraph import connected_components
            # Convert DataFrame to numpy array for connected_components
            adj_matrix_array = adj_matrix.values if isinstance(adj_matrix, pd.DataFrame) else adj_matrix
            n_components, labels = connected_components(adj_matrix_array, directed=False)
            
            processed_vars = set()
            for comp_id in range(n_components):
                group_vars = [numeric_cols[i] for i in range(len(numeric_cols)) if labels[i] == comp_id]
                if len(group_vars) > 2 and not any(v in processed_vars for v in group_vars):
                    multicollinearity_groups.append({
                        "variables": group_vars,
                        "size": len(group_vars),
                        "description": f"Group of {len(group_vars)} highly correlated variables"
                    })
                    processed_vars.update(group_vars)
        except ImportError:
            # Fallback if scipy.sparse not available
            logger.warning("scipy.sparse not available, using simple multicollinearity detection")
            processed_vars = set()
            for corr in high_correlations:
                var1, var2 = corr["variable_1"], corr["variable_2"]
                if var1 not in processed_vars and var2 not in processed_vars:
                    group = {var1, var2}
                    for other_corr in high_correlations:
                        other_var1, other_var2 = other_corr["variable_1"], other_corr["variable_2"]
                        if (other_var1 in group or other_var2 in group) and other_var1 != var1 and other_var2 != var2:
                            group.add(other_var1)
                            group.add(other_var2)
                    
                    if len(group) > 2:
                        multicollinearity_groups.append({
                            "variables": list(group),
                            "size": len(group),
                            "description": f"Group of {len(group)} highly correlated variables"
                        })
                        processed_vars.update(group)
        
        # VECTORIZED: Redundant variables (count high correlations per variable)
        variable_correlation_counts = adj_matrix.sum(axis=0).to_dict()
        redundant_variables = [
            {"variable": numeric_cols[i], "high_correlation_count": int(count)}
            for i, count in enumerate(variable_correlation_counts.values())
            if count >= 3
        ]
        redundant_variables.sort(key=lambda x: x["high_correlation_count"], reverse=True)
        
        # Generate summary statistics
        total_variables = len(numeric_cols)
        high_corr_pairs = len(high_correlations)
        moderate_corr_pairs = len(moderate_correlations)
        multicollinearity_groups_count = len(multicollinearity_groups)
        
        # Generate actionable recommendations
        recommendations = []
        
        if high_corr_pairs > 0:
            recommendations.append({
                "type": "multicollinearity_concern",
                "priority": "high",
                "description": f"Found {high_corr_pairs} pairs of variables with very high correlations (|r| ≥ {high_corr_threshold})",
                "action": "Consider removing one variable from each highly correlated pair or using dimensionality reduction techniques"
            })
        
        if multicollinearity_groups_count > 0:
            recommendations.append({
                "type": "multicollinearity_groups",
                "priority": "high", 
                "description": f"Identified {multicollinearity_groups_count} groups of variables with multicollinearity issues",
                "action": "Use Principal Component Analysis (PCA) or select representative variables from each group"
            })
        
        if len(redundant_variables) > 0:
            recommendations.append({
                "type": "redundant_variables",
                "priority": "medium",
                "description": f"Found {len(redundant_variables)} variables that are highly correlated with multiple other variables",
                "action": "Consider removing redundant variables to improve model interpretability and reduce overfitting risk"
            })
        
        if len(target_correlations) > 0:
            strong_target_correlations = [c for c in target_correlations if c["strength"] in ["very_high", "high"]]
            if len(strong_target_correlations) > 0:
                recommendations.append({
                    "type": "strong_predictors",
                    "priority": "low",
                    "description": f"Identified {len(strong_target_correlations)} variables with strong correlations to target",
                    "action": "These variables are likely to be important predictors in your model"
                })
        
        # Generate correlation matrix summary
        correlation_summary = {
            "total_numeric_variables": total_variables,
            "high_correlation_pairs": high_corr_pairs,
            "moderate_correlation_pairs": moderate_corr_pairs,
            "multicollinearity_groups": multicollinearity_groups_count,
            "redundant_variables": len(redundant_variables),
            "correlation_matrix_shape": corr_matrix.shape
        }
        
        # Generate correlation matrix table for display
        correlation_matrix_table = generate_correlation_matrix_table(corr_matrix, numeric_cols)
        
        return {
            "correlation_summary": correlation_summary,
            "high_correlations": high_correlations,
            "moderate_correlations": moderate_correlations,
            "multicollinearity_groups": multicollinearity_groups,
            "target_correlations": target_correlations,
            "redundant_variables": redundant_variables,
            "recommendations": recommendations,
            "correlation_matrix": corr_matrix.to_dict(),
            "correlation_matrix_table": correlation_matrix_table,
            "analysis_metadata": {
                "high_corr_threshold": high_corr_threshold,
                "moderate_corr_threshold": moderate_corr_threshold,
                "analysis_timestamp": pd.Timestamp.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Correlation matrix analysis failed: {str(e)}")
        return {"error": f"Correlation matrix analysis failed: {str(e)}"}

def generate_correlation_matrix_table(corr_matrix: pd.DataFrame, variable_names: List[str]) -> Dict[str, Any]:
    """
    Generate correlation matrix tables in the exact format shown in the image.
    
    Args:
        corr_matrix: Pandas correlation matrix
        variable_names: List of variable names
    
    Returns:
        Dictionary containing both tables for frontend display
    """
    logger = get_logger(__name__)
    try:
        # Limit to reasonable number of variables for display (max 20)
        max_vars = 20
        if len(variable_names) > max_vars:
            variable_names = variable_names[:max_vars]
            corr_matrix = corr_matrix.loc[variable_names, variable_names]
        
        # Create main correlation matrix table (the big square table)
        columns = ["Variable"] + variable_names
        rows = []
        
        for var in variable_names:
            row = {"Variable": var}
            for other_var in variable_names:
                if var == other_var:
                    row[other_var] = 1.00  # Perfect correlation with itself
                else:
                    corr_value = corr_matrix.loc[var, other_var]
                    row[other_var] = round(float(corr_value), 2) if not pd.isna(corr_value) else 0.00
            rows.append(row)
        
        # Create correlated variables count table (the small summary table)
        correlation_counts = []
        for var in variable_names:
            # Count variables with correlation > 0.5 (excluding self-correlation)
            high_corr_vars = []
            for other_var in variable_names:
                if var != other_var:
                    corr_value = corr_matrix.loc[var, other_var]
                    if not pd.isna(corr_value) and abs(corr_value) > 0.5:
                        high_corr_vars.append(other_var)
            
            if high_corr_vars:
                correlation_counts.append({
                    "Variable": var,
                    "Correlated Variables": ", ".join(high_corr_vars),
                    "Count": len(high_corr_vars)
                })
        
        # Return both tables
        return {
            "correlation_matrix": {
                "columns": columns,
                "rows": rows,
                "title": "Correlation Matrix"
            },
            "correlation_summary": {
                "columns": ["Variable", "Correlated Variables", "Count"],
                "rows": correlation_counts,
                "title": "Correlated Variables Count"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to generate correlation matrix table: {str(e)}")
        return {"error": f"Failed to generate correlation matrix table: {str(e)}"}

# ============================================================================
# VIF (VARIATION INFLATION FACTOR) ANALYSIS HELPERS
# ============================================================================

def calculate_vif(df: pd.DataFrame, target_variable: str, max_columns: int = None) -> List[Dict[str, Any]]:
    """
    Calculate VIF using VECTORIZED matrix operations.
    Much faster than looping through each column individually.
    
    Uses correlation matrix approach for speed with large datasets.
    
    Args:
        df: DataFrame containing the data
        target_variable: Name of the target variable (excluded from VIF calculation)
        max_columns: Maximum number of columns to process (auto-determined if None)
    
    Returns:
        List of dictionaries with VIF results for each variable
    """
    logger = get_logger(__name__)
    
    try:
        if max_columns is not None:
            try:
                max_columns = int(max_columns)
                if max_columns < 1:
                    max_columns = None
            except (TypeError, ValueError):
                max_columns = None

        # Get only numeric columns, excluding target variable
        numeric_cols = [col for col in df.select_dtypes(include=['number']).columns if col != target_variable]
        
        if len(numeric_cols) < 2:
            logger.warning("Need at least 2 numeric variables for VIF calculation")
            return []
        
        # ADAPTIVE: Determine limits
        if max_columns is None:
            num_total_cols = len(df.columns)
            if num_total_cols > 1000:
                max_columns = 50
            elif num_total_cols > 500:
                max_columns = 100
            elif num_total_cols > 200:
                max_columns = 150
            else:
                max_columns = 200
        
        # Limit columns for performance
        if len(numeric_cols) > max_columns:
            logger.warning(f"Dataset has {len(numeric_cols)} numeric columns, limiting to {max_columns} for VIF")
            numeric_cols = numeric_cols[:max_columns]
        
        # Remove infinite values first
        df_clean = df[numeric_cols].replace([np.inf, -np.inf], np.nan)
        
        # VECTORIZED: Find valid columns using vectorized operations
        non_null_counts = df_clean.notna().sum()
        min_valid_rows = min(100, len(df) * 0.1)
        valid_cols = non_null_counts[non_null_counts >= min_valid_rows].index.tolist()
        
        if len(valid_cols) < 2:
            logger.warning(f"Not enough valid numeric columns for VIF calculation: {len(valid_cols)} < 2")
            return []
        
        # For very sparse data, use pairwise correlation approximation
        df_subset = df_clean[valid_cols]
        
        # Sample rows if dataset is too large for correlation matrix
        if len(df_subset) > 100000:
            logger.info(f"Sampling 100k rows from {len(df_subset)} for VIF calculation")
            df_subset = df_subset.sample(n=100000, random_state=42)
        
        # VECTORIZED: Compute correlation matrix once
        corr_matrix = df_subset.corr()
        
        # VECTORIZED: Calculate VIF from correlation matrix
        vif_results = []
        
        for col in valid_cols:
            try:
                # Get correlations with all other columns (vectorized)
                other_cols = [c for c in valid_cols if c != col]
                if not other_cols:
                    vif_value = 1.0
                else:
                    # Get all correlations with other columns
                    corr_with_others = corr_matrix.loc[col, other_cols].abs()
                    
                    # Use maximum correlation as proxy for multicollinearity
                    # This is faster than fitting regression for each variable
                    max_corr = corr_with_others.max()
                    
                    # Approximate VIF: if max correlation is r, VIF ≈ 1/(1-r²)
                    if pd.isna(max_corr) or max_corr >= 0.999:
                        vif_value = float('inf')
                    else:
                        vif_value = 1 / (1 - max_corr**2)
                
                # Determine interpretation based on thresholds
                if vif_value == float('inf'):
                    interpretation = "🚨 Perfect multicollinearity"
                elif vif_value > 10:
                    interpretation = "🚨 Severe multicollinearity"
                elif vif_value >= 5:
                    interpretation = "⚠️ Potential multicollinearity"
                else:
                    interpretation = "✅ Acceptable"
                
                vif_results.append({
                    "Variable": col,
                    "VIF": round(vif_value, 2) if vif_value != float('inf') else "∞",
                    "Interpretation": interpretation
                })
                
            except Exception as e:
                logger.warning(f"VIF calculation failed for {col}: {e}")
                vif_results.append({
                    "Variable": col,
                    "VIF": "Error",
                    "Interpretation": "❌ Calculation failed"
                })
        
        # Sort by VIF value (descending, with errors at the end)
        def sort_key(x):
            vif = x["VIF"]
            if vif == "Error":
                return -1
            elif vif == "∞":
                return float('inf')
            else:
                return float(vif)
        
        vif_results.sort(key=sort_key, reverse=True)
        
        logger.info(f"VIF analysis completed for {len(vif_results)} variables (vectorized)")
        return vif_results
        
    except Exception as e:
        logger.error(f"VIF analysis failed: {e}", exc_info=True)
        return []

def generate_vif_analysis_tables(
    dataset_id: str,
    target_variable: str,
) -> List[Dict[str, Any]]:
    """
    Generate VIF analysis tables for the dataset.
    
    Args:
        dataset_id: ID of the dataset
        target_variable: Name of the target variable
    
    Returns:
        List of sections with VIF analysis results
    """
    logger = get_logger(__name__)
    logger.info(f"Generating VIF Analysis for dataset: {dataset_id}")
    
    current_df = dataframe_state_manager.get_dataframe(dataset_id)
    if current_df is None:
        logger.warning("No DataFrame for VIF analysis")
        return []
    df = dataframe_state_manager.get_latest_dataframe_for_planning(current_df, dataset_id)
    if df is None or target_variable not in df.columns:
        logger.warning("No DataFrame or missing target for VIF analysis")
        return []
    
    # Calculate VIF for all numeric variables
    vif_results = calculate_vif(df, target_variable)
    
    if not vif_results:
        logger.warning("No VIF results generated, creating fallback analysis")
        # Create a fallback VIF analysis with basic correlation
        try:
            # Get numeric columns
            numeric_cols = [col for col in df.select_dtypes(include=['number']).columns 
                           if col != target_variable]
            
            if len(numeric_cols) >= 2:
                # Calculate correlation matrix
                corr_matrix = df[numeric_cols].corr()
                
                # Create simple VIF-like analysis using correlation
                fallback_results = []
                for col in numeric_cols[:10]:  # Limit to first 10 columns
                    try:
                        # Calculate average correlation with other variables
                        other_cols = [c for c in numeric_cols if c != col]
                        if other_cols:
                            avg_corr = corr_matrix.loc[col, other_cols].abs().mean()
                            # Convert to VIF-like score
                            vif_like = 1 / (1 - avg_corr) if avg_corr < 0.99 else 10.0
                            
                            if vif_like > 10:
                                interpretation = "🚨 High correlation"
                            elif vif_like > 5:
                                interpretation = "⚠️ Moderate correlation"
                            else:
                                interpretation = "✅ Low correlation"
                            
                            fallback_results.append({
                                "Variable": col,
                                "VIF": round(vif_like, 2),
                                "Interpretation": interpretation
                            })
                    except:
                        continue
                
                if fallback_results:
                    logger.info(f"Created fallback VIF analysis with {len(fallback_results)} variables")
                    return [{
                        "analysis_kind": "vif_analysis",
                        "title": "Variance Inflation Factor (VIF) Analysis (Fallback)",
                        "columns": ["Variable", "VIF", "Interpretation"],
                        "rows": fallback_results,
                        "thresholds": {
                            "acceptable": "VIF < 5 → Acceptable",
                            "potential": "VIF 5-10 → Potential multicollinearity", 
                            "severe": "VIF > 10 → Serious multicollinearity"
                        }
                    }]
        except Exception as e:
            logger.warning(f"Fallback VIF analysis also failed: {e}")
        
        return []
    
    # Create VIF analysis section
    vif_section = {
        "analysis_kind": "vif_analysis",
        "title": "Variation Inflation Factor (VIF) Analysis",
        "columns": ["Variable", "VIF", "Interpretation"],
        "rows": vif_results,
        "thresholds": {
            "acceptable": "VIF < 5 → Acceptable",
            "potential": "VIF 5-10 → Potential multicollinearity", 
            "severe": "VIF > 10 → Serious multicollinearity"
        }
    }
    
    logger.info(f"VIF Analysis generated {len(vif_results)} results")
    return [vif_section]

# ============================================================================
# BIVARIATE ANALYSIS HELPER FUNCTIONS
# ============================================================================


def parse_coarse_bins_edges(spec: str):
    """
    Parse a coarse binning spec like '0-20, 20-40, 40+' into strictly increasing
    edges suitable for pd.cut (last edge may be +inf).
    """
    import numpy as np

    spec = (spec or "").strip()
    if not spec:
        raise ValueError("Coarse binning spec is empty")

    parts = [p.strip() for p in spec.split(",") if p.strip()]
    if not parts:
        raise ValueError("Coarse binning spec has no segments")

    edges: list = []
    for p in parts:
        if p.endswith("+"):
            low = float(p[:-1].strip())
            edges.append(low)
            edges.append(np.inf)
        else:
            m = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*-\s*([+-]?\d+(?:\.\d+)?)$", p)
            if not m:
                raise ValueError(f"Invalid bin segment '{p}'. Use e.g. 0-20, 20-40, 40+")
            edges.append(float(m.group(1)))
            edges.append(float(m.group(2)))

    edges = sorted(set(edges))
    if len(edges) < 2:
        raise ValueError("Need at least two distinct bin edges")
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1] and not (edges[i] == np.inf and edges[i - 1] < np.inf):
            raise ValueError("Bin edges must be strictly increasing")
    return edges


def parse_category_groups_spec(spec: str):
    """
    Parse 'AA+BB, CC+DD' into [('AA+BB', ['AA','BB']), ('CC+DD', ['CC','DD'])].
    Labels are joined with '+' for display.
    """
    spec = (spec or "").strip()
    if not spec:
        raise ValueError("Category grouping spec is empty")

    groups = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        members = [m.strip() for m in chunk.split("+") if m.strip()]
        if len(members) < 2:
            raise ValueError(
                f"Each group must merge at least two categories (use +). Invalid: '{chunk}'"
            )
        label = "+".join(members)
        groups.append((label, members))
    if not groups:
        raise ValueError("No category groups parsed")
    return groups


def _bin_left_edge_from_interval_str(bin_range: str) -> float:
    """Lower bound of a bin label for sorting rows low → high."""
    s = str(bin_range).replace("(", "").replace("]", "").replace(" ", "")
    nums = re.findall(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", s)
    if not nums:
        return 0.0
    return float(nums[0])


def _format_scalar_bin_edge(x: float) -> str:
    """Compact string for one bin edge (matches coarse-bin input style)."""
    if x is None:
        return "?"
    xf = float(x)
    if np.isnan(xf):
        return "?"
    if np.isposinf(xf):
        return "inf"
    if abs(xf - round(xf)) < 1e-6 and abs(xf) < 1e15:
        return str(int(round(xf)))
    s = f"{xf:.8g}"
    if "e" in s.lower():
        return s
    s = s.rstrip("0").rstrip(".")
    return s if s else "0"


def format_numeric_bin_range_label(interval) -> str:
    """
    Human-readable numeric bounds for tables and charts, e.g.:
    0 – 20, 20 – 40, 40+ (open upper). Aligns with coarse binning syntax 0-20, 20-40, 40+.
    """
    if isinstance(interval, pd.Interval):
        left, right = float(interval.left), float(interval.right)
        if np.isposinf(right) or right >= np.finfo(np.float64).max / 4:
            return f"{_format_scalar_bin_edge(left)}+"
        return f"{_format_scalar_bin_edge(left)} – {_format_scalar_bin_edge(right)}"

    s = str(interval).strip()
    nums = re.findall(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", s.replace("∞", ""))
    if len(nums) >= 2:
        lo, hi = float(nums[0]), float(nums[1])
        if np.isposinf(hi) or hi >= np.finfo(np.float64).max / 4:
            return f"{_format_scalar_bin_edge(lo)}+"
        return f"{_format_scalar_bin_edge(lo)} – {_format_scalar_bin_edge(hi)}"
    if len(nums) == 1:
        return f"{_format_scalar_bin_edge(float(nums[0]))}+"
    return s


def _sort_numerical_bins_by_range(analysis_data: list) -> None:
    """Sort bin rows from low to high by numeric lower bound."""
    if not analysis_data:
        return
    analysis_data.sort(
        key=lambda r: _bin_left_edge_from_interval_str(str(r.get("Bin_Range_Decile", "")))
    )


def _apply_category_group_map(series: pd.Series, groups):
    """Map raw category values to merged labels; unlisted values keep str(value)."""

    member_to_label = {}
    for label, members in groups:
        for m in members:
            key = str(m).strip()
            if key in member_to_label and member_to_label[key] != label:
                raise ValueError(f"Category '{m}' appears in more than one group")
            member_to_label[key] = label

    def _map_one(v):
        s = str(v).strip() if v is not None and not (isinstance(v, float) and pd.isna(v)) else ""
        if s in member_to_label:
            return member_to_label[s]
        return v

    return series.map(_map_one)


def analyze_categorical_vs_target(
    df,
    target_variable,
    feature_variable,
    dataset_summary,
    top_categories,
    dataset_id,
    category_groups_spec=None,
):
    """Analyze categorical variable against target"""
    try:
        df_processed = df.copy()
        merged_labels = None

        if category_groups_spec:
            groups = parse_category_groups_spec(category_groups_spec)
            df_processed[feature_variable] = _apply_category_group_map(
                df_processed[feature_variable], groups
            )
            # Only keep rows that belong to explicitly defined merged groups; hide all other categories
            merged_labels = [label for label, _ in groups]
            df_processed = df_processed[df_processed[feature_variable].isin(merged_labels)]
            if df_processed.empty:
                raise ValueError(
                    "No rows remain after category grouping. Check that category names match "
                    "the data (including spelling) and that each group lists at least two values."
                )
            is_high_cardinality = False
            cardinality = df_processed[feature_variable].nunique()
        else:
            # Handle high cardinality (default path only)
            cardinality = df_processed[feature_variable].nunique()
            is_high_cardinality = cardinality > top_categories

            if is_high_cardinality:
                # Keep top N categories, bucket rest into "Others".
                # Vectorised via where + isin: ~50x faster than Series.apply over
                # 4M rows. See backend/docs/midas-4m-row-performance-analysis 1.md.
                _col = df_processed[feature_variable]
                top_cats_set = set(
                    _col.value_counts().head(top_categories).index
                )
                df_processed[feature_variable] = _col.where(
                    _col.isin(top_cats_set), other="Others"
                )
        
        # Calculate metrics
        analysis_data = calculate_categorical_metrics(df_processed, feature_variable, target_variable)

        if merged_labels is not None:
            order = {lab: i for i, lab in enumerate(merged_labels)}
            analysis_data["analysis_data"].sort(
                key=lambda r: order.get(str(r["Category"]), 999)
            )

        # Generate insights
        insights = generate_categorical_insights(analysis_data, is_high_cardinality, feature_variable)
        
        out = {
            "analysis_type": "categorical",
            "target_variable": target_variable,
            "feature_variable": feature_variable,
            "insights": insights,
            "visualization_data": prepare_categorical_visualization(analysis_data),
            "analysis_result": analysis_data,
            "is_high_cardinality": is_high_cardinality,
            "cardinality": cardinality,
        }
        if category_groups_spec:
            out["category_groups_spec"] = category_groups_spec.strip()
        return out

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in categorical analysis for {feature_variable}: {str(e)}")
        raise

def _numerical_metrics_from_binned_column(df_binned, feature_variable, target_variable, bin_col_name: str, binning_method: str, bins: int):
    """Shared metrics table from an already-binned dataframe."""
    grouped = df_binned.groupby(bin_col_name)[target_variable].agg(["count", "sum", "mean"]).reset_index()
    grouped.columns = [bin_col_name, "Total", "Defaults", "Default_Rate"]

    analysis_data = []
    for _, row in grouped.iterrows():
        iv = row[bin_col_name]
        bin_range = format_numeric_bin_range_label(iv)

        analysis_data.append(
            {
                "Variable": feature_variable,
                "Bin_Range_Decile": bin_range,
                "Default_Rate": round(row["Default_Rate"], 2),
                "Total": int(row["Total"]),
                "Defaults": int(row["Defaults"]),
            }
        )

    _sort_numerical_bins_by_range(analysis_data)

    correlation = df_binned[feature_variable].corr(df_binned[target_variable])

    return {
        "analysis_data": analysis_data,
        "correlation": correlation,
        "summary_stats": {
            "total_bins": len(grouped),
            "avg_default_rate": grouped["Default_Rate"].mean(),
            "max_default_rate": grouped["Default_Rate"].max(),
            "min_default_rate": grouped["Default_Rate"].min(),
        },
    }


def analyze_numerical_vs_target(
    df,
    target_variable,
    feature_variable,
    dataset_summary,
    binning_method,
    bins,
    dataset_id,
    coarse_bins_spec=None,
):
    """Analyze numerical variable against target"""
    try:
        if coarse_bins_spec:
            edges = parse_coarse_bins_edges(coarse_bins_spec)
            df_binned = df.copy()
            bin_col = f"{feature_variable}_binned"
            df_binned[bin_col] = pd.cut(
                df[feature_variable], bins=edges, include_lowest=True
            )
            df_binned = df_binned.dropna(subset=[bin_col])
            if df_binned.empty:
                raise ValueError(
                    "No observations fall into the specified bins for this variable."
                )

            analysis_data = _numerical_metrics_from_binned_column(
                df_binned, feature_variable, target_variable, bin_col, "custom", len(edges) - 1
            )

            insights = generate_numerical_insights(analysis_data, "custom", feature_variable)

            return {
                "analysis_type": "numerical",
                "target_variable": target_variable,
                "feature_variable": feature_variable,
                "insights": insights,
                "visualization_data": prepare_numerical_visualization(analysis_data),
                "analysis_result": analysis_data,
                "binning_method": "custom",
                "bins": len(edges) - 1,
                "coarse_bins_spec": coarse_bins_spec.strip(),
            }

        # Apply binning
        df_binned = apply_binning(df, feature_variable, binning_method, bins)

        # Calculate metrics
        analysis_data = calculate_numerical_metrics(
            df_binned, feature_variable, target_variable, binning_method, bins
        )

        # Generate insights
        insights = generate_numerical_insights(analysis_data, binning_method, feature_variable)

        return {
            "analysis_type": "numerical",
            "target_variable": target_variable,
            "feature_variable": feature_variable,
            "insights": insights,
            "visualization_data": prepare_numerical_visualization(analysis_data),
            "analysis_result": analysis_data,
            "binning_method": binning_method,
            "bins": bins,
        }

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in numerical analysis for {feature_variable}: {str(e)}")
        raise

def calculate_categorical_metrics(df, feature_variable, target_variable):
    """Calculate categorical analysis metrics in the specified format"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Group by feature variable and calculate target rates
        grouped = df.groupby(feature_variable)[target_variable].agg(['count', 'sum', 'mean']).reset_index()
        grouped.columns = [feature_variable, 'Total', 'Defaults', 'Default_Rate']
        
        # Sort by default rate (descending)
        grouped = grouped.sort_values('Default_Rate', ascending=False)
        
        # Create the analysis data in the exact format requested
        analysis_data = []
        for _, row in grouped.iterrows():
            raw_category = row[feature_variable]
            category_str = str(raw_category)
            
            # Debug: Log the conversion for first few items
            if len(analysis_data) < 5:
                logger.info(f"Converting category: {raw_category} (type: {type(raw_category)}) -> '{category_str}'")
            
            analysis_data.append({
                'Variable': feature_variable,
                'Category': category_str,
                'Raw_Value': raw_category,  # Add raw value for debugging
                'Default_Rate': round(row['Default_Rate'], 2),
                'Total': int(row['Total']),
                'Defaults': int(row['Defaults'])
            })
        
        return {
            'analysis_data': analysis_data,
            'summary_stats': {
                'total_categories': len(grouped),
                'avg_default_rate': grouped['Default_Rate'].mean(),
                'max_default_rate': grouped['Default_Rate'].max(),
                'min_default_rate': grouped['Default_Rate'].min()
            }
        }
    except Exception as e:
        logger.error(f"Error calculating categorical metrics: {str(e)}")
        raise

def calculate_numerical_metrics(df, feature_variable, target_variable, binning_method, bins):
    """Calculate numerical analysis metrics in the specified format with bin ranges"""
    try:
        # Apply binning to create deciles
        if binning_method == "quantile":
            df_binned = df.copy()
            df_binned[f'{feature_variable}_binned'] = pd.qcut(
                df[feature_variable], 
                q=bins, 
                duplicates='drop'
            )
        else:
            df_binned = df.copy()
            df_binned[f'{feature_variable}_binned'] = pd.cut(
                df[feature_variable], 
                bins=bins
            )
        
        # Group by binned variable and calculate metrics
        grouped = df_binned.groupby(f'{feature_variable}_binned')[target_variable].agg(['count', 'sum', 'mean']).reset_index()
        grouped.columns = [f'{feature_variable}_binned', 'Total', 'Defaults', 'Default_Rate']

        # Create the analysis data in the exact format requested
        analysis_data = []
        for _, row in grouped.iterrows():
            iv = row[f"{feature_variable}_binned"]
            bin_range = format_numeric_bin_range_label(iv)

            analysis_data.append({
                'Variable': feature_variable,
                'Bin_Range_Decile': bin_range,
                'Default_Rate': round(row['Default_Rate'], 2),
                'Total': int(row['Total']),
                'Defaults': int(row['Defaults'])
            })

        _sort_numerical_bins_by_range(analysis_data)

        # Calculate correlation
        correlation = df[feature_variable].corr(df[target_variable])
        
        return {
            'analysis_data': analysis_data,
            'correlation': correlation,
            'summary_stats': {
                'total_bins': len(grouped),
                'avg_default_rate': grouped['Default_Rate'].mean(),
                'max_default_rate': grouped['Default_Rate'].max(),
                'min_default_rate': grouped['Default_Rate'].min()
            }
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error calculating numerical metrics: {str(e)}")
        raise

def apply_binning(df, feature_variable, binning_method, bins):
    """Apply binning to numerical variable"""
    try:
        df_binned = df.copy()
        
        if binning_method == "quantile":
            # Quantile-based binning
            df_binned[f'{feature_variable}_binned'] = pd.qcut(
                df[feature_variable], 
                q=bins, 
                duplicates='drop'
            )
        elif binning_method == "equal_width":
            # Equal-width binning
            df_binned[f'{feature_variable}_binned'] = pd.cut(
                df[feature_variable], 
                bins=bins
            )
        else:
            # Default to quantile
            df_binned[f'{feature_variable}_binned'] = pd.qcut(
                df[feature_variable], 
                q=bins, 
                duplicates='drop'
            )
        
        return df_binned
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error applying binning: {str(e)}")
        raise

def generate_categorical_insights(analysis_data, is_high_cardinality, variable_name: Optional[str] = None):
    """Generate insights for categorical analysis"""
    insights = []
    
    try:
        data = analysis_data['analysis_data']
        default_rates = [item['Default_Rate'] for item in data]
        categories = [item['Category'] for item in data]

        if not default_rates:
            return [f"No valid categories found for {variable_name or 'variable'} - column may be all-null or constant."]

        # Find highest and lowest default rates
        max_rate_idx = default_rates.index(max(default_rates))
        min_rate_idx = default_rates.index(min(default_rates))
        
        insights.append(f"Highest default rate: {categories[max_rate_idx]} ({default_rates[max_rate_idx]:.2%})")
        insights.append(f"Lowest default rate: {categories[min_rate_idx]} ({default_rates[min_rate_idx]:.2%})")
        
        if is_high_cardinality:
            insights.append("High cardinality detected - top categories analyzed with 'Others' bucket")
        
        # Check for monotonic relationship
        if len(default_rates) > 2:
            is_monotonic = all(default_rates[i] >= default_rates[i+1] for i in range(len(default_rates)-1)) or \
                          all(default_rates[i] <= default_rates[i+1] for i in range(len(default_rates)-1))
            if is_monotonic:
                insights.append("Monotonic relationship detected between categories and target")
        
        return insights
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating categorical insights: {str(e)}")
        return [f"Error generating insights for {variable_name}"] if variable_name else ["Error generating insights"]

def generate_numerical_insights(analysis_data, binning_method, variable_name: Optional[str] = None):
    """Generate insights for numerical analysis"""
    insights = []
    
    try:
        data = analysis_data['analysis_data']
        default_rates = [item['Default_Rate'] for item in data]

        if not default_rates:
            return [f"No valid bins produced for {variable_name or 'variable'} - column may be all-null or constant."]

        # Include binning method info
        insights.append(f"Binning method applied: {binning_method}")

        # Find highest and lowest default rates
        max_rate = max(default_rates)
        min_rate = min(default_rates)
        insights.append(f"Default rate range: {min_rate:.2%} to {max_rate:.2%}")
        
        return insights
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating numerical insights: {str(e)}")
        return [f"Error generating insights for {variable_name}"] if variable_name else ["Error generating insights"]

def prepare_categorical_visualization(analysis_data):
    """Prepare data for categorical combination chart (bar + line)"""
    try:
        data = analysis_data['analysis_data']
        return {
            "chart_type": "combination_chart",
            "chart_title": f"Bivariate Analysis - {data[0]['Variable'] if data else 'Variable'}",
            "x_axis_label": "Category",
            "left_y_axis_label": "Total Count",
            "right_y_axis_label": "Event Rate",
            "data": {
                "categories": [item['Category'] for item in data],
                "bar_data": {
                    "label": "Total",
                    "values": [item['Total'] for item in data],
                    "color": "#FFA500"  # Orange bars
                },
                "line_data": {
                    "label": "Event Rate", 
                    "values": [item['Default_Rate'] for item in data],
                    "color": "#0066CC"  # Blue line
                }
            },
            "summary_stats": analysis_data['summary_stats']
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error preparing categorical visualization: {str(e)}")
        return {"chart_type": "combination_chart", "data": {}}

def prepare_numerical_visualization(analysis_data):
    """Prepare data for numerical combination chart (bar + line)"""
    try:
        data = analysis_data['analysis_data']
        return {
            "chart_type": "combination_chart",
            "chart_title": f"Bivariate Analysis - {data[0]['Variable'] if data else 'Variable'}",
            "x_axis_label": "Range",
            "left_y_axis_label": "Total Count",
            "right_y_axis_label": "Event Rate",
            "data": {
                "categories": [item['Bin_Range_Decile'] for item in data],
                "bar_data": {
                    "label": "Total",
                    "values": [item['Total'] for item in data],
                    "color": "#FFA500"  # Orange bars
                },
                "line_data": {
                    "label": "Event Rate",
                    "values": [item['Default_Rate'] for item in data],
                    "color": "#0066CC"  # Blue line
                }
            },
            "correlation": analysis_data['correlation'],
            "summary_stats": analysis_data['summary_stats']
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error preparing numerical visualization: {str(e)}")
        return {"chart_type": "combination_chart", "data": {}}

def generate_variable_summary(analysis_result, variable_type):
    """Generate a brief summary for the variable"""
    try:
        insights = analysis_result.get('insights', [])
        
        if variable_type == "categorical":
            return {
                "key_insight": insights[0] if insights else "No insights available",
                "total_categories": len(analysis_result.get('visualization_data', {}).get('data', {}).get('categories', [])),
                "has_high_cardinality": analysis_result.get('is_high_cardinality', False)
            }
        else:  # numerical
            return {
                "key_insight": insights[0] if insights else "No insights available",
                "binning_method": analysis_result.get('binning_method', 'unknown'),
                "correlation": analysis_result.get('visualization_data', {}).get('data', {}).get('correlation', 0)
            }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating variable summary: {str(e)}")
        return {"key_insight": "Error generating summary"}


# ============================================================================
# STANDARD DATA INSIGHTS (BIVARIATE TABLES)
# ============================================================================

def generate_bivariate_tables_for_standard_insights(
    dataset_id: str,
    target_variable: str,
    top_categories: int = 10,
    bins: int = 10,
    binning_method: str = "quantile"
) -> List[Dict[str, Any]]:
    """Generate bivariate table data using VECTORIZED operations.
    
    Automatically adapts to dataset size for optimal performance.
    Works on ANY size dataset (small, medium, large, very large).
    
    Returns a list of table dicts (helper-only, not API payload):
    [
      {
        "variable_name": str,
        "variable_type": "categorical"|"numerical",
        "columns": [...],
        "rows": [...],
        "insights": [...]
      },
      ...
    ]
    """
    logger = get_logger(__name__)
    logger.info(f"Generating Standard Data Insights (bivariate) for dataset: {dataset_id}")

    # Fetch train-preferred planning DataFrame from the state manager
    current_df = dataframe_state_manager.get_dataframe(dataset_id)
    if current_df is None:
        logger.error(f"No DataFrame found for dataset_id: {dataset_id}")
        return []
    df = dataframe_state_manager.get_latest_dataframe_for_planning(current_df, dataset_id)
    logger.info(f"DATA_INSIGHTS_DATASET_INFO: {df.shape}")

    if target_variable not in df.columns:
        logger.error(f"Target variable '{target_variable}' not in dataset columns")
        return []

    # ADAPTIVE: Detect dataset size and set limits automatically
    num_rows = len(df)
    num_cols = len(df.columns)
    
    # Determine adaptive limits based on dataset size
    if num_cols > 1000:
        # Very large: 100 columns, sample 50k rows
        max_columns = 100
        sample_rows = 50000
        logger.info(f"Very large dataset detected ({num_cols} cols, {num_rows} rows). Using limits: {max_columns} cols, {sample_rows} rows")
    elif num_cols > 500:
        # Large: 150 columns, sample 100k rows if >200k rows
        max_columns = 150
        sample_rows = 100000 if num_rows > 200000 else None
        logger.info(f"Large dataset detected ({num_cols} cols, {num_rows} rows). Using limits: {max_columns} cols, {'sampling ' + str(sample_rows) + ' rows' if sample_rows else 'all rows'}")
    elif num_cols > 200:
        # Medium-large: 200 columns, no sampling unless >500k rows
        max_columns = 200
        sample_rows = 150000 if num_rows > 500000 else None
        logger.info(f"Medium-large dataset ({num_cols} cols, {num_rows} rows). Processing {max_columns} cols")
    else:
        # Small-medium: Process all columns, no sampling
        max_columns = None  # No limit
        sample_rows = None
        logger.info(f"Small-medium dataset ({num_cols} cols, {num_rows} rows). Processing all columns")

    # Convert boolean target to numeric if needed for default rate calculations
    target_series = df[target_variable]
    if target_series.dtype == "bool":
        df = df.copy()
        df[target_variable] = target_series.astype(int)

    # ADAPTIVE: Sample rows if dataset is very large
    if sample_rows and num_rows > sample_rows:
        logger.info(f"Sampling {sample_rows} rows from {num_rows} for faster processing")
        df = df.sample(n=sample_rows, random_state=42).copy()
        logger.info(f"Working with sampled dataset: {df.shape}")

    # VECTORIZED: Fast column type detection (avoid full summary for speed)
    numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
    categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    # Remove target variable
    numeric_columns = [c for c in numeric_columns if c != target_variable]
    categorical_columns = [c for c in categorical_columns if c != target_variable]

    total_columns = len(categorical_columns) + len(numeric_columns)
    
    # ADAPTIVE: Apply column limits if needed
    if max_columns and total_columns > max_columns:
        logger.warning(f"Limiting processing to {max_columns} columns (dataset has {total_columns} columns)")
        # Prioritize: take proportional from each type
        cat_ratio = len(categorical_columns) / total_columns if total_columns > 0 else 0.5
        max_cat = max(1, int(max_columns * cat_ratio))
        max_num = max(1, max_columns - max_cat)
        
        categorical_columns = categorical_columns[:max_cat]
        numerical_columns = numeric_columns[:max_num]
        logger.info(f"Processing {len(categorical_columns)} categorical + {len(numerical_columns)} numerical = {len(categorical_columns) + len(numerical_columns)} columns")
    else:
        numerical_columns = numeric_columns
        logger.info(f"Processing all {total_columns} columns ({len(categorical_columns)} categorical, {len(numerical_columns)} numerical)")

    tables: List[Dict[str, Any]] = []

    def _format_number(n: float) -> str:
        try:
            return f"{int(round(float(n))):,}"
        except Exception:
            return str(n)

    def _format_bin_label(bin_label: str) -> str:
        """Turn raw '(a,b]' style into human friendly ranges like '< 25,000' or '25k - 50k'."""
        try:
            # Expect 'a,b' from earlier cleanup
            parts = str(bin_label).split(',')
            if len(parts) != 2:
                return bin_label
            left = float(parts[0])
            right = float(parts[1]) if len(parts) > 1 else float(parts[0])
            if left <= 0 and right > 0:
                return f"< {_format_number(right)}"
            # Treat extreme max as open ended
            if str(right).lower() in {"inf", "infinity"}:
                return f"> {_format_number(left)}"
            return f"{_format_number(left)} - {_format_number(right)}"
        except Exception:
            return bin_label

    def _bin_sort_key(bin_value: Any) -> float:
        """Return the numeric lower bound for a bin so bins can be ordered left→right."""
        try:
            if pd.isna(bin_value):
                return float("inf")
            if isinstance(bin_value, pd.Interval):
                return float(bin_value.left)
            if isinstance(bin_value, (int, float)):
                return float(bin_value)
            interval_text = str(bin_value).replace("[", "").replace("(", "")
            left_part = interval_text.split(",")[0].strip()
            return float("-inf") if left_part.lower() in {"-inf"} else float(left_part)
        except Exception:
            return float("inf")
    identifier_like = {"id", "member_id", "index", "row_id", "key"}

    from concurrent.futures import ThreadPoolExecutor as _TPE
    from app.core.config import settings as _settings
    _biv_workers = min(getattr(_settings, "INSIGHTS_MAX_WORKERS", 4), max(1, len(categorical_columns) + len(numerical_columns)))

    def _process_categorical(col):
        if col.lower() in identifier_like:
            return None
        try:
            grouped = df.groupby(col)[target_variable].agg(['count', 'sum', 'mean']).reset_index()
            grouped.columns = [col, 'Total', 'Defaults', 'Default_Rate']
            if len(grouped) > top_categories:
                grouped = grouped.nlargest(top_categories, 'Total')
            rows = grouped.to_dict('records')
            formatted_rows = [{
                "Variable": col,
                "Category": str(row[col]),
                "Event Rate": round(row['Default_Rate'], 4),
                "Total": int(row['Total']),
                "Event(Target flag=1)": int(row['Defaults'])
            } for row in rows]
            insights = []
            if formatted_rows:
                rates = [r['Event Rate'] for r in formatted_rows]
                insights.append(f"Event rate range: {min(rates):.2%} to {max(rates):.2%}")
                max_row = max(formatted_rows, key=lambda x: x['Event Rate'])
                insights.append(f"Highest event rate: {max_row['Category']} ({max(rates):.2%})")
            return {
                "variable_name": col,
                "variable_type": "categorical",
                "columns": ["Variable", "Category", "Event Rate", "Total", "Event(Target flag=1)"],
                "rows": formatted_rows,
                "insights": insights,
            }
        except Exception as e:
            logger.warning(f"Failed bivariate categorical for {col}: {e}")
            return None

    def _process_numerical(col):
        if col.lower() in identifier_like:
            return None
        try:
            binned_col = "__binned__"
            col_series = df[col]
            if binning_method == "quantile":
                try:
                    binned = pd.qcut(col_series, q=bins, duplicates='drop', precision=3)
                except ValueError:
                    binned = pd.cut(col_series, bins=bins, duplicates='drop', precision=3)
            else:
                binned = pd.cut(col_series, bins=bins, duplicates='drop', precision=3)

            tmp = pd.DataFrame({binned_col: binned, target_variable: df[target_variable]})
            grouped = tmp.groupby(binned_col)[target_variable].agg(['count', 'sum', 'mean']).reset_index()
            grouped.columns = [binned_col, 'Total', 'Defaults', 'Default_Rate']
            grouped = grouped.sort_values('Default_Rate', ascending=False)

            formatted_rows = []
            for row in grouped.to_dict('records'):
                bin_range = str(row[binned_col]).replace('(', '').replace(']', '').replace(' ', '')
                formatted_rows.append({
                    "Variable": col,
                    "Bin Range (Decile)": _format_bin_label(bin_range),
                    "Event Rate": round(row['Default_Rate'], 4),
                    "Total": int(row['Total']),
                    "Event(Target flag=1)": int(row['Defaults'])
                })

            insights = []
            if formatted_rows:
                rates = [r['Event Rate'] for r in formatted_rows]
                insights.append(f"Event rate range: {min(rates):.2%} to {max(rates):.2%}")
                if rates == sorted(rates, reverse=True):
                    insights.append("Monotonic decreasing pattern")
                elif rates == sorted(rates):
                    insights.append("Monotonic increasing pattern")

            return {
                "variable_name": col,
                "variable_type": "numerical",
                "columns": ["Variable", "Bin Range (Decile)", "Event Rate", "Total", "Event(Target flag=1)"],
                "rows": formatted_rows,
                "insights": insights,
            }
        except Exception as e:
            logger.warning(f"Failed bivariate numerical for {col}: {e}")
            return None

    logger.info(f"Processing {len(categorical_columns)} categorical + {len(numerical_columns)} numerical variables in parallel (workers={_biv_workers})")

    with _TPE(max_workers=_biv_workers) as pool:
        cat_results = list(pool.map(_process_categorical, categorical_columns))
        num_results = list(pool.map(_process_numerical, numerical_columns))

    tables.extend(r for r in cat_results if r is not None)
    tables.extend(r for r in num_results if r is not None)

    logger.info(f"Standard Data Insights generated: {len(tables)} variables")
    return tables

def _coerce_binary_target(series: pd.Series) -> Optional[pd.Series]:
    """Coerce a target series to numeric binary 0/1 if possible; return None if not possible."""
    if series.dtype == "bool":
        return series.astype(int)
    if pd.api.types.is_numeric_dtype(series):
        unique_vals = set(pd.Series(series.dropna().unique()).astype(float))
        if unique_vals.issubset({0.0, 1.0}):
            return series.astype(int)
        return None
    mapped = series.astype(str).str.lower().map({"true": 1, "false": 0, "yes": 1, "no": 0})
    if mapped.isna().any():
        return None
    return mapped.astype(int)

def _get_numeric_predictors(df: pd.DataFrame, target: str, include_bool: bool = True) -> List[str]:
    """Return numeric predictor columns excluding target. Optionally exclude boolean columns."""
    numeric = df.select_dtypes(include=["number"]).columns.tolist()
    numeric = [c for c in numeric if c != target]
    if not include_bool:
        numeric = [c for c in numeric if df[c].dtype != "bool"]
    return numeric

def _qcut_numeric(series: pd.Series, bins: int) -> pd.Series:
    """Quantile bin numeric series with duplicate handling; fallback to identity on failure or 1 unique value."""
    try:
        q = min(bins, max(1, series.dropna().nunique()))
        if q <= 1:
            return series
        return pd.qcut(series, q=q, duplicates='drop')
    except Exception:
        return series

def _group_counts_for_iv(bin_series: pd.Series, y: pd.Series) -> pd.DataFrame:
    """Group by bin and compute Total, Event=1 and Event=0 columns."""
    tmp = pd.DataFrame({"bin": bin_series, "y": y})
    grp = tmp.groupby("bin", dropna=False)["y"].agg(["count", "sum"]).reset_index()
    grp.columns = ["bin", "Total", "Event=1"]
    grp["Event=0"] = grp["Total"] - grp["Event=1"]
    return grp

def _compute_pg_pb(grp: pd.DataFrame) -> (pd.Series, pd.Series):
    """Compute perc shares for good (Event=1) and bad (Event=0)."""
    good_sum = grp["Event=1"].sum()
    bad_sum = grp["Event=0"].sum()
    pg = grp["Event=1"] / good_sum if good_sum != 0 else pd.Series(np.zeros(len(grp)))
    pb = grp["Event=0"] / bad_sum if bad_sum != 0 else pd.Series(np.zeros(len(grp)))
    return pg, pb

def _compute_woe_iv_bins(pg: pd.Series, pb: pd.Series) -> (pd.Series, pd.Series, float):
    """Compute WOE, per-bin IV, and total IV. Handle infinities like pipeline."""
    with np.errstate(divide="ignore", invalid="ignore"):
        woe = np.log(pg / pb)
    woe = pd.Series(woe).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    iv_bin = (pg - pb) * woe
    return woe, iv_bin, float(iv_bin.sum())

def _build_iv_detail_table(col: str, grp: pd.DataFrame, pg: pd.Series, pb: pd.Series, woe: pd.Series, iv_bin: pd.Series) -> pd.DataFrame:
    """Build detailed IV table rows for a variable."""
    return pd.DataFrame({
        "Variable": col,
        "Bin": grp["bin"].astype(str),
        "Total": grp["Total"].astype(int),
        "Event=0": grp["Event=0"].astype(int),
        "Event=1": grp["Event=1"].astype(int),
        "Per_Event=0": pb.round(6),
        "Per_Event=1": pg.round(6),
        "woe": woe.round(6),
        "iv": iv_bin.round(6),
    })

def _calculate_iv_for_single_variable(var: str, dfw: pd.DataFrame, target_variable: str, 
                                      unique_segments: List[int], bins: int, y: pd.Series) -> Optional[Dict[str, Any]]:
    """Helper function to calculate IV for a single variable - used for parallelization"""
    logger = get_logger(__name__)
    
    if var not in dfw.columns or var == target_variable:
        return None
        
    try:
        # Calculate overall IV
        overall_iv = 0.0
        try:
            if pd.api.types.is_numeric_dtype(dfw[var]):
                binned = _qcut_numeric(dfw[var], bins)
                grp = _group_counts_for_iv(binned, y)
                pg, pb = _compute_pg_pb(grp)
                _, _, overall_iv = _compute_woe_iv_bins(pg, pb)
            else:
                # For categorical, use categories as bins
                grp = _group_counts_for_iv(dfw[var], y)
                pg, pb = _compute_pg_pb(grp)
                _, _, overall_iv = _compute_woe_iv_bins(pg, pb)
        except Exception as e:
            logger.warning(f"Failed to calculate overall IV for {var}: {e}")
            overall_iv = 0.0
        
        # Calculate IV for each segment
        segment_ivs = {}
        for seg_id in unique_segments:
            try:
                seg_mask = dfw['_segment_id'] == seg_id
                seg_df = dfw[seg_mask]
                seg_y = seg_df[target_variable]
                
                # Skip if segment too small or no variation in target
                if len(seg_df) < 30 or seg_y.nunique() < 2:
                    segment_ivs[int(seg_id)] = 0.0
                    continue
                
                seg_iv = 0.0
                if pd.api.types.is_numeric_dtype(seg_df[var]):
                    binned = _qcut_numeric(seg_df[var], bins)
                    grp = _group_counts_for_iv(binned, seg_y)
                    pg, pb = _compute_pg_pb(grp)
                    _, _, seg_iv = _compute_woe_iv_bins(pg, pb)
                else:
                    grp = _group_counts_for_iv(seg_df[var], seg_y)
                    pg, pb = _compute_pg_pb(grp)
                    _, _, seg_iv = _compute_woe_iv_bins(pg, pb)
                
                segment_ivs[int(seg_id)] = float(seg_iv)
            except Exception as e:
                logger.warning(f"Failed to calculate segment {seg_id} IV for {var}: {e}")
                segment_ivs[int(seg_id)] = 0.0
        
        return {
            'variable_name': var,
            'overall_iv': float(overall_iv),
            'segment_ivs': segment_ivs
        }
        
    except Exception as e:
        logger.warning(f"Failed to process variable {var}: {e}")
        return None

def calculate_variable_iv_for_segments(
    df: pd.DataFrame,
    segment_ids: np.ndarray,
    target_variable: str,
    selected_variables: List[str],
    bins: int = 10
) -> Dict[str, Any]:
    """
    Calculate IV for each variable both overall and for each segment (OPTIMIZED: Parallel processing).
    
    Args:
        df: DataFrame with the data
        segment_ids: Array of segment assignments for each row
        target_variable: Name of the binary target variable
        selected_variables: List of variables to calculate IV for
        bins: Number of bins for numeric variables
    
    Returns:
        Dictionary with structure:
        {
            'variables': [
                {
                    'variable_name': str,
                    'overall_iv': float,
                    'segment_ivs': {segment_id: iv_value}
                },
                ...
            ]
        }
    """
    logger = get_logger(__name__)
    logger.info(f"Calculating variable IV for {len(selected_variables)} variables across segments (parallel processing)")
    
    # Coerce target to binary
    y = _coerce_binary_target(df[target_variable])
    if y is None:
        logger.warning("Target variable is not binary, cannot compute IV")
        return {'variables': []}
    
    dfw = df.copy()
    dfw[target_variable] = y
    dfw['_segment_id'] = segment_ids
    
    unique_segments = sorted(np.unique(segment_ids))
    
    # Filter valid variables
    valid_variables = [var for var in selected_variables if var in dfw.columns and var != target_variable]
    
    if not valid_variables:
        logger.warning("No valid variables found for IV calculation")
        return {'variables': []}
    
    # OPTIMIZATION: Use parallel processing for variable IV calculation
    try:
        results = Parallel(n_jobs=-1, backend='loky', verbose=0)(
            delayed(_calculate_iv_for_single_variable)(var, dfw, target_variable, unique_segments, bins, y)
            for var in valid_variables
        )
        # Filter out None results
        results = [r for r in results if r is not None]
    except Exception as e:
        logger.warning(f"Parallel IV calculation failed, falling back to sequential: {str(e)}")
        # Fallback to sequential processing
        results = []
        for var in valid_variables:
            result = _calculate_iv_for_single_variable(var, dfw, target_variable, unique_segments, bins, y)
            if result is not None:
                results.append(result)
    
    logger.info(f"Calculated IV for {len(results)} variables")
    return {'variables': results}

def generate_iv_analysis_tables_pipeline_style(
    dataset_id: str,
    target_variable: str,
    bins: int = 10,
    df: Optional[pd.DataFrame] = None
) -> List[Dict[str, Any]]:
    """
    Pipeline-style Information Value (IV) computation for NUMERIC predictors only.
    Mirrors the pipeline logic: bin (qcut) -> group -> perc shares -> WOE -> IV.

    Returns two kinds of sections:
    - iv_analysis_summary: overall IV per variable (sorted desc)
    - iv_analysis_details: one detail section per variable with per-bin rows
    """
    logger = get_logger(__name__)
    logger.info(f"Generating IV (pipeline-style) for dataset: {dataset_id}")

    # Use provided DataFrame or load from DataFrameStateManager/raw file
    if df is None:
        df = dataframe_state_manager.get_dataframe(dataset_id)
    if df is None or target_variable not in df.columns:
        from app.services.dataset_service import dataset_manager

        df = dataset_manager.load_dataset(dataset_id)
        if df is None or target_variable not in df.columns:
            logger.warning("IV: DataFrame missing or target not found after fallback")
            return []

    y = _coerce_binary_target(df[target_variable])
    if y is None:
        logger.warning("IV: target not binary; aborting")
        return []

    dfw = df.copy()
    dfw[target_variable] = y

    numeric_predictors = _get_numeric_predictors(dfw, target_variable, include_bool=True)

    detail_sections: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []

    for col in numeric_predictors:
        try:
            binned = _qcut_numeric(dfw[col], bins)
            grp = _group_counts_for_iv(binned, y)
            pg, pb = _compute_pg_pb(grp)
            woe, iv_bin, iv_val = _compute_woe_iv_bins(pg, pb)
            detail_df = _build_iv_detail_table(col, grp, pg, pb, woe, iv_bin)

            summary_rows.append({"Feature Name": col, "IV": round(iv_val, 6)})
            detail_sections.append({
                "analysis_kind": "iv_analysis_details",
                "variable": col,
                "title": f"IV Detail - {col}",
                "columns": [
                    "Variable", "Bin", "Total", "Event=0", "Event=1",
                    "Per_Event=0", "Per_Event=1", "woe", "iv"
                ],
                "rows": detail_df.to_dict("records")
            })
        except Exception as e:
            logger.warning(f"IV detail failed for {col}: {e}")
            summary_rows.append({"Feature Name": col, "IV": None})

    summary_rows_sorted = sorted(
        summary_rows,
        key=lambda r: (-r["IV"] if isinstance(r["IV"], (int, float)) and r["IV"] is not None else float("inf"))
    )

    sections: List[Dict[str, Any]] = [
        {
            "analysis_kind": "iv_analysis_summary",
            "title": "Information Value (IV) Summary",
            "columns": ["Feature Name", "IV"],
            "rows": summary_rows_sorted
        }
    ]
    sections.extend(detail_sections)
    logger.info(f"IV analysis generated summary for {len(summary_rows_sorted)} variables and {len(detail_sections)} detail tables")
    return sections

    # ---------------------ANALYZE ALL CORRELATIONS---------------------
    # ------------------------------------------------------------------
def analyze_all_correlations(df, target_variable, threshold=0.05):
    """
    Analyze correlations for all variables against target variable
    Returns comprehensive correlation analysis with visualization data
    """
    try:
        import logging
        import time
        logger = logging.getLogger(__name__)
        logger.info(f"Starting correlation analysis for target: {target_variable}")
        
        # Get variable types
        numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
        categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        # Exclude problematic columns like member_id, id, etc.
        problematic_columns = ['member_id', 'id', 'index', 'row_id']
        numeric_columns = [col for col in numeric_columns if col.lower() not in [p.lower() for p in problematic_columns]]
        
        # Remove target variable from analysis columns
        if target_variable in numeric_columns:
            numeric_columns.remove(target_variable)
        if target_variable in categorical_columns:
            categorical_columns.remove(target_variable)
        
        # For very large datasets, limit the number of variables to analyze
        max_variables = 100
        if len(numeric_columns) > max_variables:
            logger.info(f"Dataset has {len(numeric_columns)} numeric variables, limiting to {max_variables} for performance")
            numeric_columns = numeric_columns[:max_variables]
        
        if len(categorical_columns) > max_variables:
            logger.info(f"Dataset has {len(categorical_columns)} categorical variables, limiting to {max_variables} for performance")
            categorical_columns = categorical_columns[:max_variables]
        
        correlation_results = []
        significant_variables = 0
        visualization_data = {}
        start_time = time.time()

        from concurrent.futures import ThreadPoolExecutor as _TPE
        from app.core.config import settings as _settings
        _max_workers = min(getattr(_settings, "INSIGHTS_MAX_WORKERS", 4), max(1, len(numeric_columns) + len(categorical_columns)))

        def _analyze_numeric(col):
            try:
                pearson = calculate_pearson_correlation(df, col, target_variable)
                spearman = calculate_spearman_correlation(df, col, target_variable)
                max_corr = max(abs(pearson), abs(spearman))
                viz_data = generate_correlation_visualization_data(df, col, target_variable, pearson, "numeric")
                return {
                    "result": {
                        "variable_name": col,
                        "variable_type": "numeric",
                        "pearson_correlation": pearson,
                        "spearman_correlation": spearman,
                        "is_significant": max_corr >= threshold,
                        "significance_level": get_correlation_significance_level(max_corr, threshold),
                        "primary_correlation": pearson,
                    },
                    "viz": viz_data,
                    "col": col,
                }
            except Exception as e:
                logger.warning(f"Failed to analyze numeric variable {col}: {e}")
                return {
                    "result": {
                        "variable_name": col, "variable_type": "numeric",
                        "pearson_correlation": 0.0, "spearman_correlation": 0.0,
                        "is_significant": False, "significance_level": "none",
                        "primary_correlation": 0.0, "error": str(e),
                    },
                    "viz": generate_correlation_visualization_data(df, col, target_variable, 0.0, "numeric"),
                    "col": col,
                }

        def _analyze_categorical(col):
            try:
                chi_square_results = calculate_chi_square_test(df, col, target_variable)
                cramers_v = chi_square_results["cramers_v"]
                if cramers_v is None or (isinstance(cramers_v, float) and (np.isnan(cramers_v) or np.isinf(cramers_v))):
                    cramers_v = 0.0
                viz_data = generate_correlation_visualization_data(df, col, target_variable, cramers_v, "categorical")
                return {
                    "result": {
                        "variable_name": col,
                        "variable_type": "categorical",
                        "chi_square_statistic": chi_square_results["chi_square_statistic"],
                        "chi_square_p_value": chi_square_results["chi_square_p_value"],
                        "cramers_v": cramers_v,
                        "is_significant": abs(cramers_v) >= threshold,
                        "significance_level": get_correlation_significance_level(cramers_v, threshold),
                        "primary_correlation": cramers_v,
                    },
                    "viz": viz_data,
                    "col": col,
                }
            except Exception as e:
                logger.warning(f"Failed to analyze categorical variable {col}: {e}")
                return {
                    "result": {
                        "variable_name": col, "variable_type": "categorical",
                        "chi_square_statistic": 0.0, "chi_square_p_value": 1.0,
                        "cramers_v": 0.0, "is_significant": False,
                        "significance_level": "none", "primary_correlation": 0.0, "error": str(e),
                    },
                    "viz": generate_correlation_visualization_data(df, col, target_variable, 0.0, "categorical"),
                    "col": col,
                }

        logger.info(f"Analyzing {len(numeric_columns)} numeric + {len(categorical_columns)} categorical variables in parallel (workers={_max_workers})")

        with _TPE(max_workers=_max_workers) as pool:
            num_futures = list(pool.map(_analyze_numeric, numeric_columns))
            cat_futures = list(pool.map(_analyze_categorical, categorical_columns))

        for item in num_futures + cat_futures:
            correlation_results.append(item["result"])
            visualization_data[item["col"]] = item["viz"]
            if item["result"].get("is_significant"):
                significant_variables += 1

        logger.info(f"Correlation analysis completed: {len(correlation_results)} variables, {significant_variables} significant")
        
        return {
            "total_variables": len(correlation_results),
            "significant_variables": significant_variables,
            "correlation_results": correlation_results,
            "visualization_data": visualization_data
        }
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in analyze_all_correlations: {str(e)}")
        return {"error": str(e)}

def calculate_pearson_correlation(df, var1, var2):
    """Calculate Pearson correlation coefficient"""
    try:
        import numpy as np
        # Remove NaN values
        clean_data = df[[var1, var2]].dropna()
        if len(clean_data) < 2:
            return 0.0
        
        correlation = clean_data[var1].corr(clean_data[var2])
        return float(correlation) if not np.isnan(correlation) else 0.0
    except Exception:
        return 0.0

def calculate_spearman_correlation(df, var1, var2):
    """Calculate Spearman rank correlation coefficient"""
    try:
        from scipy.stats import spearmanr
        import numpy as np
        
        # Remove NaN values
        clean_data = df[[var1, var2]].dropna()
        if len(clean_data) < 2:
            return 0.0
        
        correlation, _ = spearmanr(clean_data[var1], clean_data[var2])
        return float(correlation) if not np.isnan(correlation) else 0.0
    except Exception:
        return 0.0

def calculate_kendall_correlation(df, var1, var2):
    """Calculate Kendall tau correlation coefficient"""
    try:
        from scipy.stats import kendalltau
        import numpy as np
        
        # Remove NaN values
        clean_data = df[[var1, var2]].dropna()
        if len(clean_data) < 2:
            return 0.0
        
        correlation, _ = kendalltau(clean_data[var1], clean_data[var2])
        return float(correlation) if not np.isnan(correlation) else 0.0
    except Exception:
        return 0.0

def calculate_biweight_correlation(df, var1, var2):
    """Calculate biweight midcorrelation (outlier-robust)"""
    try:
        import numpy as np
        from scipy.stats import pearsonr
        
        # Remove NaN values
        clean_data = df[[var1, var2]].dropna()
        if len(clean_data) < 2:
            return 0.0
        
        x = clean_data[var1].values
        y = clean_data[var2].values
        
        # Winsorize data (replace extreme values)
        x_winsorized = winsorize_data(x)
        y_winsorized = winsorize_data(y)
        
        # Calculate Pearson correlation on winsorized data
        correlation, _ = pearsonr(x_winsorized, y_winsorized)
        return float(correlation) if not np.isnan(correlation) else 0.0
    except Exception:
        return 0.0

def calculate_distance_correlation(df, var1, var2):
    """Calculate distance correlation (detects any dependence)"""
    try:
        import numpy as np
        import pandas as pd
        
        # Remove NaN values
        clean_data = df[[var1, var2]].dropna()
        if len(clean_data) < 2:
            return 0.0
        
        # Skip distance correlation for large datasets to prevent hanging
        if len(clean_data) > 5000:
            return 0.0
        
        x = clean_data[var1].values
        y = clean_data[var2].values
        
        # Convert to numeric if needed
        x = pd.to_numeric(x, errors='coerce')
        y = pd.to_numeric(y, errors='coerce')
        
        # Remove any remaining NaN values
        mask = ~(np.isnan(x) | np.isnan(y))
        x = x[mask]
        y = y[mask]
        
        if len(x) < 2:
            return 0.0
        
        # Calculate distance correlation
        dcor = distance_correlation_impl(x, y)
        return float(dcor) if not np.isnan(dcor) else 0.0
    except Exception:
        return 0.0

def calculate_chi_square_test(df, var1, var2):
    """Calculate Chi-square test of independence and Cramér's V"""
    try:
        from scipy.stats import chi2_contingency
        import numpy as np
        import pandas as pd
        
        # Create contingency table
        contingency_table = pd.crosstab(df[var1], df[var2])
        
        # Check if table has valid dimensions
        if contingency_table.shape[0] < 2 or contingency_table.shape[1] < 2:
            return {
                "chi_square_statistic": 0.0,
                "chi_square_p_value": 1.0,
                "degrees_of_freedom": 0,
                "cramers_v": 0.0
            }
        
        # Perform chi-square test
        chi2_stat, p_value, dof, expected = chi2_contingency(contingency_table)
        
        # Calculate Cramér's V
        n = contingency_table.sum().sum()
        min_dim = min(contingency_table.shape)
        cramers_v = np.sqrt(chi2_stat / (n * (min_dim - 1)))
        
        # Ensure cramers_v is a valid number
        if np.isnan(cramers_v) or np.isinf(cramers_v):
            cramers_v = 0.0
        
        return {
            "chi_square_statistic": float(chi2_stat),
            "chi_square_p_value": float(p_value),
            "degrees_of_freedom": int(dof),
            "cramers_v": float(cramers_v)
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Chi-square test failed for {var1} vs {var2}: {str(e)}")
        return {
            "chi_square_statistic": 0.0,
            "chi_square_p_value": 1.0,
            "degrees_of_freedom": 0,
            "cramers_v": 0.0
        }

def get_correlation_significance_level(corr_value, threshold):
    """Determine significance level based on correlation value and threshold"""
    abs_corr = abs(corr_value)
    
    if abs_corr >= 0.7:
        return "high"
    elif abs_corr >= 0.3:
        return "moderate"
    elif abs_corr >= threshold:
        return "low"
    else:
        return "none"

def generate_correlation_visualization_data(df, var_name, target_variable, corr_value, var_type):
    """Generate visualization data for correlation analysis"""
    try:
        # Handle None correlation values
        safe_corr_value = corr_value if corr_value is not None and not (isinstance(corr_value, float) and np.isnan(corr_value)) else 0.0
        
        if var_type == "numeric":
            # For numeric variables, create scatter plot data
            clean_data = df[[var_name, target_variable]].dropna()
            
            return {
                "chart_type": "scatter",
                "title": f"Correlation: {var_name} vs {target_variable}",
                "x_axis_label": var_name,
                "y_axis_label": target_variable,
                "data": {
                    "x_values": clean_data[var_name].tolist(),
                    "y_values": clean_data[target_variable].tolist(),
                    "correlation": safe_corr_value
                },
                "correlation_value": safe_corr_value,
                "trend_line_data": {
                    "slope": safe_corr_value,
                    "intercept": clean_data[target_variable].mean() - safe_corr_value * clean_data[var_name].mean()
                }
            }
        else:
            # For categorical variables, create histogram with trend line
            clean_data = df[[var_name, target_variable]].dropna()
            
            # Group by categorical variable and calculate mean target
            grouped = clean_data.groupby(var_name)[target_variable].agg(['count', 'mean']).reset_index()
            
            return {
                "chart_type": "histogram_with_trend",
                "title": f"Distribution: {var_name} vs {target_variable}",
                "x_axis_label": var_name,
                "y_axis_label": f"Mean {target_variable}",
                "data": {
                    "categories": grouped[var_name].tolist(),
                    "values": grouped['mean'].tolist(),
                    "counts": grouped['count'].tolist()
                },
                "correlation_value": safe_corr_value
            }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating visualization data for {var_name}: {str(e)}")
        return {
            "chart_type": "scatter",
            "title": f"Correlation: {var_name} vs {target_variable}",
            "x_axis_label": var_name,
            "y_axis_label": target_variable,
            "data": {
                "x_values": [],
                "y_values": [],
                "correlation": 0.0
            },
            "correlation_value": 0.0,
            "trend_line_data": {
                "slope": 0,
                "intercept": 0
            }
        }

# Removed unused functions: generate_correlation_bar_chart_data, generate_correlation_tables
# These were only used by the removed APIs: /chart-data, /tables

def winsorize_data(data, limits=(0.1, 0.1)):
    """Winsorize data by replacing extreme values"""
    try:
        import numpy as np
        
        # Calculate percentiles
        lower_percentile = np.percentile(data, limits[0] * 100)
        upper_percentile = np.percentile(data, (1 - limits[1]) * 100)
        
        # Clip extreme values
        winsorized = np.clip(data, lower_percentile, upper_percentile)
        return winsorized
    except Exception:
        return data

def distance_correlation_impl(x, y):
    """Implementation of distance correlation - optimized for large datasets"""
    try:
        import numpy as np
        
        # For large datasets, use a more efficient approach or skip distance correlation
        n = len(x)
        if n > 10000:  # Skip distance correlation for very large datasets
            return 0.0
        
        def dist_matrix(data):
            """Calculate distance matrix efficiently using broadcasting"""
            n = len(data)
            # Use broadcasting to calculate all pairwise distances at once
            data = data.reshape(-1, 1)
            dist = np.abs(data - data.T)
            return dist
        
        def centered_dist_matrix(dist):
            """Center the distance matrix"""
            n = dist.shape[0]
            row_means = np.mean(dist, axis=1)
            col_means = np.mean(dist, axis=0)
            grand_mean = np.mean(dist)
            
            centered = dist - row_means[:, np.newaxis] - col_means[np.newaxis, :] + grand_mean
            return centered
        
        # Calculate distance matrices
        dist_x = dist_matrix(x)
        dist_y = dist_matrix(y)
        
        # Center the distance matrices
        centered_x = centered_dist_matrix(dist_x)
        centered_y = centered_dist_matrix(dist_y)
        
        # Calculate distance covariance
        dcov_xy = np.sqrt(np.mean(centered_x * centered_y))
        
        # Calculate distance variances
        dcov_xx = np.sqrt(np.mean(centered_x * centered_x))
        dcov_yy = np.sqrt(np.mean(centered_y * centered_y))
        
        # Calculate distance correlation
        if dcov_xx > 0 and dcov_yy > 0:
            dcor = dcov_xy / np.sqrt(dcov_xx * dcov_yy)
        else:
            dcor = 0.0
        
        return dcor
    except Exception:
        return 0.0

def clean_nan_values(data, replace_with=None):
    """
    Recursively clean NaN, None, and infinite values from nested data structures.
    
    Args:
        data: The data structure to clean (dict, list, or primitive)
        replace_with: Value to replace NaN/None/inf with. If None, dict keys whose value
            becomes None are omitted; list positions are kept (values may become None).
    
    Returns:
        Cleaned data structure with NaN/inf values handled for JSON
    """
    try:
        import numpy as np
        import pandas as pd
        
        if isinstance(data, dict):
            # Recursively clean dictionary values
            cleaned_dict = {}
            for key, value in data.items():
                cleaned_value = clean_nan_values(value, replace_with)
                # Only include the key-value pair if the cleaned value is not None (when replace_with is None)
                if replace_with is not None or cleaned_value is not None:
                    cleaned_dict[key] = cleaned_value
            return cleaned_dict
            
        elif isinstance(data, list):
            # Preserve list length (including None cells), e.g. η heatmap matrices after NaN→None.
            return [clean_nan_values(item, replace_with) for item in data]
            
        elif isinstance(data, (np.floating, float)):
            # Handle NaN and infinite values
            if np.isnan(data) or np.isinf(data):
                return replace_with
            return float(data)
            
        elif isinstance(data, (np.integer, int)):
            # Handle NaN integers (shouldn't happen but just in case)
            if np.isnan(data):
                return replace_with
            return int(data)
            
        elif isinstance(data, (np.bool_, bool)):
            return bool(data)
            
        elif isinstance(data, (np.str_, str)):
            return str(data)
            
        elif isinstance(data, pd.Series):
            # Clean pandas Series
            if replace_with is not None:
                return data.fillna(replace_with).tolist()
            else:
                return data.dropna().tolist()
                
        elif isinstance(data, pd.DataFrame):
            # Clean pandas DataFrame
            if replace_with is not None:
                return data.fillna(replace_with).to_dict('records')
            else:
                return data.dropna().to_dict('records')
                
        elif data is None:
            return replace_with
            
        else:
            # For other types, return as-is
            return data
            
    except Exception as e:
        # If cleaning fails, return the original data or replace_with
        logger = get_logger(__name__)
        logger.warning(f"Error cleaning NaN values: {str(e)}")
        return replace_with if replace_with is not None else data

def compute_iv(df: pd.DataFrame, feature: str, target: str) -> float:
    """
    Compute Information Value (IV) for a categorical feature against a binary target.
    """
    try:
        df2 = df[[feature, target]].dropna()
        total_event = df2[target].sum()
        total_non_event = df2.shape[0] - total_event
        iv = 0.0
        for val, grp in df2.groupby(feature):
            event_count = grp[target].sum()
            non_event_count = grp.shape[0] - event_count
            if event_count == 0 or non_event_count == 0 or total_event == 0 or total_non_event == 0:
                continue
            rate_event = event_count / total_event
            rate_non_event = non_event_count / total_non_event
            iv += (rate_non_event - rate_event) * math.log(rate_non_event / rate_event)
        return float(iv)
    except Exception:
        return 0.0



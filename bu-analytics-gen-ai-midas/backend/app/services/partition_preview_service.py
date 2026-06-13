"""
Compute partition row indices and summary stats for Step 1 Review Stats (no global state).
Mirrors dataframe_state_manager.apply_split_configuration split logic.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


def _split_indices_from_config(
    master_df: pd.DataFrame,
    target_variable: str,
    split_configuration: Dict[str, Any],
    seed: int = 42,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    if not split_configuration or split_configuration.get("ingestion_mode") != "platform_split":
        return None
    method = split_configuration.get("split_method")
    n = len(master_df)
    if n == 0:
        return None
    indices = np.arange(n, dtype=np.int64)

    cfg_seed = split_configuration.get("seed")
    if cfg_seed is not None:
        try:
            seed = int(cfg_seed)
        except (ValueError, TypeError):
            pass

    try:
        if method == "user_identifier":
            col = split_configuration.get("identifier_column")
            mapping = split_configuration.get("identifier_mapping") or {}
            if not col or col not in master_df.columns:
                return None
            s = master_df[col]
            train_v = mapping.get("train")
            test_v = mapping.get("test")
            validation_v = mapping.get("validation")
            if not train_v:
                return None
            
            def norm_cell(x):
                if pd.isna(x):
                    return None
                s = str(x).strip()
                if s.endswith('.0'):
                    s = s[:-2]
                return s

            s_norm = s.map(norm_cell)
            null_mask = s_norm.isna() | (s_norm == "")

            def norm_mapping_val(v):
                s = str(v).strip()
                if s.endswith('.0'):
                    s = s[:-2]
                return s
            
            def create_match_mask(s_norm_series, target_val, null_mask):
                """Create mask that matches either exact string or numeric prefix."""
                if not target_val:
                    return pd.Series(False, index=s_norm_series.index)
                
                target_norm = norm_mapping_val(target_val)
                exact_match = (s_norm_series == target_norm) & ~null_mask
                
                if exact_match.sum() > 0:
                    return exact_match
                
                try:
                    target_num = float(target_norm)
                    def extract_leading_number(s):
                        if pd.isna(s) or s == "":
                            return None
                        match = re.match(r'^[\s]*(-?\d+\.?\d*)', str(s))
                        if match:
                            try:
                                return float(match.group(1))
                            except ValueError:
                                return None
                        return None
                    
                    s_nums = s_norm_series.map(extract_leading_number)
                    numeric_match = (s_nums == target_num) & ~null_mask
                    return numeric_match
                except ValueError:
                    return exact_match
            
            train_norm = norm_mapping_val(train_v) if train_v else None
            test_norm = norm_mapping_val(test_v) if test_v else None
            
            train_mask = create_match_mask(s_norm, train_v, null_mask)
            test_mask = create_match_mask(s_norm, test_v, null_mask)
            
            if isinstance(validation_v, list) and len(validation_v) > 0:
                validation_mask = pd.Series(False, index=master_df.index)
                for v in validation_v:
                    validation_mask = validation_mask | create_match_mask(s_norm, v, null_mask)
            elif validation_v:
                validation_mask = create_match_mask(s_norm, validation_v, null_mask)
            else:
                validation_mask = pd.Series(False, index=master_df.index)

            train_idx = np.where(train_mask.values)[0].astype(np.int64)
            test_idx = np.where(test_mask.values)[0].astype(np.int64)
            validation_idx = np.where(validation_mask.values)[0].astype(np.int64)
            
            print(f"[DEBUG partition_preview] train_count={len(train_idx)}, test_count={len(test_idx)}, validation_count={len(validation_idx)}")

        elif method == "time_based":
            dc = split_configuration.get("date_column")
            if not dc or dc not in master_df.columns:
                return None
            ratios = split_configuration.get("ratios") or {}
            tr = int(ratios.get("train", 60))
            te = int(ratios.get("test", 20))
            va = int(ratios.get("validation", 20))
            if tr + te + va != 100:
                tr, te, va = 60, 20, 20

            cutoff_1 = split_configuration.get("cutoff_1")
            cutoff_2 = split_configuration.get("cutoff_2")
            
            # Check if this is a year-less date format (DD-Mon like 12-Nov)
            is_yearless = _is_yearless_date_format(master_df, dc)
            
            if is_yearless:
                # For year-less dates, sort by month-day order using the shared parser
                def get_sort_key(val):
                    result = _parse_yearless_date(val)
                    if result:
                        return (result[0], result[1], str(val).strip())
                    return (99, 99, str(val).strip())  # Invalid dates go to end
                
                # Create sorting data
                sort_data = [(i, get_sort_key(master_df[dc].iloc[i])) for i in range(n)]
                sort_data.sort(key=lambda x: (x[1][0], x[1][1]))  # Sort by (month, day)
                sort_order = np.array([x[0] for x in sort_data], dtype=np.int64)
                sorted_values = [x[1][2] for x in sort_data]  # Original strings
                
                if cutoff_1 is not None and cutoff_1.strip():
                    # Manual cutoff provided - find the index where this value appears
                    try:
                        cutoff_1_result = _parse_yearless_date(cutoff_1)
                        cutoff_2_result = _parse_yearless_date(cutoff_2) if cutoff_2 and cutoff_2.strip() and va > 0 else None
                        
                        if cutoff_1_result is None:
                            raise ValueError("Invalid cutoff_1 format")
                        
                        cutoff_1_key = (cutoff_1_result[0], cutoff_1_result[1])
                        cutoff_2_key = (cutoff_2_result[0], cutoff_2_result[1]) if cutoff_2_result else None
                        
                        # Find indices based on month-day comparison
                        def get_md_key(v):
                            r = _parse_yearless_date(v)
                            return (r[0], r[1]) if r else (99, 99)
                        
                        train_mask = np.array([get_md_key(v) <= cutoff_1_key for v in sorted_values])
                        
                        if cutoff_2_key is not None:
                            test_mask = np.array([cutoff_1_key < get_md_key(v) <= cutoff_2_key for v in sorted_values])
                            validation_mask = np.array([get_md_key(v) > cutoff_2_key for v in sorted_values])
                        else:
                            test_mask = np.array([get_md_key(v) > cutoff_1_key for v in sorted_values])
                            validation_mask = np.zeros(n, dtype=bool)
                        
                        train_idx = sort_order[train_mask].astype(np.int64)
                        test_idx = sort_order[test_mask].astype(np.int64)
                        validation_idx = sort_order[validation_mask].astype(np.int64)
                    except Exception:
                        # Fallback to percentage-based split
                        train_end = int(n * tr / 100)
                        test_end = int(n * (tr + te) / 100)
                        train_idx = sort_order[:train_end].astype(np.int64)
                        test_idx = sort_order[train_end:test_end].astype(np.int64)
                        validation_idx = sort_order[test_end:].astype(np.int64)
                else:
                    # Auto-compute based on percentages
                    train_end = int(n * tr / 100)
                    test_end = int(n * (tr + te) / 100)
                    train_idx = sort_order[:train_end].astype(np.int64)
                    test_idx = sort_order[train_end:test_end].astype(np.int64)
                    validation_idx = sort_order[test_end:].astype(np.int64)
            else:
                # Standard date parsing for dates with year
                dt = pd.to_datetime(master_df[dc], errors="coerce")
                if dt.isna().all() or (dt.notna().any() and dt.dt.year.max() < 1950):
                    for fmt in ["%y-%b", "%b-%y", "%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"]:
                        try:
                            test_dt = pd.to_datetime(master_df[dc], format=fmt, errors="coerce")
                            if test_dt.notna().any() and test_dt.dt.year.max() >= 1950:
                                dt = test_dt
                                break
                        except Exception:
                            continue
                sort_order = np.argsort(dt.values, kind="mergesort")
                sorted_dates = dt.iloc[sort_order]

                if cutoff_1 is not None and cutoff_1.strip():
                    cutoff_1_dt = pd.to_datetime(cutoff_1, errors="coerce")
                    cutoff_2_dt = pd.to_datetime(cutoff_2, errors="coerce") if cutoff_2 and va > 0 else None

                    train_mask = sorted_dates <= cutoff_1_dt
                    if cutoff_2_dt is not None and pd.notna(cutoff_2_dt):
                        test_mask = (sorted_dates > cutoff_1_dt) & (sorted_dates <= cutoff_2_dt)
                        validation_mask = sorted_dates > cutoff_2_dt
                    else:
                        test_mask = sorted_dates > cutoff_1_dt
                        validation_mask = pd.Series(False, index=sorted_dates.index)

                    train_idx = sort_order[train_mask.values].astype(np.int64)
                    test_idx = sort_order[test_mask.values].astype(np.int64)
                    validation_idx = sort_order[validation_mask.values].astype(np.int64)
                else:
                    train_end = int(n * tr / 100)
                    test_end = int(n * (tr + te) / 100)

                    train_idx = sort_order[:train_end].astype(np.int64)
                    test_idx = sort_order[train_end:test_end].astype(np.int64)
                    validation_idx = sort_order[test_end:].astype(np.int64)

        elif method == "stratified_random":
            ratios = split_configuration.get("ratios") or {}
            tr = int(ratios.get("train", 60))
            te = int(ratios.get("test", 20))
            va = int(ratios.get("validation", 20))
            if tr + te + va != 100:
                tr, te, va = 60, 20, 20
            tf, tef, vf = tr / 100.0, te / 100.0, va / 100.0

            y = master_df[target_variable] if target_variable in master_df.columns else None
            strat = None
            if y is not None and y.nunique() > 1:
                if y.nunique() <= 50:
                    strat = y
                else:
                    try:
                        strat = pd.qcut(y, q=10, labels=False, duplicates="drop")
                    except Exception:
                        strat = None

            if vf <= 1e-12:
                rest_idx = indices.copy()
                validation_idx = np.array([], dtype=np.int64)
            else:
                rest_idx, validation_idx = train_test_split(
                    indices,
                    test_size=vf,
                    random_state=seed,
                    stratify=strat,
                )
                validation_idx = np.asarray(validation_idx, dtype=np.int64)

            strat_rest = None
            if strat is not None and len(rest_idx) > 0:
                y_rest = strat.iloc[rest_idx].reset_index(drop=True)
                if y_rest.nunique() > 1:
                    strat_rest = y_rest

            rel_tf = tf / (tf + tef) if (tf + tef) > 1e-9 else 1.0
            if len(rest_idx) == 0:
                train_idx = np.array([], dtype=np.int64)
                test_idx = np.array([], dtype=np.int64)
            elif tef <= 1e-12:
                train_idx = np.asarray(rest_idx, dtype=np.int64)
                test_idx = np.array([], dtype=np.int64)
            elif tf <= 1e-12:
                train_idx = np.array([], dtype=np.int64)
                test_idx = np.asarray(rest_idx, dtype=np.int64)
            else:
                train_idx, test_idx = train_test_split(
                    rest_idx,
                    train_size=rel_tf,
                    random_state=seed,
                    stratify=strat_rest,
                )
                train_idx = np.asarray(train_idx, dtype=np.int64)
                test_idx = np.asarray(test_idx, dtype=np.int64)
        else:
            return None

        return train_idx, test_idx, validation_idx
    except Exception:
        return None


def _binary_event_mask(series: pd.Series) -> Optional[Tuple[pd.Series, str]]:
    s = series.dropna()
    if len(s) == 0 or s.nunique() != 2:
        return None
    vc = s.value_counts()
    rare_label = vc.idxmin()
    mask = series == rare_label
    return mask, str(rare_label)


def _safe_strftime(ts: pd.Timestamp, fmt: str = "%b %y") -> str:
    """Format timestamp safely, handling years < 1900 on Windows."""
    if pd.isna(ts):
        return "N/A"
    try:
        return ts.strftime(fmt)
    except ValueError:
        return f"{ts.month_name()[:3]} {str(ts.year)[-2:]}"


def _format_date_range(sub_df: pd.DataFrame, date_col: str) -> Optional[str]:
    if date_col not in sub_df.columns or len(sub_df) == 0:
        return None
    
    # First check if this is a year-less date format
    if _is_yearless_date_format(sub_df, date_col):
        result = _compute_yearless_date_range(sub_df, date_col)
        if result.get("min_date") and result.get("max_date"):
            return f"{result['min_date']} - {result['max_date']}"
        return None
    
    # Try multiple date parsing approaches (same logic as cutoff computation)
    dt = pd.to_datetime(sub_df[date_col], errors="coerce")
    if dt.isna().all() or (dt.notna().any() and dt.dt.year.max() < 1950):
        for fmt in ["%y-%b", "%b-%y", "%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"]:
            try:
                test_dt = pd.to_datetime(sub_df[date_col], format=fmt, errors="coerce")
                if test_dt.notna().any() and test_dt.dt.year.max() >= 1950:
                    dt = test_dt
                    break
            except Exception:
                continue
    valid = dt.dropna()
    valid = valid[valid.dt.year >= 1900]
    if len(valid) == 0:
        return None
    mn, mx = valid.min(), valid.max()
    return f"{_safe_strftime(mn)} - {_safe_strftime(mx)}"


def _is_yearless_date_format(df: pd.DataFrame, date_col: str, sample_size: int = 100) -> bool:
    """
    Check if the date column contains year-less date formats.
    Supported formats:
    - DD-Mon (e.g., 12-Nov, 3-Feb)
    - Mon-DD (e.g., Nov-12, Feb-3)
    - DD/MM (e.g., 12/11, 03/02)
    - MM/DD (e.g., 11/12, 02/03)
    Returns True if the format lacks year information.
    """
    sample = df[date_col].dropna().head(sample_size).astype(str).str.strip()
    if len(sample) == 0:
        return False
    
    # Patterns for year-less dates
    yearless_patterns = [
        re.compile(r"^\d{1,2}-[A-Za-z]{3,}$"),  # DD-Mon (e.g., 12-Nov)
        re.compile(r"^[A-Za-z]{3,}-\d{1,2}$"),  # Mon-DD (e.g., Nov-12)
        re.compile(r"^\d{1,2}/\d{1,2}$"),       # DD/MM or MM/DD (e.g., 12/11)
    ]
    
    match_count = 0
    for v in sample:
        if any(p.fullmatch(v) for p in yearless_patterns):
            match_count += 1
    
    # If >70% match any yearless pattern, it's a yearless format
    return (match_count / len(sample)) >= 0.7


def _parse_yearless_date(val: str):
    """
    Parse a year-less date string into (month, day) tuple.
    Supports multiple formats:
    - DD-Mon (e.g., 12-Nov)
    - DD-Month (e.g., 12-November)
    - Mon-DD (e.g., Nov-12)
    - Month-DD (e.g., November-12)
    - DD/MM (e.g., 12/11)
    - MM/DD (e.g., 11/12) - ambiguous, treated as MM/DD
    Returns (month, day) tuple or None if parsing fails.
    """
    val = str(val).strip()
    
    # Try DD-Mon (e.g., 12-Nov)
    try:
        dt = datetime.strptime(val, "%d-%b")
        return (dt.month, dt.day)
    except ValueError:
        pass
    
    # Try DD-Month (e.g., 12-November)
    try:
        dt = datetime.strptime(val, "%d-%B")
        return (dt.month, dt.day)
    except ValueError:
        pass
    
    # Try Mon-DD (e.g., Nov-12)
    try:
        dt = datetime.strptime(val, "%b-%d")
        return (dt.month, dt.day)
    except ValueError:
        pass
    
    # Try Month-DD (e.g., November-12)
    try:
        dt = datetime.strptime(val, "%B-%d")
        return (dt.month, dt.day)
    except ValueError:
        pass
    
    # Try DD/MM format (e.g., 12/11)
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})", val)
    if match:
        d1, d2 = int(match.group(1)), int(match.group(2))
        # Heuristic: if first number > 12, it's DD/MM, else MM/DD
        if d1 > 12 and 1 <= d2 <= 12:
            return (d2, d1)  # DD/MM
        elif d2 > 12 and 1 <= d1 <= 12:
            return (d1, d2)  # MM/DD
        elif 1 <= d1 <= 12 and 1 <= d2 <= 31:
            return (d1, d2)  # Assume MM/DD
        elif 1 <= d2 <= 12 and 1 <= d1 <= 31:
            return (d2, d1)  # Assume DD/MM
    
    return None


def _compute_yearless_date_range(
    df: pd.DataFrame, 
    date_col: str,
    train_pct: int = 60,
    test_pct: int = 20,
    validation_pct: int = 20,
    manual_cutoff_1: str = None,
    manual_cutoff_2: str = None
) -> Dict[str, Any]:
    """
    Compute min/max date range and cutoffs for year-less date formats.
    Sorts by month-day order (calendar order) and computes cutoffs based on row percentages.
    If manual cutoffs are provided, uses those instead.
    Returns the actual values at cutoff points.
    """
    # Get all values (not just sample) for proper cutoff computation
    all_values = df[date_col].dropna().astype(str).str.strip()
    if len(all_values) == 0:
        return {
            "min_date": None, 
            "max_date": None, 
            "cutoff_1": None, 
            "cutoff_2": None,
            "cutoff_1_display": None,
            "cutoff_2_display": None,
            "has_year": False,
            "warning": "No valid date values found",
            "total_rows": 0
        }
    
    # Parse year-less dates
    parsed_data = []  # List of (month, day, original_value, original_index)
    for idx, val in enumerate(all_values):
        result = _parse_yearless_date(val)
        if result:
            month, day = result
            parsed_data.append((month, day, val, idx))
    
    if len(parsed_data) == 0:
        return {
            "min_date": None, 
            "max_date": None, 
            "cutoff_1": None, 
            "cutoff_2": None,
            "cutoff_1_display": None,
            "cutoff_2_display": None,
            "has_year": False,
            "warning": "Could not parse date values",
            "total_rows": 0
        }
    
    # Sort by (month, day) to get calendar order
    sorted_data = sorted(parsed_data, key=lambda x: (x[0], x[1]))
    n = len(sorted_data)
    
    min_val = sorted_data[0][2]  # Original string value (earliest in calendar)
    max_val = sorted_data[-1][2]  # Original string value (latest in calendar)
    
    # Check if manual cutoffs are provided
    use_manual_cutoff_1 = manual_cutoff_1 and manual_cutoff_1.strip()
    use_manual_cutoff_2 = manual_cutoff_2 and manual_cutoff_2.strip() and validation_pct > 0
    
    if use_manual_cutoff_1:
        # Parse manual cutoff and find the split point
        cutoff_1_parsed = _parse_yearless_date(manual_cutoff_1)
        if cutoff_1_parsed:
            cutoff_1_key = (cutoff_1_parsed[0], cutoff_1_parsed[1])
            # Count rows <= cutoff_1
            train_end = sum(1 for d in sorted_data if (d[0], d[1]) <= cutoff_1_key)
            cutoff_1_display = manual_cutoff_1.strip()
        else:
            # Invalid manual cutoff, fall back to percentage
            train_end = int(n * train_pct / 100)
            train_end = max(1, min(train_end, n))
            cutoff_1_idx = train_end - 1
            cutoff_1_display = sorted_data[cutoff_1_idx][2] if cutoff_1_idx >= 0 else min_val
    else:
        # Compute cutoffs based on percentages
        train_end = int(n * train_pct / 100)
        train_end = max(1, min(train_end, n))
        cutoff_1_idx = train_end - 1
        cutoff_1_display = sorted_data[cutoff_1_idx][2] if cutoff_1_idx >= 0 else min_val
    
    if use_manual_cutoff_2:
        # Parse manual cutoff_2 and find the split point
        cutoff_2_parsed = _parse_yearless_date(manual_cutoff_2)
        if cutoff_2_parsed:
            cutoff_2_key = (cutoff_2_parsed[0], cutoff_2_parsed[1])
            # Count rows <= cutoff_2
            test_end = sum(1 for d in sorted_data if (d[0], d[1]) <= cutoff_2_key)
            test_end = max(train_end, test_end)  # Ensure test_end >= train_end
            cutoff_2_display = manual_cutoff_2.strip()
        else:
            # Invalid manual cutoff, fall back to percentage
            test_end = int(n * (train_pct + test_pct) / 100)
            test_end = max(train_end, min(test_end, n))
            cutoff_2_idx = test_end - 1
            cutoff_2_display = sorted_data[cutoff_2_idx][2] if cutoff_2_idx >= train_end else None
    else:
        # Compute based on percentages
        test_end = int(n * (train_pct + test_pct) / 100)
        test_end = max(train_end, min(test_end, n))
        cutoff_2_display = None
        if validation_pct > 0 and test_end < n:
            cutoff_2_idx = test_end - 1
            cutoff_2_display = sorted_data[cutoff_2_idx][2] if cutoff_2_idx >= train_end else None
    
    # Calculate row counts
    train_rows = train_end
    test_rows = test_end - train_end
    validation_rows = n - test_end if validation_pct > 0 else 0
    
    # Check for seasonal warnings
    warnings = []
    
    # For year-less dates, we check based on month span in the sorted data
    train_months = set(d[0] for d in sorted_data[:train_end])
    if len(train_months) < 3 and train_end > 0:
        warnings.append(f"Train: Covers only {len(train_months)} month(s). Consider including more months.")
    
    test_months = set(d[0] for d in sorted_data[train_end:test_end])
    if len(test_months) < 3 and len(sorted_data[train_end:test_end]) > 0:
        warnings.append(f"Test: Covers only {len(test_months)} month(s). Consider including more months.")
    
    if validation_pct > 0 and test_end < n:
        val_months = set(d[0] for d in sorted_data[test_end:])
        if len(val_months) < 3 and len(sorted_data[test_end:]) > 0:
            warnings.append(f"Validation: Covers only {len(val_months)} month(s). Consider including more months.")
    
    result = {
        "min_date": min_val,
        "max_date": max_val,
        "cutoff_1": None,  # No YYYY-MM-DD format cutoff
        "cutoff_2": None,
        "cutoff_1_display": cutoff_1_display,  # DD-Mon format for display
        "cutoff_2_display": cutoff_2_display,
        "has_year": False,
        "warning": "Date column does not contain year information. Split is based on calendar month-day order.",
        "total_rows": n,
        "train_rows": train_rows,
        "test_rows": test_rows,
        "validation_rows": validation_rows,
        "manual_cutoff_active": use_manual_cutoff_1 or use_manual_cutoff_2,
    }
    
    if warnings:
        result["seasonal_warning"] = " | ".join(warnings)
    
    return result


def _check_seasonal_warning(partition_dates: pd.Series) -> Optional[str]:
    """
    Check if the smallest partition covers less than 3 months.
    Returns a warning message if seasonal patterns may be affected.
    """
    if len(partition_dates) == 0:
        return None
    
    min_date = partition_dates.min()
    max_date = partition_dates.max()
    
    if pd.isna(min_date) or pd.isna(max_date):
        return None
    
    # Calculate the span in months
    months_span = (max_date.year - min_date.year) * 12 + (max_date.month - min_date.month)
    
    if months_span < 3:
        return f"This partition covers only ~{months_span} month(s). Consider including at least 3 months to capture seasonal patterns."
    
    return None


def _compute_time_cutoffs(
    df: pd.DataFrame,
    date_col: str,
    train_pct: int,
    test_pct: int,
    validation_pct: int,
    manual_cutoff_1: str = None,
    manual_cutoff_2: str = None,
) -> Dict[str, Any]:
    """
    Compute cutoff dates at cumulative percentage boundaries.
    
    Logic:
    - Sort data by date_col
    - train_end = int(n * train_pct / 100)
    - test_end = int(n * (train_pct + test_pct) / 100)
    - cutoff_1 = date at index train_end - 1 (last date in Train)
    - cutoff_2 = date at index test_end - 1 (last date in Test)
    - If validation_pct = 0, hide cutoff_2 (all rows after cutoff_1 go to Test)
    - If manual cutoffs are provided, use those instead.
    """
    
    # First check if this is a year-less date format
    if _is_yearless_date_format(df, date_col):
        return _compute_yearless_date_range(df, date_col, train_pct, test_pct, validation_pct, manual_cutoff_1, manual_cutoff_2)
    
    # Try multiple date parsing approaches
    dt = pd.to_datetime(df[date_col], errors="coerce")
    
    # If standard parsing fails or results in invalid years, try common formats
    if dt.isna().all() or (dt.notna().any() and dt.dt.year.max() < 1950):
        for fmt in ["%y-%b", "%b-%y", "%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"]:
            try:
                test_dt = pd.to_datetime(df[date_col], format=fmt, errors="coerce")
                if test_dt.notna().any() and test_dt.dt.year.max() >= 1950:
                    dt = test_dt
                    break
            except Exception:
                continue
    
    # Create a temporary dataframe with parsed dates for sorting
    temp_df = df.copy()
    temp_df['_parsed_date'] = dt
    
    # Filter valid dates
    valid_mask = temp_df['_parsed_date'].notna() & (temp_df['_parsed_date'].dt.year >= 1900)
    valid_df = temp_df[valid_mask].copy()
    
    if len(valid_df) == 0:
        return {"min_date": None, "max_date": None, "cutoff_1": None, "cutoff_2": None, "has_year": True}

    # Sort by date column
    data_sorted = valid_df.sort_values(by='_parsed_date').reset_index(drop=True)
    n = len(data_sorted)
    
    mn = data_sorted['_parsed_date'].iloc[0]
    mx = data_sorted['_parsed_date'].iloc[-1]

    # Compute partition boundaries
    train_end = int(n * train_pct / 100)
    test_end = int(n * (train_pct + test_pct) / 100)
    
    # Ensure indices are within bounds
    train_end = max(1, min(train_end, n))
    test_end = max(train_end, min(test_end, n))
    
    # cutoff_1 = last date in Train (index train_end - 1)
    cutoff_1_idx = train_end - 1
    cutoff_1 = data_sorted['_parsed_date'].iloc[cutoff_1_idx] if cutoff_1_idx >= 0 else mn
    
    # cutoff_2 = last date in Test (index test_end - 1)
    # Only compute if validation_pct > 0
    cutoff_2 = None
    if validation_pct > 0 and test_end < n:
        cutoff_2_idx = test_end - 1
        cutoff_2 = data_sorted['_parsed_date'].iloc[cutoff_2_idx] if cutoff_2_idx >= train_end else None
    
    # Check for seasonal warnings on each partition
    warnings = []
    
    # Train partition: rows 0 to train_end-1
    train_dates = data_sorted['_parsed_date'].iloc[:train_end]
    train_warning = _check_seasonal_warning(train_dates)
    if train_warning:
        warnings.append(f"Train: {train_warning}")
    
    # Test partition: rows train_end to test_end-1
    test_dates = data_sorted['_parsed_date'].iloc[train_end:test_end]
    test_warning = _check_seasonal_warning(test_dates)
    if test_warning:
        warnings.append(f"Test: {test_warning}")
    
    # Validation partition: rows test_end to end (only if validation_pct > 0)
    if validation_pct > 0 and test_end < n:
        validation_dates = data_sorted['_parsed_date'].iloc[test_end:]
        validation_warning = _check_seasonal_warning(validation_dates)
        if validation_warning:
            warnings.append(f"Validation: {validation_warning}")
    
    result = {
        "min_date": mn.strftime("%Y-%m-%d") if pd.notna(mn) else None,
        "max_date": mx.strftime("%Y-%m-%d") if pd.notna(mx) else None,
        "cutoff_1": cutoff_1.strftime("%Y-%m-%d") if pd.notna(cutoff_1) else None,
        "cutoff_2": cutoff_2.strftime("%Y-%m-%d") if cutoff_2 is not None and pd.notna(cutoff_2) else None,
        "has_year": True,
        "total_rows": n,
        "train_rows": train_end,
        "test_rows": test_end - train_end,
        "validation_rows": n - test_end if validation_pct > 0 else 0,
    }
    
    # Add seasonal warning if any partition is < 3 months
    if warnings:
        result["seasonal_warning"] = " | ".join(warnings)
    
    return result


def build_partition_preview(
    df: pd.DataFrame,
    target_variable: str,
    split_configuration: Dict[str, Any],
) -> Dict[str, Any]:
    n = len(df)
    feature_cols = [c for c in df.columns if c != target_variable]
    n_features = len(feature_cols)

    split = _split_indices_from_config(df, target_variable, split_configuration, seed=42)
    if split is None:
        return {"success": False, "error": "Invalid split configuration or method."}

    train_idx, test_idx, validation_idx = split
    keys = ["train", "test", "validation"]
    idx_map = {"train": train_idx, "test": test_idx, "validation": validation_idx}

    method = split_configuration.get("split_method")
    date_col = split_configuration.get("date_column") if method == "time_based" else None

    computed_cutoffs = None
    if method == "time_based" and date_col and date_col in df.columns:
        ratios = split_configuration.get("ratios") or {}
        tr = int(ratios.get("train", 60))
        te = int(ratios.get("test", 20))
        va = int(ratios.get("validation", 20))
        manual_cutoff_1 = split_configuration.get("cutoff_1")
        manual_cutoff_2 = split_configuration.get("cutoff_2")
        computed_cutoffs = _compute_time_cutoffs(df, date_col, tr, te, va, manual_cutoff_1, manual_cutoff_2)

    target_in_df = target_variable in df.columns
    y = df[target_variable] if target_in_df else None

    event_mask_full, event_label = (None, None)
    target_kind = "unknown"
    if y is not None:
        if pd.api.types.is_numeric_dtype(y) and y.nunique() > 10:
            target_kind = "regression"
        elif y.nunique() == 2:
            target_kind = "binary"
            be = _binary_event_mask(y)
            if be:
                event_mask_full, event_label = be
        elif y.nunique() > 2 and y.nunique() <= 50:
            target_kind = "multiclass"
        else:
            target_kind = "regression"

    partitions: List[Dict[str, Any]] = []
    overall_event_rate: Optional[float] = None
    if target_kind == "binary" and event_mask_full is not None:
        overall_event_rate = float(np.sum(event_mask_full.to_numpy())) / max(n, 1) * 100.0

    for key in keys:
        idx = idx_map[key]
        valid_idx = idx[idx < len(df)]
        sub = df.iloc[valid_idx]
        rc = int(len(sub))
        prop = (rc / n * 100.0) if n else 0.0
        part: Dict[str, Any] = {
            "key": key,
            "row_count": rc,
            "proportion_pct": round(prop, 2),
        }
        if date_col:
            part["date_range"] = _format_date_range(sub, date_col)

        if target_kind == "binary" and event_mask_full is not None and rc > 0:
            em_arr = event_mask_full.to_numpy()
            em = em_arr[valid_idx]
            ev = int(em.sum())
            part["event_count"] = ev
            part["event_rate_pct"] = round(float(ev) / rc * 100.0, 2) if rc else 0.0
            part["non_event_count"] = rc - ev
        elif target_kind == "regression" and target_in_df and rc > 0:
            vals = pd.to_numeric(sub[target_variable], errors="coerce").dropna()
            if len(vals):
                part["target_mean"] = round(float(vals.mean()), 4)
                part["target_median"] = round(float(vals.median()), 4)
                part["target_std"] = round(float(vals.std()), 4)
        elif target_kind == "multiclass" and target_in_df and rc > 0:
            vc = sub[target_variable].value_counts().head(10)
            part["class_counts"] = {str(k): int(v) for k, v in vc.items()}

        partitions.append(part)

    result = {
        "success": True,
        "total_rows": n,
        "features": n_features,
        "target_kind": target_kind,
        "event_label": event_label,
        "overall_event_rate_pct": round(overall_event_rate, 2) if overall_event_rate is not None else None,
        "partitions": partitions,
    }
    if computed_cutoffs:
        result["computed_cutoffs"] = computed_cutoffs
    return result

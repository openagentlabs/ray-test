from typing import Dict, Any, List, Optional, Tuple  
import numpy as np  
import pandas as pd  
import scipy.sparse as sp  
from pandas.api.types import is_numeric_dtype, is_object_dtype, is_categorical_dtype  
  
from app.core.logging_config import get_logger  
from app.services.dataframe_state_manager import dataframe_state_manager  
from app.utils.helpers import (  
    _qcut_numeric,  
    _group_counts_for_iv,  
    _compute_woe_iv_bins,  
    _coerce_binary_target,  
)  
  
  
class FeatureEngineeringService:  
    """  
    Applies feature engineering transformations to the latest DataFrame and  
    persists the updated DataFrame via DataFrameStateManager.  
  
    Supported methods per variable:  
    - "LOG": numerical only; creates {var}_transform_log using log1p  
    - "OHE": categorical only; creates {var}_transform_OHE_<category>  
    - "WOE": both types; numeric binned via quantiles; creates {var}_transform_woe  
    """  
  
    def __init__(self):  
        self.logger = get_logger(__name__)  
  
    # ==================================================================  
    # PUBLIC ENTRY POINT  
    # ==================================================================  
    def apply_transformations(  
        self,  
        dataset_id: str,  
        df: pd.DataFrame,  
        plan: List[Dict[str, Any]],  
        target_variable: Optional[str] = None,  
        weight_variable: Optional[str] = None,  
        woe_bins: int = 10,  
        selected_segments: Optional[List[int]] = None,  
        scope: str = "dev",  
        stored_metadata: Optional[Dict[str, Dict[str, dict]]] = None,  
        persist: bool = True,  
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Dict[str, dict]]]]:  
        """  
        Apply feature engineering transformations.  
  
        Scope modes:  
        - "dev": Fit parameters and apply to dev data, collect metadata  
        - "hold": Apply using stored metadata from dev  
        - "entire": Fit parameters and apply to entire dataset  
  
        Weight variable handling:  
        - weight_variable is a protected column like target_variable  
        - It must NOT be transformed (no WoE, OHE, LOG, imputation)  
        - It is carried through untouched for downstream model training  
  
        Returns: (ui_rows, metadata)  
        - metadata is returned only for "dev" scope  
        """  
        transformed = df.copy(deep=False)  
        ui_rows: List[Dict[str, Any]] = []  
        collected_metadata: Dict[str, Dict[str, dict]] = {}
        
        # Filter out weight_variable from plan - it must never be transformed
        if weight_variable:
            plan = [p for p in plan if p.get("variable") != weight_variable]
            self.logger.info(f"Weight variable '{weight_variable}' excluded from feature engineering")  
  
        segment_mode = (  
            selected_segments is not None and len(selected_segments) > 0  
        )  
        is_fit_mode = scope in ["dev", "entire"]  
  
        # --------------------------------------------------------------  
        # SEGMENT-WISE PROCESSING  
        # --------------------------------------------------------------  
        if segment_mode:  
            if "segment" not in transformed.columns:  
                raise ValueError(  
                    "Segment-wise feature engineering requested "  
                    "but 'segment' column not found."  
                )  
  
            unique_selected = [int(s) for s in selected_segments]  
            segment_groups = transformed.groupby("segment").groups  
  
            for seg_id in unique_selected:  
                seg_id_int = int(seg_id)  
  
                if seg_id_int not in segment_groups:  
                    self.logger.warning(  
                        f"Segment {seg_id} has no rows; skipping."  
                    )  
                    continue  
  
                work_idx = segment_groups[seg_id_int]  
  
                if len(work_idx) == 0:  
                    self.logger.warning(  
                        f"Segment {seg_id} has no rows; skipping."  
                    )  
                    continue  
  
                work_view = transformed.loc[work_idx]  
  
                if is_fit_mode:  
                    transformed = self._fit_and_assign_for_view(  
                        transformed=transformed,  
                        work_idx=work_idx,  
                        work_view=work_view,  
                        plan=plan or [],  
                        segment_id=seg_id,  
                        collected_metadata=collected_metadata,  
                        ui_rows=ui_rows,  
                        target_variable=target_variable,  
                        woe_bins=woe_bins,  
                        df_original=df,  
                    )  
                else:  
                    transformed = self._apply_from_meta_for_view(  
                        transformed=transformed,  
                        work_idx=work_idx,  
                        work_view=work_view,  
                        plan=plan or [],  
                        segment_id=seg_id,  
                        stored_metadata=stored_metadata,  
                    )  
  
        # --------------------------------------------------------------  
        # GLOBAL PROCESSING (no segments)  
        # --------------------------------------------------------------  
        else:  
            work_idx = transformed.index  
            work_view = transformed  
  
            if is_fit_mode:  
                transformed = self._fit_and_assign_for_view(  
                    transformed=transformed,  
                    work_idx=work_idx,  
                    work_view=work_view,  
                    plan=plan or [],  
                    segment_id=None,  
                    collected_metadata=collected_metadata,  
                    ui_rows=ui_rows,  
                    target_variable=target_variable,  
                    woe_bins=woe_bins,  
                    df_original=df,  
                )  
            else:  
                transformed = self._apply_from_meta_for_view(  
                    transformed=transformed,  
                    work_idx=work_idx,  
                    work_view=work_view,  
                    plan=plan or [],  
                    segment_id=None,  
                    stored_metadata=stored_metadata,  
                )  
  
        # --------------------------------------------------------------  
        # PERSIST RESULT  
        # --------------------------------------------------------------  
        if persist:  
            dataframe_state_manager.update_dataframe(  
                dataset_id, transformed, original_shape=df.shape  
            )  

            # In split mode, FE may run on a subset view (dev/hold). Model training typically
            # loads the master "entire" dataset, so we must also merge newly-created
            # transformation columns into the master to make them available downstream.
            if scope in ("dev", "hold"):
                try:
                    self._merge_transforms_into_master_entire(dataset_id, transformed)
                except Exception as e:
                    self.logger.warning(f"Failed to merge transformed columns into master entire dataset: {e}")

  
            stored_df = dataframe_state_manager.get_dataframe(dataset_id)  
            if stored_df is not None:  
                self.logger.info(  
                    f"✅ Feature engineering completed. "  
                    f"Transformed dataframe stored with shape: {stored_df.shape}"  
                )  
  
                # Check for transformed columns  
                transformed_cols = [  
                    col for col in stored_df.columns if "transform" in col  
                ]  
                if transformed_cols:  
                    self.logger.info(  
                        f"✅ Transformed columns available: {transformed_cols}"  
                    )  
                else:  
                    self.logger.warning(  
                        f"⚠️ No transformed columns found in stored dataframe"  
                    )  
  
                # Verify no columns are lost  
                original_cols = set(df.columns)  
                stored_cols = set(stored_df.columns)  
                if original_cols.issubset(stored_cols):  
                    self.logger.info(  
                        f"✅ All original columns preserved. "  
                        f"Original: {len(original_cols)}, "  
                        f"Stored: {len(stored_cols)}"  
                    )  
                else:  
                    missing_cols = original_cols - stored_cols  
                    self.logger.error(  
                        f"❌ Missing original columns: {missing_cols}"  
                    )  
            else:  
                self.logger.error(  
                    f"❌ Failed to store transformed dataframe in state manager"  
                )  
  
        # Return ui_rows and metadata  
        # metadata is populated only for "dev" scope (for later hold application)  
        return ui_rows, (collected_metadata if scope == "dev" else None)  
  
    def _merge_transforms_into_master_entire(self, dataset_id: str, view_df: pd.DataFrame) -> None:
        """Merge transformation columns from a scoped view (dev/hold) into master entire dataframe.

        This is required because training services often load the "entire" dataframe from
        DataFrameStateManager. When feature engineering runs in split mode, it operates
        on a row-subset view; without merging, newly created columns exist only in the
        scoped copy and are invisible to training.

        NOTE: This method avoids partial assignment into sparse columns.
        """
        # Need a master dataframe to merge into
        master = dataframe_state_manager._transformed_copies.get(dataset_id, {}).get("entire")
        if master is None:
            master = dataframe_state_manager._full_dataframes.get(dataset_id)
        if master is None or master.empty:
            return

        # Only merge transformation columns
        transform_cols = [c for c in view_df.columns if "transform" in c]
        if not transform_cols:
            return

        # Align by index labels; view_df was created as master.iloc[idx].copy(), so labels match
        pos = master.index.get_indexer(view_df.index)
        valid = pos >= 0
        if not np.any(valid):
            return
        pos = pos[valid]
        view_index = view_df.index[valid]

        updated_master = master.copy()
        for col in transform_cols:
            s = view_df.loc[view_index, col]

            is_sparse = False
            try:
                is_sparse = isinstance(s.dtype, pd.SparseDtype)
            except Exception:
                is_sparse = False

            if is_sparse:
                base = np.zeros(len(updated_master), dtype=np.int8)
                try:
                    vals = s.to_numpy(dtype=np.int8, copy=False)
                except Exception:
                    vals = np.asarray(s.values, dtype=np.int8)
                n = min(len(pos), len(vals))
                base[pos[:n]] = vals[:n]
                updated_master[col] = pd.arrays.SparseArray(base, fill_value=0)
            else:
                # Numeric transforms (LOG/WOE) are float with NaNs outside the subset
                try:
                    vals = s.to_numpy(copy=False)
                except Exception:
                    vals = np.asarray(s.values)

                if col not in updated_master.columns:
                    # initialize column full-length
                    if pd.api.types.is_numeric_dtype(s):
                        base = np.full(len(updated_master), np.nan, dtype=float)
                        base[pos[: len(vals)]] = vals[: len(pos)]
                        updated_master[col] = base
                    else:
                        # fallback object
                        base_obj = np.array([None] * len(updated_master), dtype=object)
                        base_obj[pos[: len(vals)]] = vals[: len(pos)]
                        updated_master[col] = base_obj
                else:
                    # Existing column: safe for non-sparse via .loc assignment
                    updated_master.loc[view_index, col] = s

        # Persist merged master under entire scope
        dataframe_state_manager.update_dataframe(dataset_id=dataset_id, df=updated_master, force_scope="entire")

    # ==================================================================  
    # FIT MODE - Class method (processes entire plan, batches OHE)  
    # ==================================================================  
    def _fit_and_assign_for_view(  
        self,  
        transformed: pd.DataFrame,  
        work_idx: pd.Index,  
        work_view: pd.DataFrame,  
        plan: List[Dict[str, Any]],  
        segment_id: Optional[int],  
        collected_metadata: Dict[str, Dict[str, dict]],  
        ui_rows: List[Dict[str, Any]],  
        target_variable: Optional[str],  
        woe_bins: int,  
        df_original: pd.DataFrame,  
    ) -> pd.DataFrame:  
        """  
        Process ALL plan items for a single segment/global view.  
        OHE results are batched and assigned in a single operation at the end  
        to avoid repeated DataFrame column expansion.  
  
        Returns:  
            Updated transformed DataFrame (may be a new object if OHE columns added)  
        """  
        # Collector for OHE results - batched assignment at the end  
        ohe_batch: List[Tuple[pd.DataFrame, str, Optional[int]]] = []  
  
        seg_suffix = f"_seg{segment_id}" if segment_id is not None else ""  
        segment_key = (  
            f"seg{segment_id}" if segment_id is not None else "global"  
        )  
  
        for item in plan:  
            # ----------------------------------------------------------  
            # 1. Extract variable name and methods from plan item  
            # ----------------------------------------------------------  
            var = item.get("variable") or item.get("variable_name")  
            methods_source = (  
                item.get("transformation_methods")  
                if item.get("transformation_methods") is not None  
                else item.get("methods")  
            )  
            norm_methods = self._normalize_methods(methods_source)  
  
            # Skip if variable is invalid or not in the current view  
            if not var or var not in work_view.columns:  
                self.logger.warning(  
                    f"FE: Variable not found or invalid: {var}"  
                )  
                continue  
  
            # ----------------------------------------------------------  
            # 2. Resolve dtype and variable definition from plan metadata  
            # ----------------------------------------------------------  
            plan_var_type, plan_var_def = self._extract_plan_metadata(item)  
            dtype = plan_var_type or (  
                "Numerical"  
                if is_numeric_dtype(work_view[var])  
                else "Categorical"  
            )  
            if dtype:  
                dtype_lower = dtype.lower()  
                if dtype_lower in ("num", "numeric"):  
                    dtype = "Numerical"  
                elif dtype_lower in ("char", "character", "cat"):  
                    dtype = "Categorical"  
  
            # ----------------------------------------------------------  
            # 3. Ensure metadata dicts exist for this segment and variable  
            # ----------------------------------------------------------  
            if segment_key not in collected_metadata:  
                collected_metadata[segment_key] = {}  
            if var not in collected_metadata[segment_key]:  
                collected_metadata[segment_key][var] = {}  
  
            # ----------------------------------------------------------  
            # 4. LOG TRANSFORMATION  
            # ----------------------------------------------------------  
            if "LOG" in norm_methods and is_numeric_dtype(work_view[var]):  
                log_series, log_meta = self._log_transform(work_view[var])  
                new_col = f"{var}{seg_suffix}_transform_log"  
  
                if new_col not in transformed.columns:  
                    transformed[new_col] = np.nan  
  
                transformed.loc[work_idx, new_col] = log_series.values  
  
                collected_metadata[segment_key][var]["LOG"] = {  
                    "method": "log1p",  
                    "shift": log_meta.get("shift", 0.0),  
                }  
  
                ui_rows.append(  
                    self._build_log_ui_row(  
                        var, dtype, plan_var_def, log_meta, segment_id  
                    )  
                )  
  
            # ----------------------------------------------------------  
            # 5. ONE HOT ENCODING - COLLECT, DO NOT ASSIGN YET  
            # ----------------------------------------------------------  
            if "OHE" in norm_methods and (  
                is_object_dtype(work_view[var])  
                or is_categorical_dtype(work_view[var])  
            ):  
                ohe_df, ohe_meta = self._one_hot_encode(  
                    work_view[var], var  
                )  
  
                # Collect for batched assignment later  
                ohe_batch.append((ohe_df, seg_suffix, segment_id))  
  
                collected_metadata[segment_key][var]["OHE"] = {  
                    "categories": ohe_meta.get("categories", []),  
                }  
  
                ui_rows.extend(  
                    self._build_ohe_ui_rows(  
                        var, dtype, plan_var_def, ohe_meta, segment_id  
                    )  
                )  
  
            # ----------------------------------------------------------  
            # 6. WOE TRANSFORMATION  
            # ----------------------------------------------------------  
            if "WOE" in norm_methods:  
                if (  
                    not target_variable  
                    or target_variable not in work_view.columns  
                ):  
                    raise ValueError(  
                        "WOE requires a valid target_variable "  
                        "present in the DataFrame"  
                    )  
  
                y = _coerce_binary_target(work_view[target_variable])  
                if y is None:  
                    raise ValueError(  
                        "WOE requires binary target (0/1, bool, or yes/no)"  
                    )  
  
                woe_series, woe_meta = self._woe_from_existing_logic(  
                    feature=work_view[var], y=y, bins=woe_bins  
                )  
                new_col = f"{var}{seg_suffix}_transform_woe"  
  
                if new_col not in transformed.columns:  
                    transformed[new_col] = np.nan  
  
                transformed.loc[work_idx, new_col] = woe_series.values  
  
                collected_metadata[segment_key][var]["WOE"] = woe_meta  
  
                ui_rows.append(  
                    self._build_woe_ui_row(  
                        var,  
                        dtype,  
                        plan_var_def,  
                        df_original[var],  
                        woe_meta,  
                        segment_id,  
                    )  
                )  
  
        # ==============================================================  
        # 7. BATCH OHE ASSIGNMENT - single DataFrame expansion  
        # ==============================================================  
        if ohe_batch:  
            transformed = self._batch_ohe_assign(  
                transformed=transformed,  
                work_idx=work_idx,  
                ohe_results=ohe_batch,  
            )  
  
        return transformed  
  
    # ==================================================================  
    # BATCH OHE ASSIGN - shared by both fit and hold modes  
    # ==================================================================  
    def _batch_ohe_assign(  
        self,  
        transformed: pd.DataFrame,  
        work_idx: pd.Index,  
        ohe_results: List[Tuple[pd.DataFrame, str, Optional[int]]],  
    ) -> pd.DataFrame:  
        if not ohe_results:  
            return transformed  
  
        all_data_frames: List[pd.DataFrame] = []  
        for ohe_df, seg_suffix, segment_id in ohe_results:  
            if segment_id is not None:  
                ohe_df = ohe_df.copy()  
                ohe_df.columns = [  
                    c.replace(  
                        "_transform_OHE",  
                        f"_seg{segment_id}_transform_OHE",  
                    )  
                    for c in ohe_df.columns  
                ]  
            all_data_frames.append(ohe_df)  
  
        combined_ohe = pd.concat(all_data_frames, axis=1)  
        existing = set(transformed.columns)  
        new_cols = [c for c in combined_ohe.columns if c not in existing]  
  
        use_sparse = False  
        try:  
            use_sparse = any(  
                isinstance(combined_ohe[c].dtype, pd.SparseDtype)  
                for c in combined_ohe.columns  
            )  
        except Exception:  
            use_sparse = False  
  
        if new_cols and not use_sparse:  
            batch_size = 200  
            for i in range(0, len(new_cols), batch_size):  
                transformed.loc[:, new_cols[i : i + batch_size]] = 0  
  
        if use_sparse:  
            pos = transformed.index.get_indexer(work_idx)  
            valid_pos = pos >= 0  
            if not np.all(valid_pos):  
                pos = pos[valid_pos]  
  
            try:  
                sub_coo = combined_ohe.sparse.to_coo()  
                full_rows = pos[sub_coo.row]  
                full_cols = sub_coo.col  
                full_data = sub_coo.data.astype(np.int8, copy=False)  
  
                full_mat = sp.csr_matrix(  
                    (full_data, (full_rows, full_cols)),  
                    shape=(len(transformed), sub_coo.shape[1]),  
                    dtype=np.int8,  
                )  
                full_df = pd.DataFrame.sparse.from_spmatrix(  
                    full_mat,  
                    index=transformed.index,  
                    columns=combined_ohe.columns,  
                )  
                try:  
                    full_df = full_df.astype(pd.SparseDtype("int", 0))  
                except Exception:  
                    pass  
  
                transformed.loc[:, combined_ohe.columns] = full_df  
            except Exception:  
                for c in combined_ohe.columns:  
                    base = np.zeros(len(transformed), dtype=np.int8)  
                    try:  
                        vals = combined_ohe[c].to_numpy(dtype=np.int8, copy=False)  
                    except Exception:  
                        vals = np.asarray(combined_ohe[c].values, dtype=np.int8)  
  
                    n = min(len(pos), len(vals))  
                    base[pos[:n]] = vals[:n]  
                    transformed[c] = pd.arrays.SparseArray(base, fill_value=0)  
        else:  
            transformed.loc[work_idx, combined_ohe.columns] = (  
                combined_ohe.to_numpy(dtype=np.int8, copy=False)  
            )  
  
        return transformed  
  
    def _apply_from_meta_for_view(  
        self,  
        transformed: pd.DataFrame,  
        work_idx: pd.Index,  
        work_view: pd.DataFrame,  
        plan: List[Dict[str, Any]],  
        segment_id: Optional[int],  
        stored_metadata: Optional[Dict[str, Dict[str, dict]]],  
    ) -> pd.DataFrame:  
        if not stored_metadata:  
            return transformed  
  
        seg_suffix = f"_seg{segment_id}" if segment_id is not None else ""  
        segment_key = (  
            f"seg{segment_id}" if segment_id is not None else "global"  
        )  
        seg_meta = stored_metadata.get(segment_key) or {}  
  
        ohe_batch: List[Tuple[pd.DataFrame, str, Optional[int]]] = []  
  
        for item in plan:  
            var = item.get("variable") or item.get("variable_name")  
            methods_source = (  
                item.get("transformation_methods")  
                if item.get("transformation_methods") is not None  
                else item.get("methods")  
            )  
            norm_methods = self._normalize_methods(methods_source)  
  
            if not var or var not in work_view.columns:  
                continue  
  
            var_meta = seg_meta.get(var) or {}  
  
            if "LOG" in norm_methods and "LOG" in var_meta:  
                new_col = f"{var}{seg_suffix}_transform_log"  
                if new_col not in transformed.columns:  
                    transformed[new_col] = np.nan  
                s = self._apply_log_with_meta(work_view[var], var_meta["LOG"])  
                transformed.loc[work_idx, new_col] = s.values  
  
            if "WOE" in norm_methods and "WOE" in var_meta:  
                new_col = f"{var}{seg_suffix}_transform_woe"  
                if new_col not in transformed.columns:  
                    transformed[new_col] = np.nan  
                s = self._apply_woe_from_meta(work_view[var], var_meta["WOE"])  
                transformed.loc[work_idx, new_col] = s.values  
  
            if "OHE" in norm_methods and "OHE" in var_meta:  
                col_names, mat = self._apply_ohe_with_meta(  
                    s=work_view[var],  
                    var_name=var,  
                    meta=var_meta["OHE"],  
                    segment_id=segment_id,  
                )  
                if col_names:  
                    ohe_df = pd.DataFrame(mat, index=work_idx, columns=col_names)  
                    for c in ohe_df.columns:  
                        ohe_df[c] = pd.arrays.SparseArray(  
                            ohe_df[c].to_numpy(dtype=np.int8, copy=False),  
                            fill_value=0,  
                        )  
                    ohe_batch.append((ohe_df, "", segment_id))  
  
        if ohe_batch:  
            transformed = self._batch_ohe_assign(  
                transformed=transformed,  
                work_idx=work_idx,  
                ohe_results=ohe_batch,  
            )  
  
        return transformed  
  
    def _apply_log_with_meta(self, s: pd.Series, meta: Dict[str, Any]) -> pd.Series:
        s_num = pd.to_numeric(s, errors="coerce")
        shift = float(meta.get("shift", 0.0))
        result = np.log1p(s_num + shift)
        return np.round(result, 4)
  
    def _apply_ohe_with_meta(
        self,
        s: pd.Series,
        var_name: str,
        meta: Dict[str, Any],
        segment_id: Optional[int],
    ) -> Tuple[List[str], np.ndarray]:
        cats = [str(c) for c in (meta.get("categories") or [])]
        s_obj = s.astype("object").fillna("NA").astype(str)
        if len(cats) == 0:
            return [], np.zeros((len(s_obj), 0), dtype=int)

        cats_set = set(cats)
        has_other = "Other" in cats_set
        if has_other:
            # Vectorised via where + isin: ~38x faster than Series.apply over
            # 4M rows (see backend/docs/midas-4m-row-performance-analysis 1.md).
            s_obj = s_obj.where(s_obj.isin(cats_set), other="Other")

        seg_suffix = f"_seg{segment_id}" if segment_id is not None else ""
        if len(cats) == 1:
            col_names = [f"{var_name}{seg_suffix}_transform_OHE"]
        else:
            col_names = [
                f"{var_name}{seg_suffix}_transform_OHE_{i}"
                for i in range(1, len(cats) + 1)
            ]

        cats_index = pd.Index([str(c) for c in cats], dtype="object")
        s_cat = pd.Categorical(s_obj, categories=cats_index, ordered=False)
        codes = s_cat.codes

        mat = np.zeros((len(s_obj), len(cats_index)), dtype=int)
        if len(codes) > 0:
            rows = np.arange(len(codes))
            valid = codes >= 0
            if np.any(valid):
                mat[rows[valid], codes[valid]] = 1

        return col_names, mat

    def _apply_woe_from_meta(self, feature: pd.Series, woe_meta: Dict[str, Any]) -> pd.Series:
        woe_table = woe_meta.get("woe_table", {})
        case_type = woe_meta.get("type", "")
        if case_type == "numeric_binned" and is_numeric_dtype(feature):
            values = feature.astype(float)
            result = pd.Series(np.nan, index=feature.index, dtype="float64")

            intervals: List[Tuple[float, float, float]] = []
            for label, rec in woe_table.items():
                try:
                    text = str(label).strip()
                    text = (
                        text.replace("(", "")
                        .replace(")", "")
                        .replace("[", "")
                        .replace("]", "")
                        .replace(" ", "")
                    )
                    parts = text.split(",")
                    left = float("-inf" if parts[0] in {"-inf", "-Inf"} else parts[0])
                    right = float("inf" if parts[1] in {"inf", "Inf"} else parts[1])
                    intervals.append((left, right, float(rec.get("woe", 0.0))))
                except Exception:
                    continue

            intervals.sort(key=lambda x: (x[0], x[1]))
            for left, right, w in intervals:
                mask = pd.Series(True, index=values.index)
                if not np.isneginf(left):
                    mask &= values > left
                if not np.isposinf(right):
                    mask &= values <= right
                result.loc[mask & values.notna()] = w

            return result.fillna(0.0)

        s_obj = feature.astype("object").fillna("NA")
        mapping = {str(label): float(rec.get("woe", 0.0)) for label, rec in woe_table.items()}
        return s_obj.map(mapping).fillna(0.0).astype(float)

    def _log_transform(  
        self, s: pd.Series  
    ) -> Tuple[pd.Series, Dict[str, Any]]:  
        s_num = pd.to_numeric(s, errors="coerce")  
        min_val = s_num.min(skipna=True)  
        shift = (  
            float(abs(min_val) + 1.0)  
            if pd.notna(min_val) and min_val <= 0  
            else 0.0  
        )  
        result = np.log1p(s_num + shift)  
        result = np.round(result, 4)  
        return result, {"method": "log1p", "shift": shift}  
  
    def _one_hot_encode(  
        self, s: pd.Series, var_name: str, max_categories: int = 50  
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:  
        """  
        Memory-efficient OHE using scipy sparse intermediate.  
        Only densifies at the final assignment step.
        
        High-cardinality columns (> max_categories unique values) are limited:
        - Keep the top N-1 most frequent categories
        - Group all remaining categories into "Other"
        
        This prevents explosion of columns for high-cardinality features
        like job titles, addresses, etc.
        """  
        s_obj = s.astype("object").fillna("NA").astype(str)
        
        unique_count = s_obj.nunique()
        
        if unique_count > max_categories:
            self.logger.info(
                f"OHE: Column '{var_name}' has {unique_count} unique values, "
                f"limiting to top {max_categories - 1} + 'Other'"
            )
            value_counts = s_obj.value_counts()
            top_categories = set(value_counts.head(max_categories - 1).index)
            s_obj = s_obj.apply(lambda x: x if x in top_categories else "Other")
        
        dummies = pd.get_dummies(s_obj, dtype=np.int8, sparse=True)

        cats_sorted = pd.Index(sorted(dummies.columns.astype(str)), dtype="object")
        dummies = dummies[cats_sorted]
        n_cats = len(cats_sorted)

        if n_cats == 0:
            empty_df = pd.DataFrame(index=s.index)
            meta = {
                "categories": [],
                "n_categories": 0,
                "column_names": [],
            }
            return empty_df, meta

        if n_cats == 1:
            column_names = [f"{var_name}_transform_OHE"]
        else:
            column_names = [
                f"{var_name}_transform_OHE_{i}"
                for i in range(1, n_cats + 1)
            ]

        try:
            sparse_mat = dummies.sparse.to_coo().tocsr()
            dummies = pd.DataFrame.sparse.from_spmatrix(
                sparse_mat, index=s.index, columns=column_names
            )
        except Exception:
            dummies.columns = column_names
            for c in dummies.columns:
                dummies[c] = pd.arrays.SparseArray(
                    dummies[c].to_numpy(dtype=np.int8, copy=False),
                    fill_value=0,
                )
  
        # Force 0/1 int sparse dtype (avoid float sparse from pandas defaults)  
        try:  
            dummies = dummies.astype(pd.SparseDtype("int", 0))  
        except Exception:  
            pass  

  
        meta = {  
            "categories": [str(c) for c in cats_sorted],  
            "n_categories": n_cats,  
            "column_names": column_names,
            "max_categories": max_categories,
            "original_unique_count": unique_count,
        }  

        return dummies, meta
  
    def _woe_from_existing_logic(  
        self, feature: pd.Series, y: pd.Series, bins: int = 10  
    ) -> Tuple[pd.Series, Dict[str, Any]]:  
        """  
        Reuse the helpers' WOE/IV pipeline for both categorical  
        and numeric features.  
        """  
        if is_numeric_dtype(feature):  
            binned = _qcut_numeric(feature, bins)  
        else:  
            binned = feature.astype("object").fillna("NA")  
  
        grp = _group_counts_for_iv(binned, y)  
        pg, pb = self._compute_pg_pb_from_group(grp)  
        woe, iv_bin, iv_total = _compute_woe_iv_bins(pg, pb)  
  
        # Map back to original index (round WOE values to 4 decimal places)  
        woe_rounded = np.round(woe, 4)  
        woe_map = dict(  
            zip(grp["bin"].astype(str), woe_rounded.tolist())  
        )  
        # Vectorized mapping via astype(str).map for speed  
        woe_series = binned.astype(str).map(woe_map)  
  
        meta = {  
            "type": (  
                "numeric_binned"  
                if is_numeric_dtype(feature)  
                else "categorical"  
            ),  
            "iv_total": float(iv_total),  
            "woe_table": {  
                str(b): {  
                    "Total": int(t),  
                    "Event=1": int(e1),  
                    "Event=0": int(e0),  
                    "woe": float(w),  
                }  
                for b, t, e1, e0, w in zip(  
                    grp["bin"].astype(str).tolist(),  
                    grp["Total"].tolist(),  
                    grp["Event=1"].tolist(),  
                    grp["Event=0"].tolist(),  
                    woe_rounded.tolist(),  
                )  
            },  
        }  
        return woe_series, meta  
  
    def _compute_pg_pb_from_group(  
        self, grp: pd.DataFrame  
    ) -> Tuple[pd.Series, pd.Series]:  
        good_sum = grp["Event=1"].sum()  
        bad_sum = grp["Event=0"].sum()  
        pg = (  
            grp["Event=1"] / good_sum  
            if good_sum != 0  
            else pd.Series(np.zeros(len(grp)))  
        )  
        pb = (  
            grp["Event=0"] / bad_sum  
            if bad_sum != 0  
            else pd.Series(np.zeros(len(grp)))  
        )  
        return pg, pb  
  
    # ==================================================================  
    # Small builders / normalizers to simplify main flow  
    # ==================================================================  
    def _normalize_methods(self, methods: Optional[Any]) -> List[str]:  
        if isinstance(methods, str):  
            parts = [p.strip() for p in methods.split(",") if p.strip()]  
        else:  
            parts = [str(m).strip() for m in (methods or [])]  
  
        raw_methods = [p.lower() for p in parts]  
        norm_methods: List[str] = []  
  
        for m in raw_methods:  
            if m in ("woe", "woe_transformation"):  
                norm_methods.append("WOE")  
            elif m in ("log", "log_transformation"):  
                norm_methods.append("LOG")  
            elif m in ("ohe", "one_hot_encoding"):  
                norm_methods.append("OHE")  
            elif m in ("no_transformation", "none", ""):  
                continue  
  
        return norm_methods  
  
    def _extract_plan_metadata(  
        self, item: Dict[str, Any]  
    ) -> Tuple[Optional[str], Optional[str]]:  
        """  
        Extract 'Var Type' and 'Variable definition' from plan item  
        with flexible keys.  
        Returns (var_type, variable_definition) or (None, None).  
        """  
        var_type = (  
            item.get("var_type")  
            or item.get("Var Type")  
            or item.get("VarType")  
            or item.get("variable_type")  
        )  
        var_def = (  
            item.get("variable_definition")  
            or item.get("Variable definition")  
            or item.get("VariableDefinition")  
        )  
  
        if isinstance(var_type, str):  
            var_type = var_type.strip()  
        if isinstance(var_def, str):  
            var_def = var_def.strip()  
  
        return (  
            var_type if var_type else None,  
            var_def if var_def else None,  
        )  
  
    # ==================================================================  
    # UI row builders  
    # ==================================================================  
    def _build_log_ui_row(  
        self,  
        var: str,  
        dtype: str,  
        var_def: str,  
        log_meta: Dict[str, Any],  
        segment_id: Optional[int] = None,  
    ) -> Dict[str, Any]:  
        shift = log_meta.get("shift", 0.0)  
        seg_suffix = (  
            f"_seg{segment_id}" if segment_id is not None else ""  
        )  
        log_col = f"{var}{seg_suffix}_transform_log"  
        return {  
            "new_variable_name": log_col,  
            "var_type": dtype,  
            "variable_definition": var_def or "",  
            "transformation_methods": "Log transformation",  
            "code_logic": (  
                f"df['{log_col}'] = "  
                f"np.round(np.log1p(df['{var}'] + {shift:.4f}), 4)"  
            ),  
        }  
  
    def _build_woe_ui_row(  
        self,  
        var: str,  
        dtype: str,  
        var_def: str,  
        series: pd.Series,  
        woe_meta: Dict[str, Any],  
        segment_id: Optional[int] = None,  
    ) -> Dict[str, Any]:  
        seg_suffix = (  
            f"_seg{segment_id}" if segment_id is not None else ""  
        )  
        woe_col = f"{var}{seg_suffix}_transform_woe"  
        return {  
            "new_variable_name": woe_col,  
            "var_type": dtype,  
            "variable_definition": var_def or "",  
            "transformation_methods": "WOE transformation",  
            "code_logic": self._build_woe_code_logic(  
                var, series, woe_meta, segment_id  
            ),  
        }  
  
    def _build_ohe_ui_rows(  
        self,  
        var: str,  
        dtype: str,  
        var_def: str,  
        ohe_meta: Dict[str, Any],  
        segment_id: Optional[int] = None,  
    ) -> List[Dict[str, Any]]:  
        cats = ohe_meta.get("categories", [])  
        col_names = ohe_meta.get("column_names", [])  
        seg_suffix = (  
            f"_seg{segment_id}" if segment_id is not None else ""  
        )  
        rows: List[Dict[str, Any]] = []  
  
        if not cats:  
            return rows  
  
        if len(cats) == 1:  
            ohe_col = (  
                col_names[0]  
                if col_names  
                else f"{var}_transform_OHE"  
            )  
            ohe_col = ohe_col.replace(  
                f"{var}_transform_OHE",  
                f"{var}{seg_suffix}_transform_OHE",  
            )  
            cat = cats[0]  
            rows.append(  
                {  
                    "new_variable_name": ohe_col,  
                    "var_type": dtype,  
                    "variable_definition": var_def or "",  
                    "transformation_methods": "One Hot Encoding",  
                    "code_logic": (  
                        f"df['{ohe_col}'] = "  
                        f"(df['{var}'].fillna('NA') == '{cat}').astype(int)"  
                    ),  
                }  
            )  
            return rows  
  
        for c, ohe_col in zip(cats, col_names):  
            # Apply segment suffix to column name  
            ohe_col = ohe_col.replace(  
                f"{var}_transform_OHE",  
                f"{var}{seg_suffix}_transform_OHE",  
            )  
            rows.append(  
                {  
                    "new_variable_name": ohe_col,  
                    "var_type": dtype,  
                    "variable_definition": var_def or "",  
                    "transformation_methods": "One Hot Encoding",  
                    "code_logic": (  
                        f"df['{ohe_col}'] = "  
                        f"(df['{var}'].fillna('NA') == '{c}').astype(int)"  
                    ),  
                }  
            )  
  
        return rows  
  
    # ==================================================================  
    # WOE code logic builder (for UI display)  
    # ==================================================================  
    def _build_woe_code_logic(  
        self,  
        var_name: str,  
        series: pd.Series,  
        woe_meta: Dict[str, Any],  
        segment_id: Optional[int] = None,  
    ) -> str:  
        """  
        Create readable Python-like logic to compute WOE for the  
        given feature. Handles numeric (binned) and categorical cases.  
        """  
        if not woe_meta or "woe_table" not in woe_meta:  
            return ""  
  
        woe_table = woe_meta.get("woe_table", {})  
        case_type = woe_meta.get("type", "")  
  
        seg_suffix = (  
            f"_seg{segment_id}" if segment_id is not None else ""  
        )  
  
        original_var = var_name  
        transformed_var = f"{var_name}{seg_suffix}_transform_woe"  
  
        # Numeric binned intervals like '(a, b]'  
        if case_type == "numeric_binned" and is_numeric_dtype(series):  
            intervals: List[Tuple[float, float, float]] = []  
            for label, rec in woe_table.items():  
                try:  
                    text = str(label).strip()  
                    text = (  
                        text.replace("(", "")  
                        .replace(")", "")  
                        .replace("[", "")  
                        .replace("]", "")  
                        .replace(" ", "")  
                    )  
                    parts = text.split(",")  
                    left = float(  
                        "-inf"  
                        if parts[0] in {"-inf", "-Inf"}  
                        else parts[0]  
                    )  
                    right = float(  
                        "inf"  
                        if parts[1] in {"inf", "Inf"}  
                        else parts[1]  
                    )  
                    intervals.append(  
                        (left, right, float(rec.get("woe", 0.0)))  
                    )  
                except Exception:  
                    continue  
  
            intervals.sort(key=lambda x: (x[0], x[1]))  
  
            lines = [  
                f"# WOE for {original_var}",  
                f"{original_var} = df['{original_var}']",  
                f"{transformed_var} = np.nan",  
            ]  
            for i, (left, right, w) in enumerate(intervals):  
                cond_parts = []  
                if not np.isneginf(left):  
                    cond_parts.append(f"{original_var} > {left}")  
                if not np.isposinf(right):  
                    cond_parts.append(f"{original_var} <= {right}")  
                cond = (  
                    " and ".join(cond_parts)  
                    if cond_parts  
                    else f"~{original_var}.isna()"  
                )  
                prefix = "if" if i == 0 else "elif"  
                lines.append(  
                    f"{prefix} ({cond}): {transformed_var} = {w:.4f}"  
                )  
  
            lines.append(f"df['{transformed_var}'] = {transformed_var}")  
            return "\n".join(lines)  
  
        # Categorical  
        lines = [  
            f"# WOE for {original_var}",  
            f"{original_var} = df['{original_var}'].fillna('NA')",  
            f"{transformed_var} = 0.0",  
        ]  
        first = True  
        for label, rec in woe_table.items():  
            prefix = "if" if first else "elif"  
            first = False  
            val = str(label).replace("'", "\\'")  
            lines.append(  
                f"{prefix} ({original_var} == '{val}'): "  
                f"{transformed_var} = {float(rec.get('woe', 0.0)):.4f}"  
            )  
  
        lines.append(f"df['{transformed_var}'] = {transformed_var}")  
        return "\n".join(lines)  
  
  
# ==================================================================  
# Module-level singleton  
# ==================================================================  
feature_engineering_service = FeatureEngineeringService()  
import pandas as pd
import numpy as np
import ast
import json
import os
import re
import uuid
import joblib
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from joblib import Parallel, delayed

from app.core.logging_config import get_logger
from app.services.dataframe_state_manager import dataframe_state_manager
from app.services.dataset_service import dataset_manager
from app.services.model_training_manual_configuration import ModelTrainingManualConfigurationService

logger = get_logger(__name__)

class SegmentTrainingManualConfigurationService:
    """Service for segment-specific model training with manual configuration"""

    def __init__(self):
        self.logger = logger
        self.model_storage_path = "models/segment_models/"
        self.base_service = ModelTrainingManualConfigurationService()
        os.makedirs(self.model_storage_path, exist_ok=True)

    @staticmethod
    def _segmentation_scheme_like_columns(df: pd.DataFrame) -> List[str]:
        cols: List[str] = []
        for c in df.columns:
            if not isinstance(c, str):
                continue
            if re.fullmatch(r"segmentation_scheme_\d+", c):
                cols.append(c)
            elif c.startswith("seg_") and len(c) > 4:
                cols.append(c)
        return sorted(set(cols))

    @staticmethod
    def _pick_default_scheme_column(scheme_cols: List[str], dataset_id: str, df: pd.DataFrame) -> Optional[str]:
        if not scheme_cols:
            return None
        try:
            schemes = dataset_manager.get_segmentation_schemes_metadata(dataset_id)
            for rec in reversed(list(schemes or [])):
                cn = (rec or {}).get("column_name")
                if isinstance(cn, str) and cn in df.columns:
                    return cn
        except Exception:
            pass
        numbered = [c for c in scheme_cols if re.fullmatch(r"segmentation_scheme_\d+", c)]
        if numbered:
            return max(numbered, key=lambda c: int(c.rsplit("_", 1)[1]))
        return scheme_cols[0]

    def detect_segments(
        self, dataset_id: str, preferred_segment_column: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Detect if segmentation column exists and return segment distribution

        Args:
            dataset_id: ID of the dataset to check
            preferred_segment_column: Optional column name (e.g. segmentation_scheme_2) from UI

        Returns:
            Dictionary with segment information
        """
        try:
            df = dataframe_state_manager.get_dataframe(dataset_id)
            if df is None:
                return {'available': False, 'error': 'Dataset not found'}

            scheme_cols = self._segmentation_scheme_like_columns(df)
            segment_column: Optional[str] = None
            segment_column_candidates: List[str] = []

            pref = (preferred_segment_column or "").strip()
            if pref and pref in df.columns:
                segment_column = pref
                segment_column_candidates = scheme_cols[:] if scheme_cols else [pref]
                if pref not in segment_column_candidates:
                    segment_column_candidates = [pref] + segment_column_candidates
            elif scheme_cols:
                segment_column = self._pick_default_scheme_column(scheme_cols, dataset_id, df)
                segment_column_candidates = scheme_cols[:]
            else:
                legacy = ['segment', 'SEGMENT', 'segment_id', 'SEGMENT_ID']
                for col in legacy:
                    if col in df.columns:
                        segment_column = col
                        segment_column_candidates = [col]
                        self.logger.info(f"Found legacy segment column: {segment_column}")
                        break

            if segment_column is None:
                return {
                    'available': False,
                    'message': 'No segment column detected. Add to Data from Step 3.5 (segmentation_scheme_*) first.',
                    'suggestion': 'Run segmentation and use Add to Data, or add a segment / segmentation_scheme column.',
                }

            # Filter out NaN values to prevent JSON serialization errors
            segments = df[segment_column].dropna().unique()
            segment_counts = df[segment_column].value_counts(dropna=True)

            # Ensure segments is properly converted to list with native Python types
            segments_list = list(segments) if hasattr(segments, '__iter__') and not isinstance(segments, (str, bytes)) else [segments]

            # Convert numpy types to native Python types for JSON serialization
            # Filter out any remaining NaN/None values
            segments_list = [x.item() if hasattr(x, 'item') else x for x in segments_list if pd.notna(x)]

            # Convert segment_counts to dict with native Python types
            counts_dict = {}
            for key, value in segment_counts.items():
                # Skip NaN keys to prevent JSON serialization errors
                if pd.notna(key):
                    # Convert numpy types to native Python types
                    key_converted = key.item() if hasattr(key, 'item') else key
                    value_converted = int(value) if hasattr(value, 'item') else value
                    counts_dict[key_converted] = value_converted

            return {
                'available': True,
                'segment_column': segment_column,
                'segment_column_candidates': segment_column_candidates,
                'segments': segments_list,
                'counts': counts_dict,
                'total_segments': len(segments),
                'total_rows': len(df)
            }

        except Exception as e:
            self.logger.error(f"Error detecting segments: {str(e)}")
            return {'available': False, 'error': str(e)}

    def train_models_by_segment(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Train models for each segment with the same configuration

        Args:
            config: Training configuration including dataset_id, target_column, etc.

        Returns:
            Dictionary with model results for each segment
        """
        try:
            dataset_id = config.get('dataset_id')
            if not dataset_id:
                raise ValueError("dataset_id is required")

            df = dataframe_state_manager.get_dataframe(dataset_id)
            if df is None:
                raise ValueError(f"Dataset {dataset_id} not found")

            # Detect segments (optional column from training request — plan §12.5)
            preferred = (config.get("segment_column") or "").strip() or None
            segment_info = self.detect_segments(dataset_id, preferred_segment_column=preferred)
            if not segment_info['available']:
                raise ValueError("No segments available for training")

            segment_column = segment_info['segment_column']
            segments = segment_info['segments']

            self.logger.info(f"Training models for {len(segments)} segments: {segments}")

            # Get active_scope from parent dataset to apply to all segments
            active_scope = 'entire'  # default
            try:
                active_scope = dataframe_state_manager._active_scope.get(dataset_id, 'entire')
                self.logger.info(f"Retrieved active_scope for dataset {dataset_id}: {active_scope}")
            except Exception as e:
                self.logger.warning(f"Could not retrieve active_scope for dataset {dataset_id}: {str(e)}, using default 'entire'")

            results = {}
            segment_models = {}

            def _merge_segment_transforms_into_base(
                base_dataset_id: str,
                segment_dataset_id: str,
                segment_id: Any,
            ) -> None:
                """
                Merge transformed columns created during manual segment training back into the
                base dataset's processed DataFrame, using segment-specific column names.

                This mirrors the behavior of the auto segment training merge helper and ensures
                global encodings are never overwritten.
                """
                try:
                    seg_df = dataframe_state_manager.get_dataframe(segment_dataset_id)
                    if seg_df is None or seg_df.empty:
                        logger.info(f"No processed DataFrame found for segment dataset {segment_dataset_id}")
                        return

                    base_df = dataframe_state_manager.get_dataframe(base_dataset_id)
                    if base_df is None or base_df.empty:
                        logger.info(
                            f"No processed DataFrame found for base dataset {base_dataset_id}, "
                            f"skipping merge of segment transforms"
                        )
                        return

                    suffixes = ("_le_auto", "_ss_auto", "_le_manual", "_ss_manual")
                    column_mappings: Dict[str, str] = {}

                    for col in seg_df.columns:
                        if not isinstance(col, str):
                            continue
                        if not col.endswith(suffixes):
                            continue

                        if col.endswith("_le_auto"):
                            new_name = col.replace("_le_auto", "_le_seg_auto")
                        elif col.endswith("_ss_auto"):
                            new_name = col.replace("_ss_auto", "_ss_seg_auto")
                        elif col.endswith("_le_manual"):
                            new_name = col.replace("_le_manual", "_le_seg_manual")
                        elif col.endswith("_ss_manual"):
                            new_name = col.replace("_ss_manual", "_ss_seg_manual")
                        else:
                            continue

                        column_mappings[col] = new_name

                        if new_name not in base_df.columns:
                            base_df[new_name] = pd.NA

                    if not column_mappings:
                        logger.info(
                            f"No transformed columns with expected suffixes found to merge for segment {segment_id}"
                        )
                        return

                    common_idx = seg_df.index.intersection(base_df.index)
                    if len(common_idx) == 0:
                        logger.warning(
                            f"No overlapping indices between base {base_dataset_id} and segment {segment_dataset_id}; "
                            f"skipping merge of segment transforms"
                        )
                        return

                    for seg_col, base_col in column_mappings.items():
                        try:
                            base_df.loc[common_idx, base_col] = seg_df.loc[common_idx, seg_col]
                        except Exception as e:
                            logger.error(
                                f"Failed to merge column {seg_col} into {base_col} for segment {segment_id}: {e}"
                            )

                    dataframe_state_manager.update_dataframe(
                        base_dataset_id,
                        base_df,
                        force_scope="entire",
                    )
                    logger.info(
                        f"Merged {len(column_mappings)} transformed columns from segment dataset "
                        f"{segment_dataset_id} into base dataset {base_dataset_id} for segment {segment_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error while merging segment transforms into base dataset "
                        f"for base={base_dataset_id}, segment_ds={segment_dataset_id}: {e}"
                    )

            # Helper function for parallel segment training
            def train_single_segment(segment_id):
                """Train models for a single segment - used for parallelization"""
                try:
                    self.logger.info(f"Training model for segment: {segment_id}")

                    # Filter data for this segment
                    segment_df = df[df[segment_column] == segment_id].copy()

                    if len(segment_df) < 10:
                        self.logger.warning(f"Segment {segment_id} has only {len(segment_df)} rows, skipping")
                        return {
                            'segment_id': segment_id,
                            'error': f'Insufficient data: only {len(segment_df)} rows'
                        }

                    # Filter out the segment column from independent variables to avoid data leakage
                    independent_variables = config.get('independent_variables', [])
                    if independent_variables and segment_column in independent_variables:
                        filtered_variables = [var for var in independent_variables if var != segment_column]
                        print(f"Filtered out segment column '{segment_column}' from independent variables")
                    else:
                        filtered_variables = independent_variables
                    locked_variables = config.get('locked_variables', [])
                    filtered_locked_variables = [
                        var for var in (locked_variables or []) if var != segment_column
                    ]

                    # Use the base service to train a model for this segment
                    segment_config = config.copy()
                    segment_config['df'] = segment_df
                    segment_config['independent_variables'] = filtered_variables

                    # Create a temporary dataset ID for this segment to save preprocessed data
                    temp_segment_id = f"{dataset_id}_segment_{segment_id}"
                    
                    # Persist the segment dataframe into the dataframe_state_manager so downstream
                    # components that rely on dataset_id can access it (mirrors auto flow).
                    try:
                        dataframe_state_manager.update_dataframe(temp_segment_id, segment_df, original_shape=segment_df.shape)
                    except Exception as e:
                        self.logger.warning(f"Could not persist temp segment dataframe for {temp_segment_id}: {e}")

                    # Set the active_scope for this segment dataset to match the parent dataset
                    # This ensures train/test split behavior is consistent (dev = 70/30, entire = no split)
                    try:
                        dataframe_state_manager._active_scope[temp_segment_id] = active_scope
                        self.logger.info(f"Set active_scope='{active_scope}' for segment {segment_id} (temp_dataset_id: {temp_segment_id})")
                    except Exception as e:
                        self.logger.warning(f"Could not set active_scope for segment dataset {temp_segment_id}: {str(e)}")
                    
                    # FIX: Create segment-specific split indices for HOLD evaluation
                    # If parent has a dev/hold split, we need to filter parent's HOLD data for this segment
                    # This allows model_training_manual_configuration.py to evaluate on segment HOLD data
                    if active_scope == 'dev':
                        try:
                            parent_hold_df = dataframe_state_manager._transformed_copies.get(dataset_id, {}).get('hold')
                            if parent_hold_df is None:
                                # Fallback: filter from master using parent split indices
                                parent_hold_idx = dataframe_state_manager._split_indices.get(dataset_id, {}).get('hold')
                                parent_master_df = dataframe_state_manager._full_dataframes.get(dataset_id)
                                if parent_hold_idx is not None and parent_master_df is not None and len(parent_hold_idx) > 0:
                                    parent_hold_df = parent_master_df.iloc[parent_hold_idx].copy()
                            
                            if parent_hold_df is not None and segment_column in parent_hold_df.columns:
                                # Filter parent HOLD data for this segment
                                segment_hold_df = parent_hold_df[parent_hold_df[segment_column] == segment_id].copy()
                                
                                if len(segment_hold_df) > 0:
                                    # Store segment HOLD data in _transformed_copies for evaluation
                                    if temp_segment_id not in dataframe_state_manager._transformed_copies:
                                        dataframe_state_manager._transformed_copies[temp_segment_id] = {}
                                    dataframe_state_manager._transformed_copies[temp_segment_id]['hold'] = segment_hold_df
                                    
                                    # Create split indices for segment (dev = all rows in segment_df, hold = segment_hold_df indices)
                                    dev_idx = np.arange(len(segment_df))
                                    hold_idx = np.arange(len(segment_hold_df))
                                    dataframe_state_manager._split_indices[temp_segment_id] = {'dev': dev_idx, 'hold': hold_idx}
                                    
                                    self.logger.info(f"✅ Created segment HOLD data for {temp_segment_id}: DEV={len(segment_df)} rows, HOLD={len(segment_hold_df)} rows")
                                else:
                                    self.logger.warning(f"⚠️ No HOLD data found for segment {segment_id} in parent HOLD dataset")
                            else:
                                self.logger.warning(f"⚠️ Parent HOLD data not available or missing segment column for {dataset_id}")
                        except Exception as hold_err:
                            self.logger.warning(f"⚠️ Failed to create segment HOLD data for {temp_segment_id}: {hold_err}")

                    # Train model using the existing manual configuration service
                    # Ensure max_iterations is an integer and not None
                    max_iterations = config.get('max_iterations')
                    if max_iterations is None or not isinstance(max_iterations, (int, float)):
                        max_iterations = 3  # Optimized: Reduced from 5 to 3 for faster training
                    else:
                        max_iterations = int(max_iterations)
                    
                    # Sanitize algorithm_params to ensure no None values
                    algorithm_params = config.get('algorithm_params', {})
                    if algorithm_params:
                        sanitized_params = {}
                        for algo_name, algo_params in algorithm_params.items():
                            if algo_params and isinstance(algo_params, dict):
                                # Remove None values from params
                                sanitized_params[algo_name] = {
                                    k: v for k, v in algo_params.items() if v is not None
                                }
                            else:
                                sanitized_params[algo_name] = {}
                        algorithm_params = sanitized_params
                    try:
                        segment_result = self.base_service.train_multiple_models(
                            df=segment_df,
                            target_column=config['target_column'],
                            independent_variables=filtered_variables,
                            algorithms=config.get('algorithms', ['xgboost']),
                            algorithm_params=algorithm_params,
                            max_iterations=max_iterations,
                            dataset_id=temp_segment_id,
                            locked_variables=filtered_locked_variables,
                            algorithm_param_ranges=config.get('algorithm_param_ranges', {}),
                            optimization_method=config.get('optimization_method', 'random'),
                            target_metric=config.get('target_metric'),
                            cv_folds=config.get('cv_folds'),
                            optuna_trials=config.get('optuna_trials'),
                            early_stopping_rounds=config.get('early_stopping_rounds'),
                            lr_backward_elimination=config.get('lr_backward_elimination'),
                        )
                    except Exception as e:
                        # If training fails, propagate the exception to be handled by the outer try
                        raise
                    # FIX: For segmented models, update stored indices to use base dataframe indices
                    # The indices stored by train_multiple_models are position indices (0, 1, 2, ...) relative to segment_df
                    # We need to convert them to original base dataframe indices for use during explainability
                    # This ensures that when we filter the base dataframe during explainability, we can use these indices
                    if segment_result and 'results' in segment_result:
                        # Get the mapping: position index in segment_df -> original index in base df
                        segment_df_index_list = segment_df.index.tolist()  # Original indices from base df
                        
                        for model_result in segment_result['results']:
                            if 'model_id' not in model_result:
                                continue
                            
                            # After training, update the indices in the database
                            # This happens AFTER train_multiple_models has saved to database
                            model_id = model_result['model_id']
                            
                            try:
                                from app.models.model_evaluation_database import model_evaluation_db
                                import time
                                
                                # Wait a brief moment to ensure database save is complete
                                time.sleep(0.1)
                                
                                evaluation_data = model_evaluation_db.get_model_evaluation(model_id)
                                
                                if evaluation_data and 'model' in evaluation_data:
                                    model_info = evaluation_data['model']
                                    train_indices = model_info.get('train_indices')
                                    test_indices = model_info.get('test_indices')
                                    
                                    updated = False
                                    
                                    # Convert position indices to base dataframe indices
                                    if train_indices:
                                        base_train_indices = []
                                        for pos_idx in train_indices:
                                            if isinstance(pos_idx, (int, np.integer)) and 0 <= pos_idx < len(segment_df_index_list):
                                                base_train_indices.append(segment_df_index_list[pos_idx])
                                            else:
                                                # If index is already an original index, keep it
                                                base_train_indices.append(pos_idx)
                                        if base_train_indices != train_indices:
                                            model_info['train_indices'] = base_train_indices
                                            updated = True
                                            self.logger.info(f"Updated train_indices for segmented model {model_id}: {len(train_indices)} -> {len(base_train_indices)} indices mapped to base dataframe")
                                    
                                    if test_indices:
                                        base_test_indices = []
                                        for pos_idx in test_indices:
                                            if isinstance(pos_idx, (int, np.integer)) and 0 <= pos_idx < len(segment_df_index_list):
                                                base_test_indices.append(segment_df_index_list[pos_idx])
                                            else:
                                                # If index is already an original index, keep it
                                                base_test_indices.append(pos_idx)
                                        if base_test_indices != test_indices:
                                            model_info['test_indices'] = base_test_indices
                                            updated = True
                                            self.logger.info(f"Updated test_indices for segmented model {model_id}: {len(test_indices)} -> {len(base_test_indices)} indices mapped to base dataframe")
                                    
                                    # Update the database with base dataframe indices
                                    if updated:
                                        # Re-save the evaluation data with updated indices
                                        model_evaluation_db.save_evaluation_results(evaluation_data)
                                        self.logger.info(f"Updated indices in database for segmented model {model_id}: train={len(model_info.get('train_indices', []))}, test={len(model_info.get('test_indices', []))}")
                                        
                            except Exception as e:
                                self.logger.warning(f"Failed to update indices for segmented model {model_id}: {str(e)}")
                                # Continue even if update fails - the model is still trained correctly
                                import traceback
                                self.logger.debug(traceback.format_exc())

                    # After training, merge any transformed columns created for this
                    # segment back into the base dataset using segment-specific names.
                    _merge_segment_transforms_into_base(
                        base_dataset_id=dataset_id,
                        segment_dataset_id=temp_segment_id,
                        segment_id=segment_id,
                    )

                    # Clean up temporary segment dataset to avoid polluting global state
                    # NOTE: We intentionally clean up AFTER merging transformed columns into
                    # the base dataframe so that the merge can access the processed
                    # segment DataFrame created during training. This mirrors the auto
                    # segment training behaviour and fixes missing preprocessed columns
                    # which previously caused explainability to be incomplete for
                    # manual-segment models.
                    try:
                        dataframe_state_manager.update_dataframe(temp_segment_id, pd.DataFrame())
                    except Exception:
                        pass

                    # Filter out error results from the results array
                    # Only include results that have successfully trained models with model_id
                    if segment_result and 'results' in segment_result:
                        filtered_results = [r for r in segment_result['results'] if 'model_id' in r and 'error' not in r]
                        
                        # Log errors for failed algorithms
                        error_results = [r for r in segment_result['results'] if 'error' in r or 'model_id' not in r]
                        for error_result in error_results:
                            algo_name = error_result.get('algorithm', 'unknown')
                            error_msg = error_result.get('error', 'Unknown error')
                            self.logger.warning(f"Algorithm {algo_name} failed for segment {segment_id}: {error_msg}")
                        
                        # Update segment_result with filtered results
                        segment_result['results'] = filtered_results
                        segment_result['failed_algorithms'] = len(error_results)
                        segment_result['successful_algorithms'] = len(filtered_results)

                    # Collect model IDs for this segment
                    model_ids = []
                    if segment_result and 'results' in segment_result:
                        model_ids = [r['model_id'] for r in segment_result['results'] if 'model_id' in r]

                    return {
                        'segment_id': segment_id,
                        'segment_key': f'segment_{segment_id}',
                        'segment_result': segment_result,
                        'model_ids': model_ids
                    }

                except Exception as e:
                    self.logger.error(f"Error training model for segment {segment_id}: {str(e)}")
                    return {
                        'segment_id': segment_id,
                        'segment_key': f'segment_{segment_id}',
                        'error': str(e)
                    }

            # Use parallel processing with n_jobs=2 for Azure (limited cores)
            self.logger.info(f"Training {len(segments)} segments in parallel...")
            segment_results_list = Parallel(n_jobs=-1, backend='loky', verbose=1, batch_size='auto', pre_dispatch='2*n_jobs')(
                delayed(train_single_segment)(segment_id) for segment_id in segments
            )

            # Process parallel results
            for seg_result in segment_results_list:
                if seg_result is None:
                    continue
                    
                segment_id = seg_result['segment_id']
                segment_key = seg_result['segment_key']
                
                if 'error' in seg_result:
                    results[segment_key] = {'error': seg_result['error']}
                else:
                    results[segment_key] = seg_result['segment_result']
                    segment_models[segment_id] = seg_result['model_ids']

            # Generate overall model ID
            overall_model_id = f"SEG_MULTI_{uuid.uuid4().hex[:8].upper()}"

            # Save segment training results
            segments_list = list(segments) if hasattr(segments, '__iter__') and not isinstance(segments, (str, bytes)) else [segments]
            # Convert numpy types to native Python types for JSON serialization
            segments_list = [x.item() if hasattr(x, 'item') else x for x in segments_list]
            training_results = {
                'model_id': overall_model_id,
                'segment_column': segment_column,
                'segments': segments_list,
                'segment_results': results,
                'segment_models': segment_models,
                'config': config,
                'timestamp': datetime.now().isoformat()
            }

            results_path = os.path.join(self.model_storage_path, f"{overall_model_id}_segment_results.json")
            with open(results_path, 'w') as f:
                json.dump(training_results, f, indent=2, default=str)

            # Get unified results for immediate use
            unified_results = self.get_unified_segment_results(overall_model_id)

            return {
                'model_id': overall_model_id,
                'results': [],  # Regular results array (empty for segment training)
                'segment_results': results,
                'segment_models': segment_models,
                'segment_column': segment_column,
                'segments': segments_list,
                'total_segments': len(segments),
                'successful_segments': len([r for r in results.values() if 'error' not in r]),
                'unified_results': unified_results  # Add unified results for dashboard
            }

        except Exception as e:
            self.logger.error(f"Error in segment training: {str(e)}")
            raise

    def get_segment_model_results(self, model_id: str, segment_id: str) -> Dict[str, Any]:
        """
        Get results for a specific segment model

        Args:
            model_id: Overall segment model ID
            segment_id: Specific segment ID

        Returns:
            Dictionary with segment model results
        """
        try:
            results_path = os.path.join(self.model_storage_path, f"{model_id}_segment_results.json")

            if not os.path.exists(results_path):
                return {'error': f'Model {model_id} not found'}

            with open(results_path, 'r') as f:
                training_results = json.load(f)

            segment_key = f'segment_{segment_id}'
            if segment_key not in training_results['segment_results']:
                return {'error': f'Segment {segment_id} not found in model {model_id}'}

            segment_result = training_results['segment_results'][segment_key]

            # Load individual model details
            model_details = []
            if 'results' in segment_result:
                for model_result in segment_result['results']:
                    if 'model_id' in model_result:
                        # Load detailed model information
                        model_detail = self._load_model_details(model_result['model_id'])
                        if model_detail:
                            model_details.append(model_detail)

            return {
                'segment_id': segment_id,
                'model_id': model_id,
                'segment_result': segment_result,
                'model_details': model_details,
                'segment_info': training_results.get('segment_info', {})
            }

        except Exception as e:
            self.logger.error(f"Error getting segment model results: {str(e)}")
            return {'error': str(e)}

    def get_segment_training_history(self, model_id: str, segment_id: str) -> List[Dict[str, Any]]:
        """
        Get training history for a specific segment

        Args:
            model_id: Overall segment model ID
            segment_id: Specific segment ID

        Returns:
            List of training history entries for the segment
        """
        try:
            segment_results = self.get_segment_model_results(model_id, segment_id)

            if 'error' in segment_results:
                return []

            history = []
            if 'model_details' in segment_results:
                for model_detail in segment_results['model_details']:
                    if 'iteration_history' in model_detail:
                        # Add segment info to each iteration
                        for iteration in model_detail['iteration_history']:
                            iteration['segment_id'] = segment_id
                            iteration['algorithm'] = model_detail.get('algorithm', 'Unknown')
                        history.extend(model_detail['iteration_history'])

            return history

        except Exception as e:
            self.logger.error(f"Error getting segment training history: {str(e)}")
            return []

    def compare_segment_models(self, model_id: str, segments: List[str]) -> Dict[str, Any]:
        """
        Compare performance across segments

        Args:
            model_id: Overall segment model ID
            segments: List of segment IDs to compare

        Returns:
            Dictionary with comparison results
        """
        try:
            comparison = {}

            for segment_id in segments:
                segment_results = self.get_segment_model_results(model_id, segment_id)

                if 'error' not in segment_results and 'model_details' in segment_results:
                    comparison[segment_id] = {
                        'models': segment_results['model_details'],
                        'best_score': max([m.get('metrics', {}).get('auc', 0) if 'classification' in str(m.get('problem_type', '')).lower()
                                         else m.get('metrics', {}).get('r2', 0)
                                         for m in segment_results['model_details']] or [0])
                    }

            return {
                'model_id': model_id,
                'segments': segments,
                'comparison': comparison,
                'summary': {
                    'total_segments': len(segments),
                    'segments_with_models': len(comparison)
                }
            }

        except Exception as e:
            self.logger.error(f"Error comparing segment models: {str(e)}")
            return {'error': str(e)}

    def get_model_screen_results(self, model_id: str, segment_id: str) -> Dict[str, Any]:
        """
        Get model screening results for a specific segment

        Args:
            model_id: Overall segment model ID
            segment_id: Specific segment ID

        Returns:
            Dictionary with model screening results
        """
        try:
            segment_results = self.get_segment_model_results(model_id, segment_id)

            if 'error' in segment_results:
                return segment_results

            # Filter models by algorithm if specified
            algorithm_filter = segment_results.get('algorithm_filter')

            filtered_models = []
            if 'model_details' in segment_results:
                for model in segment_results['model_details']:
                    if not algorithm_filter or model.get('algorithm') == algorithm_filter:
                        filtered_models.append(model)

            return {
                'segment_id': segment_id,
                'model_id': model_id,
                'filtered_models': filtered_models,
                'total_models': len(filtered_models),
                'algorithm_filter': algorithm_filter
            }

        except Exception as e:
            self.logger.error(f"Error getting model screen results: {str(e)}")
            return {'error': str(e)}

    def get_unified_segment_results(self, model_id: str) -> Dict[str, Any]:
        """
        Get unified segment results for dashboard display with segment selector
        
        Args:
            model_id: Overall segment model ID
            
        Returns:
            Dictionary with unified results for all segments
        """
        try:
            results_path = os.path.join(self.model_storage_path, f"{model_id}_segment_results.json")
            
            if not os.path.exists(results_path):
                return {'error': f'Model {model_id} not found'}
                
            with open(results_path, 'r') as f:
                training_results = json.load(f)
            
            segments = training_results.get('segments', [])
            segment_results_data = training_results.get('segment_results', {})
            
            # Process each segment to extract unified results
            unified_segments = {}
            overall_best_algorithm = None
            overall_best_score = -1
            
            for segment_id in segments:
                segment_key = f'segment_{segment_id}'
                if segment_key not in segment_results_data:
                    continue
                    
                segment_result = segment_results_data[segment_key]
                if 'error' in segment_result:
                    continue
                    
                # Extract best algorithm and metrics for this segment
                # Store ALL models in a list (not keyed by algorithm to avoid overwrites)
                segment_models_list = []
                segment_best_algorithm = None
                segment_best_score = -1
                segment_best_model_id = None
                
                if 'results' in segment_result:
                    for model_result in segment_result['results']:
                        if 'model_id' not in model_result:
                            continue
                            
                        # Load detailed model information
                        model_detail = self._load_model_details(model_result['model_id'])
                        if not model_detail:
                            continue
                            
                        algorithm = model_detail.get('algorithm', 'Unknown')
                        metrics = model_detail.get('metrics', {})
                        
                        # Get primary score (AUC for classification, R2 for regression)
                        problem_type = model_detail.get('problem_type', 'classification')
                        if 'classification' in problem_type.lower():
                            primary_score = metrics.get('auc', metrics.get('accuracy', 0))
                            primary_metric = 'auc'
                        else:
                            primary_score = metrics.get('r2', metrics.get('rmse', 0))
                            primary_metric = 'r2'
                        
                        # Store ALL models in a list (fixes issue where multiple models of same algorithm were overwritten)
                        model_info = {
                            'model_id': model_result['model_id'],
                            'algorithm': algorithm,
                            'primary_score': primary_score,
                            'primary_metric': primary_metric,
                            'metrics': {
                                'accuracy': metrics.get('accuracy', 0),
                                'precision': metrics.get('precision', 0),
                                'recall': metrics.get('recall', 0),
                                'f1': metrics.get('f1', 0),
                                'auc': metrics.get('auc', 0),
                                'log_loss': metrics.get('log_loss', 0),
                                'cv_mean': metrics.get('cross_validation_scores', [0])
                            },
                            'hyperparameters': model_detail.get('hyperparameters', {}),
                            'problem_type': problem_type
                        }
                        segment_models_list.append(model_info)
                        
                        # Track best for this segment
                        if primary_score > segment_best_score:
                            segment_best_score = primary_score
                            segment_best_algorithm = algorithm
                            segment_best_model_id = model_result['model_id']
                            
                        # Track overall best
                        if primary_score > overall_best_score:
                            overall_best_score = primary_score
                            overall_best_algorithm = algorithm
                
                # Store segment data with all models
                unified_segments[segment_id] = {
                    'segment_id': segment_id,
                    'models': segment_models_list,  # All models as a list
                    'algorithms': {m['algorithm']: m for m in segment_models_list},  # Also provide dict for backward compat
                    'best_algorithm': segment_best_algorithm,
                    'best_score': segment_best_score,
                    'best_model_id': segment_best_model_id,
                    'total_models': len(segment_models_list),
                    'total_algorithms': len(set(m['algorithm'] for m in segment_models_list))  # Unique algorithms count
                }
            
            return {
                'model_id': model_id,
                'segments': segments,  # Return as array for frontend compatibility
                'segments_data': unified_segments,  # Detailed segment data as dict
                'segment_list': segments,  # Alias for backward compatibility
                'segment_results': segment_results_data,  # Full segment results for frontend (used in graphs)
                'segment_column': training_results.get('segment_column', 'segment'),
                'overall_best_algorithm': overall_best_algorithm,
                'overall_best_score': overall_best_score,
                'total_segments': len(segments),
                'successful_segments': len(unified_segments)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting unified segment results: {str(e)}")
            return {'error': str(e)}

    def get_organized_segment_results(self, model_id: str) -> Dict[str, Any]:
        """
        Get organized segment results with algorithm and segment grouping for filtering
        
        Args:
            model_id: Overall segment model ID
            
        Returns:
            Dictionary with organized results by segment and algorithm
        """
        try:
            results_path = os.path.join(self.model_storage_path, f"{model_id}_segment_results.json")
            
            if not os.path.exists(results_path):
                return {'error': f'Model {model_id} not found'}
                
            with open(results_path, 'r') as f:
                training_results = json.load(f)
            
            segments = training_results.get('segments', [])
            segment_results_data = training_results.get('segment_results', {})
            
            # Organize by segment and algorithm
            organized_results = {
                'model_id': model_id,
                'segments': {},
                'algorithms': set(),
                'segment_list': segments,
                'segment_column': training_results.get('segment_column', 'segment'),
                'all_results': []  # Flattened results for easy filtering
            }
            
            for segment_id in segments:
                segment_key = f'segment_{segment_id}'
                if segment_key not in segment_results_data:
                    continue
                    
                segment_result = segment_results_data[segment_key]
                if 'error' in segment_result:
                    continue
                
                organized_results['segments'][segment_id] = {
                    'segment_id': segment_id,
                    'algorithms': {},
                    'total_models': 0
                }
                
                if 'results' in segment_result:
                    for model_result in segment_result['results']:
                        if 'model_id' not in model_result:
                            continue
                            
                        # Load detailed model information
                        model_detail = self._load_model_details(model_result['model_id'])
                        if not model_detail:
                            continue
                            
                        algorithm = model_detail.get('algorithm', 'Unknown')
                        organized_results['algorithms'].add(algorithm)
                        
                        # Create enriched result with segment info
                        enriched_result = {
                            **model_result,
                            'segment_id': segment_id,
                            'segment_key': segment_key,
                            'algorithm': algorithm,
                            'metrics': model_detail.get('metrics', {}),
                            'hyperparameters': model_detail.get('hyperparameters', {}),
                            'problem_type': model_detail.get('problem_type', 'classification'),
                            'iteration_history': model_detail.get('iteration_history', []),
                            'used_features': model_detail.get('used_features', [])
                        }
                        
                        # Store algorithm result for this segment
                        organized_results['segments'][segment_id]['algorithms'][algorithm] = enriched_result
                        organized_results['segments'][segment_id]['total_models'] += 1
                        
                        # Add to flattened results
                        organized_results['all_results'].append(enriched_result)
            
            organized_results['algorithms'] = list(organized_results['algorithms'])
            
            return organized_results
            
        except Exception as e:
            self.logger.error(f"Error getting organized segment results: {str(e)}")
            return {'error': str(e)}

    def get_segment_iteration_history(self, model_id: str, segment_id: str = None, algorithm: str = None) -> Dict[str, Any]:
        """
        Get iteration history for segment training with filtering options
        
        Args:
            model_id: Overall segment model ID
            segment_id: Optional specific segment ID to filter by
            algorithm: Optional specific algorithm to filter by
            
        Returns:
            Dictionary with filtered iteration history data
        """
        try:
            results_path = os.path.join(self.model_storage_path, f"{model_id}_segment_results.json")
            
            if not os.path.exists(results_path):
                return {'error': f'Model {model_id} not found'}
                
            with open(results_path, 'r') as f:
                training_results = json.load(f)
            
            segments = training_results.get('segments', [])
            segment_results_data = training_results.get('segment_results', {})
            
            # Organize iteration history by segment and algorithm
            iteration_data = {
                'model_id': model_id,
                'segments': [],
                'algorithms': set(),
                'problem_type': None,
                'segment_column': training_results.get('segment_column', 'segment')
            }
            
            for seg_id in segments:
                # Apply segment filter if specified
                if segment_id and seg_id != segment_id:
                    continue
                    
                segment_key = f'segment_{seg_id}'
                if segment_key not in segment_results_data:
                    continue
                    
                segment_result = segment_results_data[segment_key]
                if 'error' in segment_result:
                    continue
                
                segment_data = {
                    'segment_id': seg_id,
                    'algorithms': []
                }
                
                if 'results' in segment_result:
                    for model_result in segment_result['results']:
                        if 'model_id' not in model_result:
                            continue
                            
                        # Load detailed model information
                        model_detail = self._load_model_details(model_result['model_id'])
                        if not model_detail:
                            continue
                            
                        algo_name = model_detail.get('algorithm', 'Unknown')
                        
                        # Apply algorithm filter if specified
                        if algorithm and algo_name != algorithm:
                            continue
                            
                        iteration_data['algorithms'].add(algo_name)
                        
                        # Set problem type from first valid result
                        if not iteration_data['problem_type']:
                            iteration_data['problem_type'] = model_detail.get('problem_type', 'classification')
                        
                        # Process iteration history
                        iteration_history = model_detail.get('iteration_history', [])
                        
                        algorithm_data = {
                            'algorithm': algo_name,
                            'model_id': model_result['model_id'],
                            'iteration_history': iteration_history,
                            'problem_type': model_detail.get('problem_type', 'classification'),
                            'metrics': model_detail.get('metrics', {}),
                            'hyperparameters': model_detail.get('hyperparameters', {})
                        }
                        
                        segment_data['algorithms'].append(algorithm_data)
                
                if segment_data['algorithms']:  # Only add segments that have algorithm data
                    iteration_data['segments'].append(segment_data)
            
            iteration_data['algorithms'] = list(iteration_data['algorithms'])
            
            return iteration_data
            
        except Exception as e:
            self.logger.error(f"Error getting segment iteration history: {str(e)}")
            return {'error': str(e)}

    def _load_model_details(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Load detailed model information from stored files

        Args:
            model_id: Individual model ID

        Returns:
            Dictionary with model details or None if not found
        """
        try:
            # Try to load from the regular models directory first
            model_path = f"models/{model_id}.pkl"
            results_path = f"models/{model_id}_training_results.json"

            if not os.path.exists(model_path) or not os.path.exists(results_path):
                return None

            # Load training results
            with open(results_path, 'r') as f:
                training_data = json.load(f)

            return {
                'model_id': model_id,
                'algorithm': training_data.get('algorithm', 'Unknown'),
                'problem_type': training_data.get('problem_type', 'Unknown'),
                'metrics': training_data.get('metrics', {}),
                'iteration_history': training_data.get('iteration_history', []),
                'hyperparameters': training_data.get('hyperparameters', {}),
                'used_features': training_data.get('used_features', [])
            }

        except Exception as e:
            self.logger.error(f"Error loading model details for {model_id}: {str(e)}")
            return None


# Create singleton instance
segment_training_service = SegmentTrainingManualConfigurationService()

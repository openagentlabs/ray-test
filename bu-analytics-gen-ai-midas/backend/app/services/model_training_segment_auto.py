import pandas as pd
import numpy as np
import json
import os
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from joblib import Parallel, delayed

from app.core.logging_config import get_logger
from app.services.dataframe_state_manager import dataframe_state_manager
from app.services.model_training_auto_training import ModelTrainingAutoTrainingService

logger = get_logger(__name__)


class SegmentTrainingAutoService:
    """Service for segment-specific automatic model training"""

    def __init__(self):
        self.logger = logger
        self.model_storage_path = "models/segment_models/"
        self.auto_service = ModelTrainingAutoTrainingService()
        os.makedirs(self.model_storage_path, exist_ok=True)

    def _merge_segment_transforms_into_base(
        self,
        base_dataset_id: str,
        segment_dataset_id: str,
        segment_id: Any,
    ) -> None:
        """
        Merge transformed columns created during segment training back into the
        base dataset's processed DataFrame, using segment-specific column names.

        This keeps per-segment encodings isolated while making them available on
        the global dataframe for downstream agents (e.g., explainability).
        """
        try:
            # Get processed DataFrames for segment and base datasets
            seg_df = dataframe_state_manager.get_dataframe(segment_dataset_id)
            if seg_df is None or seg_df.empty:
                self.logger.info(f"No processed DataFrame found for segment dataset {segment_dataset_id}")
                return

            base_df = dataframe_state_manager.get_dataframe(base_dataset_id)
            if base_df is None or base_df.empty:
                # If base isn't in state yet, initialize it from the original data for this dataset
                self.logger.info(
                    f"No processed DataFrame found for base dataset {base_dataset_id}, "
                    f"skipping merge of segment transforms"
                )
                return

            # Identify transformed columns created by auto/manual training
            # We only care about *_le_auto, *_ss_auto, *_le_manual, *_ss_manual
            suffixes = ("_le_auto", "_ss_auto", "_le_manual", "_ss_manual")
            column_mappings: Dict[str, str] = {}  # segment_col -> base_col

            for col in seg_df.columns:
                if not isinstance(col, str):
                    continue
                if not col.endswith(suffixes):
                    continue

                # Build a segment-safe name on the base df so we never overwrite global encodings
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

                # Ensure the base df has this column
                if new_name not in base_df.columns:
                    base_df[new_name] = pd.NA

            if not column_mappings:
                self.logger.info(
                    f"No transformed columns with expected suffixes found to merge for segment {segment_id}"
                )
                return

            # Align rows between base and segment DataFrames using their indices
            common_idx = seg_df.index.intersection(base_df.index)
            if len(common_idx) == 0:
                self.logger.warning(
                    f"No overlapping indices between base {base_dataset_id} and segment {segment_dataset_id}; "
                    f"skipping merge of segment transforms"
                )
                return

            for seg_col, base_col in column_mappings.items():
                try:
                    base_df.loc[common_idx, base_col] = seg_df.loc[common_idx, seg_col]
                except Exception as e:
                    self.logger.error(
                        f"Failed to merge column {seg_col} into {base_col} for segment {segment_id}: {e}"
                    )

            # Persist updated base dataframe as the master 'entire' dataset
            dataframe_state_manager.update_dataframe(
                base_dataset_id,
                base_df,
                force_scope="entire",
            )
            self.logger.info(
                f"Merged {len(column_mappings)} transformed columns from segment dataset "
                f"{segment_dataset_id} into base dataset {base_dataset_id} for segment {segment_id}"
            )
        except Exception as e:
            self.logger.error(
                f"Error while merging segment transforms into base dataset "
                f"for base={base_dataset_id}, segment_ds={segment_dataset_id}: {e}"
            )

    def detect_segments(self, dataset_id: str) -> Dict[str, Any]:
        """
        Detect if segmentation column exists and return segment distribution

        Args:
            dataset_id: ID of the dataset to check

        Returns:
            Dictionary with segment information
        """
        try:
            df = dataframe_state_manager.get_dataframe(dataset_id)
            if df is None:
                return {'available': False, 'error': 'Dataset not found'}

            # Look for segment column - be comprehensive
            segment_columns = ['segment', 'SEGMENT', 'segment_id', 'SEGMENT_ID', 'group', 'GROUP', 'cluster', 'CLUSTER']

            segment_column = None
            for col in segment_columns:
                if col in df.columns:
                    segment_column = col
                    break

            # If no exact match found, look for columns that might be segments
            if segment_column is None:
                potential_segments = []
                for col in df.columns:
                    if df[col].dtype in ['object', 'category'] or (df[col].dtype in ['int64', 'float64'] and df[col].nunique() < 50):
                        unique_ratio = df[col].nunique() / len(df)
                        if 0.01 < unique_ratio < 0.5:  # Between 1% and 50% unique values
                            potential_segments.append(col)

                if potential_segments:
                    segment_column = potential_segments[0]
                    self.logger.info(f"Using potential segment column: {segment_column}")
                else:
                    return {
                        'available': False,
                        'message': 'No segment column detected',
                        'suggestion': 'Consider creating a segment column or use global training mode'
                    }

            segments = df[segment_column].unique()
            segment_counts = df[segment_column].value_counts()

            # Convert to native Python types for JSON serialization
            segments_list = [x.item() if hasattr(x, 'item') else x for x in segments]
            counts_dict = {
                (key.item() if hasattr(key, 'item') else key): int(value)
                for key, value in segment_counts.items()
            }

            return {
                'available': True,
                'segment_column': segment_column,
                'segments': segments_list,
                'counts': counts_dict,
                'total_segments': len(segments),
                'total_rows': len(df)
            }

        except Exception as e:
            self.logger.error(f"Error detecting segments: {str(e)}")
            return {'available': False, 'error': str(e)}

    def run_complete_segment_auto_training(
        self,
        dataset_id: str,
        target_column: str,
        selected_variables: Optional[List[str]] = None,
        selection_mode: str = "auto",
        selected_algorithms: Optional[List[str]] = None,
        locked_variables: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Run complete automatic training pipeline for each segment

        Args:
            dataset_id: ID of the dataset to use
            target_column: Name of the target column
            selected_variables: Optional list of pre-selected variables (if None, auto-selects)
            selection_mode: Variable selection mode ("auto", "manual", etc.)

        Returns:
            Dictionary with complete segment training results
        """
        try:
            self.logger.info(f"Starting segment auto training for dataset {dataset_id}")

            # Load dataset
            df = dataframe_state_manager.get_dataframe(dataset_id)
            if df is None:
                raise ValueError(f"Dataset {dataset_id} not found")

            # Detect segments
            segment_info = self.detect_segments(dataset_id)
            if not segment_info['available']:
                raise ValueError("No segments available for training")

            segment_column = segment_info['segment_column']
            segments = segment_info['segments']

            self.logger.info(f"Training auto models for {len(segments)} segments: {segments}")

            # Get active_scope from parent dataset to apply to all segments
            active_scope = 'entire'  # default
            try:
                active_scope = dataframe_state_manager._active_scope.get(dataset_id, 'entire')
                self.logger.info(f"Retrieved active_scope for dataset {dataset_id}: {active_scope}")
            except Exception as e:
                self.logger.warning(f"Could not retrieve active_scope for dataset {dataset_id}: {str(e)}, using default 'entire'")

            # Store results per segment
            segment_results = {}
            segment_models = {}
            all_segment_data = {}

            # Helper function for parallel segment training
            def train_single_segment(segment_id):
                """Train models for a single segment - used for parallelization"""
                try:
                    self.logger.info(f"Processing segment: {segment_id}")

                    # Filter data for this segment
                    segment_df = df[df[segment_column] == segment_id].copy()

                    if len(segment_df) < 10:
                        self.logger.warning(f"Segment {segment_id} has only {len(segment_df)} rows, skipping")
                        return {
                            'segment_id': segment_id,
                            'error': f'Insufficient data: only {len(segment_df)} rows'
                        }

                    # Remove segment column from independent variables to avoid data leakage
                    segment_independent_vars = None
                    if selected_variables:
                        segment_independent_vars = [v for v in selected_variables if v != segment_column]
                    segment_locked_vars = None
                    if locked_variables:
                        segment_locked_vars = [v for v in locked_variables if v != segment_column]

                    # Create a temporary dataset ID for this segment (in-memory, not persisted)
                    temp_segment_id = f"{dataset_id}_segment_{segment_id}"
                    dataframe_state_manager.update_dataframe(temp_segment_id, segment_df)
                    
                    # Set the active_scope for this segment dataset to match the parent dataset
                    # This ensures train/test split behavior is consistent (dev = 70/30, entire = no split)
                    try:
                        dataframe_state_manager._active_scope[temp_segment_id] = active_scope
                        self.logger.info(f"Set active_scope='{active_scope}' for segment {segment_id} (temp_dataset_id: {temp_segment_id})")
                    except Exception as e:
                        self.logger.warning(f"Could not set active_scope for segment dataset {temp_segment_id}: {str(e)}")
                    
                    # FIX: Create segment-specific split indices for HOLD evaluation
                    # If parent has a dev/hold split, we need to filter parent's HOLD data for this segment
                    # This allows auto training to evaluate on segment HOLD data
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

                    try:
                        # Run complete auto training for this segment using a fresh service instance
                        # to avoid shared-instance state (X_before_encoding, X_before_scaling, etc.)
                        # being overwritten when training segments in parallel.
                        local_auto_service = ModelTrainingAutoTrainingService()
                        segment_training_result = local_auto_service.run_complete_auto_training(
                            dataset_id=temp_segment_id,
                            target_column=target_column,
                            selected_variables=segment_independent_vars,
                            selection_mode=selection_mode,
                            selected_algorithms=selected_algorithms,
                            locked_variables=segment_locked_vars,
                        )

                        # FIX: For segmented models, update stored indices to use base dataframe indices
                        # The indices stored by run_complete_auto_training are position indices (0, 1, 2, ...) relative to segment_df
                        # We need to convert them to original base dataframe indices for use during explainability
                        # This ensures that when we filter the base dataframe during explainability, we can use these indices
                        if segment_training_result and 'results' in segment_training_result:
                            # Get the mapping: position index in segment_df -> original index in base df
                            segment_df_index_list = segment_df.index.tolist()  # Original indices from base df
                            
                            for model_result in segment_training_result['results']:
                                if 'model_id' not in model_result:
                                    continue
                                
                                # After training, update the indices in the database
                                # This happens AFTER run_complete_auto_training has saved to database
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
                                            # Robust detection: determine whether stored indices are positional
                                            # (0..n-1 relative to segment_df) or actual base dataframe index labels.
                                            segment_idx_set = set(segment_df_index_list)
                                            present_count = sum(1 for idx in train_indices if idx in segment_idx_set)
                                            # If majority of stored indices are present in the segment index set, assume they are labels
                                            assume_labels = present_count >= max(1, len(train_indices) // 2)

                                            base_train_indices = []
                                            if assume_labels:
                                                # Indices already look like labels; keep as-is but ensure they exist in base
                                                for idx in train_indices:
                                                    if idx in segment_idx_set:
                                                        base_train_indices.append(idx)
                                                    else:
                                                        # Keep the value (fallback) - downstream code will filter invalid entries
                                                        base_train_indices.append(idx)
                                            else:
                                                # Treat as positional indices and map to base dataframe indices
                                                for pos_idx in train_indices:
                                                    if isinstance(pos_idx, (int, np.integer)) and 0 <= pos_idx < len(segment_df_index_list):
                                                        base_train_indices.append(segment_df_index_list[pos_idx])
                                                    else:
                                                        # If index looks like a label or is out of range, keep it
                                                        base_train_indices.append(pos_idx)

                                            if base_train_indices != train_indices:
                                                model_info['train_indices'] = base_train_indices
                                                updated = True
                                                self.logger.info(f"Updated train_indices for segmented model {model_id}: {len(train_indices)} -> {len(base_train_indices)} indices mapped to base dataframe")
                                        
                                        if test_indices:
                                            # Same robust detection for test indices
                                            segment_idx_set = set(segment_df_index_list)
                                            present_count_test = sum(1 for idx in test_indices if idx in segment_idx_set)
                                            assume_labels_test = present_count_test >= max(1, len(test_indices) // 2)

                                            base_test_indices = []
                                            if assume_labels_test:
                                                for idx in test_indices:
                                                    if idx in segment_idx_set:
                                                        base_test_indices.append(idx)
                                                    else:
                                                        base_test_indices.append(idx)
                                            else:
                                                for pos_idx in test_indices:
                                                    if isinstance(pos_idx, (int, np.integer)) and 0 <= pos_idx < len(segment_df_index_list):
                                                        base_test_indices.append(segment_df_index_list[pos_idx])
                                                    else:
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
                        self._merge_segment_transforms_into_base(
                            base_dataset_id=dataset_id,
                            segment_dataset_id=temp_segment_id,
                            segment_id=segment_id,
                        )

                        # Collect model IDs for this segment
                        model_ids = []
                        if 'results' in segment_training_result:
                            model_ids = [
                                r['model_id'] for r in segment_training_result['results']
                                if 'model_id' in r and 'error' not in r
                            ]

                        # Store segment-level data for unified view
                        segment_data = {
                            'segment_id': segment_id,
                            'segment_size': len(segment_df),
                            'problem_type': segment_training_result.get('problem_type'),
                            'num_models_trained': segment_training_result.get('auto_selection_summary', {}).get('num_models_trained', 0),
                            'best_model': segment_training_result.get('best_model_selection', {}),
                            'algorithms': [r.get('algorithm') for r in segment_training_result.get('results', []) if 'algorithm' in r],
                            'training_complete': True
                        }

                        return {
                            'segment_id': segment_id,
                            'segment_key': f'segment_{segment_id}',
                            'segment_training_result': segment_training_result,
                            'model_ids': model_ids,
                            'segment_data': segment_data
                        }

                    finally:
                        # Clean up temporary segment dataset
                        try:
                            dataframe_state_manager.update_dataframe(temp_segment_id, pd.DataFrame())
                        except Exception:
                            pass

                except Exception as e:
                    self.logger.error(f"Error training segment {segment_id}: {str(e)}")
                    import traceback
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
                    return {
                        'segment_id': segment_id,
                        'segment_key': f'segment_{segment_id}',
                        'error': str(e),
                        'segment_data': {
                            'segment_id': segment_id,
                            'error': str(e),
                            'training_complete': False
                        }
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
                    segment_results[segment_key] = {'error': seg_result['error']}
                    all_segment_data[segment_id] = seg_result['segment_data']
                else:
                    segment_results[segment_key] = seg_result['segment_training_result']
                    segment_models[segment_id] = seg_result['model_ids']
                    all_segment_data[segment_id] = seg_result['segment_data']

            # Generate overall model ID
            overall_model_id = f"SEG_AUTO_{uuid.uuid4().hex[:8].upper()}"

            # Prepare metadata
            segments_list = [x.item() if hasattr(x, 'item') else x for x in segments]
            training_metadata = {
                'model_id': overall_model_id,
                'training_mode': 'segment_auto',
                'segment_column': segment_column,
                'segments': segments_list,
                'segment_results': segment_results,
                'segment_models': segment_models,
                'all_segment_data': all_segment_data,
                'config': {
                    'dataset_id': dataset_id,
                    'target_column': target_column,
                    'selected_variables': selected_variables,
                    'selection_mode': selection_mode
                },
                'timestamp': datetime.now().isoformat()
            }

            # Save segment training results
            results_path = os.path.join(self.model_storage_path, f"{overall_model_id}_segment_auto_results.json")
            with open(results_path, 'w') as f:
                json.dump(training_metadata, f, indent=2, default=str)

            # Get unified results for immediate use
            unified_results = self.get_unified_segment_results(overall_model_id)

            # Return comprehensive response
            return {
                'success': True,
                'model_id': overall_model_id,
                'training_mode': 'segment_auto',
                'segment_column': segment_column,
                'segments': segments_list,
                'total_segments': len(segments),
                'successful_segments': len([r for r in segment_results.values() if 'error' not in r]),
                'segment_results': segment_results,
                'segment_models': segment_models,
                'unified_results': unified_results,
                'all_segment_data': all_segment_data,
                'message': f'Successfully trained auto models for {len([r for r in segment_results.values() if "error" not in r])} out of {len(segments)} segments'
            }

        except Exception as e:
            self.logger.error(f"Error in segment auto training: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def get_unified_segment_results(self, model_id: str) -> Dict[str, Any]:
        """
        Get unified segment results for dashboard display with segment selector

        Args:
            model_id: Overall segment model ID

        Returns:
            Dictionary with unified results for all segments
        """
        try:
            results_path = os.path.join(self.model_storage_path, f"{model_id}_segment_auto_results.json")

            if not os.path.exists(results_path):
                return {'error': f'Model {model_id} not found'}

            with open(results_path, 'r') as f:
                training_results = json.load(f)

            segments = training_results.get('segments', [])
            segment_results_data = training_results.get('segment_results', {})
            all_segment_data = training_results.get('all_segment_data', {})

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
                    unified_segments[segment_id] = {
                        'segment_id': segment_id,
                        'error': segment_result['error'],
                        'training_complete': False
                    }
                    continue

                # Extract algorithms and metrics for this segment
                # Store ALL models in a list (not keyed by algorithm to avoid overwrites)
                segment_models_list = []
                segment_best_algorithm = None
                segment_best_score = -1
                segment_best_model_id = None

                problem_type = segment_result.get('problem_type', 'classification')
                if 'results' in segment_result:
                    for model_result in segment_result['results']:
                        if 'model_id' not in model_result or 'error' in model_result:
                            continue

                        algorithm = model_result.get('algorithm', 'Unknown')
                        metrics = model_result.get('metrics', {})

                        # Get primary score
                        if 'classification' in problem_type.lower():
                            primary_score = metrics.get('auc', metrics.get('accuracy', 0))
                            primary_metric = 'auc'
                        else:
                            primary_score = metrics.get('r2', 0)
                            primary_metric = 'r2'

                        # Store ALL models in a list (fixes issue where multiple models of same algorithm were overwritten)
                        model_info = {
                            'model_id': model_result['model_id'],
                            'algorithm': algorithm,
                            'primary_score': primary_score,
                            'primary_metric': primary_metric,
                            'metrics': metrics,
                            'hyperparameters': model_result.get('hyperparameters', {}),
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

                # Get additional segment data
                segment_data = all_segment_data.get(segment_id, {})

                # Store segment data with all models
                unified_segments[segment_id] = {
                    'segment_id': segment_id,
                    'segment_size': segment_data.get('segment_size', 0),
                    'models': segment_models_list,  # All models as a list
                    'algorithms': {m['algorithm']: m for m in segment_models_list},  # Also provide dict for backward compat
                    'best_algorithm': segment_best_algorithm,
                    'best_score': segment_best_score,
                    'best_model_id': segment_best_model_id,
                    'total_models': len(segment_models_list),
                    'total_algorithms': len(set(m['algorithm'] for m in segment_models_list)),  # Unique algorithms count
                    'training_complete': True,
                    'problem_type': problem_type
                }

            return {
                'model_id': model_id,
                'training_mode': 'segment_auto',
                'segments': segments,  # Return as array for frontend compatibility
                'segments_data': unified_segments,  # Detailed segment data as dict
                'segment_list': segments,  # Alias for backward compatibility
                'segment_results': segment_results_data,  # Full segment results for frontend (used in graphs)
                'segment_column': training_results.get('segment_column', 'segment'),
                'overall_best_algorithm': overall_best_algorithm,
                'overall_best_score': overall_best_score,
                'total_segments': len(segments),
                'successful_segments': len([s for s in unified_segments.values() if s.get('training_complete', False)])
            }

        except Exception as e:
            self.logger.error(f"Error getting unified segment results: {str(e)}")
            return {'error': str(e)}

    def get_segment_training_results(self, model_id: str, segment_id: str) -> Dict[str, Any]:
        """
        Get detailed training results for a specific segment

        Args:
            model_id: Overall segment model ID
            segment_id: Specific segment ID

        Returns:
            Dictionary with segment-specific training results
        """
        try:
            results_path = os.path.join(self.model_storage_path, f"{model_id}_segment_auto_results.json")

            if not os.path.exists(results_path):
                return {'error': f'Model {model_id} not found'}

            with open(results_path, 'r') as f:
                training_results = json.load(f)

            segment_key = f'segment_{segment_id}'
            if segment_key not in training_results['segment_results']:
                return {'error': f'Segment {segment_id} not found in model {model_id}'}

            segment_result = training_results['segment_results'][segment_key]
            segment_data = training_results.get('all_segment_data', {}).get(segment_id, {})

            return {
                'segment_id': segment_id,
                'model_id': model_id,
                'segment_result': segment_result,
                'segment_data': segment_data,
                'segment_info': {
                    'segment_column': training_results.get('segment_column'),
                    'segment_size': segment_data.get('segment_size', 0)
                }
            }

        except Exception as e:
            self.logger.error(f"Error getting segment training results: {str(e)}")
            return {'error': str(e)}


# Create singleton instance
segment_auto_training_service = SegmentTrainingAutoService()
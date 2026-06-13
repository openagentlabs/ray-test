import pandas as pd
from app.services.dataframe_state_manager import dataframe_state_manager
from typing import Dict, Any, Optional
from app.models.database import message_state_db
from app.services.agentic_system import MessageState
from app.services.dataset_service import dataset_manager
from app.core.logging_config import get_logger
from langchain_core.messages import HumanMessage, AIMessage

class MessageStateManager:
    """
    Service to manage MessageState persistence with dataset integration
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.db = message_state_db
        # In-memory cache for modelling artifacts (workaround for database persistence issues)
        self._modelling_artifacts_cache: Dict[str, Dict[str, Any]] = {}
        self.logger.info("MessageStateManager initialized with modelling artifacts cache")
    
    def create_or_load_state(self, dataset_id: str, userquery: str = "") -> MessageState:
        """
        Create a new MessageState or load existing one from database
        """
        self.logger.info(f"Creating or loading MessageState for dataset: {dataset_id}")
        
        # Try to load existing state first
        existing_state = self.db.load_message_state(dataset_id)
        
        if existing_state:
            self.logger.info(f"Found existing MessageState for dataset: {dataset_id}")
            return self._reconstruct_message_state(existing_state, dataset_id, userquery)
        else:
            self.logger.info(f"Creating new MessageState for dataset: {dataset_id}")
            return self._create_new_message_state(dataset_id, userquery)
    
    def _create_new_message_state(self, dataset_id: str, userquery: str = "") -> MessageState:
        """Create a fresh MessageState"""
        # Get dataset info
        dataset_info = dataset_manager.get_dataset_info(dataset_id)
        if not dataset_info:
            raise ValueError(f"Dataset not found: {dataset_id}")
        
        # Prefer in-memory frame (copy from state manager), else load CSV from disk
        df = dataframe_state_manager.get_dataframe(dataset_id)
        if df is not None:
            self.logger.info(
                f"Using DataFrame from DataFrameStateManager for dataset: {dataset_id}, shape: {df.shape}"
            )
        else:
            df = dataset_manager.load_dataset(dataset_id)
            if df is None:
                raise ValueError(f"Failed to load dataset: {dataset_id}")
            self.logger.info(
                f"Loaded dataset from file for dataset: {dataset_id}, shape: {df.shape}"
            )

        # Initialize fresh state
        state = MessageState()
        state["userquery"] = userquery
        state["datasetFile"] = df
        state["previousDatasetFile"] = None
        state["projectDescFile"] = dataset_info.get('problem_statement', '')
        state["dataDesc"] = dataset_info.get('data_dictionary', '')
        state["datasetFileName"] = dataset_info.get('filename', '')
        state["chat_history"] = []
        state["messages"] = []
        state["plan"] = ""
        state["generatedCode"] = ""
        state["summary"] = ""
        state["intent"] = ""
        state["planExist"] = ""
        state["approved"] = False
        state["notes"] = []
        state["dataset_id"] = dataset_id  # Add dataset_id to the state
        
        # Initialize QC pipeline fields
        state["qc_mode"] = None
        state["treatment_sequence"] = None
        state["current_treatment_index"] = None
        state["completed_treatments"] = []
        state["skipped_treatments"] = []
        state["quality_detections"] = {}
        state["quality_plans"] = {}
        state["qc_templates"] = {}
        state["qc_ui_selections"] = {}
        
        self.logger.info(f"Created new MessageState for dataset: {dataset_id}")
        return state
    
    def _reconstruct_message_state(self, state_data: Dict[str, Any], dataset_id: str, userquery: str = "") -> MessageState:
        """Reconstruct MessageState from database data"""
        # Get dataset info for metadata
        dataset_info = dataset_manager.get_dataset_info(dataset_id)
        if not dataset_info:
            raise ValueError(f"Dataset not found: {dataset_id}")
        
        # Prefer latest in-memory transformed data first so stale DB snapshots
        # do not override post-treatment/dedup changes.
        df = dataframe_state_manager.get_dataframe(dataset_id)
        if df is not None:
            self.logger.info(
                f"Using DataFrame from DataFrameStateManager for dataset: {dataset_id}, shape: {df.shape} (source=state_manager)"
            )
        elif 'datasetFile' in state_data and isinstance(state_data['datasetFile'], pd.DataFrame):
            df = state_data['datasetFile']
            self.logger.info(
                f"Using DataFrame restored from database for dataset: {dataset_id}, shape: {df.shape} (source=db_snapshot)"
            )
        else:
            df = dataset_manager.load_dataset(dataset_id)
            if df is None:
                raise ValueError(f"Failed to load dataset: {dataset_id}")
            self.logger.info(
                f"Loaded dataset from file for dataset: {dataset_id}, shape: {df.shape} "
                f"(source=disk; no state-manager or DB snapshot available)"
            )
        
        # Reconstruct MessageState
        state = MessageState()
        
        # Update with new query if provided, otherwise use stored query
        state["userquery"] = userquery if userquery else state_data.get('userquery', '')
        state["datasetFile"] = df
        state["previousDatasetFile"] = state_data.get('previousDatasetFile') if isinstance(state_data.get('previousDatasetFile'), pd.DataFrame) else None
        state["projectDescFile"] = state_data.get('projectDescFile', dataset_info.get('problem_statement', ''))
        state["dataDesc"] = state_data.get('dataDesc', dataset_info.get('data_dictionary', ''))
        state["datasetFileName"] = state_data.get('datasetFileName', dataset_info.get('filename', ''))
        state["chat_history"] = state_data.get('chat_history', [])
        state["plan"] = state_data.get('plan', '')
        state["generatedCode"] = state_data.get('generatedCode', '')
        state["summary"] = state_data.get('summary', '')
        state["intent"] = state_data.get('intent', '')
        state["planExist"] = state_data.get('planExist', '')
        state["approved"] = state_data.get('approved', False)
        state["notes"] = state_data.get('notes', [])
        state["dataset_id"] = dataset_id  # Add dataset_id to the state
        
        # Restore QC pipeline fields - these are stored in modelling_artifacts in database
        # but load_message_state() already merges modelling_artifacts into state_data via state.update()
        # So QC fields should be directly in state_data at this point
        
        # Log what we have for debugging
        self.logger.info(f"QC fields in state_data: qc_mode={state_data.get('qc_mode')}, treatment_sequence={state_data.get('treatment_sequence')}, current_idx={state_data.get('current_treatment_index')}")
        
        state["qc_mode"] = state_data.get('qc_mode')
        state["treatment_sequence"] = state_data.get('treatment_sequence')
        state["current_treatment_index"] = state_data.get('current_treatment_index')
        state["completed_treatments"] = state_data.get('completed_treatments', [])
        state["skipped_treatments"] = state_data.get('skipped_treatments', [])
        state["treatment_statuses"] = state_data.get('treatment_statuses', {})
        state["quality_detections"] = state_data.get('quality_detections', {})
        state["quality_plans"] = state_data.get('quality_plans', {})
        state["qc_metrics"] = state_data.get('qc_metrics', {})
        state["qc_sequence_complete"] = state_data.get('qc_sequence_complete', False)
        state["qc_templates"] = state_data.get('qc_templates', {})
        state["qc_ui_selections"] = state_data.get('qc_ui_selections', {})
        
        # Log QC state restoration for debugging
        if state["treatment_sequence"]:
            self.logger.info(f"Restored QC state: mode={state['qc_mode']}, sequence={state['treatment_sequence']}, current_idx={state['current_treatment_index']}")

        # Preserve additional modelling context fields that downstream agents rely on
        # (VIF/IV/correlation tables, used_features, training results, etc.)
        modelling_keys = [
            "variable_analysis",
            "variableAnalysis",
            "variable_analysis_context",
            "variable_statistics",
            "training_context",
            "training_progress",
            "trainingProgress",
            "train_ctx",
            "used_features",
            "used_features_short",
            "results",
            "model_comparison",
            "best_model_summary",
            "best_model",
            "model_id",
            "cv_summary",
            "confusion_matrix_summary",
            "comparison_results_json",
            "calibration_threshold_info",
            "segment_info",
            "model_params_short",
            "auto_selection_summary",
            "algorithm_selection",
            "variable_selection",
            "segmentation_insight_pins",
        ]
        for key in modelling_keys:
            if key in state_data and key not in state:
                state[key] = state_data.get(key)
        
        # Also check in-memory cache for modelling artifacts (workaround for database issues)
        if dataset_id in self._modelling_artifacts_cache:
            cached_artifacts = self._modelling_artifacts_cache[dataset_id]
            self.logger.info(f"Loading modelling artifacts from in-memory cache for dataset {dataset_id}: {list(cached_artifacts.keys())}")
            for key, value in cached_artifacts.items():
                if key not in state or state[key] is None:
                    state[key] = value
                    if key == "used_features" and isinstance(value, list):
                        self.logger.info(f"  - Restored used_features from cache: {len(value)} features")
        
        # Reconstruct messages (simplified for now)
        messages = []
        stored_messages = state_data.get('messages', [])
        for msg_data in stored_messages:
            if isinstance(msg_data, dict):
                if msg_data.get('type') == 'HumanMessage':
                    messages.append(HumanMessage(content=msg_data.get('content', '')))
                elif msg_data.get('type') == 'AIMessage':
                    messages.append(AIMessage(content=msg_data.get('content', '')))
            # If it's already a message object, keep it as is
            elif hasattr(msg_data, 'content'):
                messages.append(msg_data)
        
        state["messages"] = messages
        
        self.logger.info(f"Reconstructed MessageState for dataset: {dataset_id}")
        return state
    
    def save_state(self, dataset_id: str, state: MessageState) -> bool:
        """
        Save MessageState to database
        """
        self.logger.info(f"Saving MessageState for dataset: {dataset_id}")
        
        try:
            # Convert MessageState to dictionary for storage
            state_dict = dict(state)
            
            # Debug: Check if DataFrame is in the state
            if 'datasetFile' in state_dict and isinstance(state_dict['datasetFile'], pd.DataFrame):
                self.logger.info(f"DataFrame found in state to save: shape {state_dict['datasetFile'].shape}")
            else:
                self.logger.warning(f"No DataFrame found in state to save for dataset: {dataset_id}")
            if 'previousDatasetFile' in state_dict and isinstance(state_dict['previousDatasetFile'], pd.DataFrame):
                self.logger.info(f"Previous DataFrame snapshot found in state to save: shape {state_dict['previousDatasetFile'].shape}")
            
            # Cache modelling artifacts in memory (workaround for database persistence issues)
            modelling_keys = [
                "variable_analysis", "variableAnalysis", "variable_analysis_context",
                "variable_statistics", "training_context", "training_progress",
                "trainingProgress", "train_ctx", "used_features", "used_features_short",
                "results", "model_comparison", "best_model_summary", "best_model",
                "model_id", "cv_summary", "confusion_matrix_summary",
                "comparison_results_json", "calibration_threshold_info",
                "segment_info", "model_params_short", "auto_selection_summary",
                "algorithm_selection", "variable_selection",
                "segmentation_insight_pins",
            ]
            
            artifacts_to_cache = {}
            for key in modelling_keys:
                if key in state_dict and state_dict[key] is not None:
                    artifacts_to_cache[key] = state_dict[key]
            
            if artifacts_to_cache:
                self._modelling_artifacts_cache[dataset_id] = artifacts_to_cache
                self.logger.info(f"✅ Cached modelling artifacts in memory for dataset {dataset_id}: {list(artifacts_to_cache.keys())}")
                if "used_features" in artifacts_to_cache:
                    uf = artifacts_to_cache["used_features"]
                    self.logger.info(f"  - Cached used_features: {len(uf) if isinstance(uf, list) else 'N/A'} features")
            
            # Save to database
            success = self.db.save_message_state(dataset_id, state_dict)
            
            if success:
                self.logger.info(f"MessageState saved successfully for dataset: {dataset_id}")
            else:
                self.logger.error(f"Failed to save MessageState for dataset: {dataset_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error saving MessageState for {dataset_id}: {str(e)}")
            return False
    
    def update_state_with_query(self, dataset_id: str, state: MessageState, new_query: str) -> MessageState:
        """
        Update existing state with new user query and add to chat history
        """
        self.logger.info(f"Updating MessageState with new query for dataset: {dataset_id}")
        
        # Add previous query to chat history if it exists
        if state.get("userquery"):
            chat_entry = {
                "timestamp": pd.Timestamp.now().isoformat(),
                "query": state["userquery"],
                "response": state.get("summary", ""),
                "intent": state.get("intent", "")
            }
            
            if "chat_history" not in state:
                state["chat_history"] = []
            state["chat_history"].append(chat_entry)
        
        # Update with new query
        state["userquery"] = new_query
        
        # Reset response fields for new query (but keep context)
        state["plan"] = ""
        state["generatedCode"] = ""
        state["summary"] = ""
        state["intent"] = ""
        state["approved"] = False
        
        # Keep accumulated notes but don't reset them
        if "notes" not in state:
            state["notes"] = []
        
        self.logger.info(f"Updated MessageState with new query for dataset: {dataset_id}")
        return state
    
    def delete_state(self, dataset_id: str) -> bool:
        """
        Delete MessageState from database
        """
        self.logger.info(f"Deleting MessageState for dataset: {dataset_id}")
        
        success = self.db.delete_message_state(dataset_id)
        
        if success:
            self.logger.info(f"MessageState deleted successfully for dataset: {dataset_id}")
        else:
            self.logger.warning(f"No MessageState found to delete for dataset: {dataset_id}")
        
        return success
    
    def list_all_states(self):
        """List all stored MessageStates"""
        return self.db.list_all_states()
    
    def cleanup_old_states(self, days_old: int = 30) -> int:
        """Cleanup old MessageStates"""
        return self.db.cleanup_old_states(days_old)

# Global instance
message_state_manager = MessageStateManager()


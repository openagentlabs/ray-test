import json
import polars as pl
import numpy as np
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from langchain_core.messages import HumanMessage, AIMessage
from app.services.llm_service import llm_service
from app.services.dataset_service import dataset_manager
from app.utils.helpers import generate_bivariate_tables_for_standard_insights
from app.services.vector_store import vector_store
from app.services.dataframe_state_manager import dataframe_state_manager
from app.core.config import settings
from app.core.logging_config import get_logger, hash_for_log

class MessageState(dict):
    """Manages the State"""
    messages: Annotated[list, add_messages]
    userquery: str
    plan: str
    generatedCode: str
    summary: str
    intent: str
    planExist: str
    approved: bool
    notes: List[str]
    datasetFileName: str
    chat_history: list[dict]
    dataset_id: str  # Added dataset_id to MessageState schema

    # filepaths
    datasetFile: pl.DataFrame
    projectDescFile: str
    dataDesc: str

class DatasetAnalyser:
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def generate_dataset_summary(self, df: pl.DataFrame, dataset_id: str = None) -> str:
        """Generate comprehensive dataset summary"""
        self.logger.info(f"Generating dataset summary for shape: {df.shape}")
        summary_parts = []
        
        # Basic info
        summary_parts.append(f"SHAPE: {df.shape[0]} rows × {df.shape[1]} columns")
        # TODO: Polars memory usage calculation - using estimated_size() as approximation
        memory_mb = df.estimated_size() / 1024**2 if hasattr(df, 'estimated_size') else 0.0
        summary_parts.append(f"MEMORY USAGE: {memory_mb:.2f} MB")
        
        # ML Problem Type Detection
        if dataset_id:
            try:
                ds_info = dataset_manager.get_dataset_info(dataset_id)
                if ds_info and ds_info.get('target_variable'):
                    target_var = ds_info['target_variable']
                    if target_var in df.columns:
                        from app.utils.problem_type_detector import infer_problem_type
                        problem_type = infer_problem_type(df[target_var])
                        target_type = ds_info.get('target_variable_type', 'unknown')
                        unique_count = df[target_var].n_unique()
                        
                        summary_parts.append(f"\nML PROBLEM TYPE DETECTION:")
                        summary_parts.append(f"  Target Variable: {target_var}")
                        summary_parts.append(f"  Detected Problem Type: {problem_type.value.upper()}")
                        summary_parts.append(f"  Target Variable Type: {target_type}")
                        summary_parts.append(f"  Unique Target Values: {unique_count}")
                        
                        if problem_type.value == 'classification':
                            if unique_count == 2:
                                summary_parts.append(f"  Classification Type: BINARY")
                            else:
                                summary_parts.append(f"  Classification Type: MULTICLASS ({unique_count} classes)")
                        else:
                            summary_parts.append(f"  Regression Type: CONTINUOUS")
            except Exception as e:
                self.logger.warning(f"Could not detect ML problem type: {str(e)}")
        
        # Columns and types
        summary_parts.append(f"\nCOLUMNS:")
        for col in df.columns:
            dtype = str(df[col].dtype)
            non_null = df[col].count()
            null_pct = (df[col].null_count() / len(df)) * 100
            summary_parts.append(f"  {col}: {dtype} | {non_null} non-null ({100-null_pct:.1f}%)")
        
        # Data type distribution - Polars uses schema
        dtype_counts = {}
        for col, dtype in df.schema.items():
            dtype_str = str(dtype)
            dtype_counts[dtype_str] = dtype_counts.get(dtype_str, 0) + 1
        summary_parts.append(f"\nDATA TYPES: {dtype_counts}")
        
        # Missing values - Polars approach
        missing_dict = {}
        for col in df.columns:
            null_count = df[col].null_count()
            if null_count > 0:
                missing_dict[col] = null_count
        if missing_dict:
            summary_parts.append(f"\nMISSING VALUES:")
            for col, count in missing_dict.items():
                pct = (count / len(df)) * 100
                summary_parts.append(f"  {col}: {count} ({pct:.1f}%)")
        else:
            summary_parts.append("\nMISSING VALUES: None")
        
        # Duplicates - Enhanced analysis similar to missing values
        dup_count = df.is_duplicated().sum()
        dup_pct = (dup_count / len(df) * 100) if len(df) > 0 else 0
        summary_parts.append(f"\nDUPLICATE ROWS: {dup_count} ({dup_pct:.1f}%)")
        
        # Detailed duplicate analysis (similar to missing values)
        if dup_count > 0:
            summary_parts.append(f"\nDUPLICATE DETAILS:")
            # Show total unique vs duplicate
            unique_rows = len(df) - dup_count
            summary_parts.append(f"  Total rows: {len(df)}")
            summary_parts.append(f"  Unique rows: {unique_rows}")
            summary_parts.append(f"  Duplicate rows: {dup_count}")
            
            # Find which columns contribute most to duplicates
            col_list = df.columns.tolist()[:10]  # Limit to first 10 columns for performance
            col_dup_info = []
            for col in col_list:
                try:
                    col_dup_count = df.is_duplicated(subset=[col]).sum()
                    if col_dup_count > 0:
                        col_dup_pct = (col_dup_count / len(df)) * 100
                        col_dup_info.append((col, col_dup_count, col_dup_pct))
                except:
                    continue
            
            # Report top contributing columns
            if col_dup_info:
                col_dup_info.sort(key=lambda x: x[1], reverse=True)
                summary_parts.append(f"  Top columns with duplicate values:")
                for col, count, pct in col_dup_info[:5]:  # Top 5 columns
                    summary_parts.append(f"    - {col}: {count} rows ({pct:.1f}%)")
        else:
            summary_parts.append(f"  No duplicate rows detected")
        
        # Outliers - Enhanced analysis similar to missing values
        # TODO: Polars select_dtypes equivalent - select numeric columns
        numeric_cols = [col for col in df.columns if df[col].dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64, pl.Float32, pl.Float64]]
        if numeric_cols:
            summary_parts.append(f"\nOUTLIER ANALYSIS (IQR Method):")
            outlier_info = []
            for col in numeric_cols:
                try:
                    # Skip columns with all NaN or insufficient data
                    col_data = df[col].drop_nulls()
                    if len(col_data) < 4:  # Need at least 4 values for quartiles
                        continue
                    
                    # Calculate IQR method outliers on non-null values
                    Q1 = col_data.quantile(0.25)
                    Q3 = col_data.quantile(0.75)
                    IQR = Q3 - Q1
                    
                    # Skip if IQR is 0 (all values are the same)
                    if IQR == 0:
                        continue
                    
                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR
                    
                    # Count outliers in original dataframe
                    outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
                    outlier_count = outlier_mask.sum()
                    
                    if outlier_count > 0:
                        outlier_pct = (outlier_count / len(df)) * 100
                        outlier_info.append((col, outlier_count, outlier_pct))
                except Exception as e:
                    self.logger.debug(f"Could not calculate outliers for {col}: {str(e)}")
                    continue
            
            # Display outlier information (format matches missing values)
            if outlier_info:
                for col, count, pct in outlier_info:
                    summary_parts.append(f"  {col}: {count} ({pct:.1f}%)")
            else:
                summary_parts.append(f"  No significant outliers detected")
        
        # Numeric columns analysis
        if numeric_cols:
            summary_parts.append(f"\nNUMERIC COLUMNS ({len(numeric_cols)}): {', '.join(numeric_cols)}")
            summary_parts.append("\nNUMERIC SUMMARY:")
            summary_parts.append(str(df[numeric_cols].describe().round(3)))
        
        # Categorical columns analysis
        # TODO: Polars select_dtypes equivalent - select string/categorical columns
        cat_cols = [col for col in df.columns if df[col].dtype == pl.Utf8]
        if cat_cols:
            summary_parts.append(f"\nCATEGORICAL COLUMNS ({len(cat_cols)}):")
            for col in cat_cols[:8]:  # Show first 8 categorical columns
                unique_count = df[col].n_unique()
                if unique_count <= 10:
                    top_values = df[col].value_counts().head(5).to_dict()
                    summary_parts.append(f"  {col}: {unique_count} unique | Top values: {top_values}")
                else:
                    summary_parts.append(f"  {col}: {unique_count} unique values")
        
        # Date columns
        # TODO: Polars select_dtypes equivalent - select date columns
        date_cols = [col for col in df.columns if df[col].dtype in [pl.Datetime, pl.Date]]
        if date_cols:
            summary_parts.append(f"\nDATE COLUMNS: {', '.join(date_cols)}")
            for col in date_cols:
                min_date = df[col].min()
                max_date = df[col].max()
                summary_parts.append(f"  {col}: {min_date} to {max_date}")
        
        # Sample data
        summary_parts.append(f"\nSAMPLE DATA (first 3 rows):")
        # TODO: Polars to_string - may need to convert to pandas for display
        summary_parts.append(str(df.head(3)))
        
        # Critical instructions for LLM
        summary_parts.append(f"\n=== CRITICAL INSTRUCTIONS FOR CODE GENERATION ===")
        summary_parts.append(f"1. ONLY use columns that exist in the current dataset: {list(df.columns)}")
        summary_parts.append(f"2. If the plan mentions columns not in this list, adapt your code to use available columns")
        summary_parts.append(f"3. Check data types and missing values before generating code")
        summary_parts.append(f"4. Generate code that will work with the current dataset state")
        
        summary = "\n".join(summary_parts)
        self.logger.info("Dataset summary generated successfully")
        return summary

class AgentPrompt:
    def __init__(self, summary_info: str, project_summary: str, description: str, kb_context: str, userquery: str):
        self.logger = get_logger(__name__)

        _ap_extra: Dict[str, Any] = {
            "event": "agent_prompt_init",
            "log_category": "agent",
            "summary_info_chars": len(summary_info) if summary_info else 0,
        }
        if settings.LOG_PROMPT_HASH and summary_info:
            _ap_extra["summary_info_sha256"] = hash_for_log(summary_info)
        self.logger.info("agent_prompt_init", extra=_ap_extra)

        self.generate_new_plan = f"""
            Always have a close eye on the knowledge base and summary and follow the instructions. You can't afford have any mistakes here. You must adhere to every instructions in the knowledge base without fail. Any deviation no matter how small will result immediate termination. Whereas if you perfectly able to give correct recommendations and treatment based on the knowledge base and data summary, you will be rewarded with a bonus of $5M USD
 
            Below is the dataset INFO:

            DATASET TECHNICAL SUMMARY: {summary_info} 
            DATASET DATA DESCRIPTION: {description}
            DATASET PROJECT DESCRIPTION: {project_summary}
            
            Cover all the points from below:
            {userquery}

            AVAILABLE CATEGORIES (use these exact field names in your response):
            - missing_values: For missing value imputation and handling (column-by-column analysis)
            - outliers: For outlier detection and treatment (column-by-column analysis)
            - duplicates: For duplicate row detection and removal (dataset-level analysis)
            
            CATEGORY MAPPING GUIDE (DO NOT CONFUSE THESE):
            - User mentions "missing values", "missing data", "null values" → use "missing_values" category
            - User mentions "outliers", "outlier treatment", "extreme values" → use "outliers" category (NOT duplicates!)
            - User mentions "duplicates", "duplicate rows", "deduplication", "duplicate removal" → use "duplicates" category (NOT outliers!)
            
            ⚠️ WARNING: "outliers" and "duplicates" are COMPLETELY DIFFERENT:
            - Outliers = extreme values in numeric columns (column-by-column)
            - Duplicates = repeated rows in dataset (dataset-level)
            - DO NOT mix these up or include both when only one is requested!

            CATEGORY-SPECIFIC INSTRUCTIONS:
            
            For MISSING VALUES:
            - Analyze each column with missing values
            - Provide detection: "X missing values (Y%)"
            - Provide treatment: "median imputation", "mode imputation", "mean imputation", or "Drop from analysis"
            
            For OUTLIERS:
            - Analyze each numeric column for outliers
            - Check "OUTLIER ANALYSIS (IQR Method)" section in dataset summary for the exact counts
            - The summary format is: "column_name: X (Y%)" where X is outlier count and Y is percentage
            - Provide detection: "X outliers (Y%)" - use the EXACT count and percentage from summary
            - Provide treatment: "Cap at 99th percentile", "Cap at 95th percentile", "Cap at 90th percentile", etc.
            - Example format:
              {{"name": "loan_amnt", "detection": "50 outliers (5.0%)", "treatment": "Cap at 99th percentile"}}
            - CRITICAL: Read the outlier counts directly from "OUTLIER ANALYSIS (IQR Method)" section, just like you read missing values
            
            For DUPLICATES:
            - Analyze dataset for duplicate rows
            - Check DUPLICATE ROWS section in dataset summary for the count
            - Provide ONE entry with name="Dataset" or "All rows"
            - Provide detection: "X duplicate rows found (Y% of dataset)" - use the exact count from summary
            - Provide treatment: "Drop all duplicates", "Drop duplicates keep first", or "Drop duplicates keep last"
            - Example format:
              {{"name": "Dataset", "detection": "150 duplicate rows found (15.0% of dataset)", "treatment": "Drop all duplicates"}}

            INSTRUCTION:
            1. If you have multiple recommendation for {userquery} combine it into one keyvalue pair
            2. The Key should always be unique and must match one of the AVAILABLE CATEGORIES above
            3. For missing_values and outliers: Provide detection and treatment for each variable individually in bullets format
            4. For duplicates: Provide ONE entry for the entire dataset with the duplicate row count from the summary
            5. **CRITICAL**: Provide ONLY the categories explicitly mentioned in the userquery({userquery}). DO NOT include any other categories.
            6. **CRITICAL**: If the user asks for "duplicates" only, your response must ONLY contain the "duplicates" field. Do NOT include "missing_values" or "outliers".
            7. **CRITICAL**: If the user asks for "missing_values" only, your response must ONLY contain the "missing_values" field. Do NOT include other categories.
            8. **CRITICAL**: If the user asks for "outliers" only, your response must ONLY contain the "outliers" field with column-by-column analysis. Do NOT return "duplicates" or "missing_values".
            9. **CRITICAL FOR OUTLIERS**: When user asks for "outliers", analyze EACH numeric column from "OUTLIER ANALYSIS (IQR Method)" section and create one entry per column. DO NOT create dataset-level entry like duplicates.
            10. Even if the dataset summary shows missing values or duplicates, do NOT generate plans for them unless explicitly requested in userquery
            11. As for treatment, provide only one treatment for each variable which is most relevant to the variable distribution
            12. IMPORTANT: Map user query terms to the correct category field names listed above
            13. CRITICAL FOR DUPLICATES: Always read the "DUPLICATE ROWS" count from the dataset summary and include it in your detection message
            14. CRITICAL FOR OUTLIERS: Always read the "OUTLIER ANALYSIS (IQR Method)" section from the dataset summary and include the exact counts in your detection message
            15. **CRITICAL**: User query "outliers" means analyze outliers, NOT duplicates. User query "duplicates" means analyze duplicates, NOT outliers. These are completely different analyses!
            16 **CRITICAL** ALways provide detection and treatment plan for all the variables in the dataset.
            EXAMPLES OF CORRECT BEHAVIOR:
            
            Example 1 - User asks for "duplicates" only:
            Userquery: "Please run the following data quality checks on my dataset: duplicates"
            Correct Response: {{"duplicates": [{{"name": "Dataset", "detection": "150 duplicate rows (15%)", "treatment": "Drop all duplicates"}}]}}
            WRONG Response: {{"duplicates": [...], "missing_values": [...]}}  ❌ DO NOT DO THIS
            
            Example 2 - User asks for "missing values" only:
            Userquery: "Please run the following data quality checks on my dataset: missing_values"
            Correct Response: {{"missing_values": [{{"name": "column1", "detection": "50 missing (5%)", "treatment": "median imputation"}}]}}
            WRONG Response: {{"missing_values": [...], "outliers": [...]}}  ❌ DO NOT DO THIS
            
            Example 3 - User asks for "outliers" only:
            Userquery: "Please run the following data quality checks on my dataset: outliers"
            Correct Response: {{"outliers": [{{"name": "loan_amnt", "detection": "50 outliers (5.0%)", "treatment": "Cap at 99th percentile"}}, {{"name": "annual_inc", "detection": "75 outliers (7.5%)", "treatment": "Cap at 95th percentile"}}]}}
            WRONG Response: {{"outliers": [...], "duplicates": [...]}}  ❌ DO NOT DO THIS
            WRONG Response: {{"duplicates": [...]}}  ❌ DO NOT DO THIS - user asked for outliers, not duplicates!
            
            Example 4 - User asks for multiple checks:
            Userquery: "Please run the following data quality checks on my dataset: missing_values, duplicates"
            Correct Response: {{"missing_values": [...], "duplicates": [...]}}
            WRONG Response: {{"missing_values": [...], "duplicates": [...], "outliers": [...]}}  ❌ DO NOT DO THIS
            
            Example 5 - Full outliers response (multi-column):
            Userquery: "Please run the following data quality checks on my dataset: outliers"
            Dataset Summary shows:
              OUTLIER ANALYSIS (IQR Method):
                loan_amnt: 50 (5.0%)
                annual_inc: 75 (7.5%)
                int_rate: 30 (3.0%)
            Correct Response: {{
              "outliers": [
                {{"name": "loan_amnt", "detection": "50 (5.0%)", "treatment": "Cap at 99th percentile"}},
                {{"name": "annual_inc", "detection": "75 (7.5%)", "treatment": "Cap at 95th percentile"}},
                {{"name": "int_rate", "detection": "30 (3.0%)", "treatment": "Cap at 99th percentile"}}
              ]
            }}
            WRONG Response: {{"duplicates": [...]}}  ❌ COMPLETELY WRONG - user asked for outliers!
            WRONG Response: {{"outliers": [...], "duplicates": [...]}}  ❌ DO NOT ADD duplicates when not requested!

            KNOWLEDGE BASE : {kb_context}
            """

class AgenticSystem:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.dataset_analyser = DatasetAnalyser()
    
    def _process_plan_for_llm(self, plan_data: str) -> str:
        """
        Process plan data to create final_treatment column with selective override logic.
        This ensures LLM gets the correct treatment values while keeping existing flow untouched.
        """
        try:
            if not plan_data or not plan_data.strip():
                return plan_data
            
            # Parse the plan data
            plan_dict = json.loads(plan_data)
            
            # Counters for tracking custom vs original treatments
            custom_count = 0
            original_count = 0
            
            # Process each category in the plan
            for category, items in plan_dict.items():
                if isinstance(items, list):
                    # Array format: [{"name": "...", "treatment": "...", "custom_treatment": "..."}]
                    for item in items:
                        if isinstance(item, dict):
                            # Create final_treatment column with selective override logic
                            original_treatment = item.get('treatment', '')
                            custom_treatment = item.get('custom_treatment', '')
                            
                            # Debug logging
                            self.logger.debug(f"Processing {category} item: name={item.get('name', 'unknown')}, original_treatment='{original_treatment}', custom_treatment='{custom_treatment}'")
                            
                            # Check if custom_treatment is valid (not empty, not placeholder)
                            if (custom_treatment and 
                                custom_treatment.strip() and 
                                not custom_treatment.lower().startswith('enter custom') and
                                not custom_treatment.lower().startswith('original:') and
                                custom_treatment.strip() != ''):
                                # Use custom treatment
                                item['final_treatment'] = custom_treatment.strip()
                                custom_count += 1
                                self.logger.info(f"Using custom treatment for {category}: '{custom_treatment.strip()}'")
                            else:
                                # Use original treatment
                                item['final_treatment'] = original_treatment
                                original_count += 1
                                self.logger.info(f"Using original treatment for {category}: '{original_treatment}'")
                            
                            # Remove both treatment and custom_treatment fields after creating final_treatment
                            # Keep only final_treatment field for LLM
                            if 'treatment' in item:
                                del item['treatment']
                            if 'custom_treatment' in item:
                                del item['custom_treatment']
                                
                elif isinstance(items, dict):
                    # Legacy object format: {"name": "...", "treatment": "...", "custom_treatment": "..."}
                    original_treatment = items.get('treatment', '')
                    custom_treatment = items.get('custom_treatment', '')
                    
                    # Debug logging
                    self.logger.debug(f"Processing {category} legacy item: name={items.get('name', 'unknown')}, original_treatment='{original_treatment}', custom_treatment='{custom_treatment}'")
                    
                    # Check if custom_treatment is valid
                    if (custom_treatment and 
                        custom_treatment.strip() and 
                        not custom_treatment.lower().startswith('enter custom') and
                        not custom_treatment.lower().startswith('original:') and
                        custom_treatment.strip() != ''):
                        # Use custom treatment
                        items['final_treatment'] = custom_treatment.strip()
                        custom_count += 1
                        self.logger.info(f"Using custom treatment for {category}: '{custom_treatment.strip()}'")
                    else:
                        # Use original treatment
                        items['final_treatment'] = original_treatment
                        original_count += 1
                        self.logger.info(f"Using original treatment for {category}: '{original_treatment}'")
                    
                    # Remove both treatment and custom_treatment fields after creating final_treatment
                    # Keep only final_treatment field for LLM
                    if 'treatment' in items:
                        del items['treatment']
                    if 'custom_treatment' in items:
                        del items['custom_treatment']
            
            # Convert back to JSON string
            processed_plan = json.dumps(plan_dict, indent=2)
            
            self.logger.info(f"Plan data processed successfully - final_treatment column created. Custom treatments: {custom_count}, Original treatments: {original_count}")
            return processed_plan
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse plan data for processing: {str(e)}")
            return plan_data
        except Exception as e:
            self.logger.error(f"Error processing plan data: {str(e)}")
            return plan_data
    
    
    def _data_transformation_agent_node(self, state: MessageState):
        if not state["plan"] or state["intent"] == 'plan_agent':
            state = self._planner_agent_node(state)
            if state["plan"]:
                self.logger.info(f"Inside if state plan")
                payload = {
                    "response": state["plan"],
                    "data": "",
                    "suggestion": []
                }
                
            state['messages'].append(AIMessage(json.dumps(payload)))
            state['intent'] = 'plan_agent'
            return state
        self.logger.info(f"Processing data transformation request for dataset: {state['datasetFileName']}")
        _uq = state.get("userquery") or ""
        if settings.LOG_SENSITIVE_DEBUG:
            self.logger.debug("User query len=%s preview=%s", len(_uq), _uq[:100])
        else:
            self.logger.debug("User query len=%s", len(_uq))

        # Get the most recent processed DataFrame for code generation
        from app.services.dataframe_state_manager import dataframe_state_manager
        
        # Use DataFrameStateManager to get the latest processed DataFrame
        dataset_id = state.get('dataset_id', 'unknown')
        latest_df = dataframe_state_manager.get_latest_dataframe_for_planning(state['datasetFile'], dataset_id)
        
        # Log which DataFrame is being used for code generation
        self.logger.info(f"Data transformation agent using DataFrame: shape {latest_df.shape}, columns: {list(latest_df.columns)[:5]}...")
        
        # Get current DataFrame context for code generation using the latest DataFrame
        dataset_id = state.get('dataset_id')
        current_df_summary = self.dataset_analyser.generate_dataset_summary(latest_df, dataset_id)
        
        # Process plan data to replace original treatments with custom treatments
        # Reload the latest plan data to ensure custom treatments are included
        from app.services.message_state_service import message_state_manager
        latest_state = message_state_manager.create_or_load_state(state.get('dataset_id', 'unknown'), "")
        latest_plan = latest_state.get('plan', state['plan'])

        processed_plan = self._process_plan_for_llm(latest_plan)

        try:
            _pd = json.loads(processed_plan) if processed_plan else {}
        except Exception:
            _pd = {}
        _plan_flags: Dict[str, Any] = {}
        if isinstance(_pd, dict):
            _plan_flags = {
                "has_missing_values": "missing_values" in _pd,
                "has_outliers": "outliers" in _pd,
                "has_duplicates": "duplicates" in _pd,
            }
        self.logger.info(
            "plan_context_for_code_gen",
            extra={
                "event": "plan_context_for_code_gen",
                "log_category": "agent",
                "latest_plan_chars": len(latest_plan) if isinstance(latest_plan, str) else len(str(latest_plan)),
                "processed_plan_chars": len(processed_plan) if processed_plan else 0,
                **_plan_flags,
            },
        )

        try:
            plan_dict = json.loads(processed_plan)
            if "outliers" in plan_dict and isinstance(plan_dict.get("outliers"), list):
                self.logger.info(f"Outliers section found with {len(plan_dict['outliers'])} items")
                if settings.LOG_SENSITIVE_DEBUG:
                    for i, outlier in enumerate(plan_dict["outliers"]):
                        if isinstance(outlier, dict) and "final_treatment" in outlier:
                            self.logger.info(
                                f"Outlier {i}: {outlier.get('name', 'unknown')} -> final_treatment: '{outlier['final_treatment']}'"
                            )
        except Exception as e:
            self.logger.warning(f"Could not parse processed plan for debugging: {e}")

        prompt = f"""Answer the user questions by adhering to the plan, ensuring that your insights and code are practical and directly useful to the user question, while keeping the context of the dataset in mind. Output should be in a json format with all explanations in response, codes in code and suggestions for next prompt in suggestion.
        
        DATASET FILE NAME: {state["datasetFileName"]}
        USER QUERY: {state['userquery']}
        PLAN: {processed_plan}
        CURRENT DATASET STATE: {current_df_summary}

        CRITICAL INSTRUCTION: You MUST use the 'final_treatment' field from the plan data for ALL operations. Do NOT use hardcoded logic or assumptions. Read the 'final_treatment' field for each variable and implement exactly what it says.
        
        TREATMENT MAPPING EXAMPLES (use these EXACT mappings based on final_treatment field):
        
        MISSING VALUES:
        - "median imputation" → df['column'].fillna(df['column'].median())
        - "mode imputation" → df['column'].fillna(df['column'].mode()[0])
        - "mean imputation" → df['column'].fillna(df['column'].mean())
        - "Drop from analysis" → df.drop(columns=['column'], inplace=True)
        
        OUTLIERS:
        - "Cap at 99th percentile" → df['column'] = df['column'].clip(upper=df['column'].quantile(0.99))
        - "Cap at 50th percentile" → df['column'] = df['column'].clip(upper=df['column'].quantile(0.50))
        - "Cap at 50th percentile." → df['column'] = df['column'].clip(upper=df['column'].quantile(0.50))
        
        DUPLICATES:
        - "Drop all duplicates" → df = df.drop_duplicates()
        - "Drop duplicates keep first" → df = df.drop_duplicates(keep='first')
        - "Drop duplicates keep last" → df = df.drop_duplicates(keep='last')
        - "Drop duplicates on key columns" → df = df.drop_duplicates(subset=['col1', 'col2'], keep='first')
        - "Keep only unique rows" → df = df.drop_duplicates()
        
        GENERAL:
        - "No action needed" → Skip this column
        
        IMPLEMENTATION RULE: For each variable in the plan, check its 'final_treatment' field and implement exactly what it says. Do NOT use hardcoded logic like "0.50 if col=='loan_amnt' else 0.99". Instead, read the final_treatment for each column individually.

        NOTE: 
        1. Include explanations and Keep it crisp and at the top.
        2. Try to understand the userquery and generate the code accordingly
        3. Provide entire code as one snippet
        4. **Donot provide any code in explanations**
        5. If no code generated, return a comment No Code to Display
        6. The length of suggestions should not exceed more than 4
        7. Provide atleast 3 suggestions
        8. Generate code based on the CURRENT DATASET STATE, not just the plan. If the plan mentions operations on columns that don't exist or data has changed in the current dataset, adapt the code accordingly.
        9. While generating the code check each column if it exists in the CURRENT DATASET STATE like if 'column' in df.columns: then use it otherwise skip it.
        10. Make sure the final resulting dataframe is stored in the variable `df`.
        11. Do not include any calls to `df.to_csv()` or any code that writes the dataframe to a file.
        12. CRITICAL: Always use 'final_treatment' field from plan data for all imputation and transformation operations. This is the only treatment field available in the plan data.
        13. IMPLEMENTATION RULES: Follow the exact treatment mapping examples above. For "median imputation" use .median(), for "mode imputation" use .mode()[0], for "mean imputation" use .mean().
        14. COLUMN CHECK: Always check if column exists using 'if column_name in df.columns:' before applying any treatment.
        15. PLAN PARSING: Parse the PLAN data carefully. For each variable, find its 'final_treatment' value and implement exactly what it says. Do NOT make assumptions or use hardcoded logic.
        16. EXAMPLE: If plan shows "loan_amnt" with "final_treatment": "Cap at 50th percentile.", then use df['loan_amnt'] = df['loan_amnt'].clip(upper=df['loan_amnt'].quantile(0.50))
        17. **IMPORTANT: Donot provide any code in explanations and explanations should be crisp and to the point in about 3 lines.**
        """
    
        try:
            state["chat_history"].append({"role":"user", "content": [{"type": "text","text": prompt}]})
            resp = llm_service.get_data_response(prompt, state["chat_history"][-5:])
            state["chat_history"].append({"role":"assistant", "content": [{"type": "text","text": resp}]})
            state['messages'].append(AIMessage(resp))
            self.logger.info("Data transformation completed successfully")
            return state
        except Exception as e:
            self.logger.error(f"Data transformation failed: {str(e)}")
            # Return a fallback response instead of raising
            fallback_response = '{"response": "Sorry, I encountered an error processing your request. Please try again.", "code": "# Error occurred during processing", "suggestion": ["Try simplifying your query", "Check dataset format", "Try again later"]}'
            state['messages'].append(AIMessage(fallback_response))
            return state

    def _modelling_agent_node(self, state: MessageState):
        self.logger.info(f"Processing modelling request for dataset: {state.get('datasetFileName', 'unknown')}")
        _uq = state.get("userquery") or ""
        if settings.LOG_SENSITIVE_DEBUG:
            self.logger.debug("User query len=%s preview=%s", len(_uq), _uq[:100])
        else:
            self.logger.debug("User query len=%s", len(_uq))

        try:
            # Get dataset context
            dataset_id = state.get('dataset_id')
            if not dataset_id:
                raise ValueError("dataset_id is required for modelling agent")
           
            # Get dataset info
            from app.services.dataset_service import dataset_manager
            ds_info = dataset_manager.get_dataset_info(dataset_id)
            if not ds_info:
                raise ValueError(f"Dataset {dataset_id} not found")
           
            # Get current DataFrame for context
            from app.services.dataframe_state_manager import dataframe_state_manager
            latest_df = dataframe_state_manager.get_latest_dataframe_for_planning(
                state.get('datasetFile'), dataset_id
            )
           
            # Generate dataset summary for context
            current_df_summary = self.dataset_analyser.generate_dataset_summary(latest_df, dataset_id)
           
            # Get target variable info
            target_variable = ds_info.get('target_variable', '')
            target_type = ds_info.get('target_variable_type', 'unknown')
           
            # Get knowledge base context
            kb_context = ""
            if vector_store.is_initialized():
                kb_context = vector_store.get_relevant_context(
                    f"model training machine learning {state['userquery']}"
                )
                self.logger.info("Using vector store context for modelling agent")
           
            # Build comprehensive prompt for modelling agent (robust and dataset-agnostic)
            prompt = f"""You are an expert machine learning consultant specializing in model training, algorithm selection, hyperparameter tuning, and model evaluation. Generate complete, executable Python code that works directly with the in-memory DataFrame `df` provided by the system.

DATASET FILE NAME: {state.get('datasetFileName', 'unknown')}
USER QUERY: {state['userquery']}
DATASET SUMMARY: {current_df_summary[:2000]}...
TARGET VARIABLE: {target_variable}
TARGET TYPE: {target_type}
PROJECT DESCRIPTION: {state.get('projectDescFile', 'Not provided')}
DATA DESCRIPTION: {state.get('dataDesc', 'Not provided')}
KNOWLEDGE BASE CONTEXT: {kb_context[:1000] if kb_context else 'Not available'}

AVAILABLE COLUMNS: {list(latest_df.columns)[:50]}

INSTRUCTIONS:
1. Provide clear, concise guidance about the approach in 2-3 sentences.
2. Generate practical, COMPLETE Python code for training and evaluating a model on the provided dataset.
3. Prefer a Pipeline with ColumnTransformer for preprocessing (impute + encode), then the estimator.
4. Handle both binary and multiclass targets robustly.
5. Ensure outputs (metrics) are programmatically consumable and printed.

TARGET HANDLING RULES:
- Prefer the binary target 'target_flag' if it exists and is appropriate.
- If the chosen target is multiclass with string labels (e.g., 'loan_status'):
  - Encode labels with LabelEncoder to integers 0..K-1.
  - Configure XGBoost with objective='multi:softprob' and num_class=K.
  - Use multiclass-compatible metrics (e.g., weighted AUC with ROC AUC OVR).
- For classification, ALWAYS stratify train_test_split with the target y.

CODE GENERATION RULES:
- Libraries: scikit-learn, pandas, numpy, xgboost.
- Do NOT read or write files. Use the in-memory DataFrame `df`.
- Identify columns by dtype:
  - Categorical: object dtype.
  - Numerical: np.number dtype.
- Exclude identifiers and the target from features: 'id', 'member_id', and the selected target column.
- Build a sklearn Pipeline with ColumnTransformer:
  - Numerical: SimpleImputer(strategy='median').
  - Categorical: SimpleImputer(strategy='most_frequent') + OneHotEncoder(handle_unknown='ignore', version-safe:
    - Try: OneHotEncoder(handle_unknown='ignore', sparse_output=True, max_categories=50)
    - Except TypeError: OneHotEncoder(handle_unknown='ignore', sparse=True, max_categories=50)
- XGBoost configuration:
  - Binary: xgb.XGBClassifier(use_label_encoder=False, eval_metric='logloss', random_state=42).
  - Multiclass: xgb.XGBClassifier(objective='multi:softprob', num_class=K, eval_metric='mlogloss', random_state=42).
- Perform train_test_split(test_size=0.2, random_state=42, stratify=y for classification).
- After fitting:
  - For binary: predict_proba to get y_proba[:, 1], then compute AUC with roc_auc_score(y_test, y_proba).
  - For multiclass: predict_proba to get y_proba (n_samples x K), compute AUC with roc_auc_score(y_test, y_proba, multi_class='ovr', average='weighted').
- Extract metrics numerically:
  - For binary: precision_score, recall_score, f1_score on y_pred; AUC on y_proba.
  - For multiclass: classification_report(..., output_dict=True)['weighted avg'] for precision/recall/F1.
  - DO NOT use the plain string from classification_report to build DataFrames.
- Create a pandas DataFrame named results_df with at least: AUC, Precision, Recall, F1-Score.
- Print AUC and a human-readable classification report (string) for the console.
- Ensure the code is COMPLETE and EXECUTABLE.

CRITICAL CODE COMPLETENESS REQUIREMENTS:
- Generate COMPLETE, EXECUTABLE Python code - no incomplete statements, no missing brackets/parentheses.
- All dictionaries must have matching opening {{ and closing }}.
- All lists must have matching opening [ and closing ].
- All function calls must have matching opening ( and closing ).
- All code blocks must be syntactically valid and self-contained.

CRITICAL INDENTATION REQUIREMENTS:
- Use EXACTLY 4 spaces for each indentation level (NO tabs).
- After a line ending with ':', the next line MUST be indented by 4 more spaces.
- Be consistent with indentation throughout.

CRITICAL PIPELINE REQUIREMENTS:
- Use ColumnTransformer with:
  - Numerical: SimpleImputer(strategy='median') on numerical_cols.
  - Categorical: SimpleImputer(strategy='most_frequent') + OneHotEncoder with version-safe parameters on categorical_cols.
- Exclude target and identifier columns from the transformer lists and from X.

CRITICAL VALIDATION RULES:
- Do NOT pre-validate NaNs in X before fitting; the Pipeline handles imputation.
- If validating, do it AFTER pipeline.fit() or pipeline.transform().
- You may validate the target y for NaNs before modeling.

OUTPUT REQUIREMENTS (UI consumption):
- Provide a pandas DataFrame named results_df with at least ['Metric', 'Score'] rows for AUC, Precision, Recall, F1-Score.
- Optionally print a human-readable classification report string.
- Keep variable names consistent: X, y, X_train, X_test, y_train, y_test, model_pipeline (or model), y_pred, y_proba, results_df.

RESPONSE FORMAT:
Return a JSON with:
- "response": 2-3 sentence explanation (no code).
- "code": COMPLETE Python code snippet (as a string).
- "suggestion": A list of 3-4 relevant next steps (e.g., hyperparameter tuning, feature importance, cross-validation).

IMPORTANT:
- Keep explanations crisp (about 3 lines).
- Generate code that works with the current dataset state and selected target.
- Ensure compatibility with different scikit-learn versions for OneHotEncoder by using a try/except TypeError fallback.
"""
 
            # Call LLM service
            state["chat_history"].append({"role": "user", "content": [{"type": "text", "text": prompt}]})
            resp = llm_service.get_data_response(prompt, state["chat_history"][-5:])
            state["chat_history"].append({"role": "assistant", "content": [{"type": "text", "text": resp}]})

            # Ensure modelling node always returns a JSON payload parseable by routes.py
            try:
                parsed = json.loads(resp)
                if isinstance(parsed, dict) and {"response", "code", "suggestion"}.issubset(parsed.keys()):
                    payload = parsed
                    # Ensure role if missing
                    if "role" not in payload:
                        payload["role"] = "modelling"
                else:
                    payload = {
                        "response": parsed if isinstance(parsed, str) else json.dumps(parsed),
                        "code": "# No Code to Display",
                        "suggestion": [
                            "Run automatic training with cross-validation",
                            "Tune key hyperparameters (n_estimators, max_depth, learning_rate)",
                            "Compare algorithms (Logistic/RandomForest/GBM) on your target"
                        ],
                        "role": "modelling"
                    }
            except Exception:
                payload = {
                    "response": str(resp),
                    "code": "# No Code to Display",
                    "suggestion": [
                        "Run automatic training with cross-validation",
                        "Tune key hyperparameters (n_estimators, max_depth, learning_rate)",
                        "Compare algorithms (Logistic/RandomForest/GBM) on your target"
                    ],
                    "role": "modelling"
                }
            self.logger.info(f"Modelling agent payload: {payload}")
            state['messages'].append(AIMessage(json.dumps(payload)))
            self.logger.info("Modelling agent completed successfully")
            return state
           
        except Exception as e:
            self.logger.error(f"Modelling agent failed: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            # Return a fallback response instead of raising
            fallback_response = json.dumps({
                "response": f"Sorry, I encountered an error processing your modelling request: {str(e)}. Please try again or rephrase your question.",
                "code": "# Error occurred during processing",
                "suggestion": [
                    "Try rephrasing your question",
                    "Check if dataset is properly loaded",
                    "Verify target variable is set",
                    "Try again later"
                ]
            })
            state['messages'].append(AIMessage(fallback_response))
        return state
    
    def _route_request(self, state: MessageState):
        self.logger.info(f"Routing request: {state['userquery'][:100]}...")

        # Lightweight heuristic routing to avoid misclassification by LLM
        try:
            uq = (state.get('userquery') or '').lower()

            # If actual code is present, route to code_execution
            code_indicators = ["```", "import ", "def ", "class ", "pd.read_csv", "plt.", "df ="]
            if any(tok in uq for tok in code_indicators):
                state['intent'] = 'code_execution'
                self.logger.info("Heuristic router: routed to code_execution based on code indicators")
                return state

            # Modelling-related keywords: ask-for-code or training/evaluation terms
            modelling_keywords = [
                "xgboost", "xg boost", "lightgbm", "catboost", "random forest", "logistic regression",
                "gradient boosting", "train model", "model training", "hyperparameter", "grid search",
                "bayesian", "cross-validation", "k-fold", "cv", "roc", "auc", "f1", "precision", "recall",
                "confusion matrix", "feature importance", "model evaluation", "fit model", "predict",
                "auto train", "auto-training", "give me the code", "model code", "gbm"
            ]
            if any(k in uq for k in modelling_keywords):
                state['intent'] = 'modelling'
                self.logger.info("Heuristic router: routed to modelling based on modelling keywords")
                return state

            # Data insight keywords (keep conservative)
            insight_keywords = ["bivariate", "correlation", "vif", "information value", "heatmap", "iv"]
            if any(k in uq for k in insight_keywords):
                state['intent'] = 'data_insight'
                self.logger.info("Heuristic router: routed to data_insight based on insight keywords")
                return state
        except Exception as e:
            self.logger.warning(f"Heuristic routing skipped due to error: {e}")

        prompt = f'''You are a router agent responsible for directing incoming request to the appropriate specialized agents based on the content and intent of the request.
        Carefully analyse each request and determine the best-suited agent for handling it.
        The list of available agents is given below:
        1. Planner agent (plan_agent)
        2. Data Transformation agent (data_transformation)
        3. Code execution agent (code_execution)
        4. Data Insight agent (data_insight)
        5. Modelling agent (modelling)

        The output should always be in a json format.
        Example: If the intent of userquery is for planner agent then response should be {{'intent':'plan_agent'}}

        NOTE: 
        -If the intent of the user query if for updating the plan then it should point to planing agent.
        -Missing values, Outliers or duplicate detection comes under data transformation agent.
        -Modelling agent is used for , algorithm selection, model shortlisting, model training, model evaluation and any questions related to model development.
        Now analyse the below user query:
        USER QUERY : {state['userquery']}
        '''
        
        try:
            state["chat_history"].append({"role":"user", "content": [{"type": "text","text": prompt}]})
            intent = llm_service.get_response_route(prompt, state["chat_history"][-1:])
            state["chat_history"].append({"role":"assistant", "content": [{"type": "text","text": intent}]})
            state['intent'] = json.loads(intent)['intent']
            self.logger.info(f"Request routed to: {state['intent']}")
            return state
        except Exception as e:
            self.logger.error(f"Routing failed: {str(e)}")
            raise
    
    def _create_plan(self, state: MessageState):
        self.logger.info("Creating/updating analysis plan")
        
        # Extract requested categories from user query
        userquery_lower = state.get('userquery', '').lower()
        requested_categories = []
        if 'missing_values' in userquery_lower or 'missing values' in userquery_lower:
            requested_categories.append('missing_values')
        if 'outliers' in userquery_lower or 'outlier' in userquery_lower:
            requested_categories.append('outliers')
        if 'duplicates' in userquery_lower or 'duplicate' in userquery_lower:
            requested_categories.append('duplicates')
        
        self.logger.info(f"Detected requested categories: {requested_categories}")
        
        sys_prompt = f"""You are an expert in data analysis. Your task is to provide a detailed next steps which should be performed on dataset based on the knowledge base and dataset technical summary.

🚨 ABSOLUTE CRITICAL RULE 🚨
The user has EXPLICITLY requested ONLY these categories: {', '.join(requested_categories) if requested_categories else 'NONE'}

YOU MUST:
- Generate plans ONLY for: {', '.join(requested_categories) if requested_categories else 'NONE'}
- Return a JSON with ONLY these fields: {', '.join(requested_categories) if requested_categories else 'NONE'}
- DO NOT include any other categories, even if you see issues in the dataset

FORBIDDEN BEHAVIORS (will result in failure):
❌ Adding "duplicates" when user only asked for "outliers"
❌ Adding "outliers" when user only asked for "duplicates"  
❌ Adding "missing_values" when user only asked for "outliers"
❌ Adding ANY category not in the explicit request

CORRECT BEHAVIOR EXAMPLES:
✅ User asks for "outliers" → Response has ONLY "outliers" field
✅ User asks for "duplicates" → Response has ONLY "duplicates" field
✅ User asks for "missing_values" → Response has ONLY "missing_values" field

Do NOT be helpful by adding extra categories. Only return what was explicitly requested."""
        
        try:
            if state["plan"]:
                self.logger.info("Updating existing plan")
                prompt = f"""Now Update the Plan as per the userquery. I have provided the pervious version of plan and userquery.
                PREVIOUS PLAN:{state["plan"]}
                USERQUERY:{state["userquery"]}
                
                CRITICAL: Only update the categories explicitly mentioned in USERQUERY. Remove or keep other categories unchanged."""
                state["chat_history"].append({"role":"user", "content": [{"type": "text","text": prompt}]})
                resp = llm_service.get_response(sys_prompt, prompt, state["chat_history"][-5:])
                payload = {
                    "response": resp,
                    "data": "",
                    "suggestion": ""
                }
                state['messages'].append(AIMessage(json.dumps(payload)))
                # state['messages'].append(AIMessage(json.dumps(resp)))
                state["chat_history"].append({"role":"assistant", "content": [{"type": "text","text": resp}]})
            else:
                raise ValueError("No existing plan found, creating new plan")
        except Exception as e:
            self.logger.info("Creating new plan")
            dataset_id = state.get('dataset_id')
            summary = self.dataset_analyser.generate_dataset_summary(state['datasetFile'], dataset_id)
            prj_summary = state['projectDescFile']
            data_summary = state['dataDesc']
            
            # Get relevant context from vector store
            kb_context = ""
            if vector_store.is_initialized():
                kb_context = vector_store.get_relevant_context(f"dataset analysis plan for {summary}")
                self.logger.info("Using vector store context for plan generation")
            else:
                self.logger.warning("Vector store not available, proceeding without knowledge base context")
            
            prompt = AgentPrompt(summary, prj_summary, data_summary, kb_context, state['userquery']).generate_new_plan
            state["chat_history"].append({"role":"user", "content": [{"type": "text","text": prompt}]})
            resp = llm_service.get_response(sys_prompt, prompt, state["chat_history"][-5:])
            # state['messages'].append(AIMessage(json.dumps(payload)))
            state["chat_history"].append({"role":"assistant", "content": [{"type": "text","text": resp}]})

        # Validate and filter response to only include requested categories
        try:
            resp_dict = json.loads(resp)
            filtered_resp = {}
            
            for category in requested_categories:
                if category in resp_dict:
                    filtered_resp[category] = resp_dict[category]
            
            # Log if we filtered out unrequested categories
            removed_categories = [k for k in resp_dict.keys() if k not in requested_categories]
            if removed_categories:
                self.logger.warning(f"Filtered out unrequested categories from LLM response: {removed_categories}")
                self.logger.info(f"Kept only requested categories: {list(filtered_resp.keys())}")
            
            resp = json.dumps(filtered_resp)
        except json.JSONDecodeError:
            self.logger.warning("Could not parse LLM response as JSON for filtering")
        except Exception as e:
            self.logger.warning(f"Error filtering response: {str(e)}")

        self.logger.info("Plan created/updated successfully")
        # return {'plan': resp, 'dataset_id': state.get('dataset_id')}
        state['plan'] = resp
        # state['dataset_id'] = 'plan_agent'
        return state

    def _planner_agent_node(self, state: MessageState):
        state = self._create_plan(state)
        return state
    
    def _return_plan(self, state: MessageState):
        payload = {
                    "response": state["plan"],
                    "data": "",
                    "suggestion": ""
                }
        state['messages'].append(AIMessage(json.dumps(payload)))
        # state['messages'].append(AIMessage(state['plan']))
        state['intent'] = 'plan_agent'
        return state
    
    def check_plan_exist(self, state: MessageState):
        try:
            if state.get("plan") and state["plan"].strip():
                return "check_plan"
            else:
                return "plan_agent"
        except Exception as e:
            self.logger.error(f"Error checking plan existence: {str(e)}")
            return "plan_agent"
    
    def _data_insight_agent_node(self, state: MessageState): 
        """
        Standard Data Insights agent
        - Supports multiple selections: bivariate, correlation (extensible)
        - Computes metrics deterministically; LLM is used only for a short summary
        - If only bivariate is requested, preserve legacy payload shape
        """
        self.logger.info("Starting data insight analysis")

        try:
            dataset_id = state.get('dataset_id')
            if not dataset_id:
                raise ValueError("dataset_id missing in state")

            # Resolve target variable from stored dataset metadata
            ds_info = dataset_manager.get_dataset_info(dataset_id)
            
            if not ds_info:
                raise ValueError(f"Dataset info not found for dataset_id: {dataset_id}. Please ensure the dataset is properly uploaded.")
            
            target_variable = ds_info.get('target_variable')
            if not target_variable:
                # Try to get DataFrame to suggest available columns
                try:
                    df = dataframe_state_manager.get_dataframe(dataset_id)
                    if df is not None and len(df.columns) > 0:
                        available_cols = list(df.columns)[:10]  # First 10 columns as suggestion
                        raise ValueError(
                            f"Target variable not found in dataset metadata for dataset_id: {dataset_id}. "
                            f"Please set the target variable in dataset configuration. "
                            f"Available columns (first 10): {', '.join(available_cols)}"
                        )
                    else:
                        raise ValueError(
                            f"Target variable not found in dataset metadata for dataset_id: {dataset_id}. "
                            f"Please set the target variable in dataset configuration."
                        )
                except Exception as e:
                    # If we can't access DataFrame, provide generic error
                    if "Target variable not found" not in str(e):
                        self.logger.warning(f"Could not access DataFrame for better error message: {e}")
                    raise ValueError(
                        f"Target variable not found in dataset metadata for dataset_id: {dataset_id}. "
                        f"Please set the target variable in dataset configuration using the dataset settings."
                    ) from e
            
            # Validate that target variable exists in the DataFrame
            try:
                df = dataframe_state_manager.get_dataframe(dataset_id)
                if df is not None and target_variable not in df.columns:
                    available_cols = list(df.columns)[:10]
                    raise ValueError(
                        f"Target variable '{target_variable}' not found in dataset columns. "
                        f"Available columns (first 10): {', '.join(available_cols)}. "
                        f"Please update the target variable in dataset configuration."
                    )
            except ValueError:
                raise  # Re-raise ValueError if it's about target variable
            except Exception as e:
                self.logger.warning(f"Could not validate target variable in DataFrame: {e}")
                # Continue anyway - validation will happen in helper functions

            # Parse selections from user query
            uq = (state.get('userquery') or "").lower()
            wants_bivariate = any(k in uq for k in ["bivariate_analysis"])
            wants_correlation = any(k in uq for k in ["correlation_analysis"])
            wants_vif = any(k in uq for k in ["variance_inflation_factor"])
            wants_iv = any(k in uq for k in ["iv_analysis"])   
            wants_correlation_matrix = any(k in uq for k in ["correlation_matrix"])

            # wants_bivariate = any(k in uq for k in ["bivariate", "bi-variate", "bi variate", "bivariate_analysis"]) \
            #     or ("standard data insights" in uq and "correlation" not in uq and "vif" not in uq)
            
            # # Check for specific correlation types - more precise matching
            # wants_correlation_matrix = any(k in uq for k in ["correlation_matrix", "correlation matrix analysis", "correlation_matrix_analysis"])
            # wants_correlation = any(k in uq for k in ["correlation_analysis", "correlation insights", "correlation analysis insights"])
            # wants_vif = any(k in uq for k in ["vif", "variation inflation factor", "variance_inflation_factor", "variance inflation factor", "multicollinearity", "vif_analysis", "vif analysis"])
            
            # Debug logging (no raw query unless LOG_SENSITIVE_DEBUG)
            if settings.LOG_SENSITIVE_DEBUG:
                self.logger.info("User query len=%s preview=%s", len(uq), uq[:80])
            else:
                self.logger.info("User query len=%s", len(uq))
            self.logger.info(f"Parsed selections - bivariate: {wants_bivariate}, correlation: {wants_correlation}, correlation_matrix: {wants_correlation_matrix}, vif: {wants_vif}, iv: {wants_iv}")

            # Assume UI always sends at least one valid selection; no defaulting needed

            standard_insights: Dict[str, Any] = {}
            summary_bullets: List[str] = []

            # ---- Bivariate (existing helper) ----
            bivariate_tables: List[Dict[str, Any]] = []
            if wants_bivariate:
                bivariate_tables = generate_bivariate_tables_for_standard_insights(
                dataset_id=dataset_id,
                target_variable=target_variable,
                top_categories=10,
                bins=10,
                binning_method="quantile"
            )
                if bivariate_tables:
                    standard_insights["bivariate_analysis"] = bivariate_tables
                    for t in bivariate_tables[:6]:
                        var = t.get('variable_name', 'variable')
                        ins = t.get('insights', [])
                        if ins:
                            summary_bullets.append(f"{var}: " + "; ".join(ins[:2]))

            # ---- Correlation (numeric + categorical) ----
            if wants_correlation:
                try:
                    from app.utils.helpers import generate_correlation_analysis_tables
                    correlation_sections = generate_correlation_analysis_tables(
                        dataset_id=dataset_id,
                        target_variable=target_variable,
                        r_threshold=0.05
                    )
                except Exception as e:
                    self.logger.warning(f"Correlation generation failed: {e}")
                    correlation_sections = []

                corr_numeric_rows: List[Dict[str, Any]] = []
                corr_categorical_rows: List[Dict[str, Any]] = []
                for sec in correlation_sections:
                    if sec.get("analysis_kind") == "correlation_numeric":
                        corr_numeric_rows = sec.get("rows", [])
                    elif sec.get("analysis_kind") == "correlation_categorical":
                        corr_categorical_rows = sec.get("rows", [])

                standard_insights["correlation_analysis"] = {
                    "numeric": {
                        "columns": ["Variable Name","Type of Variable","Pearson Coefficient","Spearman Coefficient"],
                        "rows": corr_numeric_rows
                    },
                    "categorical": {
                        "columns": ["Variable Name","Type of Variable","Chi-Square test of Independence","Cramér’s V"],
                        "rows": corr_categorical_rows
                    }
                }

                # Human-readable bullets are generated via dedicated LLM calls; skip here

            # ---- VIF Analysis ----
            if wants_vif:
                try:
                    from app.utils.helpers import generate_vif_analysis_tables
                    vif_sections = generate_vif_analysis_tables(
                        dataset_id=dataset_id,
                        target_variable=target_variable
                    )
                except Exception as e:
                    self.logger.warning(f"VIF generation failed: {e}")
                    vif_sections = []

                vif_rows: List[Dict[str, Any]] = []
                for sec in vif_sections:
                    if sec.get("analysis_kind") == "vif_analysis":
                        vif_rows = sec.get("rows", [])

                if vif_rows:
                    standard_insights["vif_analysis"] = {
                        "columns": ["Variable", "VIF", "Interpretation"],
                        "rows": vif_rows,
                        "thresholds": {
                            "acceptable": "VIF < 5 → Acceptable",
                            "potential": "VIF 5-10 → Potential multicollinearity", 
                            "severe": "VIF > 10 → Serious multicollinearity"
                        }
                    }

            # ---- IV Analysis (numeric-only, pipeline-style) ----
            if wants_iv:
                try:
                    from app.utils.helpers import generate_iv_analysis_tables_pipeline_style
                    iv_sections = generate_iv_analysis_tables_pipeline_style(
                        dataset_id=dataset_id,
                        target_variable=target_variable,
                        bins=10
                    )
                except Exception as e:
                    self.logger.warning(f"IV generation failed: {e}")
                    iv_sections = []

                iv_summary_rows: List[Dict[str, Any]] = []
                iv_detail_tables: List[Dict[str, Any]] = []
                for sec in iv_sections:
                    if sec.get("analysis_kind") == "iv_analysis_summary":
                        iv_summary_rows = sec.get("rows", [])
                        iv_summary_cols = sec.get("columns", ["Feature Name", "IV"]) 
                    elif sec.get("analysis_kind") == "iv_analysis_details":
                        iv_detail_tables.append(sec)

                if iv_summary_rows:
                    standard_insights["iv_analysis_summary"] = {
                        "columns": iv_summary_cols,
                        "rows": iv_summary_rows,
                        "title": "Information Value (IV) Summary"
                    }
                if iv_detail_tables:
                    standard_insights["iv_analysis_details"] = iv_detail_tables
            # ---- Correlation Matrix Analysis ----
            if wants_correlation_matrix:
                try:
                    from app.utils.helpers import generate_correlation_matrix_analysis
                    df = dataframe_state_manager.get_dataframe(dataset_id)
                    if df is not None:
                        correlation_matrix_analysis = generate_correlation_matrix_analysis(
                            df=df,
                            target_variable=target_variable,
                            high_corr_threshold=0.8,
                            moderate_corr_threshold=0.5
                        )
                        
                        if "error" not in correlation_matrix_analysis:
                            standard_insights["correlation_matrix_analysis"] = correlation_matrix_analysis
                except Exception as e:
                    self.logger.warning(f"Correlation matrix analysis generation failed: {e}")
                    standard_insights["correlation_matrix_analysis"] = {"error": f"Analysis failed: {str(e)}"}

            if not standard_insights:
                payload = {
                    "response": json.dumps({"standard_insights": {}}),
                    "data": {"type": "standard_data_insights", "sections": []},
                    "suggestion": ["Check target variable", "Ensure dataset is loaded", "Try again"]
                }
                state['messages'].append(AIMessage(json.dumps(payload)))
                return state

            # ---- Section-specific LLM insights (bivariate / correlation / vif / correlation_matrix) ----
            llm_bivariate_insight: List[str] = []
            llm_correlation_insight: List[str] = []
            llm_vif_insight: List[str] = []
            llm_iv_insight: List[str] = []
            llm_correlation_matrix_insight: List[str] = []

            # Prepare KB for section prompts
            kb_context_section = ""
            if vector_store.is_initialized():
                kb_context_section = vector_store.get_relevant_context(
                    "Generate data insights grounded in provided tables; check monotonicity, rank-order breaks, anomalies; do not invent numbers"
                )

            # Bivariate section prompt
            if "bivariate_analysis" in standard_insights and standard_insights["bivariate_analysis"]:
                try:
                    bivar_payload = json.dumps(standard_insights["bivariate_analysis"])  # full tables
                    bivar_prompt = (
                        "Using the following full bivariate tables, produce concise insights.\n\n"
                        f"KNOWLEDGE BASE:\n{kb_context_section}\n\n"
                        f"BIVARIATE TABLES JSON:\n{bivar_payload}\n\n"
                        "INSTRUCTIONS:\n"
                        "- Evaluate monotonicity of event rate across bins; state if increasing/decreasing or flat.\n"
                        "- Detect rank-order breaks (non-monotonic reversals between adjacent bins) and count them.\n"
                        "- Highlight anomaly cases: unexpected spikes/dips, bins with unusually high/low event rate, or sparse bins.\n"
                        "- Mention strength/consistency of pattern (e.g., strong monotone up with 0 breaks, moderate with 1-2 breaks).\n"
                        "- Keep insights short, decision-oriented, and grounded only in provided numbers.\n\n"
                        "IMPORTANT: Respond strictly as JSON with key 'llm_bivariate_insight' as a list."
                    )
                    bivar_sys = "You are a senior data scientist returning JSON under 'llm_bivariate_insight'."
                    llm_bivariate_insight = llm_service.get_insight('bivariate', bivar_sys, bivar_prompt, state.get("chat_history", [])[-5:])
                except Exception as e:
                    self.logger.warning(f"Bivariate insight LLM failed: {e}")

            # Correlation section prompt (numeric + categorical)
            if "correlation_analysis" in standard_insights:
                try:
                    corr_payload = json.dumps(standard_insights["correlation_analysis"])  # full sections
                    corr_prompt = (
                        "Using the following full correlation sections (numeric and categorical), produce concise insights.\n\n"
                        f"KNOWLEDGE BASE:\n{kb_context_section}\n\n"
                        f"CORRELATION JSON:\n{corr_payload}\n\n"
                        "INSTRUCTIONS:\n"
                        "- Comment on strongest relationships (|Pearson|) and ordinal associations (Spearman).\n"
                        "- For categorical, assess strength using Cramér’s V; note chi‑square significance if present.\n"
                        "- Highlight anomalies: variables with surprisingly high/low association, or unexpected direction.\n"
                        "- Be crisp and base claims only on provided numbers.\n\n"
                        "IMPORTANT: Respond strictly as JSON with key 'llm_correlation_insight' as a list."
                    )
                    corr_sys = "You are a senior data scientist returning JSON under 'llm_correlation_insight'."
                    llm_correlation_insight = llm_service.get_insight('correlation', corr_sys, corr_prompt, state.get("chat_history", [])[-5:])
                except Exception as e:
                    self.logger.warning(f"Correlation insight LLM failed: {e}")

            # VIF section prompt
            if "vif_analysis" in standard_insights:
                try:
                    vif_payload = json.dumps(standard_insights["vif_analysis"])  # full VIF data
                    vif_prompt = (
                        "Using the following VIF (Variation Inflation Factor) analysis results, produce concise insights.\n\n"
                        f"KNOWLEDGE BASE:\n{kb_context_section}\n\n"
                        f"VIF ANALYSIS JSON:\n{vif_payload}\n\n"
                        "INSTRUCTIONS:\n"
                        "- Identify variables with severe multicollinearity (VIF > 10) and potential issues (VIF 5-10).\n"
                        "- Highlight which variables are most problematic and may need to be removed or combined.\n"
                        "- Suggest practical actions: which variables to consider dropping, combining, or transforming.\n"
                        "- Note any variables that are perfectly correlated (VIF = ∞) and require immediate attention.\n"
                        "- Be specific about the impact on model performance and interpretability.\n"
                        "- Keep insights actionable and focused on model building decisions.\n\n"
                        "IMPORTANT: Respond strictly as JSON with key 'llm_vif_insight' as a list."
                    )
                    vif_sys = "You are a senior data scientist returning JSON under 'llm_vif_insight'."
                    llm_vif_insight = llm_service.get_insight('vif', vif_sys, vif_prompt, state.get("chat_history", [])[-5:])
                except Exception as e:
                    self.logger.warning(f"VIF insight LLM failed: {e}")

            # IV section prompt (summary + selected details)
            if "iv_analysis_summary" in standard_insights:
                try:
                    iv_summary_payload = json.dumps(standard_insights["iv_analysis_summary"])  # summary table
                    # Optionally include top-3 variable details to ground insights
                    iv_detail_tables = standard_insights.get("iv_analysis_details", [])
                    top_vars = [r.get("Feature Name") for r in standard_insights["iv_analysis_summary"].get("rows", [])[:3]]
                    selected_details = [t for t in iv_detail_tables if t.get("variable") in top_vars]
                    iv_details_payload = json.dumps(selected_details)
                    iv_prompt = (
                        "Using the following IV results, produce concise insights.\n\n"
                        f"IV SUMMARY JSON:\n{iv_summary_payload}\n\n"
                        f"IV DETAILS (top variables) JSON:\n{iv_details_payload}\n\n"
                        "INSTRUCTIONS:\n"
                        "- Highlight strongest predictors by IV and their interpretation bands.\n"
                        "- Note any variables with suspiciously high IV (>0.2).\n"
                        "- Mention variables with near-zero IV that can be dropped.\n"
                        "- If details are present, reference notable bins with extreme WOE contributions.\n\n"
                        "IMPORTANT: Respond strictly as JSON with key 'llm_iv_insight' as a list."
                    )
                    iv_sys = "You are a senior data scientist returning JSON under 'llm_iv_insight'."
                    llm_iv_insight = llm_service.get_insight('iv', iv_sys, iv_prompt, state.get("chat_history", [])[-5:])
                except Exception as e:
                    self.logger.warning(f"IV insight LLM failed: {e}")
            # Correlation Matrix section prompt (optimized to reduce payload size)
            if "correlation_matrix_analysis" in standard_insights and "error" not in standard_insights["correlation_matrix_analysis"]:
                try:
                    # Extract only key information instead of full matrix (reduces payload size significantly)
                    corr_matrix_data = standard_insights["correlation_matrix_analysis"]
                    
                    # Create a lightweight summary for LLM (exclude full correlation_matrix dict which is huge)
                    corr_matrix_summary = {
                        "correlation_summary": corr_matrix_data.get("correlation_summary", {}),
                        "high_correlations": corr_matrix_data.get("high_correlations", [])[:50],  # Limit to top 50
                        "moderate_correlations": corr_matrix_data.get("moderate_correlations", [])[:30],  # Limit to top 30
                        "multicollinearity_groups": corr_matrix_data.get("multicollinearity_groups", []),
                        "target_correlations": corr_matrix_data.get("target_correlations", [])[:30],  # Top 30 target correlations
                        "redundant_variables": corr_matrix_data.get("redundant_variables", []),
                        "recommendations": corr_matrix_data.get("recommendations", [])
                    }
                    
                    corr_matrix_payload = json.dumps(corr_matrix_summary)
                    corr_matrix_prompt = (
                        "Using the following correlation matrix analysis summary, produce detailed insights.\n\n"
                        f"KNOWLEDGE BASE:\n{kb_context_section}\n\n"
                        f"CORRELATION MATRIX SUMMARY:\n{corr_matrix_payload}\n\n"
                        "INSTRUCTIONS:\n"
                        "- Identify pairs or groups of variables with very high positive or negative correlations (|correlation| > 0.8).\n"
                        "- Highlight potential multicollinearity issues evident from the analysis.\n"
                        "- Identify any redundant or strongly dependent variables that could be candidates for removal or transformation.\n"
                        "- Suggest actionable insights on how to handle these correlations in downstream modeling or analysis.\n"
                        "- Summarize key patterns and relationships that could impact model performance or interpretation.\n"
                        "- Focus on practical recommendations for data scientists and analysts.\n"
                        "- Be specific about which variables to consider removing, combining, or transforming.\n"
                        "- Mention the impact on model interpretability and overfitting risk.\n"
                        "- Reference the high correlations, multicollinearity groups, and redundant variables from the summary.\n"
                        "- Each insight should be a clear, concise sentence or bullet point.\n\n"
                        "IMPORTANT: Respond with JSON containing 'insights' as a list of strings."
                    )
                    corr_matrix_sys = "You are a senior data scientist. Return JSON with 'insights' key containing a list of insight strings."
                    llm_correlation_matrix_insight = llm_service.get_insight('correlation_matrix', corr_matrix_sys, corr_matrix_prompt, state.get("chat_history", [])[-5:])
                    
                    # Log if insights were generated
                    if llm_correlation_matrix_insight:
                        self.logger.info(f"Generated {len(llm_correlation_matrix_insight)} correlation matrix insights")
                    else:
                        self.logger.warning("Correlation matrix insights are empty - LLM may have failed or returned empty response. Generating fallback insights.")
                        # Generate fallback insights from correlation matrix data
                        llm_correlation_matrix_insight = self._generate_fallback_correlation_matrix_insights(corr_matrix_data)
                except Exception as e:
                    self.logger.warning(f"Correlation matrix insight LLM failed: {e}", exc_info=True)
                    # Generate fallback insights even if LLM completely fails
                    try:
                        corr_matrix_data = standard_insights.get("correlation_matrix_analysis", {})
                        llm_correlation_matrix_insight = self._generate_fallback_correlation_matrix_insights(corr_matrix_data)
                    except Exception as fallback_error:
                        self.logger.error(f"Fallback insight generation also failed: {fallback_error}")
                        llm_correlation_matrix_insight = []  # Ensure it's initialized

            # ---- Build payloads ----
            # Create a clean response that the UI can easily parse
            response_data: Dict[str, Any] = {}
            
            # Build a generic response containing any analyses that were computed
            if "bivariate_analysis" in standard_insights:
                response_data["bivariate_analysis"] = standard_insights["bivariate_analysis"]

            if "correlation_analysis" in standard_insights:
                corr = standard_insights["correlation_analysis"]
                # Add numeric correlation table
                if corr.get("numeric", {}).get("rows"):
                    response_data["correlation_numeric"] = [{
                        "columns": corr["numeric"]["columns"],
                        "rows": corr["numeric"]["rows"],
                        "title": "Correlation (Numerical vs Target)"
                    }]
                # Add categorical correlation table
                if corr.get("categorical", {}).get("rows"):
                    response_data["correlation_categorical"] = [{
                        "columns": corr["categorical"]["columns"],
                        "rows": corr["categorical"]["rows"],
                        "title": "Association (Categorical vs Target)"
                    }]

            # Add VIF analysis table
            if "vif_analysis" in standard_insights:
                vif = standard_insights["vif_analysis"]
                if vif.get("rows"):
                    response_data["vif_analysis"] = [{
                        "columns": vif["columns"],
                        "rows": vif["rows"],
                        "title": "Variation Inflation Factor (VIF) Analysis",
                        "thresholds": vif["thresholds"]
                    }]

            # Add IV analysis tables
            if "iv_analysis_summary" in standard_insights:
                ivs = standard_insights["iv_analysis_summary"]
                if ivs.get("rows"):
                    response_data["iv_analysis_summary"] = [{
                        "columns": ivs["columns"],
                        "rows": ivs["rows"],
                        "title": ivs.get("title", "Information Value (IV) Summary")
                    }]
            if "iv_analysis_details" in standard_insights:
                ivd = standard_insights["iv_analysis_details"]
                # list of per-variable tables, already shaped
                response_data["iv_analysis_details"] = [{
                    "columns": t.get("columns", []),
                    "rows": t.get("rows", []),
                    "title": t.get("title", "IV Detail"),
                    "variable": t.get("variable", "")
                } for t in ivd]
            # Add correlation matrix analysis table
            if "correlation_matrix_analysis" in standard_insights and "error" not in standard_insights["correlation_matrix_analysis"]:
                corr_matrix = standard_insights["correlation_matrix_analysis"]
                
                # Create high correlations table
                if corr_matrix.get("high_correlations"):
                    high_corr_rows = []
                    for corr in corr_matrix["high_correlations"]:
                        high_corr_rows.append({
                            "Variable 1": corr["variable_1"],
                            "Variable 2": corr["variable_2"],
                            "Correlation": corr["correlation"],
                            "Strength": corr["strength"],
                            "Direction": corr["direction"]
                        })
                    
                    response_data["correlation_matrix_high"] = [{
                        "columns": ["Variable 1", "Variable 2", "Correlation", "Strength", "Direction"],
                        "rows": high_corr_rows,
                        "title": "High Correlations (|r| ≥ 0.8)"
                    }]
                
                # Create multicollinearity groups table
                if corr_matrix.get("multicollinearity_groups"):
                    multicollinearity_rows = []
                    for group in corr_matrix["multicollinearity_groups"]:
                        multicollinearity_rows.append({
                            "Group Size": group["size"],
                            "Variables": ", ".join(group["variables"]),
                            "Description": group["description"]
                        })
                    
                    response_data["correlation_matrix_multicollinearity"] = [{
                        "columns": ["Group Size", "Variables", "Description"],
                        "rows": multicollinearity_rows,
                        "title": "Multicollinearity Groups"
                    }]
                
                # Create redundant variables table
                if corr_matrix.get("redundant_variables"):
                    redundant_rows = []
                    for var in corr_matrix["redundant_variables"]:
                        redundant_rows.append({
                            "Variable": var["variable"],
                            "High Correlation Count": var["high_correlation_count"],
                            "Recommendation": "Consider removing or transforming"
                        })
                    
                    response_data["correlation_matrix_redundant"] = [{
                        "columns": ["Variable", "High Correlation Count", "Recommendation"],
                        "rows": redundant_rows,
                        "title": "Redundant Variables"
                    }]
                
                # Create target correlations table
                if corr_matrix.get("target_correlations"):
                    target_corr_rows = []
                    for corr in corr_matrix["target_correlations"][:10]:  # Top 10
                        target_corr_rows.append({
                            "Variable": corr["variable"],
                            "Correlation with Target": corr["correlation_with_target"],
                            "Strength": corr["strength"]
                        })
                    
                    response_data["correlation_matrix_target"] = [{
                        "columns": ["Variable", "Correlation with Target", "Strength"],
                        "rows": target_corr_rows,
                        "title": "Target Variable Correlations (Top 10)"
                    }]
                
                # Add correlation matrix tables (both main matrix and summary)
                if corr_matrix.get("correlation_matrix_table"):
                    corr_table = corr_matrix["correlation_matrix_table"]
                    
                    # Add main correlation matrix table (the big square table)
                    if corr_table.get("correlation_matrix"):
                        response_data["correlation_matrix_heatmap"] = [corr_table["correlation_matrix"]]
                    
                    # Add correlated variables count table (the small summary table)
                    if corr_table.get("correlation_summary"):
                        response_data["correlation_matrix_summary"] = [corr_table["correlation_summary"]]

            inner_response = {
                "response": response_data,
                "data": {
                    "bivariate_insight": llm_bivariate_insight,
                    "correlation_insight": llm_correlation_insight,
                    "vif_insight": llm_vif_insight,
                    "correlation_matrix_insight": llm_correlation_matrix_insight,
                    "iv_insight": llm_iv_insight
                }
            }
            payload = {
                "response": json.dumps(inner_response)
            }

            state['messages'].append(AIMessage(json.dumps(payload)))
            return state

        except Exception as e:
            self.logger.error(f"Data insight analysis failed: {str(e)}")
            state['messages'].append(AIMessage(json.dumps({
                "response": json.dumps({"standard_insights": {}, "error": f"Data insight analysis failed: {str(e)}"}),
                "data": {"type": "standard_data_insights", "standard_insights": {}},
                "suggestion": ["Verify dataset & target", "Try again"]
            })))
            return state

    def _generate_fallback_correlation_matrix_insights(self, corr_matrix_data: Dict[str, Any]) -> List[str]:
        """
        Generate fallback insights from correlation matrix data when LLM fails.
        This ensures insights are always available even if LLM is unavailable.
        """
        insights = []
        
        try:
            # Extract key information
            high_correlations = corr_matrix_data.get("high_correlations", [])
            moderate_correlations = corr_matrix_data.get("moderate_correlations", [])
            multicollinearity_groups = corr_matrix_data.get("multicollinearity_groups", [])
            target_correlations = corr_matrix_data.get("target_correlations", [])
            redundant_variables = corr_matrix_data.get("redundant_variables", [])
            correlation_summary = corr_matrix_data.get("correlation_summary", {})
            
            # High correlations insights
            if high_correlations:
                top_high = high_correlations[:5]  # Top 5
                if top_high:
                    insights.append(f"Found {len(high_correlations)} pairs of variables with very high correlations (|r| ≥ 0.8).")
                    top_pair = top_high[0]
                    insights.append(f"The strongest correlation is between '{top_pair.get('variable_1', 'N/A')}' and '{top_pair.get('variable_2', 'N/A')}' with correlation {top_pair.get('correlation', 0):.4f}.")
            
            # Multicollinearity groups
            if multicollinearity_groups:
                insights.append(f"Identified {len(multicollinearity_groups)} groups of variables with multicollinearity issues.")
                largest_group = max(multicollinearity_groups, key=lambda x: x.get('size', 0), default={})
                if largest_group.get('size', 0) > 2:
                    insights.append(f"The largest multicollinearity group contains {largest_group.get('size', 0)} variables, indicating potential redundancy.")
            
            # Redundant variables
            if redundant_variables:
                top_redundant = redundant_variables[:3]  # Top 3
                if top_redundant:
                    insights.append(f"Found {len(redundant_variables)} variables that are highly correlated with multiple other variables.")
                    for var in top_redundant:
                        var_name = var.get('variable', 'N/A')
                        count = var.get('high_correlation_count', 0)
                        insights.append(f"Variable '{var_name}' has high correlations with {count} other variables, making it a candidate for removal.")
            
            # Target correlations
            if target_correlations:
                top_target = target_correlations[:3]  # Top 3
                if top_target:
                    insights.append(f"Identified {len(target_correlations)} variables with correlations to the target variable.")
                    for corr in top_target:
                        var_name = corr.get('variable', 'N/A')
                        corr_value = corr.get('correlation_with_target', 0)
                        strength = corr.get('strength', 'unknown')
                        insights.append(f"Variable '{var_name}' shows {strength} correlation ({corr_value:.4f}) with the target variable.")
            
            # Moderate correlations
            if moderate_correlations:
                insights.append(f"Found {len(moderate_correlations)} pairs of variables with moderate correlations (0.5 ≤ |r| < 0.8).")
            
            # Summary statistics
            total_vars = correlation_summary.get("total_numeric_variables", 0)
            if total_vars > 0:
                insights.append(f"Analysis covered {total_vars} numeric variables in the correlation matrix.")
            
            # Recommendations
            if high_correlations or multicollinearity_groups:
                insights.append("Consider removing one variable from each highly correlated pair or using dimensionality reduction techniques like PCA to address multicollinearity.")
            
            if not insights:
                insights.append("Correlation matrix analysis completed. Review the correlation pairs and multicollinearity groups for potential variable removal or transformation.")
            
            self.logger.info(f"Generated {len(insights)} fallback correlation matrix insights")
            return insights
            
        except Exception as e:
            self.logger.error(f"Error generating fallback insights: {e}", exc_info=True)
            return ["Correlation matrix analysis completed. Review the correlation data for insights on variable relationships and multicollinearity."]

    def _code_execution_node(self, state: MessageState):
        try:
            code = state.get('generatedCode', '')
            if not code or not code.strip():
                self.logger.warning("No code provided for execution")
                state['messages'].append(AIMessage('{"response": "No code provided for execution", "code": "# No code to display", "suggestion": ["Provide Python code to execute", "Check code format", "Try again"]}'))
                return state

            df = state['datasetFile'].clone()  # Create a copy to avoid modifying original

            # Debug: Log the code being executed
            self.logger.info(f"Executing generated code: {code[:500]}...")
            self.logger.info(f"DataFrame shape before execution: {df.shape}")
            self.logger.info(f"DataFrame columns before execution: {list(df.columns)}")
            
            # Strip markdown code fences if present
            code_lines = code.splitlines()
            # Remove opening markdown fence (```python, ```py, or just ```)
            if code_lines and code_lines[0].strip().startswith('```'):
                code_lines = code_lines[1:]
            # Remove closing markdown fence (```)
            if code_lines and code_lines[-1].strip() == '```':
                code_lines = code_lines[:-1]
            
            # Filter out pd.read_csv lines
            code_lines = [line for line in code_lines if not ("pd.read_csv" in line and "df" in line)]
            
            # Normalize code: fix indentation and clean up
            import textwrap
            import re
            
            def normalize_code_lines(lines):
                """Fix common indentation and formatting issues"""
                if not lines:
                    return lines
                
                # Convert tabs to 4 spaces
                lines = [line.replace('\t', '    ') for line in lines]
                
                # Remove leading/trailing empty lines
                while lines and not lines[0].strip():
                    lines.pop(0)
                while lines and not lines[-1].strip():
                    lines.pop()
                
                if not lines:
                    return lines
                
                # Find minimum indentation of non-empty, non-comment lines
                min_indent = float('inf')
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith('#'):
                        indent = len(line) - len(line.lstrip())
                        if indent < min_indent:
                            min_indent = indent
                
                # If all lines are indented, remove the base indentation
                if min_indent > 0 and min_indent != float('inf'):
                    normalized = []
                    for line in lines:
                        if line.strip():
                            current_indent = len(line) - len(line.lstrip())
                            if current_indent >= min_indent:
                                normalized.append(line[min_indent:])
                            else:
                                # Line has less indentation than base - keep as is (might be dedent)
                                normalized.append(line)
                        else:
                            normalized.append('')
                    return normalized
                
                return lines
            
            # Normalize the code
            normalized_lines = normalize_code_lines(code_lines)
            modified_code = "\n".join(normalized_lines)
            
            # Try to compile and fix indentation errors automatically
            lines = modified_code.splitlines()
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    # Try to compile to check syntax
                    compile(modified_code, '<string>', 'exec')
                    # If successful, break
                    break
                except IndentationError as ind_err:
                    if attempt < max_attempts - 1:
                        # Try to fix indentation error
                        error_line_num = ind_err.lineno if hasattr(ind_err, 'lineno') and ind_err.lineno else None
                        if error_line_num and error_line_num <= len(lines):
                            # Fix the problematic line
                            error_idx = error_line_num - 1
                            problem_line = lines[error_idx]
                            stripped = problem_line.strip()
                            
                            # Check previous line's indentation
                            if error_idx > 0:
                                prev_line = lines[error_idx - 1]
                                prev_indent = len(prev_line) - len(prev_line.lstrip())
                                prev_stripped = prev_line.strip()
                                
                                # If previous line ends with ':', this line should be indented
                                if prev_stripped.endswith(':'):
                                    # This line should be indented by 4 more spaces
                                    expected_indent = prev_indent + 4
                                    if len(problem_line) - len(problem_line.lstrip()) != expected_indent:
                                        lines[error_idx] = ' ' * expected_indent + stripped
                                        modified_code = "\n".join(lines)
                                        continue
                                
                                # If previous line doesn't end with ':', check if this line is over-indented
                                elif not prev_stripped.endswith(':'):
                                    # This line might be incorrectly indented - try same as previous
                                    if len(problem_line) - len(problem_line.lstrip()) > prev_indent:
                                        lines[error_idx] = ' ' * prev_indent + stripped
                                        modified_code = "\n".join(lines)
                                        continue
                        
                        # If we can't fix it automatically, try removing all base indentation
                        if attempt == 1:
                            # Second attempt: remove all base indentation
                            min_indent = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
                            if min_indent > 0:
                                lines = [l[min_indent:] if l.strip() else l for l in lines]
                                modified_code = "\n".join(lines)
                                continue
                    
                    # If we can't fix it, let it fail and show error
                    raise
                except SyntaxError:
                    # Other syntax errors - let them be caught by the main handler
                    break
            
            # Validate syntax before execution
            try:
                compile(modified_code, '<string>', 'exec')
            except SyntaxError as syn_err:
                error_msg = f"Syntax error in generated code: {syn_err.msg} at line {syn_err.lineno}"
                if syn_err.text:
                    error_msg += f"\nProblematic line: {syn_err.text.strip()}"
                # Show context around the error
                error_lines = modified_code.splitlines()
                if syn_err.lineno and syn_err.lineno <= len(error_lines):
                    context_start = max(0, syn_err.lineno - 3)
                    context_end = min(len(error_lines), syn_err.lineno + 2)
                    context_lines = error_lines[context_start:context_end]
                    numbered_context = "\n".join(
                        f"{context_start + i + 1:3d}: {line}" 
                        for i, line in enumerate(context_lines)
                    )
                    error_msg += f"\n\nCode context:\n{numbered_context}"
                self.logger.error(error_msg)
                self.logger.error(f"Full normalized code:\n{modified_code}")
                state['messages'].append(AIMessage(json.dumps({
                    "response": f"Code execution failed: {error_msg}\n\nPlease check the code for incomplete statements, missing brackets, or syntax errors.",
                    "code": code,
                    "suggestion": [
                        "Check for incomplete code blocks (missing opening/closing brackets)",
                        "Ensure all dictionaries and lists are properly closed",
                        "Verify all function calls have matching parentheses",
                        "Check for incomplete string literals",
                        "Verify indentation is consistent (use 4 spaces, not tabs)"
                    ],
                    "role": "modelling"
                })))
                return state
            
            # Debug: Log the modified code
            self.logger.info(f"Modified code for execution: {modified_code[:500]}...")
            
            # Capture stdout to get print statements
            import io
            from contextlib import redirect_stdout
            import re
            
            stdout_capture = io.StringIO()
            
            # Execute code in a local namespace to capture changes to df
            local_namespace = {'df': df, 'pl': pl, 'np': np}
            
            # Redirect stdout to capture print statements
            try:
                with redirect_stdout(stdout_capture):
                    exec(modified_code, globals(), local_namespace)
            except MemoryError as mem_err:
                # Automatic retry with memory-efficient settings
                self.logger.warning(f"Memory error detected, retrying with sparse encoding: {mem_err}")
                
                # Modify code to use sparse encoding and limit categories
                try:
                    import sklearn
                    sklearn_version = sklearn.__version__
                except ImportError:
                    sklearn_version = "1.0.0"
                
                # Fix OneHotEncoder to use sparse output
                # Handle both sparse_output (new) and sparse (old) parameters
                if 'sparse_output=False' in modified_code:
                    modified_code = modified_code.replace('sparse_output=False', 'sparse_output=True')
                elif 'sparse=False' in modified_code:
                    modified_code = modified_code.replace('sparse=False', 'sparse=True')
                elif 'OneHotEncoder(' in modified_code and 'sparse_output' not in modified_code and 'sparse=' not in modified_code:
                    # Add sparse_output parameter if not present
                    modified_code = re.sub(
                        r'OneHotEncoder\(([^)]*)\)',
                        lambda m: m.group(0) if 'sparse_output' in m.group(0) or 'sparse=' in m.group(0) else m.group(0).rstrip(')') + ', sparse_output=True)',
                        modified_code
                    )
                
                # Add max_categories to limit feature explosion
                if 'max_categories' not in modified_code and 'OneHotEncoder(' in modified_code:
                    # Find OneHotEncoder calls and add max_categories if not present
                    def add_max_categories(match):
                        content = match.group(1)
                        if 'max_categories' not in content:
                            # Add max_categories before closing parenthesis
                            if content.strip().endswith(','):
                                return f'OneHotEncoder({content} max_categories=50)'
                            else:
                                return f'OneHotEncoder({content}, max_categories=50)'
                        return match.group(0)
                    
                    modified_code = re.sub(
                        r'OneHotEncoder\(([^)]*)\)',
                        add_max_categories,
                        modified_code
                    )
                
                # Clear the previous stdout capture and reset namespace
                stdout_capture = io.StringIO()
                local_namespace = {'df': df, 'pl': pl, 'np': np}
                
                # Retry execution with fixed code
                try:
                    with redirect_stdout(stdout_capture):
                        exec(modified_code, globals(), local_namespace)
                    self.logger.info("Memory error fixed, code executed successfully with sparse encoding")
                except Exception as retry_err:
                    # If retry also fails, raise the original memory error with guidance
                    self.logger.error(f"Retry with sparse encoding also failed: {retry_err}")
                    raise MemoryError(f"Memory allocation failed even with sparse encoding. Original error: {mem_err}. Retry error: {retry_err}")
            
            # Get the captured output
            execution_output = stdout_capture.getvalue()
            
            # Get the modified dataframe from local namespace
            modified_df = local_namespace.get('df', df)
            
            self.logger.info(f"DataFrame shape after execution: {modified_df.shape}")
            self.logger.info(f"DataFrame columns after execution: {list(modified_df.columns)}")
            
            # Check if columns were actually dropped
            original_columns = set(df.columns)
            new_columns = set(modified_df.columns)
            dropped_columns = original_columns - new_columns
            if dropped_columns:
                self.logger.info(f"Columns dropped: {list(dropped_columns)}")
            else:
                self.logger.warning("No columns were dropped - check the code!")

            # Build response with execution output
            response_text = "Code executed successfully"
            if execution_output.strip():
                response_text = f"Code executed successfully\n\n{execution_output}"
            elif isinstance(modified_df, pl.DataFrame):
                response_text = "Code executed successfully"
            else:
                response_text = "Execution failed"

            payload = {
                "response": response_text,
                "code": code,
                "suggestion": ["Proceed with next step"]
            }
            
            state['messages'].append(AIMessage(json.dumps(payload)))
            state['datasetFile'] = modified_df  # Use the modified dataframe
            return state
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            
            # Add line numbers to the code for easier debugging
            numbered_code = "\n".join(f"{i+1:3d}: {line}" for i, line in enumerate(code.splitlines()))
            
            self.logger.error(f"Code execution failed: {str(e)}")
            self.logger.error(f"Full error traceback:\n{error_details}")
            self.logger.error(f"Full code that failed (with line numbers):\n{numbered_code}")

            # Provide actionable guidance based on error type
            guidance = []
            emsg = str(e).lower()
            
            if "syntax" in emsg or "unmatched" in emsg or "invalid syntax" in emsg:
                guidance = [
                    "Check for incomplete code blocks (missing opening/closing brackets)",
                    "Ensure all dictionaries {{}} and lists [] are properly closed",
                    "Verify all function calls have matching parentheses ()",
                    "Check for incomplete string literals or missing quotes"
                ]
            elif "boolean index did not match indexed array" in emsg or ("boolean index" in emsg and "match indexed array" in emsg):
                guidance = [
                    "Avoid df[mask] when mask length != n_rows. Use df.loc[row_mask, :] for row filters (len == n_rows).",
                    "Use df.loc[:, col_mask] for column filters (len == n_cols).",
                    "Prefer a Pipeline with ColumnTransformer (imputer + OneHotEncoder) to avoid manual boolean masks."
                ]
            elif "nan" in emsg or "null" in emsg:
                guidance = [
                    "Ensure all missing values are handled before model training",
                    "Use SimpleImputer in a Pipeline to handle NaNs automatically",
                    "Check that preprocessing steps are applied correctly"
                ]
            elif "memory" in emsg or "allocation" in emsg:
                guidance = [
                    "Use sparse encoding for categorical features (OneHotEncoder with sparse_output=True)",
                    "Consider reducing max_categories in OneHotEncoder",
                    "Use a more memory-efficient solver (e.g., 'saga' for LogisticRegression)"
                ]
            elif ("invalid classes inferred" in emsg 
                  or "unknown label type" in emsg 
                  or ("xgb" in emsg and "classes" in emsg)):
                guidance = [
                    "Your target appears to be non-numeric or multiclass while the model/pipeline expects binary numeric labels.",
                    "Prefer a binary target like 'target_flag' if available (0/1) and stratify on it.",
                    "If using a multiclass string target (e.g., 'loan_status'), encode labels (LabelEncoder) and set XGBoost objective='multi:softprob' with num_class=K and eval_metric='mlogloss'. Evaluate with multiclass ROC AUC."
                ]
            else:
                guidance = [
                    "Review the error message above for specific issues",
                    "Check that all required variables are defined",
                    "Verify column names match your dataset",
                    "Ensure code follows the pipeline requirements"
                ]

            # Extract error line number if available
            error_msg = str(e)
            if hasattr(e, 'lineno') and e.lineno:
                error_msg = f"Error at line {e.lineno}: {error_msg}"

            state['messages'].append(AIMessage(json.dumps({
                "response": f"Code execution failed: {error_msg}",
                "code": code,
                "suggestion": guidance,
                "role": "modelling"
            })))
            return state

    def set_graph(self):
        graph = StateGraph(MessageState)
        graph.add_node("route_request", self._route_request)
        # graph.add_node("check_plan", lambda state: state)
        # graph.add_node("plan_agent", self._planner_agent_node)
        graph.add_node("data_transformation", self._data_transformation_agent_node)
        graph.add_node("modelling", self._modelling_agent_node)
        graph.add_node("code_execution", self._code_execution_node)
        graph.add_node("data_insight", self._data_insight_agent_node)
        # graph.add_node("return_plan", self._return_plan)

        graph.add_edge(START, "route_request")
        # graph.add_conditional_edges("route_request", self.check_plan_exist, {
        #     "check_plan": "check_plan",
        #     "plan_agent": "plan_agent"
        # })
        graph.add_conditional_edges("route_request", lambda state: state.get('intent'), {
            "data_transformation": "data_transformation",
            "modelling": "modelling",
            # "plan_agent": "plan_agent",
            "code_execution": "code_execution",
            "data_insight": "data_insight"
        })
        
        # graph.add_edge("plan_agent", "return_plan")
        # graph.add_edge("return_plan", END)
        graph.add_edge("data_transformation", END)
        graph.add_edge("code_execution", END)
        graph.add_edge("modelling", END)
        graph.add_edge("data_insight", END)
        
        agent = graph.compile()
        return agent

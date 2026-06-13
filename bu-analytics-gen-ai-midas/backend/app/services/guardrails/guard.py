"""
Guard class for input/output validation
"""
from typing import Dict, Any, Optional, Tuple, List
from app.services.llm_service import LLMService
from app.core.logging_config import get_logger
from .validators.relevance_validator import (
    build_llm_validation_prompt,
    parse_llm_response,
    handle_timeout
)

logger = get_logger(__name__)


class Guard:
    """
    Guard class for validating user queries against agent capabilities
    """
    
    # Relevant keywords for each agent (extracted from agent prompts)
    AGENT_KEYWORDS = {
        "modelling": [
            "vif", "variance inflation factor", "iv", "information value",
            "correlation", "model training", "train model", "xgboost",
            "lightgbm", "catboost", "random forest", "logistic regression",
            "hyperparameter", "grid search", "bayesian", "cross validation",
            "k-fold", "cv", "roc", "auc", "f1", "precision", "recall",
            "confusion matrix", "feature importance", "model evaluation",
            "shap", "pdp", "partial dependence", "feature selection",
            "class imbalance", "threshold optimization", "calibration",
            "woe", "bivariate", "model performance", "algorithm selection",
            "gradient boosting", "gbm", "svm", "support vector machine",
            "regularization", "overfitting", "underfitting", "feature engineering",
            "model interpretability", "deployment", "drift monitoring"
        ],
        "data_transformation": [
            "missing values", "missing data", "null values", "na values",
            "outliers", "outlier detection", "outlier treatment", "extreme values",
            "duplicates", "duplicate rows", "deduplication", "duplicate removal",
            "data cleaning", "data preprocessing", "imputation", "scaling",
            "encoding", "data transformation", "data quality"
        ],
        "data_insight": [
            "bivariate", "bivariate analysis", "data insights", "insights",
            "correlation analysis", "correlation matrix", "standard data insights",
            "data visualization", "statistical summary", "descriptive statistics"
        ],
        "plan_agent": [
            "create plan", "analysis plan", "treatment plan", "data quality plan",
            "plan for", "generate plan", "data quality checks"
        ],
        "code_execution": [
            "execute code", "run code", "python code", "code execution",
            "import pandas", "df =", "pd.read_csv", "plt.", "def ", "class "
        ]
    }
    
    # Agent display names and capabilities for guidance messages
    AGENT_INFO = {
        "modelling": {
            "name": "Model Training Agent",
            "capabilities": [
                "Model training and algorithm selection",
                "Hyperparameter tuning and optimization",
                "Model evaluation and performance metrics",
                "Feature analysis (VIF, IV, Correlation)",
                "Model interpretability and feature importance"
            ]
        },
        "data_transformation": {
            "name": "Data Transformation Agent",
            "capabilities": [
                "Missing value detection and imputation",
                "Outlier detection and treatment",
                "Duplicate row detection and removal",
                "Data cleaning and preprocessing"
            ]
        },
        "data_insight": {
            "name": "Data Insight Agent",
            "capabilities": [
                "Bivariate analysis",
                "Correlation analysis",
                "Data insights and visualizations",
                "Statistical summaries"
            ]
        },
        "plan_agent": {
            "name": "Planner Agent",
            "capabilities": [
                "Creating data quality analysis plans",
                "Planning data transformations",
                "Treatment recommendations"
            ]
        },
        "code_execution": {
            "name": "Code Execution Agent",
            "capabilities": [
                "Executing Python code for data analysis",
                "Running data transformations",
                "Code execution and validation"
            ]
        }
    }
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.llm_service = LLMService()
        self.logger = logger
    
    def _get_agent_prompt(self) -> str:
        """
        Get agent prompt based on agent name
        Returns simplified prompt for validation
        """
        prompts = {
            "modelling": """You are an expert ML assistant for model development, evaluation, optimisation, data diagnostics, and statistical relationship analysis.

Your mission:
→ Answer every modelling-related question accurately and independently.  
→ Use dataset context, variable analysis results, and model training results when relevant.

TOPICS YOU MUST HANDLE:
A) Data readiness  
B) VIF, correlations, IV, WOE, bivariate  
C) All standard ML algorithms (concepts, use cases, hyperparameters)  
D) Hyperparameter tuning (RF, XGBoost, LightGBM, CatBoost, SVM, LR)  
E) Model performance analysis & evaluation  
F) Improving recall/precision/AUC/F1/robustness  
G) Regularisation & overfitting control  
H) Threshold optimisation & calibration  
I) Feature engineering & selection guidance  
J) Interpretability (feature importance, SHAP, PDP)  
K) Class imbalance handling  
L) Deployment & drift monitoring""",
            
            "data_transformation": """You are a Data Transformation Agent for data quality checks and transformations.

Your mission:
→ Handle missing value detection and imputation
→ Detect and treat outliers
→ Identify and remove duplicate rows
→ Perform data cleaning and preprocessing

TOPICS YOU MUST HANDLE:
- Missing values: Detection and imputation (median, mean, mode, or drop)
- Outliers: Detection and treatment (capping, removal)
- Duplicates: Detection and removal
- Data cleaning: Preprocessing and transformation""",
            
            "data_insight": """You are a Data Insight Agent for generating data insights and visualizations.

Your mission:
→ Generate bivariate analysis
→ Perform correlation analysis
→ Create data insights and visualizations
→ Provide statistical summaries

TOPICS YOU MUST HANDLE:
- Bivariate analysis
- Correlation analysis and correlation matrices
- Data insights and visualizations
- Statistical summaries""",
            
            "plan_agent": """You are a Planner Agent for creating data quality analysis plans.

Your mission:
→ Create analysis plans for data quality checks
→ Plan data transformations
→ Recommend treatments for data issues

TOPICS YOU MUST HANDLE:
- Creating data quality analysis plans
- Planning missing value treatments
- Planning outlier treatments
- Planning duplicate removal strategies""",
            
            "code_execution": """You are a Code Execution Agent for executing Python code.

Your mission:
→ Execute Python code for data analysis
→ Run data transformations
→ Validate code execution

TOPICS YOU MUST HANDLE:
- Python code execution
- Data analysis code
- Data transformation code"""
        }
        
        return prompts.get(self.agent_name, "You are an AI assistant.")
    
    def _extract_keywords_from_prompt(self, agent_prompt: str) -> List[str]:
        """
        Extract relevant keywords from agent prompt
        Uses predefined keywords for each agent
        """
        return self.AGENT_KEYWORDS.get(self.agent_name, [])
    
    def _fast_relevance_check(self, query: str, relevant_keywords: List[str]) -> Tuple[bool, Optional[bool]]:
        """
        Fast keyword-based relevance check (no LLM call)
        Returns: (is_clear, is_relevant)
        - (True, False): Clear & Not Relevant (no relevant keywords found)
        - (False, None): Unclear, need LLM check (relevant keywords found, but could be partially relevant)
        """
        if not relevant_keywords:
            return (False, None)  # Unclear, need LLM check
        
        query_lower = query.lower()
        
        # Check if relevant keywords are present
        has_relevant = any(kw in query_lower for kw in relevant_keywords)
        
        if not has_relevant:
            # No relevant keywords → Completely irrelevant
            return (True, False)  # Clear & Not Relevant
        else:
            # Relevant keywords found → Need LLM check
            # (Could be fully relevant OR partially relevant)
            return (False, None)  # Unclear → Need LLM check
    
    def _llm_relevance_check(self, query: str, agent_prompt: str) -> Dict[str, Any]:
        """
        LLM-based relevance check for unclear cases
        """
        try:
            validation_prompt = build_llm_validation_prompt(query, agent_prompt)
            
            # Call LLM with timeout
            response = self.llm_service.get_response_route(validation_prompt, [], context="guardrail")
            
            # Parse response
            result = parse_llm_response(response)
            
            return result
        except Exception as e:
            self.logger.error(f"LLM relevance check failed: {e}")
            # Fallback: allow through on error
            return handle_timeout()
    
    @staticmethod
    def is_completely_irrelevant(query: str) -> bool:
        """
        Check if query is completely irrelevant to ALL agents
        Returns True if query has NO relevant keywords from ANY agent
        """
        query_lower = query.lower()
        
        # Collect all keywords from all agents
        all_keywords = []
        for agent_keywords in Guard.AGENT_KEYWORDS.values():
            all_keywords.extend(agent_keywords)
        
        # Check if query has ANY relevant keyword
        has_any_relevant = any(kw in query_lower for kw in all_keywords)
        
        # If no relevant keywords found → completely irrelevant
        return not has_any_relevant
    
    def _get_guidance_message(
        self,
        agent_name: str,
        relevance_level: str,
        relevant_parts: List[str],
        irrelevant_parts: List[str],
        agent_prompt: str
    ) -> str:
        """
        Generate guidance message based on relevance level
        """
        if relevance_level == "partially_relevant":
            irrelevant_str = ", ".join(irrelevant_parts) if irrelevant_parts else "those parts"
            relevant_str = ", ".join(relevant_parts) if relevant_parts else "the relevant parts"
            
            return (
                f"Please note that I cannot assist you with {irrelevant_str} "
                f"as that is out of my training scope. "
                f"Would you like me to proceed with just {relevant_str}?"
            )
        
        elif relevance_level == "not_relevant":
            # Get agent info
            agent_info = self.AGENT_INFO.get(self.agent_name, {
                "name": f"{self.agent_name} Agent",
                "capabilities": ["Data analysis tasks"]
            })
            
            agent_display_name = agent_info["name"]
            capabilities = agent_info["capabilities"]
            
            capabilities_str = "\n".join(f"- {cap}" for cap in capabilities)
            
            return (
                f"I am a {agent_display_name} for MIDAS. "
                f"I can help you with:\n{capabilities_str}\n\n"
                f"Could you please rephrase your question related to these capabilities?"
            )
        
        return None
    
    def validate_input(
        self,
        query: str,
        agent_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate user query against agent capabilities
        
        Returns:
            {
                "is_valid": bool,
                "guidance": str or None,
                "filtered_query": str or None,
                "relevance_level": str
            }
        """
        try:
            # Get agent prompt if not provided
            if agent_prompt is None:
                agent_prompt = self._get_agent_prompt()
            
            # Extract relevant keywords from prompt
            relevant_keywords = self._extract_keywords_from_prompt(agent_prompt)
            
            # Step 1: Fast check (no LLM call)
            is_clear, is_relevant = self._fast_relevance_check(query, relevant_keywords)
            
            if is_clear and is_relevant:
                # Fast check: Relevant → Process normally
                return {
                    "is_valid": True,
                    "guidance": None,
                    "filtered_query": query,
                    "relevance_level": "fully_relevant"
                }
            
            if is_clear and not is_relevant:
                # Fast check: Completely irrelevant (no relevant keywords found)
                guidance = self._get_guidance_message(
                    self.agent_name,
                    "not_relevant",
                    [],
                    [],
                    agent_prompt
                )
                return {
                    "is_valid": False,
                    "guidance": guidance,
                    "filtered_query": None,
                    "relevance_level": "not_relevant"
                }
            
            # Step 3: LLM check (partially relevant)
            llm_result = self._llm_relevance_check(query, agent_prompt)
            
            relevance_level = llm_result.get("relevance_level", "fully_relevant")
            relevant_parts = llm_result.get("relevant_parts", [])
            irrelevant_parts = llm_result.get("irrelevant_parts", [])
            filtered_query = llm_result.get("filtered_query", query)
            
            # Generate guidance message
            guidance = self._get_guidance_message(
                self.agent_name,
                relevance_level,
                relevant_parts,
                irrelevant_parts,
                agent_prompt
            )
            
            # Override with LLM guidance if provided
            if llm_result.get("guidance"):
                guidance = llm_result["guidance"]
            
            if relevance_level == "not_relevant":
                return {
                    "is_valid": False,
                    "guidance": guidance,
                    "filtered_query": None,
                    "relevance_level": "not_relevant"
                }
            elif relevance_level == "partially_relevant":
                return {
                    "is_valid": True,  # Still valid, but filtered
                    "guidance": guidance,
                    "filtered_query": filtered_query,
                    "relevance_level": "partially_relevant"
                }
            else:
                # fully_relevant
                return {
                    "is_valid": True,
                    "guidance": None,
                    "filtered_query": query,
                    "relevance_level": "fully_relevant"
                }
        
        except Exception as e:
            self.logger.error(f"Guard validation error: {e}", exc_info=True)
            # Fail open: Allow query through on error
            return {
                "is_valid": True,
                "guidance": None,
                "filtered_query": query,
                "relevance_level": "fully_relevant"
            }


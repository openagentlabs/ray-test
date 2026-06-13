"""
MIDAS Testing Configuration
"""

import os
from pathlib import Path

# Test Configuration
TEST_CONFIG = {
    "backend_url": os.getenv("MIDAS_BACKEND_URL", "http://localhost:8000"),
    "test_dataset_path": os.getenv("MIDAS_TEST_DATASET", "testing/loan_data_sample 3.csv"),
    "test_data_dictionary_path": os.getenv("MIDAS_DATA_DICTIONARY", "testing/LCDataDictionary 2 4.csv"),
    "test_timeout": int(os.getenv("MIDAS_TEST_TIMEOUT", "600")),  # 10 minutes for larger dataset
    "verbose_logging": os.getenv("MIDAS_VERBOSE", "false").lower() == "true",
    
    # Test Data Configuration - Updated for Lending Club data
    "sample_data": {
        "classification": {
            "target_variable": "target_flag",  # Binary target for loan default prediction
            "features": ["loan_amnt", "funded_amnt", "term", "int_rate", "installment", 
                        "grade", "emp_length", "home_ownership", "annual_inc", 
                        "verification_status", "dti", "delinq_2yrs", "inq_last_6mths",
                        "open_acc", "pub_rec", "revol_bal", "revol_util", "total_acc"],
            "categorical_features": ["grade", "home_ownership", "verification_status", "term"],
            "numerical_features": ["loan_amnt", "funded_amnt", "int_rate", "installment", 
                                 "emp_length", "annual_inc", "dti", "delinq_2yrs", 
                                 "inq_last_6mths", "open_acc", "pub_rec", "revol_bal", 
                                 "revol_util", "total_acc"]
        },
        "regression": {
            "target_variable": "loan_amnt",
            "features": ["funded_amnt", "int_rate", "installment", "annual_inc", 
                        "dti", "delinq_2yrs", "open_acc", "revol_bal", "total_acc"],
            "categorical_features": ["grade", "home_ownership"],
            "numerical_features": ["funded_amnt", "int_rate", "installment", "annual_inc", 
                                 "dti", "delinq_2yrs", "open_acc", "revol_bal", "total_acc"]
        }
    },
    
    # Model Configuration
    "algorithms_to_test": [
        "xgboost",
        "random_forest", 
        "logistic_regression",
        "gradient_boosting",
        "catboost",
        "lightgbm"
    ],
    
    # Segmentation Configuration
    "segmentation_config": {
        "min_segment_size": 1000,  # Larger for bigger dataset
        "max_segments": 5,
        "methods": ["cart", "chaid"]
    },
    
    # Feature Engineering Configuration
    "feature_engineering_config": {
        "woe_bins": 10,
        "log_shift": 1e-6,
        "vif_threshold": 5.0
    },
    
    # Hyperparameter Optimization
    "optimization_config": {
        "methods": ["bayesian", "random"],
        "max_evaluations": 20,
        "target_metrics": ["auc_roc", "f1_score", "accuracy"]
    },
    
    # DatasetOverviewSidebar Features
    "sidebar_features": {
        "overview_tab": [
            "dataset_statistics",
            "key_metrics",
            "data_types_distribution",
            "column_details",
            "target_distribution"
        ],
        "quality_tab": [
            "data_quality_score",
            "completeness_analysis",
            "validity_analysis",
            "missing_values_analysis",
            "duplicate_detection",
            "outlier_detection",
            "quality_recommendations"
        ],
        "insights_tab": [
            "bivariate_analysis",
            "correlation_analysis",
            "correlation_matrix",
            "multicollinearity_analysis",
            "data_distribution_insights"
        ],
        "config_tab": [
            "dataset_configuration",
            "target_variable_setup",
            "problem_statement",
            "data_dictionary_integration",
            "knowledge_graph_generation",
            "raw_data_viewing",
            "dataset_export"
        ],
        "segmentation_tab": [
            "segmentation_results",
            "segment_sizes_charts",
            "segment_proportions",
            "segment_viability_analysis",
            "segment_profiling"
        ]
    }
}

# Expected API Response Structure
EXPECTED_RESPONSES = {
    "upload": {
        "required_fields": ["dataset_id", "filename", "file_size"],
        "status_code": 200
    },
    "model_training": {
        "required_fields": ["model_id", "algorithm", "performance_metrics"],
        "status_code": 200
    },
    "evaluation": {
        "required_fields": ["model_id", "metrics", "feature_importance"],
        "status_code": 200
    },
    "knowledge_graph": {
        "required_fields": ["nodes", "edges"],
        "status_code": 200
    }
}

# Test Scenarios - Updated with complete feature list
TEST_SCENARIOS = {
    "basic_workflow": [
        "data_ingestion",
        "dataset_validation", 
        "problem_type_detection",
        "data_quality_checks",
        "model_training",
        "model_evaluation"
    ],
    
    "advanced_workflow": [
        "data_ingestion",
        "dataset_validation",
        "data_quality_checks",
        "bivariate_analysis",
        "correlation_analysis",
        "segmentation",
        "feature_engineering",
        "model_training",
        "hyperparameter_optimization",
        "model_evaluation",
        "explainability_analysis"
    ],
    
    "comprehensive_workflow": [
        # Dataset Management & Ingestion
        "data_ingestion",
        "dataset_validation", 
        "problem_type_detection",
        "data_dictionary_upload",
        
        # Data Quality & Treatment (Quality Tab)
        "data_quality_overview",
        "completeness_analysis",
        "validity_analysis",
        "missing_value_treatment",
        "duplicate_detection",
        "outlier_detection",
        "quality_recommendations",
        
        # Data Insights & Analysis (Insights Tab)
        "bivariate_analysis",
        "correlation_analysis", 
        "correlation_matrix",
        "multicollinearity_analysis",
        "vif_analysis",
        "data_distribution_insights",
        
        # Knowledge Graph (Config Tab)
        "knowledge_graph_generation",
        
        # Segmentation (Segmentation Tab)
        "segmentation_cart",
        "segmentation_chaid",
        "segment_profiling",
        "segment_sizes_analysis",
        "segment_viability_analysis",
        "segmented_insights",
        
        # Feature Engineering
        "feature_engineering",
        "woe_transformation",
        "log_transformation",
        "one_hot_encoding",
        
        # Model Training
        "global_model_training",
        "segment_model_training",
        "hyperparameter_optimization",
        "model_training_with_vif",
        
        # Model Evaluation (MEEA)
        "model_evaluation",
        "performance_metrics",
        "feature_importance",
        "granular_accuracy",
        "error_patterns",
        
        # AI Explainability
        "shap_analysis",
        "lime_analysis",
        "partial_dependence_plots",
        "permutation_importance",
        
        # Chat & AI Assistant
        "chat_interface",
        "code_execution",
        
        # Reporting & Documentation
        "model_codebook",
        "api_documentation",
        "raw_data_viewing",
        "dataset_export"
    ]
}

def get_config():
    """Get test configuration"""
    return TEST_CONFIG

def get_test_scenarios():
    """Get available test scenarios"""
    return TEST_SCENARIOS

def validate_config():
    """Validate test configuration"""
    config = get_config()
    
    # Check if test dataset exists
    dataset_path = Path(__file__).parent.parent / config["test_dataset_path"]
    if not dataset_path.exists():
        print(f"⚠️  Warning: Test dataset not found at {dataset_path}")
        return False
    
    # Check if data dictionary exists
    dict_path = Path(__file__).parent.parent / config["test_data_dictionary_path"]
    if not dict_path.exists():
        print(f"⚠️  Warning: Data dictionary not found at {dict_path}")
        return False
    
    # Check backend URL format
    if not config["backend_url"].startswith("http"):
        print("❌ Invalid backend URL format")
        return False
    
    return True

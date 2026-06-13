import pandas as pd
import numpy as np
import joblib
import os
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, 
    roc_auc_score, log_loss, mean_squared_error, r2_score,
    mean_absolute_error
)
import warnings
warnings.filterwarnings('ignore')

# Try to import AutoML libraries
try:
    from flaml import AutoML
    FLAML_AVAILABLE = True
except ImportError:
    FLAML_AVAILABLE = False

try:
    from tpot import TPOTClassifier, TPOTRegressor
    TPOT_AVAILABLE = True
except ImportError:
    TPOT_AVAILABLE = False

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Global storage for training logs
training_logs_storage = {}

class ModelTrainingService:
    """Service for automated machine learning model training"""
    
    def __init__(self):
        self.logger = logger
        self.model_storage_path = "models/"
        self.ensure_model_directory()
        
    def ensure_model_directory(self):
        """Ensure model storage directory exists"""
        if not os.path.exists(self.model_storage_path):
            os.makedirs(self.model_storage_path)
    
    def add_training_log(self, model_id: str, message: str):
        """Add a training log message for a specific model"""
        if model_id not in training_logs_storage:
            training_logs_storage[model_id] = []
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        training_logs_storage[model_id].append(log_entry)
        
        # Keep only last 50 logs to prevent memory issues
        if len(training_logs_storage[model_id]) > 50:
            training_logs_storage[model_id] = training_logs_storage[model_id][-50:]
    
    def get_training_logs(self, model_id: str) -> List[str]:
        """Get training logs for a specific model"""
        return training_logs_storage.get(model_id, [])
    
    def clear_training_logs(self, model_id: str):
        """Clear training logs for a specific model"""
        if model_id in training_logs_storage:
            del training_logs_storage[model_id]
    
    def preprocess_data(self, df: pd.DataFrame, target_column: str, 
                       independent_variables: List[str]) -> Tuple[pd.DataFrame, pd.Series]:
        """Preprocess data for machine learning"""
        try:
            # Select only required columns
            feature_columns = [col for col in independent_variables if col in df.columns]
            if target_column not in df.columns:
                raise ValueError(f"Target column '{target_column}' not found in dataset")
            
            # Prepare features and target
            X = df[feature_columns].copy()
            y = df[target_column].copy()
            
            # Handle missing values
            for col in X.columns:
                if X[col].dtype in ['object', 'category']:
                    X[col] = X[col].fillna(X[col].mode()[0] if not X[col].mode().empty else 'Unknown')
                else:
                    X[col] = X[col].fillna(X[col].median())
            
            # Encode categorical variables
            categorical_columns = X.select_dtypes(include=['object', 'category']).columns
            label_encoders = {}
            
            for col in categorical_columns:
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))
                label_encoders[col] = le
            
            # Scale numerical features
            numerical_columns = X.select_dtypes(include=[np.number]).columns
            scaler = StandardScaler()
            X[numerical_columns] = scaler.fit_transform(X[numerical_columns])
            
            # Store preprocessing objects for later use
            self.label_encoders = label_encoders
            self.scaler = scaler
            
            self.logger.info(f"Data preprocessed: {X.shape[0]} samples, {X.shape[1]} features")
            return X, y
            
        except Exception as e:
            self.logger.error(f"Error preprocessing data: {str(e)}")
            raise
    
    def detect_problem_type(self, y: pd.Series) -> str:
        """Detect if problem is classification or regression"""
        try:
            # Check if target is non-numeric or boolean
            if not pd.api.types.is_numeric_dtype(y):
                return 'classification'
            
            # Check if target is boolean
            if y.dtype == bool:
                return 'classification'
            
            # For numeric targets, check unique values
            unique_count = y.nunique()
            total_count = len(y)
            unique_ratio = unique_count / total_count
            
            # Binary classification (0/1)
            if unique_count == 2:
                unique_vals = sorted(y.dropna().unique())
                if (unique_vals[0] == 0 and unique_vals[1] == 1) or \
                   (unique_vals[0] == 0.0 and unique_vals[1] == 1.0):
                    return 'classification'
            
            # Categorical classification (few unique values)
            if unique_count <= 20 and unique_ratio <= 0.05:
                # Check if values are mostly integers
                integer_count = sum(1 for val in y.dropna().unique() if isinstance(val, (int, np.integer)) or (isinstance(val, float) and val.is_integer()))
                if integer_count / len(y.dropna().unique()) > 0.8:
                    return 'classification'
            
            # Default to regression for numeric variables
            return 'regression'
            
        except Exception as e:
            self.logger.error(f"Error detecting problem type: {str(e)}")
            return 'regression'  # Default fallback
    
    def select_algorithms(self, problem_type: str) -> List[str]:
        """Select appropriate algorithms based on problem type"""
        if problem_type == 'classification':
            return ['LightGBM', 'XGBoost', 'RandomForest', 'LogisticRegression', 'CatBoost', 'ExtraTrees', 'KNN', 'SVM']
        else:  # regression
            return ['LightGBM', 'XGBoost', 'RandomForest', 'LinearRegression', 'CatBoost', 'ExtraTrees', 'KNN', 'Ridge']
    
    def flaml_optimization(self, X: pd.DataFrame, y: pd.Series, 
                          problem_type: str, target_metric: str, 
                          time_budget: int = 30) -> Dict[str, Any]:
        """Use FLAML for hyperparameter optimization"""
        if not FLAML_AVAILABLE:
            raise ImportError("FLAML not available")
        
        try:
            automl = AutoML()
            
            # Map target metric to FLAML metric
            flaml_metric_map = {
                'f1': 'f1',
                'auc': 'roc_auc',
                'accuracy': 'accuracy',
                'precision': 'precision',
                'recall': 'recall',
                'log_loss': 'log_loss',
                'r2': 'r2',
                'mae': 'mae',
                'mse': 'mse',
                'rmse': 'rmse'
            }
            
            flaml_metric = flaml_metric_map.get(target_metric, 'auto')
            
            # Configure FLAML for fast training with all learners
            automl_settings = {
                'time_budget': 300,
                'metric': flaml_metric,
                'task': "classification" if problem_type == "classification" else "regression",
                'verbose': 0,
                'max_iter': 20,  # Limit iterations for faster training
                'n_jobs': 4,    # Use single job for faster startup
                'sample': False, # Use sampling for faster training
                'eval_method': 'cv',  # Use holdout instead of CV for speed
                # Add learner selection - let FLAML choose from all available
                'learner_selector': 'auto',
                'estimator_list': ['rf', 'xgboost','lgbm', 'catboost', 'extra_tree', 'kneighbor']  # This will try all available learners
            }
            
            automl.fit(X, y, **automl_settings)
            
            # Better algorithm name extraction
            selected_algorithm = "Unknown"
            if hasattr(automl, 'best_config') and automl.best_config:
                # Try different possible keys for learner name
                learner_keys = ['learner', 'model', 'algorithm', 'estimator']
                for key in learner_keys:
                    if key in automl.best_config:
                        selected_algorithm = automl.best_config[key]
                        break
                
                # If still unknown, try to get from model type
                if selected_algorithm == "Unknown" and hasattr(automl, 'model'):
                    model_type = type(automl.model).__name__
                    # Map sklearn model names to readable names
                    model_mapping = {
                        'LGBMClassifier': 'LightGBM',
                        'LGBMRegressor': 'LightGBM',
                        'LGBMEstimator': 'LightGBM',  # FLAML's LightGBM wrapper
                        'RandomForestClassifier': 'Random Forest',
                        'RandomForestRegressor': 'Random Forest',
                        'XGBClassifier': 'XGBoost',
                        'XGBRegressor': 'XGBoost',
                        'CatBoostClassifier': 'CatBoost',
                        'CatBoostRegressor': 'CatBoost',
                        'LogisticRegression': 'Logistic Regression',
                        'LinearRegression': 'Linear Regression',
                        'ExtraTreesClassifier': 'Extra Trees',
                        'ExtraTreesRegressor': 'Extra Trees',
                        'KNeighborsClassifier': 'K-Nearest Neighbors',
                        'KNeighborsRegressor': 'K-Nearest Neighbors',
                        'SVC': 'Support Vector Machine',
                        'Ridge': 'Ridge Regression'
                    }
                    selected_algorithm = model_mapping.get(model_type, model_type)
            
            return {
                'best_model': automl.model,
                'best_params': automl.best_config,
                'best_score': automl.best_loss,
                'method': 'flaml',
                'selected_algorithm': selected_algorithm
            }
            
        except Exception as e:
            self.logger.error(f"FLAML optimization failed: {str(e)}")
            raise
    
    def tpot_optimization(self, X: pd.DataFrame, y: pd.Series, 
                         problem_type: str, target_metric: str,
                         generations: int = 5) -> Dict[str, Any]:
        """Use TPOT for hyperparameter optimization"""
        if not TPOT_AVAILABLE:
            raise ImportError("TPOT not available")
        
        try:
            if problem_type == 'classification':
                tpot = TPOTClassifier(
                    generations=generations,
                    population_size=20,
                    verbosity=2,
                    random_state=42
                )
            else:
                tpot = TPOTRegressor(
                    generations=generations,
                    population_size=20,
                    verbosity=2,
                    random_state=42
                )
            
            tpot.fit(X, y)
            
            return {
                'best_model': tpot.fitted_pipeline_,
                'best_params': getattr(tpot, 'best_params_', {}),
                'best_score': getattr(tpot, 'best_score_', 0),
                'method': 'tpot'
            }
            
        except Exception as e:
            self.logger.error(f"TPOT optimization failed: {str(e)}")
            raise
    
    def manual_optimization(self, X: pd.DataFrame, y: pd.Series, 
                           problem_type: str, target_metric: str) -> Dict[str, Any]:
        """Manual sklearn optimization as fallback"""
        try:
            # Select base model with fast training settings
            if problem_type == 'classification':
                base_model = LogisticRegression(random_state=42, max_iter=1)
                param_grid = {
                    'C': [0.1, 1.0],
                    'penalty': ['l2'],
                    'solver': ['liblinear']
                }
            else:
                base_model = LinearRegression()
                param_grid = {}  # Linear regression has no hyperparameters
            
            # Grid search with minimal parameters for speed
            grid_search = GridSearchCV(
                base_model, 
                param_grid, 
                cv=3,  # Reduced CV folds for speed
                scoring=target_metric,
                n_jobs=1  # Single job for faster startup
            )
            grid_search.fit(X, y)
            
            # Map sklearn model names to readable names
            model_type = type(grid_search.best_estimator_).__name__
            model_mapping = {
                'LogisticRegression': 'Logistic Regression',
                'LinearRegression': 'Linear Regression',
                'RandomForestClassifier': 'Random Forest',
                'RandomForestRegressor': 'Random Forest',
                'LGBMClassifier': 'LightGBM',
                'LGBMRegressor': 'LightGBM',
                'LGBMEstimator': 'LightGBM'
            }
            selected_algorithm = model_mapping.get(model_type, model_type)
            
            return {
                'best_model': grid_search.best_estimator_,
                'best_params': grid_search.best_params_,
                'best_score': grid_search.best_score_,
                'method': 'manual',
                'selected_algorithm': selected_algorithm
            }
            
        except Exception as e:
            self.logger.error(f"Manual optimization failed: {str(e)}")
            raise
    
    def optimize_hyperparameters(self, X: pd.DataFrame, y: pd.Series, 
                               problem_type: str, target_metric: str) -> Dict[str, Any]:
        """Optimize hyperparameters using available methods"""
        optimization_methods = []
        
        # Try FLAML first
        if FLAML_AVAILABLE:
            optimization_methods.append(self.flaml_optimization)
        
        # Try TPOT as fallback
        if TPOT_AVAILABLE:
            optimization_methods.append(self.tpot_optimization)
        
        # Manual optimization as final fallback
        optimization_methods.append(self.manual_optimization)
        
        last_error = None
        for method in optimization_methods:
            try:
                self.logger.info(f"Trying optimization method: {method.__name__}")
                result = method(X, y, problem_type, target_metric)
                self.logger.info(f"Optimization successful with {result['method']}")
                return result
            except Exception as e:
                self.logger.warning(f"Optimization method {method.__name__} failed: {str(e)}")
                last_error = e
                continue
        
        # If all methods fail, raise the last error
        raise Exception(f"All optimization methods failed. Last error: {str(last_error)}")
    
    def train_final_model(self, model: Any, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Train the final model and evaluate performance"""
        try:
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, 
                stratify=y if len(y.unique()) <= 10 else None
            )
            
            # Train model
            model.fit(X_train, y_train)
            
            # Make predictions
            y_pred = model.predict(X_test)
            y_pred_proba = None
            
            # Get prediction probabilities ONLY for classification
            if hasattr(model, 'predict_proba') and len(y.unique()) <= 10:  # Classification
                y_pred_proba = model.predict_proba(X_test)
            
            # Calculate metrics
            metrics = self.calculate_metrics(y_test, y_pred, y_pred_proba)
            
            # Cross-validation scores
            cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='accuracy' if len(y.unique()) <= 10 else 'r2')
            
            # Feature importance - REMOVED
            feature_importance = []
            
            return {
                'model': model,
                'metrics': metrics,
                'cv_scores': cv_scores.tolist(),
                'feature_importance': feature_importance,
                'test_size': len(X_test)
            }
            
        except Exception as e:
            self.logger.error(f"Error training final model: {str(e)}")
            raise
    
    def calculate_metrics(self, y_true: pd.Series, y_pred: np.ndarray, 
                         y_pred_proba: Optional[np.ndarray] = None) -> Dict[str, float]:
        """Calculate comprehensive metrics"""
        metrics = {}
        
        try:
            # Classification metrics
            if len(y_true.unique()) <= 10:  # Classification
                metrics['accuracy'] = float(accuracy_score(y_true, y_pred))
                metrics['precision'] = float(precision_score(y_true, y_pred, average='weighted'))
                metrics['recall'] = float(recall_score(y_true, y_pred, average='weighted'))
                metrics['f1'] = float(f1_score(y_true, y_pred, average='weighted'))
                
                if y_pred_proba is not None and len(y_true.unique()) == 2:
                    metrics['auc'] = float(roc_auc_score(y_true, y_pred_proba[:, 1]))
                    metrics['log_loss'] = float(log_loss(y_true, y_pred_proba))
            
            # Regression metrics
            else:
                metrics['r2'] = float(r2_score(y_true, y_pred))
                metrics['mae'] = float(mean_absolute_error(y_true, y_pred))
                metrics['mse'] = float(mean_squared_error(y_true, y_pred))
                metrics['rmse'] = float(np.sqrt(mean_squared_error(y_true, y_pred)))
            
        except Exception as e:
            self.logger.error(f"Error calculating metrics: {str(e)}")
            # Return basic metrics if detailed calculation fails
            metrics = {'accuracy': 0.0}
        
        return metrics
    
    def select_best_model(self, optimization_result: Dict[str, Any], 
                        target_metric: str, target_value: float) -> Dict[str, Any]:
        """Select the best model based on target metric and value"""
        try:
            model = optimization_result['best_model']
            achieved_value = optimization_result['best_score']
            
            # Calculate difference from target
            difference = abs(achieved_value - target_value)
            
            return {
                'model': model,
                'achieved_value': achieved_value,
                'target_value': target_value,
                'difference': difference,
                'optimization_method': optimization_result['method']
            }
            
        except Exception as e:
            self.logger.error(f"Error selecting best model: {str(e)}")
            raise
    
    def save_model_artifact(self, model: Any, model_id: str) -> str:
        """Save model artifact to disk"""
        try:
            artifact_path = os.path.join(self.model_storage_path, f"{model_id}.pkl")
            joblib.dump(model, artifact_path)
            self.logger.info(f"Model saved to: {artifact_path}")
            return artifact_path
        except Exception as e:
            self.logger.error(f"Error saving model: {str(e)}")
            raise
    
    async def run_auto_training(self, dataset_id: str, target_column: str, 
                              target_metric: str, target_value: float,
                              independent_variables: List[str],
                              max_runtime_secs: int = 60) -> Dict[str, Any]:
        """Main method to run the complete auto training pipeline"""
        start_time = datetime.now()
        model_id = f"MDL_AUTO_{uuid.uuid4().hex[:8].upper()}"
        
        try:
            self.logger.info(f"Starting auto training for model {model_id}")
            self.add_training_log(model_id, f"Starting auto training for model {model_id}")
            
            # Step 1: Load real dataset
            from app.services.dataset_service import dataset_manager
            df = dataset_manager.load_dataset(dataset_id)
            
            if df is None:
                raise ValueError(f"Dataset {dataset_id} not found or could not be loaded")
            
            self.logger.info(f"Loaded dataset with shape: {df.shape}")
            self.add_training_log(model_id, f"Loaded dataset with shape: {df.shape}")
            
            # Step 2: Preprocess data
            self.logger.info("Step 1/4: Data Preprocessing")
            self.add_training_log(model_id, "Step 1/4: Data Preprocessing")
            X, y = self.preprocess_data(df, target_column, independent_variables)
            self.add_training_log(model_id, f"Data preprocessed: {X.shape[0]} samples, {X.shape[1]} features")
            # Track which features were actually used during preprocessing
            used_features = list(X.columns)
            
            # Step 3: Detect problem type
            problem_type = self.detect_problem_type(y)
            self.logger.info(f"Detected problem type: {problem_type}")
            self.add_training_log(model_id, f"Detected problem type: {problem_type}")
            
            # Step 4: Algorithm Selection
            self.logger.info("Step 2/4: Algorithm Selection")
            self.add_training_log(model_id, "Step 2/4: Algorithm Selection")
            algorithms = self.select_algorithms(problem_type)
            self.logger.info(f"Selected algorithms: {algorithms}")
            self.add_training_log(model_id, f"Selected algorithms: {algorithms}")
            
            # Step 5: Hyperparameter Optimization
            self.logger.info("Step 3/4: Hyperparameter Optimization")
            self.add_training_log(model_id, "Step 3/4: Hyperparameter Optimization")
            optimization_result = self.optimize_hyperparameters(X, y, problem_type, target_metric)
            self.add_training_log(model_id, f"Optimization successful with {optimization_result['method']}")
            
            # Step 6: Training
            self.logger.info("Step 4/4: Training")
            self.add_training_log(model_id, "Step 4/4: Training")
            training_result = self.train_final_model(optimization_result['best_model'], X, y)
            
            # Step 7: Model Selection
            # Use the actual training metrics instead of optimization score
            achieved_value = training_result['metrics'].get(target_metric, 0.0)
            best_model_result = {
                'model': training_result['model'],
                'achieved_value': achieved_value,
                'target_value': target_value,
                'difference': abs(achieved_value - target_value),
                'optimization_method': optimization_result['method']
            }
            
            # Step 8: Save model artifact
            artifact_path = self.save_model_artifact(training_result['model'], model_id)
            self.add_training_log(model_id, f"Model saved to: {artifact_path}")
            
            # Calculate training time
            training_time = (datetime.now() - start_time).total_seconds()
            self.add_training_log(model_id, f"Auto training completed successfully for model {model_id}")
            
            # Prepare response with real metrics
            response = {
                "model_id": model_id,
                "problem_type": problem_type,
                "metrics": training_result['metrics'],
                "user_defined_metric": {
                    "metric_name": target_metric,
                    "target_value": target_value,
                    "achieved_value": best_model_result['achieved_value'],
                    "difference": best_model_result['difference']
                },
                "artifact_path": artifact_path,
                "training_time_seconds": int(training_time),
                "feature_importance": [],  # Removed feature importance
                "cross_validation_scores": training_result['cv_scores'],
                "optimization_method": optimization_result['method'],
                "selected_algorithm": optimization_result.get('selected_algorithm', 'Unknown'),
                "hyperparameters": optimization_result['best_params'],
                # Expose the exact feature list used so the modelling agent
                # can answer "variables used in model training" queries
                "used_features": used_features,
            }
            
            self.logger.info(f"Auto training completed successfully for model {model_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Auto training failed: {str(e)}")
            raise

# Create singleton instance
model_training_service = ModelTrainingService()
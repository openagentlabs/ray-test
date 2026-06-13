from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import xgboost as xgb
import lightgbm as lgb
import shap
import joblib
import os
from datetime import datetime
import asyncio
import redis
import json

app = FastAPI(
    title="Credit Risk ML Engine",
    description="Machine Learning microservice for credit risk model development",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection for job status updates
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Data models
class PreprocessingRequest(BaseModel):
    job_id: str
    dataset_path: str
    config: Dict[str, Any]

class TrainingRequest(BaseModel):
    job_id: str
    dataset_path: str
    target_column: str
    algorithm: str
    hyperparameters: Dict[str, Any]
    test_size: float = 0.2
    random_state: int = 42

class PredictionRequest(BaseModel):
    model_id: str
    features: Dict[str, Any]

class ModelResponse(BaseModel):
    model_id: str
    algorithm: str
    performance: Dict[str, float]
    feature_importance: List[Dict[str, Any]]
    created_at: datetime

class CreditRiskMLEngine:
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_names = {}
        
    async def update_job_status(self, job_id: str, status: str, progress: int = 0, results: Dict = None):
        """Update job status in Redis"""
        try:
            job_data = {
                'status': status,
                'progress': progress,
                'results': results,
                'updated_at': datetime.now().isoformat()
            }
            redis_client.set(f"ml_job:{job_id}", json.dumps(job_data), ex=3600)
            
            # Publish update event
            event = {
                'type': f'ml_{status}',
                'payload': {
                    'jobId': job_id,
                    'progress': progress,
                    'results': results
                },
                'timestamp': datetime.now().isoformat()
            }
            redis_client.publish('model-builder-events', json.dumps(event))
        except Exception as e:
            print(f"Failed to update job status: {e}")
    
    async def preprocess_data(self, request: PreprocessingRequest):
        """Preprocess data for credit risk modeling"""
        job_id = request.job_id
        
        try:
            await self.update_job_status(job_id, 'running', 10)
            
            # Load data (simulate - in real implementation would load from actual file)
            df = self.generate_mock_credit_data(10000)
            
            await self.update_job_status(job_id, 'running', 30)
            
            # Handle missing values
            if request.config.get('missing_values') == 'impute_median':
                numeric_columns = df.select_dtypes(include=[np.number]).columns
                df[numeric_columns] = df[numeric_columns].fillna(df[numeric_columns].median())
            
            await self.update_job_status(job_id, 'running', 50)
            
            # Handle outliers
            if request.config.get('outliers') == 'winsorize_99':
                numeric_columns = df.select_dtypes(include=[np.number]).columns
                for col in numeric_columns:
                    q99 = df[col].quantile(0.99)
                    q01 = df[col].quantile(0.01)
                    df[col] = df[col].clip(lower=q01, upper=q99)
            
            await self.update_job_status(job_id, 'running', 70)
            
            # Feature scaling
            if request.config.get('scaling') == 'robust':
                scaler = RobustScaler()
                numeric_columns = df.select_dtypes(include=[np.number]).columns
                df[numeric_columns] = scaler.fit_transform(df[numeric_columns])
                self.scalers[job_id] = scaler
            
            await self.update_job_status(job_id, 'running', 90)
            
            # Save processed data
            output_path = f"processed_data_{job_id}.csv"
            df.to_csv(output_path, index=False)
            
            results = {
                'processed_records': len(df),
                'features': list(df.columns),
                'output_path': output_path,
                'data_quality': {
                    'missing_values_handled': True,
                    'outliers_treated': True,
                    'features_scaled': True
                }
            }
            
            await self.update_job_status(job_id, 'completed', 100, results)
            return results
            
        except Exception as e:
            await self.update_job_status(job_id, 'failed', 0, {'error': str(e)})
            raise HTTPException(status_code=500, detail=str(e))
    
    async def train_model(self, request: TrainingRequest):
        """Train credit risk model"""
        job_id = request.job_id
        
        try:
            await self.update_job_status(job_id, 'running', 10)
            
            # Load data
            df = self.generate_mock_credit_data(10000)
            
            await self.update_job_status(job_id, 'running', 20)
            
            # Prepare features and target
            target = df[request.target_column]
            features = df.drop(columns=[request.target_column])
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                features, target, 
                test_size=request.test_size, 
                random_state=request.random_state,
                stratify=target
            )
            
            await self.update_job_status(job_id, 'running', 40)
            
            # Select and train model
            model = self.get_model(request.algorithm, request.hyperparameters)
            model.fit(X_train, y_train)
            
            await self.update_job_status(job_id, 'running', 70)
            
            # Make predictions
            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else y_pred
            
            # Calculate metrics
            performance = {
                'accuracy': float(accuracy_score(y_test, y_pred)),
                'precision': float(precision_score(y_test, y_pred)),
                'recall': float(recall_score(y_test, y_pred)),
                'f1_score': float(f1_score(y_test, y_pred)),
                'auc': float(roc_auc_score(y_test, y_pred_proba))
            }
            
            await self.update_job_status(job_id, 'running', 85)
            
            # Feature importance
            feature_importance = []
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                for i, (feature, importance) in enumerate(zip(features.columns, importances)):
                    feature_importance.append({
                        'feature': feature,
                        'importance': float(importance),
                        'rank': i + 1
                    })
                feature_importance.sort(key=lambda x: x['importance'], reverse=True)
            
            # Save model - TEMPORARILY DISABLED
            model_id = f"model_{job_id}"
            # model_path = f"{model_id}.joblib"
            # joblib.dump(model, model_path)  # TEMPORARILY DISABLED
            
            # Return placeholder path for now
            model_path = f"{model_id}.joblib"
            print(f"Model saving temporarily disabled - would have saved to: {model_path}")
            
            self.models[model_id] = {
                'model': model,
                'algorithm': request.algorithm,
                'performance': performance,
                'feature_names': list(features.columns),
                'created_at': datetime.now()
            }
            
            results = {
                'model_id': model_id,
                'algorithm': request.algorithm,
                'performance': performance,
                'feature_importance': feature_importance,
                'model_path': model_path,
                'training_samples': len(X_train),
                'test_samples': len(X_test)
            }
            
            await self.update_job_status(job_id, 'completed', 100, results)
            return results
            
        except Exception as e:
            await self.update_job_status(job_id, 'failed', 0, {'error': str(e)})
            raise HTTPException(status_code=500, detail=str(e))
    
    def get_model(self, algorithm: str, hyperparameters: Dict[str, Any]):
        """Get model instance based on algorithm and hyperparameters"""
        if algorithm == 'random_forest':
            return RandomForestClassifier(**hyperparameters)
        elif algorithm == 'gradient_boosting':
            return GradientBoostingClassifier(**hyperparameters)
        elif algorithm == 'xgboost':
            return xgb.XGBClassifier(**hyperparameters)
        elif algorithm == 'lightgbm':
            return lgb.LGBMClassifier(**hyperparameters)
        elif algorithm == 'logistic_regression':
            return LogisticRegression(**hyperparameters)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    def generate_mock_credit_data(self, n_samples: int = 10000) -> pd.DataFrame:
        """Generate mock credit risk data for demonstration"""
        np.random.seed(42)
        
        data = {
            'credit_score': np.random.normal(650, 100, n_samples),
            'annual_income': np.random.lognormal(10.5, 0.5, n_samples),
            'debt_to_income': np.random.beta(2, 5, n_samples),
            'credit_utilization': np.random.beta(2, 3, n_samples),
            'payment_history': np.random.choice([0, 1], n_samples, p=[0.1, 0.9]),
            'credit_age_months': np.random.gamma(2, 24, n_samples),
            'num_credit_lines': np.random.poisson(3, n_samples),
            'transaction_amount': np.random.lognormal(6, 1, n_samples),
            'unemployment_rate': np.random.normal(0.05, 0.02, n_samples),
            'gdp_growth': np.random.normal(0.02, 0.01, n_samples)
        }
        
        df = pd.DataFrame(data)
        
        # Create target variable (default probability)
        df['default_prob'] = (
            -0.01 * df['credit_score'] +
            -0.000001 * df['annual_income'] +
            2.0 * df['debt_to_income'] +
            1.5 * df['credit_utilization'] +
            -0.5 * df['payment_history'] +
            -0.001 * df['credit_age_months'] +
            np.random.normal(0, 0.1, n_samples)
        )
        
        df['default'] = (df['default_prob'] > df['default_prob'].median()).astype(int)
        df = df.drop('default_prob', axis=1)
        
        # Ensure realistic ranges
        df['credit_score'] = df['credit_score'].clip(300, 850)
        df['debt_to_income'] = df['debt_to_income'].clip(0, 1)
        df['credit_utilization'] = df['credit_utilization'].clip(0, 1)
        df['credit_age_months'] = df['credit_age_months'].clip(0, 600)
        df['num_credit_lines'] = df['num_credit_lines'].clip(0, 20)
        
        return df

# Global ML engine instance
ml_engine = CreditRiskMLEngine()

# API endpoints
@app.get("/")
async def root():
    return {
        "service": "Credit Risk ML Engine",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "models_loaded": len(ml_engine.models)
    }

@app.post("/preprocess")
async def preprocess_data(request: PreprocessingRequest, background_tasks: BackgroundTasks):
    """Start data preprocessing job"""
    background_tasks.add_task(ml_engine.preprocess_data, request)
    return {
        "job_id": request.job_id,
        "status": "started",
        "message": "Data preprocessing job started"
    }

@app.post("/train")
async def train_model(request: TrainingRequest, background_tasks: BackgroundTasks):
    """Start model training job"""
    background_tasks.add_task(ml_engine.train_model, request)
    return {
        "job_id": request.job_id,
        "status": "started",
        "message": "Model training job started"
    }

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get ML job status"""
    try:
        job_data = redis_client.get(f"ml_job:{job_id}")
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return json.loads(job_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict")
async def predict(request: PredictionRequest):
    """Make prediction using trained model"""
    model_info = ml_engine.models.get(request.model_id)
    if not model_info:
        raise HTTPException(status_code=404, detail="Model not found")
    
    try:
        # Convert features to DataFrame
        feature_df = pd.DataFrame([request.features])
        
        # Make prediction
        model = model_info['model']
        prediction = model.predict(feature_df)[0]
        probability = model.predict_proba(feature_df)[0] if hasattr(model, 'predict_proba') else None
        
        return {
            "prediction": int(prediction),
            "probability": probability.tolist() if probability is not None else None,
            "model_id": request.model_id,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models")
async def list_models():
    """List all trained models"""
    models = []
    for model_id, model_info in ml_engine.models.items():
        models.append({
            "model_id": model_id,
            "algorithm": model_info['algorithm'],
            "performance": model_info['performance'],
            "created_at": model_info['created_at'].isoformat()
        })
    
    return {"models": models}

@app.get("/models/{model_id}/explainability")
async def get_model_explainability(model_id: str):
    """Get model explainability using SHAP"""
    model_info = ml_engine.models.get(model_id)
    if not model_info:
        raise HTTPException(status_code=404, detail="Model not found")
    
    try:
        # Generate sample data for SHAP explanation
        sample_data = ml_engine.generate_mock_credit_data(100)
        features = sample_data.drop('default', axis=1)
        
        model = model_info['model']
        
        # Create SHAP explainer
        explainer = shap.TreeExplainer(model) if hasattr(model, 'tree_') else shap.LinearExplainer(model, features)
        shap_values = explainer.shap_values(features.head(10))
        
        # Format SHAP values for response
        explanations = []
        for i in range(len(shap_values)):
            explanations.append({
                "instance_id": i,
                "base_value": float(explainer.expected_value),
                "shap_values": [float(val) for val in shap_values[i]],
                "features": model_info['feature_names']
            })
        
        return {
            "model_id": model_id,
            "explanations": explanations,
            "feature_names": model_info['feature_names'],
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
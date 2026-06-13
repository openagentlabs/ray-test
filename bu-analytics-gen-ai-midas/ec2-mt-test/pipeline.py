import os
import time
import gc
import uuid
import random
import logging
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, f1_score, accuracy_score, r2_score, mean_squared_error
import xgboost as xgb
import lightgbm as lgb
from catboost import CatBoostClassifier, CatBoostRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
import shap
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tools.tools import add_constant
from tqdm import tqdm

logger = logging.getLogger(__name__)

TARGET_VARIABLE = "target_Variable" 
#target_flag
#target_Variable
ID_COLUMN = "CAMPAIGN_SEQUENCE_NUMBER"
#id
#CAMPAIGN_SEQUENCE_NUMBER

def _can_stratify(y: pd.Series) -> bool:
    """
    sklearn train_test_split requires every class to appear at least twice
    when stratify=y. Otherwise use random split (same 60/20/20 sizes).
    """
    if y is None or len(y) == 0:
        return False
    counts = y.value_counts(dropna=False)
    return bool(counts.min() >= 2)

def calculate_vif(df, features):
    vif_data = {}
    if not features:
        return vif_data
    try:
        X = df[features].dropna()
        # Only use numeric columns
        X = X.select_dtypes(include=[np.number])
        if X.empty or X.shape[1] == 0:
            return vif_data
            
        X_with_const = add_constant(X)
        for i, col in enumerate(X_with_const.columns):
            if col == 'const':
                continue
            try:
                vif = variance_inflation_factor(X_with_const.values, i)
                vif_data[col] = vif
            except Exception:
                vif_data[col] = float('inf')
    except Exception as e:
        logger.warning(f"VIF calculation failed: {e}")
    return vif_data

def run_pipeline_for_csv(csv_path, output_dir, seed=42, rfe_locked_count=7):
    csv_stem = os.path.splitext(os.path.basename(csv_path))[0]
    dataset_id = f"{csv_stem}_{uuid.uuid4().hex[:8]}"
    
    timings = {}
    
    # 1. Load CSV
    t0 = time.perf_counter()
    logger.info(f"Loading CSV: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        logger.error(f"Failed to load CSV {csv_path}: {e}")
        return None, None, dataset_id
        
    if TARGET_VARIABLE not in df.columns:
        logger.error(f"Target column '{TARGET_VARIABLE}' not found in {csv_path}. Skipping.")
        return None, None, dataset_id
        
    if ID_COLUMN not in df.columns:
        logger.warning(f"ID column '{ID_COLUMN}' not found in {csv_path}. Proceeding anyway.")
        
    timings["load_csv"] = time.perf_counter() - t0
    
    # 2. Split Configuration (60/20/20)
    t0 = time.perf_counter()
    logger.info("Applying split configuration (60/20/20 train/val/test)")
    
    # Determine problem type
    target_series = df[TARGET_VARIABLE].dropna()
    is_classification = target_series.nunique() <= 20
    
    # Drop rows where target is null
    df = df.dropna(subset=[TARGET_VARIABLE])
    
    stratify_col = df[TARGET_VARIABLE] if is_classification else None
    use_strat_1 = is_classification and _can_stratify(stratify_col)
    if is_classification and not use_strat_1:
        logger.warning(
            "Stratified split skipped (some target classes have < 2 rows). "
            "Using random 60/20/20 split so training can proceed."
        )

    try:
        # Split into 60% train, 40% temp (val + test)
        train_df, temp_df = train_test_split(
            df,
            test_size=0.4,
            random_state=seed,
            stratify=stratify_col if use_strat_1 else None,
        )

        stratify_temp = temp_df[TARGET_VARIABLE] if is_classification else None
        use_strat_2 = is_classification and _can_stratify(stratify_temp)
        if is_classification and use_strat_1 and not use_strat_2:
            logger.warning(
                "Stratified split for val/test skipped (rare class in holdout slice). "
                "Using random 50/50 split of the 40% temp partition."
            )

        val_df, test_df = train_test_split(
            temp_df,
            test_size=0.5,
            random_state=seed,
            stratify=stratify_temp if use_strat_2 else None,
        )
        logger.info(
            "Split successful. Train: %s, Val: %s, Test: %s (stratify_1=%s stratify_2=%s)",
            len(train_df),
            len(val_df),
            len(test_df),
            use_strat_1,
            use_strat_2,
        )
    except Exception as e:
        logger.error(f"Failed to apply split configuration: {e}")
        return None, None, dataset_id

    timings["split_config"] = time.perf_counter() - t0
    
    # 3. Steps 1-4
    t0 = time.perf_counter()
    logger.info("Step 1: Random 20 lock")
    
    # Get available features (numeric only for simplicity in standalone script)
    numeric_cols = train_df.select_dtypes(include=[np.number]).columns.tolist()
    independent_variables = [c for c in numeric_cols if c != TARGET_VARIABLE and c != ID_COLUMN]
        
    if len(independent_variables) < 20:
        logger.error(f"Fewer than 20 eligible numeric columns ({len(independent_variables)}). Skipping.")
        return None, None, dataset_id
        
    # Random 20
    rng = random.Random(seed)
    candidate_20 = rng.sample(independent_variables, 20)
    logger.info(f"Selected 20 random candidates: {candidate_20}")
    timings["step1_lock"] = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    logger.info("Step 2: Variable Screener")
    # Calculate Correlation and VIF on train scope
    correlations = {}
    for col in candidate_20:
        try:
            corr = train_df[col].corr(train_df[TARGET_VARIABLE])
            correlations[col] = abs(corr) if not pd.isna(corr) else 0
        except Exception:
            correlations[col] = 0
            
    vif_data = calculate_vif(train_df, candidate_20)
    
    # Apply screener logic
    screened_vars = []
    for var in candidate_20:
        corr = correlations.get(var, 0)
        vif = vif_data.get(var, float('inf'))
        
        # Relaxed criteria for standalone script to ensure we get features
        if corr >= 0.01 and vif <= 20:
            screened_vars.append(var)
            
    # Sort by correlation
    screened_vars.sort(key=lambda x: correlations.get(x, 0), reverse=True)
        
    if len(screened_vars) > 20:
        screened_vars = screened_vars[:20]
    elif len(screened_vars) < 20:
        # Backfill
        remaining = [v for v in candidate_20 if v not in screened_vars]
        remaining.sort(key=lambda x: correlations.get(x, 0), reverse=True)
        needed = 20 - len(screened_vars)
        screened_vars.extend(remaining[:needed])
        
    logger.info(f"Screener finalized 20 variables: {screened_vars}")
    timings["step2_screener"] = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    logger.info("Step 3: RFE (Simulated via XGBoost Feature Importances)")
    
    # Train a quick XGBoost model to get feature importances
    X_train = train_df[screened_vars].fillna(0)
    y_train = train_df[TARGET_VARIABLE]
    
    if is_classification:
        # Map labels to 0, 1, ...
        y_train_mapped, unique_classes = pd.factorize(y_train)
        model = xgb.XGBClassifier(n_estimators=50, random_state=seed, use_label_encoder=False, eval_metric='logloss')
        model.fit(X_train, y_train_mapped)
    else:
        model = xgb.XGBRegressor(n_estimators=50, random_state=seed)
        model.fit(X_train, y_train)
        
    importances = model.feature_importances_
    feat_imp = sorted(zip(screened_vars, importances), key=lambda x: x[1], reverse=True)
    rfe_ranked_vars = [f[0] for f in feat_imp]
    
    timings["step3_rfe"] = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    logger.info("Step 4: Finalize")
    # Take top 20 (which is all of them, but ordered by importance)
    final_features = rfe_ranked_vars[:20]
    logger.info(f"Finalized 20 features: {final_features}")
    timings["step4_finalize"] = time.perf_counter() - t0
    
    # 4. Auto Training
    t0 = time.perf_counter()
    logger.info("Step 5: Global Auto Training")
    
    X_train_final = train_df[final_features].fillna(0)
    y_train_final = train_df[TARGET_VARIABLE]
    X_test_final = test_df[final_features].fillna(0)
    y_test_final = test_df[TARGET_VARIABLE]
    
    if is_classification:
        y_train_final, unique_classes = pd.factorize(y_train_final)
        # Map test set using same mapping
        class_map = {val: i for i, val in enumerate(unique_classes)}
        y_test_final = y_test_final.map(class_map).fillna(-1).astype(int)
        
        algorithms = [
            ("XGBoost", xgb.XGBClassifier(n_estimators=100, random_state=seed, eval_metric='logloss')),
            ("LightGBM", lgb.LGBMClassifier(n_estimators=100, random_state=seed)),
            ("CatBoost", CatBoostClassifier(n_estimators=100, random_state=seed, verbose=0)),
            ("RandomForest", RandomForestClassifier(n_estimators=100, random_state=seed)),
            ("LogisticRegression", LogisticRegression(max_iter=1000, random_state=seed)),
            ("GradientBoosting", GradientBoostingClassifier(n_estimators=100, random_state=seed))
        ]
    else:
        algorithms = [
            ("XGBoost", xgb.XGBRegressor(n_estimators=100, random_state=seed)),
            ("LightGBM", lgb.LGBMRegressor(n_estimators=100, random_state=seed)),
            ("CatBoost", CatBoostRegressor(n_estimators=100, random_state=seed, verbose=0)),
            ("RandomForest", RandomForestRegressor(n_estimators=100, random_state=seed)),
            ("LinearRegression", LinearRegression()),
            ("GradientBoosting", GradientBoostingRegressor(n_estimators=100, random_state=seed))
        ]
        
    auto_results = {"results": []}
    
    algo_pbar = tqdm(algorithms, desc="Training Algorithms", leave=False)
    for algo_name, model in algo_pbar:
        algo_pbar.set_description(f"Training {algo_name}")
        logger.info(f"Training {algo_name}...")
        t_algo_start = time.perf_counter()
        
        try:
            model.fit(X_train_final, y_train_final)
            y_pred = model.predict(X_test_final)
            
            metrics = {}
            if is_classification:
                # Filter out -1 (unseen classes in test)
                valid_idx = y_test_final != -1
                y_test_valid = y_test_final[valid_idx]
                y_pred_valid = y_pred[valid_idx]
                
                if len(y_test_valid) > 0:
                    metrics["test_accuracy"] = accuracy_score(y_test_valid, y_pred_valid)
                    metrics["test_f1"] = f1_score(y_test_valid, y_pred_valid, average='weighted')
                    if len(unique_classes) == 2:
                        try:
                            y_pred_proba = model.predict_proba(X_test_final[valid_idx])[:, 1]
                            metrics["test_auc"] = roc_auc_score(y_test_valid, y_pred_proba)
                        except Exception:
                            pass
            else:
                metrics["test_r2"] = r2_score(y_test_final, y_pred)
                metrics["test_rmse"] = np.sqrt(mean_squared_error(y_test_final, y_pred))
                
            training_time = time.perf_counter() - t_algo_start
            
            auto_results["results"].append({
                "algorithm": algo_name,
                "model_id": f"MDL_{algo_name[:3].upper()}_{uuid.uuid4().hex[:6]}",
                "metrics": metrics,
                "training_time_seconds": training_time
            })
            logger.info(f"{algo_name} trained successfully in {training_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to train {algo_name}: {e}")
            auto_results["results"].append({
                "algorithm": algo_name,
                "error": str(e)
            })

    timings["auto_training"] = time.perf_counter() - t0
    
    return timings, auto_results, dataset_id

def cleanup_memory(dataset_id):
    logger.info(f"Cleaning up memory for dataset {dataset_id}")
    gc.collect()

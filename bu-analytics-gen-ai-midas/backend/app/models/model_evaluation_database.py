"""
Model Evaluation Database - Database manager for MEEA (Model Evaluation and Error Analysis) tables
"""

import sqlite3  # kept for sqlite3.Row / OperationalError compatibility
import json
import uuid
import gzip
import base64
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from app.core.config import settings
from app.core.logging_config import get_logger
from app.models._db_backend import BACKEND, connect as _db_connect

logger = get_logger(__name__)


def compress_indices(indices: List[int]) -> Optional[str]:
    """Compress a list of indices using gzip and base64 encoding.
    
    Args:
        indices: List of integer indices
        
    Returns:
        Compressed and base64-encoded string, or None if indices is empty
    """
    if not indices:
        return None
    
    try:
        # Convert to JSON string
        json_str = json.dumps(indices)
        
        # Compress with gzip
        compressed = gzip.compress(json_str.encode('utf-8'), compresslevel=6)
        
        # Encode to base64 for safe storage
        encoded = base64.b64encode(compressed).decode('utf-8')
        
        return encoded
    except Exception as e:
        logger.warning(f"Failed to compress indices: {str(e)}")
        return None


def decompress_indices(compressed_str: str) -> Optional[List[int]]:
    """Decompress a base64-encoded gzip-compressed list of indices.
    
    Args:
        compressed_str: Compressed and base64-encoded string
        
    Returns:
        List of integer indices, or None if decompression fails
    """
    if not compressed_str:
        return None
    
    try:
        # Decode from base64
        compressed = base64.b64decode(compressed_str.encode('utf-8'))
        
        # Decompress with gzip
        json_str = gzip.decompress(compressed).decode('utf-8')
        
        # Parse JSON
        indices = json.loads(json_str)
        
        return indices
    except Exception as e:
        logger.warning(f"Failed to decompress indices: {str(e)}")
        return None


class ModelEvaluationDB:
    """SQLite database manager for Model Evaluation persistence (MEEA integration)"""
    
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path if db_path else settings.DATABASE_PATH)
        self.logger = logger
        self.backend = BACKEND
        self._init_database()

    def connect(self):
        """Open a new DB connection (Postgres adapter or real sqlite3).

        Callers that need raw access (e.g. ``routes.py``) should use this
        instead of ``sqlite3.connect(model_evaluation_db.db_path)`` so they
        transparently get the Postgres adapter when Postgres is configured.
        """
        return _db_connect(self.db_path)
    
    def _init_database(self):
        """Initialize the database and create MEEA tables if they don't exist"""
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                
                # 1. Create models table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS evaluation_models (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        model_type TEXT NOT NULL,
                        task_type TEXT DEFAULT 'classification',
                        training_date TEXT,
                        status TEXT DEFAULT 'completed',
                        color TEXT NOT NULL,
                        description TEXT,
                        dataset_id TEXT,
                        active_scope TEXT DEFAULT 'entire',
                        target_column TEXT,
                        split_params TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Add new columns if they don't exist (for existing databases)
                try:
                    cursor.execute("ALTER TABLE evaluation_models ADD COLUMN dataset_id TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                try:
                    cursor.execute("ALTER TABLE evaluation_models ADD COLUMN active_scope TEXT DEFAULT 'entire'")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                try:
                    cursor.execute("ALTER TABLE evaluation_models ADD COLUMN target_column TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                try:
                    cursor.execute("ALTER TABLE evaluation_models ADD COLUMN split_params TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                try:
                    cursor.execute("ALTER TABLE evaluation_models ADD COLUMN preprocessed_columns TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                try:
                    cursor.execute("ALTER TABLE evaluation_models ADD COLUMN train_indices TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                try:
                    cursor.execute("ALTER TABLE evaluation_models ADD COLUMN test_indices TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                try:
                    cursor.execute("ALTER TABLE evaluation_models ADD COLUMN used_features TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                
                # 2. Create performance_metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS performance_metrics (
                        id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        accuracy REAL,
                        precision REAL,
                        recall REAL,
                        f1_score REAL,
                        auc_roc REAL,
                        auc_pr REAL,
                        log_loss REAL,
                        confusion_matrix TEXT,
                        class_metrics TEXT,
                        -- JSON blob storing all train_*/test_* metrics (to avoid many columns)
                        train_test_metrics TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (model_id) REFERENCES evaluation_models(id) ON DELETE CASCADE
                    )
                """)

                # Add new column for train/test metrics JSON if it doesn't exist (for existing databases)
                try:
                    cursor.execute("ALTER TABLE performance_metrics ADD COLUMN train_test_metrics TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                
                # 3. Create feature_importance table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS feature_importance (
                        id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        feature_name TEXT NOT NULL,
                        shap_importance REAL DEFAULT 0,
                        permutation_importance REAL DEFAULT 0,
                        gain_importance REAL DEFAULT 0,
                        rank INTEGER,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (model_id) REFERENCES evaluation_models(id) ON DELETE CASCADE
                    )
                """)
                
                # 4. Create fairness_metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fairness_metrics (
                        id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        protected_attribute TEXT NOT NULL,
                        group_name TEXT NOT NULL,
                        demographic_parity_ratio REAL,
                        equalized_odds_gap REAL,
                        calibration_score REAL,
                        sample_size INTEGER,
                        pass_threshold INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (model_id) REFERENCES evaluation_models(id) ON DELETE CASCADE
                    )
                """)
                
                # 5. Create explainability_data table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS explainability_data (
                        id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        data_type TEXT NOT NULL,
                        data_source TEXT DEFAULT 'test',
                        feature_name TEXT,
                        data_values TEXT,
                        metadata TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (model_id) REFERENCES evaluation_models(id) ON DELETE CASCADE
                    )
                """)
                
                # Add data_source column if it doesn't exist (for existing databases)
                try:
                    cursor.execute("ALTER TABLE explainability_data ADD COLUMN data_source TEXT DEFAULT 'test'")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                
                # 6. Create model_comparisons table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS model_comparisons (
                        id TEXT PRIMARY KEY,
                        comparison_name TEXT NOT NULL,
                        model_ids TEXT,
                        winner_model_id TEXT,
                        comparison_criteria TEXT,
                        recommendation TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (winner_model_id) REFERENCES evaluation_models(id)
                    )
                """)
                
                # 7. Create granular_accuracy table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS granular_accuracy (
                        id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        variable TEXT NOT NULL,
                        segment TEXT NOT NULL,
                        granularity_level TEXT NOT NULL,
                        accuracy REAL NOT NULL,
                        sample_count INTEGER NOT NULL,
                        precision REAL NOT NULL,
                        recall REAL NOT NULL,
                        f1_score REAL NOT NULL,
                        confusion_matrix TEXT,
                        split_type TEXT DEFAULT 'test',
                        category_value TEXT,
                        grouped_categories TEXT,
                        value_range TEXT,
                        min_value REAL,
                        max_value REAL,
                        is_continuous INTEGER,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (model_id) REFERENCES evaluation_models(id) ON DELETE CASCADE
                    )
                """)
                
                # Add split_type column if it doesn't exist (for existing databases)
                try:
                    cursor.execute("ALTER TABLE granular_accuracy ADD COLUMN split_type TEXT DEFAULT 'test'")
                except sqlite3.OperationalError:
                    # Column already exists, ignore
                    pass
                
                # Add new columns for segment information (for existing databases)
                new_columns = [
                    ('category_value', 'TEXT'),
                    ('grouped_categories', 'TEXT'),
                    ('value_range', 'TEXT'),
                    ('min_value', 'REAL'),
                    ('max_value', 'REAL'),
                    ('is_continuous', 'INTEGER')
                ]
                for col_name, col_type in new_columns:
                    try:
                        cursor.execute(f"ALTER TABLE granular_accuracy ADD COLUMN {col_name} {col_type}")
                    except sqlite3.OperationalError:
                        # Column already exists, ignore
                        pass
                
                # 8. Create error_patterns table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS error_patterns (
                        id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        error_type TEXT NOT NULL,
                        count INTEGER,
                        percentage REAL,
                        avg_confidence REAL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (model_id) REFERENCES evaluation_models(id) ON DELETE CASCADE
                    )
                """)
                
                # 9. Create prediction_confidence table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS prediction_confidence (
                        id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        bin_start REAL,
                        bin_end REAL,
                        count INTEGER,
                        accuracy REAL,
                        avg_confidence REAL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (model_id) REFERENCES evaluation_models(id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_metrics_model_id ON performance_metrics(model_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_feature_imp_model_id ON feature_importance(model_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_fairness_model_id ON fairness_metrics(model_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_explainability_model_id ON explainability_data(model_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_feature_imp_rank ON feature_importance(rank)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_models_status ON evaluation_models(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_granular_acc_model_id ON granular_accuracy(model_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_patterns_model_id ON error_patterns(model_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pred_conf_model_id ON prediction_confidence(model_id)")
                
                conn.commit()
                self.logger.info("Model Evaluation database initialized successfully (MEEA tables)")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize model evaluation database: {str(e)}")
            raise
    
    def save_evaluation_results(self, evaluation_data: Dict[str, Any]) -> bool:
        """Save comprehensive evaluation results to database"""
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                
                # 1. Save model metadata
                model = evaluation_data['model']
                
                # Compress train/test indices if available
                train_indices_compressed = None
                test_indices_compressed = None
                
                if model.get('train_indices'):
                    train_indices_compressed = compress_indices(model['train_indices'])
                if model.get('test_indices'):
                    test_indices_compressed = compress_indices(model['test_indices'])
                
                cursor.execute("""
                    INSERT OR REPLACE INTO evaluation_models 
                    (id, name, model_type, task_type, training_date, status, color, description, 
                     dataset_id, active_scope, target_column, split_params, preprocessed_columns, 
                     train_indices, test_indices, used_features, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    model['id'],
                    model['name'],
                    model['model_type'],
                    model['task_type'],
                    model['training_date'],
                    model['status'],
                    model['color'],
                    model.get('description', ''),
                    model.get('dataset_id'),
                    model.get('active_scope', 'entire'),
                    model.get('target_column'),
                    json.dumps(model.get('split_params', {}), allow_nan=False) if model.get('split_params') else None,
                    json.dumps(model.get('preprocessed_columns', {}), allow_nan=False) if model.get('preprocessed_columns') else None,
                    train_indices_compressed,
                    test_indices_compressed,
                    json.dumps(model.get('used_features', [])) if model.get('used_features') else None,
                    datetime.now().isoformat()
                ))
                
                # 2. Save performance metrics
                perf = evaluation_data['performance_metrics']
                perf_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO performance_metrics 
                    (id, model_id, accuracy, precision, recall, f1_score, auc_roc, auc_pr, 
                     log_loss, confusion_matrix, class_metrics, train_test_metrics, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    perf_id,
                    perf['model_id'],
                    perf.get('accuracy'),
                    perf.get('precision'),
                    perf.get('recall'),
                    perf.get('f1_score'),
                    perf.get('auc_roc'),
                    perf.get('auc_pr'),
                    perf.get('log_loss'),
                    json.dumps(perf.get('confusion_matrix'), allow_nan=False) if perf.get('confusion_matrix') else None,
                    json.dumps(perf.get('class_metrics'), allow_nan=False) if perf.get('class_metrics') else None,
                    json.dumps(perf.get('train_test_metrics'), allow_nan=False) if perf.get('train_test_metrics') is not None else None,
                    datetime.now().isoformat()
                ))
                
                # 3. Save feature importance
                for feature in evaluation_data['feature_importance']:
                    feature_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO feature_importance 
                        (id, model_id, feature_name, shap_importance, permutation_importance, 
                         gain_importance, rank, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        feature_id,
                        feature['model_id'],
                        feature['feature_name'],
                        feature.get('shap_importance', 0),
                        feature.get('permutation_importance', 0),
                        feature.get('gain_importance', 0),
                        feature.get('rank', 0),
                        datetime.now().isoformat()
                    ))
                
                # 4. Save granular accuracy (TEST data - default)
                granular_test_count = len(evaluation_data.get('granular_accuracy', []))
                if granular_test_count > 0:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"💾 Saving {granular_test_count} TEST granular accuracy segments to database for model {evaluation_data.get('model', {}).get('id', 'unknown')}")
                for granular in evaluation_data.get('granular_accuracy', []):
                    granular_id = str(uuid.uuid4())
                    # Convert grouped_categories list to JSON string if present
                    grouped_categories_json = None
                    if granular.get('grouped_categories'):
                        grouped_categories_json = json.dumps(granular['grouped_categories'])
                    
                    cursor.execute("""
                        INSERT INTO granular_accuracy 
                        (id, model_id, variable, segment, granularity_level, accuracy, 
                         sample_count, precision, recall, f1_score, confusion_matrix, split_type,
                         category_value, grouped_categories, value_range, min_value, max_value, is_continuous, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        granular_id,
                        granular['model_id'],
                        granular['variable'],
                        granular['segment'],
                        granular['granularity_level'],
                        granular['accuracy'],
                        granular['sample_count'],
                        granular['precision'],
                        granular['recall'],
                        granular['f1_score'],
                        json.dumps(granular.get('confusion_matrix', []), allow_nan=False),
                        'test',  # Default to 'test' for backward compatibility
                        granular.get('category_value'),
                        grouped_categories_json,
                        granular.get('value_range'),
                        granular.get('min_value'),
                        granular.get('max_value'),
                        1 if granular.get('is_continuous') else 0,
                        datetime.now().isoformat()
                    ))
                
                # 4b. Save granular accuracy (TRAIN data)
                granular_train_count = len(evaluation_data.get('granular_accuracy_train', []))
                if granular_train_count > 0:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"💾 Saving {granular_train_count} TRAIN granular accuracy segments to database for model {evaluation_data.get('model', {}).get('id', 'unknown')}")
                for granular in evaluation_data.get('granular_accuracy_train', []):
                    granular_id = str(uuid.uuid4())
                    # Convert grouped_categories list to JSON string if present
                    grouped_categories_json = None
                    if granular.get('grouped_categories'):
                        grouped_categories_json = json.dumps(granular['grouped_categories'])
                    
                    cursor.execute("""
                        INSERT INTO granular_accuracy 
                        (id, model_id, variable, segment, granularity_level, accuracy, 
                         sample_count, precision, recall, f1_score, confusion_matrix, split_type,
                         category_value, grouped_categories, value_range, min_value, max_value, is_continuous, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        granular_id,
                        granular['model_id'],
                        granular['variable'],
                        granular['segment'],
                        granular['granularity_level'],
                        granular['accuracy'],
                        granular['sample_count'],
                        granular['precision'],
                        granular['recall'],
                        granular['f1_score'],
                        json.dumps(granular.get('confusion_matrix', []), allow_nan=False),
                        'train',
                        granular.get('category_value'),
                        grouped_categories_json,
                        granular.get('value_range'),
                        granular.get('min_value'),
                        granular.get('max_value'),
                        1 if granular.get('is_continuous') else 0,
                        datetime.now().isoformat()
                    ))
                
                # 5. Save error patterns
                for error in evaluation_data.get('error_patterns', []):
                    error_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO error_patterns 
                        (id, model_id, error_type, count, percentage, avg_confidence, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        error_id,
                        error['model_id'],
                        error['error_type'],
                        error['count'],
                        error['percentage'],
                        error.get('avg_confidence'),
                        datetime.now().isoformat()
                    ))
                
                # 6. Save prediction confidence
                for conf in evaluation_data.get('prediction_confidence', []):
                    conf_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO prediction_confidence 
                        (id, model_id, bin_start, bin_end, count, accuracy, avg_confidence, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        conf_id,
                        conf['model_id'],
                        conf['bin_start'],
                        conf['bin_end'],
                        conf['count'],
                        conf['accuracy'],
                        conf['avg_confidence'],
                        datetime.now().isoformat()
                    ))
                
                # 7. Save explainability data
                for explain in evaluation_data.get('explainability_data', []):
                    explain_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO explainability_data 
                        (id, model_id, data_type, data_source, feature_name, data_values, metadata, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        explain_id,
                        explain['model_id'],
                        explain['data_type'],
                        explain.get('data_source', 'test'),  # Default to 'test' for backward compatibility
                        explain.get('feature_name'),
                        json.dumps(explain['values'], allow_nan=False),
                        json.dumps(explain.get('metadata', {}), allow_nan=False),
                        datetime.now().isoformat()
                    ))
                
                conn.commit()
                self.logger.info(f"Evaluation results saved successfully for model: {model['id']}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to save evaluation results: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def get_model_evaluation(self, model_id: str, include_explainability: bool = True, include_pdp: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive evaluation data for a model
        
        Args:
            model_id: Model identifier
            include_explainability: If False, skips fetching explainability data to speed up initial load (default: True)
            include_pdp: If False, skips fetching PDP data for faster initial load (default: True, only used if include_explainability=True)
        """
        try:
            with self.connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get model metadata
                cursor.execute("SELECT * FROM evaluation_models WHERE id = ?", (model_id,))
                model_row = cursor.fetchone()
                
                if not model_row:
                    self.logger.warning(f"No evaluation data found for model: {model_id}")
                    return None
                
                model_data = dict(model_row)
                
                # Parse JSON fields in model_data
                if model_data.get('split_params'):
                    try:
                        model_data['split_params'] = json.loads(model_data['split_params'])
                    except (json.JSONDecodeError, TypeError):
                        model_data['split_params'] = {}
                if model_data.get('preprocessed_columns'):
                    try:
                        model_data['preprocessed_columns'] = json.loads(model_data['preprocessed_columns'])
                    except (json.JSONDecodeError, TypeError):
                        model_data['preprocessed_columns'] = {}
                else:
                    model_data['preprocessed_columns'] = {}
                
                # Decompress train/test indices if available
                if model_data.get('train_indices'):
                    model_data['train_indices'] = decompress_indices(model_data['train_indices'])
                if model_data.get('test_indices'):
                    model_data['test_indices'] = decompress_indices(model_data['test_indices'])
                
                # Parse used_features JSON if available
                if model_data.get('used_features'):
                    try:
                        model_data['used_features'] = json.loads(model_data['used_features'])
                    except (json.JSONDecodeError, TypeError):
                        model_data['used_features'] = []
                else:
                    model_data['used_features'] = []
                
                # Get performance metrics
                cursor.execute("SELECT * FROM performance_metrics WHERE model_id = ?", (model_id,))
                perf_row = cursor.fetchone()
                performance_metrics = dict(perf_row) if perf_row else {}
                
                # Parse JSON fields
                if performance_metrics.get('confusion_matrix'):
                    performance_metrics['confusion_matrix'] = json.loads(performance_metrics['confusion_matrix'])
                if performance_metrics.get('class_metrics'):
                    performance_metrics['class_metrics'] = json.loads(performance_metrics['class_metrics'])
                # NEW: expand train/test metrics JSON blob into top-level keys
                monotonicity_results = None
                if performance_metrics.get('train_test_metrics'):
                    try:
                        extra_metrics = json.loads(performance_metrics['train_test_metrics'])
                        if isinstance(extra_metrics, dict):
                            # Extract monotonicity_results before updating (preserve reference)
                            monotonicity_results = extra_metrics.get('monotonicity_results')
                            # Update performance_metrics with all extra metrics
                            performance_metrics.update(extra_metrics)
                            # Ensure monotonicity_results is available in performance_metrics after update
                            if monotonicity_results:
                                performance_metrics['monotonicity_results'] = monotonicity_results
                            self.logger.debug(f"Successfully parsed train_test_metrics for model {model_id}, monotonicity_results present: {monotonicity_results is not None}")
                    except Exception as e:
                        self.logger.warning(f"Failed to parse train_test_metrics for model {model_id}: {e}")
                        import traceback
                        self.logger.debug(f"Traceback: {traceback.format_exc()}")
                
                # Fallback: try to get monotonicity_results from performance_metrics if not already extracted
                if monotonicity_results is None:
                    monotonicity_results = performance_metrics.get('monotonicity_results')
                
                # Get feature importance
                cursor.execute("SELECT * FROM feature_importance WHERE model_id = ? ORDER BY rank", (model_id,))
                feature_rows = cursor.fetchall()
                feature_importance = [dict(row) for row in feature_rows]
                
                # Get granular accuracy (separate train and test)
                cursor.execute("SELECT * FROM granular_accuracy WHERE model_id = ?", (model_id,))
                granular_rows = cursor.fetchall()
                granular_accuracy = []
                granular_accuracy_train = []
                
                for row in granular_rows:
                    granular = dict(row)
                    # Parse confusion matrix
                    if granular.get('confusion_matrix'):
                        granular['confusion_matrix'] = json.loads(granular['confusion_matrix'])
                    
                    # Parse grouped_categories JSON string if present
                    if granular.get('grouped_categories'):
                        try:
                            granular['grouped_categories'] = json.loads(granular['grouped_categories'])
                        except (json.JSONDecodeError, TypeError):
                            granular['grouped_categories'] = None
                    
                    # Convert is_continuous from integer to boolean
                    if granular.get('is_continuous') is not None:
                        granular['is_continuous'] = bool(granular['is_continuous'])
                    
                    # Separate by split_type
                    split_type = granular.get('split_type', 'test')  # Default to 'test' for backward compatibility
                    if split_type == 'train':
                        granular_accuracy_train.append(granular)
                    else:
                        granular_accuracy.append(granular)
                
                # Get error patterns
                cursor.execute("SELECT * FROM error_patterns WHERE model_id = ?", (model_id,))
                error_rows = cursor.fetchall()
                error_patterns = [dict(row) for row in error_rows]
                
                # Get prediction confidence
                cursor.execute("SELECT * FROM prediction_confidence WHERE model_id = ?", (model_id,))
                conf_rows = cursor.fetchall()
                prediction_confidence = [dict(row) for row in conf_rows]
                
                # Get explainability data (only if requested - skip for faster initial load)
                explainability_data = []
                if include_explainability:
                    self.logger.debug(f"Fetching explainability data for model: {model_id} (include_pdp={include_pdp})")
                    
                    # Build query based on include_pdp parameter to optimize initial load
                    if include_pdp:
                        # Fetch all explainability data including PDP
                        cursor.execute("SELECT * FROM explainability_data WHERE model_id = ?", (model_id,))
                    else:
                        # OPTIMIZATION: Exclude PDP data for faster initial load (lazy load PDP later)
                        cursor.execute("""
                            SELECT * FROM explainability_data 
                            WHERE model_id = ? AND data_type != 'pdp'
                        """, (model_id,))
                    
                    explain_rows = cursor.fetchall()
                    explainability_data = [dict(row) for row in explain_rows]
                    
                    # Parse JSON values and ensure data_source is properly set
                    for explain in explainability_data:
                        if explain.get('data_values'):
                            explain['values'] = json.loads(explain['data_values'])
                        if explain.get('metadata'):
                            explain['metadata'] = json.loads(explain['metadata'])
                        
                        # Ensure data_source is a string (handle None/null)
                        raw_data_source = explain.get('data_source')
                        if raw_data_source is None or raw_data_source == '':
                            explain['data_source'] = 'test'  # Default for backward compatibility
                        else:
                            # Convert to string and strip whitespace
                            explain['data_source'] = str(raw_data_source).strip()
                        
                        # Debug logging for data_source values
                        self.logger.debug(f"Retrieved explainability entry: data_type={explain.get('data_type')}, data_source={explain.get('data_source')}, feature_name={explain.get('feature_name')}")
                else:
                    self.logger.debug(f"Skipping explainability data fetch for model: {model_id} (include_explainability=False)")
                
                # Prefer used_features from database, fall back to JSON file for backward compatibility
                used_features: List[str] = model_data.get('used_features', []) or []
                if not used_features:
                    # Fallback: Load from training results file if not in database
                    try:
                        models_dir = Path("models")
                        training_results_path = models_dir / f"{model_id}_training_results.json"
                        if training_results_path.exists():
                            with open(training_results_path, 'r') as f:
                                training_results = json.load(f)
                                used_features = training_results.get('used_features', []) or []
                    except Exception as e:
                        self.logger.warning(f"Failed to load used features from JSON for model {model_id}: {str(e)}")
                        used_features = []
                
                # Load column_stats from training results file if available (not stored in DB yet)
                column_stats: Dict[str, Any] = {}
                try:
                    models_dir = Path("models")
                    training_results_path = models_dir / f"{model_id}_training_results.json"
                    if training_results_path.exists():
                        with open(training_results_path, 'r') as f:
                            training_results = json.load(f)
                            column_stats = training_results.get('column_stats', {}) or {}
                except Exception as e:
                    self.logger.debug(f"Failed to load column_stats for model {model_id}: {str(e)}")
                    column_stats = {}
                
                # Build response with convenience fields
                # CRITICAL: Ensure granular_accuracy_train is always a list (never None) for frontend compatibility
                if granular_accuracy_train is None:
                    granular_accuracy_train = []
                
                # monotonicity_results should already be extracted above, but ensure it's set
                if monotonicity_results is None:
                    monotonicity_results = performance_metrics.get('monotonicity_results')
                
                # Log monotonicity_results availability for debugging
                if monotonicity_results:
                    self.logger.debug(f"✅ Monotonicity results found for model {model_id}: deciles={len(monotonicity_results.get('deciles', []))}, violations={len(monotonicity_results.get('monotonicity_violations', []))}")
                else:
                    self.logger.debug(f"⚠️ No monotonicity results found for model {model_id}")
                
                response = {
                    'model': model_data,
                    'performance_metrics': performance_metrics,
                    'feature_importance': feature_importance,
                    'granular_accuracy': granular_accuracy,  # Test data (default)
                    'granular_accuracy_train': granular_accuracy_train,  # Train data (always a list)
                    'error_patterns': error_patterns,
                    'prediction_confidence': prediction_confidence,
                    'explainability_data': explainability_data,
                    'used_features': used_features,
                    'column_stats': column_stats,
                    'monotonicity_results': monotonicity_results,
                    # Convenience field: map task_type to problem_type for frontend compatibility
                    'problem_type': model_data.get('task_type', 'unknown')
                }
                
                # Log granular accuracy counts for debugging
                self.logger.debug(f"📊 Retrieved granular accuracy for model {model_id}: TEST={len(granular_accuracy)} segments, TRAIN={len(granular_accuracy_train)} segments")
                
                return response
                
        except Exception as e:
            self.logger.error(f"Failed to get evaluation data for model {model_id}: {str(e)}")
            return None
    
    def list_all_models(self) -> List[Dict[str, Any]]:
        """List all evaluated models"""
        try:
            with self.connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM evaluation_models 
                    ORDER BY created_at DESC
                """)
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            self.logger.error(f"Failed to list models: {str(e)}")
            return []
    
    def list_models_by_dataset(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        List all evaluated models for a specific dataset_id.
        
        This is used by Model Lab → MEEA integration so that the Explainability
        tab only shows models trained on the currently active dataset.
        Includes both:
        - Global models: evaluation_models.dataset_id == dataset_id
        - Segment models: evaluation_models.dataset_id LIKE f"{dataset_id}_segment_%"
        """
        try:
            with self.connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Fetch both global and segment models for this dataset.
                like_pattern = f"{dataset_id}_segment_%"
                cursor.execute("""
                    SELECT * FROM evaluation_models
                    WHERE dataset_id = ?
                       OR dataset_id LIKE ?
                    ORDER BY created_at DESC
                """, (dataset_id, like_pattern))
                
                rows = cursor.fetchall()
                models: List[Dict[str, Any]] = []
                for row in rows:
                    data = dict(row)
                    ds_id = data.get("dataset_id") or ""
                    # Mark whether this is a per-segment model
                    if ds_id == dataset_id:
                        data["is_segment_model"] = False
                    elif ds_id.startswith(f"{dataset_id}_segment_"):
                        data["is_segment_model"] = True
                        # Extract the segment identifier for UI convenience
                        try:
                            data["segment_id"] = ds_id.split("_segment_", 1)[1]
                        except Exception:
                            data["segment_id"] = None
                    else:
                        # Should not happen given the WHERE clause, but keep behavior safe
                        data["is_segment_model"] = False
                    models.append(data)
                
                return models
        
        except Exception as e:
            self.logger.error(f"Failed to list models for dataset_id {dataset_id}: {str(e)}")
            return []
    
    def delete_model_evaluation(self, model_id: str) -> bool:
        """Delete all evaluation data for a model"""
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                
                # Delete model (CASCADE will delete related data)
                cursor.execute("DELETE FROM evaluation_models WHERE id = ?", (model_id,))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    self.logger.info(f"Evaluation data deleted successfully for model: {model_id}")
                    return True
                else:
                    self.logger.warning(f"No evaluation data found to delete for model: {model_id}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Failed to delete evaluation data for model {model_id}: {str(e)}")
            return False
    
    def get_model_comparison(self, model_ids: List[str]) -> Dict[str, Any]:
        """Get comparison data for multiple models"""
        try:
            comparison_data = []
            
            for model_id in model_ids:
                eval_data = self.get_model_evaluation(model_id)
                if eval_data:
                    comparison_data.append(eval_data)
            
            return {
                'models': comparison_data,
                'comparison_count': len(comparison_data)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get model comparison: {str(e)}")
            return {'models': [], 'comparison_count': 0}


# Global database instance
model_evaluation_db = ModelEvaluationDB()


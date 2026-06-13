"""MessageState persistence with a Postgres-preferred, SQLite-fallback backend.

At import time a single health check is performed against Postgres. If the
probe succeeds, every operation uses Postgres (``_PostgresMessageStateDB``).
If the probe fails (no ``DATABASE_URL``, driver missing, connect error, or
write failure) the module falls back to SQLite (``_SqliteMessageStateDB``),
which preserves the original behaviour.

The public surface (``MessageStateDB`` + the module-level ``message_state_db``
singleton with methods ``save_message_state``, ``load_message_state``,
``delete_message_state``, ``list_all_states``, ``cleanup_old_states``) is
unchanged, so callers do not need to change.
"""

from __future__ import annotations

import json
import pickle
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _safe_json_serializable(obj):
    """Convert numpy/pandas types to JSON-serializable Python types."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _safe_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json_serializable(item) for item in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if isinstance(obj, pd.DataFrame):
        return None
    if isinstance(obj, pd.Series):
        return obj.tolist()
    if hasattr(obj, 'item'):
        return obj.item()
    return obj


# =========================================================================
# SQLite backend (original implementation, unchanged behaviour)
# =========================================================================
class _SqliteMessageStateDB:
    """SQLite-backed ``MessageState`` store (fallback path)."""

    backend = "sqlite"

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path if db_path else settings.DATABASE_PATH)
        self.logger = logger
        self._init_database()

    def _init_database(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS message_states (
                        dataset_id TEXT PRIMARY KEY,
                        userquery TEXT,
                        plan TEXT,
                        generated_code TEXT,
                        summary TEXT,
                        intent TEXT,
                        plan_exist TEXT,
                        approved BOOLEAN DEFAULT FALSE,
                        notes TEXT,
                        dataset_filename TEXT,
                        chat_history TEXT,
                        messages TEXT,
                        project_desc_file TEXT,
                        data_desc TEXT,
                        dataset_file_data TEXT,
                        previous_dataset_file_data TEXT,
                        modelling_artifacts TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_dataset_id ON message_states(dataset_id)"
                )
                try:
                    cursor.execute("SELECT modelling_artifacts FROM message_states LIMIT 1")
                except sqlite3.OperationalError:
                    self.logger.info("Adding modelling_artifacts column to existing message_states table")
                    cursor.execute("ALTER TABLE message_states ADD COLUMN modelling_artifacts TEXT")
                try:
                    cursor.execute("SELECT previous_dataset_file_data FROM message_states LIMIT 1")
                except sqlite3.OperationalError:
                    self.logger.info("Adding previous_dataset_file_data column to existing message_states table")
                    cursor.execute("ALTER TABLE message_states ADD COLUMN previous_dataset_file_data TEXT")
                conn.commit()
                self.logger.info("MessageState SQLite database initialized at %s", self.db_path)
        except Exception as e:
            self.logger.error("Failed to initialize SQLite database: %s", e)
            raise

    @staticmethod
    def _serialize_dataframes(state: Dict[str, Any], log):
        MAX_BYTES = 50 * 1024 * 1024  # 50 MiB
        dataset_file_data: Optional[bytes] = None
        if 'datasetFile' in state and isinstance(state['datasetFile'], pd.DataFrame):
            df_save = state['datasetFile']
            try:
                mem_bytes = int(df_save.memory_usage(deep=True).sum())
                if mem_bytes >= MAX_BYTES:
                    log.info(
                        "Skipping DataFrame DB snapshot (~%s bytes >= %s cap), shape=%s",
                        mem_bytes, MAX_BYTES, df_save.shape,
                    )
                else:
                    pickled = pickle.dumps(df_save)
                    if len(pickled) < MAX_BYTES:
                        dataset_file_data = pickled
                        log.info("DataFrame pickled for DB: %s bytes, shape: %s", len(pickled), df_save.shape)
                    else:
                        log.info("Skipping DataFrame DB snapshot (pickled %s bytes >= cap)", len(pickled))
            except Exception as e:
                log.warning("Could not pickle DataFrame: %s", e)

        previous_dataset_file_data: Optional[bytes] = None
        if 'previousDatasetFile' in state and isinstance(state['previousDatasetFile'], pd.DataFrame):
            try:
                pickled = pickle.dumps(state['previousDatasetFile'])
                if len(pickled) < MAX_BYTES:
                    previous_dataset_file_data = pickled
                    log.info(
                        "Previous DataFrame pickled: %s bytes, shape: %s",
                        len(pickled), state['previousDatasetFile'].shape,
                    )
                else:
                    log.warning("Previous DataFrame too large (%s bytes); skipping DB snapshot", len(pickled))
            except Exception as e:
                log.warning("Could not pickle previous DataFrame: %s", e)

        return dataset_file_data, previous_dataset_file_data

    @staticmethod
    def _extract_modelling(state: Dict[str, Any], log=None) -> Optional[str]:
        if log is None:
            log = logger
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
            # QC pipeline fields
            "qc_mode", "treatment_sequence", "current_treatment_index",
            "completed_treatments", "skipped_treatments", "treatment_statuses",
            "quality_detections", "quality_plans", "qc_metrics", "qc_sequence_complete",
            "qc_templates", "qc_ui_selections"  # Uploaded templates and user selections
        ]
        modelling_artifacts = {k: state[k] for k in modelling_keys if k in state and state[k] is not None}
        
        modelling_artifacts_json = None
        if modelling_artifacts:
            try:
                modelling_artifacts_json = json.dumps(_safe_json_serializable(modelling_artifacts))
            except Exception as e:
                log.warning(f"Failed to serialize modelling_artifacts: {e}, saving QC fields only")
                qc_only_keys = [
                    "qc_mode", "treatment_sequence", "current_treatment_index",
                    "completed_treatments", "skipped_treatments", "treatment_statuses",
                    "qc_sequence_complete", "qc_ui_selections"
                ]
                qc_only = {k: modelling_artifacts[k] for k in qc_only_keys if k in modelling_artifacts}
                try:
                    modelling_artifacts_json = json.dumps(_safe_json_serializable(qc_only)) if qc_only else None
                except Exception as e2:
                    log.error(f"Failed to serialize even QC-only fields: {e2}")
        return modelling_artifacts_json

    def save_message_state(self, dataset_id: str, state: Dict[str, Any]) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                notes_json = json.dumps(state.get('notes', []))
                chat_history_json = json.dumps(state.get('chat_history', []))
                messages_json = json.dumps([
                    {'type': type(msg).__name__, 'content': msg.content if hasattr(msg, 'content') else str(msg)}
                    for msg in state.get('messages', [])
                ])
                dataset_file_data, previous_dataset_file_data = self._serialize_dataframes(state, self.logger)
                modelling_artifacts_json = self._extract_modelling(state, self.logger)

                cursor.execute("""
                    INSERT OR REPLACE INTO message_states (
                        userquery, plan, generated_code, summary, intent, plan_exist,
                        approved, notes, dataset_filename, chat_history, messages,
                        project_desc_file, data_desc, dataset_file_data, previous_dataset_file_data, modelling_artifacts,
                        updated_at, dataset_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    state.get('userquery', ''), state.get('plan', ''), state.get('generatedCode', ''),
                    state.get('summary', ''), state.get('intent', ''), state.get('planExist', ''),
                    state.get('approved', False), notes_json, state.get('datasetFileName', ''),
                    chat_history_json, messages_json, state.get('projectDescFile', ''),
                    state.get('dataDesc', ''), dataset_file_data, previous_dataset_file_data,
                    modelling_artifacts_json, datetime.now().isoformat(), dataset_id,
                ))
                conn.commit()
                self.logger.info("MessageState[sqlite] saved for dataset: %s", dataset_id)
                return True
        except Exception as e:
            self.logger.error("Failed to save MessageState[sqlite] for %s: %s", dataset_id, e)
            return False

    def load_message_state(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM message_states WHERE dataset_id = ?", (dataset_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return _row_to_state(dict(row), self.logger)
        except Exception as e:
            self.logger.error("Failed to load MessageState[sqlite] for %s: %s", dataset_id, e)
            return None

    def delete_message_state(self, dataset_id: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM message_states WHERE dataset_id = ?", (dataset_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error("Failed to delete MessageState[sqlite] for %s: %s", dataset_id, e)
            return False

    def list_all_states(self) -> List[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT dataset_id, dataset_filename, intent, created_at, updated_at
                    FROM message_states ORDER BY updated_at DESC
                """)
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            self.logger.error("Failed to list MessageStates[sqlite]: %s", e)
            return []

    def cleanup_old_states(self, days_old: int = 30) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"DELETE FROM message_states WHERE created_at < datetime('now', '-{int(days_old)} days')"
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            self.logger.error("Failed to cleanup old MessageStates[sqlite]: %s", e)
            return 0


# =========================================================================
# Postgres backend
# =========================================================================
class _PostgresMessageStateDB:
    """Postgres-backed ``MessageState`` store.

    Uses ``psycopg2`` with ``DATABASE_URL``. Same public surface as the SQLite
    version. DataFrame pickles are stored as ``BYTEA`` so the size cap behaviour
    matches the SQLite implementation.
    """

    backend = "postgres"

    def __init__(self, database_url: str):
        import psycopg2  # noqa: F401  - imported here so missing driver is caught by health check

        self._database_url = database_url
        self.logger = logger
        # Kept for API compatibility with routes that reference ``.db_path``;
        # callers should not use this on the Postgres backend for raw sqlite3 access.
        self.db_path = Path(settings.DATABASE_PATH)
        self._init_database()

    def _connect(self):
        import psycopg2
        return psycopg2.connect(self._database_url, connect_timeout=5)

    def _init_database(self):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS message_states (
                        dataset_id TEXT PRIMARY KEY,
                        userquery TEXT,
                        plan TEXT,
                        generated_code TEXT,
                        summary TEXT,
                        intent TEXT,
                        plan_exist TEXT,
                        approved BOOLEAN DEFAULT FALSE,
                        notes TEXT,
                        dataset_filename TEXT,
                        chat_history TEXT,
                        messages TEXT,
                        project_desc_file TEXT,
                        data_desc TEXT,
                        dataset_file_data BYTEA,
                        previous_dataset_file_data BYTEA,
                        modelling_artifacts TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_dataset_id ON message_states(dataset_id)"
                )
            conn.commit()
        self.logger.info("MessageState Postgres table initialized")

    def save_message_state(self, dataset_id: str, state: Dict[str, Any]) -> bool:
        import psycopg2
        try:
            notes_json = json.dumps(state.get('notes', []))
            chat_history_json = json.dumps(state.get('chat_history', []))
            messages_json = json.dumps([
                {'type': type(msg).__name__, 'content': msg.content if hasattr(msg, 'content') else str(msg)}
                for msg in state.get('messages', [])
            ])
            dataset_file_data, previous_dataset_file_data = _SqliteMessageStateDB._serialize_dataframes(
                state, self.logger
            )
            modelling_artifacts_json = _SqliteMessageStateDB._extract_modelling(state, self.logger)

            # ``psycopg2`` needs bytes wrapped as ``Binary`` for BYTEA parameters.
            bin_dataset = psycopg2.Binary(dataset_file_data) if dataset_file_data is not None else None
            bin_prev = (
                psycopg2.Binary(previous_dataset_file_data)
                if previous_dataset_file_data is not None else None
            )

            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO message_states (
                            dataset_id, userquery, plan, generated_code, summary, intent, plan_exist,
                            approved, notes, dataset_filename, chat_history, messages,
                            project_desc_file, data_desc, dataset_file_data,
                            previous_dataset_file_data, modelling_artifacts, updated_at
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                        ON CONFLICT (dataset_id) DO UPDATE SET
                            userquery = EXCLUDED.userquery,
                            plan = EXCLUDED.plan,
                            generated_code = EXCLUDED.generated_code,
                            summary = EXCLUDED.summary,
                            intent = EXCLUDED.intent,
                            plan_exist = EXCLUDED.plan_exist,
                            approved = EXCLUDED.approved,
                            notes = EXCLUDED.notes,
                            dataset_filename = EXCLUDED.dataset_filename,
                            chat_history = EXCLUDED.chat_history,
                            messages = EXCLUDED.messages,
                            project_desc_file = EXCLUDED.project_desc_file,
                            data_desc = EXCLUDED.data_desc,
                            dataset_file_data = EXCLUDED.dataset_file_data,
                            previous_dataset_file_data = EXCLUDED.previous_dataset_file_data,
                            modelling_artifacts = EXCLUDED.modelling_artifacts,
                            updated_at = NOW()
                    """, (
                        dataset_id, state.get('userquery', ''), state.get('plan', ''),
                        state.get('generatedCode', ''), state.get('summary', ''),
                        state.get('intent', ''), state.get('planExist', ''),
                        bool(state.get('approved', False)), notes_json,
                        state.get('datasetFileName', ''), chat_history_json, messages_json,
                        state.get('projectDescFile', ''), state.get('dataDesc', ''),
                        bin_dataset, bin_prev, modelling_artifacts_json,
                    ))
                conn.commit()
            self.logger.info("MessageState[postgres] saved for dataset: %s", dataset_id)
            return True
        except Exception as e:
            self.logger.error("Failed to save MessageState[postgres] for %s: %s", dataset_id, e)
            return False

    def load_message_state(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM message_states WHERE dataset_id = %s", (dataset_id,))
                    row = cur.fetchone()
                    if not row:
                        return None
                    cols = [c[0] for c in cur.description]
                    data = dict(zip(cols, row))
            # BYTEA comes back as memoryview / bytes; normalize for pickle
            for k in ('dataset_file_data', 'previous_dataset_file_data'):
                v = data.get(k)
                if isinstance(v, memoryview):
                    data[k] = bytes(v)
            return _row_to_state(data, self.logger)
        except Exception as e:
            self.logger.error("Failed to load MessageState[postgres] for %s: %s", dataset_id, e)
            return None

    def delete_message_state(self, dataset_id: str) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM message_states WHERE dataset_id = %s", (dataset_id,))
                    deleted = cur.rowcount
                conn.commit()
            return deleted > 0
        except Exception as e:
            self.logger.error("Failed to delete MessageState[postgres] for %s: %s", dataset_id, e)
            return False

    def list_all_states(self) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT dataset_id, dataset_filename, intent, created_at, updated_at
                        FROM message_states ORDER BY updated_at DESC
                    """)
                    rows = cur.fetchall()
                    cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in rows]
        except Exception as e:
            self.logger.error("Failed to list MessageStates[postgres]: %s", e)
            return []

    def cleanup_old_states(self, days_old: int = 30) -> int:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM message_states WHERE created_at < NOW() - make_interval(days => %s)",
                        (int(days_old),),
                    )
                    deleted = cur.rowcount
                conn.commit()
            return deleted
        except Exception as e:
            self.logger.error("Failed to cleanup old MessageStates[postgres]: %s", e)
            return 0


# =========================================================================
# Shared row → state deserializer (identical semantics for both backends)
# =========================================================================
def _row_to_state(row: Dict[str, Any], log) -> Dict[str, Any]:
    def _get(k):
        return row.get(k)

    state: Dict[str, Any] = {
        'userquery': _get('userquery'),
        'plan': _get('plan'),
        'generatedCode': _get('generated_code'),
        'summary': _get('summary'),
        'intent': _get('intent'),
        'planExist': _get('plan_exist'),
        'approved': bool(_get('approved')) if _get('approved') is not None else False,
        'notes': json.loads(_get('notes')) if _get('notes') else [],
        'datasetFileName': _get('dataset_filename'),
        'chat_history': json.loads(_get('chat_history')) if _get('chat_history') else [],
        'messages': [],
        'projectDescFile': _get('project_desc_file'),
        'dataDesc': _get('data_desc'),
    }
    if _get('messages'):
        try:
            state['messages'] = json.loads(_get('messages'))
        except json.JSONDecodeError:
            state['messages'] = []
    if _get('dataset_file_data'):
        try:
            state['datasetFile'] = pickle.loads(_get('dataset_file_data'))
        except Exception as e:
            log.warning("Could not unpickle DataFrame: %s", e)
    if _get('previous_dataset_file_data'):
        try:
            state['previousDatasetFile'] = pickle.loads(_get('previous_dataset_file_data'))
        except Exception as e:
            log.warning("Could not unpickle previous DataFrame: %s", e)
    try:
        if _get('modelling_artifacts'):
            modelling = json.loads(_get('modelling_artifacts'))
            state.update(modelling)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        log.warning("Could not deserialize modelling artifacts: %s", e)
    return state


# =========================================================================
# Facade: Postgres-first with SQLite fallback (picked once, at init)
# =========================================================================
class MessageStateDB:
    """Public facade. Picks Postgres when healthy, otherwise SQLite.

    The Postgres probe is run once in ``app.models._db_backend`` at import
    time; this facade reuses that decision so we do not double-probe.
    """

    def __init__(self, db_path: Optional[str] = None):
        # Imported here (rather than at module top) to avoid moving the
        # health check before the ``_SqliteMessageStateDB`` class definition.
        from app.models._db_backend import BACKEND, _DATABASE_URL

        self._impl: Any
        if BACKEND == "postgres" and _DATABASE_URL:
            try:
                self._impl = _PostgresMessageStateDB(_DATABASE_URL)
                logger.info("MessageStateDB using backend=postgres")
            except Exception as e:
                logger.warning("Postgres backend init failed (%s); falling back to SQLite", e)
                self._impl = _SqliteMessageStateDB(db_path)
        else:
            if _DATABASE_URL:
                logger.warning("Postgres not usable; falling back to SQLite at %s", settings.DATABASE_PATH)
            else:
                logger.info("No DATABASE_URL configured; using SQLite at %s", settings.DATABASE_PATH)
            self._impl = _SqliteMessageStateDB(db_path)

    @property
    def backend(self) -> str:
        return getattr(self._impl, "backend", "sqlite")

    @property
    def db_path(self) -> Path:
        return self._impl.db_path

    def save_message_state(self, dataset_id: str, state: Dict[str, Any]) -> bool:
        return self._impl.save_message_state(dataset_id, state)

    def load_message_state(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        return self._impl.load_message_state(dataset_id)

    def delete_message_state(self, dataset_id: str) -> bool:
        return self._impl.delete_message_state(dataset_id)

    def list_all_states(self) -> List[Dict[str, Any]]:
        return self._impl.list_all_states()

    def cleanup_old_states(self, days_old: int = 30) -> int:
        return self._impl.cleanup_old_states(days_old)


message_state_db = MessageStateDB()

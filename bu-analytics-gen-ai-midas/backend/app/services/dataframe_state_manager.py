"""
DataFrame State Manager
This module provides a singleton class to manage processed DataFrames across the application.
It ensures that processed DataFrames are maintained in memory and accessible to all components
that need them, while providing clean APIs for state management.
"""

import re

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from typing import Dict, Optional, Tuple, Any

import json as _json
import os as _os
import time as _time
import threading as _threading
from app.core.logging_config import get_logger
from app.services import split_state_store as _split_state_store
import app.utils.helpers as _helpers
import gc

# Path to the persisted split configs file (same directory as training_jobs_state.json)
_SPLIT_CONFIG_FILE = _os.path.join(_os.path.dirname(__file__), "..", "..", "split_configs_state.json")

# Base directory for "previous DataFrame" snapshots written to disk so we don't
# duplicate the full DataFrame in RAM on every update (P1.5). Kept alongside
# the existing uploads directory so cleanup follows the dataset lifecycle.
_PREV_SNAPSHOT_DIR_BASE = _os.path.abspath(
    _os.path.join(_os.path.dirname(__file__), "..", "..", "uploads")
)


def _prev_snapshot_dir(dataset_id: str) -> str:
    return _os.path.join(_PREV_SNAPSHOT_DIR_BASE, dataset_id, "snapshots")

def _load_persisted_split_config(dataset_id: str) -> dict:
    """
    Load the persisted split config for a dataset from disk.
    Returns a dict with keys: ratio, seed, sampling_variable, scope - or {} if not found.
    This is used to rehydrate the correct split parameters after an Azure process restart
    so that set_scope recreates the *same* split the user configured in Step 1.
    """
    try:
        if not _os.path.exists(_SPLIT_CONFIG_FILE):
            return {}
        with open(_SPLIT_CONFIG_FILE, "r", encoding="utf-8") as _fh:
            configs = _json.load(_fh)
        return configs.get(dataset_id, {})
    except Exception:
        return {}


class DataFrameStateManager:
    """
    Singleton class to manage processed DataFrame states across the application.
    This class maintains a cache of processed DataFrames and provides methods to:
    - Store processed DataFrames after code execution
    - Retrieve the latest processed DataFrame for a dataset
    - Get the appropriate DataFrame for plan generation
    - Clean up old entries to manage memory

    Design intent:
      - "entire" is the master dataset that contains all transformations
      - "train", "test", "validation" are filtered views (row subsets) derived from the master
    """

    _instance = None
    # _processed_dataframes: Dict[str, pd.DataFrame] = {}
    # _dataset_metadata: Dict[str, Dict] = {}  # Store metadata like original shape, last_updated
    # _full_dataframes: Dict[str, pd.DataFrame] = {}
    # _split_indices: Dict[str, Dict[str, np.ndarray]] = {}  # {dataset_id: {"train": idx, "test": idx, "validation": idx}}
    # _active_scope: Dict[str, str] = {}  # {dataset_id: 'train'/'test'/'validation'/'entire'}
    # _split_copies: Dict[str, Dict[str, pd.DataFrame]] = {}  # (kept for backward compatibility)
    # _transformed_copies: Dict[str, Dict[str, pd.DataFrame]] = {}  # {dataset_id: {"train": df, "test": df, "validation": df, "entire": df}}
    
    # P1.5: previous-dataframe snapshots are now stored on disk as Parquet, not
    # held in RAM as a full DataFrame copy. _previous_dataframes is retained
    # only as a fallback when the Parquet write fails (so semantics are
    # preserved bit-for-bit when storage is healthy or unhealthy).
    # _previous_dataframes: Dict[str, pd.DataFrame] = {}
    # _previous_snapshot_paths: Dict[str, str] = {}  # {dataset_id: path/to/prev_<ts>.parquet}
    _previous_snapshot_lock: _threading.Lock = _threading.Lock()

    # P2.3: monotonic per-dataset version counter. Bumped on every
    # update_dataframe so the analytics result cache (column-info, DQS,
    # etc.) treats the prior keys as unreachable and recomputes on the
    # next read. Reads use get_version(dataset_id) -> current int.
    _version_counters: Dict[str, int] = {}
    _version_lock: _threading.Lock = _threading.Lock()

    def _initialize(self):
        #Initialize attributes
        self._processed_dataframes: Dict[str, pd.DataFrame] = {}
        self._dataset_metadata: Dict[str, Dict] = {}  # Store metadata like original shape, last_updated
        self._full_dataframes: Dict[str, pd.DataFrame] = {}
        self._split_indices: Dict[str, Dict[str, np.ndarray]] = {}  # {dataset_id: {"train": idx, "test": idx, "validation": idx}}
        self._active_scope: Dict[str, str] = {}  # {dataset_id: 'train'/'test'/'validation'/'entire'}
        self._split_copies: Dict[str, Dict[str, pd.DataFrame]] = {}  # (kept for backward compatibility)
        self._transformed_copies: Dict[str, Dict[str, pd.DataFrame]] = {}  # {dataset_id: {"train": df, "test": df, "validation": df, "entire": df}}
        # P1.5: previous-dataframe snapshots are now stored on disk as Parquet, not
        # held in RAM as a full DataFrame copy. self._previous_dataframes is retained
        # only as a fallback when the Parquet write fails (so semantics are
        # preserved bit-for-bit when storage is healthy or unhealthy).
        self._previous_dataframes: Dict[str, pd.DataFrame] = {}
        self._previous_snapshot_paths: Dict[str, str] = {} 
        

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
            cls._instance.logger = get_logger(__name__)
            cls._instance.logger.info("DataFrameStateManager singleton instance created")
        return cls._instance

    def update_dataframe(
        self,
        dataset_id: str,
        df: pd.DataFrame,
        original_shape: Optional[Tuple[int, int]] = None,
        force_scope: Optional[str] = None,
    ) -> None:
        """Update the processed DataFrame for a dataset."""
        try:
            # Cache full DataFrame if first time (original, before any transformations).
            #
            # P3.x: alias the caller's frame instead of ``df.copy()``. The caller
            # in ``/upload`` does not mutate ``df`` after this call (it just
            # builds a response), and the few in-house mutators that DO touch
            # the master frame (``add_split_tag_for_pre_split``) take care to
            # ``df.copy()`` themselves before reassigning ``_full_dataframes``,
            # so the master stays consistent. Subsequent
            # ``update_dataframe`` invocations (post exclusion / variable-
            # removal) still go through the ``else`` branch in the
            # ``first_entire_upload`` check below, which copies, so transforms
            # never mutate the master via aliasing.
            #
            # On a 2 GB / 5.4 GiB pandas frame this single copy was costing
            # ~10-30 s on the ``/upload`` hot path (allocator + GC pressure on
            # multi-million-row object columns), and dominated the second-half
            # of the request budget on multi-GB existing-dataset submits.
            if dataset_id not in self._full_dataframes:
                # Guardrail: never seed the master/full dataset from an empty scoped view.
                # If this happens, downstream scopes and training will permanently see 0 rows.
                try:
                    if df is not None and hasattr(df, "shape") and df.shape[0] == 0:
                        existing = self._processed_dataframes.get(dataset_id)
                        if existing is not None and hasattr(existing, "shape") and existing.shape[0] > 0:
                            self._full_dataframes[dataset_id] = existing
                        else:
                            self.logger.warning(
                                f"Refusing to initialize full dataframe for {dataset_id} from empty df."
                            )
                    else:
                        self._full_dataframes[dataset_id] = df
                except Exception:
                    self._full_dataframes[dataset_id] = df

            # Preserve the current processed DataFrame so we can compare before/after.
            # P1.5: Write to a Parquet snapshot on disk instead of holding a full
            # in-RAM copy. For a 5.4 GiB pandas DataFrame this drops peak RAM by
            # ~5 GiB per update_dataframe call (sparse 174-col data compresses to
            # ~300-500 MiB on disk). If the parquet write fails for any reason
            # we fall back to the legacy in-memory copy so behavior is preserved.
            prev_df = self._processed_dataframes.get(dataset_id)
            if prev_df is not None:
                self._snapshot_previous_to_disk(dataset_id, prev_df)

            # Determine which scope to save to
            if force_scope:
                save_scope = force_scope
            else:
                save_scope = self._active_scope.get(dataset_id, "entire")

            # Guardrail: avoid overwriting a non-empty dataset with a 0-row scoped view.
            # This happens when split indices / segment filters produce an empty dev/hold view,
            # and would propagate as a 0xN dataframe into training.
            try:
                full_df = self._full_dataframes.get(dataset_id)
                if (
                    df is not None
                    and hasattr(df, "shape")
                    and df.shape[0] == 0
                    and save_scope in ("dev", "hold")
                    and full_df is not None
                    and hasattr(full_df, "shape")
                    and full_df.shape[0] > 0
                ):
                    self.logger.warning(
                        f"Refusing to overwrite dataset {dataset_id} scope={save_scope} with empty dataframe; "
                        f"full_shape={full_df.shape}. Investigate split indices/segment filters."
                    )
                    return
            except Exception:
                pass

            # Initialize transformed copies if needed
            if dataset_id not in self._transformed_copies:
                self._transformed_copies[dataset_id] = {}

            # First "entire" registration: reuse the single copy already stored in _full_dataframes
            # (avoids tripling memory vs. separate df.copy() for full / entire / processed).
            first_entire_upload = (
                save_scope == "entire"
                and dataset_id not in self._processed_dataframes
                and dataset_id in self._full_dataframes
            )

            if first_entire_upload:
                master_ref = self._full_dataframes[dataset_id]
                self._transformed_copies[dataset_id][save_scope] = master_ref
            else:
                self._transformed_copies[dataset_id][save_scope] = df.copy()

            # Update _processed_dataframes only for train or entire scope (not test/validation)
            # This prevents test/validation propagation from overwriting the active train view.
            #
            # P1.5 part 2: previously this took an additional df.copy(), so a 2 GB
            # frame held three references in RAM (transformed_copies[scope],
            # _processed_dataframes, df).  We now point _processed_dataframes
            # at the SAME object we just stored under transformed_copies[scope]
            # because the existing first_entire_upload branch already proves
            # this aliasing is safe - mutating treatments go through this very
            # method which produces a new transformed copy on each call. The
            # subsequent `_processed['split_tag'] = ...` line is consistent
            # with the per-scope split_tag mutation loop below, so aliasing is
            # logically a no-op there too.
            #
            # Set MIDAS_DEDUP_PROCESSED_REF=0 to revert to the legacy double-copy
            # behavior if any unforeseen mutation surfaces.
            if save_scope in ('train', 'entire'):
                if _os.environ.get("MIDAS_DEDUP_PROCESSED_REF", "1") == "0":
                    self._processed_dataframes[dataset_id] = df.copy()
                else:
                    self._processed_dataframes[dataset_id] = (
                        self._transformed_copies[dataset_id][save_scope]
                    )

            # Store metadata. ``memory_usage(deep=False)`` is intentional: the
            # value is only used for display in logs / metadata. ``deep=True``
            # walks every Python string in every object column and on a 2 GB
            # frame takes ~30 s, which on the ``/upload`` hot path was a
            # meaningful contributor to the 504 idle-timeout we saw at the ALB.
            self._dataset_metadata[dataset_id] = {
                "shape": df.shape,
                "original_shape": original_shape or df.shape,
                "last_updated": pd.Timestamp.now(),
                "memory_usage": df.memory_usage(deep=False).sum() / 1024**2,  # MB
            }

            # P2.3: bump the per-dataset version so any cached analytics
            # results (column-info, DQS, comprehensive_stats, etc.) keyed
            # by the prior version become unreachable on the next read.
            with self._version_lock:
                self._version_counters[dataset_id] = self._version_counters.get(dataset_id, 0) + 1

            self.logger.info(
                f"Updated DataFrame for dataset: {dataset_id}, scope: {save_scope}, "
                f"shape: {df.shape}, memory: {self._dataset_metadata[dataset_id]['memory_usage']:.2f}MB, "
                f"version: {self._version_counters.get(dataset_id, 1)}"
            )

            # Clean up old entries if we have too many (keep last 10)
            self._cleanup_old_entries()

        except Exception as e:
            self.logger.error(f"Failed to update DataFrame for dataset {dataset_id}: {str(e)}")
            raise

    def get_version(self, dataset_id: str) -> int:
        """
        P2.3: Return the current version of a dataset's DataFrame state.
        Starts at 0 for freshly-known dataset IDs that have not yet been
        through update_dataframe (their analytics responses can still be
        cached at version 0; the first update bumps to 1 and invalidates).
        """
        with self._version_lock:
            return self._version_counters.get(dataset_id, 0)

    def merge_scopes_to_entire(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """
        Merge all transformed scopes (train, test, validation) into the 'entire' scope.
        This should be called after treatments are applied to all scopes to get the full combined dataset.
        Returns the merged DataFrame or None if no scopes are available.
        """
        try:
            transformed_copies = self._transformed_copies.get(dataset_id, {})
            dfs_to_combine = []
            
            for scope_name in ['train', 'test', 'validation']:
                if scope_name in transformed_copies and transformed_copies[scope_name] is not None:
                    scope_df = transformed_copies[scope_name]
                    if len(scope_df) > 0:
                        dfs_to_combine.append(scope_df)
                        self.logger.info(f"📊 Adding {scope_name} scope to 'entire': {scope_df.shape}")
            
            if not dfs_to_combine:
                self.logger.warning(f"No transformed scopes found for {dataset_id} to merge")
                return None
            
            combined_df = pd.concat(dfs_to_combine, ignore_index=True)
            self._transformed_copies[dataset_id]['entire'] = combined_df
            self.logger.info(f"✅ Merged all scopes to 'entire' for {dataset_id}: {combined_df.shape}")
            
            return combined_df
        except Exception as e:
            self.logger.error(f"Failed to merge scopes to 'entire' for {dataset_id}: {e}")
            return None

    def get_processed_dataframe(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """Retrieve the processed DataFrame for a dataset if available."""
        return self._processed_dataframes.get(dataset_id)

    def _add_split_tag_column(
        self,
        dataset_id: str,
        master_df: pd.DataFrame,
        train_idx: np.ndarray,
        test_idx: np.ndarray,
        validation_idx: np.ndarray,
    ) -> None:
        """
        Add a 'split_tag' column to the master DataFrame indicating the split assignment.
        Values: 'train', 'test', 'validation', or 'unassigned' for rows not in any split.
        """
        try:
            # Initialize with 'unassigned' for all rows
            split_tags = pd.Series('unassigned', index=master_df.index)
            
            # Assign split tags based on indices
            if len(train_idx) > 0:
                split_tags.iloc[train_idx] = 'train'
            if len(test_idx) > 0:
                split_tags.iloc[test_idx] = 'test'
            if len(validation_idx) > 0:
                split_tags.iloc[validation_idx] = 'validation'
            
            # Add the column to the master DataFrame
            master_df['split_tag'] = split_tags
            
            # Update the stored DataFrames with the new column
            if dataset_id in self._full_dataframes:
                self._full_dataframes[dataset_id]['split_tag'] = split_tags.copy()
            
            if dataset_id in self._processed_dataframes:
                # Get the current processed df indices and map split_tags
                processed_df = self._processed_dataframes[dataset_id]
                if len(processed_df) == len(master_df):
                    self._processed_dataframes[dataset_id]['split_tag'] = split_tags.copy()
                else:
                    # Processed df might be a subset, need to align
                    processed_idx = processed_df.index
                    self._processed_dataframes[dataset_id]['split_tag'] = split_tags.loc[processed_idx].values
            
            # Update transformed copies if they exist
            if dataset_id in self._transformed_copies:
                for scope_name, scope_df in self._transformed_copies[dataset_id].items():
                    if scope_df is not None and len(scope_df) > 0:
                        if len(scope_df) == len(master_df):
                            self._transformed_copies[dataset_id][scope_name]['split_tag'] = split_tags.copy()
                        else:
                            # Subset - align by index
                            try:
                                scope_idx = scope_df.index
                                self._transformed_copies[dataset_id][scope_name]['split_tag'] = split_tags.loc[scope_idx].values
                            except Exception:
                                # Fallback: assign scope name as the tag for scoped views
                                self._transformed_copies[dataset_id][scope_name]['split_tag'] = scope_name
            
            self.logger.info(
                f"Added split_tag column to dataset {dataset_id}: "
                f"train={len(train_idx)}, test={len(test_idx)}, validation={len(validation_idx)}"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to add split_tag column for {dataset_id}: {e}")

    def _persist_split_to_durable_stores(
        self,
        dataset_id: str,
        master_df: pd.DataFrame,
        split_configuration: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist the just-computed split so every worker can see it.

        **Memory-safe at multi-GB CSV scale.** We do NOT rewrite the entire
        dataset object to S3 (that would build a 3+ GB CSV in ``io.BytesIO``
        and OOM-kill the pod). Instead we write:

        1. A tiny one-column **split-tag sidecar Parquet** to S3 via a
           ``NamedTemporaryFile`` (peak process memory ~5–50 MB regardless
           of dataset size, thanks to categorical dictionary encoding).
        2. The lightweight split **config** (~a few hundred bytes) to Redis.
           Indices are NOT stored in Redis — that would be hundreds of MB
           per dataset and is unsafe as a single Redis string.

        Cold worker recovery: load main frame from S3 (existing TTL+LRU
        readonly cache, single shared reference, no extra copy) + load
        sidecar (~10–50 MB) + ``_rebuild_split_indices_from_split_tag``
        (single O(n) boolean mask, ~100 ms for 30M rows).
        """
        scope_sizes: Dict[str, int] = {}
        try:
            for k, v in (self._split_indices.get(dataset_id) or {}).items():
                try:
                    scope_sizes[k] = int(len(v))
                except Exception:
                    continue
        except Exception:
            scope_sizes = {}

        # 1. Redis — lightweight config only (a few hundred bytes).
        try:
            cfg_to_store: Dict[str, Any] = dict(split_configuration or {})
            cfg_to_store.setdefault("_persisted_at_ms", int(_time.time() * 1000))
            _split_state_store.put_config(dataset_id, cfg_to_store, scope_sizes)
        except Exception as exc:
            self.logger.warning(
                f"persist split config to Redis failed for {dataset_id}: {exc}"
            )

        # 2. S3 — split-tag sidecar (single column, ~10–50 MB streamed via
        # a temp file). The full dataset object is NOT rewritten.
        try:
            from app.services.dataset_service import dataset_manager as _ds_mgr
            if "split_tag" in master_df.columns:
                ok = _ds_mgr.save_split_tag_sidecar(dataset_id, master_df["split_tag"])
                if ok:
                    self.logger.info(
                        f"split_tag sidecar persisted for {dataset_id} "
                        f"(rows={len(master_df)})"
                    )
                else:
                    self.logger.warning(
                        f"save_split_tag_sidecar returned False for {dataset_id}; "
                        f"cold workers will fall back to in-RAM split state if any."
                    )
        except Exception as exc:
            self.logger.warning(
                f"persist split_tag sidecar to S3 failed for {dataset_id}: {exc}"
            )

    def _hydrate_split_indices_from_durable(self, dataset_id: str) -> bool:
        """Rebuild ``_split_indices[dataset_id]`` from the S3 sidecar.

        Used by cold workers (no in-RAM split state for this dataset).
        Memory cost: one categorical Series of size N (~5–50 MB for 30M
        rows) + the int64 index arrays themselves (~unavoidable cost of
        any per-scope ``iloc`` view). Returns True on success.
        """
        try:
            from app.services.dataset_service import dataset_manager as _ds_mgr
            tag_series = _ds_mgr.load_split_tag_sidecar(dataset_id)
        except Exception as exc:
            self.logger.warning(
                f"load split_tag sidecar failed for {dataset_id}: {exc}"
            )
            return False
        if tag_series is None or len(tag_series) == 0:
            return False
        try:
            st = tag_series.astype(str)
            train_mask = (st == "train").values
            test_mask = (st == "test").values
            val_mask = st.str.startswith("validation", na=False).values
            n_train = int(train_mask.sum())
            n_test = int(test_mask.sum())
            n_val = int(val_mask.sum())
            if n_train + n_test + n_val == 0:
                return False
            self._split_indices[dataset_id] = {
                "train": np.where(train_mask)[0].astype(np.int64),
                "test": np.where(test_mask)[0].astype(np.int64),
                "validation": np.where(val_mask)[0].astype(np.int64),
            }
            for i in range(1, 4):
                tag = f"validation_{i}"
                m = (st == tag).values
                if int(m.sum()) > 0:
                    self._split_indices[dataset_id][tag] = np.where(m)[0].astype(np.int64)
            self._ensure_scope_aliases(dataset_id)
            self.logger.info(
                f"Rebuilt split indices from sidecar for {dataset_id}: "
                f"train={n_train} test={n_test} validation={n_val}"
            )
            return True
        except Exception as exc:
            self.logger.warning(
                f"rebuild indices from sidecar failed for {dataset_id}: {exc}"
            )
            return False

    # Backwards-compatible alias used by routes.py.
    def _hydrate_split_indices_from_redis(self, dataset_id: str) -> bool:
        return self._hydrate_split_indices_from_durable(dataset_id)

    def _ensure_full_dataframe_loaded(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """Lazy-load the master frame from S3 onto this worker without copying.

        Cold-worker path: when a request lands on a FastAPI worker that did
        not handle the original ``/upload``, ``_full_dataframes[dataset_id]``
        is empty. We borrow the SHARED read-only frame from
        ``dataset_manager.load_dataset_readonly_cached`` and alias it into
        the DFSM caches. ``load_dataset_readonly_cached`` already coalesces
        concurrent loads + TTL-caches the result process-locally, so this is
        a single S3 read per worker per TTL window with no extra ``.copy()``.

        IMPORTANT: callers reading via ``_full_dataframes`` after this call
        must treat the frame as read-only — DFSM's own mutating paths
        (``update_dataframe``, ``apply_exclusion_rules``,
        ``_add_split_tag_column``) already copy before mutating, so this
        aliasing is safe.
        """
        existing = self._full_dataframes.get(dataset_id)
        if existing is not None:
            return existing
        try:
            from app.services.dataset_service import dataset_manager as _ds_mgr
            df = _ds_mgr.load_dataset_readonly_cached(dataset_id)
        except Exception as exc:
            self.logger.warning(
                f"lazy-load full dataframe failed for {dataset_id}: {exc}"
            )
            return None
        if df is None or len(df) == 0:
            return None
        # Alias rather than copy. _processed_dataframes is updated lazily by
        # set_scope/_filtered_view below.
        self._full_dataframes[dataset_id] = df
        self.logger.info(
            f"Lazy-loaded master frame from object storage for {dataset_id}: "
            f"shape={df.shape}, has_split_tag={'split_tag' in df.columns}"
        )
        return df

    def _ensure_scope_aliases(self, dataset_id: str) -> None:
        """
        Keep train/test/validation (TTV) and dev/hold aligned for mixed callers.

        - TTV-only: dev = train ∪ test, hold = validation.
        - dev/hold-only (legacy ratio / sampling-variable split): train = dev, test = ∅,
          validation = hold so TTV scopes and APIs still resolve.
        """
        sid = self._split_indices.get(dataset_id)
        if not sid:
            return
        try:
            has_ttv = all(k in sid for k in ("train", "test", "validation"))
            has_dh = "dev" in sid and "hold" in sid
            if has_ttv and not has_dh:
                tr = np.asarray(sid.get("train", []), dtype=np.int64)
                te = np.asarray(sid.get("test", []), dtype=np.int64)
                va = np.asarray(sid.get("validation", []), dtype=np.int64)
                if len(tr) > 0 or len(te) > 0:
                    sid["dev"] = np.unique(np.concatenate([tr, te]))
                else:
                    sid["dev"] = np.array([], dtype=np.int64)
                sid["hold"] = va.copy()
            elif has_dh and not has_ttv:
                sid["train"] = np.asarray(sid.get("dev", []), dtype=np.int64).copy()
                sid["test"] = np.array([], dtype=np.int64)
                sid["validation"] = np.asarray(sid.get("hold", []), dtype=np.int64).copy()
        except Exception as e:
            self.logger.warning(f"_ensure_scope_aliases failed for {dataset_id}: {e}")

    def _rebuild_split_indices_from_split_tag(self, dataset_id: str, df: pd.DataFrame) -> bool:
        """
        Rebuild TTV _split_indices from split_tag (train / test / validation / validation_n).
        """
        if df is None or len(df) == 0 or "split_tag" not in df.columns:
            return False
        try:
            st = df["split_tag"]
            train_mask = st == "train"
            test_mask = st == "test"
            val_mask = st.astype(str).str.startswith("validation", na=False)
            n_train = int(train_mask.sum())
            n_test = int(test_mask.sum())
            n_val = int(val_mask.sum())
            if n_train + n_test + n_val == 0:
                return False
            self._split_indices[dataset_id] = {
                "train": np.where(train_mask.values)[0].astype(np.int64),
                "test": np.where(test_mask.values)[0].astype(np.int64),
                "validation": np.where(val_mask.values)[0].astype(np.int64),
            }
            for i in range(1, 4):
                val_tag = f"validation_{i}"
                vm = st == val_tag
                if int(vm.sum()) > 0:
                    self._split_indices[dataset_id][val_tag] = np.where(vm.values)[0].astype(np.int64)
            self._ensure_scope_aliases(dataset_id)
            self.logger.info(
                f"Rebuilt split indices from split_tag for {dataset_id}: "
                f"train={n_train}, test={n_test}, validation={n_val}"
            )
            return True
        except Exception as e:
            self.logger.warning(f"_rebuild_split_indices_from_split_tag failed for {dataset_id}: {e}")
            return False

    def add_split_tag_for_pre_split(
        self,
        dataset_id: str,
        df: pd.DataFrame,
        split_role: str,
    ) -> pd.DataFrame:
        """
        Add split_tag column for pre-split uploaded files.
        Called when user uploads separate train/test/validation files.
        
        Args:
            dataset_id: The dataset identifier
            df: The DataFrame to add the tag to
            split_role: One of 'train', 'test', 'validation'
            
        Returns:
            DataFrame with split_tag column added
        """
        try:
            # Normalize the role name
            role_mapping = {
                'train': 'train',
                'test': 'test',
                'validation': 'validation',
                'oot': 'validation',  # OOT maps to validation
                'full': 'train',  # Full population defaults to train
            }
            normalized_role = role_mapping.get(split_role.lower(), 'train')
            
            # Add the split_tag column
            df['split_tag'] = normalized_role
            
            self.logger.info(
                f"Added split_tag='{normalized_role}' to pre-split dataset {dataset_id}, shape: {df.shape}"
            )
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to add split_tag for pre-split dataset {dataset_id}: {e}")
            return df

    def apply_split_configuration(
        self,
        dataset_id: str,
        master_df: pd.DataFrame,
        target_variable: str,
        split_configuration: Optional[Dict[str, Any]],
        seed: int = 42,
        partition_role: Optional[str] = None,
    ) -> bool:
        """
        Apply Step-1 split configuration (train/test/validation scopes).
        Pre-populates _split_indices so set_scope reuses them.
        
        Handles two modes:
        - platform_split: Single file split by the platform into train/test/validation
        - pre_split: User uploads separate files with partition_role specified
        """
        if not split_configuration:
            return False
            
        ingestion_mode = split_configuration.get("ingestion_mode")
        
        # Handle pre_split mode (separate files uploaded by user)
        if ingestion_mode == "pre_split" and partition_role:
            # For pre-split, add split_tag column based on the partition_role
            master_df = self.add_split_tag_for_pre_split(dataset_id, master_df, partition_role)
            
            # Update the stored dataframes with the tagged version
            if dataset_id in self._full_dataframes:
                self._full_dataframes[dataset_id] = master_df.copy()
            if dataset_id in self._processed_dataframes:
                self._processed_dataframes[dataset_id] = master_df.copy()
            
            # For pre-split, entire dataset is assigned to its role
            n = len(master_df)
            all_idx = np.arange(n, dtype=np.int64)
            empty_idx = np.array([], dtype=np.int64)
            
            # Map role to correct split index
            role_lower = partition_role.lower()
            if role_lower in ('train', 'full'):
                self._split_indices[dataset_id] = {
                    "train": all_idx,
                    "test": empty_idx,
                    "validation": empty_idx,
                }
            elif role_lower == 'test':
                self._split_indices[dataset_id] = {
                    "train": empty_idx,
                    "test": all_idx,
                    "validation": empty_idx,
                }
            elif role_lower in ('validation', 'oot'):
                self._split_indices[dataset_id] = {
                    "train": empty_idx,
                    "test": empty_idx,
                    "validation": all_idx,
                }
            
            self.logger.info(
                f"apply_split_configuration (pre_split): {dataset_id} role={partition_role} rows={n}"
            )
            self._ensure_scope_aliases(dataset_id)
            # Make split visible to other workers (S3 + Redis). Best-effort;
            # failures degrade to the legacy in-process-only behaviour.
            self._persist_split_to_durable_stores(
                dataset_id, master_df, split_configuration
            )
            return True
        
        # Handle platform_split mode (single file split by platform)
        if ingestion_mode != "platform_split":
            return False
        method = split_configuration.get("split_method")
        n = len(master_df)
        if n == 0:
            return False
        indices = np.arange(n, dtype=np.int64)
        
        cfg_seed = split_configuration.get("seed")
        if cfg_seed is not None:
            try:
                seed = int(cfg_seed)
            except (ValueError, TypeError):
                pass

        try:
            if method == "user_identifier":
                col = split_configuration.get("identifier_column")
                mapping = split_configuration.get("identifier_mapping") or {}
                if not col or col not in master_df.columns:
                    return False
                s = master_df[col]
                train_v = mapping.get("train")
                test_v = mapping.get("test")
                validation_v = mapping.get("validation")
                if not train_v:
                    return False
                
                def norm_cell(x):
                    if pd.isna(x):
                        return None
                    s = str(x).strip()
                    if s.endswith('.0'):
                        s = s[:-2]
                    return s

                s_norm = s.map(norm_cell)
                null_mask = s_norm.isna() | (s_norm == "")

                def norm_mapping_val(v):
                    s = str(v).strip()
                    if s.endswith('.0'):
                        s = s[:-2]
                    return s
                
                def create_match_mask(s_norm_series, target_val, null_mask):
                    """Create mask that matches either exact string or numeric prefix."""
                    if not target_val:
                        return pd.Series(False, index=s_norm_series.index)
                    
                    target_norm = norm_mapping_val(target_val)
                    exact_match = (s_norm_series == target_norm) & ~null_mask
                    
                    if exact_match.sum() > 0:
                        return exact_match
                    
                    try:
                        target_num = float(target_norm)
                        def extract_leading_number(s):
                            if pd.isna(s) or s == "":
                                return None
                            match = re.match(r'^[\s]*(-?\d+\.?\d*)', str(s))
                            if match:
                                try:
                                    return float(match.group(1))
                                except ValueError:
                                    return None
                            return None
                        
                        s_nums = s_norm_series.map(extract_leading_number)
                        numeric_match = (s_nums == target_num) & ~null_mask
                        return numeric_match
                    except ValueError:
                        return exact_match
                
                train_mask = create_match_mask(s_norm, train_v, null_mask)
                test_mask = create_match_mask(s_norm, test_v, null_mask)
                
                if isinstance(validation_v, list) and len(validation_v) > 0:
                    validation_mask = pd.Series(False, index=master_df.index)
                    for v in validation_v:
                        validation_mask = validation_mask | create_match_mask(s_norm, v, null_mask)
                elif validation_v:
                    validation_mask = create_match_mask(s_norm, validation_v, null_mask)
                else:
                    validation_mask = pd.Series(False, index=master_df.index)
                
                train_idx = np.where(train_mask.values)[0].astype(np.int64)
                test_idx = np.where(test_mask.values)[0].astype(np.int64)
                validation_idx = np.where(validation_mask.values)[0].astype(np.int64)

            elif method == "time_based":
                dc = split_configuration.get("date_column")
                if not dc or dc not in master_df.columns:
                    return False
                ratios = split_configuration.get("ratios") or {}
                tr = int(ratios.get("train", 60))
                te = int(ratios.get("test", 20))
                va = int(ratios.get("validation", 20))
                if tr + te + va != 100:
                    tr, te, va = 60, 20, 20

                # Try multiple date parsing approaches
                dt = pd.to_datetime(master_df[dc], errors="coerce")
                if dt.isna().all() or (dt.notna().any() and dt.dt.year.max() < 1950):
                    for fmt in ["%y-%b", "%b-%y", "%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"]:
                        try:
                            test_dt = pd.to_datetime(master_df[dc], format=fmt, errors="coerce")
                            if test_dt.notna().any() and test_dt.dt.year.max() >= 1950:
                                dt = test_dt
                                break
                        except Exception:
                            continue
                sort_order = np.argsort(dt.values, kind="mergesort")
                sorted_dates = dt.iloc[sort_order]

                cutoff_1 = split_configuration.get("cutoff_1")
                cutoff_2 = split_configuration.get("cutoff_2")

                if cutoff_1 is not None:
                    cutoff_1_dt = pd.to_datetime(cutoff_1, errors="coerce")
                    cutoff_2_dt = pd.to_datetime(cutoff_2, errors="coerce") if cutoff_2 and va > 0 else None

                    train_mask = sorted_dates <= cutoff_1_dt
                    if cutoff_2_dt is not None and pd.notna(cutoff_2_dt):
                        test_mask = (sorted_dates > cutoff_1_dt) & (sorted_dates <= cutoff_2_dt)
                        validation_mask = sorted_dates > cutoff_2_dt
                    else:
                        test_mask = sorted_dates > cutoff_1_dt
                        validation_mask = pd.Series(False, index=sorted_dates.index)

                    train_idx = sort_order[train_mask.values].astype(np.int64)
                    test_idx = sort_order[test_mask.values].astype(np.int64)
                    validation_idx = sort_order[validation_mask.values].astype(np.int64)
                else:
                    train_end = int(n * tr / 100)
                    test_end = int(n * (tr + te) / 100)

                    train_idx = sort_order[:train_end].astype(np.int64)
                    test_idx = sort_order[train_end:test_end].astype(np.int64)
                    validation_idx = sort_order[test_end:].astype(np.int64)

            elif method == "stratified_random":
                ratios = split_configuration.get("ratios") or {}
                tr = int(ratios.get("train", 60))
                te = int(ratios.get("test", 20))
                va = int(ratios.get("validation", 20))
                if tr + te + va != 100:
                    tr, te, va = 60, 20, 20
                tf, tef, vf = tr / 100.0, te / 100.0, va / 100.0

                y = master_df[target_variable] if target_variable in master_df.columns else None
                strat = None
                if y is not None and y.nunique() > 1:
                    if y.nunique() <= 50:
                        strat = y
                    else:
                        try:
                            strat = pd.qcut(y, q=10, labels=False, duplicates="drop")
                            self.logger.info(
                                f"Regression target detected; using 10-quantile bins for stratification"
                            )
                        except Exception:
                            strat = None

                if vf <= 1e-12:
                    rest_idx = indices.copy()
                    validation_idx = np.array([], dtype=np.int64)
                else:
                    rest_idx, validation_idx = train_test_split(
                        indices,
                        test_size=vf,
                        random_state=seed,
                        stratify=strat,
                    )
                    validation_idx = np.asarray(validation_idx, dtype=np.int64)

                strat_rest = None
                if strat is not None and len(rest_idx) > 0:
                    y_rest = strat.iloc[rest_idx].reset_index(drop=True)
                    if y_rest.nunique() > 1:
                        strat_rest = y_rest

                rel_tf = tf / (tf + tef) if (tf + tef) > 1e-9 else 1.0
                if len(rest_idx) == 0:
                    train_idx = np.array([], dtype=np.int64)
                    test_idx = np.array([], dtype=np.int64)
                elif tef <= 1e-12:
                    train_idx = np.asarray(rest_idx, dtype=np.int64)
                    test_idx = np.array([], dtype=np.int64)
                elif tf <= 1e-12:
                    train_idx = np.array([], dtype=np.int64)
                    test_idx = np.asarray(rest_idx, dtype=np.int64)
                else:
                    train_idx, test_idx = train_test_split(
                        rest_idx,
                        train_size=rel_tf,
                        random_state=seed,
                        stratify=strat_rest,
                    )
                    train_idx = np.asarray(train_idx, dtype=np.int64)
                    test_idx = np.asarray(test_idx, dtype=np.int64)

            else:
                return False

            self._split_indices[dataset_id] = {
                "train": train_idx,
                "test": test_idx,
                "validation": validation_idx,
            }
            self.logger.info(
                f"apply_split_configuration: {dataset_id} method={method} "
                f"train={len(train_idx)} test={len(test_idx)} validation={len(validation_idx)}"
            )
            # #region agent log
            try:
                import os as _dbg_os, json as _dbg_json, time as _dbg_time
                _dbg_payload = {
                    "sessionId": "826a95",
                    "hypothesisId": "H1",
                    "location": "dataframe_state_manager.py:apply_split_configuration",
                    "message": "split applied on this worker only (in-memory)",
                    "data": {
                        "pid": _dbg_os.getpid(),
                        "dataset_id": dataset_id,
                        "method": method,
                        "train": int(len(train_idx)),
                        "test": int(len(test_idx)),
                        "validation": int(len(validation_idx)),
                    },
                    "timestamp": int(_dbg_time.time() * 1000),
                }
                with open("/Users/saiyam268728/Library/CloudStorage/OneDrive-EXLService.com(I)Pvt.Ltd/Desktop/UC-Github/RI Branch/.cursor/debug-826a95.log", "a") as _dbg_fh:
                    _dbg_fh.write(_dbg_json.dumps(_dbg_payload) + "\n")
            except Exception:
                pass
            # #endregion
            
            # Add split_tag column to the master DataFrame
            self._add_split_tag_column(dataset_id, master_df, train_idx, test_idx, validation_idx)
            self._ensure_scope_aliases(dataset_id)

            # Make split visible to other workers (S3 + Redis). Best-effort;
            # failures degrade to the legacy in-process-only behaviour.
            self._persist_split_to_durable_stores(
                dataset_id, master_df, split_configuration
            )

            # DO NOT set scope here - keep _processed_dataframes as full data during Step 1
            # Scope will be set to "train" when user clicks Confirm button in frontend
            return True
        except Exception as e:
            self.logger.error(f"apply_split_configuration failed for {dataset_id}: {e}")
            return False

    def set_scope(
        self,
        dataset_id: str,
        scope: str = "train",
        ratio: float = 0.7,
        seed: int = 42,
        sampling_variable: Optional[str] = None,
    ) -> Dict:
        """
        Set the active scope (train/test/validation/entire) for a dataset.
        Uses pre-computed split indices from apply_split_configuration.
        """

        self.logger.info(
            f"📊 set_scope called for {dataset_id}: scope={scope}, ratio={ratio}, seed={seed}"
        )

        # Ensure full df exists
        if dataset_id not in self._full_dataframes and dataset_id in self._processed_dataframes:
            self._full_dataframes[dataset_id] = self._processed_dataframes[dataset_id].copy()

        # Cold-worker hydration: if neither cache has the frame, pull the
        # baseline (with split_tag, post-fix) from object storage. This is
        # the read-only shared reference from dataset_manager so no extra
        # in-RAM copies are introduced.
        if dataset_id not in self._full_dataframes:
            self._ensure_full_dataframe_loaded(dataset_id)

        full_df = self._full_dataframes.get(dataset_id)
        # #region agent log
        try:
            import os as _dbg_os, json as _dbg_json, time as _dbg_time
            _dbg_si = self._split_indices.get(dataset_id)
            _dbg_payload = {
                "sessionId": "826a95",
                "hypothesisId": "H5",
                "location": "dataframe_state_manager.py:set_scope:after-full-lookup",
                "message": "worker view of full_df + split state on set_scope",
                "data": {
                    "pid": _dbg_os.getpid(),
                    "dataset_id": dataset_id,
                    "requested_scope": scope,
                    "full_df_present": full_df is not None,
                    "full_df_shape": list(full_df.shape) if full_df is not None else None,
                    "has_split_indices": _dbg_si is not None,
                    "split_keys": list(_dbg_si.keys()) if _dbg_si else [],
                },
                "timestamp": int(_dbg_time.time() * 1000),
            }
            with open("/Users/saiyam268728/Library/CloudStorage/OneDrive-EXLService.com(I)Pvt.Ltd/Desktop/UC-Github/RI Branch/.cursor/debug-826a95.log", "a") as _dbg_fh:
                _dbg_fh.write(_dbg_json.dumps(_dbg_payload) + "\n")
        except Exception:
            pass
        # #endregion
        if full_df is None:
            self.logger.warning(f"set_scope: No full DataFrame for {dataset_id}")
            return {"dataset_id": dataset_id, "scope": scope, "shape": None}

        # Master transformed "entire" dataset (contains all transformations)
        if dataset_id in self._transformed_copies and "entire" in self._transformed_copies[dataset_id]:
            master_df = self._transformed_copies[dataset_id]["entire"].copy()
            self.logger.info(f"Using master transformed entire dataset for {dataset_id}, shape: {master_df.shape}")
        else:
            master_df = full_df.copy()
            self.logger.info(f"Using original full dataset as master for {dataset_id}, shape: {master_df.shape}")

        # If split indices don't exist yet: try Redis first (cross-pod
        # authoritative), then split_tag (TTV), else legacy dev/hold +
        # persisted config.
        if dataset_id not in self._split_indices:
            if self._hydrate_split_indices_from_redis(dataset_id):
                self.logger.info(
                    f"set_scope: hydrated split indices from Redis for {dataset_id}"
                )
        if dataset_id not in self._split_indices:
            _persisted_cfg = _load_persisted_split_config(dataset_id)
            if _persisted_cfg:
                _p_ratio = _persisted_cfg.get("ratio", ratio)
                _p_seed = _persisted_cfg.get("seed", seed)
                _p_sv = _persisted_cfg.get("sampling_variable", sampling_variable)
                if _p_ratio != ratio or _p_seed != seed or _p_sv != sampling_variable:
                    self.logger.info(
                        f"🔄 Rehydrating split config for {dataset_id} from disk: "
                        f"ratio={_p_ratio}, seed={_p_seed}, sampling_variable={_p_sv} "
                        f"(caller passed ratio={ratio}, seed={seed})"
                    )
                    ratio = _p_ratio
                    seed = _p_seed
                    sampling_variable = _p_sv

            rebuilt_from_tag = self._rebuild_split_indices_from_split_tag(dataset_id, master_df)
            if not rebuilt_from_tag:
                self.logger.info(f"📊 Creating new split for dataset {dataset_id} (total rows: {len(full_df)})")

                if sampling_variable and sampling_variable in full_df.columns:
                    self.logger.info(
                        f"📊 Creating stratified split for {dataset_id} using sampling variable: {sampling_variable}"
                    )

                    if ratio is None or ratio <= 0 or ratio >= 1:
                        ratio = 0.7

                    dev_indices_list = []
                    hold_indices_list = []

                    for value in full_df[sampling_variable].unique():
                        value_mask = full_df[sampling_variable] == value
                        value_indices = np.where(value_mask)[0]

                        rng = np.random.default_rng(seed)
                        rng.shuffle(value_indices)

                        split_point = round(len(value_indices) * ratio)
                        dev_indices_list.append(value_indices[:split_point])
                        hold_indices_list.append(value_indices[split_point:])

                    dev_idx = np.concatenate(dev_indices_list) if dev_indices_list else np.array([], dtype=np.int64)
                    hold_idx = np.concatenate(hold_indices_list) if hold_indices_list else np.array([], dtype=np.int64)

                    rng = np.random.default_rng(seed)
                    rng.shuffle(dev_idx)
                    rng.shuffle(hold_idx)

                    self.logger.info(
                        f"✅ Stratified split created for {dataset_id} - Dev: {len(dev_idx)} rows ({ratio*100:.1f}%), "
                        f"Hold: {len(hold_idx)} rows ({(1-ratio)*100:.1f}%)"
                    )
                    self._split_indices[dataset_id] = {"dev": dev_idx, "hold": hold_idx}

                else:
                    if ratio == 1.0:
                        dev_idx = np.arange(len(full_df))
                        hold_idx = np.array([], dtype=np.int64)
                        self.logger.info(f"📊 Creating split for 'Entire' selection (ratio=1.0) for {dataset_id}")
                        self._split_indices[dataset_id] = {"dev": dev_idx, "hold": hold_idx}
                    else:
                        if ratio is None or ratio <= 0 or ratio >= 1:
                            raise ValueError(
                                f"Invalid split ratio: {ratio}. Must be between 0 and 1 (exclusive) or exactly 1.0 for 'Entire'."
                            )
                        rng = np.random.default_rng(seed)
                        indices = np.arange(len(full_df))
                        rng.shuffle(indices)

                        split = int(len(indices) * max(0.0, min(1.0, ratio)))
                        dev_idx = indices[:split]
                        hold_idx = indices[split:]

                        self.logger.info(
                            f"✅ Random split created for {dataset_id} - Dev: {len(dev_idx)} rows, Hold: {len(hold_idx)} rows"
                        )
                        self._split_indices[dataset_id] = {"dev": dev_idx, "hold": hold_idx}

                try:
                    dev_idx = self._split_indices[dataset_id].get("dev")
                    hold_idx = self._split_indices[dataset_id].get("hold")
                    if (
                        isinstance(dev_idx, np.ndarray)
                        and isinstance(hold_idx, np.ndarray)
                        and len(full_df) > 0
                        and len(dev_idx) == 0
                    ):
                        self.logger.warning(
                            f"Split produced 0-row dev for {dataset_id}. Forcing at least 1 row into dev."
                        )
                        dev_idx = np.array([0], dtype=np.int64)
                        hold_idx = np.array([i for i in range(1, len(full_df))], dtype=np.int64)
                        self._split_indices[dataset_id] = {"dev": dev_idx, "hold": hold_idx}
                except Exception:
                    pass
        else:
            self.logger.info(f"📌 Reusing existing split indices for {dataset_id}")
            # Ensure split_tag column exists in master_df
            if 'split_tag' not in master_df.columns:
                train_idx = self._split_indices[dataset_id].get("train", np.array([], dtype=np.int64))
                test_idx = self._split_indices[dataset_id].get("test", np.array([], dtype=np.int64))
                validation_idx = self._split_indices[dataset_id].get("validation", np.array([], dtype=np.int64))
                self._add_split_tag_column(dataset_id, master_df, train_idx, test_idx, validation_idx)

        self._ensure_scope_aliases(dataset_id)

        # Helper to build filtered view from master using indices
        def _filtered_view(which: str) -> pd.DataFrame:
            idx = self._split_indices[dataset_id].get(which)
            if idx is None or len(idx) == 0:
                return pd.DataFrame()
            valid_idx = idx[idx < len(master_df)]
            return master_df.iloc[valid_idx].copy()

        # Switch to selected scope view (TTV + entire + legacy dev/hold)
        valid_scopes = ["entire", "train", "test", "validation", "dev", "hold"]
        if scope not in valid_scopes:
            self.logger.warning(f"Unknown scope '{scope}'; defaulting to train")
            scope = "train"

        if scope == "entire":
            view = master_df.copy()
            self.logger.info(f"Switched to entire scope for {dataset_id}, shape: {view.shape}")
        else:
            expected_rows = len(self._split_indices[dataset_id].get(scope, []))
            transformed = self._transformed_copies.get(dataset_id, {}).get(scope)

            if transformed is not None and len(transformed) == expected_rows:
                view = transformed.copy()
                self.logger.info(f"Switched to transformed {scope} scope for {dataset_id}, shape: {view.shape}")
            else:
                view = _filtered_view(scope)
                self.logger.info(f"Switched to {scope} scope (filtered from master) for {dataset_id}, shape: {view.shape}")

        # Switch active view
        self._processed_dataframes[dataset_id] = view
        self._active_scope[dataset_id] = scope

        # Update metadata
        self._dataset_metadata[dataset_id] = {
            "shape": view.shape,
            "original_shape": self._dataset_metadata.get(dataset_id, {}).get("original_shape", full_df.shape),
            "last_updated": pd.Timestamp.now(),
            "memory_usage": view.memory_usage(deep=True).sum() / 1024**2,
        }

        self.logger.info(f"Set scope for {dataset_id} -> {scope}, shape: {view.shape}")
        return {"dataset_id": dataset_id, "scope": scope, "shape": view.shape}

    def get_dataframe(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """
        Get the processed DataFrame for a specific dataset.
        Returns a copy to prevent external modifications.
        Use get_dataframe_readonly() for read-only callers (insights, stats, previews)
        to avoid the copy overhead on large datasets.
        """
        df = self._processed_dataframes.get(dataset_id)
        if df is not None:
            self.logger.info(f"Retrieved processed DataFrame for dataset: {dataset_id}, shape: {df.shape}")
            return df.copy()
        self.logger.info(f"No processed DataFrame found for dataset: {dataset_id}")
        return None

    def get_dataframe_readonly(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """
        Return the internal DataFrame reference WITHOUT copying.
        Only use this for read-only operations (insights, stats, previews, storage backends).
        Never mutate the returned DataFrame - use get_dataframe() for that.
        """
        df = self._processed_dataframes.get(dataset_id)
        if df is not None:
            self.logger.debug(f"Readonly ref for dataset: {dataset_id}, shape: {df.shape}")
        return df

    def get_full_dataframe_readonly(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """
        Full combined/master frame for Step 1 previews (exclusion/partition by id),
        ignoring active train/test/validation scope on _processed_dataframes.
        """
        full = self._full_dataframes.get(dataset_id)
        if full is not None:
            return full
        return self._processed_dataframes.get(dataset_id)

    def _snapshot_previous_to_disk(
        self, dataset_id: str, prev_df: pd.DataFrame
    ) -> None:
        """
        P1.5: Persist the pre-update DataFrame to a Parquet sidecar so we don't
        have to hold a full duplicate in RAM. Falls back to an in-memory copy
        if Parquet write fails (preserves the semantic guarantee that
        get_previous_dataframe() can return the snapshot).

        Synchronous on purpose: callers expect the previous-snapshot to be
        available immediately after update_dataframe returns. Parquet write of
        a 5.4 GiB pandas frame on sparse numeric data is typically faster than
        the equivalent in-memory copy + the GC pressure it creates.
        """
        snapshot_dir = _prev_snapshot_dir(dataset_id)
        try:
            _os.makedirs(snapshot_dir, exist_ok=True)
        except Exception as exc:
            self.logger.warning(
                f"prev-df snapshot dir create failed for {dataset_id}: {exc}; "
                f"falling back to in-memory copy."
            )
            with self._previous_snapshot_lock:
                self._previous_dataframes[dataset_id] = prev_df.copy()
            return

        snapshot_path = _os.path.join(
            snapshot_dir,
            f"prev_{int(_time.time() * 1000)}.parquet",
        )

        try:
            prev_df.to_parquet(snapshot_path, engine="pyarrow", index=True)
        except Exception as exc:
            self.logger.warning(
                f"prev-df parquet write failed for {dataset_id} "
                f"({snapshot_path}): {exc}; falling back to in-memory copy."
            )
            try:
                if _os.path.exists(snapshot_path):
                    _os.unlink(snapshot_path)
            except OSError:
                pass
            with self._previous_snapshot_lock:
                self._previous_dataframes[dataset_id] = prev_df.copy()
            return

        with self._previous_snapshot_lock:
            old_path = self._previous_snapshot_paths.get(dataset_id)
            self._previous_snapshot_paths[dataset_id] = snapshot_path
            # Drop any stale in-memory fallback now that we have a fresh
            # on-disk snapshot.
            if dataset_id in self._previous_dataframes:
                del self._previous_dataframes[dataset_id]

        if old_path and old_path != snapshot_path and _os.path.exists(old_path):
            try:
                _os.unlink(old_path)
            except OSError:
                pass

        self.logger.info(
            f"prev-df snapshot persisted for {dataset_id} -> {snapshot_path} "
            f"(shape={prev_df.shape})"
        )

    def get_previous_dataframe(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """
        Get the dataset snapshot that existed just before the most recent update.
        Useful for comparing pre- and post-change column stats and missingness.

        P1.5: Reads the on-disk Parquet snapshot when available. Falls back to
        the in-memory copy (only present if the Parquet write previously failed).
        """
        # In-memory fallback (failure path; rare).
        previous_df = self._previous_dataframes.get(dataset_id)
        if previous_df is not None:
            self.logger.info(
                f"Retrieved previous DataFrame snapshot (in-memory fallback) "
                f"for {dataset_id}, shape: {previous_df.shape}"
            )
            return previous_df.copy()

        snapshot_path = self._previous_snapshot_paths.get(dataset_id)
        if snapshot_path and _os.path.exists(snapshot_path):
            try:
                df = pd.read_parquet(snapshot_path, engine="pyarrow")
                self.logger.info(
                    f"Loaded prev-df snapshot from disk for {dataset_id} "
                    f"({snapshot_path}), shape: {df.shape}"
                )
                return df
            except Exception as exc:
                self.logger.warning(
                    f"Failed to read prev-df snapshot {snapshot_path} "
                    f"for {dataset_id}: {exc}"
                )
                return None

        self.logger.info(f"No previous DataFrame snapshot cached for {dataset_id}")
        return None

    def get_latest_dataframe_for_planning(self, original_df: pd.DataFrame, dataset_id: Optional[str] = None) -> pd.DataFrame:
        """
        Get the most appropriate DataFrame for plan generation.
        Returns the latest processed DataFrame that matches the original shape,
        or the original DataFrame if no processed version is available.
        """
        if dataset_id:
            split_indices = self._split_indices.get(dataset_id, {})
            train_idx = split_indices.get('train') if split_indices else None

            # If split exists, always prefer TRAIN data for assistant planning/EDA/QC tables.
            if train_idx is not None and len(train_idx) > 0:
                transformed = self._transformed_copies.get(dataset_id, {})
                master_df = transformed.get('entire')
                if master_df is None:
                    master_df = self._full_dataframes.get(dataset_id)
                if master_df is None:
                    master_df = self._processed_dataframes.get(dataset_id)

                if master_df is not None and len(master_df) > 0:
                    if 'split_tag' in master_df.columns:
                        train_df = master_df[master_df['split_tag'].astype(str) == 'train'].copy()
                        if len(train_df) > 0:
                            self.logger.info(
                                f"Using TRAIN dataframe for planning (split_tag) for {dataset_id}, shape: {train_df.shape}"
                            )
                            return train_df

                    valid_idx = train_idx[train_idx < len(master_df)]
                    if len(valid_idx) > 0:
                        train_df = master_df.iloc[valid_idx].copy()
                        self.logger.info(
                            f"Using TRAIN dataframe for planning (indices) for {dataset_id}, shape: {train_df.shape}"
                        )
                        return train_df

                transformed_train = transformed.get('train')
                if transformed_train is not None and len(transformed_train) > 0:
                    self.logger.info(
                        f"Using transformed TRAIN dataframe for planning for {dataset_id}, shape: {transformed_train.shape}"
                    )
                    return transformed_train.copy()

            df = self.get_dataframe(dataset_id)
            if df is not None:
                self.logger.info(f"Using direct lookup processed DataFrame for planning: {dataset_id}, shape: {df.shape}")
                return df

        if self._processed_dataframes:
            most_recent_id, most_recent_df = list(self._processed_dataframes.items())[-1]
            self.logger.info(f"Using most recent processed DataFrame for planning: {most_recent_id}, shape: {most_recent_df.shape}")
            return most_recent_df

        self.logger.info("No processed DataFrame found, using original DataFrame for planning")
        return original_df

    def get_dataframe_for_execution(self, dataset_id: str, original_df: pd.DataFrame = None) -> Optional[pd.DataFrame]:
        """
        Get the appropriate DataFrame for code execution.
        Returns the processed DataFrame if available, otherwise the original.
        Returns None if neither is available.
        """
        processed_df = self.get_dataframe(dataset_id)
        if processed_df is not None:
            self.logger.info(f"Using processed DataFrame for execution: {dataset_id}, shape: {processed_df.shape}")
            return processed_df
        if original_df is not None:
            self.logger.info(f"Using original DataFrame for execution: {dataset_id}, shape: {original_df.shape}")
            return original_df
        self.logger.info(f"No processed DataFrame found for dataset: {dataset_id}")
        return None

    def has_processed_dataframe(self, dataset_id: str) -> bool:
        """Check if a processed DataFrame exists for the given dataset."""
        return dataset_id in self._processed_dataframes

    def get_dataset_info(self, dataset_id: str) -> Optional[Dict]:
        """Get metadata information for a dataset."""
        return self._dataset_metadata.get(dataset_id)

    def clear_dataset(self, dataset_id: str) -> bool:
        """
        Clear the processed DataFrame and metadata for a specific dataset.
        """
        cleared = False
        self.logger.info('clearing dataset', dataset_id)
        if dataset_id in self._processed_dataframes:
            self.logger.info('clearing processed _processed_dataframes')
            del self._processed_dataframes[dataset_id]
            cleared = True
        if dataset_id in self._dataset_metadata:
            self.logger.info('clearing processed _dataset_metadata')
            del self._dataset_metadata[dataset_id]
        if dataset_id in self._full_dataframes:
            self.logger.info('clearing processed _full_dataframes')
            del self._full_dataframes[dataset_id]
        if dataset_id in self._split_indices:
            self.logger.info('clearing processed _split_indices')
            del self._split_indices[dataset_id]
        if dataset_id in self._active_scope:
            self.logger.info('clearing processed _active_scope')
            del self._active_scope[dataset_id]
        if dataset_id in self._transformed_copies:
            self.logger.info('clearing processed _transformed_copies')
            del self._transformed_copies[dataset_id]
        if dataset_id in self._previous_dataframes:
            self.logger.info('clearing processed _previous_dataframes')
            del self._previous_dataframes[dataset_id]
        gc.collect()
        _helpers.dataframe_report("after_clear_dataset")
        # P1.5: also delete the on-disk previous-df snapshot so storage is freed
        # alongside in-memory state.
        with self._previous_snapshot_lock:
            snapshot_path = self._previous_snapshot_paths.pop(dataset_id, None)
        if snapshot_path and _os.path.exists(snapshot_path):
            try:
                _os.unlink(snapshot_path)
            except OSError as exc:
                self.logger.warning(
                    f"Failed to delete prev-df snapshot {snapshot_path}: {exc}"
                )
        # P2.3: clear version counter and proactively drop cached analytics.
        with self._version_lock:
            self._version_counters.pop(dataset_id, None)
        try:
            from app.services.analytics_cache import analytics_cache
            analytics_cache.invalidate_dataset(dataset_id)
        except Exception:
            pass
        # Drop any cross-pod split state so a re-upload starts clean.
        try:
            _split_state_store.invalidate(dataset_id)
        except Exception:
            pass
        if cleared:
            self.logger.info(f"Cleared processed DataFrame and all related data for dataset: {dataset_id}")
        return cleared

    def get_cache_stats(self) -> Dict:
        """Get statistics about the current cache state."""
        total_memory = sum(meta.get("memory_usage", 0) for meta in self._dataset_metadata.values())
        return {
            "total_datasets": len(self._processed_dataframes),
            "total_memory_mb": round(total_memory, 2),
            "datasets": list(self._processed_dataframes.keys()),
            "metadata": self._dataset_metadata,
        }

    def collect_state_metrics(self) -> Dict[str, Dict[str, float]]:
        """Collect per-dictionary frame counts and shallow byte sizes.

        Returns a mapping ``<dict_name> -> {"frame_count", "size_bytes"}`` for
        each DataFrame-holding dictionary this manager owns. The keys are the
        attribute names (minus the leading underscore) so emitted metric names
        line up with the dictionaries themselves:
        ``processed_dataframes``, ``full_dataframes``, ``transformed_copies``,
        ``previous_dataframes``.

        Performance contract (this method is called from a background metrics
        thread, never on a request hot path):
          - Uses ``memory_usage(deep=False)`` which is O(columns) and does NOT
            scan row values. ``deep=True`` would walk every Python object and
            hold the GIL for tens of seconds on a multi-GB frame, stalling all
            request threads — so it is deliberately avoided. The trade-off is
            that object/string columns are undercounted, making ``size_bytes``
            a lower-bound estimate of resident size.
          - No locks are taken (locking these dicts would add contention to the
            ``/upload`` hot path). Iteration is over a best-effort ``list(...)``
            snapshot guarded by ``try/except`` so a concurrent mutation can
            never raise into the caller.
        """
        def _frame_bytes(df: Optional[pd.DataFrame]) -> int:
            if df is None:
                return 0
            try:
                return int(df.memory_usage(index=True, deep=False).sum())
            except Exception:
                return 0

        stats: Dict[str, Dict[str, float]] = {}

        # Flat {dataset_id: DataFrame} dictionaries.
        for name, store in (
            ("processed_dataframes", self._processed_dataframes),
            ("full_dataframes", self._full_dataframes),
            ("previous_dataframes", self._previous_dataframes),
        ):
            count = 0
            total = 0
            try:
                for df in list(store.values()):
                    if df is not None:
                        count += 1
                        total += _frame_bytes(df)
            except Exception:
                pass
            stats[name] = {"frame_count": float(count), "size_bytes": float(total)}

        # Nested {dataset_id: {scope: DataFrame}} dictionary.
        count = 0
        total = 0
        try:
            for inner in list(self._transformed_copies.values()):
                for df in list(inner.values()):
                    if df is not None:
                        count += 1
                        total += _frame_bytes(df)
        except Exception:
            pass
        stats["transformed_copies"] = {"frame_count": float(count), "size_bytes": float(total)}

        return stats

    def _cleanup_old_entries(self, max_entries: int = 10) -> None:
        """
        Clean up old entries to manage memory usage.
        Keeps the most recently updated entries.
        """
        if len(self._processed_dataframes) <= max_entries:
            return

        sorted_items = sorted(
            self._dataset_metadata.items(),
            key=lambda x: x[1].get("last_updated", pd.Timestamp.min),
            reverse=True,
        )
        entries_to_keep = dict(sorted_items[:max_entries])
        entries_to_remove = set(self._dataset_metadata.keys()) - set(entries_to_keep.keys())

        for dataset_id in entries_to_remove:
            self.clear_dataset(dataset_id)

        if entries_to_remove:
            self.logger.info(f"Cleaned up {len(entries_to_remove)} old DataFrame entries")  
    def apply_exclusion_rules(
        self,
        dataset_id: str,
        exclusion_groups: list,
        target_variable: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply exclusion rules to the master DataFrame and remove matching rows.
        
        Args:
            dataset_id: The dataset ID
            exclusion_groups: List of exclusion groups, each with conditions
            target_variable: Optional target variable for event rate calculation
            
        Returns:
            Dict with statistics: original_count, removed_count, remaining_count, event_rate_before, event_rate_after
        """
        df = self._full_dataframes.get(dataset_id)
        if df is None:
            df = self._processed_dataframes.get(dataset_id)
        
        if df is None:
            self.logger.warning(f"No DataFrame found for dataset {dataset_id}")
            return {"error": "Dataset not found"}
        
        original_count = len(df)
        event_rate_before = None
        if target_variable and target_variable in df.columns:
            event_rate_before = float(df[target_variable].mean() * 100)
        
        self.logger.info(f"Applying exclusion rules to dataset {dataset_id}: {len(exclusion_groups)} groups, {original_count} rows")
        
        def evaluate_condition(data: pd.DataFrame, cond: dict) -> pd.Series:
            """Evaluate a single condition and return boolean mask."""
            col = cond.get('column')
            op = cond.get('operator', '=')
            val = cond.get('value')
            
            if col not in data.columns:
                return pd.Series(False, index=data.index)
            
            # Unwrap single-element lists for scalar comparison operators
            if isinstance(val, list) and len(val) == 1 and op in ('=', '!=', '>', '>=', '<', '<=', 'STARTS WITH', 'CONTAINS'):
                val = val[0]
            
            series = data[col]
            
            if op == 'IS NULL':
                return series.isna()
            elif op == 'IS NOT NULL':
                return series.notna()
            elif op == '= TRUE':
                return series.astype(str).str.lower().isin(['true', '1', 'yes'])
            elif op == '= FALSE':
                return series.astype(str).str.lower().isin(['false', '0', 'no'])
            elif op == '=':
                return series == val
            elif op == '!=':
                return series != val
            elif op == '>':
                return series > val
            elif op == '>=':
                return series >= val
            elif op == '<':
                return series < val
            elif op == '<=':
                return series <= val
            elif op == 'IN':
                vals = val if isinstance(val, list) else [v.strip() for v in str(val).split(',')]
                return series.astype(str).isin([str(v) for v in vals])
            elif op == 'NOT IN':
                vals = val if isinstance(val, list) else [v.strip() for v in str(val).split(',')]
                return ~series.astype(str).isin([str(v) for v in vals])
            elif op == 'STARTS WITH':
                return series.astype(str).str.startswith(str(val), na=False)
            elif op == 'CONTAINS':
                return series.astype(str).str.contains(str(val), na=False, case=False)
            elif op == 'BETWEEN':
                if isinstance(val, list) and len(val) == 2:
                    return (series >= val[0]) & (series <= val[1])
                return pd.Series(False, index=data.index)
            elif op == 'NOT BETWEEN':
                if isinstance(val, list) and len(val) == 2:
                    return (series < val[0]) | (series > val[1])
                return pd.Series(False, index=data.index)
            else:
                return pd.Series(False, index=data.index)
        
        def evaluate_group(data: pd.DataFrame, group: dict) -> pd.Series:
            """Evaluate a group of conditions with AND/OR connectors."""
            conditions = group.get('conditions', [])
            if not conditions:
                return pd.Series(False, index=data.index)
            
            masks = [evaluate_condition(data, c) for c in conditions]
            connectors = [c.get('connector', 'AND') for c in conditions]
            
            # Parse AND groups first, then OR them (AND binds before OR)
            and_groups = []
            current_group_indices = [0]
            
            for i in range(1, len(masks)):
                prev_connector = connectors[i - 1]
                if prev_connector == 'AND':
                    current_group_indices.append(i)
                else:  # OR
                    and_groups.append(current_group_indices)
                    current_group_indices = [i]
            and_groups.append(current_group_indices)
            
            # AND within each group
            and_results = []
            for grp_indices in and_groups:
                grp_masks = [masks[i] for i in grp_indices]
                grp_result = grp_masks[0]
                for m in grp_masks[1:]:
                    grp_result = grp_result & m
                and_results.append(grp_result)
            
            # OR between groups
            final_result = and_results[0]
            for ar in and_results[1:]:
                final_result = final_result | ar
            
            return final_result
        
        # Combine all groups with OR (any group match = exclude)
        if not exclusion_groups:
            return {
                "original_count": original_count,
                "removed_count": 0,
                "remaining_count": original_count,
                "event_rate_before": event_rate_before,
                "event_rate_after": event_rate_before
            }
        
        combined_mask = pd.Series(False, index=df.index)
        for group in exclusion_groups:
            group_mask = evaluate_group(df, group)
            combined_mask = combined_mask | group_mask
            self.logger.info(f"  Group matched {group_mask.sum()} rows, cumulative: {combined_mask.sum()}")
        
        # Filter out excluded rows
        filtered_df = df[~combined_mask].copy()
        removed_count = combined_mask.sum()
        remaining_count = len(filtered_df)
        
        event_rate_after = None
        if target_variable and target_variable in filtered_df.columns and len(filtered_df) > 0:
            event_rate_after = float(filtered_df[target_variable].mean() * 100)
        
        # Update the stored DataFrames
        self._full_dataframes[dataset_id] = filtered_df
        self._processed_dataframes[dataset_id] = filtered_df
        
        # Clear any existing split indices since the data changed
        if dataset_id in self._split_indices:
            del self._split_indices[dataset_id]
        if dataset_id in self._transformed_copies:
            del self._transformed_copies[dataset_id]
        # Indices no longer valid; drop the cross-pod copy so other workers
        # do not serve stale partitions for the trimmed dataset.
        try:
            _split_state_store.invalidate(dataset_id)
        except Exception:
            pass

        if len(filtered_df) > 0:
            self._rebuild_split_indices_from_split_tag(dataset_id, filtered_df)
            # Re-publish the (now smaller) split-tag sidecar + config so
            # other workers stay aligned with the trimmed dataset.
            try:
                if "split_tag" in filtered_df.columns:
                    self._persist_split_to_durable_stores(
                        dataset_id, filtered_df, None
                    )
            except Exception:
                pass
        
        self.logger.info(f"Exclusion rules applied: {removed_count} rows removed, {remaining_count} remaining")
        
        return {
            "original_count": original_count,
            "removed_count": int(removed_count),
            "remaining_count": remaining_count,
            "event_rate_before": event_rate_before,
            "event_rate_after": event_rate_after
        }


# Global instance for easy access
dataframe_state_manager = DataFrameStateManager()



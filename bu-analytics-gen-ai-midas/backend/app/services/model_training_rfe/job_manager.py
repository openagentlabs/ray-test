"""
RfeJobManager - facade over storage / state / event_bus / queue.

Responsibilities:
- `start(config)` - validate, write config.json, materialize train.parquet (only
  useful in multi-worker mode), create a JobStateRow, enqueue the job. Returns job_id.
- `get_status(job_id)` - return the current JobStateRow + lightweight iteration
  count (read from storage listing).
- `cancel(job_id)` - flips the cancel flag.
- `get_result(job_id)` - returns the final_result.json payload (or None if not done).
- `subscribe(job_id)` - async iterator of SSE ticks (delegates to EventBus).
- `hydrate_startup()` - marks any "running" jobs from a previous process as
  `interrupted` so the UI can re-start them.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, AsyncIterator, Dict, Optional

from app.core.logging_config import get_logger

from .backends import get_backends
from .contracts import (
    RfeJobConfig,
    RfeStatus,
    WorkingFeatureSet,
    _to_plain,
)
from .event_bus.base import EventBus
from .job_queue.base import JobQueue
from .job_queue.in_process import InProcessJobQueue
from .job_state.base import JobStateRow, JobStateStore
from .rfe_service import RfeService
from .storage.base import StorageBackend
from .training_data_provider import TrainingDataProvider

_logger = get_logger(__name__)


class RfeJobManager:
    def __init__(self) -> None:
        storage, state, bus, queue, mode = get_backends()
        self._storage: StorageBackend = storage
        self._state: JobStateStore = state
        self._bus: EventBus = bus
        self._queue: JobQueue = queue
        self._mode: str = mode
        if isinstance(self._queue, InProcessJobQueue):
            # Wire the executor for local mode: run RfeService synchronously in the queue's thread.
            self._queue.set_executor(self._run_inline)

    # ---------------- public API ----------------

    def start(
        self,
        *,
        dataset_id: str,
        target: str,
        working_set: WorkingFeatureSet,
        weight_col: Optional[str],
        user_id: Optional[str],
    ) -> str:
        job_id = f"rfe_{uuid.uuid4().hex[:12]}"

        # Persist train.parquet only when we are running multi-worker (redis).
        # In local mode, the service thread shares memory with DFSM so parquet is
        # unnecessary overhead.
        need_parquet = self._mode == "redis"
        parquet_ok = False
        if need_parquet:
            parquet_ok = TrainingDataProvider(storage=self._storage).materialize_train_parquet(
                dataset_id=dataset_id,
                target=target,
                feature_cols=working_set.all_features,
                weight_col=weight_col,
                job_id=job_id,
            )

        cfg = RfeJobConfig(
            job_id=job_id,
            dataset_id=dataset_id,
            target=target,
            working_set=working_set,
            weight_col=weight_col,
            user_id=user_id,
            created_at_epoch=time.time(),
            train_parquet_available=parquet_ok,
        )
        self._storage.put_json(job_id, "config.json", _to_plain(cfg))

        row = JobStateRow(
            job_id=job_id,
            status=RfeStatus.PENDING.value,
            message="Queued",
            dataset_id=dataset_id,
            user_id=user_id,
            current_iteration=0,
            total_features=len(working_set.all_features),
            best_iteration=-1,
            created_at=time.time(),
        )
        self._state.create(row)
        self._queue.enqueue(job_id)
        _logger.info("Enqueued RFE job %s (mode=%s, features=%d)", job_id, self._mode, row.total_features)
        return job_id

    def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        row = self._state.get(job_id)
        if row is None:
            # EKS / multi-replica: job metadata lives in Redis only when
            # RFE_SCALING_MODE=redis. Otherwise each pod has its own in-memory
            # store; artifacts still land on shared storage (filesystem PVC or
            # RFE_STORAGE_BACKEND=s3). Reconstruct status from artifacts so
            # GET /rfe/status and POST /rfe/finalize work on any pod once the
            # worker has written iteration_* / final_result.json.
            recovered = self._recover_status_from_storage(job_id)
            return recovered
        # Count iterations by listing keys (cheap for filesystem; fine for S3 at our volume).
        iteration_keys = [k for k in self._storage.list_keys(job_id) if k.startswith("iteration_")]
        return {
            **row.to_dict(),
            "iteration_count": len(iteration_keys),
        }

    def _recover_status_from_storage(self, job_id: str) -> Optional[Dict[str, Any]]:
        cfg = self._storage.get_json(job_id, "config.json")
        if cfg is None:
            return None
        iteration_keys = [
            k for k in self._storage.list_keys(job_id) if k.startswith("iteration_") and k.endswith(".json")
        ]
        final = self._storage.get_json(job_id, "final_result.json")
        if final is not None:
            return {
                "job_id": job_id,
                "status": "completed",
                "message": "Recovered from artifact storage",
                "dataset_id": final.get("dataset_id") or cfg.get("dataset_id"),
                "user_id": cfg.get("user_id"),
                "current_iteration": int(final.get("total_iterations") or len(iteration_keys) or 0),
                "total_features": int(final.get("starting_feature_count") or cfg.get("total_features") or 0),
                "best_iteration": int(final.get("best_iteration", -1)),
                "latest_cv_auc": final.get("best_cv_auc"),
                "cancel_flag": False,
                "heartbeat_at": time.time(),
                "created_at": float(cfg.get("created_at_epoch") or 0),
                "updated_at": time.time(),
                "error": None,
                "iteration_count": len(iteration_keys),
            }
        # In-flight job started on another pod (or local memory lost): expose progress from artifacts.
        ws = cfg.get("working_set") or {}
        locked = ws.get("locked") if isinstance(ws, dict) else []
        screened = ws.get("screened") if isinstance(ws, dict) else []
        if not isinstance(locked, list):
            locked = []
        if not isinstance(screened, list):
            screened = []
        seen = set()
        total_feat_count = 0
        for v in locked + screened:
            if v not in seen:
                seen.add(v)
                total_feat_count += 1

        return {
            "job_id": job_id,
            "status": "running",
            "message": "Recovered from artifact storage (in progress)",
            "dataset_id": cfg.get("dataset_id"),
            "user_id": cfg.get("user_id"),
            "current_iteration": len(iteration_keys),
            "total_features": total_feat_count,
            "best_iteration": -1,
            "latest_cv_auc": None,
            "cancel_flag": False,
            "heartbeat_at": time.time(),
            "created_at": float(cfg.get("created_at_epoch") or 0),
            "updated_at": time.time(),
            "error": None,
            "iteration_count": len(iteration_keys),
        }

    def cancel(self, job_id: str) -> bool:
        return self._state.request_cancel(job_id)

    def list_active_jobs(self) -> list[Dict[str, Any]]:
        """Return active (pending/running) RFE jobs as plain dict rows."""
        return [row.to_dict() for row in self._state.list_active()]

    def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._storage.get_json(job_id, "final_result.json")

    def list_iteration_keys(self, job_id: str) -> list[str]:
        """Return iteration_NNNN.json keys for this job, sorted by index."""
        keys = [k for k in self._storage.list_keys(job_id) if k.startswith("iteration_") and k.endswith(".json")]
        keys.sort()
        return keys

    def get_iteration(self, job_id: str, key: str) -> Optional[Dict[str, Any]]:
        return self._storage.get_json(job_id, key)

    def get_config(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._storage.get_json(job_id, "config.json")

    def audit(self, job_id: str, row: Dict[str, Any]) -> None:
        self._storage.append_jsonl(job_id, "audit.jsonl", row)

    def write_monotone_and_features(
        self,
        *,
        job_id: str,
        monotone: Dict[str, int],
        features: Dict[str, Any],
    ) -> None:
        """Called by /rfe/finalize - persist the HITL outcome for Step 5 pickup."""
        self._storage.put_json(job_id, "monotone.json", monotone)
        self._storage.put_json(job_id, "final_features.json", features)

    def read_monotone_by_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """
        Lookup the latest finalized monotone payload for a dataset by scanning active rows
        + completed jobs for matching dataset_id. Cheapest path: check active rows first.
        """
        # For filesystem backend we can walk the artifact dir. For S3 this needs a
        # lightweight index; out of scope for now (documented on the plan).
        if not hasattr(self._storage, "root_dir"):
            return None
        root = getattr(self._storage, "root_dir")
        import os

        if not os.path.isdir(root):
            return None
        latest = None
        latest_mtime = -1.0
        for job_id in os.listdir(root):
            folder = os.path.join(root, job_id)
            mon = os.path.join(folder, "monotone.json")
            features = os.path.join(folder, "final_features.json")
            if not (os.path.isfile(mon) and os.path.isfile(features)):
                continue
            cfg = self._storage.get_json(job_id, "config.json")
            if not cfg or cfg.get("dataset_id") != dataset_id:
                continue
            mtime = max(os.path.getmtime(mon), os.path.getmtime(features))
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest = {
                    "job_id": job_id,
                    "monotone": self._storage.get_json(job_id, "monotone.json"),
                    "final_features": self._storage.get_json(job_id, "final_features.json"),
                }
        return latest

    async def subscribe(self, job_id: str) -> AsyncIterator[Dict[str, Any]]:
        async for event in self._bus.subscribe(job_id):
            yield event

    def hydrate_startup(self) -> None:
        """
        Mark jobs whose status was running/pending at process start as `interrupted`.
        Called from main.py startup_event so a pod restart doesn't leave stuck jobs.
        """
        for row in self._state.list_active():
            self._state.update(
                row.job_id,
                status=RfeStatus.INTERRUPTED.value,
                message="Interrupted by server restart",
            )
            self.audit(row.job_id, {"event": "job_interrupted_on_startup", "ts": time.time()})

    # ---------------- internal ----------------

    def _run_inline(self, job_id: str) -> None:
        """Executor wired to the InProcessJobQueue for local mode."""
        svc = RfeService(
            storage=self._storage,
            job_state=self._state,
            event_bus=self._bus,
            worker_context=False,
        )
        svc.run(job_id)


# Lazy singleton - constructed on first access so backends env reads happen after app setup.
_INSTANCE: Optional[RfeJobManager] = None


def get_job_manager() -> RfeJobManager:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = RfeJobManager()
    return _INSTANCE

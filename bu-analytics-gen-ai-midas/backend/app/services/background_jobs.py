"""
Background Job Manager for handling long-running tasks asynchronously
Prevents timeout errors in Azure deployments.

Job snapshots are mirrored to shared object storage (same S3 bucket / upload root as datasets)
so GET /.../status/{job_id} works across Kubernetes replicas (not only the pod that started the job).
"""
import json
import os
import threading
import time
import uuid
from typing import Dict, Any, List, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# Per-job JSON objects in shared object storage (S3 / local upload dir) so status polling
# works across Kubernetes replicas (in-memory _jobs alone only works on a single pod).
_BG_JOB_STORE_PREFIX = "midas_bg_jobs/"


def _job_store_key(job_id: str) -> str:
    return f"{_BG_JOB_STORE_PREFIX}{job_id}.json"


def _job_snapshot_fresher(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Whether job snapshot ``a`` should replace ``b`` (e.g. S3 vs in-memory on a poller pod)."""
    term = (JobStatus.COMPLETED.value, JobStatus.FAILED.value)
    sa, sb = str(a.get("status") or ""), str(b.get("status") or "")
    if sa in term and sb not in term:
        return True
    if sb in term and sa not in term:
        return False
    # Both terminal: prefer a successful completion over a stale local "restart"
    # failure so EKS clients polling S3 don't lose results after deploy/restart.
    if sa == JobStatus.COMPLETED.value and sb == JobStatus.FAILED.value:
        return True
    if sb == JobStatus.COMPLETED.value and sa == JobStatus.FAILED.value:
        return False
    try:
        ta = float(a.get("completed_at") or a.get("started_at") or 0)
        tb = float(b.get("completed_at") or b.get("started_at") or 0)
        if ta != tb:
            return ta > tb
    except (TypeError, ValueError):
        pass
    return int(a.get("progress", 0) or 0) > int(b.get("progress", 0) or 0)


def _job_to_persistable(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """Subset of job fields written to disk / object storage."""
    return {
        "job_id": job_data.get("job_id"),
        "job_type": job_data.get("job_type"),
        "status": job_data.get("status"),
        "params": job_data.get("params"),
        "result": job_data.get("result"),
        "error": job_data.get("error"),
        "progress": job_data.get("progress", 0),
        "message": job_data.get("message", ""),
        "step": job_data.get("step", 0),
        "started_at": job_data.get("started_at"),
        "completed_at": job_data.get("completed_at"),
    }


class BackgroundJobManager:
    """
    Thread-safe background job manager for async operations
    """
    
    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._threads: Dict[str, threading.Thread] = {}
        self._persist_path = os.getenv(
            "BACKGROUND_JOBS_STATE_PATH",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "background_jobs_state.json")),
        )
        self._load_jobs_state()

    def _sync_jobs_to_object_storage(self, safe_jobs: Dict[str, Dict[str, Any]]) -> None:
        """Write each job snapshot to shared storage for multi-replica API servers (EKS)."""
        try:
            from app.services.object_storage.registry import get_object_storage

            store = get_object_storage()
            for jid, blob in safe_jobs.items():
                key = _job_store_key(str(jid))
                body = json.dumps(blob, default=str).encode("utf-8")
                store.put_bytes(key, body)
        except Exception as exc:
            logger.warning("Could not sync background jobs to object storage: %s", exc)

    def _load_job_from_object_storage(self, job_id: str) -> Optional[Dict[str, Any]]:
        try:
            from app.services.object_storage.registry import get_object_storage

            store = get_object_storage()
            key = _job_store_key(job_id)
            if not store.exists(key):
                return None
            raw = store.get_bytes(key)
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, dict) and str(data.get("job_id", "")) == str(job_id):
                return data
        except Exception as exc:
            logger.warning("Could not load job %s from object storage: %s", job_id, exc)
        return None

    def _save_jobs_state(self) -> None:
        """Persist jobs to disk (best-effort). Running jobs are persisted as metadata only."""
        try:
            with self._lock:
                safe_jobs: Dict[str, Dict[str, Any]] = {}
                for job_id, job_data in self._jobs.items():
                    # Keep completed results for analyze/status retrieval after restart.
                    # json.dumps(default=str) keeps persistence best-effort.
                    safe_jobs[job_id] = _job_to_persistable(job_data)

            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "w", encoding="utf-8") as fp:
                json.dump(safe_jobs, fp, default=str)
            self._sync_jobs_to_object_storage(safe_jobs)
        except Exception as exc:
            logger.warning("Could not persist background jobs state: %s", exc)

    def _load_jobs_state(self) -> None:
        """
        Restore persisted jobs from disk.
        Pending/running jobs are marked as failed because worker threads do not survive restart.
        """
        try:
            if not os.path.exists(self._persist_path):
                return
            with open(self._persist_path, "r", encoding="utf-8") as fp:
                saved = json.load(fp) or {}
            if not isinstance(saved, dict):
                return

            restored_count = 0
            for job_id, job_data in saved.items():
                if not isinstance(job_data, dict):
                    continue
                status = str(job_data.get("status") or "")
                if status in (JobStatus.PENDING.value, JobStatus.RUNNING.value):
                    remote = self._load_job_from_object_storage(str(job_id))
                    if remote is not None:
                        rs = str(remote.get("status") or "")
                        if rs == JobStatus.COMPLETED.value:
                            # Worker finished and S3 has the result; recover even if
                            # local disk was not flushed (EKS / deploy race).
                            job_data = remote
                        elif rs == JobStatus.FAILED.value:
                            job_data = remote
                        else:
                            # pending/running on both sides after a process restart:
                            # the in-process worker is gone; fail stale jobs.
                            job_data["status"] = JobStatus.FAILED.value
                            job_data["error"] = (
                                "Job was interrupted by server restart. Please retry."
                            )
                            job_data["completed_at"] = time.time()
                    else:
                        job_data["status"] = JobStatus.FAILED.value
                        job_data["error"] = (
                            "Job was interrupted by server restart. Please retry."
                        )
                        job_data["completed_at"] = time.time()
                self._jobs[str(job_id)] = job_data
                restored_count += 1

            if restored_count:
                logger.info("Restored %s background job(s) from disk", restored_count)
        except Exception as exc:
            logger.warning("Could not restore background jobs state: %s", exc)
    
    def start_job(self, job_id: str, job_type: str, params: Dict[str, Any], job_function=None):
        """
        Start a background job

        Args:
            job_id: Unique job identifier
            job_type: Type of job (e.g., 'vif_correlation', 'segment_vif_correlation')
            params: Job parameters
            job_function: Function to execute (must accept params and return result)

        P3.2: When BROKER_URL is set the job is enqueued onto an external
        broker (Celery / RQ) instead of a daemon thread - this lets the
        FastAPI worker stay tiny while a separate worker pool drains heavy
        jobs. The broker abstraction degrades gracefully: if enqueue fails
        we fall back to the in-process thread implementation so a flaky
        broker never blocks ingest.
        """
        with self._lock:
            if job_id in self._jobs:
                raise ValueError(f"Job {job_id} already exists")

            self._jobs[job_id] = {
                'job_id': job_id,
                'job_type': job_type,
                'status': JobStatus.PENDING.value,
                'params': params,
                'result': None,
                'error': None,
                'progress': 0,
                'message': '',
                'step': 0,
                'started_at': None,
                'completed_at': None
            }
            self._save_jobs_state()

            if not job_function:
                return

            broker = _get_job_broker()
            if broker is not None:
                try:
                    broker.enqueue(job_id, job_function, self._jobs[job_id]['params'])
                    return
                except Exception as exc:
                    logger.warning(
                        "Broker enqueue failed for job %s (%s); falling back to thread",
                        job_id, exc,
                    )

            thread = threading.Thread(
                target=self._execute_job,
                args=(job_id, job_function),
                daemon=True,
            )
            thread.start()
            self._threads[job_id] = thread
    
    def _execute_job(self, job_id: str, job_function):
        """Execute job function and update status"""
        try:
            with self._lock:
                if job_id not in self._jobs:
                    return
                self._jobs[job_id]['status'] = JobStatus.RUNNING.value
                self._jobs[job_id]['started_at'] = time.time()
            self._save_jobs_state()
            
            # Execute the job function
            result = job_function(self._jobs[job_id]['params'])
            
            # Update with result
            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id]['status'] = JobStatus.COMPLETED.value
                    self._jobs[job_id]['result'] = result
                    self._jobs[job_id]['progress'] = 100
                    self._jobs[job_id]['completed_at'] = time.time()
            self._save_jobs_state()
                    
        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id]['status'] = JobStatus.FAILED.value
                    self._jobs[job_id]['error'] = str(e)
                    self._jobs[job_id]['completed_at'] = time.time()
            self._save_jobs_state()
    
    def persist_job_snapshot(self, job_id: str) -> None:
        """
        Persist a single job to shared object storage after in-memory progress updates
        so other API pods (EKS replicas) can poll status without seeing a stale snapshot.
        """
        try:
            with self._lock:
                job_data = self._jobs.get(job_id)
                if not job_data:
                    return
                blob = _job_to_persistable(job_data)
            from app.services.object_storage.registry import get_object_storage

            store = get_object_storage()
            store.put_bytes(_job_store_key(job_id), json.dumps(blob, default=str).encode("utf-8"))
        except Exception as exc:
            logger.warning("persist_job_snapshot failed for %s: %s", job_id, exc)

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Merge in-memory job with shared object storage so a poller pod always sees
        terminal state after the worker pod finishes (avoids stale ``running`` in RAM).
        """
        with self._lock:
            local = self._jobs.get(job_id)
        remote = self._load_job_from_object_storage(job_id)
        if local is None and remote is None:
            return None
        if local is None:
            chosen = remote
        elif remote is None:
            chosen = local
        elif _job_snapshot_fresher(remote, local):
            chosen = remote
        else:
            chosen = local
        with self._lock:
            self._jobs[job_id] = chosen
        return chosen.copy()
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job"""
        with self._lock:
            if job_id in self._jobs:
                if self._jobs[job_id]['status'] == JobStatus.RUNNING.value:
                    # Can't actually cancel running thread, but mark as cancelled
                    self._jobs[job_id]['status'] = JobStatus.FAILED.value
                    self._jobs[job_id]['error'] = "Cancelled by user"
                    self._save_jobs_state()
                    return True
            return False

    def cancel_active_jobs(
        self,
        *,
        dataset_id: Optional[str] = None,
        job_types: Optional[Set[str]] = None,
        reason: str = "Cancelled by user",
    ) -> List[str]:
        """Cancel pending/running jobs, optionally filtered by dataset and job type."""
        cancelled_job_ids: List[str] = []
        active_statuses = {JobStatus.PENDING.value, JobStatus.RUNNING.value}
        with self._lock:
            for job_id, job_data in self._jobs.items():
                status = str(job_data.get("status") or "")
                if status not in active_statuses:
                    continue
                if job_types and str(job_data.get("job_type") or "") not in job_types:
                    continue
                params = job_data.get("params") or {}
                if dataset_id and str(params.get("dataset_id") or "") != str(dataset_id):
                    continue
                job_data["status"] = JobStatus.FAILED.value
                job_data["error"] = reason
                job_data["completed_at"] = time.time()
                cancelled_job_ids.append(job_id)
            if cancelled_job_ids:
                self._save_jobs_state()
        return cancelled_job_ids
    
    def cleanup_old_jobs(self, max_age_seconds: int = 3600):
        """Clean up jobs older than max_age_seconds"""
        current_time = time.time()
        with self._lock:
            jobs_to_remove = []
            for job_id, job_data in self._jobs.items():
                completed_at = job_data.get('completed_at') or job_data.get('started_at')
                if completed_at and (current_time - completed_at) > max_age_seconds:
                    jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                del self._jobs[job_id]
                if job_id in self._threads:
                    del self._threads[job_id]
            
            if jobs_to_remove:
                logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")
                try:
                    from app.services.object_storage.registry import get_object_storage

                    store = get_object_storage()
                    for jid in jobs_to_remove:
                        try:
                            store.delete(_job_store_key(jid))
                        except Exception:
                            pass
                except Exception as exc:
                    logger.warning("Could not delete old job blobs from object storage: %s", exc)
                self._save_jobs_state()


# Singleton instance
background_job_manager = BackgroundJobManager()


# ---------------------------------------------------------------------------
# P3.2: Broker abstraction (Celery / RQ).
#
# Activation (env vars):
#   BROKER_URL   -> required. e.g. redis://redis:6379/0  or  amqp://...
#   BROKER_KIND  -> "celery" (default) | "rq". Both expect Redis-compatible URLs.
#
# When unset, _get_job_broker() returns None and BackgroundJobManager.start_job
# uses the original in-process thread path. The broker is therefore a strict
# upgrade - existing deployments behave identically.
#
# The functions executed by Celery / RQ workers must be importable on the
# worker side. We DO NOT try to ship arbitrary lambdas across processes;
# instead the contract is "the worker calls midas_jobs:run_job(payload)"
# which dispatches to a registered handler keyed by job_type. This keeps the
# pickling surface minimal and avoids the standard Celery footgun of trying
# to pickle closures captured from FastAPI request scope.
# ---------------------------------------------------------------------------

_JOB_HANDLERS: Dict[str, Any] = {}
_BROKER: Optional[Any] = None


def register_job_handler(job_type: str, handler) -> None:
    """Register a function to be invoked by remote workers for a job_type."""
    _JOB_HANDLERS[job_type] = handler
    logger.info("Registered remote job handler for job_type=%s", job_type)


def run_job_dispatch(job_type: str, params: Dict[str, Any]) -> Any:
    """Worker-side entry: look up the handler by job_type and execute."""
    handler = _JOB_HANDLERS.get(job_type)
    if handler is None:
        raise RuntimeError(
            f"No registered handler for job_type={job_type!r}. "
            "Workers must import the same handler-registration module the API does."
        )
    return handler(params)


class _CeleryBroker:
    kind = "celery"

    def __init__(self, broker_url: str) -> None:
        from celery import Celery
        self._app = Celery("midas_bg_jobs", broker=broker_url, backend=broker_url)
        # The actual handler is registered server-side via register_job_handler
        # and invoked by name from the worker.
        @self._app.task(name="midas.run_job")
        def _run_job(job_type: str, params: Dict[str, Any]):
            return run_job_dispatch(job_type, params)

        self._task = _run_job
        logger.info("Celery broker initialised: %s", broker_url)

    def enqueue(self, job_id: str, _job_function, params: Dict[str, Any]) -> None:
        # job_function is ignored on the API side - the worker dispatches via
        # run_job_dispatch using the job_type embedded in params.
        job_type = params.get("__job_type__")
        if not job_type:
            with background_job_manager._lock:
                job = background_job_manager._jobs.get(job_id)
                job_type = job.get("job_type") if job else None
        if not job_type:
            raise RuntimeError("Cannot enqueue: missing job_type")
        self._task.apply_async(args=(job_type, dict(params)), task_id=job_id)


class _RqBroker:
    kind = "rq"

    def __init__(self, broker_url: str) -> None:
        from redis import Redis
        from rq import Queue
        self._conn = Redis.from_url(broker_url)
        self._queue = Queue("midas-bg", connection=self._conn)
        logger.info("RQ broker initialised: %s", broker_url)

    def enqueue(self, job_id: str, _job_function, params: Dict[str, Any]) -> None:
        job_type = params.get("__job_type__")
        if not job_type:
            with background_job_manager._lock:
                job = background_job_manager._jobs.get(job_id)
                job_type = job.get("job_type") if job else None
        if not job_type:
            raise RuntimeError("Cannot enqueue: missing job_type")
        self._queue.enqueue_call(
            func=run_job_dispatch,
            args=(job_type, dict(params)),
            job_id=job_id,
            timeout=3600,
        )


def _get_job_broker() -> Optional[Any]:
    global _BROKER
    if _BROKER is not None:
        return _BROKER
    broker_url = os.environ.get("BROKER_URL")
    if not broker_url:
        return None
    kind = (os.environ.get("BROKER_KIND") or "celery").lower().strip()
    try:
        if kind == "rq":
            _BROKER = _RqBroker(broker_url)
        else:
            _BROKER = _CeleryBroker(broker_url)
        return _BROKER
    except Exception as exc:
        logger.warning(
            "Broker init failed (BROKER_URL=%s, kind=%s): %s. "
            "Falling back to in-process thread executor.",
            broker_url, kind, exc,
        )
        return None


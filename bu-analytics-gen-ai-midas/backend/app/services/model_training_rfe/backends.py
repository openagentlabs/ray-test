"""
Backend factory - single place that reads env vars and selects the right
(StorageBackend, JobStateStore, EventBus, JobQueue) tuple.

Selection rules:
  RFE_SCALING_MODE=local  (default)
    - InMemoryJobStateStore + InProcessEventBus + InProcessJobQueue
  RFE_SCALING_MODE=redis
    - RedisJobStateStore + RedisEventBus + RedisJobQueue (REDIS_URL required)
    - Falls back to local with a loud warning if redis is unreachable.

  RFE_STORAGE_BACKEND=filesystem (default)
    - FilesystemBackend (RFE_ARTIFACTS_DIR, default /app/rfe_artifacts)
  RFE_STORAGE_BACKEND=s3
    - S3Backend(RFE_S3_BUCKET, RFE_S3_PREFIX)

Singletons are cached at module scope so the API process reuses the same
backends for every request.
"""

from __future__ import annotations

import os
import threading
from typing import Optional, Tuple

from app.core.logging_config import get_logger

from .event_bus import EventBus, InProcessEventBus, RedisEventBus
from .job_queue import InProcessJobQueue, JobQueue, RedisJobQueue
from .job_state import InMemoryJobStateStore, JobStateStore, RedisJobStateStore
from .storage import FilesystemBackend, S3Backend, StorageBackend

_logger = get_logger(__name__)
_LOCK = threading.Lock()

_STORAGE: Optional[StorageBackend] = None
_JOB_STATE: Optional[JobStateStore] = None
_EVENT_BUS: Optional[EventBus] = None
_JOB_QUEUE: Optional[JobQueue] = None
_MODE: Optional[str] = None


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def _build_storage() -> StorageBackend:
    backend = _env("RFE_STORAGE_BACKEND", "filesystem").lower()
    if backend == "s3":
        bucket = _env("RFE_S3_BUCKET", "")
        prefix = _env("RFE_S3_PREFIX", "rfe_artifacts/")
        if not bucket:
            _logger.warning("RFE_STORAGE_BACKEND=s3 but RFE_S3_BUCKET not set; falling back to filesystem.")
        else:
            try:
                return S3Backend(bucket=bucket, prefix=prefix)
            except Exception as e:
                _logger.warning("S3Backend construction failed: %s; falling back to filesystem.", e)
    artifacts_dir = _env("RFE_ARTIFACTS_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "..", "rfe_artifacts"))
    artifacts_dir = os.path.abspath(artifacts_dir)
    return FilesystemBackend(root_dir=artifacts_dir)


def _try_redis_client():
    try:
        import redis  # type: ignore

        url = _env("REDIS_URL", "")
        if not url:
            return None
        client = redis.from_url(url)
        client.ping()
        return client
    except Exception as e:
        _logger.warning("Redis not reachable (%s); RFE will use local mode.", e)
        return None


def _build_triplet() -> Tuple[JobStateStore, EventBus, JobQueue, str]:
    mode = _env("RFE_SCALING_MODE", "local").lower()
    if mode == "redis":
        client = _try_redis_client()
        if client is not None:
            return (
                RedisJobStateStore(client),
                RedisEventBus(redis_client=client),
                RedisJobQueue(client),
                "redis",
            )
        # Fall through to local
    return (
        InMemoryJobStateStore(),
        InProcessEventBus(),
        InProcessJobQueue(),
        "local",
    )


def get_backends() -> Tuple[StorageBackend, JobStateStore, EventBus, JobQueue, str]:
    """
    Returns (storage, job_state, event_bus, job_queue, mode) singletons. Thread-safe.
    """
    global _STORAGE, _JOB_STATE, _EVENT_BUS, _JOB_QUEUE, _MODE
    with _LOCK:
        if _STORAGE is None:
            _STORAGE = _build_storage()
        if _JOB_STATE is None or _EVENT_BUS is None or _JOB_QUEUE is None:
            js, bus, queue, mode = _build_triplet()
            _JOB_STATE, _EVENT_BUS, _JOB_QUEUE, _MODE = js, bus, queue, mode
        return _STORAGE, _JOB_STATE, _EVENT_BUS, _JOB_QUEUE, _MODE or "local"


def reset_for_tests() -> None:
    """Exposed for unit tests to reset the module singletons."""
    global _STORAGE, _JOB_STATE, _EVENT_BUS, _JOB_QUEUE, _MODE
    with _LOCK:
        _STORAGE = None
        _JOB_STATE = None
        _EVENT_BUS = None
        _JOB_QUEUE = None
        _MODE = None

"""
In-process job queue = daemon thread per submitted job.

Local-mode semantics: we don't actually fan out to an external worker pool; we
spawn a daemon thread that imports the RFE service and runs it in the same
process. This keeps local dev dependency-free (no Redis required) while using
exactly the same `RfeService.run(job_id)` code path that the Redis worker uses.
"""

from __future__ import annotations

import queue
import threading
from typing import Callable, Optional

from app.core.logging_config import get_logger

from .base import JobQueue

_logger = get_logger(__name__)


class InProcessJobQueue(JobQueue):
    def __init__(self, executor: Optional[Callable[[str], None]] = None) -> None:
        """
        executor: function accepting a job_id and running it synchronously.
          Usually a thin lambda that instantiates RfeService with the local
          backends and calls `.run(job_id)`. Wired up in backends.py.
        """
        self._q: "queue.Queue[str]" = queue.Queue()
        self._executor = executor
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def set_executor(self, executor: Callable[[str], None]) -> None:
        self._executor = executor

    def enqueue(self, job_id: str) -> None:
        self._q.put(job_id)
        if self._executor is None:
            _logger.warning(f"InProcessJobQueue has no executor yet; job {job_id} will queue until set_executor is called")
            return
        t = threading.Thread(target=self._run_one, args=(job_id,), daemon=True, name=f"rfe-worker-{job_id[:8]}")
        with self._lock:
            self._threads[job_id] = t
        t.start()

    def _run_one(self, job_id: str) -> None:
        try:
            # Drain the matching item from the queue so size() is accurate.
            try:
                _ = self._q.get_nowait()
            except queue.Empty:
                pass
            if self._executor is not None:
                self._executor(job_id)
        except Exception as e:
            _logger.exception(f"RFE in-process execution failed for job {job_id}: {e}")
        finally:
            with self._lock:
                self._threads.pop(job_id, None)

    def dequeue(self, timeout: float = 5.0) -> Optional[str]:
        # Local mode doesn't use a pull model (threads are spawned on enqueue).
        # Provided so the worker.py loop still compiles under local mode; in that
        # case it will simply idle forever.
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def size(self) -> int:
        return self._q.qsize()

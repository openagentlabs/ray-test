"""In-process JobStateStore for local dev and the default single-replica mode."""

from __future__ import annotations

import threading
import time
from dataclasses import replace
from typing import Any, Dict, List, Optional

from .base import JobStateRow, JobStateStore


class InMemoryJobStateStore(JobStateStore):
    def __init__(self) -> None:
        self._rows: Dict[str, JobStateRow] = {}
        self._lock = threading.Lock()

    def create(self, row: JobStateRow) -> None:
        with self._lock:
            now = time.time()
            if not row.created_at:
                row.created_at = now
            row.updated_at = now
            self._rows[row.job_id] = row

    def get(self, job_id: str) -> Optional[JobStateRow]:
        with self._lock:
            row = self._rows.get(job_id)
            return replace(row) if row is not None else None

    def update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            row = self._rows.get(job_id)
            if row is None:
                return
            for k, v in fields.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            row.updated_at = time.time()

    def request_cancel(self, job_id: str) -> bool:
        with self._lock:
            row = self._rows.get(job_id)
            if row is None or row.status in ("completed", "failed", "cancelled"):
                return False
            row.cancel_flag = True
            row.updated_at = time.time()
            return True

    def list_active(self) -> List[JobStateRow]:
        with self._lock:
            return [replace(r) for r in self._rows.values() if r.status in ("pending", "running")]

    def delete(self, job_id: str) -> None:
        with self._lock:
            self._rows.pop(job_id, None)

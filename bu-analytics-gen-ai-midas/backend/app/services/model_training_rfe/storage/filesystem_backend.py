"""
Filesystem storage backend.

Default backend used whenever RFE_STORAGE_BACKEND=filesystem (the default). When the
artifact directory (`RFE_ARTIFACTS_DIR`) is mounted on a shared RWX volume (local
bind-mount in compose, EFS ReadWriteMany PVC on EKS), this single backend services
both API pods and worker pods with zero network round-trips.

Atomicity: `put_json` writes to `<key>.tmp` then `os.replace` to make the write
visible atomically to concurrent readers (POSIX guarantees this on the same
filesystem, which EFS satisfies).
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from .base import StorageBackend

_LOCK = threading.Lock()


class FilesystemBackend(StorageBackend):
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        os.makedirs(self.root_dir, exist_ok=True)

    def _dir(self, job_id: str) -> str:
        path = os.path.join(self.root_dir, job_id)
        os.makedirs(path, exist_ok=True)
        return path

    def _path(self, job_id: str, key: str) -> str:
        return os.path.join(self._dir(job_id), key)

    # ---------- JSON ----------
    def put_json(self, job_id: str, key: str, payload: Dict[str, Any]) -> None:
        final_path = self._path(job_id, key)
        tmp_path = final_path + ".tmp"
        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, default=str)
        os.replace(tmp_path, final_path)

    def get_json(self, job_id: str, key: str) -> Optional[Dict[str, Any]]:
        path = self._path(job_id, key)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def append_jsonl(self, job_id: str, key: str, row: Dict[str, Any]) -> None:
        path = self._path(job_id, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Process-wide lock is sufficient - multi-pod append ordering isn't required
        # for audit.jsonl (it's already per-job and events are timestamped).
        with _LOCK:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, default=str) + "\n")

    def read_jsonl(self, job_id: str, key: str) -> List[Dict[str, Any]]:
        path = self._path(job_id, key)
        if not os.path.exists(path):
            return []
        rows: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows

    # ---------- binary / parquet ----------
    def put_bytes(self, job_id: str, key: str, data: bytes) -> None:
        final_path = self._path(job_id, key)
        tmp_path = final_path + ".tmp"
        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        with open(tmp_path, "wb") as fh:
            fh.write(data)
        os.replace(tmp_path, final_path)

    def get_bytes(self, job_id: str, key: str) -> Optional[bytes]:
        path = self._path(job_id, key)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as fh:
            return fh.read()

    # ---------- listing ----------
    def list_keys(self, job_id: str, prefix: str = "") -> List[str]:
        root = self._dir(job_id)
        out: List[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                rel = os.path.relpath(os.path.join(dirpath, name), root)
                if rel.startswith(prefix):
                    out.append(rel)
        out.sort()
        return out

    def exists(self, job_id: str, key: str) -> bool:
        return os.path.exists(self._path(job_id, key))

    def job_path(self, job_id: str) -> str:
        return self._dir(job_id)

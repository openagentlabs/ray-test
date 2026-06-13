"""
StorageBackend ABC - one interface, many implementations (filesystem, S3, ...).

Every backend stores artifacts under a per-job namespace so concurrent jobs can't
collide. Keys are relative paths within that namespace.

Guarantees expected from implementations:
- `put_json` is atomic from a reader's perspective (rename/copy trick).
- `append_jsonl` is append-only and safe for concurrent writers on the same key
  (filesystem uses O_APPEND; S3 version emulates with per-append objects).
- `exists`/`get_json`/`list_iterations` are idempotent read-only operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class StorageBackend(ABC):
    """Pluggable object/file store for RFE run artifacts."""

    # ---------- JSON ----------
    @abstractmethod
    def put_json(self, job_id: str, key: str, payload: Dict[str, Any]) -> None: ...

    @abstractmethod
    def get_json(self, job_id: str, key: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def append_jsonl(self, job_id: str, key: str, row: Dict[str, Any]) -> None: ...

    @abstractmethod
    def read_jsonl(self, job_id: str, key: str) -> List[Dict[str, Any]]: ...

    # ---------- binary / parquet ----------
    @abstractmethod
    def put_bytes(self, job_id: str, key: str, data: bytes) -> None: ...

    @abstractmethod
    def get_bytes(self, job_id: str, key: str) -> Optional[bytes]: ...

    # ---------- listing ----------
    @abstractmethod
    def list_keys(self, job_id: str, prefix: str = "") -> List[str]: ...

    @abstractmethod
    def exists(self, job_id: str, key: str) -> bool: ...

    @abstractmethod
    def job_path(self, job_id: str) -> str:
        """
        A location handle (local path or s3 uri) callers can pass to pandas / pyarrow
        for heavy reads like parquet. Implementations should return a string that can
        be used with `pd.read_parquet`.
        """
        ...

"""Abstract object storage for uploaded datasets (local filesystem or S3)."""

from __future__ import annotations

import io
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional


class ObjectStorageBackend(ABC):
    """Strategy for persisting upload keys (CSV, Parquet, sidecar JSON)."""

    @property
    @abstractmethod
    def kind(self) -> str:
        """``local`` or ``s3`` for logging."""

    @abstractmethod
    def put_bytes(self, key: str, data: bytes) -> None:
        """Write object at logical key (relative path / object name)."""

    @abstractmethod
    def get_bytes(self, key: str) -> bytes:
        """Read full object."""

    @contextmanager
    def open_binary_stream(self, key: str) -> Iterator[BinaryIO]:
        """
        Streamed binary read for large objects (Parquet/CSV previews).
        Default implementation buffers the full object; prefer overrides on S3/local.
        """
        yield io.BytesIO(self.get_bytes(key))

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Whether key is present."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Best-effort delete."""

    @abstractmethod
    def list_csv_keys(self) -> List[str]:
        """List logical keys for ``*.csv`` objects (dataset discovery)."""

    def list_prefix(self, prefix: str) -> List[str]:
        """
        List logical keys whose path starts with ``prefix`` (slash-separated,
        relative to the storage root). Used for distributed chunked uploads
        (S3) and cleanup. Default: empty (local single-file layout does not
        require prefix listing).
        """
        return []

    def put_fileobj(self, key: str, fp: BinaryIO, *, length: Optional[int] = None) -> None:
        """Default: read fp to bytes and delegate to ``put_bytes``."""
        data = fp.read() if length is None else fp.read(length)
        self.put_bytes(key, data)

    def upload_file_path(self, key: str, path: Path) -> None:
        """Copy a file on disk into storage without loading whole file into memory (override on S3)."""
        self.put_bytes(key, Path(path).read_bytes())

    def head_object(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Cheap metadata lookup. Returns ``{"size": int, "etag": Optional[str],
        "last_modified": Optional[str]}`` or ``None`` when the key is missing.

        Used by the local sidecar cache to decide whether a previously
        downloaded copy is still current. Implementations should NOT read the
        object body; subclasses override with ``HEAD``/``stat``.
        """
        return None

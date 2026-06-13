"""Process-wide object storage backend (set at FastAPI startup)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.services.object_storage.contracts import ObjectStorageBackend
from app.services.object_storage.local_object_storage import LocalObjectStorage

_store: Optional[ObjectStorageBackend] = None


def set_object_storage(backend: ObjectStorageBackend) -> None:
    global _store
    _store = backend


def get_object_storage() -> ObjectStorageBackend:
    """Return configured backend, or local ``UPLOAD_DIR`` before startup runs."""
    global _store
    if _store is None:
        from app.core.config import settings

        _store = LocalObjectStorage(Path(settings.UPLOAD_DIR))
    return _store

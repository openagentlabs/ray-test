"""Local filesystem object storage under a single root directory."""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional

from app.services.object_storage.contracts import ObjectStorageBackend


class LocalObjectStorage(ObjectStorageBackend):
    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def kind(self) -> str:
        return "local"

    def _path(self, key: str) -> Path:
        # Prevent path traversal
        rel = key.replace("\\", "/").lstrip("/")
        p = (self._root / rel).resolve()
        try:
            p.relative_to(self._root.resolve())
        except ValueError as exc:
            raise ValueError(f"Invalid storage key: {key!r}") from exc
        return p

    def put_bytes(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    @contextmanager
    def open_binary_stream(self, key: str) -> Iterator[BinaryIO]:
        with open(self._path(key), "rb") as fp:
            yield fp

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def head_object(self, key: str) -> Optional[Dict[str, Any]]:
        p = self._path(key)
        if not p.is_file():
            return None
        st = p.stat()
        last_modified = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        return {
            "size": int(st.st_size),
            "etag": None,
            "last_modified": last_modified.isoformat(),
        }

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.is_file():
            p.unlink()

    def list_csv_keys(self) -> List[str]:
        if not self._root.exists():
            return []
        return sorted(
            f.name for f in self._root.iterdir() if f.is_file() and f.suffix.lower() == ".csv"
        )

    def list_prefix(self, prefix: str) -> List[str]:
        rel = prefix.replace("\\", "/").lstrip("/")
        base = (self._root / rel).resolve()
        try:
            base.relative_to(self._root.resolve())
        except ValueError:
            return []
        if not base.exists():
            return []
        keys: List[str] = []
        if base.is_file():
            keys.append(Path(rel).as_posix())
            return keys
        for p in base.rglob("*"):
            if p.is_file():
                try:
                    rel_path = p.relative_to(self._root.resolve())
                except ValueError:
                    continue
                keys.append(rel_path.as_posix())
        return sorted(keys)

    def upload_file_path(self, key: str, path: Path) -> None:
        dst = self._path(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dst)

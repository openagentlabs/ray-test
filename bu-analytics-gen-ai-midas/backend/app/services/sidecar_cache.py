"""
Local-disk LRU cache for object-storage sidecars used by the unique-id
validation fast path.

When ``ObjectStorageBackend.kind != "local"`` (e.g. S3 in EKS), the legacy
``materialize_unique_id_validation_path`` would download the parquet sidecar
to a fresh tempfile on every call and then ``os.unlink`` it. That made every
multiselect change in Step 1 pay a 5-15 s S3 round-trip on multi-GB datasets.

This cache:

* Downloads each ``(storage_key, version_token)`` pair at most once.
* Pins entries via a refcount while a caller is reading them, so eviction
  cannot pull the file out from under polars mid-scan.
* Serializes concurrent first-time downloads of the same key with a per-key
  lock so two simultaneous validates do not double-download.
* Bounds total disk usage with an LRU + ``max_bytes`` ceiling.

Configuration env vars:

* ``MIDAS_SIDECAR_CACHE_DIR`` -- root directory (default ``/tmp/midas-sidecars``).
* ``MIDAS_SIDECAR_CACHE_MAX_BYTES`` -- soft ceiling (default 8 GiB).

The cache is purely process-local. Cross-worker / cross-replica caching is
out of scope; the dataset_id-based result cache (``AnalyticsResultCache``)
provides Redis L2 for the cheap part (the JSON response), which is what
matters for "instant" repeats of the same column selection.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import threading
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from app.core.logging_config import get_logger
from app.services.object_storage.contracts import ObjectStorageBackend

logger = get_logger(__name__)


_KNOWN_SUFFIXES = (".parquet", ".csv", ".json")


def _safe_basename(key: str, version: str) -> str:
    """Stable on-disk filename derived from (key, version_token).

    Hashing prevents path-traversal and key-charset issues. The extension is
    preserved so polars / pyarrow can pick the right reader from the path.
    """
    digest = hashlib.sha1(f"{key}|{version}".encode("utf-8")).hexdigest()
    suffix = ""
    for sfx in _KNOWN_SUFFIXES:
        if key.endswith(sfx):
            suffix = sfx
            break
    return f"{digest}{suffix}"


@dataclass
class _CacheEntry:
    path: Path
    size: int
    version: str
    ref_count: int = 0


_EntryKey = Tuple[str, str]  # (storage_key, version_token)


class SidecarCache:
    """Bounded local-disk cache for read-only object-storage sidecars."""

    def __init__(self, root: Path, max_bytes: int) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._max_bytes = max(0, int(max_bytes))
        self._entries: "OrderedDict[_EntryKey, _CacheEntry]" = OrderedDict()
        self._global_lock = threading.Lock()
        self._key_locks: Dict[str, threading.Lock] = {}
        self._total_bytes = 0
        self._hits = 0
        self._misses = 0

    @property
    def root(self) -> Path:
        return self._root

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    def _resolve_meta(
        self, store: ObjectStorageBackend, key: str
    ) -> Tuple[int, str]:
        """Return (size_bytes, opaque_version_token) for cache invalidation.

        ETag is preferred (S3); falls back to last_modified, then size; then
        a constant when the storage backend does not implement ``head_object``.
        """
        meta = None
        try:
            meta = store.head_object(key)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("sidecar_cache: head_object(%s) failed: %s", key, exc)
        if not meta:
            return 0, "0"
        size = int(meta.get("size") or 0)
        token = (
            meta.get("etag")
            or meta.get("last_modified")
            or str(size)
            or "0"
        )
        return size, str(token)

    def _get_key_lock(self, key: str) -> threading.Lock:
        with self._global_lock:
            lock = self._key_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._key_locks[key] = lock
            return lock

    @contextmanager
    def acquire(
        self, store: ObjectStorageBackend, key: str
    ) -> Iterator[Path]:
        """Pin a local copy of ``key`` and yield its path.

        Refcount is incremented on entry and decremented on exit. The cached
        file is guaranteed to exist for the duration of the ``with`` block.
        """
        path, entry_key = self._acquire(store, key)
        try:
            yield path
        finally:
            self._release(entry_key)

    def _acquire(
        self, store: ObjectStorageBackend, key: str
    ) -> Tuple[Path, _EntryKey]:
        size, version = self._resolve_meta(store, key)
        entry_key: _EntryKey = (key, version)

        # Fast path: entry already cached and on disk.
        with self._global_lock:
            entry = self._entries.get(entry_key)
            if entry is not None and entry.path.is_file():
                entry.ref_count += 1
                self._entries.move_to_end(entry_key)
                self._hits += 1
                return entry.path, entry_key
            # Tentative miss; the per-key lock below handles re-check.
            self._misses += 1

        # Slow path: download exactly once per key, even under concurrency.
        kl = self._get_key_lock(key)
        with kl:
            with self._global_lock:
                entry = self._entries.get(entry_key)
                if entry is not None and entry.path.is_file():
                    entry.ref_count += 1
                    self._entries.move_to_end(entry_key)
                    # Roll back the optimistic miss we recorded above.
                    self._hits += 1
                    self._misses = max(0, self._misses - 1)
                    return entry.path, entry_key
                local_path = self._root / _safe_basename(key, version)
                tmp_path = local_path.with_suffix(local_path.suffix + ".part")

            local_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                logger.info(
                    "sidecar_cache: download key=%s version=%s expected_bytes=%s -> %s",
                    key,
                    version,
                    size,
                    local_path,
                )
                with store.open_binary_stream(key) as src, open(tmp_path, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=4 * 1024 * 1024)
                actual_size = tmp_path.stat().st_size
                os.replace(tmp_path, local_path)
            except Exception:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass
                raise

            with self._global_lock:
                # If a different version is already cached for the same key,
                # drop it (only when nobody is holding it).
                stale = [
                    k
                    for k in list(self._entries.keys())
                    if k[0] == key and k[1] != version
                ]
                for sk in stale:
                    se = self._entries.get(sk)
                    if se is not None and se.ref_count == 0:
                        self._evict_entry(sk, se)

                entry = _CacheEntry(
                    path=local_path,
                    size=actual_size,
                    version=version,
                    ref_count=1,
                )
                self._entries[entry_key] = entry
                self._total_bytes += actual_size
                self._enforce_max_bytes()
                return local_path, entry_key

    def _release(self, entry_key: _EntryKey) -> None:
        with self._global_lock:
            entry = self._entries.get(entry_key)
            if entry is not None and entry.ref_count > 0:
                entry.ref_count -= 1

    def _enforce_max_bytes(self) -> None:
        """Evict idle entries (ref_count==0) oldest-first until under the cap.

        Caller MUST hold ``self._global_lock``.
        """
        if self._max_bytes <= 0:
            return
        if self._total_bytes <= self._max_bytes:
            return
        candidates = [
            (k, v) for k, v in list(self._entries.items()) if v.ref_count == 0
        ]
        for k, v in candidates:
            if self._total_bytes <= self._max_bytes:
                break
            self._evict_entry(k, v)

    def _evict_entry(self, entry_key: _EntryKey, entry: _CacheEntry) -> None:
        """Remove a single entry. Caller MUST hold ``self._global_lock``."""
        try:
            if entry.path.exists():
                entry.path.unlink()
        except OSError as exc:
            logger.warning(
                "sidecar_cache: failed to unlink %s during eviction: %s",
                entry.path,
                exc,
            )
        self._entries.pop(entry_key, None)
        self._total_bytes = max(0, self._total_bytes - entry.size)
        logger.debug(
            "sidecar_cache: evicted key=%s version=%s freed_bytes=%s",
            entry_key[0],
            entry_key[1],
            entry.size,
        )

    def invalidate_key(self, key: str) -> int:
        """Drop every cached entry for ``key`` regardless of version.

        Best-effort; entries currently in use (ref_count > 0) are skipped.
        Returns the number of entries removed.
        """
        removed = 0
        with self._global_lock:
            stale = [
                k
                for k in list(self._entries.keys())
                if k[0] == key
            ]
            for sk in stale:
                se = self._entries.get(sk)
                if se is not None and se.ref_count == 0:
                    self._evict_entry(sk, se)
                    removed += 1
        return removed

    def stats(self) -> Dict[str, Any]:
        with self._global_lock:
            return {
                "entries": len(self._entries),
                "size_bytes": self._total_bytes,
                "max_bytes": self._max_bytes,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": (
                    self._hits / max(1, self._hits + self._misses)
                ),
                "root": str(self._root),
            }


_singleton: Optional[SidecarCache] = None
_singleton_lock = threading.Lock()


def get_sidecar_cache() -> SidecarCache:
    """Return a process-wide ``SidecarCache`` built lazily from env vars."""
    global _singleton
    if _singleton is not None:
        return _singleton
    with _singleton_lock:
        if _singleton is None:
            root = Path(
                os.environ.get("MIDAS_SIDECAR_CACHE_DIR", "/tmp/midas-sidecars")
            )
            try:
                max_bytes = int(
                    os.environ.get(
                        "MIDAS_SIDECAR_CACHE_MAX_BYTES",
                        str(8 * 1024 * 1024 * 1024),
                    )
                )
            except ValueError:
                max_bytes = 8 * 1024 * 1024 * 1024
            _singleton = SidecarCache(root=root, max_bytes=max_bytes)
            logger.info(
                "sidecar_cache initialized: root=%s max_bytes=%d",
                root,
                max_bytes,
            )
    return _singleton


def reset_sidecar_cache_for_testing(
    cache: Optional[SidecarCache] = None,
) -> None:
    """Test helper: replace the process-wide cache. Do not call in prod."""
    global _singleton
    with _singleton_lock:
        _singleton = cache

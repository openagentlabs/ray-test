"""
Tests for the S3 fast-path in ``chunked_upload._s3_finalize_sync``.

The previous implementation finalized a chunked upload by:

  1. Sequentially ``GetObject``-ing every part.
  2. Writing all bytes to a local temp file.
  3. ``PutObject``-ing the assembled file back to S3.

For a 2.5 GB / 313-part upload that sequence took ~80-150 s end-to-end and
routinely exceeded the ALB idle timeout, surfacing as a 504 Gateway Timeout
on ``POST /api/v1/upload-chunked/{id}/finalize``.

The fix is server-side concatenation via S3's
``CreateMultipartUpload`` + ``UploadPartCopy`` + ``CompleteMultipartUpload``:
bytes never transit our network, the same finalize completes in ~5-7 s, and
no local temp file is needed. These tests lock in:

* The fast path is used when every non-last part is at least 5 MiB.
* The fast path skips the local-disk roundtrip (no file written under
  ``UPLOAD_DIR/<storage_key>``).
* The bytes-copy fallback runs when a non-last part is below 5 MiB
  (the only case S3 multipart-copy refuses).
* The bytes-copy fallback also runs when ``assemble_via_multipart_copy``
  raises -- e.g. transient S3 error or stale credentials -- and the
  assembled file is still byte-perfect.
* Cleanup uses the batched ``delete_keys_batch`` when available.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest


try:
    from app.api import chunked_upload as cu  # noqa: F401

    _CHUNKED_IMPORTABLE = True
except Exception:  # pragma: no cover
    _CHUNKED_IMPORTABLE = False


pytestmark = pytest.mark.skipif(
    not _CHUNKED_IMPORTABLE,
    reason="chunked_upload module not importable in this environment",
)


class _MockS3Store:
    """In-memory store that quacks like ``S3ObjectStorage`` for finalize.

    Keeps every PUT in a dict keyed by logical key, exposes ``kind == "s3"``
    so ``_s3_finalize_sync`` takes the S3 branch, and records every call to
    ``assemble_via_multipart_copy`` / ``delete_keys_batch`` so tests can
    assert which path was taken.
    """

    kind = "s3"

    def __init__(self) -> None:
        self._objects: Dict[str, bytes] = {}
        self.assemble_calls: List[Tuple[str, List[str]]] = []
        self.delete_keys_batch_calls: List[List[str]] = []
        self.upload_file_path_calls: List[Tuple[str, Path]] = []
        self.assemble_raises: bool = False

    def put_bytes(self, key: str, data: bytes) -> None:
        self._objects[key] = bytes(data)

    def get_bytes(self, key: str) -> bytes:
        return self._objects[key]

    def exists(self, key: str) -> bool:
        return key in self._objects

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    def list_csv_keys(self) -> List[str]:
        return sorted(k for k in self._objects if k.endswith(".csv"))

    def list_prefix(self, prefix: str) -> List[str]:
        return sorted(k for k in self._objects if k.startswith(prefix))

    def upload_file_path(self, key: str, path: Path) -> None:
        self.upload_file_path_calls.append((key, Path(path)))
        self._objects[key] = Path(path).read_bytes()

    def head_object(self, key: str) -> Optional[Dict[str, Any]]:
        if key not in self._objects:
            return None
        return {
            "size": len(self._objects[key]),
            "etag": None,
            "last_modified": None,
        }

    def assemble_via_multipart_copy(
        self,
        target_key: str,
        sources: List[str],
        *,
        max_concurrency: int = 10,
    ) -> Dict[str, Any]:
        self.assemble_calls.append((target_key, list(sources)))
        if self.assemble_raises:
            raise RuntimeError("simulated S3 multipart-copy failure")
        # Simulate the S3 server-side concatenation by joining bytes locally.
        # The point is that we never actually transit through the bytes-copy
        # fallback path -- the test asserts that.
        out = b"".join(self._objects[s] for s in sources)
        self._objects[target_key] = out
        return {"key": target_key, "etag": "mock-etag"}

    def delete_keys_batch(self, keys: List[str]) -> int:
        self.delete_keys_batch_calls.append(list(keys))
        for k in keys:
            self._objects.pop(k, None)
        return len(keys)


def _seed_s3_session(
    store: _MockS3Store,
    upload_id: str,
    filename: str,
    parts: List[bytes],
) -> int:
    """Simulate a completed S3-backed chunked upload: write the session JSON
    + every part object the way ``_s3_append_chunk_sync`` would have."""
    total_size = sum(len(p) for p in parts)
    session_key = f"midas_chunked_sessions/{upload_id}.json"
    store.put_bytes(
        session_key,
        json.dumps(
            {
                "upload_id": upload_id,
                "filename": filename,
                "total_size": total_size,
                "created_ts": time.time(),
            }
        ).encode("utf-8"),
    )
    cursor = 0
    for body in parts:
        start = cursor
        end = start + len(body) - 1
        pk = f"midas_chunked_parts/{upload_id}/{start:016d}_{end:016d}.bin"
        store.put_bytes(pk, body)
        cursor = end + 1
    return total_size


@pytest.fixture
def s3_finalize_env(monkeypatch, tmp_path):
    """Wire ``_s3_finalize_sync`` to a fresh ``_MockS3Store`` in a clean
    UPLOAD_DIR. Yields ``(store, tmp_path)``."""
    if not _CHUNKED_IMPORTABLE:
        pytest.skip("chunked_upload module not importable")

    from app.api import chunked_upload as cu_module
    from app.core import config as core_config
    from app.services.dataset_service import dataset_manager
    from app.services.object_storage import registry as _store_registry

    monkeypatch.setattr(core_config.settings, "UPLOAD_DIR", str(tmp_path))
    cu_module.CHUNK_DIR = tmp_path / "_chunked"
    cu_module.CHUNK_DIR.mkdir(parents=True, exist_ok=True)

    store = _MockS3Store()
    _store_registry.set_object_storage(store)

    monkeypatch.setattr(dataset_manager, "upload_dir", tmp_path)
    dataset_manager.datasets.clear()

    yield store, tmp_path


def _five_mib_block(seed: int = 0) -> bytes:
    """Deterministic exactly-5 MiB byte block. The seed lets each block
    contain different bytes so we can detect order/concatenation bugs."""
    fill = chr(ord("a") + (seed % 26)).encode("ascii")
    return fill * (5 * 1024 * 1024)


def test_s3_finalize_uses_server_side_multipart_copy_when_parts_qualify(
    s3_finalize_env,
):
    """Every non-last part >= 5 MiB -> server-side multipart copy fast path.

    The test verifies that:
      - ``assemble_via_multipart_copy`` was called exactly once with the
        sources in ascending byte-offset order.
      - The assembled object exists at ``storage_key`` in the store.
      - No local file is written under ``UPLOAD_DIR/<storage_key>`` (the
        old code path's biggest cost).
      - Parts are batch-deleted via ``delete_keys_batch`` instead of N
        individual ``DeleteObject`` calls.
      - The dataset is registered with ``storage_key`` (not a local path).
    """
    store, upload_dir = s3_finalize_env
    from app.api.chunked_upload import _s3_finalize_sync
    from app.services.dataset_service import dataset_manager

    upload_id = "test-fast-path"
    parts = [_five_mib_block(0), _five_mib_block(1), b"tail!"]
    total_size = _seed_s3_session(store, upload_id, "data.csv", parts)

    result = _s3_finalize_sync(upload_id)

    assert result["success"] is True
    assert result["filename"] == "data.csv"
    assert result["total_size"] == total_size
    storage_key = result["storage_key"]
    assert storage_key.endswith("_data.csv")

    assert len(store.assemble_calls) == 1, (
        "fast path must call assemble_via_multipart_copy exactly once "
        f"(got {len(store.assemble_calls)})"
    )
    target, sources = store.assemble_calls[0]
    assert target == storage_key
    assert len(sources) == len(parts)
    expected_prefix = f"midas_chunked_parts/{upload_id}/"
    assert all(src.startswith(expected_prefix) for src in sources)
    assert sources == sorted(sources), (
        "sources must be in ascending offset order"
    )

    # Fast path skips the local-disk roundtrip
    assert not (upload_dir / storage_key).exists(), (
        "fast path must not write the assembled CSV to local UPLOAD_DIR"
    )
    # Fast path skips upload_file_path
    assert store.upload_file_path_calls == [], (
        "fast path must not re-upload the assembled file to S3"
    )

    # Batch cleanup, not 313 individual deletes
    assert len(store.delete_keys_batch_calls) == 1
    assert sorted(store.delete_keys_batch_calls[0]) == sorted(sources)

    info = dataset_manager.get_dataset_info(result["dataset_id"])
    assert info is not None
    assert info["storage_key"] == storage_key
    assert info["filename"] == "data.csv"

    # Assembled object actually exists in the store at the storage_key
    assembled = store.get_bytes(storage_key)
    expected = b"".join(parts)
    assert assembled == expected


def test_s3_finalize_falls_back_when_non_last_part_below_5_mib(s3_finalize_env):
    """If a non-last part is below the S3 multipart minimum (5 MiB) the fast
    path is skipped and the bytes-copy fallback assembles correctly.

    The fallback writes to local UPLOAD_DIR and then calls
    ``upload_file_path`` so the canonical bytes still live in object storage.
    """
    store, upload_dir = s3_finalize_env
    from app.api.chunked_upload import _s3_finalize_sync

    upload_id = "test-small-part"
    # Middle part is 1 KiB -- well under the 5 MiB minimum, forcing fallback.
    parts = [_five_mib_block(0), b"x" * 1024, b"tail!"]
    total_size = _seed_s3_session(store, upload_id, "data.csv", parts)

    result = _s3_finalize_sync(upload_id)

    assert result["success"] is True
    assert result["total_size"] == total_size
    storage_key = result["storage_key"]

    # The fast path must not have run
    assert store.assemble_calls == [], (
        "non-last part < 5 MiB must skip server-side multipart copy"
    )
    # Bytes-copy path writes a local file then uploads it
    assert (upload_dir / storage_key).exists()
    assert (upload_dir / storage_key).read_bytes() == b"".join(parts)
    assert len(store.upload_file_path_calls) == 1
    # The S3 object also has the bytes (so downstream by-id routes resolve)
    assert store.get_bytes(storage_key) == b"".join(parts)


def test_s3_finalize_falls_back_when_multipart_copy_raises(s3_finalize_env):
    """``assemble_via_multipart_copy`` failures (transient 5xx, expired creds,
    aborted upload) fall through to the bytes-copy path. The user's response
    is still 200 with a byte-perfect assembled file."""
    store, upload_dir = s3_finalize_env
    from app.api.chunked_upload import _s3_finalize_sync

    upload_id = "test-assemble-raises"
    parts = [_five_mib_block(0), _five_mib_block(1), b"tail!"]
    _seed_s3_session(store, upload_id, "data.csv", parts)
    store.assemble_raises = True

    result = _s3_finalize_sync(upload_id)

    storage_key = result["storage_key"]
    # Fast path was attempted exactly once before falling back
    assert len(store.assemble_calls) == 1
    # Bytes-copy fallback wrote the assembled file locally + back to S3
    assert (upload_dir / storage_key).read_bytes() == b"".join(parts)
    assert len(store.upload_file_path_calls) == 1
    assert store.get_bytes(storage_key) == b"".join(parts)


def test_s3_finalize_rejects_incomplete_intervals(s3_finalize_env):
    """If the part interval set doesn't cover [0, total_size) the finalize
    must raise ChunkedUploadHttpError(409). Lock that in so the new fast path
    can't accidentally bypass the integrity check."""
    store, _upload_dir = s3_finalize_env
    from app.api.chunked_upload import _s3_finalize_sync, ChunkedUploadHttpError

    upload_id = "test-incomplete"
    # Lie about total_size: the session says 100 MiB but only 5 MiB worth
    # of parts are present.
    session_key = f"midas_chunked_sessions/{upload_id}.json"
    store.put_bytes(
        session_key,
        json.dumps(
            {
                "upload_id": upload_id,
                "filename": "data.csv",
                "total_size": 100 * 1024 * 1024,
                "created_ts": time.time(),
            }
        ).encode("utf-8"),
    )
    body = _five_mib_block(0)
    pk = f"midas_chunked_parts/{upload_id}/{0:016d}_{len(body) - 1:016d}.bin"
    store.put_bytes(pk, body)

    with pytest.raises(ChunkedUploadHttpError) as excinfo:
        _s3_finalize_sync(upload_id)

    assert excinfo.value.status_code == 409
    assert "incomplete" in excinfo.value.detail.lower()
    # And no garbage is left behind at the future storage_key
    csv_keys = [k for k in store._objects if k.endswith(".csv")]
    assert csv_keys == []


def test_s3_finalize_rejects_overlapping_parts(s3_finalize_env):
    """Two parts whose byte-ranges overlap should fail finalize. Otherwise
    the multipart copy might succeed but the assembled file would have
    duplicated bytes."""
    store, _ = s3_finalize_env
    from app.api.chunked_upload import _s3_finalize_sync, ChunkedUploadHttpError

    upload_id = "test-overlap"
    block_a = _five_mib_block(0)
    block_b = _five_mib_block(1)

    session_key = f"midas_chunked_sessions/{upload_id}.json"
    store.put_bytes(
        session_key,
        json.dumps(
            {
                "upload_id": upload_id,
                "filename": "data.csv",
                "total_size": len(block_a) + len(block_b),
                "created_ts": time.time(),
            }
        ).encode("utf-8"),
    )
    # Part A: 0 .. len(A)-1
    pk_a = (
        f"midas_chunked_parts/{upload_id}/"
        f"{0:016d}_{len(block_a) - 1:016d}.bin"
    )
    store.put_bytes(pk_a, block_a)
    # Part B: starts at len(A) - 100 (overlap by 100 bytes!), goes to total-1.
    overlap_start = len(block_a) - 100
    overlap_end = len(block_a) + len(block_b) - 1
    pk_b = (
        f"midas_chunked_parts/{upload_id}/"
        f"{overlap_start:016d}_{overlap_end:016d}.bin"
    )
    store.put_bytes(pk_b, b"y" * (overlap_end - overlap_start + 1))

    with pytest.raises(ChunkedUploadHttpError) as excinfo:
        _s3_finalize_sync(upload_id)

    assert excinfo.value.status_code == 409
    detail = excinfo.value.detail.lower()
    assert "gap" in detail or "overlap" in detail


def test_can_use_s3_multipart_copy_size_check():
    """Pure unit check on the size-validation helper."""
    from app.api.chunked_upload import _can_use_s3_multipart_copy

    five_mib = 5 * 1024 * 1024
    # All parts >= 5 MiB except the last (which can be anything): allowed.
    triples = [
        (0, five_mib - 1, "p0"),
        (five_mib, 2 * five_mib - 1, "p1"),
        (2 * five_mib, 2 * five_mib + 99, "p2"),  # tiny last part -- fine
    ]
    assert _can_use_s3_multipart_copy(triples) is True

    # Non-last part < 5 MiB: refused.
    bad = [
        (0, five_mib - 1, "p0"),
        (five_mib, five_mib + 1023, "p1"),  # 1 KiB middle part
        (five_mib + 1024, five_mib + 1024 + 9, "p2"),
    ]
    assert _can_use_s3_multipart_copy(bad) is False

    # Empty list: refused.
    assert _can_use_s3_multipart_copy([]) is False

    # Single part of any size: allowed (it IS the last part).
    assert _can_use_s3_multipart_copy([(0, 99, "p0")]) is True

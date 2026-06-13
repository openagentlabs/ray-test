"""
Chunked / resumable CSV upload (P2.5).

Three-step protocol so the browser does NOT need to keep an entire 2 GB
CSV in a single PUT (which Azure Front Door / API Gateway will time out
at 100-300s):

    POST   /upload-chunked/init      -> upload_id, chunk_size_hint
    PATCH  /upload-chunked/{id}      -> Content-Range: bytes A-B/Total
    POST   /upload-chunked/{id}/finalize -> { dataset_id, file_path }

Properties:
  - The server pre-allocates the destination file at ``init`` and keeps
    a single open file descriptor in the upload state. Each PATCH writes
    its byte range with ``os.pwrite`` (POSIX-atomic, position-independent),
    so multiple chunks can be uploaded *in parallel* without any per-upload
    serialization lock. Retries that re-send the same range are idempotent
    (``pwrite`` overwrites the same bytes).
  - Received byte ranges are tracked as a merged interval set; "complete"
    is determined at finalize from interval coverage, not a high-water
    counter -- safe even if chunks arrive out of order.
  - finalize moves the assembled file into the standard storage layer
    (`save_uploaded_file_streaming`'s output location), so the rest of
    the pipeline (`/upload`, `/analyze-dataset`, etc.) doesn't need to
    care that the upload was chunked. The post-finalize streaming Parquet
    conversion is offloaded to the shared executor so it never blocks
    the FastAPI event loop.
  - Reaper: uploads with no activity for >1h are GC'd off disk.

Out of scope:
  - Server-side resume across worker restarts (would need durable state).
    The temp file survives restarts; the in-memory upload registry does
    NOT, so a fresh init is required after a worker recycle.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.api._chunked_upload_intervals import (
    Interval,
    add_interval as _add_interval,
    bytes_received as _bytes_received,
    is_complete as _is_complete,
)
from app.api.auth_routes import get_current_user_dependency
from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.metrics import time_stage
from app.services.dataset_service import dataset_manager
from app.services.object_storage.registry import get_object_storage

logger = get_logger(__name__)
router = APIRouter()


class ChunkedUploadHttpError(Exception):
    """Raised from sync S3 helpers; mapped to ``HTTPException`` in async routes."""

    __slots__ = ("status_code", "detail")

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


# EKS / multi-replica: in-memory ``_uploads`` only works when all PATCHes hit
# the same pod. For S3-backed deployments we persist each chunk as its own
# object so any replica can accept writes and any replica can finalize.
S3_CHUNKED_SESSION_PREFIX = "midas_chunked_sessions"
S3_CHUNKED_PARTS_PREFIX = "midas_chunked_parts"

CHUNK_DIR = Path(settings.UPLOAD_DIR) / "_chunked"
CHUNK_DIR.mkdir(parents=True, exist_ok=True)

# Suggested chunk size for the client. 8 MiB plays well with both
# Azure Front Door (max 100 MiB per request) and slow last-mile networks,
# while still letting parallel-6 saturate a 100 MB/s pipe (~48 MiB in flight).
CHUNK_SIZE_HINT = 8 * 1024 * 1024
UPLOAD_TTL_S = 3600  # GC partially-uploaded files after 1h of inactivity

# S3 multipart-upload requires every part except the last to be at least 5 MiB.
# When the chunked-upload client respects ``CHUNK_SIZE_HINT`` (default 8 MiB)
# this is always satisfied, and ``_s3_finalize_sync`` can use the server-side
# fast path. Smaller parts force the bytes-copy fallback.
S3_MULTIPART_MIN_PART_BYTES = 5 * 1024 * 1024
# Boto3's default connection pool is 10; matching that keeps UploadPartCopy
# parallelism saturated without adding queue contention.
S3_MULTIPART_COPY_MAX_CONCURRENCY = 10


def _s3_session_key(upload_id: str) -> str:
    return f"{S3_CHUNKED_SESSION_PREFIX}/{upload_id}.json"


def _s3_parts_prefix(upload_id: str) -> str:
    return f"{S3_CHUNKED_PARTS_PREFIX}/{upload_id}/"


def _s3_part_key(upload_id: str, start: int, end: int) -> str:
    return f"{S3_CHUNKED_PARTS_PREFIX}/{upload_id}/{start:016d}_{end:016d}.bin"


def _parse_s3_part_range(key: str) -> Optional[Tuple[int, int]]:
    if not key.endswith(".bin"):
        return None
    base = key.rsplit("/", 1)[-1][:-4]
    if "_" not in base:
        return None
    a, b = base.split("_", 1)
    return int(a), int(b)


def _delete_prefix_sync(store, prefix: str) -> None:
    for k in store.list_prefix(prefix):
        try:
            store.delete(k)
        except Exception as exc:
            logger.debug("delete_prefix skip %s: %s", k, exc)


def _gc_s3_stale_sessions_sync() -> None:
    store = get_object_storage()
    if store.kind != "s3":
        return
    now = time.time()
    for sk in store.list_prefix(f"{S3_CHUNKED_SESSION_PREFIX}/"):
        if not sk.endswith(".json"):
            continue
        try:
            meta = json.loads(store.get_bytes(sk).decode("utf-8"))
            created = float(meta.get("created_ts", 0) or 0)
            if now - created <= UPLOAD_TTL_S:
                continue
            uid = str(meta.get("upload_id") or "") or sk.rsplit("/", 1)[-1].replace(".json", "")
            logger.info("chunked-upload S3 GC: dropping stale upload %s", uid)
            _delete_prefix_sync(store, _s3_parts_prefix(uid))
            store.delete(sk)
        except Exception as exc:
            logger.debug("chunked-upload S3 GC skip %s: %s", sk, exc)


def _parse_content_range_plain(header: str) -> tuple[int, int, int]:
    if not header or not header.startswith("bytes "):
        raise ValueError("Missing/invalid Content-Range header")
    spec = header[len("bytes ") :]
    rng, _, total = spec.partition("/")
    start_s, _, end_s = rng.partition("-")
    try:
        start = int(start_s)
        end = int(end_s)
        total_i = int(total)
    except ValueError as exc:
        raise ValueError(f"Bad Content-Range: {exc}") from exc
    if start < 0 or end < start or total_i <= 0:
        raise ValueError("Content-Range bounds invalid")
    return start, end, total_i


def _s3_append_chunk_sync(upload_id: str, content_range: str, body: bytes) -> dict:
    store = get_object_storage()
    sk = _s3_session_key(upload_id)
    if not store.exists(sk):
        raise FileNotFoundError("Unknown or expired upload_id")
    start, end, total_hdr = _parse_content_range_plain(content_range)
    meta = json.loads(store.get_bytes(sk).decode("utf-8"))
    total_size = int(meta["total_size"])
    if total_hdr != total_size:
        raise ChunkedUploadHttpError(409, "total_size mismatch with init")
    if end >= total_size:
        raise ChunkedUploadHttpError(416, "Range past total_size")
    expected = end - start + 1
    if len(body) != expected:
        raise ChunkedUploadHttpError(
            400, f"Body length {len(body)} != range size {expected}"
        )

    store.put_bytes(_s3_part_key(upload_id, start, end), body)

    part_prefix = _s3_parts_prefix(upload_id)
    keys = [k for k in store.list_prefix(part_prefix) if k.endswith(".bin")]
    intervals: List[Interval] = []
    for k in keys:
        pr = _parse_s3_part_range(k)
        if pr:
            s, e_inc = pr
            _add_interval(intervals, s, e_inc + 1)
    received = _bytes_received(intervals)
    complete = _is_complete(intervals, total_size)
    return {
        "upload_id": upload_id,
        "bytes_received": received,
        "total_size": total_size,
        "complete": complete,
    }


def _can_use_s3_multipart_copy(triples: List[Tuple[int, int, str]]) -> bool:
    """Server-side ``UploadPartCopy`` requires every part except the last to be
    at least 5 MiB. With the default 8 MiB chunk hint this is always true, but
    a misbehaving client (or the tail of a small upload split into multiple
    PATCHes) can violate it -- in which case we fall back to the bytes-copy
    path."""
    if not triples:
        return False
    for s, e_inc, _ in triples[:-1]:
        if (e_inc - s + 1) < S3_MULTIPART_MIN_PART_BYTES:
            return False
    return True


def _s3_finalize_sync(upload_id: str) -> dict:
    """Assemble S3 parts into the final CSV object + register the dataset.

    Fast path (typical case, ~5-7s on 2.5 GB / 313 parts):
      - Validate parts cover [0, total_size) contiguously.
      - ``store.assemble_via_multipart_copy`` -- S3 server-side concatenation
        via ``CreateMultipartUpload`` + parallel ``UploadPartCopy``. No bytes
        leave S3.
      - ``register_existing_dataset`` against the storage key (no local file).
      - Batch-delete parts with one ``DeleteObjects`` call.

    Fallback (rare; some part < 5 MiB or multipart copy fails): the original
    download-to-temp / write-to-UPLOAD_DIR / re-upload flow.

    The fast path replaces ~80-150s of network round-trips on a 2.5 GB upload
    that previously caused 504 Gateway Timeouts at the ALB.
    """
    store = get_object_storage()
    sk = _s3_session_key(upload_id)
    if not store.exists(sk):
        raise FileNotFoundError("Unknown or expired upload_id")
    meta = json.loads(store.get_bytes(sk).decode("utf-8"))
    filename = str(meta["filename"])
    total_size = int(meta["total_size"])

    part_prefix = _s3_parts_prefix(upload_id)
    keys = [k for k in store.list_prefix(part_prefix) if k.endswith(".bin")]
    triples: List[Tuple[int, int, str]] = []
    for k in keys:
        pr = _parse_s3_part_range(k)
        if pr:
            s, e_inc = pr
            triples.append((s, e_inc, k))
    triples.sort(key=lambda t: t[0])

    intervals: List[Interval] = []
    for s, e_inc, _ in triples:
        _add_interval(intervals, s, e_inc + 1)
    if not _is_complete(intervals, total_size):
        received = _bytes_received(intervals)
        raise ChunkedUploadHttpError(
            409,
            f"Upload incomplete: {received}/{total_size} bytes "
            f"({len(intervals)} merged range(s))",
        )

    cursor = 0
    for s, e_inc, _ in triples:
        if s != cursor:
            raise ChunkedUploadHttpError(
                409,
                f"Gap or overlap in assembled file at offset {cursor} "
                f"(next part starts at {s})",
            )
        cursor = e_inc + 1
    if cursor != total_size:
        raise ChunkedUploadHttpError(
            409, f"Assembled size mismatch: {cursor} != {total_size}"
        )

    dataset_id = str(uuid.uuid4())
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    storage_key = f"{dataset_id}_{safe_name}"

    used_multipart_copy = False
    if (
        hasattr(store, "assemble_via_multipart_copy")
        and _can_use_s3_multipart_copy(triples)
    ):
        try:
            with time_stage(
                "chunked_upload_s3_assemble_via_multipart_copy",
                bytes_processed=total_size,
            ):
                store.assemble_via_multipart_copy(
                    storage_key,
                    [pk for _, _, pk in triples],
                    max_concurrency=S3_MULTIPART_COPY_MAX_CONCURRENCY,
                )
            used_multipart_copy = True
            logger.info(
                "chunked-upload S3 finalize: server-side assembly OK "
                "(parts=%d, total_size=%d, key=%s)",
                len(triples), total_size, storage_key,
            )
        except Exception as exc:
            logger.warning(
                "chunked-upload S3 finalize: server-side multipart copy "
                "failed; falling back to bytes-copy path: %s",
                exc,
            )
            try:
                store.delete(storage_key)
            except Exception:
                pass

    file_path_for_register: str
    if used_multipart_copy:
        # Assembled file lives only in object storage. ``register_existing_dataset``
        # accepts a logical key when the local path doesn't exist (it falls back
        # to ``store.exists(key)``), so downstream ``*-by-id`` routes still
        # resolve via the object-storage backend.
        file_path_for_register = storage_key
    else:
        # Bytes-copy fallback: download every part, write to local UPLOAD_DIR,
        # PutObject the assembled file. Slow on multi-GB uploads but correct
        # when parts are < 5 MiB or multipart copy is unsupported.
        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                tmp_path = tmp.name
            with open(tmp_path, "wb") as out:
                for s, e_inc, pk in triples:
                    chunk = store.get_bytes(pk)
                    if len(chunk) != e_inc - s + 1:
                        raise ChunkedUploadHttpError(
                            500, "Chunk size mismatch during assembly"
                        )
                    out.write(chunk)

            target = Path(settings.UPLOAD_DIR) / storage_key
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(tmp_path, str(target))
            tmp_path = None

            if store.kind != "local":
                try:
                    store.upload_file_path(storage_key, target)
                except Exception as exc:
                    logger.exception(
                        "chunked-upload S3 finalize: PutObject failed: %s", exc
                    )
                    raise ChunkedUploadHttpError(
                        500, "Could not push assembled file to S3"
                    ) from exc
            file_path_for_register = str(target)
        finally:
            if tmp_path and Path(tmp_path).exists():
                try:
                    Path(tmp_path).unlink()
                except OSError:
                    pass

    registered = dataset_manager.register_existing_dataset(
        dataset_id, file_path_for_register, filename
    )
    if not registered:
        logger.warning(
            "chunked-upload S3 finalize: register_existing_dataset returned False "
            "(dataset_id=%s key=%s)",
            dataset_id, storage_key,
        )

    # 313 individual ``DeleteObject`` calls take ~10s on a typical S3 endpoint;
    # one batched ``DeleteObjects`` call clears the same parts in a single
    # round-trip. Best-effort -- a failure here just leaves orphan parts.
    part_keys = [pk for _, _, pk in triples]
    if hasattr(store, "delete_keys_batch"):
        try:
            store.delete_keys_batch(part_keys)
        except Exception as exc:
            logger.warning(
                "chunked-upload S3 finalize: batch part cleanup failed: %s", exc
            )
    else:
        _delete_prefix_sync(store, part_prefix)
    try:
        store.delete(sk)
    except Exception:
        pass

    return {
        "success": True,
        "dataset_id": dataset_id,
        "storage_key": storage_key,
        "filename": filename,
        "total_size": total_size,
    }


def _s3_status_sync(upload_id: str) -> dict:
    store = get_object_storage()
    sk = _s3_session_key(upload_id)
    if not store.exists(sk):
        raise FileNotFoundError("Unknown or expired upload_id")
    meta = json.loads(store.get_bytes(sk).decode("utf-8"))
    filename = str(meta["filename"])
    total_size = int(meta["total_size"])
    created = float(meta.get("created_ts", 0) or 0)

    part_prefix = _s3_parts_prefix(upload_id)
    keys = [k for k in store.list_prefix(part_prefix) if k.endswith(".bin")]
    intervals: List[Interval] = []
    for k in keys:
        pr = _parse_s3_part_range(k)
        if pr:
            s, e_inc = pr
            _add_interval(intervals, s, e_inc + 1)
    received = _bytes_received(intervals)
    complete = _is_complete(intervals, total_size)
    return {
        "upload_id": upload_id,
        "filename": filename,
        "bytes_received": received,
        "total_size": total_size,
        "complete": complete,
        "last_activity_s_ago": int(time.time() - created),
    }


def _s3_cancel_sync(upload_id: str) -> bool:
    store = get_object_storage()
    sk = _s3_session_key(upload_id)
    if not store.exists(sk):
        return False
    try:
        meta = json.loads(store.get_bytes(sk).decode("utf-8"))
        uid = str(meta.get("upload_id") or upload_id)
    except Exception:
        uid = upload_id
    _delete_prefix_sync(store, _s3_parts_prefix(uid))
    try:
        store.delete(sk)
    except Exception:
        pass
    return True


@dataclass
class _ChunkedUpload:
    upload_id: str
    filename: str
    total_size: int
    path: Path
    fd: Optional[int] = None
    intervals: List[Interval] = field(default_factory=list)
    last_activity: float = 0.0
    state_lock: Optional[asyncio.Lock] = None

    @property
    def bytes_received(self) -> int:
        return _bytes_received(self.intervals)

    @property
    def is_complete(self) -> bool:
        return _is_complete(self.intervals, self.total_size)

    def close_fd(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None


_uploads: Dict[str, _ChunkedUpload] = {}
_uploads_lock = asyncio.Lock()


async def _gc_expired(now: Optional[float] = None) -> None:
    now = now if now is not None else time.time()
    await asyncio.to_thread(_gc_s3_stale_sessions_sync)
    async with _uploads_lock:
        stale = [
            uid for uid, u in _uploads.items()
            if now - u.last_activity > UPLOAD_TTL_S
        ]
        for uid in stale:
            u = _uploads.pop(uid, None)
            if u is not None:
                u.close_fd()
                if u.path.exists():
                    try:
                        u.path.unlink()
                    except OSError:
                        pass
            logger.info("chunked-upload GC: dropped stale upload %s", uid)


def _validate_csv_filename(name: str) -> None:
    if not name or not name.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")


@router.post("/upload-chunked/init")
async def init_chunked_upload(
    body: dict,
    current_user=Depends(get_current_user_dependency),
):
    """Reserve an upload slot and return an opaque upload_id."""
    filename = str(body.get("filename") or "").strip()
    total_size = int(body.get("total_size") or 0)
    _validate_csv_filename(filename)
    if total_size <= 0:
        raise HTTPException(status_code=400, detail="total_size must be > 0")
    if total_size > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds maximum limit")

    await _gc_expired()
    store = get_object_storage()
    if store.kind == "s3":
        upload_id = str(uuid.uuid4())
        session = {
            "upload_id": upload_id,
            "filename": filename,
            "total_size": total_size,
            "created_ts": time.time(),
        }

        def _put_session() -> None:
            store.put_bytes(
                _s3_session_key(upload_id),
                json.dumps(session).encode("utf-8"),
            )

        await asyncio.to_thread(_put_session)
        logger.info(
            "chunked-upload S3 init: id=%s filename=%s total=%d hint=%d",
            upload_id,
            filename,
            total_size,
            CHUNK_SIZE_HINT,
        )
        return {
            "upload_id": upload_id,
            "chunk_size_hint": CHUNK_SIZE_HINT,
            "expires_in_s": UPLOAD_TTL_S,
        }

    upload_id = str(uuid.uuid4())
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    path = CHUNK_DIR / f"{upload_id}_{safe_name}"

    # Pre-allocate the destination file at full size so concurrent ``pwrite``s
    # at the eventual byte offsets do not race on file-extension. ``os.open``
    # gives us a long-lived FD that every PATCH reuses; closed at finalize /
    # cancel / GC. This is the key to lock-free parallel chunk writes.
    try:
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
        if total_size > 0:
            os.ftruncate(fd, total_size)
    except OSError as exc:
        logger.exception("chunked-upload init: pre-allocate failed: %s", exc)
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        raise HTTPException(
            status_code=507,
            detail=f"Could not pre-allocate {total_size} bytes for upload",
        ) from exc

    upload = _ChunkedUpload(
        upload_id=upload_id,
        filename=filename,
        total_size=total_size,
        path=path,
        fd=fd,
        last_activity=time.time(),
        state_lock=asyncio.Lock(),
    )
    async with _uploads_lock:
        _uploads[upload_id] = upload

    logger.info(
        "chunked-upload init: id=%s filename=%s total=%d hint=%d",
        upload_id, filename, total_size, CHUNK_SIZE_HINT,
    )
    return {
        "upload_id": upload_id,
        "chunk_size_hint": CHUNK_SIZE_HINT,
        "expires_in_s": UPLOAD_TTL_S,
    }


def _parse_content_range(header: str) -> tuple[int, int, int]:
    """Parse `bytes <start>-<end>/<total>` (RFC 7233-ish)."""
    try:
        return _parse_content_range_plain(header)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/upload-chunked/{upload_id}")
async def append_chunk(
    upload_id: str,
    request: Request,
    content_range: str = Header(default="", alias="Content-Range"),
    current_user=Depends(get_current_user_dependency),
):
    """Append one chunk.

    Multiple chunks may be PATCHed in parallel for the same ``upload_id``;
    the write itself is lock-free (positional ``os.pwrite`` runs in a worker
    thread) and a small ``state_lock`` only guards the merged-interval set
    bookkeeping. Re-PATCHing the same Content-Range is idempotent.
    """
    store = get_object_storage()
    if store.kind == "s3" and store.exists(_s3_session_key(upload_id)):
        body = await request.body()
        try:
            return await asyncio.to_thread(
                _s3_append_chunk_sync, upload_id, content_range, body
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Unknown or expired upload_id")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ChunkedUploadHttpError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    async with _uploads_lock:
        upload = _uploads.get(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Unknown or expired upload_id")
    if upload.fd is None:
        raise HTTPException(status_code=410, detail="Upload no longer accepting chunks")

    start, end, total = _parse_content_range(content_range)
    if total != upload.total_size:
        raise HTTPException(status_code=409, detail="total_size mismatch with init")
    if end >= upload.total_size:
        raise HTTPException(status_code=416, detail="Range past total_size")

    body = await request.body()
    expected = end - start + 1
    if len(body) != expected:
        raise HTTPException(
            status_code=400,
            detail=f"Body length {len(body)} != range size {expected}",
        )

    fd = upload.fd

    def _pwrite_blocking(buf: bytes, offset: int) -> int:
        # ``os.pwrite`` is POSIX-atomic at the offset and does not touch the
        # file's seek cursor, so concurrent calls from multiple threads /
        # asyncio workers do not race when they target disjoint ranges. It
        # *can* return a short write on signals; loop until everything lands.
        view = memoryview(buf)
        written = 0
        while written < len(view):
            n = os.pwrite(fd, view[written:], offset + written)
            if n <= 0:
                raise OSError("os.pwrite returned non-positive count")
            written += n
        return written

    with time_stage("chunked_upload_append", bytes_processed=len(body)):
        await asyncio.to_thread(_pwrite_blocking, body, start)
        async with upload.state_lock:
            _add_interval(upload.intervals, start, end + 1)
            upload.last_activity = time.time()
            received = _bytes_received(upload.intervals)
            complete = _is_complete(upload.intervals, upload.total_size)

    return {
        "upload_id": upload_id,
        "bytes_received": received,
        "total_size": upload.total_size,
        "complete": complete,
    }


@router.post("/upload-chunked/{upload_id}/finalize")
async def finalize_chunked_upload(
    upload_id: str,
    current_user=Depends(get_current_user_dependency),
):
    """
    Move the assembled file into the standard storage layer and return a
    `dataset_id` + `storage_key` the existing `/analyze-dataset` and
    `/upload` endpoints can consume.

    NOTE: this does *not* run the heavy `/upload` pipeline (target
    selection, splits, etc.). The frontend should POST to /upload-chunked/
    {id}/finalize first to obtain a storage_key, then POST to /upload
    with `existing_storage_key=<key>` (a lighter ingest path that skips
    the multipart re-upload).
    """
    store = get_object_storage()
    if store.kind == "s3" and store.exists(_s3_session_key(upload_id)):
        loop = asyncio.get_event_loop()
        from app.core.executor import executor as _executor

        try:
            result = await loop.run_in_executor(_executor, _s3_finalize_sync, upload_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Unknown or expired upload_id")
        except ChunkedUploadHttpError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

        logger.info(
            "chunked-upload S3 finalize: id=%s dataset_id=%s key=%s size=%d",
            upload_id,
            result["dataset_id"],
            result["storage_key"],
            result["total_size"],
        )
        try:
            loop.run_in_executor(_executor, _safe_stream_convert, result["storage_key"])
        except Exception as exc:
            logger.warning(
                "post-finalize streaming Parquet conversion not scheduled: %s", exc
            )
        return result

    async with _uploads_lock:
        upload = _uploads.get(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Unknown or expired upload_id")

    async with upload.state_lock:
        received = _bytes_received(upload.intervals)
        complete = _is_complete(upload.intervals, upload.total_size)
    if not complete:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Upload incomplete: {received}/{upload.total_size} bytes"
                f" ({len(upload.intervals)} non-contiguous range(s))"
            ),
        )

    # Close the FD before moving so the kernel flushes pending writes and we
    # don't move-while-open (works on Linux but unnecessary risk on others).
    upload.close_fd()

    dataset_id = str(uuid.uuid4())
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in upload.filename)
    storage_key = f"{dataset_id}_{safe_name}"

    target = Path(settings.UPLOAD_DIR) / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Move (rename) is O(1) on the same filesystem; copy+remove on cross-fs.
        shutil.move(str(upload.path), str(target))
    except Exception as exc:
        logger.exception("chunked-upload finalize: move failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not finalize upload") from exc

    async with _uploads_lock:
        _uploads.pop(upload_id, None)

    logger.info(
        "chunked-upload finalize: id=%s dataset_id=%s key=%s size=%d",
        upload_id, dataset_id, storage_key, upload.total_size,
    )

    loop = asyncio.get_event_loop()
    from app.core.executor import executor as _executor

    # If the configured object store is remote (S3), push the assembled
    # file there before we register the dataset. Every downstream Step 1
    # endpoint (analyze, validate-unique-ids-by-id, partition-preview-by-id,
    # the background parquet conversion) reads through ``get_object_storage``,
    # so the canonical bytes MUST live in that store -- otherwise *-by-id
    # routes 404 because ``store.exists(storage_key)`` is false. boto3's
    # ``upload_file`` uses multipart with parallel parts, so a 2 GB push
    # over an EKS->S3 VPC endpoint completes in seconds and stays bounded
    # in memory regardless of file size.
    if store.kind != "local":
        try:
            with time_stage("chunked_upload_push_to_store", bytes_processed=upload.total_size):
                await loop.run_in_executor(
                    _executor,
                    store.upload_file_path,
                    storage_key,
                    target,
                )
        except Exception as exc:
            logger.exception(
                "chunked-upload finalize: push to %s failed: %s",
                store.kind,
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Could not push assembled file to {store.kind} storage",
            ) from exc

    # Register the dataset so every ``*-by-id`` endpoint resolves it via
    # ``dataset_manager.get_dataset_info``. ``register_existing_dataset``
    # also persists a JSON sidecar through the same object store, so a
    # request that lands on a different replica can rehydrate the entry
    # without needing the upload-time pod's local memory.
    try:
        registered = await loop.run_in_executor(
            _executor,
            dataset_manager.register_existing_dataset,
            dataset_id,
            str(target),
            upload.filename,
        )
        if not registered:
            logger.warning(
                "chunked-upload finalize: register_existing_dataset returned False "
                "(dataset_id=%s key=%s)",
                dataset_id,
                storage_key,
            )
    except Exception as exc:
        logger.exception("chunked-upload finalize: register failed: %s", exc)
        # Don't fail the request -- the file is in the store; downstream
        # routes will fall through to the lazy ``_load_dataset_info_from_disk``
        # path. Just surface a warning so we notice in metrics.

    # P2.1: kick off streaming Parquet conversion so subsequent analytics
    # endpoints see a Parquet sidecar and skip the slow CSV path. This is a
    # multi-second CPU + I/O job, so we offload to the shared executor and
    # do not await it -- the upload response returns immediately and the
    # parquet sidecar appears in the background. Validate-unique-id and
    # analyze-dataset endpoints fall back to the CSV path until it lands.
    try:
        loop.run_in_executor(
            _executor,
            _safe_stream_convert,
            storage_key,
        )
    except Exception as exc:
        logger.warning("post-finalize streaming Parquet conversion not scheduled: %s", exc)

    return {
        "success": True,
        "dataset_id": dataset_id,
        "storage_key": storage_key,
        "filename": upload.filename,
        "total_size": upload.total_size,
    }


def _safe_stream_convert(storage_key: str) -> None:
    """Background job: best-effort CSV -> Parquet sidecar conversion.

    Runs in the shared executor; never raises into the event loop.
    """
    try:
        dataset_manager.stream_convert_csv_to_parquet(storage_key)
    except Exception as exc:
        logger.warning(
            "background parquet conversion skipped (key=%s): %s",
            storage_key,
            exc,
        )


@router.delete("/upload-chunked/{upload_id}")
async def cancel_chunked_upload(
    upload_id: str,
    current_user=Depends(get_current_user_dependency),
):
    store = get_object_storage()
    cancelled_s3 = False
    if store.kind == "s3":
        cancelled_s3 = await asyncio.to_thread(_s3_cancel_sync, upload_id)

    async with _uploads_lock:
        upload = _uploads.pop(upload_id, None)
    if upload is not None:
        upload.close_fd()
        try:
            if upload.path.exists():
                upload.path.unlink()
        except OSError:
            pass
        logger.info("chunked-upload cancel: id=%s (memory)", upload_id)
        return {"success": True}

    if cancelled_s3:
        logger.info("chunked-upload cancel: id=%s (S3)", upload_id)
        return {"success": True}

    return {"success": True, "message": "Upload already gone"}


@router.get("/upload-chunked/{upload_id}/status")
async def chunked_upload_status(
    upload_id: str,
    current_user=Depends(get_current_user_dependency),
):
    store = get_object_storage()
    if store.kind == "s3":
        try:
            return await asyncio.to_thread(_s3_status_sync, upload_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Unknown or expired upload_id")

    async with _uploads_lock:
        upload = _uploads.get(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Unknown or expired upload_id")
    async with upload.state_lock:
        received = _bytes_received(upload.intervals)
        complete = _is_complete(upload.intervals, upload.total_size)
    return {
        "upload_id": upload_id,
        "filename": upload.filename,
        "bytes_received": received,
        "total_size": upload.total_size,
        "complete": complete,
        "last_activity_s_ago": int(time.time() - upload.last_activity),
    }

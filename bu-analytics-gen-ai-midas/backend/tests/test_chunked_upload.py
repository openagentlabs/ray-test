"""
Tests for the chunked-upload backend (P2.5):

* `_add_interval` / `_bytes_received` / `_is_complete` -- merging logic
  that backs out-of-order parallel chunk arrivals.
* End-to-end PATCH flow with the FastAPI TestClient: in-order, reverse-
  order, and duplicate-range (idempotent retry) all assemble byte-perfect
  output and report `complete=True` only once every byte is covered.

The HTTP tests bypass the auth dependency and disable the rate limiter
so they run in <1s without any external services.
"""

from __future__ import annotations

import os
import secrets

import pytest


from app.api._chunked_upload_intervals import (
    add_interval,
    bytes_received,
    is_complete,
)


def test_add_interval_in_order_merges_into_single_range():
    iv = []
    add_interval(iv, 0, 100)
    add_interval(iv, 100, 200)
    add_interval(iv, 200, 300)
    assert iv == [(0, 300)]
    assert bytes_received(iv) == 300
    assert is_complete(iv, 300)


def test_add_interval_out_of_order_still_merges():
    iv = []
    add_interval(iv, 200, 300)
    add_interval(iv, 0, 100)
    add_interval(iv, 100, 200)
    assert iv == [(0, 300)]
    assert is_complete(iv, 300)


def test_add_interval_duplicates_are_idempotent():
    iv = []
    add_interval(iv, 0, 100)
    add_interval(iv, 0, 100)
    add_interval(iv, 0, 100)
    assert iv == [(0, 100)]
    assert bytes_received(iv) == 100


def test_add_interval_overlap_extends_existing_range():
    iv = []
    add_interval(iv, 0, 100)
    add_interval(iv, 50, 200)
    assert iv == [(0, 200)]
    assert bytes_received(iv) == 200


def test_is_complete_requires_zero_start_and_full_coverage():
    iv = []
    add_interval(iv, 0, 90)
    assert not is_complete(iv, 100)
    add_interval(iv, 90, 100)
    assert is_complete(iv, 100)

    iv2 = []
    add_interval(iv2, 10, 110)
    assert bytes_received(iv2) == 100
    assert not is_complete(iv2, 100)


def test_add_interval_rejects_zero_or_negative_length():
    iv = []
    add_interval(iv, 50, 50)
    add_interval(iv, 100, 90)
    assert iv == []


def test_add_interval_handles_many_random_chunks_assembled_in_random_order():
    """Worst-case for the merge logic: simulate parallel-out-of-order delivery
    of every chunk in a 2 GB upload at 8 MiB granularity. After all chunks
    land the interval set must collapse to one [0, total) range."""
    import random

    chunk = 8 * 1024 * 1024
    total = 2 * 1024 * 1024 * 1024
    starts = list(range(0, total, chunk))
    random.Random(0).shuffle(starts)

    iv = []
    for s in starts:
        e = min(s + chunk, total)
        add_interval(iv, s, e)

    assert iv == [(0, total)]
    assert is_complete(iv, total)


# The HTTP-level tests below import the FastAPI router, which transitively
# pulls in auth + litellm + the full config bundle. On a thin local checkout
# those deps may be missing; we skip the integration tests in that case so
# the pure-helper tests above still run anywhere.
try:
    from app.api import chunked_upload as _cu_probe  # noqa: F401
    _CHUNKED_IMPORTABLE = True
except Exception:  # pragma: no cover
    _CHUNKED_IMPORTABLE = False


pytestmark_http = pytest.mark.skipif(
    not _CHUNKED_IMPORTABLE,
    reason="chunked_upload router not importable in this environment",
)


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Build a FastAPI app exposing only the chunked-upload router with auth
    stubbed out and the rate limiter disabled. Each test gets its own temp
    UPLOAD_DIR so concurrent runs do not collide. We also rebind the global
    object-storage backend and the global dataset_manager.upload_dir to the
    fresh tmp_path so finalize-time registration writes the dataset metadata
    next to the assembled file (otherwise the cached LocalObjectStorage from
    process import would still point at the original UPLOAD_DIR)."""

    if not _CHUNKED_IMPORTABLE:
        pytest.skip("chunked_upload router not importable in this environment")

    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api import chunked_upload as cu
    from app.api.auth_routes import get_current_user_dependency

    cu.CHUNK_DIR = tmp_path / "_chunked"
    cu.CHUNK_DIR.mkdir(parents=True, exist_ok=True)

    cu._uploads.clear()

    monkeypatch.setattr(cu, "_safe_stream_convert", lambda _key: None)

    from app.core import config as core_config

    monkeypatch.setattr(core_config.settings, "UPLOAD_DIR", str(tmp_path))

    # Rebind the process-wide object storage to the per-test tmp directory
    # so finalize -> register_existing_dataset -> persist works on a clean
    # slate. Each test starts with no datasets and an empty bucket.
    from app.services.object_storage import registry as _store_registry
    from app.services.object_storage.local_object_storage import LocalObjectStorage

    _store_registry.set_object_storage(LocalObjectStorage(tmp_path))

    from app.services.dataset_service import dataset_manager

    monkeypatch.setattr(dataset_manager, "upload_dir", tmp_path)
    dataset_manager.datasets.clear()

    app = FastAPI()
    app.include_router(cu.router)
    app.dependency_overrides[get_current_user_dependency] = lambda: {"sub": "test-user"}

    with TestClient(app) as tc:
        yield tc, tmp_path


def _init(client, total_size: int, filename: str = "data.csv") -> str:
    res = client.post(
        "/upload-chunked/init",
        json={"filename": filename, "total_size": total_size},
    )
    assert res.status_code == 200, res.text
    return res.json()["upload_id"]


def _patch(client, upload_id: str, body: bytes, start: int, total: int):
    return client.patch(
        f"/upload-chunked/{upload_id}",
        content=body,
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Range": f"bytes {start}-{start + len(body) - 1}/{total}",
        },
    )


def _finalize(client, upload_id: str):
    return client.post(f"/upload-chunked/{upload_id}/finalize")


def test_in_order_chunks_assemble_byte_perfect(client):
    tc, tmp = client
    payload = secrets.token_bytes(50_000)
    upload_id = _init(tc, len(payload))

    chunk = 4096
    for start in range(0, len(payload), chunk):
        body = payload[start : start + chunk]
        res = _patch(tc, upload_id, body, start, len(payload))
        assert res.status_code == 200, res.text

    fin = _finalize(tc, upload_id)
    assert fin.status_code == 200, fin.text
    storage_key = fin.json()["storage_key"]
    final_path = tmp / storage_key
    assert final_path.read_bytes() == payload


def test_reverse_order_chunks_still_assemble_byte_perfect(client):
    tc, tmp = client
    payload = secrets.token_bytes(50_000)
    upload_id = _init(tc, len(payload))

    chunk = 4096
    starts = list(range(0, len(payload), chunk))
    for start in reversed(starts):
        body = payload[start : start + chunk]
        res = _patch(tc, upload_id, body, start, len(payload))
        assert res.status_code == 200, res.text

    fin = _finalize(tc, upload_id)
    assert fin.status_code == 200, fin.text
    storage_key = fin.json()["storage_key"]
    final_path = tmp / storage_key
    assert final_path.read_bytes() == payload


def test_duplicate_range_is_idempotent(client):
    tc, tmp = client
    payload = secrets.token_bytes(20_000)
    upload_id = _init(tc, len(payload))

    chunk = 4096
    starts = list(range(0, len(payload), chunk))
    for start in starts:
        body = payload[start : start + chunk]
        res = _patch(tc, upload_id, body, start, len(payload))
        assert res.status_code == 200

    mid = starts[len(starts) // 2]
    for _ in range(3):
        body = payload[mid : mid + chunk]
        res = _patch(tc, upload_id, body, mid, len(payload))
        assert res.status_code == 200
        assert res.json()["complete"] is True

    fin = _finalize(tc, upload_id)
    assert fin.status_code == 200
    storage_key = fin.json()["storage_key"]
    assert (tmp / storage_key).read_bytes() == payload


def test_finalize_rejects_incomplete_upload(client):
    tc, _tmp = client
    payload = secrets.token_bytes(10_000)
    upload_id = _init(tc, len(payload))

    res = _patch(tc, upload_id, payload[:4096], 0, len(payload))
    assert res.status_code == 200
    assert res.json()["complete"] is False

    fin = _finalize(tc, upload_id)
    assert fin.status_code == 409, fin.text
    assert "incomplete" in fin.json()["detail"].lower()


def test_pre_allocates_full_size_at_init(client):
    tc, _tmp = client
    total = 1_500_000
    upload_id = _init(tc, total)
    from app.api import chunked_upload as cu

    upload = cu._uploads[upload_id]
    assert os.path.getsize(upload.path) == total


def test_init_rejects_non_csv_filename(client):
    tc, _tmp = client
    res = tc.post(
        "/upload-chunked/init",
        json={"filename": "data.parquet", "total_size": 100},
    )
    assert res.status_code == 400
    assert "csv" in res.json()["detail"].lower()


def test_status_reports_partial_progress(client):
    tc, _tmp = client
    payload = secrets.token_bytes(20_000)
    upload_id = _init(tc, len(payload))

    res = _patch(tc, upload_id, payload[:5_000], 0, len(payload))
    assert res.status_code == 200

    status = tc.get(f"/upload-chunked/{upload_id}/status")
    assert status.status_code == 200
    body = status.json()
    assert body["bytes_received"] == 5_000
    assert body["complete"] is False
    assert body["total_size"] == len(payload)


def test_cancel_drops_upload_and_unlinks_file(client):
    tc, _tmp = client
    upload_id = _init(tc, 4096)

    from app.api import chunked_upload as cu

    upload = cu._uploads[upload_id]
    path = upload.path
    assert path.exists()

    res = tc.delete(f"/upload-chunked/{upload_id}")
    assert res.status_code == 200
    assert upload_id not in cu._uploads
    assert not path.exists()


def test_finalize_registers_dataset_with_dataset_manager(client):
    """The single root cause of the validate-unique-id / partition-preview
    failures was that ``finalize`` never called ``register_existing_dataset``.
    Lock that in: after finalize the dataset_id MUST resolve via
    ``dataset_manager.get_dataset_info`` with a storage_key matching the
    response, otherwise every downstream ``*-by-id`` route 404s."""
    tc, tmp = client
    payload = b"col_a,col_b\n" + b"1,2\n" * 100
    upload_id = _init(tc, len(payload))

    res = _patch(tc, upload_id, payload, 0, len(payload))
    assert res.status_code == 200

    fin = _finalize(tc, upload_id)
    assert fin.status_code == 200, fin.text
    body = fin.json()
    dataset_id = body["dataset_id"]
    storage_key = body["storage_key"]

    from app.services.dataset_service import dataset_manager

    info = dataset_manager.get_dataset_info(dataset_id)
    assert info is not None, "dataset_manager did not register the dataset on finalize"
    assert info.get("storage_key") == storage_key
    assert info.get("filename") == "data.csv"

    assert (tmp / storage_key).read_bytes() == payload


def test_finalize_persists_metadata_for_cross_replica_rehydration(client):
    """Multi-replica EKS: a different pod must be able to rehydrate the
    dataset entry from the persisted JSON sidecar in object storage even
    if it never saw the upload itself. Simulate that by clearing the
    in-memory ``datasets`` dict after finalize and confirming that
    ``get_dataset_info`` still returns a populated record (loaded from
    the sidecar via ``_load_dataset_info_from_disk``)."""
    tc, _tmp = client
    payload = b"a,b\n1,2\n3,4\n"
    upload_id = _init(tc, len(payload))
    _patch(tc, upload_id, payload, 0, len(payload))
    fin = _finalize(tc, upload_id)
    assert fin.status_code == 200, fin.text
    dataset_id = fin.json()["dataset_id"]

    from app.services.dataset_service import dataset_manager

    dataset_manager.datasets.clear()

    info = dataset_manager.get_dataset_info(dataset_id)
    assert info is not None, (
        "Sidecar metadata was not persisted; another replica cannot resolve "
        "the dataset_id after the upload pod GCs its in-memory entry."
    )
    assert info.get("storage_key", "").startswith(dataset_id)


def test_finalize_returns_500_when_object_store_rejects_push(monkeypatch, client):
    """If the configured store is remote (S3-like) and the post-finalize push
    fails, finalize must surface a 500 rather than silently returning a
    dataset_id that downstream routes can't resolve."""
    tc, _tmp = client
    payload = b"x,y\n1,2\n"
    upload_id = _init(tc, len(payload))
    _patch(tc, upload_id, payload, 0, len(payload))

    from app.services.object_storage import registry as _store_registry

    real_store = _store_registry.get_object_storage()

    class _BrokenRemoteStore:
        kind = "s3"

        def __init__(self, inner):
            self._inner = inner

        def upload_file_path(self, *_args, **_kwargs):
            raise RuntimeError("simulated PutObject failure")

        def __getattr__(self, name):
            return getattr(self._inner, name)

    _store_registry.set_object_storage(_BrokenRemoteStore(real_store))
    try:
        fin = _finalize(tc, upload_id)
        assert fin.status_code == 500, fin.text
        assert "storage" in fin.json()["detail"].lower()
    finally:
        _store_registry.set_object_storage(real_store)

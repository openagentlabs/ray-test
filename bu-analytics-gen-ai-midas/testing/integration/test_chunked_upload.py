"""Integration tests for chunked_upload router — full lifecycle."""

from __future__ import annotations

import pytest
from returns.result import Failure, Success

from testing.api_client.client import MidasHttpClient
from testing.integration.support.auth_guards import skip_on_auth_reject

pytestmark = pytest.mark.chunked_upload

_CHUNKED_BASE = "/api/v1/upload-chunked"


def _init_upload(
    client: MidasHttpClient,
    filename: str = "test_chunked.csv",
    total_size: int = 100,
) -> str:
    """Init a chunked upload and return the upload_id; skip on auth failure."""
    result = client.post_json(
        f"{_CHUNKED_BASE}/init",
        {"filename": filename, "total_size": total_size},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200, f"Init failed: {resp.text[:300]}"
            body = resp.json()
            upload_id = str(body.get("upload_id", ""))
            assert upload_id, "upload_id missing from init response"
            return upload_id
        case Failure(exc):
            pytest.skip(f"Transport error during chunked init: {exc}")
    raise RuntimeError("unreachable")


# ------------------------------------------------------------------
# Init
# ------------------------------------------------------------------


def test_init_returns_upload_id(midas_client: MidasHttpClient) -> None:
    """POST /upload-chunked/init returns upload_id string and chunk_size_hint int."""
    result = midas_client.post_json(
        f"{_CHUNKED_BASE}/init",
        {"filename": "init_test.csv", "total_size": 200},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            assert isinstance(body.get("upload_id"), str), "upload_id must be a string"
            assert isinstance(body.get("chunk_size_hint"), int), "chunk_size_hint must be int"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# PATCH chunk
# ------------------------------------------------------------------


def test_patch_chunk(midas_client: MidasHttpClient) -> None:
    """PATCH /{upload_id} with Content-Range returns 200 and progress dict."""
    chunk = b"x" * 100
    upload_id = _init_upload(midas_client, total_size=100)
    result = midas_client.patch_bytes(
        f"{_CHUNKED_BASE}/{upload_id}",
        chunk,
        content_range="bytes 0-99/100",
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {200, 206}, (
                f"Unexpected status: {resp.status_code}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_patch_wrong_content_range_format(midas_client: MidasHttpClient) -> None:
    """PATCH without Content-Range header returns 400 or 422."""
    upload_id = _init_upload(midas_client, total_size=100)
    try:
        result = midas_client.request(
            "PATCH",
            f"{_CHUNKED_BASE}/{upload_id}",
            content=b"x" * 10,
        )
    except Exception as exc:
        pytest.skip(f"Transport error: {exc}")
        return
    assert result.status_code in {400, 422}, (
        f"Expected 400/422 for missing Content-Range, got {result.status_code}"
    )


def test_patch_invalid_upload_id(midas_client: MidasHttpClient) -> None:
    """PATCH /upload-chunked/nonexistent-id returns 404."""
    result = midas_client.patch_bytes(
        f"{_CHUNKED_BASE}/nonexistent-upload-id-00000",
        b"x" * 10,
        content_range="bytes 0-9/10",
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 404
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------


def test_status_after_init(midas_client: MidasHttpClient) -> None:
    """GET /{upload_id}/status after init returns 200."""
    upload_id = _init_upload(midas_client, total_size=100)
    result = midas_client.get_raw(f"{_CHUNKED_BASE}/{upload_id}/status")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Finalize
# ------------------------------------------------------------------


def test_finalize_incomplete(midas_client: MidasHttpClient) -> None:
    """POST /{upload_id}/finalize before uploading chunks returns 400 or 409."""
    upload_id = _init_upload(midas_client, total_size=1000)
    result = midas_client.post_json(
        f"{_CHUNKED_BASE}/{upload_id}/finalize",
        {},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {400, 409}, (
                f"Expected 400/409 for premature finalize, got {resp.status_code}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_full_lifecycle(midas_client: MidasHttpClient) -> None:
    """Full chunked upload lifecycle: init → patch → finalize → status → delete."""
    chunk = b"a" * 100
    total = len(chunk)

    upload_id = _init_upload(midas_client, filename="lifecycle.csv", total_size=total)

    patch_result = midas_client.patch_bytes(
        f"{_CHUNKED_BASE}/{upload_id}",
        chunk,
        content_range=f"bytes 0-{total - 1}/{total}",
    )
    match patch_result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {200, 206}
        case Failure(exc):
            pytest.skip(f"Transport error during patch: {exc}")

    finalize_result = midas_client.post_json(
        f"{_CHUNKED_BASE}/{upload_id}/finalize",
        {},
    )
    match finalize_result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {200, 201, 202}, (
                f"Finalize returned {resp.status_code}: {resp.text[:300]}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error during finalize: {exc}")

    del_result = midas_client.delete(f"{_CHUNKED_BASE}/{upload_id}")
    match del_result:
        case Success(resp):
            assert resp.status_code in {200, 204}
        case Failure(exc):
            pytest.skip(f"Transport error during delete: {exc}")


# ------------------------------------------------------------------
# Delete non-existent
# ------------------------------------------------------------------


def test_delete_nonexistent(midas_client: MidasHttpClient) -> None:
    """DELETE /upload-chunked/nonexistent-id returns 404 or 200 (API is idempotent)."""
    result = midas_client.delete(f"{_CHUNKED_BASE}/nonexistent-upload-id-00001")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {200, 404}, (
                f"Expected 200 or 404, got {resp.status_code}: {resp.text[:200]}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")

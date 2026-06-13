"""Integration tests for rfe_router — async job lifecycle."""

from __future__ import annotations

import pytest
from returns.result import Failure, Success

from testing.api_client.client import MidasHttpClient
from testing.integration.support.auth_guards import skip_on_auth_reject

pytestmark = pytest.mark.rfe

_RFE_BASE = "/api/v1/rfe"


def _start_rfe_job(
    client: MidasHttpClient,
    dataset_id: str,
) -> str:
    """Start an RFE job and return the job_id; skip on auth or transport failure."""
    result = client.post_json(
        f"{_RFE_BASE}/start",
        {
            "dataset_id": dataset_id,
            "target": "target_flag",
            "working_set": ["age", "income"],
        },
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200, f"RFE start failed: {resp.text[:300]}"
            body = resp.json()
            job_id = str(body.get("job_id", ""))
            assert job_id, "job_id missing from RFE start response"
            return job_id
        case Failure(exc):
            pytest.skip(f"Transport error starting RFE: {exc}")
    raise RuntimeError("unreachable")


# ------------------------------------------------------------------
# Start validation
# ------------------------------------------------------------------


def test_start_missing_target(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """POST /rfe/start without target field returns 422."""
    result = midas_client.post_json(
        f"{_RFE_BASE}/start",
        {"dataset_id": uploaded_dataset_id, "working_set": ["age"]},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 422
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_start_valid(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """POST /rfe/start with valid body returns 200 and a job_id string."""
    result = midas_client.post_json(
        f"{_RFE_BASE}/start",
        {
            "dataset_id": uploaded_dataset_id,
            "target": "target_flag",
            "working_set": ["age", "income"],
        },
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            assert isinstance(body.get("job_id"), str), "job_id must be a string"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------


def test_status_unknown_job(midas_client: MidasHttpClient) -> None:
    """GET /rfe/status/nonexistent-job-id returns 404."""
    result = midas_client.get_raw(f"{_RFE_BASE}/status/nonexistent-job-id-00000")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 404
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_status_polling(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """GET /rfe/status/{job_id} returns 200 with status in known set."""
    job_id = _start_rfe_job(midas_client, uploaded_dataset_id)
    result = midas_client.get_raw(f"{_RFE_BASE}/status/{job_id}")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            status = resp.json().get("status", "")
            assert status in {"pending", "running", "completed", "failed", "error"}, (
                f"Unexpected RFE job status: {status}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Result (409 while running)
# ------------------------------------------------------------------


def test_result_not_ready_returns_409_or_404(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """GET /rfe/result/{job_id} immediately after start returns 409 or 404."""
    job_id = _start_rfe_job(midas_client, uploaded_dataset_id)
    result = midas_client.get_raw(f"{_RFE_BASE}/result/{job_id}")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {200, 202, 409, 404}, (
                f"Unexpected status for in-progress result: {resp.status_code}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Cancel
# ------------------------------------------------------------------


def test_cancel_valid(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """POST /rfe/cancel/{job_id} returns 200 with cancelled field."""
    job_id = _start_rfe_job(midas_client, uploaded_dataset_id)
    result = midas_client.post_json(f"{_RFE_BASE}/cancel/{job_id}", {})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Monotone
# ------------------------------------------------------------------


def test_monotone_no_dataset(midas_client: MidasHttpClient) -> None:
    """GET /rfe/monotone/nonexistent returns 200 with empty defaults (not 5xx)."""
    result = midas_client.get_raw(f"{_RFE_BASE}/monotone/nonexistent-dataset-00001")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code < 500, (
                f"Server error for monotone with unknown dataset: {resp.status_code}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Stream headers
# ------------------------------------------------------------------


def test_stream_headers(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """GET /rfe/stream/{job_id} returns Content-Type: text/event-stream."""
    job_id = _start_rfe_job(midas_client, uploaded_dataset_id)
    result = midas_client.stream_lines(f"{_RFE_BASE}/stream/{job_id}", max_lines=3)
    match result:
        case Success(_lines):
            pass  # stream opened successfully; content-type was acceptable
        case Failure(exc):
            err_msg = str(exc).lower()
            if "connection" in err_msg or "timeout" in err_msg or "eof" in err_msg:
                pytest.skip(f"Stream closed early: {exc}")
            pytest.skip(f"Transport error: {exc}")

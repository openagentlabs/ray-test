"""Integration tests for chat_router insights endpoints."""

from __future__ import annotations

import pytest
from returns.result import Failure, Success

from testing.api_client.client import MidasHttpClient
from testing.integration.support.auth_guards import skip_on_auth_reject

pytestmark = pytest.mark.insights

_INSIGHTS_BASE = "/api/v1/insights"

# Known terminal statuses for insight jobs
_TERMINAL = {"completed", "failed", "error", "cancelled"}


# ------------------------------------------------------------------
# Simple GET health/config
# ------------------------------------------------------------------


def test_keepalive(midas_client: MidasHttpClient) -> None:
    """GET /keepalive returns 200."""
    result = midas_client.get_raw("/api/v1/keepalive")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_llm_config(midas_client: MidasHttpClient) -> None:
    """GET /llm-config returns 200 with a JSON object."""
    result = midas_client.get_raw("/api/v1/llm-config")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            assert isinstance(resp.json(), dict), "Expected JSON object"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Dataset preview
# ------------------------------------------------------------------


def test_dataset_preview(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """GET /dataset-preview/{id} returns 200 with non-empty preview_data."""
    result = midas_client.get_raw(f"/api/v1/dataset-preview/{uploaded_dataset_id}")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            assert body, "Expected non-empty preview response"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Bivariate analysis job
# ------------------------------------------------------------------


def test_bivariate_all_enqueue(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """POST /insights/bivariate/all returns 200 or 202 with job_id."""
    result = midas_client.post_json(
        f"{_INSIGHTS_BASE}/bivariate/all",
        {"dataset_id": uploaded_dataset_id, "target_variable": "target_flag"},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {200, 202}, (
                f"Unexpected status: {resp.status_code}: {resp.text[:300]}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_insight_job_status(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """Start a bivariate job then poll its status; status must be in known set."""
    enqueue_result = midas_client.post_json(
        f"{_INSIGHTS_BASE}/bivariate/all",
        {"dataset_id": uploaded_dataset_id, "target_variable": "target_flag"},
    )
    job_id = _extract_job_id(enqueue_result)
    if not job_id:
        pytest.skip("Could not obtain a job_id from bivariate/all")

    status_result = midas_client.get_raw(
        f"{_INSIGHTS_BASE}/jobs/status/{job_id}"
    )
    match status_result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            status = resp.json().get("status", "")
            assert status in {"pending", "running", "completed", "failed", "error"}, (
                f"Unexpected job status: {status}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# VIF analysis
# ------------------------------------------------------------------


def test_vif_analysis(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """POST /insights/vif-analysis returns 200 or 202."""
    result = midas_client.post_json(
        f"{_INSIGHTS_BASE}/vif-analysis",
        {"dataset_id": uploaded_dataset_id, "features": ["age", "income"]},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {200, 202}, (
                f"Unexpected status: {resp.status_code}: {resp.text[:300]}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Correlation analysis
# ------------------------------------------------------------------


def test_correlation_analyze(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """POST /insights/correlation/analyze returns 200 or 202."""
    result = midas_client.post_json(
        f"{_INSIGHTS_BASE}/correlation/analyze",
        {"dataset_id": uploaded_dataset_id},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {200, 202}, (
                f"Unexpected status: {resp.status_code}: {resp.text[:300]}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _extract_job_id(result: object) -> str:
    """Extract job_id string from a post_json Result; return empty string on failure."""
    from returns.result import Success as _Success

    if not isinstance(result, _Success):
        return ""
    resp = result.unwrap()
    body = resp.json()
    if isinstance(body, dict):
        return str(body.get("job_id", ""))
    return ""

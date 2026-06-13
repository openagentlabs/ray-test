"""Integration tests for segmentation endpoints."""

from __future__ import annotations

import pytest
from returns.result import Failure, Success

from testing.api_client.client import MidasHttpClient
from testing.integration.support.auth_guards import skip_on_auth_reject

pytestmark = pytest.mark.segmentation

_SEG_BASE = "/api/v1/segmentation"


# ------------------------------------------------------------------
# run-segmentation (legacy endpoint)
# ------------------------------------------------------------------


def test_run_segmentation_valid(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """POST /run-segmentation with dataset_id and variables returns 200 with segments."""
    result = midas_client.post_json(
        "/api/v1/run-segmentation",
        {
            "dataset_id": uploaded_dataset_id,
            "variables": ["age", "income"],
        },
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200, f"Unexpected: {resp.text[:300]}"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_run_segmentation_missing_dataset(midas_client: MidasHttpClient) -> None:
    """POST /run-segmentation with nonexistent dataset_id does not crash the server."""
    result = midas_client.post_json(
        "/api/v1/run-segmentation",
        {
            "dataset_id": "nonexistent-dataset-00000",
            "variables": ["age"],
        },
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code < 500, (
                f"Server error for unknown dataset: {resp.status_code} {resp.text[:200]}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Unified segmentation
# ------------------------------------------------------------------


def test_unified_segmentation_auto_mode(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """POST /segmentation/run with mode=auto returns 200."""
    result = midas_client.post_json(
        f"{_SEG_BASE}/run",
        {
            "dataset_id": uploaded_dataset_id,
            "mode": "auto",
        },
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {200, 202}, f"Unexpected: {resp.text[:300]}"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Scheme registry
# ------------------------------------------------------------------


def test_scheme_registry(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """GET /segmentation/schemes/{dataset_id} returns 200 with schemes list."""
    result = midas_client.get_raw(f"{_SEG_BASE}/schemes/{uploaded_dataset_id}")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            assert "schemes" in body or isinstance(body, list), (
                f"Unexpected response shape: {body}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Validate rules
# ------------------------------------------------------------------


def test_validate_rules_empty_rules(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """POST /segmentation/validate-rules with empty rules list returns 200 (no error)."""
    result = midas_client.post_json(
        f"{_SEG_BASE}/validate-rules",
        {"dataset_id": uploaded_dataset_id, "rules": []},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200, f"Unexpected: {resp.text[:300]}"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")

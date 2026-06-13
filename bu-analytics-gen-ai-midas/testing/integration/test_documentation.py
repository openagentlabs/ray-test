"""Integration tests for documentation_router — POST endpoints with valid and 422 payloads."""

from __future__ import annotations

import pytest
from returns.result import Failure, Success

from testing.api_client.client import MidasHttpClient
from testing.integration.support.auth_guards import skip_on_auth_reject

pytestmark = pytest.mark.documentation

_DOC_BASE = "/api/v1/documentation"


def _post_doc(
    client: MidasHttpClient,
    path: str,
    body: dict[str, object],
) -> object:
    """POST to a documentation endpoint; return the Result."""
    return client.post_json(path, body)


# ------------------------------------------------------------------
# generate-data-summary
# ------------------------------------------------------------------


def test_generate_data_summary_valid(midas_client: MidasHttpClient) -> None:
    """POST /documentation/generate-data-summary with columns list returns 200."""
    result = _post_doc(
        midas_client,
        f"{_DOC_BASE}/generate-data-summary",
        {"columns": ["age", "income", "target_flag"]},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200, f"Unexpected: {resp.text[:300]}"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_generate_data_summary_missing_columns(midas_client: MidasHttpClient) -> None:
    """POST /documentation/generate-data-summary with empty body returns 422."""
    result = _post_doc(midas_client, f"{_DOC_BASE}/generate-data-summary", {})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 422
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# generate-data-quality-summary
# ------------------------------------------------------------------


def test_generate_data_quality_summary_valid(midas_client: MidasHttpClient) -> None:
    """POST /documentation/generate-data-quality-summary with valid metrics returns 200."""
    result = _post_doc(
        midas_client,
        f"{_DOC_BASE}/generate-data-quality-summary",
        {
            "metrics": {
                "emptyColumns": 0,
                "constantColumns": 0,
                "sparseColumns": 0,
                "formattingIssues": 0,
                "emptyColumnNames": [],
                "constantColumnNames": [],
                "sparseColumnNames": [],
                "formattingIssueColumnNames": [],
            },
            "recommendations": [],
            "totalRows": 100,
            "totalColumns": 3,
        },
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200, f"Unexpected: {resp.text[:300]}"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_generate_data_quality_summary_wrong_type(midas_client: MidasHttpClient) -> None:
    """POST /documentation/generate-data-quality-summary with metrics as string returns 422."""
    result = _post_doc(
        midas_client,
        f"{_DOC_BASE}/generate-data-quality-summary",
        {"metrics": "not-an-object"},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 422
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# generate-target-definition
# ------------------------------------------------------------------


def test_target_definition_valid(midas_client: MidasHttpClient) -> None:
    """POST /documentation/generate-target-definition with valid body returns 200."""
    result = _post_doc(
        midas_client,
        f"{_DOC_BASE}/generate-target-definition",
        {
            "target_variable": "target_flag",
            "target_variable_type": "Categorical",
            "columns": ["age", "income", "target_flag"],
        },
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200, f"Unexpected: {resp.text[:300]}"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_target_definition_missing_field(midas_client: MidasHttpClient) -> None:
    """POST /documentation/generate-target-definition missing required fields returns 422."""
    result = _post_doc(midas_client, f"{_DOC_BASE}/generate-target-definition", {})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 422
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# generate-model-objective
# ------------------------------------------------------------------


def test_model_objective_valid(midas_client: MidasHttpClient) -> None:
    """POST /documentation/generate-model-objective with minimal body returns 200."""
    result = _post_doc(
        midas_client,
        f"{_DOC_BASE}/generate-model-objective",
        {"target_variable": "target_flag", "problem_type": "classification"},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200, f"Unexpected: {resp.text[:300]}"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# event-rate
# ------------------------------------------------------------------


def test_event_rate_missing_field(midas_client: MidasHttpClient) -> None:
    """POST /documentation/calculate-event-rate without required field returns 422."""
    result = _post_doc(midas_client, f"{_DOC_BASE}/calculate-event-rate", {})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 422
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# sampling-plan
# ------------------------------------------------------------------


def test_sampling_plan_missing_field(midas_client: MidasHttpClient) -> None:
    """POST /documentation/get-sampling-plan without required field returns 422."""
    result = _post_doc(midas_client, f"{_DOC_BASE}/get-sampling-plan", {})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 422
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# get-column-stats
# ------------------------------------------------------------------


def test_get_column_stats_missing_field(midas_client: MidasHttpClient) -> None:
    """POST /documentation/get-column-stats without required field returns 422."""
    result = _post_doc(midas_client, f"{_DOC_BASE}/get-column-stats", {})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 422
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# get-variable-analysis
# ------------------------------------------------------------------


def test_get_variable_analysis_missing_field(midas_client: MidasHttpClient) -> None:
    """POST /documentation/get-variable-analysis without required field returns 422."""
    result = _post_doc(midas_client, f"{_DOC_BASE}/get-variable-analysis", {})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 422
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")

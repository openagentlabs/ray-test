"""Integration tests for upload_router — full dataset lifecycle."""

from __future__ import annotations

import pytest
from returns.result import Failure, Success

from testing.api_client.client import MidasHttpClient
from testing.api_client.http_types import MultipartFile
from testing.integration.support.auth_guards import skip_on_auth_reject

pytestmark = pytest.mark.upload

_UPLOAD_PATH = "/api/v1/upload"
_DATASETS_BASE = "/api/v1/datasets"


# ------------------------------------------------------------------
# Upload
# ------------------------------------------------------------------


def test_upload_happy_path(
    midas_client: MidasHttpClient,
    tiny_csv_bytes: bytes,
) -> None:
    """POST /upload with valid multipart returns 200 and dataset_id."""
    file = MultipartFile.new("test.csv", tiny_csv_bytes, "text/csv")
    result = midas_client.post_multipart(
        _UPLOAD_PATH,
        fields={
            "target_variable": "target_flag",
            "target_variable_type": "Categorical",
            "unique_id_combinations": '["age"]',
        },
        files=[file],
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200, f"Upload failed: {resp.text[:300]}"
            body = resp.json()
            assert "dataset_id" in body, f"dataset_id missing from response: {body}"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_upload_no_file(midas_client: MidasHttpClient) -> None:
    """POST /upload with form fields but no file returns 422."""
    result = midas_client.post_multipart(
        _UPLOAD_PATH,
        fields={"target_variable": "target_flag", "target_variable_type": "Categorical"},
        files=[],
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {400, 422}, (
                f"Expected 400/422 for missing file, got {resp.status_code}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_upload_wrong_content_type(midas_client: MidasHttpClient) -> None:
    """POST /upload with JSON body (not multipart) returns 400 or 422."""
    result = midas_client.post_json(
        _UPLOAD_PATH,
        {"target_variable": "target_flag"},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {400, 415, 422}, (
                f"Expected error for wrong content-type, got {resp.status_code}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Dataset list / get
# ------------------------------------------------------------------


def test_datasets_list_after_upload(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """GET /datasets returns 200 and the list contains the uploaded dataset_id."""
    result = midas_client.get_raw(_DATASETS_BASE)
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            ids = _extract_dataset_ids(body)
            assert uploaded_dataset_id in ids, (
                f"Uploaded dataset {uploaded_dataset_id} not found in list"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_dataset_stats(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """GET /datasets/{id}/stats returns 200 with rows > 0 and columns > 0."""
    result = midas_client.get_raw(f"{_DATASETS_BASE}/{uploaded_dataset_id}/stats")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            assert body.get("rows", 0) > 0, "Expected rows > 0"
            assert body.get("columns", 0) > 0, "Expected columns > 0"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_dataset_raw_data(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """GET /datasets/{id}/raw-data returns 200 or 206."""
    result = midas_client.get_raw(f"{_DATASETS_BASE}/{uploaded_dataset_id}/raw-data")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {200, 206}, (
                f"Unexpected status: {resp.status_code}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_dataset_export(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """GET /datasets/{id}/export returns CSV or JSON content-type."""
    result = midas_client.get_raw(f"{_DATASETS_BASE}/{uploaded_dataset_id}/export")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            ct = resp.headers.get("content-type", "")
            assert "csv" in ct or "json" in ct or "octet-stream" in ct, (
                f"Unexpected content-type: {ct}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_dataset_dqs(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """GET /datasets/{id}/dqs returns 200 with composite_score in 0–100."""
    result = midas_client.get_raw(f"{_DATASETS_BASE}/{uploaded_dataset_id}/dqs")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            score = body.get("composite_score")
            if score is not None:
                assert 0 <= float(score) <= 100, f"Score out of range: {score}"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_dataset_overview_bundle(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """GET /datasets/{id}/overview-bundle returns 200."""
    result = midas_client.get_raw(f"{_DATASETS_BASE}/{uploaded_dataset_id}/overview-bundle")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_dataset_column_info(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """GET /datasets/{id}/column-info returns 200."""
    result = midas_client.get_raw(f"{_DATASETS_BASE}/{uploaded_dataset_id}/column-info")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Analyze / detect
# ------------------------------------------------------------------


def test_analyze_dataset(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """POST /analyze-dataset returns 200 or 202."""
    result = midas_client.post_json(
        "/api/v1/analyze-dataset",
        {"dataset_id": uploaded_dataset_id},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code in {200, 202}, (
                f"Unexpected status: {resp.status_code}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_detect_problem_type(
    midas_client: MidasHttpClient,
    uploaded_dataset_id: str,
) -> None:
    """POST /detect-problem-type returns 200 with problem_type in known set."""
    result = midas_client.post_json(
        "/api/v1/detect-problem-type",
        {"dataset_id": uploaded_dataset_id, "target_variable": "target_flag"},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            pt = body.get("problem_type", "")
            assert pt in {"classification", "regression", "unknown", ""}, (
                f"Unexpected problem_type: {pt}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------


def test_dataset_delete_and_missing(
    midas_client: MidasHttpClient,
    tiny_csv_bytes: bytes,
) -> None:
    """DELETE /datasets/{id} returns 200; subsequent GET stats returns 404."""
    file = MultipartFile.new("del_test.csv", tiny_csv_bytes, "text/csv")
    upload_result = midas_client.post_multipart(
        _UPLOAD_PATH,
        fields={"target_variable": "target_flag", "target_variable_type": "Categorical"},
        files=[file],
    )
    match upload_result:
        case Success(up_resp):
            skip_on_auth_reject(up_resp)
            if up_resp.status_code != 200:
                pytest.skip(f"Upload failed with {up_resp.status_code}")
            dataset_id = up_resp.json().get("dataset_id", "")
        case Failure(exc):
            pytest.skip(f"Transport error during upload: {exc}")
            return

    del_result = midas_client.delete(f"{_DATASETS_BASE}/{dataset_id}")
    match del_result:
        case Success(del_resp):
            skip_on_auth_reject(del_resp)
            assert del_resp.status_code == 200
        case Failure(exc):
            pytest.skip(f"Transport error during delete: {exc}")
            return

    get_result = midas_client.get_raw(f"{_DATASETS_BASE}/{dataset_id}/stats")
    match get_result:
        case Success(get_resp):
            assert get_resp.status_code == 404
        case Failure(exc):
            pytest.skip(f"Transport error after delete: {exc}")


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _extract_dataset_ids(body: object) -> set[str]:
    """Extract dataset id strings from a list or paginated response body."""
    if isinstance(body, list):
        return {str(item.get("id", item.get("dataset_id", ""))) for item in body if isinstance(item, dict)}
    if isinstance(body, dict):
        items = body.get("datasets", body.get("items", []))
        if isinstance(items, list):
            return {str(i.get("id", i.get("dataset_id", ""))) for i in items if isinstance(i, dict)}
    return set()

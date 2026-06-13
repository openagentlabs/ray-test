"""Cross-cutting validation error contract tests — FastAPI 422 envelope shape."""

from __future__ import annotations

import pytest
from returns.result import Failure, Success

from testing.api_client.client import MidasHttpClient
from testing.integration.support.auth_guards import skip_on_auth_reject

pytestmark = pytest.mark.validation

_PROJECTS_PATH = "/api/v1/projects"
_CHAT_PATH = "/api/v1/chat"


# ------------------------------------------------------------------
# 422 envelope shape
# ------------------------------------------------------------------


def test_422_envelope_shape(midas_client: MidasHttpClient) -> None:
    """POST /projects with wrong type for name returns 422 with FastAPI detail envelope."""
    result = midas_client.post_json(_PROJECTS_PATH, {"name": 5})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 422, (
                f"Expected 422, got {resp.status_code}: {resp.text[:200]}"
            )
            body = resp.json()
            assert "detail" in body, "422 body must contain 'detail'"
            detail = body["detail"]
            assert isinstance(detail, list), "'detail' must be a list"
            assert len(detail) > 0, "'detail' list must be non-empty"
            first = detail[0]
            assert "loc" in first, "Each 422 detail item must have 'loc'"
            assert "msg" in first, "Each 422 detail item must have 'msg'"
            assert "type" in first, "Each 422 detail item must have 'type'"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Empty body on JSON endpoint
# ------------------------------------------------------------------


def test_empty_body_on_json_endpoint(midas_client: MidasHttpClient) -> None:
    """POST /chat with empty body returns 422."""
    result = midas_client.post_json(_CHAT_PATH, {})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 422, (
                f"Expected 422 for empty body, got {resp.status_code}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Wrong content-type
# ------------------------------------------------------------------


def test_invalid_content_type(midas_client: MidasHttpClient) -> None:
    """POST /chat with Content-Type: text/plain returns 422 or 415."""
    try:
        result = midas_client.request(
            "POST",
            _CHAT_PATH,
            headers={"Content-Type": "text/plain"},
            content=b"hello",
        )
    except Exception as exc:
        pytest.skip(f"Transport error: {exc}")
        return
    assert result.status_code in {415, 422, 400}, (
        f"Expected 415/422/400 for wrong content-type, got {result.status_code}"
    )

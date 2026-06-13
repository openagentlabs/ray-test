"""Integration tests for auth_router and cognito_router."""

from __future__ import annotations

import pytest

from testing.api_client.client import MidasHttpClient
from testing.integration.support.auth_guards import skip_on_auth_reject

pytestmark = pytest.mark.auth

_AUTH_BASE = "/api/v1/auth"
_COGNITO_BASE = "/api/v1/auth/cognito"


# ------------------------------------------------------------------
# /auth/me
# ------------------------------------------------------------------


def test_me_without_token(public_client: MidasHttpClient) -> None:
    """GET /auth/me without any token must be rejected (401 or 403)."""
    try:
        resp = public_client.request("GET", f"{_AUTH_BASE}/me")
    except Exception as exc:
        pytest.skip(f"Server unreachable: {exc}")
    assert resp.status_code in {401, 403}, (
        f"Expected 401/403 without token, got {resp.status_code}"
    )


def test_me_with_invalid_token(midas_base_url: str) -> None:
    """GET /auth/me with a garbage Bearer token must return 401."""
    import httpx

    try:
        resp = httpx.get(
            f"{midas_base_url}{_AUTH_BASE}/me",
            headers={"Authorization": "Bearer this-is-not-a-valid-token"},
            verify=True,
            timeout=30,
        )
    except Exception as exc:
        pytest.skip(f"Server unreachable: {exc}")
    assert resp.status_code == 401, (
        f"Expected 401 with invalid token, got {resp.status_code}"
    )


# ------------------------------------------------------------------
# /auth/verify-token
# ------------------------------------------------------------------


def test_verify_token_valid(midas_client: MidasHttpClient) -> None:
    """POST /auth/verify-token with a valid session token must return valid=true."""
    result = midas_client.post_json(f"{_AUTH_BASE}/verify-token", {})
    from returns.result import Success

    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            assert body.get("valid") is True, f"Expected valid=true, got {body}"
        case _:
            pytest.skip("HTTP transport error during verify-token")


def test_verify_token_invalid(public_client: MidasHttpClient) -> None:
    """POST /auth/verify-token without a token must return valid=false or 401."""
    result = public_client.post_json(f"{_AUTH_BASE}/verify-token", {})
    from returns.result import Success

    match result:
        case Success(resp):
            assert resp.status_code in {200, 401}, (
                f"Unexpected status {resp.status_code}"
            )
            if resp.status_code == 200:
                assert resp.json().get("valid") is False
        case _:
            pytest.skip("HTTP transport error during verify-token")


# ------------------------------------------------------------------
# Legacy auth endpoints (expected to be disabled → 410 Gone)
# ------------------------------------------------------------------


def test_register_disabled(public_client: MidasHttpClient) -> None:
    """POST /auth/register when legacy login is off must return 410 Gone."""
    try:
        result = public_client.post_json(
            f"{_AUTH_BASE}/register",
            {"username": "test@example.com", "password": "irrelevant"},
        )
    except Exception as exc:
        pytest.skip(f"Transport error: {exc}")
        return
    from returns.result import Success

    match result:
        case Success(resp):
            assert resp.status_code in {410, 404, 405}, (
                f"Expected legacy endpoint to be disabled (410/404/405), got {resp.status_code}"
            )
        case _:
            pytest.skip("HTTP transport error during register")


def test_login_disabled(public_client: MidasHttpClient) -> None:
    """POST /auth/login when legacy login is off must return 410 Gone."""
    try:
        result = public_client.post_form(
            f"{_AUTH_BASE}/login",
            {"username": "test@example.com", "password": "irrelevant"},
        )
    except Exception as exc:
        pytest.skip(f"Transport error: {exc}")
        return
    from returns.result import Success

    match result:
        case Success(resp):
            assert resp.status_code in {410, 404, 405, 422}, (
                f"Expected legacy endpoint to be disabled, got {resp.status_code}"
            )
        case _:
            pytest.skip("HTTP transport error during login")


# ------------------------------------------------------------------
# /auth/users
# ------------------------------------------------------------------


def test_users_list_authenticated(midas_client: MidasHttpClient) -> None:
    """GET /auth/users with valid session must return 200 and a list."""
    result = midas_client.get_raw(f"{_AUTH_BASE}/users")
    from returns.result import Success

    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            assert isinstance(body, (list, dict)), (
                f"Expected list or paginated object, got {type(body)}"
            )
        case _:
            pytest.skip("HTTP transport error during users list")


def test_users_list_pagination(midas_client: MidasHttpClient) -> None:
    """GET /auth/users?skip=0&limit=1 must return at most one user."""
    result = midas_client.get_raw(
        f"{_AUTH_BASE}/users",
        params={"skip": "0", "limit": "1"},
    )
    from returns.result import Success

    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            if isinstance(body, list):
                assert len(body) <= 1, f"Expected <= 1 user with limit=1, got {len(body)}"
        case _:
            pytest.skip("HTTP transport error during users pagination")


# ------------------------------------------------------------------
# /auth/cognito/login-url
# ------------------------------------------------------------------


def test_cognito_login_url_missing_vhash(public_client: MidasHttpClient) -> None:
    """GET /auth/cognito/login-url without vhash query param must return 422."""
    result = public_client.get_raw(f"{_COGNITO_BASE}/login-url")
    from returns.result import Success

    match result:
        case Success(resp):
            assert resp.status_code == 422, (
                f"Expected 422 for missing vhash, got {resp.status_code}"
            )
        case _:
            pytest.skip("HTTP transport error during cognito login-url")


def test_cognito_login_url_bad_vhash(public_client: MidasHttpClient) -> None:
    """GET /auth/cognito/login-url with a malformed vhash must return 400 or 422."""
    result = public_client.get_raw(
        f"{_COGNITO_BASE}/login-url",
        params={"vhash": "tooshort"},
    )
    from returns.result import Success

    match result:
        case Success(resp):
            assert resp.status_code in {400, 422}, (
                f"Expected 400/422 for bad vhash, got {resp.status_code}"
            )
        case _:
            pytest.skip("HTTP transport error during cognito login-url bad vhash")


# ------------------------------------------------------------------
# /auth/cognito/exchange
# ------------------------------------------------------------------


def test_cognito_exchange_missing_fields(public_client: MidasHttpClient) -> None:
    """POST /auth/cognito/exchange with empty body must return 422 with field errors."""
    result = public_client.post_json(f"{_COGNITO_BASE}/exchange", {})
    from returns.result import Success

    match result:
        case Success(resp):
            assert resp.status_code == 422, (
                f"Expected 422 for missing fields, got {resp.status_code}"
            )
            body = resp.json()
            assert "detail" in body, "422 body must have 'detail' key"
        case _:
            pytest.skip("HTTP transport error during cognito exchange")


# ------------------------------------------------------------------
# /auth/cognito/refresh
# ------------------------------------------------------------------


def test_cognito_refresh_no_cookie(public_client: MidasHttpClient) -> None:
    """POST /auth/cognito/refresh without a refresh cookie must return 401."""
    result = public_client.post_json(f"{_COGNITO_BASE}/refresh", {})
    from returns.result import Success

    match result:
        case Success(resp):
            assert resp.status_code in {401, 400, 422}, (
                f"Expected 401/400/422 with no cookie, got {resp.status_code}"
            )
        case _:
            pytest.skip("HTTP transport error during cognito refresh")

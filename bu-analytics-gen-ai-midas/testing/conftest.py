"""Shared pytest fixtures for MIDAS integration tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator, Optional

import pytest
from returns.result import Failure, Success

from testing.api_client.auth_protocol import StaticBearerAuthProvider
from testing.api_client.client import MidasHttpClient
from testing.api_client.config import MidasClientConfig
from testing.api_client.credentials import MidasSessionCredentials
from testing.integration.fixtures.csv_factory import build_tiny_csv
from testing.integration.fixtures.upload_state import UploadedDatasetState


def pytest_configure(config: pytest.Config) -> None:
    """Tighten Hypothesis budgets for Schemathesis-driven tests."""
    try:
        from hypothesis import settings

        settings.register_profile("midas_integration", max_examples=5, deadline=None)
        settings.load_profile("midas_integration")
    except ImportError:
        pass


@pytest.fixture(scope="session")
def midas_openapi_get_schema_raw() -> object:
    """Full GET-only OpenAPI document (generated) for Schemathesis."""
    import schemathesis.openapi as openapi

    path = Path(__file__).resolve().parent / "generated" / "openapi_from_inventory_get_only.json"
    if not path.is_file():
        pytest.skip(f"Missing OpenAPI stub: {path} — run testing/scripts/generate_route_inventory.py")
    return openapi.from_path(path)


@pytest.fixture(scope="session")
def midas_base_url() -> str:
    """Backend API origin (scheme + host, no path)."""
    raw = os.environ.get("MIDAS_BASE_URL", "https://exldecision-ai-dev.exlservice.com")
    return raw.strip().rstrip("/")


@pytest.fixture(scope="session")
def midas_session_credentials(midas_base_url: str) -> MidasSessionCredentials:
    """
    Resolve Bearer token: prefer MIDAS_ACCESS_TOKEN, else Playwright SSO once per session.

    For Playwright, set MIDAS_SSO_EMAIL and MIDAS_SSO_PASSWORD.
    Optional: MIDAS_SPA_ORIGIN (defaults to midas_base_url), MIDAS_SESSION_ID, MIDAS_COOKIE_HEADER.
    """
    token = os.environ.get("MIDAS_ACCESS_TOKEN", "").strip()
    if token:
        sid: Optional[str] = os.environ.get("MIDAS_SESSION_ID", "").strip() or None
        cookie: Optional[str] = os.environ.get("MIDAS_COOKIE_HEADER", "").strip() or None
        return MidasSessionCredentials(
            access_token=token,
            session_id=sid,
            cookie_header_value=cookie,
        )

    from testing.integration.sso_playwright import PlaywrightSsoOptions, obtain_credentials_via_playwright

    spa = os.environ.get("MIDAS_SPA_ORIGIN", midas_base_url).strip().rstrip("/")
    email = os.environ.get("MIDAS_SSO_EMAIL", "").strip()
    password = os.environ.get("MIDAS_SSO_PASSWORD", "").strip()

    # Interactive mode: browser opens, user logs in manually.
    # Automated mode: only when both email AND password are set.
    interactive = not (email and password)

    opts = PlaywrightSsoOptions(
        spa_origin=spa,
        interactive=interactive,
        slow_mo_ms=int(os.environ.get("PLAYWRIGHT_SLOW_MO_MS", "0")),
        navigation_timeout_ms=int(os.environ.get("PLAYWRIGHT_NAV_TIMEOUT_MS", "300000")),
        sso_email=email or None,
        sso_password=password or None,
    )
    return obtain_credentials_via_playwright(opts)


@pytest.fixture(scope="session")
def midas_client(
    midas_base_url: str,
    midas_session_credentials: MidasSessionCredentials,
) -> Generator[MidasHttpClient, None, None]:
    """Authenticated MidasHttpClient for the whole test session."""
    cfg = MidasClientConfig(
        base_url=midas_base_url,
        timeout_seconds=float(os.environ.get("MIDAS_HTTP_TIMEOUT", "120")),
        verify_tls=os.environ.get("MIDAS_VERIFY_TLS", "1") != "0",
    )
    auth = StaticBearerAuthProvider(midas_session_credentials)
    client = MidasHttpClient(cfg, auth)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def public_client(midas_base_url: str) -> Generator[MidasHttpClient, None, None]:
    """Unauthenticated client (empty auth headers via anonymous provider)."""

    class _AnonymousAuth:
        def request_headers(self) -> dict[str, str]:
            return {}

    cfg = MidasClientConfig(base_url=midas_base_url)
    client = MidasHttpClient(cfg, _AnonymousAuth())
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def tiny_csv_bytes() -> bytes:
    """Synthesised 20-row CSV — no file dependency."""
    return build_tiny_csv()


@pytest.fixture(scope="session")
def uploaded_dataset_id(
    midas_client: MidasHttpClient,
    tiny_csv_bytes: bytes,
) -> str:
    """Upload the tiny CSV once per session; return dataset_id for dataset-dependent tests."""
    result = UploadedDatasetState.new(midas_client, tiny_csv_bytes)
    match result:
        case Success(state):
            return state.dataset_id
        case Failure(exc):
            pytest.skip(f"Dataset upload unavailable (skipping dependent tests): {exc}")
    raise RuntimeError("unreachable")

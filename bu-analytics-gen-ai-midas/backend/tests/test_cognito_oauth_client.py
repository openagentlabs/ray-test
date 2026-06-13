"""Tests for the confidential vs. public app-client auth mode in oauth_client."""

import unittest
from dataclasses import dataclass, field
from typing import FrozenSet, Optional

import httpx

from app.services.cognito.oauth_client import _auth_for


@dataclass(frozen=True)
class _FakeCfg:
    """Minimal stand-in for CognitoSettings — only the fields _auth_for touches."""
    client_id: str = "abc123"
    client_secret: Optional[str] = None
    # Fields below are unused by _auth_for but required to mimic the real dataclass shape.
    domain: str = "https://example.com"
    region: str = "us-east-1"
    user_pool_id: str = "us-east-1_XXX"
    redirect_uris: FrozenSet[str] = field(default_factory=frozenset)
    logout_redirect_uri: str = "https://example.com/"
    scopes: str = "openid"
    idp_name: Optional[str] = None
    cookie_secure: bool = True
    login_cookie_secret: str = "x" * 40
    login_cookie_ttl_seconds: int = 600
    refresh_cookie_ttl_seconds: int = 3600


class TestOAuthClientAuthMode(unittest.TestCase):
    def test_public_spa_client_returns_none(self) -> None:
        """No client_secret -> _auth_for returns None (httpx skips Authorization header)."""
        self.assertIsNone(_auth_for(_FakeCfg(client_secret=None)))

    def test_public_spa_client_empty_string_returns_none(self) -> None:
        """Treat empty-string secret (from `COGNITO_CLIENT_SECRET=` in .env) as absent."""
        self.assertIsNone(_auth_for(_FakeCfg(client_secret="")))

    def test_confidential_client_returns_basic_auth(self) -> None:
        """With a secret -> httpx.BasicAuth instance with the configured credentials."""
        auth = _auth_for(_FakeCfg(client_id="my-id", client_secret="my-secret"))
        self.assertIsInstance(auth, httpx.BasicAuth)
        # httpx.BasicAuth stores credentials as a pre-encoded header; verify by roundtripping a request.
        req = httpx.Request("POST", "https://example.com/token")
        flow = auth.sync_auth_flow(req)  # type: ignore[attr-defined]
        signed = next(flow)
        header = signed.headers.get("Authorization", "")
        self.assertTrue(header.startswith("Basic "))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

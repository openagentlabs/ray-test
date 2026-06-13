"""
Runtime configuration for the Cognito integration.

Derives URLs (authorize, token, logout, revoke, JWKS) from the raw values in
``app.core.config.settings`` and validates the redirect-URI allowlist once at
process start so misconfigurations fail fast instead of at the first login.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from typing import FrozenSet, Optional

from app.core.config import settings as app_settings


class CognitoConfigError(RuntimeError):
    """Raised when Cognito integration is used while required settings are missing."""


@dataclass(frozen=True)
class CognitoSettings:
    domain: str
    region: str
    user_pool_id: str
    client_id: str
    client_secret: Optional[str]  # None for public SPA app clients (PKCE-only)
    redirect_uris: FrozenSet[str]
    logout_redirect_uri: str
    scopes: str
    idp_name: Optional[str]
    cookie_secure: bool
    login_cookie_secret: str
    login_cookie_ttl_seconds: int
    refresh_cookie_ttl_seconds: int

    # Computed URLs
    authorize_url: str = field(init=False)
    token_url: str = field(init=False)
    logout_url: str = field(init=False)
    revoke_url: str = field(init=False)
    jwks_url: str = field(init=False)
    issuer: str = field(init=False)

    def __post_init__(self) -> None:
        base = self.domain.rstrip("/")
        object.__setattr__(self, "authorize_url", f"{base}/oauth2/authorize")
        object.__setattr__(self, "token_url", f"{base}/oauth2/token")
        object.__setattr__(self, "logout_url", f"{base}/logout")
        object.__setattr__(self, "revoke_url", f"{base}/oauth2/revoke")
        object.__setattr__(
            self,
            "jwks_url",
            f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}/.well-known/jwks.json",
        )
        object.__setattr__(
            self,
            "issuer",
            f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}",
        )

    # -- helpers -------------------------------------------------------------

    def redirect_uri_allowed(self, redirect_uri: str) -> bool:
        """Exact-match check against the configured allowlist."""
        return redirect_uri in self.redirect_uris

    def primary_redirect_uri(self) -> str:
        """First configured redirect URI (used when frontend did not send one)."""
        return next(iter(self.redirect_uris))


def _parse_redirect_uris(raw: Optional[str]) -> FrozenSet[str]:
    if not raw:
        return frozenset()
    return frozenset(u.strip() for u in raw.split(",") if u.strip())


@lru_cache(maxsize=1)
def get_cognito_settings() -> CognitoSettings:
    """
    Build and cache ``CognitoSettings`` from ``app.core.config.settings``.

    Raises ``CognitoConfigError`` with a clear message listing missing fields
    so operators see what to set in ``.env`` / Secrets Manager.
    """
    required = {
        "COGNITO_DOMAIN": app_settings.COGNITO_DOMAIN,
        "COGNITO_REGION": app_settings.COGNITO_REGION,
        "COGNITO_USER_POOL_ID": app_settings.COGNITO_USER_POOL_ID,
        "COGNITO_CLIENT_ID": app_settings.COGNITO_CLIENT_ID,
        # COGNITO_CLIENT_SECRET is intentionally NOT required — public SPA app
        # clients rely on PKCE only and do not have a client secret.
        "COGNITO_REDIRECT_URIS": app_settings.COGNITO_REDIRECT_URIS,
        "COGNITO_LOGOUT_REDIRECT_URI": app_settings.COGNITO_LOGOUT_REDIRECT_URI,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise CognitoConfigError(
            "Cognito integration misconfigured. Missing: " + ", ".join(missing)
        )

    redirect_uris = _parse_redirect_uris(app_settings.COGNITO_REDIRECT_URIS)
    if not redirect_uris:
        raise CognitoConfigError("COGNITO_REDIRECT_URIS must contain at least one URI")

    # Login cookie secret: dev fallback to a random per-process value; prod must be set.
    # Note: with the dev fallback, any in-flight logins are invalidated on backend restart.
    cookie_secret = app_settings.COGNITO_LOGIN_COOKIE_SECRET
    if not cookie_secret:
        if app_settings.APP_ENV == "production":
            raise CognitoConfigError(
                "COGNITO_LOGIN_COOKIE_SECRET is required when APP_ENV=production"
            )
        cookie_secret = secrets.token_urlsafe(48)

    return CognitoSettings(
        domain=str(app_settings.COGNITO_DOMAIN).rstrip("/"),
        region=str(app_settings.COGNITO_REGION),
        user_pool_id=str(app_settings.COGNITO_USER_POOL_ID),
        client_id=str(app_settings.COGNITO_CLIENT_ID),
        client_secret=str(app_settings.COGNITO_CLIENT_SECRET) if app_settings.COGNITO_CLIENT_SECRET else None,
        redirect_uris=redirect_uris,
        logout_redirect_uri=str(app_settings.COGNITO_LOGOUT_REDIRECT_URI),
        scopes=app_settings.COGNITO_SCOPES,
        idp_name=app_settings.COGNITO_IDP_NAME,
        cookie_secure=bool(app_settings.COGNITO_COOKIE_SECURE),
        login_cookie_secret=cookie_secret,
        login_cookie_ttl_seconds=int(app_settings.COGNITO_LOGIN_COOKIE_TTL),
        refresh_cookie_ttl_seconds=int(app_settings.COGNITO_REFRESH_COOKIE_TTL_DAYS) * 24 * 3600,
    )


def cognito_is_configured() -> bool:
    """Non-throwing check used by diagnostics / conditional router registration."""
    try:
        get_cognito_settings()
        return True
    except CognitoConfigError:
        return False

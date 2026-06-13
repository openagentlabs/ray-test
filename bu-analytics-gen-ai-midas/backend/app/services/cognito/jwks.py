"""
Cognito JWKS fetch + JWT verification.

Design:
- Async TTL cache (default 1h) around the JWKS document.
- Single-flight: concurrent verifications share one in-flight fetch via ``asyncio.Lock``.
- Force-refresh on unknown ``kid`` so key rotation does not require a process restart.
- Strict RS256 verification with ``iss`` / ``aud`` (id tokens) / ``client_id`` (access tokens)
  / ``token_use`` / ``exp`` / ``nbf`` / ``nonce`` (when provided) and 30s clock skew leeway.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Literal, Optional

import httpx
from jose import jwt
from jose.exceptions import JWTError
from jose.utils import base64url_decode  # noqa: F401  (ensures jose crypto module loads)

from app.services.cognito.settings import CognitoSettings, get_cognito_settings

logger = logging.getLogger(__name__)

_JWKS_TTL_SECONDS = 3600
_HTTP_TIMEOUT_SECONDS = 10
_CLOCK_SKEW_LEEWAY_SECONDS = 30

TokenUse = Literal["id", "access"]


class CognitoTokenInvalid(Exception):
    """Raised when a Cognito token fails signature or claim validation."""


class _JwksCache:
    """Process-local JWKS cache with async single-flight refresh."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._jwks: Optional[Dict[str, Any]] = None
        self._fetched_at: float = 0.0

    def _expired(self) -> bool:
        return (time.time() - self._fetched_at) > _JWKS_TTL_SECONDS

    async def get(self, url: str, *, force: bool = False) -> Dict[str, Any]:
        if not force and self._jwks is not None and not self._expired():
            return self._jwks
        async with self._lock:
            # Re-check inside lock; another coroutine may have refreshed it.
            if not force and self._jwks is not None and not self._expired():
                return self._jwks
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            if not isinstance(data, dict) or "keys" not in data:
                raise CognitoTokenInvalid("Malformed JWKS document")
            self._jwks = data
            self._fetched_at = time.time()
            logger.info("Cognito JWKS refreshed (%d keys)", len(data.get("keys", [])))
            return data

    def clear(self) -> None:
        self._jwks = None
        self._fetched_at = 0.0


_cache = _JwksCache()


async def get_jwks(*, force: bool = False) -> Dict[str, Any]:
    settings = get_cognito_settings()
    return await _cache.get(settings.jwks_url, force=force)


def _find_key(jwks: Dict[str, Any], kid: str) -> Optional[Dict[str, Any]]:
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


async def verify_cognito_jwt(
    token: str,
    expected_use: TokenUse,
    *,
    nonce: Optional[str] = None,
    access_token: Optional[str] = None,
    settings: Optional[CognitoSettings] = None,
) -> Dict[str, Any]:
    """
    Verify signature + standard claims for a Cognito-issued JWT.

    Parameters
    ----------
    token:
        The raw JWT string.
    expected_use:
        ``"id"`` for id tokens (audience must match client_id), ``"access"`` for access
        tokens (``client_id`` claim must match).
    nonce:
        When provided (id tokens only), must equal the token's ``nonce`` claim.
    access_token:
        When provided (id tokens only), used to verify the ``at_hash`` claim.
    settings:
        Injectable for tests; defaults to ``get_cognito_settings()``.

    Returns
    -------
    The validated claims dict.

    Raises
    ------
    CognitoTokenInvalid
        On any validation failure. The message is safe to log but should not be
        echoed to clients verbatim (see ``cognito_routes.py`` which collapses to 401).
    """
    cfg = settings or get_cognito_settings()
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise CognitoTokenInvalid(f"Invalid JWT header: {exc}") from exc

    kid = unverified_header.get("kid")
    alg = unverified_header.get("alg")
    if alg != "RS256":
        raise CognitoTokenInvalid(f"Unexpected JWT alg: {alg}")
    if not kid:
        raise CognitoTokenInvalid("JWT header missing 'kid'")

    jwks = await get_jwks()
    key = _find_key(jwks, kid)
    if key is None:
        # Key rotation: force-refresh once before giving up.
        logger.info("Cognito JWKS kid miss; forcing refresh")
        jwks = await get_jwks(force=True)
        key = _find_key(jwks, kid)
        if key is None:
            raise CognitoTokenInvalid("Signing key not found for token kid")

    decode_kwargs: Dict[str, Any] = {
        "algorithms": ["RS256"],
        "issuer": cfg.issuer,
        "options": {"leeway": _CLOCK_SKEW_LEEWAY_SECONDS, "require_exp": True},
    }
    if expected_use == "id":
        # For id tokens python-jose verifies the ``aud`` claim when ``audience`` is set.
        decode_kwargs["audience"] = cfg.client_id

    try:
        claims = jwt.decode(token, key, access_token=access_token, **decode_kwargs)
    except JWTError as exc:
        raise CognitoTokenInvalid(f"JWT signature or claims invalid: {exc}") from exc

    # token_use enforcement (Cognito-specific).
    token_use = claims.get("token_use")
    if token_use != expected_use:
        raise CognitoTokenInvalid(
            f"token_use mismatch: expected {expected_use!r}, got {token_use!r}"
        )

    if expected_use == "access":
        # Access tokens do NOT carry ``aud``; instead Cognito puts the app client id in ``client_id``.
        if claims.get("client_id") != cfg.client_id:
            raise CognitoTokenInvalid("access token client_id does not match configured app client")

    if nonce is not None:
        if claims.get("nonce") != nonce:
            raise CognitoTokenInvalid("id token nonce mismatch")

    return claims


def _reset_cache_for_tests() -> None:  # pragma: no cover - test hook
    _cache.clear()

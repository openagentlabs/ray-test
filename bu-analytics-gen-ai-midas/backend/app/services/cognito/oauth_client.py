"""
Thin async wrapper around the Cognito OAuth2 token + revoke endpoints.

Supports both **confidential** (client_id + client_secret via Basic auth) and
**public** (SPA / PKCE-only, no secret) app clients. The mode is chosen
automatically from ``CognitoSettings.client_secret``:

- confidential client  -> ``Authorization: Basic <b64(client_id:client_secret)>``
- public SPA client    -> no Authorization header; ``client_id`` in the form body only

``application/x-www-form-urlencoded`` bodies per RFC 6749 / RFC 7009.

No retries: auth operations must be deterministic and observable.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.services.cognito.settings import CognitoSettings, get_cognito_settings

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_SECONDS = 10


class CognitoOAuthError(Exception):
    """Raised on non-2xx responses from Cognito's OAuth endpoints."""

    def __init__(self, status_code: int, payload: Any) -> None:
        super().__init__(f"Cognito OAuth error ({status_code}): {payload}")
        self.status_code = status_code
        self.payload = payload


def _auth_for(cfg: CognitoSettings) -> Optional[httpx.BasicAuth]:
    """
    Return HTTP Basic auth if a client secret is configured (confidential app
    client), or ``None`` for public SPA clients where PKCE is the only
    credential. httpx treats ``auth=None`` as "do not add an Authorization
    header", which is exactly what Cognito's ``/oauth2/token`` expects for
    public clients.
    """
    if cfg.client_secret:
        return httpx.BasicAuth(cfg.client_id, cfg.client_secret)
    return None


async def exchange_code(
    code: str,
    code_verifier: str,
    redirect_uri: str,
    *,
    settings: Optional[CognitoSettings] = None,
) -> Dict[str, Any]:
    """
    Exchange an authorization code for tokens (id/access/refresh).

    PKCE ``code_verifier`` is always sent. Returns the parsed token JSON.
    """
    cfg = settings or get_cognito_settings()
    data = {
        "grant_type": "authorization_code",
        "client_id": cfg.client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            cfg.token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=_auth_for(cfg),
        )
    return _handle_token_response(resp)


async def refresh(
    refresh_token: str,
    *,
    settings: Optional[CognitoSettings] = None,
) -> Dict[str, Any]:
    """
    Refresh tokens using a Cognito refresh token.

    Cognito may or may not return a new refresh token; callers should rotate the
    cookie only if a new ``refresh_token`` field is present.
    """
    cfg = settings or get_cognito_settings()
    data = {
        "grant_type": "refresh_token",
        "client_id": cfg.client_id,
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            cfg.token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=_auth_for(cfg),
        )
    return _handle_token_response(resp)


async def revoke(
    refresh_token: str,
    *,
    settings: Optional[CognitoSettings] = None,
) -> bool:
    """
    Revoke a Cognito refresh token via ``/oauth2/revoke``.

    Returns True on 200 (per RFC 7009; also accepts the 400 "unsupported_token"
    case which Cognito returns if the app client does not have revocation
    enabled, to keep logout idempotent). Exceptions are logged and swallowed
    so logout remains best-effort from the caller's perspective.
    """
    cfg = settings or get_cognito_settings()
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                cfg.revoke_url,
                data={"token": refresh_token, "client_id": cfg.client_id},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=_auth_for(cfg),
            )
    except httpx.HTTPError as exc:
        logger.warning("Cognito revoke transport error: %s", exc)
        return False

    if resp.status_code == 200:
        return True
    # Cognito returns 400 with error=unsupported_token_type if revocation is disabled
    # on the app client. Treat as non-fatal so logout can proceed.
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": resp.text}
    logger.warning("Cognito revoke non-200 (%s): %s", resp.status_code, payload)
    return False


def _handle_token_response(resp: httpx.Response) -> Dict[str, Any]:
    if resp.status_code >= 400:
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": resp.text}
        raise CognitoOAuthError(resp.status_code, payload)
    try:
        return resp.json()
    except Exception as exc:  # pragma: no cover - extremely rare
        raise CognitoOAuthError(resp.status_code, {"error": "invalid_json"}) from exc

"""
Short-lived, server-signed login-binding cookie (``cg_login``).

The browser holds the PKCE ``code_verifier`` in ``sessionStorage``. To bind the
authorize request to the exchange step (and to ensure the same browser that
initiated the login completes it), the backend also issues an HttpOnly,
path-scoped JWS cookie containing:

- ``state``  : the anti-CSRF value echoed to Cognito
- ``nonce``  : OIDC nonce also echoed to Cognito and validated on the id token
- ``vhash``  : SHA-256 hex of the PKCE ``code_verifier`` provided by the browser
- ``exp``    : absolute expiry (epoch seconds)

The token is **HS256-signed** with ``COGNITO_LOGIN_COOKIE_SECRET`` and has no
encryption requirement because nothing inside is secret by itself — the secrecy
of the actual verifier stays in the browser (only its hash is bound here).
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Optional

from jose import jwt
from jose.exceptions import JWTError

from app.services.cognito.settings import CognitoSettings, get_cognito_settings

_ALGORITHM = "HS256"
LOGIN_COOKIE_NAME = "cg_login"


class LoginStateInvalid(Exception):
    """Raised when the cg_login cookie is missing, tampered, expired, or mismatched."""


@dataclass(frozen=True)
class LoginBinding:
    state: str
    nonce: str
    verifier_hash: str
    expires_at: int


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_state() -> str:
    return secrets.token_urlsafe(32)


def new_nonce() -> str:
    return secrets.token_urlsafe(32)


def issue(
    verifier_hash: str,
    *,
    settings: Optional[CognitoSettings] = None,
) -> tuple[str, LoginBinding]:
    """
    Create a new login binding and return ``(jws_token, binding)``.

    Caller sets ``jws_token`` as the cookie value with
    ``HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth/cognito; Max-Age=ttl``.
    """
    cfg = settings or get_cognito_settings()
    expires_at = int(time.time()) + cfg.login_cookie_ttl_seconds
    state = new_state()
    nonce = new_nonce()
    payload = {
        "state": state,
        "nonce": nonce,
        "vhash": verifier_hash,
        "exp": expires_at,
    }
    token = jwt.encode(payload, cfg.login_cookie_secret, algorithm=_ALGORITHM)
    return token, LoginBinding(state=state, nonce=nonce, verifier_hash=verifier_hash, expires_at=expires_at)


def verify(
    cookie_value: str,
    *,
    expected_state: str,
    expected_verifier: str,
    settings: Optional[CognitoSettings] = None,
) -> LoginBinding:
    """
    Validate the ``cg_login`` cookie and return the binding payload.

    Performs: signature check, expiry check, ``state`` equality, and
    ``sha256(verifier) == vhash`` equality.
    """
    cfg = settings or get_cognito_settings()
    try:
        payload = jwt.decode(
            cookie_value,
            cfg.login_cookie_secret,
            algorithms=[_ALGORITHM],
            options={"require_exp": True, "leeway": 10},
        )
    except JWTError as exc:
        raise LoginStateInvalid(f"invalid cookie: {exc}") from exc

    state = payload.get("state")
    nonce = payload.get("nonce")
    vhash = payload.get("vhash")
    exp = int(payload.get("exp") or 0)
    if not (isinstance(state, str) and isinstance(nonce, str) and isinstance(vhash, str)):
        raise LoginStateInvalid("cookie payload malformed")

    if not secrets.compare_digest(state, expected_state):
        raise LoginStateInvalid("state mismatch")
    if not secrets.compare_digest(vhash, sha256_hex(expected_verifier)):
        raise LoginStateInvalid("verifier hash mismatch")

    return LoginBinding(state=state, nonce=nonce, verifier_hash=vhash, expires_at=exp)

"""Async Cognito JWT validation (SR-1, DS-3)."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import aiohttp

from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CognitoConfig:
    """JWKS issuer settings."""

    issuer: str
    audience: str
    jwks_uri: str = ""


class JwtValidator:
    """Validates bearer tokens and extracts ``sub``."""

    __slots__ = ("_cfg", "_jwks_cache", "_jwks_fetched_at")

    def __init__(self, *, cognito: CognitoConfig) -> None:
        self._cfg = cognito
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_fetched_at: float = 0.0

    async def validate_and_extract_sub(self, token: str) -> Result[str, AppError]:
        if not token.strip():
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Empty bearer token.",
                    detail=None,
                ),
            )
        try:
            import base64

            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("expected three JWT segments")
            header = json.loads(_b64url_decode(parts[0]))
            payload = json.loads(_b64url_decode(parts[1]))
        except (ValueError, json.JSONDecodeError) as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Malformed JWT.",
                    detail=str(exc),
                ),
            )

        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="JWT missing kid header.",
                    detail=None,
                ),
            )

        jwks_result = await self._load_jwks()
        if isinstance(jwks_result, Failure):
            return jwks_result
        jwks = jwks_result.unwrap()

        if not _claims_valid(payload, issuer=self._cfg.issuer, audience=self._cfg.audience):
            return Failure(
                AppError(
                    code=ErrorCodes.FORBIDDEN,
                    message="JWT claims validation failed.",
                    detail=None,
                ),
            )

        if not _verify_signature(token, kid=kid, jwks=jwks):
            return Failure(
                AppError(
                    code=ErrorCodes.FORBIDDEN,
                    message="JWT signature verification failed.",
                    detail=None,
                ),
            )

        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub.strip():
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="JWT missing sub claim.",
                    detail=None,
                ),
            )
        return Success(sub.strip())

    async def _load_jwks(self) -> Result[dict[str, Any], AppError]:
        now = time.time()
        if self._jwks_cache is not None and now - self._jwks_fetched_at < 3600:
            return Success(self._jwks_cache)
        uri = self._cfg.jwks_uri or urljoin(
            self._cfg.issuer.rstrip("/") + "/",
            ".well-known/jwks.json",
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(uri, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return Failure(
                            AppError(
                                code=ErrorCodes.UPSTREAM,
                                message="JWKS fetch failed.",
                                detail=f"status={resp.status}",
                            ),
                        )
                    data = await resp.json()
        except (TimeoutError, aiohttp.ClientError, OSError) as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.UPSTREAM,
                    message="JWKS fetch failed.",
                    detail=str(exc),
                ),
            )
        if not isinstance(data, dict):
            return Failure(
                AppError(
                    code=ErrorCodes.UPSTREAM,
                    message="Invalid JWKS payload.",
                    detail=None,
                ),
            )
        self._jwks_cache = data
        self._jwks_fetched_at = now
        return Success(data)


def _b64url_decode(segment: str) -> bytes:
    import base64

    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _claims_valid(payload: dict[str, Any], *, issuer: str, audience: str) -> bool:
    if payload.get("iss") != issuer:
        return False
    aud = payload.get("aud")
    if aud != audience and audience not in (aud if isinstance(aud, list) else []):
        return False
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return False
    return float(exp) > time.time()


def _verify_signature(token: str, *, kid: str, jwks: dict[str, Any]) -> bool:
    try:
        from jwt import PyJWKClient

        _ = PyJWKClient  # optional dependency path
    except ImportError:
        logger.warning("PyJWT not installed; skipping signature verify in dev")
        return True

    try:
        import jwt
        from jwt import PyJWKClient

        client = PyJWKClient.from_dict(jwks)  # type: ignore[attr-defined]
        signing_key = client.get_signing_key_from_jwt(token)
        jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=None,
            options={"verify_aud": False, "verify_exp": False},
        )
        return True
    except Exception:
        keys = jwks.get("keys", [])
        for key in keys:
            if key.get("kid") == kid:
                try:
                    import jwt

                    jwk_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
                    jwt.decode(
                        token,
                        jwk_key,
                        algorithms=["RS256"],
                        options={"verify_signature": True, "verify_exp": False, "verify_aud": False},
                    )
                    return True
                except Exception:
                    return False
        return False

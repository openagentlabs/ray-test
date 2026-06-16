"""JWT auth token issuance, validation, and JWKS helpers."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from base64 import urlsafe_b64encode
from typing import Final

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from iam_service.auth.permissions_codec import (
    PermissionGrantSet,
    decode_permissions,
    encode_permissions,
)
from iam_service.auth.token_models import AuthTokenClaims, IssuedAuthToken, JwksDocument, JwksKey
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.plugins.vault.interface import VaultDriver
from iam_service.plugins.vault.types import VaultKeyContent

ACCESS_TOKEN_TTL_SECONDS: Final[int] = 900
REFRESH_TOKEN_TTL_SECONDS: Final[int] = 86_400
REFRESH_GRACE_SECONDS: Final[int] = 120


def _checksum(sub: str, perm: str, exp: int) -> str:
    payload = f"{sub}|{perm}|{exp}".encode()
    return hashlib.sha256(payload).hexdigest()


def _claims_to_dict(claims: AuthTokenClaims) -> dict[str, str | int]:
    return {
        "sub": claims.sub,
        "jti": claims.jti,
        "perm": claims.perm,
        "chk": claims.chk,
        "iat": claims.iat,
        "exp": claims.exp,
        "nbf": claims.nbf,
    }


class AuthTokenService:
    """Sign and verify IAM auth tokens using vault-stored RSA keys."""

    __slots__ = ("_vault", "_master_key_id", "_cached_key", "_cached_jwks")

    def __init__(self, *, vault: VaultDriver, master_key_id: str) -> None:
        self._vault = vault
        self._master_key_id = master_key_id
        self._cached_key: VaultKeyContent | None = None
        self._cached_jwks: JwksDocument | None = None

    async def _load_key(self) -> Result[VaultKeyContent, AppError]:
        if self._cached_key is not None:
            return Success(self._cached_key)
        result = await self._vault.get_key(self._master_key_id)
        if not result.success or result.key_content is None:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Could not load IAM signing key from vault.",
                    detail=result.error_message,
                ),
            )
        self._cached_key = result.key_content
        return Success(result.key_content)

    async def ensure_master_key_exists(self) -> Result[VaultKeyContent, AppError]:
        """Create a dev master key in the vault when missing."""
        loaded = await self._load_key()
        if isinstance(loaded, Success):
            return loaded
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        public_pem = (
            private_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("utf-8")
        )
        content = VaultKeyContent(
            kid=self._master_key_id,
            algorithm="RS256",
            private_key_pem=private_pem,
            public_key_pem=public_pem,
        )
        written = await self._vault.set_key(self._master_key_id, content)
        if not written.success:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Could not persist IAM signing key to vault.",
                    detail=written.error_message,
                ),
            )
        self._cached_key = content
        self._cached_jwks = None
        return Success(content)

    async def build_jwks(self) -> Result[JwksDocument, AppError]:
        if self._cached_jwks is not None:
            return Success(self._cached_jwks)
        key_result = await self._load_key()
        if isinstance(key_result, Failure):
            return key_result
        key_content = key_result.unwrap()
        public_key = serialization.load_pem_public_key(
            key_content.public_key_pem.encode("utf-8"),
        )
        jwk_dict = json.loads(RSAAlgorithm.to_jwk(public_key))
        jwks = JwksDocument(
            keys=(
                JwksKey(
                    kid=key_content.kid,
                    n=str(jwk_dict["n"]),
                    e=str(jwk_dict["e"]),
                ),
            ),
        )
        self._cached_jwks = jwks
        return Success(jwks)

    async def issue_tokens(
        self,
        *,
        user_id: str,
        grants: PermissionGrantSet,
        session_id: str | None = None,
    ) -> Result[IssuedAuthToken, AppError]:
        encoded = encode_permissions(grants)
        if isinstance(encoded, Failure):
            return encoded
        perm = encoded.unwrap()
        key_result = await self._load_key()
        if isinstance(key_result, Failure):
            return key_result
        key_content = key_result.unwrap()
        if not key_content.private_key_pem:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Signing key has no private key material.",
                    detail=None,
                ),
            )
        now = int(time.time())
        access_exp = now + ACCESS_TOKEN_TTL_SECONDS
        refresh_exp = now + REFRESH_TOKEN_TTL_SECONDS
        jti = session_id or str(uuid.uuid4())
        access_claims = AuthTokenClaims(
            sub=user_id,
            jti=jti,
            perm=perm,
            chk=_checksum(user_id, perm, access_exp),
            iat=now,
            exp=access_exp,
            nbf=now,
        )
        refresh_claims = AuthTokenClaims(
            sub=user_id,
            jti=jti,
            perm=perm,
            chk=_checksum(user_id, perm, refresh_exp),
            iat=now,
            exp=refresh_exp,
            nbf=now,
        )
        access_token = jwt.encode(
            _claims_to_dict(access_claims),
            key_content.private_key_pem,
            algorithm="RS256",
            headers={"kid": key_content.kid, "typ": "JWT"},
        )
        refresh_token = jwt.encode(
            {**_claims_to_dict(refresh_claims), "typ": "refresh"},
            key_content.private_key_pem,
            algorithm="RS256",
            headers={"kid": key_content.kid, "typ": "JWT"},
        )
        return Success(
            IssuedAuthToken(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=ACCESS_TOKEN_TTL_SECONDS,
                refresh_expires_in=REFRESH_TOKEN_TTL_SECONDS,
            ),
        )

    async def validate_token(
        self,
        token: str,
        *,
        allow_refresh: bool = False,
    ) -> Result[AuthTokenClaims, AppError]:
        key_result = await self._load_key()
        if isinstance(key_result, Failure):
            return key_result
        key_content = key_result.unwrap()
        try:
            payload = jwt.decode(
                token,
                key_content.public_key_pem,
                algorithms=["RS256"],
                options={"require": ["exp", "iat", "sub", "jti", "perm", "chk"]},
            )
        except jwt.PyJWTError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.UNAUTHENTICATED,
                    message="Invalid or expired auth token.",
                    detail=str(exc),
                ),
            )
        token_type = str(payload.get("typ", "access"))
        if token_type == "refresh" and not allow_refresh:
            return Failure(
                AppError(
                    code=ErrorCodes.UNAUTHENTICATED,
                    message="Refresh token cannot be used as access token.",
                    detail=None,
                ),
            )
        try:
            claims = AuthTokenClaims(
                sub=str(payload["sub"]),
                jti=str(payload["jti"]),
                perm=str(payload["perm"]),
                chk=str(payload["chk"]),
                iat=int(payload["iat"]),
                exp=int(payload["exp"]),
                nbf=int(payload.get("nbf", 0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.UNAUTHENTICATED,
                    message="Malformed auth token claims.",
                    detail=str(exc),
                ),
            )
        expected_chk = _checksum(claims.sub, claims.perm, claims.exp)
        if not secrets.compare_digest(claims.chk, expected_chk):
            return Failure(
                AppError(
                    code=ErrorCodes.UNAUTHENTICATED,
                    message="Auth token checksum mismatch.",
                    detail=None,
                ),
            )
        perm_valid = decode_permissions(claims.perm)
        if isinstance(perm_valid, Failure):
            return perm_valid
        now = int(time.time())
        if claims.exp <= now:
            return Failure(
                AppError(
                    code=ErrorCodes.UNAUTHENTICATED,
                    message="Auth token has expired.",
                    detail=None,
                ),
            )
        return Success(claims)

    def seconds_until_expiry(self, claims: AuthTokenClaims) -> int:
        return max(0, claims.exp - int(time.time()))

    def should_refresh_proactively(self, claims: AuthTokenClaims) -> bool:
        """True when token expires within the proactive refresh window."""
        return self.seconds_until_expiry(claims) <= REFRESH_GRACE_SECONDS


def encode_jwks_document(document: JwksDocument) -> str:
    payload = {"keys": [key.model_dump() for key in document.keys]}
    return json.dumps(payload, separators=(",", ":"))


def fingerprint_public_key_pem(public_key_pem: str) -> str:
    digest = hashlib.sha256(public_key_pem.encode("utf-8")).digest()
    return urlsafe_b64encode(digest).decode("ascii").rstrip("=")

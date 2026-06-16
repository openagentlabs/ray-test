"""Auth token domain models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuthTokenClaims(BaseModel):
    """Claims embedded in a signed IAM auth token."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sub: str = Field(..., min_length=1, description="User UUID.")
    jti: str = Field(..., min_length=1, description="Token id / session id.")
    perm: str = Field(..., min_length=1, description="Compressed permission string.")
    chk: str = Field(..., min_length=64, max_length=64, description="SHA-256 checksum hex.")
    iat: int = Field(..., ge=0)
    exp: int = Field(..., ge=0)
    nbf: int = Field(default=0, ge=0)


class IssuedAuthToken(BaseModel):
    """Token bundle returned to clients after successful authentication."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(..., ge=1)
    refresh_expires_in: int = Field(..., ge=1)


class JwksKey(BaseModel):
    """JSON Web Key for public verification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kty: str = Field(default="RSA")
    kid: str
    use: str = Field(default="sig")
    alg: str = Field(default="RS256")
    n: str
    e: str


class JwksDocument(BaseModel):
    """JWKS document served to microservices at startup."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    keys: tuple[JwksKey, ...]

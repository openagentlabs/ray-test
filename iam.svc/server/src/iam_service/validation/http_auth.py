"""Pydantic ingress models for HTTP auth endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequestBody(BaseModel):
    """POST ``/auth/login`` JSON body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    email: EmailStr
    password: str = Field(..., min_length=1)


class RefreshRequestBody(BaseModel):
    """POST ``/auth/refresh`` JSON body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    refresh_token: str = Field(default="")


class ValidateTokenResponseBody(BaseModel):
    """GET ``/auth/validate`` success payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool = Field(default=True)
    sub: str
    jti: str
    perm: str
    exp: int


class LogoutResponseBody(BaseModel):
    """POST ``/auth/logout`` success payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool = Field(default=True)


class HttpErrorBody(BaseModel):
    """Structured HTTP error envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str


class HttpErrorResponse(BaseModel):
    """Top-level error JSON shape."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    error: HttpErrorBody

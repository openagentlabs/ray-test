"""Identity provider shared types."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AuthFlowKind(StrEnum):
    """Supported authentication flows."""

    PASSWORD = "password"
    OAUTH2 = "oauth2"
    SAML = "saml"


class IdpMetadata(BaseModel):
    """Driver capabilities and display metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    supported_flows: tuple[AuthFlowKind, ...]


class IdpCredentialRequest(BaseModel):
    """Username/password authentication request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    username: EmailStr
    password: str = Field(..., min_length=1)


class IdpAuthorizeRequest(BaseModel):
    """OAuth2 / SAML authorization redirect request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    redirect_uri: str = Field(..., min_length=1)
    state: str = Field(..., min_length=8)
    nonce: str = Field(default="")


class IdpCallbackRequest(BaseModel):
    """OAuth2 / SAML callback payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(default="")
    state: str = Field(..., min_length=8)
    saml_response: str = Field(default="")


class IdpAuthResult(BaseModel):
    """Normalized identity assertion from any IdP driver."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str = Field(..., min_length=1, description="Stable IdP subject (email or sub).")
    email: EmailStr
    given_name: str = Field(default="")
    family_name: str = Field(default="")
    idp_provider_id: str = Field(..., min_length=1)
    idp_subject: str = Field(..., min_length=1)
    flow: AuthFlowKind

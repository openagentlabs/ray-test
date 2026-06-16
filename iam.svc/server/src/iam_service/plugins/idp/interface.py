"""Identity provider driver interface."""

from __future__ import annotations

from typing import Protocol

from iam_service.core.errors import AppError
from iam_service.core.results import Result
from iam_service.plugins.idp.types import (
    IdpAuthorizeRequest,
    IdpAuthResult,
    IdpCallbackRequest,
    IdpCredentialRequest,
    IdpMetadata,
)


class IdentityProviderDriver(Protocol):
    """Pluggable third-party identity provider adapter."""

    def metadata(self) -> IdpMetadata:
        """Return provider capabilities."""

    async def authenticate_credentials(
        self,
        request: IdpCredentialRequest,
    ) -> Result[IdpAuthResult, AppError]:
        """Validate username/password (local or federated password grant)."""

    async def build_authorization_url(
        self,
        request: IdpAuthorizeRequest,
    ) -> Result[str, AppError]:
        """Build redirect URL for OAuth2 or SAML SP-initiated login."""

    async def handle_callback(
        self,
        request: IdpCallbackRequest,
    ) -> Result[IdpAuthResult, AppError]:
        """Complete OAuth2 or SAML callback and return normalized identity."""

"""Hardcoded test IdP driver for local development."""

from __future__ import annotations

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.plugins.idp.types import (
    AuthFlowKind,
    IdpAuthorizeRequest,
    IdpAuthResult,
    IdpCallbackRequest,
    IdpCredentialRequest,
    IdpMetadata,
)


class HardcodedIdpDriver:
    """Test driver with fixed credentials — not for production."""

    __slots__ = ("_provider_id", "_display_name", "_users")

    def __init__(
        self,
        *,
        provider_id: str,
        display_name: str,
        users: dict[str, str],
    ) -> None:
        self._provider_id = provider_id
        self._display_name = display_name
        self._users = {email.lower(): password for email, password in users.items()}

    def metadata(self) -> IdpMetadata:
        return IdpMetadata(
            provider_id=self._provider_id,
            display_name=self._display_name,
            supported_flows=(AuthFlowKind.PASSWORD,),
        )

    async def authenticate_credentials(
        self,
        request: IdpCredentialRequest,
    ) -> Result[IdpAuthResult, AppError]:
        email = str(request.username).lower()
        expected = self._users.get(email)
        if expected is None or request.password != expected:
            return Failure(
                AppError(
                    code=ErrorCodes.UNAUTHENTICATED,
                    message="Invalid email or password.",
                    detail=None,
                ),
            )
        return Success(
            IdpAuthResult(
                subject=email,
                email=email,
                given_name="Keith",
                family_name="Tobin",
                idp_provider_id=self._provider_id,
                idp_subject=email,
                flow=AuthFlowKind.PASSWORD,
            ),
        )

    async def build_authorization_url(
        self,
        request: IdpAuthorizeRequest,
    ) -> Result[str, AppError]:
        _ = request
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="OAuth redirect is not supported by the hardcoded test IdP.",
                detail=None,
            ),
        )

    async def handle_callback(
        self,
        request: IdpCallbackRequest,
    ) -> Result[IdpAuthResult, AppError]:
        _ = request
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="OAuth/SAML callback is not supported by the hardcoded test IdP.",
                detail=None,
            ),
        )

"""FastAPI routes for browser-facing IAM auth."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse, Response

from iam_service.auth.token_models import IssuedAuthToken
from iam_service.auth.token_service import encode_jwks_document
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure
from iam_service.http_transport.errors import http_exception_for_app_error
from iam_service.services.auth_application import AuthApplication
from iam_service.validation.http_auth import (
    HttpErrorBody,
    HttpErrorResponse,
    LoginRequestBody,
    LogoutResponseBody,
    RefreshRequestBody,
    ValidateTokenResponseBody,
)


def create_auth_router(auth_app: AuthApplication) -> APIRouter:
    """Build auth routes bound to a single ``AuthApplication`` instance."""
    router = APIRouter(tags=["auth"])

    @router.post("/auth/login", response_model=IssuedAuthToken)
    async def login(body: LoginRequestBody) -> IssuedAuthToken:
        result = await auth_app.login_with_password(
            email=str(body.email),
            password=body.password,
        )
        if isinstance(result, Failure):
            raise http_exception_for_app_error(result.failure())
        return result.unwrap()

    @router.post("/auth/refresh", response_model=IssuedAuthToken)
    async def refresh(
        body: RefreshRequestBody,
        x_refresh_token: Annotated[str | None, Header()] = None,
    ) -> IssuedAuthToken:
        refresh_token = body.refresh_token.strip() or (x_refresh_token or "").strip()
        if not refresh_token:
            raise http_exception_for_app_error(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="refresh_token is required.",
                    detail=None,
                ),
            )
        result = await auth_app.refresh_tokens(refresh_token)
        if isinstance(result, Failure):
            raise http_exception_for_app_error(result.failure())
        return result.unwrap()

    @router.post("/auth/logout", response_model=LogoutResponseBody)
    async def logout(
        authorization: Annotated[str | None, Header()] = None,
        x_refresh_token: Annotated[str | None, Header()] = None,
    ) -> LogoutResponseBody:
        access_token: str | None = None
        if authorization:
            access_token = authorization.removeprefix("Bearer ").strip() or None
        refresh_token = (x_refresh_token or "").strip() or None
        result = await auth_app.logout(
            access_token=access_token,
            refresh_token=refresh_token,
        )
        if isinstance(result, Failure):
            raise http_exception_for_app_error(result.failure())
        return LogoutResponseBody()

    @router.get("/auth/validate", response_model=ValidateTokenResponseBody)
    async def validate(
        authorization: Annotated[str | None, Header()] = None,
    ) -> ValidateTokenResponseBody:
        token = ""
        if authorization:
            token = authorization.removeprefix("Bearer ").strip()
        if not token:
            raise http_exception_for_app_error(
                AppError(
                    code=ErrorCodes.UNAUTHENTICATED,
                    message="Bearer token required.",
                    detail=None,
                ),
            )
        result = await auth_app.validate_access_token(token)
        if isinstance(result, Failure):
            raise http_exception_for_app_error(result.failure())
        claims = result.unwrap()
        return ValidateTokenResponseBody(
            sub=claims.sub,
            jti=claims.jti,
            perm=claims.perm,
            exp=claims.exp,
        )

    async def _jwks_handler() -> Response:
        result = await auth_app.get_jwks()
        if isinstance(result, Failure):
            raise http_exception_for_app_error(result.failure())
        body = encode_jwks_document(result.unwrap())
        return Response(content=body, media_type="application/json")

    @router.get("/auth/jwks")
    async def jwks() -> Response:
        return await _jwks_handler()

    @router.get("/.well-known/jwks.json")
    async def well_known_jwks() -> Response:
        return await _jwks_handler()

    @router.get("/auth/authorize")
    async def authorize_redirect(
        redirect_uri: Annotated[str, Query(min_length=1)],
    ) -> JSONResponse:
        _ = redirect_uri
        payload = HttpErrorResponse(
            error=HttpErrorBody(
                code=ErrorCodes.VALIDATION,
                message="OAuth/SAML redirect is not configured for the active IdP driver.",
            ),
        )
        return JSONResponse(status_code=501, content=payload.model_dump())

    return router

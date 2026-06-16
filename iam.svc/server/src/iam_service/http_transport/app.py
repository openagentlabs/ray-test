"""FastAPI application factory for IAM HTTP auth."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from iam_service.core.app_config import HttpAuthConfig
from iam_service.core.errors import ErrorCodes
from iam_service.http_transport.routes import create_auth_router
from iam_service.services.auth_application import AuthApplication
from iam_service.validation.http_auth import HttpErrorBody, HttpErrorResponse


def create_auth_fastapi_app(
    *,
    config: HttpAuthConfig,
    auth_app: AuthApplication,
) -> FastAPI:
    """Build the FastAPI app with CORS and structured error responses."""
    app = FastAPI(
        title="IAM Auth",
        description="Browser-facing authentication API for iam.svc",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    origins = list(config.cors_allow_origins)
    allow_all = "*" in origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else origins,
        allow_credentials=not allow_all,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Refresh-Token"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        payload = HttpErrorResponse(
            error=HttpErrorBody(
                code=ErrorCodes.VALIDATION,
                message=str(exc.detail),
            ),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        payload = HttpErrorResponse(
            error=HttpErrorBody(
                code=ErrorCodes.VALIDATION,
                message="Request validation failed.",
            ),
        )
        _ = exc
        return JSONResponse(status_code=422, content=payload.model_dump())

    app.include_router(create_auth_router(auth_app))
    return app

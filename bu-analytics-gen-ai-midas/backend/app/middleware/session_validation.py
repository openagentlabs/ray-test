"""
Session validation middleware: orchestrates token extraction, path policy, and SessionManager (SRP).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.http_auth import extract_bearer_token
from app.core.logging_config import get_logger, set_user_context
from app.core.session.contracts import ISessionAuthenticator
from app.core.session.path_policy import IPublicPathPolicy, default_session_skip_path_policy
from app.core.session.session_http_responses import build_session_expired_json_response

logger = get_logger(__name__)


class SessionValidationMiddleware(BaseHTTPMiddleware):
    """
    When a Bearer (or query `token`) is present, delegates validation to ISessionAuthenticator.
    Path skipping is delegated to IPublicPathPolicy (OCP: swap policy without changing dispatch logic).
    """

    def __init__(
        self,
        app,
        path_policy: IPublicPathPolicy | None = None,
    ) -> None:
        super().__init__(app)
        self._path_policy = path_policy or default_session_skip_path_policy

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        if path.startswith("/api/v1/rfe/stream/") or path.startswith("/api/v1/auto-training/stream/"):
            return await call_next(request)

        if self._path_policy.allows_anonymous_bearer_skip(path):
            return await call_next(request)

        token = extract_bearer_token(request)
        if not token:
            return await call_next(request)

        sm: ISessionAuthenticator = request.app.state.session_manager
        # Use verbose method when available (SessionManager implements it).
        # Falls back to the boolean contract for any custom ISessionAuthenticator
        # that has not yet added the verbose variant.
        if hasattr(sm, "authenticate_access_token_verbose"):
            user, rejection_reason = await sm.authenticate_access_token_verbose(token)  # type: ignore[union-attr]
        else:
            user = await sm.authenticate_access_token(token)
            rejection_reason = "invalid_or_expired_token" if user is None else "ok"

        if user is None:
            req_id = request.headers.get("x-request-id", "")
            logger.info(
                "session_auth_rejected",
                extra={
                    "event": "auth_session_rejected",
                    "log_category": "security",
                    "outcome": "failure",
                    # Precise reason: jwt_invalid | user_not_found | sid_invalid
                    "auth_failure_reason": rejection_reason,
                    "path": path,
                    "method": request.method,
                    "req_id": req_id,
                },
            )
            return build_session_expired_json_response()

        request.state.session_user = user
        set_user_context(user_id=user.id)
        return await call_next(request)

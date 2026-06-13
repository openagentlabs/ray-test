"""
HTTP-layer payloads for session authentication failures (DRY: one definition for API + middleware).
"""

from __future__ import annotations

from starlette.responses import JSONResponse


def build_session_expired_detail() -> dict[str, str]:
    """FastAPI `detail` body and JSON `detail` key share this shape."""
    return {
        "message": "Invalid or expired session",
        "code": "session_invalid",
        "error_code": "SESSION_EXPIRED",
    }


def build_session_expired_json_response(status_code: int = 401) -> JSONResponse:
    """401 response for invalid Bearer when middleware rejects before route handlers."""
    return JSONResponse(
        status_code=status_code,
        content={"detail": build_session_expired_detail()},
    )

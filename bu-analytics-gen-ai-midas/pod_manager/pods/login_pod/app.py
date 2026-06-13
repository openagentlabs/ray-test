"""FastAPI login service for users without a backend lease."""

from __future__ import annotations

import os
import re

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SESSION_COOKIE = os.environ.get("SESSION_COOKIE_NAME", "pod_manager_user")


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_name: str = Field(..., min_length=1)
    user_password: str = Field(default="")


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    error_code: int
    message: str


def _is_email(value: str) -> bool:
    candidate = value.strip()
    return bool(candidate) and len(candidate) <= 320 and _EMAIL_RE.match(candidate) is not None


app = FastAPI(title="login_pod", version="0.1.0")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/{path:path}")
@app.post("/api/{path:path}")
@app.put("/api/{path:path}")
@app.patch("/api/{path:path}")
@app.delete("/api/{path:path}")
async def api_requires_backend_lease(path: str) -> JSONResponse:
    """Users without a backend lease are routed here; API calls must fail clearly."""
    _ = path
    return JSONResponse(
        status_code=403,
        content={
            "error": "no_backend_lease",
            "message": "Acquire a backend lease before calling the backend API.",
        },
    )


@app.post("/login")
async def login(body: LoginRequest) -> JSONResponse:
    if not _is_email(body.user_name):
        payload = LoginResponse(
            success=False,
            error_code=4001,
            message="user_name must be a valid email address.",
        )
        return JSONResponse(content=payload.model_dump(), status_code=400)

    _ = body.user_password
    email = body.user_name.strip().lower()
    payload = LoginResponse(success=True, error_code=0, message="success")
    response = JSONResponse(content=payload.model_dump(), status_code=200)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=email,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response

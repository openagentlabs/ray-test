"""Credentials produced after browser SSO (or static token injection)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MidasSessionCredentials(BaseModel):
    """Bearer access token plus optional ``X-Session-Id`` (matches SPA :func:`buildMidasAuthHeaders`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    access_token: str = Field(..., min_length=1)
    session_id: Optional[str] = Field(None, description="Redis session id echoed as X-Session-Id")
    cookie_header_value: Optional[str] = Field(
        None,
        description="Optional raw Cookie header for /auth/cognito/refresh (HttpOnly cookies)",
    )

    def authorization_header(self) -> str:
        """Return ``Bearer …`` value for the Authorization header."""
        return f"Bearer {self.access_token}"

    def request_headers(self) -> dict[str, str]:
        """Headers to merge onto each outbound API request."""
        h: dict[str, str] = {"Authorization": self.authorization_header()}
        if self.session_id:
            h["X-Session-Id"] = self.session_id
        if self.cookie_header_value:
            h["Cookie"] = self.cookie_header_value
        return h

    @staticmethod
    def cookie_header_from_playwright_cookies(cookies: list[dict[str, object]]) -> str:
        """Build a ``Cookie`` header string from Playwright ``context.cookies()`` entries."""
        parts: list[str] = []
        for c in cookies:
            name = c.get("name")
            value = c.get("value")
            if isinstance(name, str) and isinstance(value, str) and name.strip():
                parts.append(f"{name}={value}")
        return "; ".join(parts)

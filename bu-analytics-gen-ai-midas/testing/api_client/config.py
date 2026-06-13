"""HTTP client configuration (immutable Pydantic v2)."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MidasClientConfig(BaseModel):
    """Base URL and transport options for :class:`MidasHttpClient`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str = Field(
        ...,
        min_length=8,
        description="API origin, e.g. https://exldecision-ai-dev.exlservice.com (no trailing slash)",
    )
    timeout_seconds: float = Field(120.0, ge=1.0, le=3600.0)
    verify_tls: bool = Field(True, description="Passed through to httpx verify=…")

    @field_validator("base_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        s = v.strip().rstrip("/")
        if not re.match(r"^https?://[^/]+$", s):
            raise ValueError("base_url must be http(s) origin without path segment")
        return s

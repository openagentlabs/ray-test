"""
HTTP rate limiting: every tunable value comes from environment variables
(`RATE_LIMIT_*`), typically set in `backend/.env` (loaded by `app.core.config`).

- If `RATE_LIMIT_ENABLED` is unset, empty, or false → rate limiting is off; other
  `RATE_LIMIT_*` keys are not required.
- If `RATE_LIMIT_ENABLED` is true → all limits below must be set in the environment.
"""

from __future__ import annotations

import app.core.config  # noqa: F401 - loads `.env` into `os.environ` first

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RateLimitSettings:
    enabled: bool
    window_seconds: int
    max_default: int
    max_auth: int
    max_llm: int
    max_poll: int
    max_upload: int
    trust_proxy: bool
    redis_url: Optional[str]


def _truthy_enabled(raw: Optional[str]) -> bool:
    if raw is None:
        return False
    s = raw.strip()
    if not s:
        return False
    return s.lower() in {"1", "true", "yes", "on"}


def _require_int(key: str) -> int:
    v = os.getenv(key)
    if v is None or not str(v).strip():
        raise RuntimeError(
            f"Rate limiting is enabled but {key} is missing or empty. "
            f"Set it in backend/.env (see .env.example)."
        )
    try:
        return max(1, int(str(v).strip()))
    except ValueError as e:
        raise RuntimeError(f"{key} must be an integer, got {v!r}") from e


def _require_bool(key: str) -> bool:
    v = os.getenv(key)
    if v is None or not str(v).strip():
        raise RuntimeError(
            f"Rate limiting is enabled but {key} is missing or empty. "
            f"Set it in backend/.env (see .env.example)."
        )
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


def _redis_url() -> Optional[str]:
    from app.core.config import settings as app_settings

    if app_settings.RATE_LIMIT_REDIS_URL:
        return app_settings.RATE_LIMIT_REDIS_URL
    return app_settings.REDIS_URL


def load_rate_limit_settings() -> RateLimitSettings:
    enabled = _truthy_enabled(os.getenv("RATE_LIMIT_ENABLED"))

    if not enabled:
        return RateLimitSettings(
            enabled=False,
            window_seconds=0,
            max_default=0,
            max_auth=0,
            max_llm=0,
            max_poll=0,
            max_upload=0,
            trust_proxy=False,
            redis_url=_redis_url(),
        )

    return RateLimitSettings(
        enabled=True,
        window_seconds=_require_int("RATE_LIMIT_WINDOW_SECONDS"),
        max_default=_require_int("RATE_LIMIT_DEFAULT_MAX"),
        max_auth=_require_int("RATE_LIMIT_AUTH_MAX"),
        max_llm=_require_int("RATE_LIMIT_LLM_MAX"),
        max_poll=_require_int("RATE_LIMIT_POLL_MAX"),
        max_upload=_require_int("RATE_LIMIT_UPLOAD_MAX"),
        trust_proxy=_require_bool("RATE_LIMIT_TRUST_PROXY"),
        redis_url=_redis_url(),
    )

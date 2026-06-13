"""
HTTP rate limiting middleware (fixed window). Registered last so it runs first on the stack.
"""

from __future__ import annotations

import hashlib
import time
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.rate_limit_config import RateLimitSettings, load_rate_limit_settings
from app.core.rate_limit_store import RateLimitStore, build_rate_limit_store
from app.services.auth_service import verify_token
from app.core.logging_config import get_logger, hash_for_log

logger = get_logger(__name__)


def _exempt_path(path: str) -> bool:
    if path in ("/", "/health", "/docs", "/redoc", "/openapi.json"):
        return True
    if path.startswith("/favicon"):
        return True
    if path.startswith("/api/v1/rfe/stream/") or path.startswith("/api/v1/auto-training/stream/"):
        return True
    return False


def _classify_bucket(path: str) -> str:
    """Return bucket name: poll, auth, upload, llm, or default."""
    p = path.lower()

    if "/status/" in p or p.endswith("/keepalive") or "knowledge-graph-progress" in p or "meea-status" in p:
        return "poll"

    if p.startswith("/api/v1/auth/"):
        seg = p[len("/api/v1/auth/") :].split("/")[0]
        if seg in ("login", "register", "refresh", "verify-token"):
            return "auth"

    upload_markers = (
        "/upload",
        "/analyze-dataset",
        "combine-presplit",
        "finalize-presplit",
        "partition-preview",
        "user-knowledge",
        "validate-unique-ids-by-id",
        "exclusion-preview",
        "variable-review",
    )
    if any(m in p for m in upload_markers):
        return "upload"

    llm_markers = (
        "/chat",
        "execute-code",
        "knowledge-graph",
        "/documentation/",
        "/insights/",
        "train-global",
        "train-multiple",
        "segment-training",
        "auto-training",
        "model-evaluation",
        "feature-transformation",
        "dataset-type-classification",
        "run-segmentation",
        "segment-profiling",
        "auto-train",
        "detect-",
        "calculate-vif",
        "/correlation",
        "bivariate",
        "dataset/scope",
        "llm-config",
        "column-insights",
        "classify-variables",
        "vector-store/reinitialize",
        "dqs-recommendations",
        "segment-auto-training",
        "codebook",
        "segmentation-model-evaluation",
    )
    if any(m in p for m in llm_markers):
        return "llm"

    return "default"


def _bucket_limit(settings: RateLimitSettings, bucket: str) -> int:
    return {
        "poll": settings.max_poll,
        "auth": settings.max_auth,
        "upload": settings.max_upload,
        "llm": settings.max_llm,
        "default": settings.max_default,
    }.get(bucket, settings.max_default)


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    q = request.query_params.get("token")
    return q.strip() if q else ""


def _client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _identity_key(request: Request, settings: RateLimitSettings) -> str:
    token = _extract_bearer(request)
    if token:
        try:
            data = verify_token(token)
            if data is not None and data.username:
                return f"u:{data.username}"
        except Exception:
            pass
        # opaque token subject for invalid / unverified tokens
        h = hashlib.sha256(token.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return f"t:{h}"
    ip = _client_ip(request, settings.trust_proxy)
    return f"ip:{ip}"


def _window_key(prefix: str, identity: str, bucket: str, window_seconds: int) -> str:
    slot = int(time.time()) // max(1, window_seconds)
    return f"{prefix}:{bucket}:{identity}:{slot}"


def _identity_kind(identity: str) -> str:
    if identity.startswith("u:"):
        return "user"
    if identity.startswith("t:"):
        return "token_hash"
    if identity.startswith("ip:"):
        return "ip"
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        settings: Optional[RateLimitSettings] = None,
        store: Optional[RateLimitStore] = None,
        key_prefix: str = "midas_rl_v1",
    ):
        super().__init__(app)
        self.settings = settings or load_rate_limit_settings()
        self._store = store
        self._key_prefix = key_prefix

    @property
    def store(self) -> RateLimitStore:
        if self._store is None:
            self._store = build_rate_limit_store(self.settings.redis_url)
        return self._store

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        if not self.settings.enabled:
            return await call_next(request)

        path = request.url.path
        if _exempt_path(path):
            return await call_next(request)

        bucket = _classify_bucket(path)
        limit = _bucket_limit(self.settings, bucket)
        ident = _identity_key(request, self.settings)
        key = _window_key(self._key_prefix, ident, bucket, self.settings.window_seconds)

        try:
            count, ttl = await self.store.rate_limit_tick(key, self.settings.window_seconds)
        except Exception as exc:
            logger.warning("Rate limit store error (fail open): %s", exc)
            return await call_next(request)

        remaining = max(0, limit - count)
        reset_ts = int(time.time()) + ttl

        if count > limit:
            body = {
                "success": False,
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Try again later.",
            }
            headers = {
                "Retry-After": str(ttl),
                "RateLimit-Limit": str(limit),
                "RateLimit-Remaining": "0",
                "RateLimit-Reset": str(reset_ts),
            }
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "event": "rate_limit_exceeded",
                    "log_category": "security",
                    "outcome": "failure",
                    "rate_limit_bucket": bucket,
                    "rate_limit_identity_kind": _identity_kind(ident),
                    "rate_limit_identity_hash": hash_for_log(ident),
                    "path": path,
                    "method": request.method,
                    "rate_limit_max": limit,
                    "retry_after_seconds": ttl,
                },
            )
            return JSONResponse(status_code=429, content=body, headers=headers)

        response = await call_next(request)
        # Standard headers on success
        response.headers["RateLimit-Limit"] = str(limit)
        response.headers["RateLimit-Remaining"] = str(remaining)
        response.headers["RateLimit-Reset"] = str(reset_ts)
        return response

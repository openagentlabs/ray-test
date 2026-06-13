"""
Factory: resolve Redis URL chain, then construct ISessionStore (Redis or in-memory).
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.core.session.contracts import ISessionStore
from app.core.session.redis_url_resolution import build_default_redis_url_chain
from app.core.session.session_backends import InMemorySessionStore, RedisSessionStore
from app.core.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


def build_session_store() -> ISessionStore:
    """
    Build the session store. Redis-first with an in-memory fallback for development.

    Production safety: when ``settings.SESSION_REQUIRE_REDIS`` is True or
    ``settings.APP_ENV == "production"``, the factory refuses to fall back to in-memory
    (which would silently break multi-instance deployments) and raises RuntimeError
    so the process fails fast at startup and the platform (k8s/ECS) surfaces it.
    """
    chain = build_default_redis_url_chain()
    url = chain.resolve()
    require_redis = bool(getattr(settings, "SESSION_REQUIRE_REDIS", False)) or (
        str(getattr(settings, "APP_ENV", "development")).lower() == "production"
    )

    if url:
        try:
            logger.info("Session store: using Redis backend")
            return RedisSessionStore(url)
        except Exception as exc:
            if require_redis:
                logger.error("Session store: Redis required but unavailable (%s)", exc)
                raise RuntimeError(
                    "Redis required but unavailable; refusing to fall back to in-memory session store"
                ) from exc
            logger.warning(
                "Session store: Redis unavailable (%s); falling back to in-memory (development only).",
                exc,
            )
    else:
        if require_redis:
            logger.error(
                "Session store: Redis required but no URL resolved (APP_ENV=production or SESSION_REQUIRE_REDIS=true)"
            )
            raise RuntimeError(
                "Redis required but no URL resolved; set SESSION_REDIS_URL / REDIS_URL / SESSION_ELASTICACHE_SECRET_ARN"
            )
        logger.info("Session store: using in-memory backend (no Redis URL resolved; development only)")
    return InMemorySessionStore()


def build_session_manager() -> SessionManager:
    store = build_session_store()
    # Use settings.SESSION_TIMEOUT exclusively (default 3600 s / 60 min).
    # The old inline fallback of 5400 diverged from Settings and could cause the
    # server session to expire before the JWT (if someone set SESSION_TIMEOUT < 5400
    # but left this code path at 5400). Now both agree.
    ttl = int(settings.SESSION_TIMEOUT)

    # Safety: session TTL must be >= JWT TTL so a valid JWT always has a matching
    # server session for its full lifetime.
    from app.services.auth_service import ACCESS_TOKEN_EXPIRE_MINUTES
    min_ttl = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    if ttl < min_ttl:
        logger.warning(
            "SESSION_TIMEOUT (%ds) is shorter than the JWT TTL (%ds). "
            "Server sessions will expire before JWTs, causing spurious 401s. "
            "Clamping to %ds.",
            ttl,
            min_ttl,
            min_ttl,
            extra={"event": "session_ttl_clamped", "log_category": "security"},
        )
        ttl = min_ttl

    return SessionManager(store=store, ttl_seconds=ttl)

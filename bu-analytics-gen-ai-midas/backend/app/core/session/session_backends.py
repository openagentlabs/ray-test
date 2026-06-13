"""
Concrete session stores: in-process and Redis.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Optional, Tuple

from app.core.logging_config import get_logger
from app.core.session.contracts import ISessionStore

logger = get_logger(__name__)


class InMemorySessionStore(ISessionStore):
    """Process-local session map with TTL (suitable for single-instance dev)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._data: Dict[str, Tuple[str, float]] = {}  # sid -> (username, expiry_epoch)

    async def save(self, session_id: str, username: str, ttl_seconds: int) -> None:
        exp = time.time() + max(1, ttl_seconds)
        async with self._lock:
            self._data[session_id] = (username, exp)

    async def is_valid(self, session_id: str, username: str) -> bool:
        async with self._lock:
            self._purge_stale_unlocked()
            row = self._data.get(session_id)
            if not row:
                return False
            stored_user, exp = row
            if time.time() > exp:
                del self._data[session_id]
                return False
            return stored_user == username

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._data.pop(session_id, None)

    async def extend(self, session_id: str, ttl_seconds: int) -> None:
        async with self._lock:
            row = self._data.get(session_id)
            if row:
                username, exp = row
                # Guard: only extend keys that are still live. An expired key
                # left in _data before the next _purge_stale_unlocked() call
                # must not be resurrected by an out-of-order extend() invocation.
                if time.time() <= exp:
                    self._data[session_id] = (username, time.time() + max(1, ttl_seconds))

    def _purge_stale_unlocked(self) -> None:
        now = time.time()
        dead = [k for k, (_, exp) in self._data.items() if exp <= now]
        for k in dead:
            del self._data[k]


class RedisSessionStore(ISessionStore):
    """Redis-backed sessions (ElastiCache-compatible when URL uses TLS)."""

    def __init__(self, url: str, key_prefix: str = "midas:sess:") -> None:
        import redis.asyncio as redis  # type: ignore

        self._prefix = key_prefix
        # ElastiCache uses TLS (rediss:// scheme).
        # redis-py ≥ 4.2 accepts ssl_cert_reqs via from_url kwargs; we disable
        # cert verification because ElastiCache in the private VPC uses an
        # internal CA that we do not need to pin. Traffic never leaves the VPC.
        kwargs: dict = {"decode_responses": True}
        if url.startswith("rediss://"):
            kwargs["ssl_cert_reqs"] = "none"
        self._redis = redis.from_url(url, **kwargs)

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    async def save(self, session_id: str, username: str, ttl_seconds: int) -> None:
        ttl = max(1, int(ttl_seconds))
        try:
            await self._redis.set(self._key(session_id), username, ex=ttl)
        except Exception as exc:
            logger.error(
                "Redis session save failed — sessions will not persist: %s",
                exc,
                exc_info=True,
            )
            raise

    async def is_valid(self, session_id: str, username: str) -> bool:
        try:
            stored = await self._redis.get(self._key(session_id))
        except Exception as exc:
            logger.warning("Redis session read failed: %s", exc)
            return False
        return stored is not None and stored == username

    async def delete(self, session_id: str) -> None:
        try:
            await self._redis.delete(self._key(session_id))
        except Exception as exc:
            logger.warning("Redis session delete failed: %s", exc)

    async def extend(self, session_id: str, ttl_seconds: int) -> None:
        try:
            await self._redis.expire(self._key(session_id), max(1, int(ttl_seconds)))
        except Exception as exc:
            logger.warning("Redis session extend failed: %s", exc)

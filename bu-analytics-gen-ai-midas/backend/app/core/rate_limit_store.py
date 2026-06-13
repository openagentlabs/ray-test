"""
Fixed-window rate limit counters shared by Redis (if REDIS_URL / RATE_LIMIT_REDIS_URL)
or an in-process fallback. All operations fail open on errors (caller treats as allow).

Environment (see also rate_limit_config):
  RATE_LIMIT_REDIS_URL - optional; defaults to REDIS_URL from app.core.config when set.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class RateLimitStore(ABC):
    """Increment a fixed-window counter; returns (count_after_increment, ttl_seconds_remaining)."""

    @abstractmethod
    async def rate_limit_tick(self, key: str, window_seconds: int) -> Tuple[int, int]:
        ...


class InMemoryRateLimitStore(RateLimitStore):
    """Thread-safe fixed-window counters keyed by full key (include window slot in key)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._counts: dict[str, int] = {}
        self._prune_lock = threading.Lock()
        self._last_prune = 0.0

    def _maybe_prune(self) -> None:
        now = time.time()
        if now - self._last_prune < 60:
            return
        with self._prune_lock:
            if now - self._last_prune < 60:
                return
            self._last_prune = now
            # Drop very old keys (best-effort; keys embed window slot so old slots are stale)
            if len(self._counts) > 100_000:
                self._counts.clear()

    async def rate_limit_tick(self, key: str, window_seconds: int) -> Tuple[int, int]:
        async with self._lock:
            self._maybe_prune()
            n = self._counts.get(key, 0) + 1
            self._counts[key] = n
            slot = int(time.time()) // max(1, window_seconds)
            slot_start = slot * window_seconds
            reset_at = slot_start + window_seconds
            ttl = max(0, int(reset_at - time.time()) or window_seconds)
            return n, ttl


_LUA_INCR_EXPIRE = """
local c = redis.call('INCR', KEYS[1])
if c == 1 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
local ttl = redis.call('TTL', KEYS[1])
return {c, ttl}
"""


class RedisRateLimitStore(RateLimitStore):
    def __init__(self, url: str) -> None:
        import redis.asyncio as redis  # type: ignore

        self._redis = redis.from_url(url, decode_responses=True)

    async def rate_limit_tick(self, key: str, window_seconds: int) -> Tuple[int, int]:
        w = max(1, window_seconds)
        result = await self._redis.eval(_LUA_INCR_EXPIRE, 1, key, str(w))
        count = int(result[0])
        ttl = int(result[1])
        if ttl < 0:
            ttl = w
        return count, ttl


def build_rate_limit_store(redis_url: Optional[str]) -> RateLimitStore:
    if redis_url:
        try:
            return RedisRateLimitStore(redis_url)
        except Exception as exc:
            logger.warning("Rate limit: Redis unavailable (%s); using in-memory store.", exc)
    return InMemoryRateLimitStore()

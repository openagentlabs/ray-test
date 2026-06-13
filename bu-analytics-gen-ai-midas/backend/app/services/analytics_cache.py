"""
Process-local LRU cache for read-only analytics responses (P2.3).

Keyed by (kind, dataset_id, scope, version) so cache entries become
unreachable the moment the underlying DataFrame is mutated -
DataFrameStateManager.update_dataframe bumps the per-dataset version
counter, making the prior keys unrecoverable on lookup.

Why this matters:
  Multiple sidebar/EDA effects fire concurrently for the same
  (dataset_id, scope) tuple after a Step 1 submit. Without caching, each
  one re-runs the full O(N*C) calculate_column_info / DQS scan even
  though the data has not changed. With this cache the second through
  Nth calls become O(1) lookups.

P2.3 part 2: Optional Redis-backed L2 cache. When `REDIS_URL` is set in
the environment, cache misses fall through to Redis (cross-worker, even
cross-replica). Successful Redis lookups warm the local LRU. Writes go
to both LRU and Redis. Network errors degrade *gracefully* to LRU-only
behavior - Redis is never on the critical path.

Notes:
  - In-PROCESS cache is always present. Redis is opt-in.
  - Cache entries are pickleable Pydantic responses. We never cache the
    DataFrame itself.
  - LRU eviction caps memory growth.
"""

from __future__ import annotations

import os
import pickle
import threading
from collections import OrderedDict
from typing import Any, Optional, Tuple

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class _RedisAdapter:
    """Thin wrapper around redis-py that no-ops cleanly when Redis is down.

    Lazy: only imports `redis` if `REDIS_URL` is set; never logs above WARNING
    so a degraded Redis can't drown the application logs.
    """

    def __init__(self, url: str, namespace: str = "midas:ac:") -> None:
        self.url = url
        self.namespace = namespace
        self._client = None
        self._lock = threading.Lock()
        self._failures = 0
        self._max_failures_before_quiet = 5

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is not None:
                return self._client
            try:
                import redis
                client = redis.Redis.from_url(
                    self.url,
                    socket_timeout=1.0,
                    socket_connect_timeout=1.0,
                    health_check_interval=30,
                    decode_responses=False,
                )
                client.ping()
                self._client = client
                logger.info(
                    "AnalyticsResultCache: Redis L2 connected url=%s namespace=%s",
                    self.url, self.namespace,
                )
            except Exception as exc:
                self._record_failure(exc)
                self._client = None
        return self._client

    def _record_failure(self, exc: Exception) -> None:
        self._failures += 1
        if self._failures <= self._max_failures_before_quiet:
            logger.warning("Redis L2 cache error: %s (failure #%d)", exc, self._failures)
        elif self._failures == self._max_failures_before_quiet + 1:
            logger.warning("Redis L2 cache failing repeatedly; suppressing further log lines")

    def _make_key(self, kind: str, dataset_id: str, scope: str, version: int) -> str:
        return f"{self.namespace}{kind}:{dataset_id}:{scope}:v{version}"

    def get(self, kind: str, dataset_id: str, scope: str, version: int) -> Optional[Any]:
        client = self._ensure_client()
        if client is None:
            return None
        try:
            raw = client.get(self._make_key(kind, dataset_id, scope, version))
            if raw is None:
                return None
            return pickle.loads(raw)
        except Exception as exc:
            self._record_failure(exc)
            self._client = None
            return None

    def set(
        self, kind: str, dataset_id: str, scope: str, version: int, value: Any, ttl_s: int
    ) -> None:
        client = self._ensure_client()
        if client is None:
            return
        try:
            blob = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
            client.set(self._make_key(kind, dataset_id, scope, version), blob, ex=ttl_s)
        except Exception as exc:
            self._record_failure(exc)
            self._client = None

    def invalidate_dataset(self, dataset_id: str) -> int:
        client = self._ensure_client()
        if client is None:
            return 0
        removed = 0
        try:
            pattern = f"{self.namespace}*:{dataset_id}:*"
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor=cursor, match=pattern, count=200)
                if keys:
                    removed += client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            self._record_failure(exc)
            self._client = None
        return removed


class AnalyticsResultCache:
    """Bounded LRU keyed by (kind, dataset_id, scope, version)."""

    def __init__(
        self,
        max_entries: int = 128,
        redis_url: Optional[str] = None,
        redis_ttl_s: int = 3600,
    ) -> None:
        _Key = Tuple[str, str, str, int]
        self._cache: "OrderedDict[_Key, Any]" = OrderedDict()
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0
        self._redis_hits = 0
        self._redis_ttl_s = redis_ttl_s

        # Redis is opt-in. When unset, this stays None and the cache behaves
        # exactly like the original in-process LRU.
        url = redis_url if redis_url is not None else os.environ.get("REDIS_URL")
        self._redis: Optional[_RedisAdapter] = _RedisAdapter(url) if url else None

    def get(
        self, kind: str, dataset_id: str, scope: str, version: int
    ) -> Optional[Any]:
        key = (kind, dataset_id, scope, version)
        with self._lock:
            value = self._cache.get(key)
            if value is not None:
                self._cache.move_to_end(key)
                self._hits += 1
                hit = True
            else:
                self._misses += 1
                hit = False
        if hit:
            self._emit_metric(kind, True)
            return value

        # L1 miss: try Redis L2 if configured. Warm L1 on success.
        if self._redis is not None:
            redis_value = self._redis.get(kind, dataset_id, scope, version)
            if redis_value is not None:
                with self._lock:
                    self._cache[key] = redis_value
                    self._cache.move_to_end(key)
                    self._redis_hits += 1
                    while len(self._cache) > self._max_entries:
                        self._cache.popitem(last=False)
                self._emit_metric(kind, True)
                return redis_value

        self._emit_metric(kind, False)
        return None

    @staticmethod
    def _emit_metric(kind: str, hit: bool) -> None:
        try:
            from app.core.metrics import record_cache_hit
            record_cache_hit(kind, hit)
        except Exception:
            pass

    def set(
        self,
        kind: str,
        dataset_id: str,
        scope: str,
        version: int,
        value: Any,
    ) -> None:
        if value is None:
            return
        key = (kind, dataset_id, scope, version)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = value
            else:
                self._cache[key] = value
                while len(self._cache) > self._max_entries:
                    evicted_key, _ = self._cache.popitem(last=False)
                    logger.debug(
                        "AnalyticsResultCache evicted oldest entry %s", evicted_key
                    )
        # Write-through to Redis if configured. Failures are silently
        # absorbed; we don't want a flaky Redis to slow down the request.
        if self._redis is not None:
            self._redis.set(kind, dataset_id, scope, version, value, self._redis_ttl_s)

    def invalidate_dataset(self, dataset_id: str) -> int:
        """Drop every cached entry for a given dataset_id."""
        removed = 0
        with self._lock:
            stale = [k for k in self._cache if k[1] == dataset_id]
            for k in stale:
                del self._cache[k]
                removed += 1
        if self._redis is not None:
            try:
                redis_removed = self._redis.invalidate_dataset(dataset_id)
                if redis_removed:
                    logger.info(
                        "AnalyticsResultCache: Redis L2 dropped %d keys for dataset_id=%s",
                        redis_removed, dataset_id,
                    )
            except Exception:
                pass
        if removed:
            logger.info(
                "AnalyticsResultCache invalidated %d entries for dataset_id=%s",
                removed, dataset_id,
            )
        return removed

    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._cache),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "redis_hits": self._redis_hits,
                "redis_enabled": self._redis is not None,
                "hit_rate": (
                    (self._hits + self._redis_hits)
                    / max(1, (self._hits + self._misses))
                ),
            }


analytics_cache = AnalyticsResultCache()

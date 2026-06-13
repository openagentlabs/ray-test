"""
Redis-backed JobQueue.

- enqueue  -> RPUSH rfe:queue <job_id>
- dequeue  -> BLPOP rfe:queue timeout
- size     -> LLEN rfe:queue

Cluster-safety note: BLPOP is single-key so this works on Redis Cluster too. For
fairness under contention we'd eventually want a dedicated scheduler; the
distributed list queue is fine for the Step 3/4 throughput envelope.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import JobQueue

_QUEUE_KEY = "rfe:queue"


class RedisJobQueue(JobQueue):
    def __init__(self, redis_client: Any):
        self._redis = redis_client

    def enqueue(self, job_id: str) -> None:
        self._redis.rpush(_QUEUE_KEY, job_id)

    def dequeue(self, timeout: float = 5.0) -> Optional[str]:
        # BLPOP returns (key, value) or None on timeout.
        result = self._redis.blpop([_QUEUE_KEY], timeout=int(max(1, timeout)))
        if result is None:
            return None
        _key, value = result
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return value

    def size(self) -> int:
        try:
            return int(self._redis.llen(_QUEUE_KEY))
        except Exception:
            return 0

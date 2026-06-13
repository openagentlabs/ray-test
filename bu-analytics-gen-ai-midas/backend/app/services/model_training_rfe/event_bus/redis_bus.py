"""
Redis pub/sub EventBus.

Channel: `rfe:stream:{job_id}`. Any API pod that handles GET /rfe/stream/{job_id}
subscribes to that channel and relays each message as an SSE `data:` frame.
Workers publish without waiting for a consumer (fire-and-forget, consistent with
pub/sub semantics).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict

from app.core.logging_config import get_logger

from .base import EventBus

_logger = get_logger(__name__)


def _channel(job_id: str) -> str:
    return f"rfe:stream:{job_id}"


class RedisEventBus(EventBus):
    def __init__(self, redis_client: Any, redis_async_factory: Any = None) -> None:
        """
        redis_client: sync `redis.Redis` used for `publish`.
        redis_async_factory: optional async-redis client factory for `subscribe`;
            if None, we lazily import `redis.asyncio` on first subscribe.
        """
        self._sync = redis_client
        self._async_factory = redis_async_factory

    def publish(self, job_id: str, payload: Dict[str, Any]) -> None:
        try:
            self._sync.publish(_channel(job_id), json.dumps(payload, default=str))
        except Exception as e:
            _logger.warning(f"RedisEventBus publish failed for {job_id}: {e}")

    async def subscribe(self, job_id: str) -> AsyncIterator[Dict[str, Any]]:
        # Lazy import so local mode never requires redis.asyncio.
        if self._async_factory is None:
            import redis.asyncio as aioredis  # type: ignore

            url = getattr(self._sync, "connection_pool", None)
            # Reuse connection URL if the sync client exposes it; otherwise fall back
            # to env REDIS_URL via the factory.
            import os

            client = aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        else:
            client = self._async_factory()
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(_channel(job_id))
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.5)
                if msg is None:
                    # Idle tick keeps the generator alive without emitting.
                    await asyncio.sleep(0)
                    continue
                data = msg.get("data")
                if data is None:
                    continue
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                try:
                    yield json.loads(data)
                except Exception:
                    continue
        finally:
            try:
                await pubsub.unsubscribe(_channel(job_id))
                await pubsub.close()
                await client.close()
            except Exception:
                pass

    def close_channel(self, job_id: str) -> None:
        # Redis pub/sub has no server-side channel close; subscribers notice
        # the terminal status from JobStateStore and disconnect themselves.
        return

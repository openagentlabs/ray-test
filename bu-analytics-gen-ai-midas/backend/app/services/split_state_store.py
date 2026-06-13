"""Cross-pod split-config store backed by Redis (ElastiCache).

Why this exists
---------------
``DataFrameStateManager`` keeps the train/test/validation split metadata in
a per-process singleton. On a multi-replica EKS deployment each FastAPI
worker has its own copy, so a request that lands on a worker which did NOT
process the original ``/upload`` sees no split state and the
``column-info-by-scope`` / ``dqs-by-scope`` / ``rfe/start`` endpoints return
``0 rows`` or ``400 No data available for scope 'train'``.

What we store
-------------
**Only the lightweight split config** (method, seed, ratios, identifier
mapping, etc.) — a few hundred bytes per dataset. Indices are NOT stored
here: they would be hundreds of MB compressed for a 30M-row dataset, which
is unsafe to keep as a single Redis string and slow to (de)serialise.

The actual partition assignments (``split_tag``) live in a small Parquet
sidecar in S3 (``DatasetManager.save_split_tag_sidecar``). A cold worker:

1. ``HGETALL`` this Redis key (a few hundred bytes) for the config.
2. ``GET`` the split-tag sidecar from S3 (~10–50 MB Parquet for 30M rows).
3. Rebuilds indices locally via a single O(n) boolean mask.

Falls back gracefully when Redis is unreachable.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, Optional

from app.core.logging_config import get_logger

logger = get_logger(__name__)

_KEY_PREFIX = os.environ.get("MIDAS_SPLIT_STATE_KEY_PREFIX", "midas:split:")
_TTL_SECONDS = int(float(os.environ.get("MIDAS_SPLIT_STATE_TTL_SECONDS", str(24 * 3600))))
_DISABLED_ENV = os.environ.get("MIDAS_SPLIT_STATE_DISABLED", "").lower() in {"1", "true", "yes"}

_REDIS_CLIENT_CACHE: Any = None
_REDIS_CLIENT_CACHE_LOCK = threading.Lock()


def _resolve_redis_client() -> Any:
    """Return a connected redis client or ``None`` if unavailable.

    Mirrors ``app.services.job_locks._resolve_redis_client``: caches the
    resolved client (or ``False`` for "unavailable") at module level so we
    never block hot paths re-resolving.
    """
    global _REDIS_CLIENT_CACHE
    if _DISABLED_ENV:
        return None
    if _REDIS_CLIENT_CACHE is not None:
        return _REDIS_CLIENT_CACHE if _REDIS_CLIENT_CACHE is not False else None

    with _REDIS_CLIENT_CACHE_LOCK:
        if _REDIS_CLIENT_CACHE is not None:
            return _REDIS_CLIENT_CACHE if _REDIS_CLIENT_CACHE is not False else None

        try:
            import redis  # type: ignore[import-not-found]
            from app.core.session.redis_url_resolution import (  # type: ignore[import-not-found]
                build_default_redis_url_chain,
            )
        except ImportError as exc:
            logger.info(
                "split_state_store: redis client/url resolver unavailable (%s); "
                "split state will be process-local only.",
                exc,
            )
            _REDIS_CLIENT_CACHE = False
            return None

        try:
            url = build_default_redis_url_chain().resolve()
        except Exception as exc:  # pylint: disable=broad-except
            logger.info(
                "split_state_store: failed to resolve Redis URL (%s); "
                "split state will be process-local only.",
                exc,
            )
            _REDIS_CLIENT_CACHE = False
            return None

        if not url:
            _REDIS_CLIENT_CACHE = False
            return None

        try:
            client = redis.Redis.from_url(
                url,
                socket_connect_timeout=3.0,
                socket_timeout=3.0,
                health_check_interval=30,
            )
            client.ping()
        except Exception as exc:  # pylint: disable=broad-except
            logger.info(
                "split_state_store: Redis ping failed (%s); falling back to "
                "process-local split state.",
                exc,
            )
            _REDIS_CLIENT_CACHE = False
            return None

        logger.info("split_state_store: Redis backend active.")
        _REDIS_CLIENT_CACHE = client
        return client


def _key(dataset_id: str) -> str:
    safe = "".join(c for c in (dataset_id or "unknown") if c.isalnum() or c in ("-", "_")) or "unknown"
    return f"{_KEY_PREFIX}{safe}"


def put_config(
    dataset_id: str,
    config: Dict[str, Any],
    scope_sizes: Optional[Dict[str, int]] = None,
) -> bool:
    """Persist the lightweight split config (a few hundred bytes).

    ``scope_sizes`` is optional metadata so a cold worker can validate that
    the rebuilt indices match the snapshot the original worker produced
    (helps detect mid-flight re-uploads that would otherwise misalign).
    """
    if not dataset_id or not config:
        return False
    client = _resolve_redis_client()
    if client is None:
        return False
    try:
        payload = {
            "config": json.dumps(config, default=str),
            "scope_sizes": json.dumps(scope_sizes or {}),
            "written_at": str(int(time.time() * 1000)),
            "schema": "2",
        }
        key = _key(dataset_id)
        pipe = client.pipeline(transaction=False)
        pipe.hset(key, mapping=payload)
        pipe.expire(key, _TTL_SECONDS)
        pipe.execute()
        logger.info(
            "split_state_store.put_config: dataset_id=%s scope_sizes=%s",
            dataset_id,
            scope_sizes,
        )
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "split_state_store.put_config failed for %s: %s", dataset_id, exc
        )
        return False


def get_config(dataset_id: str) -> Optional[Dict[str, Any]]:
    """Fetch ``{"config": {...}, "scope_sizes": {...}}`` or ``None``."""
    if not dataset_id:
        return None
    client = _resolve_redis_client()
    if client is None:
        return None
    try:
        key = _key(dataset_id)
        raw = client.hgetall(key)
        if not raw:
            return None

        def _b(x: Any) -> str:
            return x.decode("utf-8") if isinstance(x, (bytes, bytearray)) else str(x)

        normalised = {_b(k): _b(v) for k, v in raw.items()}
        try:
            cfg = json.loads(normalised.get("config") or "{}")
        except json.JSONDecodeError:
            cfg = {}
        try:
            sizes = json.loads(normalised.get("scope_sizes") or "{}")
        except json.JSONDecodeError:
            sizes = {}
        # Refresh TTL on read so actively used datasets do not expire mid-session.
        try:
            client.expire(key, _TTL_SECONDS)
        except Exception:  # pylint: disable=broad-except
            pass
        return {"config": cfg, "scope_sizes": sizes}
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "split_state_store.get_config failed for %s: %s", dataset_id, exc
        )
        return None


def invalidate(dataset_id: str) -> bool:
    """Drop any cached split config for ``dataset_id``."""
    if not dataset_id:
        return False
    client = _resolve_redis_client()
    if client is None:
        return False
    try:
        client.delete(_key(dataset_id))
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "split_state_store.invalidate failed for %s: %s", dataset_id, exc
        )
        return False

"""
P3.3: Server-Sent Events for ingest progress.

The /upload pipeline goes through several wall-clock-heavy stages:
  - streaming bytes to disk
  - streaming pyarrow Parquet conversion
  - target_profile sidecar
  - read_csv_for_upload
  - duplicate / unique-id checks
  - DQS pre-warm (when enabled)

Without progress signals the frontend has to poll a status endpoint or
just spin a "Processing..." indicator for 30+ seconds. With SSE we stream
each stage transition to the browser as it happens, so users see
"Converting CSV to Parquet... done in 4.2s" progressing live.

We don't pull in `sse-starlette` because we need ONE event format and
StreamingResponse with the SSE wire format is ten lines.

Wire format (per the SSE RFC):

    data: {"stage": "parquet", "status": "running", "elapsed_ms": 1230}\n
    \n

The publisher is `progress_bus.publish(dataset_id, event)` from anywhere
(including the executor pool). The consumer is the GET /ingest-stream/{id}
endpoint, which holds a long-lived response and forwards events.

Lifetime:
  - Per dataset_id: an asyncio.Queue with a bounded buffer.
  - The bus auto-evicts after IDLE_TTL_S of no subscribers.
  - The frontend receives an `end` event after the final stage; the
    server then closes the stream so EventSource doesn't auto-reconnect.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.auth_routes import get_current_user_dependency
from app.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()


_QUEUES: Dict[str, "asyncio.Queue[Optional[Dict[str, Any]]]"] = {}
_LAST_ACTIVITY: Dict[str, float] = {}
_LOCK = asyncio.Lock()
IDLE_TTL_S = 1800  # subscribe windows expire after 30 min of no events


async def _gc() -> None:
    now = time.time()
    async with _LOCK:
        stale = [k for k, ts in _LAST_ACTIVITY.items() if now - ts > IDLE_TTL_S]
        for k in stale:
            _QUEUES.pop(k, None)
            _LAST_ACTIVITY.pop(k, None)


async def _get_queue(dataset_id: str) -> "asyncio.Queue[Optional[Dict[str, Any]]]":
    async with _LOCK:
        q = _QUEUES.get(dataset_id)
        if q is None:
            q = asyncio.Queue(maxsize=256)
            _QUEUES[dataset_id] = q
        _LAST_ACTIVITY[dataset_id] = time.time()
        return q


async def publish(dataset_id: str, event: Dict[str, Any]) -> None:
    """Publish a progress event for a dataset_id. Safe to call from any thread."""
    if not dataset_id:
        return
    q = await _get_queue(dataset_id)
    try:
        if not q.full():
            await q.put(event)
        _LAST_ACTIVITY[dataset_id] = time.time()
    except Exception as exc:
        logger.debug("SSE publish dropped event for %s: %s", dataset_id, exc)


def publish_threadsafe(dataset_id: str, event: Dict[str, Any]) -> None:
    """
    Synchronous shim for publishing from non-async code (executor threads).
    Schedules the publish on the running event loop without blocking the caller.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(publish(dataset_id, event), loop)
        else:
            loop.run_until_complete(publish(dataset_id, event))
    except RuntimeError:
        # No event loop in this thread (CLI, worker pool with no loop) -
        # silently drop. Subscribers will just miss this event.
        logger.debug("publish_threadsafe: no loop available for %s", dataset_id)


async def end(dataset_id: str, *, ok: bool = True, message: str = "") -> None:
    await publish(dataset_id, {
        "type": "end",
        "ok": ok,
        "message": message,
        "ts": time.time(),
    })
    q = await _get_queue(dataset_id)
    try:
        await q.put(None)
    except Exception:
        pass


@router.get("/ingest-stream/{dataset_id}")
async def ingest_stream(
    dataset_id: str,
    request: Request,
    current_user=Depends(get_current_user_dependency),
):
    """Long-lived SSE stream of ingest-stage events for a dataset_id."""
    await _gc()
    q = await _get_queue(dataset_id)

    async def generator():
        # Initial comment keeps proxies (nginx default 60s) from closing
        # the connection before the first event lands.
        yield ":hello\n\n"
        last_keepalive = time.time()
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    if time.time() - last_keepalive > 14.0:
                        yield ":keepalive\n\n"
                        last_keepalive = time.time()
                    continue
                if evt is None:
                    return
                yield f"data: {json.dumps(evt, default=str)}\n\n"
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("ingest_stream generator error for %s: %s", dataset_id, exc)
            return

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(generator(), media_type="text/event-stream", headers=headers)


@router.post("/ingest-stream/{dataset_id}/test-publish")
async def test_publish(
    dataset_id: str,
    body: dict,
    current_user=Depends(get_current_user_dependency),
):
    """Test endpoint: publish an arbitrary event. Useful for dev/QA."""
    await publish(dataset_id, body or {"type": "test", "ts": time.time()})
    return {"published": True}

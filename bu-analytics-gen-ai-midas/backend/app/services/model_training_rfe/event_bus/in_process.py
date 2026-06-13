"""
In-process event bus.

Backs every subscriber with its own asyncio.Queue. Publisher side uses
``loop.call_soon_threadsafe`` so the RFE loop (which runs in a background
thread) can hand ticks to the FastAPI event loop safely.

Notes:
- We lazily capture the API event loop on first subscribe. This matches how
  FastAPI + uvicorn run (single event loop per worker process).
- We keep bounded queues (maxsize=64) so a slow consumer can't grow memory
  without bound; overflow is dropped with a debug log.
- We also keep a short **backlog ring buffer** per job so a late subscriber
  that joins shortly after the worker started still sees the most recent
  status/iteration ticks. Without this, in local mode every event published
  before the SSE client attached was silently dropped and the UI looked
  frozen during the first 30s of iteration 0 (XGBoost warm-up).
"""

from __future__ import annotations

import asyncio
import collections
import threading
from typing import Any, AsyncIterator, Deque, Dict, List

from app.core.logging_config import get_logger

from .base import EventBus

_logger = get_logger(__name__)


class InProcessEventBus(EventBus):
    def __init__(self, queue_maxsize: int = 64, backlog_maxsize: int = 32) -> None:
        self._queue_maxsize = queue_maxsize
        self._backlog_maxsize = backlog_maxsize
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._backlogs: Dict[str, Deque[Dict[str, Any]]] = {}
        self._closed_channels: set[str] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_event_loop()
        return self._loop

    async def subscribe(self, job_id: str) -> AsyncIterator[Dict[str, Any]]:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._queue_maxsize)
        with self._lock:
            self._loop = asyncio.get_running_loop()
            self._subscribers.setdefault(job_id, []).append(q)
            backlog = list(self._backlogs.get(job_id, ()))
            channel_closed = job_id in self._closed_channels
        # Replay backlog first so the subscriber catches up on events emitted
        # before it attached.
        for evt in backlog:
            try:
                q.put_nowait(evt)
            except asyncio.QueueFull:
                break
        if channel_closed:
            try:
                q.put_nowait(None)  # sentinel - channel already closed
            except asyncio.QueueFull:
                pass
        try:
            while True:
                payload = await q.get()
                if payload is None:  # sentinel
                    break
                yield payload
        finally:
            with self._lock:
                lst = self._subscribers.get(job_id, [])
                if q in lst:
                    lst.remove(q)
                if not lst:
                    self._subscribers.pop(job_id, None)

    def publish(self, job_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subscribers.get(job_id, []))
            loop = self._loop
            backlog = self._backlogs.setdefault(
                job_id, collections.deque(maxlen=self._backlog_maxsize)
            )
            backlog.append(payload)
        if not subs or loop is None:
            return
        for q in subs:
            try:
                # Thread-safe put (fire-and-forget, drop on overflow).
                loop.call_soon_threadsafe(_safe_put_nowait, q, payload)
            except Exception as e:
                _logger.debug(f"in-process publish failed for {job_id}: {e}")

    def close_channel(self, job_id: str) -> None:
        with self._lock:
            subs = list(self._subscribers.get(job_id, []))
            loop = self._loop
            self._closed_channels.add(job_id)
            # Keep the backlog around briefly so clients who reconnect within a
            # few seconds of completion still see the final event; a long-lived
            # process would need a periodic sweep but that's out of scope for
            # the in-process local-mode bus.
        if loop is None:
            return
        for q in subs:
            try:
                loop.call_soon_threadsafe(_safe_put_nowait, q, None)  # sentinel
            except Exception:
                continue


def _safe_put_nowait(queue: asyncio.Queue, payload: Any) -> None:
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull:
        # Drop-late semantics: prefer dropping a stale iteration tick over blocking
        # the worker thread.
        try:
            _ = queue.get_nowait()
            queue.put_nowait(payload)
        except Exception:
            pass

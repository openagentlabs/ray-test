"""Non-blocking async export queue used by drivers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class AsyncExportQueue(Generic[T]):
    """Fire-and-forget queue with bounded size; drops when full to protect the hot path."""

    def __init__(self, *, max_size: int, flush_handler: Callable[[list[T]], Awaitable[None]]) -> None:
        self._queue: asyncio.Queue[T | None] = asyncio.Queue(maxsize=max_size)
        self._flush_handler = flush_handler
        self._worker: asyncio.Task[None] | None = None
        self._batch: list[T] = []
        self._batch_size = 50
        self._running = False

    def enqueue(self, item: T) -> bool:
        """Enqueue without awaiting; returns False when the queue is full."""
        if not self._running:
            return False
        try:
            self._queue.put_nowait(item)
            return True
        except asyncio.QueueFull:
            return False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        await self._queue.put(None)
        if self._worker is not None:
            await self._worker
            self._worker = None
        if self._batch:
            await self._flush_handler(self._batch)
            self._batch.clear()

    async def _run(self) -> None:
        while True:
            item = await self._queue.get()
            if item is None:
                if self._batch:
                    await self._flush_handler(self._batch)
                    self._batch.clear()
                return
            self._batch.append(item)
            if len(self._batch) >= self._batch_size:
                await self._flush_handler(self._batch)
                self._batch.clear()

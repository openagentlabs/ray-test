"""
EventBus ABC - publish/subscribe channel per job.

The SSE handler on any API pod can subscribe and forward ticks to the client.
Implementations must deliver at-least-once ordering within a single publisher
and be non-blocking on publish (drop-late rather than block the RFE loop).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict


class EventBus(ABC):
    @abstractmethod
    def publish(self, job_id: str, payload: Dict[str, Any]) -> None: ...

    @abstractmethod
    async def subscribe(self, job_id: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Async-iterate events for a given job_id. Must yield JSON-serialisable dicts.
        The caller handles the SSE framing.
        """
        ...

    @abstractmethod
    def close_channel(self, job_id: str) -> None:
        """Release resources once a job is terminal and everyone has drained."""
        ...

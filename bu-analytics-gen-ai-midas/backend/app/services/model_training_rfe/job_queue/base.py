"""
JobQueue ABC.

API pods call `enqueue(job_id)` from /rfe/start. Workers call `dequeue(timeout)`
in a loop. The queue item is intentionally tiny - workers rehydrate the full
config from StorageBackend using the `job_id`, which keeps the queue lightweight
and consistent across backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class JobQueue(ABC):
    @abstractmethod
    def enqueue(self, job_id: str) -> None: ...

    @abstractmethod
    def dequeue(self, timeout: float = 5.0) -> Optional[str]: ...

    @abstractmethod
    def size(self) -> int: ...

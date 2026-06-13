"""In-memory sub → route cache for ext_authz (DS-4)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CachedRoute:
    pod_dns: str
    assignment_epoch: int


class AssignmentRouteCache:
    """Thread-unsafe cache; used from single asyncio event loop only."""

    __slots__ = ("_entries", "_hits", "_misses")

    def __init__(self) -> None:
        self._entries: dict[str, CachedRoute] = {}
        self._hits = 0
        self._misses = 0

    def get(self, *, sub: str) -> CachedRoute | None:
        route = self._entries.get(sub)
        if route is None:
            self._misses += 1
            return None
        self._hits += 1
        return route

    def set(self, *, sub: str, pod_dns: str, epoch: int) -> None:
        self._entries[sub] = CachedRoute(pod_dns=pod_dns, assignment_epoch=epoch)

    def invalidate(self, *, sub: str) -> None:
        self._entries.pop(sub, None)

    def clear(self) -> None:
        self._entries.clear()

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

"""In-memory ``EksClusterDriver`` for unit tests."""

from __future__ import annotations

from solutions_service.core.errors import AppError
from solutions_service.core.results import Result, Success
from solutions_service.drivers.eks.protocol import DiscoveredBackendPod


class FakeEksClusterDriver:
    """Returns a fixed pod list configured at construction."""

    __slots__ = ("_pods",)

    def __init__(self, *, pods: list[DiscoveredBackendPod] | None = None) -> None:
        self._pods = list(pods or [])

    def set_pods(self, pods: list[DiscoveredBackendPod]) -> None:
        self._pods = list(pods)

    async def list_ready_backend_pods(self) -> Result[list[DiscoveredBackendPod], AppError]:
        return Success(list(self._pods))

    async def close(self) -> None:
        return None

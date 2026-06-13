"""EKS cluster driver protocol — backend pod discovery (BP-1, BP-2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from solutions_service.core.errors import AppError
from solutions_service.core.results import Result


@dataclass(frozen=True, slots=True)
class DiscoveredBackendPod:
    """A ready backend pod eligible for the pod pool."""

    pod_id: str
    pod_dns: str


class EksClusterDriver(Protocol):
    """Lists ready backend pods from the cluster (reconciler only)."""

    async def list_ready_backend_pods(self) -> Result[list[DiscoveredBackendPod], AppError]:
        """Return pods that are Running and Ready."""

    async def close(self) -> None:
        """Release cluster client resources."""

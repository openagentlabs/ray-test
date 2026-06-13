"""Production ``EksClusterDriver`` via kubernetes-asyncio."""

from __future__ import annotations

from solutions_service.core.app_config import KubernetesConfig
from solutions_service.core.errors import AppError
from solutions_service.core.results import Failure, Result, Success
from solutions_service.drivers.eks.protocol import DiscoveredBackendPod, EksClusterDriver
from solutions_service.kubernetes.discovery import KubernetesPodDiscovery


class KubernetesEksClusterDriver:
    """Delegates to ``KubernetesPodDiscovery``."""

    __slots__ = ("_inner",)

    def __init__(self, *, kubernetes_config: KubernetesConfig) -> None:
        self._inner = KubernetesPodDiscovery(kubernetes_config=kubernetes_config)

    async def list_ready_backend_pods(self) -> Result[list[DiscoveredBackendPod], AppError]:
        discovered = await self._inner.list_ready_backend_pods()
        if isinstance(discovered, Failure):
            return discovered
        pods = [
            DiscoveredBackendPod(pod_id=p.pod_id, pod_dns=p.pod_dns)
            for p in discovered.unwrap()
        ]
        return Success(pods)

    async def close(self) -> None:
        await self._inner.close()

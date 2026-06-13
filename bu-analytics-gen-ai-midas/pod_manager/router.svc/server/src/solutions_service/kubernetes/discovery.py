"""Async discovery of backend pods via the Kubernetes API (in-cluster or kubeconfig)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.exceptions import ApiException

from solutions_service.core.app_config import KubernetesConfig
from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DiscoveredBackendPod:
    """A ready backend pod eligible for the pod pool."""

    pod_id: str
    pod_dns: str


class KubernetesPodDiscovery:
    """Lists ready pods matching the configured label selector."""

    __slots__ = ("_cfg", "_api", "_loaded")

    def __init__(self, *, kubernetes_config: KubernetesConfig) -> None:
        self._cfg = kubernetes_config
        self._api: client.CoreV1Api | None = None
        self._loaded = False

    async def _ensure_client(self) -> Result[client.CoreV1Api, AppError]:
        if self._api is not None:
            return Success(self._api)
        try:
            if self._cfg.use_in_cluster_config:
                await config.load_incluster_config()
            else:
                await config.load_kube_config(config_file=self._cfg.kubeconfig_path or None)
            api_client = client.ApiClient()
            self._api = client.CoreV1Api(api_client)
            self._loaded = True
            return Success(self._api)
        except (OSError, config.ConfigException) as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.UPSTREAM,
                    message="Could not load Kubernetes client configuration.",
                    detail=str(exc),
                ),
            )

    def _pod_dns(self, pod_name: str) -> str:
        svc = self._cfg.headless_service_name
        ns = self._cfg.namespace
        port = self._cfg.backend_port
        host = f"{pod_name}.{svc}.{ns}.svc.cluster.local"
        return f"{host}:{port}"

    async def list_ready_backend_pods(self) -> Result[list[DiscoveredBackendPod], AppError]:
        """Return pods that are Running and Ready (BP-2)."""
        api_result = await self._ensure_client()
        if isinstance(api_result, Failure):
            return api_result
        api = api_result.unwrap()
        try:
            resp = await api.list_namespaced_pod(
                namespace=self._cfg.namespace,
                label_selector=self._cfg.pod_label_selector,
            )
        except ApiException as exc:
            logger.warning("kubernetes list_namespaced_pod failed status=%s", exc.status)
            return Failure(
                AppError(
                    code=ErrorCodes.UPSTREAM,
                    message="Kubernetes API list pods failed.",
                    detail=str(exc),
                ),
            )
        except OSError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.UPSTREAM,
                    message="Kubernetes API list pods failed.",
                    detail=str(exc),
                ),
            )

        out: list[DiscoveredBackendPod] = []
        for pod in resp.items:
            if pod.metadata is None or not pod.metadata.name:
                continue
            if pod.status is None or pod.status.phase != "Running":
                continue
            if not _pod_is_ready(pod):
                continue
            name = pod.metadata.name
            out.append(
                DiscoveredBackendPod(
                    pod_id=name,
                    pod_dns=self._pod_dns(name),
                ),
            )
        logger.debug(
            "kubernetes_discovery namespace=%s selector=%s ready_pods=%d",
            self._cfg.namespace,
            self._cfg.pod_label_selector,
            len(out),
        )
        return Success(out)

    async def close(self) -> None:
        """Release the Kubernetes client (best-effort)."""
        if self._api is not None and self._loaded:
            await self._api.api_client.close()
        self._api = None
        self._loaded = False


def _pod_is_ready(pod: client.V1Pod) -> bool:
    conditions = pod.status.conditions if pod.status else None
    if not conditions:
        return False
    for cond in conditions:
        if cond.type == "Ready" and cond.status == "True":
            return True
    return False

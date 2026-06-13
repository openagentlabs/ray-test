"""Pod-manager client adapter used by backend auth/session flows."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from app.core.logging_config import get_logger

try:
    from pod_manager_client import PodManagerClient
    from pod_manager_client.errors import PodManagerClientError
except Exception:  # pragma: no cover - handled by availability guard
    PodManagerClient = None  # type: ignore[assignment]
    PodManagerClientError = Exception  # type: ignore[assignment]

logger = get_logger(__name__)


class PodManagerServiceError(RuntimeError):
    """Raised when pod-manager operations fail."""


@dataclass(frozen=True)
class PodManagerLease:
    """Backend-friendly lease view."""

    pod_id: str
    pod_dns: str
    assignment_epoch: int
    already_leased: bool


class PodManagerService:
    """Lifecycle-managed wrapper over ``pod_manager_client.PodManagerClient``."""

    def __init__(
        self,
        host: str,
        port: int,
        timeout_seconds: float,
        ensure_retries: int,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout_seconds = max(0.1, timeout_seconds)
        self._ensure_retries = max(0, ensure_retries)
        self._client: Optional[PodManagerClient] = None
        self._connected = False

    async def start(self) -> None:
        """Connect the underlying async client once during app startup."""
        if PodManagerClient is None:
            raise PodManagerServiceError("pod_manager_client package is not installed")
        if self._connected:
            return
        self._client = PodManagerClient(host=self._host, port=self._port)
        await self._client.__aenter__()
        self._connected = True
        logger.info(
            "Pod-manager client connected",
            extra={
                "event": "pod_manager_client_connected",
                "host": self._host,
                "port": self._port,
            },
        )

    async def close(self) -> None:
        """Close the underlying async channel."""
        if self._client is None:
            return
        await self._client.close()
        self._client = None
        self._connected = False
        logger.info(
            "Pod-manager client closed",
            extra={"event": "pod_manager_client_closed"},
        )

    async def acquire_lease(self, sub: str) -> PodManagerLease:
        """Acquire lease for subject identifier."""
        lease = await self._run("acquire_lease", self._require_client().acquire_lease(sub))
        return PodManagerLease(
            pod_id=lease.pod_id,
            pod_dns=lease.pod_dns,
            assignment_epoch=lease.assignment_epoch,
            already_leased=lease.already_leased,
        )

    async def get_lease(self, sub: str) -> PodManagerLease:
        """Get existing lease for subject identifier."""
        lease = await self._run("get_lease", self._require_client().get_lease(sub))
        return PodManagerLease(
            pod_id=lease.pod_id,
            pod_dns=lease.pod_dns,
            assignment_epoch=lease.assignment_epoch,
            already_leased=lease.already_leased,
        )

    async def release_lease(self, sub: str) -> None:
        """Release lease for subject identifier."""
        await self._run("release_lease", self._require_client().release_lease(sub))

    async def ensure_lease(self, sub: str) -> PodManagerLease:
        """Get lease; if missing, attempt acquire with limited retries."""
        attempts = self._ensure_retries + 1
        last_error: Optional[Exception] = None
        for _ in range(attempts):
            try:
                return await self.get_lease(sub)
            except PodManagerServiceError as exc:
                last_error = exc
            try:
                return await self.acquire_lease(sub)
            except PodManagerServiceError as exc:
                last_error = exc
        raise PodManagerServiceError(f"Failed to ensure pod-manager lease for '{sub}': {last_error}")

    def _require_client(self) -> PodManagerClient:
        if self._client is None or not self._connected:
            raise PodManagerServiceError("pod-manager client is not connected")
        return self._client

    async def _run(self, operation: str, coroutine):
        try:
            return await asyncio.wait_for(coroutine, timeout=self._timeout_seconds)
        except TimeoutError as exc:
            raise PodManagerServiceError(f"{operation} timed out after {self._timeout_seconds}s") from exc
        except PodManagerClientError as exc:
            raise PodManagerServiceError(f"{operation} failed: {exc}") from exc

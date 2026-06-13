"""Unit tests for pod-manager service adapter."""

from __future__ import annotations

import unittest
from unittest import mock

from app.services.pod_manager_service import PodManagerLease, PodManagerService, PodManagerServiceError


class TestPodManagerService(unittest.IsolatedAsyncioTestCase):
    async def test_ensure_lease_falls_back_to_acquire(self) -> None:
        service = PodManagerService(host="localhost", port=8804, timeout_seconds=1.0, ensure_retries=0)
        expected = PodManagerLease(
            pod_id="pod-1",
            pod_dns="pod-1.ns.svc.cluster.local",
            assignment_epoch=1,
            already_leased=False,
        )
        service.get_lease = mock.AsyncMock(side_effect=PodManagerServiceError("not found"))  # type: ignore[assignment]
        service.acquire_lease = mock.AsyncMock(return_value=expected)  # type: ignore[assignment]

        lease = await service.ensure_lease("alice")

        self.assertEqual(lease.pod_id, "pod-1")
        service.acquire_lease.assert_awaited_once_with("alice")

    async def test_ensure_lease_raises_after_retries(self) -> None:
        service = PodManagerService(host="localhost", port=8804, timeout_seconds=1.0, ensure_retries=1)
        service.get_lease = mock.AsyncMock(side_effect=PodManagerServiceError("missing"))  # type: ignore[assignment]
        service.acquire_lease = mock.AsyncMock(side_effect=PodManagerServiceError("unavailable"))  # type: ignore[assignment]

        with self.assertRaises(PodManagerServiceError):
            await service.ensure_lease("alice")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

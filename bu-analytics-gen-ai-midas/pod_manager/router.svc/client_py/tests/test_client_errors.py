"""Client error type tests."""

from __future__ import annotations

import grpc

from pod_manager_client.errors import PodManagerClientError, error_from_rpc


def test_pod_manager_client_error_code() -> None:
    err = PodManagerClientError("unavailable", code=grpc.StatusCode.UNAVAILABLE)
    assert err.code == grpc.StatusCode.UNAVAILABLE


def test_error_from_rpc_uses_details() -> None:
    class _FakeExc(grpc.RpcError):
        def code(self) -> grpc.StatusCode:
            return grpc.StatusCode.INVALID_ARGUMENT

        def details(self) -> str:
            return "bad sub"

    mapped = error_from_rpc(_FakeExc())  # type: ignore[arg-type]
    assert "bad sub" in str(mapped)

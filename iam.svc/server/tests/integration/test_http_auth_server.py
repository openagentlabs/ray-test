"""Integration tests for FastAPI HTTP auth routes."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from iam_service.auth.token_service import AuthTokenService
from iam_service.core.app_config import HttpAuthConfig
from iam_service.http_transport.auth_server import HttpAuthServer
from iam_service.plugins.idp.hardcoded_driver import HardcodedIdpDriver
from iam_service.plugins.vault.local_driver import LocalVaultDriver
from iam_service.services.auth_application import AuthApplication


class _InMemoryUserRepo:
    async def put(self, record):  # noqa: ANN001, ANN201
        from iam_service.core.results import Success

        self._record = record
        return Success(None)


def test_http_login_validate_and_jwks(tmp_path: Path) -> None:
    import asyncio

    vault = LocalVaultDriver(vault_path=tmp_path)
    token_service = AuthTokenService(vault=vault, master_key_id="iam-master-key-1")
    asyncio.run(token_service.ensure_master_key_exists())

    idp = HardcodedIdpDriver(
        provider_id="test",
        display_name="Test",
        users={"keith.tobin@gmail.com": "123456"},
    )

    class EmptyRepo:
        async def list_for_user(self, _user_id: str):  # noqa: ANN001, ANN202
            from iam_service.core.results import Success

            return Success([])

        async def put(self, _record):  # noqa: ANN001, ANN202
            from iam_service.core.results import Success

            return Success(None)

        async def get_by_id(self, _session_id: str):  # noqa: ANN001, ANN202
            from iam_service.core.results import Success

            return Success(None)

        async def revoke(self, _session_id: str, *, now_iso: str):  # noqa: ANN001, ANN202
            from iam_service.core.results import Success

            return Success(None)

    auth_app = AuthApplication(
        idp=idp,
        token_service=token_service,
        users=_InMemoryUserRepo(),  # type: ignore[arg-type]
        user_permissions=EmptyRepo(),  # type: ignore[arg-type]
        service_registry=EmptyRepo(),  # type: ignore[arg-type]
        auth_sessions=EmptyRepo(),  # type: ignore[arg-type]
    )
    server = HttpAuthServer(
        config=HttpAuthConfig(host="127.0.0.1", port=8873),
        auth_app=auth_app,
    )
    with TestClient(server.build_app()) as client:
        login = client.post(
            "/auth/login",
            json={"email": "keith.tobin@gmail.com", "password": "123456"},
        )
        assert login.status_code == 200
        body = login.json()
        assert "access_token" in body
        assert "refresh_token" in body

        jwks = client.get("/.well-known/jwks.json")
        assert jwks.status_code == 200
        assert "keys" in jwks.json()

        validate = client.get(
            "/auth/validate",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        assert validate.status_code == 200
        assert validate.json()["valid"] is True

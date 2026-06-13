"""Tests for pod-manager integration hooks in auth routes."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from fastapi import FastAPI, Response
from starlette.requests import Request

from app.api import auth_routes
from app.models.schemas import UserInDB, UserLogin


def _build_request_with_state() -> Request:
    app = FastAPI()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/auth/test",
        "headers": [],
        "app": app,
    }
    return Request(scope)


def _build_user(username: str) -> UserInDB:
    now = datetime.now(timezone.utc)
    return UserInDB(
        id=1,
        username=username,
        full_name="Test User",
        email=f"{username}@example.com",
        hashed_password="x",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


class TestAuthPodManagerIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_get_current_user_dependency_ensures_lease(self) -> None:
        request = _build_request_with_state()
        user = _build_user("alice")
        sm = mock.AsyncMock()
        sm.authenticate_access_token = mock.AsyncMock(return_value=user)
        request.app.state.session_manager = sm
        pod_manager_service = mock.AsyncMock()
        request.app.state.pod_manager_service = pod_manager_service

        creds = SimpleNamespace(credentials="token")
        resolved = await auth_routes.get_current_user_dependency(request, creds)

        self.assertEqual(resolved.username, "alice")
        pod_manager_service.ensure_lease.assert_awaited_once_with("alice")

    async def test_login_user_acquires_lease_when_service_available(self) -> None:
        request = _build_request_with_state()
        response = Response()
        session_manager = mock.AsyncMock()
        session_manager.create_session = mock.AsyncMock(return_value="sid-1")
        session_manager.ttl_seconds = 3600
        request.app.state.session_manager = session_manager
        pod_manager_service = mock.AsyncMock()
        request.app.state.pod_manager_service = pod_manager_service
        user = _build_user("bob")

        with (
            mock.patch.object(auth_routes.app_settings, "ENABLE_LEGACY_PASSWORD_LOGIN", True),
            mock.patch("app.api.auth_routes.authenticate_user", return_value=user),
            mock.patch("app.api.auth_routes.create_access_token", return_value="access"),
            mock.patch("app.api.auth_routes.create_refresh_token", return_value="refresh"),
            mock.patch("app.api.auth_routes.get_refresh_token_expiry", return_value=datetime.now(timezone.utc)),
            mock.patch("app.api.auth_routes.user_db.create_refresh_token", return_value=True),
        ):
            result = await auth_routes.login_user(request, UserLogin(username="bob", password="pw"), response)

        self.assertEqual(result["session_id"], "sid-1")
        pod_manager_service.acquire_lease.assert_awaited_once_with("bob")

    async def test_logout_user_releases_lease_when_service_available(self) -> None:
        request = _build_request_with_state()
        session_manager = mock.AsyncMock()
        request.app.state.session_manager = session_manager
        pod_manager_service = mock.AsyncMock()
        request.app.state.pod_manager_service = pod_manager_service
        current_user = _build_user("carol")
        credentials = SimpleNamespace(credentials="jwt-token")

        with mock.patch("app.api.auth_routes.user_db.revoke_all_refresh_tokens_for_user", return_value=1):
            result = await auth_routes.logout_current_user(
                request=request,
                credentials=credentials,
                current_user=current_user,
            )

        self.assertEqual(result["message"], "Logged out")
        pod_manager_service.release_lease.assert_awaited_once_with("carol")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

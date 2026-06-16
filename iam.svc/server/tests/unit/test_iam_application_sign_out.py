"""Unit tests for ``IamServiceApplication.sign_out``."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.results import Failure, Success
from iam_service.database.models.records import SessionRecord
from iam_service.services.iam_application import IamServiceApplication

SESSION_ID = "723e4567-e89b-12d3-a456-426614174006"
USER_ID = "323e4567-e89b-12d3-a456-426614174002"
LOGIN_ID = "423e4567-e89b-12d3-a456-426614174003"
NOW = "2025-01-01T00:00:00Z"


def _session(*, is_revoked: bool = False, is_deleted: bool = False) -> SessionRecord:
    return SessionRecord(
        id=SESSION_ID,
        user_id=USER_ID,
        login_id=LOGIN_ID,
        created_at=NOW,
        updated_at=NOW,
        expires_at="2025-01-02T00:00:00Z",
        deleted_at=NOW if is_deleted else "",
        is_deleted=is_deleted,
        is_revoked=is_revoked,
    )


def _make_app(
    *,
    app_section: AppSection,
    session_get: AsyncMock,
    sessions_put: AsyncMock,
) -> IamServiceApplication:
    sessions_repo = AsyncMock()
    sessions_repo.get_by_id = session_get
    sessions_repo.put = sessions_put
    deployment_admins_repo = AsyncMock()
    deployment_admins_repo.find_active_by_email = AsyncMock(return_value=Success(None))
    return IamServiceApplication(
        app=app_section,
        users=AsyncMock(),
        user_types=AsyncMock(),
        login_types=AsyncMock(),
        skill_lists=AsyncMock(),
        skills=AsyncMock(),
        user_skills=AsyncMock(),
        logins=AsyncMock(),
        sessions=sessions_repo,
        invites=AsyncMock(),
        deployment_admins=deployment_admins_repo,
        rbac=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_sign_out_revokes_active_session(app_section: AppSection) -> None:
    session_get = AsyncMock(return_value=Success(_session()))
    sessions_put = AsyncMock(return_value=Success(None))
    app = _make_app(
        app_section=app_section,
        session_get=session_get,
        sessions_put=sessions_put,
    )

    result = await app.sign_out(iam_pb2.SignOutRequest(session_id=SESSION_ID))

    assert isinstance(result, Success)
    sessions_put.assert_awaited_once()
    revoked = sessions_put.await_args.args[0]
    assert revoked.is_revoked is True
    assert revoked.is_deleted is True


@pytest.mark.asyncio
async def test_sign_out_is_idempotent_when_session_missing(app_section: AppSection) -> None:
    session_get = AsyncMock(return_value=Success(None))
    sessions_put = AsyncMock()
    app = _make_app(
        app_section=app_section,
        session_get=session_get,
        sessions_put=sessions_put,
    )

    result = await app.sign_out(iam_pb2.SignOutRequest(session_id=SESSION_ID))

    assert isinstance(result, Success)
    sessions_put.assert_not_awaited()


@pytest.mark.asyncio
async def test_sign_out_is_idempotent_when_already_revoked(app_section: AppSection) -> None:
    session_get = AsyncMock(return_value=Success(_session(is_revoked=True, is_deleted=True)))
    sessions_put = AsyncMock()
    app = _make_app(
        app_section=app_section,
        session_get=session_get,
        sessions_put=sessions_put,
    )

    result = await app.sign_out(iam_pb2.SignOutRequest(session_id=SESSION_ID))

    assert isinstance(result, Success)
    sessions_put.assert_not_awaited()


@pytest.mark.asyncio
async def test_sign_out_rejects_invalid_session_id(app_section: AppSection) -> None:
    app = _make_app(
        app_section=app_section,
        session_get=AsyncMock(),
        sessions_put=AsyncMock(),
    )

    result = await app.sign_out(iam_pb2.SignOutRequest(session_id="not-a-uuid"))

    assert isinstance(result, Failure)

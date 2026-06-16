"""Unit tests: ``reset_database``."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.results import Failure, Success
from iam_service.services.iam_application import IamServiceApplication


def _make_app(*, admin: AsyncMock, app_section: AppSection) -> IamServiceApplication:
    return IamServiceApplication(
        app=app_section,
        users=AsyncMock(),
        user_types=AsyncMock(),
        login_types=AsyncMock(),
        skill_lists=AsyncMock(),
        skills=AsyncMock(),
        user_skills=AsyncMock(),
        logins=AsyncMock(),
        sessions=AsyncMock(),
        invites=AsyncMock(),
        deployment_admins=AsyncMock(),
        rbac=AsyncMock(),
        admin=admin,
    )


@pytest.mark.asyncio
async def test_reset_database_wipes_users_logins_then_provisions_admin(
    app_section: AppSection,
) -> None:
    admin = AsyncMock()
    admin.users_and_logins_item_count = AsyncMock(return_value=Success(3))
    admin.wipe_users_and_logins = AsyncMock(return_value=Success(None))
    admin.wipe_deployment_admin_table = AsyncMock(return_value=Success(None))
    app = _make_app(admin=admin, app_section=app_section)

    user_pb = iam_pb2.User(id="323e4567-e89b-12d3-a456-426614174002")
    login_pb = iam_pb2.Login(
        id="423e4567-e89b-12d3-a456-426614174003",
        user_id=user_pb.id,
        name="admin@example.com",
    )
    with patch(
        "iam_service.services.iam_application.IamServiceApplication._provision_initial_admin_user",
        new=AsyncMock(return_value=Success((user_pb, login_pb))),
    ) as provision:
        out = await app.reset_database(
            iam_pb2.ResetDatabaseRequest(
                username="admin@example.com",
                password="Secret12@",
            ),
        )

    assert isinstance(out, Success)
    reply = out.unwrap()
    assert reply.total_records_before_reset == 3
    assert reply.user.id == user_pb.id
    assert reply.login.name == login_pb.name
    admin.wipe_users_and_logins.assert_awaited_once()
    admin.wipe_deployment_admin_table.assert_awaited_once()
    provision.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_database_requires_admin(app_section: AppSection) -> None:
    app = IamServiceApplication(
        app=app_section,
        users=AsyncMock(),
        user_types=AsyncMock(),
        login_types=AsyncMock(),
        skill_lists=AsyncMock(),
        skills=AsyncMock(),
        user_skills=AsyncMock(),
        logins=AsyncMock(),
        sessions=AsyncMock(),
        invites=AsyncMock(),
        deployment_admins=AsyncMock(),
        rbac=AsyncMock(),
        admin=None,
    )
    out = await app.reset_database(
        iam_pb2.ResetDatabaseRequest(
            username="admin@example.com",
            password="Secret12@",
        ),
    )
    assert isinstance(out, Failure)

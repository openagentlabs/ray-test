"""Unit tests: ``check_if_new_deployment_can_create_admin``."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.results import Success
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
async def test_check_if_new_deployment_skips_when_logins_exist(app_section: AppSection) -> None:
    admin = AsyncMock()
    admin.count_logins = AsyncMock(return_value=Success(2))
    app = _make_app(admin=admin, app_section=app_section)

    out = await app.check_if_new_deployment_can_create_admin()

    assert isinstance(out, Success)
    admin.count_logins.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_if_new_deployment_provisions_admin_when_logins_empty(
    app_section: AppSection,
) -> None:
    admin = AsyncMock()
    admin.count_logins = AsyncMock(return_value=Success(0))
    app = _make_app(admin=admin, app_section=app_section)

    user_pb = iam_pb2.User(id="323e4567-e89b-12d3-a456-426614174002")
    login_pb = iam_pb2.Login(
        id="423e4567-e89b-12d3-a456-426614174003", name="keith.tobin@gmail.com"
    )
    with (
        patch.dict(
            "os.environ",
            {
                "IAM_BOOTSTRAP_FIRST_NAME": "Keith",
                "IAM_BOOTSTRAP_LAST_NAME": "Tobin",
                "IAM_BOOTSTRAP_EMAIL": "keith.tobin@gmail.com",
                "IAM_BOOTSTRAP_PASSWORD": "Tippertobin12@",
            },
        ),
        patch(
            "iam_service.services.iam_application.IamServiceApplication._provision_initial_admin_user",
            new=AsyncMock(return_value=Success((user_pb, login_pb))),
        ) as provision,
    ):
        out = await app.check_if_new_deployment_can_create_admin()

    assert isinstance(out, Success)
    provision.assert_awaited_once()
    kwargs = provision.await_args.kwargs
    assert kwargs["first_name"] == "Keith"
    assert kwargs["last_name"] == "Tobin"
    assert kwargs["email"] == "keith.tobin@gmail.com"
    assert kwargs["password"] == "Tippertobin12@"


@pytest.mark.asyncio
async def test_check_if_new_deployment_honors_disable_flag(app_section: AppSection) -> None:
    admin = AsyncMock()
    admin.count_logins = AsyncMock(return_value=Success(0))
    app = _make_app(admin=admin, app_section=app_section)

    with patch.dict("os.environ", {"IAM_AUTO_BOOTSTRAP_ADMIN_ON_EMPTY": "false"}):
        out = await app.check_if_new_deployment_can_create_admin()

    assert isinstance(out, Success)
    admin.count_logins.assert_not_awaited()

"""Unit tests for ``IamServiceApplication.sign_in_check``."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.errors import ErrorCodes
from iam_service.core.results import Failure, Success
from iam_service.database.models.records import LoginRecord, UserRecord
from iam_service.services.iam_application import IamServiceApplication

USER_ID = "323e4567-e89b-12d3-a456-426614174002"
LOGIN_ID = "423e4567-e89b-12d3-a456-426614174003"
LOGIN_TYPE_ID = "523e4567-e89b-12d3-a456-426614174004"
ACCOUNT_ID = "123e4567-e89b-12d3-a456-426614174000"
USER_TYPE_ID = "223e4567-e89b-12d3-a456-426614174001"
NOW = "2025-01-01T00:00:00Z"
USERNAME = "alice@example.com"
PASSWORD = "s3cret"


def _user(*, enabled: bool = True) -> UserRecord:
    return UserRecord(
        id=USER_ID,
        created_at=NOW,
        updated_at=NOW,
        deleted_at="",
        is_deleted=False,
        enabled=enabled,
        first_name="Alice",
        last_name="Doe",
        account_id=ACCOUNT_ID,
        notes="",
        timezone="",
        location="",
        skill_list_id="",
        user_type_id=USER_TYPE_ID,
    )


def _login(*, password: str = PASSWORD) -> LoginRecord:
    return LoginRecord(
        id=LOGIN_ID,
        user_id=USER_ID,
        login_type_id=LOGIN_TYPE_ID,
        name=USERNAME,
        description="",
        created_at=NOW,
        updated_at=NOW,
        deleted_at="",
        is_deleted=False,
        enabled=True,
        data_json="{}",
        password=password,
    )


def _make_app(
    *,
    app_section: AppSection,
    login_lookup: AsyncMock,
    user_lookup: AsyncMock,
) -> IamServiceApplication:
    return IamServiceApplication(
        app=app_section,
        users=AsyncMock(get_by_id=user_lookup),
        user_types=AsyncMock(),
        login_types=AsyncMock(),
        skill_lists=AsyncMock(),
        skills=AsyncMock(),
        user_skills=AsyncMock(),
        logins=AsyncMock(find_active_by_name=login_lookup),
        sessions=AsyncMock(),
        invites=AsyncMock(),
        deployment_admins=AsyncMock(
            find_active_by_email=AsyncMock(return_value=Success(None)),
        ),
        rbac=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_sign_in_check_returns_user_and_login_ids(app_section: AppSection) -> None:
    app = _make_app(
        app_section=app_section,
        login_lookup=AsyncMock(return_value=Success(_login())),
        user_lookup=AsyncMock(return_value=Success(_user())),
    )

    out = await app.sign_in_check(
        iam_pb2.SignInCheckRequest(username=USERNAME, password=PASSWORD),
    )

    assert isinstance(out, Success)
    reply = out.unwrap()
    assert reply.user_id == USER_ID
    assert reply.login_id == LOGIN_ID


@pytest.mark.asyncio
async def test_sign_in_check_unauthenticated_on_bad_password(app_section: AppSection) -> None:
    app = _make_app(
        app_section=app_section,
        login_lookup=AsyncMock(return_value=Success(_login(password="other"))),
        user_lookup=AsyncMock(return_value=Success(_user())),
    )

    out = await app.sign_in_check(
        iam_pb2.SignInCheckRequest(username=USERNAME, password=PASSWORD),
    )

    assert isinstance(out, Failure)
    assert out.failure().code == ErrorCodes.UNAUTHENTICATED

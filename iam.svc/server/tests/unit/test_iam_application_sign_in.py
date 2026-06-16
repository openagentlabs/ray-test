"""Unit tests for ``IamServiceApplication.sign_in``."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.errors import ErrorCodes
from iam_service.core.results import Failure, Success
from iam_service.database.models.records import (
    DeploymentAdminRecord,
    LoginRecord,
    UserRecord,
    UserTypeRecord,
)
from iam_service.services.iam_application import IamServiceApplication

ACCOUNT_ID = "123e4567-e89b-12d3-a456-426614174000"
USER_TYPE_ID = "223e4567-e89b-12d3-a456-426614174001"
USER_ID = "323e4567-e89b-12d3-a456-426614174002"
LOGIN_ID = "423e4567-e89b-12d3-a456-426614174003"
LOGIN_TYPE_ID = "523e4567-e89b-12d3-a456-426614174004"
NOW = "2025-01-01T00:00:00Z"
USERNAME = "alice"
PASSWORD = "s3cret"


def _user(
    *,
    enabled: bool = True,
    is_deleted: bool = False,
) -> UserRecord:
    return UserRecord(
        id=USER_ID,
        created_at=NOW,
        updated_at=NOW,
        deleted_at=NOW if is_deleted else "",
        is_deleted=is_deleted,
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


def _login(
    *,
    name: str = USERNAME,
    password: str = PASSWORD,
    enabled: bool = True,
    is_deleted: bool = False,
) -> LoginRecord:
    return LoginRecord(
        id=LOGIN_ID,
        user_id=USER_ID,
        login_type_id=LOGIN_TYPE_ID,
        name=name,
        description="",
        created_at=NOW,
        updated_at=NOW,
        deleted_at=NOW if is_deleted else "",
        is_deleted=is_deleted,
        enabled=enabled,
        data_json="{}",
        password=password,
    )


def _make_app(
    *,
    app_section: AppSection,
    login_lookup: AsyncMock,
    user_lookup: AsyncMock,
    sessions_put: AsyncMock,
    user_type_lookup: AsyncMock | None = None,
) -> tuple[IamServiceApplication, AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    users_repo = AsyncMock()
    users_repo.get_by_id = user_lookup
    logins_repo = AsyncMock()
    logins_repo.find_active_by_name = login_lookup
    sessions_repo = AsyncMock()
    sessions_repo.put = sessions_put
    user_types_repo = AsyncMock()
    user_types_repo.get_by_id = user_type_lookup or AsyncMock(return_value=Success(None))
    deployment_admins_repo = AsyncMock()
    deployment_admins_repo.find_active_by_email = AsyncMock(return_value=Success(None))
    rbac = AsyncMock()
    rbac.build_user_auth_context = AsyncMock(
        return_value=Success(
            iam_pb2.UserAuthContext(
                user_id=USER_ID,
                role_codes=["viewer"],
                permission_grants=[
                    iam_pb2.PermissionGrant(permission_code="solutions.read", role_code="viewer"),
                ],
                auth_json=(
                    '{"permission_grants":[{"permission_code":"solutions.read","role_code":"viewer"}],'
                    f'"role_codes":["viewer"],"user_id":"{USER_ID}"}}'
                ),
            ),
        ),
    )
    app = IamServiceApplication(
        app=app_section,
        users=users_repo,
        user_types=user_types_repo,
        login_types=AsyncMock(),
        skill_lists=AsyncMock(),
        skills=AsyncMock(),
        user_skills=AsyncMock(),
        logins=logins_repo,
        sessions=sessions_repo,
        invites=AsyncMock(),
        deployment_admins=deployment_admins_repo,
        rbac=rbac,
    )
    return app, users_repo, logins_repo, sessions_repo, user_types_repo


@pytest.mark.asyncio
async def test_sign_in_returns_session_when_credentials_match(app_section: AppSection) -> None:
    login_lookup = AsyncMock(return_value=Success(_login()))
    user_lookup = AsyncMock(return_value=Success(_user()))
    sessions_put = AsyncMock(return_value=Success(None))
    app, _, logins_repo, sessions_repo, _user_types = _make_app(
        app_section=app_section,
        login_lookup=login_lookup,
        user_lookup=user_lookup,
        sessions_put=sessions_put,
    )

    out = await app.sign_in(iam_pb2.SignInRequest(username=USERNAME, password=PASSWORD))

    assert isinstance(out, Success)
    session = out.unwrap()
    assert session.user_id == USER_ID
    assert session.login_id == LOGIN_ID
    assert session.id  # non-empty UUID
    assert session.expires_at.seconds > session.created_at.seconds
    assert session.first_name == "Alice"
    assert session.last_name == "Doe"
    assert session.email == USERNAME
    assert session.user_type_id == USER_TYPE_ID
    assert session.user_type_display_name == ""
    logins_repo.find_active_by_name.assert_awaited_once_with(name=USERNAME)
    sessions_repo.put.assert_awaited_once()


@pytest.mark.asyncio
async def test_sign_in_includes_user_type_display_name_when_resolved(
    app_section: AppSection,
) -> None:
    ut = UserTypeRecord(
        id=USER_TYPE_ID,
        created_at=NOW,
        updated_at=NOW,
        deleted_at="",
        is_deleted=False,
        enabled=True,
        code="arch",
        display_name="Architect",
        data_json="{}",
    )
    login_lookup = AsyncMock(return_value=Success(_login()))
    user_lookup = AsyncMock(return_value=Success(_user()))
    sessions_put = AsyncMock(return_value=Success(None))
    user_type_lookup = AsyncMock(return_value=Success(ut))
    app, _, logins_repo, sessions_repo, _user_types = _make_app(
        app_section=app_section,
        login_lookup=login_lookup,
        user_lookup=user_lookup,
        sessions_put=sessions_put,
        user_type_lookup=user_type_lookup,
    )

    out = await app.sign_in(iam_pb2.SignInRequest(username=USERNAME, password=PASSWORD))

    assert isinstance(out, Success)
    session = out.unwrap()
    assert session.user_type_display_name == "Architect"
    _user_types.get_by_id.assert_awaited_once_with(item_id=USER_TYPE_ID, include_deleted=False)
    sessions_repo.put.assert_awaited_once()
    logins_repo.find_active_by_name.assert_awaited_once_with(name=USERNAME)


@pytest.mark.asyncio
async def test_sign_in_unauthenticated_when_login_not_found(app_section: AppSection) -> None:
    app, _, _, sessions_repo, _user_types = _make_app(
        app_section=app_section,
        login_lookup=AsyncMock(return_value=Success(None)),
        user_lookup=AsyncMock(),
        sessions_put=AsyncMock(),
    )

    out = await app.sign_in(iam_pb2.SignInRequest(username="ghost", password=PASSWORD))

    assert isinstance(out, Failure)
    assert out.failure().code == ErrorCodes.UNAUTHENTICATED
    sessions_repo.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_sign_in_succeeds_via_deployment_admin_table(app_section: AppSection) -> None:
    dep = DeploymentAdminRecord(
        id=USER_ID,
        email="bootstrap@example.com",
        password=PASSWORD,
        first_name="Boot",
        last_name="Admin",
        created_at=NOW,
        updated_at=NOW,
        user_type_id=USER_TYPE_ID,
        account_id=ACCOUNT_ID,
    )
    app, users_repo, logins_repo, sessions_repo, _user_types = _make_app(
        app_section=app_section,
        login_lookup=AsyncMock(return_value=Success(None)),
        user_lookup=AsyncMock(),
        sessions_put=AsyncMock(return_value=Success(None)),
    )
    app._deployment_admins.find_active_by_email = AsyncMock(return_value=Success(dep))

    out = await app.sign_in(
        iam_pb2.SignInRequest(username="bootstrap@example.com", password=PASSWORD),
    )

    assert isinstance(out, Success)
    users_repo.get_by_id.assert_not_awaited()
    logins_repo.find_active_by_name.assert_awaited_once_with(name="bootstrap@example.com")
    app._deployment_admins.find_active_by_email.assert_awaited_once_with(
        email="bootstrap@example.com"
    )
    sessions_repo.put.assert_awaited_once()


@pytest.mark.asyncio
async def test_sign_in_unauthenticated_when_password_mismatch(app_section: AppSection) -> None:
    app, _, _, sessions_repo, _user_types = _make_app(
        app_section=app_section,
        login_lookup=AsyncMock(return_value=Success(_login(password="other"))),
        user_lookup=AsyncMock(return_value=Success(_user())),
        sessions_put=AsyncMock(),
    )

    out = await app.sign_in(iam_pb2.SignInRequest(username=USERNAME, password=PASSWORD))

    assert isinstance(out, Failure)
    assert out.failure().code == ErrorCodes.UNAUTHENTICATED
    sessions_repo.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_sign_in_unauthenticated_when_user_disabled(app_section: AppSection) -> None:
    app, _, _, sessions_repo, _user_types = _make_app(
        app_section=app_section,
        login_lookup=AsyncMock(return_value=Success(_login())),
        user_lookup=AsyncMock(return_value=Success(_user(enabled=False))),
        sessions_put=AsyncMock(),
    )

    out = await app.sign_in(iam_pb2.SignInRequest(username=USERNAME, password=PASSWORD))

    assert isinstance(out, Failure)
    assert out.failure().code == ErrorCodes.UNAUTHENTICATED
    sessions_repo.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_sign_in_unauthenticated_when_user_missing(app_section: AppSection) -> None:
    app, _, _, sessions_repo, _user_types = _make_app(
        app_section=app_section,
        login_lookup=AsyncMock(return_value=Success(_login())),
        user_lookup=AsyncMock(return_value=Success(None)),
        sessions_put=AsyncMock(),
    )

    out = await app.sign_in(iam_pb2.SignInRequest(username=USERNAME, password=PASSWORD))

    assert isinstance(out, Failure)
    assert out.failure().code == ErrorCodes.UNAUTHENTICATED
    sessions_repo.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_sign_in_validation_error_when_username_blank(app_section: AppSection) -> None:
    app, _, logins_repo, sessions_repo, _user_types = _make_app(
        app_section=app_section,
        login_lookup=AsyncMock(),
        user_lookup=AsyncMock(),
        sessions_put=AsyncMock(),
    )

    out = await app.sign_in(iam_pb2.SignInRequest(username="   ", password=PASSWORD))

    assert isinstance(out, Failure)
    assert out.failure().code == ErrorCodes.VALIDATION
    logins_repo.find_active_by_name.assert_not_awaited()
    sessions_repo.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_sign_in_validation_error_when_password_blank(app_section: AppSection) -> None:
    app, _, logins_repo, sessions_repo, _user_types = _make_app(
        app_section=app_section,
        login_lookup=AsyncMock(),
        user_lookup=AsyncMock(),
        sessions_put=AsyncMock(),
    )

    out = await app.sign_in(iam_pb2.SignInRequest(username=USERNAME, password=""))

    assert isinstance(out, Failure)
    assert out.failure().code == ErrorCodes.VALIDATION
    logins_repo.find_active_by_name.assert_not_awaited()
    sessions_repo.put.assert_not_awaited()

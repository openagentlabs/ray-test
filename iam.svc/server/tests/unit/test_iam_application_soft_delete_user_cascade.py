"""Unit tests: ``soft_delete_user`` cascades to dependent logins before the user."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.results import Success
from iam_service.database.models.records import LoginRecord, UserRecord
from iam_service.services.iam_application import IamServiceApplication

USER_ID = "323e4567-e89b-12d3-a456-426614174002"
LOGIN_ID = "423e4567-e89b-12d3-a456-426614174003"
NOW = "2025-01-01T00:00:00Z"


@pytest.fixture
def users_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(
        return_value=Success(
            UserRecord(
                id=USER_ID,
                created_at=NOW,
                updated_at=NOW,
                deleted_at="",
                is_deleted=False,
                enabled=True,
                first_name="A",
                last_name="B",
                account_id="123e4567-e89b-12d3-a456-426614174000",
                notes="",
                timezone="",
                location="",
                skill_list_id="",
                user_type_id="223e4567-e89b-12d3-a456-426614174001",
            ),
        ),
    )
    repo.soft_delete = AsyncMock(
        return_value=Success(
            UserRecord(
                id=USER_ID,
                created_at=NOW,
                updated_at=NOW,
                deleted_at=NOW,
                is_deleted=True,
                enabled=True,
                first_name="A",
                last_name="B",
                account_id="123e4567-e89b-12d3-a456-426614174000",
                notes="",
                timezone="",
                location="",
                skill_list_id="",
                user_type_id="223e4567-e89b-12d3-a456-426614174001",
            ),
        ),
    )
    return repo


@pytest.fixture
def logins_repo() -> AsyncMock:
    repo = AsyncMock()
    login = LoginRecord(
        id=LOGIN_ID,
        user_id=USER_ID,
        login_type_id="523e4567-e89b-12d3-a456-426614174004",
        name="a@b.co",
        description="",
        created_at=NOW,
        updated_at=NOW,
        deleted_at="",
        is_deleted=False,
        enabled=True,
        data_json="{}",
    )
    repo.query_by_user = AsyncMock(
        side_effect=[
            Success(([login], "")),
        ],
    )
    repo.soft_delete = AsyncMock(
        return_value=Success(
            login.model_copy(
                update={"is_deleted": True, "deleted_at": NOW, "updated_at": NOW},
            ),
        ),
    )
    return repo


@pytest.fixture
def delete_user_app(
    app_section: AppSection,
    users_repo: AsyncMock,
    logins_repo: AsyncMock,
    skills_repo_mock: AsyncMock,
    user_skills_repo_mock: AsyncMock,
) -> IamServiceApplication:
    return IamServiceApplication(
        app=app_section,
        users=users_repo,
        user_types=AsyncMock(),
        login_types=AsyncMock(),
        skill_lists=AsyncMock(),
        skills=skills_repo_mock,
        user_skills=user_skills_repo_mock,
        logins=logins_repo,
        sessions=AsyncMock(),
        invites=AsyncMock(),
        deployment_admins=AsyncMock(),
        rbac=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_soft_delete_user_soft_deletes_logins_first(
    delete_user_app: IamServiceApplication,
    users_repo: AsyncMock,
    logins_repo: AsyncMock,
    user_skills_repo_mock: AsyncMock,
) -> None:
    req = iam_pb2.SoftDeleteUserRequest(id=USER_ID)
    out = await delete_user_app.soft_delete_user(req)
    assert isinstance(out, Success)

    user_skills_repo_mock.query_by_user.assert_awaited()
    logins_repo.query_by_user.assert_awaited()
    logins_repo.soft_delete.assert_awaited_once()
    assert logins_repo.soft_delete.await_args.kwargs["login_id"] == LOGIN_ID

    users_repo.soft_delete.assert_awaited_once()
    assert users_repo.soft_delete.await_args.kwargs["user_id"] == USER_ID


@pytest.mark.asyncio
async def test_soft_delete_user_paginates_logins_until_exhausted(
    app_section: AppSection,
    users_repo: AsyncMock,
) -> None:
    logins_repo = AsyncMock()
    login1 = LoginRecord(
        id="623e4567-e89b-12d3-a456-426614174005",
        user_id=USER_ID,
        login_type_id="523e4567-e89b-12d3-a456-426614174004",
        name="one",
        description="",
        created_at=NOW,
        updated_at=NOW,
        deleted_at="",
        is_deleted=False,
        enabled=True,
        data_json="{}",
    )
    login2 = LoginRecord(
        id="723e4567-e89b-12d3-a456-426614174006",
        user_id=USER_ID,
        login_type_id="523e4567-e89b-12d3-a456-426614174004",
        name="two",
        description="",
        created_at=NOW,
        updated_at=NOW,
        deleted_at="",
        is_deleted=False,
        enabled=True,
        data_json="{}",
    )
    logins_repo.query_by_user = AsyncMock(
        side_effect=[
            Success(([login1], "next-page")),
            Success(([login2], "")),
        ],
    )
    logins_repo.soft_delete = AsyncMock(return_value=Success(login1))

    user_skills = AsyncMock()
    user_skills.query_by_user = AsyncMock(return_value=Success(([], "")))
    user_skills.soft_delete = AsyncMock(return_value=Success(None))
    skills = AsyncMock()

    app = IamServiceApplication(
        app=app_section,
        users=users_repo,
        user_types=AsyncMock(),
        login_types=AsyncMock(),
        skill_lists=AsyncMock(),
        skills=skills,
        user_skills=user_skills,
        logins=logins_repo,
        sessions=AsyncMock(),
        invites=AsyncMock(),
        deployment_admins=AsyncMock(),
        rbac=AsyncMock(),
    )
    out = await app.soft_delete_user(iam_pb2.SoftDeleteUserRequest(id=USER_ID))
    assert isinstance(out, Success)
    assert logins_repo.query_by_user.await_count == 2
    assert logins_repo.soft_delete.await_count == 2

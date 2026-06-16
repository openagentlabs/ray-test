"""Unit tests: ``list_users_by_account`` validation and repository kwargs."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.results import Failure, Success
from iam_service.services.iam_application import IamServiceApplication

ACCOUNT_ID = "123e4567-e89b-12d3-a456-426614174000"
USER_TYPE_ID = "223e4567-e89b-12d3-a456-426614174001"


@pytest.fixture
def users_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.query_by_account = AsyncMock(return_value=Success(([], "")))
    return repo


@pytest.fixture
def list_users_app(
    app_section: AppSection,
    users_repo: AsyncMock,
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
        logins=AsyncMock(),
        sessions=AsyncMock(),
        invites=AsyncMock(),
        deployment_admins=AsyncMock(),
        rbac=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_list_users_passes_optional_filters_to_repository(
    list_users_app: IamServiceApplication,
    users_repo: AsyncMock,
) -> None:
    req = iam_pb2.ListUsersByAccountRequest(
        account_id=ACCOUNT_ID,
        page_size=30,
        include_deleted=True,
    )
    req.user_type_id = USER_TYPE_ID
    req.enabled = False
    req.name_contains = "Ada"

    out = await list_users_app.list_users_by_account(req)
    assert isinstance(out, Success)
    users_repo.query_by_account.assert_awaited_once()
    kwargs = users_repo.query_by_account.await_args.kwargs
    assert kwargs["account_id"] == ACCOUNT_ID
    assert kwargs["include_deleted"] is True
    assert kwargs["page_size"] == 30
    assert kwargs["user_type_id"] == USER_TYPE_ID
    assert kwargs["enabled_equals"] is False
    assert kwargs["name_contains"] == "Ada"


@pytest.mark.asyncio
async def test_list_users_rejects_non_uuid_user_type_filter(
    list_users_app: IamServiceApplication,
    users_repo: AsyncMock,
) -> None:
    req = iam_pb2.ListUsersByAccountRequest(account_id=ACCOUNT_ID, page_size=10)
    req.user_type_id = "not-a-uuid"

    out = await list_users_app.list_users_by_account(req)
    assert isinstance(out, Failure)
    users_repo.query_by_account.assert_not_called()


@pytest.mark.asyncio
async def test_list_users_whitespace_only_name_filter_becomes_none(
    list_users_app: IamServiceApplication,
    users_repo: AsyncMock,
) -> None:
    req = iam_pb2.ListUsersByAccountRequest(account_id=ACCOUNT_ID, page_size=10)
    req.name_contains = "   \t  "

    await list_users_app.list_users_by_account(req)
    kwargs = users_repo.query_by_account.await_args.kwargs
    assert kwargs["name_contains"] is None

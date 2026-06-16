"""Integration-style tests: gRPC servicer delegates list users to the application layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.results import Success
from iam_service.grpc_transport.iam_servicer import IamGrpcServicer
from iam_service.services.iam_application import IamServiceApplication

ACCOUNT_ID = "123e4567-e89b-12d3-a456-426614174000"
USER_TYPE_ID = "223e4567-e89b-12d3-a456-426614174001"


def _servicer_context() -> MagicMock:
    ctx = MagicMock()
    ctx.abort = AsyncMock(return_value=None)
    return ctx


@pytest.mark.asyncio
async def test_grpc_list_users_by_account_success(
    app_section: AppSection,
    skills_repo_mock: AsyncMock,
    user_skills_repo_mock: AsyncMock,
) -> None:
    users = AsyncMock()
    users.query_by_account = AsyncMock(return_value=Success(([], "")))
    app = IamServiceApplication(
        app=app_section,
        users=users,
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
    servicer = IamGrpcServicer(app=app)
    req = iam_pb2.ListUsersByAccountRequest(account_id=ACCOUNT_ID, page_size=10)
    ctx = _servicer_context()

    resp = await servicer.ListUsersByAccount(req, ctx)

    assert resp.next_page_token == ""
    assert len(resp.users) == 0
    ctx.abort.assert_not_called()


@pytest.mark.asyncio
async def test_grpc_list_users_by_account_abort_on_validation(
    app_section: AppSection,
    skills_repo_mock: AsyncMock,
    user_skills_repo_mock: AsyncMock,
) -> None:
    users = AsyncMock()
    users.query_by_account = AsyncMock(return_value=Success(([], "")))
    app = IamServiceApplication(
        app=app_section,
        users=users,
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
    servicer = IamGrpcServicer(app=app)
    req = iam_pb2.ListUsersByAccountRequest(account_id=ACCOUNT_ID, page_size=10)
    req.user_type_id = "bad"
    ctx = _servicer_context()

    with pytest.raises(AssertionError, match="context.abort should not return"):
        await servicer.ListUsersByAccount(req, ctx)

    users.query_by_account.assert_not_called()
    ctx.abort.assert_awaited()


@pytest.mark.asyncio
async def test_grpc_list_users_forwards_filters(
    app_section: AppSection,
    skills_repo_mock: AsyncMock,
    user_skills_repo_mock: AsyncMock,
) -> None:
    users = AsyncMock()
    users.query_by_account = AsyncMock(return_value=Success(([], "")))
    app = IamServiceApplication(
        app=app_section,
        users=users,
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
    servicer = IamGrpcServicer(app=app)
    req = iam_pb2.ListUsersByAccountRequest(account_id=ACCOUNT_ID, page_size=15)
    req.user_type_id = USER_TYPE_ID
    req.enabled = True
    req.name_contains = "Kim"
    ctx = _servicer_context()

    await servicer.ListUsersByAccount(req, ctx)

    kwargs = users.query_by_account.await_args.kwargs
    assert kwargs["user_type_id"] == USER_TYPE_ID
    assert kwargs["enabled_equals"] is True
    assert kwargs["name_contains"] == "Kim"

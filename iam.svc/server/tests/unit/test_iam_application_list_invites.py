"""Unit tests: ``list_invites``."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.results import Success
from iam_service.database.models.records import InviteRecord
from iam_service.services.iam_application import IamServiceApplication

NOW = "2025-01-01T00:00:00Z"
ACCOUNT = "123e4567-e89b-12d3-a456-426614174000"
UT = "223e4567-e89b-12d3-a456-426614174001"
LT = "523e4567-e89b-12d3-a456-426614174004"


@pytest.mark.asyncio
async def test_list_invites_maps_repository_rows(
    app_section: AppSection,
    skills_repo_mock: AsyncMock,
    user_skills_repo_mock: AsyncMock,
) -> None:
    inv = InviteRecord(
        id="323e4567-e89b-12d3-a456-426614174002",
        created_at=NOW,
        updated_at=NOW,
        deleted_at="",
        is_deleted=False,
        code="AB12-CD-EF34",
        expires_at="2025-01-02T00:00:00Z",
        redeemed=False,
        account_id=ACCOUNT,
        user_type_id=UT,
        login_type_id=LT,
        recipient_email="a@b.co",
    )
    invites = AsyncMock()
    invites.scan_page = AsyncMock(return_value=Success(([inv], "next-page")))
    app = IamServiceApplication(
        app=app_section,
        users=AsyncMock(),
        user_types=AsyncMock(),
        login_types=AsyncMock(),
        skill_lists=AsyncMock(),
        skills=skills_repo_mock,
        user_skills=user_skills_repo_mock,
        logins=AsyncMock(),
        sessions=AsyncMock(),
        invites=invites,
        deployment_admins=AsyncMock(),
        rbac=AsyncMock(),
    )
    out = await app.list_invites(iam_pb2.ListInvitesRequest(include_deleted=False, page_size=10))
    assert isinstance(out, Success)
    reply = out.unwrap()
    assert reply.next_page_token == "next-page"
    assert len(reply.items) == 1
    assert reply.items[0].code == "AB12-CD-EF34"
    assert reply.items[0].recipient_email == "a@b.co"

"""Unit tests: ``get_user_type_stats`` aggregates users by resolved type label."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.results import Failure, Success
from iam_service.database.models.records import UserTypeRecord
from iam_service.services.iam_application import IamServiceApplication

ACCOUNT_ID = "123e4567-e89b-12d3-a456-426614174000"
TYPE_A = "11111111-1111-1111-1111-111111111111"
TYPE_B = "22222222-2222-2222-2222-222222222222"
NOW = "2025-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_get_user_type_stats_sorted_by_count(
    app_section: AppSection,
    skills_repo_mock: AsyncMock,
    user_skills_repo_mock: AsyncMock,
) -> None:
    user_types = AsyncMock()
    user_types.scan_page = AsyncMock(
        return_value=Success(
            (
                [
                    UserTypeRecord(
                        id=TYPE_A,
                        created_at=NOW,
                        updated_at=NOW,
                        deleted_at="",
                        is_deleted=False,
                        enabled=True,
                        code="arch",
                        display_name="Architect",
                        data_json="",
                    ),
                    UserTypeRecord(
                        id=TYPE_B,
                        created_at=NOW,
                        updated_at=NOW,
                        deleted_at="",
                        is_deleted=False,
                        enabled=True,
                        code="admin",
                        display_name="",
                        data_json="",
                    ),
                ],
                "",
            ),
        ),
    )

    users = AsyncMock()
    users.aggregate_user_type_id_counts_for_account = AsyncMock(
        return_value=Success(
            {
                TYPE_A: 2,
                TYPE_B: 1,
                "": 1,
            },
        ),
    )

    app = IamServiceApplication(
        app=app_section,
        users=users,
        user_types=user_types,
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
    req = iam_pb2.GetUserTypeStatsRequest(account_id=ACCOUNT_ID, include_deleted=False)
    out = await app.get_user_type_stats(req)
    assert isinstance(out, Success)
    reply = out.unwrap()
    assert [(e.type_name, e.count) for e in reply.entries] == [
        ("Architect", 2),
        ("admin", 1),
        ("—", 1),
    ]


@pytest.mark.asyncio
async def test_get_user_type_stats_validation(
    app_section: AppSection,
    skills_repo_mock: AsyncMock,
    user_skills_repo_mock: AsyncMock,
) -> None:
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
        invites=AsyncMock(),
        deployment_admins=AsyncMock(),
        rbac=AsyncMock(),
    )
    req = iam_pb2.GetUserTypeStatsRequest(account_id="not-a-uuid", include_deleted=False)
    out = await app.get_user_type_stats(req)
    assert isinstance(out, Failure)

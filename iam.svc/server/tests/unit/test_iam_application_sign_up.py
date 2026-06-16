"""Unit tests: ``sign_up_user`` validation."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.errors import ErrorCodes
from iam_service.core.results import Failure
from iam_service.services.iam_application import IamServiceApplication


@pytest.mark.asyncio
async def test_sign_up_password_mismatch(
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
    req = iam_pb2.SignUpUserRequest(
        email="a@b.co",
        first_name="A",
        last_name="B",
        password="one",
        password_confirm="two",
        invite_code="AB12-CD-EF34",
    )
    out = await app.sign_up_user(req)
    assert isinstance(out, Failure)
    assert out.failure().code == ErrorCodes.VALIDATION

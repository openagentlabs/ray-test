"""Unit tests for ``RbacService`` authorization helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from iam.v1 import iam_pb2
from iam_service.core.results import Success
from iam_service.database.models.records import (
    PermissionRecord,
    RolePermissionRecord,
    RoleRecord,
    UserRoleAssignmentRecord,
)
from iam_service.database.repositories.rbac_repository import RbacRepository
from iam_service.services.rbac_service import RbacService

NOW = "2025-01-01T00:00:00Z"
USER_ID = "323e4567-e89b-12d3-a456-426614174002"
ROLE_VIEWER_ID = "30000000-0000-4000-8000-000000000005"
PERM_READ_ID = "40000000-0000-4000-8000-000000000004"


def _viewer_role() -> RoleRecord:
    return RoleRecord(
        id=ROLE_VIEWER_ID,
        created_at=NOW,
        updated_at=NOW,
        code="viewer",
        display_name="Viewer",
    )


def _read_permission() -> PermissionRecord:
    return PermissionRecord(
        id=PERM_READ_ID,
        created_at=NOW,
        updated_at=NOW,
        code="solutions.read",
        display_name="Read solutions",
    )


@pytest.fixture
def rbac_service() -> RbacService:
    repo = AsyncMock(spec=RbacRepository)
    repo.list_roles_for_user = AsyncMock(
        return_value=Success(
            [
                UserRoleAssignmentRecord(
                    user_id=USER_ID,
                    role_id=ROLE_VIEWER_ID,
                    role_code="viewer",
                    created_at=NOW,
                    updated_at=NOW,
                ),
            ],
        ),
    )
    repo.list_permissions_for_role = AsyncMock(
        return_value=Success(
            [
                RolePermissionRecord(
                    role_id=ROLE_VIEWER_ID,
                    permission_id=PERM_READ_ID,
                    role_code="viewer",
                    permission_code="solutions.read",
                    created_at=NOW,
                    updated_at=NOW,
                ),
            ],
        ),
    )
    repo.roles = AsyncMock()
    repo.roles.get_by_id = AsyncMock(return_value=Success(_viewer_role()))
    repo.permissions = AsyncMock()
    repo.permissions.get_by_id = AsyncMock(return_value=Success(_read_permission()))
    return RbacService(repo=repo)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_build_user_auth_context_returns_stable_json(rbac_service: RbacService) -> None:
    out = await rbac_service.build_user_auth_context(USER_ID)

    assert isinstance(out, Success)
    ctx = out.unwrap()
    assert ctx.user_id == USER_ID
    assert list(ctx.role_codes) == ["viewer"]
    assert len(ctx.permission_grants) == 1
    assert ctx.permission_grants[0].permission_code == "solutions.read"
    assert ctx.permission_grants[0].role_code == "viewer"
    assert '"role_codes":["viewer"]' in ctx.auth_json
    assert '"permission_code":"solutions.read"' in ctx.auth_json


@pytest.mark.asyncio
async def test_check_permission_true_when_granted(rbac_service: RbacService) -> None:
    ctx = iam_pb2.UserAuthContext(
        permission_grants=[
            iam_pb2.PermissionGrant(permission_code="solutions.read", role_code="viewer"),
        ],
    )
    assert rbac_service.check_permission(ctx, "solutions.read") is True
    assert rbac_service.check_permission(ctx, "SOLUTIONS.READ") is True


@pytest.mark.asyncio
async def test_check_permission_false_when_missing(rbac_service: RbacService) -> None:
    ctx = iam_pb2.UserAuthContext(
        permission_grants=[
            iam_pb2.PermissionGrant(permission_code="solutions.read", role_code="viewer"),
        ],
    )
    assert rbac_service.check_permission(ctx, "solutions.write") is False

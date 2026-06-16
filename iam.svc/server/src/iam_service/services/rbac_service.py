"""RBAC domain: bootstrap, authorization context, and admin CRUD."""

from __future__ import annotations

import json
import re
from uuid import uuid4

from iam.v1 import iam_pb2
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.database.models.records import (
    PermissionRecord,
    RolePermissionRecord,
    RoleRecord,
    ServicePermissionRecord,
    UserRoleAssignmentRecord,
)
from iam_service.database.repositories.rbac_repository import RbacRepository
from iam_service.grpc_transport.iam_converters import (
    permission_to_pb,
    role_permission_to_pb,
    role_to_pb,
    service_permission_to_pb,
    user_role_assignment_to_pb,
)
from iam_service.grpc_transport.proto_time import utc_now_iso_z

_CODE_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")

# Stable bootstrap ids (aligned with initial_tenant_bootstrap style).
ROLE_SYSTEM_ADMIN_ID = "30000000-0000-4000-8000-000000000001"
ROLE_SOLUTION_OWNER_ID = "30000000-0000-4000-8000-000000000002"
ROLE_ARCHITECT_ID = "30000000-0000-4000-8000-000000000003"
ROLE_CONTRIBUTOR_ID = "30000000-0000-4000-8000-000000000004"
ROLE_VIEWER_ID = "30000000-0000-4000-8000-000000000005"

ROLE_SYSTEM_ADMIN_CODE = "system_admin"
ROLE_SOLUTION_OWNER_CODE = "solution_owner"
ROLE_ARCHITECT_CODE = "architect"
ROLE_CONTRIBUTOR_CODE = "contributor"
ROLE_VIEWER_CODE = "viewer"

PERM_IAM_RBAC_MANAGE = "iam.rbac.manage"
PERM_IAM_USERS_READ = "iam.users.read"
PERM_IAM_USERS_WRITE = "iam.users.write"
PERM_SOLUTIONS_READ = "solutions.read"
PERM_SOLUTIONS_WRITE = "solutions.write"
PERM_SOLUTIONS_REVIEW = "solutions.review"
PERM_STORAGE_READ = "storage.read"
PERM_STORAGE_WRITE = "storage.write"
PERM_COLLABORATION_READ = "collaboration.read"
PERM_COLLABORATION_WRITE = "collaboration.write"

_BOOTSTRAP_ROLES: tuple[tuple[str, str, str], ...] = (
    (ROLE_SYSTEM_ADMIN_ID, ROLE_SYSTEM_ADMIN_CODE, "System administrator"),
    (ROLE_SOLUTION_OWNER_ID, ROLE_SOLUTION_OWNER_CODE, "Solution owner"),
    (ROLE_ARCHITECT_ID, ROLE_ARCHITECT_CODE, "Architect"),
    (ROLE_CONTRIBUTOR_ID, ROLE_CONTRIBUTOR_CODE, "Contributor"),
    (ROLE_VIEWER_ID, ROLE_VIEWER_CODE, "Viewer"),
)

_BOOTSTRAP_PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("40000000-0000-4000-8000-000000000001", PERM_IAM_RBAC_MANAGE, "Manage IAM RBAC"),
    ("40000000-0000-4000-8000-000000000002", PERM_IAM_USERS_READ, "Read IAM users"),
    ("40000000-0000-4000-8000-000000000003", PERM_IAM_USERS_WRITE, "Write IAM users"),
    ("40000000-0000-4000-8000-000000000004", PERM_SOLUTIONS_READ, "Read solutions"),
    ("40000000-0000-4000-8000-000000000005", PERM_SOLUTIONS_WRITE, "Write solutions"),
    ("40000000-0000-4000-8000-000000000006", PERM_SOLUTIONS_REVIEW, "Review solutions"),
    ("40000000-0000-4000-8000-000000000007", PERM_STORAGE_READ, "Read storage"),
    ("40000000-0000-4000-8000-000000000008", PERM_STORAGE_WRITE, "Write storage"),
    ("40000000-0000-4000-8000-000000000009", PERM_COLLABORATION_READ, "Read collaboration"),
    ("40000000-0000-4000-8000-000000000010", PERM_COLLABORATION_WRITE, "Write collaboration"),
)

_ROLE_PERMISSION_MAP: dict[str, tuple[str, ...]] = {
    ROLE_SYSTEM_ADMIN_CODE: tuple(p[1] for p in _BOOTSTRAP_PERMISSIONS),
    ROLE_SOLUTION_OWNER_CODE: (
        PERM_IAM_USERS_READ,
        PERM_SOLUTIONS_READ,
        PERM_SOLUTIONS_WRITE,
        PERM_SOLUTIONS_REVIEW,
        PERM_STORAGE_READ,
        PERM_STORAGE_WRITE,
        PERM_COLLABORATION_READ,
        PERM_COLLABORATION_WRITE,
    ),
    ROLE_ARCHITECT_CODE: (
        PERM_IAM_USERS_READ,
        PERM_SOLUTIONS_READ,
        PERM_SOLUTIONS_WRITE,
        PERM_SOLUTIONS_REVIEW,
        PERM_STORAGE_READ,
        PERM_COLLABORATION_READ,
        PERM_COLLABORATION_WRITE,
    ),
    ROLE_CONTRIBUTOR_CODE: (
        PERM_SOLUTIONS_READ,
        PERM_SOLUTIONS_WRITE,
        PERM_STORAGE_READ,
        PERM_COLLABORATION_READ,
        PERM_COLLABORATION_WRITE,
    ),
    ROLE_VIEWER_CODE: (
        PERM_SOLUTIONS_READ,
        PERM_STORAGE_READ,
        PERM_COLLABORATION_READ,
    ),
}


def _clamp_page_size(raw: int) -> int:
    if raw <= 0:
        return 50
    return min(raw, 200)


def _normalize_code(code: str) -> str:
    return code.strip().lower()


def _validate_code(code: str) -> Result[str, AppError]:
    norm = _normalize_code(code)
    if not norm or not _CODE_RE.match(norm):
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="code must be lowercase alphanumeric with dots, dashes, or underscores.",
                detail=code,
            ),
        )
    return Success(norm)


def _stable_auth_json(
    *,
    user_id: str,
    role_codes: list[str],
    grants: list[tuple[str, str]],
) -> str:
    payload = {
        "user_id": user_id,
        "role_codes": sorted(role_codes),
        "permission_grants": [
            {"permission_code": p, "role_code": r}
            for p, r in sorted(grants, key=lambda g: (g[0], g[1]))
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class RbacService:
    """RBAC orchestration over ``RbacRepository``."""

    __slots__ = ("_repo",)

    def __init__(self, *, repo: RbacRepository) -> None:
        self._repo = repo

    async def bootstrap_default_rbac(self) -> Result[None, AppError]:
        """Seed default roles, permissions, and role-permission links (idempotent)."""
        now = utc_now_iso_z()
        perm_by_code: dict[str, PermissionRecord] = {}

        for perm_id, code, display in _BOOTSTRAP_PERMISSIONS:
            existing = await self._repo.find_permission_by_code(code=code)
            if isinstance(existing, Failure):
                return existing
            if existing.unwrap() is not None:
                perm_by_code[code] = existing.unwrap()  # type: ignore[assignment]
                continue
            rec = PermissionRecord(
                id=perm_id,
                created_at=now,
                updated_at=now,
                deleted_at="",
                is_deleted=False,
                enabled=True,
                code=code,
                display_name=display,
                data_json="{}",
            )
            put = await self._repo.permissions.put(rec)
            if isinstance(put, Failure):
                return put
            perm_by_code[code] = rec

        role_by_code: dict[str, RoleRecord] = {}
        for role_id, code, display in _BOOTSTRAP_ROLES:
            existing = await self._repo.find_role_by_code(code=code)
            if isinstance(existing, Failure):
                return existing
            if existing.unwrap() is not None:
                role_by_code[code] = existing.unwrap()  # type: ignore[assignment]
                continue
            rec = RoleRecord(
                id=role_id,
                created_at=now,
                updated_at=now,
                deleted_at="",
                is_deleted=False,
                enabled=True,
                code=code,
                display_name=display,
                data_json="{}",
            )
            put = await self._repo.roles.put(rec)
            if isinstance(put, Failure):
                return put
            role_by_code[code] = rec

        for role_code, perm_codes in _ROLE_PERMISSION_MAP.items():
            role = role_by_code.get(role_code)
            if role is None:
                found = await self._repo.find_role_by_code(code=role_code)
                if isinstance(found, Failure):
                    return found
                role = found.unwrap()
            if role is None:
                continue
            for perm_code in perm_codes:
                perm = perm_by_code.get(perm_code)
                if perm is None:
                    found_p = await self._repo.find_permission_by_code(code=perm_code)
                    if isinstance(found_p, Failure):
                        return found_p
                    perm = found_p.unwrap()
                if perm is None:
                    continue
                link_got = await self._repo.get_role_permission(
                    role_id=role.id, permission_id=perm.id
                )
                if isinstance(link_got, Failure):
                    return link_got
                if link_got.unwrap() is not None:
                    continue
                link = RolePermissionRecord(
                    role_id=role.id,
                    permission_id=perm.id,
                    role_code=role.code,
                    permission_code=perm.code,
                    created_at=now,
                    updated_at=now,
                )
                put_link = await self._repo.put_role_permission(link)
                if isinstance(put_link, Failure):
                    return put_link

        return Success(None)

    async def assign_system_admin_to_user(self, *, user_id: str) -> Result[None, AppError]:
        """Assign the bootstrap ``system_admin`` role to ``user_id`` (idempotent)."""
        role = await self._repo.find_role_by_code(code=ROLE_SYSTEM_ADMIN_CODE)
        if isinstance(role, Failure):
            return role
        role_rec = role.unwrap()
        if role_rec is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="system_admin role is not seeded.",
                    detail=None,
                ),
            )
        out = await self.assign_role_to_user(
            iam_pb2.AssignRoleToUserRequest(user_id=user_id, role_id=role_rec.id),
        )
        if isinstance(out, Failure):
            return out
        return Success(None)

    async def build_user_auth_context(
        self, user_id: str
    ) -> Result[iam_pb2.UserAuthContext, AppError]:
        """Resolve role codes and permission grants for ``user_id``."""
        uid = user_id.strip()
        if not uid:
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="user_id is required.", detail=None),
            )

        assignments = await self._repo.list_roles_for_user(user_id=uid)
        if isinstance(assignments, Failure):
            return assignments

        role_codes: list[str] = []
        grants: list[tuple[str, str]] = []
        seen_perm: set[str] = set()

        for assignment in assignments.unwrap():
            role_code = assignment.role_code.strip()
            role_id = assignment.role_id
            if not role_code:
                role_got = await self._repo.roles.get_by_id(item_id=role_id, include_deleted=False)
                if isinstance(role_got, Failure):
                    return role_got
                role_rec = role_got.unwrap()
                if role_rec is None:
                    continue
                role_code = role_rec.code
            if role_code and role_code not in role_codes:
                role_codes.append(role_code)

            links = await self._repo.list_permissions_for_role(role_id=role_id)
            if isinstance(links, Failure):
                return links
            for link in links.unwrap():
                perm_code = link.permission_code.strip()
                if not perm_code:
                    perm_got = await self._repo.permissions.get_by_id(
                        item_id=link.permission_id,
                        include_deleted=False,
                    )
                    if isinstance(perm_got, Failure):
                        return perm_got
                    perm_rec = perm_got.unwrap()
                    if perm_rec is None:
                        continue
                    perm_code = perm_rec.code
                if perm_code in seen_perm:
                    continue
                seen_perm.add(perm_code)
                grants.append((perm_code, role_code))

        role_codes.sort()
        auth_json = _stable_auth_json(user_id=uid, role_codes=role_codes, grants=grants)
        pb_grants = [
            iam_pb2.PermissionGrant(permission_code=p, role_code=r) for p, r in sorted(grants)
        ]
        return Success(
            iam_pb2.UserAuthContext(
                user_id=uid,
                role_codes=role_codes,
                permission_grants=pb_grants,
                auth_json=auth_json,
            ),
        )

    def check_permission(
        self,
        user_auth_context: iam_pb2.UserAuthContext,
        permission_code: str,
    ) -> bool:
        """Return whether ``permission_code`` is granted in ``user_auth_context``."""
        want = _normalize_code(permission_code)
        if not want:
            return False
        for grant in user_auth_context.permission_grants:
            if _normalize_code(grant.permission_code) == want:
                return True
        return False

    async def list_roles(
        self, request: iam_pb2.ListRolesRequest
    ) -> Result[iam_pb2.ListRolesReply, AppError]:
        page = await self._repo.list_roles_page(
            include_deleted=request.include_deleted,
            page_size=_clamp_page_size(request.page_size),
            page_token=request.page_token,
        )
        if isinstance(page, Failure):
            return page
        rows, next_token = page.unwrap()
        return Success(
            iam_pb2.ListRolesReply(
                items=[role_to_pb(r) for r in rows],
                next_page_token=next_token,
            ),
        )

    async def create_role(
        self, request: iam_pb2.CreateRoleRequest
    ) -> Result[iam_pb2.Role, AppError]:
        code_out = _validate_code(request.code)
        if isinstance(code_out, Failure):
            return code_out
        code = code_out.unwrap()
        dup = await self._repo.find_role_by_code(code=code)
        if isinstance(dup, Failure):
            return dup
        if dup.unwrap() is not None:
            return Failure(
                AppError(
                    code=ErrorCodes.CONFLICT,
                    message="A role with this code already exists.",
                    detail=code,
                ),
            )
        now = utc_now_iso_z()
        rec = RoleRecord(
            id=str(uuid4()),
            created_at=now,
            updated_at=now,
            deleted_at="",
            is_deleted=False,
            enabled=request.enabled,
            code=code,
            display_name=request.display_name.strip() or code,
            data_json=request.data_json or "{}",
        )
        put = await self._repo.roles.put(rec)
        if isinstance(put, Failure):
            return put
        return Success(role_to_pb(rec))

    async def list_permissions(
        self,
        request: iam_pb2.ListPermissionsRequest,
    ) -> Result[iam_pb2.ListPermissionsReply, AppError]:
        page = await self._repo.list_permissions_page(
            include_deleted=request.include_deleted,
            page_size=_clamp_page_size(request.page_size),
            page_token=request.page_token,
        )
        if isinstance(page, Failure):
            return page
        rows, next_token = page.unwrap()
        return Success(
            iam_pb2.ListPermissionsReply(
                items=[permission_to_pb(r) for r in rows],
                next_page_token=next_token,
            ),
        )

    async def create_permission(
        self,
        request: iam_pb2.CreatePermissionRequest,
    ) -> Result[iam_pb2.Permission, AppError]:
        code_out = _validate_code(request.code)
        if isinstance(code_out, Failure):
            return code_out
        code = code_out.unwrap()
        dup = await self._repo.find_permission_by_code(code=code)
        if isinstance(dup, Failure):
            return dup
        if dup.unwrap() is not None:
            return Failure(
                AppError(
                    code=ErrorCodes.CONFLICT,
                    message="A permission with this code already exists.",
                    detail=code,
                ),
            )
        now = utc_now_iso_z()
        rec = PermissionRecord(
            id=str(uuid4()),
            created_at=now,
            updated_at=now,
            deleted_at="",
            is_deleted=False,
            enabled=request.enabled,
            code=code,
            display_name=request.display_name.strip() or code,
            data_json=request.data_json or "{}",
        )
        put = await self._repo.permissions.put(rec)
        if isinstance(put, Failure):
            return put
        return Success(permission_to_pb(rec))

    async def attach_permission_to_role(
        self,
        request: iam_pb2.AttachPermissionToRoleRequest,
    ) -> Result[iam_pb2.RolePermission, AppError]:
        role_id = request.role_id.strip()
        permission_id = request.permission_id.strip()
        if not role_id or not permission_id:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="role_id and permission_id are required.",
                    detail=None,
                ),
            )
        role_got = await self._repo.roles.get_by_id(item_id=role_id, include_deleted=False)
        if isinstance(role_got, Failure):
            return role_got
        role = role_got.unwrap()
        if role is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="role_id not found.", detail=role_id)
            )
        perm_got = await self._repo.permissions.get_by_id(
            item_id=permission_id, include_deleted=False
        )
        if isinstance(perm_got, Failure):
            return perm_got
        perm = perm_got.unwrap()
        if perm is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="permission_id not found.",
                    detail=permission_id,
                ),
            )
        existing = await self._repo.get_role_permission(
            role_id=role_id, permission_id=permission_id
        )
        if isinstance(existing, Failure):
            return existing
        if existing.unwrap() is not None:
            return Failure(
                AppError(
                    code=ErrorCodes.CONFLICT,
                    message="Permission is already attached to this role.",
                    detail=None,
                ),
            )
        now = utc_now_iso_z()
        link = RolePermissionRecord(
            role_id=role_id,
            permission_id=permission_id,
            role_code=role.code,
            permission_code=perm.code,
            created_at=now,
            updated_at=now,
        )
        put = await self._repo.put_role_permission(link)
        if isinstance(put, Failure):
            return put
        return Success(role_permission_to_pb(link))

    async def assign_role_to_user(
        self,
        request: iam_pb2.AssignRoleToUserRequest,
    ) -> Result[iam_pb2.UserRoleAssignment, AppError]:
        user_id = request.user_id.strip()
        role_id = request.role_id.strip()
        if not user_id or not role_id:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="user_id and role_id are required.",
                    detail=None,
                ),
            )
        role_got = await self._repo.roles.get_by_id(item_id=role_id, include_deleted=False)
        if isinstance(role_got, Failure):
            return role_got
        role = role_got.unwrap()
        if role is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="role_id not found.", detail=role_id)
            )
        existing = await self._repo.get_user_role_assignment(user_id=user_id, role_id=role_id)
        if isinstance(existing, Failure):
            return existing
        if existing.unwrap() is not None:
            return Success(user_role_assignment_to_pb(existing.unwrap()))  # type: ignore[arg-type]
        now = utc_now_iso_z()
        assignment = UserRoleAssignmentRecord(
            user_id=user_id,
            role_id=role_id,
            role_code=role.code,
            created_at=now,
            updated_at=now,
        )
        put = await self._repo.put_user_role_assignment(assignment)
        if isinstance(put, Failure):
            return put
        return Success(user_role_assignment_to_pb(assignment))

    async def revoke_role_from_user(
        self,
        request: iam_pb2.RevokeRoleFromUserRequest,
    ) -> Result[iam_pb2.RevokeRoleFromUserReply, AppError]:
        user_id = request.user_id.strip()
        role_id = request.role_id.strip()
        if not user_id or not role_id:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="user_id and role_id are required.",
                    detail=None,
                ),
            )
        deleted = await self._repo.delete_user_role_assignment(user_id=user_id, role_id=role_id)
        if isinstance(deleted, Failure):
            return deleted
        return Success(iam_pb2.RevokeRoleFromUserReply())

    async def list_user_roles(
        self,
        request: iam_pb2.ListUserRolesRequest,
    ) -> Result[iam_pb2.ListUserRolesReply, AppError]:
        user_id = request.user_id.strip()
        if not user_id:
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="user_id is required.", detail=None),
            )
        rows = await self._repo.list_roles_for_user(user_id=user_id)
        if isinstance(rows, Failure):
            return rows
        return Success(
            iam_pb2.ListUserRolesReply(
                items=[user_role_assignment_to_pb(r) for r in rows.unwrap()],
            ),
        )

    async def check_user_auth_and_permissions(
        self,
        request: iam_pb2.CheckUserAuthAndPermissionsRequest,
    ) -> Result[iam_pb2.CheckUserAuthAndPermissionsReply, AppError]:
        ctx: iam_pb2.UserAuthContext
        if request.user_id.strip():
            built = await self.build_user_auth_context(request.user_id)
            if isinstance(built, Failure):
                return built
            ctx = built.unwrap()
        elif request.HasField("user_auth_context") and request.user_auth_context.user_id.strip():
            ctx = request.user_auth_context
        else:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="user_id or user_auth_context.user_id is required.",
                    detail=None,
                ),
            )

        codes = [_normalize_code(c) for c in request.permission_codes if c.strip()]
        missing: list[str] = []
        for code in codes:
            if not self.check_permission(ctx, code):
                missing.append(code)

        if request.require_all:
            authorized = len(missing) == 0
        else:
            authorized = len(codes) == 0 or len(missing) < len(codes)

        return Success(
            iam_pb2.CheckUserAuthAndPermissionsReply(
                user_auth_context=ctx,
                authorized=authorized,
                missing_permission_codes=missing,
            ),
        )

    async def list_service_permissions(
        self,
        request: iam_pb2.ListServicePermissionsRequest,
    ) -> Result[iam_pb2.ListServicePermissionsReply, AppError]:
        service_code = _normalize_code(request.service_code)
        if not service_code:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION, message="service_code is required.", detail=None
                ),
            )
        rows = await self._repo.list_service_permissions(service_code=service_code)
        if isinstance(rows, Failure):
            return rows
        return Success(
            iam_pb2.ListServicePermissionsReply(
                items=[service_permission_to_pb(r) for r in rows.unwrap()],
            ),
        )

    async def register_service_permission(
        self,
        request: iam_pb2.RegisterServicePermissionRequest,
    ) -> Result[iam_pb2.ServicePermission, AppError]:
        service_out = _validate_code(request.service_code)
        if isinstance(service_out, Failure):
            return service_out
        perm_out = _validate_code(request.permission_code)
        if isinstance(perm_out, Failure):
            return perm_out
        service_code = service_out.unwrap()
        permission_code = perm_out.unwrap()
        now = utc_now_iso_z()
        rec = ServicePermissionRecord(
            service_code=service_code,
            permission_code=permission_code,
            created_at=now,
            updated_at=now,
        )
        put = await self._repo.put_service_permission(rec)
        if isinstance(put, Failure):
            return put
        return Success(service_permission_to_pb(rec))

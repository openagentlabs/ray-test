"""Map Dynamo domain records to protobuf messages."""

from __future__ import annotations

from iam.v1 import iam_pb2
from iam_service.database.models.records import (
    InviteRecord,
    LoginRecord,
    LoginTypeRecord,
    PermissionRecord,
    RolePermissionRecord,
    RoleRecord,
    ServicePermissionRecord,
    SessionRecord,
    SkillListRecord,
    SkillRecord,
    UserRecord,
    UserRoleAssignmentRecord,
    UserSkillRecord,
    UserTypeRecord,
)
from iam_service.grpc_transport.proto_time import timestamp_from_iso


def user_to_pb(rec: UserRecord) -> iam_pb2.User:
    """Full user row (credentials live on ``LoginRecord``, not ``UserRecord``)."""
    return iam_pb2.User(
        id=rec.id,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
        deleted_at=timestamp_from_iso(rec.deleted_at),
        is_deleted=rec.is_deleted,
        enabled=rec.enabled,
        first_name=rec.first_name,
        last_name=rec.last_name,
        account_id=rec.account_id,
        notes=rec.notes,
        timezone=rec.timezone,
        location=rec.location,
        skill_list_id=rec.skill_list_id,
        user_type_id=rec.user_type_id,
    )


def user_to_short_pb(rec: UserRecord) -> iam_pb2.UserShort:
    """Profile-card projection (no notes/location/timezone/skill list)."""
    return iam_pb2.UserShort(
        id=rec.id,
        first_name=rec.first_name,
        last_name=rec.last_name,
        enabled=rec.enabled,
        account_id=rec.account_id,
        user_type_id=rec.user_type_id,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
    )


def user_type_to_pb(rec: UserTypeRecord) -> iam_pb2.UserType:
    return iam_pb2.UserType(
        id=rec.id,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
        deleted_at=timestamp_from_iso(rec.deleted_at),
        is_deleted=rec.is_deleted,
        enabled=rec.enabled,
        code=rec.code,
        display_name=rec.display_name,
        data_json=rec.data_json,
    )


def login_type_to_pb(rec: LoginTypeRecord) -> iam_pb2.LoginType:
    return iam_pb2.LoginType(
        id=rec.id,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
        deleted_at=timestamp_from_iso(rec.deleted_at),
        is_deleted=rec.is_deleted,
        enabled=rec.enabled,
        code=rec.code,
        display_name=rec.display_name,
        data_json=rec.data_json,
    )


def skill_list_to_pb(rec: SkillListRecord) -> iam_pb2.SkillList:
    return iam_pb2.SkillList(
        id=rec.id,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
        deleted_at=timestamp_from_iso(rec.deleted_at),
        is_deleted=rec.is_deleted,
        enabled=rec.enabled,
        name=rec.name,
        data_json=rec.data_json,
    )


def skill_to_pb(rec: SkillRecord) -> iam_pb2.Skill:
    return iam_pb2.Skill(
        id=rec.id,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
        deleted_at=timestamp_from_iso(rec.deleted_at),
        is_deleted=rec.is_deleted,
        enabled=rec.enabled,
        code=rec.code,
        display_name=rec.display_name,
        data_json=rec.data_json,
    )


def user_skill_to_pb(rec: UserSkillRecord) -> iam_pb2.UserSkill:
    return iam_pb2.UserSkill(
        id=rec.id,
        user_id=rec.user_id,
        skill_id=rec.skill_id,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
        deleted_at=timestamp_from_iso(rec.deleted_at),
        is_deleted=rec.is_deleted,
    )


def login_to_pb(rec: LoginRecord, *, include_password: bool = True) -> iam_pb2.Login:
    return iam_pb2.Login(
        id=rec.id,
        user_id=rec.user_id,
        login_type_id=rec.login_type_id,
        name=rec.name,
        description=rec.description,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
        deleted_at=timestamp_from_iso(rec.deleted_at),
        is_deleted=rec.is_deleted,
        enabled=rec.enabled,
        data_json=rec.data_json,
        password=rec.password if include_password else "",
    )


def session_to_pb(
    rec: SessionRecord,
    *,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    user_type_id: str = "",
    user_type_display_name: str = "",
    user_auth_context: iam_pb2.UserAuthContext | None = None,
) -> iam_pb2.Session:
    session = iam_pb2.Session(
        id=rec.id,
        user_id=rec.user_id,
        login_id=rec.login_id,
        created_at=timestamp_from_iso(rec.created_at),
        expires_at=timestamp_from_iso(rec.expires_at),
        deleted_at=timestamp_from_iso(rec.deleted_at),
        is_revoked=rec.is_revoked,
        first_name=first_name,
        last_name=last_name,
        email=email,
        user_type_id=user_type_id,
        user_type_display_name=user_type_display_name,
    )
    if user_auth_context is not None:
        session.user_auth_context.CopyFrom(user_auth_context)
    return session


def user_auth_context_to_pb(ctx: iam_pb2.UserAuthContext) -> iam_pb2.UserAuthContext:
    return ctx


def role_to_pb(rec: RoleRecord) -> iam_pb2.Role:
    return iam_pb2.Role(
        id=rec.id,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
        deleted_at=timestamp_from_iso(rec.deleted_at),
        is_deleted=rec.is_deleted,
        enabled=rec.enabled,
        code=rec.code,
        display_name=rec.display_name,
        data_json=rec.data_json,
    )


def permission_to_pb(rec: PermissionRecord) -> iam_pb2.Permission:
    return iam_pb2.Permission(
        id=rec.id,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
        deleted_at=timestamp_from_iso(rec.deleted_at),
        is_deleted=rec.is_deleted,
        enabled=rec.enabled,
        code=rec.code,
        display_name=rec.display_name,
        data_json=rec.data_json,
    )


def role_permission_to_pb(rec: RolePermissionRecord) -> iam_pb2.RolePermission:
    return iam_pb2.RolePermission(
        role_id=rec.role_id,
        permission_id=rec.permission_id,
        role_code=rec.role_code,
        permission_code=rec.permission_code,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
    )


def user_role_assignment_to_pb(rec: UserRoleAssignmentRecord) -> iam_pb2.UserRoleAssignment:
    return iam_pb2.UserRoleAssignment(
        user_id=rec.user_id,
        role_id=rec.role_id,
        role_code=rec.role_code,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
    )


def service_permission_to_pb(rec: ServicePermissionRecord) -> iam_pb2.ServicePermission:
    return iam_pb2.ServicePermission(
        service_code=rec.service_code,
        permission_code=rec.permission_code,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
    )


def invite_to_pb(rec: InviteRecord) -> iam_pb2.Invite:
    return iam_pb2.Invite(
        id=rec.id,
        created_at=timestamp_from_iso(rec.created_at),
        updated_at=timestamp_from_iso(rec.updated_at),
        deleted_at=timestamp_from_iso(rec.deleted_at),
        is_deleted=rec.is_deleted,
        code=rec.code,
        expires_at=timestamp_from_iso(rec.expires_at),
        redeemed=rec.redeemed,
        account_id=rec.account_id,
        user_type_id=rec.user_type_id,
        login_type_id=rec.login_type_id,
        recipient_email=rec.recipient_email,
    )

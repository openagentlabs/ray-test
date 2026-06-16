"""Persist and project deployment-admin bootstrap rows (dedicated DynamoDB table)."""

from __future__ import annotations

from uuid import uuid4

from iam.v1 import iam_pb2
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.database.models.records import (
    DeploymentAdminRecord,
    LoginRecord,
    LoginTypeRecord,
    SkillListRecord,
    SkillRecord,
    UserRecord,
    UserTypeRecord,
)
from iam_service.database.repositories.deployment_admin_repository import DeploymentAdminRepository
from iam_service.database.repositories.item_repository import ItemRepository
from iam_service.grpc_transport.iam_converters import login_to_pb, user_to_pb
from iam_service.grpc_transport.proto_time import utc_now_iso_z
from iam_service.services.initial_tenant_bootstrap import (
    INITIAL_ACCOUNT_ID,
    INITIAL_LOGIN_TYPE_ID,
    INITIAL_SKILL_LIST_ID,
    INITIAL_USER_TYPE_ID,
    put_initial_catalog,
)
from iam_service.services.rbac_service import RbacService


def deployment_admin_to_user_record(rec: DeploymentAdminRecord) -> UserRecord:
    """Synthetic user row for sign-in / RPC replies (not stored in ``users`` table)."""
    return UserRecord(
        id=rec.id,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        deleted_at=rec.deleted_at,
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


def deployment_admin_to_login_record(rec: DeploymentAdminRecord) -> LoginRecord:
    """Synthetic login row for sign-in (credentials live on deployment-admin table)."""
    return LoginRecord(
        id=rec.id,
        user_id=rec.id,
        login_type_id=rec.login_type_id,
        name=rec.email,
        description="Deployment admin (bootstrap table).",
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        deleted_at=rec.deleted_at,
        is_deleted=rec.is_deleted,
        enabled=rec.enabled,
        data_json="",
        password=rec.password,
    )


def deployment_admin_to_pb_pair(
    rec: DeploymentAdminRecord,
) -> tuple[iam_pb2.User, iam_pb2.Login]:
    user_pb = user_to_pb(deployment_admin_to_user_record(rec))
    login_pb = login_to_pb(deployment_admin_to_login_record(rec))
    login_pb.password = ""
    return user_pb, login_pb


async def upsert_deployment_admin(
    *,
    deployment_admins: DeploymentAdminRepository,
    user_types: ItemRepository[UserTypeRecord],
    login_types: ItemRepository[LoginTypeRecord],
    skill_lists: ItemRepository[SkillListRecord],
    skills: ItemRepository[SkillRecord],
    rbac: RbacService,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    enabled: bool,
    notes: str,
    timezone: str,
    location: str,
) -> Result[tuple[iam_pb2.User, iam_pb2.Login], AppError]:
    """Ensure catalog exists, then write the sole deployment-admin bootstrap row."""
    first = first_name.strip()
    last = last_name.strip()
    email_norm = email.strip()
    if not first or not last:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="first_name and last_name are required.",
                detail=None,
            ),
        )
    if not email_norm or "@" not in email_norm or "." not in email_norm.rsplit("@", maxsplit=1)[-1]:
        return Failure(
            AppError(code=ErrorCodes.VALIDATION, message="A valid email is required.", detail=None)
        )
    if not password:
        return Failure(
            AppError(code=ErrorCodes.VALIDATION, message="password is required.", detail=None)
        )

    seeded = await put_initial_catalog(
        user_types=user_types,
        login_types=login_types,
        skill_lists=skill_lists,
        skills=skills,
    )
    if isinstance(seeded, Failure):
        return seeded

    rbac_boot = await rbac.bootstrap_default_rbac()
    if isinstance(rbac_boot, Failure):
        return rbac_boot

    now = utc_now_iso_z()
    admin_id = str(uuid4())
    record = DeploymentAdminRecord(
        id=admin_id,
        email=email_norm,
        password=password,
        first_name=first,
        last_name=last,
        notes=notes.strip(),
        timezone=timezone.strip() or "UTC",
        location=location.strip(),
        account_id=INITIAL_ACCOUNT_ID,
        user_type_id=INITIAL_USER_TYPE_ID,
        login_type_id=INITIAL_LOGIN_TYPE_ID,
        skill_list_id=INITIAL_SKILL_LIST_ID,
        created_at=now,
        updated_at=now,
        deleted_at="",
        is_deleted=False,
        enabled=enabled,
    )
    put = await deployment_admins.put(record)
    if isinstance(put, Failure):
        return put

    assigned = await rbac.assign_system_admin_to_user(user_id=admin_id)
    if isinstance(assigned, Failure):
        return assigned

    return Success(deployment_admin_to_pb_pair(record))

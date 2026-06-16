"""Shared domain / persistence models for DynamoDB items."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UserRecord(BaseModel):
    """User item (PK `id`). GSI `account-users`: `account_id` + `id`."""

    # Ignore legacy ``password`` attributes still present on older user rows.
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    enabled: bool = Field(default=True)
    first_name: str = Field(default="")
    last_name: str = Field(default="")
    account_id: str = Field(default="")
    notes: str = Field(default="")
    timezone: str = Field(default="")
    location: str = Field(default="")
    skill_list_id: str = Field(default="")
    user_type_id: str = Field(default="")


class UserTypeRecord(BaseModel):
    """Catalog row for user roles (admin, architect, solution owner, …)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    enabled: bool = Field(default=True)
    code: str = Field(default="")
    display_name: str = Field(default="")
    data_json: str = Field(default="")


class LoginTypeRecord(BaseModel):
    """Catalog row describing a class of login identifiers."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    enabled: bool = Field(default=True)
    code: str = Field(default="")
    display_name: str = Field(default="")
    data_json: str = Field(default="")


class SkillListRecord(BaseModel):
    """Skill list document referenced by ``UserRecord.skill_list_id``."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    enabled: bool = Field(default=True)
    name: str = Field(default="")
    data_json: str = Field(default="")


class SkillRecord(BaseModel):
    """Catalog row for assignable skills (separate from legacy ``SkillList``)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    enabled: bool = Field(default=True)
    code: str = Field(default="")
    display_name: str = Field(default="")
    data_json: str = Field(default="")


class UserSkillRecord(BaseModel):
    """Link row: user ↔ skill. GSI ``user-skills``: ``user_id`` + ``id``."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    skill_id: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)


class LoginRecord(BaseModel):
    """Login row linked to a user; GSI ``user-logins`` on ``user_id`` + ``id``."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    login_type_id: str = Field(default="")
    name: str = Field(default="")
    description: str = Field(default="")
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    enabled: bool = Field(default=True)
    data_json: str = Field(default="")
    password: str = Field(default="")


class DeploymentAdminRecord(BaseModel):
    """Bootstrap admin for local dev / ``ResetDatabase`` (PK ``id``; GSI on ``email``)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    password: str = Field(default="")
    first_name: str = Field(default="")
    last_name: str = Field(default="")
    notes: str = Field(default="")
    timezone: str = Field(default="")
    location: str = Field(default="")
    account_id: str = Field(default="")
    user_type_id: str = Field(default="")
    login_type_id: str = Field(default="")
    skill_list_id: str = Field(default="")
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    enabled: bool = Field(default=True)


class InviteRecord(BaseModel):
    """Time-limited invite code (PK ``id``; GSI ``invite-codes`` on ``code``)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    code: str = Field(..., min_length=1)
    expires_at: str = Field(..., min_length=1)
    redeemed: bool = Field(default=False)
    account_id: str = Field(..., min_length=1)
    user_type_id: str = Field(..., min_length=1)
    login_type_id: str = Field(..., min_length=1)
    recipient_email: str = Field(default="")


class SessionRecord(BaseModel):
    """Authenticated user session (PK ``id``).

    Created by ``SignIn`` and revoked via soft delete. ``expires_at`` is an
    advisory absolute ISO-8601 instant; the application is responsible for
    rejecting expired or revoked sessions on subsequent lookups.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    login_id: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    expires_at: str = Field(default="")
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    is_revoked: bool = Field(default=False)


class RoleRecord(BaseModel):
    """RBAC role catalog row (PK ``id``; GSI ``role-codes`` on ``code``)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    enabled: bool = Field(default=True)
    code: str = Field(..., min_length=1)
    display_name: str = Field(default="")
    data_json: str = Field(default="")


class PermissionRecord(BaseModel):
    """RBAC permission catalog row (PK ``id``; GSI ``permission-codes`` on ``code``)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    enabled: bool = Field(default=True)
    code: str = Field(..., min_length=1)
    display_name: str = Field(default="")
    data_json: str = Field(default="")


class RolePermissionRecord(BaseModel):
    """Role ↔ permission link (PK ``role_id``, SK ``permission_id``)."""

    model_config = ConfigDict(extra="forbid")

    role_id: str = Field(..., min_length=1)
    permission_id: str = Field(..., min_length=1)
    role_code: str = Field(default="")
    permission_code: str = Field(default="")
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)


class UserRoleAssignmentRecord(BaseModel):
    """User ↔ role assignment (PK ``user_id``, SK ``role_id``)."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., min_length=1)
    role_id: str = Field(..., min_length=1)
    role_code: str = Field(default="")
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)


class ServicePermissionRecord(BaseModel):
    """Service-scoped permission registration (PK ``service_code``, SK ``permission_code``)."""

    model_config = ConfigDict(extra="forbid")

    service_code: str = Field(..., min_length=1)
    permission_code: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)


class ServiceFunctionRegistryRecord(BaseModel):
    """Maps a compressed service id to service name and function catalog JSON."""

    model_config = ConfigDict(extra="forbid")

    service_id: str = Field(..., min_length=5, max_length=12)
    service_name: str = Field(..., min_length=1)
    functions_json: str = Field(default="[]")
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)


class UserPermissionRecord(BaseModel):
    """User-specific service/function grants (PK ``user_id``, SK ``service_id``)."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., min_length=1)
    service_id: str = Field(..., min_length=5, max_length=12)
    functions_json: str = Field(default="[]")
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)


class AuthSessionRecord(BaseModel):
    """Persisted auth session backing issued JWT refresh tokens."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    idp_provider_id: str = Field(default="")
    idp_subject: str = Field(default="")
    refresh_token_hash: str = Field(default="")
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    expires_at: str = Field(default="")
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    is_revoked: bool = Field(default=False)

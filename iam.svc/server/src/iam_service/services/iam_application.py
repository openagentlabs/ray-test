"""Domain orchestration for IAM RPCs (DynamoDB repositories + validation)."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.invite_codes import (
    generate_random_invite_code,
)
from iam_service.core.results import Failure, Result, Success
from iam_service.database.dynamo_admin import DynamoDatabaseAdmin
from iam_service.database.models.records import (
    DeploymentAdminRecord,
    InviteRecord,
    LoginRecord,
    LoginTypeRecord,
    SessionRecord,
    SkillListRecord,
    SkillRecord,
    UserRecord,
    UserSkillRecord,
    UserTypeRecord,
)
from iam_service.database.repositories.deployment_admin_repository import DeploymentAdminRepository
from iam_service.database.repositories.invite_repository import InviteRepository
from iam_service.database.repositories.item_repository import ItemRepository
from iam_service.database.repositories.login_repository import LoginRepository
from iam_service.database.repositories.user_repository import UserRepository
from iam_service.database.repositories.user_skill_repository import UserSkillRepository
from iam_service.grpc_transport.iam_converters import (
    invite_to_pb,
    login_to_pb,
    login_type_to_pb,
    session_to_pb,
    skill_list_to_pb,
    skill_to_pb,
    user_skill_to_pb,
    user_to_pb,
    user_to_short_pb,
    user_type_to_pb,
)
from iam_service.grpc_transport.proto_time import utc_now_iso_z
from iam_service.services.deployment_admin_bootstrap import (
    auto_bootstrap_admin_on_empty_enabled,
    deployment_admin_bootstrap_fields,
)
from iam_service.services.deployment_admin_store import (
    deployment_admin_to_login_record,
    deployment_admin_to_user_record,
    upsert_deployment_admin,
)
from iam_service.services.initial_tenant_bootstrap import (
    INITIAL_ACCOUNT_ID,
    INITIAL_LOGIN_TYPE_ID,
    INITIAL_SEED_SKILL_IDS,
    INITIAL_SKILL_LIST_ID,
    INITIAL_USER_TYPE_ID,
    put_initial_catalog,
)
from iam_service.services.rbac_service import RbacService
from iam_service.validation.reset_database import validate_reset_database_request

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_SESSION_TTL = timedelta(hours=12)


def _expiry_iso_z(now_iso: str, ttl: timedelta) -> str:
    """Compute an ISO-8601 ``Z`` instant ``ttl`` after ``now_iso``."""
    base = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    moment = (base.astimezone(UTC) + ttl).replace(microsecond=0)
    return moment.isoformat().replace("+00:00", "Z")


def _is_uuid(value: str) -> bool:
    return bool(_UUID_RE.match(value.strip()))


def _invite_expired(*, expires_at_iso: str, now_iso: str) -> bool:
    if not expires_at_iso.strip():
        return False
    deadline = datetime.fromisoformat(expires_at_iso.replace("Z", "+00:00"))
    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now >= deadline.astimezone(UTC)


def _clamp_page_size(raw: int) -> int:
    if raw <= 0:
        return 50
    return min(raw, 200)


async def _collect_all_user_skills_for_user(
    user_skills: UserSkillRepository,
    *,
    user_id: str,
    include_deleted: bool,
) -> Result[list[UserSkillRecord], AppError]:
    """Paginate through every ``UserSkill`` row for ``user_id``."""
    out: list[UserSkillRecord] = []
    page_token = ""
    while True:
        batch = await user_skills.query_by_user(
            user_id=user_id,
            include_deleted=include_deleted,
            page_size=200,
            page_token=page_token,
        )
        if isinstance(batch, Failure):
            return batch
        rows, page_token = batch.unwrap()
        out.extend(rows)
        if not page_token:
            break
    return Success(out)


async def _collect_logins_for_user(
    logins: LoginRepository,
    *,
    user_id: str,
    include_deleted: bool,
) -> Result[list[LoginRecord], AppError]:
    """Paginate through every ``Login`` row for ``user_id``."""
    out: list[LoginRecord] = []
    page_token = ""
    while True:
        batch = await logins.query_by_user(
            user_id=user_id,
            include_deleted=include_deleted,
            page_size=200,
            page_token=page_token,
        )
        if isinstance(batch, Failure):
            return batch
        rows, page_token = batch.unwrap()
        out.extend(rows)
        if not page_token:
            break
    return Success(out)


def _pick_primary_login(rows: Sequence[LoginRecord]) -> LoginRecord | None:
    """Choose the best active login for credential display (email-style name preferred)."""
    active = [r for r in rows if not r.is_deleted and r.enabled]
    if not active:
        return None
    for login in active:
        if "@" in login.name:
            return login
    return active[0]


class IamServiceApplication:
    """Coordinates repositories, referential checks, and protobuf payloads."""

    __slots__ = (
        "_app",
        "_users",
        "_user_types",
        "_login_types",
        "_skill_lists",
        "_skills",
        "_user_skills",
        "_logins",
        "_sessions",
        "_invites",
        "_deployment_admins",
        "_rbac",
        "_admin",
    )

    def __init__(
        self,
        *,
        app: AppSection,
        users: UserRepository,
        user_types: ItemRepository[UserTypeRecord],
        login_types: ItemRepository[LoginTypeRecord],
        skill_lists: ItemRepository[SkillListRecord],
        skills: ItemRepository[SkillRecord],
        user_skills: UserSkillRepository,
        logins: LoginRepository,
        sessions: ItemRepository[SessionRecord],
        invites: InviteRepository,
        deployment_admins: DeploymentAdminRepository,
        rbac: RbacService,
        admin: DynamoDatabaseAdmin | None = None,
    ) -> None:
        self._app = app
        self._users = users
        self._user_types = user_types
        self._login_types = login_types
        self._skill_lists = skill_lists
        self._skills = skills
        self._user_skills = user_skills
        self._logins = logins
        self._sessions = sessions
        self._invites = invites
        self._deployment_admins = deployment_admins
        self._rbac = rbac
        self._admin = admin

    async def ping(self, request: iam_pb2.PingRequest) -> Result[iam_pb2.PingReply, AppError]:
        _ = request.client_name  # reserved for future client telemetry
        return Success(
            iam_pb2.PingReply(service_name=self._app.service_name, version=self._app.version),
        )

    async def echo(self, request: iam_pb2.EchoRequest) -> Result[iam_pb2.EchoReply, AppError]:
        return Success(iam_pb2.EchoReply(message=request.message))

    async def record_count(
        self, request: iam_pb2.RecordCountRequest
    ) -> Result[iam_pb2.RecordCountReply, AppError]:
        _ = request
        if self._admin is None:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Database admin is not configured on this process.",
                    detail=None,
                ),
            )
        counted = await self._admin.total_item_count()
        if isinstance(counted, Failure):
            return counted
        total = counted.unwrap()
        return Success(iam_pb2.RecordCountReply(total_records=total))

    async def check_if_new_deployment_can_create_admin(self) -> Result[None, AppError]:
        """When the deployment-admin table is empty, seed catalog and write bootstrap admin there."""
        if self._admin is None:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Database admin is not configured on this process.",
                    detail=None,
                ),
            )
        if not auto_bootstrap_admin_on_empty_enabled():
            logger.info(
                "deployment admin bootstrap skipped: IAM_AUTO_BOOTSTRAP_ADMIN_ON_EMPTY is false",
            )
            return Success(None)

        counted = await self._admin.count_logins()
        if isinstance(counted, Failure):
            return counted
        login_count = counted.unwrap()
        if login_count > 0:
            logger.info(
                "deployment admin bootstrap skipped: logins table has %s record(s)",
                login_count,
            )
            return Success(None)

        fields_out = deployment_admin_bootstrap_fields()
        if isinstance(fields_out, Failure):
            return fields_out
        fields = fields_out.unwrap()
        provisioned = await self._provision_initial_admin_user(
            first_name=fields.first_name,
            last_name=fields.last_name,
            email=fields.email,
            password=fields.password,
            enabled=True,
            notes="Initial deployment admin (IAM service bootstrap).",
            timezone="UTC",
            location="",
        )
        if isinstance(provisioned, Failure):
            return provisioned
        user_pb, _login_pb = provisioned.unwrap()
        logger.info(
            "deployment admin bootstrap created id=%s email_domain=%s",
            user_pb.id,
            fields.email.split("@", maxsplit=1)[-1] if "@" in fields.email else "unknown",
        )
        return Success(None)

    async def _provision_deployment_admin(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        enabled: bool,
        notes: str,
        timezone: str,
        location: str,
    ) -> Result[tuple[iam_pb2.User, iam_pb2.Login], AppError]:
        """Write bootstrap admin to the dedicated deployment-admin table (not users/logins)."""
        return await upsert_deployment_admin(
            deployment_admins=self._deployment_admins,
            user_types=self._user_types,
            login_types=self._login_types,
            skill_lists=self._skill_lists,
            skills=self._skills,
            rbac=self._rbac,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            enabled=enabled,
            notes=notes,
            timezone=timezone,
            location=location,
        )

    async def _provision_initial_admin_user(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        enabled: bool,
        notes: str,
        timezone: str,
        location: str,
    ) -> Result[tuple[iam_pb2.User, iam_pb2.Login], AppError]:
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
        if (
            not email_norm
            or "@" not in email_norm
            or "." not in email_norm.rsplit("@", maxsplit=1)[-1]
        ):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION, message="A valid email is required.", detail=None
                )
            )
        if not password:
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="password is required.", detail=None)
            )

        seeded = await put_initial_catalog(
            user_types=self._user_types,
            login_types=self._login_types,
            skill_lists=self._skill_lists,
            skills=self._skills,
        )
        if isinstance(seeded, Failure):
            return seeded

        rbac_boot = await self._rbac.bootstrap_default_rbac()
        if isinstance(rbac_boot, Failure):
            return rbac_boot

        create_user_req = iam_pb2.CreateUserRequest(
            first_name=first,
            last_name=last,
            account_id=INITIAL_ACCOUNT_ID,
            notes=notes,
            timezone=timezone,
            location=location,
            skill_list_id=INITIAL_SKILL_LIST_ID,
            user_type_id=INITIAL_USER_TYPE_ID,
            enabled=enabled,
        )
        create_user_req.skill_ids.extend(INITIAL_SEED_SKILL_IDS)
        user_out = await self.create_user(create_user_req)
        if isinstance(user_out, Failure):
            return user_out
        user_pb = user_out.unwrap()

        create_login_req = iam_pb2.CreateLoginRequest(
            user_id=user_pb.id,
            login_type_id=INITIAL_LOGIN_TYPE_ID,
            name=email_norm,
            description="",
            data_json="{}",
            enabled=True,
            password=password,
        )
        login_out = await self.create_login(create_login_req)
        if isinstance(login_out, Failure):
            _ = await self.soft_delete_user(iam_pb2.SoftDeleteUserRequest(id=user_pb.id))
            return login_out
        login_pb = login_out.unwrap()

        safe_login = iam_pb2.Login()
        safe_login.CopyFrom(login_pb)
        safe_login.password = ""

        assigned = await self._rbac.assign_system_admin_to_user(user_id=user_pb.id)
        if isinstance(assigned, Failure):
            return assigned

        return Success((user_pb, safe_login))

    async def ensure_initial_user(
        self,
        request: iam_pb2.EnsureInitialUserRequest,
    ) -> Result[iam_pb2.EnsureInitialUserReply, AppError]:
        if self._admin is None:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Database admin is not configured on this process.",
                    detail=None,
                ),
            )
        counted = await self._admin.total_item_count()
        if isinstance(counted, Failure):
            return counted
        if counted.unwrap() > 0:
            return Success(iam_pb2.EnsureInitialUserReply(skipped=True, created=False))

        provisioned = await self._provision_initial_admin_user(
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            password=request.password,
            enabled=request.enabled,
            notes=request.notes,
            timezone=request.timezone,
            location=request.location,
        )
        if isinstance(provisioned, Failure):
            return provisioned
        user_pb, safe_login = provisioned.unwrap()
        return Success(
            iam_pb2.EnsureInitialUserReply(
                skipped=False, created=True, user=user_pb, login=safe_login
            ),
        )

    async def reset_database(
        self,
        request: iam_pb2.ResetDatabaseRequest,
    ) -> Result[iam_pb2.ResetDatabaseReply, AppError]:
        """Wipe users/logins (and sessions/user-skills), then recreate admin user + login from the request."""
        validated_out = validate_reset_database_request(request)
        if isinstance(validated_out, Failure):
            return validated_out
        credentials, first_name, last_name = validated_out.unwrap()

        if self._admin is None:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Database admin is not configured on this process.",
                    detail=None,
                ),
            )

        counted = await self._admin.users_and_logins_item_count()
        if isinstance(counted, Failure):
            return counted
        total_before = counted.unwrap()

        wiped = await self._admin.wipe_users_and_logins()
        if isinstance(wiped, Failure):
            return wiped
        dep_wiped = await self._admin.wipe_deployment_admin_table()
        if isinstance(dep_wiped, Failure):
            return dep_wiped

        provisioned = await self._provision_initial_admin_user(
            first_name=first_name,
            last_name=last_name,
            email=credentials.username,
            password=credentials.password,
            enabled=True,
            notes="Deployment admin recreated after ResetDatabase.",
            timezone="UTC",
            location="",
        )
        if isinstance(provisioned, Failure):
            return provisioned
        user_pb, safe_login = provisioned.unwrap()
        if safe_login.user_id != user_pb.id:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="ResetDatabase created a login that does not reference the new user.",
                    detail=f"user_id={user_pb.id} login.user_id={safe_login.user_id}",
                ),
            )
        if safe_login.name.strip().lower() != credentials.username.strip().lower():
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="ResetDatabase login name does not match request username.",
                    detail=f"expected={credentials.username!r} actual={safe_login.name!r}",
                ),
            )
        logger.warning(
            "IAM ResetDatabase completed: removed %s user/login row(s); admin id=%s login=%s",
            total_before,
            user_pb.id,
            safe_login.name,
        )
        return Success(
            iam_pb2.ResetDatabaseReply(
                total_records_before_reset=total_before,
                user=user_pb,
                login=safe_login,
            ),
        )

    async def get_user_by_email(
        self, request: iam_pb2.GetUserByEmailRequest
    ) -> Result[iam_pb2.UserLong, AppError]:
        email = request.email.strip()
        if not email:
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="email is required.", detail=None)
            )
        if "@" not in email or "." not in email.rsplit("@", maxsplit=1)[-1]:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION, message="A valid email is required.", detail=None
                )
            )

        login_lookup = await self._logins.find_active_by_name(name=email)
        if isinstance(login_lookup, Failure):
            return login_lookup
        login = login_lookup.unwrap()
        if login is None:
            dep_lookup = await self._deployment_admins.find_active_by_email(email=email)
            if isinstance(dep_lookup, Failure):
                return dep_lookup
            dep = dep_lookup.unwrap()
            if dep is None:
                return Failure(
                    AppError(
                        code=ErrorCodes.NOT_FOUND,
                        message="No user found for that email.",
                        detail=email,
                    ),
                )
            return self._user_long_from_deployment_admin(dep)

        return await self.get_user_long(
            iam_pb2.GetUserRequest(id=login.user_id, include_deleted=False)
        )

    def _user_long_from_deployment_admin(
        self,
        dep: DeploymentAdminRecord,
    ) -> Result[iam_pb2.UserLong, AppError]:
        user = deployment_admin_to_user_record(dep)
        login = deployment_admin_to_login_record(dep)
        long = iam_pb2.UserLong(user=user_to_pb(user))
        detail = iam_pb2.LoginDetail(login=login_to_pb(login))
        detail.login.password = ""
        long.logins.append(detail)
        return Success(long)

    async def get_user_data(
        self,
        request: iam_pb2.GetUserDataRequest,
    ) -> Result[iam_pb2.GetUserDataReply, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._users.get_by_id(
            user_id=request.id, include_deleted=request.include_deleted
        )
        if isinstance(got, Failure):
            return got
        user = got.unwrap()
        if user is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="User not found.", detail=request.id)
            )

        logins_out = await _collect_logins_for_user(
            self._logins,
            user_id=user.id,
            include_deleted=request.include_deleted,
        )
        if isinstance(logins_out, Failure):
            return logins_out
        primary = _pick_primary_login(logins_out.unwrap())
        if primary is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="No active login found for user.",
                    detail=request.id,
                ),
            )
        return Success(
            iam_pb2.GetUserDataReply(
                user_id=user.id,
                username=primary.name,
                password=primary.password,
                login_id=primary.id,
            ),
        )

    async def _sync_user_skills_for_user(
        self, user_id: str, skill_ids: Sequence[str]
    ) -> Result[None, AppError]:
        """Replace active ``UserSkill`` rows for ``user_id`` with the given ``skill_ids`` set."""
        raw = [s.strip() for s in skill_ids if s.strip()]
        desired: list[str] = []
        seen: set[str] = set()
        for s in raw:
            if not _is_uuid(s):
                return Failure(
                    AppError(
                        code=ErrorCodes.VALIDATION,
                        message="Each skill_id must be a UUID.",
                        detail=s,
                    ),
                )
            if s in seen:
                continue
            seen.add(s)
            desired.append(s)

        for sid in desired:
            got = await self._skills.get_by_id(item_id=sid, include_deleted=False)
            if isinstance(got, Failure):
                return got
            if got.unwrap() is None:
                return Failure(
                    AppError(
                        code=ErrorCodes.NOT_FOUND,
                        message="skill_id does not reference an active skill.",
                        detail=sid,
                    ),
                )

        collected = await _collect_all_user_skills_for_user(
            self._user_skills,
            user_id=user_id,
            include_deleted=False,
        )
        if isinstance(collected, Failure):
            return collected
        active_rows = collected.unwrap()
        now = utc_now_iso_z()
        by_skill = {r.skill_id: r for r in active_rows}
        desired_set = set(desired)

        for sid, row in by_skill.items():
            if sid not in desired_set:
                deleted = await self._user_skills.soft_delete(link_id=row.id, now_iso=now)
                if isinstance(deleted, Failure):
                    return deleted

        for sid in desired:
            if sid not in by_skill:
                link = UserSkillRecord(
                    id=str(uuid4()),
                    user_id=user_id,
                    skill_id=sid,
                    created_at=now,
                    updated_at=now,
                    deleted_at="",
                    is_deleted=False,
                )
                put_l = await self._user_skills.put(link)
                if isinstance(put_l, Failure):
                    return put_l
        return Success(None)

    async def create_user(
        self, request: iam_pb2.CreateUserRequest
    ) -> Result[iam_pb2.User, AppError]:
        from iam_service.validation.create_user import validate_create_user_request

        validated_out = validate_create_user_request(request)
        if isinstance(validated_out, Failure):
            return validated_out
        validated = validated_out.unwrap()

        ut = await self._user_types.get_by_id(item_id=validated.user_type_id, include_deleted=False)
        if isinstance(ut, Failure):
            return ut
        if ut.unwrap() is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="user_type_id does not reference an active user type.",
                    detail=validated.user_type_id,
                ),
            )

        if validated.skill_list_id:
            sl = await self._skill_lists.get_by_id(
                item_id=validated.skill_list_id, include_deleted=False
            )
            if isinstance(sl, Failure):
                return sl
            if sl.unwrap() is None:
                return Failure(
                    AppError(
                        code=ErrorCodes.NOT_FOUND,
                        message="skill_list_id does not reference an active skill list.",
                        detail=validated.skill_list_id,
                    ),
                )

        for sid in validated.skill_ids:
            sk = await self._skills.get_by_id(item_id=sid, include_deleted=False)
            if isinstance(sk, Failure):
                return sk
            if sk.unwrap() is None:
                return Failure(
                    AppError(
                        code=ErrorCodes.NOT_FOUND,
                        message="skill_id does not reference an active skill.",
                        detail=sid,
                    ),
                )

        now = utc_now_iso_z()
        user_id = str(uuid4())
        rec = UserRecord(
            id=user_id,
            created_at=now,
            updated_at=now,
            deleted_at="",
            is_deleted=False,
            enabled=validated.enabled,
            first_name=validated.first_name,
            last_name=validated.last_name,
            account_id=validated.account_id,
            notes=validated.notes,
            timezone=validated.timezone,
            location=validated.location,
            skill_list_id=validated.skill_list_id,
            user_type_id=validated.user_type_id,
        )
        put = await self._users.put(rec)
        if isinstance(put, Failure):
            return put
        synced = await self._sync_user_skills_for_user(user_id, list(validated.skill_ids))
        if isinstance(synced, Failure):
            _ = await self.soft_delete_user(iam_pb2.SoftDeleteUserRequest(id=user_id))
            return synced
        return Success(user_to_pb(rec))

    async def get_user_short(
        self, request: iam_pb2.GetUserRequest
    ) -> Result[iam_pb2.UserShort, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._users.get_by_id(
            user_id=request.id, include_deleted=request.include_deleted
        )
        if isinstance(got, Failure):
            return got
        user = got.unwrap()
        if user is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="User not found.", detail=request.id)
            )
        return Success(user_to_short_pb(user))

    async def get_user_long(
        self, request: iam_pb2.GetUserRequest
    ) -> Result[iam_pb2.UserLong, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._users.get_by_id(
            user_id=request.id, include_deleted=request.include_deleted
        )
        if isinstance(got, Failure):
            return got
        user = got.unwrap()
        if user is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="User not found.", detail=request.id)
            )

        long = iam_pb2.UserLong(user=user_to_pb(user))

        if user.user_type_id.strip():
            ut = await self._user_types.get_by_id(item_id=user.user_type_id, include_deleted=True)
            if isinstance(ut, Failure):
                return ut
            ut_rec = ut.unwrap()
            if ut_rec is not None:
                long.user_type.CopyFrom(user_type_to_pb(ut_rec))

        if user.skill_list_id.strip():
            sl = await self._skill_lists.get_by_id(item_id=user.skill_list_id, include_deleted=True)
            if isinstance(sl, Failure):
                return sl
            sl_rec = sl.unwrap()
            if sl_rec is not None:
                long.skill_list.CopyFrom(skill_list_to_pb(sl_rec))

        page_token = ""
        while True:
            batch = await self._logins.query_by_user(
                user_id=user.id,
                include_deleted=request.include_deleted,
                page_size=100,
                page_token=page_token,
            )
            if isinstance(batch, Failure):
                return batch
            rows, page_token = batch.unwrap()
            for login in rows:
                detail = iam_pb2.LoginDetail(login=login_to_pb(login))
                if login.login_type_id.strip():
                    lt = await self._login_types.get_by_id(
                        item_id=login.login_type_id,
                        include_deleted=True,
                    )
                    if isinstance(lt, Failure):
                        return lt
                    lt_rec = lt.unwrap()
                    if lt_rec is not None:
                        detail.login_type.CopyFrom(login_type_to_pb(lt_rec))
                long.logins.append(detail)
            if not page_token:
                break

        us_tok = ""
        while True:
            us_batch = await self._user_skills.query_by_user(
                user_id=user.id,
                include_deleted=False,
                page_size=100,
                page_token=us_tok,
            )
            if isinstance(us_batch, Failure):
                return us_batch
            us_rows, us_tok = us_batch.unwrap()
            for link in us_rows:
                sk = await self._skills.get_by_id(item_id=link.skill_id, include_deleted=False)
                if isinstance(sk, Failure):
                    return sk
                sk_rec = sk.unwrap()
                if sk_rec is not None:
                    long.skills.append(skill_to_pb(sk_rec))
            if not us_tok:
                break

        return Success(long)

    async def update_user(
        self, request: iam_pb2.UpdateUserRequest
    ) -> Result[iam_pb2.User, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._users.get_by_id(user_id=request.id, include_deleted=True)
        if isinstance(got, Failure):
            return got
        existing = got.unwrap()
        if existing is None or existing.is_deleted:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="User not found.", detail=request.id)
            )

        updates: dict[str, object] = {"updated_at": utc_now_iso_z()}
        if request.HasField("first_name"):
            updates["first_name"] = request.first_name
        if request.HasField("last_name"):
            updates["last_name"] = request.last_name
        if request.HasField("account_id"):
            if not request.account_id.strip() or not _is_uuid(request.account_id):
                return Failure(
                    AppError(
                        code=ErrorCodes.VALIDATION,
                        message="account_id must be a UUID.",
                        detail=None,
                    ),
                )
            updates["account_id"] = request.account_id
        if request.HasField("notes"):
            updates["notes"] = request.notes
        if request.HasField("timezone"):
            updates["timezone"] = request.timezone
        if request.HasField("location"):
            updates["location"] = request.location
        if request.HasField("skill_list_id"):
            if request.skill_list_id.strip() and not _is_uuid(request.skill_list_id):
                return Failure(
                    AppError(
                        code=ErrorCodes.VALIDATION,
                        message="skill_list_id must be a UUID when set.",
                        detail=None,
                    ),
                )
            if request.skill_list_id.strip():
                sl = await self._skill_lists.get_by_id(
                    item_id=request.skill_list_id, include_deleted=False
                )
                if isinstance(sl, Failure):
                    return sl
                if sl.unwrap() is None:
                    return Failure(
                        AppError(
                            code=ErrorCodes.NOT_FOUND,
                            message="skill_list_id does not reference an active skill list.",
                            detail=request.skill_list_id,
                        ),
                    )
            updates["skill_list_id"] = request.skill_list_id
        if request.HasField("user_type_id"):
            if not request.user_type_id.strip() or not _is_uuid(request.user_type_id):
                return Failure(
                    AppError(
                        code=ErrorCodes.VALIDATION,
                        message="user_type_id must be a UUID.",
                        detail=None,
                    ),
                )
            ut = await self._user_types.get_by_id(
                item_id=request.user_type_id, include_deleted=False
            )
            if isinstance(ut, Failure):
                return ut
            if ut.unwrap() is None:
                return Failure(
                    AppError(
                        code=ErrorCodes.NOT_FOUND,
                        message="user_type_id does not reference an active user type.",
                        detail=request.user_type_id,
                    ),
                )
            updates["user_type_id"] = request.user_type_id
        if request.HasField("enabled"):
            updates["enabled"] = request.enabled

        merged = existing.model_copy(update=updates)
        put = await self._users.put(merged)
        if isinstance(put, Failure):
            return put
        return Success(user_to_pb(merged))

    async def soft_delete_user(
        self, request: iam_pb2.SoftDeleteUserRequest
    ) -> Result[iam_pb2.User, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._users.get_by_id(user_id=request.id, include_deleted=False)
        if isinstance(got, Failure):
            return got
        user = got.unwrap()
        if user is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="User not found.", detail=request.id)
            )

        now = utc_now_iso_z()
        us_page = ""
        while True:
            us_batch = await self._user_skills.query_by_user(
                user_id=request.id,
                include_deleted=False,
                page_size=100,
                page_token=us_page,
            )
            if isinstance(us_batch, Failure):
                return us_batch
            us_rows, us_page = us_batch.unwrap()
            for link in us_rows:
                del_us = await self._user_skills.soft_delete(link_id=link.id, now_iso=now)
                if isinstance(del_us, Failure):
                    return del_us
            if not us_page:
                break

        page_token = ""
        while True:
            batch = await self._logins.query_by_user(
                user_id=request.id,
                include_deleted=False,
                page_size=100,
                page_token=page_token,
            )
            if isinstance(batch, Failure):
                return batch
            rows, page_token = batch.unwrap()
            for login in rows:
                del_login = await self._logins.soft_delete(login_id=login.id, now_iso=now)
                if isinstance(del_login, Failure):
                    return del_login
            if not page_token:
                break

        deleted = await self._users.soft_delete(user_id=request.id, now_iso=now)
        if isinstance(deleted, Failure):
            return deleted
        rec = deleted.unwrap()
        if rec is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="User not found.", detail=request.id)
            )
        return Success(user_to_pb(rec))

    async def list_users_by_account(
        self,
        request: iam_pb2.ListUsersByAccountRequest,
    ) -> Result[iam_pb2.ListUsersByAccountReply, AppError]:
        if not request.account_id.strip() or not _is_uuid(request.account_id):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION, message="account_id must be a UUID.", detail=None
                ),
            )
        size = _clamp_page_size(int(request.page_size))
        user_type_filter: str | None = None
        if request.HasField("user_type_id"):
            tid = request.user_type_id.strip()
            if not tid or not _is_uuid(tid):
                return Failure(
                    AppError(
                        code=ErrorCodes.VALIDATION,
                        message="user_type_id filter must be a non-empty UUID when set.",
                        detail=None,
                    ),
                )
            user_type_filter = tid
        enabled_filter: bool | None = None
        if request.HasField("enabled"):
            enabled_filter = request.enabled
        name_contains: str | None = None
        if request.HasField("name_contains"):
            raw_name = request.name_contains.strip()
            name_contains = raw_name if raw_name else None

        q = await self._users.query_by_account(
            account_id=request.account_id,
            include_deleted=request.include_deleted,
            page_size=size,
            page_token=request.page_token,
            user_type_id=user_type_filter,
            enabled_equals=enabled_filter,
            name_contains=name_contains,
        )
        if isinstance(q, Failure):
            return q
        rows, next_tok = q.unwrap()
        reply = iam_pb2.ListUsersByAccountReply(next_page_token=next_tok)
        for row in rows:
            reply.users.append(user_to_pb(row))
        return Success(reply)

    async def _load_user_type_labels(self) -> Result[dict[str, str], AppError]:
        """Map user type id to human-readable label (display_name, else code)."""
        labels: dict[str, str] = {}
        page_token = ""
        while True:
            scanned = await self._user_types.scan_page(
                include_deleted=False,
                page_size=200,
                page_token=page_token,
            )
            if isinstance(scanned, Failure):
                return scanned
            rows, next_tok = scanned.unwrap()
            for row in rows:
                disp = row.display_name.strip()
                labels[row.id] = disp if disp else row.code
            if not next_tok:
                break
            page_token = next_tok
        return Success(labels)

    @staticmethod
    def _user_type_stat_label(type_labels: dict[str, str], user_type_id: str) -> str:
        tid = user_type_id.strip()
        if not tid:
            return "—"
        return type_labels.get(tid) or tid

    async def get_user_type_stats(
        self,
        request: iam_pb2.GetUserTypeStatsRequest,
    ) -> Result[iam_pb2.GetUserTypeStatsReply, AppError]:
        if not request.account_id.strip() or not _is_uuid(request.account_id):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION, message="account_id must be a UUID.", detail=None
                ),
            )
        labels_r = await self._load_user_type_labels()
        if isinstance(labels_r, Failure):
            return labels_r
        type_labels = labels_r.unwrap()

        agg = await self._users.aggregate_user_type_id_counts_for_account(
            account_id=request.account_id,
            include_deleted=request.include_deleted,
            page_size=200,
        )
        if isinstance(agg, Failure):
            return agg
        id_counts = agg.unwrap()
        counts: dict[str, int] = {}
        for ut_id, n in id_counts.items():
            label = self._user_type_stat_label(type_labels, ut_id)
            counts[label] = counts.get(label, 0) + int(n)

        sorted_pairs = sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0].lower()),
        )
        reply = iam_pb2.GetUserTypeStatsReply()
        for name, n in sorted_pairs:
            entry = reply.entries.add()
            entry.type_name = name
            entry.count = int(n)
        return Success(reply)

    async def create_user_type(
        self, request: iam_pb2.CreateUserTypeRequest
    ) -> Result[iam_pb2.UserType, AppError]:
        if not request.code.strip():
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="code is required.", detail=None)
            )
        now = utc_now_iso_z()
        rec = UserTypeRecord(
            id=str(uuid4()),
            created_at=now,
            updated_at=now,
            deleted_at="",
            is_deleted=False,
            enabled=request.enabled,
            code=request.code,
            display_name=request.display_name,
            data_json=request.data_json,
        )
        put = await self._user_types.put(rec)
        if isinstance(put, Failure):
            return put
        return Success(user_type_to_pb(rec))

    async def get_user_type(
        self, request: iam_pb2.GetUserTypeRequest
    ) -> Result[iam_pb2.UserType, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._user_types.get_by_id(
            item_id=request.id, include_deleted=request.include_deleted
        )
        if isinstance(got, Failure):
            return got
        rec = got.unwrap()
        if rec is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND, message="User type not found.", detail=request.id
                )
            )
        return Success(user_type_to_pb(rec))

    async def update_user_type(
        self, request: iam_pb2.UpdateUserTypeRequest
    ) -> Result[iam_pb2.UserType, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._user_types.get_by_id(item_id=request.id, include_deleted=True)
        if isinstance(got, Failure):
            return got
        existing = got.unwrap()
        if existing is None or existing.is_deleted:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND, message="User type not found.", detail=request.id
                )
            )
        updates: dict[str, object] = {"updated_at": utc_now_iso_z()}
        if request.HasField("code"):
            updates["code"] = request.code
        if request.HasField("display_name"):
            updates["display_name"] = request.display_name
        if request.HasField("data_json"):
            updates["data_json"] = request.data_json
        if request.HasField("enabled"):
            updates["enabled"] = request.enabled
        merged = existing.model_copy(update=updates)
        put = await self._user_types.put(merged)
        if isinstance(put, Failure):
            return put
        return Success(user_type_to_pb(merged))

    async def soft_delete_user_type(
        self,
        request: iam_pb2.SoftDeleteUserTypeRequest,
    ) -> Result[iam_pb2.UserType, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        deleted = await self._user_types.soft_delete(item_id=request.id, now_iso=utc_now_iso_z())
        if isinstance(deleted, Failure):
            return deleted
        rec = deleted.unwrap()
        if rec is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND, message="User type not found.", detail=request.id
                )
            )
        return Success(user_type_to_pb(rec))

    async def list_user_types(
        self, request: iam_pb2.ListUserTypesRequest
    ) -> Result[iam_pb2.ListUserTypesReply, AppError]:
        size = _clamp_page_size(int(request.page_size))
        scanned = await self._user_types.scan_page(
            include_deleted=request.include_deleted,
            page_size=size,
            page_token=request.page_token,
        )
        if isinstance(scanned, Failure):
            return scanned
        rows, next_tok = scanned.unwrap()
        reply = iam_pb2.ListUserTypesReply(next_page_token=next_tok)
        for row in rows:
            reply.items.append(user_type_to_pb(row))
        return Success(reply)

    async def create_login_type(
        self, request: iam_pb2.CreateLoginTypeRequest
    ) -> Result[iam_pb2.LoginType, AppError]:
        if not request.code.strip():
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="code is required.", detail=None)
            )
        now = utc_now_iso_z()
        rec = LoginTypeRecord(
            id=str(uuid4()),
            created_at=now,
            updated_at=now,
            deleted_at="",
            is_deleted=False,
            enabled=request.enabled,
            code=request.code,
            display_name=request.display_name,
            data_json=request.data_json,
        )
        put = await self._login_types.put(rec)
        if isinstance(put, Failure):
            return put
        return Success(login_type_to_pb(rec))

    async def get_login_type(
        self, request: iam_pb2.GetLoginTypeRequest
    ) -> Result[iam_pb2.LoginType, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._login_types.get_by_id(
            item_id=request.id, include_deleted=request.include_deleted
        )
        if isinstance(got, Failure):
            return got
        rec = got.unwrap()
        if rec is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND, message="Login type not found.", detail=request.id
                )
            )
        return Success(login_type_to_pb(rec))

    async def update_login_type(
        self, request: iam_pb2.UpdateLoginTypeRequest
    ) -> Result[iam_pb2.LoginType, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._login_types.get_by_id(item_id=request.id, include_deleted=True)
        if isinstance(got, Failure):
            return got
        existing = got.unwrap()
        if existing is None or existing.is_deleted:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND, message="Login type not found.", detail=request.id
                )
            )
        updates: dict[str, object] = {"updated_at": utc_now_iso_z()}
        if request.HasField("code"):
            updates["code"] = request.code
        if request.HasField("display_name"):
            updates["display_name"] = request.display_name
        if request.HasField("data_json"):
            updates["data_json"] = request.data_json
        if request.HasField("enabled"):
            updates["enabled"] = request.enabled
        merged = existing.model_copy(update=updates)
        put = await self._login_types.put(merged)
        if isinstance(put, Failure):
            return put
        return Success(login_type_to_pb(merged))

    async def soft_delete_login_type(
        self,
        request: iam_pb2.SoftDeleteLoginTypeRequest,
    ) -> Result[iam_pb2.LoginType, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        deleted = await self._login_types.soft_delete(item_id=request.id, now_iso=utc_now_iso_z())
        if isinstance(deleted, Failure):
            return deleted
        rec = deleted.unwrap()
        if rec is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND, message="Login type not found.", detail=request.id
                )
            )
        return Success(login_type_to_pb(rec))

    async def list_login_types(
        self, request: iam_pb2.ListLoginTypesRequest
    ) -> Result[iam_pb2.ListLoginTypesReply, AppError]:
        size = _clamp_page_size(int(request.page_size))
        scanned = await self._login_types.scan_page(
            include_deleted=request.include_deleted,
            page_size=size,
            page_token=request.page_token,
        )
        if isinstance(scanned, Failure):
            return scanned
        rows, next_tok = scanned.unwrap()
        reply = iam_pb2.ListLoginTypesReply(next_page_token=next_tok)
        for row in rows:
            reply.items.append(login_type_to_pb(row))
        return Success(reply)

    async def create_skill_list(
        self, request: iam_pb2.CreateSkillListRequest
    ) -> Result[iam_pb2.SkillList, AppError]:
        if not request.name.strip():
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="name is required.", detail=None)
            )
        now = utc_now_iso_z()
        rec = SkillListRecord(
            id=str(uuid4()),
            created_at=now,
            updated_at=now,
            deleted_at="",
            is_deleted=False,
            enabled=request.enabled,
            name=request.name,
            data_json=request.data_json,
        )
        put = await self._skill_lists.put(rec)
        if isinstance(put, Failure):
            return put
        return Success(skill_list_to_pb(rec))

    async def get_skill_list(
        self, request: iam_pb2.GetSkillListRequest
    ) -> Result[iam_pb2.SkillList, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._skill_lists.get_by_id(
            item_id=request.id, include_deleted=request.include_deleted
        )
        if isinstance(got, Failure):
            return got
        rec = got.unwrap()
        if rec is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND, message="Skill list not found.", detail=request.id
                )
            )
        return Success(skill_list_to_pb(rec))

    async def update_skill_list(
        self, request: iam_pb2.UpdateSkillListRequest
    ) -> Result[iam_pb2.SkillList, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._skill_lists.get_by_id(item_id=request.id, include_deleted=True)
        if isinstance(got, Failure):
            return got
        existing = got.unwrap()
        if existing is None or existing.is_deleted:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND, message="Skill list not found.", detail=request.id
                )
            )
        updates: dict[str, object] = {"updated_at": utc_now_iso_z()}
        if request.HasField("name"):
            updates["name"] = request.name
        if request.HasField("data_json"):
            updates["data_json"] = request.data_json
        if request.HasField("enabled"):
            updates["enabled"] = request.enabled
        merged = existing.model_copy(update=updates)
        put = await self._skill_lists.put(merged)
        if isinstance(put, Failure):
            return put
        return Success(skill_list_to_pb(merged))

    async def soft_delete_skill_list(
        self,
        request: iam_pb2.SoftDeleteSkillListRequest,
    ) -> Result[iam_pb2.SkillList, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        deleted = await self._skill_lists.soft_delete(item_id=request.id, now_iso=utc_now_iso_z())
        if isinstance(deleted, Failure):
            return deleted
        rec = deleted.unwrap()
        if rec is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND, message="Skill list not found.", detail=request.id
                )
            )
        return Success(skill_list_to_pb(rec))

    async def list_skills(
        self, request: iam_pb2.ListSkillsRequest
    ) -> Result[iam_pb2.ListSkillsReply, AppError]:
        size = _clamp_page_size(int(request.page_size))
        scanned = await self._skills.scan_page(
            include_deleted=request.include_deleted,
            page_size=size,
            page_token=request.page_token,
        )
        if isinstance(scanned, Failure):
            return scanned
        rows, next_tok = scanned.unwrap()
        reply = iam_pb2.ListSkillsReply(next_page_token=next_tok)
        for row in rows:
            reply.items.append(skill_to_pb(row))
        return Success(reply)

    async def create_skill(
        self, request: iam_pb2.CreateSkillRequest
    ) -> Result[iam_pb2.Skill, AppError]:
        if not request.code.strip():
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="code is required.", detail=None)
            )
        now = utc_now_iso_z()
        rec = SkillRecord(
            id=str(uuid4()),
            created_at=now,
            updated_at=now,
            deleted_at="",
            is_deleted=False,
            enabled=request.enabled,
            code=request.code,
            display_name=request.display_name,
            data_json=request.data_json,
        )
        put = await self._skills.put(rec)
        if isinstance(put, Failure):
            return put
        return Success(skill_to_pb(rec))

    async def get_skill(self, request: iam_pb2.GetSkillRequest) -> Result[iam_pb2.Skill, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._skills.get_by_id(
            item_id=request.id, include_deleted=request.include_deleted
        )
        if isinstance(got, Failure):
            return got
        rec = got.unwrap()
        if rec is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="Skill not found.", detail=request.id)
            )
        return Success(skill_to_pb(rec))

    async def update_skill(
        self, request: iam_pb2.UpdateSkillRequest
    ) -> Result[iam_pb2.Skill, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._skills.get_by_id(item_id=request.id, include_deleted=True)
        if isinstance(got, Failure):
            return got
        existing = got.unwrap()
        if existing is None or existing.is_deleted:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="Skill not found.", detail=request.id)
            )
        updates: dict[str, object] = {"updated_at": utc_now_iso_z()}
        if request.HasField("code"):
            updates["code"] = request.code
        if request.HasField("display_name"):
            updates["display_name"] = request.display_name
        if request.HasField("data_json"):
            updates["data_json"] = request.data_json
        if request.HasField("enabled"):
            updates["enabled"] = request.enabled
        merged = existing.model_copy(update=updates)
        put = await self._skills.put(merged)
        if isinstance(put, Failure):
            return put
        return Success(skill_to_pb(merged))

    async def soft_delete_skill(
        self, request: iam_pb2.SoftDeleteSkillRequest
    ) -> Result[iam_pb2.Skill, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        deleted = await self._skills.soft_delete(item_id=request.id, now_iso=utc_now_iso_z())
        if isinstance(deleted, Failure):
            return deleted
        rec = deleted.unwrap()
        if rec is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="Skill not found.", detail=request.id)
            )
        return Success(skill_to_pb(rec))

    async def list_user_skills(
        self, request: iam_pb2.ListUserSkillsRequest
    ) -> Result[iam_pb2.ListUserSkillsReply, AppError]:
        if not request.user_id.strip() or not _is_uuid(request.user_id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="user_id must be a UUID.", detail=None)
            )
        size = _clamp_page_size(int(request.page_size))
        q = await self._user_skills.query_by_user(
            user_id=request.user_id,
            include_deleted=request.include_deleted,
            page_size=size,
            page_token=request.page_token,
        )
        if isinstance(q, Failure):
            return q
        rows, next_tok = q.unwrap()
        reply = iam_pb2.ListUserSkillsReply(next_page_token=next_tok)
        for row in rows:
            reply.items.append(user_skill_to_pb(row))
        return Success(reply)

    async def create_user_skill(
        self, request: iam_pb2.CreateUserSkillRequest
    ) -> Result[iam_pb2.UserSkill, AppError]:
        uid = request.user_id.strip()
        sid = request.skill_id.strip()
        if not _is_uuid(uid):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="user_id must be a UUID.", detail=None)
            )
        if not _is_uuid(sid):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION, message="skill_id must be a UUID.", detail=None
                )
            )
        u = await self._users.get_by_id(user_id=uid, include_deleted=False)
        if isinstance(u, Failure):
            return u
        if u.unwrap() is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="user_id does not exist.", detail=uid)
            )
        sk = await self._skills.get_by_id(item_id=sid, include_deleted=False)
        if isinstance(sk, Failure):
            return sk
        if sk.unwrap() is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="skill_id does not reference an active skill.",
                    detail=sid,
                )
            )
        collected = await _collect_all_user_skills_for_user(
            self._user_skills,
            user_id=uid,
            include_deleted=False,
        )
        if isinstance(collected, Failure):
            return collected
        for row in collected.unwrap():
            if row.skill_id == sid:
                return Success(user_skill_to_pb(row))
        now = utc_now_iso_z()
        link = UserSkillRecord(
            id=str(uuid4()),
            user_id=uid,
            skill_id=sid,
            created_at=now,
            updated_at=now,
            deleted_at="",
            is_deleted=False,
        )
        put = await self._user_skills.put(link)
        if isinstance(put, Failure):
            return put
        return Success(user_skill_to_pb(link))

    async def soft_delete_user_skill(
        self, request: iam_pb2.SoftDeleteUserSkillRequest
    ) -> Result[iam_pb2.UserSkill, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        deleted = await self._user_skills.soft_delete(link_id=request.id, now_iso=utc_now_iso_z())
        if isinstance(deleted, Failure):
            return deleted
        rec = deleted.unwrap()
        if rec is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="User skill link not found.",
                    detail=request.id,
                )
            )
        return Success(user_skill_to_pb(rec))

    async def replace_user_skills(
        self,
        request: iam_pb2.ReplaceUserSkillsRequest,
    ) -> Result[iam_pb2.ReplaceUserSkillsReply, AppError]:
        uid = request.user_id.strip()
        if not _is_uuid(uid):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="user_id must be a UUID.", detail=None)
            )
        u = await self._users.get_by_id(user_id=uid, include_deleted=False)
        if isinstance(u, Failure):
            return u
        if u.unwrap() is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="User not found.", detail=uid)
            )
        synced = await self._sync_user_skills_for_user(uid, list(request.skill_ids))
        if isinstance(synced, Failure):
            return synced
        deduped = list(
            dict.fromkeys(
                [s.strip() for s in request.skill_ids if s.strip() and _is_uuid(s.strip())]
            ),
        )
        return Success(iam_pb2.ReplaceUserSkillsReply(applied_count=len(deduped)))

    async def create_login(
        self, request: iam_pb2.CreateLoginRequest
    ) -> Result[iam_pb2.Login, AppError]:
        if not request.user_id.strip() or not _is_uuid(request.user_id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="user_id must be a UUID.", detail=None)
            )
        if not request.login_type_id.strip() or not _is_uuid(request.login_type_id):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION, message="login_type_id must be a UUID.", detail=None
                ),
            )
        u = await self._users.get_by_id(user_id=request.user_id, include_deleted=False)
        if isinstance(u, Failure):
            return u
        if u.unwrap() is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="user_id does not exist.",
                    detail=request.user_id,
                )
            )
        lt = await self._login_types.get_by_id(item_id=request.login_type_id, include_deleted=False)
        if isinstance(lt, Failure):
            return lt
        if lt.unwrap() is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="login_type_id does not reference an active login type.",
                    detail=request.login_type_id,
                ),
            )
        now = utc_now_iso_z()
        rec = LoginRecord(
            id=str(uuid4()),
            user_id=request.user_id,
            login_type_id=request.login_type_id,
            name=request.name,
            description=request.description,
            created_at=now,
            updated_at=now,
            deleted_at="",
            is_deleted=False,
            enabled=request.enabled,
            data_json=request.data_json,
            password=request.password,
        )
        put = await self._logins.put(rec)
        if isinstance(put, Failure):
            return put
        return Success(login_to_pb(rec))

    async def get_login(self, request: iam_pb2.GetLoginRequest) -> Result[iam_pb2.Login, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._logins.get_by_id(
            login_id=request.id, include_deleted=request.include_deleted
        )
        if isinstance(got, Failure):
            return got
        rec = got.unwrap()
        if rec is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="Login not found.", detail=request.id)
            )
        return Success(login_to_pb(rec))

    async def update_login(
        self, request: iam_pb2.UpdateLoginRequest
    ) -> Result[iam_pb2.Login, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._logins.get_by_id(login_id=request.id, include_deleted=True)
        if isinstance(got, Failure):
            return got
        existing = got.unwrap()
        if existing is None or existing.is_deleted:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="Login not found.", detail=request.id)
            )
        updates: dict[str, object] = {"updated_at": utc_now_iso_z()}
        if request.HasField("login_type_id"):
            if not request.login_type_id.strip() or not _is_uuid(request.login_type_id):
                return Failure(
                    AppError(
                        code=ErrorCodes.VALIDATION,
                        message="login_type_id must be a UUID.",
                        detail=None,
                    ),
                )
            lt = await self._login_types.get_by_id(
                item_id=request.login_type_id, include_deleted=False
            )
            if isinstance(lt, Failure):
                return lt
            if lt.unwrap() is None:
                return Failure(
                    AppError(
                        code=ErrorCodes.NOT_FOUND,
                        message="login_type_id does not reference an active login type.",
                        detail=request.login_type_id,
                    ),
                )
            updates["login_type_id"] = request.login_type_id
        if request.HasField("name"):
            updates["name"] = request.name
        if request.HasField("description"):
            updates["description"] = request.description
        if request.HasField("data_json"):
            updates["data_json"] = request.data_json
        if request.HasField("enabled"):
            updates["enabled"] = request.enabled
        if request.HasField("password"):
            updates["password"] = request.password
        merged = existing.model_copy(update=updates)
        put = await self._logins.put(merged)
        if isinstance(put, Failure):
            return put
        return Success(login_to_pb(merged))

    async def soft_delete_login(
        self, request: iam_pb2.SoftDeleteLoginRequest
    ) -> Result[iam_pb2.Login, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        deleted = await self._logins.soft_delete(login_id=request.id, now_iso=utc_now_iso_z())
        if isinstance(deleted, Failure):
            return deleted
        rec = deleted.unwrap()
        if rec is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="Login not found.", detail=request.id)
            )
        return Success(login_to_pb(rec))

    async def generate_invite(
        self, request: iam_pb2.GenerateInviteRequest
    ) -> Result[iam_pb2.Invite, AppError]:
        if not request.account_id.strip() or not _is_uuid(request.account_id):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION, message="account_id must be a UUID.", detail=None
                )
            )
        if not request.user_type_id.strip() or not _is_uuid(request.user_type_id):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION, message="user_type_id must be a UUID.", detail=None
                )
            )
        if not request.login_type_id.strip() or not _is_uuid(request.login_type_id):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION, message="login_type_id must be a UUID.", detail=None
                )
            )

        ut = await self._user_types.get_by_id(item_id=request.user_type_id, include_deleted=False)
        if isinstance(ut, Failure):
            return ut
        if ut.unwrap() is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="user_type_id does not reference an active user type.",
                    detail=request.user_type_id,
                ),
            )

        lt = await self._login_types.get_by_id(item_id=request.login_type_id, include_deleted=False)
        if isinstance(lt, Failure):
            return lt
        if lt.unwrap() is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="login_type_id does not reference an active login type.",
                    detail=request.login_type_id,
                ),
            )

        ttl_hours = int(request.ttl_hours)
        if ttl_hours <= 0:
            ttl_hours = 24

        now = utc_now_iso_z()
        expires_at = _expiry_iso_z(now, timedelta(hours=ttl_hours))

        for _ in range(32):
            code = generate_random_invite_code()
            exists = await self._invites.any_item_exists_for_code(code=code)
            if isinstance(exists, Failure):
                return exists
            if exists.unwrap():
                continue
            invite_id = str(uuid4())
            rec = InviteRecord(
                id=invite_id,
                created_at=now,
                updated_at=now,
                deleted_at="",
                is_deleted=False,
                code=code,
                expires_at=expires_at,
                redeemed=False,
                account_id=request.account_id,
                user_type_id=request.user_type_id,
                login_type_id=request.login_type_id,
                recipient_email=request.recipient_email.strip(),
            )
            put = await self._invites.put(rec)
            if isinstance(put, Failure):
                return put
            return Success(invite_to_pb(rec))

        return Failure(
            AppError(
                code=ErrorCodes.INTERNAL,
                message="Could not allocate a unique invite code.",
                detail=None,
            ),
        )

    async def list_invites(
        self, request: iam_pb2.ListInvitesRequest
    ) -> Result[iam_pb2.ListInvitesReply, AppError]:
        size = _clamp_page_size(int(request.page_size))
        scanned = await self._invites.scan_page(
            include_deleted=request.include_deleted,
            page_size=size,
            page_token=request.page_token,
        )
        if isinstance(scanned, Failure):
            return scanned
        rows, next_tok = scanned.unwrap()
        reply = iam_pb2.ListInvitesReply(next_page_token=next_tok)
        for row in rows:
            reply.items.append(invite_to_pb(row))
        return Success(reply)

    async def soft_delete_invite(
        self, request: iam_pb2.SoftDeleteInviteRequest
    ) -> Result[iam_pb2.Invite, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        deleted = await self._invites.soft_delete(invite_id=request.id, now_iso=utc_now_iso_z())
        if isinstance(deleted, Failure):
            return deleted
        rec = deleted.unwrap()
        if rec is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="Invite not found.", detail=request.id)
            )
        return Success(invite_to_pb(rec))

    async def redeem_invite(
        self, request: iam_pb2.RedeemInviteRequest
    ) -> Result[iam_pb2.Invite, AppError]:
        if not request.id.strip() or not _is_uuid(request.id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="id must be a UUID.", detail=None)
            )
        got = await self._invites.get_by_id(invite_id=request.id, include_deleted=True)
        if isinstance(got, Failure):
            return got
        inv = got.unwrap()
        if inv is None:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="Invite not found.", detail=request.id)
            )
        if inv.is_deleted:
            return Failure(
                AppError(code=ErrorCodes.NOT_FOUND, message="Invite not found.", detail=request.id)
            )

        now = utc_now_iso_z()
        if _invite_expired(expires_at_iso=inv.expires_at, now_iso=now):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION, message="This invite has expired.", detail=None
                )
            )

        if inv.redeemed:
            return Success(invite_to_pb(inv))

        redeem = await self._invites.set_redeemed_if_unredeemed(invite_id=inv.id, now_iso=now)
        if isinstance(redeem, Failure):
            return redeem
        if redeem.unwrap() == "updated":
            merged = inv.model_copy(update={"redeemed": True, "updated_at": now})
            return Success(invite_to_pb(merged))

        refreshed = await self._invites.get_by_id(invite_id=inv.id, include_deleted=True)
        if isinstance(refreshed, Failure):
            return refreshed
        inv2 = refreshed.unwrap()
        if inv2 is not None and inv2.redeemed:
            return Success(invite_to_pb(inv2))
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION, message="Invite could not be redeemed.", detail=None
            )
        )

    async def sign_up_user(
        self, request: iam_pb2.SignUpUserRequest
    ) -> Result[iam_pb2.SignUpUserReply, AppError]:
        from iam_service.validation.sign_up_user import validate_sign_up_user_request

        validated_out = validate_sign_up_user_request(request)
        if isinstance(validated_out, Failure):
            return validated_out
        validated = validated_out.unwrap()
        email = str(validated.email)
        password = validated.password
        code = validated.invite_code

        got_inv = await self._invites.find_first_by_code(code=code)
        if isinstance(got_inv, Failure):
            return got_inv
        inv = got_inv.unwrap()
        if inv is None or inv.is_deleted:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="Unknown or unusable invite code.",
                    detail=None,
                )
            )
        if inv.redeemed:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="This invite has already been redeemed.",
                    detail=None,
                )
            )

        now = utc_now_iso_z()
        if _invite_expired(expires_at_iso=inv.expires_at, now_iso=now):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION, message="This invite has expired.", detail=None
                )
            )

        taken = await self._logins.find_active_by_name(name=email)
        if isinstance(taken, Failure):
            return taken
        if taken.unwrap() is not None:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="An account with this email already exists.",
                    detail=None,
                ),
            )

        create_user_req = iam_pb2.CreateUserRequest(
            first_name=validated.first_name,
            last_name=validated.last_name,
            account_id=inv.account_id,
            notes="",
            timezone="",
            location="",
            skill_list_id="",
            user_type_id=inv.user_type_id,
            enabled=True,
        )
        user_out = await self.create_user(create_user_req)
        if isinstance(user_out, Failure):
            return user_out
        user_pb = user_out.unwrap()

        create_login_req = iam_pb2.CreateLoginRequest(
            user_id=user_pb.id,
            login_type_id=inv.login_type_id,
            name=email,
            description="",
            data_json="{}",
            enabled=True,
            password=password,
        )
        login_out = await self.create_login(create_login_req)
        if isinstance(login_out, Failure):
            _ = await self.soft_delete_user(iam_pb2.SoftDeleteUserRequest(id=user_pb.id))
            return login_out
        login_pb = login_out.unwrap()

        redeem = await self._invites.set_redeemed_if_unredeemed(invite_id=inv.id, now_iso=now)
        if isinstance(redeem, Failure):
            _ = await self.soft_delete_user(iam_pb2.SoftDeleteUserRequest(id=user_pb.id))
            return redeem
        if redeem.unwrap() != "updated":
            _ = await self.soft_delete_user(iam_pb2.SoftDeleteUserRequest(id=user_pb.id))
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Invite could not be confirmed; please try again.",
                    detail=None,
                ),
            )

        safe_login = iam_pb2.Login()
        safe_login.CopyFrom(login_pb)
        safe_login.password = ""
        return Success(iam_pb2.SignUpUserReply(user=user_pb, login=safe_login))

    async def _verify_sign_in_credentials(
        self,
        *,
        username: str,
        password: str,
    ) -> Result[tuple[LoginRecord, UserRecord], AppError]:
        """Resolve ``username`` to an active login and verify ``password`` on that login row."""
        invalid = AppError(
            code=ErrorCodes.UNAUTHENTICATED,
            message="Invalid username or password.",
            detail=None,
        )

        login_lookup = await self._logins.find_active_by_name(name=username)
        if isinstance(login_lookup, Failure):
            return login_lookup
        login = login_lookup.unwrap()
        if login is not None and login.enabled:
            user_lookup = await self._users.get_by_id(user_id=login.user_id, include_deleted=False)
            if isinstance(user_lookup, Failure):
                return user_lookup
            user = user_lookup.unwrap()
            if user is not None and user.enabled and login.password == password:
                return Success((login, user))

        dep_lookup = await self._deployment_admins.find_active_by_email(email=username)
        if isinstance(dep_lookup, Failure):
            return dep_lookup
        dep = dep_lookup.unwrap()
        if dep is None or not dep.enabled or dep.password != password:
            return Failure(invalid)
        return Success(
            (deployment_admin_to_login_record(dep), deployment_admin_to_user_record(dep)),
        )

    async def sign_in_check(
        self,
        request: iam_pb2.SignInCheckRequest,
    ) -> Result[iam_pb2.SignInCheckReply, AppError]:
        from iam_service.validation.sign_in import validate_sign_in_check_request

        validated_out = validate_sign_in_check_request(request)
        if isinstance(validated_out, Failure):
            return validated_out
        validated = validated_out.unwrap()

        verified = await self._verify_sign_in_credentials(
            username=validated.username,
            password=validated.password,
        )
        if isinstance(verified, Failure):
            return verified
        login, user = verified.unwrap()
        return Success(
            iam_pb2.SignInCheckReply(
                user_id=user.id,
                login_id=login.id,
            ),
        )

    async def sign_in(self, request: iam_pb2.SignInRequest) -> Result[iam_pb2.Session, AppError]:
        """Authenticate ``username`` (Login.name) + ``password`` (Login.password).

        Returns a freshly persisted :class:`SessionRecord` on success. Bad
        credentials, missing logins, and disabled users all surface as
        ``UNAUTHENTICATED`` with an intentionally generic message so callers
        cannot probe which factor was wrong.
        """
        from iam_service.validation.sign_in import validate_sign_in_request

        validated_out = validate_sign_in_request(request)
        if isinstance(validated_out, Failure):
            return validated_out
        validated = validated_out.unwrap()

        verified = await self._verify_sign_in_credentials(
            username=validated.username,
            password=validated.password,
        )
        if isinstance(verified, Failure):
            return verified
        login, user = verified.unwrap()

        now = utc_now_iso_z()
        session = SessionRecord(
            id=str(uuid4()),
            user_id=user.id,
            login_id=login.id,
            created_at=now,
            updated_at=now,
            expires_at=_expiry_iso_z(now, _SESSION_TTL),
            deleted_at="",
            is_deleted=False,
            is_revoked=False,
        )
        put = await self._sessions.put(session)
        if isinstance(put, Failure):
            return put

        user_type_id = user.user_type_id.strip()
        user_type_display_name = ""
        if user_type_id:
            ut = await self._user_types.get_by_id(item_id=user_type_id, include_deleted=False)
            if isinstance(ut, Failure):
                return ut
            ut_rec = ut.unwrap()
            if ut_rec is not None:
                user_type_display_name = ut_rec.display_name

        auth_out = await self._rbac.build_user_auth_context(user.id)
        if isinstance(auth_out, Failure):
            return auth_out
        user_auth_context = auth_out.unwrap()

        return Success(
            session_to_pb(
                session,
                first_name=user.first_name,
                last_name=user.last_name,
                email=login.name,
                user_type_id=user.user_type_id,
                user_type_display_name=user_type_display_name,
                user_auth_context=user_auth_context,
            ),
        )

    async def sign_out(
        self, request: iam_pb2.SignOutRequest
    ) -> Result[iam_pb2.SignOutReply, AppError]:
        """Revoke a session by id (soft-delete + ``is_revoked``).

        Idempotent: missing or already-revoked sessions return success so clients
        can safely retry logout.
        """
        from iam_service.validation.sign_out import validate_sign_out_request

        validated_out = validate_sign_out_request(request)
        if isinstance(validated_out, Failure):
            return validated_out
        session_id = str(validated_out.unwrap().session_id)

        got = await self._sessions.get_by_id(item_id=session_id, include_deleted=True)
        if isinstance(got, Failure):
            return got
        existing = got.unwrap()
        if existing is None or existing.is_revoked or existing.is_deleted:
            return Success(iam_pb2.SignOutReply())

        now = utc_now_iso_z()
        revoked = existing.model_copy(
            update={
                "is_revoked": True,
                "is_deleted": True,
                "deleted_at": now,
                "updated_at": now,
            },
        )
        put = await self._sessions.put(revoked)
        if isinstance(put, Failure):
            return put
        return Success(iam_pb2.SignOutReply())

    async def list_logins_by_user_id(
        self,
        request: iam_pb2.ListLoginsByUserIdRequest,
    ) -> Result[iam_pb2.ListLoginsByUserIdReply, AppError]:
        if not request.user_id.strip() or not _is_uuid(request.user_id):
            return Failure(
                AppError(code=ErrorCodes.VALIDATION, message="user_id must be a UUID.", detail=None)
            )
        size = _clamp_page_size(int(request.page_size))
        q = await self._logins.query_by_user(
            user_id=request.user_id,
            include_deleted=request.include_deleted,
            page_size=size,
            page_token=request.page_token,
        )
        if isinstance(q, Failure):
            return q
        rows, next_tok = q.unwrap()
        reply = iam_pb2.ListLoginsByUserIdReply(next_page_token=next_tok)
        for login in rows:
            detail = iam_pb2.LoginDetail(login=login_to_pb(login))
            if login.login_type_id.strip():
                lt = await self._login_types.get_by_id(
                    item_id=login.login_type_id, include_deleted=True
                )
                if isinstance(lt, Failure):
                    return lt
                lt_rec = lt.unwrap()
                if lt_rec is not None:
                    detail.login_type.CopyFrom(login_type_to_pb(lt_rec))
            reply.items.append(detail)
        return Success(reply)

    async def list_roles(
        self, request: iam_pb2.ListRolesRequest
    ) -> Result[iam_pb2.ListRolesReply, AppError]:
        return await self._rbac.list_roles(request)

    async def create_role(
        self, request: iam_pb2.CreateRoleRequest
    ) -> Result[iam_pb2.Role, AppError]:
        return await self._rbac.create_role(request)

    async def list_permissions(
        self,
        request: iam_pb2.ListPermissionsRequest,
    ) -> Result[iam_pb2.ListPermissionsReply, AppError]:
        return await self._rbac.list_permissions(request)

    async def create_permission(
        self,
        request: iam_pb2.CreatePermissionRequest,
    ) -> Result[iam_pb2.Permission, AppError]:
        return await self._rbac.create_permission(request)

    async def attach_permission_to_role(
        self,
        request: iam_pb2.AttachPermissionToRoleRequest,
    ) -> Result[iam_pb2.RolePermission, AppError]:
        return await self._rbac.attach_permission_to_role(request)

    async def assign_role_to_user(
        self,
        request: iam_pb2.AssignRoleToUserRequest,
    ) -> Result[iam_pb2.UserRoleAssignment, AppError]:
        return await self._rbac.assign_role_to_user(request)

    async def revoke_role_from_user(
        self,
        request: iam_pb2.RevokeRoleFromUserRequest,
    ) -> Result[iam_pb2.RevokeRoleFromUserReply, AppError]:
        return await self._rbac.revoke_role_from_user(request)

    async def list_user_roles(
        self,
        request: iam_pb2.ListUserRolesRequest,
    ) -> Result[iam_pb2.ListUserRolesReply, AppError]:
        return await self._rbac.list_user_roles(request)

    async def check_user_auth_and_permissions(
        self,
        request: iam_pb2.CheckUserAuthAndPermissionsRequest,
    ) -> Result[iam_pb2.CheckUserAuthAndPermissionsReply, AppError]:
        return await self._rbac.check_user_auth_and_permissions(request)

    async def list_service_permissions(
        self,
        request: iam_pb2.ListServicePermissionsRequest,
    ) -> Result[iam_pb2.ListServicePermissionsReply, AppError]:
        return await self._rbac.list_service_permissions(request)

    async def register_service_permission(
        self,
        request: iam_pb2.RegisterServicePermissionRequest,
    ) -> Result[iam_pb2.ServicePermission, AppError]:
        return await self._rbac.register_service_permission(request)

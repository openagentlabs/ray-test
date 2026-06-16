"""Deterministic catalog rows for first-time tenant bootstrap (``EnsureInitialUser``)."""

from __future__ import annotations

from iam_service.core.errors import AppError
from iam_service.core.results import Failure, Result, Success
from iam_service.database.models.records import (
    LoginTypeRecord,
    SkillListRecord,
    SkillRecord,
    UserTypeRecord,
)
from iam_service.database.repositories.item_repository import ItemRepository
from iam_service.grpc_transport.proto_time import utc_now_iso_z

# Stable ids aligned with ``IamServiceConfig.accountId`` / invite defaults in the frontend.
INITIAL_ACCOUNT_ID = "00000000-0000-4000-8000-000000000001"
INITIAL_USER_TYPE_ID = "10000000-0000-4000-8000-000000000001"
INITIAL_LOGIN_TYPE_ID = "10000000-0000-4000-8000-000000000002"
INITIAL_SKILL_LIST_ID = "10000000-0000-4000-8000-000000000003"
INITIAL_SKILL_PYTHON_ID = "20000000-0000-4000-8000-000000000001"
INITIAL_SKILL_ARCH_ID = "20000000-0000-4000-8000-000000000002"
INITIAL_SEED_SKILL_IDS: tuple[str, ...] = (INITIAL_SKILL_PYTHON_ID, INITIAL_SKILL_ARCH_ID)


async def put_initial_catalog(
    *,
    user_types: ItemRepository[UserTypeRecord],
    login_types: ItemRepository[LoginTypeRecord],
    skill_lists: ItemRepository[SkillListRecord],
    skills: ItemRepository[SkillRecord],
) -> Result[None, AppError]:
    """Insert default user type, login type, skill list, and skill catalog when empty."""
    now = utc_now_iso_z()
    ut = UserTypeRecord(
        id=INITIAL_USER_TYPE_ID,
        created_at=now,
        updated_at=now,
        deleted_at="",
        is_deleted=False,
        enabled=True,
        code="admin",
        display_name="Administrator",
        data_json="{}",
    )
    put_ut = await user_types.put(ut)
    if isinstance(put_ut, Failure):
        return put_ut

    lt = LoginTypeRecord(
        id=INITIAL_LOGIN_TYPE_ID,
        created_at=now,
        updated_at=now,
        deleted_at="",
        is_deleted=False,
        enabled=True,
        code="email",
        display_name="Email address",
        data_json="{}",
    )
    put_lt = await login_types.put(lt)
    if isinstance(put_lt, Failure):
        return put_lt

    sl = SkillListRecord(
        id=INITIAL_SKILL_LIST_ID,
        created_at=now,
        updated_at=now,
        deleted_at="",
        is_deleted=False,
        enabled=True,
        name="Default skills",
        data_json="[]",
    )
    put_sl = await skill_lists.put(sl)
    if isinstance(put_sl, Failure):
        return put_sl

    py_skill = SkillRecord(
        id=INITIAL_SKILL_PYTHON_ID,
        created_at=now,
        updated_at=now,
        deleted_at="",
        is_deleted=False,
        enabled=True,
        code="python",
        display_name="Python",
        data_json="{}",
    )
    put_py = await skills.put(py_skill)
    if isinstance(put_py, Failure):
        return put_py

    arch_skill = SkillRecord(
        id=INITIAL_SKILL_ARCH_ID,
        created_at=now,
        updated_at=now,
        deleted_at="",
        is_deleted=False,
        enabled=True,
        code="architecture",
        display_name="Architecture",
        data_json="{}",
    )
    put_arch = await skills.put(arch_skill)
    if isinstance(put_arch, Failure):
        return put_arch

    return Success(None)

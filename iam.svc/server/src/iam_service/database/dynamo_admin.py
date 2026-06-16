"""Low-level DynamoDB maintenance: wipe tables (hard delete) and count rows."""

from __future__ import annotations

from typing import Any

import aioboto3
from botocore.exceptions import ClientError

from iam_service.core.app_config import DynamoDbTablesConfig
from iam_service.core.errors import AppError
from iam_service.core.results import Failure, Result, Success
from iam_service.database.dynamo_sdk_errors import failure_from_dynamo_sdk


class DynamoDatabaseAdmin:
    """Scans by partition key ``id`` and deletes every item (all entity tables)."""

    __slots__ = ("_session", "_region", "_endpoint_url", "_tables")

    def __init__(
        self,
        *,
        session: aioboto3.Session,
        region: str,
        endpoint_url: str | None,
        tables: DynamoDbTablesConfig,
    ) -> None:
        self._session = session
        self._region = region
        self._endpoint_url = endpoint_url
        self._tables = tables

    async def wipe_deployment_admin_table(self) -> Result[None, AppError]:
        """Hard-delete every row from the deployment-admin bootstrap table only."""
        return await self._wipe_table(table_name=self._tables.deployment_admin)

    async def wipe_all_tables(self) -> Result[None, AppError]:
        """Hard-delete every row from IAM entity tables (dependency-safe order).

        Does **not** touch ``deployment_admin`` — use ``wipe_deployment_admin_table``.
        """
        order = (
            self._tables.sessions,
            self._tables.invites,
            self._tables.user_role_assignments,
            self._tables.logins,
            self._tables.user_skills,
            self._tables.users,
            self._tables.role_permissions,
            self._tables.service_permissions,
            self._tables.roles,
            self._tables.permissions,
            self._tables.skills,
            self._tables.skill_lists,
            self._tables.login_types,
            self._tables.user_types,
        )
        for name in order:
            wiped = await self._wipe_table(table_name=name)
            if isinstance(wiped, Failure):
                return wiped
        return Success(None)

    async def deployment_admin_item_count(self) -> Result[int, AppError]:
        """Count rows in the deployment-admin table."""
        return await self._count_table(table_name=self._tables.deployment_admin)

    async def users_and_logins_item_count(self) -> Result[int, AppError]:
        """Count rows in users + logins tables (includes soft-deleted)."""
        total = 0
        for name in (self._tables.users, self._tables.logins):
            c = await self._count_table(table_name=name)
            if isinstance(c, Failure):
                return c
            total += c.unwrap()
        return Success(total)

    async def wipe_users_and_logins(self) -> Result[None, AppError]:
        """Hard-delete user credentials and profiles (sessions/skills links first)."""
        order = (
            self._tables.sessions,
            self._tables.user_skills,
            self._tables.logins,
            self._tables.users,
        )
        for name in order:
            wiped = await self._wipe_table(table_name=name)
            if isinstance(wiped, Failure):
                return wiped
        return Success(None)

    async def login_item_count(self) -> Result[int, AppError]:
        """Count rows in the logins table (includes soft-deleted rows)."""
        return await self._count_table(table_name=self._tables.logins)

    async def count_logins(self) -> Result[int, AppError]:
        """Alias for ``login_item_count``."""
        return await self.login_item_count()

    async def total_item_count(self) -> Result[int, AppError]:
        """Sum of items across all tables (includes soft-deleted rows)."""
        names = (
            self._tables.users,
            self._tables.user_types,
            self._tables.login_types,
            self._tables.skill_lists,
            self._tables.skills,
            self._tables.user_skills,
            self._tables.logins,
            self._tables.sessions,
            self._tables.invites,
            self._tables.roles,
            self._tables.permissions,
            self._tables.role_permissions,
            self._tables.user_role_assignments,
            self._tables.service_permissions,
        )
        total = 0
        for name in names:
            c = await self._count_table(table_name=name)
            if isinstance(c, Failure):
                return c
            total += c.unwrap()
        return Success(total)

    async def _wipe_table(self, *, table_name: str) -> Result[None, AppError]:
        if table_name == self._tables.role_permissions:
            return await self._wipe_composite_table(
                table_name=table_name,
                key_attrs=("role_id", "permission_id"),
            )
        if table_name == self._tables.user_role_assignments:
            return await self._wipe_composite_table(
                table_name=table_name,
                key_attrs=("user_id", "role_id"),
            )
        if table_name == self._tables.service_permissions:
            return await self._wipe_composite_table(
                table_name=table_name,
                key_attrs=("service_code", "permission_code"),
            )
        return await self._wipe_id_table(table_name=table_name)

    async def _wipe_id_table(self, *, table_name: str) -> Result[None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(table_name)
                start: dict[str, Any] | None = None
                while True:
                    kwargs: dict[str, Any] = {
                        "ProjectionExpression": "id",
                        "ConsistentRead": False,
                    }
                    if start:
                        kwargs["ExclusiveStartKey"] = start
                    resp = await table.scan(**kwargs)
                    for item in resp.get("Items", []):
                        key = item.get("id")
                        if key is None:
                            continue
                        await table.delete_item(Key={"id": key})
                    start = resp.get("LastEvaluatedKey")
                    if not start:
                        break
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk(f"DynamoDB wipe failed for table {table_name!r}.", exc)
        return Success(None)

    async def _wipe_composite_table(
        self,
        *,
        table_name: str,
        key_attrs: tuple[str, str],
    ) -> Result[None, AppError]:
        hash_attr, range_attr = key_attrs
        projection = f"{hash_attr}, {range_attr}"
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(table_name)
                start: dict[str, Any] | None = None
                while True:
                    kwargs: dict[str, Any] = {
                        "ProjectionExpression": projection,
                        "ConsistentRead": False,
                    }
                    if start:
                        kwargs["ExclusiveStartKey"] = start
                    resp = await table.scan(**kwargs)
                    for item in resp.get("Items", []):
                        h = item.get(hash_attr)
                        r = item.get(range_attr)
                        if h is None or r is None:
                            continue
                        await table.delete_item(Key={hash_attr: h, range_attr: r})
                    start = resp.get("LastEvaluatedKey")
                    if not start:
                        break
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk(f"DynamoDB wipe failed for table {table_name!r}.", exc)
        return Success(None)

    async def _count_table(self, *, table_name: str) -> Result[int, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(table_name)
                total = 0
                start: dict[str, Any] | None = None
                while True:
                    kwargs: dict[str, Any] = {"Select": "COUNT"}
                    if start:
                        kwargs["ExclusiveStartKey"] = start
                    resp = await table.scan(**kwargs)
                    total += int(resp.get("Count", 0))
                    start = resp.get("LastEvaluatedKey")
                    if not start:
                        break
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk(f"DynamoDB count failed for table {table_name!r}.", exc)
        return Success(total)

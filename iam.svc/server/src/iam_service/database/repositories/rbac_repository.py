"""RBAC persistence: catalog tables (PK ``id``) and composite-key link tables."""

from __future__ import annotations

from typing import Any

import aioboto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from pydantic import BaseModel, ValidationError

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.database.dynamo_sdk_errors import failure_from_dynamo_sdk
from iam_service.database.models.records import (
    PermissionRecord,
    RolePermissionRecord,
    RoleRecord,
    ServicePermissionRecord,
    UserRoleAssignmentRecord,
)
from iam_service.database.repositories.item_repository import ItemRepository


class RbacRepository:
    """Roles/permissions catalogs plus composite-key assignment tables."""

    __slots__ = (
        "_session",
        "_region",
        "_endpoint_url",
        "_roles_table",
        "_permissions_table",
        "_role_permissions_table",
        "_user_role_assignments_table",
        "_service_permissions_table",
        "_roles",
        "_permissions",
    )

    def __init__(
        self,
        *,
        session: aioboto3.Session,
        region: str,
        endpoint_url: str | None,
        roles_table: str,
        permissions_table: str,
        role_permissions_table: str,
        user_role_assignments_table: str,
        service_permissions_table: str,
    ) -> None:
        self._session = session
        self._region = region
        self._endpoint_url = endpoint_url
        self._roles_table = roles_table
        self._permissions_table = permissions_table
        self._role_permissions_table = role_permissions_table
        self._user_role_assignments_table = user_role_assignments_table
        self._service_permissions_table = service_permissions_table
        self._roles = ItemRepository[RoleRecord](
            session=session,
            region=region,
            endpoint_url=endpoint_url,
            table_name=roles_table,
            model=RoleRecord,
        )
        self._permissions = ItemRepository[PermissionRecord](
            session=session,
            region=region,
            endpoint_url=endpoint_url,
            table_name=permissions_table,
            model=PermissionRecord,
        )

    @property
    def roles(self) -> ItemRepository[RoleRecord]:
        return self._roles

    @property
    def permissions(self) -> ItemRepository[PermissionRecord]:
        return self._permissions

    async def find_role_by_code(self, *, code: str) -> Result[RoleRecord | None, AppError]:
        return await self._find_by_code(
            table_name=self._roles_table,
            index_name="role-codes",
            model=RoleRecord,
            code=code,
        )

    async def find_permission_by_code(
        self, *, code: str
    ) -> Result[PermissionRecord | None, AppError]:
        return await self._find_by_code(
            table_name=self._permissions_table,
            index_name="permission-codes",
            model=PermissionRecord,
            code=code,
        )

    async def list_roles_page(
        self,
        *,
        include_deleted: bool,
        page_size: int,
        page_token: str,
    ) -> Result[tuple[list[RoleRecord], str], AppError]:
        return await self._roles.scan_page(
            include_deleted=include_deleted,
            page_size=page_size,
            page_token=page_token,
        )

    async def list_permissions_page(
        self,
        *,
        include_deleted: bool,
        page_size: int,
        page_token: str,
    ) -> Result[tuple[list[PermissionRecord], str], AppError]:
        return await self._permissions.scan_page(
            include_deleted=include_deleted,
            page_size=page_size,
            page_token=page_token,
        )

    async def put_role_permission(self, record: RolePermissionRecord) -> Result[None, AppError]:
        return await self._put_composite(self._role_permissions_table, record)

    async def get_role_permission(
        self,
        *,
        role_id: str,
        permission_id: str,
    ) -> Result[RolePermissionRecord | None, AppError]:
        return await self._get_composite(
            self._role_permissions_table,
            RolePermissionRecord,
            {"role_id": role_id, "permission_id": permission_id},
        )

    async def list_permissions_for_role(
        self,
        *,
        role_id: str,
    ) -> Result[list[RolePermissionRecord], AppError]:
        return await self._query_composite(
            table_name=self._role_permissions_table,
            model=RolePermissionRecord,
            hash_key_name="role_id",
            hash_key_value=role_id,
        )

    async def put_user_role_assignment(
        self, record: UserRoleAssignmentRecord
    ) -> Result[None, AppError]:
        return await self._put_composite(self._user_role_assignments_table, record)

    async def delete_user_role_assignment(
        self, *, user_id: str, role_id: str
    ) -> Result[None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._user_role_assignments_table)
                await table.delete_item(Key={"user_id": user_id, "role_id": role_id})
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk(
                "DynamoDB delete_item failed for user role assignment.", exc
            )
        return Success(None)

    async def get_user_role_assignment(
        self,
        *,
        user_id: str,
        role_id: str,
    ) -> Result[UserRoleAssignmentRecord | None, AppError]:
        return await self._get_composite(
            self._user_role_assignments_table,
            UserRoleAssignmentRecord,
            {"user_id": user_id, "role_id": role_id},
        )

    async def list_roles_for_user(
        self, *, user_id: str
    ) -> Result[list[UserRoleAssignmentRecord], AppError]:
        return await self._query_composite(
            table_name=self._user_role_assignments_table,
            model=UserRoleAssignmentRecord,
            hash_key_name="user_id",
            hash_key_value=user_id,
        )

    async def put_service_permission(
        self, record: ServicePermissionRecord
    ) -> Result[None, AppError]:
        return await self._put_composite(self._service_permissions_table, record)

    async def list_service_permissions(
        self,
        *,
        service_code: str,
    ) -> Result[list[ServicePermissionRecord], AppError]:
        return await self._query_composite(
            table_name=self._service_permissions_table,
            model=ServicePermissionRecord,
            hash_key_name="service_code",
            hash_key_value=service_code,
        )

    async def _find_by_code[TModel: BaseModel](
        self,
        *,
        table_name: str,
        index_name: str,
        model: type[TModel],
        code: str,
    ) -> Result[TModel | None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(table_name)
                resp = await table.query(
                    IndexName=index_name,
                    KeyConditionExpression=Key("code").eq(code),
                    Limit=5,
                )
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB query failed for RBAC catalog by code.", exc)
        for raw in resp.get("Items", []):
            try:
                rec = model.model_validate(raw)
            except ValidationError:
                continue
            if getattr(rec, "is_deleted", False):
                continue
            return Success(rec)
        return Success(None)

    async def _put_composite(self, table_name: str, record: BaseModel) -> Result[None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(table_name)
                await table.put_item(Item=record.model_dump())
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB put_item failed for RBAC link row.", exc)
        return Success(None)

    async def _get_composite[TModel: BaseModel](
        self,
        table_name: str,
        model: type[TModel],
        key: dict[str, str],
    ) -> Result[TModel | None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(table_name)
                resp = await table.get_item(Key=key)
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB get_item failed for RBAC link row.", exc)
        item = resp.get("Item")
        if item is None:
            return Success(None)
        try:
            return Success(model.model_validate(item))
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Stored RBAC link record is invalid.",
                    detail=str(exc),
                ),
            )

    async def _query_composite[TModel: BaseModel](
        self,
        *,
        table_name: str,
        model: type[TModel],
        hash_key_name: str,
        hash_key_value: str,
    ) -> Result[list[TModel], AppError]:
        out: list[TModel] = []
        start: dict[str, Any] | None = None
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(table_name)
                while True:
                    kwargs: dict[str, Any] = {
                        "KeyConditionExpression": Key(hash_key_name).eq(hash_key_value),
                    }
                    if start:
                        kwargs["ExclusiveStartKey"] = start
                    resp = await table.query(**kwargs)
                    for raw in resp.get("Items", []):
                        try:
                            out.append(model.model_validate(raw))
                        except ValidationError:
                            continue
                    start = resp.get("LastEvaluatedKey")
                    if not start:
                        break
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB query failed for RBAC link rows.", exc)
        return Success(out)

"""Repository for service function registry and user permission tables."""

from __future__ import annotations

from typing import Any

import aioboto3
from botocore.exceptions import ClientError
from pydantic import ValidationError

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.database.dynamo_sdk_errors import failure_from_dynamo_sdk
from iam_service.database.filters import active_item_filter
from iam_service.database.models.records import (
    ServiceFunctionRegistryRecord,
    UserPermissionRecord,
)


class ServiceFunctionRegistryRepository:
    """PK ``service_id`` catalog of service names and function JSON."""

    __slots__ = ("_session", "_region", "_endpoint_url", "_table_name")

    def __init__(
        self,
        *,
        session: aioboto3.Session,
        region: str,
        endpoint_url: str | None,
        table_name: str,
    ) -> None:
        self._session = session
        self._region = region
        self._endpoint_url = endpoint_url
        self._table_name = table_name

    async def get_by_service_id(
        self,
        service_id: str,
    ) -> Result[ServiceFunctionRegistryRecord | None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                resp = await table.get_item(Key={"service_id": service_id})
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB get_item failed.", exc)
        item = resp.get("Item")
        if item is None:
            return Success(None)
        try:
            rec = ServiceFunctionRegistryRecord.model_validate(item)
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Stored service registry record is invalid.",
                    detail=str(exc),
                ),
            )
        if rec.is_deleted:
            return Success(None)
        return Success(rec)

    async def put(self, record: ServiceFunctionRegistryRecord) -> Result[None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                await table.put_item(Item=record.model_dump())
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB put_item failed.", exc)
        return Success(None)

    async def list_active(self) -> Result[list[ServiceFunctionRegistryRecord], AppError]:
        items: list[ServiceFunctionRegistryRecord] = []
        kwargs: dict[str, Any] = {"FilterExpression": active_item_filter()}
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                while True:
                    resp = await table.scan(**kwargs)
                    for raw in resp.get("Items", []):
                        try:
                            rec = ServiceFunctionRegistryRecord.model_validate(raw)
                        except ValidationError:
                            continue
                        if not rec.is_deleted:
                            items.append(rec)
                    last_key = resp.get("LastEvaluatedKey")
                    if not last_key:
                        break
                    kwargs["ExclusiveStartKey"] = last_key
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB scan failed.", exc)
        return Success(items)


class UserPermissionRepository:
    """PK ``user_id``, SK ``service_id`` user permission grants."""

    __slots__ = ("_session", "_region", "_endpoint_url", "_table_name")

    def __init__(
        self,
        *,
        session: aioboto3.Session,
        region: str,
        endpoint_url: str | None,
        table_name: str,
    ) -> None:
        self._session = session
        self._region = region
        self._endpoint_url = endpoint_url
        self._table_name = table_name

    async def list_for_user(
        self,
        user_id: str,
    ) -> Result[list[UserPermissionRecord], AppError]:
        items: list[UserPermissionRecord] = []
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                resp = await table.query(
                    KeyConditionExpression="user_id = :uid",
                    ExpressionAttributeValues={":uid": user_id},
                    FilterExpression=active_item_filter(),
                )
                for raw in resp.get("Items", []):
                    try:
                        rec = UserPermissionRecord.model_validate(raw)
                    except ValidationError:
                        continue
                    if not rec.is_deleted:
                        items.append(rec)
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB query failed.", exc)
        return Success(items)

    async def put(self, record: UserPermissionRecord) -> Result[None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                await table.put_item(Item=record.model_dump())
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB put_item failed.", exc)
        return Success(None)

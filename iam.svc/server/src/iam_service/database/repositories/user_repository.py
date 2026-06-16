"""User table repository (PK ``id``; GSI ``account-users``)."""

from __future__ import annotations

from typing import Any

import aioboto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from pydantic import ValidationError

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.database.dynamo_sdk_errors import failure_from_dynamo_sdk
from iam_service.database.models.records import UserRecord
from iam_service.database.pagination import decode_exclusive_start_key, encode_exclusive_start_key
from iam_service.database.user_account_list_filters import user_account_list_filter_expression


class UserRepository:
    """CRUD + account listing for ``UserRecord`` items."""

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

    async def get_by_id(
        self,
        *,
        user_id: str,
        include_deleted: bool,
    ) -> Result[UserRecord | None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                resp = await table.get_item(Key={"id": user_id})
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB get_item failed for user.", exc)
        item = resp.get("Item")
        if item is None:
            return Success(None)
        try:
            rec = UserRecord.model_validate(item)
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Stored user record is invalid.",
                    detail=str(exc),
                ),
            )
        if not include_deleted and rec.is_deleted:
            return Success(None)
        return Success(rec)

    async def put(self, record: UserRecord) -> Result[None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                await table.put_item(Item=record.model_dump())
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB put_item failed for user.", exc)
        return Success(None)

    async def soft_delete(
        self,
        *,
        user_id: str,
        now_iso: str,
    ) -> Result[UserRecord | None, AppError]:
        got = await self.get_by_id(user_id=user_id, include_deleted=True)
        if isinstance(got, Failure):
            return got
        existing = got.unwrap()
        if existing is None:
            return Success(None)
        updated = existing.model_copy(
            update={"is_deleted": True, "deleted_at": now_iso, "updated_at": now_iso},
        )
        put = await self.put(updated)
        if isinstance(put, Failure):
            return put
        return Success(updated)

    async def query_by_account(
        self,
        *,
        account_id: str,
        include_deleted: bool,
        page_size: int,
        page_token: str,
        user_type_id: str | None = None,
        enabled_equals: bool | None = None,
        name_contains: str | None = None,
    ) -> Result[tuple[list[UserRecord], str], AppError]:
        filt = user_account_list_filter_expression(
            include_deleted=include_deleted,
            user_type_id=user_type_id,
            enabled_equals=enabled_equals,
            name_contains=name_contains,
        )
        start = decode_exclusive_start_key(page_token)
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                kwargs: dict[str, Any] = {
                    "IndexName": "account-users",
                    "KeyConditionExpression": Key("account_id").eq(account_id),
                    "Limit": page_size,
                }
                if filt is not None:
                    kwargs["FilterExpression"] = filt
                if start:
                    kwargs["ExclusiveStartKey"] = start
                resp = await table.query(**kwargs)
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB query failed for users by account.", exc)
        items = resp.get("Items", [])
        out: list[UserRecord] = []
        for raw in items:
            try:
                out.append(UserRecord.model_validate(raw))
            except ValidationError:
                continue
        next_key = encode_exclusive_start_key(resp.get("LastEvaluatedKey"))
        return Success((out, next_key))

    async def aggregate_user_type_id_counts_for_account(
        self,
        *,
        account_id: str,
        include_deleted: bool,
        page_size: int,
    ) -> Result[dict[str, int], AppError]:
        """Count users per ``user_type_id`` for an account via projected GSI query.

        Smaller I/O than loading full user rows.
        """
        filt = user_account_list_filter_expression(
            include_deleted=include_deleted,
            user_type_id=None,
            enabled_equals=None,
            name_contains=None,
        )
        counts: dict[str, int] = {}
        page_token = ""
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                while True:
                    start = decode_exclusive_start_key(page_token)
                    kwargs: dict[str, Any] = {
                        "IndexName": "account-users",
                        "KeyConditionExpression": Key("account_id").eq(account_id),
                        "Limit": page_size,
                        "ProjectionExpression": "user_type_id",
                    }
                    if filt is not None:
                        kwargs["FilterExpression"] = filt
                    if start:
                        kwargs["ExclusiveStartKey"] = start
                    resp = await table.query(**kwargs)
                    for raw in resp.get("Items", []):
                        tid = raw.get("user_type_id", "")
                        tid_s = tid.strip() if isinstance(tid, str) else ""
                        counts[tid_s] = counts.get(tid_s, 0) + 1
                    lek = resp.get("LastEvaluatedKey")
                    if not lek:
                        break
                    page_token = encode_exclusive_start_key(lek)
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB query failed for user type id counts.", exc)
        return Success(counts)

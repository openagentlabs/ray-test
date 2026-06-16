"""Login table repository (PK ``id``; GSI ``user-logins``)."""

from __future__ import annotations

from typing import Any

import aioboto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from pydantic import ValidationError

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.database.dynamo_sdk_errors import failure_from_dynamo_sdk
from iam_service.database.filters import active_item_filter
from iam_service.database.models.records import LoginRecord
from iam_service.database.pagination import decode_exclusive_start_key, encode_exclusive_start_key


class LoginRepository:
    """CRUD + user-centric listing for ``LoginRecord`` items."""

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
        login_id: str,
        include_deleted: bool,
    ) -> Result[LoginRecord | None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                resp = await table.get_item(Key={"id": login_id})
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB get_item failed for login.", exc)
        item = resp.get("Item")
        if item is None:
            return Success(None)
        try:
            rec = LoginRecord.model_validate(item)
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Stored login record is invalid.",
                    detail=str(exc),
                ),
            )
        if not include_deleted and rec.is_deleted:
            return Success(None)
        return Success(rec)

    async def put(self, record: LoginRecord) -> Result[None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                await table.put_item(Item=record.model_dump())
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB put_item failed for login.", exc)
        return Success(None)

    async def soft_delete(
        self,
        *,
        login_id: str,
        now_iso: str,
    ) -> Result[LoginRecord | None, AppError]:
        got = await self.get_by_id(login_id=login_id, include_deleted=True)
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

    async def find_active_by_name(self, *, name: str) -> Result[LoginRecord | None, AppError]:
        """Return the first active, enabled ``Login`` whose ``name`` equals ``name``.

        Performs a paginated DynamoDB scan with a ``name`` equality filter. The
        login table has no GSI on ``name``; sign-in volume is expected to be low,
        so this trades off a scan for schema simplicity. Soft-deleted and
        disabled rows are skipped server-side.
        """
        if not name:
            return Success(None)
        filt = (
            Attr("name").eq(name)
            & (Attr("is_deleted").not_exists() | Attr("is_deleted").eq(False))
            & Attr("enabled").eq(True)
        )
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                last_evaluated: dict[str, Any] | None = None
                while True:
                    kwargs: dict[str, Any] = {"FilterExpression": filt}
                    if last_evaluated:
                        kwargs["ExclusiveStartKey"] = last_evaluated
                    resp = await table.scan(**kwargs)
                    for raw in resp.get("Items", []):
                        try:
                            return Success(LoginRecord.model_validate(raw))
                        except ValidationError:
                            continue
                    last_evaluated = resp.get("LastEvaluatedKey")
                    if not last_evaluated:
                        return Success(None)
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB scan failed for login by name.", exc)

    async def query_by_user(
        self,
        *,
        user_id: str,
        include_deleted: bool,
        page_size: int,
        page_token: str,
    ) -> Result[tuple[list[LoginRecord], str], AppError]:
        filt = active_item_filter(include_deleted=include_deleted)
        start = decode_exclusive_start_key(page_token)
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                kwargs: dict[str, Any] = {
                    "IndexName": "user-logins",
                    "KeyConditionExpression": Key("user_id").eq(user_id),
                    "Limit": page_size,
                }
                if filt is not None:
                    kwargs["FilterExpression"] = filt
                if start:
                    kwargs["ExclusiveStartKey"] = start
                resp = await table.query(**kwargs)
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB query failed for logins by user.", exc)
        items = resp.get("Items", [])
        out: list[LoginRecord] = []
        for raw in items:
            try:
                out.append(LoginRecord.model_validate(raw))
            except ValidationError:
                continue
        next_key = encode_exclusive_start_key(resp.get("LastEvaluatedKey"))
        return Success((out, next_key))

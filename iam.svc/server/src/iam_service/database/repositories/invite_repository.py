"""Invite table repository (PK ``id``; GSI ``invite-codes`` on ``code``)."""

from __future__ import annotations

from typing import Any, Literal

import aioboto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from pydantic import ValidationError

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.database.dynamo_sdk_errors import failure_from_dynamo_sdk
from iam_service.database.filters import active_item_filter
from iam_service.database.models.records import InviteRecord
from iam_service.database.pagination import decode_exclusive_start_key, encode_exclusive_start_key


class InviteRepository:
    """Persistence for ``InviteRecord`` rows."""

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
        invite_id: str,
        include_deleted: bool,
    ) -> Result[InviteRecord | None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                resp = await table.get_item(Key={"id": invite_id})
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB get_item failed for invite.", exc)
        item = resp.get("Item")
        if item is None:
            return Success(None)
        try:
            rec = InviteRecord.model_validate(item)
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Stored invite record is invalid.",
                    detail=str(exc),
                ),
            )
        if not include_deleted and rec.is_deleted:
            return Success(None)
        return Success(rec)

    async def put(self, record: InviteRecord) -> Result[None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                await table.put_item(Item=record.model_dump())
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB put_item failed for invite.", exc)
        return Success(None)

    async def soft_delete(
        self,
        *,
        invite_id: str,
        now_iso: str,
    ) -> Result[InviteRecord | None, AppError]:
        got = await self.get_by_id(invite_id=invite_id, include_deleted=True)
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

    async def any_item_exists_for_code(self, *, code: str) -> Result[bool, AppError]:
        """True when any row uses this ``code`` in the GSI (including soft-deleted)."""
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                resp = await table.query(
                    IndexName="invite-codes",
                    KeyConditionExpression=Key("code").eq(code),
                    Limit=1,
                )
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB query failed for invite by code.", exc)
        items = resp.get("Items", [])
        return Success(len(items) > 0)

    async def find_first_by_code(self, *, code: str) -> Result[InviteRecord | None, AppError]:
        """Return the first stored row for ``code`` (caller filters deleted / redeemed / expiry)."""
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                resp = await table.query(
                    IndexName="invite-codes",
                    KeyConditionExpression=Key("code").eq(code),
                    Limit=5,
                )
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB query failed for invite by code.", exc)
        for raw in resp.get("Items", []):
            try:
                return Success(InviteRecord.model_validate(raw))
            except ValidationError:
                continue
        return Success(None)

    async def set_redeemed_if_unredeemed(
        self,
        *,
        invite_id: str,
        now_iso: str,
    ) -> Result[Literal["updated", "unchanged"], AppError]:
        """Atomically flip ``redeemed`` to true when it is currently false and the row is active."""
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                await table.update_item(
                    Key={"id": invite_id},
                    UpdateExpression="SET redeemed = :true, updated_at = :u",
                    ConditionExpression="redeemed = :rf AND is_deleted = :df",
                    ExpressionAttributeValues={
                        ":true": True,
                        ":u": now_iso,
                        ":rf": False,
                        ":df": False,
                    },
                )
        except ClientError as exc:
            err: dict[str, Any] = exc.response.get("Error", {})
            if err.get("Code") == "ConditionalCheckFailedException":
                return Success("unchanged")
            return failure_from_dynamo_sdk("DynamoDB update_item failed for invite redeem.", exc)
        except OSError as exc:
            return failure_from_dynamo_sdk("DynamoDB update_item failed for invite redeem.", exc)
        return Success("updated")

    async def scan_page(
        self,
        *,
        include_deleted: bool,
        page_size: int,
        page_token: str,
    ) -> Result[tuple[list[InviteRecord], str], AppError]:
        filt = active_item_filter(include_deleted=include_deleted)
        start = decode_exclusive_start_key(page_token)
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                kwargs: dict[str, Any] = {"Limit": page_size}
                if filt is not None:
                    kwargs["FilterExpression"] = filt
                if start:
                    kwargs["ExclusiveStartKey"] = start
                resp = await table.scan(**kwargs)
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB scan failed for invites.", exc)
        items = resp.get("Items", [])
        out: list[InviteRecord] = []
        for raw in items:
            try:
                out.append(InviteRecord.model_validate(raw))
            except ValidationError:
                continue
        next_key = encode_exclusive_start_key(resp.get("LastEvaluatedKey"))
        return Success((out, next_key))

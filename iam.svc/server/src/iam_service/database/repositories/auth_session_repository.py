"""Auth session persistence repository."""

from __future__ import annotations

import aioboto3
from botocore.exceptions import ClientError
from pydantic import ValidationError

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.database.dynamo_sdk_errors import failure_from_dynamo_sdk
from iam_service.database.models.records import AuthSessionRecord


class AuthSessionRepository:
    """PK ``id`` auth session rows backing refresh tokens."""

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
        session_id: str,
    ) -> Result[AuthSessionRecord | None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                resp = await table.get_item(Key={"id": session_id})
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB get_item failed.", exc)
        item = resp.get("Item")
        if item is None:
            return Success(None)
        try:
            rec = AuthSessionRecord.model_validate(item)
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Stored auth session record is invalid.",
                    detail=str(exc),
                ),
            )
        if rec.is_deleted or rec.is_revoked:
            return Success(None)
        return Success(rec)

    async def put(self, record: AuthSessionRecord) -> Result[None, AppError]:
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

    async def revoke(self, session_id: str, *, now_iso: str) -> Result[None, AppError]:
        loaded = await self.get_by_id(session_id)
        if isinstance(loaded, Failure):
            return loaded
        record = loaded.unwrap()
        if record is None:
            return Success(None)
        updated = record.model_copy(
            update={
                "is_revoked": True,
                "is_deleted": True,
                "deleted_at": now_iso,
                "updated_at": now_iso,
            },
        )
        return await self.put(updated)

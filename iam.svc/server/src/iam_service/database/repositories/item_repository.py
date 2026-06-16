"""Generic single-table repository (PK ``id``) with optional scan listing."""

from __future__ import annotations

from typing import Any

import aioboto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, ValidationError

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.database.dynamo_sdk_errors import failure_from_dynamo_sdk
from iam_service.database.filters import active_item_filter
from iam_service.database.pagination import decode_exclusive_start_key, encode_exclusive_start_key


class ItemRepository[TModel: BaseModel]:
    """CRUD + paginated scan for catalog-like tables."""

    __slots__ = ("_session", "_region", "_endpoint_url", "_table_name", "_model")

    def __init__(
        self,
        *,
        session: aioboto3.Session,
        region: str,
        endpoint_url: str | None,
        table_name: str,
        model: type[TModel],
    ) -> None:
        self._session = session
        self._region = region
        self._endpoint_url = endpoint_url
        self._table_name = table_name
        self._model = model

    async def get_by_id(
        self,
        *,
        item_id: str,
        include_deleted: bool,
    ) -> Result[TModel | None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                resp = await table.get_item(Key={"id": item_id})
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB get_item failed.", exc)
        item = resp.get("Item")
        if item is None:
            return Success(None)
        try:
            rec = self._model.model_validate(item)
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Stored record is invalid.",
                    detail=str(exc),
                ),
            )
        if not include_deleted and getattr(rec, "is_deleted", False):
            return Success(None)
        return Success(rec)

    async def put(self, record: TModel) -> Result[None, AppError]:
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

    async def soft_delete(self, *, item_id: str, now_iso: str) -> Result[TModel | None, AppError]:
        got = await self.get_by_id(item_id=item_id, include_deleted=True)
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

    async def scan_page(
        self,
        *,
        include_deleted: bool,
        page_size: int,
        page_token: str,
    ) -> Result[tuple[list[TModel], str], AppError]:
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
            return failure_from_dynamo_sdk("DynamoDB scan failed.", exc)
        items = resp.get("Items", [])
        out: list[TModel] = []
        for raw in items:
            try:
                out.append(self._model.model_validate(raw))
            except ValidationError:
                continue
        next_key = encode_exclusive_start_key(resp.get("LastEvaluatedKey"))
        return Success((out, next_key))

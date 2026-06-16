"""Deployment-admin table (``make reset-iam`` / empty-deployment bootstrap only)."""

from __future__ import annotations

import aioboto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from pydantic import ValidationError

from iam_service.core.errors import AppError
from iam_service.core.results import Result, Success
from iam_service.database.dynamo_sdk_errors import failure_from_dynamo_sdk
from iam_service.database.models.records import DeploymentAdminRecord


class DeploymentAdminRepository:
    """CRUD for ``DeploymentAdminRecord`` (GSI ``deployment-admin-email`` on ``email``)."""

    __slots__ = ("_session", "_region", "_endpoint_url", "_table_name", "_email_gsi")

    def __init__(
        self,
        *,
        session: aioboto3.Session,
        region: str,
        endpoint_url: str | None,
        table_name: str,
        email_gsi_name: str = "deployment-admin-email",
    ) -> None:
        self._session = session
        self._region = region
        self._endpoint_url = endpoint_url
        self._table_name = table_name
        self._email_gsi = email_gsi_name

    async def put(self, record: DeploymentAdminRecord) -> Result[None, AppError]:
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                await table.put_item(Item=record.model_dump())
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk("DynamoDB put_item failed for deployment admin.", exc)
        return Success(None)

    async def find_active_by_email(
        self,
        *,
        email: str,
    ) -> Result[DeploymentAdminRecord | None, AppError]:
        if not email.strip():
            return Success(None)
        try:
            async with self._session.resource(
                "dynamodb",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ) as dynamo:
                table = await dynamo.Table(self._table_name)
                resp = await table.query(
                    IndexName=self._email_gsi,
                    KeyConditionExpression=Key("email").eq(email.strip()),
                )
        except (OSError, ClientError) as exc:
            return failure_from_dynamo_sdk(
                "DynamoDB query failed for deployment admin by email.",
                exc,
            )
        for raw in resp.get("Items", []):
            try:
                rec = DeploymentAdminRecord.model_validate(raw)
            except ValidationError:
                continue
            if rec.is_deleted or not rec.enabled:
                continue
            return Success(rec)
        return Success(None)

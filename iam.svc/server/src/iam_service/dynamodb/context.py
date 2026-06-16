"""DynamoDB session lifecycle for repositories."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError

from iam_service.core.app_config import AppConfig
from iam_service.core.app_config_store import app_config as get_app_config
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.util.aws_env import aws_region

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DynamoContext:
    """Holds aioboto3 session and resolved AWS SDK parameters."""

    session: aioboto3.Session
    region: str
    endpoint_url: str | None

    @staticmethod
    def from_app_config(config: AppConfig | None = None) -> DynamoContext:
        """Build a context from validated application config (singleton when omitted)."""
        cfg = config or get_app_config()
        endpoint = cfg.dynamodb.endpoint_url.strip()
        region = aws_region(config_fallback=cfg.dynamodb.region)
        return DynamoContext(
            session=aioboto3.Session(region_name=region),
            region=region,
            endpoint_url=endpoint if endpoint else None,
        )

    async def check_conn(self) -> Result[None, AppError]:
        """Verify DynamoDB API access (``ListTables`` with ``Limit=1``)."""
        try:
            async with self.session.client(
                "dynamodb",
                region_name=self.region,
                endpoint_url=self.endpoint_url,
            ) as client:
                await client.list_tables(Limit=1)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            logger.warning("dynamodb check_conn client_error code=%s", code)
            return Failure(
                AppError(
                    code=ErrorCodes.UPSTREAM,
                    message="DynamoDB connectivity check failed.",
                    detail=str(exc),
                ),
            )
        except (BotoCoreError, OSError) as exc:
            logger.warning("dynamodb check_conn failed: %s", exc)
            return Failure(
                AppError(
                    code=ErrorCodes.UPSTREAM,
                    message="Could not reach DynamoDB for connectivity check.",
                    detail=str(exc),
                ),
            )
        return Success(None)

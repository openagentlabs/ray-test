"""Startup validation (configuration, AWS, DynamoDB connectivity)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from iam_service.core.app_config import AppConfig
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.dynamodb.context import DynamoContext
from iam_service.util.aws_env import (
    aws_credentials_available,
    aws_region,
)

logger = logging.getLogger(__name__)

DATABASE_RETRY_ATTEMPTS = 3
DATABASE_RETRY_DELAY_SEC = 1.0


async def validate(app_config: AppConfig) -> Result[None, AppError]:
    region = aws_region(config_fallback=app_config.dynamodb.region)
    if not region:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="AWS region is required (AWS_DEFAULT_REGION or AWS_REGION).",
                detail=None,
            ),
        )
    if not aws_credentials_available():
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="AWS credentials must be set in the environment or via EKS IRSA.",
                detail=None,
            ),
        )
    if not app_config.dynamodb.tables.logins.strip():
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="DynamoDB logins table name must be configured.",
                detail=None,
            ),
        )
    logger.info("startup validate: DynamoDB region=%s credentials present", region)
    return Success(None)


async def validate_database(dynamo: DynamoContext) -> Result[None, AppError]:
    return await _validate_database_with_retries(dynamo.check_conn)


async def _validate_database_with_retries(
    check_conn: Callable[[], Awaitable[Result[None, AppError]]],
) -> Result[None, AppError]:
    last: AppError | None = None
    for attempt in range(1, DATABASE_RETRY_ATTEMPTS + 1):
        logger.info("database validation attempt %s/%s", attempt, DATABASE_RETRY_ATTEMPTS)
        result = await check_conn()
        if isinstance(result, Success):
            logger.info(
                "database validation attempt %s/%s succeeded",
                attempt,
                DATABASE_RETRY_ATTEMPTS,
            )
            return result
        last = result.failure()
        logger.warning(
            "database validation attempt %s/%s failed: %s",
            attempt,
            DATABASE_RETRY_ATTEMPTS,
            last.message,
        )
        if attempt < DATABASE_RETRY_ATTEMPTS:
            await asyncio.sleep(DATABASE_RETRY_DELAY_SEC)
    assert last is not None
    logger.error(
        "database validation failed after %s attempts: %s",
        DATABASE_RETRY_ATTEMPTS,
        last.message,
    )
    return Failure(last)

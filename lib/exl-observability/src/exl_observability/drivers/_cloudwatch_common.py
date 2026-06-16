"""Shared CloudWatch Logs helpers for async export."""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

from botocore.exceptions import ClientError


async def ensure_log_stream(
    *,
    client: Any,
    log_group_name: str,
    log_stream_name: str,
) -> None:
    """Create the log stream if it does not exist."""

    def _create() -> None:
        try:
            client.create_log_stream(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
            )
        except ClientError as err:
            code = err.response.get("Error", {}).get("Code", "")
            if code != "ResourceAlreadyExistsException":
                raise

    await asyncio.to_thread(_create)


async def put_log_events(
    *,
    client: Any,
    log_group_name: str,
    log_stream_name: str,
    events: list[dict[str, Any]],
    sequence_token: str | None,
) -> str | None:
    """Put a batch of log events; returns the next sequence token."""

    def _put() -> str | None:
        kwargs: dict[str, Any] = {
            "logGroupName": log_group_name,
            "logStreamName": log_stream_name,
            "logEvents": events,
        }
        if sequence_token is not None:
            kwargs["sequenceToken"] = sequence_token
        response = client.put_log_events(**kwargs)
        return response.get("nextSequenceToken")

    return await asyncio.to_thread(_put)


def build_stream_name(*, prefix: str) -> str:
    """Build a unique log stream name for this process."""
    return f"{prefix}-{os.getpid()}-{uuid.uuid4().hex[:8]}"

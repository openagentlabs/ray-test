"""Shared DynamoDB mocks for iam_service database tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class AsyncTableFactory:
    async def __call__(self, _name: str) -> AsyncMock:
        return self._table

    def __init__(self, table: AsyncMock) -> None:
        self._table = table


@asynccontextmanager
async def _dynamo_resource_cm(dynamo: MagicMock) -> AsyncIterator[MagicMock]:
    yield dynamo


@pytest.fixture
def dynamo_table() -> AsyncMock:
    table = AsyncMock()
    table.get_item = AsyncMock(return_value={})
    table.put_item = AsyncMock(return_value={})
    table.query = AsyncMock(return_value={"Items": []})
    table.scan = AsyncMock(return_value={"Items": [], "LastEvaluatedKey": None})
    return table


@pytest.fixture
def boto_session(dynamo_table: AsyncMock) -> tuple[MagicMock, AsyncMock]:
    dynamo = MagicMock()
    dynamo.Table = AsyncTableFactory(dynamo_table)
    session = MagicMock()
    session.resource = MagicMock(side_effect=lambda *_a, **_k: _dynamo_resource_cm(dynamo))
    return session, dynamo_table


@pytest.fixture
def repo_kwargs(boto_session: tuple[MagicMock, AsyncMock]) -> dict[str, Any]:
    session, _table = boto_session
    return {
        "session": session,
        "region": "us-east-1",
        "endpoint_url": None,
        "table_name": "iam-test-table",
    }

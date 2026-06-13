"""Shared asyncpg mocks for solutions_service database tests."""

from __future__ import annotations

from types import TracebackType
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class _AcquireCtx:
    """Mimics ``async with pool.acquire() as conn``."""

    def __init__(self, conn: AsyncMock) -> None:
        self._conn = conn

    async def __aenter__(self) -> AsyncMock:
        return self._conn

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False


@pytest.fixture
def pg_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock(return_value="")
    return conn


@pytest.fixture
def pg_pool(pg_conn: AsyncMock) -> MagicMock:
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=lambda: _AcquireCtx(pg_conn))
    return pool


@pytest.fixture
def repo_kwargs(pg_pool: MagicMock) -> dict[str, Any]:
    return {
        "pool": pg_pool,
        "table_name": "pm_solution_documents",
    }

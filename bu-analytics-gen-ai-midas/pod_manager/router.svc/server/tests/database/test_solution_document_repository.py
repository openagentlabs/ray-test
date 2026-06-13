"""SolutionDocumentRepository — document metadata table (Postgres)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from returns.result import Failure, Success

from solutions_service.core.errors import ErrorCodes
from solutions_service.database.repositories.solution_document_repository import (
    SolutionDocumentRepository,
)

DOC_ID = "423e4567-e89b-12d3-a456-426614174000"
SOLUTION_ID = "423e4567-e89b-12d3-a456-426614174001"


def _doc_row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": DOC_ID,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "deleted_at": "",
        "is_deleted": False,
        "solution_id": SOLUTION_ID,
        "name": "spec.pdf",
        "description": "",
        "path": "/files/spec.pdf",
    }
    base.update(overrides)
    return base


@pytest.fixture
def repo(repo_kwargs: dict[str, object]) -> SolutionDocumentRepository:
    return SolutionDocumentRepository(**repo_kwargs)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_by_id_hides_deleted_by_default(
    repo: SolutionDocumentRepository,
    pg_conn: AsyncMock,
) -> None:
    pg_conn.fetchrow = AsyncMock(return_value=_doc_row(is_deleted=True, deleted_at="t"))

    result = await repo.get_by_id(item_id=DOC_ID, include_deleted=False)

    assert isinstance(result, Success)
    assert result.unwrap() is None


@pytest.mark.asyncio
async def test_get_by_id_include_deleted_returns_row(
    repo: SolutionDocumentRepository,
    pg_conn: AsyncMock,
) -> None:
    pg_conn.fetchrow = AsyncMock(return_value=_doc_row(is_deleted=True, deleted_at="t"))

    result = await repo.get_by_id(item_id=DOC_ID, include_deleted=True)

    assert isinstance(result, Success)
    assert result.unwrap() is not None
    assert result.unwrap().is_deleted is True


@pytest.mark.asyncio
async def test_soft_delete_updates_flags(
    repo: SolutionDocumentRepository,
    pg_conn: AsyncMock,
) -> None:
    pg_conn.fetchrow = AsyncMock(return_value=_doc_row())

    result = await repo.soft_delete(item_id=DOC_ID, now_iso="2026-01-02T00:00:00Z")

    assert isinstance(result, Success)
    updated = result.unwrap()
    assert updated is not None
    assert updated.is_deleted is True
    assert updated.deleted_at == "2026-01-02T00:00:00Z"
    pg_conn.execute.assert_awaited()


@pytest.mark.asyncio
async def test_list_by_solution_excludes_deleted_and_orders(
    repo: SolutionDocumentRepository,
    pg_conn: AsyncMock,
) -> None:
    pg_conn.fetch = AsyncMock(
        return_value=[
            _doc_row(updated_at="2026-01-03T00:00:00Z"),
            _doc_row(id="423e4567-e89b-12d3-a456-426614174002", updated_at="2026-01-01T00:00:00Z"),
        ],
    )

    result = await repo.list_by_solution(solution_id=SOLUTION_ID, include_deleted=False)

    assert isinstance(result, Success)
    rows = result.unwrap()
    assert rows[0].updated_at == "2026-01-03T00:00:00Z"
    query = pg_conn.fetch.await_args.args[0]
    assert "ORDER BY updated_at DESC" in query
    assert "is_deleted = FALSE" in query


@pytest.mark.asyncio
async def test_count_by_solution_returns_total(
    repo: SolutionDocumentRepository,
    pg_conn: AsyncMock,
) -> None:
    pg_conn.fetchval = AsyncMock(return_value=3)

    result = await repo.count_by_solution(solution_id=SOLUTION_ID, include_deleted=False)

    assert isinstance(result, Success)
    assert result.unwrap() == 3


@pytest.mark.asyncio
async def test_list_by_solution_invalid_item_returns_failure(
    repo: SolutionDocumentRepository,
    pg_conn: AsyncMock,
) -> None:
    pg_conn.fetch = AsyncMock(return_value=[{"id": DOC_ID}])

    result = await repo.list_by_solution(solution_id=SOLUTION_ID, include_deleted=False)

    assert isinstance(result, Failure)
    assert result.failure().code == ErrorCodes.INTERNAL

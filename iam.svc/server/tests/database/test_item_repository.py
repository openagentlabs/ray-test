"""ItemRepository — generic DynamoDB catalog CRUD."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from returns.result import Failure, Success

from iam_service.core.errors import ErrorCodes
from iam_service.database.models.records import UserTypeRecord
from iam_service.database.repositories.item_repository import ItemRepository


def _user_type_item(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "323e4567-e89b-12d3-a456-426614174002",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "deleted_at": "",
        "is_deleted": False,
        "enabled": True,
        "code": "owner",
        "display_name": "Owner",
        "data_json": "{}",
    }
    base.update(overrides)
    return base


@pytest.fixture
def repo(repo_kwargs: dict[str, object]) -> ItemRepository[UserTypeRecord]:
    return ItemRepository(model=UserTypeRecord, **repo_kwargs)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing(
    repo: ItemRepository[UserTypeRecord],
    dynamo_table: AsyncMock,
) -> None:
    dynamo_table.get_item = AsyncMock(return_value={})

    result = await repo.get_by_id(item_id="missing", include_deleted=False)

    assert isinstance(result, Success)
    assert result.unwrap() is None


@pytest.mark.asyncio
async def test_get_by_id_hides_soft_deleted(
    repo: ItemRepository[UserTypeRecord],
    dynamo_table: AsyncMock,
) -> None:
    dynamo_table.get_item = AsyncMock(
        return_value={"Item": _user_type_item(is_deleted=True, deleted_at="t")}
    )

    result = await repo.get_by_id(
        item_id="323e4567-e89b-12d3-a456-426614174002",
        include_deleted=False,
    )

    assert isinstance(result, Success)
    assert result.unwrap() is None


@pytest.mark.asyncio
async def test_put_writes_record(
    repo: ItemRepository[UserTypeRecord],
    dynamo_table: AsyncMock,
) -> None:
    record = UserTypeRecord.model_validate(_user_type_item())

    result = await repo.put(record)

    assert isinstance(result, Success)
    dynamo_table.put_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_soft_delete_marks_deleted(
    repo: ItemRepository[UserTypeRecord],
    dynamo_table: AsyncMock,
) -> None:
    dynamo_table.get_item = AsyncMock(return_value={"Item": _user_type_item()})

    result = await repo.soft_delete(
        item_id="323e4567-e89b-12d3-a456-426614174002",
        now_iso="2026-01-02T00:00:00Z",
    )

    assert isinstance(result, Success)
    updated = result.unwrap()
    assert updated is not None
    assert updated.is_deleted is True


@pytest.mark.asyncio
async def test_scan_page_returns_items_and_token(
    repo: ItemRepository[UserTypeRecord],
    dynamo_table: AsyncMock,
) -> None:
    dynamo_table.scan = AsyncMock(
        return_value={
            "Items": [_user_type_item()],
            "LastEvaluatedKey": {"id": "323e4567-e89b-12d3-a456-426614174002"},
        },
    )

    result = await repo.scan_page(include_deleted=False, page_size=10, page_token="")

    assert isinstance(result, Success)
    items, token = result.unwrap()
    assert len(items) == 1
    assert token != ""


@pytest.mark.asyncio
async def test_scan_page_skips_invalid_rows(
    repo: ItemRepository[UserTypeRecord],
    dynamo_table: AsyncMock,
) -> None:
    dynamo_table.scan = AsyncMock(return_value={"Items": [{"id": "bad"}], "LastEvaluatedKey": None})

    result = await repo.scan_page(include_deleted=True, page_size=5, page_token="")

    assert isinstance(result, Success)
    assert result.unwrap()[0] == []


@pytest.mark.asyncio
async def test_get_by_id_invalid_stored_shape_returns_failure(
    repo: ItemRepository[UserTypeRecord],
    dynamo_table: AsyncMock,
) -> None:
    dynamo_table.get_item = AsyncMock(return_value={"Item": {"id": "x"}})

    result = await repo.get_by_id(item_id="x", include_deleted=True)

    assert isinstance(result, Failure)
    assert result.failure().code == ErrorCodes.INTERNAL

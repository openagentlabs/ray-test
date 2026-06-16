"""User persistence port."""

from __future__ import annotations

from typing import Protocol

from iam_service.core.errors import AppError
from iam_service.core.results import Result
from iam_service.domain.entities import User


class UserPort(Protocol):
    """Contract for user storage — implemented by ``UserRepository``."""

    async def get_by_id(
        self,
        *,
        user_id: str,
        include_deleted: bool,
    ) -> Result[User | None, AppError]:
        ...

    async def put(self, record: User) -> Result[None, AppError]:
        ...

    async def soft_delete(self, *, user_id: str) -> Result[None, AppError]:
        ...

    async def query_by_account(
        self,
        *,
        account_id: str,
        include_deleted: bool,
        page_size: int,
        page_token: str,
    ) -> Result[tuple[list[User], str], AppError]:
        ...

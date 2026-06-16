"""Login persistence port."""

from __future__ import annotations

from typing import Protocol

from iam_service.core.errors import AppError
from iam_service.core.results import Result
from iam_service.domain.entities import Login


class LoginPort(Protocol):
    """Contract for login storage — implemented by ``LoginRepository``."""

    async def get_by_id(
        self,
        *,
        login_id: str,
        include_deleted: bool,
    ) -> Result[Login | None, AppError]:
        ...

    async def put(self, record: Login) -> Result[None, AppError]:
        ...

    async def soft_delete(self, *, login_id: str) -> Result[None, AppError]:
        ...

    async def query_by_user(
        self,
        *,
        user_id: str,
        include_deleted: bool,
        page_size: int,
        page_token: str,
    ) -> Result[tuple[list[Login], str], AppError]:
        ...

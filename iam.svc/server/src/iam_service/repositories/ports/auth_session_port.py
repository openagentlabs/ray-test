"""Auth session persistence port."""

from __future__ import annotations

from typing import Protocol

from iam_service.core.errors import AppError
from iam_service.core.results import Result
from iam_service.domain.entities import AuthSession


class AuthSessionPort(Protocol):
    """Contract for JWT refresh sessions — implemented by ``AuthSessionRepository``."""

    async def get_by_id(
        self,
        *,
        session_id: str,
        include_deleted: bool,
    ) -> Result[AuthSession | None, AppError]:
        ...

    async def put(self, record: AuthSession) -> Result[None, AppError]:
        ...

    async def soft_delete(self, *, session_id: str) -> Result[None, AppError]:
        ...

"""Invite persistence port."""

from __future__ import annotations

from typing import Protocol

from iam_service.core.errors import AppError
from iam_service.core.results import Result
from iam_service.domain.entities import Invite


class InvitePort(Protocol):
    """Contract for invite storage — implemented by ``InviteRepository``."""

    async def get_by_id(
        self,
        *,
        invite_id: str,
        include_deleted: bool,
    ) -> Result[Invite | None, AppError]:
        ...

    async def put(self, record: Invite) -> Result[None, AppError]:
        ...

    async def soft_delete(self, *, invite_id: str) -> Result[None, AppError]:
        ...

    async def scan_page(
        self,
        *,
        include_deleted: bool,
        page_size: int,
        page_token: str,
    ) -> Result[tuple[list[Invite], str], AppError]:
        ...

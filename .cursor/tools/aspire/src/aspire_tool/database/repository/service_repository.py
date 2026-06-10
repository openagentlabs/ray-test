"""Persistence operations for ``registered_services`` (async SQLAlchemy)."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from aspire_tool.core.errors import AppError, ErrorCodes
from aspire_tool.core.results import Failure, Result, Success
from aspire_tool.database.sqlalchemy.models import ServiceRow


def _slug_id(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    if len(cleaned) == 0:
        cleaned = "service"
    return f"{cleaned}-{uuid.uuid4().hex[:10]}"


def validate_executable_path(path: Path) -> Result[Path, AppError]:
    """Ensure ``path`` exists, is a file, and is executable on this OS."""
    try:
        resolved = path.expanduser().resolve(strict=False)
    except OSError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Could not resolve executable path.",
                detail=str(exc),
            ),
        )
    if not resolved.exists():
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Executable path does not exist.",
                detail=str(resolved),
            ),
        )
    if not resolved.is_file():
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Executable path is not a file.",
                detail=str(resolved),
            ),
        )
    if os.name == "nt":
        if not os.access(resolved, os.X_OK):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="File is not executable on this platform.",
                    detail=str(resolved),
                ),
            )
    else:
        if not os.access(resolved, os.X_OK):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="File is not executable (missing execute permission).",
                    detail=str(resolved),
                ),
            )
    return Success(resolved)


def infer_kind(executable: Path) -> str:
    """Infer ``kind`` column from extension / shebang (best-effort)."""
    suffix = executable.suffix.lower()
    if suffix in {".py", ".pyw"}:
        return "python"
    if suffix in {".js", ".mjs", ".cjs", ".ts"}:
        return "node"
    try:
        head = executable.read_text(encoding="utf-8", errors="ignore")[:120]
    except OSError:
        return "shell"
    if "python" in head.lower():
        return "python"
    if "node" in head.lower():
        return "node"
    return "shell"


class ServiceRepository:
    """Repository pattern on top of the ORM (no inheritance beyond composition)."""

    __slots__ = ()

    @staticmethod
    async def list_all(session: AsyncSession) -> Result[list[ServiceRow], AppError]:
        try:
            result = await session.execute(
                select(ServiceRow).order_by(ServiceRow.start_order.asc(), ServiceRow.id.asc()),
            )
            return Success(list(result.scalars().all()))
        except SQLAlchemyError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Failed to list services.",
                    detail=str(exc),
                ),
            )

    @staticmethod
    async def next_start_order(session: AsyncSession) -> Result[int, AppError]:
        try:
            value = await session.scalar(select(func.max(ServiceRow.start_order)))
            if value is None:
                return Success(0)
            return Success(int(value) + 1)
        except SQLAlchemyError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Failed to compute next start order.",
                    detail=str(exc),
                ),
            )

    @staticmethod
    async def add_executable_service(
        session: AsyncSession,
        *,
        executable: Path,
        display_name: str,
        description: str,
    ) -> Result[ServiceRow, AppError]:
        validated = validate_executable_path(executable)
        if isinstance(validated, Failure):
            return validated
        exe = validated.unwrap()

        order_r = await ServiceRepository.next_start_order(session)
        if isinstance(order_r, Failure):
            return order_r
        start_order = order_r.unwrap()

        cwd = Path.cwd()
        try:
            workdir = str(exe.parent.resolve().relative_to(cwd.resolve()))
        except ValueError:
            workdir = "."

        row = ServiceRow(
            id=_slug_id(display_name),
            display_name=display_name.strip(),
            role="service",
            kind=infer_kind(exe),
            workdir_relative=workdir,
            command=str(exe.resolve()),
            args_json=json.dumps([]),
            port=None,
            health_kind="none",
            health_target=None,
            description=description.strip(),
            start_order=start_order,
            enabled=True,
            auto_start_with_home=False,
            env_json=None,
        )
        try:
            session.add(row)
            await session.flush()
            await session.refresh(row)
        except SQLAlchemyError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Failed to insert service row.",
                    detail=str(exc),
                ),
            )
        return Success(row)

    @staticmethod
    async def delete_by_id(session: AsyncSession, service_id: str) -> Result[None, AppError]:
        try:
            row = await session.get(ServiceRow, service_id)
            if row is None:
                return Failure(
                    AppError(
                        code=ErrorCodes.NOT_FOUND,
                        message="Service id not found.",
                        detail=service_id,
                    ),
                )
            await session.delete(row)
        except SQLAlchemyError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Failed to delete service row.",
                    detail=str(exc),
                ),
            )
        return Success(None)

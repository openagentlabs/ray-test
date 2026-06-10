"""Async engine lifecycle for the service registry SQLite file."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from aspire_tool.core.errors import AppError, ErrorCodes
from aspire_tool.core.results import Failure, Result, Success
from aspire_tool.database.context_config import DatabaseContextConfig
from aspire_tool.database.migrations import (
    ensure_registered_services_columns_async,
    ensure_registered_services_columns_sync,
)
from aspire_tool.database.schema import SERVICE_REGISTRY_DDL


class DatabaseContext:
    """Owns async engine + session factory (composition; no deep inheritance)."""

    __slots__ = ("_engine", "_session_factory")

    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._engine = engine
        self._session_factory = session_factory

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    @staticmethod
    def check_database_file(path: Path) -> Result[None, AppError]:
        """Return ``Success`` if the SQLite file exists and is a regular file."""
        try:
            resolved = path.resolve()
        except OSError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Could not resolve database path.",
                    detail=str(exc),
                ),
            )
        if not resolved.exists():
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Database file does not exist.",
                    detail=str(resolved),
                ),
            )
        if not resolved.is_file():
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Database path is not a file.",
                    detail=str(resolved),
                ),
            )
        return Success(None)

    @staticmethod
    def create_database_file(path: Path) -> Result[None, AppError]:
        """Create parent directories and apply DDL using the stdlib sqlite3 driver."""
        resolved = path.resolve()
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Could not create database parent directory.",
                    detail=str(exc),
                ),
            )
        try:
            conn = sqlite3.connect(str(resolved))
            try:
                conn.executescript(SERVICE_REGISTRY_DDL)
                ensure_registered_services_columns_sync(conn)
                conn.commit()
            finally:
                conn.close()
        except OSError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Could not create SQLite database file.",
                    detail=str(exc),
                ),
            )
        except sqlite3.Error as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Could not initialize SQLite schema.",
                    detail=str(exc),
                ),
            )
        return Success(None)

    @staticmethod
    async def open(config: DatabaseContextConfig) -> Result[DatabaseContext, AppError]:
        """Open engine + session factory; ensures parent exists and DB is reachable."""
        resolved = config.sqlite_path.resolve()
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Could not create database parent directory.",
                    detail=str(exc),
                ),
            )

        url = f"sqlite+aiosqlite:///{resolved}"
        engine = create_async_engine(url, echo=False)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            async with engine.begin() as conn:
                await ensure_registered_services_columns_async(conn)
        except OSError as exc:
            await engine.dispose()
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Database engine ping failed.",
                    detail=str(exc),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            await engine.dispose()
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Database engine ping failed.",
                    detail=str(exc),
                ),
            )

        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        return Success(DatabaseContext(engine=engine, session_factory=factory))

    async def dispose(self) -> None:
        await self._engine.dispose()

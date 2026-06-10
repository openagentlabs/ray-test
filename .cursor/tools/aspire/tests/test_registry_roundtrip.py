"""Async persistence tests against a temporary SQLite registry file."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from returns.result import Failure, Success

from aspire_tool.database.context import DatabaseContext
from aspire_tool.database.context_config import DatabaseContextConfig
from aspire_tool.database.repository.service_repository import ServiceRepository


@pytest.fixture
def registry_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db = tmp_path / "svc.sqlite"
    monkeypatch.setenv("ASPIRE_REGISTRY_DB", str(db))
    return db


@pytest.fixture
def executable(tmp_path: Path) -> Path:
    if os.name == "nt":
        script = tmp_path / "tool.cmd"
        script.write_text("@echo off\r\n", encoding="utf-8")
    else:
        script = tmp_path / "tool.sh"
        script.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IRUSR)
    return script


@pytest.mark.asyncio
async def test_add_list_delete_roundtrip(registry_db: Path, executable: Path) -> None:
    config = DatabaseContextConfig.from_environment()
    created = DatabaseContext.create_database_file(config.sqlite_path)
    assert isinstance(created, Success)

    opened = await DatabaseContext.open(config)
    assert isinstance(opened, Success)
    ctx = opened.unwrap()
    try:
        async with ctx.session_factory() as session:
            async with session.begin():
                added = await ServiceRepository.add_executable_service(
                    session,
                    executable=executable,
                    display_name="Roundtrip Service",
                    description="test",
                )
        assert isinstance(added, Success)
        service_id = added.unwrap().id

        async with ctx.session_factory() as session:
            async with session.begin():
                listed = await ServiceRepository.list_all(session)
        assert isinstance(listed, Success)
        assert any(row.id == service_id for row in listed.unwrap())

        async with ctx.session_factory() as session:
            async with session.begin():
                deleted = await ServiceRepository.delete_by_id(session, service_id)
        assert isinstance(deleted, Success)

        async with ctx.session_factory() as session:
            async with session.begin():
                listed_after = await ServiceRepository.list_all(session)
        assert isinstance(listed_after, Success)
        assert all(row.id != service_id for row in listed_after.unwrap())
    finally:
        await ctx.dispose()


@pytest.mark.asyncio
async def test_delete_missing_returns_not_found(registry_db: Path) -> None:
    config = DatabaseContextConfig.from_environment()
    assert isinstance(DatabaseContext.create_database_file(config.sqlite_path), Success)
    opened = await DatabaseContext.open(config)
    assert isinstance(opened, Success)
    ctx = opened.unwrap()
    try:
        async with ctx.session_factory() as session:
            async with session.begin():
                deleted = await ServiceRepository.delete_by_id(session, "missing-id")
        assert isinstance(deleted, Failure)
    finally:
        await ctx.dispose()

"""Typer CLI for the Aspire service registry tool."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import NoReturn

import typer
from returns.result import Failure

from aspire_tool.core.errors import AppError, ErrorCodes
from aspire_tool.database.context import DatabaseContext
from aspire_tool.database.context_config import DatabaseContextConfig
from aspire_tool.database.repository.service_repository import ServiceRepository
from aspire_tool.manifest.spec import ServiceRecordOut, build_tool_manifest_json


def _die_json_error(err: AppError, *, code: int = 2) -> NoReturn:
    payload = {"error": err.code, "message": err.message, "detail": err.detail}
    print(json.dumps(payload, indent=2), file=sys.stderr)
    raise typer.Exit(code)


def _mode_flags(add: bool, list_rows: bool, remove: bool) -> int:
    return int(add) + int(list_rows) + int(remove)


async def _ensure_db(config: DatabaseContextConfig) -> DatabaseContext:
    check = DatabaseContext.check_database_file(config.sqlite_path)
    if isinstance(check, Failure):
        created = DatabaseContext.create_database_file(config.sqlite_path)
        if isinstance(created, Failure):
            _die_json_error(created.failure())
    opened = await DatabaseContext.open(config)
    if isinstance(opened, Failure):
        _die_json_error(opened.failure())
    return opened.unwrap()


def _service_row_to_model(row: object) -> ServiceRecordOut:
    return ServiceRecordOut.model_validate(row, from_attributes=True)


async def _cmd_list(ctx: DatabaseContext) -> None:
    async with ctx.session_factory() as session:
        async with session.begin():
            listed = await ServiceRepository.list_all(session)
    if isinstance(listed, Failure):
        _die_json_error(listed.failure())
    services = [_service_row_to_model(r).model_dump() for r in listed.unwrap()]
    print(json.dumps({"services": services}, indent=2))


async def _cmd_add(
    ctx: DatabaseContext,
    *,
    path: str,
    name: str,
    description: str,
) -> None:
    async with ctx.session_factory() as session:
        async with session.begin():
            added = await ServiceRepository.add_executable_service(
                session,
                executable=Path(path),
                display_name=name,
                description=description,
            )
    if isinstance(added, Failure):
        _die_json_error(added.failure())
    print(json.dumps(_service_row_to_model(added.unwrap()).model_dump(), indent=2))


async def _cmd_remove(ctx: DatabaseContext, *, service_id: str) -> None:
    async with ctx.session_factory() as session:
        async with session.begin():
            deleted = await ServiceRepository.delete_by_id(session, service_id)
    if isinstance(deleted, Failure):
        err = deleted.failure()
        if err.code == ErrorCodes.NOT_FOUND:
            _die_json_error(err, code=1)
        _die_json_error(err)
    print(json.dumps({"deleted": service_id}, indent=2))


def main() -> None:
    typer.run(_main)


def _main(
    add: bool = typer.Option(False, "-a", "--add", help="Add a service executable."),
    list_rows: bool = typer.Option(False, "-l", "--list", help="List all services."),
    remove: bool = typer.Option(False, "-r", "--remove", help="Remove a service by id."),
    path: str | None = typer.Option(
        None,
        "-p",
        "--path",
        help="Executable path (required with -a).",
    ),
    name: str | None = typer.Option(None, "-n", "--name", help="Display name (required with -a)."),
    description: str | None = typer.Option(
        None,
        "-d",
        "--description",
        help="Description (optional with -a; defaults to empty string).",
    ),
    service_id: str | None = typer.Option(None, "-i", "--id", help="Row id (required with -r)."),
) -> None:
    modes = _mode_flags(add, list_rows, remove)
    if modes > 1:
        raise typer.BadParameter("Use only one of: -a/--add, -l/--list, -r/--remove.")

    if modes == 0:
        print(build_tool_manifest_json())
        raise typer.Exit(0)

    config = DatabaseContextConfig.from_environment()

    if list_rows:

        async def _run() -> None:
            ctx = await _ensure_db(config)
            await _cmd_list(ctx)
            await ctx.dispose()

        asyncio.run(_run())
        return

    if add:
        if path is None or name is None:
            raise typer.BadParameter("`-a` requires `-p/--path` and `-n/--name`.")
        desc = "" if description is None else description

        async def _run_add() -> None:
            ctx = await _ensure_db(config)
            await _cmd_add(ctx, path=path, name=name, description=desc)
            await ctx.dispose()

        asyncio.run(_run_add())
        return

    if remove:
        if service_id is None:
            raise typer.BadParameter("`-r` requires `-i/--id`.")

        async def _run_remove() -> None:
            ctx = await _ensure_db(config)
            await _cmd_remove(ctx, service_id=service_id)
            await ctx.dispose()

        asyncio.run(_run_remove())
        return

    raise typer.BadParameter("Unreachable mode.")

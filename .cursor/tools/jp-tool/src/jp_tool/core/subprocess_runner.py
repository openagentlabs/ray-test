"""Subprocess helpers returning ``JpResult``."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jp_tool.core.errors import AppError, ErrorCodes
from jp_tool.core.option import Option
from jp_tool.core.results import Failure, Success
from jp_tool.core.types import JpResult


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Captured subprocess output."""

    returncode: int
    stdout: str
    stderr: str


def run_command(
    cmd: list[str],
    *,
    cwd: Path,
    env: Option[dict[str, str]] = None,
    capture: bool = True,
) -> JpResult[CommandResult]:
    """Run a subprocess and return structured output without raising."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=capture,
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.SUBPROCESS,
                message="Command not found.",
                detail=f"{' '.join(cmd)} — {exc}",
            ),
        )

    return Success(
        CommandResult(
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        ),
    )


def run_command_checked(
    cmd: list[str],
    *,
    cwd: Path,
    env: Option[dict[str, str]] = None,
) -> JpResult[CommandResult]:
    """Run a subprocess; map non-zero exit codes to ``Failure``."""
    result = run_command(cmd, cwd=cwd, env=env, capture=True)
    if isinstance(result, Failure):
        return result
    proc = result.unwrap()
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        return Failure(
            AppError(
                code=ErrorCodes.SUBPROCESS,
                message="Command failed.",
                detail=f"+ {' '.join(cmd)}\n{detail}",
            ),
        )
    return Success(proc)


def run_json_command(
    cmd: list[str],
    *,
    cwd: Path,
    env: Option[dict[str, str]] = None,
) -> JpResult[Any]:
    """Run a command expected to emit JSON on stdout."""
    checked = run_command_checked(cmd, cwd=cwd, env=env)
    if isinstance(checked, Failure):
        return checked
    stdout = checked.unwrap().stdout.strip() or "{}"
    try:
        return Success(json.loads(stdout))
    except json.JSONDecodeError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.SUBPROCESS,
                message="Command did not return valid JSON.",
                detail=str(exc),
            ),
        )

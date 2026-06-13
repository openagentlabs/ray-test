"""Shared CLI output helpers for action handlers."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import NoReturn

import typer
from returns.result import Failure

from tf_tool.core.errors import AppError
from tf_tool.core.operation_ui import get_session, run_if_session
from tf_tool.core.types import TextResult


class _ActionFailure(Exception):
    def __init__(self, err: AppError) -> None:
        self.err = err
        super().__init__(err.message)


def emit_result(result: TextResult) -> None:
    """Print a successful action result or exit with a structured JSON error."""
    if isinstance(result, Failure):
        die_json_error(result.failure())
    payload = result.unwrap()
    session = get_session()
    if session is not None:
        session.replay_text(payload, kind="result")
    print(payload)


def emit_action(
    fn: Callable[[], TextResult],
    *,
    operation: str,
    command: str,
) -> None:
    """Run ``fn`` under the operation spinner when UI is active."""
    session = get_session()

    def _execute() -> str:
        outcome = fn()
        if isinstance(outcome, Failure):
            raise _ActionFailure(outcome.failure())
        return outcome.unwrap()

    try:
        if session is None:
            emit_result(fn())
            return
        payload = run_if_session(operation, command, _execute)
        session.replay_success(payload)
        print(payload)
    except _ActionFailure as exc:
        if session is not None:
            session.record_failure(exc.err.message, command=command)
            if exc.err.detail:
                session.replay_text(exc.err.detail, kind="error")
        die_json_error(exc.err)


def die_json_error(err: AppError, *, code: int = 2) -> NoReturn:
    """Write a JSON error payload to stderr and exit."""
    payload = {"error": err.code, "message": err.message, "detail": err.detail}
    session = get_session()
    if session is not None:
        session.record_failure(err.message)
        if err.detail:
            session.replay_text(err.detail, kind="error")
    print(json.dumps(payload, indent=2), file=sys.stderr)
    raise typer.Exit(code)

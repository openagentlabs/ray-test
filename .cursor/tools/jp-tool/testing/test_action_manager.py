"""Unit tests for action registration and dispatch."""

from __future__ import annotations

import json

import typer
from returns.result import Failure, Success

from jp_tool.action_manager.manager import ActionManager
from jp_tool.actions.action_base import ActionBase
from jp_tool.actions.bootstrap import register_all_actions
from jp_tool.actions.doctor import DoctorAction
from jp_tool.core.errors import ErrorCodes
from jp_tool.core.protocols import Action


def test_registered_actions_satisfy_action_protocol() -> None:
    cli = typer.Typer()
    manager = ActionManager(cli)
    registered = register_all_actions(manager)
    assert isinstance(registered, Success)
    for action in manager.list_actions():
        assert isinstance(action, ActionBase)
        assert isinstance(action, Action)


def test_register_and_invoke_doctor() -> None:
    cli = typer.Typer()
    manager = ActionManager(cli)
    registered = manager.register(DoctorAction())
    assert isinstance(registered, Success)

    invoked = manager.invoke("doctor")
    assert isinstance(invoked, Success)
    payload = json.loads(invoked.unwrap())
    assert payload["ok"] is True


def test_register_duplicate_name_fails() -> None:
    cli = typer.Typer()
    manager = ActionManager(cli)
    first = manager.register(DoctorAction())
    assert isinstance(first, Success)

    second = manager.register(DoctorAction())
    assert isinstance(second, Failure)
    err = second.failure()
    assert err.code == ErrorCodes.DUPLICATE


def test_invoke_unknown_action_fails() -> None:
    manager = ActionManager(typer.Typer())
    result = manager.invoke("missing")
    assert isinstance(result, Failure)
    err = result.failure()
    assert err.code == ErrorCodes.NOT_FOUND

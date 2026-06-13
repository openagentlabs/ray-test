"""Unit tests for action registration and dispatch."""

from __future__ import annotations

import typer
from returns.result import Failure, Success

from tf_tool.action_manager.manager import ActionManager
from tf_tool.actions.action_base import ActionBase
from tf_tool.actions.helloworld import HelloWorldAction
from tf_tool.core.errors import ErrorCodes
from tf_tool.core.protocols import Action


def test_registered_actions_satisfy_action_protocol() -> None:
    cli = typer.Typer()
    manager = ActionManager(cli)
    registered = manager.register(HelloWorldAction())
    assert isinstance(registered, Success)
    for action in manager.list_actions():
        assert isinstance(action, ActionBase)
        assert isinstance(action, Action)


def test_register_and_invoke_helloworld() -> None:
    cli = typer.Typer()
    manager = ActionManager(cli)
    registered = manager.register(HelloWorldAction())
    assert isinstance(registered, Success)

    invoked = manager.invoke("helloworld", name="Terraform")
    assert isinstance(invoked, Success)
    assert invoked.unwrap() == "Hello, Terraform!"


def test_register_duplicate_name_fails() -> None:
    cli = typer.Typer()
    manager = ActionManager(cli)
    first = manager.register(HelloWorldAction())
    assert isinstance(first, Success)

    second = manager.register(HelloWorldAction())
    assert isinstance(second, Failure)
    err = second.failure()
    assert err.code == ErrorCodes.DUPLICATE


def test_invoke_unknown_action_fails() -> None:
    manager = ActionManager(typer.Typer())
    result = manager.invoke("missing")
    assert isinstance(result, Failure)
    err = result.failure()
    assert err.code == ErrorCodes.NOT_FOUND

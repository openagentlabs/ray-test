"""Tests for action manager registration."""

from __future__ import annotations

import typer
from returns.result import Success

from deploy_to_aws.action_manager.manager import ActionManager
from deploy_to_aws.actions.bootstrap import register_all_actions


def test_register_all_actions() -> None:
    app = typer.Typer()
    manager = ActionManager(app)
    result = register_all_actions(manager)
    assert isinstance(result, Success)
    names = {action.name for action in manager.list_actions()}
    assert names == {"deploy", "post-deploy"}

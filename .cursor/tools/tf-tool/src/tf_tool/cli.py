"""Typer CLI for Terraform helpers."""

from __future__ import annotations

import os
import sys

import typer
from returns.result import Failure

from tf_tool.action_manager.manager import ActionManager
from tf_tool.actions.bootstrap import register_all_actions
from tf_tool.actions.helloworld import HelloWorldAction
from tf_tool.build.gate import emit_build_failure, run_build_gate
from tf_tool.core.agent_help import agent_guide_requested, render_agent_guide
from tf_tool.core.cli_output import die_json_error, emit_result
from tf_tool.core.env_check import EnvCheckReport, run_env_check
from tf_tool.core.errors import AppError
from tf_tool.core.help_text import (
    AGENT_GUIDE_COMMAND_HELP,
    APP_EPILOG,
    APP_HELP,
    OPT_AGENT_HELP,
    OPT_HELLO_NAME,
)
from tf_tool.core.operation_ui import OperationSession, get_session, ui_enabled

_HELP_OPTION_NAMES: list[str] = ["-h", "--help"]

app = typer.Typer(
    name="tf-tool",
    help=APP_HELP,
    epilog=APP_EPILOG,
    no_args_is_help=True,
    add_completion=False,
    invoke_without_command=True,
    context_settings={"help_option_names": _HELP_OPTION_NAMES},
)

action_manager = ActionManager(app)
_actions_bootstrapped = False
_agent_guide_registered = False


class _EnvCheckFailed(Exception):
    def __init__(self, err: AppError) -> None:
        self.err = err
        super().__init__(err.message)


def help_requested(argv: list[str] | None = None) -> bool:
    """Return True when the user asked for standard CLI help."""
    args = sys.argv[1:] if argv is None else argv
    return any(arg in _HELP_OPTION_NAMES for arg in args)


def _print_agent_guide() -> None:
    print(render_agent_guide())


def _register_agent_guide_commands() -> None:
    global _agent_guide_registered
    if _agent_guide_registered:
        return

    def _agent_guide_cmd() -> None:
        _print_agent_guide()

    for command_name in ("agent-guide", "agent-help"):
        app.command(command_name, help=AGENT_GUIDE_COMMAND_HELP)(_agent_guide_cmd)
    _agent_guide_registered = True


@app.callback()
def _app_callback(
    ctx: typer.Context,
    helloworld: bool = typer.Option(
        False,
        HelloWorldAction.FLAG_SHORT,
        HelloWorldAction.FLAG_LONG,
        help=HelloWorldAction.DESCRIPTION,
    ),
    agent_help: bool = typer.Option(
        False,
        "--agent-help",
        help=OPT_AGENT_HELP,
    ),
    name: str = typer.Option("World", "-n", "--name", help=OPT_HELLO_NAME),
) -> None:
    """Browse and search modules on the public Terraform Registry."""
    if agent_help:
        if ctx.invoked_subcommand is not None:
            print(
                "error: --agent-help cannot be combined with a subcommand.",
                file=sys.stderr,
            )
            raise typer.Exit(2)
        _print_agent_guide()
        raise typer.Exit(0)

    if helloworld:
        session = get_session()
        if session is not None:
            result = session.run_operation(
                "Running smoke test",
                f"tf-tool helloworld --name {name}",
                lambda: action_manager.invoke(HelloWorldAction.NAME, name=name),
            )
            if isinstance(result, Failure):
                die_json_error(result.failure())
            session.replay_success(result.unwrap())
            print(result.unwrap())
        else:
            emit_result(action_manager.invoke(HelloWorldAction.NAME, name=name))
        raise typer.Exit(0)


def _bootstrap_actions() -> None:
    global _actions_bootstrapped
    if _actions_bootstrapped:
        return
    bootstrapped = register_all_actions(action_manager)
    if isinstance(bootstrapped, Failure):
        die_json_error(bootstrapped.failure())
    _actions_bootstrapped = True


def _run_build_gate() -> None:
    session = get_session()
    progress = session.run_operation if session is not None else None
    gated = run_build_gate(progress=progress)
    if isinstance(gated, Failure):
        emit_build_failure(gated.failure())
        raise typer.Exit(2)


def _doctor_requested(argv: list[str] | None = None) -> bool:
    args = sys.argv[1:] if argv is None else argv
    return bool(args) and args[0] in {"doctor", "env-check"}


def _run_env_check() -> None:
    session = get_session()

    def _check() -> EnvCheckReport:
        checked = run_env_check()
        if isinstance(checked, Failure):
            raise _EnvCheckFailed(checked.failure())
        return checked.unwrap()

    try:
        if session is not None:
            report = session.run_operation(
                "Checking Python and runtime dependencies",
                "tf-tool env-check",
                _check,
            )
            session.replay_success(
                f"Environment OK — Python {report.python.current}, "
                f"{len(report.dependencies)} dependencies verified",
            )
            return
        checked = run_env_check()
        if isinstance(checked, Failure):
            die_json_error(checked.failure())
    except _EnvCheckFailed as exc:
        die_json_error(exc.err)


def main() -> None:
    skip_checks = help_requested() or agent_guide_requested()
    skip_env = skip_checks or _doctor_requested() or os.environ.get("TF_TOOL_SKIP_ENV_CHECK") == "1"
    skip_gate = (
        skip_checks or _doctor_requested() or os.environ.get("TF_TOOL_SKIP_BUILD_GATE") == "1"
    )
    use_ui = ui_enabled() and not skip_checks
    session = OperationSession.start() if use_ui else None
    _register_agent_guide_commands()
    try:
        if not skip_env:
            _run_env_check()
        if not skip_gate:
            _run_build_gate()
        _bootstrap_actions()
        app()
    finally:
        if session is not None:
            session.finish_summary()


if __name__ == "__main__":
    main()

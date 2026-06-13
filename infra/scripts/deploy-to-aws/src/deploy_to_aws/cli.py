"""Typer CLI entrypoint."""

from __future__ import annotations

import sys

import typer
from returns.result import Failure

from deploy_to_aws.action_manager.manager import ActionManager
from deploy_to_aws.actions.bootstrap import register_all_actions
from deploy_to_aws.build.prepare import prepare_runtime
from deploy_to_aws.build_info import BuildInfo
from deploy_to_aws.core.cli_output import die_json_error

app = typer.Typer(
    name="deploy-to-aws",
    help="Deploy ARB workloads to AWS (Terraform, ECR, Helm).",
    no_args_is_help=True,
    add_completion=False,
    invoke_without_command=True,
)

action_manager = ActionManager(app)
_bootstrapped = False

_HELP_FLAGS = frozenset({"-h", "--help"})
_VERSION_FLAGS = frozenset({"-V", "--version"})


def _skip_build_gate_argv() -> bool:
    args = sys.argv[1:]
    return any(flag in _HELP_FLAGS or flag in _VERSION_FLAGS for flag in args)


def _bootstrap_actions() -> None:
    global _bootstrapped
    if _bootstrapped:
        return
    bootstrapped = register_all_actions(action_manager)
    if isinstance(bootstrapped, Failure):
        die_json_error(bootstrapped.failure())
    _bootstrapped = True


@app.callback()
def _app_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show application and build metadata.",
    ),
) -> None:
    """Deploy ARB workloads to AWS."""
    if version:
        print(BuildInfo.app())
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        return


def main() -> None:
    prepared = prepare_runtime(
        refresh_build_id=True,
        run_ruff_gate=not _skip_build_gate_argv(),
    )
    if isinstance(prepared, Failure):
        die_json_error(prepared.failure(), exit_code=2)
    _bootstrap_actions()
    app()


if __name__ == "__main__":
    main()

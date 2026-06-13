"""Doctor / environment-check action."""

from __future__ import annotations

import json

import typer
from returns.result import Failure

from tf_tool.actions.action_base import ActionBase
from tf_tool.core.command_label import argv_command_label
from tf_tool.core.env_check import report_to_json, run_env_check
from tf_tool.core.help_text import format_examples
from tf_tool.core.operation_ui import get_session
from tf_tool.core.results import Success
from tf_tool.core.types import TextResult, UnitResult


class DoctorAction(ActionBase):
    """Validate Python version and runtime dependencies."""

    ID = "d4e8f2a1-6b3c-4e9f-8a12-5d7f9c3e2b81"
    NAME = "doctor"
    CLI_ALIASES = ("env-check",)
    DESCRIPTION = "Validate Python and runtime dependencies for this environment."
    VERSION = "0.1.0"

    def invoke(self, **kwargs: object) -> TextResult:
        del kwargs
        checked = run_env_check()
        if isinstance(checked, Failure):
            return checked
        return Success(report_to_json(checked.unwrap()))

    def bind_cli(self, app: typer.Typer) -> UnitResult:
        def _doctor_cmd() -> None:
            session = get_session()
            command = argv_command_label(default="tf-tool doctor")

            def _run() -> str:
                checked = run_env_check()
                if isinstance(checked, Failure):
                    err = checked.failure()
                    payload = {
                        "error": err.code,
                        "message": err.message,
                        "detail": err.detail,
                    }
                    raise _DoctorFailed(payload, err.code)
                return report_to_json(checked.unwrap())

            try:
                if session is not None:
                    payload = session.run_operation(
                        "Checking Python and runtime dependencies",
                        command,
                        _run,
                    )
                    session.replay_success(payload)
                    print(payload)
                    return
                checked = run_env_check()
                if isinstance(checked, Failure):
                    err = checked.failure()
                    print(
                        json.dumps(
                            {"error": err.code, "message": err.message, "detail": err.detail},
                            indent=2,
                        ),
                    )
                    raise typer.Exit(2)
                print(report_to_json(checked.unwrap()))
            except _DoctorFailed as exc:
                print(json.dumps(exc.payload, indent=2))
                raise typer.Exit(2) from exc

        epilog = format_examples(
            "uv run tf-tool doctor",
            "tf-tool env-check",
        )
        for command_name in (self.NAME, *self.CLI_ALIASES):
            app.command(command_name, help=self.DESCRIPTION, epilog=epilog)(_doctor_cmd)
        return Success(None)


class _DoctorFailed(Exception):
    def __init__(self, payload: dict[str, object], code: str) -> None:
        self.payload = payload
        super().__init__(str(code))

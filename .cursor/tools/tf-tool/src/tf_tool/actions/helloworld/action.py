"""Hello-world action."""

from __future__ import annotations

import typer
from returns.result import Failure

from tf_tool.actions.action_base import ActionBase
from tf_tool.actions.helloworld.greet import greet
from tf_tool.actions.helloworld.validation import parse_hello_invoke_params
from tf_tool.core.cli_output import emit_result
from tf_tool.core.help_text import OPT_HELLO_NAME, format_examples
from tf_tool.core.results import Success
from tf_tool.core.types import TextResult, UnitResult


class HelloWorldAction(ActionBase):
    """Print a hello-world greeting."""

    ID = "a3f2c8e1-9b4d-4f6a-bc12-8e7d5f3a1c20"
    NAME = "helloworld"
    DESCRIPTION = "Demo greeting (smoke test)."
    VERSION = "0.1.0"
    FLAG_SHORT = "-w"
    FLAG_LONG = "--helloworld"

    def invoke(self, **kwargs: object) -> TextResult:
        parsed = parse_hello_invoke_params(kwargs)
        if isinstance(parsed, Failure):
            return parsed
        return greet(parsed.unwrap().name)

    def bind_cli(self, app: typer.Typer) -> UnitResult:
        @app.command(
            self.NAME,
            help=self.DESCRIPTION,
            epilog=format_examples(
                "tf-tool helloworld",
                "tf-tool helloworld --name Terraform",
            ),
        )
        def _helloworld_cmd(
            name: str = typer.Option("World", "-n", "--name", help=OPT_HELLO_NAME),
        ) -> None:
            emit_result(self.invoke(name=name))

        return Success(None)

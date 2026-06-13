"""Validate hello-world greet input."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tf_tool.core.error_format import format_validation_detail
from tf_tool.core.errors import AppError, ErrorCodes
from tf_tool.core.results import Failure, Success
from tf_tool.core.types import TfResult
from tf_tool.core.validation import parse_invoke_model


class GreetRequest(BaseModel):
    """Validated greet payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., min_length=1, max_length=120)


class HelloWorldInvokeParams(BaseModel):
    """Typed parameters for ``HelloWorldAction.invoke``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(default="World", min_length=1, max_length=120)


def validate_greet_request(name: str) -> TfResult[GreetRequest]:
    """Validate raw CLI name input before domain logic runs."""
    try:
        return Success(GreetRequest(name=name.strip()))
    except ValidationError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Invalid greet request.",
                detail=format_validation_detail(exc),
            ),
        )


def parse_hello_invoke_params(kwargs: Mapping[str, object]) -> TfResult[HelloWorldInvokeParams]:
    """Parse and validate hello-world action invoke kwargs."""
    return parse_invoke_model(
        HelloWorldInvokeParams,
        kwargs,
        message="Invalid hello-world invoke parameters.",
    )

"""Hello-world greet logic."""

from __future__ import annotations

from tf_tool.actions.helloworld.validation import GreetRequest, validate_greet_request
from tf_tool.core.results import Failure, Success
from tf_tool.core.types import TextResult


def greet(name: str) -> TextResult:
    """Return a greeting for ``name`` using validated input."""
    validated = validate_greet_request(name)
    if isinstance(validated, Failure):
        return validated

    request: GreetRequest = validated.unwrap()
    return Success(f"Hello, {request.name}!")

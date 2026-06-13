"""Unit tests for hello-world greet logic."""

from __future__ import annotations

from returns.result import Failure, Success

from tf_tool.actions.helloworld.greet import greet
from tf_tool.core.errors import ErrorCodes


def test_greet_default_name() -> None:
    result = greet("World")
    assert isinstance(result, Success)
    assert result.unwrap() == "Hello, World!"


def test_greet_trims_whitespace() -> None:
    result = greet("  Terraform  ")
    assert isinstance(result, Success)
    assert result.unwrap() == "Hello, Terraform!"


def test_greet_rejects_blank_name() -> None:
    result = greet("   ")
    assert isinstance(result, Failure)
    err = result.failure()
    assert err.code == ErrorCodes.VALIDATION

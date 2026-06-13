"""Tests for Pydantic invoke parameter parsing."""

from __future__ import annotations

from returns.result import Failure, Success

from tf_tool.actions.helloworld.validation import parse_hello_invoke_params
from tf_tool.actions.registry_search.validation import (
    parse_provider_search_invoke,
    parse_registry_search_invoke,
)


def test_parse_hello_invoke_params_defaults() -> None:
    result = parse_hello_invoke_params({})
    assert isinstance(result, Success)
    assert result.unwrap().name == "World"


def test_parse_registry_search_invoke_requires_query() -> None:
    result = parse_registry_search_invoke({})
    assert isinstance(result, Failure)


def test_parse_provider_search_invoke_accepts_optional_filters() -> None:
    result = parse_provider_search_invoke(
        {"query": "vpc", "namespace": "terraform-aws-modules", "limit": 5},
    )
    assert isinstance(result, Success)
    params = result.unwrap()
    assert params.query == "vpc"
    assert params.namespace == "terraform-aws-modules"
    assert params.limit == 5

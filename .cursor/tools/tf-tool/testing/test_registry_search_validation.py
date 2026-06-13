"""Unit tests for registry search ingress validation."""

from __future__ import annotations

from returns.result import Failure, Success

from tf_tool.actions.registry_search.validation import validate_search_request
from tf_tool.core.errors import ErrorCodes


def test_validate_search_request_minimal() -> None:
    result = validate_search_request(query="vpc")
    assert isinstance(result, Success)
    request = result.unwrap()
    assert request.query == "vpc"
    assert request.provider is None
    assert request.limit == 20


def test_validate_search_request_with_filters() -> None:
    result = validate_search_request(
        query="network",
        provider="aws",
        namespace="terraform-aws-modules",
        verified=True,
        limit=5,
        offset=10,
    )
    assert isinstance(result, Success)
    request = result.unwrap()
    assert request.provider == "aws"
    assert request.namespace == "terraform-aws-modules"
    assert request.verified is True
    assert request.limit == 5
    assert request.offset == 10


def test_validate_search_request_rejects_blank_query() -> None:
    result = validate_search_request(query="   ")
    assert isinstance(result, Failure)
    assert result.failure().code == ErrorCodes.VALIDATION


def test_validate_search_request_rejects_invalid_provider() -> None:
    result = validate_search_request(query="vpc", provider="AWS!")
    assert isinstance(result, Failure)
    assert result.failure().code == ErrorCodes.VALIDATION

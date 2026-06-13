"""Tests for cloud provider name resolution."""

from __future__ import annotations

from returns.result import Failure, Success

from tf_tool.actions.registry_search.providers.catalog import resolve_cloud_provider
from tf_tool.actions.registry_search.validation import validate_search_request


def test_resolve_aws_aliases() -> None:
    for name in ("aws", "AWS", "amazon"):
        result = resolve_cloud_provider(name)
        assert isinstance(result, Success)
        assert result.unwrap() == "aws"


def test_resolve_azure_to_azurerm() -> None:
    result = resolve_cloud_provider("azure")
    assert isinstance(result, Success)
    assert result.unwrap() == "azurerm"


def test_resolve_gcp_to_google() -> None:
    result = resolve_cloud_provider("gcp")
    assert isinstance(result, Success)
    assert result.unwrap() == "google"


def test_resolve_unknown_provider_fails() -> None:
    result = resolve_cloud_provider("AWS!")
    assert isinstance(result, Failure)


def test_resolve_custom_registry_slug() -> None:
    result = resolve_cloud_provider("vsphere")
    assert isinstance(result, Success)
    assert result.unwrap() == "vsphere"


def test_validate_search_request_resolves_provider_alias() -> None:
    result = validate_search_request(query="network", provider="azure", limit=3)
    assert isinstance(result, Success)
    assert result.unwrap().provider == "azurerm"

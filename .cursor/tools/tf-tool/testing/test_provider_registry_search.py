"""Unit tests for provider-scoped registry search actions."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from returns.result import Success

from tf_tool.actions.registry_search.client import RegistrySearchClient
from tf_tool.actions.registry_search.providers.aws import (
    AwsRegistrySearchAction,
    search_aws_modules,
)
from tf_tool.actions.registry_search.providers.aws.constants import AWS_PROVIDER
from tf_tool.actions.registry_search.providers.azurerm import AzurermRegistrySearchAction
from tf_tool.actions.registry_search.providers.google import GoogleRegistrySearchAction

_FIXTURE = Path(__file__).parent / "fixtures" / "registry_search_vpc.json"


def _mock_client() -> RegistrySearchClient:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    http_client = Mock(spec=httpx.Client)
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.text = json.dumps(payload)
    response.json.return_value = payload
    http_client.get.return_value = response
    return RegistrySearchClient(client=http_client)


def test_aws_action_metadata() -> None:
    action = AwsRegistrySearchAction()
    assert action.name == "registry-search-aws"
    assert action.PROVIDER == AWS_PROVIDER


def test_search_aws_modules_locks_provider() -> None:
    client = _mock_client()
    result = search_aws_modules(
        query="vpc",
        namespace="terraform-aws-modules",
        limit=1,
        client=client,
    )
    assert isinstance(result, Success)
    data = json.loads(result.unwrap())
    assert data["provider"] == "aws"
    assert data["query"] == "vpc"
    assert data["namespace"] == "terraform-aws-modules"

    call_kwargs = client._client.get.call_args.kwargs  # type: ignore[union-attr]
    assert call_kwargs["params"]["provider"] == "aws"
    assert call_kwargs["params"]["q"] == "vpc"


def test_provider_actions_invoke_with_fixed_provider() -> None:
    with patch(
        "tf_tool.actions.registry_search.search.search_registry_modules",
    ) as mock_search:
        mock_search.return_value = Success('{"provider":"aws","count":0}')
        AwsRegistrySearchAction().invoke(query="vpc", limit=2)
        mock_search.assert_called_once_with(
            query="vpc",
            provider="aws",
            namespace=None,
            verified=None,
            limit=2,
            offset=0,
        )

        mock_search.reset_mock()
        mock_search.return_value = Success('{"provider":"google","count":0}')
        GoogleRegistrySearchAction().invoke(query="network", limit=2)
        mock_search.assert_called_once_with(
            query="network",
            provider="google",
            namespace=None,
            verified=None,
            limit=2,
            offset=0,
        )

        mock_search.reset_mock()
        mock_search.return_value = Success('{"provider":"azurerm","count":0}')
        AzurermRegistrySearchAction().invoke(query="network", limit=2)
        mock_search.assert_called_once_with(
            query="network",
            provider="azurerm",
            namespace=None,
            verified=None,
            limit=2,
            offset=0,
        )

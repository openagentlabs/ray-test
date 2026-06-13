"""Unit tests for registry search HTTP client."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import httpx
from returns.result import Failure, Success

from tf_tool.actions.registry_search.client import RegistrySearchClient
from tf_tool.actions.registry_search.validation import SearchRequest
from tf_tool.core.errors import ErrorCodes

_FIXTURE = Path(__file__).parent / "fixtures" / "registry_search_vpc.json"


def _mock_response(*, status_code: int, payload: object) -> Mock:
    response = Mock(spec=httpx.Response)
    response.status_code = status_code
    response.text = json.dumps(payload)
    response.json.return_value = payload
    return response


def test_client_search_success() -> None:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    http_client = Mock(spec=httpx.Client)
    http_client.get.return_value = _mock_response(status_code=200, payload=payload)

    client = RegistrySearchClient(client=http_client)
    result = client.search(SearchRequest(query="vpc", limit=2))

    assert isinstance(result, Success)
    assert result.unwrap().modules[0].name == "vpc"
    http_client.get.assert_called_once()
    call_kwargs = http_client.get.call_args.kwargs
    assert call_kwargs["params"]["q"] == "vpc"
    assert call_kwargs["params"]["limit"] == 2


def test_client_search_registry_error() -> None:
    http_client = Mock(spec=httpx.Client)
    http_client.get.return_value = _mock_response(
        status_code=400,
        payload={"errors": ["Query string must be specified"]},
    )

    client = RegistrySearchClient(client=http_client)
    result = client.search(SearchRequest(query="vpc"))

    assert isinstance(result, Failure)
    err = result.failure()
    assert err.code == ErrorCodes.REGISTRY
    assert "Query string must be specified" in (err.detail or "")


def test_client_search_invalid_response_schema() -> None:
    http_client = Mock(spec=httpx.Client)
    http_client.get.return_value = _mock_response(status_code=200, payload={"unexpected": True})

    client = RegistrySearchClient(client=http_client)
    result = client.search(SearchRequest(query="vpc"))

    assert isinstance(result, Failure)
    assert result.failure().code == ErrorCodes.REGISTRY

"""Unit tests for registry list HTTP client."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import httpx
from returns.result import Success

from tf_tool.actions.registry_search.client import RegistryClient
from tf_tool.actions.registry_search.validation import ListRequest

_FIXTURE = Path(__file__).parent / "fixtures" / "registry_search_vpc.json"


def _mock_response(*, status_code: int, payload: object) -> Mock:
    response = Mock(spec=httpx.Response)
    response.status_code = status_code
    response.text = json.dumps(payload)
    response.json.return_value = payload
    return response


def test_client_list_modules_success() -> None:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    http_client = Mock(spec=httpx.Client)
    http_client.get.return_value = _mock_response(status_code=200, payload=payload)

    client = RegistryClient(client=http_client)
    result = client.list_modules(ListRequest(provider="aws", limit=2))

    assert isinstance(result, Success)
    assert result.unwrap().modules[0].provider == "aws"
    call_args = http_client.get.call_args
    assert call_args.args[0].endswith("/v1/modules")
    assert call_args.kwargs["params"]["provider"] == "aws"


def test_client_list_modules_namespace_path() -> None:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    http_client = Mock(spec=httpx.Client)
    http_client.get.return_value = _mock_response(status_code=200, payload=payload)

    client = RegistryClient(client=http_client)
    result = client.list_modules(
        ListRequest(namespace="terraform-aws-modules", provider="aws", limit=1),
    )

    assert isinstance(result, Success)
    assert http_client.get.call_args.args[0].endswith("/v1/modules/terraform-aws-modules")

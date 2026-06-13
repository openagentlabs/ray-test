"""Unit tests for registry search response schemas."""

from __future__ import annotations

import json
from pathlib import Path

from tf_tool.actions.registry_search.models import (
    RegistryErrorResponse,
    RegistrySearchResponse,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "registry_search_vpc.json"


def test_registry_search_response_parses_fixture() -> None:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    parsed = RegistrySearchResponse.model_validate(payload)
    assert parsed.meta.limit == 2
    assert len(parsed.modules) == 1
    module = parsed.modules[0]
    assert module.namespace == "terraform-aws-modules"
    assert module.source_address == "terraform-aws-modules/vpc/aws"


def test_registry_error_response_parses_api_errors() -> None:
    parsed = RegistryErrorResponse.model_validate({"errors": ["Query string must be specified"]})
    assert parsed.errors[0] == "Query string must be specified"


def test_registry_search_meta_accepts_prev_pagination_fields() -> None:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    payload["meta"]["current_offset"] = 20
    payload["meta"]["prev_offset"] = 0
    payload["meta"]["prev_url"] = "https://registry.terraform.io/v1/modules?limit=20&provider=aws"
    parsed = RegistrySearchResponse.model_validate(payload)
    assert parsed.meta.prev_offset == 0
    assert parsed.meta.prev_url is not None

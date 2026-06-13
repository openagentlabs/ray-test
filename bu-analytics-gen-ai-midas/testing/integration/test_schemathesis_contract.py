"""Schemathesis contract smoke: GET operations from generated OpenAPI stub (inventory-derived)."""

from __future__ import annotations

import pytest
import schemathesis.pytest as st_pytest
from schemathesis.checks import not_a_server_error

pytestmark = [pytest.mark.schemathesis, pytest.mark.slow]

_schema = (
    st_pytest.from_fixture("midas_openapi_get_schema_raw")
    .include(method="GET", path_regex=r"/api/v1/(?!.+\{)(?!.+(stream|sse|event)).+")
)


@_schema.parametrize()
def test_get_operations_not_server_error(
    case,
    midas_base_url: str,
    midas_session_credentials,
) -> None:
    """Each GET operation must not return HTTP 5xx when called with session auth."""
    case.call_and_validate(
        base_url=midas_base_url,
        headers=midas_session_credentials.request_headers(),
        checks=[not_a_server_error],
    )

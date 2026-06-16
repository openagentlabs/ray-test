"""Unit tests for hardcoded IdP driver."""

from __future__ import annotations

import pytest

from iam_service.core.results import Failure, Success
from iam_service.plugins.idp.hardcoded_driver import HardcodedIdpDriver
from iam_service.plugins.idp.types import IdpCredentialRequest


@pytest.mark.asyncio
async def test_hardcoded_idp_valid_credentials() -> None:
    driver = HardcodedIdpDriver(
        provider_id="test",
        display_name="Test",
        users={"keith.tobin@gmail.com": "123456"},
    )
    result = await driver.authenticate_credentials(
        IdpCredentialRequest(username="keith.tobin@gmail.com", password="123456"),
    )
    assert isinstance(result, Success)
    assert result.unwrap().email == "keith.tobin@gmail.com"


@pytest.mark.asyncio
async def test_hardcoded_idp_invalid_password() -> None:
    driver = HardcodedIdpDriver(
        provider_id="test",
        display_name="Test",
        users={"keith.tobin@gmail.com": "123456"},
    )
    result = await driver.authenticate_credentials(
        IdpCredentialRequest(username="keith.tobin@gmail.com", password="wrong"),
    )
    assert isinstance(result, Failure)

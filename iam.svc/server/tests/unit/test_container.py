"""Tests for IoC ``ServiceContainer`` wiring."""

from __future__ import annotations

import pytest

from iam_service.core.app_config_store import (
    ensure_app_config_for_tests,
    reset_app_config_for_tests,
)
from iam_service.core.container import ServiceContainer
from iam_service.core.results import Success
from iam_service.dynamodb.context import DynamoContext


@pytest.fixture(autouse=True)
def _config_singleton() -> None:
    reset_app_config_for_tests()
    ensure_app_config_for_tests()
    yield
    reset_app_config_for_tests()


@pytest.fixture
def dynamo_context() -> DynamoContext:
    import aioboto3

    return DynamoContext(
        session=aioboto3.Session(region_name="us-east-1"),
        region="us-east-1",
        endpoint_url=None,
    )


def test_container_builds_all_services(dynamo_context: DynamoContext) -> None:
    """Container wires IAM and auth applications from singleton config."""
    built = ServiceContainer.build(dynamo=dynamo_context)
    assert isinstance(built, Success)
    container = built.unwrap()
    assert container.iam_app is not None
    assert container.auth_app is not None
    assert container.token_service is not None
    assert container.repos.users is not None


@pytest.mark.asyncio
async def test_container_token_service_is_wired(dynamo_context: DynamoContext) -> None:
    """Token service is constructed with vault driver from config."""
    built = ServiceContainer.build(dynamo=dynamo_context)
    container = built.unwrap()
    assert container.token_service is not None
    assert hasattr(container.token_service, "ensure_master_key_exists")

"""Shared pytest fixtures for iam-service."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from iam.v1 import iam_pb2
from iam_service.core.app_config import AppSection
from iam_service.core.app_config_store import (
    ensure_app_config_for_tests,
    reset_app_config_for_tests,
)
from iam_service.core.results import Success

pytest_plugins = ("support.result_table",)


@pytest.fixture(autouse=True)
def _app_config_singleton() -> None:
    """Seed singleton defaults so code using ``app_config()`` works in tests."""
    reset_app_config_for_tests()
    ensure_app_config_for_tests()
    yield
    reset_app_config_for_tests()


@pytest.fixture
def app_section() -> AppSection:
    return AppSection(service_name="iam-test", version="0.0.0-test", log_level="INFO")


@pytest.fixture
def skills_repo_mock() -> AsyncMock:
    """Catalog repo defaults for ``IamServiceApplication`` unit tests."""
    m = AsyncMock()
    m.scan_page = AsyncMock(return_value=Success(([], "")))
    m.get_by_id = AsyncMock(return_value=Success(None))
    m.put = AsyncMock(return_value=Success(None))
    m.soft_delete = AsyncMock(return_value=Success(None))
    return m


@pytest.fixture
def rbac_mock() -> AsyncMock:
    """RBAC service defaults for ``IamServiceApplication`` unit tests."""
    m = AsyncMock()
    m.bootstrap_default_rbac = AsyncMock(return_value=Success(None))
    m.assign_system_admin_to_user = AsyncMock(return_value=Success(None))
    m.build_user_auth_context = AsyncMock(
        return_value=Success(
            iam_pb2.UserAuthContext(
                user_id="",
                role_codes=[],
                auth_json='{"permission_grants":[],"role_codes":[],"user_id":""}',
            ),
        ),
    )
    return m


@pytest.fixture
def user_skills_repo_mock() -> AsyncMock:
    """User-skill link repo defaults for ``IamServiceApplication`` unit tests."""
    m = AsyncMock()
    m.query_by_user = AsyncMock(return_value=Success(([], "")))
    m.put = AsyncMock(return_value=Success(None))
    m.soft_delete = AsyncMock(return_value=Success(None))
    m.get_by_id = AsyncMock(return_value=Success(None))
    return m

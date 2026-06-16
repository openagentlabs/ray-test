"""Tests for ``app_config`` singleton load-once semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

from iam_service.core.app_config import AppConfig
from iam_service.core.app_config_store import (
    app_config,
    ensure_app_config_for_tests,
    init_app_config,
    is_app_config_loaded,
    reset_app_config_for_tests,
)
from iam_service.core.results import Failure, Success


@pytest.fixture(autouse=True)
def _reset_config_singleton() -> None:
    reset_app_config_for_tests()
    yield
    reset_app_config_for_tests()


def test_init_app_config_loads_toml_once(tmp_path: Path) -> None:
    """Second init returns cached instance without re-reading disk."""
    toml = tmp_path / "app_config.toml"
    toml.write_text(
        """
[app]
service_name = "singleton-test"

[api_service]
port = 8803

[dynamodb]
region = "us-east-1"

[dynamodb.tables]
users = "t-users"
user_types = "t-user-types"
login_types = "t-login-types"
logins = "t-logins"
skill_lists = "t-skill-lists"
skills = "t-skills"
user_skills = "t-user-skills"
sessions = "t-sessions"
invites = "t-invites"
deployment_admin = "t-deployment-admin"
roles = "t-roles"
permissions = "t-permissions"
role_permissions = "t-role-permissions"
user_role_assignments = "t-user-role-assignments"
service_permissions = "t-service-permissions"
service_function_registry = "t-service-function-registry"
user_permissions = "t-user-permissions"
auth_sessions = "t-auth-sessions"
""",
        encoding="utf-8",
    )

    first = init_app_config(toml)
    second = init_app_config(toml)

    assert isinstance(first, Success)
    assert isinstance(second, Success)
    assert first.unwrap() is second.unwrap()
    assert app_config().app.service_name == "singleton-test"


def test_app_config_raises_before_init() -> None:
    """Access before init fails fast."""
    with pytest.raises(RuntimeError, match="not loaded"):
        app_config()


def test_ensure_app_config_for_tests_seeds_defaults() -> None:
    """Tests can seed singleton without TOML."""
    cfg = ensure_app_config_for_tests()
    assert isinstance(cfg, AppConfig)
    assert is_app_config_loaded()
    assert app_config() is cfg


def test_init_app_config_invalid_path_returns_failure(tmp_path: Path) -> None:
    """Missing file surfaces ``Failure`` not exception."""
    missing = tmp_path / "missing.toml"
    outcome = init_app_config(missing)
    assert isinstance(outcome, Failure)

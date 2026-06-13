"""Tests for application configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
from returns.result import Failure, Success

from deploy_to_aws.core.config import (
    APP_ENV_PREFIX,
    AppConfig,
    apply_env_overrides,
    env_var_name,
    load_app_config,
    read_env_override,
    to_screaming_snake,
)


def test_env_var_name_mapping() -> None:
    assert env_var_name("App", "Env") == f"{APP_ENV_PREFIX}_APP_ENV"
    assert env_var_name("Aws", "AccountId") == f"{APP_ENV_PREFIX}_AWS_ACCOUNT_ID"
    assert to_screaming_snake("HelmStableTimeout") == "HELM_STABLE_TIMEOUT"


def test_env_var_names_are_uppercase() -> None:
    key = env_var_name("Aws", "Profile")
    assert key == key.upper()
    assert key.startswith(f"{APP_ENV_PREFIX}_")


def test_read_env_override_accepts_uppercase_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(f"{APP_ENV_PREFIX}_APP_ENV", "test")
    assert read_env_override(f"{APP_ENV_PREFIX}_APP_ENV") == "test"


def test_apply_env_overrides_bool_and_int(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(f"{APP_ENV_PREFIX}_DEPLOY_AUTO_APPROVE", "true")
    monkeypatch.setenv(f"{APP_ENV_PREFIX}_DEPLOY_HELM_STABLE_TIMEOUT", "1200")
    merged = apply_env_overrides(
        {
            "App": {"Env": "dev", "Target": "aws"},
            "Deploy": {"AutoApprove": False, "HelmStableTimeout": 900},
        },
    )
    assert merged["Deploy"]["AutoApprove"] is True
    assert merged["Deploy"]["HelmStableTimeout"] == 1200


def test_env_overrides_toml_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """UPPERCASE env vars must override app_config.toml values."""
    monkeypatch.setenv(f"{APP_ENV_PREFIX}_APP_ENV", "test")
    monkeypatch.setenv(f"{APP_ENV_PREFIX}_AWS_PROFILE", "override-profile")
    merged = apply_env_overrides(
        {
            "App": {"Env": "dev", "Target": "aws"},
            "Aws": {
                "Profile": "kt-acc",
                "Region": "us-east-1",
                "AccountId": "017868795096",
            },
        },
    )
    assert merged["App"]["Env"] == "test"
    assert merged["Aws"]["Profile"] == "override-profile"


def test_load_app_config_discovers_repo_root() -> None:
    app_dir = Path(__file__).resolve().parents[1]
    loaded = load_app_config(app_dir=app_dir)
    assert isinstance(loaded, Success)
    config: AppConfig = loaded.unwrap()
    assert config.app.Env == "dev"
    assert config.aws.Profile == "kt-acc"
    assert (config.repo_root / "infra" / "aws" / "aws_tf").is_dir()


def test_load_app_config_missing_file(tmp_path: Path) -> None:
    loaded = load_app_config(config_path=tmp_path / "missing.toml", app_dir=tmp_path)
    assert isinstance(loaded, Failure)
    assert loaded.failure().code == "config"

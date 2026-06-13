"""Tests for schema-driven config environment overrides."""

from __future__ import annotations

from pathlib import Path

import pytest
from returns.result import Success

from solutions_service.core.app_config import AppConfig
from solutions_service.core.config_env import documented_env_keys, env_var_name

_BASE_TOML = """
[app]
service_name = "from-toml"
log_level = "INFO"

[api_service]
host = "0.0.0.0"
port = 8804

[ext_authz]
host = "127.0.0.1"
port = 9000

[kubernetes]
enabled = false

[reconciliation]
enabled = false

[auth]
dev_mode = true
dev_sub_header = "x-test-sub"

[cognito]
enabled = false
issuer = ""
audience = ""

[reaper]
enabled = false
interval_sec = 60.0
idle_ttl_sec = 900.0

[envoy_management]
enabled = false

[login_pod_pool]
routing_upstream = "login-pod:8080"

[postgres]
dsn = ""
table_prefix = "pm_"
pool_min = 1
pool_max = 10
command_timeout_sec = 10.0
""".strip()


def test_env_var_name_from_path() -> None:
    assert env_var_name("POD_MANAGER", ("api_service", "port")) == "POD_MANAGER_API_SERVICE_PORT"


def test_apply_env_overrides_canonical_and_legacy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    toml = tmp_path / "app_config.toml"
    toml.write_text(_BASE_TOML, encoding="utf-8")

    monkeypatch.setenv("POD_MANAGER_APP_SERVICE_NAME", "from-env")
    monkeypatch.setenv("SOLUTIONS_SERVICE_GRPC_PORT", "9999")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("POD_MANAGER_POSTGRES_TABLE_PREFIX", "ovr_")
    monkeypatch.setenv("POD_MANAGER_POSTGRES_SCHEMA_NAME", "routing")

    loaded = AppConfig.load(toml)
    assert isinstance(loaded, Success)
    cfg = loaded.unwrap()
    assert cfg.app.service_name == "from-env"
    assert cfg.api_service.port == 9999
    assert cfg.postgres.dsn == "postgresql://u:p@host:5432/db"
    assert cfg.postgres.table_prefix == "ovr_"
    assert cfg.postgres.schema_name == "routing"
    assert cfg.physical_table("backend_pool") == "ovr_backend_pool"


def test_apply_env_pool_sizes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    toml = tmp_path / "app_config.toml"
    toml.write_text(_BASE_TOML, encoding="utf-8")
    monkeypatch.setenv("POD_MANAGER_POSTGRES_POOL_MAX", "25")

    loaded = AppConfig.load(toml)
    assert isinstance(loaded, Success)
    assert loaded.unwrap().postgres.pool_max == 25


def test_documented_env_keys_include_canonical_and_legacy() -> None:
    keys = {name for name, _ in documented_env_keys(AppConfig)}
    assert "POD_MANAGER_API_SERVICE_PORT" in keys
    assert "SOLUTIONS_SERVICE_GRPC_PORT" in keys
    assert any(name.startswith("POD_MANAGER_") for name in keys)

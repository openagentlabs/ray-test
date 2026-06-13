"""Tests for Postgres physical table name resolution."""

from __future__ import annotations

from pathlib import Path

import pytest
from returns.result import Success

from solutions_service.core.app_config import AppConfig
from solutions_service.core.table_names import physical_table_name, safe_identifier

_TOML = """
[app]
service_name = "my-service"
log_level = "INFO"

[api_service]
host = "127.0.0.1"
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
dev_sub_header = ""

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


def test_physical_table_name_applies_prefix() -> None:
    assert physical_table_name("pm_", "backend_pool") == "pm_backend_pool"


def test_physical_table_name_rejects_unsafe_identifier() -> None:
    with pytest.raises(ValueError, match="Unsafe SQL identifier"):
        physical_table_name("pm_", "backend_pool; DROP TABLE x")


def test_safe_identifier_rejects_uppercase() -> None:
    with pytest.raises(ValueError, match="Unsafe SQL identifier"):
        safe_identifier("PmBackendPool")


def test_app_config_physical_table_from_toml(tmp_path: Path) -> None:
    toml = tmp_path / "app_config.toml"
    toml.write_text(_TOML, encoding="utf-8")

    loaded = AppConfig.load(toml)

    assert isinstance(loaded, Success)
    cfg = loaded.unwrap()
    assert cfg.physical_table("solution_documents") == "pm_solution_documents"
    assert cfg.physical_table("backend_pool") == "pm_backend_pool"
    assert cfg.physical_tables()["service_config"] == "pm_service_config"

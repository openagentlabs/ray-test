"""Log effective configuration and environment parameters at startup."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from solutions_service.core.app_config import AppConfig
from solutions_service.core.config_env import documented_env_keys

logger = logging.getLogger(__name__)


def _redact_env_value(key: str, value: str) -> str:
    upper = key.upper()
    if "SECRET" in upper or "PASSWORD" in upper or "TOKEN" in upper:
        return f"***({len(value)} chars)"
    # Connection strings (e.g. DATABASE_URL / *_DSN) embed credentials.
    if "DATABASE_URL" in upper or upper.endswith("_DSN") or upper == "DSN":
        return f"***({len(value)} chars)"
    if "ACCESS_KEY_ID" in upper and len(value) >= 4:
        return f"{value[:4]}…"
    return value


def _env_snapshot(keys: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in keys:
        raw = os.environ.get(key)
        if raw is None or not str(raw).strip():
            continue
        out[key] = _redact_env_value(key, str(raw).strip())
    return out


def log_parameters(*, app_config: AppConfig, config_path: Path) -> None:
    env_keys = tuple(
        {
            *{name for name, _ in documented_env_keys(AppConfig)},
            "DATABASE_URL",
            "SOLUTIONS_APP_CONFIG_PATH",
        },
    )
    parts = [
        f"config_path={config_path.resolve()}",
        f"service_name={app_config.app.service_name}",
        f"log_level={app_config.app.log_level}",
        f"grpc_host={app_config.api_service.host}",
        f"grpc_port={app_config.api_service.port}",
        f"postgres_table_prefix={app_config.postgres.table_prefix}",
        f"postgres_tables={app_config.physical_tables()}",
        f"postgres_dsn_set={bool(app_config.postgres.dsn.strip())}",
        f"env={_env_snapshot(env_keys)}",
    ]
    logger.info("startup parameters: %s", " | ".join(parts))

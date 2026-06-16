"""Log effective configuration and environment parameters at startup."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from iam_service.core.app_config import AppConfig
from iam_service.util.aws_env import (
    aws_access_key_id,
    aws_region,
    aws_secret_access_key,
)

logger = logging.getLogger(__name__)


def _redact_env_value(key: str, value: str) -> str:
    upper = key.upper()
    if "SECRET" in upper or "PASSWORD" in upper or "TOKEN" in upper:
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
    ddb = app_config.dynamodb
    env_keys = (
        "IAM_LOG_LEVEL",
        "LOG_LEVEL",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
        "AWS_REGION",
        "IAM_AUTO_BOOTSTRAP_ADMIN_ON_EMPTY",
    )
    parts = [
        f"config_path={config_path.resolve()}",
        f"service_name={app_config.app.service_name}",
        f"log_level={app_config.app.log_level}",
        f"grpc_host={app_config.api_service.host}",
        f"grpc_port={app_config.api_service.port}",
        f"dynamodb_region={aws_region(config_fallback=ddb.region)}",
        f"dynamodb_tables={ddb.tables.model_dump()}",
        f"aws_access_key_set={aws_access_key_id() is not None}",
        f"aws_secret_set={aws_secret_access_key() is not None}",
        f"env={_env_snapshot(env_keys)}",
    ]
    logger.info("startup parameters: %s", " | ".join(parts))

"""Resolve Postgres DSN from MIDAS RDS secret environment variables."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import boto3
from botocore.exceptions import BotoCoreError, ClientError


@dataclass(frozen=True, slots=True)
class RdsBundle:
    """Resolved RDS connection values required to build a PostgreSQL DSN."""

    username: str
    password: str
    host: str
    port: str
    dbname: str
    sslmode: str


def resolve_dsn_from_rds_env() -> str:
    """Build DATABASE_URL from AWS_RDS_POSTGRES_* env variables.

    Returns an empty string when required keys are not present or cannot be resolved.
    """
    inline_secret_json = (os.getenv("AWS_RDS_POSTGRES_SECRET_JSON") or "").strip()
    secret_payload = _parse_secret_json(inline_secret_json)
    if secret_payload is None:
        secret_payload = _fetch_secret_payload()
    if secret_payload is None:
        return ""

    bundle = _to_rds_bundle(secret_payload)
    if bundle is None:
        return ""

    return (
        f"postgresql://{quote(bundle.username)}:{quote(bundle.password)}@"
        f"{bundle.host}:{bundle.port}/{bundle.dbname}?sslmode={bundle.sslmode}"
    )


def _fetch_secret_payload() -> dict[str, Any] | None:
    secret_id = (os.getenv("AWS_RDS_POSTGRES_SECRET_ID") or "").strip()
    if not secret_id:
        return None
    region = (
        (os.getenv("AWS_SECRETS_MANAGER_REGION") or "").strip()
        or (os.getenv("AWS_REGION") or "").strip()
        or (os.getenv("AWS_DEFAULT_REGION") or "").strip()
    )
    if not region:
        return None

    verify_ssl_raw = (os.getenv("AWS_SECRETS_MANAGER_VERIFY_SSL") or "true").strip().lower()
    verify_ssl = verify_ssl_raw not in {"0", "false", "no", "off"}
    try:
        client = boto3.client("secretsmanager", region_name=region, verify=verify_ssl)
        response = client.get_secret_value(SecretId=secret_id)
        return _parse_secret_json(response.get("SecretString", ""))
    except (ClientError, BotoCoreError, ValueError, TypeError):
        return None


def _parse_secret_json(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _to_rds_bundle(secret_payload: dict[str, Any]) -> RdsBundle | None:
    username = _pick_string(secret_payload, ("username", "user"), "")
    password = _pick_string(secret_payload, ("password",), "")

    host = (os.getenv("AWS_RDS_POSTGRES_HOST") or "").strip() or _pick_string(
        secret_payload,
        ("host", "hostname"),
        "",
    )
    port = (os.getenv("AWS_RDS_POSTGRES_PORT") or "").strip() or _pick_string(
        secret_payload,
        ("port",),
        "5432",
    )
    dbname = (os.getenv("AWS_RDS_POSTGRES_DB_NAME") or "").strip() or _pick_string(
        secret_payload,
        ("dbname", "database", "db_name"),
        "",
    )
    sslmode = (os.getenv("AWS_RDS_POSTGRES_SSLMODE") or "").strip() or "require"

    if not (username and password and host and port and dbname):
        return None
    return RdsBundle(
        username=username,
        password=password,
        host=host,
        port=port,
        dbname=dbname,
        sslmode=sslmode,
    )


def _pick_string(source: dict[str, Any], keys: tuple[str, ...], default: str) -> str:
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default

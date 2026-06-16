"""AWS credential and region values from the process environment only.

Canonical local source: ``infra/envs/dev/.env.aws`` (merged at startup by ``make start-local``).
Standard variables: ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``AWS_DEFAULT_REGION``.
"""

from __future__ import annotations

import os


def _nonempty(key: str) -> str | None:
    raw = os.environ.get(key)
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def aws_access_key_id() -> str | None:
    return _nonempty("AWS_ACCESS_KEY_ID")


def aws_secret_access_key() -> str | None:
    return _nonempty("AWS_SECRET_ACCESS_KEY")


def aws_credentials_available() -> bool:
    if aws_access_key_id() and aws_secret_access_key():
        return True
    return bool(_nonempty("AWS_WEB_IDENTITY_TOKEN_FILE") and _nonempty("AWS_ROLE_ARN"))


def aws_region(*, config_fallback: str) -> str:
    return (
        _nonempty("IAM_DYNAMODB_REGION")
        or _nonempty("AWS_DEFAULT_REGION")
        or _nonempty("AWS_REGION")
        or config_fallback.strip()
    )

"""Construct ``ISecretsReader`` from ``Settings`` (only when SM is required)."""

from __future__ import annotations

import base64
import binascii
import logging
from typing import TYPE_CHECKING, Optional

import boto3

from app.core.secrets.aws_secrets_manager import AwsSecretsManagerReader
from app.core.secrets.contracts import ISecretsReader
from app.core.secrets.slot_definitions import SECRET_SLOTS

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)

# MIDAS deploy target region when env is missing or corrupted (e.g. base64 pasted into SM).
_MIDAS_DEFAULT_AWS_REGION = "us-east-1"


def _strip(s: Optional[str]) -> str:
    return (s or "").strip()


def _slot_needs_reader(secret_id: Optional[str], inline_json: Optional[str]) -> bool:
    """True if this slot will call Secrets Manager (id set and no inline JSON override)."""
    return bool(_strip(secret_id)) and not _strip(inline_json)


def aws_secrets_reader_needed(settings: "Settings") -> bool:
    """Build boto3 client only when at least one slot resolves via Secrets Manager."""
    for slot in SECRET_SLOTS:
        sid = slot.secret_id_from_settings(settings)
        j = slot.inline_json_from_settings(settings)
        if _slot_needs_reader(sid, j):
            return True
    return False


def _coerce_secrets_manager_region(region: Optional[str]) -> Optional[str]:
    """
    Return a botocore-valid Secrets Manager region name.

    Misconfigured Secrets Manager JSON (or .env merge) can set AWS_REGION to a
    base64-encoded region string, which makes boto3 build invalid endpoints
    (e.g. secretsmanager.dXMtZWFzdC0x.amazonaws.com).
    """
    stripped = (region or "").strip()
    if not stripped:
        return None
    try:
        valid = set(boto3.session.Session().get_available_regions("secretsmanager"))
    except Exception:
        valid = set()
    if stripped in valid:
        return stripped
    try:
        pad = stripped + "=" * ((4 - len(stripped) % 4) % 4)
        decoded = base64.b64decode(pad, validate=True).decode("ascii").strip()
        if decoded in valid:
            logger.warning(
                "Invalid-looking AWS region %r for Secrets Manager; using decoded value %r.",
                stripped,
                decoded,
            )
            return decoded
    except (ValueError, binascii.Error, UnicodeDecodeError):
        pass
    if _MIDAS_DEFAULT_AWS_REGION in valid:
        logger.warning(
            "Invalid AWS region %r for Secrets Manager client; using MIDAS default %r.",
            stripped,
            _MIDAS_DEFAULT_AWS_REGION,
        )
        return _MIDAS_DEFAULT_AWS_REGION
    logger.warning(
        "Could not validate AWS region %r for Secrets Manager; passing through unchanged.",
        stripped,
    )
    return stripped


def build_secrets_reader(settings: "Settings") -> Optional[ISecretsReader]:
    """
    Build a Secrets Manager reader when any configured slot needs a remote fetch.
    Returns None if every slot uses inline JSON only or no secret ids are set.
    """
    if not aws_secrets_reader_needed(settings):
        return None

    region = (
        settings.AWS_SECRETS_MANAGER_REGION
        or settings.AWS_REGION
        or settings.AWS_DEFAULT_REGION
    )
    region = _coerce_secrets_manager_region(region)
    return AwsSecretsManagerReader(
        region=region,
        verify_ssl=settings.AWS_SECRETS_MANAGER_VERIFY_SSL,
        profile_name=settings.AWS_PROFILE,
    )

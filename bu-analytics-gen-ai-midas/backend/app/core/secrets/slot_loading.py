"""Generic load step: inline JSON from env → else Secrets Manager by id (per slot)."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Optional, TypeVar

from botocore.exceptions import ClientError

from app.core.secrets.contracts import ISecretsReader
from app.core.secrets.models import _str_field, rds_database_field_absent

logger = logging.getLogger(__name__)

T = TypeVar("T")


def parse_inline_secret_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse ``AWS_*_SECRET_JSON`` env value; return None if unset/blank."""
    if not raw or not str(raw).strip():
        return None
    try:
        val = json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in inline secret env")
        raise
    if not isinstance(val, dict):
        raise ValueError("Inline secret JSON must be an object")
    return val


def _merge_into_sm_payload(
    label: str, payload: Dict[str, Any], merge_into_payload: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Shallow-merge optional keys into a copy of the SM JSON (RDS connection fields when missing only)."""
    if not merge_into_payload:
        return payload
    out = dict(payload)
    for key, val in merge_into_payload.items():
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        if label == "rds_postgres":
            if key == "dbname" and rds_database_field_absent(out):
                out["dbname"] = str(val).strip()
            elif key == "host" and not _str_field(out, "host", "hostname", "endpoint", "address"):
                # RDS-managed secrets after rotation omit host; supply from config fallback.
                out["host"] = str(val).strip()
            elif key == "port" and "port" not in out:
                out["port"] = val
    return out


def load_secret_slot(
    *,
    label: str,
    env_json: Optional[str],
    secret_id: Optional[str],
    reader: Optional[ISecretsReader],
    parser: Callable[[Dict[str, Any]], T],
    merge_into_payload: Optional[Dict[str, Any]] = None,
) -> Optional[T]:
    """Precedence: inline env JSON → Secrets Manager by id → None."""
    if env_json:
        data = parse_inline_secret_json(env_json)
        if data is not None:
            try:
                return parser(data)
            except Exception:
                logger.exception("Failed to parse %s from inline env JSON", label)
                raise
    sid = (secret_id or "").strip()
    if not sid:
        return None
    if reader is None:
        logger.warning(
            "Secret id is set for %s but no Secrets Manager reader could be built "
            "(install boto3, set region/profile).",
            label,
        )
        return None
    try:
        payload = reader.get_secret_json(sid)
        merged = _merge_into_sm_payload(label, payload, merge_into_payload)
        return parser(merged)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "ExpiredTokenException":
            logger.warning(
                "AWS credentials expired; cannot load %s from Secrets Manager (%r). "
                "Refresh credentials (e.g. `aws sso login`) and restart.",
                label,
                sid,
            )
            return None
        logger.exception("Failed to load %s from Secrets Manager id %r", label, sid)
        raise
    except Exception:
        logger.exception("Failed to load %s from Secrets Manager id %r", label, sid)
        raise

"""Opaque pagination tokens for DynamoDB ``LastEvaluatedKey``."""

from __future__ import annotations

import base64
import json
from typing import Any, cast


def encode_exclusive_start_key(key: dict[str, Any] | None) -> str:
    """Serialize Dynamo ``LastEvaluatedKey`` for clients."""
    if not key:
        return ""
    raw = json.dumps(key, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_exclusive_start_key(token: str) -> dict[str, Any] | None:
    """Parse a client page token back to Dynamo ``ExclusiveStartKey``."""
    if not token.strip():
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        loaded = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    return cast(dict[str, Any], loaded)

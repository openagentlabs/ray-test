"""Invite code format: four alphanumerics, hyphen, two, hyphen, four (all uppercase)."""

from __future__ import annotations

import re
import secrets
import string

_INVITE_CODE_RE = re.compile(r"^[0-9A-Z]{4}-[0-9A-Z]{2}-[0-9A-Z]{4}$")
_ALNUM = string.ascii_uppercase + string.digits


def normalize_invite_code(raw: str) -> str:
    """Uppercase; if ten alphanumeric characters are present, insert hyphens."""
    compact = "".join(ch for ch in raw if ch.isalnum()).upper()
    if len(compact) == 10:
        return f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"
    return raw.strip().upper()


def is_valid_invite_code(code: str) -> bool:
    return bool(_INVITE_CODE_RE.match(code))


def generate_random_invite_code() -> str:
    """Return a fresh ``XXXX-XX-XXXX`` code using uppercase letters and digits."""
    parts = (
        "".join(secrets.choice(_ALNUM) for _ in range(4)),
        "".join(secrets.choice(_ALNUM) for _ in range(2)),
        "".join(secrets.choice(_ALNUM) for _ in range(4)),
    )
    return f"{parts[0]}-{parts[1]}-{parts[2]}"

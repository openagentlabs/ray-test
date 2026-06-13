"""Email format validation for login identity (sub)."""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value: str) -> bool:
    candidate = value.strip()
    if not candidate or len(candidate) > 320:
        return False
    return _EMAIL_RE.match(candidate) is not None

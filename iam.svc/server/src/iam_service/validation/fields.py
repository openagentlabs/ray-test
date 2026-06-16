"""Reusable Pydantic field types for IAM request validation."""

from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, Field, StringConstraints

from iam_service.core.invite_codes import is_valid_invite_code, normalize_invite_code

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

PersonName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]

SignUpPassword = Annotated[
    str,
    StringConstraints(min_length=8, max_length=512),
]

SignInPassword = Annotated[
    str,
    StringConstraints(min_length=1, max_length=512),
]

OptionalNotes = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=2000),
]


def _normalize_invite_field(value: str) -> str:
    code = normalize_invite_code(value)
    if not is_valid_invite_code(code):
        msg = "Invite code must match format XXXX-XX-XXXX (uppercase letters and digits)."
        raise ValueError(msg)
    return code


InviteCode = Annotated[str, AfterValidator(_normalize_invite_field)]


def _require_uuid(value: str) -> str:
    text = value.strip()
    if not text:
        msg = "UUID is required."
        raise ValueError(msg)
    if not UUID_RE.match(text):
        msg = "Value must be a valid UUID."
        raise ValueError(msg)
    try:
        UUID(text)
    except ValueError as exc:
        msg = "Value must be a valid UUID."
        raise ValueError(msg) from exc
    return text


RequiredUuid = Annotated[str, AfterValidator(_require_uuid)]


def _optional_uuid(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    return _require_uuid(text)


OptionalUuid = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=36), AfterValidator(_optional_uuid)
]

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _validate_email(value: str) -> str:
    text = value.strip().lower()
    if not _EMAIL_RE.match(text):
        msg = "A valid email is required."
        raise ValueError(msg)
    return text


EmailField = Annotated[
    str, StringConstraints(strip_whitespace=True), AfterValidator(_validate_email)
]

NonEmptyId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]

PageSize = Annotated[int, Field(ge=0, le=500)]

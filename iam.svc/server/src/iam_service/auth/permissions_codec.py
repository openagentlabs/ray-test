"""Compressed permission string codec for auth tokens."""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success

# Service and function ids: 5-12 chars, alphanumeric + hyphen only.
_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z0-9-]{5,12}$")

# Format: svcId:fn1,fn2>svcId2:fn3
_SERVICE_SEPARATOR: Final[str] = ">"
_FUNCTION_SEPARATOR: Final[str] = ","
_BINDING_SEPARATOR: Final[str] = ":"

FORBIDDEN_IN_IDS: Final[frozenset[str]] = frozenset(
    {_SERVICE_SEPARATOR, _FUNCTION_SEPARATOR, _BINDING_SEPARATOR},
)


class ServicePermissionGrant(BaseModel):
    """One service id and its granted function ids."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    service_id: str = Field(..., min_length=5, max_length=12)
    function_ids: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("service_id")
    @classmethod
    def validate_service_id(cls, value: str) -> str:
        return _validate_identifier(value, label="service_id")

    @field_validator("function_ids")
    @classmethod
    def validate_function_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            msg = "At least one function_id is required per service grant."
            raise ValueError(msg)
        seen: set[str] = set()
        validated: list[str] = []
        for fn in value:
            fn_id = _validate_identifier(fn, label="function_id")
            if fn_id in seen:
                msg = f"Duplicate function_id: {fn_id}"
                raise ValueError(msg)
            seen.add(fn_id)
            validated.append(fn_id)
        return tuple(validated)


class PermissionGrantSet(BaseModel):
    """Structured permission grants before compression."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    grants: tuple[ServicePermissionGrant, ...] = Field(default_factory=tuple)

    @field_validator("grants")
    @classmethod
    def validate_grants(
        cls,
        value: tuple[ServicePermissionGrant, ...],
    ) -> tuple[ServicePermissionGrant, ...]:
        seen: set[str] = set()
        for grant in value:
            if grant.service_id in seen:
                msg = f"Duplicate service_id: {grant.service_id}"
                raise ValueError(msg)
            seen.add(grant.service_id)
        return value


def _validate_identifier(value: str, *, label: str) -> str:
    trimmed = value.strip()
    if not _ID_PATTERN.fullmatch(trimmed):
        msg = (
            f"{label} must be 5-12 alphanumeric or hyphen characters; "
            f"reserved separators are forbidden."
        )
        raise ValueError(msg)
    for char in FORBIDDEN_IN_IDS:
        if char in trimmed:
            msg = f"{label} must not contain reserved separator {char!r}."
            raise ValueError(msg)
    return trimmed


def encode_permissions(grants: PermissionGrantSet) -> Result[str, AppError]:
    """Serialize grants to the compressed token permission string."""
    if not grants.grants:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Permission grant set cannot be empty.",
                detail=None,
            ),
        )
    parts: list[str] = []
    for grant in grants.grants:
        fn_part = _FUNCTION_SEPARATOR.join(grant.function_ids)
        parts.append(f"{grant.service_id}{_BINDING_SEPARATOR}{fn_part}")
    return Success(_SERVICE_SEPARATOR.join(parts))


def decode_permissions(encoded: str) -> Result[PermissionGrantSet, AppError]:
    """Parse and validate a compressed permission string."""
    trimmed = encoded.strip()
    if not trimmed:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Permission string cannot be empty.",
                detail=None,
            ),
        )
    if any(sep in trimmed for sep in ("|", ";", " ", "\t", "\n")):
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Permission string contains invalid separator characters.",
                detail=None,
            ),
        )
    grant_parts = trimmed.split(_SERVICE_SEPARATOR)
    grants: list[ServicePermissionGrant] = []
    for part in grant_parts:
        if _BINDING_SEPARATOR not in part:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Malformed permission segment: missing service binding.",
                    detail=part,
                ),
            )
        service_raw, fn_raw = part.split(_BINDING_SEPARATOR, maxsplit=1)
        if not fn_raw:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Malformed permission segment: missing functions.",
                    detail=part,
                ),
            )
        function_ids = tuple(fn_raw.split(_FUNCTION_SEPARATOR))
        try:
            grants.append(
                ServicePermissionGrant(service_id=service_raw, function_ids=function_ids),
            )
        except ValueError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Invalid permission identifier.",
                    detail=str(exc),
                ),
            )
    try:
        return Success(PermissionGrantSet(grants=tuple(grants)))
    except ValueError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Invalid permission grant set.",
                detail=str(exc),
            ),
        )


def validate_permission_string(encoded: str) -> Result[None, AppError]:
    """Validate format without returning structured grants."""
    decoded = decode_permissions(encoded)
    if isinstance(decoded, Failure):
        return decoded
    return Success(None)

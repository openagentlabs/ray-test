"""Validate ``ResetDatabase`` gRPC requests."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationError

from iam.v1 import iam_pb2
from iam_service.core.errors import AppError
from iam_service.core.results import Failure, Result, Success
from iam_service.validation.fields import EmailField, SignInPassword
from iam_service.validation.format_errors import validation_error_to_app_error


class ResetDatabaseInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    username: EmailField
    password: SignInPassword


def names_from_username(username: str) -> tuple[str, str]:
    """Derive display names from the email local part (e.g. keith.tobin -> Keith, Tobin)."""
    local = username.split("@", maxsplit=1)[0]
    parts = [segment.capitalize() for segment in local.replace("_", ".").split(".") if segment]
    if len(parts) >= 2:
        return parts[0], parts[-1]
    if len(parts) == 1:
        return parts[0], "User"
    return "Admin", "User"


def validate_reset_database_request(
    request: iam_pb2.ResetDatabaseRequest,
) -> Result[tuple[ResetDatabaseInput, str, str], AppError]:
    """Return validated credentials plus derived ``first_name`` / ``last_name``."""
    try:
        validated = ResetDatabaseInput.model_validate(
            {"username": request.username, "password": request.password},
        )
    except ValidationError as exc:
        return Failure(validation_error_to_app_error(exc))

    first_name, last_name = names_from_username(validated.username)
    return Success((validated, first_name, last_name))

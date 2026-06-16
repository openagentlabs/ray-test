"""Validation for ``SignOut`` gRPC requests."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError

from iam.v1 import iam_pb2
from iam_service.core.errors import AppError
from iam_service.core.results import Failure, Result, Success
from iam_service.validation.format_errors import validation_error_to_app_error


class SignOutInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    session_id: UUID


def validate_sign_out_request(
    request: iam_pb2.SignOutRequest,
) -> Result[SignOutInput, AppError]:
    try:
        validated = SignOutInput.model_validate({"session_id": request.session_id})
    except ValidationError as exc:
        return Failure(validation_error_to_app_error(exc))
    return Success(validated)

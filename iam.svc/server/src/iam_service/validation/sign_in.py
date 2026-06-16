"""Validate sign-in gRPC requests."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from iam.v1 import iam_pb2
from iam_service.core.errors import AppError
from iam_service.core.results import Failure, Result, Success
from iam_service.validation.fields import SignInPassword
from iam_service.validation.format_errors import validation_error_to_app_error

Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=320),
]


class SignInInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    username: Username
    password: SignInPassword


def validate_sign_in_request(request: iam_pb2.SignInRequest) -> Result[SignInInput, AppError]:
    try:
        validated = SignInInput.model_validate(
            {"username": request.username, "password": request.password},
        )
    except ValidationError as exc:
        return Failure(validation_error_to_app_error(exc))
    return Success(validated)


def validate_sign_in_check_request(
    request: iam_pb2.SignInCheckRequest,
) -> Result[SignInInput, AppError]:
    try:
        validated = SignInInput.model_validate(
            {"username": request.username, "password": request.password},
        )
    except ValidationError as exc:
        return Failure(validation_error_to_app_error(exc))
    return Success(validated)

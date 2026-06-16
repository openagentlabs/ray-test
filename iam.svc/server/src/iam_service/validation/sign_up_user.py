"""Validate ``SignUpUser`` gRPC requests."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from iam.v1 import iam_pb2
from iam_service.core.errors import AppError
from iam_service.core.results import Failure, Result, Success
from iam_service.validation.fields import EmailField, InviteCode, PersonName, SignUpPassword
from iam_service.validation.format_errors import validation_error_to_app_error


class SignUpUserInput(BaseModel):
    """Normalized sign-up payload after schema validation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    email: EmailField
    first_name: PersonName
    last_name: PersonName
    password: SignUpPassword
    password_confirm: str
    invite_code: InviteCode

    @model_validator(mode="after")
    def passwords_match(self) -> SignUpUserInput:
        if self.password != self.password_confirm:
            msg = "Passwords do not match."
            raise ValueError(msg)
        return self


def validate_sign_up_user_request(
    request: iam_pb2.SignUpUserRequest,
) -> Result[SignUpUserInput, AppError]:
    """Validate protobuf input; returns normalized fields for ``sign_up_user``."""
    try:
        validated = SignUpUserInput.model_validate(
            {
                "email": request.email,
                "first_name": request.first_name,
                "last_name": request.last_name,
                "password": request.password,
                "password_confirm": request.password_confirm,
                "invite_code": request.invite_code,
            },
        )
    except ValidationError as exc:
        return Failure(validation_error_to_app_error(exc))
    return Success(validated)

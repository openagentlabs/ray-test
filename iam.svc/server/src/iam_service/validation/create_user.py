"""Validate ``CreateUser`` gRPC requests."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from iam.v1 import iam_pb2
from iam_service.core.errors import AppError
from iam_service.core.results import Failure, Result, Success
from iam_service.validation.fields import OptionalNotes, OptionalUuid, PersonName, RequiredUuid
from iam_service.validation.format_errors import validation_error_to_app_error


class CreateUserInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    first_name: PersonName
    last_name: PersonName
    account_id: RequiredUuid
    user_type_id: RequiredUuid
    skill_list_id: OptionalUuid = ""
    skill_ids: list[RequiredUuid] = Field(default_factory=list)
    notes: OptionalNotes = ""
    timezone: OptionalNotes = ""
    location: OptionalNotes = ""
    enabled: bool = True

    @field_validator("skill_ids", mode="before")
    @classmethod
    def _strip_skill_ids(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            return []
        out: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                out.append(text)
        return out


def validate_create_user_request(
    request: iam_pb2.CreateUserRequest,
) -> Result[CreateUserInput, AppError]:
    try:
        validated = CreateUserInput.model_validate(
            {
                "first_name": request.first_name,
                "last_name": request.last_name,
                "account_id": request.account_id,
                "user_type_id": request.user_type_id,
                "skill_list_id": request.skill_list_id,
                "skill_ids": list(request.skill_ids),
                "notes": request.notes,
                "timezone": request.timezone,
                "location": request.location,
                "enabled": request.enabled,
            },
        )
    except ValidationError as exc:
        return Failure(validation_error_to_app_error(exc))
    return Success(validated)

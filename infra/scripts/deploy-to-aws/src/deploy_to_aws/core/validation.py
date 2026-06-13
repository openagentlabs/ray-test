"""Shared Pydantic ingress helpers."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ValidationError

from deploy_to_aws.core.errors import AppError, ErrorCodes
from deploy_to_aws.core.results import Failure, Success
from deploy_to_aws.core.types import DeployResult


def format_validation_detail(exc: ValidationError) -> str:
    """Render pydantic validation errors as a single line."""
    parts = [
        f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
        for err in exc.errors()
    ]
    return "; ".join(parts)


def parse_invoke_model[ModelT: BaseModel](
    model_type: type[ModelT],
    kwargs: Mapping[str, object],
    *,
    message: str,
) -> DeployResult[ModelT]:
    """Validate action invoke kwargs against a frozen Pydantic model."""
    allowed = set(model_type.model_fields)
    payload = {key: kwargs[key] for key in allowed if key in kwargs}
    try:
        return Success(model_type.model_validate(payload))
    except ValidationError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message=message,
                detail=format_validation_detail(exc),
            ),
        )

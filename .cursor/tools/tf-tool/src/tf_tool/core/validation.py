"""Shared Pydantic ingress helpers for action invoke kwargs."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ValidationError

from tf_tool.core.error_format import format_validation_detail
from tf_tool.core.errors import AppError, ErrorCodes
from tf_tool.core.results import Failure, Success
from tf_tool.core.types import TfResult


def parse_invoke_model[ModelT: BaseModel](
    model_type: type[ModelT],
    kwargs: Mapping[str, object],
    *,
    message: str,
) -> TfResult[ModelT]:
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

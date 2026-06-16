"""Map Pydantic ``ValidationError`` to ``AppError`` with field-level detail."""

from __future__ import annotations

import json

from pydantic import ValidationError

from iam_service.core.errors import AppError, ErrorCodes


def validation_error_to_app_error(exc: ValidationError) -> AppError:
    """Build a validation ``AppError`` with a short message and JSON field detail."""
    issues = [
        {
            "field": ".".join(str(part) for part in err["loc"]),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    parts = [f"{item['field']}: {item['message']}" for item in issues if item["field"]]
    if not parts:
        parts = [err["msg"] for err in exc.errors() if err.get("msg")]
    message = "; ".join(parts[:4])
    if len(parts) > 4:
        message = f"{message}; and {len(parts) - 4} more issue(s)"
    if not message:
        message = "Request validation failed."
    detail = json.dumps({"fields": issues}, separators=(",", ":"))
    return AppError(code=ErrorCodes.VALIDATION, message=message, detail=detail)

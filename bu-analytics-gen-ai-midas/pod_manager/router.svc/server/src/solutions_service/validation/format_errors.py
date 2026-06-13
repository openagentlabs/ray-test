"""Map Pydantic ``ValidationError`` to ``AppError``."""

from __future__ import annotations

import json

from pydantic import ValidationError

from solutions_service.core.errors import AppError, ErrorCodes


def validation_error_to_app_error(exc: ValidationError) -> AppError:
    issues = [
        {"field": ".".join(str(part) for part in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    parts = [f"{item['field']}: {item['message']}" for item in issues if item["field"]]
    message = "; ".join(parts[:4]) or "Request validation failed."
    detail = json.dumps({"fields": issues}, separators=(",", ":"))
    return AppError(code=ErrorCodes.VALIDATION, message=message, detail=detail)

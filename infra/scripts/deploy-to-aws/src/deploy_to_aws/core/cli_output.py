"""CLI output helpers."""

from __future__ import annotations

import json
import sys

from deploy_to_aws.core.errors import AppError
from deploy_to_aws.core.results import Failure
from deploy_to_aws.core.types import TextResult


def die_json_error(err: AppError, *, exit_code: int = 2) -> None:
    """Print structured JSON error and exit."""
    payload = err.model_dump(exclude_none=True)
    print(json.dumps(payload, indent=2), file=sys.stderr)
    raise SystemExit(exit_code)


def emit_result(
    result: TextResult, *, success_exit: int = 0, failure_exit: int = 1
) -> None:
    """Print action output or JSON error and exit."""
    if isinstance(result, Failure):
        die_json_error(result.failure(), exit_code=failure_exit)
    print(result.unwrap())
    raise SystemExit(success_exit)

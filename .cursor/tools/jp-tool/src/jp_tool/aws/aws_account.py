"""AWS account identity object."""

from __future__ import annotations

import re
from typing import Final

from jp_tool.core.errors import AppError, ErrorCodes
from jp_tool.core.results import Failure, Success
from jp_tool.core.types import JpResult

AWS_ACCOUNT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\d{12}$")


class AwsAccount:
    """Immutable AWS account holder with a validated twelve-digit account id."""

    def __init__(self, account_id: str) -> None:
        self._account_id = account_id

    @property
    def account_id(self) -> str:
        """Read-only AWS account id supplied at construction."""
        return self._account_id

    @classmethod
    def new(cls, account_id: str) -> JpResult[AwsAccount]:
        """Create an account after validating the mandatory account id."""
        if not account_id or not account_id.strip():
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="AWS account id is required",
                    detail="account_id must be a non-empty string",
                ),
            )

        normalized = account_id.strip()
        if AWS_ACCOUNT_ID_PATTERN.fullmatch(normalized) is None:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="AWS account id has invalid format",
                    detail="account_id must be exactly 12 digits",
                ),
            )

        return Success(cls(normalized))

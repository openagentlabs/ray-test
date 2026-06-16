"""AWS CLI connection identity object."""

from __future__ import annotations

import re
from typing import Final

from jp_tool.aws.connection_info_base import ConnectionInfoBase
from jp_tool.core.errors import AppError, ErrorCodes
from jp_tool.core.results import Failure, Success
from jp_tool.core.types import JpResult

AWS_PROFILE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_-]+$")
AWS_REGION_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9-]{2,64}$")


class ConnectionInfo(ConnectionInfoBase):
    """Immutable AWS connection holder with validated profile and region."""

    def __init__(self, profile: str, region: str) -> None:
        self._profile = profile
        self._region = region

    @property
    def profile(self) -> str:
        """Read-only AWS CLI profile name supplied at construction."""
        return self._profile

    @property
    def region(self) -> str:
        """Read-only AWS region id supplied at construction."""
        return self._region

    @classmethod
    def new(cls, profile: str, region: str) -> JpResult[ConnectionInfo]:
        """Create connection info after validating mandatory profile and region."""
        if not profile or not profile.strip():
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="AWS profile is required",
                    detail="profile must be a non-empty string",
                ),
            )

        if not region or not region.strip():
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="AWS region is required",
                    detail="region must be a non-empty string",
                ),
            )

        normalized_profile = profile.strip()
        normalized_region = region.strip().lower()

        if AWS_PROFILE_PATTERN.fullmatch(normalized_profile) is None:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="AWS profile has invalid format",
                    detail="profile may contain only letters, digits, underscores, and hyphens",
                ),
            )

        if AWS_REGION_PATTERN.fullmatch(normalized_region) is None:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="AWS region has invalid format",
                    detail="region must be 2-64 lowercase letters, digits, or hyphens",
                ),
            )

        return Success(cls(normalized_profile, normalized_region))

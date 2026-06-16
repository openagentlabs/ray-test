"""Core types shared across observability interfaces."""

from exl_observability.core.correlation import (
    get_correlation_id,
    new_correlation_token,
    reset_correlation_token,
)
from exl_observability.core.errors import ErrorCodes, ObsError
from exl_observability.core.result import Failure, Result, Success

__all__ = (
    "ErrorCodes",
    "Failure",
    "ObsError",
    "Result",
    "Success",
    "get_correlation_id",
    "new_correlation_token",
    "reset_correlation_token",
)

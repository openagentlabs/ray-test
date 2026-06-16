"""Structured errors for observability operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


class ErrorCodes:
    """Stable error codes returned by observability clients and drivers."""

    VALIDATION: Final[str] = "OBS_VALIDATION"
    CONFIG: Final[str] = "OBS_CONFIG"
    DRIVER: Final[str] = "OBS_DRIVER"
    INTERNAL: Final[str] = "OBS_INTERNAL"
    NOT_INITIALIZED: Final[str] = "OBS_NOT_INITIALIZED"
    METRIC_UNKNOWN: Final[str] = "OBS_METRIC_UNKNOWN"


@dataclass(frozen=True, slots=True)
class ObsError:
    """Human-readable observability failure."""

    code: str
    message: str
    detail: str | None = None

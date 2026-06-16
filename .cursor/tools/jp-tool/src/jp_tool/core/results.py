"""``returns`` re-exports and jp-tool ``Result`` type aliases."""

from __future__ import annotations

from returns.result import Failure, Result, Success

from jp_tool.core.types import JpResult, TextResult, UnitResult

__all__ = (
    "JpResult",
    "Failure",
    "Result",
    "Success",
    "TextResult",
    "UnitResult",
)

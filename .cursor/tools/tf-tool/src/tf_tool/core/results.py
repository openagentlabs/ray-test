"""``returns`` re-exports and tf-tool ``Result`` type aliases."""

from __future__ import annotations

from returns.result import Failure, Result, Success

from tf_tool.core.types import TextResult, TfResult, UnitResult

__all__ = (
    "Failure",
    "Result",
    "Success",
    "TextResult",
    "TfResult",
    "UnitResult",
)

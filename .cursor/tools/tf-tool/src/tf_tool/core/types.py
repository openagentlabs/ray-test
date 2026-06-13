"""Canonical ``Result`` aliases for tf-tool public APIs."""

from __future__ import annotations

from typing import TypeVar

from returns.result import Result

from tf_tool.core.errors import AppError

T = TypeVar("T")

TfResult = Result[T, AppError]
"""Typed ``Result`` carrying ``AppError`` on failure (Rust ``anyhow``-style boundary)."""

TextResult = TfResult[str]
"""Action and CLI text output."""

UnitResult = TfResult[None]
"""Success-without-payload operations (register, bind, cleanup steps)."""

__all__ = (
    "TextResult",
    "TfResult",
    "UnitResult",
)

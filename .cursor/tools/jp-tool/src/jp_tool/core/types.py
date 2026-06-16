"""Canonical ``Result`` aliases for jp-tool public APIs."""

from __future__ import annotations

from typing import TypeVar

from returns.result import Result

from jp_tool.core.errors import AppError

T = TypeVar("T")

JpResult = Result[T, AppError]
"""Typed ``Result`` carrying ``AppError`` on failure."""

TextResult = JpResult[str]
"""CLI and action text output."""

UnitResult = JpResult[None]
"""Success-without-payload operations."""

__all__ = (
    "JpResult",
    "TextResult",
    "UnitResult",
)

"""Canonical ``Result`` aliases for deploy-to-aws public APIs."""

from __future__ import annotations

from typing import TypeVar

from returns.result import Result

from deploy_to_aws.core.errors import AppError

T = TypeVar("T")

DeployResult = Result[T, AppError]
"""Typed ``Result`` carrying ``AppError`` on failure."""

TextResult = DeployResult[str]
"""CLI and action text output."""

UnitResult = DeployResult[None]
"""Success-without-payload operations."""

__all__ = (
    "DeployResult",
    "TextResult",
    "UnitResult",
)

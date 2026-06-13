"""Shared primitives for the Terraform tool."""

from tf_tool.core.errors import AppError, ErrorCodes
from tf_tool.core.protocols import Action, RegistrySearchService
from tf_tool.core.results import Failure, Result, Success
from tf_tool.core.types import TextResult, TfResult, UnitResult

__all__ = (
    "Action",
    "AppError",
    "ErrorCodes",
    "Failure",
    "RegistrySearchService",
    "Result",
    "Success",
    "TextResult",
    "TfResult",
    "UnitResult",
)

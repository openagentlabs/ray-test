"""Re-export ``returns`` Result primitives bound to ``AppError`` failures."""

from __future__ import annotations

from returns.result import Failure, Result, Success

__all__ = ("Failure", "Result", "Success")

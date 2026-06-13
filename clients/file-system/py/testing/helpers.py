"""Shared test helpers (not pytest fixtures)."""

from __future__ import annotations

from returns.result import Failure, Success

from file_system.core.errors import AppError


def assert_success[T](result: Success[T] | Failure[AppError]) -> T:
    assert isinstance(result, Success), f"expected Success, got {type(result)}"
    return result.unwrap()


def assert_failure[T](
    result: Success[T] | Failure[AppError],
    *,
    code: str | None = None,
) -> AppError:
    assert isinstance(result, Failure), f"expected Failure, got {type(result)}"
    error = result.failure()
    assert error is not None
    if code is not None:
        assert error.code == code
    return error

"""Result helpers for dev_testing modules."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from returns.result import Failure, Result, Success

T = TypeVar("T")


def ok(value: T) -> Success[T]:
    return Success(value)


def err(message: str) -> Failure[str]:
    return Failure(message)


def unwrap(result: Result[T, str], label: str) -> T:
    if isinstance(result, Failure):
        raise RuntimeError(f"{label}: {result.failure()}")
    return result.unwrap()


def collect_results(results: list[tuple[str, Result[None, str]]]) -> Result[None, str]:
    failures = [f"{name}: {result.failure()}" for name, result in results if isinstance(result, Failure)]
    if failures:
        return Failure("\n".join(failures))
    return Success(None)


Reporter = Callable[[bool, str], None]

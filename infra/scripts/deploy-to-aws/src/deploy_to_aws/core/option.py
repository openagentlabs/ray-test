"""Optional value alias (Rust ``Option`` style)."""

from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")

type Option[T] = T | None

__all__ = ("Option",)

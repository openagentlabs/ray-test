"""Declarative ORM base (single inheritance layer: models extend this only)."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Registry for ORM metadata."""

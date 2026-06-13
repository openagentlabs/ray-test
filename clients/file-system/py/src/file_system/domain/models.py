"""Validated request models for file-system ingress."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from file_system.domain.enums import TextEncoding


class PathRequest(BaseModel):
    """Validated filesystem path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path = Field(...)


class TextWriteRequest(BaseModel):
    """Validated text write payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path = Field(...)
    text: str = Field(...)
    encoding: TextEncoding = Field(default=TextEncoding.UTF8)


class BytesWriteRequest(BaseModel):
    """Validated binary write payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path = Field(...)
    data: bytes = Field(...)

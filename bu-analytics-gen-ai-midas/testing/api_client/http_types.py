"""Shared Pydantic v2 value types for the MIDAS HTTP client."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class MultipartFile(BaseModel):
    """Describes a single file part in a multipart/form-data upload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    content: bytes
    content_type: str

    @staticmethod
    def new(
        name: str,
        content: bytes,
        content_type: Optional[str] = None,
    ) -> "MultipartFile":
        """Create a MultipartFile, defaulting content_type to octet-stream."""
        return MultipartFile(
            name=name,
            content=content,
            content_type=content_type or "application/octet-stream",
        )

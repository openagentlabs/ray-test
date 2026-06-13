"""Domain enumerations for file-system operations."""

from __future__ import annotations

from enum import StrEnum


class TextEncoding(StrEnum):
    """Supported text encodings for read and write."""

    UTF8 = "utf-8"
    UTF16 = "utf-16"
    ASCII = "ascii"
    LATIN1 = "latin-1"

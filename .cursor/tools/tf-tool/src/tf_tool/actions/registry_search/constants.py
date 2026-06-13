"""Terraform Registry API constants."""

from __future__ import annotations

from typing import Final

REGISTRY_API_BASE: Final[str] = "https://registry.terraform.io/v1/modules"
DEFAULT_TIMEOUT_SECONDS: Final[float] = 30.0
DEFAULT_LIMIT: Final[int] = 20
MAX_LIMIT: Final[int] = 100
MAX_OFFSET: Final[int] = 10_000

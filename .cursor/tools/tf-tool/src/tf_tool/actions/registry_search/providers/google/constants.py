"""Google Cloud provider constants for Terraform Registry search."""

from __future__ import annotations

from typing import Final

GOOGLE_PROVIDER: Final[str] = "google"
GOOGLE_PROVIDER_LABEL: Final[str] = "Google Cloud"

KNOWN_GOOGLE_NAMESPACES: Final[tuple[str, ...]] = (
    "GoogleCloudPlatform",
    "terraform-google-modules",
)

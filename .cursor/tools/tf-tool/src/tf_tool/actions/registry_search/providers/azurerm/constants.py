"""Azure Resource Manager provider constants for Terraform Registry search."""

from __future__ import annotations

from typing import Final

AZURERM_PROVIDER: Final[str] = "azurerm"
AZURERM_PROVIDER_LABEL: Final[str] = "Azure"

KNOWN_AZURERM_NAMESPACES: Final[tuple[str, ...]] = (
    "Azure",
    "claranet",
)

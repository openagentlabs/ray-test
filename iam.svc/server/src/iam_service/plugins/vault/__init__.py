"""Vault plugin drivers for cryptographic key storage."""

from iam_service.plugins.vault.factory import build_vault_driver
from iam_service.plugins.vault.interface import VaultDriver
from iam_service.plugins.vault.types import VaultKeyContent, VaultOperationResult

__all__ = (
    "VaultDriver",
    "VaultKeyContent",
    "VaultOperationResult",
    "build_vault_driver",
)

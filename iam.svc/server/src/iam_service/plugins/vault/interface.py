"""Vault driver interface."""

from __future__ import annotations

from typing import Protocol

from iam_service.plugins.vault.types import VaultKeyContent, VaultOperationResult


class VaultDriver(Protocol):
    """Pluggable secret store for IAM signing keys."""

    async def get_key(self, key_id: str) -> VaultOperationResult:
        """Load and validate a key by id; return error result on failure."""

    async def set_key(self, key_id: str, key_json: VaultKeyContent) -> VaultOperationResult:
        """Persist a validated key payload; return error result on failure."""

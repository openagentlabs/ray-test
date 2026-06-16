"""Local filesystem vault driver — plain JSON files under a configured directory."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from iam_service.plugins.vault.interface import VaultDriver
from iam_service.plugins.vault.types import VaultKeyContent, VaultOperationResult


class LocalVaultDriver:
    """Store vault secrets as ``{key_id}.json`` files under ``vault_path``."""

    __slots__ = ("_vault_path",)

    def __init__(self, *, vault_path: Path) -> None:
        self._vault_path = vault_path

    def _key_file(self, key_id: str) -> Path:
        safe_id = key_id.strip()
        if not safe_id or "/" in safe_id or "\\" in safe_id or ".." in safe_id:
            msg = "Invalid vault key id."
            raise ValueError(msg)
        return self._vault_path / f"{safe_id}.json"

    async def get_key(self, key_id: str) -> VaultOperationResult:
        path = self._key_file(key_id)
        if not path.is_file():
            return VaultOperationResult.err(f"Vault key not found: {key_id}")
        try:
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw)
            content = VaultKeyContent.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            return VaultOperationResult.err(f"Could not read vault key {key_id}: {exc}")
        if content.kid != key_id:
            return VaultOperationResult.err(
                f"Vault key kid mismatch: expected {key_id}, got {content.kid}",
            )
        return VaultOperationResult.ok(content)

    async def set_key(self, key_id: str, key_json: VaultKeyContent) -> VaultOperationResult:
        if key_json.kid != key_id:
            return VaultOperationResult.err(
                f"Key kid must match key_id: expected {key_id}, got {key_json.kid}",
            )
        path = self._key_file(key_id)
        try:
            self._vault_path.mkdir(parents=True, exist_ok=True)
            path.write_text(
                key_json.model_dump_json(indent=2),
                encoding="utf-8",
            )
        except (OSError, ValueError) as exc:
            return VaultOperationResult.err(f"Could not write vault key {key_id}: {exc}")
        return VaultOperationResult.ok(key_json)


def ensure_local_vault_driver(vault_path: Path) -> VaultDriver:
    return LocalVaultDriver(vault_path=vault_path)

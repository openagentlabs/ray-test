"""Unit tests for local vault driver."""

from __future__ import annotations

from pathlib import Path

import pytest

from iam_service.plugins.vault.local_driver import LocalVaultDriver
from iam_service.plugins.vault.types import VaultKeyContent


@pytest.mark.asyncio
async def test_local_vault_get_set_round_trip(tmp_path: Path) -> None:
    driver = LocalVaultDriver(vault_path=tmp_path)
    content = VaultKeyContent(
        kid="test-key-1",
        algorithm="RS256",
        private_key_pem="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        public_key_pem="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
    )
    written = await driver.set_key("test-key-1", content)
    assert written.success
    loaded = await driver.get_key("test-key-1")
    assert loaded.success
    assert loaded.key_content == content


@pytest.mark.asyncio
async def test_local_vault_missing_key(tmp_path: Path) -> None:
    driver = LocalVaultDriver(vault_path=tmp_path)
    loaded = await driver.get_key("missing-key")
    assert not loaded.success
    assert loaded.error_message is not None

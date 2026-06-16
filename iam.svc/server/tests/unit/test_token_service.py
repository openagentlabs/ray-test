"""Unit tests for JWT auth token service."""

from __future__ import annotations

from pathlib import Path

import pytest

from iam_service.auth.permissions_codec import PermissionGrantSet, ServicePermissionGrant
from iam_service.auth.token_service import AuthTokenService
from iam_service.core.results import Failure, Success
from iam_service.plugins.vault.local_driver import LocalVaultDriver


@pytest.mark.asyncio
async def test_token_issue_validate_and_jwks(tmp_path: Path) -> None:
    vault = LocalVaultDriver(vault_path=tmp_path)
    service = AuthTokenService(vault=vault, master_key_id="iam-master-key-1")
    ready = await service.ensure_master_key_exists()
    assert isinstance(ready, Success)

    grants = PermissionGrantSet(
        grants=(
            ServicePermissionGrant(
                service_id="iam-svc",
                function_ids=("readProf",),
            ),
        ),
    )
    issued = await service.issue_tokens(user_id="user-1234-5678-90ab-cdef", grants=grants)
    assert isinstance(issued, Success)
    bundle = issued.unwrap()
    validated = await service.validate_token(bundle.access_token)
    assert isinstance(validated, Success)
    assert validated.unwrap().sub == "user-1234-5678-90ab-cdef"

    jwks = await service.build_jwks()
    assert isinstance(jwks, Success)
    assert len(jwks.unwrap().keys) == 1


@pytest.mark.asyncio
async def test_refresh_token_rejected_as_access(tmp_path: Path) -> None:
    vault = LocalVaultDriver(vault_path=tmp_path)
    service = AuthTokenService(vault=vault, master_key_id="iam-master-key-1")
    await service.ensure_master_key_exists()
    grants = PermissionGrantSet(
        grants=(
            ServicePermissionGrant(
                service_id="iam-svc",
                function_ids=("readProf",),
            ),
        ),
    )
    issued = await service.issue_tokens(user_id="user-1234-5678-90ab-cdef", grants=grants)
    assert isinstance(issued, Success)
    result = await service.validate_token(issued.unwrap().refresh_token, allow_refresh=False)
    assert isinstance(result, Failure)

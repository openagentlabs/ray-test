"""Build vault driver from application config."""

from __future__ import annotations

from pathlib import Path

from iam_service.core.app_config import VaultConfig
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.plugins.vault.aws_driver import (
    AwsSecretsManagerVaultDriver,
    aws_credentials_from_env,
)
from iam_service.plugins.vault.interface import VaultDriver
from iam_service.plugins.vault.local_driver import LocalVaultDriver


def build_vault_driver(config: VaultConfig) -> Result[VaultDriver, AppError]:
    """Instantiate the configured vault driver."""
    driver_name = config.driver.strip().lower()
    if driver_name == "local":
        vault_path = Path(config.local.vault_path).expanduser().resolve()
        return Success(LocalVaultDriver(vault_path=vault_path))
    if driver_name == "aws":
        access_key, secret_key = aws_credentials_from_env()
        if config.aws.access_key_id.strip():
            access_key = config.aws.access_key_id.strip()
        if config.aws.secret_access_key.strip():
            secret_key = config.aws.secret_access_key.strip()
        return Success(
            AwsSecretsManagerVaultDriver(
                region=config.aws.region,
                expected_account_id=config.aws.account_id,
                access_key_id=access_key,
                secret_access_key=secret_key,
            ),
        )
    return Failure(
        AppError(
            code=ErrorCodes.VALIDATION,
            message="Unknown vault driver.",
            detail=f"driver={driver_name!r}",
        ),
    )

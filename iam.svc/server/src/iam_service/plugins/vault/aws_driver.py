"""AWS Secrets Manager vault driver."""

from __future__ import annotations

import json
import os

import aioboto3
from botocore.exceptions import ClientError
from pydantic import ValidationError

from iam_service.plugins.vault.types import VaultKeyContent, VaultOperationResult


class AwsSecretsManagerVaultDriver:
    """Read/write secrets via AWS Secrets Manager with account/region validation."""

    __slots__ = ("_session", "_region", "_expected_account_id")

    def __init__(
        self,
        *,
        region: str,
        expected_account_id: str,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self._region = region
        self._expected_account_id = expected_account_id.strip()
        self._session = aioboto3.Session(
            region_name=region,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
        )

    async def _validate_account(self) -> VaultOperationResult | None:
        async with self._session.client("sts") as sts:
            try:
                identity = await sts.get_caller_identity()
            except ClientError as exc:
                return VaultOperationResult.err(f"AWS STS validation failed: {exc}")
        account = str(identity.get("Account", ""))
        if account != self._expected_account_id:
            return VaultOperationResult.err(
                f"AWS account mismatch: expected {self._expected_account_id}, got {account}",
            )
        return None

    async def get_key(self, key_id: str) -> VaultOperationResult:
        account_err = await self._validate_account()
        if account_err is not None:
            return account_err
        async with self._session.client("secretsmanager", region_name=self._region) as sm:
            try:
                response = await sm.get_secret_value(SecretId=key_id)
            except ClientError as exc:
                return VaultOperationResult.err(f"AWS get_secret_value failed: {exc}")
        raw = response.get("SecretString")
        if not raw:
            return VaultOperationResult.err(f"Secret {key_id} has no string payload.")
        try:
            payload = json.loads(raw)
            content = VaultKeyContent.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            return VaultOperationResult.err(f"Invalid vault key JSON for {key_id}: {exc}")
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
        account_err = await self._validate_account()
        if account_err is not None:
            return account_err
        secret_string = key_json.model_dump_json()
        async with self._session.client("secretsmanager", region_name=self._region) as sm:
            try:
                await sm.describe_secret(SecretId=key_id)
                await sm.put_secret_value(SecretId=key_id, SecretString=secret_string)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code == "ResourceNotFoundException":
                    await sm.create_secret(Name=key_id, SecretString=secret_string)
                else:
                    return VaultOperationResult.err(f"AWS set_secret failed: {exc}")
        return VaultOperationResult.ok(key_json)


def aws_credentials_from_env() -> tuple[str | None, str | None]:
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip() or None
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip() or None
    return access_key, secret_key

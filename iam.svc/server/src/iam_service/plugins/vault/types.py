"""Vault key payload models and operation result types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VaultKeyContent(BaseModel):
    """Validated JSON payload stored in a vault secret."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kid: str = Field(..., min_length=1, description="Key identifier (matches vault key id).")
    algorithm: str = Field(default="RS256", min_length=1)
    private_key_pem: str = Field(default="", description="PEM-encoded private key for signing.")
    public_key_pem: str = Field(..., min_length=1, description="PEM-encoded public key for verify.")


class VaultOperationResult(BaseModel):
    """Success or failure from a vault driver operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    success: bool
    key_content: VaultKeyContent | None = None
    error_message: str | None = None

    @staticmethod
    def ok(key_content: VaultKeyContent) -> VaultOperationResult:
        return VaultOperationResult(success=True, key_content=key_content, error_message=None)

    @staticmethod
    def err(message: str) -> VaultOperationResult:
        return VaultOperationResult(success=False, key_content=None, error_message=message)

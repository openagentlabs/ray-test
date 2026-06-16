"""TOML-backed application configuration with ``Result``-style loading (``returns``)."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Final, cast

from exl_observability.config import ObservabilityConfig
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success

DEFAULT_APPLICATION_LOG_LEVEL: Final[str] = "DEBUG"


def _nonempty_env(key: str) -> str | None:
    raw = os.environ.get(key)
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def _apply_env_overrides_iam(
    app_raw: dict[str, object],
    api_raw: dict[str, object],
    dynamodb_raw: dict[str, object],
) -> None:
    """Process environment overrides TOML for the same logical settings (non-empty values only)."""
    log_level = _nonempty_env("IAM_APP_LOG_LEVEL") or _nonempty_env("LOG_LEVEL")
    if log_level is not None:
        app_raw["log_level"] = log_level
    host = _nonempty_env("IAM_SERVICE_HOST")
    if host is not None:
        api_raw["host"] = host
    port_s = _nonempty_env("IAM_SERVICE_PORT")
    if port_s is not None:
        try:
            api_raw["port"] = int(port_s)
        except ValueError:
            pass
    region = _nonempty_env("IAM_DYNAMODB_REGION")
    if region is not None:
        dynamodb_raw["region"] = region
    if "IAM_DYNAMODB_ENDPOINT_URL" in os.environ:
        dynamodb_raw["endpoint_url"] = os.environ["IAM_DYNAMODB_ENDPOINT_URL"].strip()


def _nested_table(raw: dict[str, object], key: str) -> dict[str, object]:
    value = raw.get(key, {})
    return value if isinstance(value, dict) else {}


def _load_vault(vault_raw: dict[str, object]) -> VaultConfig:
    local_raw = _nested_table(vault_raw, "local")
    aws_raw = _nested_table(vault_raw, "aws")
    return VaultConfig(
        driver=str(vault_raw.get("driver", "local")),
        master_key_id=str(vault_raw.get("master_key_id", "iam-master-key-1")),
        local=LocalVaultConfig.model_validate(local_raw),
        aws=AwsVaultConfig.model_validate(aws_raw),
    )


def _load_idp(idp_raw: dict[str, object]) -> IdpConfig:
    hardcoded_raw = _nested_table(idp_raw, "hardcoded")
    users_raw = hardcoded_raw.get("users", [])
    users: list[HardcodedIdpUserConfig] = []
    if isinstance(users_raw, list):
        for entry in users_raw:
            if isinstance(entry, dict):
                users.append(HardcodedIdpUserConfig.model_validate(entry))
    hardcoded = HardcodedIdpConfig(
        provider_id=str(hardcoded_raw.get("provider_id", "hardcoded-test")),
        display_name=str(hardcoded_raw.get("display_name", "Hardcoded Test IdP")),
        users=tuple(users),
    )
    return IdpConfig(
        driver=str(idp_raw.get("driver", "hardcoded")),
        hardcoded=hardcoded,
    )


def _load_http_auth(http_auth_raw: dict[str, object]) -> HttpAuthConfig:
    origins = http_auth_raw.get("cors_allow_origins", ["*"])
    if isinstance(origins, str):
        cors = (origins,)
    elif isinstance(origins, list):
        cors = tuple(str(item) for item in origins)
    else:
        cors = ("*",)
    payload = {**http_auth_raw, "cors_allow_origins": cors}
    return HttpAuthConfig.model_validate(payload)


class AppSection(BaseModel):
    """``[app]`` section from ``app_config.toml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    service_name: str = Field(default="iam-service", min_length=1)
    log_level: str = Field(
        default=DEFAULT_APPLICATION_LOG_LEVEL,
        min_length=1,
        description="Stdlib / OTel root minimum level (e.g. DEBUG, INFO).",
    )
    version: str = Field(default="0.1.0", min_length=1)


class ApiServiceConfig(BaseModel):
    """``[api_service]`` — gRPC bind address and listen port."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str = Field(default="127.0.0.1", min_length=1, description="Listen host / interface.")
    port: int = Field(
        default=8803,
        ge=1,
        le=65535,
        description="Listen port for gRPC (insecure).",
    )


class HttpAuthConfig(BaseModel):
    """``[http_auth]`` — browser-facing OAuth/SAML/password auth HTTP API."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(default=True)
    host: str = Field(default="0.0.0.0", min_length=1)
    port: int = Field(default=8873, ge=1, le=65535)
    public_base_url: str = Field(
        default="http://127.0.0.1:8873",
        min_length=1,
        description="External URL for redirects and CORS.",
    )
    cors_allow_origins: tuple[str, ...] = Field(default=("*",))


class LocalVaultConfig(BaseModel):
    """``[vault.local]`` section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    vault_path: str = Field(default="./vault", min_length=1)


class AwsVaultConfig(BaseModel):
    """``[vault.aws]`` section — credentials overridden by env when set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    region: str = Field(default="us-east-1", min_length=1)
    account_id: str = Field(default="", min_length=1)
    access_key_id: str = Field(default="")
    secret_access_key: str = Field(default="")


class VaultConfig(BaseModel):
    """``[vault]`` — pluggable secret store for signing keys."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    driver: str = Field(default="local", min_length=1)
    master_key_id: str = Field(default="iam-master-key-1", min_length=1)
    local: LocalVaultConfig = Field(default_factory=LocalVaultConfig)
    aws: AwsVaultConfig = Field(default_factory=AwsVaultConfig)


class HardcodedIdpUserConfig(BaseModel):
    """One hardcoded test user for the hardcoded IdP driver."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class HardcodedIdpConfig(BaseModel):
    """``[idp.hardcoded]`` test IdP settings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str = Field(default="hardcoded-test", min_length=1)
    display_name: str = Field(default="Hardcoded Test IdP", min_length=1)
    users: tuple[HardcodedIdpUserConfig, ...] = Field(default_factory=tuple)


class IdpConfig(BaseModel):
    """``[idp]`` — pluggable identity provider driver."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    driver: str = Field(default="hardcoded", min_length=1)
    hardcoded: HardcodedIdpConfig = Field(default_factory=HardcodedIdpConfig)


class DynamoDbTablesConfig(BaseModel):
    """Physical DynamoDB table names (one table per entity family)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    users: str = Field(..., min_length=1)
    user_types: str = Field(..., min_length=1)
    login_types: str = Field(..., min_length=1)
    logins: str = Field(..., min_length=1)
    skill_lists: str = Field(..., min_length=1)
    skills: str = Field(..., min_length=1)
    user_skills: str = Field(..., min_length=1)
    sessions: str = Field(..., min_length=1)
    invites: str = Field(..., min_length=1)
    deployment_admin: str = Field(..., min_length=1)
    roles: str = Field(..., min_length=1)
    permissions: str = Field(..., min_length=1)
    role_permissions: str = Field(..., min_length=1)
    user_role_assignments: str = Field(..., min_length=1)
    service_permissions: str = Field(..., min_length=1)
    service_function_registry: str = Field(..., min_length=1)
    user_permissions: str = Field(..., min_length=1)
    auth_sessions: str = Field(..., min_length=1)


class DynamoDbSection(BaseModel):
    """``[dynamodb]`` — region, optional custom endpoint, nested table names."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    region: str = Field(default="us-east-1", min_length=1)
    endpoint_url: str = Field(
        default="",
        description="Empty string uses default AWS endpoint for the region.",
    )
    tables: DynamoDbTablesConfig


class AppConfig(BaseModel):
    """Root configuration object: one nested model per TOML top-level table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    app: AppSection
    api_service: ApiServiceConfig
    http_auth: HttpAuthConfig = Field(default_factory=HttpAuthConfig)
    vault: VaultConfig = Field(default_factory=VaultConfig)
    idp: IdpConfig = Field(default_factory=IdpConfig)
    dynamodb: DynamoDbSection
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig.defaults)

    @staticmethod
    def load(path: Path) -> Result[AppConfig, AppError]:
        """Load and validate TOML at ``path``; failures return ``Failure(AppError)``."""
        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="Could not read application config file.",
                    detail=f"path={path!s} error={exc!s}",
                ),
            )

        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Application config file is not valid UTF-8.",
                    detail=str(exc),
                ),
            )

        try:
            loaded = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Application config file is not valid TOML.",
                    detail=str(exc),
                ),
            )

        if not isinstance(loaded, dict):
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Application config root must be a TOML table.",
                    detail=None,
                ),
            )

        tables = cast(dict[str, object], loaded)
        app_raw = tables.get("app", {})
        api_raw = tables.get("api_service", {})
        http_auth_raw = tables.get("http_auth", {})
        vault_raw = tables.get("vault", {})
        idp_raw = tables.get("idp", {})
        dynamodb_raw = tables.get("dynamodb", {})
        if not isinstance(app_raw, dict):
            app_raw = {}
        if not isinstance(api_raw, dict):
            api_raw = {}
        if not isinstance(http_auth_raw, dict):
            http_auth_raw = {}
        if not isinstance(vault_raw, dict):
            vault_raw = {}
        if not isinstance(idp_raw, dict):
            idp_raw = {}
        if not isinstance(dynamodb_raw, dict):
            dynamodb_raw = {}

        tables_raw = dynamodb_raw.get("tables", {})
        if not isinstance(tables_raw, dict):
            tables_raw = {}

        _apply_env_overrides_iam(app_raw, api_raw, dynamodb_raw)

        dynamodb_payload = {**dynamodb_raw, "tables": tables_raw}

        try:
            app_section = AppSection.model_validate(app_raw)
            api_section = ApiServiceConfig.model_validate(api_raw)
            http_auth_section = _load_http_auth(http_auth_raw)
            vault_section = _load_vault(vault_raw)
            idp_section = _load_idp(idp_raw)
            dynamodb_section = DynamoDbSection.model_validate(dynamodb_payload)
            observability_section = ObservabilityConfig.from_toml_tables(tables)
        except ValidationError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="Application config failed validation.",
                    detail=exc.json(),
                ),
            )

        return Success(
            AppConfig(
                app=app_section,
                api_service=api_section,
                http_auth=http_auth_section,
                vault=vault_section,
                idp=idp_section,
                dynamodb=dynamodb_section,
                observability=observability_section,
            ),
        )

    @staticmethod
    def default() -> AppConfig:
        """In-process defaults for tests or minimal runs."""
        return AppConfig(
            app=AppSection(),
            api_service=ApiServiceConfig(),
            http_auth=HttpAuthConfig(),
            vault=VaultConfig(),
            idp=IdpConfig(),
            dynamodb=DynamoDbSection(
                tables=DynamoDbTablesConfig(
                    users="iam-users",
                    user_types="iam-user-types",
                    login_types="iam-login-types",
                    logins="iam-logins",
                    skill_lists="iam-skill-lists",
                    skills="iam-skills",
                    user_skills="iam-user-skills",
                    sessions="iam-sessions",
                    invites="iam-invites",
                    deployment_admin="iam-deployment-admin",
                    roles="iam-roles",
                    permissions="iam-permissions",
                    role_permissions="iam-role-permissions",
                    user_role_assignments="iam-user-role-assignments",
                    service_permissions="iam-service-permissions",
                    service_function_registry="iam-service-function-registry",
                    user_permissions="iam-user-permissions",
                    auth_sessions="iam-auth-sessions",
                ),
            ),
        )

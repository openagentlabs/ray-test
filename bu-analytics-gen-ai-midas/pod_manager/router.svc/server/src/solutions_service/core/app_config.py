"""TOML-backed application configuration with ``Result``-style loading (``returns``)."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from solutions_service.core.config_env import apply_env_overrides_to_config
from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success
from solutions_service.core.table_names import physical_table_name

DEFAULT_APPLICATION_LOG_LEVEL: Final[str] = "DEBUG"


def _ensure_section(raw: dict[str, object], key: str) -> dict[str, object]:
    section = raw.get(key)
    if not isinstance(section, dict):
        section = {}
        raw[key] = section
    return section


class AppSection(BaseModel):
    """``[app]`` section from ``app_config.toml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    service_name: str = Field(default="router-svc", min_length=1)
    log_level: str = Field(
        default=DEFAULT_APPLICATION_LOG_LEVEL,
        min_length=1,
        description="Stdlib / OTel root minimum level (e.g. DEBUG, INFO).",
    )


class ApiServiceConfig(BaseModel):
    """``[api_service]`` — gRPC bind address and listen port."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str = Field(default="127.0.0.1", min_length=1, description="Listen host / interface.")
    port: int = Field(
        default=8804,
        ge=1,
        le=65535,
        description="Listen port for gRPC (insecure).",
    )


_ROUTING_TABLES: Final[tuple[str, ...]] = (
    "backend_pool",
    "login_pod_pool",
    "user_assignments",
    "assignment_events",
    "solution_documents",
    "service_config",
)


class PostgresSection(BaseModel):
    """``[postgres]`` — connection DSN, table prefix, and pool sizing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dsn: str = Field(
        default="",
        description="Postgres DSN; empty falls back to the DATABASE_URL env alias.",
    )
    schema_name: str = Field(
        default="pod_manager",
        pattern=r"^[a-z_][a-z0-9_]*$",
        description="Dedicated Postgres schema that owns every routing-tier table.",
    )
    table_prefix: str = Field(
        default="pm_",
        pattern=r"^[a-z_][a-z0-9_]*$",
        description="Prefix applied to every routing-tier table (e.g. pm_backend_pool).",
    )
    pool_min: int = Field(default=1, ge=1, le=100)
    pool_max: int = Field(default=10, ge=1, le=200)
    command_timeout_sec: float = Field(default=10.0, gt=0.0)


class ExtAuthzConfig(BaseModel):
    """``[ext_authz]`` — gRPC Authorization.Check listener (DS-2, DS-6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=9000, ge=1, le=65535)


class KubernetesConfig(BaseModel):
    """``[kubernetes]`` — EKS / in-cluster backend pod discovery."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(default=False)
    namespace: str = Field(default="routing", min_length=1)
    pod_label_selector: str = Field(default="app=backend-pool-node", min_length=1)
    headless_service_name: str = Field(default="backend-pool-node", min_length=1)
    backend_port: int = Field(default=8080, ge=1, le=65535)
    use_in_cluster_config: bool = Field(default=True)
    kubeconfig_path: str = Field(
        default="",
        description="Path to kubeconfig when use_in_cluster_config is false.",
    )


class ReconciliationConfig(BaseModel):
    """``[reconciliation]`` — background backend_pool sync (OP-7)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(default=True)
    interval_sec: float = Field(default=30.0, gt=0.0)


class AuthConfig(BaseModel):
    """``[auth]`` — identity for ext_authz (SR-1; dev header for local testing)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dev_mode: bool = Field(
        default=True,
        description="When true, allow dev_sub_header for identity (non-production).",
    )
    dev_sub_header: str = Field(
        default="x-test-sub",
        description="HTTP header supplying Cognito sub substitute when dev_mode is true.",
    )
    session_cookie_name: str = Field(
        default="pod_manager_user",
        min_length=1,
        description="Cookie name set by pods/login_pod; value is user email used as sub.",
    )


class LoginPodPoolConfig(BaseModel):
    """``[login_pod_pool]`` — routing target for users without a backend lease."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    routing_upstream: str = Field(
        default="login-pod:8080",
        min_length=1,
        description="host:port for Envoy dynamic forward proxy when no lease exists.",
    )


class CognitoConfig(BaseModel):
    """``[cognito]`` — JWT validation for ext_authz (SR-1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(default=False)
    issuer: str = Field(default="", description="Expected JWT iss claim.")
    audience: str = Field(default="", description="Expected JWT aud claim.")
    jwks_uri: str = Field(default="", description="Optional JWKS URL override.")


class ReaperConfig(BaseModel):
    """``[reaper]`` — idle assignment reaper (OP-4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(default=True)
    interval_sec: float = Field(default=60.0, gt=0.0)
    idle_ttl_sec: float = Field(default=900.0, gt=0.0)


class EnvoyManagementConfig(BaseModel):
    """``[envoy_management]`` — co-located Envoy admin (PM-3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(default=False)
    admin_host: str = Field(default="127.0.0.1")
    admin_port: int = Field(default=9901, ge=1, le=65535)


class AppConfig(BaseModel):
    """Root configuration object: one nested model per TOML top-level table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    app: AppSection
    api_service: ApiServiceConfig
    ext_authz: ExtAuthzConfig
    kubernetes: KubernetesConfig
    reconciliation: ReconciliationConfig
    auth: AuthConfig
    cognito: CognitoConfig
    reaper: ReaperConfig
    envoy_management: EnvoyManagementConfig
    login_pod_pool: LoginPodPoolConfig
    postgres: PostgresSection

    def physical_table(
        self,
        table: Literal[
            "backend_pool",
            "login_pod_pool",
            "user_assignments",
            "assignment_events",
            "solution_documents",
            "service_config",
        ],
    ) -> str:
        """Physical Postgres table name: ``{table_prefix}{logical_name}``."""
        return physical_table_name(self.postgres.table_prefix, table)

    def physical_tables(self) -> dict[str, str]:
        """Resolved physical table names keyed by logical config field."""
        return {field: self.physical_table(field) for field in _ROUTING_TABLES}  # type: ignore[arg-type]

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
        app_raw = _ensure_section(tables, "app")
        api_raw = _ensure_section(tables, "api_service")
        ext_authz_raw = _ensure_section(tables, "ext_authz")
        kubernetes_raw = _ensure_section(tables, "kubernetes")
        reconciliation_raw = _ensure_section(tables, "reconciliation")
        auth_raw = _ensure_section(tables, "auth")
        cognito_raw = _ensure_section(tables, "cognito")
        reaper_raw = _ensure_section(tables, "reaper")
        envoy_raw = _ensure_section(tables, "envoy_management")
        login_pod_pool_raw = _ensure_section(tables, "login_pod_pool")
        postgres_raw = _ensure_section(tables, "postgres")

        apply_env_overrides_to_config(tables, model=AppConfig)

        try:
            app_section = AppSection.model_validate(app_raw)
            api_section = ApiServiceConfig.model_validate(api_raw)
            ext_authz_section = ExtAuthzConfig.model_validate(ext_authz_raw)
            kubernetes_section = KubernetesConfig.model_validate(kubernetes_raw)
            reconciliation_section = ReconciliationConfig.model_validate(reconciliation_raw)
            auth_section = AuthConfig.model_validate(auth_raw)
            cognito_section = CognitoConfig.model_validate(cognito_raw)
            reaper_section = ReaperConfig.model_validate(reaper_raw)
            envoy_section = EnvoyManagementConfig.model_validate(envoy_raw)
            login_pod_pool_section = LoginPodPoolConfig.model_validate(login_pod_pool_raw)
            postgres_section = PostgresSection.model_validate(postgres_raw)
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
                ext_authz=ext_authz_section,
                kubernetes=kubernetes_section,
                reconciliation=reconciliation_section,
                auth=auth_section,
                cognito=cognito_section,
                reaper=reaper_section,
                envoy_management=envoy_section,
                login_pod_pool=login_pod_pool_section,
                postgres=postgres_section,
            ),
        )

    @staticmethod
    def default() -> AppConfig:
        """In-process defaults for tests or minimal runs."""
        return AppConfig(
            app=AppSection(),
            api_service=ApiServiceConfig(),
            ext_authz=ExtAuthzConfig(),
            kubernetes=KubernetesConfig(),
            reconciliation=ReconciliationConfig(),
            auth=AuthConfig(),
            cognito=CognitoConfig(),
            reaper=ReaperConfig(),
            envoy_management=EnvoyManagementConfig(),
            login_pod_pool=LoginPodPoolConfig(),
            postgres=PostgresSection(),
        )

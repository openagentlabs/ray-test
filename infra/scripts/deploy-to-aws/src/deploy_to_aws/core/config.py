"""Application configuration from ``app_config.toml`` with environment overrides."""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from deploy_to_aws.core.errors import AppError, ErrorCodes
from deploy_to_aws.core.option import Option
from deploy_to_aws.core.results import Failure, Success
from deploy_to_aws.core.types import DeployResult

APP_ENV_PREFIX = "DEPLOY_TO_AWS"
DEFAULT_CONFIG_FILENAME = "app_config.toml"


class AppSection(BaseModel):
    """[App] section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    Env: str = Field(default="dev", min_length=1)
    Target: str = Field(default="aws", min_length=1)

    @field_validator("Env")
    @classmethod
    def validate_env(cls, value: str) -> str:
        allowed = {"dev", "test", "prod"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"App.Env must be one of {sorted(allowed)}."
            raise ValueError(msg)
        return normalized


class AwsSection(BaseModel):
    """[Aws] section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    Profile: str = Field(default="kt-acc", min_length=1)
    Region: str = Field(default="us-east-1", min_length=1)
    AccountId: str = Field(default="017868795096", min_length=12, max_length=12)


class DeploySection(BaseModel):
    """[Deploy] section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    AutoApprove: bool = False
    SkipBuild: bool = False
    SkipScaffold: bool = True
    SkipPreflight: bool = False
    ImageTag: str = ""
    NoCache: bool = False
    HelmStableTimeout: int = Field(default=900, ge=60)
    AlbTimeout: int = Field(default=600, ge=60)


class PathsSection(BaseModel):
    """[Paths] section — repo-relative paths unless RepoRoot is set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    RepoRoot: str = ""
    TerraformDir: str = "infra/aws/aws_tf"
    EnvsDir: str = "infra/aws/envs"
    HelmChartDir: str = "infra/aws/deployed/aws/017868795096/us-east-1/helm/workload"
    K8sNamespace: str = "ray-test"


class AppConfigRoot(BaseModel):
    """Parsed TOML root matching ``app_config.toml`` sections."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    App: AppSection = Field(default_factory=AppSection)
    Aws: AwsSection = Field(default_factory=AwsSection)
    Deploy: DeploySection = Field(default_factory=DeploySection)
    Paths: PathsSection = Field(default_factory=PathsSection)


class AppConfig:
    """Facade over ``AppConfigRoot`` with section properties for ergonomic access."""

    SECTION_MODELS: ClassVar[tuple[tuple[str, type[BaseModel]], ...]] = (
        ("App", AppSection),
        ("Aws", AwsSection),
        ("Deploy", DeploySection),
        ("Paths", PathsSection),
    )

    def __init__(
        self, root: AppConfigRoot, *, repo_root: Path, config_path: Path
    ) -> None:
        self._root = root
        self._repo_root = repo_root
        self._config_path = config_path

    @property
    def app(self) -> AppSection:
        return self._root.App

    @property
    def aws(self) -> AwsSection:
        return self._root.Aws

    @property
    def deploy(self) -> DeploySection:
        return self._root.Deploy

    @property
    def paths(self) -> PathsSection:
        return self._root.Paths

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    @property
    def config_path(self) -> Path:
        return self._config_path

    @property
    def terraform_dir(self) -> Path:
        return self._repo_root / self.paths.TerraformDir

    @property
    def env_dir(self) -> Path:
        return self._repo_root / self.paths.EnvsDir / self.app.Env

    @property
    def helm_chart_dir(self) -> Path:
        return self._repo_root / self.paths.HelmChartDir

    def terraform_var_files(self) -> tuple[Path, ...]:
        env_dir = self.env_dir
        return (
            self.terraform_dir / "terraform.tfvars",
            env_dir / "terraform.tfvars",
            env_dir / "k8s.tfvars",
            env_dir / "secrets.auto.tfvars",
        )


def to_screaming_snake(name: str) -> str:
    """Convert PascalCase / camelCase to UPPER_SNAKE."""
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return normalized.replace("-", "_").upper()


def env_var_name(section: str, field: str) -> str:
    """Build the canonical UPPERCASE env key: ``DEPLOY_TO_AWS_<SECTION>_<FIELD>``."""
    return f"{APP_ENV_PREFIX}_{to_screaming_snake(section)}_{to_screaming_snake(field)}"


def build_env_key_index() -> dict[str, tuple[str, str]]:
    """Map canonical UPPERCASE env keys to ``(section, field)`` pairs."""
    index: dict[str, tuple[str, str]] = {}
    for section_name, model_type in AppConfig.SECTION_MODELS:
        for field_name in model_type.model_fields:
            index[env_var_name(section_name, field_name)] = (section_name, field_name)
    return index


def read_env_override(env_key: str) -> Option[str]:
    """Read an env override using the canonical UPPERCASE key.

    Lookup order (env always wins over TOML when present):
    1. Exact UPPERCASE key in ``os.environ``
    2. Case-insensitive match normalized to the canonical UPPERCASE key
    """
    canonical = env_key.upper()
    direct = os.environ.get(canonical)
    if direct is not None:
        return direct

    for key, value in os.environ.items():
        if key.upper() == canonical:
            return value
    return None


def _coerce_env_value(field_name: str, raw: str) -> object:
    lowered = raw.strip().lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if field_name.endswith("Timeout"):
        return int(raw.strip())
    return raw.strip()


def apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """Apply UPPERCASE ``DEPLOY_TO_AWS_*`` env vars on top of TOML (env wins)."""
    merged: dict[str, Any] = {key: dict(section) for key, section in data.items()}
    env_index = build_env_key_index()

    for env_key, (section_name, field_name) in env_index.items():
        raw = read_env_override(env_key)
        if raw is None:
            continue
        section_data = merged.setdefault(section_name, {})
        section_data[field_name] = _coerce_env_value(field_name, raw)

    return merged


def discover_repo_root(start: Path, configured: Option[str]) -> DeployResult[Path]:
    """Resolve repository root from config or by walking upward."""
    if configured and configured.strip():
        candidate = Path(configured).expanduser().resolve()
        if candidate.is_dir():
            return Success(candidate)
        return Failure(
            AppError(
                code=ErrorCodes.CONFIG,
                message="Configured RepoRoot is not a directory.",
                detail=str(candidate),
            ),
        )

    current = start.resolve()
    for directory in (current, *current.parents):
        if (directory / "infra" / "aws" / "aws_tf").is_dir():
            return Success(directory)
        if (directory / ".git").exists():
            return Success(directory)
    return Failure(
        AppError(
            code=ErrorCodes.CONFIG,
            message="Could not discover repository root.",
            detail=(
                f"Started search at {start}. "
                "Set Paths.RepoRoot or DEPLOY_TO_AWS_PATHS_REPO_ROOT."
            ),
        ),
    )


def default_config_path(app_dir: Path) -> Path:
    """Return the default ``app_config.toml`` beside the uv project."""
    return app_dir / DEFAULT_CONFIG_FILENAME


def load_app_config(
    *,
    config_path: Option[Path] = None,
    app_dir: Option[Path] = None,
) -> DeployResult[AppConfig]:
    """Load configuration with precedence: defaults → ``app_config.toml`` → env.

    Environment variables use the app prefix ``DEPLOY_TO_AWS_`` and UPPERCASE
    names ``DEPLOY_TO_AWS_<SECTION>_<FIELD>``. When set, they override TOML.
    """
    base_dir = (app_dir or Path(__file__).resolve().parents[3]).resolve()
    path = (config_path or default_config_path(base_dir)).resolve()
    if not path.is_file():
        return Failure(
            AppError(
                code=ErrorCodes.CONFIG,
                message="Application config file not found.",
                detail=str(path),
            ),
        )

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.CONFIG,
                message="Invalid app_config.toml.",
                detail=str(exc),
            ),
        )

    try:
        merged = apply_env_overrides(raw)
        root = AppConfigRoot.model_validate(merged)
    except ValueError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.CONFIG,
                message="Application config validation failed.",
                detail=str(exc),
            ),
        )

    repo_root_result = discover_repo_root(path.parent, root.Paths.RepoRoot)
    if isinstance(repo_root_result, Failure):
        return repo_root_result

    return Success(
        AppConfig(
            root,
            repo_root=repo_root_result.unwrap(),
            config_path=path,
        ),
    )

"""Deploy target profiles for local vs AWS endpoints."""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl, field_validator


class DeployTarget(StrEnum):
    LOCAL = "local"
    AWS = "aws"


class EndpointProfile(BaseModel):
    deploy_target: DeployTarget = Field(default=DeployTarget.LOCAL)
    envoy_url: str = "http://localhost:10000"
    pod_manager_host: str = "localhost"
    pod_manager_port: int = 8804
    database_url: str | None = None

    @field_validator("envoy_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @classmethod
    def from_environment(cls) -> EndpointProfile:
        raw_target = os.environ.get("POD_MANAGER_DEPLOY_TARGET", "local")
        try:
            deploy_target = DeployTarget(raw_target)
        except ValueError as exc:
            msg = f"Invalid POD_MANAGER_DEPLOY_TARGET={raw_target!r}; expected local or aws"
            raise ValueError(msg) from exc

        defaults = _DEFAULTS[deploy_target]
        return cls(
            deploy_target=deploy_target,
            envoy_url=os.environ.get("ENVOY_URL", defaults.envoy_url),
            pod_manager_host=os.environ.get("POD_MANAGER_HOST", defaults.pod_manager_host),
            pod_manager_port=int(os.environ.get("POD_MANAGER_PORT", str(defaults.pod_manager_port))),
            database_url=os.environ.get("DATABASE_URL", defaults.database_url),
        )

    def validate_aws(self) -> None:
        if self.deploy_target != DeployTarget.AWS:
            return
        if self.pod_manager_host in {"", "localhost", "127.0.0.1"}:
            msg = "POD_MANAGER_HOST must be set to the AWS gRPC endpoint when deploy target is aws"
            raise ValueError(msg)
        if "REPLACE_" in self.envoy_url or "REPLACE_" in self.pod_manager_host:
            msg = "Replace placeholder values in config/deploy/aws.env before using AWS profile"
            raise ValueError(msg)
        HttpUrl(self.envoy_url)


_DEFAULTS: dict[DeployTarget, EndpointProfile] = {
    DeployTarget.LOCAL: EndpointProfile(
        deploy_target=DeployTarget.LOCAL,
        envoy_url="http://localhost:10000",
        pod_manager_host="localhost",
        pod_manager_port=8804,
        database_url="postgresql://postgres:postgres@localhost:5432/midas",
    ),
    DeployTarget.AWS: EndpointProfile(
        deploy_target=DeployTarget.AWS,
        envoy_url="http://localhost:10000",
        pod_manager_host="localhost",
        pod_manager_port=8804,
        database_url=None,
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def profile_env_path(target: DeployTarget) -> Path:
    return repo_root() / "config" / "deploy" / f"{target.value}.env"


def load_profile_file(target: DeployTarget) -> dict[str, str]:
    path = profile_env_path(target)
    if not path.is_file():
        msg = f"Profile file not found: {path}"
        raise FileNotFoundError(msg)
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values

"""Endpoint profiles for local vs AWS deploy targets."""

from __future__ import annotations

import os
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class DeployTarget(StrEnum):
    LOCAL = "local"
    AWS = "aws"


class EndpointProfile(BaseModel):
    deploy_target: DeployTarget = DeployTarget.LOCAL
    envoy_url: str = "http://localhost:10000"
    envoy_health_url: str = "http://localhost:8080"
    pod_manager_host: str = "localhost"
    pod_manager_port: int = 8804
    database_url: str | None = "postgresql://postgres:postgres@localhost:5432/midas"
    schema_name: str = "pod_manager"
    table_prefix: str = "pm_"
    service_prefix: str = "router-svc"
    test_sub: str = Field(default="dev-test@example.com")

    @field_validator("envoy_url", "envoy_health_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @classmethod
    def from_environment(cls, target: DeployTarget | None = None) -> EndpointProfile:
        raw = target.value if target else os.environ.get("POD_MANAGER_DEPLOY_TARGET", "local")
        deploy_target = DeployTarget(raw)
        defaults = _DEFAULTS[deploy_target]
        return cls(
            deploy_target=deploy_target,
            envoy_url=os.environ.get("ENVOY_URL", defaults.envoy_url),
            envoy_health_url=os.environ.get(
                "ENVOY_HEALTH_URL",
                os.environ.get("ENVOY_URL", defaults.envoy_health_url).rstrip("/"),
            ),
            pod_manager_host=os.environ.get("POD_MANAGER_HOST", defaults.pod_manager_host),
            pod_manager_port=int(
                os.environ.get("POD_MANAGER_PORT", str(defaults.pod_manager_port)),
            ),
            database_url=os.environ.get("DATABASE_URL", defaults.database_url),
            schema_name=os.environ.get(
                "POD_MANAGER_POSTGRES_SCHEMA_NAME",
                defaults.schema_name,
            ),
            table_prefix=os.environ.get(
                "POD_MANAGER_POSTGRES_TABLE_PREFIX",
                defaults.table_prefix,
            ),
            service_prefix=os.environ.get(
                "POD_MANAGER_APP_SERVICE_NAME",
                defaults.service_prefix,
            ),
            test_sub=os.environ.get("TEST_SUB", defaults.test_sub),
        )

    def validate_ready(self) -> None:
        if self.deploy_target == DeployTarget.AWS:
            if "REPLACE_" in self.envoy_url or "REPLACE_" in self.pod_manager_host:
                msg = "AWS profile has placeholder values — run infra/scripts/write-aws-profile.sh"
                raise ValueError(msg)


_DEFAULTS: dict[DeployTarget, EndpointProfile] = {
    DeployTarget.LOCAL: EndpointProfile(
        deploy_target=DeployTarget.LOCAL,
        envoy_url="http://localhost:10000",
        envoy_health_url="http://localhost:8080",
        pod_manager_host="localhost",
        pod_manager_port=8804,
        database_url="postgresql://postgres:postgres@localhost:5432/midas",
    ),
    DeployTarget.AWS: EndpointProfile(
        deploy_target=DeployTarget.AWS,
        envoy_url="http://localhost:10000",
        envoy_health_url="http://localhost:8080",
        pod_manager_host="localhost",
        pod_manager_port=8804,
        database_url=None,
    ),
}

"""Pydantic configuration models for observability interfaces and drivers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DriverName = Literal["noop", "cloudwatch"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class ServiceIdentityConfig(BaseModel):
    """Service identity attached to every exported observability record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    service_id: str = Field(default="unknown-service", min_length=1)
    service_name: str = Field(default="unknown-service", min_length=1)
    service_version: str = Field(default="0.0.0", min_length=1)
    instance_id: str = Field(default="local", min_length=1)
    environment: str = Field(default="dev", min_length=1)


class LoggingInterfaceConfig(BaseModel):
    """``[observability.logging]`` — application log channel."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    driver: DriverName = "noop"
    level: LogLevel = "DEBUG"


class SecurityLoggingInterfaceConfig(BaseModel):
    """``[observability.security_logging]`` — dedicated security audit channel."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    driver: DriverName = "noop"
    level: LogLevel = "INFO"


class TracingInterfaceConfig(BaseModel):
    """``[observability.tracing]`` — distributed tracing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    driver: DriverName = "noop"
    sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)


class MetricsInterfaceConfig(BaseModel):
    """``[observability.metrics]`` — application metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    driver: DriverName = "noop"
    namespace: str = Field(default="EXL/Services", min_length=1)


class ApmInterfaceConfig(BaseModel):
    """``[observability.apm]`` — application performance monitoring events."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    driver: DriverName = "noop"


class CloudWatchLoggingDriverConfig(BaseModel):
    """``[observability.drivers.cloudwatch_logging]``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    region: str = Field(default="us-east-1", min_length=1)
    log_group_name: str = Field(default="/exl/services/default", min_length=1)
    log_stream_prefix: str = Field(default="app", min_length=1)
    queue_max_size: int = Field(default=10_000, ge=100)


class CloudWatchSecurityLoggingDriverConfig(BaseModel):
    """``[observability.drivers.cloudwatch_security_logging]``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    region: str = Field(default="us-east-1", min_length=1)
    log_group_name: str = Field(default="/exl/security/default", min_length=1)
    log_stream_prefix: str = Field(default="security", min_length=1)
    queue_max_size: int = Field(default=5_000, ge=100)


class CloudWatchTracingDriverConfig(BaseModel):
    """``[observability.drivers.cloudwatch_tracing]`` — X-Ray compatible export."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    region: str = Field(default="us-east-1", min_length=1)
    segment_name: str = Field(default="exl-service", min_length=1)


class CloudWatchMetricsDriverConfig(BaseModel):
    """``[observability.drivers.cloudwatch_metrics]``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    region: str = Field(default="us-east-1", min_length=1)
    namespace: str = Field(default="EXL/Services", min_length=1)
    queue_max_size: int = Field(default=10_000, ge=100)


class CloudWatchApmDriverConfig(BaseModel):
    """``[observability.drivers.cloudwatch_apm]`` — APM events via CloudWatch Logs EMF."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    region: str = Field(default="us-east-1", min_length=1)
    log_group_name: str = Field(default="/exl/apm/default", min_length=1)
    log_stream_prefix: str = Field(default="apm", min_length=1)
    queue_max_size: int = Field(default=5_000, ge=100)


class ObservabilityDriversConfig(BaseModel):
    """Nested driver configuration tables."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cloudwatch_logging: CloudWatchLoggingDriverConfig = Field(
        default_factory=CloudWatchLoggingDriverConfig,
    )
    cloudwatch_security_logging: CloudWatchSecurityLoggingDriverConfig = Field(
        default_factory=CloudWatchSecurityLoggingDriverConfig,
    )
    cloudwatch_tracing: CloudWatchTracingDriverConfig = Field(
        default_factory=CloudWatchTracingDriverConfig,
    )
    cloudwatch_metrics: CloudWatchMetricsDriverConfig = Field(
        default_factory=CloudWatchMetricsDriverConfig,
    )
    cloudwatch_apm: CloudWatchApmDriverConfig = Field(
        default_factory=CloudWatchApmDriverConfig,
    )


class ObservabilityConfig(BaseModel):
    """Root observability configuration loaded from ``app_config.toml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    identity: ServiceIdentityConfig = Field(default_factory=ServiceIdentityConfig)
    logging: LoggingInterfaceConfig = Field(default_factory=LoggingInterfaceConfig)
    security_logging: SecurityLoggingInterfaceConfig = Field(
        default_factory=SecurityLoggingInterfaceConfig,
    )
    tracing: TracingInterfaceConfig = Field(default_factory=TracingInterfaceConfig)
    metrics: MetricsInterfaceConfig = Field(default_factory=MetricsInterfaceConfig)
    apm: ApmInterfaceConfig = Field(default_factory=ApmInterfaceConfig)
    drivers: ObservabilityDriversConfig = Field(default_factory=ObservabilityDriversConfig)

    @staticmethod
    def from_toml_tables(tables: dict[str, Any]) -> ObservabilityConfig:
        """Build config from a parsed TOML root (typically ``[observability]`` subtree)."""
        obs_raw = tables.get("observability", {})
        if not isinstance(obs_raw, dict):
            obs_raw = {}

        identity_raw = obs_raw.get("identity", {})
        if not isinstance(identity_raw, dict):
            identity_raw = {}

        drivers_raw = obs_raw.get("drivers", {})
        if not isinstance(drivers_raw, dict):
            drivers_raw = {}

        def _section(name: str) -> dict[str, Any]:
            raw = obs_raw.get(name, {})
            return raw if isinstance(raw, dict) else {}

        def _driver_section(name: str) -> dict[str, Any]:
            raw = drivers_raw.get(name, {})
            return raw if isinstance(raw, dict) else {}

        return ObservabilityConfig(
            identity=ServiceIdentityConfig.model_validate(identity_raw),
            logging=LoggingInterfaceConfig.model_validate(_section("logging")),
            security_logging=SecurityLoggingInterfaceConfig.model_validate(
                _section("security_logging"),
            ),
            tracing=TracingInterfaceConfig.model_validate(_section("tracing")),
            metrics=MetricsInterfaceConfig.model_validate(_section("metrics")),
            apm=ApmInterfaceConfig.model_validate(_section("apm")),
            drivers=ObservabilityDriversConfig(
                cloudwatch_logging=CloudWatchLoggingDriverConfig.model_validate(
                    _driver_section("cloudwatch_logging"),
                ),
                cloudwatch_security_logging=CloudWatchSecurityLoggingDriverConfig.model_validate(
                    _driver_section("cloudwatch_security_logging"),
                ),
                cloudwatch_tracing=CloudWatchTracingDriverConfig.model_validate(
                    _driver_section("cloudwatch_tracing"),
                ),
                cloudwatch_metrics=CloudWatchMetricsDriverConfig.model_validate(
                    _driver_section("cloudwatch_metrics"),
                ),
                cloudwatch_apm=CloudWatchApmDriverConfig.model_validate(
                    _driver_section("cloudwatch_apm"),
                ),
            ),
        )

    @staticmethod
    def defaults() -> ObservabilityConfig:
        """In-process defaults for tests."""
        return ObservabilityConfig()

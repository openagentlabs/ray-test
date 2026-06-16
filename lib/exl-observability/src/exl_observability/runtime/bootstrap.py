"""Observability runtime — init/shutdown all interfaces from configuration."""

from __future__ import annotations

from exl_observability.apm.client import ApmClient
from exl_observability.apm.interface import ApmDriver
from exl_observability.apm.noop_driver import NoOpApmDriver
from exl_observability.config.models import ObservabilityConfig
from exl_observability.core.errors import ObsError
from exl_observability.core.result import Failure, Result, Success
from exl_observability.logging.client import LoggingClient
from exl_observability.logging.interface import LoggingDriver
from exl_observability.logging.noop_driver import NoOpLoggingDriver
from exl_observability.metrics.client import MetricsClient
from exl_observability.metrics.interface import MetricsDriver
from exl_observability.metrics.noop_driver import NoOpMetricsDriver
from exl_observability.runtime.factory import (
    build_apm_driver,
    build_logging_driver,
    build_metrics_driver,
    build_security_logging_driver,
    build_tracing_driver,
)
from exl_observability.security_logging.client import SecurityLoggingClient
from exl_observability.security_logging.interface import SecurityLoggingDriver
from exl_observability.security_logging.noop_driver import NoOpSecurityLoggingDriver
from exl_observability.tracing.client import TracingClient
from exl_observability.tracing.interface import TracingDriver
from exl_observability.tracing.noop_driver import NoOpTracingDriver

_RUNTIME: ObservabilityRuntime | None = None


class ObservabilityRuntime:
    """Owns all observability drivers and exposes lightweight clients."""

    def __init__(self, config: ObservabilityConfig) -> None:
        self._config = config
        self._logging_driver: LoggingDriver = build_logging_driver(config)
        self._security_driver: SecurityLoggingDriver = build_security_logging_driver(config)
        self._tracing_driver: TracingDriver = build_tracing_driver(config)
        self._metrics_driver: MetricsDriver = build_metrics_driver(config)
        self._apm_driver: ApmDriver = build_apm_driver(config)
        self._logging_client = self._logging_driver.create_client()
        self._security_client = self._security_driver.create_client()
        self._tracing_client = self._tracing_driver.create_client()
        self._metrics_client = self._metrics_driver.create_client()
        self._apm_client = self._apm_driver.create_client()
        self._initialized = False

    @property
    def config(self) -> ObservabilityConfig:
        return self._config

    async def init(self) -> Result[None, ObsError]:
        for name, driver in (
            ("logging", self._logging_driver),
            ("security_logging", self._security_driver),
            ("tracing", self._tracing_driver),
            ("metrics", self._metrics_driver),
            ("apm", self._apm_driver),
        ):
            result = await driver.init()
            if isinstance(result, Failure):
                err = result.failure()
                return Failure(
                    ObsError(
                        code=err.code,
                        message=f"Failed to initialize {name} driver.",
                        detail=err.detail,
                    ),
                )
        self._initialized = True
        global _RUNTIME
        _RUNTIME = self
        return Success(None)

    async def shutdown(self) -> Result[None, ObsError]:
        errors: list[str] = []
        for name, driver in (
            ("apm", self._apm_driver),
            ("metrics", self._metrics_driver),
            ("tracing", self._tracing_driver),
            ("security_logging", self._security_driver),
            ("logging", self._logging_driver),
        ):
            result = await driver.shutdown()
            if isinstance(result, Failure):
                err = result.failure()
                errors.append(f"{name}: {err.message}")
        self._initialized = False
        global _RUNTIME
        if _RUNTIME is self:
            _RUNTIME = None
        if errors:
            return Failure(
                ObsError(
                    code="OBS_SHUTDOWN",
                    message="One or more observability drivers failed shutdown.",
                    detail="; ".join(errors),
                ),
            )
        return Success(None)

    def logging_client(self) -> LoggingClient:
        return self._logging_client

    def security_logging_client(self) -> SecurityLoggingClient:
        return self._security_client

    def tracing_client(self) -> TracingClient:
        return self._tracing_client

    def metrics_client(self) -> MetricsClient:
        return self._metrics_client

    def apm_client(self) -> ApmClient:
        return self._apm_client


def get_runtime() -> ObservabilityRuntime | None:
    """Return the process-wide runtime after ``init()``."""
    return _RUNTIME


def get_logging_client() -> LoggingClient:
    """Return the global logging client or a NoOp-bound client before init."""
    if _RUNTIME is not None:
        return _RUNTIME.logging_client()
    return LoggingClient(NoOpLoggingDriver())


def get_security_logging_client() -> SecurityLoggingClient:
    if _RUNTIME is not None:
        return _RUNTIME.security_logging_client()
    return SecurityLoggingClient(NoOpSecurityLoggingDriver())


def get_tracing_client() -> TracingClient:
    if _RUNTIME is not None:
        return _RUNTIME.tracing_client()
    return TracingClient(NoOpTracingDriver())


def get_metrics_client() -> MetricsClient:
    if _RUNTIME is not None:
        return _RUNTIME.metrics_client()
    return MetricsClient(NoOpMetricsDriver(namespace="EXL/Services"), namespace="EXL/Services")


def get_apm_client() -> ApmClient:
    if _RUNTIME is not None:
        return _RUNTIME.apm_client()
    return ApmClient(NoOpApmDriver())

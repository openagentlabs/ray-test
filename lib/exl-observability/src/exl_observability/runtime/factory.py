"""Driver factory — selects implementation from interface config."""

from __future__ import annotations

from exl_observability.apm.interface import ApmDriver
from exl_observability.apm.noop_driver import NoOpApmDriver
from exl_observability.config.models import ObservabilityConfig
from exl_observability.drivers.cloudwatch_apm.driver import CloudWatchApmDriver
from exl_observability.drivers.cloudwatch_logging.driver import CloudWatchLoggingDriver
from exl_observability.drivers.cloudwatch_metrics.driver import CloudWatchMetricsDriver
from exl_observability.drivers.cloudwatch_security_logging.driver import (
    CloudWatchSecurityLoggingDriver,
)
from exl_observability.drivers.cloudwatch_tracing.driver import CloudWatchTracingDriver
from exl_observability.logging.interface import LoggingDriver
from exl_observability.logging.noop_driver import NoOpLoggingDriver
from exl_observability.metrics.interface import MetricsDriver
from exl_observability.metrics.noop_driver import NoOpMetricsDriver
from exl_observability.security_logging.interface import SecurityLoggingDriver
from exl_observability.security_logging.noop_driver import NoOpSecurityLoggingDriver
from exl_observability.tracing.interface import TracingDriver
from exl_observability.tracing.noop_driver import NoOpTracingDriver


def build_logging_driver(config: ObservabilityConfig) -> LoggingDriver:
    if config.logging.enabled and config.logging.driver == "cloudwatch":
        return CloudWatchLoggingDriver(
            identity=config.identity,
            interface_config=config.logging,
            driver_config=config.drivers.cloudwatch_logging,
        )
    return NoOpLoggingDriver()


def build_security_logging_driver(config: ObservabilityConfig) -> SecurityLoggingDriver:
    if config.security_logging.enabled and config.security_logging.driver == "cloudwatch":
        return CloudWatchSecurityLoggingDriver(
            identity=config.identity,
            interface_config=config.security_logging,
            driver_config=config.drivers.cloudwatch_security_logging,
        )
    return NoOpSecurityLoggingDriver()


def build_tracing_driver(config: ObservabilityConfig) -> TracingDriver:
    if config.tracing.enabled and config.tracing.driver == "cloudwatch":
        return CloudWatchTracingDriver(
            identity=config.identity,
            interface_config=config.tracing,
            driver_config=config.drivers.cloudwatch_tracing,
        )
    return NoOpTracingDriver()


def build_metrics_driver(config: ObservabilityConfig) -> MetricsDriver:
    if config.metrics.enabled and config.metrics.driver == "cloudwatch":
        return CloudWatchMetricsDriver(
            identity=config.identity,
            interface_config=config.metrics,
            driver_config=config.drivers.cloudwatch_metrics,
        )
    return NoOpMetricsDriver(namespace=config.metrics.namespace)


def build_apm_driver(config: ObservabilityConfig) -> ApmDriver:
    if config.apm.enabled and config.apm.driver == "cloudwatch":
        return CloudWatchApmDriver(
            identity=config.identity,
            interface_config=config.apm,
            driver_config=config.drivers.cloudwatch_apm,
        )
    return NoOpApmDriver()

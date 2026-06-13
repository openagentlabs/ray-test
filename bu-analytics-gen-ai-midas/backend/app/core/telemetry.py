"""
OpenTelemetry + CloudWatch (EMF) telemetry bootstrap for the MIDAS backend.

Design
------
- Logs continue to flow through ``logging_config.JsonFormatter`` (stdout).
  This module does NOT replace the stdlib logging hierarchy.
- Metrics are emitted via AWS Embedded Metric Format (EMF), which writes a
  specially-annotated JSON line to stdout.  The CloudWatch Agent / Fluent Bit
  DaemonSet (already present on the node) parses EMF and publishes metrics
  to the configured CloudWatch namespace.  No extra IAM permissions are
  required on the backend pod.
- Everything is feature-flagged off by default.  ``setup_telemetry`` is
  idempotent and ``record_*`` functions are safe to call when telemetry is
  disabled (they no-op).
- All configuration is read from **environment variables only** — no
  ``Settings`` coupling.  Helm / Kubernetes injects the env vars at pod
  creation time (see ``deploy/ecs-app/helm/midas-api-backend-svc/``).

Environment variables
---------------------
OTEL_ENABLED                 Master switch (default false).
OTEL_METRICS_ENABLED         Enable EMF CloudWatch Metrics (default false).
OTEL_METRICS_NAMESPACE       CloudWatch custom-metric namespace (default MIDAS).
OTEL_SERVICE_NAME            Service dimension on every metric (default midas-backend).
OTEL_ENVIRONMENT             Environment dimension (default: APP_ENV → ENVIRONMENT → development).
LOG_CLOUDWATCH_LOG_GROUP     When set, ``JsonFormatter`` emits ``@logGroupName``.

Phase B extras (OTLP / Prometheus path, see docs/observability-metric-catalog.md)
OTEL_EXPORTER_OTLP_ENDPOINT  gRPC endpoint of the in-cluster OTel Collector.
OTEL_RESOURCE_ATTRIBUTES     Comma-separated resource attributes (e.g. service.name=midas-backend).

Adding a new metric (recipe)
----------------------------
1. Add a ``record_<thing>(...)`` function below following the same shape as
   ``record_http_request``.
2. Call it from the relevant code path (middleware, service, etc).
3. Document it in ``docs/observability-configuration.md`` and
   ``docs/observability-metric-catalog.md``.

No other file changes are needed; dimensions and unit are baked into the
recorder, and ``aws-embedded-metrics`` handles flushing on context exit.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional


_logger = logging.getLogger("midas.telemetry")

_TELEMETRY_INITIALISED: bool = False
_METRICS_ENABLED: bool = False
_OTLP_ENABLED: bool = False
_SERVICE_NAME: str = "midas-backend"
_ENVIRONMENT: str = "development"
_NAMESPACE: str = "MIDAS"


def _read_env_bool(key: str, *, default: bool) -> bool:
    """Read a boolean env var using the same rules as config._env_bool."""
    raw = os.environ.get(key)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def setup_telemetry() -> None:
    """Initialise telemetry from environment variables.

    Idempotent: safe to call more than once (subsequent calls are ignored).
    All state is module-level so individual recorders can read it without
    re-reading env on every request.

    No arguments — all config is from ``os.environ``.
    """
    global _TELEMETRY_INITIALISED, _METRICS_ENABLED, _OTLP_ENABLED
    global _SERVICE_NAME, _ENVIRONMENT, _NAMESPACE

    if _TELEMETRY_INITIALISED:
        return

    if not _read_env_bool("OTEL_ENABLED", default=False):
        _logger.info("Telemetry disabled (OTEL_ENABLED=false)")
        _TELEMETRY_INITIALISED = True
        return

    _SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "midas-backend")
    _ENVIRONMENT = os.environ.get(
        "OTEL_ENVIRONMENT",
        os.environ.get(
            "APP_ENV",
            os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")),
        ),
    )
    _NAMESPACE = os.environ.get("OTEL_METRICS_NAMESPACE", "MIDAS")
    _METRICS_ENABLED = _read_env_bool("OTEL_METRICS_ENABLED", default=False)

    # Phase B: OTLP exporter active when an endpoint is configured.
    _OTLP_ENABLED = bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip())

    if _METRICS_ENABLED:
        try:
            _configure_emf_environment()
            _logger.info(
                "Telemetry initialised (EMF): service=%s environment=%s namespace=%s",
                _SERVICE_NAME,
                _ENVIRONMENT,
                _NAMESPACE,
            )
        except Exception as exc:  # pragma: no cover - never break startup
            _METRICS_ENABLED = False
            _logger.warning("Telemetry EMF init failed; metrics disabled: %s", exc)
    else:
        _logger.info("Telemetry initialised (metrics disabled)")

    if _OTLP_ENABLED:
        try:
            _configure_otlp_meter_provider()
            _logger.info(
                "Telemetry OTLP exporter initialised: endpoint=%s",
                os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
            )
        except Exception as exc:  # pragma: no cover - never break startup
            _OTLP_ENABLED = False
            _logger.warning("Telemetry OTLP init failed; OTLP disabled: %s", exc)

    _TELEMETRY_INITIALISED = True


def _configure_emf_environment() -> None:
    """Configure ``aws-embedded-metrics`` via env vars.

    ``setdefault`` is used so that any pre-set env (e.g. from the K8s pod
    spec) takes precedence over these defaults.  Uses the deployment
    environment rather than the misleading hard-coded ``"Local"`` value.
    """
    os.environ.setdefault("AWS_EMF_ENVIRONMENT", _ENVIRONMENT)
    os.environ.setdefault("AWS_EMF_NAMESPACE", _NAMESPACE)
    os.environ.setdefault("AWS_EMF_SERVICE_NAME", _SERVICE_NAME)
    os.environ.setdefault(
        "AWS_EMF_LOG_GROUP_NAME",
        os.environ.get("LOG_CLOUDWATCH_LOG_GROUP", ""),
    )


def _configure_otlp_meter_provider() -> None:
    """Initialise the OpenTelemetry SDK MeterProvider with an OTLP exporter.

    Only called when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set (Phase B).
    The SDK reads ``OTEL_EXPORTER_OTLP_*`` and ``OTEL_RESOURCE_ATTRIBUTES``
    from the environment automatically — no explicit SDK config needed here
    beyond setting the provider as global.
    """
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (  # type: ignore[import]
        OTLPMetricExporter,
    )
    from opentelemetry.sdk.resources import Resource

    resource = Resource.create(
        {
            "service.name": _SERVICE_NAME,
            "deployment.environment": _ENVIRONMENT,
        }
    )
    exporter = OTLPMetricExporter()
    reader = PeriodicExportingMetricReader(exporter)
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    otel_metrics.set_meter_provider(provider)


def is_metrics_enabled() -> bool:
    """True when EMF metrics should be emitted."""
    return _METRICS_ENABLED


def is_otlp_enabled() -> bool:
    """True when OTLP metrics should be emitted (Phase B)."""
    return _OTLP_ENABLED


def get_metric_logger(namespace: Optional[str] = None):
    """Return a fresh ``aws-embedded-metrics`` MetricsLogger.

    Used by recorder functions in this module; exposed for future modules
    that want to emit their own metric families (e.g. LLM latency, queue
    depth) without duplicating bootstrap logic.
    """
    from aws_embedded_metrics.logger.metrics_logger_factory import create_metrics_logger

    metrics = create_metrics_logger()
    metrics.set_namespace(namespace or _NAMESPACE)
    metrics.set_dimensions({"Service": _SERVICE_NAME, "Environment": _ENVIRONMENT})
    return metrics


def record_http_request(
    *,
    method: str,
    route: str,
    outcome: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """First-class HTTP request metric.

    Emits via EMF (CloudWatch) when ``OTEL_METRICS_ENABLED=true`` and
    optionally via OTLP (Prometheus/AMP) when ``OTEL_EXPORTER_OTLP_ENDPOINT``
    is set.

    Dimensions: ``Service``, ``Environment``, ``Method``, ``Route``, ``Outcome``.
    Properties (high-cardinality, non-dimension): ``StatusCode``.
    EMF metrics: ``HttpRequestDuration`` (Milliseconds), ``HttpRequestCount`` (Count).
    OTLP metrics: ``http.server.request.duration`` (histogram, seconds),
                  ``http.server.request.count`` (counter).
    """
    if not (_METRICS_ENABLED or _OTLP_ENABLED):
        return

    try:
        coro = _emit_http_request(
            method=method,
            route=route,
            outcome=outcome,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
        else:
            loop.create_task(coro)
    except Exception as exc:  # pragma: no cover - never break a request on metric error
        _logger.debug("record_http_request suppressed error: %s", exc)


async def _emit_http_request(
    *,
    method: str,
    route: str,
    outcome: str,
    status_code: int,
    duration_ms: float,
) -> None:
    if _METRICS_ENABLED:
        emf = get_metric_logger()
        emf.set_dimensions(
            {
                "Service": _SERVICE_NAME,
                "Environment": _ENVIRONMENT,
                "Method": method,
                "Route": route,
                "Outcome": outcome,
            }
        )
        emf.set_property("StatusCode", status_code)
        emf.put_metric("HttpRequestDuration", duration_ms, "Milliseconds")
        emf.put_metric("HttpRequestCount", 1, "Count")
        await emf.flush()

    if _OTLP_ENABLED:
        _emit_http_request_otlp(
            method=method,
            route=route,
            outcome=outcome,
            status_code=status_code,
            duration_ms=duration_ms,
        )


def _emit_http_request_otlp(
    *,
    method: str,
    route: str,
    outcome: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """Emit HTTP request metrics via OTel SDK → OTLP exporter (Phase B).

    Uses OTel semantic conventions for metric names so the Prometheus series
    names are predictable after the Collector's prometheusremotewrite exporter
    normalises dots to underscores:
      http_server_request_duration_seconds_bucket / _sum / _count
      http_server_request_count_total
    """
    try:
        from opentelemetry import metrics as otel_metrics

        meter = otel_metrics.get_meter("midas.http", version="1.0")
        attrs = {
            "http.method": method,
            "http.route": route,
            "http.status_code": status_code,
            "midas.outcome": outcome,
            "service.name": _SERVICE_NAME,
            "deployment.environment": _ENVIRONMENT,
        }
        duration_histogram = meter.create_histogram(
            name="http.server.request.duration",
            description="HTTP server request duration",
            unit="s",
        )
        request_counter = meter.create_counter(
            name="http.server.request.count",
            description="HTTP server request count",
            unit="{request}",
        )
        duration_histogram.record(duration_ms / 1000.0, attributes=attrs)
        request_counter.add(1, attributes=attrs)
    except Exception as exc:  # pragma: no cover - never break a request
        _logger.debug("OTLP emit suppressed error: %s", exc)

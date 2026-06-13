"""
keith_log_matrics_test.py
--------------------------
Heartbeat context manager that at every tick (default 30 s):

  1. Logs a keep-alive INFO message (existing behaviour - prevents silent gaps in
     CloudWatch Logs / Azure Log Stream during long ML training runs).

  2. Emits a ``keith_kets_training_value`` OpenTelemetry metric **directly** to
     CloudWatch via boto3 ``put_metric_data``.  This uses the CloudWatch VPC
     interface endpoint (PrivateLink) so no internet egress is required.

Architecture
------------
  Python heartbeat thread
    |
    |- logger.info(...)                  ->  /midas/{env}/backend  (existing logs, untouched)
    |
    +- OTel SDK records measurement
         |
         +- CloudWatchMetricExporter (boto3 PutMetricData)
              |
              +- CloudWatch VPC endpoint (monitoring.us-east-1.vpce.amazonaws.com)
                   |
                   +- CloudWatch Custom Metric
                        Namespace : MIDAS/Training
                        Metric    : keith_kets_training_value
                        Value     : random integer 1-1000
                        Dimensions: operation, service, environment

OTel integration notes
----------------------
- A module-level ``MeterProvider`` with a ``PeriodicExportingMetricReader`` is
  created once at import time.  The reader collects and exports every
  ``OTEL_METRIC_EXPORT_INTERVAL`` seconds (default 30 s, matching the heartbeat).
- The ``CloudWatchMetricExporter`` is a thin boto3 wrapper that converts OTel
  ``MetricsData`` into ``put_metric_data`` API calls.
- The existing ``logging_config.py`` (stdlib ``logging`` + ``JsonFormatter``) is
  completely unaffected; it remains the sole owner of the ``/midas/{env}/backend``
  log group.
- Metric errors are caught and logged as warnings so a boto3 failure never
  interrupts a training run.

Usage::

    with run_with_heartbeat(logger, "CatBoost - Trial 1: still fitting"):
        model.fit(X_train, y_train)

    with run_with_heartbeat(logger, "CatBoost - Trial 1: cross-validation running"):
        cross_val_score(...)
"""

from __future__ import annotations

import logging
import os
import random
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, Optional

# ---------------------------------------------------------------------------
# boto3 CloudWatch client (lazy singleton - created once on first metric emit)
# ---------------------------------------------------------------------------
import boto3
from botocore.config import Config as BotocoreConfig

_CW_CLIENT = None
_CW_CLIENT_LOCK = threading.Lock()

_AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
_METRIC_NAMESPACE = "MIDAS/Training"
_SERVICE_NAME = os.environ.get("LOG_SERVICE_NAME", os.environ.get("APP_NAME", "midas"))
_ENVIRONMENT = os.environ.get(
    "LOG_ENVIRONMENT",
    os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")),
)


def _get_cw_client():
    """Return the module-level CloudWatch boto3 client, creating it on first call.

    Uses the CloudWatch VPC interface endpoint when ``CLOUDWATCH_ENDPOINT_URL``
    is set, otherwise falls back to the default regional endpoint (for local dev).
    The endpoint env var is injected via Helm values from Terraform output.
    """
    global _CW_CLIENT
    if _CW_CLIENT is not None:
        return _CW_CLIENT
    with _CW_CLIENT_LOCK:
        if _CW_CLIENT is not None:
            return _CW_CLIENT
        endpoint_url = os.environ.get("CLOUDWATCH_ENDPOINT_URL")
        _CW_CLIENT = boto3.client(
            "cloudwatch",
            region_name=_AWS_REGION,
            endpoint_url=endpoint_url or None,
            config=BotocoreConfig(
                retries={"max_attempts": 2, "mode": "standard"},
                connect_timeout=5,
                read_timeout=10,
            ),
        )
    return _CW_CLIENT


# ---------------------------------------------------------------------------
# OpenTelemetry meter - module-level, created once
# ---------------------------------------------------------------------------
from opentelemetry import metrics as otel_metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource, SERVICE_NAME as OTEL_SERVICE_NAME

_resource = Resource.create({
    OTEL_SERVICE_NAME: _SERVICE_NAME,
    "deployment.environment": _ENVIRONMENT,
})

# MeterProvider with no SDK exporter - we drive export manually from the
# heartbeat thread via boto3 so we control the exact timing and dimensions.
_meter_provider = MeterProvider(resource=_resource)
otel_metrics.set_meter_provider(_meter_provider)
_meter = otel_metrics.get_meter("midas.training.heartbeat", version="1.0.0")

# ---------------------------------------------------------------------------
# Direct CloudWatch PutMetricData emitter
# ---------------------------------------------------------------------------

def _put_metric_direct(operation: str, value: int) -> None:
    """Call CloudWatch PutMetricData directly via boto3.

    Writes one data point to the MIDAS/Training namespace through the
    CloudWatch VPC interface endpoint (PrivateLink).  Falls back gracefully
    if the boto3 call fails so training is never interrupted.

    Args:
        operation: Dimension value identifying the training phase, e.g.
            ``"still_fitting"`` or ``"cross_validation_running"``.
        value: Metric sample value (random integer 1-1000).
    """
    client = _get_cw_client()
    client.put_metric_data(
        Namespace=_METRIC_NAMESPACE,
        MetricData=[
            {
                "MetricName": "keith_kets_training_value",
                "Dimensions": [
                    {"Name": "operation",    "Value": operation},
                    {"Name": "service",      "Value": _SERVICE_NAME},
                    {"Name": "environment",  "Value": _ENVIRONMENT},
                ],
                "Timestamp": datetime.now(tz=timezone.utc),
                "Value": float(value),
                "Unit": "None",
            }
        ],
    )


# ---------------------------------------------------------------------------
# Always-on backend heartbeat (started once at app startup)
# ---------------------------------------------------------------------------

_backend_heartbeat_started = False
_backend_heartbeat_lock = threading.Lock()


def start_backend_heartbeat(
    logger: logging.Logger,
    interval_seconds: int = 30,
) -> None:
    """Start a single daemon thread that emits a log + metric every *interval_seconds*
    for the entire lifetime of the backend process.

    Safe to call multiple times — only one thread is ever started (idempotent).
    Intended to be called once from the FastAPI ``startup_event`` in ``main.py``.

    Args:
        logger: Logger to write keep-alive messages to (should be the root app logger).
        interval_seconds: Tick interval in seconds. Defaults to 30.
    """
    global _backend_heartbeat_started
    with _backend_heartbeat_lock:
        if _backend_heartbeat_started:
            return
        _backend_heartbeat_started = True

    def _heartbeat() -> None:
        elapsed = 0
        stop = threading.Event()
        while not stop.wait(interval_seconds):
            elapsed += interval_seconds
            logger.info(
                "MIDAS backend alive (%ds uptime)",
                elapsed,
                extra={"event": "backend_heartbeat", "log_category": "ops"},
            )
            sample_value = random.randint(1, 1000)
            try:
                _put_metric_direct(operation="backend_alive", value=sample_value)
            except Exception as exc:
                logger.warning(
                    "keith_kets backend heartbeat PutMetricData failed (non-fatal): %s", exc
                )

    thread = threading.Thread(target=_heartbeat, daemon=True, name="midas-backend-heartbeat")
    thread.start()


# ---------------------------------------------------------------------------
# DataFrameStateManager in-memory state metrics (per-process)
# ---------------------------------------------------------------------------

_dfsm_metrics_started = False
_dfsm_metrics_lock = threading.Lock()


def _put_dfsm_state_metrics(stats: dict) -> None:
    """Emit DataFrameStateManager per-dictionary metrics via one PutMetricData call.

    For every dictionary reported by ``DataFrameStateManager.collect_state_metrics``
    this emits two CloudWatch metrics whose names align with the dictionary name:
      - ``<dict_name>_frame_count`` (Unit: Count)
      - ``<dict_name>_size_gb``     (Unit: Gigabytes)

    Dimensions on every metric: ``pid`` (so the series is per-process), plus the
    existing ``service`` and ``environment`` dimensions. Written to the
    ``MIDAS/Training`` namespace through the same CloudWatch client / VPC endpoint
    used by the heartbeat, so no new IAM or networking is required.

    Args:
        stats: Mapping of ``dict_name -> {"frame_count", "size_bytes"}`` as
            returned by ``DataFrameStateManager.collect_state_metrics``.
    """
    if not stats:
        return
    client = _get_cw_client()
    dimensions = [
        {"Name": "pid", "Value": str(os.getpid())},
        {"Name": "service", "Value": _SERVICE_NAME},
        {"Name": "environment", "Value": _ENVIRONMENT},
    ]
    timestamp = datetime.now(tz=timezone.utc)
    metric_data = []
    for dict_name, measures in stats.items():
        frame_count = float(measures.get("frame_count", 0))
        size_gb = float(measures.get("size_bytes", 0)) / (1024 ** 3)
        metric_data.append({
            "MetricName": f"{dict_name}_frame_count",
            "Dimensions": dimensions,
            "Timestamp": timestamp,
            "Value": frame_count,
            "Unit": "Count",
        })
        metric_data.append({
            "MetricName": f"{dict_name}_size_gb",
            "Dimensions": dimensions,
            "Timestamp": timestamp,
            "Value": size_gb,
            "Unit": "Gigabytes",
        })
    # ~8 metrics per tick — well under the PutMetricData 1000-metric / 1 MB limit.
    client.put_metric_data(Namespace=_METRIC_NAMESPACE, MetricData=metric_data)


def start_dfsm_state_metrics_heartbeat(
    logger: logging.Logger,
    interval_seconds: int = 60,
) -> None:
    """Start a single daemon thread that publishes DataFrameStateManager memory
    stats to CloudWatch every *interval_seconds* for the process lifetime.

    Idempotent — only one thread is ever started. Intended to be called once
    from the FastAPI ``startup_event`` in ``main.py``.

    Performance: all work happens on this background thread. The per-tick cost
    is a cheap ``deep=False`` size scan (O(columns)) over at most a handful of
    datasets plus one ``PutMetricData`` call, so it never touches the request /
    upload hot path. Metric failures are logged as warnings and never raised.

    Args:
        logger: Logger for the keep-alive / failure messages.
        interval_seconds: Tick interval in seconds. Defaults to 60.
    """
    global _dfsm_metrics_started
    with _dfsm_metrics_lock:
        if _dfsm_metrics_started:
            return
        _dfsm_metrics_started = True

    def _emit() -> None:
        stop = threading.Event()
        while not stop.wait(interval_seconds):
            try:
                from app.services.dataframe_state_manager import dataframe_state_manager
                stats = dataframe_state_manager.collect_state_metrics()
            except Exception as exc:
                logger.warning(
                    "DFSM state metrics collection failed (non-fatal): %s", exc
                )
                continue
            logger.info(
                "DataFrameStateManager memory stats",
                extra={"event": "dfsm_state_metrics", "log_category": "ops", "stats": stats},
            )
            try:
                _put_dfsm_state_metrics(stats)
            except Exception as exc:
                logger.warning(
                    "DFSM state metrics PutMetricData failed (non-fatal): %s", exc
                )

    thread = threading.Thread(target=_emit, daemon=True, name="midas-dfsm-state-metrics")
    thread.start()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@contextmanager
def run_with_heartbeat(
    logger: logging.Logger,
    message_prefix: str,
    interval_seconds: int = 30,
    metric_operation: Optional[str] = None,
) -> Generator[None, None, None]:
    """Context manager that every *interval_seconds*:

    1. Logs ``"<message_prefix> (<N>s elapsed)"`` at INFO level (keep-alive for
       the existing CloudWatch Logs stream at ``/midas/{env}/backend``).
    2. Records a ``keith_kets_training_value`` measurement via the OTel SDK and
       pushes it **directly** to CloudWatch via ``PutMetricData`` (boto3 through
       the CloudWatch VPC interface endpoint).  Value is a random integer 1-1000.

    The daemon thread is stopped cleanly via a ``threading.Event`` in the
    ``finally`` block - always, even if the body raises an exception.
    Metric push errors are caught and logged as warnings; they never propagate
    to the caller.

    Args:
        logger: Logger to write keep-alive messages to.
        message_prefix: Prefix for each log line, e.g.
            ``"CatBoost - Trial 3: still fitting..."``.
        interval_seconds: Tick interval in seconds. Defaults to 30.
        metric_operation: CloudWatch dimension value for the ``operation``
            dimension.  Derived from *message_prefix* when omitted.

    Yields:
        None - the caller's ``with`` body runs here.

    Example::

        with run_with_heartbeat(self.logger, f"{algo} - Trial {n}: still fitting..."):
            model.fit(X_train, y_train)
    """
    if metric_operation is None:
        last_segment = message_prefix.split(":")[-1].strip()
        metric_operation = (
            last_segment.rstrip("...").rstrip("\u2026").strip()
            .lower().replace(" ", "_").replace("-", "_")
        )

    done = threading.Event()

    def _heartbeat() -> None:
        elapsed = 0
        while not done.wait(interval_seconds):
            elapsed += interval_seconds

            # 1. Keep-alive log entry (existing behaviour - logs to /midas/{env}/backend)
            logger.info(f"{message_prefix} ({elapsed}s elapsed)")

            # 2. OTel measurement + direct CloudWatch PutMetricData
            sample_value = random.randint(1, 1000)
            try:
                _put_metric_direct(operation=metric_operation, value=sample_value)
            except Exception as exc:
                logger.warning(
                    "keith_kets metric PutMetricData failed (non-fatal): %s", exc
                )

    thread = threading.Thread(target=_heartbeat, daemon=True)
    thread.start()
    try:
        yield
    finally:
        done.set()

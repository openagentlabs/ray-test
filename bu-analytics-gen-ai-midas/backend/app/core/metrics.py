"""
Prometheus instrumentation for MIDAS.

Exposes:
  * Per-route HTTP duration / count histograms (via prometheus-fastapi-instrumentator).
  * `midas_event_loop_lag_seconds` gauge -- updated once per second by a
    background task, this is the canary that proves the asyncio event loop
    is responsive. A healthy backend keeps this <0.05s. Sustained values
    above 1s mean a synchronous call is blocking the loop (the exact failure
    mode the 17h22 / 20h07 stress runs hit).
  * `midas_dataset_df_cache_size` gauge -- per-worker count of resident
    DataFrames in the LRU cache (B2). Useful for sizing DATASET_DF_CACHE_SIZE.

Multi-worker safety:
  When uvicorn is running with workers > 1, set PROMETHEUS_MULTIPROC_DIR to a
  shared dir writable by all workers (start.py does this automatically). The
  /metrics endpoint then aggregates counters across all workers via
  MultiProcessCollector. Without that env var, /metrics shows only the worker
  that happened to handle the scrape -- still useful, just less precise.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

from contextlib import contextmanager

from fastapi import FastAPI, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.logging_config import get_logger

logger = get_logger(__name__)


# Multiproc-safe gauges. multiprocess_mode='liveall' so /metrics shows every
# worker's current value rather than aggregating across forks (which would be
# meaningless for instantaneous values like loop lag).
EVENT_LOOP_LAG = Gauge(
    "midas_event_loop_lag_seconds",
    "Time between scheduled and actual execution of a 1Hz heartbeat task. "
    "Sustained >0.1s indicates the asyncio event loop is blocked by a "
    "synchronous call (pandas, json.dumps, etc.).",
    multiprocess_mode="liveall",
)

DF_CACHE_SIZE = Gauge(
    "midas_dataset_df_cache_size",
    "Number of DataFrames currently resident in this worker's DatasetManager "
    "LRU cache. Bounded by DATASET_DF_CACHE_SIZE env var (default 4).",
    multiprocess_mode="liveall",
)


# P3.5: per-stage histograms for the heavy ingest / analytics path.
# Buckets are tuned for what we expect on tt3_2gb-shaped data:
#   - upload  : ~5 s for 2 GiB on local SSD, up to 60 s on slow networks
#   - parquet : ~3-15 s streaming write (compresses ~5x for sparse data)
#   - dqs     : sub-second after P2.4a; 60+ s without
#   - column-info : 1-30 s depending on dtypes / row count
# Stage labels keep the cardinality bounded.
_STAGE_BUCKETS = (
    0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0,
)
STAGE_DURATION_SECONDS = Histogram(
    "midas_pipeline_stage_seconds",
    "Wall-clock duration of named pipeline stages "
    "(upload/parquet/dqs/column_info/classify/sample).",
    labelnames=("stage", "outcome"),
    buckets=_STAGE_BUCKETS,
)
STAGE_BYTES_PROCESSED = Counter(
    "midas_pipeline_stage_bytes_total",
    "Total uncompressed bytes processed by a pipeline stage. Useful to "
    "compute MB/s throughput in Grafana.",
    labelnames=("stage",),
)
ANALYTICS_CACHE_HITS = Counter(
    "midas_analytics_cache_hits_total",
    "Hit/miss counter for the AnalyticsResultCache, by kind "
    "(column_info|dqs|eda_snapshot|comprehensive_stats) and outcome.",
    labelnames=("kind", "outcome"),
)


@contextmanager
def time_stage(stage: str, *, bytes_processed: Optional[int] = None):
    """
    Record the duration of a named ingest/analytics stage. Use as a context
    manager so failures are tagged outcome=error and don't get lumped into the
    success-latency histogram.

        from app.core.metrics import time_stage
        with time_stage("dqs"):
            dqs_service.calculate_dqs(df, ...)
    """
    start = time.perf_counter()
    outcome = "success"
    try:
        yield
    except Exception:
        outcome = "error"
        raise
    finally:
        STAGE_DURATION_SECONDS.labels(stage=stage, outcome=outcome).observe(
            max(0.0, time.perf_counter() - start)
        )
        if bytes_processed is not None and bytes_processed > 0:
            STAGE_BYTES_PROCESSED.labels(stage=stage).inc(bytes_processed)


def record_cache_hit(kind: str, hit: bool) -> None:
    ANALYTICS_CACHE_HITS.labels(
        kind=kind, outcome="hit" if hit else "miss"
    ).inc()


_lag_task: Optional[asyncio.Task] = None


async def _event_loop_lag_probe(interval_seconds: float = 1.0) -> None:
    """Schedule itself every `interval_seconds`; record actual delay vs. target."""
    target = time.perf_counter() + interval_seconds
    while True:
        try:
            await asyncio.sleep(max(0.0, target - time.perf_counter()))
            now = time.perf_counter()
            lag = max(0.0, now - target)
            EVENT_LOOP_LAG.set(lag)
            try:
                from app.services.dataset_service import dataset_manager as _dm

                with _dm._df_cache_lock:
                    DF_CACHE_SIZE.set(len(_dm._df_cache))
            except Exception:
                pass
            target = now + interval_seconds
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("event_loop_lag_probe iteration failed")
            target = time.perf_counter() + interval_seconds


def setup_metrics(app: FastAPI) -> None:
    """Attach Prometheus instrumentation to a FastAPI app.

    Call this once during module import (after `app = FastAPI(...)`). Adds
    `/metrics`, registers HTTP middleware, and starts the loop-lag probe on
    application startup.
    """
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=["/metrics"],
        env_var_name="ENABLE_METRICS",
    )
    instrumentator.instrument(app)

    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if multiproc_dir:
        # Multi-worker: aggregate counter/histogram series across all forks
        # by reading the shared mmap dir. /metrics returns merged counters.
        @app.get("/metrics", include_in_schema=False)
        async def metrics_multiproc() -> Response:
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
        logger.info(
            "Prometheus /metrics in multiproc mode (PROMETHEUS_MULTIPROC_DIR=%s)",
            multiproc_dir,
        )
    else:
        # Single-worker: scrape the default registry directly. Each scrape
        # only sees its own worker's counters (which is fine for workers=1).
        @app.get("/metrics", include_in_schema=False)
        async def metrics_single() -> Response:
            return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
        logger.info("Prometheus /metrics in single-process mode")

    @app.on_event("startup")
    async def _start_loop_lag_probe() -> None:
        global _lag_task
        if _lag_task is None or _lag_task.done():
            _lag_task = asyncio.create_task(
                _event_loop_lag_probe(interval_seconds=1.0),
                name="midas_event_loop_lag_probe",
            )
            logger.info("Event-loop lag probe task started")

    @app.on_event("shutdown")
    async def _stop_loop_lag_probe() -> None:
        global _lag_task
        if _lag_task is not None and not _lag_task.done():
            _lag_task.cancel()
            try:
                await _lag_task
            except (asyncio.CancelledError, Exception):
                pass
        _lag_task = None

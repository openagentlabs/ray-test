"""Metric enums — single source for metric names, groups, and types."""

from __future__ import annotations

from enum import StrEnum


class MetricType(StrEnum):
    """Supported CloudWatch metric kinds."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class MetricGroup(StrEnum):
    """High-level metric grouping dimension."""

    GRPC = "grpc"
    DATABASE = "database"
    AUTH = "auth"
    RUNTIME = "runtime"
    BUSINESS = "business"
    SECURITY = "security"


class MetricName(StrEnum):
    """Catalog of first-class metric names (extend per service)."""

    REQUEST_COUNT = "request_count"
    REQUEST_DURATION_MS = "request_duration_ms"
    ERROR_COUNT = "error_count"
    ACTIVE_CONNECTIONS = "active_connections"
    DB_QUERY_DURATION_MS = "db_query_duration_ms"
    AUTH_FAILURE_COUNT = "auth_failure_count"
    QUEUE_DROPPED_COUNT = "queue_dropped_count"

"""EXL structured log format specification and serialization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from exl_observability.config.models import ServiceIdentityConfig
from exl_observability.core.correlation import get_correlation_id


@dataclass(frozen=True, slots=True)
class ExlLogRecord:
    """Canonical application log record (JSON line)."""

    timestamp: str
    level: str
    message: str
    service: dict[str, str]
    correlation_id: str
    channel: str
    attributes: dict[str, Any]

    def to_json_line(self) -> str:
        """Serialize to a single JSON line for CloudWatch / log aggregators."""
        payload = {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "service": self.service,
            "correlation_id": self.correlation_id,
            "channel": self.channel,
            "attributes": self.attributes,
            "format": "exl-log-v1",
        }
        return json.dumps(payload, default=str, separators=(",", ":"))


def build_log_record(
    *,
    level: str,
    message: str,
    identity: ServiceIdentityConfig,
    channel: str,
    attributes: dict[str, Any] | None = None,
) -> ExlLogRecord:
    """Build a normalized EXL log record."""
    return ExlLogRecord(
        timestamp=datetime.now(UTC).isoformat(),
        level=level.upper(),
        message=message,
        service={
            "id": identity.service_id,
            "name": identity.service_name,
            "version": identity.service_version,
            "instanceId": identity.instance_id,
            "environment": identity.environment,
        },
        correlation_id=get_correlation_id() or "-",
        channel=channel,
        attributes=attributes or {},
    )

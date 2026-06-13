"""Audit trail records for the ``assignment_events`` table."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AssignmentEventRecord(BaseModel):
    """Append-only assignment lifecycle event (PK ``event_id``)."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., min_length=1)
    sub: str = Field(..., min_length=1)
    pod_id: str = Field(default="")
    event_type: str = Field(..., min_length=1)
    timestamp: str = Field(..., min_length=1)
    assignment_epoch: int = Field(default=0, ge=0)

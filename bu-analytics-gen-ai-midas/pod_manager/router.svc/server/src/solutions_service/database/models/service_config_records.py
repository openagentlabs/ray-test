"""Record model for the ``service_config`` table."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ServiceConfigRecord(BaseModel):
    """Non-environment tunable (PK ``config_key``)."""

    model_config = ConfigDict(extra="forbid")

    config_key: str = Field(..., min_length=1)
    value: str = Field(default="")
    updated_at: str = Field(..., min_length=1)
    description: str = Field(default="")

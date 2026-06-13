"""Routing-tier record models (reference patterns for future tables)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SolutionDocumentRecord(BaseModel):
    """Solution document row (PK ``id``, indexed on ``solution_id``)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    deleted_at: str = Field(default="")
    is_deleted: bool = Field(default=False)
    solution_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = Field(default="")
    path: str = Field(..., min_length=1)

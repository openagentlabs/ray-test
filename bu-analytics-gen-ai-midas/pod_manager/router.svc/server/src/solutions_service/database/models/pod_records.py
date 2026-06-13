"""Routing record models (backend_pool, login_pod_pool, user_assignments)."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from solutions_service.database.models.pool_kind import BACKEND_POOL

NODE_STATE_FREE: Final[str] = "free"
NODE_STATE_CLAIMED: Final[str] = "claimed"

POD_STATE_FREE = NODE_STATE_FREE
POD_STATE_CLAIMED = NODE_STATE_CLAIMED


class BackendPoolNodeRecord(BaseModel):
    """Row in a pool registry table: one routable node (PK ``pod_id``, indexed on ``state``)."""

    model_config = ConfigDict(extra="forbid")

    pod_id: str = Field(..., min_length=1)
    pod_dns: str = Field(..., min_length=1)
    state: str = Field(default=NODE_STATE_FREE, min_length=1)
    assigned_sub: str = Field(default="")
    assignment_epoch: int = Field(default=0, ge=0)
    updated_at: str = Field(..., min_length=1)


PodPoolRecord = BackendPoolNodeRecord


class UserAssignmentRecord(BaseModel):
    """User → pool node (PK ``sub``, indexed on ``pod_id``)."""

    model_config = ConfigDict(extra="forbid")

    sub: str = Field(..., min_length=1)
    pod_id: str = Field(..., min_length=1)
    pod_dns: str = Field(..., min_length=1)
    pool: str = Field(
        default=BACKEND_POOL,
        min_length=1,
        description="backend_pool (leases only; login_pod_pool has no user assignments)",
    )
    assignment_epoch: int = Field(..., ge=1)
    updated_at: str = Field(..., min_length=1)

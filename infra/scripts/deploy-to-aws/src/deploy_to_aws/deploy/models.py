"""Deploy phase models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from deploy_to_aws.core.option import Option


class DeployInvokeParams(BaseModel):
    """Validated CLI / action invoke parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    auto_approve: Option[bool] = None
    skip_build: Option[bool] = None
    skip_scaffold: Option[bool] = None
    skip_preflight: Option[bool] = None
    image_tag: Option[str] = None
    no_cache: Option[bool] = None
    post_terraform_only: bool = False


class PhaseOutcome(BaseModel):
    """Result payload for a single deploy phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., min_length=1)
    ok: bool
    detail: str = ""
    data: dict[str, object] = Field(default_factory=dict)


class DeploySummary(BaseModel):
    """Aggregate deploy run summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phases: tuple[PhaseOutcome, ...]
    success: bool
    manager_web_url: str = ""

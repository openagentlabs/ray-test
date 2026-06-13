"""Pydantic v2 models for JIRA-aligned Bug ticket records and consolidated findings rows."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums / literals
# ---------------------------------------------------------------------------

ScanSource = Literal["fortify", "container", "iac", "oss"]
JiraPriority = Literal["Critical", "High", "Medium", "Low"]
OwnerTeam = Literal["Software", "DevOps"]
EffortEstimate = Literal["S", "M", "L"]
ComplexityLevel = Literal["LOW", "MID", "HIGH", "MAX"]
ParentGroup = Literal["CONTAINER_CVE", "OSS_CVE", "IAC_POLICY", "FORTIFY_CODE", "RESIDUAL"]


# ---------------------------------------------------------------------------
# Consolidated finding row (one per original finding across all sources)
# ---------------------------------------------------------------------------

class ConsolidatedFinding(BaseModel):
    """One normalised finding row, regardless of source scan type."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    source: ScanSource
    severity: str
    category_or_policy: str
    file_or_resource: str
    vulnerability_or_policy_id: str
    description: str
    fix_version_or_recommendation: str
    bug_id: str = ""


# ---------------------------------------------------------------------------
# JIRA Bug ticket (one per group or residual)
# ---------------------------------------------------------------------------

class JiraTicket(BaseModel):
    """One JIRA Bug ticket row."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    parent_epic: str = "SEC-EPIC-001"
    parent_group: ParentGroup
    title: str
    issue_type: str = "Bug"
    priority: JiraPriority
    owner_team: OwnerTeam
    effort_estimate: EffortEstimate
    complexity: ComplexityLevel
    root_cause: str
    files_to_change: str
    findings_cleared_count: int
    findings_cleared_ids: str
    risk: str
    validation_steps: str
    is_grouped: bool
    residual_file_line: str = ""
    labels: str
    consolidated_finding_ids: str = ""  # comma-separated finding_id values from all_findings_consolidated.csv

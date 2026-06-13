"""Canonical domain models — internal representation independent of output encoding."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fortify_workbook_tool.constants import DEFAULT_ISSUE_STATE, DEFAULT_STRIP_PREFIXES


class FortifyIssue(BaseModel):
    """One Fortify finding (Kingdom block) after parsing Results Outline text."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    #: Stable row id for tracking (``OBV0001`` …) — assigned in order when the extract is built.
    obv_id: str = ""
    category: str = ""
    category_issue_count: str = ""
    fortify_priority: str = ""
    package: str = ""
    reference_line: str = ""
    kingdom: str = ""
    scan_engine: str = ""
    source_kind: str = ""
    source_detail: str = ""
    source_file: str = ""
    source_line: str = ""
    sink_kind: str = ""
    sink_detail: str = ""
    sink_file: str = ""
    sink_line: str = ""
    taint_flags: str = ""
    abstract: str = ""
    explanation: str = ""
    recommendation: str = ""
    # --- Analysis workflow (empty placeholders on PDF extract; filled during AI/human remediation tracking) ---
    analysis_id: str = ""
    analysis_log_file: str = ""
    resolution_owner: str = ""
    complexity: str = ""
    human_fix_hours: str = ""
    cursor_fix_hours: str = ""
    hybrid_fix_hours: str = ""
    issue_scope_summary: str = ""
    # --- Remediation workflow (empty except ``issue_state`` on PDF extract) ---
    root_cause: str = ""
    remediation_plan: str = ""
    validation: str = ""
    acceptance_criteria: str = ""
    #: Team ownership of the fix: ``Software`` (app/IaC code) or ``DevOps`` (platform/pipeline).
    #: Empty on PDF extract; populated during Phase-2 analysis.
    owner: str = ""
    issue_resolve_progress: str = ""
    resolved_date: str = ""
    working_log: str = ""
    issue_state: str = DEFAULT_ISSUE_STATE

    def as_flat_strings(self, normalize_paths: bool, strip_prefixes: Tuple[str, ...]) -> Dict[str, str]:
        """CSV-oriented flat dict with optional repo path normalization."""
        from fortify_workbook_tool.normalization import TextNormalizer

        data = self.model_dump()
        if normalize_paths:
            for key in ("source_file", "sink_file"):
                val = data.get(key)
                if val:
                    data[key] = TextNormalizer.normalize_repo_path(str(val), strip_prefixes)
        return {k: str(v) if v is not None else "" for k, v in data.items()}

    def projected_dict(self, fields: Optional[List[str]]) -> Dict[str, Any]:
        """Subset of fields for JSON/YAML; ``None`` means all fields; ``[]`` means empty dict."""
        full = self.model_dump()
        if fields is None:
            return full
        unknown = set(fields) - set(full.keys())
        if unknown:
            raise ValueError(f"Unknown issue fields requested: {sorted(unknown)}")
        return {k: full[k] for k in fields}


class PrioritySummary(BaseModel):
    """Aggregated Fortify priority counts."""

    model_config = ConfigDict(frozen=True)

    total: int = Field(ge=0)
    critical: int = Field(ge=0)
    high: int = Field(ge=0)
    medium: int = Field(ge=0)
    low: int = Field(ge=0)
    other: int = Field(ge=0)

    @model_validator(mode="after")
    def _totals_consistent(self) -> PrioritySummary:
        known = self.critical + self.high + self.medium + self.low
        if known + self.other != self.total:
            raise ValueError("Priority buckets must sum to total")
        return self


class WorkbookExtraction(BaseModel):
    """Internal extraction result — input to all output formatters."""

    model_config = ConfigDict(frozen=True)

    source_pdf: Path
    issues: Tuple[FortifyIssue, ...]
    warnings: Tuple[str, ...]
    loader_warnings: Tuple[str, ...] = ()

    def all_warnings(self) -> Tuple[str, ...]:
        return tuple(self.loader_warnings) + tuple(self.warnings)


class FormatterOptions(BaseModel):
    """Options passed to concrete formatters (paths, projections)."""

    model_config = ConfigDict(frozen=True)

    normalize_paths: bool = True
    strip_prefixes: Tuple[str, ...] = DEFAULT_STRIP_PREFIXES
    issue_field_subset: Optional[Tuple[str, ...]] = None
    include_priority_summary: bool = True
    schema_version: str = "1.3"

"""Pydantic models for JSON-driven tool invocations (schemas for agents / skills)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class StructuredJobOutputSpec(BaseModel):
    """Output section for the structured job — format, path, and optional field projection."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["json", "csv", "yaml"] = Field(
        description="Serialized encoding for issues and metadata.",
    )
    path: Optional[Path] = Field(
        default=None,
        description="If set, write to this file; if omitted with stdout_mode, print to stdout.",
    )
    include_priority_summary: bool = True
    issue_field_subset: Optional[List[str]] = Field(
        default=None,
        description="If set, each issue object only includes these FortifyIssue field names (JSON/YAML only).",
    )


class StructuredJobConfig(BaseModel):
    """Rich JSON job: PDF path + nested output specification."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    job_type: Literal["structured"] = "structured"
    pdf_path: Path
    normalize_paths: bool = True
    fail_on_warnings: bool = False
    output: StructuredJobOutputSpec


class SimpleFileJobConfig(BaseModel):
    """Minimal JSON job: PDF path + explicit output file path + format."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    job_type: Literal["simple_file"] = "simple_file"
    pdf_path: Path
    output_path: Path
    output_format: Literal["json", "csv", "yaml"]
    normalize_paths: bool = True
    fail_on_warnings: bool = False


def coerce_job_config(data: object) -> Union[StructuredJobConfig, SimpleFileJobConfig]:
    """Infer structured vs simple_file job from parsed JSON object."""
    if not isinstance(data, dict):
        raise TypeError("JSON root must be an object")

    raw_job_type = data.get("job_type")
    if raw_job_type == "simple_file":
        return SimpleFileJobConfig.model_validate(data)
    if raw_job_type == "structured":
        return StructuredJobConfig.model_validate(data)

    if "output_path" in data and "output_format" in data:
        payload = {**data, "job_type": "simple_file"}
        return SimpleFileJobConfig.model_validate(payload)

    if "output" in data and isinstance(data["output"], dict):
        payload = {**data, "job_type": "structured"}
        return StructuredJobConfig.model_validate(payload)

    raise ValueError(
        "Cannot infer job: include job_type, or use simple_file keys "
        "(output_path + output_format), or structured keys (output.format + output)."
    )


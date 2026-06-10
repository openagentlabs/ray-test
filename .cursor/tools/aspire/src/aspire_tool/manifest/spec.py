"""AI-facing JSON manifest describing this CLI (name, version, use cases, JSON Schemas)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AddServiceInput(BaseModel):
    """Input schema for ``-a`` use case."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="Absolute or relative path to an executable file.")
    name: str = Field(..., min_length=1, description="Display name for the registry row.")
    description: str = Field(default="", description="Human description stored in the DB.")


class RemoveServiceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, description="Primary key of the row to delete.")


class ServiceRecordOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    display_name: str
    role: str
    kind: str
    workdir_relative: str
    command: str
    args_json: str
    port: int | None
    health_kind: str
    health_target: str | None
    description: str | None
    start_order: int
    enabled: bool
    auto_start_with_home: bool
    env_json: str | None


class UseCaseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    flags: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class ToolManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    version: str
    use_cases: list[UseCaseSpec]


def build_tool_manifest_json() -> str:
    """Return a single JSON string suitable for stdout (AI discovery)."""
    manifest = ToolManifest(
        name="aspire-registry-tool",
        description=(
            "Manage the Arb Aspire `registered_services` SQLite registry "
            "(same schema as `aspire.svc/service-registry.sqlite`)."
        ),
        version="0.1.0",
        use_cases=[
            UseCaseSpec(
                id="manifest",
                description="Print this JSON document (no operation flags).",
                flags=[],
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema=ToolManifest.model_json_schema(),
            ),
            UseCaseSpec(
                id="list_services",
                description="List all rows as JSON objects.",
                flags=["-l", "--list"],
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema={
                    "type": "object",
                    "properties": {
                        "services": {
                            "type": "array",
                            "items": ServiceRecordOut.model_json_schema(),
                        },
                    },
                    "required": ["services"],
                },
            ),
            UseCaseSpec(
                id="add_service",
                description="Insert a new executable-backed service row.",
                flags=["-a", "--add", "-p", "--path", "-n", "--name", "-d", "--description"],
                input_schema=AddServiceInput.model_json_schema(),
                output_schema=ServiceRecordOut.model_json_schema(),
            ),
            UseCaseSpec(
                id="remove_service",
                description="Delete a row by id.",
                flags=["-r", "--remove", "-i", "--id"],
                input_schema=RemoveServiceInput.model_json_schema(),
                output_schema={
                    "type": "object",
                    "properties": {"deleted": {"type": "string"}},
                    "required": ["deleted"],
                },
            ),
        ],
    )
    return json.dumps(manifest.model_dump(), indent=2, sort_keys=False)

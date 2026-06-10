"""Tests for the AI-facing manifest JSON."""

from __future__ import annotations

import json

from aspire_tool.manifest.spec import ToolManifest, build_tool_manifest_json


def test_manifest_is_valid_json_and_matches_model() -> None:
    raw = build_tool_manifest_json()
    data = json.loads(raw)
    parsed = ToolManifest.model_validate(data)
    assert parsed.name == "aspire-registry-tool"
    assert len(parsed.use_cases) >= 4
    ids = {uc.id for uc in parsed.use_cases}
    assert ids >= {"manifest", "list_services", "add_service", "remove_service"}

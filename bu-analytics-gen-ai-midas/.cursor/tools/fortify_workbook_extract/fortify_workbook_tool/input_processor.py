"""Parse and validate JSON configuration for agent-driven invocations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from fortify_workbook_tool.input_models import SimpleFileJobConfig, StructuredJobConfig, coerce_job_config


class ToolJsonInputProcessor:
    """
    Loads JSON job definitions used by Cursor agents / CI.

    Accepts either a bare job object or ``{\"job\": { ... }}``.
    """

    def parse_bytes(self, raw: bytes) -> Union[StructuredJobConfig, SimpleFileJobConfig]:
        text = raw.decode("utf-8")
        return self.parse_string(text)

    def parse_string(self, raw: str) -> Union[StructuredJobConfig, SimpleFileJobConfig]:
        data = json.loads(raw)
        if isinstance(data, dict) and "job" in data and isinstance(data["job"], dict):
            return coerce_job_config(data["job"])
        return coerce_job_config(data)

    def parse_path(self, path: Path) -> Union[StructuredJobConfig, SimpleFileJobConfig]:
        return self.parse_bytes(path.expanduser().read_bytes())

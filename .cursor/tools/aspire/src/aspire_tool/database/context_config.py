"""Resolved SQLite path for the service registry."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class DatabaseContextConfig(BaseModel):
    """Immutable database wiring."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sqlite_path: Path = Field(..., description="Absolute path to service-registry.sqlite.")

    @staticmethod
    def from_environment(*, cwd: Path | None = None) -> DatabaseContextConfig:
        raw = os.environ.get("ASPIRE_REGISTRY_DB", "").strip()
        base = cwd if cwd is not None else Path.cwd()
        if len(raw) > 0:
            candidate = Path(raw)
            resolved = candidate if candidate.is_absolute() else (base / candidate)
        else:
            resolved = base / "aspire.svc" / "service-registry.sqlite"
        return DatabaseContextConfig(sqlite_path=resolved.resolve())

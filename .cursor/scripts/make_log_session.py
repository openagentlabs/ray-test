"""Shared paths and helpers for make-local ruff logging sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKE_LOGS_ROOT = REPO_ROOT / ".cursor/scratch/make-logs"

# Python microservices with ruff in pyproject.toml (frontend uses ESLint, not ruff).
RUFF_SERVICE_DIRS: tuple[tuple[str, Path], ...] = (
    ("iam", REPO_ROOT / "iam.svc/server"),
    ("general-ai-agent", REPO_ROOT / "general.ai.agent.svc/server"),
    ("solutions", REPO_ROOT / "solutions.svc/server"),
    ("storage", REPO_ROOT / "storage.svc/server"),
    ("notification", REPO_ROOT / "notification.svc/server"),
    ("collaboration", REPO_ROOT / "collaboration.svc/server"),
    ("document-storage", REPO_ROOT / "document-storage.svc/server"),
    ("arch-diagram-agent", REPO_ROOT / "arch.diagram.agent.svc/server"),
)


def session_stamp(now: datetime | None = None) -> str:
    dt = now or datetime.now(timezone.utc).astimezone()
    return dt.strftime("%Y%m%d%H%M%S")


@dataclass(frozen=True)
class MakeLogSession:
    stamp: str
    directory: Path

    @classmethod
    def create(cls, *, stamp: str | None = None) -> MakeLogSession:
        value = stamp or session_stamp()
        directory = MAKE_LOGS_ROOT / value
        directory.mkdir(parents=True, exist_ok=True)
        return cls(stamp=value, directory=directory)

    def artifact_path(self, service_id: str, extension: str) -> Path:
        ext = extension if extension.startswith(".") else f".{extension}"
        return self.directory / f"{service_id}_{self.stamp}{ext}"

"""Typed application configuration loaded from ``app_config.toml``.

Supports dotted attribute access on the returned root object, for example
``get_app_config().paths.analysis_log_dir``.

Optional override: set env ``FORTIFY_WORKBOOK_APP_CONFIG`` to an absolute or relative path
to a replacement TOML file.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import tomllib
from pydantic import BaseModel, ConfigDict, Field

_config_path_override: Path | None = None


class AppSection(BaseModel):
    """Product identity strings."""

    model_config = ConfigDict(extra="forbid")

    name: str = "Fortify Developer Workbook Extract"
    tool_id: str = "parse_isg_code_scan_report_tool"


class PathsSection(BaseModel):
    """Repo-relative paths used by remediation workflows."""

    model_config = ConfigDict(extra="forbid")

    analysis_log_dir: str = ".cursor/scratch/analysis_log"


class FormatterSection(BaseModel):
    """Serialized output metadata."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.3"


class ExtractionSection(BaseModel):
    """PDF parse / path normalization defaults."""

    model_config = ConfigDict(extra="forbid")

    normalize_paths_default: bool = True
    strip_prefixes: tuple[str, ...] = Field(
        default=(
            "Downloads/bu-analytics-gen-ai-midas-deployment-dev-jenkins/",
            "bu-analytics-gen-ai-midas-deployment-dev-jenkins/",
        )
    )


class OutputSection(BaseModel):
    """CLI defaults when flags are omitted."""

    model_config = ConfigDict(extra="forbid")

    default_format: str = "csv"


class FortifyWorkbookAppConfig(BaseModel):
    """Root configuration — sections map 1:1 to ``app_config.toml`` tables."""

    model_config = ConfigDict(extra="forbid")

    app: AppSection = Field(default_factory=AppSection)
    paths: PathsSection = Field(default_factory=PathsSection)
    formatter: FormatterSection = Field(default_factory=FormatterSection)
    extraction: ExtractionSection = Field(default_factory=ExtractionSection)
    output: OutputSection = Field(default_factory=OutputSection)


def default_app_config_path() -> Path:
    """``app_config.toml`` beside this package (``.cursor/tools/fortify_workbook_extract/``)."""
    return Path(__file__).resolve().parent.parent / "app_config.toml"


def set_app_config_path(path: Path | None) -> None:
    """Force loads from *path* (or embedded defaults if ``None``). Clears the config cache."""
    global _config_path_override
    _config_path_override = path.expanduser() if path is not None else None
    reload_app_config()


def resolve_app_config_path(explicit: Path | None = None) -> Path | None:
    """Return path to load, or ``None`` to use embedded Pydantic defaults only."""
    if explicit is not None:
        return explicit
    if _config_path_override is not None:
        return _config_path_override
    env = os.environ.get("FORTIFY_WORKBOOK_APP_CONFIG", "").strip()
    if env:
        return Path(env).expanduser()
    p = default_app_config_path()
    return p if p.is_file() else None


def load_app_config(path: Path | None = None) -> FortifyWorkbookAppConfig:
    """Load and validate config. If ``path`` is ``None``, resolves via :func:`resolve_app_config_path`."""
    resolved = path if path is not None else resolve_app_config_path()
    if resolved is None:
        return FortifyWorkbookAppConfig()
    raw = resolved.read_bytes()
    data = tomllib.loads(raw.decode("utf-8"))
    return FortifyWorkbookAppConfig.model_validate(data)


@lru_cache(maxsize=1)
def _cached_load() -> FortifyWorkbookAppConfig:
    return load_app_config()


def get_app_config() -> FortifyWorkbookAppConfig:
    """Singleton config for CLI runs (cached)."""
    return _cached_load()


def reload_app_config() -> FortifyWorkbookAppConfig:
    """Clear cache and reload (e.g. after setting ``FORTIFY_WORKBOOK_APP_CONFIG``)."""
    _cached_load.cache_clear()
    return get_app_config()


def dotted_get(root: Any, dotted_path: str) -> Any:
    """Resolve a dotted path like ``paths.analysis_log_dir`` on *root* via repeated :func:`getattr`.

    Raises :class:`AttributeError` if any segment is missing.
    """
    cur: Any = root
    segments = [s for s in dotted_path.strip().split(".") if s]
    if not segments:
        raise ValueError("dotted_path must contain at least one segment")
    for seg in segments:
        cur = getattr(cur, seg)
    return cur


def dotted_get_optional(root: Any, dotted_path: str, default: Any = None) -> Any:
    """Like :func:`dotted_get` but returns *default* if a segment is absent."""
    cur: Any = root
    for seg in [s for s in dotted_path.strip().split(".") if s]:
        if cur is None:
            return default
        cur = getattr(cur, seg, None)
    return cur if cur is not None else default

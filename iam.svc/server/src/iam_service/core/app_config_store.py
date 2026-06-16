"""Process-wide ``app_config`` singleton — load once, read everywhere."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from iam_service.core.app_config import AppConfig
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success

_DEFAULT_ENV_KEY: Final[str] = "IAM_APP_CONFIG_PATH"
_DEFAULT_FILENAME: Final[str] = "app_config.toml"

_store: AppConfig | None = None
_store_path: Path | None = None


def default_config_path() -> Path:
    """Resolve config file path from env or CWD default."""
    import os

    raw = os.environ.get(_DEFAULT_ENV_KEY, _DEFAULT_FILENAME).strip()
    return Path(raw)


def init_app_config(path: Path | None = None) -> Result[AppConfig, AppError]:
    """Load TOML into the singleton; return cached instance on repeat calls."""
    global _store, _store_path
    if _store is not None:
        return Success(_store)

    resolved = (path or default_config_path()).resolve()
    loaded = AppConfig.load(resolved)
    if isinstance(loaded, Failure):
        return loaded

    _store = loaded.unwrap()
    _store_path = resolved
    return Success(_store)


def app_config() -> AppConfig:
    """Return the loaded singleton; fail fast if startup has not initialized it."""
    if _store is None:
        msg = (
            "app_config is not loaded. Call init_app_config() from main before "
            "accessing app_config()."
        )
        raise RuntimeError(msg)
    return _store


def app_config_path() -> Path | None:
    """Path used for the active singleton, or ``None`` before init."""
    return _store_path


def reset_app_config_for_tests() -> None:
    """Clear singleton state — tests only."""
    global _store, _store_path
    _store = None
    _store_path = None


def ensure_app_config_for_tests(config: AppConfig | None = None) -> AppConfig:
    """Seed singleton with defaults when tests need config without TOML I/O."""
    global _store, _store_path
    if _store is not None:
        return _store
    cfg = config or AppConfig.default()
    _store = cfg
    _store_path = None
    return cfg


def is_app_config_loaded() -> bool:
    """Whether ``app_config()`` is safe to call."""
    return _store is not None


def require_app_config() -> Result[AppConfig, AppError]:
    """Result-style access for code that must not raise."""
    if _store is None:
        return Failure(
            AppError(
                code=ErrorCodes.INTERNAL,
                message="Application config is not loaded.",
                detail="Call init_app_config() during startup.",
            ),
        )
    return Success(_store)

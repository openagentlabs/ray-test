"""Apply process environment overrides to a TOML config dict (DRY, schema-driven)."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from typing import Final, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

# Canonical prefix for generated keys: POD_MANAGER_<SECTION>_<FIELD>...
DEFAULT_CONFIG_ENV_PREFIX: Final[str] = "POD_MANAGER"

# Non-standard env names kept for backward compatibility (oldest deployments).
LEGACY_ENV_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "LOG_LEVEL": ("app", "log_level"),
    "SOLUTIONS_APP_LOG_LEVEL": ("app", "log_level"),
    "SOLUTIONS_LOG_LEVEL": ("app", "log_level"),
    "SOLUTIONS_SERVICE_GRPC_HOST": ("api_service", "host"),
    "SOLUTIONS_SERVICE_GRPC_PORT": ("api_service", "port"),
    # Shared Postgres DSN (same variable the backend uses).
    "DATABASE_URL": ("postgres", "dsn"),
}


def env_var_name(prefix: str, path: tuple[str, ...]) -> str:
    """Build ``PREFIX_SECTION_FIELD`` from a nested config path."""
    return f"{prefix}_{'_'.join(part.upper() for part in path)}"


def legacy_env_var_name(prefix: str, path: tuple[str, ...]) -> str:
    """``SOLUTIONS_*`` mirror of ``env_var_name`` (same segments, legacy product prefix)."""
    legacy_prefix = "SOLUTIONS" if prefix == DEFAULT_CONFIG_ENV_PREFIX else prefix
    return env_var_name(legacy_prefix, path)


def env_keys_for_path(
    prefix: str,
    path: tuple[str, ...],
    *,
    extra_aliases: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[str, ...]:
    """All env var names that may override ``path`` (canonical first, then legacy)."""
    keys: list[str] = [env_var_name(prefix, path)]
    if prefix == DEFAULT_CONFIG_ENV_PREFIX:
        keys.append(legacy_env_var_name(prefix, path))
    aliases = extra_aliases if extra_aliases is not None else LEGACY_ENV_ALIASES
    keys.extend(alias for alias, alias_path in aliases.items() if alias_path == path)
    return tuple(keys)


def iter_leaf_field_paths(model: type[BaseModel]) -> Iterator[tuple[tuple[str, ...], FieldInfo]]:
    """Yield ``(path, FieldInfo)`` for every scalar leaf in a nested Pydantic model tree."""
    for name, field in model.model_fields.items():
        path = (name,)
        yield from _iter_field_paths(field.annotation, path, field)


def _iter_field_paths(
    annotation: object,
    path: tuple[str, ...],
    field: FieldInfo,
) -> Iterator[tuple[tuple[str, ...], FieldInfo]]:
    nested = _nested_model_type(annotation)
    if nested is not None:
        for name, child in nested.model_fields.items():
            yield from _iter_field_paths(child.annotation, path + (name,), child)
        return
    yield path, field


def _nested_model_type(annotation: object) -> type[BaseModel] | None:
    origin = get_origin(annotation)
    if origin is not None:
        for arg in get_args(annotation):
            nested = _nested_model_type(arg)
            if nested is not None:
                return nested
        return None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _coerce_env_value(raw: str, field: FieldInfo) -> object:
    annotation = field.annotation
    nested = _nested_model_type(annotation)
    if nested is not None:
        msg = "leaf coercion called on nested model field"
        raise TypeError(msg)

    origin = get_origin(annotation)
    if origin is not None:
        for arg in get_args(annotation):
            if arg is type(None):
                continue
            if isinstance(arg, type) and issubclass(arg, BaseModel):
                continue
            annotation = arg
            break

    if annotation is int:
        return int(raw.strip())
    if annotation is bool:
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        msg = f"invalid boolean env value: {raw!r}"
        raise ValueError(msg)
    return raw.strip()


def _set_nested(config: dict[str, object], path: tuple[str, ...], value: object) -> None:
    cursor: dict[str, object] = config
    for key in path[:-1]:
        child = cursor.get(key)
        if not isinstance(child, dict):
            child = {}
            cursor[key] = child
        cursor = child
    cursor[path[-1]] = value


def apply_env_overrides_to_config(
    config: dict[str, object],
    *,
    model: type[BaseModel],
    prefix: str = DEFAULT_CONFIG_ENV_PREFIX,
    extra_aliases: Mapping[str, tuple[str, ...]] | None = None,
) -> None:
    """Override ``config`` leaves when matching env vars are set (including empty strings)."""
    for path, field in iter_leaf_field_paths(model):
        raw_value: str | None = None
        for env_key in env_keys_for_path(prefix, path, extra_aliases=extra_aliases):
            if env_key not in os.environ:
                continue
            raw_value = os.environ[env_key]
        if raw_value is None:
            continue
        try:
            coerced = _coerce_env_value(raw_value, field)
        except ValueError:
            continue
        _set_nested(config, path, coerced)


def documented_env_keys(
    model: type[BaseModel],
    *,
    prefix: str = DEFAULT_CONFIG_ENV_PREFIX,
    extra_aliases: Mapping[str, tuple[str, ...]] | None = None,
) -> list[tuple[str, tuple[str, ...]]]:
    """Sorted ``(env_var, config_path)`` pairs for docs and ``.env.example`` generation."""
    seen: dict[str, tuple[str, ...]] = {}
    for path, _ in iter_leaf_field_paths(model):
        for key in env_keys_for_path(prefix, path, extra_aliases=extra_aliases):
            seen.setdefault(key, path)
    return sorted(seen.items(), key=lambda item: item[0])

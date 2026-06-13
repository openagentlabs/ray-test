import json
from pathlib import Path
from typing import Any, Dict, Optional

_cache_mtime: Optional[float] = None
_cache_data: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None

# Usage-type sections that should be exposed to the UI. Sections such as
# ``_disabled`` live in the JSON alongside these but must never be served.
_PUBLIC_USAGE_SECTIONS = ("chat", "knowledge_graph", "embedding")


def _mapping_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "llm_model_mapping.json"


def _load_mapping() -> Dict[str, Dict[str, Dict[str, Any]]]:
    global _cache_mtime, _cache_data
    path = _mapping_path()
    mtime = path.stat().st_mtime if path.exists() else None
    if _cache_data is not None and _cache_mtime == mtime:
        return _cache_data
    if not path.exists():
        _cache_data = {}
        _cache_mtime = None
        return _cache_data
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    _cache_data = data or {}
    _cache_mtime = mtime
    return _cache_data


def _filter_for_gateway(
    entries: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """When the AI Gateway is active, hide any model that lacks a
    ``gateway_model_id`` so the UI dropdown never surfaces un-routable options.
    """
    try:
        # Local import avoids a circular import at module load time.
        from app.core.config import gateway_enabled
    except Exception:
        return entries
    if not gateway_enabled():
        return entries
    return {
        name: payload
        for name, payload in entries.items()
        if isinstance(payload, dict) and payload.get("gateway_model_id")
    }


def get_model_config(usage_type: str, model_id: str) -> Optional[Dict[str, Any]]:
    """Return the raw mapping entry. Not filtered — callers need the full
    config (incl. direct-provider fallback fields) so resolution still works
    even when the UI listing would hide the entry.
    """
    mapping = _load_mapping()
    usage_key = usage_type.strip().lower()
    return mapping.get(usage_key, {}).get(model_id)


def list_models(usage_type: str) -> Dict[str, Dict[str, Any]]:
    mapping = _load_mapping()
    usage_key = usage_type.strip().lower()
    return _filter_for_gateway(mapping.get(usage_key, {}))


def list_all_models() -> Dict[str, Dict[str, Dict[str, Any]]]:
    mapping = _load_mapping()
    return {
        usage_key: _filter_for_gateway(mapping.get(usage_key, {}))
        for usage_key in _PUBLIC_USAGE_SECTIONS
        if usage_key in mapping
    }

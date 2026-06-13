"""Tag-based LLM routing policy and candidate resolution.

Each UI/backend operation declares a :class:`RoutingPolicy` naming a default
model and the set of tags a fallback candidate must carry. The candidate list
always starts with the declared default (if it is still routable), followed by
all other models whose ``tags`` array is a superset of the required tags.

Agnostic to gateway vs direct-provider: when the AI Gateway is enabled, models
without a ``gateway_model_id`` are filtered out so we never queue an
un-routable candidate.

Embeddings are intentionally excluded from tag routing — the embedding path
uses a single model (see ``DEFAULT_EMBEDDING_MODEL``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.core.llm_registry import _load_mapping  # noqa: WPS450 - intentional internal use


# ---------------------------------------------------------------------------
# Policy registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoutingPolicy:
    """Routing config for a given usage context."""

    default_model: str
    required_tags: Tuple[str, ...]
    usage_key: str  # "chat" or "knowledge_graph"


# Canonical context name -> policy.
#
# The names here are what callers pass to ``execute_with_fallback`` /
# ``candidates_for``. Keep them stable; they show up in logs.
POLICIES: Dict[str, RoutingPolicy] = {
    "objectives_classification": RoutingPolicy("claude-haiku-4-5", ("fast", "cheap"), "chat"),
    "variable_classification":   RoutingPolicy("claude-haiku-4-5", ("fast", "cheap"), "chat"),
    "knowledge_graph":           RoutingPolicy("claude-haiku-4-5", ("fast", "coding"), "knowledge_graph"),
    "data_treatment":            RoutingPolicy("claude-opus-4-6",  ("fast", "coding"), "chat"),
    "data_insights":             RoutingPolicy("claude-haiku-4-5", ("fast",),          "chat"),
    "feature_engineering":       RoutingPolicy("claude-opus-4-6",  ("fast", "coding"), "chat"),
    "model_training":            RoutingPolicy("claude-haiku-4-5", ("fast",),          "chat"),
    "model_documentation":       RoutingPolicy("claude-haiku-4-5", ("fast",),          "chat"),
    "segmentation":              RoutingPolicy("claude-haiku-4-5", ("fast",),          "chat"),
    "model_evaluation":          RoutingPolicy("claude-haiku-4-5", ("fast",),          "chat"),
    "ai_explainability":         RoutingPolicy("claude-haiku-4-5", ("fast",),          "chat"),
    "guardrail":                 RoutingPolicy("claude-haiku-4-5", ("fast", "cheap"), "chat"),
    "default_chat":              RoutingPolicy("claude-haiku-4-5", ("fast",),          "chat"),
}


# ``agent_context`` values the frontend sends on POST /chat map 1:1 to routing
# contexts. Any value not in this map degrades to ``default_chat``.
AGENT_CONTEXT_TO_ROUTING: Dict[str, str] = {
    "data_transformation": "data_treatment",
    "data_insight":        "data_insights",
    "feature_engineering": "feature_engineering",
    "modelling":           "model_training",
    "segmentation":        "segmentation",
    "model_evaluation":    "model_evaluation",
    "ai_explainability":   "ai_explainability",
}


def policy_for(context: str) -> RoutingPolicy:
    """Return the declared policy; fall back to ``default_chat`` if unknown."""
    return POLICIES.get(context) or POLICIES["default_chat"]


def routing_context_for_agent(agent_context: str | None) -> str:
    """Map a frontend ``agent_context`` to a routing context name."""
    if not agent_context:
        return "default_chat"
    return AGENT_CONTEXT_TO_ROUTING.get(agent_context.strip().lower(), "default_chat")


# ---------------------------------------------------------------------------
# Candidate resolution
# ---------------------------------------------------------------------------


def _gateway_on() -> bool:
    """Cheap guarded import to avoid a circular dependency at module load."""
    try:
        from app.core.config import gateway_enabled  # local import on purpose
        return bool(gateway_enabled())
    except Exception:
        return False


def _is_routable(payload: Dict, gateway_on: bool) -> bool:
    """Gateway-on: entry must carry a ``gateway_model_id``.
    Gateway-off: any entry with the minimum provider/model fields is fine.
    """
    if not isinstance(payload, dict):
        return False
    if gateway_on:
        return bool(payload.get("gateway_model_id"))
    return bool(payload.get("provider")) and bool(payload.get("model"))


def _score(model_tags: Tuple[str, ...], required: Tuple[str, ...]) -> int:
    required_set = set(required)
    model_set = set(model_tags)
    if not required_set.issubset(model_set):
        return -1
    # More required-tag matches first, then wider tag coverage as tiebreaker.
    return len(required_set & model_set) * 100 + len(model_set)


def candidates_for(context: str) -> List[str]:
    """Return an ordered list of model ids to try for ``context``.

    Ordering: the declared default first (if routable), then all other models
    whose tags cover the required set, sorted by match strength then by
    appearance order in ``llm_model_mapping.json``.
    """
    policy = policy_for(context)
    mapping = _load_mapping()
    section = mapping.get(policy.usage_key, {}) or {}
    gw = _gateway_on()

    ordered: List[str] = []
    seen = set()

    # 1) default first if it is defined and routable.
    default_payload = section.get(policy.default_model)
    if default_payload and _is_routable(default_payload, gw):
        ordered.append(policy.default_model)
        seen.add(policy.default_model)

    # 2) everyone else whose tags satisfy the policy, ranked by score then by
    # appearance order (stable Python sort preserves insertion order on ties).
    scored: List[Tuple[int, int, str]] = []
    for idx, (model_id, payload) in enumerate(section.items()):
        if model_id in seen:
            continue
        if not _is_routable(payload, gw):
            continue
        tags = tuple(payload.get("tags") or ())
        score = _score(tags, policy.required_tags)
        if score < 0:
            continue
        scored.append((-score, idx, model_id))

    scored.sort()
    ordered.extend(model_id for _, _, model_id in scored)
    return ordered


__all__ = [
    "RoutingPolicy",
    "POLICIES",
    "AGENT_CONTEXT_TO_ROUTING",
    "policy_for",
    "routing_context_for_agent",
    "candidates_for",
]

"""Tests for the tag-based LLM routing policy and candidate resolution."""

from __future__ import annotations

import unittest
from typing import Any, Dict, List
from unittest.mock import patch

import app.core.config as config_module
from app.core.llm_routing import (
    AGENT_CONTEXT_TO_ROUTING,
    POLICIES,
    candidates_for,
    policy_for,
    routing_context_for_agent,
)


class _GatewayCtx:
    """Flip the module-level gateway flags on/off around a test block."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self._saved = (
            config_module.LLM_USE_GATEWAY,
            config_module.LLM_GATEWAY_URL,
            config_module.LLM_GATEWAY_VIRTUAL_KEY,
        )

    def __enter__(self) -> None:
        config_module.LLM_USE_GATEWAY = self.enabled
        config_module.LLM_GATEWAY_URL = (
            "https://exlerate-ai-proxy-dev.exlservice.com" if self.enabled else None
        )
        config_module.LLM_GATEWAY_VIRTUAL_KEY = "sk-test" if self.enabled else None

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401 - passthrough
        (
            config_module.LLM_USE_GATEWAY,
            config_module.LLM_GATEWAY_URL,
            config_module.LLM_GATEWAY_VIRTUAL_KEY,
        ) = self._saved


def _mapping() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Compact, deterministic mapping used by candidate-resolution tests."""
    chat = {
        "claude-haiku-4-5": {
            "provider": "azure_ai",
            "model": "claude-haiku-4-5",
            "gateway_model_id": "anthropic.claude-haiku-4-5-v1:0.bedrock",
            "tags": ["fast", "cheap", "coding"],
        },
        "claude-opus-4-6": {
            "provider": "bedrock",
            "model": "bedrock/converse/us.anthropic.claude-opus-4-6-v1",
            "gateway_model_id": "anthropic.claude-opus-4-6-v1:0.bedrock",
            "tags": ["coding"],
        },
        "gpt-4.1-mini": {
            "provider": "azure",
            "model": "gpt-4.1-mini",
            "gateway_model_id": "openai.gpt-4-1-mini.azure.eastus",
            "tags": ["fast", "cheap", "coding"],
        },
        "gpt-5-nano": {  # no gateway id on purpose
            "provider": "azure/gpt5_series",
            "model": "gpt-5-nano",
            "tags": ["fast", "cheap"],
        },
        "mistral.devstral": {
            "provider": "bedrock",
            "model": "bedrock/converse/mistral.devstral-2-123b",
            "gateway_model_id": "mistral.devstral-2-123b.bedrock.us-east-1",
            "tags": ["coding"],
        },
    }
    kg = {
        "claude-haiku-4-5": chat["claude-haiku-4-5"],
        "gpt-4.1-mini": chat["gpt-4.1-mini"],
    }
    return {"chat": chat, "knowledge_graph": kg, "embedding": {}}


class TestPolicyRegistry(unittest.TestCase):
    def test_every_page_policy_declares_fast_tag(self) -> None:
        for name, policy in POLICIES.items():
            self.assertIn("fast", policy.required_tags, f"policy '{name}' missing fast tag")

    def test_objective_and_guardrail_defaults(self) -> None:
        self.assertEqual(POLICIES["objectives_classification"].default_model, "claude-haiku-4-5")
        self.assertEqual(POLICIES["guardrail"].default_model, "claude-haiku-4-5")

    def test_data_treatment_and_fe_use_opus(self) -> None:
        self.assertEqual(POLICIES["data_treatment"].default_model, "claude-opus-4-6")
        self.assertEqual(POLICIES["feature_engineering"].default_model, "claude-opus-4-6")

    def test_knowledge_graph_requires_coding_tag(self) -> None:
        self.assertIn("coding", POLICIES["knowledge_graph"].required_tags)
        self.assertEqual(POLICIES["knowledge_graph"].usage_key, "knowledge_graph")

    def test_policy_for_unknown_falls_back_to_default_chat(self) -> None:
        self.assertIs(policy_for("not-a-real-context"), POLICIES["default_chat"])


class TestAgentContextMapping(unittest.TestCase):
    def test_known_agent_context_mapped(self) -> None:
        self.assertEqual(routing_context_for_agent("data_transformation"), "data_treatment")
        self.assertEqual(routing_context_for_agent("modelling"), "model_training")
        self.assertEqual(routing_context_for_agent("data_insight"), "data_insights")

    def test_unknown_or_missing_agent_context_degrades(self) -> None:
        self.assertEqual(routing_context_for_agent(None), "default_chat")
        self.assertEqual(routing_context_for_agent(""), "default_chat")
        self.assertEqual(routing_context_for_agent("unknown_agent"), "default_chat")

    def test_all_routing_targets_are_defined_policies(self) -> None:
        for target in AGENT_CONTEXT_TO_ROUTING.values():
            self.assertIn(target, POLICIES, f"agent routing target '{target}' missing policy")


class TestCandidatesFor(unittest.TestCase):
    def test_default_first_then_tag_matches_gateway_on(self) -> None:
        with _GatewayCtx(enabled=True), patch(
            "app.core.llm_routing._load_mapping", return_value=_mapping()
        ):
            ordered: List[str] = candidates_for("data_treatment")

        self.assertEqual(ordered[0], "claude-opus-4-6")
        # fast+coding fallbacks remain; gpt-5-nano (no gateway id) must be filtered.
        self.assertIn("claude-haiku-4-5", ordered)
        self.assertIn("gpt-4.1-mini", ordered)
        self.assertNotIn("gpt-5-nano", ordered)
        # opus declares only "coding" -> excluded from the pool but still pinned as default.
        # Ordering guarantee: default first, scored rest after.
        self.assertLess(ordered.index("claude-opus-4-6"), ordered.index("claude-haiku-4-5"))

    def test_gateway_off_keeps_non_gateway_entries(self) -> None:
        with _GatewayCtx(enabled=False), patch(
            "app.core.llm_routing._load_mapping", return_value=_mapping()
        ):
            ordered = candidates_for("objectives_classification")

        self.assertIn("gpt-5-nano", ordered, "non-gateway model should be eligible when gateway off")

    def test_empty_when_default_and_all_candidates_fail_tag(self) -> None:
        empty_mapping = {
            "chat": {
                "only-coding": {
                    "provider": "bedrock",
                    "model": "x",
                    "gateway_model_id": "g",
                    "tags": ["coding"],
                },
            },
            "knowledge_graph": {},
            "embedding": {},
        }
        with _GatewayCtx(enabled=True), patch(
            "app.core.llm_routing._load_mapping", return_value=empty_mapping
        ):
            ordered = candidates_for("data_insights")  # requires "fast"

        self.assertEqual(ordered, [])

    def test_knowledge_graph_uses_kg_section(self) -> None:
        with _GatewayCtx(enabled=True), patch(
            "app.core.llm_routing._load_mapping", return_value=_mapping()
        ):
            ordered = candidates_for("knowledge_graph")

        self.assertEqual(ordered[0], "claude-haiku-4-5")
        self.assertIn("gpt-4.1-mini", ordered)


if __name__ == "__main__":
    unittest.main()

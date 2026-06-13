"""Tests for the Exlerate AI Gateway routing in config.py / llm_registry."""

import unittest

import app.core.config as config_module
from app.core.config import LitellmUsageConfig
from app.core.llm_registry import list_all_models, list_models


class _GatewayCtx:
    """Context manager that flips the module-level gateway flags on/off."""

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

    def __exit__(self, exc_type, exc, tb) -> None:
        (
            config_module.LLM_USE_GATEWAY,
            config_module.LLM_GATEWAY_URL,
            config_module.LLM_GATEWAY_VIRTUAL_KEY,
        ) = self._saved


AZURE_MAPPING = {
    "provider": "azure_ai",
    "model": "claude-haiku-4-5",
    "api_base": "https://ri-deployment-commongroup.services.ai.azure.com/anthropic",
    "api_version": "2025-01-01-preview",
    "reasoning_effort": "1025",
    "gateway_model_id": (
        "anthropic.claude-haiku-4-5-20251001-v1:0.bedrock.us-cross-region"
    ),
}

BEDROCK_MAPPING_NO_GATEWAY = {
    "provider": "bedrock",
    "model": "bedrock/converse/us.amazon.nova-premier-v1:0",
}


class TestGatewayRewrite(unittest.TestCase):
    def test_non_gateway_mode_keeps_direct_provider_fields(self) -> None:
        with _GatewayCtx(enabled=False):
            cfg = LitellmUsageConfig.from_mapping(
                name="chat",
                usage_type="chat",
                model_id="claude-haiku-4-5",
                mapping=AZURE_MAPPING,
            )
            kwargs = cfg.build_request_kwargs()

        self.assertEqual(cfg.provider, "azure_ai")
        self.assertEqual(kwargs["model"], "claude-haiku-4-5")
        self.assertEqual(kwargs["custom_llm_provider"], "azure_ai")
        self.assertEqual(
            kwargs["api_base"],
            "https://ri-deployment-commongroup.services.ai.azure.com/anthropic",
        )
        self.assertEqual(kwargs["api_version"], "2025-01-01-preview")
        self.assertEqual(kwargs["reasoning_effort"], 1025)
        self.assertNotIn("gateway_model_id", kwargs)

    def test_gateway_mode_rewrites_to_openai_endpoint(self) -> None:
        with _GatewayCtx(enabled=True):
            cfg = LitellmUsageConfig.from_mapping(
                name="chat",
                usage_type="chat",
                model_id="claude-haiku-4-5",
                mapping=AZURE_MAPPING,
            )
            kwargs = cfg.build_request_kwargs()

        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(
            kwargs["model"],
            "openai/anthropic.claude-haiku-4-5-20251001-v1:0.bedrock.us-cross-region",
        )
        self.assertEqual(kwargs["custom_llm_provider"], "openai")
        self.assertEqual(
            kwargs["api_base"],
            "https://exlerate-ai-proxy-dev.exlservice.com/v1",
        )
        self.assertEqual(kwargs["api_key"], "sk-test")
        self.assertNotIn("api_version", kwargs)
        self.assertNotIn("aws_access_key_id", kwargs)
        self.assertNotIn("aws_secret_access_key", kwargs)
        self.assertNotIn("gateway_model_id", kwargs)
        self.assertEqual(kwargs["reasoning_effort"], 1025)

    def test_mapping_without_gateway_id_stays_direct_in_gateway_mode(self) -> None:
        with _GatewayCtx(enabled=True):
            cfg = LitellmUsageConfig.from_mapping(
                name="chat",
                usage_type="chat",
                model_id="nova-premier-no-gw",
                mapping=BEDROCK_MAPPING_NO_GATEWAY,
            )

        self.assertEqual(cfg.provider, "bedrock")
        self.assertTrue(cfg.model.startswith("bedrock/"))


class TestRegistryFilter(unittest.TestCase):
    def test_listing_hides_entries_without_gateway_id_when_gateway_on(self) -> None:
        with _GatewayCtx(enabled=False):
            chat_off = list_models("chat")
            emb_off = list_models("embedding")
        with _GatewayCtx(enabled=True):
            chat_on = list_models("chat")
            emb_on = list_models("embedding")
            all_on = list_all_models()

        self.assertIn("gpt-5-nano", chat_off, "fallback-only entry visible off")
        self.assertNotIn(
            "gpt-5-nano", chat_on, "fallback-only entry hidden on gateway"
        )
        self.assertIn("text-embedding-ada-002", emb_off)
        self.assertNotIn("text-embedding-ada-002", emb_on)
        self.assertEqual(
            set(all_on.keys()), {"chat", "knowledge_graph", "embedding"}
        )

    def test_all_gateway_entries_share_expected_ids(self) -> None:
        with _GatewayCtx(enabled=True):
            chat = list_models("chat")
        expected = {
            "claude-haiku-4-5":
                "anthropic.claude-haiku-4-5-20251001-v1:0.bedrock.us-cross-region",
            "gpt-4.1-mini": "openai.gpt-4-1-mini.azure.eastus",
            "nova-premier": "amazon.nova-premier-v1:0.bedrock.us-cross-region",
            "nvidia.nemotron-nano-3-30b":
                "nvidia.nemotron-nano-3-30b.bedrock.us-east-1",
        }
        for friendly, gw_id in expected.items():
            self.assertIn(friendly, chat)
            self.assertEqual(chat[friendly]["gateway_model_id"], gw_id)


if __name__ == "__main__":
    unittest.main()

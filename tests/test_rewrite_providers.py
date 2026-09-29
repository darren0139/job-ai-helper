from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ai_providers import (
    CONFIGURED_LLM_PROVIDER,
    GITHUB_COPILOT_PROVIDER,
    RewriteContract,
    create_rewrite_provider,
)
from ai_providers.configured_llm import ConfiguredLLMRewriteProvider
from ai_providers.copilot import GitHubCopilotRewriteProvider


def contract() -> RewriteContract:
    evidence = {
        "evidence_id": "evidence_4b991082bd31",
        "kind": "bullet",
        "source": "resume",
        "text": "Implemented an Android application using Kotlin and Jetpack Compose.",
        "support_label": "direct",
    }
    return RewriteContract(
        target_requirement_id="req_android",
        project_id="project_workout_buddy",
        bullet_index=0,
        current_bullet="Implemented frontend application features for users.",
        grounded_baseline=evidence["text"],
        target_requirement="Experience working with Android app development and Kotlin",
        evidence_id=evidence["evidence_id"],
        evidence_record=evidence,
        required_ceiling="direct",
    )


class RewriteProviderTests(unittest.TestCase):
    def test_configured_provider_uses_one_existing_ask_json_call(self):
        ask_json = Mock(return_value={
            "candidate_bullet": (
                "Implemented an Android application with Kotlin and Jetpack Compose."
            ),
            "evidence_ids": ["evidence_4b991082bd31"],
        })
        provider = ConfiguredLLMRewriteProvider(
            model="openai/gpt-5.6-luna",
            ask_json_fn=ask_json,
        )
        result = provider.polish(contract())

        self.assertEqual(CONFIGURED_LLM_PROVIDER, result.provider_id)
        self.assertEqual("openai/gpt-5.6-luna", result.model)
        self.assertEqual(1, result.call_count)
        ask_json.assert_called_once()
        request_text = ask_json.call_args.args[1]
        self.assertIn("evidence_4b991082bd31", request_text)
        self.assertNotIn("evidence_library", request_text)

    def test_copilot_provider_is_text_only_one_prompt_no_retry(self):
        calls = {
            "create_session": [],
            "prompts": [],
        }

        class FakeResponse:
            data = SimpleNamespace(
                content=(
                    '{"candidate_bullet": '
                    '"Implemented an Android application using Kotlin and Jetpack Compose.", '
                    '"evidence_ids": ["evidence_4b991082bd31"]}'
                )
            )

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def send_and_wait(self, prompt):
                calls["prompts"].append(prompt)
                return FakeResponse()

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def create_session(self, **kwargs):
                calls["create_session"].append(kwargs)
                return FakeSession()

        fake_module = SimpleNamespace(CopilotClient=FakeClient)
        with patch.dict(sys.modules, {"copilot": fake_module}):
            provider = GitHubCopilotRewriteProvider(model="auto")
            result = provider.polish(contract())

        self.assertEqual(GITHUB_COPILOT_PROVIDER, result.provider_id)
        self.assertEqual("auto", result.model)
        self.assertEqual(1, result.call_count)
        self.assertEqual(1, len(calls["create_session"]))
        self.assertEqual(
            {
                "model": "auto",
                "available_tools": [],
                "enable_session_store": False,
            },
            calls["create_session"][0],
        )
        self.assertEqual(1, len(calls["prompts"]))
        self.assertEqual(
            ["evidence_4b991082bd31"],
            result.evidence_ids,
        )

    def test_factory_never_silently_falls_back(self):
        ask_json = Mock()
        provider = create_rewrite_provider(
            CONFIGURED_LLM_PROVIDER,
            model="mock-model",
            ask_json_fn=ask_json,
        )
        self.assertIsInstance(provider, ConfiguredLLMRewriteProvider)

        provider = create_rewrite_provider(
            GITHUB_COPILOT_PROVIDER,
            model="ignored",
            ask_json_fn=ask_json,
        )
        self.assertIsInstance(provider, GitHubCopilotRewriteProvider)
        self.assertEqual("auto", provider.model)

        with self.assertRaises(ValueError):
            create_rewrite_provider(
                "unknown-provider",
                model="mock",
                ask_json_fn=ask_json,
            )


if __name__ == "__main__":
    unittest.main()

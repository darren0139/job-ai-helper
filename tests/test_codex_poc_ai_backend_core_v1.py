from __future__ import annotations

import json
import sys
import types
import unittest
from unittest.mock import patch

import llm
from experimental.ai_backend_core import (
    AI_BACKEND_API,
    AI_BACKEND_CODEX,
    get_active_ai_backend,
    resolve_ai_backend,
    set_runtime_ai_backend,
)
from experimental.codex_llm_backend import (
    CodexLLMBackendError,
    get_last_codex_call_metadata,
)


class AICoreBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        set_runtime_ai_backend("api", route="analysis")
        set_runtime_ai_backend("api", route="chat")

    def tearDown(self) -> None:
        set_runtime_ai_backend("api", route="analysis")
        set_runtime_ai_backend("api", route="chat")

    def _sdk_module(self, response: str) -> types.ModuleType:
        state: dict[str, object] = {}

        class FakeThread:
            def run(self, prompt: str, **kwargs):
                state["prompt"] = prompt
                state["run_kwargs"] = kwargs
                return types.SimpleNamespace(final_response=response)

        class FakeCodex:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def thread_start(self, **kwargs):
                state["thread_kwargs"] = kwargs
                return FakeThread()

        module = types.ModuleType("openai_codex")
        module.Codex = FakeCodex
        module.Sandbox = types.SimpleNamespace(read_only="read-only")
        module.state = state
        return module

    def test_backend_resolution_and_routes_are_independent(self) -> None:
        self.assertEqual(resolve_ai_backend(""), AI_BACKEND_API)
        self.assertEqual(
            resolve_ai_backend("Codex (Local / Experimental)"),
            AI_BACKEND_CODEX,
        )
        set_runtime_ai_backend("codex", route="analysis")
        self.assertEqual(get_active_ai_backend("analysis"), "codex")
        self.assertEqual(get_active_ai_backend("chat"), "api")

    def test_api_remains_default(self) -> None:
        fake_response = types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        content='{"source":"api"}'
                    ),
                    finish_reason="stop",
                )
            ],
            model="fake-api-model",
            usage=None,
            system_fingerprint=None,
            created=None,
        )
        with patch.object(
            llm,
            "_run_completion_with_retries",
            return_value=fake_response,
        ) as run_api:
            result = llm.ask_json(
                "Return JSON.",
                "Use the API path.",
            )
        self.assertEqual(result, {"source": "api"})
        run_api.assert_called_once()

    def test_explicit_codex_json_uses_llm_router_without_api(self) -> None:
        fake_sdk = self._sdk_module(
            json.dumps({"source": "codex"})
        )
        with (
            patch.dict(sys.modules, {"openai_codex": fake_sdk}),
            patch.object(
                llm,
                "_run_completion_with_retries",
                side_effect=AssertionError("API must not be called"),
            ),
        ):
            result = llm.ask_json(
                "Return a source field.",
                "Use Codex.",
                backend="codex",
                operation="backend-core-test",
            )
        self.assertEqual(result, {"source": "codex"})
        self.assertEqual(
            fake_sdk.state["thread_kwargs"]["sandbox"],
            "read-only",
        )
        self.assertTrue(fake_sdk.state["thread_kwargs"]["ephemeral"])
        self.assertIn(
            "codex-backend-core-test-",
            fake_sdk.state["thread_kwargs"]["cwd"],
        )
        metadata = get_last_codex_call_metadata()
        self.assertEqual(metadata["backend"], "codex")
        self.assertFalse(metadata["api_call"])

    def test_runtime_codex_selection_routes_text_without_api(self) -> None:
        fake_sdk = self._sdk_module("CODEX TEXT OK")
        set_runtime_ai_backend("codex", route="chat")
        with (
            patch.dict(sys.modules, {"openai_codex": fake_sdk}),
            patch.object(
                llm,
                "_run_completion_with_retries",
                side_effect=AssertionError("API must not be called"),
            ),
        ):
            result = llm.ask_text(
                "Answer briefly.",
                "Say CODEX TEXT OK.",
                route="chat",
                operation="chat-core-test",
            )
        self.assertEqual(result, "CODEX TEXT OK")

    def test_invalid_codex_json_has_no_api_fallback(self) -> None:
        fake_sdk = self._sdk_module("not json")
        with (
            patch.dict(sys.modules, {"openai_codex": fake_sdk}),
            patch.object(
                llm,
                "_run_completion_with_retries",
                side_effect=AssertionError("API fallback must not occur"),
            ),
        ):
            with self.assertRaisesRegex(
                CodexLLMBackendError,
                "invalid JSON",
            ):
                llm.ask_json(
                    "Return JSON.",
                    "Malformed test.",
                    backend="codex",
                )

    def test_codex_does_not_pollute_api_call_ledger(self) -> None:
        fake_sdk = self._sdk_module('{"ok": true}')
        llm.reset_call_ledger()
        with patch.dict(sys.modules, {"openai_codex": fake_sdk}):
            llm.ask_json(
                "Return JSON.",
                "Codex only.",
                backend="codex",
            )
        self.assertEqual(llm.get_call_ledger(), [])


if __name__ == "__main__":
    unittest.main()

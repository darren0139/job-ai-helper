from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tailoring.ollama_performance_settings import (
    apply_rephrase_runtime_settings,
    is_local_ollama_model,
    persist_ollama_server_settings_windows,
    read_positive_int_env,
)


class OllamaPerformanceSettingsTests(unittest.TestCase):
    def test_local_model_detection_excludes_ollama_cloud(self):
        self.assertTrue(is_local_ollama_model("ollama/qwen3:8b"))
        self.assertTrue(is_local_ollama_model("ollama/gemma4:26b"))
        self.assertFalse(
            is_local_ollama_model("ollama/minimax-m3:cloud")
        )
        self.assertFalse(
            is_local_ollama_model("gemini/gemini-3.6-flash")
        )

    def test_runtime_settings_apply_to_current_streamlit_process(self):
        with patch.dict(os.environ, {}, clear=False):
            values = apply_rephrase_runtime_settings(
                num_ctx=4096,
                batch_max_bullets=3,
                evidence_max_items=16,
                evidence_max_chars=4000,
            )

            self.assertEqual(
                os.environ["OLLAMA_REPHRASE_NUM_CTX"],
                "4096",
            )
            self.assertEqual(
                os.environ["OLLAMA_REPHRASE_BATCH_MAX_BULLETS"],
                "3",
            )
            self.assertEqual(
                values[
                    "OLLAMA_REPHRASE_PROMPT_EVIDENCE_MAX_CHARS"
                ],
                "4000",
            )

    def test_positive_int_env_falls_back_safely(self):
        with patch.dict(
            os.environ,
            {"TEST_OLLAMA_INT": "not-an-int"},
            clear=False,
        ):
            self.assertEqual(
                read_positive_int_env("TEST_OLLAMA_INT", 4096),
                4096,
            )

    @patch(
        "tailoring.ollama_performance_settings.platform.system",
        return_value="Windows",
    )
    @patch(
        "tailoring.ollama_performance_settings.subprocess.run",
    )
    def test_windows_server_settings_use_setx(
        self,
        run_mock,
        _system_mock,
    ):
        result = persist_ollama_server_settings_windows(
            flash_attention=True,
            kv_cache_type="q8_0",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(run_mock.call_count, 2)

        commands = [
            call.args[0]
            for call in run_mock.call_args_list
        ]
        self.assertIn(
            ["setx", "OLLAMA_FLASH_ATTENTION", "1"],
            commands,
        )
        self.assertIn(
            ["setx", "OLLAMA_KV_CACHE_TYPE", "q8_0"],
            commands,
        )

    @patch(
        "tailoring.ollama_performance_settings.platform.system",
        return_value="Windows",
    )
    def test_invalid_kv_cache_is_rejected(
        self,
        _system_mock,
    ):
        result = persist_ollama_server_settings_windows(
            flash_attention=True,
            kv_cache_type="invalid",
        )

        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()

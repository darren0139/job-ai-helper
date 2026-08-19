from __future__ import annotations

import unittest

from tailoring.phase9f_preview_state import (
    phase9f_preview_generation_candidates,
    resolve_phase9f_preview_generation,
)


class Phase9FPreviewStateTests(unittest.TestCase):
    def test_session_generation_wins_over_older_durable_fit(self):
        candidates = phase9f_preview_generation_candidates(
            session_generation_id="new-semantic",
            durable_generation_id="old-fitted",
        )
        self.assertEqual(
            candidates,
            [
                ("session", "new-semantic"),
                ("durable_execution", "old-fitted"),
            ],
        )

    def test_durable_generation_is_restart_fallback(self):
        candidates = phase9f_preview_generation_candidates(
            session_generation_id="",
            durable_generation_id="old-fitted",
        )
        self.assertEqual(
            candidates,
            [("durable_execution", "old-fitted")],
        )

    def test_missing_session_generation_falls_back_to_durable(self):
        generations = {
            "old-fitted": {
                "generation_id": "old-fitted",
                "docx_path": "old.docx",
            }
        }

        resolved = resolve_phase9f_preview_generation(
            session_generation_id="missing-new",
            durable_generation_id="old-fitted",
            generation_loader=generations.get,
        )

        self.assertEqual(resolved["source"], "durable_execution")
        self.assertEqual(resolved["generation_id"], "old-fitted")

    def test_available_semantic_generation_is_selected_before_durable_fit(self):
        generations = {
            "new-semantic": {
                "generation_id": "new-semantic",
                "docx_path": "",
                "fit_result": None,
            },
            "old-fitted": {
                "generation_id": "old-fitted",
                "docx_path": "old.docx",
                "fit_result": {"docx_path": "old.docx"},
            },
        }

        resolved = resolve_phase9f_preview_generation(
            session_generation_id="new-semantic",
            durable_generation_id="old-fitted",
            generation_loader=generations.get,
        )

        self.assertEqual(resolved["source"], "session")
        self.assertEqual(resolved["generation_id"], "new-semantic")
        self.assertFalse(bool(resolved["generation"].get("docx_path")))

    def test_duplicate_ids_are_not_loaded_twice(self):
        calls: list[str] = []

        def loader(generation_id: str):
            calls.append(generation_id)
            return {"generation_id": generation_id}

        resolved = resolve_phase9f_preview_generation(
            session_generation_id="same",
            durable_generation_id="same",
            generation_loader=loader,
        )

        self.assertEqual(resolved["generation_id"], "same")
        self.assertEqual(calls, ["same"])


if __name__ == "__main__":
    unittest.main()

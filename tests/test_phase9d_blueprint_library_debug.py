from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import tailoring_version_manager as base_manager
from tailoring.phase9d_blueprint_library_debug import (
    BLUEPRINT_LIBRARY_DEBUG_VERSION,
    blueprint_library_debug_json,
    build_blueprint_library_debug_payload,
)
from tests.phase9d_test_support import seed_phase9d_database


class Phase9DBlueprintLibraryDebugTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_path = base_manager.DB_PATH
        self.database_path = (
            Path(self.temporary.name) / "blueprint-library-debug.sqlite"
        )
        self.state = seed_phase9d_database(self.database_path)

    def tearDown(self) -> None:
        base_manager.DB_PATH = self.old_path
        self.temporary.cleanup()

    def test_debug_snapshot_contains_page_sources_and_tag_diagnostics(self):
        evaluation = self.state["provisional_evaluation"]
        payload = build_blueprint_library_debug_payload(
            current_application_id=None,
            page_state={
                "evaluation_id": evaluation["evaluation_id"],
                "confirmed_variant_tags": ["Backend", "AI"],
                "variant_intent": "create_new_variant",
                "existing_variant_id": "",
                "new_variant_label": "Backend / AI",
                "provisional_acknowledgement": False,
                "show_history": False,
                "inspect_blueprint_id": "",
            },
        )

        self.assertEqual(
            payload["debug_version"],
            BLUEPRINT_LIBRARY_DEBUG_VERSION,
        )
        self.assertTrue(payload["safety"]["read_only"])
        self.assertFalse(payload["safety"]["model_calls"])
        self.assertGreaterEqual(
            payload["counts"]["persisted_phase9c_evaluations"],
            1,
        )
        self.assertEqual(
            payload["selected_evaluation"]["evaluation_id"],
            evaluation["evaluation_id"],
        )
        self.assertIsNotNone(payload["selected_candidate"])
        tag_debug = payload["selected_variant_tag_debug"]
        self.assertIsNotNone(tag_debug)
        self.assertEqual(
            set(tag_debug["confirmed_tags"]),
            {"Backend", "AI"},
        )
        self.assertTrue(tag_debug["tag_scores"])
        text = blueprint_library_debug_json(payload)
        self.assertIn('"debug_version"', text)
        self.assertIn('"selected_variant_tag_debug"', text)

    def test_debug_exports_only_explicit_page_state(self):
        payload = build_blueprint_library_debug_payload(
            current_application_id=None,
            page_state={
                "evaluation_id": "",
                "confirmed_variant_tags": [],
            },
        )
        self.assertEqual(
            set(payload["page_state"]),
            {"evaluation_id", "confirmed_variant_tags"},
        )
        self.assertNotIn("api_key", payload["page_state"])


if __name__ == "__main__":
    unittest.main()

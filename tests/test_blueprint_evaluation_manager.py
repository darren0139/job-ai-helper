from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import tailoring_version_manager as base_manager
from database.blueprint_evaluation_manager import (
    get_blueprint_evaluation,
    save_or_reuse_blueprint_evaluation,
)
from tailoring.phase9c_blueprint_evaluation import evaluate_blueprint_candidate


FIXTURE = Path(__file__).resolve().parents[1] / "ci_fixtures" / (
    "phase9c_application94_acceptance.json"
)


class BlueprintEvaluationManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary.name) / "phase9c.sqlite"
        self.connection_patch = patch.object(
            base_manager,
            "_connect",
            side_effect=lambda: sqlite3.connect(database_path),
        )
        self.connection_patch.start()
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.evaluation = evaluate_blueprint_candidate(
            candidate=fixture["candidate"],
            selected_jds=fixture["saved_jds"][:2],
            saved_jds_for_source_resolution=fixture["saved_jds"],
        )

    def tearDown(self) -> None:
        self.connection_patch.stop()
        self.temporary.cleanup()

    def test_identical_evaluation_is_persisted_once_and_exactly_reused(self):
        first = save_or_reuse_blueprint_evaluation(self.evaluation)
        second = save_or_reuse_blueprint_evaluation(copy.deepcopy(self.evaluation))
        self.assertEqual(first["cache_status"], "miss")
        self.assertEqual(second["cache_status"], "hit")
        self.assertEqual(first["evaluation"], second["evaluation"])
        loaded = get_blueprint_evaluation(
            self.evaluation["evaluation_fingerprint"]
        )
        self.assertEqual(loaded, first["evaluation"])

    def test_complete_selected_scope_collision_fails_closed(self):
        save_or_reuse_blueprint_evaluation(self.evaluation)
        collision = copy.deepcopy(self.evaluation)
        collision["semantic_identity"]["selected_jd_scope"].append(
            {
                "jd_key": "different-excluded-selection",
                "selection_decision": "excluded",
                "selection_reason": "different_role_family",
            }
        )
        with self.assertRaisesRegex(RuntimeError, "complete selected scope"):
            save_or_reuse_blueprint_evaluation(collision)


if __name__ == "__main__":
    unittest.main()

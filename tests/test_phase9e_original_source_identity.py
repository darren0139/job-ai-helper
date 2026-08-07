from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import db_manager, jd_library_manager, tailoring_version_manager
from database.application_blueprint_manager import (
    evaluate_and_bind_application_blueprint,
    get_current_application_blueprint_decision,
)
from tailoring.phase9e_blueprint_selection import (
    PHASE9E_ORIGINAL_SOURCE_IDENTITY_POLICY_VERSION,
    build_original_resume_starting_snapshot,
)
from tests.phase9e_test_support import seed_phase9e_database


class Phase9EOriginalSourceIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_db = db_manager.DB_PATH
        self.old_jd = jd_library_manager.DB_PATH
        self.old_tailoring = tailoring_version_manager.DB_PATH
        self.database_path = (
            Path(self.temporary.name) / "phase9e-original-source.sqlite"
        )
        self.state = seed_phase9e_database(
            self.database_path,
            different_original=True,
        )

    def tearDown(self) -> None:
        db_manager.DB_PATH = self.old_db
        jd_library_manager.DB_PATH = self.old_jd
        tailoring_version_manager.DB_PATH = self.old_tailoring
        self.temporary.cleanup()

    def _load_report(self) -> dict:
        connection = sqlite3.connect(self.database_path)
        try:
            raw = connection.execute(
                "SELECT report_json FROM applications WHERE id = 94"
            ).fetchone()[0]
            return json.loads(raw)
        finally:
            connection.close()

    def _save_report(self, report: dict) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                "UPDATE applications SET report_json = ? WHERE id = 94",
                (json.dumps(report, ensure_ascii=False),),
            )
            connection.commit()
        finally:
            connection.close()

    def test_snapshot_ignores_mutable_application_bookkeeping(self) -> None:
        report = self._load_report()
        before = build_original_resume_starting_snapshot(report)

        changed = copy.deepcopy(report)
        changed.setdefault("meta", {})["api_usage"] = {
            "calls": 3,
            "estimated_total_cost_usd": 0.0715,
        }
        changed["cover_letter"] = "Generated later."
        changed["last_ui_notice"] = "Created a new Draft."

        after = build_original_resume_starting_snapshot(changed)

        self.assertEqual(
            before["starting_snapshot_fingerprint"],
            after["starting_snapshot_fingerprint"],
        )
        self.assertEqual(
            before["source_identity"]["policy_version"],
            PHASE9E_ORIGINAL_SOURCE_IDENTITY_POLICY_VERSION,
        )
        self.assertNotIn("application_report_snapshot", before)
        self.assertNotIn(
            "persisted_report_fingerprint",
            before["source_identity"],
        )

    def test_resume_content_change_still_changes_snapshot_identity(self) -> None:
        report = self._load_report()
        before = build_original_resume_starting_snapshot(report)

        changed = copy.deepcopy(report)
        changed["resume_profile"] = copy.deepcopy(report["resume_profile"])
        changed["resume_profile"]["phase9e_identity_probe"] = "changed"

        after = build_original_resume_starting_snapshot(changed)
        self.assertNotEqual(
            before["starting_snapshot_fingerprint"],
            after["starting_snapshot_fingerprint"],
        )

    def test_bound_original_source_survives_api_usage_update(self) -> None:
        bound = evaluate_and_bind_application_blueprint(
            application_id=94,
            scope_replacement_confirmed=True,
            selected_source="original_resume",
            selection_mode="original_resume",
            actor_label="Regression test",
        )
        self.assertEqual(
            bound["decision"]["selection"]["selected_source"],
            "original_resume",
        )
        current = get_current_application_blueprint_decision(94)
        self.assertEqual(current["current_scope_status"], "current")

        report = self._load_report()
        report.setdefault("meta", {})["api_usage"] = {
            "calls": [
                {
                    "action": "generate_projects",
                    "tokens": 42040,
                    "estimated_cost_usd": 0.0715,
                }
            ]
        }
        report["generated_cover_letter"] = "Bookkeeping-only output."
        self._save_report(report)

        current_after = get_current_application_blueprint_decision(94)
        self.assertEqual(
            current_after["current_scope_status"],
            "current",
        )
        self.assertEqual(current_after["stale_reasons"], [])


if __name__ == "__main__":
    unittest.main()

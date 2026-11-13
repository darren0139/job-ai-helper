"""Focused, offline contracts for Phase 9F session handoff and fit-only controls."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from tailoring.phase9f_session_handoff import normal_fit_selection_lock_reason, confirmed_source_view
from tailoring.adaptive_project_selection_v3 import apply_adaptive_project_selection
from database.phase9f_tailoring_execution_manager import _canonical_fit_settings


class Phase9FSessionHandoffV1Tests(unittest.TestCase):
    def test_real_phase9f_d_confirmation_reuses_saved_source_and_ranking(self):
        import tempfile
        from pathlib import Path
        from database import db_manager, jd_library_manager, tailoring_version_manager
        from database.phase9f_application_confirmation_manager import confirm_phase9f_application_session
        from tests.phase9f_d_test_support import (
            configure_database, insert_base_resume, insert_blueprint, save_exact_jd, build_scope,
        )
        from tests.test_phase9f_starting_source_ranking import make_exact_jd
        old = (db_manager.DB_PATH, jd_library_manager.DB_PATH, tailoring_version_manager.DB_PATH)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "handoff.db"
                configure_database(path)
                insert_base_resume(path, strong=False)
                insert_blueprint(path, strong=True)
                exact = make_exact_jd()
                saved_jd = save_exact_jd(path)
                ranking, recommendation = build_scope(path, phase9f_a_snapshot=exact)
                winner = ranking["recommended_source"]
                result = confirm_phase9f_application_session(
                    phase9f_a_snapshot=exact,
                    persisted_exact_jd_snapshot=saved_jd,
                    ranking_result=ranking,
                    phase9f_c_recommendation=recommendation,
                    confirmed_normalized_source_fingerprint=winner["normalized_source_fingerprint"],
                    confirmed_intensity="full",
                    application_intent_id="handoff-v1-test",
                )
                view = confirmed_source_view(result["confirmation"])
                self.assertIsNotNone(view)
                self.assertTrue(view["analysis"]["canonical_requirements"])
                self.assertEqual(1, sum(row["Selected"] == "Yes" for row in view["comparison"]))
                self.assertEqual(len(ranking["ranked_candidates"]), len(view["comparison"]))
                from copy import deepcopy
                wrong = deepcopy(result["confirmation"])
                wrong["confirmation_snapshot"]["selected_candidate"]["normalized_source_fingerprint"] = "invalid"
                with self.assertRaises(ValueError):
                    confirmed_source_view(wrong)
        finally:
            db_manager.DB_PATH, jd_library_manager.DB_PATH, tailoring_version_manager.DB_PATH = old

    def test_no_confirmation_does_not_invent_document_receipt(self):
        self.assertIsNone(confirmed_source_view(None))
        self.assertIsNone(confirmed_source_view({"confirmation_snapshot": {}}))

    def test_incomplete_confirmation_fails_closed(self):
        with self.assertRaises(ValueError):
            confirmed_source_view({"confirmation_snapshot": {"phase9f_b_ranking_result": {"status": "ranked"}}})

    def test_normal_fit_controls_follow_execution_scope_not_d_initial_lock(self):
        policy = normal_fit_selection_lock_reason
        self.assertEqual("", policy(execution_active=True, normal_lifecycle=True,
            addressable=True, fit_frozen=False, workspace_edit_required=False,
            legacy_section_locked=True))
        self.assertIn("not addressable", policy(execution_active=True, normal_lifecycle=True,
            addressable=False, fit_frozen=False, workspace_edit_required=False,
            legacy_section_locked=False))
        self.assertIn("Historical private", policy(execution_active=True, normal_lifecycle=False,
            addressable=True, fit_frozen=False, workspace_edit_required=False,
            legacy_section_locked=False))
        self.assertIn("frozen", policy(execution_active=True, normal_lifecycle=True,
            addressable=True, fit_frozen=True, workspace_edit_required=False,
            legacy_section_locked=False))
        self.assertIn("legacy", policy(execution_active=False, normal_lifecycle=False,
            addressable=True, fit_frozen=False, workspace_edit_required=False,
            legacy_section_locked=True))

    def test_opt_in_project_setting_keeps_old_canonical_identity(self):
        old = _canonical_fit_settings({})
        self.assertNotIn("adaptive_projects_mode", old)
        self.assertNotIn("adaptive_project_keys", old)
        new = _canonical_fit_settings({"adaptive_projects_mode": "manual", "adaptive_project_keys": ["id:a"]})
        self.assertEqual("manual", new["adaptive_projects_mode"])
        self.assertEqual(["id:a"], new["adaptive_project_keys"])
        with self.assertRaises(ValueError):
            _canonical_fit_settings({"adaptive_projects_mode": "bad"})

    def test_project_filter_selects_only_existing_generated_bullets(self):
        saved = {"recommended_projects": [
            {"project_id": "a", "title": "A", "draft_bullets": ["Built A"]},
            {"project_id": "b", "title": "B", "draft_bullets": ["Built B"]},
        ]}
        result = apply_adaptive_project_selection(saved, mode="manual", selected_keys=["id:b"])
        self.assertEqual(["B"], [row["title"] for row in result["recommended_projects"]])
        self.assertEqual(2, len(saved["recommended_projects"]))
        with self.assertRaises(ValueError):
            apply_adaptive_project_selection(saved, mode="manual", selected_keys=["id:unrelated"])


if __name__ == "__main__":
    unittest.main()

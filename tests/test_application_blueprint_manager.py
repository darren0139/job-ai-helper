from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from database import db_manager, jd_library_manager, tailoring_version_manager
from database.application_blueprint_manager import (
    evaluate_and_bind_application_blueprint,
    get_current_application_blueprint_decision,
    init_application_blueprint_decisions,
    list_application_blueprint_binding_events,
    list_application_blueprint_decisions,
    preview_application_blueprint_decision,
    resolve_current_phase9e_generation_context,
    set_application_blueprint_workflow_action,
)
from database.tailoring_generation_control import (
    approve_tailoring_generation,
    find_cached_tailoring_generation,
    get_application_generation_control,
    record_generation_metadata,
)
from database.tailoring_verification_manager import (
    get_latest_tailoring_verification,
    save_tailoring_verification,
)
from database.tailoring_version_manager import (
    save_application_tailoring_generation,
)
from database.global_blueprint_manager import (
    remove_global_blueprint_from_reuse,
    update_global_blueprint_display_metadata,
)
from database.jd_library_manager import get_exact_job_description_for_application
from rag.jd_identity import build_job_identity
from tailoring.tailoring_generation_fingerprint import (
    build_tailoring_input_fingerprint,
)
from tailoring.phase9e_blueprint_selection import Phase9EDecisionError
from tests.phase9e_test_support import seed_phase9e_database


class ApplicationBlueprintManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_db = db_manager.DB_PATH
        self.old_jd = jd_library_manager.DB_PATH
        self.old_tailoring = tailoring_version_manager.DB_PATH
        self.database_path = Path(self.temporary.name) / "phase9e-manager.sqlite"
        self.state = seed_phase9e_database(
            self.database_path,
            different_original=True,
        )
        self.blueprint = self.state["blueprint"]

    def tearDown(self) -> None:
        db_manager.DB_PATH = self.old_db
        jd_library_manager.DB_PATH = self.old_jd
        tailoring_version_manager.DB_PATH = self.old_tailoring
        self.temporary.cleanup()

    def bind_blueprint(self):
        return evaluate_and_bind_application_blueprint(
            application_id=94,
            scope_replacement_confirmed=True,
            selected_source="global_blueprint",
            selected_blueprint_id=self.blueprint["blueprint_id"],
            selection_mode="recommended",
            actor_label="Test user",
        )

    def source_rows(self):
        connection = sqlite3.connect(self.database_path)
        try:
            return {
                "application": connection.execute(
                    "SELECT report_json FROM applications WHERE id = 94"
                ).fetchone()[0],
                "jd": connection.execute(
                    """
                    SELECT raw_text, jd_profile_json, source_version_id
                    FROM job_descriptions ORDER BY id
                    """
                ).fetchall(),
                "blueprint": connection.execute(
                    """
                    SELECT blueprint_snapshot_json, blueprint_fingerprint
                    FROM global_blueprint_versions ORDER BY blueprint_id
                    """
                ).fetchall(),
            }
        finally:
            connection.close()

    def test_schema_is_additive_and_idempotent(self):
        init_application_blueprint_decisions()
        init_application_blueprint_decisions()
        connection = sqlite3.connect(self.database_path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        finally:
            connection.close()
        self.assertIn("application_blueprint_decisions", tables)
        self.assertIn("application_blueprint_binding_state", tables)
        self.assertIn("application_blueprint_binding_events", tables)
        self.assertIn("application_blueprint_workflow_state", tables)
        self.assertIn("application_blueprint_scope_activation_state", tables)
        self.assertIn("application_blueprint_legacy_sessions", tables)
        self.assertIn("application_blueprint_compatibility_migrations", tables)

    def test_sessions_created_after_compatibility_migration_require_phase9e(self):
        init_application_blueprint_decisions()
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                """
                INSERT INTO applications (
                    id, session_name, resume_filename, job_title, company, degree,
                    overall_score, summary, report_json, cover_letter,
                    created_at, updated_at
                )
                SELECT
                    95, 'New Phase 9E Session', resume_filename, job_title,
                    company, degree, overall_score, summary, report_json,
                    cover_letter, created_at, updated_at
                FROM applications WHERE id = 94
                """
            )
            connection.commit()
        finally:
            connection.close()
        context = resolve_current_phase9e_generation_context(95)
        self.assertEqual(context["status"], "unbound")
        self.assertFalse(context["can_generate"])
        self.assertTrue(context["phase9e_enforced"])

    def test_preview_and_open_leave_legacy_scope_unbound(self):
        init_application_blueprint_decisions()
        preview = preview_application_blueprint_decision(
            application_id=94,
            selected_source="global_blueprint",
            selected_blueprint_id=self.blueprint["blueprint_id"],
            selection_mode="recommended",
        )
        self.assertEqual(preview["application_id"], 94)
        context = resolve_current_phase9e_generation_context(94)
        self.assertTrue(context["can_generate"])
        self.assertFalse(context["phase9e_enforced"])
        self.assertEqual(context["status"], "legacy")
        connection = sqlite3.connect(self.database_path)
        try:
            counts = [
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "application_blueprint_decisions",
                    "application_blueprint_binding_state",
                    "application_blueprint_scope_activation_state",
                    "application_blueprint_binding_events",
                )
            ]
        finally:
            connection.close()
        self.assertEqual(counts, [0, 0, 0, 0])

    def test_scope_replacement_requires_explicit_confirmation(self):
        init_application_blueprint_decisions()
        with self.assertRaisesRegex(
            ValueError, "requires explicit confirmation"
        ):
            evaluate_and_bind_application_blueprint(
                application_id=94,
                scope_replacement_confirmed=False,
                selected_source="global_blueprint",
                selected_blueprint_id=self.blueprint["blueprint_id"],
                selection_mode="recommended",
            )
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM application_blueprint_decisions"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM application_blueprint_scope_activation_state"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_precompatibility_binding_is_inspectable_but_legacy_stays_current(self):
        bound = self.bind_blueprint()["decision"]
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                "DELETE FROM application_blueprint_scope_activation_state WHERE application_id = 94"
            )
            connection.commit()
        finally:
            connection.close()

        current = get_current_application_blueprint_decision(94)
        self.assertEqual(current["scope_activation_status"], "pending_confirmation")
        history = list_application_blueprint_decisions(94)
        self.assertEqual(history[0]["binding_status"], "pending_confirmation")
        context = resolve_current_phase9e_generation_context(94)
        self.assertEqual(context["status"], "legacy")
        self.assertFalse(context["phase9e_enforced"])
        self.assertEqual(
            context["effective_report"]["resume_profile"]["projects"],
            self.state["original_profile"]["projects"],
        )

        rebound = self.bind_blueprint()
        self.assertEqual(rebound["cache_status"], "hit_current")
        self.assertEqual(rebound["decision"]["decision_id"], bound["decision_id"])
        active = get_current_application_blueprint_decision(94)
        self.assertEqual(active["scope_activation_status"], "active")
        event = rebound["audit_event"]
        self.assertTrue(event["event_details"]["scope_replacement_confirmed"])
        self.assertEqual(
            event["event_details"]["prior_approved_generation_disposition"],
            "historical_and_inspectable",
        )

    def test_legacy_approval_verification_and_candidate_rows_remain_accessible(self):
        generation_id = "legacy-approved-generation"
        docx_path = Path(self.temporary.name) / "legacy-fitted.docx"
        docx_path.write_bytes(b"legacy fitted fixture")
        save_application_tailoring_generation(
            application_id=94,
            generation_id=generation_id,
            projects={"recommended_projects": [{"title": "Legacy project"}]},
            skills={"skill_lines": ["Legacy skill"]},
            fit_result={"fit_one_page": True, "docx_path": str(docx_path)},
            docx_path=docx_path,
        )
        record_generation_metadata(
            application_id=94,
            generation_id=generation_id,
            input_fingerprint="legacy-input",
            generation_kind="projects_skills",
        )
        approve_tailoring_generation(94, generation_id)
        save_tailoring_verification(
            application_id=94,
            generation_id=generation_id,
            result={
                "verification_fingerprint": "legacy-verification",
                "phase8_version": "phase8-test-fixture",
                "verification_mode": "zero_cost_deterministic",
                "fits_one_page": True,
            },
        )
        connection = sqlite3.connect(self.database_path)
        try:
            before_generation = connection.execute(
                "SELECT * FROM application_tailoring_generation_meta WHERE application_id = 94"
            ).fetchall()
            before_verification = connection.execute(
                "SELECT * FROM application_tailoring_verifications WHERE application_id = 94"
            ).fetchall()
            before_candidates = connection.execute(
                "SELECT * FROM global_blueprint_candidates WHERE source_application_id = 94"
            ).fetchall()
        finally:
            connection.close()

        preview_application_blueprint_decision(
            application_id=94,
            selected_source="original_resume",
            selection_mode="original_resume",
        )
        context = resolve_current_phase9e_generation_context(94)
        control = get_application_generation_control(94)
        verification = get_latest_tailoring_verification(94, generation_id)
        self.assertEqual(context["status"], "legacy")
        self.assertEqual(control["approved_generation_id"], generation_id)
        self.assertEqual(control["approved_generation"]["status"], "approved")
        self.assertEqual(verification["verification_fingerprint"], "legacy-verification")
        self.assertTrue(docx_path.exists())

        connection = sqlite3.connect(self.database_path)
        try:
            after_generation = connection.execute(
                "SELECT * FROM application_tailoring_generation_meta WHERE application_id = 94"
            ).fetchall()
            after_verification = connection.execute(
                "SELECT * FROM application_tailoring_verifications WHERE application_id = 94"
            ).fetchall()
            after_candidates = connection.execute(
                "SELECT * FROM global_blueprint_candidates WHERE source_application_id = 94"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(after_generation, before_generation)
        self.assertEqual(after_verification, before_verification)
        self.assertEqual(after_candidates, before_candidates)

    def test_exact_binding_is_persisted_once_and_reused(self):
        before = self.source_rows()
        first = self.bind_blueprint()
        second = self.bind_blueprint()
        self.assertEqual(first["cache_status"], "miss")
        self.assertEqual(second["cache_status"], "hit_current")
        self.assertEqual(
            first["decision"]["decision_id"],
            second["decision"]["decision_id"],
        )
        self.assertEqual(len(list_application_blueprint_decisions(94)), 1)
        events = list_application_blueprint_binding_events(94)
        self.assertEqual(len(events), 2)
        self.assertEqual(
            {event["event_type"] for event in events},
            {"decision_bound", "decision_reused"},
        )
        self.assertEqual(before, self.source_rows())

    def test_switching_sources_preserves_immutable_history(self):
        original = evaluate_and_bind_application_blueprint(
            application_id=94,
            scope_replacement_confirmed=True,
            selected_source="original_resume",
            selection_mode="original_resume",
        )["decision"]
        blueprint = self.bind_blueprint()["decision"]
        self.assertNotEqual(
            original["decision_fingerprint"], blueprint["decision_fingerprint"]
        )
        history = list_application_blueprint_decisions(94)
        self.assertEqual(len(history), 2)
        statuses = {row["decision_id"]: row["binding_status"] for row in history}
        self.assertEqual(statuses[blueprint["decision_id"]], "current")
        self.assertEqual(statuses[original["decision_id"]], "historical")

    def test_selected_blueprint_context_is_a_deep_copy(self):
        before_report = json.dumps(
            self.state["application_report"], sort_keys=True
        )
        decision = self.bind_blueprint()["decision"]
        context = resolve_current_phase9e_generation_context(94)
        self.assertTrue(context["can_generate"])
        self.assertEqual(context["status"], "current")
        expected = self.blueprint["blueprint_snapshot"][
            "frozen_resume_snapshot"
        ]["resume_profile_snapshot"]
        self.assertEqual(
            context["effective_report"]["resume_profile"]["projects"],
            expected["projects"],
        )
        context["effective_report"]["resume_profile"]["projects"].clear()
        reloaded = resolve_current_phase9e_generation_context(94)
        self.assertEqual(
            reloaded["effective_report"]["resume_profile"]["projects"],
            expected["projects"],
        )
        application = db_manager.get_application_by_id(94)
        self.assertEqual(
            json.dumps(application["report"], sort_keys=True), before_report
        )
        self.assertEqual(
            decision["starting_snapshot"]["source_type"], "global_blueprint"
        )

    def test_superseded_selected_blueprint_makes_decision_stale_and_blocks(self):
        decision = self.bind_blueprint()["decision"]
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                "UPDATE global_blueprint_versions SET status = 'superseded' WHERE blueprint_id = ?",
                (self.blueprint["blueprint_id"],),
            )
            connection.commit()
        finally:
            connection.close()
        current = get_current_application_blueprint_decision(94)
        self.assertEqual(current["decision_id"], decision["decision_id"])
        self.assertEqual(current["current_scope_status"], "stale")
        context = resolve_current_phase9e_generation_context(94)
        self.assertFalse(context["can_generate"])
        self.assertEqual(context["status"], "stale")

    def test_removed_blueprint_is_blocked_for_new_selection_but_existing_binding_resolves(self):
        before_sources = self.source_rows()
        bound = self.bind_blueprint()["decision"]
        removed = remove_global_blueprint_from_reuse(
            blueprint_id=self.blueprint["blueprint_id"],
            blueprint_fingerprint=self.blueprint["blueprint_fingerprint"],
            acknowledged=True,
            actor_label="Application 94 lifecycle test",
        )["blueprint"]
        self.assertEqual(removed["availability_status"], "removed")

        current = get_current_application_blueprint_decision(94)
        self.assertEqual(current["decision_id"], bound["decision_id"])
        self.assertEqual(
            current["decision_fingerprint"], bound["decision_fingerprint"]
        )
        self.assertEqual(current["current_scope_status"], "current")
        self.assertEqual(current["scope_activation_status"], "active")
        with self.assertRaisesRegex(Phase9EDecisionError, "not active"):
            preview_application_blueprint_decision(
                application_id=94,
                selected_source="global_blueprint",
                selected_blueprint_id=self.blueprint["blueprint_id"],
                selection_mode="recommended",
            )
        self.assertEqual(before_sources, self.source_rows())

    def test_changed_exact_jd_version_makes_decision_stale(self):
        self.bind_blueprint()
        current_jd = get_exact_job_description_for_application(94)
        revised_text = current_jd["raw_text"] + "\nMust support a new deployment gate."
        revised_identity = build_job_identity(
            company=current_jd["company"],
            title=current_jd["title"],
            location=current_jd["location"],
            raw_jd_text=revised_text,
        )
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                """
                INSERT INTO job_description_versions (
                    job_description_id, source_version_id, raw_text,
                    jd_profile_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    current_jd["library_jd_id"],
                    revised_identity.source_version_id,
                    revised_text,
                    json.dumps(current_jd["jd_profile"]),
                    "2026-08-05T00:00:00",
                ),
            )
            connection.execute(
                """
                UPDATE application_job_links SET source_version_id = ?
                WHERE application_id = 94
                """,
                (revised_identity.source_version_id,),
            )
            connection.commit()
        finally:
            connection.close()
        current = get_current_application_blueprint_decision(94)
        self.assertEqual(current["current_scope_status"], "stale")
        self.assertTrue(
            any("JD changed" in reason for reason in current["stale_reasons"])
        )

    def test_display_metadata_change_does_not_stale_current_decision(self):
        decision = self.bind_blueprint()["decision"]
        update_global_blueprint_display_metadata(
            blueprint_id=self.blueprint["blueprint_id"],
            display_name="Edited display metadata",
            notes="Identity must remain stable.",
            actor_label="Metadata test",
        )
        current = get_current_application_blueprint_decision(94)
        self.assertEqual(current["current_scope_status"], "current")
        self.assertEqual(current["decision_id"], decision["decision_id"])

    def test_scorer_version_change_is_fail_closed_as_stale(self):
        self.bind_blueprint()
        with patch(
            "tailoring.phase9e_blueprint_selection.SCORING_VERSION",
            "future-stable-scorer-version",
        ):
            current = get_current_application_blueprint_decision(94)
        self.assertEqual(current["current_scope_status"], "stale")

    def test_diagnostic_evidence_policy_change_does_not_stale_exact_source(self):
        decision = self.bind_blueprint()["decision"]
        with patch(
            "tailoring.phase9e_blueprint_selection."
            "PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION",
            "phase9e-diagnostic-policy-next",
        ):
            current = get_current_application_blueprint_decision(94)
        self.assertEqual(current["current_scope_status"], "current")
        self.assertEqual(current["decision_id"], decision["decision_id"])

    def test_older_evidence_and_decision_policies_become_stale(self):
        with patch(
            "tailoring.phase9e_blueprint_selection."
            "PHASE9E_IDENTITY_POLICY_VERSION",
            "phase9e-application-blueprint-identity-v1",
        ), patch(
            "database.application_blueprint_manager."
            "PHASE9E_IDENTITY_POLICY_VERSION",
            "phase9e-application-blueprint-identity-v1",
        ), patch(
            "tailoring.phase9e_blueprint_selection."
            "PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION",
            "phase9e-legacy-single-row-evidence-v0",
        ), patch(
            "tailoring.phase9e_blueprint_selection."
            "PHASE9E_DECISION_POLICY_VERSION",
            "phase9e-deterministic-tailoring-decision-v2",
        ), patch(
            "database.application_blueprint_manager."
            "PHASE9E_DECISION_POLICY_VERSION",
            "phase9e-deterministic-tailoring-decision-v2",
        ):
            historical = self.bind_blueprint()["decision"]

        current = get_current_application_blueprint_decision(94)
        self.assertEqual(current["decision_id"], historical["decision_id"])
        self.assertEqual(current["current_scope_status"], "stale")
        self.assertTrue(
            any(
                "decision policy or section-lock scope changed" in reason
                for reason in current["stale_reasons"]
            )
        )

    def _link_revised_same_family_jd(self) -> None:
        current_jd = get_exact_job_description_for_application(94)
        revised_text = current_jd["raw_text"] + "\nRevised target scope."
        revised_identity = build_job_identity(
            company=current_jd["company"],
            title=current_jd["title"],
            location=current_jd["location"],
            raw_jd_text=revised_text,
        )
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                """
                INSERT INTO job_description_versions (
                    job_description_id, source_version_id, raw_text,
                    jd_profile_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    current_jd["library_jd_id"],
                    revised_identity.source_version_id,
                    revised_text,
                    json.dumps(current_jd["jd_profile"]),
                    "2026-08-05T00:00:00",
                ),
            )
            connection.execute(
                """
                UPDATE application_job_links SET source_version_id = ?
                WHERE application_id = 94
                """,
                (revised_identity.source_version_id,),
            )
            connection.commit()
        finally:
            connection.close()

    def _comparison_with_gap_count(self, count: int) -> dict:
        from database.application_blueprint_manager import (
            preview_application_blueprint_decision,
        )

        preview = preview_application_blueprint_decision(
            application_id=94,
            selected_source="global_blueprint",
            selected_blueprint_id=self.blueprint["blueprint_id"],
            selection_mode="recommended",
        )
        comparison = json.loads(json.dumps(preview["comparison"]))
        comparison["important_gap_count"] = count
        comparison["deal_breaker_gap_count"] = 0
        comparison["important_gaps"] = [
            {
                "requirement_id": f"req_gap_{index}",
                "text": f"Important gap {index}",
                "importance": "required",
            }
            for index in range(count)
        ]
        comparison["comparison_result_fingerprint"] = f"fixture-gaps-{count}"
        return comparison

    def test_optional_polish_can_stay_locked_or_be_explicitly_enabled(self):
        self._link_revised_same_family_jd()
        comparison = self._comparison_with_gap_count(0)
        with patch(
            "tailoring.phase9e_blueprint_selection.evaluate_starting_snapshot",
            return_value=comparison,
        ):
            decision = self.bind_blueprint()["decision"]
            self.assertEqual(decision["recommended_tailoring"], "optional_polish")
            unchanged = resolve_current_phase9e_generation_context(94)
            self.assertTrue(unchanged["can_generate"])
            self.assertTrue(
                unchanged["section_lock_scope"]["projects_locked"]
            )
            set_application_blueprint_workflow_action(
                application_id=94,
                workflow_action="apply_optional_polish",
                actor_label="Optional polish test",
            )
            polish = resolve_current_phase9e_generation_context(94)
            self.assertFalse(polish["section_lock_scope"]["projects_locked"])
            self.assertFalse(polish["section_lock_scope"]["skills_locked"])
            set_application_blueprint_workflow_action(
                application_id=94,
                workflow_action="use_blueprint_unchanged",
                actor_label="Optional unchanged test",
            )
            unchanged_again = resolve_current_phase9e_generation_context(94)
            self.assertTrue(
                unchanged_again["section_lock_scope"]["projects_locked"]
            )

    def test_targeted_retargeting_can_be_overridden_with_audit_reason(self):
        self._link_revised_same_family_jd()
        comparison = self._comparison_with_gap_count(1)
        with patch(
            "tailoring.phase9e_blueprint_selection.evaluate_starting_snapshot",
            return_value=comparison,
        ):
            decision = self.bind_blueprint()["decision"]
            self.assertEqual(
                decision["recommended_tailoring"], "targeted_retailor"
            )
            blocked = resolve_current_phase9e_generation_context(94)
            self.assertFalse(blocked["can_generate"])
            with self.assertRaisesRegex(
                ValueError, "requires acknowledgement"
            ):
                set_application_blueprint_workflow_action(
                    application_id=94,
                    workflow_action="use_blueprint_unchanged_override",
                )
            set_application_blueprint_workflow_action(
                application_id=94,
                workflow_action="use_blueprint_unchanged_override",
                acknowledgement=True,
                reason="I accept the documented gaps for this specific application.",
                actor_label="Targeted override test",
            )
            unchanged = resolve_current_phase9e_generation_context(94)
            self.assertTrue(unchanged["can_generate"])
            self.assertTrue(unchanged["section_lock_scope"]["projects_locked"])
            events = list_application_blueprint_binding_events(94)
            action_event = next(
                event
                for event in events
                if event["event_type"] == "workflow_action_selected"
            )
            self.assertTrue(
                action_event["event_details"]["acknowledgement"]
            )
            self.assertIn(
                "documented gaps", action_event["event_details"]["reason"]
            )

    def test_audit_failure_rolls_back_decision_pointer_and_row(self):
        with patch(
            "database.application_blueprint_manager._insert_binding_event",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                self.bind_blueprint()
        connection = sqlite3.connect(self.database_path)
        try:
            decision_count = connection.execute(
                "SELECT COUNT(*) FROM application_blueprint_decisions"
            ).fetchone()[0]
            state_count = connection.execute(
                "SELECT COUNT(*) FROM application_blueprint_binding_state"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(decision_count, 0)
        self.assertEqual(state_count, 0)

    def test_cache_entry_cannot_cross_starting_sources(self):
        original = evaluate_and_bind_application_blueprint(
            application_id=94,
            scope_replacement_confirmed=True,
            selected_source="original_resume",
            selection_mode="original_resume",
        )["decision"]
        original_context = resolve_current_phase9e_generation_context(94)
        original_fingerprint = build_tailoring_input_fingerprint(
            report=original_context["effective_report"],
            evidence_items=[],
            generation_settings={"max_projects": 3},
            generation_kind="projects_skills",
            model_id="test-model",
            phase9e_binding=original_context["binding_identity"],
        )
        generation_id = uuid.uuid4().hex
        save_application_tailoring_generation(
            application_id=94,
            generation_id=generation_id,
            projects={"recommended_projects": []},
            skills={"skill_lines": []},
            generation_settings={"phase9e": original["decision_id"]},
        )
        record_generation_metadata(
            application_id=94,
            generation_id=generation_id,
            input_fingerprint=original_fingerprint,
            generation_kind="projects_skills",
        )
        self.assertIsNotNone(
            find_cached_tailoring_generation(
                application_id=94,
                input_fingerprint=original_fingerprint,
                generation_kind="projects_skills",
            )
        )

        self.bind_blueprint()
        blueprint_context = resolve_current_phase9e_generation_context(94)
        blueprint_fingerprint = build_tailoring_input_fingerprint(
            report=blueprint_context["effective_report"],
            evidence_items=[],
            generation_settings={"max_projects": 3},
            generation_kind="projects_skills",
            model_id="test-model",
            phase9e_binding=blueprint_context["binding_identity"],
        )
        self.assertNotEqual(original_fingerprint, blueprint_fingerprint)
        self.assertIsNone(
            find_cached_tailoring_generation(
                application_id=94,
                input_fingerprint=blueprint_fingerprint,
                generation_kind="projects_skills",
            )
        )


if __name__ == "__main__":
    unittest.main()

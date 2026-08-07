from __future__ import annotations

import os
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
import streamlit.dataframe_util as dataframe_util

from database import db_manager, jd_library_manager, tailoring_version_manager
from database.application_blueprint_manager import (
    get_current_application_blueprint_decision,
    list_application_blueprint_decisions,
    list_application_blueprint_binding_events,
    preview_application_blueprint_decision,
    resolve_current_phase9e_generation_context,
)
from database.application_resume_result_manager import (
    list_application_resume_results,
)
from database.application_cover_letter_manager import (
    list_application_cover_letters,
)
from database.tailoring_generation_control import list_tailoring_generations
from database.jd_library_manager import get_exact_job_description_for_application
from rag.jd_identity import build_job_identity
from tests.phase9e_test_support import seed_phase9e_database


HARNESS = Path(__file__).with_name("phase9e_streamlit_harness.py")
RESULT_HARNESS = Path(__file__).with_name(
    "phase9e_application_result_streamlit_harness.py"
)
PAGES_HARNESS = Path(__file__).with_name(
    "generation_cleanup_pages_streamlit_harness.py"
)


def _by_key(elements, key):
    return next(element for element in elements if element.key == key)


def _visible_markdown_occurrences(app: AppTest, expected: str) -> int:
    """Count a complete workflow label rendered through st.write/markdown."""
    return sum(
        str(element.value).count(expected)
        for element in app.markdown
    )


class Phase9EStreamlitAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_db = db_manager.DB_PATH
        self.old_jd = jd_library_manager.DB_PATH
        self.old_tailoring = tailoring_version_manager.DB_PATH
        self.old_environment = os.environ.get("PHASE9E_TEST_DATABASE")
        self.database_path = Path(self.temporary.name) / "phase9e-app.sqlite"
        self.state = seed_phase9e_database(
            self.database_path,
            different_original=True,
        )
        os.environ["PHASE9E_TEST_DATABASE"] = str(self.database_path)

    def tearDown(self) -> None:
        db_manager.DB_PATH = self.old_db
        jd_library_manager.DB_PATH = self.old_jd
        tailoring_version_manager.DB_PATH = self.old_tailoring
        if self.old_environment is None:
            os.environ.pop("PHASE9E_TEST_DATABASE", None)
        else:
            os.environ["PHASE9E_TEST_DATABASE"] = self.old_environment
        self.temporary.cleanup()

    def link_revised_same_family_jd(self) -> None:
        current = get_exact_job_description_for_application(94)
        raw_text = current["raw_text"] + "\nRevised target scope."
        identity = build_job_identity(
            company=current["company"],
            title=current["title"],
            location=current["location"],
            raw_jd_text=raw_text,
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
                    current["library_jd_id"],
                    identity.source_version_id,
                    raw_text,
                    json.dumps(current["jd_profile"]),
                    "2026-08-05T00:00:00",
                ),
            )
            connection.execute(
                """
                UPDATE application_job_links SET source_version_id = ?
                WHERE application_id = 94
                """,
                (identity.source_version_id,),
            )
            connection.commit()
        finally:
            connection.close()

    def comparison_with_gaps(self, count: int) -> dict:
        preview = preview_application_blueprint_decision(
            application_id=94,
            selected_source="global_blueprint",
            selected_blueprint_id=self.state["blueprint"]["blueprint_id"],
            selection_mode="recommended",
        )
        comparison = json.loads(json.dumps(preview["comparison"]))
        comparison["important_gap_count"] = count
        comparison["deal_breaker_gap_count"] = 0
        comparison["important_gaps"] = [
            {
                "requirement_id": f"req_ui_gap_{index}",
                "text": f"UI gap {index}",
                "importance": "required",
            }
            for index in range(count)
        ]
        comparison["comparison_result_fingerprint"] = f"ui-gaps-{count}"
        return comparison

    def confirm_and_bind(self, app):
        _by_key(
            app.checkbox, "phase9e_scope_replacement_ack_94"
        ).set_value(True).run()
        _by_key(app.button, "phase9e_bind_94").click().run()
        return AppTest.from_file(str(HARNESS), default_timeout=60).run()

    def test_recommendation_is_explicit_and_binding_enables_context(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any(
                "same-family blueprint is recommended" in item.value
                for item in app.success
            )
        )
        self.assertTrue(
            any("provisional" in str(metric.value).lower() for metric in app.metric)
        )
        self.assertTrue(
            any("GENERATION_CONTEXT=legacy" in item.value for item in app.markdown)
        )
        bind = _by_key(app.button, "phase9e_bind_94")
        self.assertTrue(bind.disabled)
        app = self.confirm_and_bind(app)
        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any("GENERATION_CONTEXT=current" in item.value for item in app.markdown)
        )
        self.assertEqual(
            _visible_markdown_occurrences(
                app, "Reuse approved blueprint"
            ),
            1,
        )
        self.assertFalse(
            any(metric.label == "Decision" for metric in app.metric)
        )
        self.assertIsNotNone(
            _by_key(app.button, "phase9e_reuse_unchanged_94")
        )
        current = get_current_application_blueprint_decision(94)
        self.assertEqual(current["current_scope_status"], "current")
        self.assertEqual(
            current["selection"]["selected_blueprint"]["blueprint_id"],
            self.state["blueprint"]["blueprint_id"],
        )
        self.assertEqual(
            current["recommended_tailoring"], "reuse_approved_source"
        )

    def test_restart_preserves_active_binding_without_pending_replacement_ui(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
        app = self.confirm_and_bind(app)
        decision_ids = [
            row["decision_id"]
            for row in list_application_blueprint_decisions(94)
        ]

        restarted = AppTest.from_file(
            str(HARNESS), default_timeout=60
        ).run()

        self.assertEqual(list(restarted.exception), [])
        self.assertTrue(
            any(
                "current immutable Phase 9E starting snapshot" in item.value
                for item in restarted.success
            )
        )
        self.assertTrue(
            any("Active starting source" in item.value for item in restarted.markdown)
        )
        self.assertTrue(
            any("Current workflow state" in item.value for item in restarted.caption)
        )
        self.assertFalse(
            any("selection is not persisted" in item.value.lower() for item in restarted.success)
        )
        self.assertFalse(
            any(
                checkbox.key == "phase9e_scope_replacement_ack_94"
                for checkbox in restarted.checkbox
            )
        )
        self.assertFalse(
            any(button.key == "phase9e_bind_94" for button in restarted.button)
        )
        self.assertIsNotNone(
            _by_key(restarted.button, "phase9e_change_source_94")
        )
        self.assertEqual(
            _visible_markdown_occurrences(
                restarted, "Reuse approved blueprint"
            ),
            1,
        )
        self.assertFalse(
            any(
                metric.label == "Decision"
                for metric in restarted.metric
            )
        )
        self.assertEqual(
            [
                row["decision_id"]
                for row in list_application_blueprint_decisions(94)
            ],
            decision_ids,
        )

    def test_exact_source_reuse_renders_one_immutable_result_after_restart(self):
        initial = AppTest.from_file(str(RESULT_HARNESS), default_timeout=60).run()
        self.confirm_and_bind(initial)
        app = AppTest.from_file(str(RESULT_HARNESS), default_timeout=60).run()
        before_generation_ids = {
            row["generation_id"] for row in list_tailoring_generations(94)
        }
        _by_key(app.button, "phase9e_reuse_unchanged_94").click().run()

        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any(
                "Reused the approved Global Blueprint" in item.value
                for item in app.success
            )
        )
        self.assertEqual(len(list_application_resume_results(94)), 1)
        self.assertEqual(
            {row["generation_id"] for row in list_tailoring_generations(94)},
            before_generation_ids,
        )
        self.assertFalse(
            any(button.label == "Approve Selected" for button in app.button)
        )
        self.assertFalse(any("Fit" in button.label for button in app.button))
        self.assertIsNotNone(
            _by_key(app.button, "phase9e_create_editable_copy_94")
        )
        download_buttons = list(app.get("download_button"))
        self.assertTrue(
            any(
                button.label == "Download résumé DOCX"
                for button in download_buttons
            )
        )
        self.assertTrue(
            any(
                button.label == "Download Application Result Debug Bundle"
                for button in download_buttons
            )
        )
        cover_button = _by_key(
            app.button, "phase9e_result_cover_letter_generate_94"
        )
        cover_button.click().run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(len(list_application_cover_letters(94)), 1)
        self.assertTrue(
            any(
                button.label == "Download cover letter (.txt)"
                for button in app.get("download_button")
            )
        )

        restarted = AppTest.from_file(
            str(RESULT_HARNESS), default_timeout=60
        ).run()
        self.assertEqual(list(restarted.exception), [])
        self.assertEqual(len(list_application_resume_results(94)), 1)
        self.assertTrue(
            any(
                "Reused the approved Global Blueprint" in item.value
                for item in restarted.success
            )
        )
        _by_key(
            restarted.button, "phase9e_result_cover_letter_generate_94"
        ).click().run()
        self.assertEqual(len(list_application_cover_letters(94)), 1)

    def test_change_source_mode_requires_a_genuinely_different_preview(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
        app = self.confirm_and_bind(app)
        restarted = AppTest.from_file(
            str(HARNESS), default_timeout=60
        ).run()

        _by_key(restarted.button, "phase9e_change_source_94").click().run()
        self.assertEqual(list(restarted.exception), [])
        self.assertIsNotNone(
            _by_key(restarted.button, "phase9e_cancel_change_source_94")
        )
        self.assertTrue(
            any("already-active immutable starting source" in item.value for item in restarted.info)
        )
        self.assertFalse(
            any(
                checkbox.key == "phase9e_scope_replacement_ack_94"
                for checkbox in restarted.checkbox
            )
        )
        self.assertFalse(
            any(button.key == "phase9e_bind_94" for button in restarted.button)
        )
        self.assertEqual(
            _visible_markdown_occurrences(
                restarted, "Reuse approved blueprint"
            ),
            1,
        )
        self.assertFalse(
            any(
                metric.label == "Decision"
                for metric in restarted.metric
            )
        )

        _by_key(restarted.radio, "phase9e_selection_94").set_value(
            "original_resume"
        ).run()
        replacement = _by_key(
            restarted.checkbox, "phase9e_scope_replacement_ack_94"
        )
        self.assertFalse(replacement.value)
        self.assertTrue(_by_key(restarted.button, "phase9e_bind_94").disabled)
        self.assertEqual(
            len(list_application_blueprint_decisions(94)),
            1,
        )

    def test_stale_binding_remains_visible_and_blocks_generation(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
        app = self.confirm_and_bind(app)
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                "UPDATE global_blueprint_versions SET status = 'superseded'"
            )
            connection.commit()
        finally:
            connection.close()
        app.run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any("historical/stale" in item.value for item in app.error)
        )
        self.assertTrue(
            any("GENERATION_CONTEXT=stale" in item.value for item in app.markdown)
        )

    def test_original_resume_preview_labels_profile_only_fidelity(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
        selection = _by_key(app.radio, "phase9e_selection_94")
        selection.set_value("original_resume").run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any("not the original uploaded raw text" in item.value for item in app.info)
        )

    def test_original_resume_activation_has_no_unsuitable_blueprint_action(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
        _by_key(app.radio, "phase9e_selection_94").set_value(
            "original_resume"
        ).run()
        app = self.confirm_and_bind(app)
        self.assertEqual(list(app.exception), [])
        self.assertFalse(
            any("selected blueprint is unsuitable" in item.value for item in app.warning)
        )
        self.assertFalse(
            any(
                button.key == "phase9e_regenerate_original_94"
                for button in app.button
            )
        )
        self.assertTrue(
            any("Generate Projects + Skills below" in item.value for item in app.info)
        )
        context = resolve_current_phase9e_generation_context(94)
        self.assertTrue(context["can_generate"])
        self.assertTrue(context["phase9e_enforced"])
        self.assertEqual(
            context["decision"]["selection"]["selected_source"],
            "original_resume",
        )

    def test_optional_polish_actions_are_both_available_in_streamlit(self):
        self.link_revised_same_family_jd()
        comparison = self.comparison_with_gaps(0)
        with patch(
            "tailoring.phase9e_blueprint_selection.evaluate_starting_snapshot",
            return_value=comparison,
        ):
            app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
            app = self.confirm_and_bind(app)
            self.assertEqual(list(app.exception), [])
            self.assertIsNotNone(
                _by_key(app.button, "phase9e_use_unchanged_94")
            )
            _by_key(app.button, "phase9e_optional_polish_94").click().run()
            context = resolve_current_phase9e_generation_context(94)
            editable_drafts = [
                row for row in list_tailoring_generations(94)
                if row.get("generation_kind")
                == "phase9e_editable_action_draft"
            ]
        self.assertTrue(context["can_generate"])
        self.assertEqual(
            context["workflow_action"]["workflow_action"],
            "apply_optional_polish",
        )
        self.assertFalse(context["section_lock_scope"]["projects_locked"])
        self.assertEqual(len(editable_drafts), 1)
        self.assertFalse(editable_drafts[0]["content_changed"])

    def test_targeted_retargeting_action_creates_one_editable_draft(self):
        self.link_revised_same_family_jd()
        comparison = self.comparison_with_gaps(1)
        with patch(
            "tailoring.phase9e_blueprint_selection.evaluate_starting_snapshot",
            return_value=comparison,
        ):
            app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
            app = self.confirm_and_bind(app)
            _by_key(app.button, "phase9e_targeted_94").click().run()
            drafts = [
                row for row in list_tailoring_generations(94)
                if row.get("generation_kind")
                == "phase9e_editable_action_draft"
            ]
        self.assertEqual(len(drafts), 1)
        self.assertFalse(drafts[0]["content_changed"])
        self.assertTrue(drafts[0]["phase9e_decision_fingerprint"])

    def test_targeted_unchanged_override_is_audited_in_streamlit(self):
        self.link_revised_same_family_jd()
        comparison = self.comparison_with_gaps(1)
        with patch(
            "tailoring.phase9e_blueprint_selection.evaluate_starting_snapshot",
            return_value=comparison,
        ):
            app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
            app = self.confirm_and_bind(app)
            self.assertTrue(
                any(
                    "GENERATION_CONTEXT=awaiting_explicit_choice" in item.value
                    for item in app.markdown
                )
            )
            _by_key(
                app.checkbox, "phase9e_targeted_override_ack_94"
            ).set_value(True).run()
            _by_key(
                app.text_area, "phase9e_targeted_override_reason_94"
            ).set_value(
                "I accept these documented gaps for this application."
            ).run()
            _by_key(
                app.button, "phase9e_targeted_override_94"
            ).click().run()
            context = resolve_current_phase9e_generation_context(94)
        self.assertTrue(context["can_generate"])
        self.assertTrue(context["section_lock_scope"]["projects_locked"])
        events = list_application_blueprint_binding_events(94)
        self.assertTrue(
            any(
                event["event_type"] == "workflow_action_selected"
                and event["event_details"]["acknowledgement"] is True
                for event in events
            )
        )

    def test_main_app_registers_phase9e_inside_application_sessions(self):
        source = (HARNESS.parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn("render_phase9e_blueprint_selection(", source)
        self.assertIn("phase9e_ready", source)
        self.assertIn("phase9e_binding=phase9e_binding", source)
        self.assertNotIn('"Phase 9E"\n        ],', source)

    def test_cleanup_pages_tables_render_without_arrow_type_repair(self):
        original_fix = dataframe_util.fix_arrow_incompatible_column_types
        with patch.object(
            dataframe_util,
            "fix_arrow_incompatible_column_types",
            wraps=original_fix,
        ) as automatic_repair:
            app = AppTest.from_file(
                str(PAGES_HARNESS), default_timeout=60
            ).run()

        self.assertEqual(list(app.exception), [])
        self.assertEqual(len(app.dataframe), 3)
        automatic_repair.assert_not_called()


if __name__ == "__main__":
    unittest.main()

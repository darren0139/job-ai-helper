from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from database import (
    db_manager,
    jd_library_manager,
    tailoring_version_manager,
    user_profile_manager,
)
from database.phase9f_tailoring_execution_manager import (
    get_phase9f_tailoring_execution,
)
import database.phase9f_tailoring_execution_manager as execution_manager
from tailoring.phase9f_tailoring_execution import (
    PHASE9F_F_SECTION_SCOPE_POLICY_VERSION,
)
from tests.phase9f_d_test_support import configure_database
from tests.phase9f_e_test_support import create_d_reuse_session


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "tests" / "phase9f_tailoring_execution_streamlit_harness.py"


class Phase9FTailoringExecutionStreamlitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database_path = self.root / "phase9f-f-ui.db"
        self.source_root = self.root / "sources"
        self.source_root.mkdir()
        self.old_paths = (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
            user_profile_manager.DB_PATH,
        )
        configure_database(self.database_path)
        user_profile_manager.DB_PATH = self.database_path
        state = create_d_reuse_session(
            self.database_path,
            source_type="global_blueprint",
            artifact_root=self.source_root,
            confirmed_intensity="minor",
        )
        self.application_id = state["application_id"]
        self.source_docx = self.root / "source.docx"
        self.output_docx = self.root / "output.docx"
        self.output_pdf = self.root / "output.pdf"
        self.source_docx.write_bytes(b"phase9f-f-settings-source")
        self.output_docx.write_bytes(b"phase9f-f-settings-output-docx")
        self.output_pdf.write_bytes(b"phase9f-f-settings-output-pdf")
        self.environment = {
            "PHASE9F_F_TEST_DATABASE": str(self.database_path),
            "PHASE9F_F_TEST_APPLICATION_ID": str(self.application_id),
            "PHASE9F_F_TEST_SOURCE_DOCX": str(self.source_docx),
            "PHASE9F_F_TEST_OUTPUT_DOCX": str(self.output_docx),
            "PHASE9F_F_TEST_OUTPUT_PDF": str(self.output_pdf),
        }

    def tearDown(self) -> None:
        (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
            user_profile_manager.DB_PATH,
        ) = self.old_paths
        self.temporary.cleanup()

    def _counts(self) -> tuple[int, int]:
        connection = tailoring_version_manager._connect()
        try:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            return tuple(
                int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE application_id=?",
                        (self.application_id,),
                    ).fetchone()[0]
                )
                if table in tables
                else 0
                for table in (
                    "phase9f_tailoring_executions",
                    "application_tailoring_versions",
                )
            )
        finally:
            connection.close()

    def _event_count(self) -> int:
        connection = tailoring_version_manager._connect()
        try:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM phase9f_tailoring_execution_events "
                    "WHERE application_id=?",
                    (self.application_id,),
                ).fetchone()[0]
            )
        finally:
            connection.close()

    @staticmethod
    def _widget(elements, label: str):
        return next(item for item in elements if item.label == label)

    def _settings_environment(self) -> dict[str, str]:
        return {
            **self.environment,
            "PHASE9F_F_TEST_SURFACE": "settings",
        }

    def _add_evidence(self) -> None:
        user_profile_manager.init_user_profile_library()
        user_profile_manager.create_evidence_item(
            category="Project",
            title="Fresh F settings evidence",
            description=(
                "Built a truthful React and PostgreSQL integration for a target JD."
            ),
            skills=["React", "PostgreSQL"],
            tools=["PostgREST"],
        )

    def test_passive_render_writes_nothing_then_prepare_creates_one_blocked_execution(self) -> None:
        before = self._counts()
        with patch.dict(os.environ, self.environment):
            app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
        self.assertEqual(app.exception, [])
        self.assertEqual(self._counts(), before)
        self.assertTrue(any("Begin Minor tailoring" == button.label for button in app.button))

        prepare = next(button for button in app.button if button.label == "Begin Minor tailoring")
        with patch.dict(os.environ, self.environment):
            blocked = prepare.click().run(timeout=60)
        self.assertEqual(blocked.exception, [])
        execution = get_phase9f_tailoring_execution(self.application_id)
        self.assertIsNotNone(execution)
        self.assertEqual(execution["status"], "blocked")
        self.assertEqual(self._counts(), (1, 0))
        self.assertTrue(any("No truthful Projects or Skills change" in str(item.value) for item in blocked.warning))

    def test_interrupted_model_stage_renders_uncertainty_without_a_passive_write(self) -> None:
        def scope(**kwargs):
            return {
                "policy_version": PHASE9F_F_SECTION_SCOPE_POLICY_VERSION,
                "phase9a_version": "phase9a-evidence-opportunity-v1",
                "confirmed_intensity": kwargs["confirmed_intensity"],
                "opportunity_fingerprint": "ui-interrupted-opportunity",
                "selected_evidence_ids": [],
                "selected_evidence_fingerprint": "ui-interrupted-evidence",
                "projects_addressable": True,
                "skills_addressable": True,
                "enabled_sections": ["projects", "skills"],
                "selected_evidence": [],
                "opportunity": {},
                "scope_fingerprint": "ui-interrupted-scope",
            }

        with patch.object(execution_manager, "build_section_scope", scope):
            prepared = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                application_id=self.application_id
            )["execution"]
            prepared, settings_snapshot = (
                execution_manager._freeze_or_reuse_generation_settings(
                    execution=prepared,
                    generation_settings={
                        "max_projects": 2,
                        "max_bullets": 3,
                        "bullet_allocation_mode": "adaptive",
                    },
                    selected_model="focused-ui-model",
                    actor_label="Focused UI test",
                )
            )
            execution_manager._mark_stage_requested(
                execution=prepared,
                stage="projects",
                input_fingerprint="ui-lost-projects-response",
                actor_label="Focused UI test",
                settings_snapshot=settings_snapshot,
            )
        connection = tailoring_version_manager._connect()
        try:
            events_before = int(
                connection.execute(
                    "SELECT COUNT(*) FROM phase9f_tailoring_execution_events WHERE application_id=?",
                    (self.application_id,),
                ).fetchone()[0]
            )
        finally:
            connection.close()
        before = self._counts()
        with patch.dict(os.environ, self.environment):
            app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
        self.assertEqual(app.exception, [])
        self.assertEqual(self._counts(), before)
        connection = tailoring_version_manager._connect()
        try:
            events_after = int(
                connection.execute(
                    "SELECT COUNT(*) FROM phase9f_tailoring_execution_events WHERE application_id=?",
                    (self.application_id,),
                ).fetchone()[0]
            )
        finally:
            connection.close()
        self.assertEqual(events_after, events_before)
        self.assertTrue(
            any("prior paid model attempt" in str(item.value).lower() for item in app.error)
        )
        execution = get_phase9f_tailoring_execution(self.application_id)
        self.assertEqual(execution["recovery_state"], "model_attempt_uncertain")

    def test_fresh_full_uses_normal_generations_without_session_wide_settings_lock(self) -> None:
        full_database = self.root / "phase9f-f-full-settings-ui.db"
        configure_database(full_database)
        user_profile_manager.DB_PATH = full_database
        self._add_evidence()
        state = create_d_reuse_session(
            full_database,
            source_type="global_blueprint",
            artifact_root=self.source_root,
            confirmed_intensity="full",
        )
        application_id = state["application_id"]
        environment = {
            **self._settings_environment(),
            "PHASE9F_F_TEST_DATABASE": str(full_database),
            "PHASE9F_F_TEST_APPLICATION_ID": str(application_id),
        }

        with patch.dict(os.environ, environment):
            app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
        self.assertEqual(app.exception, [])
        begin = self._widget(app.button, "Begin Full tailoring")
        self.assertFalse(begin.disabled)

        with patch.dict(os.environ, environment):
            initialized = begin.click().run(timeout=60)
        self.assertEqual(initialized.exception, [])
        max_projects = self._widget(initialized.slider, "Maximum projects")
        allocation = self._widget(initialized.radio, "Bullet allocation")
        max_bullets = self._widget(initialized.slider, "Bullet limit per project")
        self.assertFalse(max_projects.disabled)
        self.assertFalse(allocation.disabled)
        self.assertFalse(max_bullets.disabled)

        execution = get_phase9f_tailoring_execution(application_id)
        self.assertEqual(execution["stage_outputs"].get("generation_settings"), None)
        self.assertNotIn("projects", execution["stage_outputs"])
        events_before_tuning = self._event_count_for(application_id)

        with patch.dict(os.environ, environment):
            tuned = max_projects.set_value(5).run(timeout=60)
            tuned = self._widget(tuned.radio, "Bullet allocation").set_value(
                "Adaptive"
            ).run(timeout=60)
            tuned = self._widget(tuned.slider, "Bullet limit per project").set_value(
                4
            ).run(timeout=60)
        self.assertEqual(tuned.exception, [])
        self.assertEqual(self._event_count_for(application_id), events_before_tuning)
        unchanged = get_phase9f_tailoring_execution(application_id)
        self.assertNotIn("generation_settings", unchanged["stage_outputs"])
        self.assertNotIn("projects", unchanged["stage_outputs"])
        self.assertNotIn("skills", unchanged["stage_outputs"])

        acknowledgement = self._widget(
            tuned.checkbox,
            "I understand this starts paid Projects/Skills generation for the enabled sections.",
        )
        with patch.dict(os.environ, environment):
            ready = acknowledgement.set_value(True).run(timeout=60)
            generated = self._widget(
                ready.button, "Generate Projects + Skills"
            ).click().run(timeout=60)
        self.assertEqual(generated.exception, [])
        bound = get_phase9f_tailoring_execution(application_id)
        self.assertNotIn("generation_settings", bound["stage_outputs"])
        self.assertNotIn("projects", bound["stage_outputs"])
        self.assertNotIn("skills", bound["stage_outputs"])
        versions = execution_manager.list_tailoring_generations(application_id)
        self.assertEqual(len(versions), 1)
        lifecycle = versions[0]["generation_settings"][
            "phase9f_f_normal_lifecycle"
        ]
        settings = lifecycle["settings"]
        self.assertEqual(
            settings,
            {
                "policy_version": "phase9f-f-generation-settings-stage-v1",
                "max_projects": 5,
                "max_bullets": 4,
                "bullet_allocation_mode": "adaptive",
            },
        )
        self.assertEqual(lifecycle["generation_status"], "completed")
        self.assertFalse(
            self._widget(generated.slider, "Maximum projects").disabled
        )
        self.assertFalse(
            self._widget(generated.radio, "Bullet allocation").disabled
        )
        self.assertFalse(
            self._widget(generated.slider, "Bullet limit per project").disabled
        )

        # Sections are durable, but the first deterministic fitting attempt has
        # not happened. Its normal controls remain editable.
        page_density = self._widget(generated.radio, "Page density")
        self.assertFalse(page_density.disabled)
        with patch.dict(os.environ, environment):
            fitted = self._widget(generated.button, "Build and Fit").click().run(
                timeout=60
            )
        self.assertEqual(fitted.exception, [])
        self.assertFalse(self._widget(fitted.radio, "Page density").disabled)
        fitted_versions = execution_manager.list_tailoring_generations(application_id)
        self.assertEqual(len(fitted_versions), 1)
        fit_stage = fitted_versions[0]["generation_settings"][
            "phase9f_f_normal_lifecycle"
        ]["fit"]
        self.assertEqual(fit_stage["status"], "completed")
        self.assertEqual(
            fit_stage["settings"]["page_density_mode"],
            "balanced",
        )

    def test_f_normal_generation_has_visible_spinner_feedback(self) -> None:
        app_text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        message = '"Generating Projects and Skills from the frozen application context..."'
        self.assertIn(message, app_text)
        message_at = app_text.index(message)
        spinner_at = app_text.rfind("with st.spinner(", 0, message_at)
        call_at = app_text.index(
            "normal_generation = run_phase9f_normal_generation(",
            message_at,
        )
        rerun_at = app_text.index("st.rerun()", call_at)
        self.assertGreaterEqual(spinner_at, 0)
        self.assertLess(spinner_at, message_at)
        self.assertLess(message_at, call_at)
        self.assertLess(call_at, rerun_at)

    def test_legacy_uncertain_stage_keeps_controls_locked(self) -> None:
        self._add_evidence()

        def scope(**kwargs):
            return {
                "policy_version": PHASE9F_F_SECTION_SCOPE_POLICY_VERSION,
                "phase9a_version": "phase9a-evidence-opportunity-v1",
                "confirmed_intensity": kwargs["confirmed_intensity"],
                "opportunity_fingerprint": "legacy-uncertain-opportunity",
                "selected_evidence_ids": [],
                "selected_evidence_fingerprint": "legacy-uncertain-evidence",
                "projects_addressable": True,
                "skills_addressable": True,
                "enabled_sections": ["projects", "skills"],
                "selected_evidence": [],
                "opportunity": {},
                "scope_fingerprint": "legacy-uncertain-scope",
            }

        with patch.object(execution_manager, "build_section_scope", scope):
            prepared = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                application_id=self.application_id
            )["execution"]
            outputs = dict(prepared["stage_outputs"])
            outputs["projects"] = {
                "status": "requested",
                "input_fingerprint": "legacy-uncertain-request",
            }
            execution_manager._update_execution(
                execution_id=prepared["execution_id"],
                status="running",
                current_stage="projects",
                stage_outputs=outputs,
                event_type="legacy_model_stage_observed",
                actor_label="Focused Streamlit test",
                details={},
            )
        connection = tailoring_version_manager._connect()
        try:
            connection.execute(
                "UPDATE phase9f_tailoring_executions SET identity_policy_version=? "
                "WHERE application_id=?",
                ("phase9f-tailoring-execution-identity-v2", self.application_id),
            )
            connection.commit()
        finally:
            connection.close()

        with patch.dict(os.environ, self._settings_environment()):
            app = AppTest.from_file(str(HARNESS), default_timeout=60).run()
        self.assertEqual(app.exception, [])
        self.assertTrue(self._widget(app.slider, "Maximum projects").disabled)
        self.assertTrue(self._widget(app.radio, "Bullet allocation").disabled)
        self.assertTrue(self._widget(app.slider, "Bullet limit per project").disabled)

    def _event_count_for(self, application_id: int) -> int:
        connection = tailoring_version_manager._connect()
        try:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM phase9f_tailoring_execution_events "
                    "WHERE application_id=?",
                    (int(application_id),),
                ).fetchone()[0]
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()

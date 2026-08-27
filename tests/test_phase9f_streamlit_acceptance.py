from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from database import jd_library_manager as manager
from tailoring.jd_user_input_overrides import (
    JD_USER_OVERRIDE_POLICY_VERSION,
    PREFERRED_REQUIREMENTS_HELP,
    PREFERRED_REQUIREMENTS_LABEL,
)
from tailoring.phase9f_jd_intake import build_phase9f_analysis_diagnostics


HARNESS = Path(__file__).with_name("phase9f_streamlit_harness.py")
REPO_ROOT = HARNESS.parents[1]
RAW_JD = """
Junior AI Full-Stack Engineer
Example Company
Responsibilities
Build and maintain full-stack applications using Python, React, TypeScript,
PostgreSQL, authentication workflows, automated tests, and secure deployment.
Collaborate with engineers and product stakeholders to operate reliable services.
Requirements
Python, React, PostgreSQL, API design, testing, and collaboration are required.
Preferred qualifications
Cloud deployment and container experience are preferred.
""".strip()


def _by_key(elements, key):
    return next(element for element in elements if element.key == key)


def _contains(elements, expected: str) -> bool:
    return any(expected in str(element.value) for element in elements)


def _profile() -> dict:
    return {
        "job_title": "Junior AI Full-Stack Engineer",
        "company": "Example Company",
        "location": "Singapore",
        "experience_level": "Junior",
        "responsibilities": [
            "Build full-stack applications with Python and React."
        ],
        "required_skills": ["Python", "React"],
        "preferred_skills": ["PostgreSQL"],
        "tools_technologies": ["Python", "React", "PostgreSQL"],
        "soft_skills": ["Collaboration"],
        "buzzwords": [],
        "deal_breakers": [],
    }


class Phase9FStreamlitAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_path = manager.DB_PATH
        self.old_environment = os.environ.get("PHASE9F_TEST_DATABASE")
        self.database_path = Path(self.temporary.name) / "phase9f.sqlite"
        manager.DB_PATH = self.database_path
        manager.init_jd_library()
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                "CREATE TABLE applications (id INTEGER PRIMARY KEY)"
            )
            connection.execute(
                "CREATE TABLE application_blueprint_decisions "
                "(decision_id TEXT PRIMARY KEY)"
            )
            connection.execute(
                "CREATE TABLE phase9f_confirmations (id TEXT PRIMARY KEY)"
            )
            connection.commit()
        finally:
            connection.close()
        os.environ["PHASE9F_TEST_DATABASE"] = str(self.database_path)

    def tearDown(self) -> None:
        manager.DB_PATH = self.old_path
        if self.old_environment is None:
            os.environ.pop("PHASE9F_TEST_DATABASE", None)
        else:
            os.environ["PHASE9F_TEST_DATABASE"] = self.old_environment
        self.temporary.cleanup()

    def _lifecycle_counts(self) -> dict[str, int]:
        connection = sqlite3.connect(self.database_path)
        try:
            return {
                table: int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                )
                for table in (
                    "applications",
                    "application_blueprint_decisions",
                    "phase9f_confirmations",
                )
            }
        finally:
            connection.close()

    def test_navigation_is_first_and_preserves_existing_routes(self):
        source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        widget = source[source.index("page = st.radio(") :]
        widget = widget[: widget.index('key="navigation_page"')]
        labels = (
            "Tailor Resume",
            "Application Sessions",
            "Blueprint Library",
            "Profile & Evidence",
            "Job Market Insights",
        )
        positions = [widget.index(f'"{label}"') for label in labels]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('"Global Blueprints"', widget)
        self.assertIn("render_phase9f_jd_intake()", source)
        self.assertIn('elif page == "Application Sessions":', source)
        self.assertIn("render_phase9d_global_blueprints(", source)

    def test_passive_render_and_input_modes_are_zero_cost_and_read_only(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(_contains(app.header, "Tailor Resume"))
        self.assertTrue(_contains(app.markdown, "MODEL_CALLS=0"))
        self.assertTrue(_contains(app.markdown, "EMBEDDING_CALLS=0"))
        self.assertEqual(
            manager.get_jd_library_stats(),
            {"canonical_jobs": 0, "versions": 0, "session_links": 0},
        )
        self.assertEqual(
            self._lifecycle_counts(),
            {
                "applications": 0,
                "application_blueprint_decisions": 0,
                "phase9f_confirmations": 0,
            },
        )

        _by_key(app.selectbox, "phase9f_jd_source_mode").set_value(
            "Upload job-description file"
        ).run()
        self.assertTrue(_contains(app.markdown, "MODEL_CALLS=0"))
        self.assertTrue(_contains(app.markdown, "EMBEDDING_CALLS=0"))
        self.assertEqual(manager.get_jd_library_stats()["canonical_jobs"], 0)

    def test_paste_requires_explicit_analysis_and_becomes_stale_on_change(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.text_area, "phase9f_pasted_jd_text").set_value(
            RAW_JD
        ).run()
        self.assertTrue(_contains(app.markdown, "MODEL_CALLS=0"))
        self.assertTrue(
            any(
                "may incur API charges" in str(item.value)
                for item in app.warning
            )
        )
        self.assertEqual(manager.get_jd_library_stats()["canonical_jobs"], 0)

    def test_preferred_requirement_input_is_zero_cost_until_analysis_and_is_semantic(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.text_area, "phase9f_pasted_jd_text").set_value(
            RAW_JD
        ).run()
        _by_key(
            app.text_area, "phase9f_jd_preferred_requirements"
        ).set_value("Experience with Android app development and Kotlin").run()

        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any(item.label == PREFERRED_REQUIREMENTS_LABEL for item in app.text_area)
        )
        self.assertIn("new entries are added only to this application.", PREFERRED_REQUIREMENTS_HELP)
        self.assertTrue(_contains(app.markdown, "MODEL_CALLS=0"))
        self.assertTrue(_contains(app.markdown, "EMBEDDING_CALLS=0"))
        self.assertEqual(
            manager.get_jd_library_stats(),
            {"canonical_jobs": 0, "versions": 0, "session_links": 0},
        )
        self.assertEqual(sum(self._lifecycle_counts().values()), 0)

        _by_key(app.button, "phase9f_analyse_jd").click().run()

        self.assertEqual(list(app.exception), [])
        snapshot = app.session_state["phase9f_jd_analysis"]
        inputs = snapshot["application_local_jd_user_inputs"]
        self.assertEqual(inputs["policy_version"], JD_USER_OVERRIDE_POLICY_VERSION)
        self.assertEqual(
            inputs["supplemental_preferred_requirements"],
            ["Experience with Android app development and Kotlin"],
        )
        supplemental = [
            row
            for row in snapshot["canonical_requirements"]
            if row.get("application_requirement_scope") == "application_local"
        ]
        self.assertEqual(len(supplemental), 1)
        self.assertEqual(supplemental[0]["importance"], "preferred")
        self.assertEqual(supplemental[0]["importance_source"], "user_supplied")
        self.assertFalse(supplemental[0]["canonical_shared"])
        self.assertNotIn(
            "Experience with Android app development and Kotlin",
            snapshot["raw_text"],
        )
        self.assertNotIn(
            "Experience with Android app development and Kotlin",
            snapshot["jd_profile"].get("preferred_skills", []),
        )
        self.assertEqual(snapshot["extraction_provenance"]["method"], "existing_jd_extraction_and_review")
        self.assertTrue(_contains(app.markdown, "EMBEDDING_CALLS=0"))
        self.assertEqual(manager.get_jd_library_stats()["canonical_jobs"], 0)

        _by_key(app.button, "phase9f_analyse_jd").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(_contains(app.subheader, "Job Analysis"))
        snapshot = app.session_state["phase9f_jd_analysis"]
        self.assertTrue(snapshot["canonical_requirements"])
        self.assertEqual(
            snapshot["role_family"]["role_family_id"],
            "ai_fullstack_software_engineering",
        )
        self.assertNotIn("final_scoring_seed", snapshot)
        self.assertEqual(manager.get_jd_library_stats()["canonical_jobs"], 0)

        _by_key(app.text_area, "phase9f_pasted_jd_text").set_value(
            RAW_JD + "\nThe exact posting has changed."
        ).run()
        self.assertTrue(
            any("historical/stale" in item.value for item in app.warning)
        )
        self.assertEqual(manager.get_jd_library_stats()["canonical_jobs"], 0)

    def test_passive_diagnostics_are_zero_cost_and_read_only(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.text_area, "phase9f_pasted_jd_text").set_value(
            RAW_JD
        ).run()
        _by_key(app.button, "phase9f_analyse_jd").click().run()
        baseline_stats = manager.get_jd_library_stats()
        baseline_lifecycle = self._lifecycle_counts()
        snapshot_fingerprint = app.session_state["phase9f_jd_analysis"][
            "snapshot_fingerprint"
        ]

        app.run()

        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any(
                item.label == "Analysis diagnostics"
                for item in app.expander
            )
        )
        source = (
            REPO_ROOT / "tailoring" / "phase9f_orchestrator_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"Download diagnostics JSON"', source)
        self.assertTrue(_contains(app.markdown, "MODEL_CALLS=1"))
        self.assertTrue(_contains(app.markdown, "EMBEDDING_CALLS=0"))
        self.assertEqual(manager.get_jd_library_stats(), baseline_stats)
        self.assertEqual(self._lifecycle_counts(), baseline_lifecycle)
        self.assertEqual(
            app.session_state["phase9f_jd_analysis"]["snapshot_fingerprint"],
            snapshot_fingerprint,
        )

    def test_meaningless_pasted_input_fails_before_model_call(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.text_area, "phase9f_pasted_jd_text").set_value(
            "Too short to be a meaningful job description."
        ).run()
        _by_key(app.button, "phase9f_analyse_jd").click().run()

        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any("too short" in str(item.value).lower() for item in app.error)
        )
        self.assertTrue(_contains(app.markdown, "MODEL_CALLS=0"))
        self.assertTrue(_contains(app.markdown, "EMBEDDING_CALLS=0"))
        self.assertEqual(manager.get_jd_library_stats()["canonical_jobs"], 0)
        self.assertEqual(sum(self._lifecycle_counts().values()), 0)

    def test_exact_saved_version_reuses_stored_analysis_without_model_calls(self):
        saved = manager.save_job_description_to_library(
            raw_text=RAW_JD,
            jd_profile=_profile(),
        )
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.selectbox, "phase9f_jd_source_mode").set_value(
            "Choose saved JD"
        ).run()
        _by_key(app.button, "phase9f_analyse_jd").click().run()

        self.assertEqual(list(app.exception), [])
        self.assertTrue(_contains(app.markdown, "MODEL_CALLS=0"))
        self.assertTrue(_contains(app.success, "Saved JD · Exact version"))
        snapshot = app.session_state["phase9f_jd_analysis"]
        self.assertEqual(
            snapshot["source_version_id"], saved["source_version_id"]
        )
        self.assertEqual(snapshot["model_call_count"], 0)
        self.assertEqual(snapshot["embedding_call_count"], 0)

    def test_pasted_exact_saved_jd_reuses_analysis_before_model_call(self):
        saved = manager.save_job_description_to_library(
            raw_text=RAW_JD,
            jd_profile=_profile(),
        )

        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.text_area, "phase9f_pasted_jd_text").set_value(
            RAW_JD
        ).run()

        self.assertTrue(
            _contains(
                app.success,
                "exact JD already exists in the JD Library",
            )
        )
        self.assertFalse(
            any(
                "may incur API charges" in str(item.value)
                for item in app.warning
            )
        )

        _by_key(app.button, "phase9f_analyse_jd").click().run()

        self.assertEqual(list(app.exception), [])
        self.assertTrue(_contains(app.markdown, "MODEL_CALLS=0"))
        self.assertTrue(_contains(app.markdown, "EMBEDDING_CALLS=0"))
        self.assertTrue(
            _contains(
                app.success,
                "Reused the exact JD Library analysis",
            )
        )

        snapshot = app.session_state["phase9f_jd_analysis"]
        self.assertEqual(snapshot["source_type"], "pasted")
        self.assertEqual(
            snapshot["library_jd_id"],
            saved["job_description_id"],
        )
        self.assertEqual(snapshot["model_call_count"], 0)
        self.assertEqual(snapshot["embedding_call_count"], 0)
        self.assertTrue(snapshot["reused_exact_saved_version"])
        self.assertEqual(
            snapshot["extraction_provenance"]["method"],
            "stored_exact_version_profile_reuse",
        )

        diagnostics = build_phase9f_analysis_diagnostics(snapshot)
        self.assertEqual(
            diagnostics["extraction"]["api_usage"]["call_count"],
            0,
        )
        self.assertTrue(
            diagnostics["extraction"]["reused_exact_saved_version"]
        )
        self.assertEqual(sum(self._lifecycle_counts().values()), 0)

    def test_explicit_save_reuses_one_exact_jd_and_creates_no_lifecycle_rows(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.text_area, "phase9f_pasted_jd_text").set_value(
            RAW_JD
        ).run()
        _by_key(app.button, "phase9f_analyse_jd").click().run()
        _by_key(app.button, "phase9f_save_jd").click().run()

        self.assertEqual(list(app.exception), [])
        self.assertTrue(_contains(app.success, "Saved to JD Library"))
        self.assertTrue(_contains(app.markdown, "EMBEDDING_CALLS=1"))
        self.assertEqual(
            manager.get_jd_library_stats(),
            {"canonical_jobs": 1, "versions": 1, "session_links": 0},
        )
        self.assertEqual(sum(self._lifecycle_counts().values()), 0)

        _by_key(app.button, "phase9f_save_jd").click().run()
        self.assertEqual(
            manager.get_jd_library_stats(),
            {"canonical_jobs": 1, "versions": 1, "session_links": 0},
        )
        self.assertTrue(_contains(app.markdown, "EMBEDDING_CALLS=1"))
        self.assertTrue(
            _contains(
                app.success,
                "no duplicate version or embedding was created",
            )
        )
        receipt = app.session_state["phase9f_jd_save_receipt"]
        diagnostics = build_phase9f_analysis_diagnostics(
            app.session_state["phase9f_jd_analysis"],
            save_receipt=receipt,
        )
        self.assertEqual(
            diagnostics["most_recent_save"]["outcome"],
            "exact_existing_jd_version_reused",
        )
        self.assertFalse(
            diagnostics["most_recent_save"]["new_version_created"]
        )
        self.assertFalse(
            diagnostics["most_recent_save"]["chroma_indexing_occurred"]
        )

        _by_key(app.button, "phase9f_save_jd").click().run()
        self.assertEqual(
            manager.get_jd_library_stats(),
            {"canonical_jobs": 1, "versions": 1, "session_links": 0},
        )
        self.assertTrue(_contains(app.markdown, "EMBEDDING_CALLS=1"))
        self.assertEqual(sum(self._lifecycle_counts().values()), 0)

    def test_phase9f_a_source_has_no_ranking_or_execution_path(self):
        source = (
            REPO_ROOT / "tailoring" / "phase9f_orchestrator_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("may incur API charges", source)
        self.assertIn("estimated cost", source)
        self.assertIn("embedding API charges", source)
        self.assertIn(
            "does not call the JD extraction model",
            source,
        )
        for forbidden in (
            "Recommended Blueprint",
            "Projected Blueprint score",
            "Create Application Session",
            "phase9e",
            "final_scoring_seed",
            "chroma similarity",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()

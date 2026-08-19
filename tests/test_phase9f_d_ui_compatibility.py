from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from database import db_manager, jd_library_manager, tailoring_version_manager
from database.application_blueprint_manager import (
    get_current_application_blueprint_decision,
)
from database.phase9f_application_confirmation_manager import (
    confirm_phase9f_application_session,
)
from tailoring.phase9f_application_confirmation import (
    PHASE9F_D_EXECUTION_NOT_STARTED_STATUS,
)
from tests.phase9f_d_test_support import (
    build_scope,
    configure_database,
    insert_base_resume,
    insert_blueprint,
    save_exact_jd,
)
from tests.test_phase9f_starting_source_ranking import make_exact_jd


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "tests" / (
    "phase9f_d_ui_compatibility_streamlit_harness.py"
)


def _values(elements) -> list[str]:
    return [str(element.value) for element in elements]


class Phase9FDUiCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "phase9f-d-ui.db"
        self.old_paths = (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
        )
        self.old_database_environment = os.environ.get(
            "PHASE9F_D_TEST_DATABASE"
        )
        self.old_application_environment = os.environ.get(
            "PHASE9F_D_TEST_APPLICATION_ID"
        )
        configure_database(self.database_path)
        insert_base_resume(self.database_path, strong=False)
        self.blueprint = insert_blueprint(self.database_path, strong=True)
        exact_jd = make_exact_jd()
        persisted_jd = save_exact_jd(self.database_path)
        ranking, recommendation = build_scope(
            self.database_path,
            phase9f_a_snapshot=exact_jd,
        )
        winner = ranking["recommended_source"]
        created = confirm_phase9f_application_session(
            phase9f_a_snapshot=exact_jd,
            persisted_exact_jd_snapshot=persisted_jd,
            ranking_result=ranking,
            phase9f_c_recommendation=recommendation,
            confirmed_normalized_source_fingerprint=winner[
                "normalized_source_fingerprint"
            ],
            confirmed_intensity="full",
            application_intent_id="phase9f-d-ui-compatibility",
        )
        self.application_id = created["confirmation"]["application_id"]
        os.environ["PHASE9F_D_TEST_DATABASE"] = str(self.database_path)
        os.environ["PHASE9F_D_TEST_APPLICATION_ID"] = str(
            self.application_id
        )

    def tearDown(self) -> None:
        (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
        ) = self.old_paths
        if self.old_database_environment is None:
            os.environ.pop("PHASE9F_D_TEST_DATABASE", None)
        else:
            os.environ["PHASE9F_D_TEST_DATABASE"] = (
                self.old_database_environment
            )
        if self.old_application_environment is None:
            os.environ.pop("PHASE9F_D_TEST_APPLICATION_ID", None)
        else:
            os.environ["PHASE9F_D_TEST_APPLICATION_ID"] = (
                self.old_application_environment
            )
        self.temporary.cleanup()

    def _row_counts(self) -> dict[str, int]:
        connection = tailoring_version_manager._connect()
        try:
            tables = [
                str(row[0])
                for row in connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                    """
                ).fetchall()
            ]
            return {
                table: int(
                    connection.execute(
                        f'SELECT COUNT(*) FROM "{table}"'
                    ).fetchone()[0]
                )
                for table in tables
            }
        finally:
            connection.close()

    def test_exact_d_binding_renders_bound_but_not_started(self) -> None:
        before = self._row_counts()
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(self._row_counts(), before)

        successes = _values(app.success)
        infos = _values(app.info)
        captions = _values(app.caption)
        markdown = _values(app.markdown)
        warnings = _values(app.warning)
        button_labels = [button.label for button in app.button]
        all_text = successes + infos + captions + markdown + warnings

        self.assertTrue(
            any(
                "Exact Phase 9F-D Tailoring Base is bound" in value
                for value in successes
            )
        )
        self.assertTrue(
            any("Confirmed tailoring intensity" in value for value in markdown)
        )
        self.assertTrue(
            any("Tailoring execution has not started" in value for value in infos)
        )
        self.assertTrue(
            any(
                f"CONTEXT_STATUS={PHASE9F_D_EXECUTION_NOT_STARTED_STATUS}"
                in value
                for value in markdown
            )
        )
        self.assertTrue(
            any("SOURCE_BINDING_STATUS=bound" in value for value in markdown)
        )
        self.assertTrue(
            any("EXECUTION_STATUS=not_started" in value for value in markdown)
        )
        self.assertTrue(
            any("CONFIRMED_INTENSITY=full" in value for value in markdown)
        )
        self.assertTrue(any("CAN_GENERATE=False" in value for value in markdown))

        prohibited = (
            "awaiting explicit choice",
            "selected blueprint is unsuitable",
            "Reuse Unchanged",
            "Phase 9E scope is explicitly evaluated and bound",
        )
        self.assertFalse(
            any(
                prohibited_text.lower() in value.lower()
                for prohibited_text in prohibited
                for value in all_text
            )
        )
        self.assertNotIn("Regenerate from original résumé", button_labels)
        self.assertNotIn("Change tailoring base", button_labels)

        decision = get_current_application_blueprint_decision(
            self.application_id
        )
        self.assertEqual(
            decision["selection"]["selected_blueprint"]["blueprint_id"],
            self.blueprint["blueprint_id"],
        )
        self.assertEqual(
            decision["phase9f_d_execution"],
            {"status": "not_started", "confirmed_intensity": "full"},
        )

    def test_main_application_waiting_copy_is_version_gated(self) -> None:
        source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("phase9f_d_execution_waiting", source)
        self.assertIn("Exact starting source is bound.", source)
        self.assertIn(
            "Tailoring execution has not started. A working résumé",
            source,
        )
        self.assertIn(
            '"mode": "phase9f_d_execution_not_started"',
            source,
        )
        d_plan = source.index(
            '"mode": "phase9f_d_execution_not_started"'
        )
        legacy_reuse = source.index(
            '"mode": "load_phase9e_starting_snapshot"',
            d_plan,
        )
        self.assertLess(d_plan, legacy_reuse)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db_manager, jd_library_manager, tailoring_version_manager
import database.phase9f_application_execution_manager as execution_manager
from database.application_blueprint_manager import (
    get_current_application_blueprint_decision,
)
from database.application_resume_result_manager import (
    get_application_resume_result,
    list_application_result_verifications,
    list_application_resume_results,
)
from database.application_resume_output_manager import (
    resolve_application_resume_output,
)
from database.global_blueprint_manager import (
    list_reusable_global_blueprints,
    remove_global_blueprint_from_reuse,
)
from database.global_master_resume_manager import (
    get_global_master_resume_artifact,
)
from database.phase9f_application_confirmation_manager import (
    get_phase9f_application_confirmation,
)
from tailoring.phase9f_application_execution import (
    PHASE9F_E_RESULT_FORMAT_VERSION,
    PHASE9F_E_RESULT_STATUS,
    PHASE9F_E_VERSION,
    Phase9FEExecutionError,
    phase9b_eligibility,
)
from tests.phase9f_d_test_support import build_scope, configure_database
from tests.phase9f_e_test_support import create_d_reuse_session
from tests.test_phase9f_starting_source_ranking import make_exact_jd


class Phase9FApplicationExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database_path = self.root / "phase9f-e.db"
        self.artifact_root = self.root / "source-artifacts"
        self.artifact_root.mkdir()
        self.result_root = self.root / "application-results"
        self.old_paths = (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
        )
        configure_database(self.database_path)

    def tearDown(self) -> None:
        (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
        ) = self.old_paths
        self.temporary.cleanup()

    def _session(self, source_type: str) -> dict:
        return create_d_reuse_session(
            self.database_path,
            source_type=source_type,
            artifact_root=self.artifact_root,
        )

    def _execute(self, application_id: int) -> dict:
        return execution_manager.execute_phase9f_reuse(
            application_id=application_id,
            actor_label="Phase 9F-E test",
            artifact_root=self.result_root,
        )

    def _count(self, table: str, where: str = "", params=()) -> int:
        connection = tailoring_version_manager._connect()
        try:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if exists is None:
                return 0
            return int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} {where}", params
                ).fetchone()[0]
            )
        finally:
            connection.close()

    def test_schema_initialization_is_additive_and_idempotent(self) -> None:
        db_manager.init_db()
        execution_manager.init_phase9f_application_execution_schema()
        execution_manager.init_phase9f_application_execution_schema()
        connection = tailoring_version_manager._connect()
        try:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            connection.close()
        self.assertIn("phase9f_application_executions", tables)
        self.assertIn("phase9f_application_execution_events", tables)
        self.assertEqual(
            execution_manager.get_phase9f_application_execution(1), None
        )

    def test_global_blueprint_reuse_is_exact_immutable_and_idempotent(self) -> None:
        state = self._session("global_blueprint")
        application_id = state["application_id"]
        confirmation_before = copy.deepcopy(
            get_phase9f_application_confirmation(application_id)
        )
        decision_before = copy.deepcopy(
            get_current_application_blueprint_decision(application_id)
        )
        candidate_count = self._count("global_blueprint_candidates")
        blueprint_count = self._count("global_blueprint_versions")

        first = self._execute(application_id)
        self.assertEqual(first["execution"]["status"], "completed")
        self.assertEqual(
            first["execution"]["phase8_mode"],
            "strict_inherited_source_phase8",
        )
        result = first["application_result"]
        self.assertEqual(result["format_version"], PHASE9F_E_RESULT_FORMAT_VERSION)
        self.assertEqual(result["initial_status"], PHASE9F_E_RESULT_STATUS)
        self.assertFalse(result["content_changed"])
        self.assertFalse(result["editable"])
        artifacts = {
            row["artifact_kind"]: Path(row["materialized_path"]).read_bytes()
            for row in result["artifacts"]
        }
        self.assertEqual(artifacts["docx"], state["blueprint"]["docx_path"].read_bytes())
        self.assertEqual(artifacts["pdf"], state["blueprint"]["pdf_path"].read_bytes())
        self.assertEqual(
            self._count(
                "application_tailoring_versions",
                "WHERE application_id=?",
                (application_id,),
            ),
            0,
        )
        self.assertEqual(self._count("global_blueprint_candidates"), candidate_count)
        self.assertEqual(self._count("global_blueprint_versions"), blueprint_count)
        self.assertEqual(
            phase9b_eligibility(
                result=result,
                phase8_result=(
                    first["phase8_binding"]["phase8_result"]
                ),
            )["reason_code"],
            "unchanged_global_blueprint_already_promoted",
        )

        second = self._execute(application_id)
        self.assertEqual(second["cache_status"], "completed_reused")
        self.assertEqual(
            second["execution"]["execution_id"],
            first["execution"]["execution_id"],
        )
        self.assertEqual(
            second["application_result"]["application_result_id"],
            result["application_result_id"],
        )
        self.assertEqual(len(list_application_resume_results(application_id)), 1)
        self.assertEqual(
            execution_manager.get_phase9f_application_execution(application_id)[
                "execution_id"
            ],
            first["execution"]["execution_id"],
        )
        self.assertEqual(
            get_phase9f_application_confirmation(application_id),
            confirmation_before,
        )
        decision_after = get_current_application_blueprint_decision(application_id)
        self.assertEqual(
            decision_after["decision_fingerprint"],
            decision_before["decision_fingerprint"],
        )
        self.assertEqual(
            decision_after["starting_snapshot"],
            decision_before["starting_snapshot"],
        )

    def test_base_resume_reuse_runs_phase8_and_preserves_future_eligibility(self) -> None:
        state = self._session("base_resume")
        result = self._execute(state["application_id"])
        self.assertEqual(
            result["execution"]["phase8_mode"],
            "executed_current_jd_phase8",
        )
        application_result = result["application_result"]
        source_artifact = get_global_master_resume_artifact(
            state["base"]["master_version_id"], "original"
        )
        self.assertIsNotNone(source_artifact)
        stored_artifact = application_result["artifacts"][0]
        self.assertEqual(
            Path(stored_artifact["materialized_path"]).read_bytes(),
            source_artifact["artifact_bytes"],
        )
        eligibility = phase9b_eligibility(
            result=application_result,
            phase8_result=result["phase8_binding"]["phase8_result"],
        )
        self.assertNotEqual(
            eligibility["reason_code"],
            "unchanged_global_blueprint_already_promoted",
        )
        self.assertEqual(
            self._count(
                "application_tailoring_versions",
                "WHERE application_id=?",
                (state["application_id"],),
            ),
            0,
        )
        output = resolve_application_resume_output(state["application_id"])
        self.assertEqual(output["output_kind"], "immutable_application_result")
        self.assertEqual(
            output["output_id"], application_result["application_result_id"]
        )
        self.assertEqual(
            output["resume_profile_snapshot"],
            application_result["result_snapshot"]["starting_snapshot"][
                "resume_profile_snapshot"
            ],
        )
        self.assertTrue(output["resume_text_snapshot"].strip())

    def test_missing_base_artifact_fails_closed_without_rematerialization(self) -> None:
        state = self._session("base_resume")
        connection = tailoring_version_manager._connect()
        try:
            connection.execute(
                "DELETE FROM global_master_resume_artifacts WHERE master_version_id=?",
                (state["base"]["master_version_id"],),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(Phase9FEExecutionError, "artifact is missing"):
            self._execute(state["application_id"])
        execution = execution_manager.get_phase9f_application_execution(
            state["application_id"]
        )
        self.assertEqual(execution["status"], "failed")
        self.assertEqual(execution["current_stage"], "source_preparation")
        self.assertEqual(list_application_resume_results(state["application_id"]), [])
        self.assertFalse(self.result_root.exists())

    def test_corrupt_base_artifact_fails_sha_validation(self) -> None:
        state = self._session("base_resume")
        connection = tailoring_version_manager._connect()
        try:
            current = bytes(
                connection.execute(
                    """
                    SELECT artifact_bytes FROM global_master_resume_artifacts
                    WHERE master_version_id=? AND artifact_kind='original'
                    """,
                    (state["base"]["master_version_id"],),
                ).fetchone()[0]
            )
            connection.execute(
                """
                UPDATE global_master_resume_artifacts
                SET artifact_bytes = ?
                WHERE master_version_id=? AND artifact_kind='original'
                """,
                (
                    sqlite3.Binary(current + b"corrupt"),
                    state["base"]["master_version_id"],
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(ValueError, "integrity validation"):
            self._execute(state["application_id"])
        self.assertEqual(
            execution_manager.get_phase9f_application_execution(
                state["application_id"]
            )["status"],
            "failed",
        )

    def test_removed_blueprint_remains_historically_executable(self) -> None:
        state = self._session("global_blueprint")
        blueprint = state["blueprint"]
        remove_global_blueprint_from_reuse(
            blueprint_id=blueprint["blueprint_id"],
            blueprint_fingerprint=blueprint["blueprint_fingerprint"],
            acknowledged=True,
            reason="Phase 9F-E historical execution regression test.",
        )
        reusable_ids = {
            row["blueprint_id"] for row in list_reusable_global_blueprints()
        }
        self.assertNotIn(blueprint["blueprint_id"], reusable_ids)
        fresh_ranking, _ = build_scope(
            self.database_path,
            phase9f_a_snapshot=make_exact_jd(),
        )
        self.assertNotIn(
            blueprint["blueprint_id"],
            {
                row["source_id"]
                for row in fresh_ranking["ranked_candidates"]
                if row["source_type"] == "global_blueprint"
            },
        )
        result = self._execute(state["application_id"])
        self.assertEqual(result["execution"]["status"], "completed")
        self.assertEqual(
            result["application_result"]["blueprint_id"],
            blueprint["blueprint_id"],
        )

    def test_blueprint_without_immutable_artifact_hash_provenance_fails_closed(self) -> None:
        state = self._session("global_blueprint")
        blueprint = state["blueprint"]
        connection = tailoring_version_manager._connect()
        try:
            result_ids = [
                str(row[0])
                for row in connection.execute(
                    """
                    SELECT application_result_id FROM application_resume_results
                    WHERE blueprint_id=? AND blueprint_fingerprint=?
                    """,
                    (
                        blueprint["blueprint_id"],
                        blueprint["blueprint_fingerprint"],
                    ),
                ).fetchall()
            ]
            for result_id in result_ids:
                connection.execute(
                    """
                    DELETE FROM application_resume_result_artifacts
                    WHERE application_result_id=?
                    """,
                    (result_id,),
                )
                connection.execute(
                    """
                    DELETE FROM application_resume_results
                    WHERE application_result_id=?
                    """,
                    (result_id,),
                )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(
            Phase9FEExecutionError,
            "no immutable approved-artifact hash provenance",
        ):
            self._execute(state["application_id"])
        self.assertEqual(
            execution_manager.get_phase9f_application_execution(
                state["application_id"]
            )["current_stage"],
            "source_preparation",
        )

    def test_strict_phase8_reuse_does_not_rerun_phase8(self) -> None:
        state = self._session("global_blueprint")
        with patch.object(
            execution_manager,
            "build_phase8_verification",
            side_effect=AssertionError("Phase 8 should have been inherited"),
        ):
            result = self._execute(state["application_id"])
        self.assertEqual(
            result["execution"]["phase8_mode"],
            "strict_inherited_source_phase8",
        )

    def test_incompatible_inherited_phase8_reruns_existing_phase8(self) -> None:
        state = self._session("global_blueprint")
        blueprint = state["blueprint"]
        source_application_id = blueprint["source_application_id"]
        connection = tailoring_version_manager._connect()
        try:
            row = connection.execute(
                """
                SELECT id, result_json FROM application_tailoring_verifications
                WHERE application_id=?
                """,
                (source_application_id,),
            ).fetchone()
            payload = copy.deepcopy(json.loads(row["result_json"]))
            payload["phase8_version"] = "historical-phase8-version"
            connection.execute(
                """
                UPDATE application_tailoring_verifications
                SET phase8_version=?, result_json=? WHERE id=?
                """,
                (
                    "historical-phase8-version",
                    json.dumps(payload),
                    int(row["id"]),
                ),
            )
            connection.commit()
        finally:
            connection.close()
        original = execution_manager.build_phase8_verification
        calls = []

        def counted(**kwargs):
            calls.append(kwargs)
            return original(**kwargs)

        with patch.object(
            execution_manager,
            "build_phase8_verification",
            side_effect=counted,
        ):
            result = self._execute(state["application_id"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            result["execution"]["phase8_mode"],
            "executed_current_jd_phase8",
        )

    def test_phase8_failure_preserves_result_and_retry_reuses_it(self) -> None:
        state = self._session("base_resume")
        application_id = state["application_id"]
        with patch.object(
            execution_manager,
            "build_phase8_verification",
            side_effect=RuntimeError("injected Phase 8 failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected Phase 8"):
                self._execute(application_id)
        failed = execution_manager.get_phase9f_application_execution(application_id)
        self.assertEqual(failed["current_stage"], "phase8")
        self.assertTrue(failed["application_result_id"])
        result_id = failed["application_result_id"]
        self.assertIsNotNone(get_application_resume_result(result_id))

        with patch.object(
            execution_manager,
            "_resolve_exact_source",
            side_effect=AssertionError("Phase 8 retry must not prepare the source again"),
        ):
            retried = self._execute(application_id)
        self.assertEqual(retried["execution"]["status"], "completed")
        self.assertEqual(
            retried["application_result"]["application_result_id"], result_id
        )
        self.assertEqual(len(list_application_resume_results(application_id)), 1)

    def test_source_failure_retry_uses_same_session_and_execution(self) -> None:
        state = self._session("global_blueprint")
        application_id = state["application_id"]
        original = execution_manager._resolve_exact_source
        with patch.object(
            execution_manager,
            "_resolve_exact_source",
            side_effect=Phase9FEExecutionError(
                "injected source failure",
                code="injected_source_failure",
            ),
        ):
            with self.assertRaisesRegex(Phase9FEExecutionError, "injected source"):
                self._execute(application_id)
        failed = execution_manager.get_phase9f_application_execution(application_id)
        with patch.object(
            execution_manager,
            "_resolve_exact_source",
            side_effect=original,
        ):
            retried = self._execute(application_id)
        self.assertEqual(retried["execution"]["execution_id"], failed["execution_id"])
        self.assertEqual(self._count("applications"), 2)

    def test_zero_cost_diagnostics_and_verification_persist_once(self) -> None:
        state = self._session("base_resume")
        result = self._execute(state["application_id"])
        self.assertEqual(
            result["zero_cost_diagnostics"],
            {
                "analysis_model_call_count": 0,
                "chatbot_model_call_count": 0,
                "embedding_call_count": 0,
                "chroma_read_count": 0,
                "chroma_write_count": 0,
                "resume_generation_call_count": 0,
                "content_rewrite_call_count": 0,
                "content_changing_fit_call_count": 0,
            },
        )
        verifications = list_application_result_verifications(
            result["application_result"]["application_result_id"]
        )
        self.assertEqual(len(verifications), 1)
        self.assertEqual(verifications[0]["model_call_count"], 0)
        self.assertEqual(verifications[0]["embedding_call_count"], 0)
        self.assertEqual(
            result["execution"]["execution_version"], PHASE9F_E_VERSION
        )

    def test_minor_confirmation_fails_before_creating_execution_or_result(self) -> None:
        state = create_d_reuse_session(
            self.database_path,
            source_type="base_resume",
            artifact_root=self.artifact_root,
            confirmed_intensity="minor",
        )
        with self.assertRaisesRegex(
            Phase9FEExecutionError,
            "cannot execute a Minor or Full confirmation",
        ):
            self._execute(state["application_id"])
        self.assertIsNone(
            execution_manager.get_phase9f_application_execution(
                state["application_id"]
            )
        )
        self.assertEqual(list_application_resume_results(state["application_id"]), [])


if __name__ == "__main__":
    unittest.main()

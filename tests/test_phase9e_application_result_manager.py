from __future__ import annotations

import sqlite3
import tempfile
import unittest
import json
import hashlib
from pathlib import Path

from database import db_manager, jd_library_manager, tailoring_version_manager
from database.application_blueprint_manager import (
    evaluate_and_bind_application_blueprint,
    set_application_blueprint_workflow_action,
)
from database.application_resume_result_manager import (
    create_editable_copy_from_current_application_result,
    create_or_reuse_current_application_result,
    get_current_application_resume_result,
    init_application_resume_results,
    list_application_resume_result_events,
    list_application_resume_results,
    verify_current_application_result,
)
from database.tailoring_generation_control import list_tailoring_generations
from database.tailoring_verification_manager import list_tailoring_verifications
from database.jd_library_manager import get_exact_job_description_for_application
from rag.jd_identity import build_job_identity
from tailoring.phase9e_application_result import (
    MODE_APPROVED_SNAPSHOT_REUSE,
    STATUS_REUSED_APPROVED,
    STATUS_REUSED_UNCHANGED_PENDING,
    Phase9EApplicationResultError,
)
from tests.phase9e_test_support import seed_phase9e_database
from resume_builder.immutable_snapshot_docx import (
    materialise_immutable_snapshot_docx,
)


class Phase9EApplicationResultManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.old_db = db_manager.DB_PATH
        self.old_jd = jd_library_manager.DB_PATH
        self.old_tailoring = tailoring_version_manager.DB_PATH
        self.database_path = self.root / "result.sqlite"
        self.state = seed_phase9e_database(
            self.database_path, different_original=True
        )
        self.blueprint = self.state["blueprint"]
        self.artifact_root = self.root / "application-results"

    def tearDown(self) -> None:
        db_manager.DB_PATH = self.old_db
        jd_library_manager.DB_PATH = self.old_jd
        tailoring_version_manager.DB_PATH = self.old_tailoring
        self.temporary.cleanup()

    def _bind_exact_source(self) -> None:
        evaluate_and_bind_application_blueprint(
            application_id=94,
            scope_replacement_confirmed=True,
            selected_source="global_blueprint",
            selected_blueprint_id=self.blueprint["blueprint_id"],
            selection_mode="recommended",
            actor_label="Result test",
        )
        set_application_blueprint_workflow_action(
            application_id=94,
            workflow_action="use_blueprint_unchanged",
            actor_label="Result test",
        )

    def _create(self):
        return create_or_reuse_current_application_result(
            application_id=94,
            actor_label="Result test",
            artifact_root=self.artifact_root,
        )

    def _link_revised_same_family_jd(self) -> None:
        current = get_exact_job_description_for_application(94)
        raw_text = current["raw_text"] + "\nRevised same-family target scope."
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
                    current["library_jd_id"], identity.source_version_id,
                    raw_text, json.dumps(current["jd_profile"]),
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

    def test_schema_is_additive_and_idempotent(self):
        init_application_resume_results()
        init_application_resume_results()
        connection = sqlite3.connect(self.database_path)
        try:
            tables = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            connection.close()
        self.assertTrue(
            {
                "application_resume_results",
                "application_resume_result_state",
                "application_resume_result_artifacts",
                "application_resume_result_verifications",
                "application_resume_result_events",
            }.issubset(tables)
        )

    def test_application94_exact_source_reuses_one_immutable_result_without_draft(self):
        self._bind_exact_source()
        before = list_tailoring_generations(94)
        first = self._create()
        after_first = list_tailoring_generations(94)
        second = self._create()
        after_second = list_tailoring_generations(94)

        result = first["application_result"]
        self.assertEqual(first["cache_status"], "miss")
        self.assertEqual(second["cache_status"], "hit")
        self.assertEqual(
            result["application_result_id"],
            second["application_result"]["application_result_id"],
        )
        self.assertEqual(result["generation_mode"], MODE_APPROVED_SNAPSHOT_REUSE)
        self.assertEqual(result["initial_status"], STATUS_REUSED_APPROVED)
        self.assertFalse(result["editable"])
        self.assertFalse(result["content_changed"])
        self.assertEqual(len(before), len(after_first))
        self.assertEqual(len(before), len(after_second))
        self.assertEqual(len(list_application_resume_results(94)), 1)
        current = get_current_application_resume_result(94)
        self.assertEqual(current["state"]["active_output_mode"], "immutable_result")
        self.assertEqual(current["state"]["acceptance_status"], "inherited_source_approval")

    def test_source_fit_phase8_and_original_artifact_are_inherited_read_only(self):
        self._bind_exact_source()
        result = self._create()["application_result"]
        identity = result["semantic_identity"]
        self.assertTrue(identity["inherited_fit"]["fit_one_page"])
        self.assertEqual(
            identity["inherited_phase8"]["verification_fingerprint"],
            self.state["source_verification"]["verification_fingerprint"],
        )
        artifact = next(
            row for row in result["artifacts"] if row["artifact_kind"] == "docx"
        )
        self.assertEqual(artifact["provenance_mode"], "original_approved_artifact")
        self.assertTrue(artifact["is_original_approved_artifact"])
        self.assertTrue(artifact["original_bytes_available"])

    def test_missing_source_artifact_is_explicitly_rematerialized(self):
        self._bind_exact_source()
        self.state["source_artifact_path"].unlink()
        result = self._create()["application_result"]
        artifact = next(
            row for row in result["artifacts"] if row["artifact_kind"] == "docx"
        )
        self.assertEqual(
            artifact["provenance_label"],
            "Re-materialized from immutable blueprint snapshot",
        )
        self.assertFalse(artifact["original_bytes_available"])
        self.assertFalse(artifact["is_original_approved_artifact"])
        self.assertTrue(Path(artifact["materialized_path"]).is_file())

    def test_snapshot_rematerialization_bytes_are_deterministic(self):
        first = self.root / "first.docx"
        second = self.root / "second.docx"
        text = self.state["candidate"]["resume_text_snapshot"]
        materialise_immutable_snapshot_docx(resume_text=text, output_path=first)
        materialise_immutable_snapshot_docx(resume_text=text, output_path=second)
        self.assertEqual(
            hashlib.sha256(first.read_bytes()).hexdigest(),
            hashlib.sha256(second.read_bytes()).hexdigest(),
        )

    def test_corrupt_result_artifact_fails_closed(self):
        self._bind_exact_source()
        result = self._create()["application_result"]
        artifact = next(
            row for row in result["artifacts"] if row["artifact_kind"] == "docx"
        )
        Path(artifact["materialized_path"]).write_bytes(b"corrupt")
        with self.assertRaisesRegex(Phase9EApplicationResultError, "corrupt"):
            get_current_application_resume_result(94)

    def test_editable_copy_is_explicit_and_starts_content_unchanged(self):
        self._bind_exact_source()
        self._create()
        created = create_editable_copy_from_current_application_result(
            application_id=94, actor_label="Result test"
        )
        generations = list_tailoring_generations(94)
        fork = next(
            row for row in generations
            if row["generation_id"] == created["generation_id"]
        )
        self.assertEqual(fork["generation_kind"], "phase9e_editable_fork")
        self.assertFalse(fork["content_changed"])
        self.assertTrue(fork["source_application_result_id"])
        current = get_current_application_resume_result(94)
        self.assertEqual(current["state"]["active_output_mode"], "editable")

    def test_no_model_or_embedding_calls_occur(self):
        self._bind_exact_source()
        result = self._create()["application_result"]
        verification = result["result_snapshot"]["inherited_phase8_verification"]
        self.assertEqual(verification["model_calls"], 0)
        self.assertEqual(verification["embedding_calls"], 0)

    def test_result_events_are_append_only_on_exact_reuse(self):
        self._bind_exact_source()
        self._create()
        self._create()
        events = list_application_resume_result_events(94)
        self.assertEqual(
            [row["event_type"] for row in events],
            ["immutable_result_reused", "immutable_result_created"],
        )

    def test_different_jd_unchanged_result_remains_separately_pending(self):
        self._link_revised_same_family_jd()
        bound = evaluate_and_bind_application_blueprint(
            application_id=94,
            scope_replacement_confirmed=True,
            selected_source="global_blueprint",
            selected_blueprint_id=self.blueprint["blueprint_id"],
            selection_mode="recommended",
            actor_label="Result test",
        )
        self.assertNotEqual(
            bound["decision"]["recommended_tailoring"],
            "reuse_approved_source",
        )
        set_application_blueprint_workflow_action(
            application_id=94,
            workflow_action="use_blueprint_unchanged",
            actor_label="Result test",
        )
        self._create()
        pending = get_current_application_resume_result(94)
        self.assertEqual(
            pending["initial_status"], STATUS_REUSED_UNCHANGED_PENDING
        )
        self.assertEqual(
            pending["state"]["acceptance_status"],
            "pending_application_verification",
        )
        phase8_before = list_tailoring_verifications(94)
        verification = verify_current_application_result(application_id=94)
        phase8_after = list_tailoring_verifications(94)
        self.assertEqual(verification["verification"]["model_calls"], 0)
        self.assertEqual(verification["verification"]["embedding_calls"], 0)
        self.assertEqual(phase8_after, phase8_before)
        still_pending = get_current_application_resume_result(94)
        self.assertEqual(
            still_pending["state"]["acceptance_status"],
            "verified_pending_user_acceptance",
        )


if __name__ == "__main__":
    unittest.main()

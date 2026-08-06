from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db_manager, jd_library_manager, tailoring_version_manager
from database import application_cover_letter_manager as cover_manager
from database.application_blueprint_manager import (
    evaluate_and_bind_application_blueprint,
    set_application_blueprint_workflow_action,
)
from database.application_cover_letter_manager import (
    build_cover_letter_request_identity,
    generate_or_reuse_application_cover_letter,
    get_current_application_cover_letter,
    init_application_cover_letters,
    list_application_cover_letters,
)
from database.application_resume_output_manager import resolve_application_resume_output
from database.application_resume_result_manager import (
    build_application_result_debug_bundle,
    create_editable_copy_from_current_application_result,
    create_or_reuse_current_application_result,
    get_current_application_resume_result,
)
from database.jd_library_manager import get_exact_job_description_for_application
from database.tailoring_generation_control import list_tailoring_generations
from database.tailoring_version_manager import save_application_tailoring_generation
from rag.jd_identity import build_job_identity
from tailoring.phase9e_blueprint_selection import fingerprint_value
from tests.phase9e_test_support import seed_phase9e_database


class ApplicationOutputIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.old_db = db_manager.DB_PATH
        self.old_jd = jd_library_manager.DB_PATH
        self.old_tailoring = tailoring_version_manager.DB_PATH
        self.database_path = self.root / "application-output.sqlite"
        self.state = seed_phase9e_database(
            self.database_path, different_original=True
        )
        self.artifact_root = self.root / "application-results"
        self._bind_and_create_result()
        init_application_cover_letters()

    def tearDown(self) -> None:
        db_manager.DB_PATH = self.old_db
        jd_library_manager.DB_PATH = self.old_jd
        tailoring_version_manager.DB_PATH = self.old_tailoring
        self.temporary.cleanup()

    def _bind_and_create_result(self) -> dict:
        evaluate_and_bind_application_blueprint(
            application_id=94,
            scope_replacement_confirmed=True,
            selected_source="global_blueprint",
            selected_blueprint_id=self.state["blueprint"]["blueprint_id"],
            selection_mode="recommended",
            actor_label="Output integration test",
        )
        set_application_blueprint_workflow_action(
            application_id=94,
            workflow_action="use_blueprint_unchanged",
            actor_label="Output integration test",
        )
        return create_or_reuse_current_application_result(
            application_id=94,
            actor_label="Output integration test",
            artifact_root=self.artifact_root,
        )["application_result"]

    def _link_revised_jd(self) -> None:
        current = get_exact_job_description_for_application(94)
        raw_text = current["raw_text"] + "\nChanged cover-letter target scope."
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

    @staticmethod
    def _generator(calls: list[tuple[str, str, str]]):
        def generate(system: str, user: str, model: str):
            calls.append((system, user, model))
            return (
                "Persisted output cover letter.",
                {
                    "model_id": model,
                    "model_calls": 1,
                    "embedding_calls": 0,
                    "summary": {"call_count": 1},
                },
            )

        return generate

    def test_debug_bundle_contains_complete_immutable_provenance(self):
        result = get_current_application_resume_result(94)
        bundle = build_application_result_debug_bundle(
            result["application_result_id"]
        )

        self.assertEqual(
            bundle["application_result"]["application_result_id"],
            result["application_result_id"],
        )
        self.assertEqual(
            bundle["application_result"]["result_fingerprint"],
            result["result_fingerprint"],
        )
        self.assertTrue(bundle["application_result"]["complete_snapshot"])
        self.assertTrue(bundle["phase9e"]["decision"])
        self.assertTrue(bundle["phase9e"]["semantic_identity"])
        self.assertTrue(bundle["phase9e"]["workflow_action"])
        self.assertEqual(
            bundle["phase9d_blueprint"]["blueprint_id"],
            result["blueprint_id"],
        )
        self.assertTrue(
            bundle["phase9d_blueprint"]["complete_frozen_snapshot"]
        )
        self.assertTrue(bundle["frozen_resume"]["resume_profile_snapshot"])
        self.assertTrue(bundle["frozen_resume"]["resume_text_snapshot"])
        self.assertTrue(bundle["source_approved_generation"])
        self.assertTrue(bundle["inherited_fit_identity"])
        self.assertTrue(bundle["inherited_phase8_verification"])
        self.assertTrue(bundle["current_jd"]["identity"])
        self.assertTrue(
            bundle["current_jd"]["stable_input_provenance"][
                "stable_input_fingerprint"
            ]
        )
        self.assertTrue(bundle["append_only_application_result_events"])
        self.assertEqual(bundle["call_totals"]["model_calls"], 0)
        self.assertEqual(bundle["call_totals"]["embedding_calls"], 0)
        self.assertFalse(
            bundle["authority_policy"]["mutable_session_state_included"]
        )
        for artifact in bundle["artifacts"]:
            self.assertTrue(artifact["materialized_path"])
            self.assertEqual(len(artifact["artifact_sha256"]), 64)
            self.assertGreater(artifact["artifact_size"], 0)
        json.dumps(bundle, ensure_ascii=False, default=str)

    def test_cover_letter_schema_is_additive_and_idempotent(self):
        init_application_cover_letters()
        init_application_cover_letters()
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
        self.assertTrue(
            {
                "application_cover_letter_results",
                "application_cover_letter_state",
                "application_cover_letter_events",
            }.issubset(tables)
        )

    def test_cover_letter_uses_immutable_result_and_exactly_reuses_it(self):
        result = get_current_application_resume_result(94)
        before_snapshot = json.dumps(
            result["result_snapshot"], sort_keys=True, ensure_ascii=False
        ).encode("utf-8")
        before_artifacts = {
            row["artifact_kind"]: Path(row["materialized_path"]).read_bytes()
            for row in result["artifacts"]
        }
        before_drafts = [
            row["generation_id"] for row in list_tailoring_generations(94)
        ]
        connection = sqlite3.connect(self.database_path)
        try:
            before_db_payload = connection.execute(
                """
                SELECT semantic_identity_json, result_snapshot_json
                FROM application_resume_results
                WHERE application_result_id = ?
                """,
                (result["application_result_id"],),
            ).fetchone()
        finally:
            connection.close()
        calls: list[tuple[str, str, str]] = []
        generator = self._generator(calls)

        first = generate_or_reuse_application_cover_letter(
            application_id=94,
            model_id="fixture-cover-model",
            generator=generator,
        )
        second = generate_or_reuse_application_cover_letter(
            application_id=94,
            model_id="fixture-cover-model",
            generator=generator,
        )

        self.assertEqual(first["cache_status"], "miss")
        self.assertEqual(second["cache_status"], "hit")
        self.assertEqual(
            first["cover_letter"]["cover_letter_id"],
            second["cover_letter"]["cover_letter_id"],
        )
        self.assertEqual(len(calls), 1)
        self.assertIn("QueryAI", calls[0][1])
        self.assertNotIn("Original Application Project", calls[0][1])
        self.assertIn(
            self.state["saved_jds"][0]["raw_text"].strip(), calls[0][1]
        )
        self.assertEqual(len(list_application_cover_letters(94)), 1)
        self.assertEqual(
            [row["generation_id"] for row in list_tailoring_generations(94)],
            before_drafts,
        )
        after = get_current_application_resume_result(94)
        self.assertEqual(
            json.dumps(
                after["result_snapshot"], sort_keys=True, ensure_ascii=False
            ).encode("utf-8"),
            before_snapshot,
        )
        self.assertEqual(
            {
                row["artifact_kind"]: Path(row["materialized_path"]).read_bytes()
                for row in after["artifacts"]
            },
            before_artifacts,
        )
        connection = sqlite3.connect(self.database_path)
        try:
            after_db_payload = connection.execute(
                """
                SELECT semantic_identity_json, result_snapshot_json
                FROM application_resume_results
                WHERE application_result_id = ?
                """,
                (result["application_result_id"],),
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(after_db_payload, before_db_payload)
        bundle = build_application_result_debug_bundle(
            result["application_result_id"]
        )
        self.assertEqual(len(bundle["application_result_cover_letters"]), 1)
        self.assertEqual(bundle["call_totals"]["cover_letter_model_calls"], 1)
        self.assertEqual(bundle["call_totals"]["embedding_calls"], 0)

    def test_changed_jd_invalidates_cover_letter_reuse(self):
        calls: list[tuple[str, str, str]] = []
        generator = self._generator(calls)
        first = generate_or_reuse_application_cover_letter(
            application_id=94,
            model_id="fixture-cover-model",
            generator=generator,
        )
        self._link_revised_jd()

        stale = get_current_application_cover_letter(
            94, model_id="fixture-cover-model"
        )
        self.assertEqual(stale["scope_status"], "stale")
        second = generate_or_reuse_application_cover_letter(
            application_id=94,
            model_id="fixture-cover-model",
            generator=generator,
        )
        self.assertEqual(second["cache_status"], "miss")
        self.assertNotEqual(
            first["cover_letter"]["input_fingerprint"],
            second["cover_letter"]["input_fingerprint"],
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(list_application_cover_letters(94)), 2)

    def test_result_fingerprint_and_policy_are_semantic_cache_inputs(self):
        output = resolve_application_resume_output(94)
        first_identity = build_cover_letter_request_identity(
            output=output, model_id="fixture-cover-model"
        )
        changed_output = copy.deepcopy(output)
        changed_output["source_fingerprint"] = "changed-result-fingerprint"
        changed_output["output_fingerprint"] = fingerprint_value(
            {"changed_result": True, "prior": output["output_fingerprint"]}
        )
        changed_identity = build_cover_letter_request_identity(
            output=changed_output, model_id="fixture-cover-model"
        )
        self.assertNotEqual(
            fingerprint_value(first_identity),
            fingerprint_value(changed_identity),
        )

        calls: list[tuple[str, str, str]] = []
        generate_or_reuse_application_cover_letter(
            application_id=94,
            model_id="fixture-cover-model",
            generator=self._generator(calls),
        )
        with patch.object(
            cover_manager,
            "COVER_LETTER_POLICY_VERSION",
            "application-output-cover-letter-policy-v2-test",
        ):
            stale = get_current_application_cover_letter(
                94, model_id="fixture-cover-model"
            )
            self.assertEqual(stale["scope_status"], "stale")

    def test_resume_docx_download_artifact_resolves_with_hash(self):
        output = resolve_application_resume_output(94)
        docx = next(
            row for row in output["artifacts"] if row["artifact_kind"] == "docx"
        )
        docx_path = Path(docx["materialized_path"])
        self.assertEqual(
            docx["artifact_sha256"],
            hashlib.sha256(docx_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(docx["artifact_size"], docx_path.stat().st_size)

    def test_resolver_supports_editable_and_explicit_historical_outputs(self):
        result = get_current_application_resume_result(94)
        created = create_editable_copy_from_current_application_result(
            application_id=94,
            actor_label="Output integration test",
        )
        editable = resolve_application_resume_output(94)
        self.assertEqual(editable["output_kind"], "editable_tailoring_draft")
        self.assertEqual(editable["source_id"], created["generation_id"])
        self.assertEqual(
            editable["source_provenance"]["baseline"]["source_type"],
            "immutable_application_result",
        )
        self.assertEqual(
            editable["source_provenance"]["baseline"][
                "application_result_id"
            ],
            result["application_result_id"],
        )
        with self.assertRaisesRegex(ValueError, "historical"):
            resolve_application_resume_output(
                94, application_result_id=result["application_result_id"]
            )
        historical = resolve_application_resume_output(
            94,
            application_result_id=result["application_result_id"],
            allow_historical=True,
        )
        self.assertTrue(historical["is_historical"])
        self.assertFalse(historical["editable"])
        with self.assertRaisesRegex(ValueError, "historical"):
            generate_or_reuse_application_cover_letter(
                application_id=94,
                application_result_id=result["application_result_id"],
                model_id="fixture-cover-model",
                generator=self._generator([]),
            )
        explicit_letter = generate_or_reuse_application_cover_letter(
            application_id=94,
            application_result_id=result["application_result_id"],
            allow_historical=True,
            model_id="fixture-cover-model",
            generator=self._generator([]),
        )
        self.assertEqual(
            explicit_letter["cover_letter"]["resume_output_id"],
            result["application_result_id"],
        )

    def test_source_pdf_is_preserved_when_available_on_result_creation(self):
        # Build a second temporary fixture so the PDF exists before the immutable
        # result is materialized; no live or historical row is rewritten.
        second_db = self.root / "application-output-pdf.sqlite"
        second_state = seed_phase9e_database(second_db, different_original=True)
        pdf_path = self.root / "source-approved.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n% immutable fixture\n%%EOF\n")
        save_application_tailoring_generation(
            application_id=94,
            generation_id=second_state["source_generation_id"],
            pdf_path=pdf_path,
        )
        self.state = second_state
        self.artifact_root = self.root / "application-results-with-pdf"
        result = self._bind_and_create_result()
        output = resolve_application_resume_output(94)
        pdf = next(
            row for row in output["artifacts"] if row["artifact_kind"] == "pdf"
        )
        materialized = Path(pdf["materialized_path"])
        self.assertEqual(result["application_result_id"], output["source_id"])
        self.assertEqual(materialized.read_bytes(), pdf_path.read_bytes())
        self.assertEqual(
            pdf["artifact_sha256"],
            hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(pdf["artifact_size"], pdf_path.stat().st_size)


if __name__ == "__main__":
    unittest.main()

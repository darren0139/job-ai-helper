from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from docx import Document

from database import global_master_resume_manager as manager
from database import tailoring_version_manager as base_manager
from parse import _MAX_RESUME_CHARS, read_resume_docx
from tailoring.phase9f_master_resume import (
    PHASE9F_MASTER_CONTENT_POLICY_VERSION,
    PHASE9F_MASTER_RESUME_VERSION,
    PHASE9F_MASTER_VERSION_POLICY_VERSION,
    Phase9FMasterResumeError,
    analyse_and_prepare_master_resume,
    attach_preview_pdf,
    build_prepared_master_resume_snapshot,
    inspect_master_resume_upload,
    prepare_master_resume_from_reusable_profile,
    sha256_bytes,
    sha256_text,
)


PROFILE = {
    "name": "Example Candidate",
    "contact": {
        "email": "candidate@example.test",
        "phone": "",
        "linkedin": "",
        "github": "",
        "portfolio": "",
    },
    "summary": "Builds reliable software products.",
    "education": [
        {
            "school": "Example University",
            "degree": "BSc",
            "graduation_date": "2026",
            "courses": [],
        }
    ],
    "experience": [
        {
            "company": "Example Co",
            "title": "Engineer",
            "date": "2025",
            "bullets": ["Built a deterministic application workflow."],
        }
    ],
    "projects": [
        {
            "title": "Job AI Helper",
            "date": "2026",
            "bullets": ["Implemented immutable resume provenance."],
        }
    ],
    "skills": {
        "languages": ["Python"],
        "frameworks": [],
        "tools": ["SQLite"],
        "concepts": [],
        "platforms": [],
    },
}


def inspection(
    *,
    artifact_bytes: bytes = b"fixture-docx-bytes-v1",
    resume_text: str = "Example Candidate\n" + ("Complete resume evidence. " * 20),
) -> dict:
    return {
        "inspection_fingerprint": "inspection-fixture",
        "artifact_sha256": sha256_bytes(artifact_bytes),
        "artifact_type": "docx",
        "artifact_size_bytes": len(artifact_bytes),
        "original_filename": "resume.docx",
        "media_type": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        "artifact_bytes": artifact_bytes,
        "resume_text": resume_text,
        "resume_text_sha256": sha256_text(resume_text),
        "resume_text_char_count": len(resume_text),
        "extraction_method": "test_complete_text",
    }


def prepared(
    inspected: dict,
    *,
    current: dict | None = None,
    profile: dict | None = None,
) -> dict:
    return build_prepared_master_resume_snapshot(
        inspection=inspected,
        structured_profile=deepcopy(profile or PROFILE),
        extraction_provenance={
            "method": "zero_cost_test_fixture",
            "requested_model": "",
            "response_model": "",
            "extraction_policy_version": "fixture",
            "call_count": 0,
            "api_usage": {"call_count": 0},
            "embedding_call_count": 0,
        },
        current_master=current,
        preparation_mode="zero_cost_test_fixture",
    )


class Phase9FMasterResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_path = base_manager.DB_PATH
        self.database_path = Path(self.temporary.name) / "master.sqlite"
        base_manager.DB_PATH = self.database_path
        manager.init_global_master_resume_registry()

    def tearDown(self) -> None:
        base_manager.DB_PATH = self.old_path
        self.temporary.cleanup()

    def _counts(self) -> dict[str, int]:
        connection = sqlite3.connect(self.database_path)
        try:
            return {
                table: int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                )
                for table in (
                    "global_master_resume_versions",
                    "global_master_resume_artifacts",
                    "global_master_resume_state",
                    "global_master_resume_events",
                )
            }
        finally:
            connection.close()

    def test_additive_schema_and_lookup_indexes_are_idempotent(self):
        manager.init_global_master_resume_registry()
        connection = sqlite3.connect(self.database_path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            indexes = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )
            }
        finally:
            connection.close()
        self.assertTrue(
            {
                "global_master_resume_versions",
                "global_master_resume_artifacts",
                "global_master_resume_state",
                "global_master_resume_events",
            }.issubset(tables)
        )
        self.assertIn("idx_master_resume_artifact_sha", indexes)
        self.assertIn("idx_master_resume_text_sha", indexes)
        self.assertEqual(sum(self._counts().values()), 0)

    def test_prepare_and_commit_are_separate_and_commit_is_atomic(self):
        candidate = prepared(inspection())
        self.assertEqual(sum(self._counts().values()), 0)

        receipt = manager.commit_prepared_global_master_resume(
            candidate,
            display_name="Primary Master Resume",
        )
        self.assertEqual(receipt["outcome"], "master_set")
        self.assertEqual(
            self._counts(),
            {
                "global_master_resume_versions": 1,
                "global_master_resume_artifacts": 1,
                "global_master_resume_state": 1,
                "global_master_resume_events": 1,
            },
        )
        current = manager.get_current_global_master_resume()
        self.assertEqual(current["format_version"], PHASE9F_MASTER_RESUME_VERSION)
        self.assertEqual(
            current["content_policy_version"],
            PHASE9F_MASTER_CONTENT_POLICY_VERSION,
        )
        self.assertEqual(
            current["version_policy_version"],
            PHASE9F_MASTER_VERSION_POLICY_VERSION,
        )
        self.assertEqual(current["resume_text"], candidate["resume_text"])
        self.assertEqual(current["structured_profile"], PROFILE)
        artifact = manager.get_global_master_resume_artifact(
            current["master_version_id"]
        )
        self.assertEqual(artifact["artifact_bytes"], candidate["artifact_bytes"])
        self.assertTrue(artifact["authoritative"])

    def test_failed_commit_rolls_back_and_same_preparation_retries(self):
        candidate = prepared(inspection())
        original_insert = manager._insert_prepared_version
        with patch.object(
            manager,
            "_insert_prepared_version",
            side_effect=RuntimeError("injected persistence failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                manager.commit_prepared_global_master_resume(candidate)
        self.assertEqual(sum(self._counts().values()), 0)

        with patch.object(
            manager,
            "_insert_prepared_version",
            wraps=original_insert,
        ) as insertion:
            receipt = manager.commit_prepared_global_master_resume(candidate)
        self.assertTrue(receipt["created_new_version"])
        self.assertEqual(insertion.call_count, 1)

    def test_model_preparation_happens_before_any_write_transaction(self):
        inspected = inspection()
        model_calls = 0

        def fake_extract(_text: str) -> dict:
            nonlocal model_calls
            model_calls += 1
            connection = sqlite3.connect(self.database_path)
            try:
                self.assertFalse(connection.in_transaction)
            finally:
                connection.close()
            return deepcopy(PROFILE)

        safe_call = {
            "requested_model": "openai/test",
            "response_model": "openai/test-response",
            "elapsed_seconds": 0.25,
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "response_cost_usd": 0.001,
            "authorization": "secret-value-must-not-persist",
        }
        with patch(
            "tailoring.phase9f_master_resume.reset_call_ledger"
        ), patch(
            "tailoring.phase9f_master_resume.drain_call_ledger",
            return_value=[safe_call],
        ):
            candidate = analyse_and_prepare_master_resume(
                inspection=inspected,
                current_master=None,
                extract_profile_fn=fake_extract,
                requested_model="openai/test",
            )
        self.assertEqual(model_calls, 1)
        self.assertEqual(sum(self._counts().values()), 0)
        encoded = json.dumps(candidate["extraction_provenance"])
        self.assertNotIn("authorization", encoded.lower())
        self.assertNotIn("secret-value", encoded)
        self.assertEqual(
            candidate["extraction_provenance"]["api_usage"]["call_count"],
            1,
        )
        with patch.object(
            manager,
            "_insert_prepared_version",
            side_effect=RuntimeError("retryable database failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "retryable"):
                manager.commit_prepared_global_master_resume(candidate)
        self.assertEqual(sum(self._counts().values()), 0)
        manager.commit_prepared_global_master_resume(candidate)
        self.assertEqual(model_calls, 1)

    def test_exact_current_reuse_creates_event_not_version(self):
        first = manager.commit_prepared_global_master_resume(
            prepared(inspection())
        )["master"]
        reusable = manager.get_current_global_master_resume()
        same = prepare_master_resume_from_reusable_profile(
            inspection=inspection(),
            reusable_master=reusable,
            current_master=reusable,
        )
        receipt = manager.commit_prepared_global_master_resume(
            same,
            display_name="Identity-excluded display change",
        )
        self.assertEqual(receipt["outcome"], "exact_current_reused")
        self.assertEqual(receipt["master"]["master_version_id"], first["master_version_id"])
        self.assertEqual(self._counts()["global_master_resume_versions"], 1)
        self.assertEqual(self._counts()["global_master_resume_events"], 2)
        self.assertEqual(
            manager.get_current_global_master_resume()["display_name"],
            "Base Resume",
        )

    def test_cost_timing_model_and_actor_metadata_do_not_change_content_identity(self):
        inspected = inspection()
        first = build_prepared_master_resume_snapshot(
            inspection=inspected,
            structured_profile=deepcopy(PROFILE),
            extraction_provenance={
                "method": "explicit_model_profile_extraction",
                "requested_model": "openai/model-a",
                "response_model": "openai/model-a-2026",
                "elapsed_seconds": 1.0,
                "call_count": 1,
                "api_usage": {"total_tokens": 100, "estimated_cost_usd": 0.01},
            },
            current_master=None,
            preparation_mode="novel_text_model_extraction",
        )
        second = build_prepared_master_resume_snapshot(
            inspection=inspected,
            structured_profile=deepcopy(PROFILE),
            extraction_provenance={
                "method": "explicit_model_profile_extraction",
                "requested_model": "openai/model-b",
                "response_model": "openai/model-b-2027",
                "elapsed_seconds": 99.0,
                "call_count": 1,
                "api_usage": {"total_tokens": 9999, "estimated_cost_usd": 99.0},
            },
            current_master=None,
            preparation_mode="novel_text_model_extraction",
        )
        self.assertEqual(
            first["master_content_fingerprint"],
            second["master_content_fingerprint"],
        )
        self.assertNotEqual(
            first["prepared_snapshot_fingerprint"],
            second["prepared_snapshot_fingerprint"],
        )

    def test_exact_text_different_artifact_and_historical_reactivation_append_versions(self):
        original_inspection = inspection()
        original = manager.commit_prepared_global_master_resume(
            prepared(original_inspection)
        )["master"]
        current = manager.get_current_global_master_resume()

        changed_artifact = inspection(
            artifact_bytes=b"different-docx-container-same-visible-text",
            resume_text=original_inspection["resume_text"],
        )
        text_reuse = prepare_master_resume_from_reusable_profile(
            inspection=changed_artifact,
            reusable_master=current,
            current_master=current,
        )
        self.assertEqual(
            text_reuse["extraction_provenance"]["call_count"], 0
        )
        second = manager.commit_prepared_global_master_resume(text_reuse)["master"]
        self.assertEqual(second["version_number"], 2)
        self.assertNotEqual(
            second["master_content_fingerprint"],
            original["master_content_fingerprint"],
        )

        historical = manager.get_global_master_resume(original["master_version_id"])
        current = manager.get_current_global_master_resume()
        historical_reuse = prepare_master_resume_from_reusable_profile(
            inspection=original_inspection,
            reusable_master=historical,
            current_master=current,
        )
        third = manager.commit_prepared_global_master_resume(historical_reuse)["master"]
        self.assertEqual(third["version_number"], 3)
        self.assertNotEqual(third["master_version_id"], original["master_version_id"])
        self.assertEqual(
            third["master_content_fingerprint"],
            original["master_content_fingerprint"],
        )
        self.assertEqual(self._counts()["global_master_resume_versions"], 3)

    def test_artifact_and_text_sha_lookups_and_preview_blob(self):
        candidate = attach_preview_pdf(
            prepared(inspection()),
            b"%PDF-1.4\nfixture preview\n%%EOF",
        )
        master = manager.commit_prepared_global_master_resume(candidate)["master"]
        by_artifact = manager.find_master_resume_by_artifact_sha256(
            candidate["artifact_sha256"]
        )
        by_text = manager.find_master_resume_by_text_sha256(
            candidate["resume_text_sha256"]
        )
        self.assertEqual(by_artifact["master_version_id"], master["master_version_id"])
        self.assertEqual(by_text["master_version_id"], master["master_version_id"])
        preview = manager.get_global_master_resume_artifact(
            master["master_version_id"], "preview_pdf"
        )
        self.assertFalse(preview["authoritative"])
        self.assertEqual(preview["sha256"], candidate["preview_pdf_sha256"])

    def test_changed_current_pointer_fails_closed(self):
        stale = prepared(inspection(artifact_bytes=b"stale-prepared"))
        manager.commit_prepared_global_master_resume(
            prepared(inspection(artifact_bytes=b"concurrent-current"))
        )
        with self.assertRaisesRegex(
            Phase9FMasterResumeError,
            "changed after preparation",
        ):
            manager.commit_prepared_global_master_resume(stale)
        self.assertEqual(self._counts()["global_master_resume_versions"], 1)

    def test_inconsistent_current_pointer_fails_closed(self):
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute(
                """
                INSERT INTO global_master_resume_state (
                    singleton_id, current_master_version_id,
                    current_master_version_fingerprint, updated_at
                ) VALUES (1, 'missing-version', 'missing-fingerprint', '2026-08-14')
                """
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(
            Phase9FMasterResumeError,
            "references a missing version",
        ):
            manager.get_current_global_master_resume()

    def test_remove_current_preserves_history_artifacts_and_next_version_number(self):
        first_receipt = manager.commit_prepared_global_master_resume(
            prepared(inspection())
        )
        first = deepcopy(first_receipt["master"])
        first_artifact = manager.get_global_master_resume_artifact(
            first["master_version_id"]
        )
        first_counts = self._counts()

        removed = manager.clear_current_global_master_resume(
            expected_master_version_id=first["master_version_id"],
            expected_master_version_fingerprint=first[
                "master_version_fingerprint"
            ],
        )
        self.assertEqual(removed["outcome"], "current_master_removed")
        self.assertTrue(removed["removed_current"])
        self.assertIsNone(manager.get_current_global_master_resume())
        self.assertEqual(
            self._counts(),
            {
                "global_master_resume_versions": 1,
                "global_master_resume_artifacts": 1,
                "global_master_resume_state": 0,
                "global_master_resume_events": 2,
            },
        )
        historical = manager.get_global_master_resume(first["master_version_id"])
        self.assertEqual(historical, first)
        historical_artifact = manager.get_global_master_resume_artifact(
            first["master_version_id"]
        )
        self.assertEqual(
            historical_artifact["artifact_bytes"],
            first_artifact["artifact_bytes"],
        )
        self.assertEqual(
            historical_artifact["sha256"],
            first_artifact["sha256"],
        )

        no_current = manager.clear_current_global_master_resume()
        self.assertEqual(no_current["outcome"], "no_current_master")
        self.assertFalse(no_current["removed_current"])
        self.assertEqual(self._counts()["global_master_resume_events"], 2)

        second_inspection = inspection(
            artifact_bytes=b"fixture-docx-bytes-v2",
            resume_text="Example Candidate\\nUpdated general resume evidence.",
        )
        second = manager.commit_prepared_global_master_resume(
            prepared(second_inspection, current=None)
        )["master"]
        self.assertEqual(second["version_number"], 2)
        self.assertEqual(
            manager.get_current_global_master_resume()["master_version_id"],
            second["master_version_id"],
        )
        self.assertEqual(
            manager.get_global_master_resume(first["master_version_id"]),
            first,
        )
        self.assertEqual(first_counts["global_master_resume_versions"], 1)

    def test_remove_current_fails_closed_if_pointer_changed(self):
        first = manager.commit_prepared_global_master_resume(
            prepared(inspection())
        )["master"]
        manager.clear_current_global_master_resume(
            expected_master_version_id=first["master_version_id"],
            expected_master_version_fingerprint=first[
                "master_version_fingerprint"
            ],
        )
        second = manager.commit_prepared_global_master_resume(
            prepared(
                inspection(
                    artifact_bytes=b"replacement-after-clear",
                    resume_text="Replacement after clear.",
                )
            )
        )["master"]
        with self.assertRaisesRegex(
            Phase9FMasterResumeError,
            "changed before removal",
        ):
            manager.clear_current_global_master_resume(
                expected_master_version_id=first["master_version_id"],
                expected_master_version_fingerprint=first[
                    "master_version_fingerprint"
                ],
            )
        self.assertEqual(
            manager.get_current_global_master_resume()["master_version_id"],
            second["master_version_id"],
        )

    def test_artifact_size_limit_fails_before_extraction_or_model(self):
        with patch("tailoring.phase9f_master_resume.read_resume_docx") as parser:
            with self.assertRaisesRegex(Phase9FMasterResumeError, "too large"):
                inspect_master_resume_upload(
                    filename="resume.docx",
                    content=b"12345",
                    artifact_size_limit_bytes=4,
                )
        parser.assert_not_called()
        self.assertEqual(sum(self._counts().values()), 0)

    def test_incomplete_structured_profile_fails_before_persistence(self):
        with self.assertRaisesRegex(
            Phase9FMasterResumeError,
            "complete profile contract",
        ):
            prepared(
                inspection(),
                profile={"name": "Incomplete"},
            )
        self.assertEqual(sum(self._counts().values()), 0)

    def test_legacy_parser_default_truncates_but_master_opt_in_is_complete(self):
        document_path = Path(self.temporary.name) / "long.docx"
        long_text = "A" * (_MAX_RESUME_CHARS + 1200)
        document = Document()
        document.add_paragraph(long_text)
        document.save(document_path)

        legacy = read_resume_docx(str(document_path))
        complete = read_resume_docx(
            str(document_path),
            preserve_complete_text=True,
        )
        self.assertEqual(len(legacy), _MAX_RESUME_CHARS)
        self.assertEqual(complete, long_text)
        self.assertGreater(len(complete), len(legacy))
        inspected = inspect_master_resume_upload(
            filename="long.docx",
            content=document_path.read_bytes(),
            artifact_size_limit_bytes=document_path.stat().st_size + 1,
        )
        self.assertEqual(inspected["resume_text"], long_text)
        manager.commit_prepared_global_master_resume(prepared(inspected))
        self.assertEqual(
            manager.get_current_global_master_resume()["resume_text"],
            long_text,
        )


if __name__ == "__main__":
    unittest.main()

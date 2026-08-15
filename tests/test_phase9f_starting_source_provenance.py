from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tailoring.phase9f_starting_source_provenance import (
    build_blueprint_provenance_debug_bundle,
    canonical_json,
    compact_artifact_resolution,
    load_blueprint_provenance_read_only,
)
from tests.test_phase9f_starting_source_ranking import make_blueprint


def _fixture_blueprint() -> tuple[dict, dict]:
    blueprint = make_blueprint(
        strong=True,
        role_family_id="ai_fullstack_software_engineering",
        role_family_label="AI & Full-Stack Software Engineering",
        marker="provenance",
        historical_score=92,
    )
    raw_jd = "Synthetic exact source JD for deterministic provenance testing."
    raw_sha256 = hashlib.sha256(raw_jd.encode("utf-8")).hexdigest()
    candidate = {
        "phase9b_version": "phase9b-blueprint-candidate-v3",
        "candidate_id": blueprint["candidate_id"],
        "candidate_fingerprint": blueprint["candidate_fingerprint"],
        "source_application_id": 94,
        "source_generation_id": "approved-generation",
        "source_verification_id": "phase8-verification",
        "source_verification_fingerprint": "phase8-fingerprint",
        "role_family": blueprint["role_family_label"],
        "score_summary": {
            "original_resume_score": 32,
            "approved_tailored_score": 92,
            "evidence_potential_score": 41,
        },
        "fit_result": {
            "generation_id": "fit-generation",
            "fit_one_page": True,
            "page_count": 1,
            "docx_path": "approved.docx",
            "pdf_path": "approved.pdf",
        },
        "evaluation_metadata": {
            "source_final_scoring_seed_fingerprint": "seed-fingerprint"
        },
    }
    evaluation = {
        "phase9c_version": "phase9c-cross-jd-evaluation-v1",
        "evaluation_id": blueprint["evaluation_id"],
        "evaluation_fingerprint": blueprint["evaluation_fingerprint"],
        "candidate_scope": {
            "candidate_id": blueprint["candidate_id"],
            "role_family_id": blueprint["role_family_id"],
        },
        "aggregate_result": {
            "provisional": False,
            "mean_score": 92,
        },
        "semantic_identity": {
            "policy": {
                "policy_version": "phase9c-same-family-explicit-scope-v3"
            }
        },
        "selected_jd_scope": [
            {
                "canonical_jd_id": "canonical-jd",
                "source_version_id": "jd-version",
                "raw_jd_sha256": raw_sha256,
                "stable_input_fingerprint": "stable-jd-input",
                "canonical_requirement_fingerprint": "requirement-scope",
            }
        ],
        "per_jd_results": [
            {
                "is_source_jd": True,
                "canonical_jd_id": "canonical-jd",
                "source_version_id": "jd-version",
                "raw_jd_sha256": raw_sha256,
                "stable_input_fingerprint": "stable-jd-input",
                "canonical_requirement_fingerprint": "requirement-scope",
                "deterministic_alignment_score": 92,
            }
        ],
    }
    snapshot = blueprint["blueprint_snapshot"]
    snapshot["phase9b_candidate_semantic_snapshot"] = copy.deepcopy(candidate)
    snapshot["phase9c_evaluation_snapshot"] = copy.deepcopy(evaluation)
    snapshot["phase9c_semantic_identity"] = copy.deepcopy(
        evaluation["semantic_identity"]
    )
    blueprint["activated_at"] = "2026-08-15T00:00:00"
    return blueprint, {
        "candidate": candidate,
        "evaluation": evaluation,
        "raw_jd": raw_jd,
    }


def _create_provenance_database(
    path: Path,
    *,
    include_application: bool = True,
) -> tuple[dict, dict]:
    blueprint, fixture = _fixture_blueprint()
    candidate = fixture["candidate"]
    evaluation = fixture["evaluation"]
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE applications (
                id INTEGER PRIMARY KEY, session_name TEXT, job_title TEXT,
                company TEXT, overall_score INTEGER, created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE application_job_links (
                application_id INTEGER, job_description_id INTEGER,
                source_version_id TEXT, linked_at TEXT
            );
            CREATE TABLE job_descriptions (
                id INTEGER PRIMARY KEY, canonical_jd_id TEXT
            );
            CREATE TABLE job_description_versions (
                job_description_id INTEGER, source_version_id TEXT,
                raw_text TEXT, jd_profile_json TEXT, created_at TEXT
            );
            CREATE TABLE application_tailoring_versions (
                application_id INTEGER, generation_id TEXT,
                fit_result_json TEXT, docx_path TEXT, pdf_path TEXT,
                created_at TEXT, updated_at TEXT
            );
            CREATE TABLE application_tailoring_generation_meta (
                application_id INTEGER, generation_id TEXT, status TEXT,
                approved_at TEXT, input_fingerprint TEXT,
                content_fingerprint TEXT
            );
            CREATE TABLE application_tailoring_verifications (
                application_id INTEGER, verification_id TEXT,
                generation_id TEXT, phase8_version TEXT,
                verification_fingerprint TEXT, result_json TEXT,
                created_at TEXT
            );
            CREATE TABLE global_blueprint_candidates (
                candidate_id TEXT, candidate_fingerprint TEXT,
                source_application_id INTEGER, source_generation_id TEXT,
                role_family TEXT, status TEXT, snapshot_json TEXT,
                created_at TEXT, updated_at TEXT
            );
            CREATE TABLE blueprint_cross_jd_evaluations (
                evaluation_id TEXT, evaluation_fingerprint TEXT,
                candidate_id TEXT, role_family_id TEXT,
                phase9c_version TEXT, evaluation_json TEXT,
                created_at TEXT
            );
            CREATE TABLE application_resume_results (
                application_result_id TEXT, result_fingerprint TEXT,
                blueprint_id TEXT, blueprint_fingerprint TEXT,
                blueprint_version INTEGER, source_application_id INTEGER,
                source_generation_id TEXT, source_verification_id TEXT,
                source_verification_fingerprint TEXT
            );
            CREATE TABLE application_resume_result_artifacts (
                application_result_id TEXT, artifact_kind TEXT,
                artifact_sha256 TEXT, artifact_size INTEGER,
                provenance_mode TEXT, source_path TEXT,
                materialized_path TEXT,
                is_original_approved_artifact INTEGER
            );
            """
        )
        if include_application:
            connection.execute(
                "INSERT INTO applications VALUES (94,?,?,?,?,?,?)",
                (
                    "Source Application 94",
                    "AI Engineer",
                    "Synthetic Co",
                    74,
                    "2026-08-01T00:00:00",
                    "2026-08-02T00:00:00",
                ),
            )
        connection.execute(
            "INSERT INTO application_job_links VALUES (94,61,?,?)",
            ("jd-version", "2026-08-01T00:00:00"),
        )
        connection.execute(
            "INSERT INTO job_descriptions VALUES (61,?)",
            ("canonical-jd",),
        )
        connection.execute(
            "INSERT INTO job_description_versions VALUES (61,?,?,?,?)",
            (
                "jd-version",
                fixture["raw_jd"],
                json.dumps(
                    {
                        "job_title": "AI Engineer",
                        "company": "Synthetic Co",
                    }
                ),
                "2026-08-01T00:00:00",
            ),
        )
        fit_json = json.dumps(candidate["fit_result"])
        connection.execute(
            "INSERT INTO application_tailoring_versions VALUES (94,?,?,?,?,?,?)",
            (
                "approved-generation",
                fit_json,
                "approved.docx",
                "approved.pdf",
                "2026-08-01T00:00:00",
                "2026-08-02T00:00:00",
            ),
        )
        connection.execute(
            "INSERT INTO application_tailoring_generation_meta VALUES (94,?,?,?,?,?)",
            (
                "approved-generation",
                "approved",
                "2026-08-02T00:00:00",
                "generation-input",
                "generation-content",
            ),
        )
        verification = {
            "blueprint_ready": True,
            "final_scoring_seed_fingerprint": "seed-fingerprint",
            "after_stable_analysis": {
                "deterministic_alignment_score": 92,
                "input_fingerprint": "stable-analysis-input",
            },
        }
        connection.execute(
            "INSERT INTO application_tailoring_verifications VALUES (94,?,?,?,?,?,?)",
            (
                "phase8-verification",
                "approved-generation",
                "phase8-before-after-verification-v8",
                "phase8-fingerprint",
                json.dumps(verification),
                "2026-08-02T00:00:00",
            ),
        )
        connection.execute(
            "INSERT INTO global_blueprint_candidates VALUES (?,?,?,?,?,?,?,?,?)",
            (
                blueprint["candidate_id"],
                blueprint["candidate_fingerprint"],
                94,
                "approved-generation",
                blueprint["role_family_label"],
                "candidate",
                json.dumps(candidate),
                "2026-08-02T00:00:00",
                "2026-08-02T00:00:00",
            ),
        )
        connection.execute(
            "INSERT INTO blueprint_cross_jd_evaluations VALUES (?,?,?,?,?,?,?)",
            (
                blueprint["evaluation_id"],
                blueprint["evaluation_fingerprint"],
                blueprint["candidate_id"],
                blueprint["role_family_id"],
                "phase9c-cross-jd-evaluation-v1",
                json.dumps(evaluation),
                "2026-08-03T00:00:00",
            ),
        )
        connection.execute(
            "INSERT INTO application_resume_results VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "immutable-result",
                "immutable-result-fingerprint",
                blueprint["blueprint_id"],
                blueprint["blueprint_fingerprint"],
                1,
                94,
                "approved-generation",
                "phase8-verification",
                "phase8-fingerprint",
            ),
        )
        connection.execute(
            "INSERT INTO application_resume_result_artifacts VALUES (?,?,?,?,?,?,?,?)",
            (
                "immutable-result",
                "docx",
                "artifact-sha256",
                1234,
                "original_approved_artifact",
                "approved.docx",
                "immutable/resume.docx",
                1,
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return blueprint, fixture


class Phase9FStartingSourceProvenanceTests(unittest.TestCase):
    def test_complete_chain_resolves_candidate_evaluation_and_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "provenance.sqlite"
            blueprint, _ = _create_provenance_database(database)
            resolved = load_blueprint_provenance_read_only(
                blueprint,
                database_path=database,
            )
        self.assertEqual(resolved["chain_status"], "resolved")
        self.assertEqual(resolved["missing_provenance_links"], [])
        self.assertEqual(
            resolved["source_application"]["application_id"], 94
        )
        self.assertTrue(resolved["source_application"]["resolved"])
        self.assertTrue(resolved["source_jd"]["exact_identity_match"])
        self.assertEqual(
            resolved["phase9b_candidate"]["candidate_id"],
            blueprint["candidate_id"],
        )
        self.assertEqual(
            resolved["phase9c_evaluation"]["evaluation_id"],
            blueprint["evaluation_id"],
        )
        self.assertEqual(
            resolved["phase8_verification"][
                "final_scoring_seed_fingerprint"
            ],
            "seed-fingerprint",
        )
        self.assertEqual(
            len(
                resolved["source_resume_result_or_generation"][
                    "immutable_artifact_hash_records"
                ]
            ),
            1,
        )

    def test_missing_source_application_is_reported_not_guessed(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "missing.sqlite"
            blueprint, _ = _create_provenance_database(
                database,
                include_application=False,
            )
            resolved = load_blueprint_provenance_read_only(
                blueprint,
                database_path=database,
            )
        self.assertEqual(resolved["chain_status"], "incomplete")
        self.assertFalse(resolved["source_application"]["resolved"])
        self.assertEqual(
            resolved["source_application"]["application_id"], 94
        )
        self.assertIn("source_application", resolved["missing_provenance_links"])

    def test_debug_bundle_is_deterministic_compact_and_score_labels_are_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "debug.sqlite"
            blueprint, _ = _create_provenance_database(database)
            provenance = load_blueprint_provenance_read_only(
                blueprint,
                database_path=database,
            )
        ranking = {
            "ranking_input_fingerprint": "ranking-input",
            "ranking_fingerprint": "ranking-result",
            "semantic_identity": {"exact_jd": {"raw_jd_sha256": "current"}},
        }
        candidate = {
            "rank": 1,
            "deterministic_alignment_score": 7,
            "required_core_coverage_score": 2,
            "preferred_coverage_score": 10,
            "evidence_strength_score": 40,
            "comparison_result_fingerprint": "comparison-result",
        }
        artifact = compact_artifact_resolution(
            {
                "source_type": "global_blueprint",
                "source_id": blueprint["blueprint_id"],
                "source_content_fingerprint": "source-content",
                "artifacts": [
                    {
                        "artifact_type": "docx",
                        "artifact_kind": "approved_fitted_source",
                        "filename": "approved.docx",
                        "media_type": "application/docx",
                        "sha256": "artifact-sha256",
                        "byte_size": 1234,
                        "artifact_bytes": b"private bytes",
                        "verification_method": (
                            "authoritative_immutable_application_result_sha256"
                        ),
                    }
                ],
            }
        )
        before = canonical_json(ranking)
        first = build_blueprint_provenance_debug_bundle(
            ranking_result=ranking,
            ranked_candidate=candidate,
            blueprint_provenance=provenance,
            artifact_resolution=artifact,
        )
        second = build_blueprint_provenance_debug_bundle(
            ranking_result=ranking,
            ranked_candidate=candidate,
            blueprint_provenance=provenance,
            artifact_resolution=artifact,
        )
        self.assertEqual(canonical_json(first), canonical_json(second))
        self.assertEqual(canonical_json(ranking), before)
        self.assertEqual(
            first["current_phase9f_b_comparison"]["current_jd_alignment"],
            7,
        )
        self.assertEqual(
            first["phase9b_candidate"]["score_summary"][
                "approved_tailored_score"
            ],
            92,
        )
        self.assertIn("used for ranking", first["score_labels"]["current_jd_alignment"])
        self.assertIn("never used", first["score_labels"]["historical_blueprint_source_score"])
        encoded = canonical_json(first).lower()
        for forbidden in (
            "api_key",
            "authorization",
            "bearer ",
            "environment_variables",
            "private bytes",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_passive_provenance_read_is_zero_cost_and_does_not_change_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "readonly.sqlite"
            blueprint, _ = _create_provenance_database(database)
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            resolved = load_blueprint_provenance_read_only(
                blueprint,
                database_path=database,
            )
            after = hashlib.sha256(database.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        self.assertEqual(
            resolved["zero_cost_diagnostics"],
            {
                "model_call_count": 0,
                "embedding_call_count": 0,
                "chroma_read_count": 0,
                "chroma_write_count": 0,
                "persistence_write_count": 0,
            },
        )
        source = Path(
            "tailoring/phase9f_starting_source_provenance.py"
        ).read_text(encoding="utf-8")
        artifact_source = Path(
            "tailoring/phase9f_starting_source_artifacts.py"
        ).read_text(encoding="utf-8")
        for module_source in (source, artifact_source):
            self.assertNotIn("import llm", module_source)
            self.assertNotIn("jd_chroma", module_source)
            self.assertNotIn("INSERT ", module_source)
            self.assertNotIn("UPDATE ", module_source)
            self.assertNotIn("DELETE ", module_source)


if __name__ == "__main__":
    unittest.main()

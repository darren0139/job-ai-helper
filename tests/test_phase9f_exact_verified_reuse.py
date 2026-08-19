from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database.global_blueprint_manager as blueprint_manager
import database.phase9f_exact_verified_reuse_manager as proof_manager
from tailoring.phase9f_exact_verified_reuse import (
    PHASE9F_BLUEPRINT_ARTIFACT_POLICY_VERSION,
    Phase9FExactVerifiedReuseError,
    build_exact_verified_reuse_proof,
    validate_exact_verified_reuse_proof,
)


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _exact_jd(*, raw_jd_sha256: str = "raw-jd", source_version_id: str = "version-1") -> dict:
    return {
        "semantic_identity": {
            "raw_jd_sha256": raw_jd_sha256,
            "structured_profile_fingerprint": "profile-fingerprint",
            "canonical_requirement_fingerprint": "requirements-fingerprint",
            "canonical_requirement_ids": ["req-a", "req-b"],
        },
        "provenance": {
            "canonical_jd_id": "canonical-jd-1",
            "source_version_id": source_version_id,
            "stable_input_fingerprint": "stable-input-1",
        },
    }


def _resolved_provenance() -> dict:
    return {
        "chain_status": "resolved",
        "source_resume_result_or_generation": {
            "source_generation": {
                "approval_resolved": True,
                "fit_identity_match": True,
                "fit_one_page": True,
                "page_count": 1,
                "application_id": 106,
                "generation_id": "approved-generation",
                "input_fingerprint": "generation-input",
                "content_fingerprint": "generation-content",
                "fit_generation_id": "approved-generation",
            }
        },
        "phase8_verification": {
            "resolved": True,
            "blueprint_ready": True,
            "verification_id": "phase8-verification",
            "verification_fingerprint": "phase8-fingerprint",
            "phase8_version": "phase8-final-tailored-resume-v1",
            "final_scoring_seed_fingerprint": "final-seed",
            "final_scoring_seed_valid": True,
            "historical_approved_score": 19,
        },
        "phase9b_candidate": {"identity_match": True},
        "phase9c_evaluation": {
            "identity_match": True,
            "source_jd_parity_accepted": True,
            "evaluation_id": "phase9c-evaluation",
            "evaluation_fingerprint": "phase9c-fingerprint",
        },
        "source_jd": {
            "resolved": True,
            "exact_identity_match": True,
            "canonical_jd_id": "canonical-jd-1",
            "source_version_id": "version-1",
            "raw_jd_sha256": "raw-jd",
            "canonical_requirement_fingerprint": "requirements-fingerprint",
        },
    }


class Phase9FExactVerifiedReuseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "owned-artifacts"
        self.source_root = Path(self.temporary.name) / "source"
        self.source_root.mkdir()
        self.docx_path = self.source_root / "approved.docx"
        self.pdf_path = self.source_root / "approved.pdf"
        self.docx_path.write_bytes(b"approved immutable docx bytes")
        self.pdf_path.write_bytes(b"%PDF-approved immutable pdf bytes")
        self.artifact_provenance = blueprint_manager._prepare_blueprint_artifact_provenance(
            {
                "fit_result": {
                    "fit_one_page": True,
                    "page_count": 1,
                    "docx_path": str(self.docx_path),
                    "pdf_path": str(self.pdf_path),
                }
            }
        )
        with patch.object(blueprint_manager, "BLUEPRINT_ARTIFACT_ROOT", self.root):
            blueprint_manager._materialize_blueprint_artifacts(
                self.artifact_provenance
            )
        artifact_identity = {
            "policy_version": PHASE9F_BLUEPRINT_ARTIFACT_POLICY_VERSION,
            "artifacts": copy.deepcopy(self.artifact_provenance["artifacts"]),
        }
        semantic = {"artifact_provenance": artifact_identity}
        self.blueprint = {
            "blueprint_id": "blueprint-1",
            "blueprint_fingerprint": "blueprint-fingerprint-1",
            "version_number": 3,
            "status": "active",
            "availability_status": "available",
            "is_reusable": True,
            "semantic_identity": semantic,
            "blueprint_snapshot": {
                "artifact_provenance": {
                    **copy.deepcopy(artifact_identity),
                    "storage": copy.deepcopy(
                        self.artifact_provenance["storage"]
                    ),
                },
                "phase9b_candidate_semantic_snapshot": {
                    "canonical_requirement_ids": ["req-a", "req-b"],
                    "evaluation_metadata": {
                        "source_final_scoring_seed_fingerprint": "final-seed"
                    },
                },
            },
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _prove(self, *, provenance: dict | None = None, exact_jd: dict | None = None) -> dict:
        with (
            patch.object(proof_manager, "BLUEPRINT_ARTIFACT_ROOT", self.root),
            patch.object(
                proof_manager,
                "load_blueprint_provenance_read_only",
                return_value=provenance or _resolved_provenance(),
            ),
        ):
            return proof_manager.prove_exact_verified_reuse(
                blueprint=copy.deepcopy(self.blueprint),
                current_exact_jd=copy.deepcopy(exact_jd or _exact_jd()),
            )

    def test_valid_exact_source_with_owned_artifacts_proves_reuse(self):
        proof = self._prove()
        self.assertTrue(proof["eligible"])
        self.assertEqual(proof["reason_code"], "exact_verified_reuse")
        self.assertEqual(proof["verified_score"], 19)
        validated = validate_exact_verified_reuse_proof(
            proof,
            source_type="global_blueprint",
            source_id="blueprint-1",
            source_fingerprint="blueprint-fingerprint-1",
        )
        self.assertEqual(validated["proof_fingerprint"], proof["proof_fingerprint"])

    def test_phase9a_snapshot_shape_proves_same_exact_source(self):
        normalized = _exact_jd()
        phase9a_shape = {
            "canonical_jd_id": normalized["provenance"]["canonical_jd_id"],
            "source_version_id": normalized["provenance"]["source_version_id"],
            "semantic_identity": copy.deepcopy(
                normalized["semantic_identity"]
            ),
        }

        proof = self._prove(exact_jd=phase9a_shape)

        self.assertTrue(proof["eligible"], proof)
        self.assertEqual(proof["reason_code"], "exact_verified_reuse")
        self.assertEqual(proof["verified_score"], 19)

    def test_phase9a_snapshot_source_version_mismatch_still_fails_closed(self):
        normalized = _exact_jd()
        phase9a_shape = {
            "canonical_jd_id": normalized["provenance"]["canonical_jd_id"],
            "source_version_id": "different-version",
            "semantic_identity": copy.deepcopy(
                normalized["semantic_identity"]
            ),
        }

        proof = self._prove(exact_jd=phase9a_shape)

        self.assertFalse(proof["eligible"])
        self.assertEqual(
            proof["reason_code"],
            "current_jd_not_exact_verified_source_jd",
        )

    def test_exact_identity_mismatches_fail_closed(self):
        raw_mismatch = self._prove(exact_jd=_exact_jd(raw_jd_sha256="other-raw"))
        version_mismatch = self._prove(
            exact_jd=_exact_jd(source_version_id="other-version")
        )
        self.assertFalse(raw_mismatch["eligible"])
        self.assertFalse(version_mismatch["eligible"])
        self.assertEqual(
            raw_mismatch["reason_code"], "current_jd_not_exact_verified_source_jd"
        )
        self.assertEqual(
            version_mismatch["reason_code"], "current_jd_not_exact_verified_source_jd"
        )

    def test_missing_or_corrupt_owned_artifact_fails_closed(self):
        pdf_manifest = next(
            row
            for row in self.artifact_provenance["artifacts"]
            if row["artifact_kind"] == "pdf"
        )
        owned_pdf = self.root / f"{pdf_manifest['sha256']}.pdf"
        owned_pdf.unlink()
        missing = self._prove()
        self.assertFalse(missing["eligible"])
        self.assertEqual(missing["reason_code"], "blueprint_owned_artifact_missing")

        with patch.object(blueprint_manager, "BLUEPRINT_ARTIFACT_ROOT", self.root):
            blueprint_manager._materialize_blueprint_artifacts(
                self.artifact_provenance
            )
        owned_pdf.write_bytes(b"corrupt bytes")
        corrupt = self._prove()
        self.assertFalse(corrupt["eligible"])
        self.assertEqual(
            corrupt["reason_code"], "blueprint_owned_artifact_hash_mismatch"
        )

    def test_invalid_phase8_or_source_generation_fails_closed(self):
        phase8_missing = _resolved_provenance()
        phase8_missing["phase8_verification"]["blueprint_ready"] = False
        source_mismatch = _resolved_provenance()
        source_mismatch["source_resume_result_or_generation"][
            "source_generation"
        ]["fit_identity_match"] = False
        self.assertEqual(
            self._prove(provenance=phase8_missing)["reason_code"],
            "blueprint_source_validation_failed",
        )
        self.assertEqual(
            self._prove(provenance=source_mismatch)["reason_code"],
            "blueprint_source_validation_failed",
        )

    def test_removed_blueprint_is_not_eligible_for_new_selection(self):
        self.blueprint["status"] = "superseded"
        result = self._prove()
        self.assertFalse(result["eligible"])
        self.assertEqual(
            result["reason_code"], "blueprint_not_active_available_reusable"
        )

    def test_legacy_blueprint_without_owned_manifest_remains_ineligible_unchanged(self):
        legacy = copy.deepcopy(self.blueprint)
        legacy["semantic_identity"].pop("artifact_provenance")
        legacy["blueprint_snapshot"].pop("artifact_provenance")
        before = copy.deepcopy(legacy)
        with (
            patch.object(proof_manager, "BLUEPRINT_ARTIFACT_ROOT", self.root),
            patch.object(
                proof_manager,
                "load_blueprint_provenance_read_only",
                side_effect=AssertionError("legacy artifact failure must preclude a DB read"),
            ),
        ):
            result = proof_manager.prove_exact_verified_reuse(
                blueprint=legacy,
                current_exact_jd=_exact_jd(),
            )
        self.assertFalse(result["eligible"])
        self.assertEqual(
            result["reason_code"], "legacy_missing_immutable_artifact_provenance"
        )
        self.assertEqual(legacy, before)

    def test_owned_copy_survives_source_deletion_and_rejects_corruption(self):
        self.docx_path.unlink()
        self.pdf_path.unlink()
        with patch.object(proof_manager, "BLUEPRINT_ARTIFACT_ROOT", self.root):
            resolved = proof_manager.resolve_blueprint_owned_artifacts(
                copy.deepcopy(self.blueprint)
            )
        self.assertEqual({row["artifact_type"] for row in resolved}, {"docx", "pdf"})
        self.assertEqual(
            _hash(next(row["artifact_bytes"] for row in resolved if row["artifact_type"] == "pdf")),
            next(
                row["sha256"]
                for row in self.artifact_provenance["artifacts"]
                if row["artifact_kind"] == "pdf"
            ),
        )
        pdf_manifest = next(
            row
            for row in self.artifact_provenance["artifacts"]
            if row["artifact_kind"] == "pdf"
        )
        (self.root / f"{pdf_manifest['sha256']}.pdf").write_bytes(b"corrupt")
        with patch.object(proof_manager, "BLUEPRINT_ARTIFACT_ROOT", self.root):
            with self.assertRaises(Phase9FExactVerifiedReuseError):
                proof_manager.resolve_blueprint_owned_artifacts(
                    copy.deepcopy(self.blueprint)
                )

    def test_proof_fingerprint_binds_jd_artifact_and_phase8_identity(self):
        identity = self._prove()["semantic_identity"]
        changed_artifact = copy.deepcopy(identity)
        changed_artifact["artifact_identity"]["artifacts"][0]["sha256"] = "changed"
        changed_jd = copy.deepcopy(identity)
        changed_jd["current_jd"]["raw_jd_sha256"] = "changed"
        changed_verification = copy.deepcopy(identity)
        changed_verification["phase8_verification"]["verification_fingerprint"] = "changed"
        fingerprints = {
            build_exact_verified_reuse_proof(value)["proof_fingerprint"]
            for value in (
                identity,
                changed_artifact,
                changed_jd,
                changed_verification,
            )
        }
        self.assertEqual(len(fingerprints), 4)

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from database import tailoring_version_manager as base_manager
from database.tailoring_verification_manager import (
    delete_application_tailoring_verifications,
    get_latest_tailoring_verification,
    get_tailoring_verification_approval_gate,
    list_tailoring_verifications,
    save_tailoring_verification,
)
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.job_match_ab_analysis import (
    build_job_match_ab_analysis,
    build_job_match_snapshot,
    inspect_job_match_ab_lifecycle,
)
from taxonomy_discovery.technology_registry import get_default_registry


def evidence(label: str) -> list[dict]:
    if label == "none":
        return []
    return [
        {
            "evidence_id": f"ev_{label}",
            "source": f"resume_profile.projects[0].{label}",
            "text": f"Grounded {label} evidence",
        }
    ]


def requirement(
    requirement_id: str,
    label: str,
    *,
    taxonomy_status: str = "not_needed",
) -> dict:
    return {
        "requirement_id": requirement_id,
        "text": f"Requirement {requirement_id}",
        "importance": "required",
        "score_eligible": True,
        "match_label": label,
        "match_value": {"none": 0.0, "weak": 0.2, "transferable": 0.55, "direct": 1.0}[label],
        "evidence_strength": {"none": 0, "weak": 2, "transferable": 3, "direct": 5}[label],
        "evidence": evidence(label),
        "capability_id": "testing.capability" if taxonomy_status != "unrecognised" else None,
        "capability_resolution_source": "canonical_taxonomy" if taxonomy_status != "unrecognised" else "unresolved",
        "capability_taxonomy_cap_status": taxonomy_status,
    }


def stable(score: int, rows: list[dict]) -> dict:
    return {
        "scoring_version": SCORING_VERSION,
        "capability_taxonomy_version": get_default_taxonomy().version,
        "technology_registry_version": get_default_registry().version,
        "input_fingerprint": f"stable-{score}",
        "deterministic_alignment_score": score,
        "canonical_requirements": rows,
        "validation_warnings": [],
    }


def snapshots() -> tuple[dict, dict]:
    initial_rows = [
        requirement("improved", "none", taxonomy_status="unrecognised"),
        requirement("preserved", "direct"),
        requirement("lost", "transferable", taxonomy_status="applied"),
        requirement("gap", "none", taxonomy_status="unrecognised"),
    ]
    tailored_rows = [
        requirement("gap", "none", taxonomy_status="unrecognised"),
        requirement("lost", "none", taxonomy_status="applied"),
        requirement("preserved", "direct"),
        requirement("improved", "transferable", taxonomy_status="unrecognised"),
    ]
    return (
        build_job_match_snapshot(
            role="initial",
            stable_analysis=stable(25, initial_rows),
            raw_jd_text="Requirements\nPython and systems experience",
        ),
        build_job_match_snapshot(
            role="tailored",
            stable_analysis=stable(35, tailored_rows),
            raw_jd_text="Requirements\nPython and systems experience",
            generation_snapshot_fingerprint="generation-a",
        ),
    )


class JobMatchSessionABTests(unittest.TestCase):
    def test_classifies_all_transitions_and_joins_by_stable_identity(self):
        initial, tailored = snapshots()
        result = build_job_match_ab_analysis(initial, tailored)
        self.assertTrue(result["comparable"])
        self.assertEqual(
            {row["requirement_id"]: row["classification"] for row in result["requirements"]},
            {
                "improved": "IMPROVED",
                "preserved": "PRESERVED",
                "lost": "LOST",
                "gap": "STILL_GAP",
            },
        )
        self.assertEqual(result["summary"]["score_delta"], 10)
        self.assertEqual(result["summary"]["requirements_improved"], 1)
        self.assertEqual(result["summary"]["requirements_preserved"], 1)
        self.assertEqual(result["summary"]["requirements_lost"], 1)
        self.assertEqual(result["summary"]["requirements_still_gaps"], 1)

    def _assert_identity_mismatch(self, field: str) -> None:
        initial, tailored = snapshots()
        tailored["identity"][field] = "different"
        result = build_job_match_ab_analysis(initial, tailored)
        self.assertFalse(result["comparable"])
        self.assertIn(f"identity_mismatch:{field}", result["blockers"])

    def test_different_scoring_versions_fail_closed(self):
        self._assert_identity_mismatch("scoring_version")

    def test_different_job_match_contracts_fail_closed(self):
        self._assert_identity_mismatch("job_match_contract")

    def test_different_taxonomy_versions_fail_closed(self):
        self._assert_identity_mismatch("taxonomy_version")

    def test_different_taxonomy_fingerprints_fail_closed(self):
        self._assert_identity_mismatch("taxonomy_fingerprint")

    def test_different_registry_versions_fail_closed(self):
        self._assert_identity_mismatch("registry_version")

    def test_different_registry_fingerprints_fail_closed(self):
        self._assert_identity_mismatch("registry_fingerprint")

    def test_different_jd_fingerprints_fail_closed(self):
        self._assert_identity_mismatch("jd_fingerprint")

    def test_evidence_fingerprints_may_differ(self):
        initial, tailored = snapshots()
        self.assertNotEqual(
            initial["identity"]["stable_input_fingerprint"],
            tailored["identity"]["stable_input_fingerprint"],
        )
        self.assertTrue(
            build_job_match_ab_analysis(initial, tailored)["comparable"]
        )

    def test_requirement_rows_preserve_both_sides_and_delta_attribution(self):
        initial, tailored = snapshots()
        result = build_job_match_ab_analysis(initial, tailored)
        row = next(
            item
            for item in result["requirements"]
            if item["requirement_id"] == "preserved"
        )
        for side in ("initial", "tailored"):
            self.assertEqual(row[side]["final_match"], "direct")
            self.assertTrue(row[side]["evidence_provenance"])
            self.assertIn("score_contribution", row[side])
            self.assertIn("taxonomy_status", row[side])
            self.assertIn("registry_resolution", row[side])
            self.assertIn("diagnostics", row[side])
        self.assertEqual(row["classification"], "PRESERVED")
        self.assertEqual(row["match_transition"], "direct -> direct")
        self.assertIn("score_contribution_delta", row)

    def test_unresolved_taxonomy_is_non_blocking_and_caps_remain_visible(self):
        initial, tailored = snapshots()
        result = build_job_match_ab_analysis(initial, tailored)
        by_id = {row["requirement_id"]: row for row in result["requirements"]}
        self.assertTrue(result["comparable"])
        self.assertEqual(by_id["improved"]["initial"]["taxonomy_status"], "unresolved")
        self.assertEqual(by_id["lost"]["initial"]["taxonomy_status"], "taxonomy_capped")

    def test_missing_positive_evidence_provenance_fails_closed(self):
        initial, tailored = snapshots()
        tailored["requirements"][0]["final_match"] = "direct"
        tailored["requirements"][0]["evidence"] = []
        tailored["requirements"][0]["evidence_provenance"] = []
        tailored["integrity_blockers"] = [
            "tailored:missing_grounded_evidence_provenance:gap"
        ]
        result = build_job_match_ab_analysis(initial, tailored)
        self.assertFalse(result["comparable"])
        self.assertIn(
            "tailored:missing_grounded_evidence_provenance:gap",
            result["blockers"],
        )

    def test_lifecycle_distinguishes_missing_stale_incompatible_and_superseded(self):
        initial, tailored = snapshots()
        comparable = build_job_match_ab_analysis(initial, tailored)
        self.assertEqual(
            inspect_job_match_ab_lifecycle(None)["state"],
            "no_initial_analysis",
        )
        self.assertEqual(
            inspect_job_match_ab_lifecycle({"initial": initial})["state"],
            "initial_available_no_tailored_analysis",
        )
        bad = deepcopy(comparable)
        bad.update(comparable=False, status="incompatible", blockers=["bad"])
        self.assertEqual(
            inspect_job_match_ab_lifecycle(bad)["state"],
            "initial_tailored_identities_incompatible",
        )
        self.assertEqual(
            inspect_job_match_ab_lifecycle(
                comparable,
                current_generation_snapshot_fingerprint="changed",
            )["state"],
            "tailored_analysis_stale",
        )
        current = deepcopy(initial["identity"])
        current["scoring_version"] = "next"
        self.assertEqual(
            inspect_job_match_ab_lifecycle(
                comparable,
                current_identity=current,
                current_generation_snapshot_fingerprint="generation-a",
            )["state"],
            "current_analysis_generation_superseded",
        )

    def test_initial_snapshot_is_immutable_across_tailored_reruns(self):
        initial, tailored = snapshots()
        comparison = build_job_match_ab_analysis(initial, tailored)
        result = {
            "phase8_version": "phase8-before-after-verification-v10",
            "verification_mode": "zero_cost_deterministic",
            "verification_fingerprint": "same-verification",
            "generation_id": "generation-a",
            "before_stable_analysis": initial["stable_analysis"],
            "after_stable_analysis": tailored["stable_analysis"],
            "job_match_ab": comparison,
            "generation_status": "draft",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            old_path = base_manager.DB_PATH
            base_manager.DB_PATH = Path(temp_dir) / "applications.db"
            try:
                first = save_tailoring_verification(
                    application_id=1,
                    generation_id="generation-a",
                    result=result,
                )
                second = save_tailoring_verification(
                    application_id=1,
                    generation_id="generation-a",
                    result={**result, "generation_status": "approved"},
                )
                self.assertEqual(first["verification_id"], second["verification_id"])
                self.assertEqual(
                    second["job_match_ab"]["initial"],
                    first["job_match_ab"]["initial"],
                )
                changed = deepcopy(result)
                changed["job_match_ab"]["initial"]["score"] = 99
                with self.assertRaisesRegex(ValueError, "immutable"):
                    save_tailoring_verification(
                        application_id=1,
                        generation_id="generation-a",
                        result=changed,
                    )
                stored = get_latest_tailoring_verification(1, "generation-a")
                self.assertEqual(stored["job_match_ab"]["initial"]["score"], 25)
            finally:
                base_manager.DB_PATH = old_path

    def test_legacy_history_remains_readable_when_current_analysis_is_added(self):
        initial, tailored = snapshots()
        current = {
            "phase8_version": "phase8-before-after-verification-v10",
            "verification_mode": "zero_cost_deterministic",
            "verification_fingerprint": "current-analysis",
            "generation_id": "generation-a",
            "before_stable_analysis": initial["stable_analysis"],
            "after_stable_analysis": tailored["stable_analysis"],
            "job_match_ab": build_job_match_ab_analysis(initial, tailored),
        }
        legacy = {
            "phase8_version": "phase8-before-after-verification-v9",
            "verification_mode": "zero_cost_deterministic",
            "verification_fingerprint": "legacy-analysis",
            "generation_id": "generation-a",
            "before_stable_analysis": {"legacy": True},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            old_path = base_manager.DB_PATH
            base_manager.DB_PATH = Path(temp_dir) / "applications.db"
            try:
                saved_legacy = save_tailoring_verification(
                    application_id=1,
                    generation_id="generation-a",
                    result=legacy,
                )
                saved_current = save_tailoring_verification(
                    application_id=1,
                    generation_id="generation-a",
                    result=current,
                )
                history = list_tailoring_verifications(1)
                self.assertEqual(len(history), 2)
                self.assertNotEqual(
                    saved_legacy["verification_id"],
                    saved_current["verification_id"],
                )
                legacy_after = next(
                    item
                    for item in history
                    if item["verification_fingerprint"] == "legacy-analysis"
                )
                self.assertEqual(legacy_after["before_stable_analysis"], {"legacy": True})
                self.assertNotIn("job_match_ab", legacy_after)
                self.assertEqual(
                    get_latest_tailoring_verification(1, "generation-a")[
                        "verification_fingerprint"
                    ],
                    "current-analysis",
                )
                self.assertEqual(delete_application_tailoring_verifications(1), 2)
                self.assertEqual(list_tailoring_verifications(1), [])
            finally:
                base_manager.DB_PATH = old_path

    @patch(
        "database.tailoring_generation_control.get_tailoring_generation",
        return_value={"generation_id": "generation-a"},
    )
    @patch(
        "database.tailoring_verification_manager.build_phase8_generation_snapshot_fingerprint",
        return_value="current-generation-snapshot",
    )
    def test_legacy_verification_cannot_pass_current_approval_gate(
        self,
        _snapshot_fingerprint,
        _generation,
    ):
        legacy = {
            "phase8_version": "phase8-before-after-verification-v9",
            "verification_mode": "zero_cost_deterministic",
            "verification_fingerprint": "legacy-analysis",
            "generation_id": "generation-a",
            "approval_ready": True,
            "approval_gate_version": "phase8-preapproval-gate-v1",
            "verified_generation_snapshot_fingerprint": (
                "current-generation-snapshot"
            ),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            old_path = base_manager.DB_PATH
            base_manager.DB_PATH = Path(temp_dir) / "applications.db"
            try:
                saved = save_tailoring_verification(
                    application_id=1,
                    generation_id="generation-a",
                    result=legacy,
                )
                gate = get_tailoring_verification_approval_gate(
                    1,
                    "generation-a",
                )
                self.assertFalse(gate["ready"])
                self.assertIn("phase8_version_mismatch", gate["reasons"])
                self.assertIn("no_initial_analysis", gate["reasons"])
                self.assertNotIn("job_match_ab", gate["verification"])
                self.assertNotIn("job_match_ab", saved)
            finally:
                base_manager.DB_PATH = old_path

    def test_streamlit_contract_extends_existing_phase8_view(self):
        source = Path("tailoring/phase8_verification_ui.py").read_text(encoding="utf-8")
        self.assertIn("Initial Job Match", source)
        self.assertIn("Tailored Job Match", source)
        self.assertIn("Initial vs Tailored", source)
        self.assertIn("Evidence / provenance", source)
        self.assertIn("Initial provenance", source)
        self.assertIn("Tailored provenance", source)
        self.assertIn("A/B taxonomy and resolver diagnostics", source)
        self.assertIn("Contribution Δ", source)


if __name__ == "__main__":
    unittest.main()

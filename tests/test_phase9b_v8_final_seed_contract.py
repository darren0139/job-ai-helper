from __future__ import annotations

import unittest

from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from tailoring.final_scoring_seed import (
    build_final_scoring_seed,
    fingerprint_final_scoring_seed,
)
from tailoring.phase9b_blueprint_candidate import (
    _evaluation_metadata,
    blueprint_candidate_eligibility,
)
from tailoring.phase9c_blueprint_evaluation import (
    Phase9CEvaluationError,
    _source_analysis,
)


def _row(label: str = "direct") -> dict:
    values = {
        "none": 0.0,
        "weak": 0.2,
        "transferable": 0.55,
        "direct": 1.0,
    }
    return {
        "requirement_id": "req_python",
        "text": "Hands-on Python",
        "importance": "core",
        "atomic_group_id": "grp_python",
        "group_weight_fraction": 1.0,
        "match_label": label,
        "match_value": values[label],
        "evidence_strength": 5 if label == "direct" else 0,
        "capability_id": "programming.python",
    }


def _verification(*, version: str, with_seed: bool) -> dict:
    seed = build_final_scoring_seed(
        {
            "scoring_version": SCORING_VERSION,
            "capability_taxonomy_version": "taxonomy-test",
            "canonical_requirements": [_row()],
        }
    )
    score = seed["aggregate"]["deterministic_alignment_score"]
    result = {
        "phase8_version": version,
        "verification_id": "verification-test",
        "verification_fingerprint": "verification-fingerprint-test",
        "generation_id": "generation-test",
        "comparison_valid": True,
        "blueprint_ready": True,
        "comparison": {
            "before_score": 0,
            "after_score": score,
            "score_delta": score,
            "required_core_coverage_delta": score,
            "improved_requirements": [],
            "important_regressions": [],
        },
        "claim_lineage": {"claim_review_required_count": 0},
        "before_stable_analysis": {
            "deterministic_alignment_score": 0,
            "input_fingerprint": "before-fingerprint",
        },
        "after_stable_analysis": {
            "deterministic_alignment_score": score,
            "scoring_version": SCORING_VERSION,
            "capability_taxonomy_version": "taxonomy-test",
            "canonical_requirements": [_row()],
        },
    }
    if with_seed:
        result["final_scoring_seed"] = seed
        result["final_scoring_seed_fingerprint"] = (
            fingerprint_final_scoring_seed(seed)
        )
    return result


def _generation() -> dict:
    return {
        "generation_id": "generation-test",
        "status": "approved",
        "fit_result": {"fit_one_page": True, "page_count": 1},
    }


class Phase9BV8FinalSeedContractTests(unittest.TestCase):
    def test_v8_missing_seed_is_not_phase9b_eligible(self) -> None:
        result = blueprint_candidate_eligibility(
            generation_state=_generation(),
            verification=_verification(
                version="phase8-before-after-verification-v8",
                with_seed=False,
            ),
        )
        self.assertFalse(
            result["reasons"]["canonical_final_scoring_seed_ready"]
        )

    def test_v8_missing_seed_promotion_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "missing its canonical final scoring seed",
        ):
            _evaluation_metadata(
                baseline_report={"stable_analysis": {}},
                verification=_verification(
                    version="phase8-before-after-verification-v8",
                    with_seed=False,
                ),
            )

    def test_v7_missing_seed_keeps_legacy_compatibility(self) -> None:
        metadata = _evaluation_metadata(
            baseline_report={"stable_analysis": {}},
            verification=_verification(
                version="phase8-before-after-verification-v7",
                with_seed=False,
            ),
        )
        self.assertEqual(
            metadata["evaluation_seed_version"],
            "phase9c-seed-v1",
        )
        self.assertNotIn("source_final_scoring_seed", metadata)

    def test_v8_valid_seed_is_promoted_as_seed_v2(self) -> None:
        metadata = _evaluation_metadata(
            baseline_report={"stable_analysis": {}},
            verification=_verification(
                version="phase8-before-after-verification-v8",
                with_seed=True,
            ),
        )
        self.assertEqual(
            metadata["evaluation_seed_version"],
            "phase9c-seed-v2",
        )
        self.assertTrue(metadata["source_final_scoring_seed"])
        self.assertTrue(
            metadata["source_final_scoring_seed_fingerprint"]
        )

    def test_existing_bad_v8_candidate_gets_actionable_phase9c_error(
        self,
    ) -> None:
        candidate = {
            "score_summary": {"approved_tailored_score": 100},
            "evaluation_metadata": {
                "evaluation_seed_version": "phase9c-seed-v1",
                "source_jd_requirement_summary": [_row()],
            },
            "provenance": {
                "phase8_version": "phase8-before-after-verification-v8",
            },
            "resume_profile_snapshot": {},
            "resume_text_snapshot": "resume",
        }
        with self.assertRaisesRegex(
            Phase9CEvaluationError,
            "missing the canonical Phase 8 final scoring seed",
        ):
            _source_analysis(
                candidate,
                {"raw_text": "Hands-on Python", "jd_profile": {}},
                {
                    "requirements": [
                        {
                            "requirement_id": "req_python",
                            "text": "Hands-on Python",
                            "importance": "core",
                            "atomic_group_id": "grp_python",
                            "group_weight_fraction": 1.0,
                        }
                    ]
                },
            )


if __name__ == "__main__":
    unittest.main()

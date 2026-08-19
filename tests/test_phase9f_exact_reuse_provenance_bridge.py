from __future__ import annotations

import copy
import inspect
import unittest

from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from tailoring.final_scoring_seed import (
    build_final_scoring_seed,
    fingerprint_final_scoring_seed,
)
from tailoring.phase9f_starting_source_provenance import (
    _persisted_source_jd_parity,
    _phase8_final_seed_is_valid,
    load_blueprint_provenance_read_only,
)


def _seed():
    seed = build_final_scoring_seed(
        {
            "scoring_version": SCORING_VERSION,
            "capability_taxonomy_version": "taxonomy-test",
            "canonical_requirements": [
                {
                    "requirement_id": "req_qa",
                    "text": "Quality assurance",
                    "importance": "core",
                    "atomic_group_id": "grp_qa",
                    "group_weight_fraction": 1.0,
                    "match_label": "direct",
                    "match_value": 1.0,
                    "evidence_strength": 5,
                    "capability_id": "quality.qa_testing",
                }
            ],
        }
    )
    return seed, fingerprint_final_scoring_seed(seed)


class Phase9FExactReuseProvenanceBridgeTests(unittest.TestCase):
    def test_phase8_final_seed_validation_is_fail_closed(self):
        seed, fingerprint = _seed()
        score = int(seed["aggregate"]["deterministic_alignment_score"])
        verification = {
            "final_scoring_seed": seed,
            "final_scoring_seed_fingerprint": fingerprint,
            "after_stable_analysis": {
                "deterministic_alignment_score": score,
            },
        }
        self.assertTrue(_phase8_final_seed_is_valid(verification))

        wrong_score = copy.deepcopy(verification)
        wrong_score["after_stable_analysis"][
            "deterministic_alignment_score"
        ] = score + 1
        self.assertFalse(_phase8_final_seed_is_valid(wrong_score))

        tampered = copy.deepcopy(verification)
        tampered["final_scoring_seed"]["canonical_requirements"][0][
            "match_label"
        ] = "none"
        self.assertFalse(_phase8_final_seed_is_valid(tampered))

    def test_phase9c_parity_requires_one_accepted_row_and_same_seed(self):
        _, fingerprint = _seed()
        evaluation = {
            "per_jd_results": [
                {
                    "is_source_jd": True,
                    "source_jd_parity": {
                        "accepted": True,
                        "final_scoring_seed_fingerprint": fingerprint,
                    },
                }
            ]
        }

        accepted, parity = _persisted_source_jd_parity(
            evaluation,
            expected_final_seed_fingerprint=fingerprint,
        )
        self.assertTrue(accepted)
        self.assertEqual(
            parity["final_scoring_seed_fingerprint"],
            fingerprint,
        )

        mismatch, _ = _persisted_source_jd_parity(
            evaluation,
            expected_final_seed_fingerprint="different",
        )
        self.assertFalse(mismatch)

        ambiguous = copy.deepcopy(evaluation)
        ambiguous["per_jd_results"].append(
            copy.deepcopy(ambiguous["per_jd_results"][0])
        )
        accepted, _ = _persisted_source_jd_parity(
            ambiguous,
            expected_final_seed_fingerprint=fingerprint,
        )
        self.assertFalse(accepted)

    def test_production_loader_exposes_both_exact_reuse_bridge_fields(self):
        source = inspect.getsource(load_blueprint_provenance_read_only)
        self.assertIn('"final_scoring_seed_valid"', source)
        self.assertIn("_phase8_final_seed_is_valid(verification)", source)
        self.assertIn('"source_jd_parity_accepted"', source)
        self.assertIn("_persisted_source_jd_parity(", source)


if __name__ == "__main__":
    unittest.main()

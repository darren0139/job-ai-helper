from __future__ import annotations

import unittest
from copy import deepcopy

from analysis_stability.stable_evidence_scoring import (
    SCORING_VERSION,
    compute_deterministic_alignment,
)
from tailoring.final_scoring_seed import (
    FINAL_SCORING_SEED_VERSION,
    build_final_scoring_seed,
    fingerprint_final_scoring_seed,
    verify_final_scoring_seed,
)
from tailoring.phase8_requirement_reconciliation import (
    _recalculate_stable_summary,
)
from tailoring.phase9c_blueprint_evaluation import _source_analysis


def _six_core_rows(label: str, strength: int) -> list[dict]:
    values = {
        "none": 0.0,
        "weak": 0.2,
        "transferable": 0.55,
        "direct": 1.0,
    }
    rows = []
    for index in range(6):
        active = index == 0
        row_label = label if active else "none"
        rows.append(
            {
                "requirement_id": f"req_{index}",
                "text": f"Requirement {index}",
                "importance": "core",
                "atomic_group_id": "group_shared",
                "group_weight_fraction": 1 / 6,
                "match_label": row_label,
                "match_value": values[row_label],
                "evidence_strength": strength if active else 0,
                "capability_id": "",
            }
        )
    return rows


class Phase8Phase9CAggregationParityTests(unittest.TestCase):
    def test_application92_shape_remains_7_to_14_under_canonical_aggregator(
        self,
    ) -> None:
        before = compute_deterministic_alignment(
            _six_core_rows("weak", 2)
        )
        after = compute_deterministic_alignment(
            _six_core_rows("transferable", 3)
        )
        self.assertEqual(before["deterministic_alignment_score"], 7)
        self.assertEqual(after["deterministic_alignment_score"], 14)

    def test_phase8_reconciliation_summary_is_exact_canonical_aggregate(
        self,
    ) -> None:
        rows = _six_core_rows("transferable", 3)
        analysis = {
            "scoring_version": SCORING_VERSION,
            "canonical_requirements": deepcopy(rows),
        }
        expected = compute_deterministic_alignment(deepcopy(rows))
        _recalculate_stable_summary(analysis)
        for key in (
            "deterministic_alignment_score",
            "required_core_coverage_score",
            "preferred_coverage_score",
            "evidence_strength_score",
            "credited_requirement_count",
            "score_weights",
        ):
            self.assertEqual(analysis[key], expected[key], key)

    def test_final_seed_is_deterministic_and_tamper_sensitive(self) -> None:
        analysis = {
            "scoring_version": SCORING_VERSION,
            "capability_taxonomy_version": "taxonomy-test",
            "canonical_requirements": _six_core_rows(
                "transferable",
                3,
            ),
        }
        seed = build_final_scoring_seed(analysis)
        fingerprint = fingerprint_final_scoring_seed(seed)
        self.assertEqual(
            seed["seed_version"],
            FINAL_SCORING_SEED_VERSION,
        )
        self.assertEqual(
            seed["aggregate"]["deterministic_alignment_score"],
            14,
        )
        verified = verify_final_scoring_seed(seed, fingerprint)
        self.assertEqual(
            verified["aggregate"]["deterministic_alignment_score"],
            14,
        )
        tampered = deepcopy(seed)
        tampered["canonical_requirements"][0]["match_label"] = "direct"
        with self.assertRaises(ValueError):
            verify_final_scoring_seed(tampered, fingerprint)

    def test_phase9c_reproduces_new_phase8_seed_at_14(self) -> None:
        rows = _six_core_rows("transferable", 3)
        seed = build_final_scoring_seed(
            {
                "scoring_version": SCORING_VERSION,
                "capability_taxonomy_version": "taxonomy-test",
                "canonical_requirements": deepcopy(rows),
            }
        )
        seed_fingerprint = fingerprint_final_scoring_seed(seed)
        candidate = {
            "score_summary": {"approved_tailored_score": 14},
            "evaluation_metadata": {
                "evaluation_seed_version": "phase9c-seed-v2",
                "source_final_scoring_seed": seed,
                "source_final_scoring_seed_fingerprint": seed_fingerprint,
            },
            "resume_profile_snapshot": {},
            "resume_text_snapshot": "resume",
        }
        canonical = {
            "requirements": [
                {
                    key: deepcopy(value)
                    for key, value in row.items()
                    if key in {
                        "requirement_id",
                        "text",
                        "importance",
                        "atomic_group_id",
                        "group_weight_fraction",
                    }
                }
                for row in rows
            ]
        }
        result = _source_analysis(
            candidate,
            {"raw_text": "source jd", "jd_profile": {}},
            canonical,
        )
        self.assertEqual(result["deterministic_alignment_score"], 14)
        self.assertTrue(result["source_jd_parity"]["accepted"])
        self.assertEqual(
            result["source_jd_parity"][
                "final_scoring_seed_fingerprint"
            ],
            seed_fingerprint,
        )




    def test_final_seed_derives_missing_match_value_from_match_label(
        self,
    ) -> None:
        analysis = {
            "scoring_version": SCORING_VERSION,
            "capability_taxonomy_version": "taxonomy-test",
            "canonical_requirements": [
                {
                    "requirement_id": "req_direct",
                    "text": "Direct requirement",
                    "importance": "required",
                    "atomic_group_id": "",
                    "group_weight_fraction": None,
                    "match_label": "direct",
                    "evidence_strength": 5,
                    "capability_id": "",
                }
            ],
        }

        seed = build_final_scoring_seed(analysis)
        row = seed["canonical_requirements"][0]

        self.assertEqual(row["match_label"], "direct")
        self.assertEqual(row["match_value"], 1.0)

        fingerprint = fingerprint_final_scoring_seed(seed)
        verified = verify_final_scoring_seed(seed, fingerprint)
        self.assertEqual(
            verified["canonical_requirements"][0]["match_value"],
            1.0,
        )

    def test_final_seed_normalizes_none_or_stale_match_value(
        self,
    ) -> None:
        rows = [
            {
                "requirement_id": "req_none",
                "text": "Missing requirement",
                "importance": "core",
                "atomic_group_id": "",
                "group_weight_fraction": None,
                "match_label": "none",
                "match_value": None,
                "evidence_strength": 0,
                "capability_id": "",
            },
            {
                "requirement_id": "req_transferable",
                "text": "Transferable requirement",
                "importance": "core",
                "atomic_group_id": "",
                "group_weight_fraction": None,
                "match_label": "transferable",
                "match_value": 1.0,
                "evidence_strength": 3,
                "capability_id": "",
            },
        ]

        seed = build_final_scoring_seed(
            {
                "scoring_version": SCORING_VERSION,
                "capability_taxonomy_version": "taxonomy-test",
                "canonical_requirements": rows,
            }
        )
        by_id = {
            row["requirement_id"]: row
            for row in seed["canonical_requirements"]
        }

        self.assertEqual(by_id["req_none"]["match_value"], 0.0)
        self.assertEqual(
            by_id["req_transferable"]["match_value"],
            0.55,
        )

if __name__ == "__main__":
    unittest.main()

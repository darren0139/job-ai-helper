from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_analysis_stability_trial.py"
)

SPEC = importlib.util.spec_from_file_location(
    "run_analysis_stability_trial",
    SCRIPT_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _report(
    *,
    score: int,
    label: str = "direct",
    requirement_id: str = "req_1",
) -> dict:
    return {
        "stable_analysis": {
            "deterministic_alignment_score": score,
            "alignment_band": "weak alignment",
            "requirement_count": 1,
            "credited_requirement_count": 1,
            "required_core_coverage_score": score,
            "preferred_coverage_score": 0,
            "evidence_strength_score": 80,
            "bullet_quality_component": 70,
            "structure_component": 100,
            "input_fingerprint": "same",
            "canonical_requirements": [
                {
                    "requirement_id": requirement_id,
                    "text": "Example requirement",
                    "importance": "required",
                    "match_label": label,
                }
            ],
        }
    }


class StabilityTrialComparisonTests(unittest.TestCase):
    def test_identical_runs_pass(self) -> None:
        result = MODULE._build_comparison(
            [_report(score=31), _report(score=31)],
            max_score_spread=5,
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["score_spread"], 0)
        self.assertEqual(
            result["core_label_differences"],
            [],
        )

    def test_large_score_spread_fails(self) -> None:
        result = MODULE._build_comparison(
            [_report(score=31), _report(score=40)],
            max_score_spread=5,
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["score_spread"], 9)

    def test_core_label_change_fails(self) -> None:
        result = MODULE._build_comparison(
            [
                _report(score=31, label="none"),
                _report(score=32, label="direct"),
            ],
            max_score_spread=5,
        )

        self.assertFalse(result["passed"])
        self.assertEqual(
            len(result["core_label_differences"]),
            1,
        )

    def test_requirement_id_change_fails(self) -> None:
        result = MODULE._build_comparison(
            [
                _report(score=31, requirement_id="req_1"),
                _report(score=31, requirement_id="req_2"),
            ],
            max_score_spread=5,
        )

        self.assertFalse(result["passed"])
        self.assertFalse(
            result["requirement_ids_stable"]
        )


if __name__ == "__main__":
    unittest.main()

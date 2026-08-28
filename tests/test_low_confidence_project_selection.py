from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from tailoring.stable_tailoring_ranking import (
    LOW_CONFIDENCE_SELECTION_VERSION,
    build_low_confidence_project_selection,
)


def _row(
    title: str,
    *,
    project_id: str,
    final_score: int,
    coverage: float,
    support_score: int,
    selection_rank: int | None = None,
    match_label: str | None = None,
) -> dict:
    matches = []
    if match_label:
        matches = [
            {
                "requirement_id": f"req_{project_id}",
                "match_label": match_label,
                "coverage_points": coverage,
            }
        ]

    return {
        "title": title,
        "display_title": title,
        "project_id": project_id,
        "final_score": final_score,
        "deterministic_coverage_score": coverage,
        "support_score": support_score,
        "support_components": {
            "evidence_completeness": max(0, support_score - 5),
            "impact_scope": min(5, support_score),
        },
        "currently_in_resume": True,
        "in_evidence_library": True,
        "requirement_matches": matches,
        "selection_rank": selection_rank,
    }


class LowConfidenceProjectSelectionTests(unittest.TestCase):
    def test_app129_shape_identifies_only_zero_coverage_fallback_slots(self):
        rows = [
            _row(
                "Workout Buddy",
                project_id="workout",
                final_score=57,
                coverage=19.5,
                support_score=18,
                selection_rank=1,
                match_label="direct",
            ),
            _row(
                "The Great Migration",
                project_id="migration",
                final_score=53,
                coverage=16.5,
                support_score=20,
                selection_rank=2,
                match_label="transferable",
            ),
            _row(
                "QueryAI",
                project_id="query",
                final_score=0,
                coverage=0.0,
                support_score=20,
                selection_rank=3,
            ),
            _row(
                "CyberSphere",
                project_id="cyber",
                final_score=0,
                coverage=0.0,
                support_score=18,
                selection_rank=4,
            ),
            _row(
                "Job AI Helper",
                project_id="job_ai",
                final_score=0,
                coverage=0.0,
                support_score=18,
            ),
        ]

        before = deepcopy(rows)
        result = build_low_confidence_project_selection(
            ranked_rows=rows,
            selected_count=4,
        )

        self.assertEqual(
            LOW_CONFIDENCE_SELECTION_VERSION,
            result["policy_version"],
        )
        self.assertTrue(result["active"])
        self.assertEqual(2, result["evidence_grounded_selected_count"])
        self.assertEqual(2, result["fallback_slot_count"])
        self.assertEqual(
            ["query", "cyber"],
            result["default_low_confidence_project_ids"],
        )
        self.assertEqual(
            ["QueryAI", "CyberSphere", "Job AI Helper"],
            [
                item["title"]
                for item in result[
                    "eligible_low_confidence_candidates"
                ]
            ],
        )
        self.assertTrue(
            result["eligible_low_confidence_candidates"][0][
                "selected_as_low_confidence_fallback"
            ]
        )
        self.assertFalse(
            result["eligible_low_confidence_candidates"][2][
                "selected_by_default"
            ]
        )
        self.assertEqual(
            "none",
            result["eligible_low_confidence_candidates"][2][
                "jd_coverage"
            ],
        )
        self.assertEqual(rows, before)

    def test_fallback_suitability_never_creates_jd_coverage(self):
        rows = [
            _row(
                "Strong Evidence Zero Match",
                project_id="strong_zero",
                final_score=0,
                coverage=0.0,
                support_score=23,
                selection_rank=1,
            ),
            _row(
                "Weak Evidence Zero Match",
                project_id="weak_zero",
                final_score=0,
                coverage=0.0,
                support_score=4,
            ),
        ]

        result = build_low_confidence_project_selection(
            ranked_rows=rows,
            selected_count=1,
        )
        candidates = result["eligible_low_confidence_candidates"]

        self.assertEqual("high", candidates[0]["fallback_suitability"])
        self.assertEqual("none", candidates[0]["jd_coverage"])
        self.assertEqual("low", candidates[1]["fallback_suitability"])
        self.assertEqual("none", candidates[1]["jd_coverage"])
        self.assertEqual(0, rows[0]["final_score"])
        self.assertEqual(0.0, rows[0]["deterministic_coverage_score"])

    def test_no_low_confidence_ui_needed_when_all_selected_have_coverage(self):
        rows = [
            _row(
                "Direct Project",
                project_id="direct",
                final_score=70,
                coverage=25.0,
                support_score=20,
                selection_rank=1,
                match_label="direct",
            ),
            _row(
                "Transferable Project",
                project_id="transferable",
                final_score=45,
                coverage=12.0,
                support_score=18,
                selection_rank=2,
                match_label="transferable",
            ),
            _row(
                "Unused Zero Project",
                project_id="unused",
                final_score=0,
                coverage=0.0,
                support_score=20,
            ),
        ]

        result = build_low_confidence_project_selection(
            ranked_rows=rows,
            selected_count=2,
        )

        self.assertFalse(result["active"])
        self.assertEqual(0, result["fallback_slot_count"])
        self.assertEqual([], result["default_low_confidence_project_ids"])

    def test_unselected_alternatives_have_stable_fallback_order(self):
        selected = _row(
            "Selected Zero",
            project_id="selected",
            final_score=0,
            coverage=0.0,
            support_score=20,
            selection_rank=1,
        )
        alpha = _row(
            "Alpha Alternative",
            project_id="alpha",
            final_score=0,
            coverage=0.0,
            support_score=18,
        )
        beta = _row(
            "Beta Alternative",
            project_id="beta",
            final_score=0,
            coverage=0.0,
            support_score=18,
        )

        first = build_low_confidence_project_selection(
            ranked_rows=[selected, beta, alpha],
            selected_count=1,
        )
        second = build_low_confidence_project_selection(
            ranked_rows=[selected, alpha, beta],
            selected_count=1,
        )

        self.assertEqual(
            ["selected", "alpha", "beta"],
            [
                item["project_id"]
                for item in first[
                    "eligible_low_confidence_candidates"
                ]
            ],
        )
        self.assertEqual(
            [
                item["project_id"]
                for item in first[
                    "eligible_low_confidence_candidates"
                ]
            ],
            [
                item["project_id"]
                for item in second[
                    "eligible_low_confidence_candidates"
                ]
            ],
        )

    def test_project_tailor_exposes_low_confidence_metadata(self):
        source = Path(
            "tailoring/project_section_tailor.py"
        ).read_text(encoding="utf-8")

        # Patch 2 intentionally replaced the patch-1-only metadata builder
        # assignment with the override-aware policy helper. Keep this
        # regression test focused on the contract rather than the old
        # implementation spelling.
        self.assertIn(
            "apply_low_confidence_project_override(",
            source,
        )
        self.assertIn(
            "low_confidence_selection,",
            source,
        )
        self.assertIn(
            '"low_confidence_selection": low_confidence_selection,',
            source,
        )
        self.assertIn(
            '"fallback_slot_count": int(',
            source,
        )


if __name__ == "__main__":
    unittest.main()

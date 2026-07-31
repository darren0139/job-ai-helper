from __future__ import annotations

import unittest
from unittest.mock import patch

from tailoring.phase9a_evidence_opportunity import (
    build_evidence_opportunity_analysis,
    build_opportunity_fingerprint,
    build_opportunity_resume_profile,
    select_evidence_opportunities,
)


REQUIREMENTS = [
    {
        "requirement_id": "req_python",
        "text": "Hands-on experience with Python",
        "importance": "required",
        "match_label": "none",
        "evidence_strength": 0,
    },
    {
        "requirement_id": "req_react",
        "text": "Experience with React",
        "importance": "required",
        "match_label": "none",
        "evidence_strength": 0,
    },
]


def stable(score: int = 20, rows=None):
    return {
        "deterministic_alignment_score": score,
        "alignment_band": "weak alignment",
        "required_core_coverage_score": score,
        "preferred_coverage_score": 0,
        "evidence_strength_score": 20,
        "canonical_requirements": rows or REQUIREMENTS,
        "input_fingerprint": "baseline-fingerprint",
    }


BASELINE_REPORT = {
    "stable_analysis": stable(),
    "resume_profile": {
        "projects": [{"title": "Existing", "bullets": ["Existing work"]}],
        "experience": [],
        "education": [],
        "skills": {"Programming": ["C++"]},
    },
    "jd_profile": {},
    "keyword_match": {"present": [], "missing": []},
    "bullets": {"bullet_quality_avg": 80},
    "structure": {"structure_score": 100},
}


EVIDENCE = [
    {
        "id": 1,
        "category": "Project",
        "title": "Job AI Helper",
        "description": "Built a Python Streamlit application.",
        "period": "2025",
        "skills": ["Python", "Streamlit"],
        "tools": ["SQLite"],
        "impact": "Delivered an AI application.",
    },
    {
        "id": 2,
        "category": "Project",
        "title": "QueryAI",
        "description": "Built React help-desk workflows.",
        "period": "2025",
        "skills": ["React"],
        "tools": ["PostgreSQL"],
        "impact": "Delivered frontend workflows.",
    },
]


def matcher(*, requirement, candidate_evidence_text):
    text = requirement["text"].lower()
    evidence = candidate_evidence_text.lower()
    if "python" in text and "python" in evidence:
        return {
            "label": "direct",
            "capability_id": "programming.python",
            "reason": "test",
            "taxonomy_version": "test",
        }
    if "react" in text and "react" in evidence:
        return {
            "label": "direct",
            "capability_id": "web.react",
            "reason": "test",
            "taxonomy_version": "test",
        }
    return {
        "label": "none",
        "capability_id": None,
        "reason": "test",
        "taxonomy_version": "test",
    }


class Phase9AEvidenceOpportunityTests(unittest.TestCase):
    @patch(
        "tailoring.phase9a_evidence_opportunity."
        "match_requirement_to_candidate",
        side_effect=matcher,
    )
    def test_selection_uses_weighted_supported_gain(self, _):
        selected = select_evidence_opportunities(
            stable_analysis=stable(),
            evidence_items=EVIDENCE,
            max_projects=2,
        )
        self.assertEqual(len(selected), 2)
        self.assertEqual(
            {row["item"]["title"] for row in selected},
            {"Job AI Helper", "QueryAI"},
        )
        self.assertTrue(
            all(row["incremental_points"] > 0 for row in selected)
        )

    def test_profile_respects_project_bullet_and_skill_constraints(self):
        selected = [
            {
                "item": {
                    **EVIDENCE[0],
                    "description": "First bullet\nSecond bullet\nThird bullet",
                },
                "matches": [],
                "incremental_points": 1,
            }
        ]
        profile = build_opportunity_resume_profile(
            baseline_resume_profile=BASELINE_REPORT["resume_profile"],
            selected=selected,
            max_bullets_per_project=2,
            max_skills=1,
        )
        self.assertEqual(
            len(profile["projects"][-1]["bullets"]),
            2,
        )
        self.assertEqual(
            len(profile["skills"]["Evidence-backed additions"]),
            1,
        )

    def test_fingerprint_changes_when_evidence_changes(self):
        first = build_opportunity_fingerprint(
            baseline_report=BASELINE_REPORT,
            raw_jd_text="Job Requirements\nPython",
            evidence_items=EVIDENCE,
            max_projects=3,
            max_bullets_per_project=2,
            max_skills=20,
        )
        second = build_opportunity_fingerprint(
            baseline_report=BASELINE_REPORT,
            raw_jd_text="Job Requirements\nPython",
            evidence_items=[
                {**EVIDENCE[0], "description": "Changed"},
                EVIDENCE[1],
            ],
            max_projects=3,
            max_bullets_per_project=2,
            max_skills=20,
        )
        self.assertNotEqual(first, second)

    @patch(
        "tailoring.phase9a_evidence_opportunity."
        "match_requirement_to_candidate",
        side_effect=matcher,
    )
    @patch(
        "tailoring.phase9a_evidence_opportunity."
        "build_stable_analysis"
    )
    def test_complete_analysis_is_forecast_and_zero_cost(
        self,
        mocked_stable,
        _,
    ):
        potential_rows = [
            {**REQUIREMENTS[0], "match_label": "direct"},
            {**REQUIREMENTS[1], "match_label": "direct"},
        ]
        mocked_stable.return_value = stable(70, potential_rows)

        result = build_evidence_opportunity_analysis(
            application_id=7,
            baseline_report=BASELINE_REPORT,
            raw_jd_text=(
                "Job Description\n\nBuild software.\n\n"
                "Job Requirements\n\nPython\nReact"
            ),
            evidence_items=EVIDENCE,
            max_projects=2,
            max_bullets_per_project=2,
            max_skills=10,
        )

        self.assertEqual(result["baseline_score"], 20)
        self.assertEqual(result["potential_score"], 70)
        self.assertEqual(result["score_delta"], 50)
        self.assertEqual(
            result["analysis_mode"],
            "zero_cost_deterministic_forecast",
        )
        self.assertTrue(result["comparison_valid"])
        self.assertEqual(
            mocked_stable.call_args.kwargs["raw_jd_text"],
            (
                "Job Description\n\nBuild software.\n\n"
                "Job Requirements\n\nPython\nReact"
            ),
        )


if __name__ == "__main__":
    unittest.main()

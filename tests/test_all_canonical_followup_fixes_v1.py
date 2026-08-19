from __future__ import annotations

import unittest
from pathlib import Path

from tailoring.project_section_tailor import build_project_candidate_pool
from tailoring.stable_tailoring_ranking import (
    _collect_supported_skill_candidates,
    _normalise_skill_key,
)


ROOT = Path(__file__).resolve().parents[1]


class AllCanonicalFollowupFixesTests(unittest.TestCase):
    def test_evidence_library_metadata_wins_for_matching_project(self) -> None:
        pool = build_project_candidate_pool(
            resume_profile={
                "projects": [
                    {
                        "title": "Job AI Helper",
                        "date": "May 2026 - Jul 2026",
                        "bullets": ["Old resume bullet."],
                    }
                ]
            },
            evidence_items=[
                {
                    "category": "Project",
                    "title": "Job AI Helper (Python, Streamlit, Solo)",
                    "period": "May 2026 - Aug 2026",
                    "description": "Current canonical bullet.",
                    "skills": [],
                    "tools": [],
                    "impact": "",
                }
            ],
        )
        self.assertEqual(len(pool), 1)
        project = pool[0]
        self.assertEqual(
            project["title"],
            "Job AI Helper",
        )
        self.assertEqual(
            project["display_title"],
            "Job AI Helper",
        )
        self.assertEqual(
            project["resume_header_tools"],
            ["Python", "Streamlit"],
        )
        self.assertEqual(
            project["resume_header_context"],
            ["Solo"],
        )
        self.assertEqual(
            project["period"],
            "May 2026 - Aug 2026",
        )
        self.assertEqual(
            project["resume_evidence"]["bullets"],
            ["Old resume bullet."],
        )
        self.assertEqual(
            project["evidence_library_evidence"]["bullets"],
            ["Current canonical bullet."],
        )

    def test_evidence_library_spelling_wins_for_equivalent_skill(self) -> None:
        candidates = _collect_supported_skill_candidates(
            resume_profile={
                "skills": {
                    "tools": [
                        "GitHub",
                        "GitHub Actions CI",
                    ]
                }
            },
            evidence_items=[
                {
                    "category": "Project",
                    "title": "Job AI Helper",
                    "skills": [],
                    "tools": [
                        "GitHub",
                        "GitHub Actions (CI)",
                    ],
                }
            ],
            selected_project_identity_index={},
            raw_result={},
        )
        key = _normalise_skill_key("GitHub Actions CI")
        self.assertIn(key, candidates)
        self.assertEqual(
            candidates[key]["skill"],
            "GitHub Actions (CI)",
        )

    def test_app_uses_effective_all_canonical_fitter_ceiling(self) -> None:
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn(
            "resolve_effective_fitting_bullet_ceiling(",
            app,
        )
        self.assertIn(
            "max_bullets_per_project=fit_max_bullets_per_project",
            app,
        )
        self.assertIn(
            '"fit_effective_max_bullets": fit_max_bullets_per_project',
            app,
        )
        self.assertIn(
            '"bullet_allocation_mode": (',
            app,
        )

    def test_skills_preview_is_content_fingerprinted(self) -> None:
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn(
            "skills_preview_fingerprint = (",
            app,
        )
        self.assertIn(
            'f"skills_preview_{current_application_id}_"',
            app,
        )


if __name__ == "__main__":
    unittest.main()

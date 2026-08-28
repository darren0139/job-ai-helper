from __future__ import annotations

import unittest
from pathlib import Path

from tailoring.stable_tailoring_ranking import (
    build_project_selection_preview,
    rank_projects_deterministically,
    select_complementary_projects,
)


def _candidate(title: str, text: str, tools: list[str]) -> dict:
    return {
        "title": title,
        "display_title": title,
        "currently_in_resume": True,
        "in_evidence_library": True,
        "period": "2026",
        "resume_evidence": {
            "description": "",
            "bullets": [text],
            "skills": [],
            "tools": [],
            "impact": "",
        },
        "evidence_library_evidence": {
            "description": text,
            "bullets": [text],
            "skills": [],
            "tools": tools,
            "impact": "Delivered a complete project.",
        },
    }


class PreGenerationProjectSelectionPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = {
            "canonical_requirements": [
                {
                    "requirement_id": "req_android",
                    "text": "Experience working with Android app development and Kotlin",
                    "atomic_focus": "Experience working with Android app development and Kotlin",
                    "parent_text": "Experience working with Android app development and Kotlin",
                    "variants": [],
                    "importance": "preferred",
                    "group_weight_fraction": 1.0,
                    "capability_taxonomy_cap_status": "unrecognised",
                }
            ]
        }
        self.candidates = [
            _candidate(
                "Android Project",
                "Led Android app development using Kotlin and Jetpack Compose.",
                ["Kotlin", "Android Studio"],
            ),
            _candidate(
                "Alpha Fallback",
                "Implemented a complete unrelated software tool.",
                ["Python", "SQLite"],
            ),
            _candidate(
                "Beta Fallback",
                "Implemented another unrelated software tool.",
                ["Python"],
            ),
        ]

    def test_preview_matches_same_deterministic_rank_select_pipeline(self):
        preview = build_project_selection_preview(
            project_candidates=self.candidates,
            stable_analysis=self.analysis,
            selected_count=2,
        )
        noisy_rows = [
            {
                "title": candidate["title"],
                "display_title": candidate["display_title"],
                "final_score": 999 - index,
                "requirement_matches": [
                    {
                        "requirement_id": "req_android",
                        "match_label": "direct",
                        "evidence_snippets": ["unsupported model claim"],
                    }
                ],
                "matched_jd_requirements": [],
                "transferable_jd_requirements": [],
            }
            for index, candidate in enumerate(reversed(self.candidates))
        ]
        ranked, _ = rank_projects_deterministically(
            ranked_rows=noisy_rows,
            project_candidates=self.candidates,
            stable_analysis=self.analysis,
        )
        selected, _ = select_complementary_projects(
            ranked_rows=ranked,
            selected_count=2,
        )
        self.assertEqual(
            [item["project_id"] for item in preview["system_selected_projects"]],
            [row["project_id"] for row in selected[:2]],
        )

    def test_preview_exposes_zero_cost_fallback_contract(self):
        preview = build_project_selection_preview(
            project_candidates=self.candidates,
            stable_analysis=self.analysis,
            selected_count=3,
        )
        self.assertEqual(
            "phase6b1-pre-generation-project-selection-v1",
            preview["preview_version"],
        )
        self.assertTrue(preview["preview_fingerprint"])
        low = preview["low_confidence_selection"]
        self.assertTrue(low["active"])
        self.assertGreaterEqual(low["fallback_slot_count"], 1)
        self.assertTrue(low["eligible_low_confidence_candidates"])

    def test_app_places_selector_before_paid_generate(self):
        source = Path("app.py").read_text(encoding="utf-8")
        preview_at = source.index("build_project_selection_preview(")
        generate_at = source.index('key=f"generate_projects_skills_')
        self.assertLess(preview_at, generate_at)
        self.assertIn("Save project selection", source)
        self.assertIn("Save this project selection before generating.", source)
        self.assertIn("or not low_confidence_project_selection_ready", source)

    def test_post_generation_selector_is_read_only_provenance(self):
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("Project selection used for this Draft", source)
        self.assertIn("User override:", source)
        self.assertNotIn("Use selected projects on next Generate", source)

    def test_debug_bundle_keeps_pre_generation_preview(self):
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn('"pre_generation_preview": deepcopy(', source)
        self.assertIn("low_confidence_project_selection_preview_", source)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from tailoring.jd_specific_rephrase_preview import (
    build_rephrase_preview_context,
    build_rephrased_generation_candidate,
    validate_rephrase_suggestion,
)


class JDSpecificRephrasePreviewTests(unittest.TestCase):
    def _generation(self):
        return {
            "generation_id": "gen-a",
            "projects": {
                "recommended_projects": [
                    {
                        "project_id": "p1",
                        "title": "CyberSphere",
                        "display_title": "CyberSphere — Shooter Game",
                        "subtitle": "Shooter Game",
                        "period": "Jan 2018 - Feb 2018",
                        "resume_header_tools": ["C#", "Unity Engine"],
                        "resume_header_context": [
                            "Published on Google Play",
                            "Team of 2",
                        ],
                        "canonical_tools": ["C#", "Unity Engine"],
                        "selected_blueprint_bullets": [
                            (
                                "Built gameplay and UI features in a small team, "
                                "contributing to a completed mobile game released "
                                "on Google Play."
                            )
                        ],
                        "draft_bullets": [
                            (
                                "Built gameplay and UI features in a small team, "
                                "contributing to a completed mobile game released "
                                "on Google Play."
                            )
                        ],
                        "compact_bullets": [
                            (
                                "Built gameplay and UI features for a completed "
                                "mobile game released on Google Play."
                            )
                        ],
                    }
                ]
            },
            "skills": {
                "skill_lines": [
                    {"category": "Game & Engine", "items": ["C#", "Unity Engine"]}
                ]
            },
            "candidate_pool": [
                {
                    "project_id": "p1",
                    "title": "CyberSphere",
                    "evidence_library_evidence": {
                        "bullets": [
                            (
                                "Built gameplay and UI features in a small team, "
                                "contributing to a completed mobile game released "
                                "on Google Play."
                            )
                        ]
                    },
                }
            ],
            "project_inputs": {
                "evidence_items": [
                    {
                        "id": 1,
                        "project_id": "p1",
                        "title": "CyberSphere",
                        "description": "Published mobile shooter game.",
                        "tools": ["C#", "Unity Engine"],
                    }
                ]
            },
            "fit_result": {
                "fit_one_page": True,
                "docx_path": "old.docx",
            },
            "docx_path": "old.docx",
            "pdf_path": "old.pdf",
        }

    def _report(self):
        return {
            "resume_profile": {
                "projects": [],
                "experience": [],
                "education": [],
                "skills": {},
            },
            "jd_profile": {
                "responsibilities": ["Support game configuration and QA workflows."]
            },
            "raw_jd_text": "Support game configuration and QA workflows.",
            "keyword_match": {"present": [], "missing": []},
            "bullets": {"bullet_quality_avg": 0},
            "structure": {"structure_score": 0},
        }

    def test_context_uses_canonical_current_and_frozen_generation_evidence(self):
        context = build_rephrase_preview_context(
            generation=self._generation(),
            project_index=0,
            bullet_index=0,
            baseline_report=self._report(),
        )
        self.assertEqual(context["project_id"], "p1")
        self.assertIn("Google Play", context["canonical_bullet"])
        self.assertIn("Unity Engine", " ".join(context["frozen_project_evidence"]))
        self.assertFalse(context["live_evidence_library_used"])
        self.assertFalse(context["historical_phase8_used"])

    def test_preview_guard_rejects_new_number(self):
        context = build_rephrase_preview_context(
            generation=self._generation(),
            project_index=0,
            bullet_index=0,
            baseline_report=self._report(),
        )
        result = validate_rephrase_suggestion(
            context=context,
            suggested_bullet=(
                "Built gameplay and UI features for 500 players using Unity Engine."
            ),
        )
        self.assertFalse(result["safe_for_lineage_evaluation"])
        self.assertIn("introduced_number", result["guard_reasons"])

    def test_candidate_changes_only_bullet_and_clears_stale_fit(self):
        generation = self._generation()
        original_project = generation["projects"]["recommended_projects"][0]
        candidate = build_rephrased_generation_candidate(
            generation=generation,
            project_index=0,
            bullet_index=0,
            accepted_bullet=(
                "Built gameplay and UI features for a completed mobile game "
                "released on Google Play."
            ),
        )
        changed = candidate["projects"]["recommended_projects"][0]

        for field in (
            "title",
            "display_title",
            "subtitle",
            "period",
            "resume_header_tools",
            "resume_header_context",
            "canonical_tools",
        ):
            self.assertEqual(changed[field], original_project[field])

        self.assertNotEqual(
            changed["draft_bullets"][0],
            original_project["draft_bullets"][0],
        )
        self.assertEqual(changed["compact_bullets"], [])
        self.assertIsNone(candidate["fit_result"])
        self.assertEqual(candidate["docx_path"], "")
        self.assertEqual(candidate["pdf_path"], "")

    def test_candidate_does_not_mutate_source_generation(self):
        generation = self._generation()
        before = generation["projects"]["recommended_projects"][0]["draft_bullets"][0]
        build_rephrased_generation_candidate(
            generation=generation,
            project_index=0,
            bullet_index=0,
            accepted_bullet=(
                "Built gameplay and UI features for a completed mobile game."
            ),
        )
        self.assertEqual(
            generation["projects"]["recommended_projects"][0]["draft_bullets"][0],
            before,
        )


if __name__ == "__main__":
    unittest.main()

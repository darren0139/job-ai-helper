from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from resume_builder.fitting_render_optimizer import (
    PHASE6C1_OPTIMIZATION_VERSION,
    build_render_state_fingerprint,
    candidate_protection_tier,
    group_candidates_by_protection_tier,
    rendered_candidate_is_effective,
    source_docx_signature,
)


class FittingRenderOptimizerTests(unittest.TestCase):
    def test_grouping_is_ascending_and_ordered(self):
        candidates = [
            {
                "candidate_order": 4,
                "change": {"protection_tier": 1},
            },
            {
                "candidate_order": 3,
                "change": {"protection_tier": 0},
            },
            {
                "candidate_order": 1,
                "change": {"protection_tier": 0},
            },
        ]

        grouped = group_candidates_by_protection_tier(candidates)

        self.assertEqual([tier for tier, _ in grouped], [0, 1])
        self.assertEqual(
            [
                row["candidate_order"]
                for row in grouped[0][1]
            ],
            [1, 3],
        )

    def test_missing_or_invalid_tier_is_safe_zero(self):
        self.assertEqual(candidate_protection_tier({}), 0)
        self.assertEqual(
            candidate_protection_tier(
                {"change": {"protection_tier": "bad"}}
            ),
            0,
        )
        self.assertEqual(
            candidate_protection_tier(
                {"change": {"protection_tier": -4}}
            ),
            0,
        )

    def test_effective_candidate_rule_matches_phase6c(self):
        self.assertTrue(
            rendered_candidate_is_effective(
                {
                    "reaches_one_page": True,
                    "space_saved_ratio": 0.0,
                },
                layout_effect_threshold=0.002,
            )
        )
        self.assertTrue(
            rendered_candidate_is_effective(
                {
                    "reaches_one_page": False,
                    "space_saved_ratio": 0.01,
                },
                layout_effect_threshold=0.002,
            )
        )
        self.assertFalse(
            rendered_candidate_is_effective(
                {
                    "reaches_one_page": False,
                    "space_saved_ratio": 0.001,
                },
                layout_effect_threshold=0.002,
            )
        )

    def test_fingerprint_ignores_non_render_metadata(self):
        projects = {
            "recommended_projects": [
                {
                    "display_title": "QueryAI",
                    "period": "2026",
                    "draft_bullets": ["Built a secure workflow."],
                    "notes_for_user": ["first note"],
                    "bullet_evidence_priorities": [
                        {"evidence_value": 50}
                    ],
                }
            ]
        }
        changed_metadata = {
            "recommended_projects": [
                {
                    "display_title": "QueryAI",
                    "period": "2026",
                    "draft_bullets": ["Built a secure workflow."],
                    "notes_for_user": ["different note"],
                    "bullet_evidence_priorities": [
                        {"evidence_value": 999}
                    ],
                }
            ]
        }
        options = {"spacing_mode": "paragraph_spacing"}

        first = build_render_state_fingerprint(
            source_signature="source",
            projects_state=projects,
            skills_state=None,
            layout_options=options,
        )
        second = build_render_state_fingerprint(
            source_signature="source",
            projects_state=changed_metadata,
            skills_state=None,
            layout_options=options,
        )

        self.assertEqual(first, second)

    def test_fingerprint_changes_for_rendered_content(self):
        base = {
            "recommended_projects": [
                {
                    "display_title": "QueryAI",
                    "period": "2026",
                    "draft_bullets": ["Built a secure workflow."],
                }
            ]
        }
        changed = {
            "recommended_projects": [
                {
                    "display_title": "QueryAI",
                    "period": "2026",
                    "draft_bullets": ["Built a different workflow."],
                }
            ]
        }

        first = build_render_state_fingerprint(
            source_signature="source",
            projects_state=base,
            skills_state=None,
            layout_options={},
        )
        second = build_render_state_fingerprint(
            source_signature="source",
            projects_state=changed,
            skills_state=None,
            layout_options={},
        )

        self.assertNotEqual(first, second)

    def test_fingerprint_changes_for_project_header_metadata(self):
        base = {
            "recommended_projects": [
                {
                    "title": "CyberSphere",
                    "display_title": "CyberSphere — Shooter Game",
                    "subtitle": "Shooter Game",
                    "resume_header_tools": ["C#", "Unity Engine"],
                    "resume_header_context": ["Published on Google Play", "Team of 2"],
                    "canonical_tools": ["C#", "Unity Engine"],
                    "period": "2018",
                    "draft_bullets": ["Built gameplay features."],
                }
            ]
        }
        changed = copy.deepcopy(base)
        changed["recommended_projects"][0]["resume_header_context"] = ["Team of 2"]

        first = build_render_state_fingerprint(
            source_signature="source", projects_state=base,
            skills_state=None, layout_options={"project_header_layout": "stacked"},
        )
        second = build_render_state_fingerprint(
            source_signature="source", projects_state=changed,
            skills_state=None, layout_options={"project_header_layout": "stacked"},
        )
        self.assertNotEqual(first, second)

    def test_source_signature_is_content_based(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.docx"
            second = Path(directory) / "second.docx"
            first.write_bytes(b"same-content")
            second.write_bytes(b"same-content")

            self.assertEqual(
                source_docx_signature(first),
                source_docx_signature(second),
            )

            second.write_bytes(b"different-content")
            self.assertNotEqual(
                source_docx_signature(first),
                source_docx_signature(second),
            )

    def test_version_is_explicit(self):
        self.assertEqual(
            PHASE6C1_OPTIMIZATION_VERSION,
            "phase6c1-exact-safe-render-v2-format-metadata",
        )


if __name__ == "__main__":
    unittest.main()

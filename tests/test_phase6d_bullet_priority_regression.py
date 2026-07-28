from __future__ import annotations

import unittest
from unittest.mock import patch

from tailoring import deterministic_bullet_allocation as allocation
from tailoring.capability_taxonomy import evaluate_evidence
from tailoring.stable_tailoring_ranking import (
    build_bullet_evidence_priorities,
)


class Phase6DBulletPriorityRegressionTests(unittest.TestCase):
    def test_sentence_end_proxy_matches_attention_detail(self):
        result = evaluate_evidence(
            {
                "text": "High attention to detail",
                "atomic_focus": "High attention to detail",
            },
            (
                "Built a C++ asset manager for a custom game engine, "
                "centralising asset loading and improving pipeline consistency."
            ),
        )
        self.assertEqual(
            result["capability_id"],
            "quality.attention_detail",
        )
        self.assertEqual(result["label"], "weak")

    def test_weak_core_match_does_not_receive_unique_core_bonus(self):
        rows = build_bullet_evidence_priorities(
            bullets=["Set up database access-control policies."],
            ranking_row={
                "requirement_matches": [
                    {
                        "requirement_id": "req_configuration",
                        "requirement_text": "gaming product configuration",
                        "match_label": "weak",
                        "importance": "core",
                        "coverage_points": 1.5,
                    }
                ]
            },
        )
        self.assertEqual(
            rows[0]["unique_required_core_count"],
            0,
        )
        self.assertIn(
            "req_configuration",
            rows[0]["protected_requirement_ids"],
        )
        self.assertTrue(rows[0]["protect_during_fitting"])

    def test_technical_ownership_beats_weak_teamwork(self):
        bullets = [
            (
                "Built a C++ asset manager for a custom game engine, "
                "centralising asset loading and improving pipeline consistency."
            ),
            (
                "Integrated FMOD audio systems into gameplay features, "
                "supporting audio proximity logic in the custom engine."
            ),
            (
                "Contributed to engine-level systems and gameplay feature "
                "support in an 8-person team project."
            ),
            (
                "Collaborated with a custom-engine team to integrate systems "
                "across asset loading, audio, and gameplay workflows."
            ),
        ]
        direct_game = {
            "requirement_id": "req_game",
            "match_label": "direct",
            "importance": "required",
            "coverage_points": 10.0,
        }
        weak_cross = {
            "requirement_id": "req_cross",
            "match_label": "weak",
            "importance": "required",
            "coverage_points": 3.75,
        }
        weak_detail = {
            "requirement_id": "req_detail",
            "match_label": "weak",
            "importance": "preferred",
            "coverage_points": 3.0,
        }

        configured = {
            bullets[0]: {
                "supported_requirement_ids": [
                    "req_game",
                    "req_detail",
                ],
                "protected_requirement_ids": [
                    "req_detail",
                ],
                "unique_required_core_count": 0,
                "evidence_value": 13.0,
                "evidence_priority": 1,
            },
            bullets[1]: {
                "supported_requirement_ids": ["req_game"],
                "protected_requirement_ids": [],
                "unique_required_core_count": 0,
                "evidence_value": 10.0,
                "evidence_priority": 2,
            },
            bullets[2]: {
                "supported_requirement_ids": [
                    "req_game",
                    "req_cross",
                ],
                "protected_requirement_ids": [],
                "unique_required_core_count": 0,
                "evidence_value": 13.75,
                "evidence_priority": 3,
            },
            bullets[3]: {
                "supported_requirement_ids": [
                    "req_game",
                    "req_cross",
                ],
                "protected_requirement_ids": [
                    "req_cross",
                ],
                "unique_required_core_count": 0,
                "evidence_value": 13.75,
                "evidence_priority": 4,
            },
        }

        def fake_priorities(*, bullets, ranking_row):
            return [
                {
                    "bullet_index": index,
                    "bullet_text": bullet,
                    **configured[bullet],
                }
                for index, bullet in enumerate(bullets)
            ]

        candidate = {
            "title": "The Great Migration",
            "display_title": (
                "The Great Migration "
                "(C++ Custom Engine, Team of 8)"
            ),
            "evidence_library_evidence": {
                "bullets": bullets,
                "tools": [
                    "C++",
                    "Custom Game Engine",
                    "FMOD",
                ],
                "skills": [
                    "asset management",
                    "audio systems",
                    "team collaboration",
                ],
            },
        }
        ranking_row = {
            "project_id": "project_tgm",
            "final_score": 50,
            "requirement_matches": [
                direct_game,
                weak_cross,
                weak_detail,
            ],
        }

        with patch.object(
            allocation,
            "build_bullet_evidence_priorities",
            side_effect=fake_priorities,
        ):
            result = (
                allocation
                .build_deterministic_bullet_allocation(
                    selected_pairs=[
                        (candidate, ranking_row),
                    ],
                    max_bullets_per_project=2,
                )
            )

        self.assertEqual(
            result["projects"][0][
                "allocated_blueprint_bullets"
            ],
            bullets[:2],
        )


if __name__ == "__main__":
    unittest.main()


from __future__ import annotations

import unittest
from unittest.mock import patch

from tailoring import deterministic_bullet_allocation as allocation


def _fake_priority_builder(
    *,
    bullets,
    ranking_row,
):
    configured = ranking_row.get(
        "_test_bullet_priorities",
        {},
    )
    rows = []
    for index, bullet in enumerate(bullets):
        details = configured.get(
            bullet,
            {},
        )
        rows.append(
            {
                "bullet_index": index,
                "bullet_text": bullet,
                "supported_requirement_ids": details.get(
                    "supported_requirement_ids",
                    [],
                ),
                "protected_requirement_ids": details.get(
                    "protected_requirement_ids",
                    [],
                ),
                "unique_required_core_count": details.get(
                    "unique_required_core_count",
                    0,
                ),
                "evidence_value": details.get(
                    "evidence_value",
                    0.0,
                ),
                "protect_during_fitting": bool(
                    details.get(
                        "protected_requirement_ids",
                        [],
                    )
                ),
                "evidence_priority": details.get(
                    "evidence_priority",
                    index + 1,
                ),
            }
        )
    return rows


def _pair(
    title: str,
    *,
    bullet_requirement_counts: list[int],
    score: int,
):
    bullets = [
        (
            f"{title} bullet {index + 1} implemented "
            f"distinct feature {index + 1}."
        )
        for index in range(
            len(bullet_requirement_counts)
        )
    ]
    requirement_matches = []
    priorities = {}

    for bullet_index, (
        bullet,
        requirement_count,
    ) in enumerate(
        zip(
            bullets,
            bullet_requirement_counts,
            strict=True,
        )
    ):
        requirement_ids = [
            (
                f"{title.lower()}_requirement_"
                f"{bullet_index}_{item_index}"
            )
            for item_index in range(
                requirement_count
            )
        ]
        for requirement_id in requirement_ids:
            requirement_matches.append(
                {
                    "requirement_id": (
                        requirement_id
                    ),
                    "match_label": "direct",
                    "importance": "required",
                    "coverage_points": 10.0,
                }
            )

        priorities[bullet] = {
            "supported_requirement_ids": (
                requirement_ids
            ),
            "protected_requirement_ids": (
                requirement_ids
            ),
            "unique_required_core_count": len(
                requirement_ids
            ),
            "evidence_value": float(
                10 * requirement_count
            ),
            "evidence_priority": (
                bullet_index + 1
            ),
        }

    candidate = {
        "title": title,
        "display_title": title,
        "evidence_library_evidence": {
            "description": "\n".join(bullets),
            "bullets": bullets,
            "skills": [],
            "tools": [],
            "impact": "",
        },
    }
    ranking_row = {
        "project_id": f"project_{title.lower()}",
        "final_score": score,
        "requirement_matches": (
            requirement_matches
        ),
        "_test_bullet_priorities": priorities,
    }
    return candidate, ranking_row


class DeterministicBulletAllocationTests(
    unittest.TestCase
):
    def _allocate(
        self,
        pairs,
        maximum,
    ):
        with patch.object(
            allocation,
            "build_bullet_evidence_priorities",
            side_effect=_fake_priority_builder,
        ):
            return (
                allocation
                .build_deterministic_bullet_allocation(
                    selected_pairs=pairs,
                    max_bullets_per_project=(
                        maximum
                    ),
                )
            )

    def test_repeat_runs_are_identical(self):
        pairs = [
            _pair(
                "Alpha",
                bullet_requirement_counts=[
                    1,
                    1,
                    1,
                ],
                score=70,
            ),
            _pair(
                "Beta",
                bullet_requirement_counts=[
                    1,
                    1,
                    0,
                ],
                score=60,
            ),
            _pair(
                "Gamma",
                bullet_requirement_counts=[
                    1,
                    1,
                    0,
                ],
                score=50,
            ),
        ]

        first = self._allocate(pairs, 3)
        second = self._allocate(pairs, 3)

        self.assertEqual(first, second)
        self.assertEqual(
            first["allocation_version"],
            (
                allocation
                .BULLET_ALLOCATION_VERSION
            ),
        )

    def test_adaptive_allocation_can_be_3_3_2(self):
        pairs = [
            _pair(
                "Alpha",
                bullet_requirement_counts=[
                    1,
                    1,
                    1,
                ],
                score=60,
            ),
            _pair(
                "Beta",
                bullet_requirement_counts=[
                    1,
                    1,
                    1,
                ],
                score=55,
            ),
            _pair(
                "Gamma",
                bullet_requirement_counts=[
                    1,
                    1,
                    0,
                ],
                score=50,
            ),
        ]

        result = self._allocate(pairs, 3)
        counts = [
            project[
                "allocated_bullet_count"
            ]
            for project in result["projects"]
        ]

        self.assertEqual(counts, [3, 3, 2])
        self.assertEqual(
            result["total_allocated_bullets"],
            8,
        )

    def test_adaptive_allocation_can_fill_3_3_3(self):
        pairs = [
            _pair(
                "Alpha",
                bullet_requirement_counts=[
                    1,
                    1,
                    1,
                ],
                score=60,
            ),
            _pair(
                "Beta",
                bullet_requirement_counts=[
                    1,
                    1,
                    1,
                ],
                score=55,
            ),
            _pair(
                "Gamma",
                bullet_requirement_counts=[
                    1,
                    1,
                    1,
                ],
                score=50,
            ),
        ]

        result = self._allocate(pairs, 3)
        counts = [
            project[
                "allocated_bullet_count"
            ]
            for project in result["projects"]
        ]

        self.assertEqual(counts, [3, 3, 3])

    def test_maximum_four_is_respected(self):
        pairs = [
            _pair(
                "Alpha",
                bullet_requirement_counts=[
                    1,
                    1,
                    1,
                    1,
                    1,
                ],
                score=75,
            ),
            _pair(
                "Beta",
                bullet_requirement_counts=[
                    1,
                    1,
                    1,
                    1,
                ],
                score=70,
            ),
        ]

        result = self._allocate(pairs, 4)

        for project in result["projects"]:
            self.assertLessEqual(
                project[
                    "allocated_bullet_count"
                ],
                4,
            )
        self.assertEqual(
            [
                project[
                    "allocated_bullet_count"
                ]
                for project in result[
                    "projects"
                ]
            ],
            [4, 4],
        )

    def test_writer_cannot_change_allocated_count(self):
        allocation_plan = {
            "allocated_bullet_count": 3,
            "allocated_blueprint_bullets": [
                "Built the first supported feature.",
                "Implemented the second supported feature.",
                "Validated the third supported feature.",
            ],
        }
        writer_plan = {
            "selected_blueprint_bullets": [
                "Built the first supported feature.",
            ],
            "draft_bullets": [
                "Only one bullet was returned.",
            ],
            "compact_bullets": [
                "Only one compact bullet was returned.",
            ],
            "rewrite_reason": "",
        }

        corrected = (
            allocation
            .enforce_writer_plan_allocation(
                writer_plan=writer_plan,
                allocation_plan=allocation_plan,
            )
        )

        self.assertEqual(
            corrected["draft_bullets"],
            allocation_plan[
                "allocated_blueprint_bullets"
            ],
        )
        self.assertEqual(
            corrected[
                "selected_blueprint_bullets"
            ],
            allocation_plan[
                "allocated_blueprint_bullets"
            ],
        )
        self.assertEqual(
            corrected["compact_bullets"],
            [],
        )
        self.assertEqual(
            corrected[
                "bullet_allocation_version"
            ],
            (
                allocation
                .BULLET_ALLOCATION_VERSION
            ),
        )

    def test_writer_sees_only_allocated_canonical_bullets(
        self,
    ):
        pair = _pair(
            "Alpha",
            bullet_requirement_counts=[
                1,
                1,
                0,
            ],
            score=50,
        )
        result = self._allocate([pair], 2)
        prepared = (
            allocation
            .apply_bullet_allocation_to_selected_pairs(
                selected_pairs=[pair],
                allocation=result,
            )
        )

        candidate, _ = prepared[0]
        allocated = result["projects"][0][
            "allocated_blueprint_bullets"
        ]
        self.assertEqual(
            candidate[
                "evidence_library_evidence"
            ]["bullets"],
            allocated,
        )
        self.assertEqual(
            candidate[
                "_phase6b2_bullet_allocation"
            ]["allocated_bullet_count"],
            2,
        )


if __name__ == "__main__":
    unittest.main()

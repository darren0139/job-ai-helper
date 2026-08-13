from __future__ import annotations

import unittest
from pathlib import Path

from tailoring.deterministic_bullet_allocation import (
    BULLET_ALLOCATION_MODE_ADAPTIVE,
    BULLET_ALLOCATION_MODE_ALL_CANONICAL,
    BULLET_ALLOCATION_MODE_PREFER_AVAILABLE,
    build_deterministic_bullet_allocation,
    normalise_bullet_allocation_mode,
)

ROOT = Path(__file__).resolve().parents[1]


def _pair(
    *,
    bullet_count: int,
    project_id: str = "project_a",
) -> tuple[dict, dict]:
    bullets = [
        f"Implemented truthful canonical capability {i} using Python."
        for i in range(1, bullet_count + 1)
    ]
    candidate = {
        "title": f"Project {project_id}",
        "display_title": f"Project {project_id} (Python)",
        "evidence_library_evidence": {
            "bullets": bullets,
            "tools": ["Python"],
            "skills": [],
        },
    }
    ranking_row = {
        "project_id": project_id,
        "title": candidate["title"],
        "display_title": candidate["display_title"],
        "final_score": 40,
        "requirement_matches": [],
    }
    return candidate, ranking_row


class AllCanonicalBeforeFittingTests(unittest.TestCase):
    def test_all_canonical_ignores_prefit_bullet_limit(self) -> None:
        result = build_deterministic_bullet_allocation(
            selected_pairs=[_pair(bullet_count=6)],
            max_bullets_per_project=4,
            allocation_mode=BULLET_ALLOCATION_MODE_ALL_CANONICAL,
        )
        self.assertEqual(
            result["allocation_mode"],
            BULLET_ALLOCATION_MODE_ALL_CANONICAL,
        )
        self.assertFalse(result["bullet_limit_applied"])
        self.assertEqual(result["max_bullets_per_project"], 4)
        self.assertEqual(result["total_available_slots"], 6)
        self.assertEqual(result["total_allocated_bullets"], 6)
        project = result["projects"][0]
        self.assertFalse(project["bullet_limit_applied"])
        self.assertEqual(project["canonical_bullet_count"], 6)
        self.assertEqual(project["allocated_bullet_count"], 6)

    def test_prefer_available_still_respects_limit(self) -> None:
        result = build_deterministic_bullet_allocation(
            selected_pairs=[_pair(bullet_count=6)],
            max_bullets_per_project=4,
            allocation_mode=BULLET_ALLOCATION_MODE_PREFER_AVAILABLE,
        )
        self.assertTrue(result["bullet_limit_applied"])
        self.assertEqual(result["total_allocated_bullets"], 4)

    def test_adaptive_stays_backward_compatible(self) -> None:
        result = build_deterministic_bullet_allocation(
            selected_pairs=[_pair(bullet_count=6)],
            max_bullets_per_project=4,
            allocation_mode=BULLET_ALLOCATION_MODE_ADAPTIVE,
        )
        self.assertTrue(result["bullet_limit_applied"])
        self.assertLessEqual(result["total_allocated_bullets"], 4)

    def test_all_canonical_does_not_pad_missing_evidence(self) -> None:
        result = build_deterministic_bullet_allocation(
            selected_pairs=[_pair(bullet_count=2)],
            max_bullets_per_project=4,
            allocation_mode=BULLET_ALLOCATION_MODE_ALL_CANONICAL,
        )
        self.assertEqual(result["total_allocated_bullets"], 2)

    def test_all_canonical_repeat_runs_are_identical(self) -> None:
        kwargs = {
            "selected_pairs": [
                _pair(bullet_count=6, project_id="a"),
                _pair(bullet_count=3, project_id="b"),
            ],
            "max_bullets_per_project": 4,
            "allocation_mode": BULLET_ALLOCATION_MODE_ALL_CANONICAL,
        }
        first = build_deterministic_bullet_allocation(**kwargs)
        second = build_deterministic_bullet_allocation(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first["total_allocated_bullets"], 9)

    def test_aliases_normalise_to_all_canonical(self) -> None:
        for value in (
            "all canonical",
            "all canonical before fitting",
            "fit from all canonical evidence",
        ):
            self.assertEqual(
                normalise_bullet_allocation_mode(value),
                BULLET_ALLOCATION_MODE_ALL_CANONICAL,
            )

    def test_ui_keeps_prefer_available_as_default(self) -> None:
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"Fit from all canonical evidence"', app)
        self.assertIn('"prefer_available_evidence"', app)
        self.assertRegex(
            app,
            r'bullet_allocation_mode\s*==\s*"all_canonical_before_fitting"',
        )
        self.assertIn("Bullet limit is disabled in this mode", app)

    def test_project_tailor_uses_allocation_writer_ceiling(self) -> None:
        source = (
            ROOT / "tailoring" / "project_section_tailor.py"
        ).read_text(encoding="utf-8")
        self.assertIn("writer_bullet_ceiling = max(", source)
        self.assertIn("{writer_bullet_ceiling}", source)
        self.assertIn("writer_max_tokens = (", source)


if __name__ == "__main__":
    unittest.main()

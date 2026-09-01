from __future__ import annotations

import unittest
from pathlib import Path

from tailoring.deterministic_bullet_allocation import (
    BULLET_ALLOCATION_MODE_ADAPTIVE,
    BULLET_ALLOCATION_MODE_PREFER_AVAILABLE,
    build_deterministic_bullet_allocation,
    normalise_bullet_allocation_mode,
)

ROOT = Path(__file__).resolve().parents[1]


def _pair(*, bullet_count: int, project_id: str = "project_a") -> tuple[dict, dict]:
    bullets = [
        f"Implemented distinct canonical capability {index} using Python."
        for index in range(1, bullet_count + 1)
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
        # Deliberately below Adaptive's existing >=70 high-value expansion gate.
        "final_score": 40,
        "requirement_matches": [],
    }
    return candidate, ranking_row


class BulletAllocationPreferenceTests(unittest.TestCase):
    def test_adaptive_default_remains_compact(self) -> None:
        result = build_deterministic_bullet_allocation(
            selected_pairs=[_pair(bullet_count=4)],
            max_bullets_per_project=4,
        )
        self.assertEqual(result["allocation_mode"], BULLET_ALLOCATION_MODE_ADAPTIVE)
        self.assertEqual(result["total_allocated_bullets"], 2)
        self.assertEqual(result["projects"][0]["allocated_bullet_count"], 2)

    def test_prefer_available_fills_canonical_capacity(self) -> None:
        result = build_deterministic_bullet_allocation(
            selected_pairs=[_pair(bullet_count=4)],
            max_bullets_per_project=4,
            allocation_mode=BULLET_ALLOCATION_MODE_PREFER_AVAILABLE,
        )
        self.assertEqual(
            result["allocation_mode"],
            BULLET_ALLOCATION_MODE_PREFER_AVAILABLE,
        )
        self.assertEqual(result["total_allocated_bullets"], 4)
        project = result["projects"][0]
        self.assertEqual(project["canonical_bullet_count"], 4)
        self.assertEqual(project["allocated_bullet_count"], 4)
        self.assertEqual(len(project["allocated_bullet_ids"]), 4)

    def test_prefer_available_never_pads_to_limit(self) -> None:
        result = build_deterministic_bullet_allocation(
            selected_pairs=[_pair(bullet_count=2)],
            max_bullets_per_project=4,
            allocation_mode=BULLET_ALLOCATION_MODE_PREFER_AVAILABLE,
        )
        project = result["projects"][0]
        self.assertEqual(project["canonical_bullet_count"], 2)
        self.assertEqual(project["allocated_bullet_count"], 2)

    def test_prefer_available_respects_limit(self) -> None:
        result = build_deterministic_bullet_allocation(
            selected_pairs=[_pair(bullet_count=6)],
            max_bullets_per_project=4,
            allocation_mode=BULLET_ALLOCATION_MODE_PREFER_AVAILABLE,
        )
        project = result["projects"][0]
        self.assertEqual(project["canonical_bullet_count"], 6)
        self.assertEqual(project["allocated_bullet_count"], 4)

    def test_prefer_available_repeat_runs_are_identical(self) -> None:
        kwargs = {
            "selected_pairs": [
                _pair(bullet_count=4, project_id="a"),
                _pair(bullet_count=3, project_id="b"),
            ],
            "max_bullets_per_project": 4,
            "allocation_mode": BULLET_ALLOCATION_MODE_PREFER_AVAILABLE,
        }
        first = build_deterministic_bullet_allocation(**kwargs)
        second = build_deterministic_bullet_allocation(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first["total_allocated_bullets"], 7)

    def test_mode_normalisation_fails_safe_to_adaptive(self) -> None:
        self.assertEqual(
            normalise_bullet_allocation_mode("fill then trim"),
            BULLET_ALLOCATION_MODE_PREFER_AVAILABLE,
        )
        self.assertEqual(
            normalise_bullet_allocation_mode("unknown"),
            BULLET_ALLOCATION_MODE_ADAPTIVE,
        )

    def test_app_wires_mode_into_generation_identity(self) -> None:
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"Bullet allocation"', app)
        self.assertIn('"Adaptive"', app)
        self.assertIn('"Prefer available evidence"', app)
        self.assertRegex(
            app,
            r'generation_control_defaults\.get\(\s*'
            r'"bullet_allocation_mode",\s*'
            r'"all_canonical_before_fitting",\s*'
            r'\)',
        )
        self.assertGreaterEqual(
            app.count("bullet_allocation_mode=bullet_allocation_mode"),
            2,
        )
        self.assertGreaterEqual(
            app.count('"bullet_allocation_mode": bullet_allocation_mode'),
            2,
        )

    def test_project_tailor_passes_mode_to_allocator(self) -> None:
        source = (ROOT / "tailoring" / "project_section_tailor.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('bullet_allocation_mode: str = "adaptive"', source)
        self.assertIn("allocation_mode=bullet_allocation_mode", source)


if __name__ == "__main__":
    unittest.main()

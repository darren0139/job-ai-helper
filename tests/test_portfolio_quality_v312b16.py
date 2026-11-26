"""B1.6 exact candidate-content, ranking, provenance and fallback parity."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import ast
import unittest

from resume_builder.evidence_aware_fitting import build_evidence_aware_project_reductions
from resume_builder.fitting_lazy_candidate_path_v312b16 import (
    VERSION, MARKER, lazy_project_reductions, materialize_selected,
)
from tailoring.portfolio_quality_v312b13 import (
    B1_PROVENANCE, prioritize_portfolio_reductions,
)

ROOT = Path(__file__).resolve().parents[1]
FITTER = ROOT / "resume_builder/docx_projects_skills_replacer.py"
MANAGER = ROOT / "database/phase9f_tailoring_execution_manager.py"


def fixture(counts=(29, 4, 6, 5), protected=True):
    projects = []
    for i, n in enumerate(counts):
        bullets = [f"Project {i} accomplished distinct feature {j} in Python." for j in range(n)]
        rows = [
            {
                "bullet_index": j, "bullet_text": b,
                "supported_requirement_ids": [f"common_{j % 3}", f"unique_{i}_{j}"],
                "protected_requirement_ids": [f"req_{i}_{j}"] if protected and j == 0 else [],
                "unique_required_core_count": 1 if protected and j == 0 else 0,
                "evidence_value": float(2 * n - j),
                "evidence_priority": j + 1,
                "metadata_extra": {"nested": list(range(24))},
            } for j, b in enumerate(bullets)
        ]
        projects.append({
            "project_id": f"p{i}", "display_title": f"Project {i}",
            "title": f"Project {i}", "draft_bullets": bullets,
            "bullet_evidence_priorities": rows, "space_action": "keep_full",
            "requirement_matches": [
                {"requirement_id": f"unique_{i}_0", "importance": "core", "match_label": "direct"}
            ],
            "extra_fields": {"a": [list(range(50)) for _ in range(3)]},
        })
    return {"recommended_projects": projects, "notes_for_user": ["baseline"],
            "portfolio_quality_b1_active": B1_PROVENANCE,
            "other_metadata": {"nested": [["x"] * 40]}}


def assert_parity(testcase, payload, balanced=False):
    old = build_evidence_aware_project_reductions(
        payload, prefer_balanced_bullets=balanced)
    new = lazy_project_reductions(payload, prefer_balanced_bullets=balanced)
    testcase.assertEqual(len(old), len(new))
    testcase.assertEqual([c for _, c in old], [c for _, c in new])
    for index in sorted(set((0, len(new)//2, len(new)-1))):
        projects, change = new[index]
        as_candidate = {"projects": projects, "change": change, "skills": {"skill_lines": ["Python"]}}
        full = materialize_selected(payload, as_candidate)
        testcase.assertEqual(full["projects"], old[index][0])
        testcase.assertEqual(full["change"], old[index][1])
        testcase.assertNotIn(MARKER, full["projects"])
    return old, new


class B16LazyMaterialization(unittest.TestCase):
    def test_exact_metadata_and_project_state(self):
        payload = fixture()
        original = deepcopy(payload)
        assert_parity(self, payload)
        self.assertEqual(original, payload)

    def test_balanced_order_parity(self):
        assert_parity(self, fixture((8, 5, 4)), balanced=True)

    def test_dynamic_unique_core_unchanged(self):
        old, new = assert_parity(self, fixture((4, 3), protected=False))
        self.assertTrue(any(x[1]["protection_tier"] > 0 for x in new))
        self.assertEqual([x[1]["unique_required_core_count"] for x in old],
                         [x[1]["unique_required_core_count"] for x in new])

    def test_b13_actual_ranking_identity(self):
        source = fixture((15, 3, 5, 4))
        old, new = assert_parity(self, source)
        def ranked(rows):
            enriched = [
                {"projects": p, "skills": {"skill_lines": ["Python"]},
                 "change": {**deepcopy(c), "section": "projects"},
                 "quality_loss": int(c["evidence_loss_score"]),
                 "candidate_order": i + 2}
                for i, (p, c) in enumerate(rows)
            ]
            return prioritize_portfolio_reductions(source, enriched)
        old_ranked, new_ranked = ranked(old), ranked(new)
        self.assertEqual(
            [(c["candidate_order"], c["quality_loss"], c["change"]) for c in old_ranked],
            [(c["candidate_order"], c["quality_loss"], c["change"]) for c in new_ranked],
        )
        for i in (0, len(new_ranked)//2, len(new_ranked)-1):
            actual = materialize_selected(source, new_ranked[i])
            self.assertEqual(actual["projects"], old_ranked[i]["projects"])

    def test_mixed_skill_fusion_and_compaction_sort_parity(self):
        source = fixture((9, 4, 3, 3))
        old, new = assert_parity(self, source)
        skill = {"projects": deepcopy(source), "skills": {"skill_lines": ["Python"]},
                 "change": {"section": "skills", "change_type": "remove_skill",
                            "protection_tier": 0, "category": "Languages"},
                 "quality_loss": 100, "candidate_order": 0}
        compact = {"projects": deepcopy(source), "skills": {"skill_lines": ["Python"]},
                   "change": {"section": "projects", "change_type": "compact_rewrite",
                              "protection_tier": 0},
                   "quality_loss": 40, "candidate_order": 1}
        def mix(rows):
            converted = [{"projects": p, "skills": None,
                          "change": {**deepcopy(c), "section": "projects"},
                          "quality_loss": int(c["evidence_loss_score"]),
                          "candidate_order": i + 2}
                         for i, (p, c) in enumerate(rows)]
            return prioritize_portfolio_reductions(source, [deepcopy(skill), deepcopy(compact), *converted])
        a, b = mix(old), mix(new)
        self.assertEqual([(c["change"], c["candidate_order"], c["quality_loss"]) for c in a],
                         [(c["change"], c["candidate_order"], c["quality_loss"]) for c in b])

    def test_one_bullet_and_invalid_geometry_fallback(self):
        for source in (fixture((1, 1, 1)), fixture((3, 2))):
            source = deepcopy(source)
            if len(source["recommended_projects"]) == 2:
                source["recommended_projects"][0]["bullet_evidence_priorities"].append("unexpected row")
            old = build_evidence_aware_project_reductions(source)
            new = lazy_project_reductions(source)
            self.assertEqual(new, old)
            self.assertFalse(any(MARKER in p for p, _ in new))

    def test_readonly_candidate_source_and_isolated_selected(self):
        payload = fixture((8, 4, 4))
        before = deepcopy(payload)
        new = lazy_project_reductions(payload)
        first = materialize_selected(payload, {"projects": new[0][0], "change": new[0][1]})
        first["projects"]["recommended_projects"][0]["draft_bullets"][0] = "mutated only this output"
        self.assertEqual(before, payload)
        self.assertNotIn("mutated only this output", str(new[-1]))

    def test_exact_callsite_and_policy(self):
        source = FITTER.read_text(encoding="utf-8-sig")
        manager = MANAGER.read_text(encoding="utf-8-sig")
        ast.parse(source)
        ast.parse(manager)
        self.assertEqual(source.count("v312b16_lazy_path: bool = False"), 1)
        self.assertEqual(source.count("materialize_selected(current_projects, next_candidate)"), 1)
        self.assertEqual(source.count("lazy_project_reductions("), 1)
        self.assertIn("+v312b16-lazy-path", manager)
        self.assertIn("+v312b15-candidate-cow", manager)
        self.assertIn("v312b141_incumbent_fit_elapsed", manager)


if __name__ == "__main__":
    unittest.main()

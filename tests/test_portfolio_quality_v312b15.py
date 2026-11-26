"""B1.5: actual Portfolio candidate ranking parity and ownership checks."""
from __future__ import annotations

from copy import deepcopy
import ast
from pathlib import Path
import unittest

from tailoring import portfolio_quality_v312b13 as mod

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tailoring" / "portfolio_quality_v312b13.py"
MANAGER = ROOT / "database" / "phase9f_tailoring_execution_manager.py"
OLD_COPY = "        updated=deepcopy(row)\n"
NEW_COPY = "        updated=row.copy()\n"


def fixture():
    base = {"portfolio_quality_b1_active": mod.B1_PROVENANCE,
        "recommended_projects": [
            {"project_id": "A", "draft_bullets": ["a", "b", "c", "d", "e"],
             "other": {"nested": [1, 2, 3]}},
            {"project_id": "B", "draft_bullets": ["x", "y"],
             "other": {"nested": [4, 5, 6]}},
        ]}
    candidates=[]
    for i in range(12):
        projects=deepcopy(base)
        projects["recommended_projects"][i % 2]["draft_bullets"].pop()
        candidates.append({"projects": projects,
            "skills": {"skill_lines": ["Python", "C++"]},
            "change": {"section": "projects", "change_type": "remove_bullet",
                       "protection_tier": i % 3, "removed_bullet_index": i,
                       "evidence_loss_score": i + 20},
            "quality_loss": i + 100,
            "candidate_order": i + 1})
    return base,candidates


def legacy_function():
    source=HELPER.read_text(encoding="utf-8")
    if source.count(NEW_COPY)!=1 or OLD_COPY in source:
        raise AssertionError("Unexpected B1.5 copy seam")
    old_source=source.replace(NEW_COPY,
        "        updated=deepcopy(row)\n",1)
    # remove isolated-change copy so the reconstructed old path is exact.
    old_source=old_source.replace('        updated["change"]=deepcopy(row["change"])\n','',1)
    namespace={}
    exec(compile(old_source,str(HELPER)+":legacy", "exec"),namespace)
    return namespace["prioritize_portfolio_reductions"]


class B15CandidateCow(unittest.TestCase):
    def test_exact_helper_seam(self):
        source=HELPER.read_text(encoding="utf-8")
        self.assertEqual(source.count(NEW_COPY),1)
        self.assertNotIn(OLD_COPY,source)
        self.assertEqual(source.count('updated["change"]=deepcopy(row["change"])'),1)
        ast.parse(source)

    def test_legacy_and_optimized_ranking_are_equal(self):
        base,candidates=fixture()
        before=deepcopy((base,candidates))
        old=legacy_function()(base,candidates)
        new=mod.prioritize_portfolio_reductions(base,candidates)
        self.assertEqual(new,old)
        self.assertEqual((base,candidates),before)
        self.assertEqual([c["candidate_order"] for c in new],list(range(1,len(new)+1)))
        self.assertEqual([c["change"]["v312b13_depth_order"] for c in new],
                         [c["change"]["v312b13_depth_order"] for c in old])

    def test_output_receipts_are_independent_of_source(self):
        base,candidates=fixture()
        new=mod.prioritize_portfolio_reductions(base,candidates)
        self.assertTrue(new)
        new[0]["change"]["v312b13_depth_order"]["depth_penalty"] = -99
        self.assertNotIn("v312b13_depth_order",candidates[0]["change"])
        self.assertFalse(any("v312b13_depth_order" in row["change"] for row in candidates))

    def test_balanced_and_invalid_candidates_unchanged(self):
        base,candidates=fixture()
        original=deepcopy(candidates)
        self.assertIs(mod.prioritize_portfolio_reductions({},candidates),candidates)
        invalid=deepcopy(candidates)
        invalid[0]["quality_loss"]=-1
        self.assertIs(mod.prioritize_portfolio_reductions(base,invalid),invalid)
        self.assertEqual(candidates,original)

    def test_policy_retains_b142_regression_pin(self):
        manager=MANAGER.read_text(encoding="utf-8-sig")
        self.assertEqual(manager.count("+v312b142-timing-order-fixed"),1)
        self.assertIn("+v312b142-timing-order-fixed+v312b15-candidate-cow",manager)
        self.assertIn("portfolio_quality_b141_final_audit",manager)
        self.assertIn("v312b141_incumbent_fit_elapsed",manager)
        ast.parse(manager)

if __name__ == "__main__":
    unittest.main()

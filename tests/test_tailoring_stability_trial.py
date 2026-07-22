from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_tailoring_stability_trial.py"
SPEC = importlib.util.spec_from_file_location("run_tailoring_stability_trial", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _run(index: int, *, selected=None, skills=None, score=40, label="direct"):
    selected = selected or ["project_a", "project_b", "project_c"]
    skills = skills or [{"category": "Programming", "items": ["Python"]}]
    return {
        "run": index,
        "selected_project_ids": selected,
        "selected_project_titles": selected,
        "selected_project_set": sorted(selected),
        "project_scores": {project_id: score for project_id in selected},
        "requirement_labels": {
            project_id: {"req_1": label} for project_id in selected
        },
        "candidate_profile_fingerprint": "same",
        "ranking_version": "phase6b1-project-ranking-v2",
        "evidence_mapping_version": "phase6b1-deterministic-evidence-mapping-v1",
        "skill_ranking_version": "phase6b1-skill-ranking-v2",
        "skill_selection_owner": "python_canonical_supported_evidence_pool",
        "skill_lines": skills,
        "bullet_text_by_project": {"A": ["One"]},
        "selected_project_rows": {},
    }


class TailoringTrialComparisonTests(unittest.TestCase):
    def test_identical_runs_pass(self):
        result = MODULE._compare([_run(1), _run(2), _run(3)], 5)
        self.assertTrue(result["passed"])

    def test_project_selection_change_fails(self):
        result = MODULE._compare(
            [_run(1), _run(2, selected=["project_a", "project_b", "project_d"])],
            5,
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["selected_project_set_stable"])

    def test_bullet_wording_change_does_not_fail(self):
        first = _run(1)
        second = _run(2)
        second["bullet_text_by_project"] = {"A": ["Different wording"]}
        result = MODULE._compare([first, second], 5)
        self.assertTrue(result["passed"])
        self.assertFalse(result["bullet_wording_stable"])


if __name__ == "__main__":
    unittest.main()

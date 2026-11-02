"""Adaptive Skills V2: no paid calls, exact saved candidate pool and no mutations."""
import unittest
from copy import deepcopy
from tailoring.adaptive_skill_selection_v2 import (
    apply_adaptive_skill_selection, supported_skill_options,
    normalise_adaptive_fit_settings,
)

def _fixture():
    ranked=[]
    for i in range(45):
        ranked.append({"skill":f"Skill {i:02}","skill_key":f"skill{i:02}","category":"Tools",
            "deterministic_priority_score":100-i,"required_match":i<3,
            "preferred_match":3<=i<6,"selected_project_support":i<8,
            "resume_support":True,"evidence_titles":["Verified project"]})
    return {"skill_lines":[{"category":"Tools","items":[r["skill"] for r in ranked[:20]]}],
        "skill_priorities":deepcopy(ranked[:20]),"deterministic_skill_ranking":deepcopy(ranked)}

class AdaptiveSkillsV2Tests(unittest.TestCase):
    def test_balanced_expands_existing_twenty_to_thirty(self):
        old=_fixture(); copy=deepcopy(old)
        got=apply_adaptive_skill_selection(old,mode="balanced")
        self.assertEqual(len(got["skill_priorities"]),30)
        self.assertEqual(old,copy)
        self.assertEqual(len(got["deterministic_skill_ranking"]),45)
    def test_preserve_supported_includes_every_ranked_evidence_skill(self):
        got=apply_adaptive_skill_selection(_fixture(),mode="preserve_supported")
        self.assertEqual(len(got["skill_priorities"]),45)
        self.assertEqual(got["adaptive_fit_selection"]["source"],"saved_deterministic_skill_ranking")
    def test_jd_focused_only_matching_capabilities(self):
        got=apply_adaptive_skill_selection(_fixture(),mode="jd_focused")
        self.assertEqual(len(got["skill_priorities"]),6)
        self.assertTrue(all(r["required_match"] or r["preferred_match"] for r in got["skill_priorities"]))
    def test_manual_cannot_create_unsupported_skill(self):
        got=apply_adaptive_skill_selection(_fixture(),mode="manual",selected_keys=["skill12","skill02"])
        self.assertEqual([r["skill_key"] for r in got["skill_priorities"]],["skill02","skill12"])
        for keys in (["unknown"],[],["skill02","Skill-02"]):
            with self.assertRaises(ValueError):
                apply_adaptive_skill_selection(_fixture(),mode="manual",selected_keys=keys)
    def test_legacy_is_unchanged_copy_and_fails_without_rank(self):
        saved={"skill_lines":[{"category":"Tools","items":["Python"]}]}
        self.assertEqual(apply_adaptive_skill_selection(saved,mode="legacy"),saved)
        with self.assertRaises(ValueError):apply_adaptive_skill_selection(saved,mode="balanced")
    def test_invalid_controls_rejected(self):
        for mode in ("", "all", "manual_typo"):
            with self.assertRaises(ValueError):normalise_adaptive_fit_settings(mode)
        with self.assertRaises(ValueError):normalise_adaptive_fit_settings("balanced",["skill02"])
    def test_options_only_from_saved_ranking(self):
        self.assertEqual(len(supported_skill_options(_fixture())),45)
        self.assertEqual(supported_skill_options({"skill_lines":[]}),[])
    def test_no_ranking_mutation_when_reading(self):
        original=_fixture(); before=deepcopy(original)
        for mode in ("balanced","preserve_supported","jd_focused"):
            apply_adaptive_skill_selection(original,mode=mode)
        self.assertEqual(original,before)

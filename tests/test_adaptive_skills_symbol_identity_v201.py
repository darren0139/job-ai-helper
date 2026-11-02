"""Regression pins for Adaptive Skills V2.0.1: preserve language identities."""
import unittest
from copy import deepcopy
from tailoring.adaptive_skill_selection_v2 import (
    _key, supported_skill_options, apply_adaptive_skill_selection,
    normalise_adaptive_fit_settings,
)


def _row(skill, key=None, *, required=False, preferred=False):
    return {
        "skill": skill,
        "skill_key": key or skill,
        "category": "Programming",
        "required_match": required,
        "preferred_match": preferred,
        "selected_project_support": False,
        "resume_support": True,
        "evidence_titles": ["Saved evidence"],
        "deterministic_priority_score": 70 if required else 50 if preferred else 30,
    }


def _skills():
    rows = [
        _row("C++", "c++", required=True),
        _row("C#", "c#"),
        _row("C", "c"),
        _row("F#", "f#"),
        _row("NVIDIA cuDF", "nvidia cudf", preferred=True),
    ]
    return {
        "skill_lines": [{"category": "Programming", "items": ["C++", "C#"]}],
        "skill_priorities": deepcopy(rows[:2]),
        "deterministic_skill_ranking": deepcopy(rows),
    }


class AdaptiveSkillsSymbolIdentityV201Tests(unittest.TestCase):
    def test_distinct_programming_languages_keep_distinct_keys(self):
        self.assertEqual([_key(s) for s in ("C", "C++", "C#", "F#")],
                         ["c", "c++", "c#", "f#"])
        self.assertEqual(_key(" C ++ "), "c++")
        self.assertEqual(_key(" c # "), "c#")

    def test_existing_punctuation_normalization_preserved(self):
        self.assertEqual(_key("NVIDIA cuDF"), "nvidiacudf")
        self.assertEqual(_key("GitHub Actions (CI)"), "githubactionsci")
        self.assertEqual(_key("GitHub Actions CI"), "githubactionsci")

    def test_saved_ranking_with_cplusplus_csharp_now_accepted(self):
        options = supported_skill_options(_skills())
        self.assertEqual(len(options), 5)
        self.assertEqual([o["key"] for o in options[:4]],
                         ["c++", "c#", "c", "f#"])

    def test_all_modes_and_original_ranking_nonmutation(self):
        saved = _skills()
        before = deepcopy(saved)
        for mode in ("balanced", "preserve_supported", "jd_focused"):
            selected = apply_adaptive_skill_selection(saved, mode=mode)
            self.assertTrue(selected["skill_lines"])
            self.assertEqual(selected["deterministic_skill_ranking"], before["deterministic_skill_ranking"])
        self.assertEqual(len(apply_adaptive_skill_selection(saved, mode="preserve_supported")["skill_priorities"]), 5)
        self.assertEqual(saved, before)

    def test_manual_distinguishes_cplusplus_and_csharp(self):
        selected = apply_adaptive_skill_selection(_skills(), mode="manual",
                                                  selected_keys=["c#", "c++"])
        self.assertEqual([r["skill"] for r in selected["skill_priorities"]], ["C++", "C#"])
        self.assertEqual(set(selected["adaptive_fit_selection"]["selected_skill_keys"]), {"c++", "c#"})
        self.assertEqual(normalise_adaptive_fit_settings("manual", ["C++", "C#"]),
                         ("manual", ["c++", "c#"]))

    def test_real_duplicates_still_fail_closed(self):
        saved = _skills()
        saved["deterministic_skill_ranking"].append(_row("c ++", "c ++"))
        with self.assertRaisesRegex(ValueError, "Duplicate skill identity"):
            supported_skill_options(saved)
        saved = _skills()
        saved["deterministic_skill_ranking"].append(_row("C#", "C#"))
        with self.assertRaisesRegex(ValueError, "Duplicate skill identity"):
            supported_skill_options(saved)
        with self.assertRaises(ValueError):
            normalise_adaptive_fit_settings("manual", ["C++", "C ++"])

    def test_manual_unknown_skill_still_rejected(self):
        with self.assertRaisesRegex(ValueError, "not in the saved supported pool"):
            apply_adaptive_skill_selection(_skills(), mode="manual", selected_keys=["cuda"])
        self.assertEqual(apply_adaptive_skill_selection(_skills(), mode="legacy"), _skills())

    def test_realistic_72_candidate_pool(self):
        saved = _skills()
        ranked = saved["deterministic_skill_ranking"]
        for i in range(67):
            ranked.append(_row(f"Recorded Tool {i:02}", f"recorded tool {i:02}"))
        self.assertEqual(len(supported_skill_options(saved)), 72)
        balanced = apply_adaptive_skill_selection(saved, mode="balanced")
        self.assertEqual(len(balanced["skill_priorities"]), 30)
        complete = apply_adaptive_skill_selection(saved, mode="preserve_supported")
        self.assertEqual(len(complete["skill_priorities"]), 72)
        self.assertIn("c++", complete["adaptive_fit_selection"]["selected_skill_keys"])
        self.assertIn("c#", complete["adaptive_fit_selection"]["selected_skill_keys"])


if __name__ == "__main__":
    unittest.main()

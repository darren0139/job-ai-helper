from __future__ import annotations

import unittest
from pathlib import Path


class ApplicationSessionOptimizerUIGeneralizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("app.py").read_text(encoding="utf-8")

    def test_optimizer_controls_are_available_for_ready_application_sessions(self):
        marker = (
            "score_optimizer_controls_available = bool(\n"
            "                phase9e_ready\n"
            "                and not workspace_edit_required\n"
            "                and not phase9f_f_blocked\n"
            "            )"
        )
        self.assertIn(marker, self.source)
        self.assertIn("if score_optimizer_controls_available:", self.source)

    def test_optimizer_controls_are_not_phase9f_f_only(self):
        old_gate = (
            "phase9f_f_paid_acknowledgement = False\n"
            "            if phase9f_f_active and not phase9f_f_blocked:\n"
            "                score_optimizer_enabled_key"
        )
        self.assertNotIn(old_gate, self.source)

    def test_phase9f_paid_acknowledgement_remains_phase9f_only(self):
        optimizer = self.source.index(
            "Optional: Optimize generated project bullets for JD score"
        )
        paid_guard = self.source.index(
            "if phase9f_f_active:",
            optimizer,
        )
        paid_warning = self.source.index(
            "Projects & Skills may make paid model calls only for the ",
            optimizer,
        )
        generate_button = self.source.index(
            'key=f"generate_projects_skills_{current_application_id}"',
            optimizer,
        )
        self.assertLess(paid_guard, paid_warning)
        self.assertLess(paid_warning, generate_button)

    def test_ordinary_application_generation_still_arms_one_shot_optimizer(self):
        ordinary_success = self.source.index(
            "Created a new Draft for the unlocked generated "
        )
        arm_call = self.source.index(
            "_arm_jd_score_optimizer_for_generation(",
            ordinary_success,
        )
        advanced_sections = self.source.index(
            "Advanced: Generate sections separately",
            ordinary_success,
        )
        self.assertLess(arm_call, advanced_sections)

    def test_exact_generation_cache_hit_arms_one_shot_optimizer(self):
        cache_hit = self.source.index(
            "Reused an exact persistent generation cache hit; "
        )
        arm_call = self.source.index(
            "_arm_jd_score_optimizer_for_generation(",
            cache_hit,
        )
        rerun = self.source.index(
            "st.rerun()",
            cache_hit,
        )
        self.assertLess(
            arm_call,
            rerun,
            (
                "An explicit Generate Projects + Skills action that restores "
                "an exact cached Draft must arm the optimizer before rerun."
            ),
        )

    def test_checkbox_still_does_not_trigger_optimizer_by_itself(self):
        self.assertIn(
            "score_optimizer_generation_triggered = bool(",
            self.source,
        )
        self.assertIn(
            "score_optimizer_enabled = (\n"
            "                                    score_optimizer_generation_triggered\n"
            "                                )",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()

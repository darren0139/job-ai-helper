from __future__ import annotations

import unittest

from scripts.apply_phase6c_patch import (
    build_patched_app_text,
    build_patched_text,
)


class Phase6CPatchTests(unittest.TestCase):
    def test_marker_patch_adds_phase6c_integration(self):
        source = """
from resume_builder.skills_section_compactor import (
    compact_skills_one_step,
    count_skill_items,
    count_skill_reduction_candidates,
    restore_skill_change,
    skill_restoration_quality_gain,
)

def apply_compact_bullets_once():
    target_project[
        "space_action"
    ] = "compact_rewrite"

def compact_tailored_projects_one_step(
    tailored_projects,
):
    return tailored_projects, False, {}

def _project_change_title(project):
    return ""

def _restore_fitting_change():
        project[
            "draft_bullets"
        ] = bullets

def _restoration_quality_gain(change):
    return 0

def _restorable_change_indices(changes):
    return []

def _project_reduction_quality_loss(change):
    return 0

def _skill_reduction_quality_loss(change):
    return 0

_LAYOUT_EFFECT_THRESHOLD = 0.002

def _choose_layout_aware_reduction(candidates):
    return candidates[0]

def generate_tailored_resume_copy_fit_one_page():
            project["compact_bullets"] = (
                project.get("compact_bullets", []) or []
            )[:max_bullets_per_project]
        if working_projects:
            reduced_projects, changed, change = compact_tailored_projects_one_step(
                working_projects,
                prefer_balanced_bullets=prefer_balanced_bullets,
            )
            if changed:
                change = deepcopy(change)
                change["section"] = "projects"
                candidate_changes.append(
                    {
                        "projects": reduced_projects,
                        "skills": working_skills,
                        "change": change,
                        "quality_loss": _project_reduction_quality_loss(change),
                        "candidate_order": 2,
                    }
                )
                "removed_skill": candidate["change"].get("removed_skill"),
                "quality_loss": candidate["quality_loss"],
        return {
            "generation_id": generation_id,
            "fitting_objective": (
                "Minimise deterministic evidence loss per unit of actual rendered "
                "space saved; do not rerun analysis or project selection."
            ),
        }

# ---------------------------------------------------------------------------
# Preview helpers
"""

        patched = build_patched_text(source)

        self.assertIn("PHASE6C_FITTING_VERSION", patched)
        self.assertIn(
            "build_evidence_aware_project_reductions",
            patched,
        )
        self.assertIn(
            "restore_removed_bullet_metadata",
            patched,
        )
        self.assertIn(
            '"fitting_version": PHASE6C_FITTING_VERSION',
            patched,
        )
        self.assertNotIn(
            "reduced_projects, changed, change = "
            "compact_tailored_projects_one_step",
            patched,
        )

    def test_app_patch_enables_compact_before_delete_by_default(self):
        source = """
                    use_compact_before_delete = st.checkbox(
                        "Compact project wording before deleting content",
                        value=False,
                    )
"""
        patched = build_patched_app_text(source)
        self.assertIn("value=True", patched)
        self.assertNotIn("value=False", patched)

    def test_patch_refuses_second_application(self):
        with self.assertRaises(RuntimeError):
            build_patched_text(
                "PHASE6C_FITTING_VERSION already present"
            )


if __name__ == "__main__":
    unittest.main()

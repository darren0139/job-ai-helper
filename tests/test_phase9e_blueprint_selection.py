from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis_stability.stable_evidence_scoring import (
    build_deterministic_keyword_match,
    build_stable_analysis,
    canonicalise_requirements,
)
from database import db_manager, jd_library_manager, tailoring_version_manager
from database.jd_library_manager import get_exact_job_description_for_application
from rag.jd_identity import build_job_identity
from tailoring.phase9e_blueprint_selection import (
    PHASE9E_DECISION_POLICY_VERSION,
    PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION,
    PHASE9E_EXACT_SOURCE_REUSE_POLICY_VERSION,
    build_effective_tailoring_report,
    build_phase9e_decision,
    build_phase9e_keyword_match,
    decide_tailoring,
    generation_binding_identity,
    materialise_phase9e_starting_sections,
    recommend_active_blueprint,
    resolve_workflow_action,
    _apply_phase9e_preliminary_match_ceilings,
)
from tailoring.tailoring_generation_fingerprint import (
    build_tailoring_input_fingerprint,
    constrain_generation_control_to_phase9e,
    generation_matches_phase9e_binding,
)
from tests.phase9e_test_support import seed_phase9e_database


class Phase9EBlueprintSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_db = db_manager.DB_PATH
        self.old_jd = jd_library_manager.DB_PATH
        self.old_tailoring = tailoring_version_manager.DB_PATH
        self.database_path = Path(self.temporary.name) / "phase9e.sqlite"
        self.state = seed_phase9e_database(
            self.database_path,
            different_original=True,
        )
        self.blueprint = self.state["blueprint"]
        self.jd = get_exact_job_description_for_application(94)

    def tearDown(self) -> None:
        db_manager.DB_PATH = self.old_db
        jd_library_manager.DB_PATH = self.old_jd
        tailoring_version_manager.DB_PATH = self.old_tailoring
        self.temporary.cleanup()

    def build_blueprint_decision(self, **overrides):
        values = {
            "application_id": 94,
            "application_report": copy.deepcopy(
                self.state["application_report"]
            ),
            "exact_jd": copy.deepcopy(self.jd),
            "active_blueprints": [copy.deepcopy(self.blueprint)],
            "selected_source": "global_blueprint",
            "selected_blueprint_id": self.blueprint["blueprint_id"],
            "selection_mode": "recommended",
        }
        values.update(overrides)
        return build_phase9e_decision(**values)

    def score_capability_fixture(
        self,
        requirement_text: str,
        resume_profile: dict,
    ):
        raw_jd = f"Requirements:\n- {requirement_text}"
        jd_profile = {"required_skills": [requirement_text]}
        canonical = canonicalise_requirements(
            jd_profile=jd_profile,
            raw_jd_text=raw_jd,
        )
        resume_text = "\n".join(
            [
                *[
                    str(bullet)
                    for project in resume_profile.get("projects", [])
                    for bullet in project.get("bullets", [])
                ],
                *[
                    str(skill)
                    for values in resume_profile.get("skills", {}).values()
                    for skill in values
                ],
            ]
        )
        baseline = build_deterministic_keyword_match(
            requirements=canonical["requirements"],
            acronym_map=canonical["acronym_map"],
            resume_profile=copy.deepcopy(resume_profile),
            raw_resume_text=resume_text,
        )
        corrected = build_phase9e_keyword_match(
            requirements=canonical["requirements"],
            acronym_map=canonical["acronym_map"],
            resume_profile=copy.deepcopy(resume_profile),
            raw_resume_text=resume_text,
        )
        analysis = build_stable_analysis(
            jd_profile=jd_profile,
            keyword_match=copy.deepcopy(corrected),
            raw_jd_text=raw_jd,
            raw_resume_text=resume_text,
            resume_profile=copy.deepcopy(resume_profile),
            retrieval_mode_override="lexical",
        )

        def keyword_row(payload):
            return next(
                row
                for row in payload.get("present", [])
                if row.get("keyword") == requirement_text
            )

        result_row = next(
            row
            for row in analysis["canonical_requirements"]
            if row.get("text") == requirement_text
        )
        return keyword_row(baseline), keyword_row(corrected), result_row

    def test_exact_linked_jd_snapshot_never_mixes_latest_version(self):
        original = copy.deepcopy(self.jd)
        revised_text = original["raw_text"] + "\nAdditional revised requirement."
        revised_identity = build_job_identity(
            company=original["company"],
            title=original["title"],
            location=original["location"],
            raw_jd_text=revised_text,
        )
        connection = db_manager._connect()
        try:
            connection.execute(
                """
                INSERT INTO job_description_versions (
                    job_description_id, source_version_id, raw_text,
                    jd_profile_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    original["library_jd_id"],
                    revised_identity.source_version_id,
                    revised_text,
                    json.dumps(original["jd_profile"]),
                    "2026-08-05T00:00:00",
                ),
            )
            connection.execute(
                """
                UPDATE job_descriptions
                SET raw_text = ?, source_version_id = ?
                WHERE id = ?
                """,
                (
                    revised_text,
                    revised_identity.source_version_id,
                    original["library_jd_id"],
                ),
            )
            connection.commit()
        finally:
            connection.close()

        resolved = get_exact_job_description_for_application(94)
        self.assertEqual(resolved["source_version_id"], original["source_version_id"])
        self.assertEqual(resolved["raw_text"], original["raw_text"])
        self.assertEqual(
            resolved["canonical_requirement_fingerprint"],
            original["canonical_requirement_fingerprint"],
        )

    def test_same_family_blueprint_is_recommended_with_visible_provenance(self):
        recommendation = recommend_active_blueprint(
            self.jd, [self.blueprint]
        )
        self.assertEqual(
            recommendation["classification"]["role_family_id"],
            "ai_fullstack_software_engineering",
        )
        self.assertEqual(recommendation["recommendation_confidence"], "high")
        self.assertEqual(
            recommendation["recommended_blueprint"]["blueprint_id"],
            self.blueprint["blueprint_id"],
        )
        decision = self.build_blueprint_decision()
        self.assertEqual(
            decision["semantic_identity"]["decision"]["policy_version"],
            PHASE9E_DECISION_POLICY_VERSION,
        )
        self.assertEqual(
            decision["recommended_tailoring"], "reuse_approved_source"
        )
        self.assertEqual(
            decision["recommended_tailoring_label"],
            "Reuse approved blueprint",
        )
        self.assertTrue(decision["source_approval"]["matched"])
        self.assertEqual(
            decision["semantic_identity"]["source_approval"][
                "policy_version"
            ],
            PHASE9E_EXACT_SOURCE_REUSE_POLICY_VERSION,
        )
        self.assertNotIn("scoring", decision["semantic_identity"])
        self.assertEqual(
            decision["comparison"][
                "evidence_selection_policy_version"
            ],
            PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION,
        )
        self.assertTrue(
            decision["semantic_identity"]["selection"][
                "source_evaluation_provisional"
            ]
        )
        self.assertGreater(
            decision["comparison"]["deterministic_alignment_score"], 0
        )
        self.assertGreater(
            decision["comparison"]["required_core_requirement_count"], 0
        )

    def test_fullstack_integration_prefers_one_complete_queryai_bullet(self):
        requirement = (
            "Build frontend and full-stack application features using React "
            "and JavaScript or TypeScript"
        )
        integration = (
            "Built full-stack help-desk workflows using React and "
            "Supabase/PostgreSQL, including login and ticket editing."
        )
        profile = {
            "projects": [{"title": "QueryAI", "bullets": [integration]}],
            "skills": {
                "Web": ["React"],
                "Programming": ["JavaScript"],
                "Backend": ["Supabase"],
            },
        }
        baseline, corrected, result = self.score_capability_fixture(
            requirement,
            profile,
        )
        self.assertEqual(baseline["matched_resume_term"], "React")
        self.assertEqual(corrected["matched_resume_term"], integration)
        self.assertEqual(corrected["match_type"], baseline["match_type"])
        self.assertEqual(
            corrected["evidence_type"], baseline["evidence_type"]
        )
        self.assertFalse(
            corrected["phase9e_evidence_selection"][
                "combined_evidence_rows"
            ]
        )
        self.assertEqual(result["match_label"], baseline["match_type"])
        self.assertLessEqual(result["evidence_strength"], 3)

    def test_database_design_prefers_sqlite_implementation_bullet(self):
        requirement = "Experience with SQLite or PostgreSQL database design"
        implementation = (
            "Implemented SQLite sessions with reports and persistent history."
        )
        profile = {
            "projects": [
                {"title": "Job AI Helper", "bullets": [implementation]}
            ],
            "skills": {"Backend": ["PostgreSQL"]},
        }
        baseline, corrected, result = self.score_capability_fixture(
            requirement,
            profile,
        )
        self.assertEqual(baseline["matched_resume_term"], "PostgreSQL")
        self.assertEqual(corrected["matched_resume_term"], implementation)
        self.assertEqual(corrected["match_type"], baseline["match_type"])
        self.assertEqual(result["match_label"], baseline["match_type"])
        self.assertLessEqual(result["evidence_strength"], 3)

    def test_access_control_tokens_do_not_outrank_rls_postgrest_bullet(self):
        implementation = (
            "Implemented backend data access through PostgREST and applied "
            "Row-Level Security policies to secure database operations."
        )
        cases = (
            (
                "Implement authentication workflows, Row-Level Security "
                "policies, and secure database access",
                ["authentication workflows", "access control"],
                "authentication workflows",
            ),
            (
                "Experience implementing authentication workflows or "
                "database access control",
                ["access control", "authentication workflows"],
                "access control",
            ),
        )
        for requirement, skills, expected_token in cases:
            with self.subTest(requirement=requirement):
                profile = {
                    "projects": [
                        {"title": "QueryAI", "bullets": [implementation]}
                    ],
                    "skills": {"Backend": skills},
                }
                baseline, corrected, result = self.score_capability_fixture(
                    requirement,
                    profile,
                )
                self.assertEqual(
                    baseline["matched_resume_term"], expected_token
                )
                self.assertEqual(
                    corrected["matched_resume_term"], implementation
                )
                self.assertEqual(
                    corrected["match_type"], baseline["match_type"]
                )
                self.assertEqual(
                    result["match_label"], baseline["match_type"]
                )
                self.assertLessEqual(result["evidence_strength"], 3)

    def test_unrelated_rows_are_never_combined_to_prove_fullstack(self):
        requirement = (
            "Build frontend and full-stack application features using React "
            "and JavaScript or TypeScript"
        )
        profile = {
            "projects": [],
            "skills": {
                "Web": ["React"],
                "Backend": ["Supabase"],
            },
        }
        baseline, corrected, result = self.score_capability_fixture(
            requirement,
            profile,
        )
        self.assertEqual(baseline, corrected)
        self.assertNotIn("phase9e_evidence_selection", corrected)
        self.assertEqual(result["match_label"], "none")
        self.assertEqual(result["evidence_strength"], 0)

    def test_atomic_promotion_cannot_exceed_preliminary_ceiling(self):
        analysis = {
            "canonical_requirements": [
                {
                    "requirement_id": "req_atomic",
                    "text": "Atomic capability",
                    "importance": "required",
                    "atomic_group_id": "grp_atomic",
                    "match_label": "direct",
                    "match_value": 1.0,
                    "evidence_strength": 5,
                    "evidence": [{"text": "One sufficient visible row"}],
                }
            ],
            "validation_warnings": [],
        }
        keyword_match = {
            "evidence_selection_audit": [
                {
                    "requirement_id": "req_atomic",
                    "preliminary_match_ceiling": "transferable",
                }
            ]
        }
        result = _apply_phase9e_preliminary_match_ceilings(
            analysis,
            keyword_match,
        )
        row = result["canonical_requirements"][0]
        self.assertEqual(row["match_label"], "transferable")
        self.assertEqual(row["match_value"], 0.55)
        self.assertEqual(row["evidence_strength"], 3)
        self.assertTrue(
            any(
                warning.get("code")
                == "phase9e_preliminary_match_ceiling_applied"
                for warning in result["validation_warnings"]
            )
        )

    def test_no_same_family_does_not_select_unrelated_blueprint(self):
        unrelated = copy.deepcopy(self.blueprint)
        unrelated["role_family_id"] = "unrelated_family"
        unrelated["blueprint_snapshot"]["role_family_id"] = "unrelated_family"
        unrelated["blueprint_snapshot"]["semantic_identity"]["role_family"][
            "role_family_id"
        ] = "unrelated_family"
        from tailoring.phase9e_blueprint_selection import fingerprint_value

        unrelated["blueprint_fingerprint"] = fingerprint_value(
            unrelated["blueprint_snapshot"]["semantic_identity"]
        )
        unrelated["blueprint_id"] = unrelated["blueprint_fingerprint"][:32]
        unrelated["blueprint_snapshot"]["blueprint_fingerprint"] = unrelated[
            "blueprint_fingerprint"
        ]
        unrelated["blueprint_snapshot"]["blueprint_id"] = unrelated[
            "blueprint_id"
        ]
        recommendation = recommend_active_blueprint(self.jd, [unrelated])
        self.assertIsNone(recommendation["recommended_blueprint"])

    def test_original_profile_is_scored_and_labelled_as_workflow_source(self):
        decision = build_phase9e_decision(
            application_id=94,
            application_report=copy.deepcopy(self.state["application_report"]),
            exact_jd=copy.deepcopy(self.jd),
            active_blueprints=[copy.deepcopy(self.blueprint)],
            selected_source="original_resume",
            selection_mode="original_resume",
        )
        self.assertEqual(
            decision["starting_snapshot"]["source_fidelity"],
            "persisted_profile_only",
        )
        self.assertFalse(
            decision["starting_snapshot"][
                "resume_text_is_original_uploaded_text"
            ]
        )
        derived = decide_tailoring(
            decision["comparison"],
            role_family_mismatch=False,
            selected_source="original_resume",
            original_source_fidelity="persisted_profile_only",
        )
        self.assertEqual(
            decision["recommended_tailoring"], derived["decision"]
        )
        self.assertGreater(
            decision["comparison"]["deterministic_alignment_score"], 0
        )

    def test_thresholds_and_role_mismatch_are_deterministic(self):
        reuse = decide_tailoring(
            {
                "deterministic_alignment_score": 85,
                "required_core_coverage_score": 90,
                "preferred_coverage_score": 65,
                "evidence_strength_score": 80,
                "preferred_requirement_count": 1,
                "important_gap_count": 0,
                "deal_breaker_gap_count": 0,
            },
            role_family_mismatch=False,
        )
        self.assertEqual(reuse["decision"], "reuse_unchanged")
        optional = decide_tailoring(
            {
                "deterministic_alignment_score": 65,
                "required_core_coverage_score": 65,
                "preferred_coverage_score": 0,
                "evidence_strength_score": 60,
                "preferred_requirement_count": 0,
                "important_gap_count": 0,
                "deal_breaker_gap_count": 0,
            },
            role_family_mismatch=False,
        )
        self.assertEqual(optional["decision"], "optional_polish")
        targeted = decide_tailoring(
            {
                "deterministic_alignment_score": 65,
                "required_core_coverage_score": 65,
                "preferred_coverage_score": 0,
                "evidence_strength_score": 60,
                "preferred_requirement_count": 0,
                "important_gap_count": 2,
                "deal_breaker_gap_count": 0,
            },
            role_family_mismatch=False,
        )
        self.assertEqual(targeted["decision"], "targeted_retailor")
        mismatch = decide_tailoring(
            {
                "deterministic_alignment_score": 100,
                "required_core_coverage_score": 100,
                "preferred_coverage_score": 100,
                "evidence_strength_score": 100,
                "preferred_requirement_count": 1,
                "important_gap_count": 0,
                "deal_breaker_gap_count": 0,
            },
            role_family_mismatch=True,
        )
        self.assertEqual(mismatch["decision"], "full_regeneration")

    def test_application94_exact_source_reuses_approved_blueprint_locked(self):
        decision = self.build_blueprint_decision()
        self.assertEqual(
            decision["recommended_tailoring"], "reuse_approved_source"
        )
        self.assertLess(
            decision["comparison"]["deterministic_alignment_score"],
            85,
        )
        action = resolve_workflow_action(decision)
        self.assertTrue(action["can_generate"])
        self.assertEqual(action["workflow_action"], "use_blueprint_unchanged")
        self.assertTrue(action["section_lock_scope"]["projects_locked"])
        self.assertTrue(action["section_lock_scope"]["skills_locked"])

    def test_optional_polish_supports_unchanged_and_explicit_polish(self):
        decision = self.build_blueprint_decision()
        decision["recommended_tailoring"] = "optional_polish"
        decision["workflow_action_policy"] = {
            "policy_version": "phase9e-workflow-action-v1",
            "default_action": "use_blueprint_unchanged",
            "available_actions": [
                "use_blueprint_unchanged",
                "apply_optional_polish",
            ],
        }
        unchanged = resolve_workflow_action(decision)
        polish = resolve_workflow_action(
            decision,
            {"workflow_action": "apply_optional_polish"},
        )
        self.assertTrue(unchanged["section_lock_scope"]["projects_locked"])
        self.assertTrue(unchanged["section_lock_scope"]["skills_locked"])
        self.assertFalse(polish["section_lock_scope"]["projects_locked"])
        self.assertFalse(polish["section_lock_scope"]["skills_locked"])
        self.assertNotEqual(
            generation_binding_identity(decision, unchanged)[
                "workflow_action_fingerprint"
            ],
            generation_binding_identity(decision, polish)[
                "workflow_action_fingerprint"
            ],
        )
        unchanged_binding = generation_binding_identity(decision, unchanged)
        polish_binding = generation_binding_identity(decision, polish)
        self.assertFalse(
            generation_matches_phase9e_binding(
                {
                    "generation_settings": {
                        "phase9e_binding": unchanged_binding
                    }
                },
                polish_binding,
            )
        )

    def test_persisted_profile_only_is_never_auto_declared_superior(self):
        comparison = {
            "deterministic_alignment_score": 40,
            "required_core_coverage_score": 40,
            "preferred_coverage_score": 40,
            "evidence_strength_score": 40,
            "preferred_requirement_count": 1,
            "important_gap_count": 1,
            "deal_breaker_gap_count": 0,
        }
        original = {
            **comparison,
            "deterministic_alignment_score": 100,
            "required_core_coverage_score": 100,
            "evidence_strength_score": 100,
            "important_gap_count": 0,
        }
        outcome = decide_tailoring(
            comparison,
            role_family_mismatch=False,
            original_comparison=original,
            original_source_fidelity="persisted_profile_only",
        )
        self.assertEqual(outcome["decision"], "targeted_retailor")
        policy = outcome["original_resume_comparison"]
        self.assertFalse(policy["automatic_superiority_eligible"])
        self.assertFalse(policy["clearly_better"])
        self.assertIn("not original uploaded text", policy["manual_option_only_reason"])

    def test_diagnostic_changes_do_not_change_exact_source_identity(self):
        first = self.build_blueprint_decision()
        changed = copy.deepcopy(first["comparison"])
        changed["deterministic_alignment_score"] = 1
        changed["comparison_result_fingerprint"] = "diagnostic-policy-changed"
        changed["evidence_selection_policy_version"] = "diagnostic-v-next"
        with patch(
            "tailoring.phase9e_blueprint_selection.evaluate_starting_snapshot",
            return_value=changed,
        ):
            second = self.build_blueprint_decision()
        self.assertEqual(
            first["decision_fingerprint"], second["decision_fingerprint"]
        )
        self.assertNotEqual(
            first["diagnostic_visible_scoring"],
            second["diagnostic_visible_scoring"],
        )

    def test_effective_context_uses_blueprint_and_never_mutates_report(self):
        original_report = copy.deepcopy(self.state["application_report"])
        decision = self.build_blueprint_decision()
        effective = build_effective_tailoring_report(
            original_report, decision
        )
        blueprint_profile = self.blueprint["blueprint_snapshot"][
            "frozen_resume_snapshot"
        ]["resume_profile_snapshot"]
        self.assertEqual(
            effective["resume_profile"]["projects"],
            blueprint_profile["projects"],
        )
        self.assertEqual(
            effective["resume_profile"]["skills"],
            blueprint_profile["skills"],
        )
        self.assertNotEqual(
            effective["resume_profile"]["projects"],
            original_report["resume_profile"]["projects"],
        )
        self.assertEqual(original_report, self.state["application_report"])

        sections = materialise_phase9e_starting_sections(decision)
        self.assertEqual(
            [row["display_title"] for row in sections["projects"]["recommended_projects"]],
            [row["title"] for row in blueprint_profile["projects"]],
        )
        self.assertTrue(sections["skills"]["skill_lines"])

    def test_approved_generation_from_another_binding_is_ignored(self):
        decision = self.build_blueprint_decision()
        binding = generation_binding_identity(decision)
        incompatible = {
            "generation_id": "old-generation",
            "generation_settings": {
                "phase9e_binding": {
                    **binding,
                    "decision_fingerprint": "different-decision",
                }
            },
        }
        constrained = constrain_generation_control_to_phase9e(
            {
                "approved_generation_id": "old-generation",
                "approved_generation": incompatible,
                "lock_projects": True,
                "lock_skills": True,
            },
            binding,
        )
        self.assertIsNone(constrained["approved_generation"])
        self.assertFalse(constrained["lock_projects"])
        self.assertFalse(constrained["lock_skills"])

    def test_generation_fingerprint_isolates_original_and_blueprint_sources(self):
        blueprint_decision = self.build_blueprint_decision()
        original_decision = build_phase9e_decision(
            application_id=94,
            application_report=copy.deepcopy(self.state["application_report"]),
            exact_jd=copy.deepcopy(self.jd),
            active_blueprints=[copy.deepcopy(self.blueprint)],
            selected_source="original_resume",
            selection_mode="original_resume",
        )
        blueprint_report = build_effective_tailoring_report(
            self.state["application_report"], blueprint_decision
        )
        original_report = build_effective_tailoring_report(
            self.state["application_report"], original_decision
        )
        common = {
            "evidence_items": [],
            "generation_settings": {"max_projects": 3, "max_bullets": 3},
            "generation_kind": "projects_skills",
            "model_id": "test-model",
        }
        blueprint_fingerprint = build_tailoring_input_fingerprint(
            report=blueprint_report,
            phase9e_binding=generation_binding_identity(blueprint_decision),
            **common,
        )
        original_fingerprint = build_tailoring_input_fingerprint(
            report=original_report,
            phase9e_binding=generation_binding_identity(original_decision),
            **common,
        )
        self.assertNotEqual(blueprint_fingerprint, original_fingerprint)
        changed_binding = generation_binding_identity(blueprint_decision)
        changed_binding["decision_fingerprint"] = "different-binding"
        changed = build_tailoring_input_fingerprint(
            report=blueprint_report,
            phase9e_binding=changed_binding,
            **common,
        )
        self.assertNotEqual(blueprint_fingerprint, changed)
        repeated = build_tailoring_input_fingerprint(
            report=blueprint_report,
            phase9e_binding=generation_binding_identity(blueprint_decision),
            **common,
        )
        self.assertEqual(blueprint_fingerprint, repeated)

    def test_display_metadata_and_active_list_order_do_not_change_identity(self):
        first = self.build_blueprint_decision()
        edited = copy.deepcopy(self.blueprint)
        edited["display_name"] = "Edited display name"
        edited["notes"] = "Edited notes"
        second = self.build_blueprint_decision(active_blueprints=[edited])
        self.assertEqual(
            first["decision_fingerprint"], second["decision_fingerprint"]
        )


if __name__ == "__main__":
    unittest.main()

"""Zero-cost real Phase 9E smoke check using a temporary SQLite database."""

from __future__ import annotations

import tempfile
from pathlib import Path

from database import db_manager, jd_library_manager, tailoring_version_manager
from database.application_blueprint_manager import (
    evaluate_and_bind_application_blueprint,
    resolve_current_phase9e_generation_context,
    set_application_blueprint_workflow_action,
)
from database.application_resume_result_manager import (
    build_application_result_debug_bundle,
    create_or_reuse_current_application_result,
    list_application_resume_results,
)
from database.application_cover_letter_manager import (
    generate_or_reuse_application_cover_letter,
    list_application_cover_letters,
)
from database.tailoring_generation_control import list_tailoring_generations
from tailoring.phase9e_blueprint_selection import (
    PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION,
)
from tests.phase9e_test_support import seed_phase9e_database


def main() -> None:
    old_db = db_manager.DB_PATH
    old_jd = jd_library_manager.DB_PATH
    old_tailoring = tailoring_version_manager.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "phase9e-smoke.sqlite"
            state = seed_phase9e_database(
                database_path,
                different_original=True,
            )
            blueprint = state["blueprint"]
            first = evaluate_and_bind_application_blueprint(
                application_id=94,
                scope_replacement_confirmed=True,
                selected_source="global_blueprint",
                selected_blueprint_id=blueprint["blueprint_id"],
                selection_mode="recommended",
                actor_label="Phase 9E smoke",
            )
            second = evaluate_and_bind_application_blueprint(
                application_id=94,
                scope_replacement_confirmed=True,
                selected_source="global_blueprint",
                selected_blueprint_id=blueprint["blueprint_id"],
                selection_mode="recommended",
                actor_label="Phase 9E smoke",
            )
            decision = first["decision"]
            comparison = decision["comparison"]
            assert first["cache_status"] == "miss"
            assert second["cache_status"] == "hit_current"
            assert second["decision"]["decision_id"] == decision["decision_id"]
            assert (
                decision["role_family_classification"]["role_family_id"]
                == "ai_fullstack_software_engineering"
            )
            assert comparison["deterministic_alignment_score"] == 59
            assert comparison["required_core_coverage_score"] == 59
            assert comparison["preferred_coverage_score"] == 53
            assert comparison["evidence_strength_score"] == 64
            assert comparison["important_gap_count"] == 0
            assert comparison["deal_breaker_gap_count"] == 0
            assert comparison["required_core_requirement_count"] > 0
            assert comparison["stable_input_fingerprint"]
            assert (
                comparison["evidence_selection_policy_version"]
                == PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION
            )
            selection_audit = comparison["keyword_match_snapshot"][
                "evidence_selection_audit"
            ]
            assert selection_audit
            assert all(
                row["combined_evidence_rows"] is False
                for row in selection_audit
            )
            assert (
                decision["recommended_tailoring"]
                == "reuse_approved_source"
            )
            assert decision["source_approval"]["matched"] is True
            assert decision["mutation_policy"]["model_calls"] == 0
            assert decision["mutation_policy"]["embedding_calls"] == 0
            context = resolve_current_phase9e_generation_context(94)
            assert context["can_generate"] is True
            assert context["section_lock_scope"]["projects_locked"] is True
            assert context["section_lock_scope"]["skills_locked"] is True
            assert (
                context["effective_report"]["resume_profile"]["projects"]
                == blueprint["blueprint_snapshot"]["frozen_resume_snapshot"][
                    "resume_profile_snapshot"
                ]["projects"]
            )
            generation_count = len(list_tailoring_generations(94))
            set_application_blueprint_workflow_action(
                application_id=94,
                workflow_action="use_blueprint_unchanged",
                actor_label="Phase 9E smoke",
            )
            first_result = create_or_reuse_current_application_result(
                application_id=94,
                actor_label="Phase 9E smoke",
                artifact_root=Path(temporary) / "application-results",
            )
            second_result = create_or_reuse_current_application_result(
                application_id=94,
                actor_label="Phase 9E smoke",
                artifact_root=Path(temporary) / "application-results",
            )
            assert first_result["cache_status"] == "miss"
            assert second_result["cache_status"] == "hit"
            assert (
                first_result["application_result"]["application_result_id"]
                == second_result["application_result"]["application_result_id"]
            )
            assert len(list_application_resume_results(94)) == 1
            assert len(list_tailoring_generations(94)) == generation_count
            assert first_result["application_result"]["editable"] is False
            assert first_result["application_result"]["content_changed"] is False
            application_result_id = first_result["application_result"][
                "application_result_id"
            ]

            def zero_cost_cover_letter(system: str, user: str, model: str):
                assert system
                assert "QueryAI" in user
                return (
                    "Zero-cost Phase 9E smoke cover letter.",
                    {
                        "model_id": model,
                        "model_calls": 0,
                        "embedding_calls": 0,
                        "generator_mode": "zero_cost_smoke_fixture",
                    },
                )

            first_letter = generate_or_reuse_application_cover_letter(
                application_id=94,
                model_id="zero-cost-smoke-model",
                generator=zero_cost_cover_letter,
            )
            second_letter = generate_or_reuse_application_cover_letter(
                application_id=94,
                model_id="zero-cost-smoke-model",
                generator=zero_cost_cover_letter,
            )
            assert first_letter["cache_status"] == "miss"
            assert second_letter["cache_status"] == "hit"
            assert len(list_application_cover_letters(94)) == 1
            debug = build_application_result_debug_bundle(
                application_result_id
            )
            assert debug["application_result"]["complete_snapshot"]
            assert debug["phase9d_blueprint"]["complete_frozen_snapshot"]
            assert len(debug["application_result_cover_letters"]) == 1
            assert debug["call_totals"]["model_calls"] == 0
            assert debug["call_totals"]["embedding_calls"] == 0
            print(
                "Phase 9E smoke passed: "
                f"score={comparison['deterministic_alignment_score']} "
                f"required_core={comparison['required_core_coverage_score']} "
                f"preferred={comparison['preferred_coverage_score']} "
                f"evidence={comparison['evidence_strength_score']} "
                f"decision={decision['recommended_tailoring']} "
                "exact_source=true all_sections_locked=true "
                "decision_cache=miss->hit_current "
                "application_result=miss->hit immutable=true drafts_created=0 "
                "debug_bundle=complete cover_letter=miss->hit "
                "model_calls=0 embedding_calls=0"
            )
    finally:
        db_manager.DB_PATH = old_db
        jd_library_manager.DB_PATH = old_jd
        tailoring_version_manager.DB_PATH = old_tailoring


if __name__ == "__main__":
    main()

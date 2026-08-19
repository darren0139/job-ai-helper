"""Pure Phase 9F-D confirmation, baseline, and exact-binding contracts.

This module deliberately imports no persistence, model, embedding, Chroma,
generation, fitting, or rendering APIs. Persistence is handled by the manager
only after the user explicitly confirms creation of an Application Session.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from tailoring.phase9e_blueprint_selection import (
    PHASE9E_BINDING_EVENT_VERSION,
    PHASE9E_WORKFLOW_ACTION_POLICY_VERSION,
    fingerprint_value,
)
from tailoring.phase9f_starting_source_ranking import (
    PHASE9F_B_VERSION,
    Phase9FBRankingError,
    validate_exact_jd_snapshot,
    validate_ranked_candidate_analysis_snapshot,
    validate_ranked_result_contract,
)
from tailoring.phase9f_tailoring_intensity import (
    PHASE9F_C_VERSION,
    recommend_tailoring_intensity,
)


PHASE9F_D_VERSION = "phase9f-application-session-confirmation-v1"
PHASE9F_D_IDENTITY_POLICY_VERSION = (
    "phase9f-application-session-confirmation-identity-v1"
)
PHASE9F_D_IDEMPOTENCY_POLICY_VERSION = (
    "phase9f-application-intent-idempotency-v1"
)
PHASE9F_D_EVENT_VERSION = "phase9f-application-confirmation-event-v1"
PHASE9F_D_BASELINE_ADAPTER_VERSION = (
    "phase9f-b-to-application-baseline-v1"
)
PHASE9E_PHASE9F_D_EXACT_BINDING_VERSION = (
    "phase9e-phase9f-d-exact-tailoring-base-v1"
)
PHASE9E_PHASE9F_D_EXACT_BINDING_POLICY_VERSION = (
    "phase9e-phase9f-d-exact-tailoring-base-binding-v1"
)
PHASE9F_D_EXECUTION_NOT_STARTED_STATUS = (
    "phase9f_d_execution_not_started"
)

VALID_INTENSITIES = {"reuse", "minor", "full"}
INTENSITY_TO_PHASE9E_DECISION = {
    "reuse": "reuse_unchanged",
    "minor": "targeted_retailor",
    "full": "full_regeneration",
}
INTENSITY_LABELS = {
    "reuse": "Reuse",
    "minor": "Minor",
    "full": "Full",
}


class Phase9FDConfirmationError(ValueError):
    """A fail-closed Phase 9F-D contract or staleness error."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = str(code)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def zero_cost_diagnostics() -> dict[str, int]:
    return {
        "model_call_count": 0,
        "embedding_call_count": 0,
        "chroma_read_count": 0,
        "chroma_write_count": 0,
        "generation_call_count": 0,
        "fitting_call_count": 0,
    }


def phase9f_d_execution_state(
    decision: dict[str, Any] | None,
) -> dict[str, str] | None:
    """Return the exact D-origin routing state without changing identity."""
    if not isinstance(decision, dict) or decision.get("phase9e_version") != (
        PHASE9E_PHASE9F_D_EXACT_BINDING_VERSION
    ):
        return None
    semantic_confirmation = (
        (decision.get("semantic_identity") or {}).get(
            "phase9f_d_confirmation"
        )
        or {}
    )
    execution = decision.get("phase9f_d_execution") or {}
    semantic_intensity = _clean(
        semantic_confirmation.get("confirmed_intensity")
    ).lower()
    execution_intensity = _clean(
        execution.get("confirmed_intensity")
    ).lower()
    execution_status = _clean(execution.get("status")).lower()
    if (
        semantic_intensity not in VALID_INTENSITIES
        or execution_intensity != semantic_intensity
        or execution_status != "not_started"
    ):
        raise Phase9FDConfirmationError(
            "The exact Phase 9F-D execution provenance is inconsistent.",
            code="phase9f_d_execution_provenance_inconsistent",
        )
    intensity_label = INTENSITY_LABELS[semantic_intensity]
    return {
        "status": PHASE9F_D_EXECUTION_NOT_STARTED_STATUS,
        "source_binding_status": "bound",
        "execution_status": execution_status,
        "confirmed_intensity": semantic_intensity,
        "confirmed_intensity_label": intensity_label,
        "next_action": f"Begin {intensity_label} tailoring",
    }


def _source_identity(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(candidate.get(key))
        for key in (
            "source_type",
            "source_id",
            "source_version",
            "source_fingerprint",
            "source_content_fingerprint",
            "normalized_source_fingerprint",
            "source_display_name",
            "source_role_family_id",
            "source_role_family_label",
            "role_family_relationship",
            "stable_input_fingerprint",
            "comparison_result_fingerprint",
            "candidate_analysis_snapshot_fingerprint",
            "exact_verified_reuse_eligible",
            "exact_verified_reuse_reason_code",
            "exact_verified_reuse_proof_fingerprint",
            "exact_verified_reuse",
        )
    }


def _jd_semantics_match(
    original: dict[str, Any],
    persisted: dict[str, Any],
) -> bool:
    return original.get("semantic_identity") == persisted.get(
        "semantic_identity"
    )


def validate_phase9f_c_recommendation(
    recommendation: Any,
    *,
    ranking_result: dict[str, Any],
) -> dict[str, Any]:
    """Reproduce and validate Phase 9F-C from the exact B winner."""
    if not isinstance(recommendation, dict):
        raise Phase9FDConfirmationError(
            "The Phase 9F-C recommendation is missing.",
            code="phase9f_c_recommendation_missing",
        )
    expected_input = _clean(ranking_result.get("ranking_input_fingerprint"))
    reproduced = recommend_tailoring_intensity(
        ranking_result,
        expected_ranking_input_fingerprint=expected_input,
    )
    if reproduced.get("status") != "recommended":
        raise Phase9FDConfirmationError(
            "Phase 9F-C no longer has a valid recommendation for this ranking.",
            code="phase9f_c_recommendation_invalid",
        )
    if (
        _clean(recommendation.get("phase9f_c_version")) != PHASE9F_C_VERSION
        or _clean(recommendation.get("recommendation_fingerprint"))
        != _clean(reproduced.get("recommendation_fingerprint"))
        or recommendation.get("semantic_identity")
        != reproduced.get("semantic_identity")
        or _clean(recommendation.get("recommended_intensity"))
        != _clean(reproduced.get("recommended_intensity"))
    ):
        raise Phase9FDConfirmationError(
            "The Phase 9F-C recommendation is stale or internally inconsistent.",
            code="phase9f_c_recommendation_stale",
        )
    return reproduced


def prepare_phase9f_d_confirmation(
    *,
    phase9f_a_snapshot: dict[str, Any],
    persisted_exact_jd_snapshot: dict[str, Any],
    ranking_result: dict[str, Any],
    phase9f_c_recommendation: dict[str, Any],
    confirmed_normalized_source_fingerprint: str,
    confirmed_intensity: str,
) -> dict[str, Any]:
    """Validate transient A/B/C and build one immutable content contract."""
    try:
        original_jd = validate_exact_jd_snapshot(
            deepcopy(phase9f_a_snapshot)
        )
        persisted_jd = validate_exact_jd_snapshot(
            deepcopy(persisted_exact_jd_snapshot)
        )
    except Phase9FBRankingError as exc:
        raise Phase9FDConfirmationError(
            str(exc), code="phase9f_a_or_persisted_jd_invalid"
        ) from exc
    if not _jd_semantics_match(original_jd, persisted_jd):
        raise Phase9FDConfirmationError(
            "The prepared persisted JD does not match the analyzed Phase 9F-A JD.",
            code="prepared_jd_semantic_mismatch",
        )

    expected_ranking_input = _clean(
        ranking_result.get("ranking_input_fingerprint")
    )
    try:
        validated_ranking = validate_ranked_result_contract(
            ranking_result,
            expected_ranking_input_fingerprint=expected_ranking_input,
        )
    except Phase9FBRankingError as exc:
        raise Phase9FDConfirmationError(
            str(exc), code="phase9f_b_result_invalid"
        ) from exc
    ranking_exact_jd = (
        ranking_result.get("semantic_identity") or {}
    ).get("exact_jd")
    if ranking_exact_jd != original_jd.get("semantic_identity"):
        raise Phase9FDConfirmationError(
            "The Phase 9F-B ranking was produced for a different Phase 9F-A JD.",
            code="phase9f_b_jd_mismatch",
        )

    selected_fingerprint = _clean(
        confirmed_normalized_source_fingerprint
    )
    selected_rows = [
        row
        for row in ranking_result.get("ranked_candidates", []) or []
        if _clean(row.get("normalized_source_fingerprint"))
        == selected_fingerprint
    ]
    if len(selected_rows) != 1:
        raise Phase9FDConfirmationError(
            "The confirmed source is missing or ambiguous in the current Phase 9F-B scope.",
            code="confirmed_source_missing_or_ambiguous",
        )
    selected = deepcopy(selected_rows[0])
    try:
        selected_analysis = validate_ranked_candidate_analysis_snapshot(
            selected
        )
    except Phase9FBRankingError as exc:
        raise Phase9FDConfirmationError(
            str(exc), code="selected_candidate_analysis_invalid"
        ) from exc

    reproduced_c = validate_phase9f_c_recommendation(
        phase9f_c_recommendation,
        ranking_result=ranking_result,
    )
    intensity = _clean(confirmed_intensity).lower()
    if intensity not in VALID_INTENSITIES:
        raise Phase9FDConfirmationError(
            "Confirmed tailoring intensity must be Reuse, Minor, or Full.",
            code="confirmed_intensity_invalid",
        )

    recommended = deepcopy(validated_ranking["recommended_source"])
    recommended_source = _source_identity(recommended)
    confirmed_source = _source_identity(selected)
    recommended_intensity = _clean(
        reproduced_c.get("recommended_intensity")
    )
    source_overridden = (
        confirmed_source["normalized_source_fingerprint"]
        != recommended_source["normalized_source_fingerprint"]
    )
    intensity_overridden = intensity != recommended_intensity
    if source_overridden and intensity_overridden:
        override_classification = "source_and_intensity_override"
    elif source_overridden:
        override_classification = "source_override"
    elif intensity_overridden:
        override_classification = "intensity_override"
    else:
        override_classification = "followed_recommendations"

    candidate_scope = [
        {
            "rank": int(row.get("rank") or 0),
            **_source_identity(row),
        }
        for row in ranking_result.get("ranked_candidates", []) or []
    ]
    content_identity = {
        "format_version": PHASE9F_D_VERSION,
        "identity_policy_version": PHASE9F_D_IDENTITY_POLICY_VERSION,
        "phase9f_a": {
            "snapshot_fingerprint": _clean(
                phase9f_a_snapshot.get("snapshot_fingerprint")
            ),
            "semantic_identity": deepcopy(original_jd["semantic_identity"]),
            "persisted_exact_jd": deepcopy(
                persisted_jd["semantic_identity"]
            ),
        },
        "phase9f_b": {
            "format_version": PHASE9F_B_VERSION,
            "ranking_input_fingerprint": expected_ranking_input,
            "ranking_fingerprint": validated_ranking[
                "ranking_fingerprint"
            ],
            "candidate_scope": candidate_scope,
        },
        "recommendation": {
            "recommended_source": recommended_source,
            "recommended_intensity_for_recommended_source": (
                recommended_intensity
            ),
            "phase9f_c_recommendation_fingerprint": _clean(
                reproduced_c.get("recommendation_fingerprint")
            ),
            "phase9f_c_decisive_rule": deepcopy(
                reproduced_c.get("decisive_rule") or {}
            ),
            "phase9f_c_reason_codes": list(
                reproduced_c.get("reason_codes") or []
            ),
        },
        "confirmation": {
            "confirmed_source": confirmed_source,
            "confirmed_intensity": intensity,
            "selected_candidate_analysis_snapshot_fingerprint": _clean(
                selected.get("candidate_analysis_snapshot_fingerprint")
            ),
            "override_classification": override_classification,
            "source_overridden": source_overridden,
            "intensity_overridden": intensity_overridden,
        },
    }
    content_fingerprint = fingerprint_value(content_identity)
    original_role_family = deepcopy(
        (phase9f_a_snapshot.get("semantic_identity") or {}).get(
            "role_family"
        )
        or {}
    )
    return {
        "confirmation_content_identity": content_identity,
        "confirmation_content_fingerprint": content_fingerprint,
        "original_exact_jd": original_jd,
        "persisted_exact_jd": persisted_jd,
        "validated_ranking": validated_ranking,
        "selected_candidate": selected,
        "selected_candidate_analysis": selected_analysis,
        "phase9f_c_recommendation": reproduced_c,
        "recommended_source": recommended_source,
        "confirmed_source": confirmed_source,
        "recommended_intensity_for_recommended_source": (
            recommended_intensity
        ),
        "confirmed_intensity": intensity,
        "override_classification": override_classification,
        "source_overridden": source_overridden,
        "intensity_overridden": intensity_overridden,
        # The full Phase 9F-A role-family row is covered by the already
        # validated Phase 9F-A snapshot fingerprint.  The narrower Phase
        # 9F-B semantic identity intentionally omits display/explanation
        # fields, but the Application Session needs the canonical label and
        # classifier audit fields for inspection.
        "original_role_family": original_role_family,
        "zero_cost_diagnostics": zero_cost_diagnostics(),
    }


def build_application_baseline_report(
    prepared: dict[str, Any],
) -> dict[str, Any]:
    """Adapt one exact B snapshot to the existing Application report schema."""
    selected = prepared["selected_candidate"]
    validated = validate_ranked_candidate_analysis_snapshot(selected)
    snapshot = validated["candidate_analysis_snapshot"]
    analysis = deepcopy(snapshot["stable_analysis_snapshot"])
    keyword_match = deepcopy(snapshot["keyword_match_snapshot"])
    profile = deepcopy(snapshot["resume_profile_snapshot"])
    jd_profile = deepcopy(snapshot["jd_profile_snapshot"])
    raw_resume_text = str(snapshot["resume_text_snapshot"])
    raw_jd_text = str(snapshot["raw_jd_text_snapshot"])
    if not profile or not jd_profile or not raw_resume_text.strip() or not raw_jd_text.strip():
        raise Phase9FDConfirmationError(
            "The selected B snapshot cannot populate the Application baseline.",
            code="application_baseline_content_missing",
        )

    alignment = int(analysis.get("deterministic_alignment_score") or 0)
    return {
        "meta": {
            "model": "deterministic-phase9f-b-baseline",
            "degree": "",
            "actual_page_count": None,
            "phase9f_d_baseline": {
                "adapter_version": PHASE9F_D_BASELINE_ADAPTER_VERSION,
                "confirmation_content_fingerprint": prepared[
                    "confirmation_content_fingerprint"
                ],
                "ranking_input_fingerprint": prepared[
                    "confirmation_content_identity"
                ]["phase9f_b"]["ranking_input_fingerprint"],
                "ranking_fingerprint": prepared[
                    "confirmation_content_identity"
                ]["phase9f_b"]["ranking_fingerprint"],
                "selected_candidate_analysis_snapshot_fingerprint": (
                    validated["candidate_analysis_snapshot_fingerprint"]
                ),
                "selected_comparison_result_fingerprint": _clean(
                    selected.get("comparison_result_fingerprint")
                ),
            },
        },
        "resume_profile": profile,
        "raw_resume_text": raw_resume_text,
        "jd_profile": jd_profile,
        "raw_jd_text": raw_jd_text,
        "keyword_match": keyword_match,
        "stable_analysis": analysis,
        # Existing downstream consumers use safe .get() access for these
        # legacy diagnostics. They are intentionally neutral because Phase
        # 9F-D does not rerun the model-backed legacy analysis pipeline.
        "bullets": {},
        "jargon": {},
        "structure": {},
        "degree_alignment": {},
        "overall_score": alignment,
        "passes_ats_threshold": False,
        "summary": (
            "Initialized from the exact Phase 9F-B selected-source current-JD "
            "analysis. No tailoring has been executed."
        ),
    }


def build_exact_phase9e_starting_snapshot(
    prepared: dict[str, Any],
    *,
    authoritative_source: dict[str, Any],
) -> dict[str, Any]:
    selected = prepared["selected_candidate"]
    analysis_snapshot = prepared["selected_candidate_analysis"][
        "candidate_analysis_snapshot"
    ]
    source_type = _clean(selected.get("source_type"))
    if source_type == "base_resume":
        authority = authoritative_source.get("master_snapshot")
        authority_key = "phase9f_master_resume_snapshot"
        fidelity = "phase9f_master_complete_immutable_snapshot"
    elif source_type == "global_blueprint":
        authority = authoritative_source.get("blueprint_snapshot")
        authority_key = "phase9d_blueprint_snapshot"
        fidelity = "phase9d_complete_frozen_snapshot"
    else:
        raise Phase9FDConfirmationError(
            "The confirmed starting-source type is unsupported.",
            code="confirmed_source_type_unsupported",
        )
    if not isinstance(authority, dict) or not authority:
        raise Phase9FDConfirmationError(
            "The authoritative immutable starting-source snapshot is missing.",
            code="authoritative_source_snapshot_missing",
        )
    starting = {
        "source_type": source_type,
        "source_fidelity": fidelity,
        "resume_text_is_original_uploaded_text": False,
        "resume_text_representation_method": (
            "phase9f_d_confirmed_immutable_source_text"
        ),
        "resume_profile_snapshot": deepcopy(
            analysis_snapshot["resume_profile_snapshot"]
        ),
        "resume_text_snapshot": str(
            analysis_snapshot["resume_text_snapshot"]
        ),
        "source_identity": _source_identity(selected),
        authority_key: deepcopy(authority),
    }
    starting["starting_snapshot_fingerprint"] = fingerprint_value(starting)
    return starting


def build_exact_phase9e_decision(
    *,
    application_id: int,
    linked_exact_jd: dict[str, Any],
    prepared: dict[str, Any],
    authoritative_source: dict[str, Any],
) -> dict[str, Any]:
    """Build the additive exact Phase 9E binding chosen by Phase 9F-D."""
    if int(application_id) <= 0:
        raise Phase9FDConfirmationError(
            "A positive Application Session ID is required.",
            code="application_id_invalid",
        )
    selected = prepared["selected_candidate"]
    starting = build_exact_phase9e_starting_snapshot(
        prepared,
        authoritative_source=authoritative_source,
    )
    analysis_snapshot = prepared["selected_candidate_analysis"][
        "candidate_analysis_snapshot"
    ]
    stable_analysis = deepcopy(
        analysis_snapshot["stable_analysis_snapshot"]
    )
    keyword_match = deepcopy(analysis_snapshot["keyword_match_snapshot"])
    source_type = _clean(selected.get("source_type"))
    selected_blueprint = {}
    if source_type == "global_blueprint":
        selected_blueprint = {
            "blueprint_id": _clean(authoritative_source.get("blueprint_id")),
            "blueprint_fingerprint": _clean(
                authoritative_source.get("blueprint_fingerprint")
            ),
            "version_number": int(
                authoritative_source.get("version_number") or 0
            ),
            "role_family_id": _clean(
                authoritative_source.get("role_family_id")
            ),
            "role_family_label": _clean(
                authoritative_source.get("role_family_label")
            ),
        }
    role = deepcopy(prepared.get("original_role_family") or {})
    jd_identity = {
        "library_jd_id": int(linked_exact_jd.get("library_jd_id") or 0),
        "canonical_jd_id": _clean(linked_exact_jd.get("canonical_jd_id")),
        "source_version_id": _clean(linked_exact_jd.get("source_version_id")),
        "raw_jd_sha256": _clean(linked_exact_jd.get("raw_jd_sha256")),
        "canonical_requirement_ids": list(
            linked_exact_jd.get("canonical_requirement_ids") or []
        ),
        "canonical_requirement_fingerprint": _clean(
            linked_exact_jd.get("canonical_requirement_fingerprint")
        ),
        "source_application_link": deepcopy(
            linked_exact_jd.get("source_application_link") or {}
        ),
        "stable_input_fingerprint": _clean(
            selected.get("stable_input_fingerprint")
        ),
    }
    role_mismatch = bool(
        source_type == "global_blueprint"
        and _clean(selected.get("source_role_family_id"))
        != _clean(role.get("role_family_id"))
    )
    confirmed_intensity = prepared["confirmed_intensity"]
    phase9e_decision = INTENSITY_TO_PHASE9E_DECISION[confirmed_intensity]
    comparison = {
        "stable_analysis_snapshot": stable_analysis,
        "keyword_match_snapshot": keyword_match,
        "stable_input_fingerprint": _clean(
            selected.get("stable_input_fingerprint")
        ),
        "comparison_result_fingerprint": _clean(
            selected.get("comparison_result_fingerprint")
        ),
        "candidate_analysis_snapshot_fingerprint": _clean(
            selected.get("candidate_analysis_snapshot_fingerprint")
        ),
        "scoring_version": _clean(selected.get("scoring_version")),
        "capability_taxonomy_version": _clean(
            selected.get("capability_taxonomy_version")
        ),
        "evidence_selection_policy_version": _clean(
            selected.get("evidence_policy_version")
        ),
        "deterministic_alignment_score": int(
            selected.get("deterministic_alignment_score") or 0
        ),
        "required_core_coverage_score": int(
            selected.get("required_core_coverage_score") or 0
        ),
        "preferred_coverage_score": int(
            selected.get("preferred_coverage_score") or 0
        ),
        "evidence_strength_score": int(
            selected.get("evidence_strength_score") or 0
        ),
        "important_gaps": deepcopy(selected.get("important_gaps") or []),
    }
    semantic_identity = {
        "phase9e_version": PHASE9E_PHASE9F_D_EXACT_BINDING_VERSION,
        "identity_policy_version": (
            PHASE9E_PHASE9F_D_EXACT_BINDING_POLICY_VERSION
        ),
        "application_id": int(application_id),
        "current_jd": jd_identity,
        "role_family_classification": deepcopy(role),
        "phase9f_d_confirmation": {
            "format_version": PHASE9F_D_VERSION,
            "confirmation_content_fingerprint": prepared[
                "confirmation_content_fingerprint"
            ],
            "ranking_fingerprint": prepared["validated_ranking"][
                "ranking_fingerprint"
            ],
            "recommended_source": deepcopy(prepared["recommended_source"]),
            "recommended_intensity_for_recommended_source": prepared[
                "recommended_intensity_for_recommended_source"
            ],
            "confirmed_source": deepcopy(prepared["confirmed_source"]),
            "confirmed_intensity": confirmed_intensity,
            "override_classification": prepared[
                "override_classification"
            ],
        },
        "selection": {
            "selected_source": source_type,
            "selection_mode": "phase9f_d_explicit_confirmation",
            "selected_blueprint": deepcopy(selected_blueprint),
            "role_family_mismatch": role_mismatch,
            "starting_snapshot_fingerprint": starting[
                "starting_snapshot_fingerprint"
            ],
            "candidate_analysis_snapshot_fingerprint": _clean(
                selected.get("candidate_analysis_snapshot_fingerprint")
            ),
        },
        "scoring": {
            "scoring_version": _clean(selected.get("scoring_version")),
            "capability_taxonomy_version": _clean(
                selected.get("capability_taxonomy_version")
            ),
            "evidence_policy_version": _clean(
                selected.get("evidence_policy_version")
            ),
            "stable_input_fingerprint": _clean(
                selected.get("stable_input_fingerprint")
            ),
            "comparison_result_fingerprint": _clean(
                selected.get("comparison_result_fingerprint")
            ),
        },
        "decision": {
            "confirmed_intensity": confirmed_intensity,
            "phase9e_compatibility_decision": phase9e_decision,
            "execution_status": "not_started",
        },
    }
    decision_fingerprint = fingerprint_value(semantic_identity)
    all_sections = ["education", "work_experience", "projects", "skills"]
    section_scope = {
        "locked_sections": all_sections,
        "tailorable_sections": [],
        "optional_tailorable_sections": [],
        "projects_locked": True,
        "skills_locked": True,
        "protected_section_reason": (
            "Phase 9F-D configures the Application Session only. Tailoring "
            "execution has not started."
        ),
    }
    return {
        "phase9e_version": PHASE9E_PHASE9F_D_EXACT_BINDING_VERSION,
        "identity_policy_version": (
            PHASE9E_PHASE9F_D_EXACT_BINDING_POLICY_VERSION
        ),
        "decision_id": decision_fingerprint[:32],
        "decision_fingerprint": decision_fingerprint,
        "application_id": int(application_id),
        "semantic_identity": semantic_identity,
        "selection": {
            "selected_source": source_type,
            "selection_mode": "phase9f_d_explicit_confirmation",
            "selected_blueprint": selected_blueprint,
            "selected_blueprint_display_name": (
                _clean(authoritative_source.get("display_name"))
                if source_type == "global_blueprint"
                else ""
            ),
            "role_family_mismatch": role_mismatch,
            "mismatch_acknowledged": True,
            "effective_starting_source": source_type,
        },
        "recommendation": {
            "recommended_source": deepcopy(prepared["recommended_source"]),
            "recommended_intensity_for_recommended_source": prepared[
                "recommended_intensity_for_recommended_source"
            ],
        },
        "role_family_classification": deepcopy(role),
        "current_jd_snapshot": deepcopy(linked_exact_jd),
        "starting_snapshot": starting,
        "diagnostic_starting_snapshot": deepcopy(starting),
        "comparison": comparison,
        "effective_starting_comparison": deepcopy(comparison),
        "diagnostic_visible_scoring": {
            "controls_exact_source_binding": True,
            "comparison_result_fingerprint": comparison[
                "comparison_result_fingerprint"
            ],
            "candidate_analysis_snapshot_fingerprint": comparison[
                "candidate_analysis_snapshot_fingerprint"
            ],
        },
        "original_resume_comparison": None,
        "original_resume_comparison_policy": {},
        "source_approval": None,
        "recommended_tailoring": phase9e_decision,
        "recommended_tailoring_label": INTENSITY_LABELS[
            confirmed_intensity
        ],
        "decision_reasons": [
            "The exact starting source and intensity were explicitly confirmed in Phase 9F-D.",
            "No tailoring execution occurred during confirmation.",
        ],
        "section_lock_scope": section_scope,
        "workflow_action_policy": {
            "policy_version": PHASE9E_WORKFLOW_ACTION_POLICY_VERSION,
            "default_action": "awaiting_explicit_choice",
            "available_actions": [],
        },
        "phase9f_d_execution": {
            "status": "not_started",
            "confirmed_intensity": confirmed_intensity,
        },
        "binding_event_version": PHASE9E_BINDING_EVENT_VERSION,
        "mutation_policy": {
            "application_report_mutated": False,
            "immutable_source_mutated": False,
            "saved_jd_mutated": False,
            "resume_snapshot_mutated": False,
            **zero_cost_diagnostics(),
        },
    }


def build_confirmation_operation_key(
    *,
    confirmation_content_fingerprint: str,
    application_intent_id: str,
) -> str:
    content = _clean(confirmation_content_fingerprint)
    intent = _clean(application_intent_id)
    if not content or not intent:
        raise Phase9FDConfirmationError(
            "Confirmation content and application intent identities are required.",
            code="confirmation_operation_identity_incomplete",
        )
    return fingerprint_value(
        {
            "idempotency_policy_version": (
                PHASE9F_D_IDEMPOTENCY_POLICY_VERSION
            ),
            "confirmation_content_fingerprint": content,
            "application_intent_id": intent,
        }
    )

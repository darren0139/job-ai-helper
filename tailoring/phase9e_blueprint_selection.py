"""Phase 9E deterministic application-to-blueprint selection semantics."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Iterable

from analysis_stability.stable_evidence_scoring import (
    SCORING_VERSION,
    build_deterministic_keyword_match,
    build_resume_evidence_index,
    build_stable_analysis,
    compute_deterministic_alignment,
)
from tailoring.capability_taxonomy import (
    evaluate_evidence,
    get_default_taxonomy,
)
from tailoring.phase8_verification import build_resume_text_from_profile
from tailoring.phase9b_role_family import suggest_role_family
from tailoring.phase9d_global_blueprint import (
    PHASE9D_LEGACY_FINGERPRINT_POLICY_VERSION,
    PHASE9D_FINGERPRINT_POLICY_VERSION,
    PHASE9D_VERSION,
)
from tailoring.jd_user_input_overrides import (
    apply_preferred_requirement_overrides_to_canonical_rows,
    build_effective_application_local_requirement_scope,
    effective_stable_input_fingerprint,
    normalise_requirement_override_lines,
    preferred_requirement_override_cache_identity,
    requirement_override_key,
    tag_application_local_supplemental_requirement_row,
)


PHASE9E_VERSION = "phase9e-application-blueprint-selection-v1"
PHASE9E_IDENTITY_POLICY_VERSION = (
    "phase9e-application-blueprint-identity-v2"
)
PHASE9E_ORIGINAL_SOURCE_IDENTITY_POLICY_VERSION = (
    "phase9e-original-resume-source-identity-v2"
)
PHASE9E_RECOMMENDATION_POLICY_VERSION = (
    "phase9e-same-family-active-recommendation-v1"
)
PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION = (
    "phase9e-capability-aware-single-row-evidence-v1"
)
PHASE9E_DECISION_POLICY_VERSION = (
    "phase9e-incremental-change-decision-v3"
)
PHASE9E_EXACT_SOURCE_REUSE_POLICY_VERSION = (
    "phase9e-exact-approved-source-reuse-v1"
)
PHASE9E_BINDING_EVENT_VERSION = (
    "phase9e-application-blueprint-binding-event-v2"
)
PHASE9E_WORKFLOW_ACTION_POLICY_VERSION = "phase9e-workflow-action-v1"

REUSE_OVERALL_MINIMUM = 85
REUSE_REQUIRED_CORE_MINIMUM = 90
REUSE_PREFERRED_MINIMUM = 65
REUSE_EVIDENCE_MINIMUM = 80
MINOR_OVERALL_MINIMUM = 65
MINOR_REQUIRED_CORE_MINIMUM = 65
MINOR_EVIDENCE_MINIMUM = 60
MINOR_IMPORTANT_GAP_MAXIMUM = 2
ORIGINAL_SUPERIORITY_MINIMUM_DELTA = 10
IMPORTANT_REQUIREMENTS = {"deal_breaker", "required", "core"}
DECISION_LABELS = {
    "reuse_approved_source": "Reuse approved blueprint",
    "reuse_unchanged": "Reuse unchanged",
    "optional_polish": "Optional polish",
    "targeted_retailor": "Targeted retargeting",
    "full_regeneration": "Regenerate from original résumé",
}
ALL_RESUME_SECTIONS = [
    "education",
    "work_experience",
    "projects",
    "skills",
]
_TAXONOMY_LABEL_ORDER = {
    "none": 0,
    "weak": 1,
    "transferable": 2,
    "direct": 3,
}
_MATCH_VALUES = {
    "none": 0.0,
    "weak": 0.20,
    "transferable": 0.55,
    "direct": 1.0,
}
_EVIDENCE_STRENGTH_CEILING = {
    "none": 0,
    "weak": 2,
    "transferable": 3,
    "direct": 5,
}


class Phase9EDecisionError(ValueError):
    """Raised when Phase 9E cannot produce a reproducible decision."""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _application_local_preferred_requirements(
    application_report: dict[str, Any] | None,
) -> list[str]:
    """Read only explicit v2 requirement overrides from this application.

    The shared exact JD remains deliberately unaware of this application-local
    scope.  Its canonical identity is still used for provenance and source-JD
    parity; this helper supplies the separately persisted user choice to the
    Phase 9E comparison that renders and drives the selected starting source.
    """
    inputs = (
        (application_report or {}).get("meta", {}).get("jd_user_inputs")
        or {}
    )
    return normalise_requirement_override_lines(
        inputs.get("preferred_requirement_overrides")
    )


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def fingerprint_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _blueprint_identity(blueprint: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(blueprint, dict):
        return {}
    return {
        "blueprint_id": _clean(blueprint.get("blueprint_id")),
        "blueprint_fingerprint": _clean(
            blueprint.get("blueprint_fingerprint")
        ),
        "version_number": int(blueprint.get("version_number", 0) or 0),
        "role_family_id": _clean(blueprint.get("role_family_id")),
        "role_family_label": _clean(blueprint.get("role_family_label")),
    }


def _source_is_provisional(blueprint: dict[str, Any]) -> bool:
    snapshot = blueprint.get("blueprint_snapshot") or {}
    evaluation = snapshot.get("phase9c_evaluation_snapshot") or {}
    aggregate = evaluation.get("aggregate_result") or {}
    return aggregate.get("provisional") is True


def validate_active_blueprint(blueprint: dict[str, Any]) -> dict[str, Any]:
    """Validate one complete active Phase 9D blueprint without mutation."""
    if not isinstance(blueprint, dict):
        raise Phase9EDecisionError("A selected active blueprint is required.")
    if _clean(blueprint.get("status")) != "active":
        raise Phase9EDecisionError("The selected blueprint is not active.")
    if _clean(blueprint.get("phase9d_version")) != PHASE9D_VERSION:
        raise Phase9EDecisionError("The selected blueprint format is not current.")
    if _clean(blueprint.get("fingerprint_policy_version")) not in {
        PHASE9D_FINGERPRINT_POLICY_VERSION,
        PHASE9D_LEGACY_FINGERPRINT_POLICY_VERSION,
    }:
        raise Phase9EDecisionError(
            "The selected blueprint identity policy is not current."
        )

    snapshot = blueprint.get("blueprint_snapshot")
    if not isinstance(snapshot, dict):
        raise Phase9EDecisionError("The selected blueprint snapshot is missing.")
    semantic = snapshot.get("semantic_identity")
    if not isinstance(semantic, dict):
        raise Phase9EDecisionError("The blueprint semantic identity is missing.")
    expected_fingerprint = fingerprint_value(semantic)
    actual_fingerprint = _clean(blueprint.get("blueprint_fingerprint"))
    if expected_fingerprint != actual_fingerprint:
        raise Phase9EDecisionError(
            "The blueprint row and immutable semantic identity do not match."
        )
    if _clean(blueprint.get("blueprint_id")) != actual_fingerprint[:32]:
        raise Phase9EDecisionError("The blueprint ID does not match its fingerprint.")

    frozen = snapshot.get("frozen_resume_snapshot")
    if not isinstance(frozen, dict):
        raise Phase9EDecisionError("The complete frozen resume snapshot is missing.")
    profile = frozen.get("resume_profile_snapshot")
    text = frozen.get("resume_text_snapshot")
    if not isinstance(profile, dict) or not _clean(text):
        raise Phase9EDecisionError(
            "The blueprint must contain frozen profile and text snapshots."
        )
    missing = [
        section
        for section in ("education", "experience", "projects", "skills")
        if section not in profile
    ]
    if missing:
        raise Phase9EDecisionError(
            "The frozen blueprint profile is missing sections: "
            + ", ".join(missing)
        )

    evaluation_identity = semantic.get("evaluation") or {}
    if _clean(evaluation_identity.get("scoring_version")) != SCORING_VERSION:
        raise Phase9EDecisionError(
            "The blueprint scorer provenance is not current."
        )
    if (
        _clean(evaluation_identity.get("taxonomy_version"))
        != get_default_taxonomy().version
    ):
        raise Phase9EDecisionError(
            "The blueprint taxonomy provenance is not current."
        )
    snapshot_role_id = _clean(snapshot.get("role_family_id"))
    if snapshot_role_id != _clean(blueprint.get("role_family_id")):
        raise Phase9EDecisionError(
            "The blueprint row and snapshot role families do not match."
        )
    return blueprint


def validate_exact_jd_snapshot(jd: dict[str, Any]) -> dict[str, Any]:
    required = (
        "library_jd_id",
        "canonical_jd_id",
        "source_version_id",
        "raw_jd_sha256",
        "canonical_requirement_fingerprint",
    )
    if not isinstance(jd, dict):
        raise Phase9EDecisionError("An exact application JD snapshot is required.")
    missing = [field for field in required if not _clean(jd.get(field))]
    if missing:
        raise Phase9EDecisionError(
            "The exact application JD is missing: " + ", ".join(missing)
        )
    if not _clean(jd.get("raw_text")) or not isinstance(
        jd.get("jd_profile"), dict
    ):
        raise Phase9EDecisionError(
            "The exact application JD requires raw text and a parsed profile."
        )
    rows = jd.get("canonical_requirements")
    if not isinstance(rows, list) or not rows:
        raise Phase9EDecisionError(
            "The exact application JD has no canonical requirements."
        )
    raw_hash = hashlib.sha256(
        str(jd.get("raw_text") or "").encode("utf-8")
    ).hexdigest()
    if raw_hash != _clean(jd.get("raw_jd_sha256")):
        raise Phase9EDecisionError("The exact application JD raw hash is stale.")
    return jd


def _text_sha256(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _phase9c_source_stable_input_fingerprint(
    *,
    profile: dict[str, Any],
    resume_text: str,
    exact_jd: dict[str, Any],
    scoring_version: str,
    taxonomy_version: str,
) -> str:
    return fingerprint_value(
        {
            "resume_profile_snapshot": profile,
            "resume_text_snapshot_sha256": _text_sha256(resume_text),
            "raw_jd_sha256": _clean(exact_jd.get("raw_jd_sha256")),
            "jd_profile": exact_jd.get("jd_profile"),
            "scoring_version": scoring_version,
            "capability_taxonomy_version": taxonomy_version,
            "retrieval_mode": "lexical",
        }
    )


def match_exact_approved_source(
    *,
    application_id: int,
    exact_jd: dict[str, Any],
    blueprint: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed on corrupt provenance and identify an exact source match."""
    validate_active_blueprint(blueprint)
    validate_exact_jd_snapshot(exact_jd)
    snapshot = blueprint["blueprint_snapshot"]
    semantic = snapshot["semantic_identity"]
    candidate_identity = semantic.get("candidate") or {}
    evaluation_identity = semantic.get("evaluation") or {}
    evaluation = snapshot.get("phase9c_evaluation_snapshot") or {}
    evaluation_semantic = evaluation.get("semantic_identity") or {}
    candidate = snapshot.get("phase9b_candidate_semantic_snapshot") or {}
    frozen = snapshot.get("frozen_resume_snapshot") or {}

    source_results = [
        row
        for row in evaluation.get("per_jd_results", []) or []
        if isinstance(row, dict) and row.get("is_source_jd") is True
    ]
    if len(source_results) != 1:
        raise Phase9EDecisionError(
            "The approved blueprint must contain exactly one Phase 9C source JD."
        )
    source = source_results[0]
    source_scope = [
        row
        for row in evaluation_semantic.get("selected_jd_scope", []) or []
        if isinstance(row, dict)
        and row.get("selection_decision") == "evaluated"
        and all(
            _clean(row.get(field)) == _clean(source.get(field))
            for field in (
                "canonical_jd_id",
                "source_version_id",
                "raw_jd_sha256",
                "canonical_requirement_fingerprint",
                "stable_input_fingerprint",
            )
        )
    ]
    stable_rows = [
        row
        for row in semantic.get("stable_input_provenance", []) or []
        if isinstance(row, dict)
        and all(
            _clean(row.get(field)) == _clean(source.get(field))
            for field in (
                "canonical_jd_id",
                "source_version_id",
                "raw_jd_sha256",
                "canonical_requirement_fingerprint",
                "stable_input_fingerprint",
            )
        )
    ]
    if len(source_scope) != 1 or len(stable_rows) != 1:
        raise Phase9EDecisionError(
            "The approved source JD has missing or ambiguous stable provenance."
        )

    phase9c_candidate = evaluation_semantic.get("candidate") or {}
    policy = evaluation_semantic.get("policy") or {}
    internal_checks = {
        "candidate_semantic_snapshot_fingerprint": fingerprint_value(candidate)
        == _clean(candidate_identity.get("semantic_snapshot_fingerprint")),
        "blueprint_candidate_id": _clean(candidate.get("candidate_id"))
        == _clean(candidate_identity.get("candidate_id")),
        "blueprint_candidate_fingerprint": _clean(
            candidate.get("candidate_fingerprint")
        )
        == _clean(candidate_identity.get("candidate_fingerprint")),
        "phase9c_candidate_id": _clean(phase9c_candidate.get("candidate_id"))
        == _clean(candidate_identity.get("candidate_id")),
        "phase9c_candidate_fingerprint": _clean(
            phase9c_candidate.get("candidate_fingerprint")
        )
        == _clean(candidate_identity.get("candidate_fingerprint")),
        "evaluation_id": _clean(evaluation.get("evaluation_id"))
        == _clean(evaluation_identity.get("evaluation_id")),
        "evaluation_fingerprint": _clean(
            evaluation.get("evaluation_fingerprint")
        )
        == _clean(evaluation_identity.get("evaluation_fingerprint")),
        "evaluation_semantic_fingerprint": fingerprint_value(
            evaluation_semantic
        )
        == _clean(evaluation_identity.get("semantic_identity_fingerprint")),
        "evaluation_policy": _clean(policy.get("policy_version"))
        == _clean(evaluation_identity.get("policy_version")),
        "evaluation_scorer": _clean(phase9c_candidate.get("scoring_version"))
        == _clean(evaluation_identity.get("scoring_version")),
        "evaluation_taxonomy": _clean(
            phase9c_candidate.get("capability_taxonomy_version")
        )
        == _clean(evaluation_identity.get("taxonomy_version")),
        "source_application_id": int(
            candidate.get("source_application_id", 0) or 0
        )
        == int(candidate_identity.get("source_application_id", 0) or 0)
        == int(phase9c_candidate.get("source_application_id", 0) or 0),
        "source_verification_fingerprint": _clean(
            candidate.get("source_verification_fingerprint")
        )
        == _clean(candidate_identity.get("source_verification_fingerprint"))
        == _clean(phase9c_candidate.get("source_verification_fingerprint")),
        "source_requirement_summary_fingerprint": _clean(
            candidate_identity.get("source_jd_requirement_summary_fingerprint")
        )
        == _clean(
            phase9c_candidate.get(
                "source_jd_requirement_summary_fingerprint"
            )
        ),
        "source_parity_accepted": bool(
            (source.get("source_jd_parity") or {}).get("accepted")
        ),
        "source_scorer": _clean(source.get("scoring_version"))
        == _clean(evaluation_identity.get("scoring_version")),
        "source_taxonomy": _clean(
            source.get("capability_taxonomy_version")
        )
        == _clean(evaluation_identity.get("taxonomy_version")),
        "resume_profile_fingerprint": fingerprint_value(
            frozen.get("resume_profile_snapshot")
        )
        == _clean(
            (semantic.get("resume_snapshot") or {}).get(
                "resume_profile_snapshot_fingerprint"
            )
        ),
        "resume_text_fingerprint": _text_sha256(
            frozen.get("resume_text_snapshot")
        )
        == _clean(
            (semantic.get("resume_snapshot") or {}).get(
                "resume_text_snapshot_sha256"
            )
        ),
        "complete_resume_fingerprint": fingerprint_value(
            {
                "resume_profile_snapshot": frozen.get(
                    "resume_profile_snapshot"
                ),
                "resume_text_snapshot": str(
                    frozen.get("resume_text_snapshot") or ""
                ),
            }
        )
        == _clean(
            (semantic.get("resume_snapshot") or {}).get(
                "complete_snapshot_fingerprint"
            )
        ),
        "canonical_role_family": _clean(
            (semantic.get("role_family") or {}).get("role_family_id")
        )
        == _clean(blueprint.get("role_family_id"))
        and _clean(
            (semantic.get("role_family") or {}).get("role_family_label")
        )
        == _clean(blueprint.get("role_family_label")),
    }
    failed_internal = [name for name, passed in internal_checks.items() if not passed]
    if failed_internal:
        raise Phase9EDecisionError(
            "The approved blueprint source provenance is not reproducible: "
            + ", ".join(failed_internal)
        )

    current_source_link = exact_jd.get("source_application_link") or {}
    current_requirement_ids = sorted(
        _clean(value)
        for value in exact_jd.get("canonical_requirement_ids", []) or []
        if _clean(value)
    )
    source_requirement_ids = sorted(
        _clean(value)
        for value in source.get("canonical_requirement_ids", []) or []
        if _clean(value)
    )
    expected_stable = _phase9c_source_stable_input_fingerprint(
        profile=frozen["resume_profile_snapshot"],
        resume_text=str(frozen["resume_text_snapshot"]),
        exact_jd=exact_jd,
        scoring_version=_clean(evaluation_identity.get("scoring_version")),
        taxonomy_version=_clean(evaluation_identity.get("taxonomy_version")),
    )
    current_checks = {
        "application_id": int(application_id)
        == int(candidate_identity.get("source_application_id", 0) or 0)
        == int(current_source_link.get("application_id", 0) or 0),
        "canonical_jd_id": _clean(exact_jd.get("canonical_jd_id"))
        == _clean(source.get("canonical_jd_id")),
        "library_jd_id": int(exact_jd.get("library_jd_id", 0) or 0)
        == int(source.get("library_jd_id", 0) or 0)
        == int(current_source_link.get("job_description_id", 0) or 0),
        "source_version_id": _clean(exact_jd.get("source_version_id"))
        == _clean(source.get("source_version_id"))
        == _clean(current_source_link.get("source_version_id")),
        "raw_jd_sha256": _clean(exact_jd.get("raw_jd_sha256"))
        == _clean(source.get("raw_jd_sha256")),
        "canonical_requirement_ids": current_requirement_ids
        == source_requirement_ids,
        "canonical_requirement_fingerprint": _clean(
            exact_jd.get("canonical_requirement_fingerprint")
        )
        == _clean(source.get("canonical_requirement_fingerprint")),
        "stable_input_fingerprint": expected_stable
        == _clean(source.get("stable_input_fingerprint")),
    }
    source_identity = {
        "policy_version": PHASE9E_EXACT_SOURCE_REUSE_POLICY_VERSION,
        "application_id": int(application_id),
        "canonical_jd_id": _clean(source.get("canonical_jd_id")),
        "library_jd_id": int(source.get("library_jd_id", 0) or 0),
        "source_version_id": _clean(source.get("source_version_id")),
        "raw_jd_sha256": _clean(source.get("raw_jd_sha256")),
        "canonical_requirement_ids": source_requirement_ids,
        "canonical_requirement_fingerprint": _clean(
            source.get("canonical_requirement_fingerprint")
        ),
        "stable_input_fingerprint": _clean(
            source.get("stable_input_fingerprint")
        ),
        "candidate_id": _clean(candidate_identity.get("candidate_id")),
        "candidate_fingerprint": _clean(
            candidate_identity.get("candidate_fingerprint")
        ),
        "source_verification_fingerprint": _clean(
            candidate_identity.get("source_verification_fingerprint")
        ),
        "source_jd_requirement_summary_fingerprint": _clean(
            candidate_identity.get(
                "source_jd_requirement_summary_fingerprint"
            )
        ),
        "evaluation_id": _clean(evaluation_identity.get("evaluation_id")),
        "evaluation_fingerprint": _clean(
            evaluation_identity.get("evaluation_fingerprint")
        ),
        "phase9b_version": _clean(candidate_identity.get("phase9b_version")),
        "phase9c_version": _clean(evaluation_identity.get("phase9c_version")),
        "phase9c_policy_version": _clean(
            evaluation_identity.get("policy_version")
        ),
        "scoring_version": _clean(evaluation_identity.get("scoring_version")),
        "taxonomy_version": _clean(evaluation_identity.get("taxonomy_version")),
        "complete_resume_snapshot_fingerprint": _clean(
            (semantic.get("resume_snapshot") or {}).get(
                "complete_snapshot_fingerprint"
            )
        ),
    }
    return {
        "matched": all(current_checks.values()),
        "source_identity": source_identity,
        "source_identity_fingerprint": fingerprint_value(source_identity),
        "current_match_gates": current_checks,
        "failed_current_match_gates": [
            name for name, passed in current_checks.items() if not passed
        ],
        "internal_provenance_gates": internal_checks,
    }


def recommend_active_blueprint(
    jd: dict[str, Any],
    active_blueprints: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Classify the JD and recommend only the exact same-family active row."""
    validate_exact_jd_snapshot(jd)
    classification = suggest_role_family(
        {"jd_profile": deepcopy(jd.get("jd_profile") or {})}
    )
    family_id = _clean(classification.get("role_family_id"))
    active = sorted(
        (
            validate_active_blueprint(deepcopy(row))
            for row in active_blueprints
            if _clean(row.get("status")) == "active"
        ),
        key=lambda row: (
            _clean(row.get("role_family_id")),
            _clean(row.get("blueprint_id")),
        ),
    )
    same_family = [
        row for row in active if _clean(row.get("role_family_id")) == family_id
    ]
    if len(same_family) > 1:
        raise Phase9EDecisionError(
            "Multiple active blueprints exist for the classified role family."
        )
    recommended = same_family[0] if same_family else None
    if recommended:
        reasons = [
            "The JD and blueprint share the same canonical role-family ID.",
            "The blueprint is the single active version for that role family.",
        ]
    else:
        reasons = [
            "No active blueprint exists for the JD's canonical role family.",
            "No unrelated blueprint was selected automatically.",
        ]
    return {
        "policy_version": PHASE9E_RECOMMENDATION_POLICY_VERSION,
        "classification": deepcopy(classification),
        "recommendation_confidence": _clean(
            classification.get("confidence")
        )
        or "low",
        "recommended_blueprint": deepcopy(recommended),
        "recommended_blueprint_identity": _blueprint_identity(recommended),
        "reasons": reasons,
        "active_blueprints": active,
    }


def build_blueprint_starting_snapshot(
    blueprint: dict[str, Any],
) -> dict[str, Any]:
    validate_active_blueprint(blueprint)
    phase9d_snapshot = deepcopy(blueprint["blueprint_snapshot"])
    frozen = phase9d_snapshot["frozen_resume_snapshot"]
    result = {
        "source_type": "global_blueprint",
        "source_fidelity": "phase9d_complete_frozen_snapshot",
        "resume_text_is_original_uploaded_text": False,
        "resume_text_representation_method": "phase9d_frozen_resume_text",
        "resume_profile_snapshot": deepcopy(
            frozen["resume_profile_snapshot"]
        ),
        "resume_text_snapshot": str(frozen["resume_text_snapshot"]),
        "source_identity": _blueprint_identity(blueprint),
        "phase9d_blueprint_snapshot": phase9d_snapshot,
    }
    result["starting_snapshot_fingerprint"] = fingerprint_value(result)
    return result


def build_original_resume_starting_snapshot(
    application_report: dict[str, Any],
) -> dict[str, Any]:
    # Freeze only semantic original-résumé inputs. Mutable report
    # bookkeeping such as API usage, costs, chat, and UI notices must not
    # redefine the selected starting source after generation.
    if not isinstance(application_report, dict) or not application_report:
        raise Phase9EDecisionError(
            "The persisted application report is missing."
        )
    profile = application_report.get("resume_profile")
    if not isinstance(profile, dict) or not profile:
        raise Phase9EDecisionError(
            "The persisted application resume profile is missing."
        )
    persisted_raw = application_report.get("raw_resume_text")
    if isinstance(persisted_raw, str) and persisted_raw.strip():
        resume_text = persisted_raw
        fidelity = "persisted_raw_text"
        representation = "persisted_original_raw_text"
        is_original = True
    else:
        resume_text = build_resume_text_from_profile(deepcopy(profile))
        fidelity = "persisted_profile_only"
        representation = "phase8_deterministic_profile_to_text"
        is_original = False
    if not _clean(resume_text):
        raise Phase9EDecisionError(
            "The persisted profile could not produce a scoring representation."
        )

    report_meta = application_report.get("meta") or {}
    analysis_cache = report_meta.get("analysis_cache") or {}
    semantic_source_identity = {
        "policy_version": (
            PHASE9E_ORIGINAL_SOURCE_IDENTITY_POLICY_VERSION
        ),
        "analysis_input_fingerprint": _clean(
            analysis_cache.get("input_fingerprint")
        ),
        "analysis_id": _clean(analysis_cache.get("analysis_id")),
        "persisted_resume_profile_fingerprint": fingerprint_value(profile),
        "persisted_resume_text_sha256": _text_sha256(resume_text),
        "source_fidelity": fidelity,
        "resume_text_representation_method": representation,
    }
    result = {
        "source_type": "original_resume",
        "source_fidelity": fidelity,
        "resume_text_is_original_uploaded_text": is_original,
        "resume_text_representation_method": representation,
        "resume_profile_snapshot": deepcopy(profile),
        "resume_text_snapshot": str(resume_text),
        "source_identity": semantic_source_identity,
    }
    result["starting_snapshot_fingerprint"] = fingerprint_value(result)
    return result

def build_phase9e_keyword_match(
    *,
    requirements: list[dict[str, Any]],
    acronym_map: dict[str, str],
    resume_profile: dict[str, Any],
    raw_resume_text: str,
) -> dict[str, Any]:
    """Prefer one independently sufficient capability-evidence row.

    The shared deterministic matcher supplies the preliminary match label.
    This Phase 9E policy changes only the cited visible row when the current
    citation would be capped to ``none`` and another individual resume row
    satisfies the same recognised capability.  It never joins evidence rows
    and never changes ``match_type`` or ``evidence_type``.
    """
    keyword_match = build_deterministic_keyword_match(
        requirements=deepcopy(requirements),
        acronym_map=deepcopy(acronym_map),
        resume_profile=deepcopy(resume_profile),
        raw_resume_text=str(raw_resume_text),
    )
    evidence_rows = build_resume_evidence_index(
        deepcopy(resume_profile),
        str(raw_resume_text),
    )
    taxonomy = get_default_taxonomy()
    present_rows = [
        row
        for row in keyword_match.get("present", []) or []
        if isinstance(row, dict)
    ]
    audit_rows: list[dict[str, Any]] = []

    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        focus = _clean(
            requirement.get("atomic_focus") or requirement.get("text")
        )
        keyword_row = next(
            (
                row
                for row in present_rows
                if _clean(row.get("keyword")) == focus
            ),
            None,
        )
        if keyword_row is None:
            continue

        original_term = _clean(keyword_row.get("matched_resume_term"))
        current_decision = evaluate_evidence(
            requirement,
            original_term,
            taxonomy,
        )
        capability_id = _clean(current_decision.get("capability_id"))
        current_label = _clean(current_decision.get("label")).lower()
        if not capability_id or _TAXONOMY_LABEL_ORDER.get(current_label, 0) > 0:
            continue

        selected: tuple[dict[str, str], dict[str, Any]] | None = None
        selected_rank = 0
        for evidence_row in evidence_rows:
            decision = evaluate_evidence(
                requirement,
                str(evidence_row.get("text") or ""),
                taxonomy,
            )
            if _clean(decision.get("capability_id")) != capability_id:
                continue
            rank = _TAXONOMY_LABEL_ORDER.get(
                _clean(decision.get("label")).lower(),
                0,
            )
            if rank > selected_rank:
                selected = (evidence_row, decision)
                selected_rank = rank

        if selected is None:
            continue

        evidence_row, selected_decision = selected
        preliminary_match_type = _clean(keyword_row.get("match_type"))
        preliminary_evidence_type = _clean(
            keyword_row.get("evidence_type")
        )
        preliminary_ceiling = preliminary_match_type
        if (
            preliminary_ceiling == "direct"
            and preliminary_evidence_type == "transferable"
        ):
            preliminary_ceiling = "transferable"
        keyword_row["matched_resume_term"] = _clean(
            evidence_row.get("text")
        )
        keyword_row["found_in"] = _clean(evidence_row.get("section"))
        keyword_row["match_reason"] = (
            "Phase 9E selected one visible resume row that independently "
            "satisfies the recognised capability taxonomy; the preliminary "
            "match ceiling was preserved."
        )
        keyword_row["evidence_similarity"] = "1.000"
        keyword_row["phase9e_evidence_selection"] = {
            "policy_version": PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION,
            "status": "capability_supporting_row_selected",
            "capability_id": capability_id,
            "taxonomy_label": _clean(selected_decision.get("label")),
            "original_matched_resume_term": original_term,
            "selected_evidence_id": _clean(
                evidence_row.get("evidence_id")
            ),
            "selected_evidence_source": _clean(
                evidence_row.get("source")
            ),
            "combined_evidence_rows": False,
            "preliminary_match_type": preliminary_match_type,
            "preliminary_evidence_type": preliminary_evidence_type,
            "preliminary_match_ceiling": preliminary_ceiling,
        }
        audit_rows.append(
            {
                "requirement_id": _clean(
                    requirement.get("requirement_id")
                ),
                **deepcopy(keyword_row["phase9e_evidence_selection"]),
            }
        )

    keyword_match["evidence_selection_policy_version"] = (
        PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION
    )
    keyword_match["evidence_selection_audit"] = audit_rows
    return keyword_match


def _apply_phase9e_preliminary_match_ceilings(
    analysis: dict[str, Any],
    keyword_match: dict[str, Any],
) -> dict[str, Any]:
    """Prevent capability-aware evidence from promoting preliminary labels."""
    audits = {
        _clean(row.get("requirement_id")): row
        for row in keyword_match.get("evidence_selection_audit", []) or []
        if isinstance(row, dict) and _clean(row.get("requirement_id"))
    }
    warnings = analysis.setdefault("validation_warnings", [])
    rows = analysis.get("canonical_requirements", []) or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        audit = audits.get(_clean(row.get("requirement_id")))
        if audit is None:
            continue
        ceiling = _clean(audit.get("preliminary_match_ceiling")).lower()
        if ceiling not in _TAXONOMY_LABEL_ORDER:
            continue
        final_label = _clean(row.get("match_label")).lower()
        if (
            _TAXONOMY_LABEL_ORDER.get(final_label, 0)
            > _TAXONOMY_LABEL_ORDER[ceiling]
        ):
            row["match_label"] = ceiling
            row["match_value"] = _MATCH_VALUES[ceiling]
            warnings.append(
                {
                    "requirement_id": _clean(row.get("requirement_id")),
                    "code": "phase9e_preliminary_match_ceiling_applied",
                    "message": (
                        "Phase 9E retained the preliminary match ceiling after "
                        "selecting stronger capability-supporting evidence."
                    ),
                }
            )
        effective_label = _clean(row.get("match_label")).lower()
        strength_ceiling = _EVIDENCE_STRENGTH_CEILING.get(
            effective_label,
            0,
        )
        row["evidence_strength"] = min(
            int(row.get("evidence_strength", 0) or 0),
            strength_ceiling,
            _EVIDENCE_STRENGTH_CEILING[ceiling],
        )

    analysis.update(compute_deterministic_alignment(rows))
    return analysis


def _build_phase9e_starting_analysis(
    *,
    starting_snapshot: dict[str, Any],
    jd: dict[str, Any],
    preferred_requirements: list[str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Score one frozen resume against base and local effective JD scope.

    The raw JD must remain the source of shared canonical requirements.  A
    nonmatching application-local input is therefore scored separately from a
    one-requirement profile, then added to the already-scored Phase 9E result.
    This mirrors the raw-JD precedence boundary used by Application Sessions
    and never writes the supplemental requirement to shared JD storage.
    """
    profile = starting_snapshot.get("resume_profile_snapshot")
    resume_text = starting_snapshot.get("resume_text_snapshot")
    if not isinstance(profile, dict) or not _clean(resume_text):
        raise Phase9EDecisionError("The starting resume snapshot is incomplete.")

    canonical = jd.get("canonicalisation") or {}
    base_requirements = canonical.get("requirements") or jd.get(
        "canonical_requirements"
    )
    acronym_map = canonical.get("acronym_map") or {}
    overrides = normalise_requirement_override_lines(preferred_requirements)
    effective_requirements, local_scope = (
        build_effective_application_local_requirement_scope(
            base_requirements,
            overrides,
        )
    )
    keyword_match = build_phase9e_keyword_match(
        requirements=deepcopy(effective_requirements),
        acronym_map=deepcopy(acronym_map),
        resume_profile=deepcopy(profile),
        raw_resume_text=str(resume_text),
    )
    analysis = build_stable_analysis(
        jd_profile=deepcopy(jd["jd_profile"]),
        keyword_match=deepcopy(keyword_match),
        raw_jd_text=str(jd["raw_text"]),
        raw_resume_text=str(resume_text),
        resume_profile=deepcopy(profile),
        retrieval_mode_override="lexical",
    )
    analysis = _apply_phase9e_preliminary_match_ceilings(
        analysis,
        keyword_match,
    )
    if not overrides:
        return analysis, keyword_match, local_scope

    rows, canonical_matches, matched_rows = (
        apply_preferred_requirement_overrides_to_canonical_rows(
            analysis.get("canonical_requirements") or [],
            overrides,
        )
    )
    canonical_match_keys = {
        requirement_override_key(item)
        for item in canonical_matches
        if requirement_override_key(item)
    }
    supplemental_requirements = [
        item
        for item in overrides
        if requirement_override_key(item) not in canonical_match_keys
    ]
    supplemental_rows: list[dict[str, Any]] = []
    for requirement in supplemental_requirements:
        requirement_key = requirement_override_key(requirement)
        local_requirement_rows = [
            deepcopy(row)
            for row in effective_requirements
            if requirement_override_key(row.get("user_supplied_requirement"))
            == requirement_key
        ]
        if not local_requirement_rows:
            raise Phase9EDecisionError(
                "The application-local preferred requirement is missing from "
                "the effective JD scope."
            )
        supplemental_keyword_match = build_phase9e_keyword_match(
            requirements=deepcopy(local_requirement_rows),
            acronym_map=deepcopy(acronym_map),
            resume_profile=deepcopy(profile),
            raw_resume_text=str(resume_text),
        )
        supplemental_analysis = build_stable_analysis(
            jd_profile={"preferred_skills": [requirement]},
            keyword_match=supplemental_keyword_match,
            raw_jd_text="",
            raw_resume_text=str(resume_text),
            resume_profile=deepcopy(profile),
            retrieval_mode_override="lexical",
        )
        supplemental_analysis = _apply_phase9e_preliminary_match_ceilings(
            supplemental_analysis,
            supplemental_keyword_match,
        )
        supplemental_rows.extend(
            tag_application_local_supplemental_requirement_row(row, requirement)
            for row in supplemental_analysis.get("canonical_requirements", [])
            if isinstance(row, dict)
        )

    covered_keys = {
        requirement_override_key(row.get("user_supplied_requirement"))
        for row in supplemental_rows
        if row.get("application_requirement_scope") == "application_local"
    }
    expected_keys = {
        requirement_override_key(item)
        for item in supplemental_requirements
        if requirement_override_key(item)
    }
    if covered_keys != expected_keys:
        raise Phase9EDecisionError(
            "Application-local preferred requirements could not be scored in "
            "the effective Phase 9E JD scope."
        )

    output = deepcopy(analysis)
    output["canonical_requirements"] = [*rows, *supplemental_rows]
    output.setdefault("canonicalisation_debug", {})[
        "application_local_supplemental_requirements"
    ] = [
        {"text": _clean(item), "scope": "application_local"}
        for item in supplemental_requirements
    ]
    output.update(compute_deterministic_alignment(output["canonical_requirements"]))
    base_fingerprint = _clean(analysis.get("input_fingerprint"))
    output["base_stable_input_fingerprint"] = base_fingerprint
    output["input_fingerprint"] = effective_stable_input_fingerprint(
        base_fingerprint,
        overrides,
    )
    output["jd_user_override_policy_version"] = local_scope["policy_version"]
    local_scope = {
        **local_scope,
        "canonical_preferred_matches": deepcopy(canonical_matches),
        "matched_canonical_requirement_rows": deepcopy(matched_rows),
        "supplemental_preferred_requirements": deepcopy(
            supplemental_requirements
        ),
    }
    return output, keyword_match, local_scope


def evaluate_starting_snapshot(
    starting_snapshot: dict[str, Any],
    jd: dict[str, Any],
    *,
    preferred_requirements: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Evaluate a frozen starting source using the current stable scorer."""
    validate_exact_jd_snapshot(jd)
    overrides = normalise_requirement_override_lines(preferred_requirements)
    analysis, keyword_match, local_scope = _build_phase9e_starting_analysis(
        starting_snapshot=starting_snapshot,
        jd=jd,
        preferred_requirements=overrides,
    )
    result_rows = [
        deepcopy(row)
        for row in analysis.get("canonical_requirements", [])
        if isinstance(row, dict)
    ]
    result_ids = sorted(
        _clean(row.get("requirement_id"))
        for row in result_rows
        if _clean(row.get("requirement_id"))
    )
    expected_rows, _expected_scope = (
        build_effective_application_local_requirement_scope(
            (jd.get("canonicalisation") or {}).get("requirements")
            or jd.get("canonical_requirements")
            or [],
            overrides,
        )
    )
    expected_ids = sorted(
        _clean(row.get("requirement_id"))
        for row in expected_rows
        if _clean(row.get("requirement_id"))
    )
    if result_ids != expected_ids:
        raise Phase9EDecisionError(
            "Stable scoring changed the effective application JD scope."
        )
    important_gaps = [
        {
            "requirement_id": _clean(row.get("requirement_id")),
            "text": _clean(row.get("text")),
            "importance": _clean(row.get("importance")),
        }
        for row in result_rows
        if _clean(row.get("importance")) in IMPORTANT_REQUIREMENTS
        and _clean(row.get("match_label")) == "none"
    ]
    semantic_results = {
        "canonical_requirements": [
            {
                "requirement_id": _clean(row.get("requirement_id")),
                "match_label": _clean(row.get("match_label")),
                "evidence_strength": int(
                    row.get("evidence_strength", 0) or 0
                ),
            }
            for row in result_rows
        ],
        "deterministic_alignment_score": int(
            analysis.get("deterministic_alignment_score", 0) or 0
        ),
        "required_core_coverage_score": int(
            analysis.get("required_core_coverage_score", 0) or 0
        ),
        "preferred_coverage_score": int(
            analysis.get("preferred_coverage_score", 0) or 0
        ),
        "evidence_strength_score": int(
            analysis.get("evidence_strength_score", 0) or 0
        ),
        "important_gaps": important_gaps,
    }
    result = {
        "scoring_version": SCORING_VERSION,
        "capability_taxonomy_version": get_default_taxonomy().version,
        "evidence_selection_policy_version": (
            PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION
        ),
        "evaluation_mode": "full_frozen_starting_snapshot",
        "stable_input_fingerprint": _clean(analysis.get("input_fingerprint")),
        "comparison_result_fingerprint": fingerprint_value(semantic_results),
        "deterministic_alignment_score": semantic_results[
            "deterministic_alignment_score"
        ],
        "alignment_band": _clean(analysis.get("alignment_band")),
        "required_core_coverage_score": semantic_results[
            "required_core_coverage_score"
        ],
        "preferred_coverage_score": semantic_results[
            "preferred_coverage_score"
        ],
        "evidence_strength_score": semantic_results[
            "evidence_strength_score"
        ],
        "required_core_requirement_count": int(
            analysis.get("required_core_requirement_count", 0) or 0
        ),
        "preferred_requirement_count": int(
            analysis.get("preferred_requirement_count", 0) or 0
        ),
        "important_gap_count": len(important_gaps),
        "deal_breaker_gap_count": sum(
            gap["importance"] == "deal_breaker" for gap in important_gaps
        ),
        "important_gaps": important_gaps,
        "canonical_requirement_results": result_rows,
        "stable_analysis_snapshot": deepcopy(analysis),
        "keyword_match_snapshot": deepcopy(keyword_match),
    }
    if overrides:
        result["application_local_jd_user_inputs"] = deepcopy(local_scope)
    return result


def decide_tailoring(
    comparison: dict[str, Any],
    *,
    role_family_mismatch: bool,
    exact_source_approved: bool = False,
    selected_source: str = "global_blueprint",
    original_comparison: dict[str, Any] | None = None,
    original_source_fidelity: str = "",
) -> dict[str, Any]:
    overall = int(comparison.get("deterministic_alignment_score", 0) or 0)
    required = int(comparison.get("required_core_coverage_score", 0) or 0)
    preferred = int(comparison.get("preferred_coverage_score", 0) or 0)
    evidence = int(comparison.get("evidence_strength_score", 0) or 0)
    preferred_count = int(
        comparison.get("preferred_requirement_count", 0) or 0
    )
    important_gaps = int(comparison.get("important_gap_count", 0) or 0)
    deal_breakers = int(comparison.get("deal_breaker_gap_count", 0) or 0)

    preferred_reuse_gate = (
        preferred_count == 0 or preferred >= REUSE_PREFERRED_MINIMUM
    )
    original = original_comparison or {}
    original_automatic_comparison = bool(original) and (
        original_source_fidelity != "persisted_profile_only"
    )
    original_clearly_better = bool(
        original_automatic_comparison
        and int(original.get("deal_breaker_gap_count", 0) or 0) == 0
        and int(original.get("deterministic_alignment_score", 0) or 0)
        >= overall + ORIGINAL_SUPERIORITY_MINIMUM_DELTA
        and int(original.get("required_core_coverage_score", 0) or 0)
        >= required
        and int(original.get("evidence_strength_score", 0) or 0)
        >= evidence
    )

    if exact_source_approved:
        decision = "reuse_approved_source"
        reasons = [
            "The application and exact JD match the blueprint's immutable approved source provenance.",
            "The visible-resume score is diagnostic and does not require tailoring the approved source again.",
        ]
        locked = list(ALL_RESUME_SECTIONS)
        tailorable: list[str] = []
        optional_tailorable: list[str] = []
    elif selected_source == "original_resume":
        decision = "full_regeneration"
        reasons = [
            "The persisted original résumé was explicitly selected as the starting source.",
            "This is a workflow-source choice, not a conclusion forced by the diagnostic score.",
        ]
        locked = ["education", "work_experience"]
        tailorable = ["projects", "skills"]
        optional_tailorable = []
    elif role_family_mismatch:
        decision = "full_regeneration"
        reasons = [
            "The selected blueprint belongs to a different role family.",
            "Restart from the persisted original résumé; Education and Work Experience remain protected.",
        ]
        locked = ["education", "work_experience"]
        tailorable = ["projects", "skills"]
        optional_tailorable = []
    elif deal_breakers:
        decision = "full_regeneration"
        reasons = [
            "One or more deal-breaker requirements are unsupported.",
            "Restart from the persisted original résumé; Education and Work Experience remain protected.",
        ]
        locked = ["education", "work_experience"]
        tailorable = ["projects", "skills"]
        optional_tailorable = []
    elif original_clearly_better:
        decision = "full_regeneration"
        reasons = [
            "The persisted original résumé is clearly stronger under a comparable deterministic evaluation.",
            "Restart from that persisted original; Education and Work Experience remain protected.",
        ]
        locked = ["education", "work_experience"]
        tailorable = ["projects", "skills"]
        optional_tailorable = []
    elif (
        overall >= REUSE_OVERALL_MINIMUM
        and required >= REUSE_REQUIRED_CORE_MINIMUM
        and preferred_reuse_gate
        and evidence >= REUSE_EVIDENCE_MINIMUM
        and important_gaps == 0
        and deal_breakers == 0
    ):
        decision = "reuse_unchanged"
        reasons = [
            "All reuse thresholds passed.",
            "No important or deal-breaker gaps were found.",
        ]
        locked = list(ALL_RESUME_SECTIONS)
        tailorable = []
        optional_tailorable = []
    elif important_gaps == 0:
        decision = "optional_polish"
        reasons = [
            "No important or deal-breaker gaps were found.",
            "The blueprint is usable unchanged; Projects and Skills may be polished only if explicitly requested.",
        ]
        locked = list(ALL_RESUME_SECTIONS)
        tailorable = []
        optional_tailorable = ["projects", "skills"]
    else:
        decision = "targeted_retailor"
        reasons = [
            "The same-family blueprint has important gaps that can be addressed through the supported Projects and Skills path.",
            "Targeted retargeting is recommended, but an acknowledged unchanged-use override remains available.",
        ]
        locked = list(ALL_RESUME_SECTIONS)
        tailorable = []
        optional_tailorable = ["projects", "skills"]

    return {
        "decision_policy_version": PHASE9E_DECISION_POLICY_VERSION,
        "decision": decision,
        "user_facing_label": DECISION_LABELS[decision],
        "reasons": reasons,
        "original_resume_comparison": {
            "automatic_superiority_eligible": original_automatic_comparison,
            "clearly_better": original_clearly_better,
            "minimum_alignment_delta": ORIGINAL_SUPERIORITY_MINIMUM_DELTA,
            "source_fidelity": original_source_fidelity,
            "manual_option_only_reason": (
                "Automatic superiority is disabled because persisted_profile_only text is a deterministic representation, not original uploaded text."
                if original_source_fidelity == "persisted_profile_only"
                else ""
            ),
        },
        "section_lock_scope": {
            "locked_sections": locked,
            "tailorable_sections": tailorable,
            "optional_tailorable_sections": optional_tailorable,
            "projects_locked": "projects" in locked,
            "skills_locked": "skills" in locked,
            "protected_section_reason": (
                "Phase 9E v1 preserves Education and Work Experience because "
                "the current tailoring engine only tailors Projects and Skills."
            ),
        },
    }


def build_phase9e_decision(
    *,
    application_id: int,
    application_report: dict[str, Any],
    exact_jd: dict[str, Any],
    active_blueprints: Iterable[dict[str, Any]],
    selected_source: str,
    selected_blueprint_id: str = "",
    selection_mode: str = "recommended",
    mismatch_acknowledged: bool = False,
) -> dict[str, Any]:
    """Build one complete deterministic Phase 9E decision and binding."""
    if int(application_id) <= 0:
        raise Phase9EDecisionError("application_id must be positive.")
    exact_jd = validate_exact_jd_snapshot(deepcopy(exact_jd))
    application_local_preferred_requirements = (
        _application_local_preferred_requirements(application_report)
    )
    recommendation = recommend_active_blueprint(exact_jd, active_blueprints)
    classification = recommendation["classification"]
    active = recommendation["active_blueprints"]
    selected_source = _clean(selected_source)
    selection_mode = _clean(selection_mode)

    selected_blueprint: dict[str, Any] | None = None
    source_approval: dict[str, Any] | None = None
    original_snapshot: dict[str, Any] | None = None
    if selected_source == "global_blueprint":
        selected_blueprint = next(
            (
                row
                for row in active
                if _clean(row.get("blueprint_id"))
                == _clean(selected_blueprint_id)
            ),
            None,
        )
        if selected_blueprint is None:
            raise Phase9EDecisionError(
                "The explicitly selected blueprint is not active."
            )
        recommended_id = _clean(
            (recommendation.get("recommended_blueprint") or {}).get(
                "blueprint_id"
            )
        )
        if selection_mode == "recommended" and (
            not recommended_id
            or recommended_id != _clean(selected_blueprint_id)
        ):
            raise Phase9EDecisionError(
                "The recommended selection no longer matches the active recommendation."
            )
        role_mismatch = _clean(selected_blueprint.get("role_family_id")) != _clean(
            classification.get("role_family_id")
        )
        if role_mismatch and not mismatch_acknowledged:
            raise Phase9EDecisionError(
                "A different-family blueprint requires explicit acknowledgement."
            )
        diagnostic_starting_snapshot = build_blueprint_starting_snapshot(
            selected_blueprint
        )
        source_approval = match_exact_approved_source(
            application_id=application_id,
            exact_jd=exact_jd,
            blueprint=selected_blueprint,
        )
        original_snapshot = build_original_resume_starting_snapshot(
            application_report
        )
    elif selected_source == "original_resume":
        if selected_blueprint_id:
            raise Phase9EDecisionError(
                "Original-resume selection cannot bind a blueprint ID."
            )
        selection_mode = "original_resume"
        role_mismatch = False
        diagnostic_starting_snapshot = build_original_resume_starting_snapshot(
            application_report
        )
        original_snapshot = diagnostic_starting_snapshot
    else:
        raise Phase9EDecisionError(
            "selected_source must be global_blueprint or original_resume."
        )

    comparison = evaluate_starting_snapshot(
        diagnostic_starting_snapshot,
        exact_jd,
        preferred_requirements=application_local_preferred_requirements,
    )
    exact_source_approved = bool(
        source_approval and source_approval.get("matched")
    )
    original_comparison: dict[str, Any] | None = None
    if selected_source == "global_blueprint" and not exact_source_approved:
        original_comparison = evaluate_starting_snapshot(
            original_snapshot or {},
            exact_jd,
            preferred_requirements=application_local_preferred_requirements,
        )
    outcome = decide_tailoring(
        comparison,
        role_family_mismatch=role_mismatch,
        exact_source_approved=exact_source_approved,
        selected_source=selected_source,
        original_comparison=original_comparison,
        original_source_fidelity=_clean(
            (original_snapshot or {}).get("source_fidelity")
        ),
    )
    starting_snapshot = diagnostic_starting_snapshot
    if outcome["decision"] == "full_regeneration":
        if not isinstance(original_snapshot, dict):
            raise Phase9EDecisionError(
                "Full regeneration requires the persisted original resume snapshot."
            )
        starting_snapshot = original_snapshot
    effective_comparison = comparison
    if (
        outcome["decision"] == "full_regeneration"
        and isinstance(original_comparison, dict)
    ):
        effective_comparison = original_comparison

    semantic_stable_input = comparison["stable_input_fingerprint"]
    if exact_source_approved:
        semantic_stable_input = source_approval["source_identity"][
            "stable_input_fingerprint"
        ]
    jd_identity = {
        "library_jd_id": int(exact_jd["library_jd_id"]),
        "canonical_jd_id": _clean(exact_jd.get("canonical_jd_id")),
        "source_version_id": _clean(exact_jd.get("source_version_id")),
        "raw_jd_sha256": _clean(exact_jd.get("raw_jd_sha256")),
        "canonical_requirement_ids": list(
            exact_jd.get("canonical_requirement_ids") or []
        ),
        "canonical_requirement_fingerprint": _clean(
            exact_jd.get("canonical_requirement_fingerprint")
        ),
        "source_application_link": {
            "application_id": int(
                (exact_jd.get("source_application_link") or {}).get(
                    "application_id", 0
                )
                or 0
            ),
            "job_description_id": int(
                (exact_jd.get("source_application_link") or {}).get(
                    "job_description_id", 0
                )
                or 0
            ),
            "source_version_id": _clean(
                (exact_jd.get("source_application_link") or {}).get(
                    "source_version_id"
                )
            ),
        },
        "stable_input_fingerprint": semantic_stable_input,
    }
    application_local_jd_scope = {}
    if application_local_preferred_requirements:
        application_local_jd_scope = {
            "policy_version": (
                preferred_requirement_override_cache_identity(
                    application_local_preferred_requirements
                )["policy_version"]
            ),
            "override_identity": preferred_requirement_override_cache_identity(
                application_local_preferred_requirements
            ),
            "effective_requirement_fingerprint": _clean(
                comparison.get("stable_input_fingerprint")
            ),
        }
    selected_identity = _blueprint_identity(selected_blueprint)
    semantic_identity = {
        "phase9e_version": PHASE9E_VERSION,
        "identity_policy_version": PHASE9E_IDENTITY_POLICY_VERSION,
        "application_id": int(application_id),
        "current_jd": jd_identity,
        "role_family_classification": {
            "role_family_id": _clean(classification.get("role_family_id")),
            "role_family_label": _clean(classification.get("role_family")),
            "confidence": _clean(classification.get("confidence")),
            "matched_terms": list(classification.get("matched_terms") or []),
            "method": _clean(classification.get("suggestion_method")),
        },
        "recommendation": {
            "policy_version": PHASE9E_RECOMMENDATION_POLICY_VERSION,
            "recommended_blueprint": deepcopy(
                recommendation["recommended_blueprint_identity"]
            ),
        },
        "selection": {
            "selected_source": selected_source,
            "selection_mode": selection_mode,
            "selected_blueprint": selected_identity,
            "role_family_mismatch": role_mismatch,
            "diagnostic_starting_snapshot_fingerprint": (
                diagnostic_starting_snapshot[
                    "starting_snapshot_fingerprint"
                ]
            ),
            "effective_starting_source": _clean(
                starting_snapshot.get("source_type")
            ),
            "starting_snapshot_fingerprint": starting_snapshot[
                "starting_snapshot_fingerprint"
            ],
            "source_evaluation_provisional": (
                _source_is_provisional(selected_blueprint)
                if selected_blueprint
                else None
            ),
        },
        "decision": {
            "policy_version": PHASE9E_DECISION_POLICY_VERSION,
            "recommended_tailoring": outcome["decision"],
            "user_facing_label": outcome["user_facing_label"],
            "section_lock_scope": deepcopy(outcome["section_lock_scope"]),
        },
    }
    if application_local_jd_scope:
        semantic_identity["application_local_jd_scope"] = (
            deepcopy(application_local_jd_scope)
        )
    if exact_source_approved:
        semantic_identity["source_approval"] = {
            "policy_version": PHASE9E_EXACT_SOURCE_REUSE_POLICY_VERSION,
            "source_identity_fingerprint": source_approval[
                "source_identity_fingerprint"
            ],
            "source_identity": deepcopy(source_approval["source_identity"]),
        }
    else:
        semantic_identity["scoring"] = {
            "scoring_version": SCORING_VERSION,
            "capability_taxonomy_version": get_default_taxonomy().version,
            "evidence_selection_policy_version": (
                PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION
            ),
            "retrieval_mode": "lexical",
            "comparison_result_fingerprint": comparison[
                "comparison_result_fingerprint"
            ],
            "original_comparison_result_fingerprint": _clean(
                (
                    (original_comparison or {}).get(
                        "comparison_result_fingerprint"
                    )
                    if outcome["original_resume_comparison"][
                        "automatic_superiority_eligible"
                    ]
                    else ""
                )
            ),
            "original_superiority_eligible": outcome[
                "original_resume_comparison"
            ]["automatic_superiority_eligible"],
        }
    decision_fingerprint = fingerprint_value(semantic_identity)
    decision = {
        "phase9e_version": PHASE9E_VERSION,
        "identity_policy_version": PHASE9E_IDENTITY_POLICY_VERSION,
        "decision_id": decision_fingerprint[:32],
        "decision_fingerprint": decision_fingerprint,
        "application_id": int(application_id),
        "semantic_identity": semantic_identity,
        "selection": {
            "selected_source": selected_source,
            "selection_mode": selection_mode,
            "selected_blueprint": selected_identity,
            "selected_blueprint_display_name": _clean(
                (selected_blueprint or {}).get("display_name")
            ),
            "role_family_mismatch": role_mismatch,
            "mismatch_acknowledged": bool(mismatch_acknowledged),
            "effective_starting_source": _clean(
                starting_snapshot.get("source_type")
            ),
        },
        "recommendation": {
            "confidence": recommendation["recommendation_confidence"],
            "reasons": list(recommendation["reasons"]),
            "recommended_blueprint": deepcopy(
                recommendation["recommended_blueprint_identity"]
            ),
        },
        "role_family_classification": deepcopy(classification),
        "current_jd_snapshot": {
            **deepcopy(exact_jd),
            **(
                {
                    "application_local_jd_user_inputs": deepcopy(
                        comparison.get("application_local_jd_user_inputs")
                        or {}
                    )
                }
                if application_local_preferred_requirements
                else {}
            ),
        },
        "starting_snapshot": deepcopy(starting_snapshot),
        "diagnostic_starting_snapshot": deepcopy(
            diagnostic_starting_snapshot
        ),
        "comparison": comparison,
        "effective_starting_comparison": deepcopy(effective_comparison),
        "diagnostic_visible_scoring": {
            "controls_exact_source_reuse": False,
            "scoring_version": comparison["scoring_version"],
            "capability_taxonomy_version": comparison[
                "capability_taxonomy_version"
            ],
            "evidence_selection_policy_version": comparison[
                "evidence_selection_policy_version"
            ],
            "stable_input_fingerprint": comparison[
                "stable_input_fingerprint"
            ],
            "comparison_result_fingerprint": comparison[
                "comparison_result_fingerprint"
            ],
        },
        "original_resume_comparison": deepcopy(original_comparison),
        "original_resume_comparison_policy": deepcopy(
            outcome["original_resume_comparison"]
        ),
        "source_approval": deepcopy(source_approval),
        "recommended_tailoring": outcome["decision"],
        "recommended_tailoring_label": outcome["user_facing_label"],
        "decision_reasons": list(outcome["reasons"]),
        "section_lock_scope": deepcopy(outcome["section_lock_scope"]),
        "workflow_action_policy": {
            "policy_version": PHASE9E_WORKFLOW_ACTION_POLICY_VERSION,
            "default_action": {
                "reuse_approved_source": "use_blueprint_unchanged",
                "reuse_unchanged": "use_blueprint_unchanged",
                "optional_polish": "use_blueprint_unchanged",
                "targeted_retailor": "awaiting_explicit_choice",
                "full_regeneration": (
                    "regenerate_from_original_resume"
                    if selected_source == "original_resume"
                    else "awaiting_explicit_choice"
                ),
            }[outcome["decision"]],
            "available_actions": {
                "reuse_approved_source": ["use_blueprint_unchanged"],
                "reuse_unchanged": ["use_blueprint_unchanged"],
                "optional_polish": [
                    "use_blueprint_unchanged",
                    "apply_optional_polish",
                ],
                "targeted_retailor": [
                    "apply_targeted_retargeting",
                    "use_blueprint_unchanged_override",
                ],
                "full_regeneration": [
                    "regenerate_from_original_resume"
                ],
            }[outcome["decision"]],
        },
        "mutation_policy": {
            "application_report_mutated": False,
            "phase9d_blueprint_mutated": False,
            "saved_jd_mutated": False,
            "resume_snapshot_mutated": False,
            "model_calls": 0,
            "embedding_calls": 0,
        },
    }
    return decision


def verify_decision_integrity(decision: dict[str, Any]) -> None:
    semantic = decision.get("semantic_identity")
    if not isinstance(semantic, dict):
        raise Phase9EDecisionError("The Phase 9E semantic identity is missing.")
    expected = fingerprint_value(semantic)
    if expected != _clean(decision.get("decision_fingerprint")):
        raise Phase9EDecisionError("The Phase 9E decision fingerprint is invalid.")
    if _clean(decision.get("decision_id")) != expected[:32]:
        raise Phase9EDecisionError("The Phase 9E decision ID is invalid.")
    starting = decision.get("starting_snapshot") or {}
    stored_starting_fingerprint = _clean(
        starting.get("starting_snapshot_fingerprint")
    )
    starting_copy = deepcopy(starting)
    starting_copy.pop("starting_snapshot_fingerprint", None)
    if fingerprint_value(starting_copy) != stored_starting_fingerprint:
        raise Phase9EDecisionError(
            "The Phase 9E frozen starting snapshot fingerprint is invalid."
        )


def build_effective_tailoring_report(
    application_report: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Return a deep-copied report backed by the immutable Phase 9E source."""
    verify_decision_integrity(decision)
    starting = decision["starting_snapshot"]
    exact_jd = decision["current_jd_snapshot"]
    comparison = decision.get("effective_starting_comparison") or decision[
        "comparison"
    ]
    effective = deepcopy(application_report)
    effective["resume_profile"] = deepcopy(
        starting["resume_profile_snapshot"]
    )
    effective["raw_resume_text"] = str(starting["resume_text_snapshot"])
    effective["jd_profile"] = deepcopy(exact_jd["jd_profile"])
    effective["raw_jd_text"] = str(exact_jd["raw_text"])
    effective["stable_analysis"] = deepcopy(
        comparison["stable_analysis_snapshot"]
    )
    effective["keyword_match"] = deepcopy(
        comparison["keyword_match_snapshot"]
    )
    effective.setdefault("meta", {})["phase9e_starting_context"] = {
        "decision_id": decision["decision_id"],
        "decision_fingerprint": decision["decision_fingerprint"],
        "selected_source": decision["selection"]["selected_source"],
        "selected_blueprint": deepcopy(
            decision["selection"]["selected_blueprint"]
        ),
        "starting_snapshot_fingerprint": starting[
            "starting_snapshot_fingerprint"
        ],
        "source_fidelity": starting["source_fidelity"],
    }
    return effective


def resolve_workflow_action(
    decision: dict[str, Any],
    persisted_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve an explicit or safe default action without changing identity."""
    verify_decision_integrity(decision)
    policy = decision.get("workflow_action_policy") or {}
    available = list(policy.get("available_actions") or [])
    default_action = _clean(policy.get("default_action"))
    action_row = persisted_action or {}
    action = _clean(action_row.get("workflow_action")) or default_action
    if action == "awaiting_explicit_choice":
        return {
            "status": "awaiting_explicit_choice",
            "can_generate": False,
            "workflow_action": action,
            "workflow_action_fingerprint": "",
            "section_lock_scope": deepcopy(decision["section_lock_scope"]),
            "reasons": [
                "Choose targeted retargeting or explicitly acknowledge use of the blueprint unchanged."
            ],
        }
    if action not in available:
        raise Phase9EDecisionError(
            "The persisted Phase 9E workflow action is not valid for this decision."
        )
    action_identity = {
        "policy_version": PHASE9E_WORKFLOW_ACTION_POLICY_VERSION,
        "decision_fingerprint": decision["decision_fingerprint"],
        "workflow_action": action,
    }
    locked = list(ALL_RESUME_SECTIONS)
    tailorable: list[str] = []
    if action in {
        "apply_optional_polish",
        "apply_targeted_retargeting",
        "regenerate_from_original_resume",
    }:
        locked = ["education", "work_experience"]
        tailorable = ["projects", "skills"]
    scope = {
        "locked_sections": locked,
        "tailorable_sections": tailorable,
        "projects_locked": "projects" in locked,
        "skills_locked": "skills" in locked,
        "protected_section_reason": (
            "Phase 9E v1 preserves Education and Work Experience because "
            "the current tailoring engine only tailors Projects and Skills."
        ),
    }
    return {
        "status": "ready",
        "can_generate": True,
        "workflow_action": action,
        "workflow_action_fingerprint": fingerprint_value(action_identity),
        "workflow_action_identity": action_identity,
        "explicit_action_event": deepcopy(action_row),
        "section_lock_scope": scope,
        "reasons": [],
    }


def generation_binding_identity(
    decision: dict[str, Any],
    workflow_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verify_decision_integrity(decision)
    action = workflow_action or resolve_workflow_action(decision)
    if not action.get("can_generate"):
        raise Phase9EDecisionError(
            "A current explicit Phase 9E workflow action is required."
        )
    return {
        "phase9e_version": decision["phase9e_version"],
        "decision_id": decision["decision_id"],
        "decision_fingerprint": decision["decision_fingerprint"],
        "selected_source": decision["selection"]["selected_source"],
        "selected_blueprint": deepcopy(
            decision["selection"]["selected_blueprint"]
        ),
        "starting_snapshot_fingerprint": decision["starting_snapshot"][
            "starting_snapshot_fingerprint"
        ],
        "workflow_action": action["workflow_action"],
        "workflow_action_fingerprint": action[
            "workflow_action_fingerprint"
        ],
    }


def materialise_phase9e_starting_sections(
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Adapt frozen profile Projects/Skills to existing display/fitting shapes."""
    verify_decision_integrity(decision)
    profile = decision["starting_snapshot"]["resume_profile_snapshot"]
    projects: list[dict[str, Any]] = []
    for index, project in enumerate(profile.get("projects", []) or [], start=1):
        if not isinstance(project, dict):
            continue
        title = _clean(
            project.get("display_title")
            or project.get("title")
            or f"Project {index}"
        )
        bullets = project.get("draft_bullets") or project.get("bullets") or []
        if isinstance(bullets, str):
            bullets = [bullets]
        projects.append(
            {
                **deepcopy(project),
                "title": title,
                "display_title": title,
                "period": _clean(
                    project.get("period") or project.get("date")
                ),
                "draft_bullets": [
                    _clean(bullet) for bullet in bullets if _clean(bullet)
                ],
                "priority": "Frozen Phase 9E starting snapshot",
                "space_action": "Preserve unchanged",
                "action": "Reuse unchanged",
                "source": decision["selection"]["selected_source"],
                "why_relevant": (
                    "The deterministic Phase 9E decision recommends reusing "
                    "the immutable starting snapshot unchanged."
                ),
            }
        )

    raw_skills = profile.get("skills") or {}
    skill_lines: list[dict[str, Any]] = []
    if isinstance(raw_skills, dict):
        for category, values in raw_skills.items():
            if isinstance(values, str):
                items = [
                    _clean(value) for value in values.split(",") if _clean(value)
                ]
            elif isinstance(values, list):
                items = [_clean(value) for value in values if _clean(value)]
            else:
                items = [_clean(values)] if _clean(values) else []
            if items:
                skill_lines.append(
                    {"category": _clean(category), "items": items}
                )
    elif isinstance(raw_skills, list):
        skill_lines.append(
            {
                "category": "Skills",
                "items": [_clean(value) for value in raw_skills if _clean(value)],
            }
        )

    return {
        "projects": {
            "recommended_projects": projects,
            "projects_to_remove_or_deprioritize": [],
            "candidate_project_ranking": [],
            "unsupported_jd_skills": [],
            "bullet_validation_warnings": [],
            "phase9e_source": "immutable_starting_snapshot",
        },
        "skills": {
            "skill_lines": skill_lines,
            "evidence_supported_additions": [],
            "unsupported_jd_skills": [],
            "phase9e_source": "immutable_starting_snapshot",
        },
    }

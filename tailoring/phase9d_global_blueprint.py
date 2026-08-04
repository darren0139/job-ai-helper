"""Phase 9D immutable global-blueprint approval semantics."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Any

from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.phase9b_blueprint_candidate import PHASE9B_VERSION
from tailoring.phase9c_blueprint_evaluation import (
    PHASE9C_EVIDENCE_LINK_VERSION,
    PHASE9C_POLICY_VERSION,
    PHASE9C_VERSION,
    Phase9CEvaluationError,
    evaluate_blueprint_candidate,
    fingerprint_semantic_identity,
    source_requirement_summary_fingerprint,
    validate_candidate,
)


PHASE9D_VERSION = "phase9d-global-blueprint-v1"
PHASE9D_FINGERPRINT_POLICY_VERSION = (
    "phase9d-global-blueprint-identity-v1"
)
PHASE9D_AUDIT_EVENT_VERSION = (
    "phase9d-global-blueprint-audit-event-v1"
)
PHASE9D_PROVISIONAL_OVERRIDE_VERSION = (
    "phase9d-provisional-override-v1"
)
MINIMUM_OVERRIDE_REASON_CHARACTERS = 20
MINIMUM_OVERRIDE_REASON_WORDS = 3


class Phase9DApprovalError(ValueError):
    """Raised when a persisted evaluation cannot be approved safely."""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


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


def _text_sha256(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def evaluation_policy_status(evaluation: dict[str, Any]) -> dict[str, Any]:
    """Return the lightweight current-policy status used by the UI."""
    semantic = evaluation.get("semantic_identity") or {}
    policy = semantic.get("policy") or {}
    scope = semantic.get("selected_jd_scope") or []
    reasons: list[str] = []
    if _clean(evaluation.get("phase9c_version")) != PHASE9C_VERSION:
        reasons.append("historical Phase 9C format")
    if _clean(semantic.get("phase9c_version")) != PHASE9C_VERSION:
        reasons.append("historical semantic Phase 9C format")
    if _clean(policy.get("policy_version")) != PHASE9C_POLICY_VERSION:
        reasons.append("historical Phase 9C fingerprint policy")
    if _clean(policy.get("evidence_link_version")) != (
        PHASE9C_EVIDENCE_LINK_VERSION
    ):
        reasons.append("historical Phase 9C evidence-link policy")
    if not isinstance(scope, list) or not scope:
        reasons.append("missing selected JD scope")
    elif any(
        not isinstance(row, dict)
        or not _clean(row.get("stable_input_fingerprint"))
        for row in scope
    ):
        reasons.append("selected scope lacks stable-input provenance")
    return {
        "approvable_policy": not reasons,
        "historical": any("historical" in reason for reason in reasons),
        "reasons": reasons,
    }


def _candidate_semantic_snapshot(candidate: dict[str, Any]) -> dict[str, Any]:
    excluded = {
        "candidate_name",
        "notes",
        "candidate_metadata",
        "created_at",
        "updated_at",
        "cache_status",
        "status",
    }
    return {
        key: deepcopy(value)
        for key, value in candidate.items()
        if key not in excluded
    }


def _validate_override(
    *,
    provisional: bool,
    override: dict[str, Any] | None,
    actor_label: str,
    evaluation: dict[str, Any],
    accepted_at: str,
) -> dict[str, Any]:
    aggregate = evaluation.get("aggregate_result") or {}
    policy = (evaluation.get("semantic_identity") or {}).get("policy") or {}
    supplied = override or {}
    if provisional:
        reason = _clean(supplied.get("reason"))
        words = [word for word in reason.split() if word]
        if supplied.get("accepted") is not True:
            raise Phase9DApprovalError(
                "A provisional evaluation requires an explicit acknowledgement."
            )
        if (
            len(reason) < MINIMUM_OVERRIDE_REASON_CHARACTERS
            or len(words) < MINIMUM_OVERRIDE_REASON_WORDS
        ):
            raise Phase9DApprovalError(
                "A provisional override requires a substantive reason of at "
                f"least {MINIMUM_OVERRIDE_REASON_CHARACTERS} characters and "
                f"{MINIMUM_OVERRIDE_REASON_WORDS} words."
            )
        acknowledgement_code = "provisional_scope_understood"
    else:
        reason = ""
        acknowledgement_code = "not_required"

    return {
        "override_schema_version": PHASE9D_PROVISIONAL_OVERRIDE_VERSION,
        "required": bool(provisional),
        "accepted": bool(provisional),
        "reason": reason,
        "acknowledgement_code": acknowledgement_code,
        "actor_label": _clean(actor_label) or "Local user",
        "actor_source": "local_streamlit_session",
        "evaluation_id": _clean(evaluation.get("evaluation_id")),
        "evaluation_fingerprint": _clean(
            evaluation.get("evaluation_fingerprint")
        ),
        "evaluated_jd_count": int(
            aggregate.get("evaluated_jd_count", 0) or 0
        ),
        "minimum_non_provisional_jds": int(
            policy.get("minimum_non_provisional_jds", 0) or 0
        ),
        "accepted_at": accepted_at,
    }


def _normalise_replay_result(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    result.pop("evaluation_id", None)
    result.pop("created_at", None)
    for row in result.get("per_jd_results", []) or []:
        if isinstance(row, dict):
            row.pop("title", None)
            row.pop("company", None)
    return result


def _validate_persisted_evaluation(
    *,
    candidate: dict[str, Any],
    evaluation: dict[str, Any],
    selected_jds: list[dict[str, Any]],
    all_saved_jds: list[dict[str, Any]],
) -> dict[str, Any]:
    policy_status = evaluation_policy_status(evaluation)
    if not policy_status["approvable_policy"]:
        raise Phase9DApprovalError(
            "The persisted evaluation is inspection-only: "
            + "; ".join(policy_status["reasons"])
        )

    semantic = evaluation.get("semantic_identity")
    if not isinstance(semantic, dict):
        raise Phase9DApprovalError(
            "The persisted Phase 9C semantic identity is missing."
        )
    evaluation_fingerprint = _clean(
        evaluation.get("evaluation_fingerprint")
    )
    if fingerprint_semantic_identity(semantic) != evaluation_fingerprint:
        raise Phase9DApprovalError(
            "The persisted Phase 9C fingerprint cannot be reproduced."
        )

    validated_candidate = validate_candidate(candidate)
    candidate_identity = semantic.get("candidate") or {}
    comparisons = {
        "candidate_id": _clean(candidate.get("candidate_id")),
        "candidate_fingerprint": _clean(candidate.get("candidate_fingerprint")),
        "phase9b_version": PHASE9B_VERSION,
        "role_family_id": validated_candidate["role_family_id"],
        "role_family": _clean(candidate.get("role_family")),
        "resume_profile_snapshot_fingerprint": fingerprint_value(
            candidate.get("resume_profile_snapshot")
        ),
        "resume_text_snapshot_sha256": _text_sha256(
            candidate.get("resume_text_snapshot")
        ),
        "source_verification_fingerprint": _clean(
            candidate.get("source_verification_fingerprint")
        ),
        "source_jd_requirement_summary_fingerprint": (
            source_requirement_summary_fingerprint(candidate)
        ),
        "source_application_id": int(candidate.get("source_application_id")),
        "scoring_version": SCORING_VERSION,
        "capability_taxonomy_version": get_default_taxonomy().version,
    }
    mismatches = [
        field
        for field, expected in comparisons.items()
        if candidate_identity.get(field) != expected
    ]
    if mismatches:
        raise Phase9DApprovalError(
            "The persisted candidate no longer matches the Phase 9C identity: "
            + ", ".join(mismatches)
        )

    scope = semantic.get("selected_jd_scope") or []
    requested_ids = [row.get("library_jd_id") for row in scope]
    if any(value is None for value in requested_ids):
        raise Phase9DApprovalError(
            "Every Phase 9C scope row must reference a current saved JD."
        )
    if len(requested_ids) != len(set(requested_ids)):
        raise Phase9DApprovalError("The persisted Phase 9C scope is ambiguous.")
    selected_by_id = {int(row["id"]): row for row in selected_jds}
    if set(selected_by_id) != {int(value) for value in requested_ids}:
        raise Phase9DApprovalError(
            "One or more selected JDs are missing or historical-only."
        )
    ordered_selected = [selected_by_id[int(value)] for value in requested_ids]
    allowed_uncertain = [
        _clean(row.get("jd_key"))
        for row in scope
        if row.get("family_match_status") == "uncertain"
        and row.get("selection_decision") == "evaluated"
    ]
    pass_threshold = int(
        (semantic.get("policy") or {}).get("pass_threshold", 0) or 0
    )
    replay = evaluate_blueprint_candidate(
        candidate=deepcopy(candidate),
        selected_jds=deepcopy(ordered_selected),
        saved_jds_for_source_resolution=deepcopy(all_saved_jds),
        explicitly_allowed_uncertain=allowed_uncertain,
        pass_threshold=pass_threshold,
    )
    if replay["evaluation_fingerprint"] != evaluation_fingerprint:
        raise Phase9DApprovalError(
            "Current persisted inputs do not reproduce the Phase 9C fingerprint."
        )
    if _normalise_replay_result(replay) != _normalise_replay_result(evaluation):
        raise Phase9DApprovalError(
            "Current persisted inputs do not reproduce the Phase 9C results."
        )
    source_rows = [
        row
        for row in evaluation.get("per_jd_results", []) or []
        if row.get("is_source_jd") is True
    ]
    if len(source_rows) != 1 or not (
        source_rows[0].get("source_jd_parity") or {}
    ).get("accepted"):
        raise Phase9DApprovalError(
            "The persisted evaluation lacks accepted source-JD parity."
        )
    return {
        "phase9c_reproduced": True,
        "source_jd_parity_accepted": True,
        "candidate_snapshot_hashes_match": True,
        "selected_scope_current": True,
        "historical_jd_fallback_used": False,
        "model_calls": 0,
        "embedding_calls": 0,
    }


def prepare_global_blueprint_approval(
    *,
    candidate: dict[str, Any],
    evaluation: dict[str, Any],
    selected_jds: list[dict[str, Any]],
    all_saved_jds: list[dict[str, Any]],
    provisional_override: dict[str, Any] | None = None,
    actor_label: str = "Local user",
    accepted_at: str | None = None,
) -> dict[str, Any]:
    """Validate and copy persisted Phase 9B/9C records without mutation."""
    candidate_before = canonical_json(candidate)
    evaluation_before = canonical_json(evaluation)
    selected_before = canonical_json(selected_jds)
    all_jds_before = canonical_json(all_saved_jds)
    approval_time = accepted_at or datetime.now().isoformat(timespec="seconds")

    try:
        validation = _validate_persisted_evaluation(
            candidate=candidate,
            evaluation=evaluation,
            selected_jds=selected_jds,
            all_saved_jds=all_saved_jds,
        )
    except Phase9CEvaluationError as exc:
        raise Phase9DApprovalError(str(exc)) from exc
    aggregate = evaluation.get("aggregate_result") or {}
    override = _validate_override(
        provisional=aggregate.get("provisional") is True,
        override=provisional_override,
        actor_label=actor_label,
        evaluation=evaluation,
        accepted_at=approval_time,
    )

    semantic = evaluation["semantic_identity"]
    candidate_identity = semantic["candidate"]
    policy = semantic["policy"]
    role_family_id = _clean(candidate_identity.get("role_family_id"))
    canonical_role_family_label = _clean(candidate_identity.get("role_family"))
    candidate_semantic_snapshot = _candidate_semantic_snapshot(candidate)
    frozen_resume_snapshot = {
        "resume_profile_snapshot": deepcopy(
            candidate["resume_profile_snapshot"]
        ),
        "resume_text_snapshot": str(candidate["resume_text_snapshot"]),
    }
    stable_provenance = deepcopy(semantic["selected_jd_scope"])
    identity = {
        "phase9d_version": PHASE9D_VERSION,
        "fingerprint_policy_version": PHASE9D_FINGERPRINT_POLICY_VERSION,
        "role_family": {
            "role_family_id": role_family_id,
            "role_family_label": canonical_role_family_label,
        },
        "candidate": {
            "candidate_id": _clean(candidate_identity.get("candidate_id")),
            "candidate_fingerprint": _clean(
                candidate_identity.get("candidate_fingerprint")
            ),
            "phase9b_version": _clean(candidate_identity.get("phase9b_version")),
            "source_application_id": candidate_identity.get(
                "source_application_id"
            ),
            "source_generation_id": _clean(
                candidate.get("source_generation_id")
            ),
            "source_verification_fingerprint": _clean(
                candidate_identity.get("source_verification_fingerprint")
            ),
            "source_jd_requirement_summary_fingerprint": _clean(
                candidate_identity.get(
                    "source_jd_requirement_summary_fingerprint"
                )
            ),
            "semantic_snapshot_fingerprint": fingerprint_value(
                candidate_semantic_snapshot
            ),
        },
        "evaluation": {
            "evaluation_id": _clean(evaluation.get("evaluation_id")),
            "evaluation_fingerprint": _clean(
                evaluation.get("evaluation_fingerprint")
            ),
            "phase9c_version": _clean(evaluation.get("phase9c_version")),
            "policy_version": _clean(policy.get("policy_version")),
            "evidence_link_version": _clean(
                policy.get("evidence_link_version")
            ),
            "scoring_version": _clean(
                candidate_identity.get("scoring_version")
            ),
            "taxonomy_version": _clean(
                candidate_identity.get("capability_taxonomy_version")
            ),
            "semantic_identity_fingerprint": fingerprint_semantic_identity(
                semantic
            ),
        },
        "resume_snapshot": {
            "complete_snapshot_fingerprint": fingerprint_value(
                frozen_resume_snapshot
            ),
            "resume_profile_snapshot_fingerprint": _clean(
                candidate_identity.get("resume_profile_snapshot_fingerprint")
            ),
            "resume_text_snapshot_sha256": _clean(
                candidate_identity.get("resume_text_snapshot_sha256")
            ),
        },
        "stable_input_provenance": stable_provenance,
    }
    blueprint_fingerprint = fingerprint_value(identity)
    blueprint_id = blueprint_fingerprint[:32]
    snapshot = {
        "phase9d_version": PHASE9D_VERSION,
        "fingerprint_policy_version": PHASE9D_FINGERPRINT_POLICY_VERSION,
        "blueprint_id": blueprint_id,
        "blueprint_fingerprint": blueprint_fingerprint,
        "role_family_id": role_family_id,
        "role_family_label": canonical_role_family_label,
        "semantic_identity": deepcopy(identity),
        "frozen_resume_snapshot": frozen_resume_snapshot,
        "phase9b_candidate_semantic_snapshot": candidate_semantic_snapshot,
        "phase9c_evaluation_snapshot": deepcopy(evaluation),
        "phase9c_semantic_identity": deepcopy(semantic),
        "provenance": {
            "candidate_provenance": deepcopy(candidate.get("provenance") or {}),
            "source_job": deepcopy(candidate.get("source_job") or {}),
            "source_verification_fingerprint": _clean(
                candidate.get("source_verification_fingerprint")
            ),
            "source_jd_requirement_summary_fingerprint": _clean(
                candidate_identity.get(
                    "source_jd_requirement_summary_fingerprint"
                )
            ),
            "stable_input_provenance": stable_provenance,
        },
    }

    if candidate_before != canonical_json(candidate):
        raise AssertionError("Phase 9D mutated the Phase 9B candidate.")
    if evaluation_before != canonical_json(evaluation):
        raise AssertionError("Phase 9D mutated the Phase 9C evaluation.")
    if selected_before != canonical_json(selected_jds):
        raise AssertionError("Phase 9D mutated selected JDs.")
    if all_jds_before != canonical_json(all_saved_jds):
        raise AssertionError("Phase 9D mutated the JD library inputs.")
    return {
        "blueprint_id": blueprint_id,
        "blueprint_fingerprint": blueprint_fingerprint,
        "role_family_id": role_family_id,
        "role_family_label": canonical_role_family_label,
        "semantic_identity": identity,
        "blueprint_snapshot": snapshot,
        "provisional_override": override,
        "validation": validation,
        "approved_at": approval_time,
    }

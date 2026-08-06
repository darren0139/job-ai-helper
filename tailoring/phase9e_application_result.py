"""Immutable application-output identities for unchanged Phase 9E reuse."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from tailoring.phase9e_blueprint_selection import (
    fingerprint_value,
    verify_decision_integrity,
)


APPLICATION_RESULT_FORMAT_VERSION = "phase9e-application-result-v1"
APPLICATION_RESULT_IDENTITY_POLICY_VERSION = (
    "phase9e-application-result-identity-v1"
)
APPLICATION_RESULT_VERIFICATION_VERSION = (
    "phase9e-unchanged-application-verification-v1"
)

MODE_APPROVED_SNAPSHOT_REUSE = "phase9e_approved_snapshot_reuse"
MODE_UNCHANGED_SNAPSHOT_REUSE = "phase9e_unchanged_snapshot_reuse"

STATUS_REUSED_APPROVED = "reused_approved"
STATUS_REUSED_UNCHANGED_PENDING = (
    "reused_unchanged_pending_application_verification"
)

UNCHANGED_WORKFLOW_ACTIONS = {
    "use_blueprint_unchanged",
    "use_blueprint_unchanged_override",
}


class Phase9EApplicationResultError(ValueError):
    """Raised when immutable application-result provenance fails closed."""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


def _without_artifact_paths(value: Any) -> Any:
    """Remove environment-specific paths from inherited semantic identity."""
    if isinstance(value, dict):
        return {
            str(key): _without_artifact_paths(item)
            for key, item in value.items()
            if str(key) not in {"docx_path", "pdf_path"}
            and not str(key).endswith("_path")
        }
    if isinstance(value, list):
        return [_without_artifact_paths(item) for item in value]
    return value


def frozen_content_identity(starting_snapshot: dict[str, Any]) -> dict[str, Any]:
    profile = starting_snapshot.get("resume_profile_snapshot")
    text = starting_snapshot.get("resume_text_snapshot")
    if not isinstance(profile, dict) or not profile:
        raise Phase9EApplicationResultError(
            "The immutable Phase 9D resume profile snapshot is missing."
        )
    if not isinstance(text, str) or not _clean(text):
        raise Phase9EApplicationResultError(
            "The immutable Phase 9D resume text snapshot is missing."
        )
    return {
        "resume_profile_fingerprint": fingerprint_value(profile),
        "resume_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "frozen_content_fingerprint": fingerprint_value(
            {
                "resume_profile_snapshot": profile,
                "resume_text_snapshot": text,
            }
        ),
    }


def source_generation_identity(
    generation: dict[str, Any],
    *,
    effective_sections: dict[str, Any],
) -> dict[str, Any]:
    fit_result = generation.get("fit_result")
    if not isinstance(fit_result, dict) or fit_result.get("fit_one_page") is not True:
        raise Phase9EApplicationResultError(
            "The inherited source generation does not contain a one-page fit."
        )
    generation_id = _clean(generation.get("generation_id"))
    if not generation_id:
        raise Phase9EApplicationResultError(
            "The inherited source generation identity is missing."
        )
    semantic_fit = _without_artifact_paths(deepcopy(fit_result))
    identity = {
        "source_application_id": int(generation.get("application_id", 0) or 0),
        "source_generation_id": generation_id,
        "effective_projects": deepcopy(effective_sections.get("projects")),
        "effective_skills": deepcopy(effective_sections.get("skills")),
        "fit_result": semantic_fit,
    }
    return {
        **identity,
        "source_generation_fingerprint": fingerprint_value(identity),
        "inherited_fit_fingerprint": fingerprint_value(semantic_fit),
    }


def result_mode_and_status(
    decision: dict[str, Any],
    workflow_action: str,
) -> tuple[str, str]:
    verify_decision_integrity(decision)
    action = _clean(workflow_action)
    if action not in UNCHANGED_WORKFLOW_ACTIONS:
        raise Phase9EApplicationResultError(
            "Only an explicitly persisted unchanged-use action can create an "
            "immutable application result."
        )
    if _clean((decision.get("selection") or {}).get("selected_source")) != (
        "global_blueprint"
    ):
        raise Phase9EApplicationResultError(
            "Immutable blueprint reuse requires an explicitly selected global blueprint."
        )
    outcome = _clean(decision.get("recommended_tailoring"))
    if outcome == "reuse_approved_source":
        if action != "use_blueprint_unchanged":
            raise Phase9EApplicationResultError(
                "Exact approved-source reuse requires use_blueprint_unchanged."
            )
        return MODE_APPROVED_SNAPSHOT_REUSE, STATUS_REUSED_APPROVED
    if outcome not in {
        "reuse_unchanged",
        "optional_polish",
        "targeted_retailor",
    }:
        raise Phase9EApplicationResultError(
            "This Phase 9E decision does not permit unchanged blueprint reuse."
        )
    return MODE_UNCHANGED_SNAPSHOT_REUSE, STATUS_REUSED_UNCHANGED_PENDING


def build_application_result_identity(
    *,
    application_id: int,
    decision: dict[str, Any],
    workflow_action: dict[str, Any],
    source_generation: dict[str, Any],
    source_verification: dict[str, Any],
    artifact_identity: dict[str, Any],
) -> dict[str, Any]:
    verify_decision_integrity(decision)
    action = _clean(workflow_action.get("workflow_action"))
    action_fingerprint = _clean(
        workflow_action.get("workflow_action_fingerprint")
    )
    if not action_fingerprint:
        raise Phase9EApplicationResultError(
            "A persisted Phase 9E workflow-action fingerprint is required."
        )
    mode, initial_status = result_mode_and_status(decision, action)
    starting = decision.get("starting_snapshot") or {}
    frozen_identity = frozen_content_identity(starting)
    verification_fingerprint = _clean(
        source_verification.get("verification_fingerprint")
    )
    if not verification_fingerprint:
        raise Phase9EApplicationResultError(
            "The inherited Phase 8 verification fingerprint is missing."
        )
    selection = decision.get("selection") or {}
    blueprint = selection.get("selected_blueprint") or {}
    semantic = decision.get("semantic_identity") or {}
    scoring = semantic.get("scoring") or {}
    current_jd = semantic.get("current_jd") or {}
    return {
        "format_version": APPLICATION_RESULT_FORMAT_VERSION,
        "identity_policy_version": APPLICATION_RESULT_IDENTITY_POLICY_VERSION,
        "application_id": int(application_id),
        "generation_mode": mode,
        "initial_status": initial_status,
        "content_changed": False,
        "editable": False,
        "phase9e": {
            "decision_id": _clean(decision.get("decision_id")),
            "decision_fingerprint": _clean(decision.get("decision_fingerprint")),
            "workflow_action": action,
            "workflow_action_fingerprint": action_fingerprint,
            "decision_policy_version": _clean(
                (semantic.get("decision") or {}).get("policy_version")
            ),
        },
        "current_jd": deepcopy(current_jd),
        "scoring": {
            "scoring_version": _clean(scoring.get("scoring_version")),
            "taxonomy_version": _clean(scoring.get("taxonomy_version")),
        },
        "blueprint": {
            "blueprint_id": _clean(blueprint.get("blueprint_id")),
            "blueprint_fingerprint": _clean(
                blueprint.get("blueprint_fingerprint")
            ),
            "version_number": int(blueprint.get("version_number", 0) or 0),
            "role_family_id": _clean(blueprint.get("role_family_id")),
            "role_family_label": _clean(blueprint.get("role_family_label")),
        },
        "starting_snapshot_fingerprint": _clean(
            starting.get("starting_snapshot_fingerprint")
        ),
        "frozen_content": frozen_identity,
        "source_generation": {
            "source_application_id": source_generation["source_application_id"],
            "source_generation_id": source_generation["source_generation_id"],
            "source_generation_fingerprint": source_generation[
                "source_generation_fingerprint"
            ],
        },
        "inherited_fit": {
            "fit_fingerprint": source_generation["inherited_fit_fingerprint"],
            "fit_one_page": True,
            "page_count": (source_generation.get("fit_result") or {}).get(
                "page_count"
            ),
        },
        "inherited_phase8": {
            "verification_id": _clean(source_verification.get("verification_id")),
            "verification_fingerprint": verification_fingerprint,
            "phase8_version": _clean(source_verification.get("phase8_version")),
        },
        "artifact": deepcopy(artifact_identity),
    }


def prepare_application_result(
    *,
    identity: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    fingerprint = fingerprint_value(identity)
    return {
        "application_result_id": fingerprint[:32],
        "result_fingerprint": fingerprint,
        "format_version": APPLICATION_RESULT_FORMAT_VERSION,
        "identity_policy_version": APPLICATION_RESULT_IDENTITY_POLICY_VERSION,
        "generation_mode": identity["generation_mode"],
        "initial_status": identity["initial_status"],
        "content_changed": False,
        "editable": False,
        "semantic_identity": deepcopy(identity),
        "result_snapshot": deepcopy(snapshot),
    }


def verify_application_result_integrity(result: dict[str, Any]) -> None:
    identity = result.get("semantic_identity")
    if not isinstance(identity, dict):
        raise Phase9EApplicationResultError(
            "The application-result semantic identity is missing."
        )
    expected = fingerprint_value(identity)
    if expected != _clean(result.get("result_fingerprint")):
        raise Phase9EApplicationResultError(
            "The application-result fingerprint is invalid."
        )
    if expected[:32] != _clean(result.get("application_result_id")):
        raise Phase9EApplicationResultError(
            "The application-result ID is invalid."
        )
    if result.get("content_changed") is not False or result.get("editable") is not False:
        raise Phase9EApplicationResultError(
            "An immutable unchanged result cannot be editable or content-changed."
        )


def build_application_result_verification(
    *,
    result: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    verify_application_result_integrity(result)
    verify_decision_integrity(decision)
    if result.get("initial_status") != STATUS_REUSED_UNCHANGED_PENDING:
        raise Phase9EApplicationResultError(
            "Only a different-JD unchanged result requires application verification."
        )
    identity = result["semantic_identity"]
    if _clean(decision.get("decision_fingerprint")) != _clean(
        (identity.get("phase9e") or {}).get("decision_fingerprint")
    ):
        raise Phase9EApplicationResultError(
            "The current Phase 9E decision no longer matches this application result."
        )
    starting = decision.get("starting_snapshot") or {}
    current_content = frozen_content_identity(starting)
    if current_content != identity.get("frozen_content"):
        raise Phase9EApplicationResultError(
            "The current immutable blueprint content no longer matches the result."
        )
    comparison = decision.get("comparison") or {}
    verification_identity = {
        "verification_version": APPLICATION_RESULT_VERIFICATION_VERSION,
        "application_result_id": result["application_result_id"],
        "result_fingerprint": result["result_fingerprint"],
        "decision_fingerprint": decision["decision_fingerprint"],
        "current_jd": deepcopy(
            (decision.get("semantic_identity") or {}).get("current_jd") or {}
        ),
        "comparison_result_fingerprint": _clean(
            comparison.get("comparison_result_fingerprint")
        ),
        "stable_input_fingerprint": _clean(
            comparison.get("stable_input_fingerprint")
        ),
        "frozen_content_fingerprint": current_content[
            "frozen_content_fingerprint"
        ],
        "content_relation": "identical_to_immutable_blueprint",
    }
    fingerprint = fingerprint_value(verification_identity)
    return {
        "verification_id": fingerprint[:32],
        "verification_fingerprint": fingerprint,
        "verification_version": APPLICATION_RESULT_VERIFICATION_VERSION,
        "semantic_identity": verification_identity,
        "status": "verified_pending_user_acceptance",
        "comparison": deepcopy(comparison),
        "content_changed": False,
        "model_calls": 0,
        "embedding_calls": 0,
    }

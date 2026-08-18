"""Pure Phase 9F-E Reuse execution and immutable-result contracts.

The module deliberately has no persistence, model, embedding, Chroma,
generation, fitting, or rendering dependencies.  It validates one frozen
Phase 9F-D intent and builds deterministic identities consumed by the
persistence/orchestration manager.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from tailoring.phase9e_application_result import frozen_content_identity
from tailoring.phase9e_blueprint_selection import (
    fingerprint_value,
    verify_decision_integrity,
)
from tailoring.phase9f_application_confirmation import (
    PHASE9E_PHASE9F_D_EXACT_BINDING_VERSION,
    PHASE9F_D_VERSION,
)


PHASE9F_E_VERSION = "phase9f-reuse-execution-v1"
PHASE9F_E_IDENTITY_POLICY_VERSION = "phase9f-reuse-execution-identity-v1"
PHASE9F_E_EVENT_VERSION = "phase9f-reuse-execution-event-v1"
PHASE9F_E_RESULT_FORMAT_VERSION = "phase9f-reuse-application-result-v1"
PHASE9F_E_RESULT_IDENTITY_POLICY_VERSION = (
    "phase9f-reuse-application-result-identity-v1"
)
PHASE9F_E_PHASE8_ADAPTER_VERSION = "phase9f-reuse-phase8-adapter-v1"
PHASE9F_E_PHASE8_BINDING_VERSION = "phase9f-reuse-phase8-binding-v1"

PHASE9F_E_GENERATION_MODE = "phase9f_reuse_unchanged"
PHASE9F_E_RESULT_STATUS = "reused_unchanged_pending_phase8"
PHASE9F_E_WORKFLOW_ACTION = "begin_phase9f_reuse"

EXECUTION_STATUSES = {
    "not_started",
    "preparing",
    "running",
    "completed",
    "failed",
}
EXECUTION_STAGES = {
    "not_started",
    "source_preparation",
    "application_result",
    "phase8",
    "completed",
}


class Phase9FEExecutionError(ValueError):
    """A fail-closed Phase 9F-E identity or execution-scope error."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        stage: str = "source_preparation",
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.stage = str(stage)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def zero_cost_diagnostics() -> dict[str, int]:
    return {
        "analysis_model_call_count": 0,
        "chatbot_model_call_count": 0,
        "embedding_call_count": 0,
        "chroma_read_count": 0,
        "chroma_write_count": 0,
        "resume_generation_call_count": 0,
        "content_rewrite_call_count": 0,
        "content_changing_fit_call_count": 0,
    }


def exact_jd_identity(exact_jd: dict[str, Any]) -> dict[str, Any]:
    requirement_ids = [
        _clean(value)
        for value in exact_jd.get("canonical_requirement_ids", []) or []
        if _clean(value)
    ]
    identity = {
        "library_jd_id": int(exact_jd.get("library_jd_id") or 0),
        "canonical_jd_id": _clean(exact_jd.get("canonical_jd_id")),
        "source_version_id": _clean(exact_jd.get("source_version_id")),
        "raw_jd_sha256": _clean(exact_jd.get("raw_jd_sha256")),
        "canonical_requirement_ids": requirement_ids,
        "canonical_requirement_fingerprint": _clean(
            exact_jd.get("canonical_requirement_fingerprint")
        ),
        "source_application_link": deepcopy(
            exact_jd.get("source_application_link") or {}
        ),
    }
    required = (
        identity["canonical_jd_id"],
        identity["source_version_id"],
        identity["raw_jd_sha256"],
        identity["canonical_requirement_fingerprint"],
    )
    if not all(required) or not requirement_ids:
        raise Phase9FEExecutionError(
            "The exact linked JD identity is incomplete.",
            code="exact_jd_identity_incomplete",
        )
    identity["jd_identity_fingerprint"] = fingerprint_value(identity)
    return identity


def _stored_jd_identity(decision: dict[str, Any]) -> dict[str, Any]:
    stored = deepcopy(
        (decision.get("semantic_identity") or {}).get("current_jd") or {}
    )
    stored.pop("stable_input_fingerprint", None)
    stored["source_application_link"] = deepcopy(
        stored.get("source_application_link") or {}
    )
    stored["canonical_requirement_ids"] = list(
        stored.get("canonical_requirement_ids") or []
    )
    return stored


def _source_identity(decision: dict[str, Any]) -> dict[str, Any]:
    starting = decision.get("starting_snapshot") or {}
    source = deepcopy(starting.get("source_identity") or {})
    source_type = _clean(starting.get("source_type"))
    if source_type not in {"global_blueprint", "base_resume"}:
        raise Phase9FEExecutionError(
            "Phase 9F-E Reuse supports only an exact Global Blueprint or Base Resume.",
            code="reuse_source_type_unsupported",
        )
    required = {
        "source_type": source_type,
        "source_id": _clean(source.get("source_id")),
        "source_version": int(source.get("source_version") or 0),
        "source_fingerprint": _clean(source.get("source_fingerprint")),
        "source_content_fingerprint": _clean(
            source.get("source_content_fingerprint")
        ),
        "normalized_source_fingerprint": _clean(
            source.get("normalized_source_fingerprint")
        ),
    }
    if (
        not required["source_id"]
        or required["source_version"] <= 0
        or not required["source_fingerprint"]
        or not required["source_content_fingerprint"]
        or not required["normalized_source_fingerprint"]
    ):
        raise Phase9FEExecutionError(
            "The exact immutable starting-source identity is incomplete.",
            code="reuse_source_identity_incomplete",
        )
    return required


def validate_phase9f_d_execution_scope(
    *,
    application_id: int,
    confirmation: dict[str, Any],
    decision: dict[str, Any],
    exact_jd: dict[str, Any],
    allowed_intensities: set[str],
    intensity_error_code: str,
    intensity_error_message: str,
) -> dict[str, Any]:
    """Validate one frozen D/Phase 9E/source/JD execution scope.

    The public helper intentionally contains only facts shared by the
    Phase 9F-E Reuse and Phase 9F-F changed-content orchestrators.  Callers
    provide their own supported intensity set so the frozen Reuse wrapper can
    preserve its established error and result contract.
    """
    if int(application_id) <= 0:
        raise Phase9FEExecutionError(
            "A positive Application Session ID is required.",
            code="application_id_invalid",
        )
    if not isinstance(confirmation, dict) or not confirmation:
        raise Phase9FEExecutionError(
            "The immutable Phase 9F-D confirmation is missing.",
            code="phase9f_d_confirmation_missing",
        )
    if int(confirmation.get("application_id") or 0) != int(application_id):
        raise Phase9FEExecutionError(
            "The Phase 9F-D confirmation belongs to another Application Session.",
            code="phase9f_d_application_mismatch",
        )
    if _clean(confirmation.get("phase9f_d_version")) != PHASE9F_D_VERSION:
        raise Phase9FEExecutionError(
            "The Phase 9F-D confirmation contract is unsupported.",
            code="phase9f_d_version_unsupported",
        )
    confirmation_semantic = confirmation.get("semantic_identity")
    if not isinstance(confirmation_semantic, dict) or fingerprint_value(
        confirmation_semantic
    ) != _clean(confirmation.get("confirmation_fingerprint")):
        raise Phase9FEExecutionError(
            "The Phase 9F-D confirmation fingerprint is invalid.",
            code="phase9f_d_confirmation_fingerprint_invalid",
        )

    verify_decision_integrity(decision)
    if _clean(decision.get("phase9e_version")) != (
        PHASE9E_PHASE9F_D_EXACT_BINDING_VERSION
    ):
        raise Phase9FEExecutionError(
            "Phase 9F-E requires the exact Phase 9F-D Phase 9E binding.",
            code="phase9e_d_binding_missing",
        )
    if int(decision.get("application_id") or 0) != int(application_id):
        raise Phase9FEExecutionError(
            "The exact Phase 9E binding belongs to another Application Session.",
            code="phase9e_application_mismatch",
        )
    if _clean(confirmation.get("phase9e_decision_id")) != _clean(
        decision.get("decision_id")
    ) or _clean(confirmation.get("phase9e_decision_fingerprint")) != _clean(
        decision.get("decision_fingerprint")
    ):
        raise Phase9FEExecutionError(
            "The Phase 9F-D confirmation and exact Phase 9E binding do not match.",
            code="phase9f_d_phase9e_binding_mismatch",
        )

    confirmed_intensity = _clean(confirmation.get("confirmed_intensity")).lower()
    decision_intensity = _clean(
        (
            (decision.get("semantic_identity") or {}).get(
                "phase9f_d_confirmation"
            )
            or {}
        ).get("confirmed_intensity")
    ).lower()
    execution_intensity = _clean(
        (decision.get("phase9f_d_execution") or {}).get(
            "confirmed_intensity"
        )
    ).lower()
    if (
        not confirmed_intensity
        or confirmed_intensity != decision_intensity
        or confirmed_intensity != execution_intensity
        or confirmed_intensity not in set(allowed_intensities)
    ):
        raise Phase9FEExecutionError(
            intensity_error_message,
            code=intensity_error_code,
        )

    current_jd = exact_jd_identity(exact_jd)
    comparable_current = deepcopy(current_jd)
    comparable_current.pop("jd_identity_fingerprint", None)
    if comparable_current != _stored_jd_identity(decision):
        raise Phase9FEExecutionError(
            "The application's exact linked JD no longer matches the Phase 9F-D binding.",
            code="exact_jd_binding_mismatch",
        )

    starting = decision.get("starting_snapshot") or {}
    starting_fingerprint = _clean(starting.get("starting_snapshot_fingerprint"))
    if starting_fingerprint != _clean(
        confirmation.get("starting_snapshot_fingerprint")
    ):
        raise Phase9FEExecutionError(
            "The frozen starting snapshot no longer matches Phase 9F-D.",
            code="starting_snapshot_mismatch",
        )
    content_identity = frozen_content_identity(starting)
    source = _source_identity(decision)
    return {
        "application_id": int(application_id),
        "confirmation_id": _clean(confirmation.get("confirmation_id")),
        "confirmation_fingerprint": _clean(
            confirmation.get("confirmation_fingerprint")
        ),
        "confirmation_content_fingerprint": _clean(
            confirmation.get("confirmation_content_fingerprint")
        ),
        "phase9e_decision_id": _clean(decision.get("decision_id")),
        "phase9e_decision_fingerprint": _clean(
            decision.get("decision_fingerprint")
        ),
        "confirmed_intensity": confirmed_intensity,
        "source": source,
        "exact_jd": current_jd,
        "starting_snapshot_fingerprint": starting_fingerprint,
        "frozen_content": content_identity,
    }


def validate_reuse_execution_scope(
    *,
    application_id: int,
    confirmation: dict[str, Any],
    decision: dict[str, Any],
    exact_jd: dict[str, Any],
) -> dict[str, Any]:
    """Validate the complete frozen D/Phase 9E/JD Reuse scope.

    This wrapper is deliberately kept as the frozen Phase 9F-E-facing API.
    Its validation order, error code, and successful output remain unchanged.
    """
    validated = validate_phase9f_d_execution_scope(
        application_id=application_id,
        confirmation=confirmation,
        decision=decision,
        exact_jd=exact_jd,
        allowed_intensities={"reuse"},
        intensity_error_code="confirmed_intensity_not_reuse",
        intensity_error_message=(
            "Phase 9F-E Reuse cannot execute a Minor or Full confirmation."
        ),
    )
    return {
        **validated,
        "confirmed_intensity": "reuse",
    }


def build_execution_identity(validated_scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "format_version": PHASE9F_E_VERSION,
        "identity_policy_version": PHASE9F_E_IDENTITY_POLICY_VERSION,
        "application_id": int(validated_scope["application_id"]),
        "phase9f_d": {
            "confirmation_id": validated_scope["confirmation_id"],
            "confirmation_fingerprint": validated_scope[
                "confirmation_fingerprint"
            ],
            "confirmation_content_fingerprint": validated_scope[
                "confirmation_content_fingerprint"
            ],
            "confirmed_intensity": "reuse",
        },
        "phase9e_exact_binding": {
            "decision_id": validated_scope["phase9e_decision_id"],
            "decision_fingerprint": validated_scope[
                "phase9e_decision_fingerprint"
            ],
            "starting_snapshot_fingerprint": validated_scope[
                "starting_snapshot_fingerprint"
            ],
        },
        "source": deepcopy(validated_scope["source"]),
        "exact_jd": deepcopy(validated_scope["exact_jd"]),
        "frozen_content": deepcopy(validated_scope["frozen_content"]),
        "execution_policy": {
            "content_changed": False,
            "editable": False,
            "authoritative_artifact_required": True,
            "artifact_rematerialization_allowed": False,
            "content_changing_fit_allowed": False,
        },
    }


def prepare_execution(validated_scope: dict[str, Any]) -> dict[str, Any]:
    identity = build_execution_identity(validated_scope)
    fingerprint = fingerprint_value(identity)
    return {
        "execution_id": fingerprint[:32],
        "execution_fingerprint": fingerprint,
        "execution_version": PHASE9F_E_VERSION,
        "identity_policy_version": PHASE9F_E_IDENTITY_POLICY_VERSION,
        "semantic_identity": identity,
        "confirmed_intensity": "reuse",
        "source_type": identity["source"]["source_type"],
        "source_id": identity["source"]["source_id"],
        "zero_cost_diagnostics": zero_cost_diagnostics(),
    }


def artifact_identity(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for artifact in artifacts:
        content = artifact.get("artifact_bytes")
        if not isinstance(content, bytes) or not content:
            raise Phase9FEExecutionError(
                "An authoritative Reuse artifact has no bytes.",
                code="authoritative_artifact_missing",
            )
        digest = hashlib.sha256(content).hexdigest()
        expected_digest = _clean(
            artifact.get("sha256") or artifact.get("artifact_sha256")
        )
        expected_size = int(
            artifact.get("byte_size")
            or artifact.get("artifact_size")
            or -1
        )
        if digest != expected_digest or len(content) != expected_size:
            raise Phase9FEExecutionError(
                "An authoritative Reuse artifact failed SHA-256 or size validation.",
                code="authoritative_artifact_integrity_failed",
            )
        rows.append(
            {
                "artifact_kind": _clean(
                    artifact.get("artifact_type")
                    or artifact.get("artifact_kind")
                ),
                "artifact_sha256": digest,
                "artifact_size": len(content),
                "mime_type": _clean(
                    artifact.get("media_type") or artifact.get("mime_type")
                ),
                "provenance_mode": "phase9f_e_exact_authoritative_copy",
                "provenance_label": _clean(
                    artifact.get("provenance_label")
                )
                or "Exact authoritative Reuse artifact",
                "verification_method": _clean(
                    artifact.get("verification_method")
                )
                or "authoritative_sha256_and_size",
            }
        )
    if not rows:
        raise Phase9FEExecutionError(
            "No authoritative Reuse artifact is available.",
            code="authoritative_artifact_missing",
        )
    kinds = [row["artifact_kind"] for row in rows]
    if len(kinds) != len(set(kinds)):
        raise Phase9FEExecutionError(
            "The authoritative Reuse artifact scope is ambiguous.",
            code="authoritative_artifact_ambiguous",
        )
    return sorted(rows, key=lambda row: row["artifact_kind"])


def build_result_identity(
    *,
    execution: dict[str, Any],
    validated_scope: dict[str, Any],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    source = deepcopy(validated_scope["source"])
    return {
        "format_version": PHASE9F_E_RESULT_FORMAT_VERSION,
        "identity_policy_version": PHASE9F_E_RESULT_IDENTITY_POLICY_VERSION,
        "application_id": int(validated_scope["application_id"]),
        "generation_mode": PHASE9F_E_GENERATION_MODE,
        "initial_status": PHASE9F_E_RESULT_STATUS,
        "content_changed": False,
        "editable": False,
        "phase9f_e_execution": {
            "execution_id": execution["execution_id"],
            "execution_fingerprint": execution["execution_fingerprint"],
            "workflow_action": PHASE9F_E_WORKFLOW_ACTION,
        },
        "phase9f_d": {
            "confirmation_id": validated_scope["confirmation_id"],
            "confirmation_fingerprint": validated_scope[
                "confirmation_fingerprint"
            ],
            "confirmed_intensity": "reuse",
        },
        "phase9e": {
            "decision_id": validated_scope["phase9e_decision_id"],
            "decision_fingerprint": validated_scope[
                "phase9e_decision_fingerprint"
            ],
        },
        "source": source,
        "exact_jd": deepcopy(validated_scope["exact_jd"]),
        "starting_snapshot_fingerprint": validated_scope[
            "starting_snapshot_fingerprint"
        ],
        "frozen_content": deepcopy(validated_scope["frozen_content"]),
        "artifacts": artifact_identity(artifacts),
        "phase9b_eligibility_policy": {
            "unchanged_global_blueprint_repromotion_allowed": False,
            "unchanged_base_resume_may_be_evaluated": True,
            "requires_current_phase8_and_phase9b_gates": True,
        },
        "mutation_policy": {
            "phase9f_d_mutated": False,
            "phase9e_binding_mutated": False,
            "starting_source_mutated": False,
            "jd_mutated": False,
            "content_changed": False,
            "artifact_rematerialized": False,
        },
    }


def prepare_result(
    *,
    identity: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    fingerprint = fingerprint_value(identity)
    return {
        "application_result_id": fingerprint[:32],
        "result_fingerprint": fingerprint,
        "format_version": PHASE9F_E_RESULT_FORMAT_VERSION,
        "identity_policy_version": PHASE9F_E_RESULT_IDENTITY_POLICY_VERSION,
        "generation_mode": PHASE9F_E_GENERATION_MODE,
        "initial_status": PHASE9F_E_RESULT_STATUS,
        "content_changed": False,
        "editable": False,
        "semantic_identity": deepcopy(identity),
        "result_snapshot": deepcopy(snapshot),
    }


def build_phase8_generation_adapter(
    *,
    application_id: int,
    result: dict[str, Any],
    projects: dict[str, Any],
    skills: dict[str, Any],
    artifact_paths: dict[str, str],
) -> dict[str, Any]:
    """Expose unchanged immutable content through Phase 8's input contract."""
    fit = {
        "generation_id": result["application_result_id"],
        "fit_one_page": True,
        "page_count": 1,
        "tailored_projects_used": deepcopy(projects),
        "tailored_skills_used": deepcopy(skills),
        "phase9f_e_adapter_version": PHASE9F_E_PHASE8_ADAPTER_VERSION,
        "content_changed": False,
        **deepcopy(artifact_paths),
    }
    return {
        "application_id": int(application_id),
        "generation_id": result["application_result_id"],
        "generation_kind": PHASE9F_E_GENERATION_MODE,
        "status": "approved",
        "updated_at": result["result_fingerprint"],
        "projects": deepcopy(projects),
        "skills": deepcopy(skills),
        "fit_result": fit,
        "content_changed": False,
        "phase9f_e_result_fingerprint": result["result_fingerprint"],
    }


def phase9b_eligibility(
    *,
    result: dict[str, Any],
    phase8_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Describe the narrow Reuse result's downstream promotion posture."""
    source_type = _clean(
        (result.get("semantic_identity") or {}).get("source", {}).get(
            "source_type"
        )
    )
    if source_type == "global_blueprint":
        return {
            "eligible": False,
            "reason_code": "unchanged_global_blueprint_already_promoted",
        }
    verification = phase8_result or {}
    return {
        "eligible": bool(
            source_type == "base_resume"
            and verification.get("blueprint_ready") is True
            and verification.get("fit_one_page") is True
            and verification.get("comparison_valid") is True
        ),
        "reason_code": (
            "base_resume_reuse_satisfies_current_phase8_gates"
            if source_type == "base_resume"
            and verification.get("blueprint_ready") is True
            and verification.get("fit_one_page") is True
            and verification.get("comparison_valid") is True
            else "base_resume_reuse_requires_current_phase8_and_phase9b_gates"
        ),
    }

"""Exact-snapshot freshness checks for automatic Phase 8 verification."""
from __future__ import annotations

from typing import Any

from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from tailoring.phase8_verification import (
    PHASE8_PREAPPROVAL_GATE_VERSION,
    PHASE8_VERIFICATION_VERSION,
    build_phase8_generation_snapshot_fingerprint,
    document_artifact_is_current,
)
from tailoring.job_match_ab_analysis import inspect_job_match_ab_lifecycle

PHASE8_AUTO_VERIFY_VERSION = "phase8-auto-verify-v1"


def _matches_active_scoring_policy(verification: dict[str, Any]) -> bool:
    """When the A1.7 scorer policy is active, refuse old-policy Phase 8 receipts.

    A1.8 enables that policy by default; an explicit legacy startup rollback
    retains the earlier historical receipt and snapshot compatibility rules.
    """
    if not SCORING_VERSION.endswith("-v312a17-fullstack-single-row"):
        return True
    after = verification.get("after_stable_analysis")
    if not isinstance(after, dict):
        return False
    version = str(after.get("scoring_version") or "")
    return version == SCORING_VERSION or version.startswith(SCORING_VERSION + "+")


def phase8_verification_is_current(
    verification: dict[str, Any] | None,
    generation_state: dict[str, Any] | None,
) -> bool:
    if not isinstance(verification, dict) or not isinstance(generation_state, dict):
        return False
    if not isinstance(generation_state.get("fit_result"), dict):
        return False
    if ((generation_state.get('generation_settings') or {}).get('phase9f_f_normal_lifecycle')
            and not isinstance(verification.get('document_analysis'), dict)):
        return False  # A legacy profile comparison is not a document-grounded certificate.
    if not document_artifact_is_current(verification, generation_state):
        return False
    if str(verification.get("phase8_version") or "").strip() != PHASE8_VERIFICATION_VERSION:
        return False
    if (
        str(verification.get("approval_gate_version") or "").strip()
        != PHASE8_PREAPPROVAL_GATE_VERSION
    ):
        return False
    if not _matches_active_scoring_policy(verification):
        return False
    expected = build_phase8_generation_snapshot_fingerprint(generation_state)
    actual = str(
        verification.get("verified_generation_snapshot_fingerprint") or ""
    ).strip()
    if not actual or actual != expected:
        return False
    lifecycle = inspect_job_match_ab_lifecycle(
        verification.get("job_match_ab"),
        current_generation_snapshot_fingerprint=expected,
    )
    return lifecycle.get("state") == "both_analyses_available_and_comparable"


def phase8_verification_refresh_reason(
    verification: dict[str, Any] | None,
    generation_state: dict[str, Any] | None,
) -> str:
    if not isinstance(verification, dict):
        return "verification_missing"
    if not isinstance(generation_state, dict):
        return "generation_missing"
    if not isinstance(generation_state.get("fit_result"), dict):
        return "fit_missing"
    if ((generation_state.get('generation_settings') or {}).get('phase9f_f_normal_lifecycle')
            and not isinstance(verification.get('document_analysis'), dict)):
        return 'legacy_profile_only_requires_new_selected_base_docx_verification'
    if not document_artifact_is_current(verification, generation_state):
        return 'actual_final_document_changed_or_unavailable'
    if str(verification.get("phase8_version") or "").strip() != PHASE8_VERIFICATION_VERSION:
        return "phase8_version_mismatch"
    if (
        str(verification.get("approval_gate_version") or "").strip()
        != PHASE8_PREAPPROVAL_GATE_VERSION
    ):
        return "approval_gate_version_mismatch"
    if not _matches_active_scoring_policy(verification):
        return "scoring_policy_changed_requires_fresh_verification"
    expected = build_phase8_generation_snapshot_fingerprint(generation_state)
    actual = str(
        verification.get("verified_generation_snapshot_fingerprint") or ""
    ).strip()
    if not actual or actual != expected:
        return "fitted_snapshot_changed"
    lifecycle = inspect_job_match_ab_lifecycle(
        verification.get("job_match_ab"),
        current_generation_snapshot_fingerprint=expected,
    )
    if lifecycle.get("state") != "both_analyses_available_and_comparable":
        return str(lifecycle.get("state") or "analysis_generation_superseded")
    return "current"

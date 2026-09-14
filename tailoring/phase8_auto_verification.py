"""Exact-snapshot freshness checks for automatic Phase 8 verification."""
from __future__ import annotations

from typing import Any

from tailoring.phase8_verification import (
    PHASE8_PREAPPROVAL_GATE_VERSION,
    PHASE8_VERIFICATION_VERSION,
    build_phase8_generation_snapshot_fingerprint,
)

PHASE8_AUTO_VERIFY_VERSION = "phase8-auto-verify-v1"


def phase8_verification_is_current(
    verification: dict[str, Any] | None,
    generation_state: dict[str, Any] | None,
) -> bool:
    if not isinstance(verification, dict) or not isinstance(generation_state, dict):
        return False
    if not isinstance(generation_state.get("fit_result"), dict):
        return False
    if str(verification.get("phase8_version") or "").strip() != PHASE8_VERIFICATION_VERSION:
        return False
    if (
        str(verification.get("approval_gate_version") or "").strip()
        != PHASE8_PREAPPROVAL_GATE_VERSION
    ):
        return False
    expected = build_phase8_generation_snapshot_fingerprint(generation_state)
    actual = str(
        verification.get("verified_generation_snapshot_fingerprint") or ""
    ).strip()
    return bool(actual and actual == expected)


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
    if str(verification.get("phase8_version") or "").strip() != PHASE8_VERIFICATION_VERSION:
        return "phase8_version_mismatch"
    if (
        str(verification.get("approval_gate_version") or "").strip()
        != PHASE8_PREAPPROVAL_GATE_VERSION
    ):
        return "approval_gate_version_mismatch"
    if not phase8_verification_is_current(verification, generation_state):
        return "fitted_snapshot_changed"
    return "current"

"""Immutable, zero-cost exact-verified-reuse proof contracts for Phase 9F.

This module is deliberately independent of SQLite and Streamlit.  The database
adapter resolves authoritative records; Phase 9F-B/C/D validate and fingerprint
the resulting compact proof here.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


PHASE9F_EXACT_VERIFIED_REUSE_PROOF_VERSION = (
    "phase9f-exact-verified-reuse-proof-v1"
)
PHASE9F_BLUEPRINT_ARTIFACT_POLICY_VERSION = (
    "phase9f-blueprint-owned-artifact-v1"
)


class Phase9FExactVerifiedReuseError(ValueError):
    """The compact proof is absent, stale, or structurally unsafe."""


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


def ineligible_exact_verified_reuse(
    reason_code: str,
    *,
    blueprint_id: str = "",
    blueprint_fingerprint: str = "",
) -> dict[str, Any]:
    """Return one canonical, non-authorizing proof result."""
    return {
        "proof_version": PHASE9F_EXACT_VERIFIED_REUSE_PROOF_VERSION,
        "eligible": False,
        "reason_code": _clean(reason_code) or "proof_unavailable",
        "blueprint_id": _clean(blueprint_id),
        "blueprint_fingerprint": _clean(blueprint_fingerprint),
        "proof_fingerprint": "",
    }


def build_exact_verified_reuse_proof(
    identity: dict[str, Any],
) -> dict[str, Any]:
    """Freeze an already validated proof into the public compact contract."""
    if not isinstance(identity, dict):
        raise Phase9FExactVerifiedReuseError("Exact-reuse identity is missing.")
    required = (
        "blueprint",
        "current_jd",
        "source_jd",
        "source_generation",
        "phase8_verification",
        "phase9c_source_parity",
        "artifact_identity",
    )
    if any(not isinstance(identity.get(key), dict) for key in required):
        raise Phase9FExactVerifiedReuseError(
            "Exact-reuse identity is incomplete."
        )
    semantic_identity = {
        "proof_version": PHASE9F_EXACT_VERIFIED_REUSE_PROOF_VERSION,
        "artifact_policy_version": PHASE9F_BLUEPRINT_ARTIFACT_POLICY_VERSION,
        **deepcopy(identity),
    }
    return {
        "proof_version": PHASE9F_EXACT_VERIFIED_REUSE_PROOF_VERSION,
        "eligible": True,
        "reason_code": "exact_verified_reuse",
        "proof_fingerprint": fingerprint_value(semantic_identity),
        "semantic_identity": semantic_identity,
        "verified_score": int(
            (identity.get("phase8_verification") or {}).get("score") or 0
        ),
        "blueprint_id": _clean((identity.get("blueprint") or {}).get("id")),
        "blueprint_fingerprint": _clean(
            (identity.get("blueprint") or {}).get("fingerprint")
        ),
        "source_application_id": int(
            (identity.get("source_generation") or {}).get("application_id") or 0
        ),
        "source_generation_id": _clean(
            (identity.get("source_generation") or {}).get("generation_id")
        ),
        "phase8_verification_id": _clean(
            (identity.get("phase8_verification") or {}).get("verification_id")
        ),
        "artifact_identity": deepcopy(identity.get("artifact_identity") or {}),
        "jd_identity": deepcopy(identity.get("current_jd") or {}),
    }


def validate_exact_verified_reuse_proof(
    proof: Any,
    *,
    source_type: str,
    source_id: str,
    source_fingerprint: str,
) -> dict[str, Any]:
    """Validate a proof supplied to B/C/D without querying persistence."""
    if _clean(source_type) != "global_blueprint":
        return ineligible_exact_verified_reuse("source_type_not_global_blueprint")
    if not isinstance(proof, dict):
        return ineligible_exact_verified_reuse(
            "exact_verified_reuse_proof_missing",
            blueprint_id=source_id,
            blueprint_fingerprint=source_fingerprint,
        )
    if proof.get("eligible") is not True:
        return ineligible_exact_verified_reuse(
            _clean(proof.get("reason_code")) or "proof_not_eligible",
            blueprint_id=source_id,
            blueprint_fingerprint=source_fingerprint,
        )
    if _clean(proof.get("proof_version")) != (
        PHASE9F_EXACT_VERIFIED_REUSE_PROOF_VERSION
    ):
        raise Phase9FExactVerifiedReuseError(
            "The exact-reuse proof version is unsupported."
        )
    semantic = proof.get("semantic_identity")
    expected = _clean(proof.get("proof_fingerprint"))
    if not isinstance(semantic, dict) or not expected or fingerprint_value(semantic) != expected:
        raise Phase9FExactVerifiedReuseError(
            "The exact-reuse proof fingerprint is inconsistent."
        )
    blueprint = semantic.get("blueprint") or {}
    if (
        _clean(blueprint.get("id")) != _clean(source_id)
        or _clean(blueprint.get("fingerprint")) != _clean(source_fingerprint)
        or _clean(proof.get("blueprint_id")) != _clean(source_id)
        or _clean(proof.get("blueprint_fingerprint")) != _clean(source_fingerprint)
    ):
        raise Phase9FExactVerifiedReuseError(
            "The exact-reuse proof belongs to another Blueprint."
        )
    if _clean(semantic.get("artifact_policy_version")) != (
        PHASE9F_BLUEPRINT_ARTIFACT_POLICY_VERSION
    ):
        raise Phase9FExactVerifiedReuseError(
            "The exact-reuse proof artifact policy is unsupported."
        )
    return deepcopy(proof)

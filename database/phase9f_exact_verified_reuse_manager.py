"""Read-only authoritative Phase 9F exact-verified-reuse proof resolution."""

from __future__ import annotations

import hashlib
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from tailoring.phase9f_exact_verified_reuse import (
    PHASE9F_BLUEPRINT_ARTIFACT_POLICY_VERSION,
    Phase9FExactVerifiedReuseError,
    build_exact_verified_reuse_proof,
    ineligible_exact_verified_reuse,
)
from tailoring.phase9f_starting_source_provenance import (
    Phase9FBProvenanceError,
    load_blueprint_provenance_read_only,
)


# Tests and isolated deployments may redirect only the owned artifact store.
# Paths are storage metadata, never semantic Blueprint identity.
BLUEPRINT_ARTIFACT_ROOT = Path(
    os.environ.get("PHASE9F_BLUEPRINT_ARTIFACT_ROOT", "data/blueprint_artifacts")
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _current_jd_identity(exact_jd: dict[str, Any]) -> dict[str, Any]:
    semantic = exact_jd.get("semantic_identity") or {}
    provenance = exact_jd.get("provenance") or {}
    return {
        "canonical_jd_id": _clean(
            provenance.get("canonical_jd_id")
            or exact_jd.get("canonical_jd_id")
        ),
        "source_version_id": _clean(
            provenance.get("source_version_id")
            or exact_jd.get("source_version_id")
        ),
        "raw_jd_sha256": _clean(semantic.get("raw_jd_sha256")),
        "structured_profile_fingerprint": _clean(
            semantic.get("structured_profile_fingerprint")
        ),
        "canonical_requirement_fingerprint": _clean(
            semantic.get("canonical_requirement_fingerprint")
        ),
        "canonical_requirement_ids": sorted(
            str(value) for value in semantic.get("canonical_requirement_ids") or []
        ),
        "stable_input_fingerprint": _clean(
            provenance.get("stable_input_fingerprint")
        ),
    }


def _owned_artifact_identity(blueprint: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    snapshot = blueprint.get("blueprint_snapshot") or {}
    semantic = blueprint.get("semantic_identity") or {}
    semantic_artifacts = semantic.get("artifact_provenance") or {}
    storage = snapshot.get("artifact_provenance") or {}
    if (
        not isinstance(semantic_artifacts, dict)
        or not isinstance(storage, dict)
        or _clean(semantic_artifacts.get("policy_version"))
        != PHASE9F_BLUEPRINT_ARTIFACT_POLICY_VERSION
        or semantic_artifacts != {
            key: value
            for key, value in storage.items()
            if key != "storage"
        }
    ):
        return None, "legacy_missing_immutable_artifact_provenance"
    records = semantic_artifacts.get("artifacts")
    locations = storage.get("storage")
    if not isinstance(records, list) or not isinstance(locations, list):
        return None, "blueprint_artifact_manifest_incomplete"
    by_kind = {str(row.get("artifact_kind") or ""): row for row in records if isinstance(row, dict)}
    by_location = {str(row.get("artifact_kind") or ""): row for row in locations if isinstance(row, dict)}
    if set(by_kind) != {"docx", "pdf"} or set(by_location) != {"docx", "pdf"}:
        return None, "blueprint_artifact_manifest_incomplete"
    root = BLUEPRINT_ARTIFACT_ROOT.resolve()
    checked: list[dict[str, Any]] = []
    for kind in ("docx", "pdf"):
        manifest = by_kind[kind]
        location = by_location[kind]
        relative = str(location.get("storage_relative_path") or "")
        path = (root / relative).resolve()
        if not relative or root not in path.parents or not path.is_file():
            return None, "blueprint_owned_artifact_missing"
        if (
            _sha256(path) != _clean(manifest.get("sha256"))
            or path.stat().st_size != int(manifest.get("byte_size") or -1)
        ):
            return None, "blueprint_owned_artifact_hash_mismatch"
        checked.append(deepcopy(manifest))
    return {
        "policy_version": PHASE9F_BLUEPRINT_ARTIFACT_POLICY_VERSION,
        "artifacts": checked,
    }, ""


def resolve_blueprint_owned_artifacts(
    blueprint: dict[str, Any],
) -> list[dict[str, Any]]:
    """Read verified Blueprint-owned bytes without touching source output paths."""
    identity, error = _owned_artifact_identity(blueprint)
    if identity is None:
        raise Phase9FExactVerifiedReuseError(error)
    snapshot = blueprint.get("blueprint_snapshot") or {}
    storage = (snapshot.get("artifact_provenance") or {}).get("storage") or []
    locations = {
        _clean(row.get("artifact_kind")): row
        for row in storage
        if isinstance(row, dict)
    }
    result: list[dict[str, Any]] = []
    root = BLUEPRINT_ARTIFACT_ROOT.resolve()
    for manifest in identity["artifacts"]:
        kind = _clean(manifest.get("artifact_kind"))
        path = (root / str(locations[kind]["storage_relative_path"])).resolve()
        content = path.read_bytes()
        result.append(
            {
                **deepcopy(manifest),
                "artifact_bytes": content,
                "source_path": str(path),
                "filename": path.name,
                "artifact_type": kind,
                "provenance_label": "Blueprint-owned immutable approved artifact",
                "verification_method": "blueprint_owned_sha256",
            }
        )
    return result


def prove_exact_verified_reuse(
    *,
    blueprint: dict[str, Any],
    current_exact_jd: dict[str, Any],
    database_path: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve one exact-reuse proof using only immutable files and SELECTs."""
    blueprint_id = _clean((blueprint or {}).get("blueprint_id"))
    blueprint_fingerprint = _clean((blueprint or {}).get("blueprint_fingerprint"))
    if not isinstance(blueprint, dict) or not blueprint_id:
        return ineligible_exact_verified_reuse("blueprint_missing")
    if (
        _clean(blueprint.get("status")) != "active"
        or _clean(blueprint.get("availability_status") or "available") != "available"
        or blueprint.get("is_reusable") is False
    ):
        return ineligible_exact_verified_reuse(
            "blueprint_not_active_available_reusable",
            blueprint_id=blueprint_id,
            blueprint_fingerprint=blueprint_fingerprint,
        )
    artifact_identity, artifact_error = _owned_artifact_identity(blueprint)
    if artifact_identity is None:
        return ineligible_exact_verified_reuse(
            artifact_error,
            blueprint_id=blueprint_id,
            blueprint_fingerprint=blueprint_fingerprint,
        )
    try:
        provenance = load_blueprint_provenance_read_only(
            blueprint, database_path=database_path
        )
    except (OSError, ValueError, Phase9FBProvenanceError) as exc:
        return ineligible_exact_verified_reuse(
            "blueprint_source_provenance_unavailable",
            blueprint_id=blueprint_id,
            blueprint_fingerprint=blueprint_fingerprint,
        )
    if provenance.get("chain_status") != "resolved":
        return ineligible_exact_verified_reuse(
            "blueprint_source_provenance_incomplete",
            blueprint_id=blueprint_id,
            blueprint_fingerprint=blueprint_fingerprint,
        )
    source_generation = (
        (provenance.get("source_resume_result_or_generation") or {}).get(
            "source_generation"
        )
        or {}
    )
    phase8 = provenance.get("phase8_verification") or {}
    phase9b = provenance.get("phase9b_candidate") or {}
    phase9c = provenance.get("phase9c_evaluation") or {}
    source_jd = provenance.get("source_jd") or {}
    snapshot = blueprint.get("blueprint_snapshot") or {}
    candidate = snapshot.get("phase9b_candidate_semantic_snapshot") or {}
    candidate_metadata = candidate.get("evaluation_metadata") or {}
    expected_final_seed_fingerprint = _clean(
        candidate_metadata.get("source_final_scoring_seed_fingerprint")
    )
    if not (
        source_generation.get("approval_resolved") is True
        and source_generation.get("fit_identity_match") is True
        and source_generation.get("fit_one_page") is True
        and int(source_generation.get("page_count") or 0) == 1
        and phase8.get("resolved") is True
        and phase8.get("blueprint_ready") is True
        and _clean(phase8.get("final_scoring_seed_fingerprint"))
        and phase8.get("final_scoring_seed_valid") is True
        and expected_final_seed_fingerprint
        and _clean(phase8.get("final_scoring_seed_fingerprint"))
        == expected_final_seed_fingerprint
        and phase9b.get("identity_match") is True
        and phase9c.get("identity_match") is True
        and phase9c.get("source_jd_parity_accepted") is True
        and source_jd.get("resolved") is True
        and source_jd.get("exact_identity_match") is True
    ):
        return ineligible_exact_verified_reuse(
            "blueprint_source_validation_failed",
            blueprint_id=blueprint_id,
            blueprint_fingerprint=blueprint_fingerprint,
        )
    current = _current_jd_identity(current_exact_jd)
    expected = {
        "canonical_jd_id": _clean(source_jd.get("canonical_jd_id")),
        "source_version_id": _clean(source_jd.get("source_version_id")),
        "raw_jd_sha256": _clean(source_jd.get("raw_jd_sha256")),
        "canonical_requirement_fingerprint": _clean(
            source_jd.get("canonical_requirement_fingerprint")
        ),
        "canonical_requirement_ids": sorted(
            str(value) for value in candidate.get("canonical_requirement_ids") or []
        ),
    }
    comparable = (
        current["canonical_jd_id"] == expected["canonical_jd_id"]
        and current["source_version_id"] == expected["source_version_id"]
        and current["raw_jd_sha256"] == expected["raw_jd_sha256"]
        and current["canonical_requirement_fingerprint"]
        == expected["canonical_requirement_fingerprint"]
        and bool(expected["canonical_requirement_ids"])
        and current["canonical_requirement_ids"]
        == expected["canonical_requirement_ids"]
    )
    if not comparable:
        return ineligible_exact_verified_reuse(
            "current_jd_not_exact_verified_source_jd",
            blueprint_id=blueprint_id,
            blueprint_fingerprint=blueprint_fingerprint,
        )
    try:
        return build_exact_verified_reuse_proof(
            {
                "blueprint": {
                    "id": blueprint_id,
                    "fingerprint": blueprint_fingerprint,
                    "version": int(blueprint.get("version_number") or 0),
                },
                "current_jd": current,
                "source_jd": expected,
                "source_generation": {
                    "application_id": int(source_generation.get("application_id") or 0),
                    "generation_id": _clean(source_generation.get("generation_id")),
                    "input_fingerprint": _clean(source_generation.get("input_fingerprint")),
                    "content_fingerprint": _clean(source_generation.get("content_fingerprint")),
                    "fit_generation_id": _clean(source_generation.get("fit_generation_id")),
                },
                "phase8_verification": {
                    "verification_id": _clean(phase8.get("verification_id")),
                    "verification_fingerprint": _clean(phase8.get("verification_fingerprint")),
                    "phase8_version": _clean(phase8.get("phase8_version")),
                    "final_scoring_seed_fingerprint": _clean(phase8.get("final_scoring_seed_fingerprint")),
                    "score": int(phase8.get("historical_approved_score") or 0),
                },
                "phase9c_source_parity": {
                    "evaluation_id": _clean(phase9c.get("evaluation_id")),
                    "evaluation_fingerprint": _clean(phase9c.get("evaluation_fingerprint")),
                    "accepted": True,
                },
                "artifact_identity": artifact_identity,
            }
        )
    except (TypeError, ValueError, Phase9FExactVerifiedReuseError):
        return ineligible_exact_verified_reuse(
            "exact_verified_reuse_proof_invalid",
            blueprint_id=blueprint_id,
            blueprint_fingerprint=blueprint_fingerprint,
        )


def annotate_blueprints_for_exact_verified_reuse(
    blueprints: list[dict[str, Any]],
    *,
    current_exact_jd: dict[str, Any],
    database_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Attach fresh, read-only proofs before the pure B ranking boundary."""
    annotated: list[dict[str, Any]] = []
    for blueprint in blueprints:
        row = deepcopy(blueprint)
        row["exact_verified_reuse_proof"] = prove_exact_verified_reuse(
            blueprint=row,
            current_exact_jd=current_exact_jd,
            database_path=database_path,
        )
        annotated.append(row)
    return annotated

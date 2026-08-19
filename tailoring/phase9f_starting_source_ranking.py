"""Phase 9F-B deterministic immutable starting-resume source ranking.

This module is deliberately pure.  It consumes already-loaded immutable JD,
Base Resume, and Global Blueprint snapshots and never imports persistence,
model, embedding, or Chroma APIs.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Iterable

from analysis_stability.stable_evidence_scoring import (
    SCORING_VERSION,
    build_deterministic_keyword_match,
    build_stable_analysis,
)
from rag.jd_identity import source_version_id
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.phase9b_role_family import suggest_role_family
from tailoring.phase9f_starting_source_transparency import (
    compact_requirement_transparency,
)
from tailoring.phase9f_exact_verified_reuse import (
    Phase9FExactVerifiedReuseError,
    ineligible_exact_verified_reuse,
    validate_exact_verified_reuse_proof,
)


PHASE9F_B_VERSION = "phase9f-starting-source-ranking-v2"
PHASE9F_B_SOURCE_POLICY_VERSION = "phase9f-immutable-starting-source-v1"
PHASE9F_B_SCORING_POLICY_VERSION = "phase9f-phase9c-fresh-target-scoring-v1"
PHASE9F_B_EVIDENCE_POLICY_VERSION = "phase9f-phase9c-fresh-target-evidence-v1"
PHASE9F_B_RANKING_POLICY_VERSION = "phase9f-starting-source-ranking-policy-v2"
PHASE9F_B_CANDIDATE_ANALYSIS_SNAPSHOT_VERSION = (
    "phase9f-b-candidate-current-jd-analysis-v1"
)

BASE_RESUME_FORMAT_VERSION = "phase9f-global-master-resume-v1"
BASE_RESUME_CONTENT_POLICY_VERSION = (
    "phase9f-global-master-resume-content-identity-v1"
)
BASE_RESUME_VERSION_POLICY_VERSION = (
    "phase9f-global-master-resume-version-identity-v1"
)
BLUEPRINT_FORMAT_VERSION = "phase9d-global-blueprint-v1"
BLUEPRINT_IDENTITY_POLICY_VERSION = "phase9d-global-blueprint-identity-v2"
LEGACY_BLUEPRINT_IDENTITY_POLICY_VERSION = "phase9d-global-blueprint-identity-v1"

IMPORTANT_REQUIREMENTS = {"deal_breaker", "required", "core"}
ROLE_FAMILY_PRIOR_CONFIDENCES = {"medium", "high"}

# Calibrated against the synthetic golden cases in
# ci_fixtures/phase9f_starting_source_ranking_golden.json.  The window allows
# only small score variation while forbidding any deal-breaker or important-gap
# disadvantage.  It is recorded verbatim in ranking semantic identity.
ROLE_FAMILY_NEAR_TIE_TOLERANCES = {
    "deal_breaker_gap_count": 0,
    "required_core_coverage_points": 3,
    "overall_alignment_points": 3,
    "evidence_strength_points": 5,
    "important_gap_count": 0,
    "preferred_coverage_points": 5,
}

RANKING_RESULT_IDENTITY_FIELDS = (
    "rank",
    "source_type",
    "source_id",
    "source_version",
    "source_fingerprint",
    "source_content_fingerprint",
    "normalized_source_fingerprint",
    "role_family_relationship",
    "role_family_prior_eligible",
    "role_family_prior_applied",
    "ranking_reason",
    "deterministic_alignment_score",
    "required_core_coverage_score",
    "preferred_coverage_score",
    "evidence_strength_score",
    "important_gap_count",
    "deal_breaker_gap_count",
    "stable_input_fingerprint",
    "comparison_result_fingerprint",
    "exact_verified_reuse_eligible",
    "exact_verified_reuse_proof_fingerprint",
)


class Phase9FBRankingError(ValueError):
    """A deterministic Phase 9F-B integrity or scoring failure."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        source_type: str = "",
        source_id: str = "",
    ) -> None:
        super().__init__(message)
        self.diagnostic = {
            "code": str(code),
            "message": str(message),
            "source_type": str(source_type),
            "source_id": str(source_id),
        }


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def fingerprint_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_text(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _requirement_scope_rows(
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "requirement_id": _clean(row.get("requirement_id")),
            "text": _clean(row.get("text")),
            "importance": _clean(row.get("importance")),
            "atomic_group_id": _clean(row.get("atomic_group_id")),
            "group_weight_fraction": row.get("group_weight_fraction"),
        }
        for row in rows
        if isinstance(row, dict)
    ]


def canonical_requirement_scope_fingerprint(
    rows: Iterable[dict[str, Any]],
) -> str:
    return fingerprint_value(_requirement_scope_rows(rows))


def _require_complete_profile(
    profile: Any,
    *,
    source_type: str,
    source_id: str,
) -> dict[str, Any]:
    if not isinstance(profile, dict) or not profile:
        raise Phase9FBRankingError(
            "The immutable resume profile is missing.",
            code="resume_profile_missing",
            source_type=source_type,
            source_id=source_id,
        )
    missing = [
        section
        for section in ("education", "experience", "projects", "skills")
        if section not in profile
    ]
    if missing:
        raise Phase9FBRankingError(
            "The immutable resume profile is missing sections: "
            + ", ".join(missing),
            code="resume_profile_sections_missing",
            source_type=source_type,
            source_id=source_id,
        )
    return deepcopy(profile)


def validate_exact_jd_snapshot(
    exact_jd: dict[str, Any],
) -> dict[str, Any]:
    """Validate Phase 9F-A semantic content without making storage provenance semantic."""
    if not isinstance(exact_jd, dict) or not exact_jd:
        raise Phase9FBRankingError(
            "A current exact Phase 9F-A JD snapshot is required.",
            code="exact_jd_missing",
        )
    raw_text = str(exact_jd.get("raw_text") or "")
    profile = exact_jd.get("jd_profile")
    rows = exact_jd.get("canonical_requirements")
    if not raw_text.strip() or not isinstance(profile, dict) or not profile:
        raise Phase9FBRankingError(
            "The exact JD raw text or structured profile is missing.",
            code="exact_jd_content_missing",
        )
    if not isinstance(rows, list) or not rows:
        raise Phase9FBRankingError(
            "The exact JD has no frozen canonical requirements.",
            code="exact_jd_requirements_missing",
        )

    raw_hash = _sha256_text(raw_text)
    profile_fingerprint = fingerprint_value(profile)
    requirement_fingerprint = canonical_requirement_scope_fingerprint(rows)
    requirement_ids = sorted(
        _clean(row.get("requirement_id"))
        for row in rows
        if isinstance(row, dict) and _clean(row.get("requirement_id"))
    )
    if len(requirement_ids) != len(set(requirement_ids)):
        raise Phase9FBRankingError(
            "The exact JD contains duplicate canonical requirement IDs.",
            code="exact_jd_duplicate_requirement_ids",
        )

    expected = {
        "raw_jd_sha256": raw_hash,
        "structured_profile_fingerprint": profile_fingerprint,
        "canonical_requirement_fingerprint": requirement_fingerprint,
        "canonical_requirement_ids": requirement_ids,
        "source_version_id": source_version_id(raw_text),
    }
    for field, value in expected.items():
        actual = exact_jd.get(field)
        if field == "canonical_requirement_ids":
            actual = sorted(str(item) for item in actual or [])
        else:
            actual = _clean(actual)
        if actual != value:
            raise Phase9FBRankingError(
                f"The exact JD {field} is stale or inconsistent.",
                code=f"exact_jd_{field}_mismatch",
            )

    canonicalisation = exact_jd.get("canonicalisation")
    canonicalisation_rows = (
        canonicalisation.get("requirements")
        if isinstance(canonicalisation, dict)
        else None
    )
    if (
        not isinstance(canonicalisation_rows, list)
        or canonical_requirement_scope_fingerprint(canonicalisation_rows)
        != requirement_fingerprint
    ):
        raise Phase9FBRankingError(
            "The exact JD canonicalisation snapshot does not match its frozen scope.",
            code="exact_jd_canonicalisation_scope_mismatch",
        )

    semantic = exact_jd.get("semantic_identity")
    snapshot_fingerprint = _clean(exact_jd.get("snapshot_fingerprint"))
    if (
        not isinstance(semantic, dict)
        or fingerprint_value(semantic) != snapshot_fingerprint
    ):
        raise Phase9FBRankingError(
            "The exact JD snapshot fingerprint is inconsistent.",
            code="exact_jd_snapshot_fingerprint_mismatch",
        )
    for field in (
        "raw_jd_sha256",
        "structured_profile_fingerprint",
        "canonical_requirement_fingerprint",
    ):
        if _clean(semantic.get(field)) != expected[field]:
            raise Phase9FBRankingError(
                f"The exact JD semantic {field} is inconsistent.",
                code=f"exact_jd_semantic_{field}_mismatch",
            )
    if sorted(semantic.get("canonical_requirement_ids") or []) != requirement_ids:
        raise Phase9FBRankingError(
            "The exact JD semantic requirement IDs are inconsistent.",
            code="exact_jd_semantic_requirement_ids_mismatch",
        )

    classified = suggest_role_family({"jd_profile": deepcopy(profile)})
    role = exact_jd.get("role_family") or {}
    role_semantic = semantic.get("role_family") or {}
    role_identity = {
        "role_family_id": _clean(classified.get("role_family_id")),
        "confidence": _clean(classified.get("confidence")).lower(),
        "classifier_version": _clean(classified.get("suggestion_method")),
    }
    if (
        _clean(role.get("role_family_id")) != role_identity["role_family_id"]
        or _clean(role.get("confidence")).lower() != role_identity["confidence"]
        or _clean(role.get("suggestion_method"))
        != role_identity["classifier_version"]
        or _clean(role_semantic.get("role_family_id"))
        != role_identity["role_family_id"]
        or _clean(role_semantic.get("confidence")).lower()
        != role_identity["confidence"]
        or _clean(role_semantic.get("classifier_version"))
        != role_identity["classifier_version"]
    ):
        raise Phase9FBRankingError(
            "The exact JD role-family classification is stale.",
            code="exact_jd_role_family_mismatch",
        )

    return {
        "raw_text": raw_text,
        "jd_profile": deepcopy(profile),
        "canonical_requirements": deepcopy(rows),
        "acronym_map": deepcopy(canonicalisation.get("acronym_map") or {}),
        "semantic_identity": {
            "raw_jd_sha256": raw_hash,
            "structured_profile_fingerprint": profile_fingerprint,
            "canonical_requirement_fingerprint": requirement_fingerprint,
            "canonical_requirement_ids": requirement_ids,
            "role_family": role_identity,
        },
        "provenance": {
            "phase9f_a_snapshot_fingerprint": snapshot_fingerprint,
            "source_mode": _clean(exact_jd.get("source_type")),
            "library_jd_id": int(exact_jd.get("library_jd_id") or 0),
            "canonical_jd_id": _clean(exact_jd.get("canonical_jd_id")),
            "source_version_id": _clean(exact_jd.get("source_version_id")),
            "saved_source_version_id": _clean(
                (semantic.get("source") or {}).get("source_version_id")
            ),
            "source_url": str(exact_jd.get("source_url") or "").strip(),
            "source_filename": _clean(exact_jd.get("source_filename")),
            "source_artifact_sha256": _clean(
                exact_jd.get("source_artifact_sha256")
            ),
        },
    }


def normalize_base_resume_source(
    master: dict[str, Any],
    authoritative_artifact: dict[str, Any] | None,
) -> dict[str, Any]:
    source_type = "base_resume"
    source_id = _clean(master.get("master_version_id")) if isinstance(master, dict) else ""
    if not isinstance(master, dict) or not master:
        raise Phase9FBRankingError(
            "The current Base Resume row is missing.",
            code="base_resume_row_missing",
            source_type=source_type,
        )
    if not source_id or _clean(master.get("master_version_fingerprint"))[:32] != source_id:
        raise Phase9FBRankingError(
            "The current Base Resume ID does not match its version fingerprint.",
            code="base_resume_id_mismatch",
            source_type=source_type,
            source_id=source_id,
        )
    if (
        _clean(master.get("format_version")) != BASE_RESUME_FORMAT_VERSION
        or _clean(master.get("content_policy_version"))
        != BASE_RESUME_CONTENT_POLICY_VERSION
        or _clean(master.get("version_policy_version"))
        != BASE_RESUME_VERSION_POLICY_VERSION
    ):
        raise Phase9FBRankingError(
            "The current Base Resume format or identity policy is unsupported.",
            code="base_resume_policy_mismatch",
            source_type=source_type,
            source_id=source_id,
        )

    version_identity = master.get("version_identity")
    semantic_identity = master.get("semantic_identity")
    if (
        not isinstance(version_identity, dict)
        or fingerprint_value(version_identity)
        != _clean(master.get("master_version_fingerprint"))
    ):
        raise Phase9FBRankingError(
            "The current Base Resume version identity is corrupt.",
            code="base_resume_version_fingerprint_mismatch",
            source_type=source_type,
            source_id=source_id,
        )
    if (
        not isinstance(semantic_identity, dict)
        or fingerprint_value(semantic_identity)
        != _clean(master.get("master_content_fingerprint"))
    ):
        raise Phase9FBRankingError(
            "The current Base Resume content identity is corrupt.",
            code="base_resume_content_fingerprint_mismatch",
            source_type=source_type,
            source_id=source_id,
        )

    profile = _require_complete_profile(
        master.get("structured_profile"),
        source_type=source_type,
        source_id=source_id,
    )
    resume_text = str(master.get("resume_text") or "")
    profile_fingerprint = fingerprint_value(profile)
    resume_text_sha256 = _sha256_text(resume_text)
    if not resume_text.strip():
        raise Phase9FBRankingError(
            "The current Base Resume complete text is missing.",
            code="base_resume_text_missing",
            source_type=source_type,
            source_id=source_id,
        )
    if (
        profile_fingerprint != _clean(master.get("structured_profile_fingerprint"))
        or resume_text_sha256 != _clean(master.get("resume_text_sha256"))
        or len(resume_text) != int(master.get("resume_text_char_count") or -1)
    ):
        raise Phase9FBRankingError(
            "The current Base Resume frozen profile or text is corrupt.",
            code="base_resume_frozen_content_mismatch",
            source_type=source_type,
            source_id=source_id,
        )

    semantic_artifact = semantic_identity.get("artifact") or {}
    semantic_text = semantic_identity.get("resume_text") or {}
    if (
        _clean(semantic_identity.get("structured_profile_fingerprint"))
        != profile_fingerprint
        or _clean(semantic_text.get("resume_text_sha256"))
        != resume_text_sha256
        or int(semantic_text.get("resume_text_char_count") or -1)
        != len(resume_text)
        or _clean(semantic_artifact.get("artifact_sha256"))
        != _clean(master.get("artifact_sha256"))
    ):
        raise Phase9FBRankingError(
            "The current Base Resume semantic content does not match the row.",
            code="base_resume_semantic_content_mismatch",
            source_type=source_type,
            source_id=source_id,
        )

    if not isinstance(authoritative_artifact, dict):
        raise Phase9FBRankingError(
            "The current Base Resume authoritative artifact is missing.",
            code="base_resume_artifact_missing",
            source_type=source_type,
            source_id=source_id,
        )
    artifact_bytes = authoritative_artifact.get("artifact_bytes")
    if (
        authoritative_artifact.get("authoritative") is not True
        or _clean(authoritative_artifact.get("master_version_id")) != source_id
        or not isinstance(artifact_bytes, bytes)
        or len(artifact_bytes) != int(authoritative_artifact.get("byte_size") or -1)
        or _sha256_bytes(artifact_bytes)
        != _clean(authoritative_artifact.get("sha256"))
        or _clean(authoritative_artifact.get("sha256"))
        != _clean(master.get("artifact_sha256"))
    ):
        raise Phase9FBRankingError(
            "The current Base Resume authoritative artifact is corrupt.",
            code="base_resume_artifact_mismatch",
            source_type=source_type,
            source_id=source_id,
        )

    snapshot = master.get("master_snapshot")
    if (
        not isinstance(snapshot, dict)
        or _clean(snapshot.get("master_version_id")) != source_id
        or _clean(snapshot.get("master_version_fingerprint"))
        != _clean(master.get("master_version_fingerprint"))
        or fingerprint_value(snapshot.get("structured_profile"))
        != profile_fingerprint
        or _sha256_text(snapshot.get("resume_text")) != resume_text_sha256
    ):
        raise Phase9FBRankingError(
            "The current Base Resume immutable snapshot is corrupt.",
            code="base_resume_snapshot_mismatch",
            source_type=source_type,
            source_id=source_id,
        )

    source_identity = {
        "source_type": source_type,
        "source_id": source_id,
        "source_version": int(master.get("version_number") or 0),
        "source_version_fingerprint": _clean(
            master.get("master_version_fingerprint")
        ),
        "source_content_fingerprint": _clean(
            master.get("master_content_fingerprint")
        ),
        "resume_profile_fingerprint": profile_fingerprint,
        "resume_text_sha256": resume_text_sha256,
        "role_family_id": "",
    }
    return {
        "source_type": source_type,
        "source_id": source_id,
        "source_version": int(master.get("version_number") or 0),
        "source_fingerprint": _clean(master.get("master_version_fingerprint")),
        "source_content_fingerprint": _clean(
            master.get("master_content_fingerprint")
        ),
        "normalized_source_fingerprint": fingerprint_value(source_identity),
        "semantic_identity": source_identity,
        "display_name": _clean(master.get("display_name")) or "Base Resume",
        "role_family_id": "",
        "role_family_label": "",
        "resume_profile_snapshot": profile,
        "resume_text_snapshot": resume_text,
        "provenance": {
            "original_filename": _clean(master.get("original_filename")),
            "artifact_sha256": _clean(master.get("artifact_sha256")),
            "artifact_type": _clean(master.get("artifact_type")),
            "created_at": _clean(master.get("created_at")),
        },
    }


def normalize_active_blueprint_source(
    blueprint: dict[str, Any],
) -> dict[str, Any]:
    source_type = "global_blueprint"
    source_id = _clean(blueprint.get("blueprint_id")) if isinstance(blueprint, dict) else ""
    if not isinstance(blueprint, dict) or not blueprint:
        raise Phase9FBRankingError(
            "An active Global Blueprint row is missing.",
            code="active_blueprint_row_missing",
            source_type=source_type,
        )
    if _clean(blueprint.get("status")) != "active":
        raise Phase9FBRankingError(
            "Only an active Global Blueprint can be normalized for ranking.",
            code="blueprint_not_active",
            source_type=source_type,
            source_id=source_id,
        )
    if (
        _clean(blueprint.get("phase9d_version")) != BLUEPRINT_FORMAT_VERSION
        or _clean(blueprint.get("fingerprint_policy_version"))
        not in {
            BLUEPRINT_IDENTITY_POLICY_VERSION,
            LEGACY_BLUEPRINT_IDENTITY_POLICY_VERSION,
        }
    ):
        raise Phase9FBRankingError(
            "The active Global Blueprint format or identity policy is unsupported.",
            code="active_blueprint_policy_mismatch",
            source_type=source_type,
            source_id=source_id,
        )
    semantic = blueprint.get("semantic_identity")
    blueprint_fingerprint = _clean(blueprint.get("blueprint_fingerprint"))
    if (
        not isinstance(semantic, dict)
        or fingerprint_value(semantic) != blueprint_fingerprint
        or source_id != blueprint_fingerprint[:32]
    ):
        raise Phase9FBRankingError(
            "The active Global Blueprint identity is corrupt.",
            code="active_blueprint_fingerprint_mismatch",
            source_type=source_type,
            source_id=source_id,
        )

    snapshot = blueprint.get("blueprint_snapshot")
    frozen = snapshot.get("frozen_resume_snapshot") if isinstance(snapshot, dict) else None
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("semantic_identity") != semantic
        or not isinstance(frozen, dict)
    ):
        raise Phase9FBRankingError(
            "The active Global Blueprint immutable snapshot is missing or inconsistent.",
            code="active_blueprint_snapshot_missing",
            source_type=source_type,
            source_id=source_id,
        )
    profile = _require_complete_profile(
        frozen.get("resume_profile_snapshot"),
        source_type=source_type,
        source_id=source_id,
    )
    resume_text = str(frozen.get("resume_text_snapshot") or "")
    if not resume_text.strip():
        raise Phase9FBRankingError(
            "The active Global Blueprint frozen resume text is missing.",
            code="active_blueprint_text_missing",
            source_type=source_type,
            source_id=source_id,
        )
    profile_fingerprint = fingerprint_value(profile)
    resume_text_sha256 = _sha256_text(resume_text)
    complete_snapshot_fingerprint = fingerprint_value(frozen)
    resume_identity = semantic.get("resume_snapshot") or {}
    if (
        _clean(resume_identity.get("complete_snapshot_fingerprint"))
        != complete_snapshot_fingerprint
        or _clean(resume_identity.get("resume_profile_snapshot_fingerprint"))
        != profile_fingerprint
        or _clean(resume_identity.get("resume_text_snapshot_sha256"))
        != resume_text_sha256
    ):
        raise Phase9FBRankingError(
            "The active Global Blueprint frozen resume content is corrupt.",
            code="active_blueprint_frozen_content_mismatch",
            source_type=source_type,
            source_id=source_id,
        )

    role_semantic = semantic.get("role_family") or {}
    role_family_id = _clean(blueprint.get("role_family_id"))
    role_family_label = _clean(blueprint.get("role_family_label"))
    if (
        not role_family_id
        or role_family_id != _clean(snapshot.get("role_family_id"))
        or role_family_id != _clean(role_semantic.get("role_family_id"))
        or role_family_label != _clean(snapshot.get("role_family_label"))
        or role_family_label != _clean(role_semantic.get("role_family_label"))
    ):
        raise Phase9FBRankingError(
            "The active Global Blueprint role-family identity is corrupt.",
            code="active_blueprint_role_family_mismatch",
            source_type=source_type,
            source_id=source_id,
        )

    source_identity = {
        "source_type": source_type,
        "source_id": source_id,
        "source_version": int(blueprint.get("version_number") or 0),
        "source_version_fingerprint": blueprint_fingerprint,
        "source_content_fingerprint": complete_snapshot_fingerprint,
        "resume_profile_fingerprint": profile_fingerprint,
        "resume_text_sha256": resume_text_sha256,
        "role_family_id": role_family_id,
    }
    evaluation = snapshot.get("phase9c_evaluation_snapshot") or {}
    aggregate = evaluation.get("aggregate_result") or {}
    try:
        exact_reuse = validate_exact_verified_reuse_proof(
            blueprint.get("exact_verified_reuse_proof"),
            source_type=source_type,
            source_id=source_id,
            source_fingerprint=blueprint_fingerprint,
        )
    except Phase9FExactVerifiedReuseError as exc:
        raise Phase9FBRankingError(
            str(exc),
            code="exact_verified_reuse_proof_invalid",
            source_type=source_type,
            source_id=source_id,
        ) from exc
    return {
        "source_type": source_type,
        "source_id": source_id,
        "source_version": int(blueprint.get("version_number") or 0),
        "source_fingerprint": blueprint_fingerprint,
        "source_content_fingerprint": complete_snapshot_fingerprint,
        "normalized_source_fingerprint": fingerprint_value(source_identity),
        "semantic_identity": source_identity,
        "display_name": _clean(blueprint.get("display_name")) or role_family_label,
        "role_family_id": role_family_id,
        "role_family_label": role_family_label,
        "resume_profile_snapshot": profile,
        "resume_text_snapshot": resume_text,
        "provenance": {
            "phase9d_version": _clean(blueprint.get("phase9d_version")),
            "candidate_id": _clean(blueprint.get("candidate_id")),
            "evaluation_id": _clean(blueprint.get("evaluation_id")),
            "source_evaluation_provisional": aggregate.get("provisional") is True,
            "created_at": _clean(blueprint.get("created_at")),
        },
        "exact_verified_reuse": exact_reuse,
    }


def _source_observation(
    source_type: str,
    row: dict[str, Any] | None,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = row or {}
    artifact = artifact or {}
    frozen = (
        ((row.get("blueprint_snapshot") or {}).get("frozen_resume_snapshot") or {})
        if source_type == "global_blueprint"
        else {}
    )
    return {
        "source_type": source_type,
        "source_id": _clean(
            row.get("blueprint_id")
            if source_type == "global_blueprint"
            else row.get("master_version_id")
        ),
        "status": _clean(row.get("status")),
        "source_fingerprint": _clean(
            row.get("blueprint_fingerprint")
            if source_type == "global_blueprint"
            else row.get("master_version_fingerprint")
        ),
        "profile_observation_fingerprint": fingerprint_value(
            frozen.get("resume_profile_snapshot")
            if source_type == "global_blueprint"
            else row.get("structured_profile")
        ),
        "text_observation_sha256": _sha256_text(
            frozen.get("resume_text_snapshot")
            if source_type == "global_blueprint"
            else row.get("resume_text")
        ),
        "artifact_observation_sha256": (
            _sha256_bytes(artifact["artifact_bytes"])
            if isinstance(artifact.get("artifact_bytes"), bytes)
            else _clean(artifact.get("sha256"))
        ),
    }


def ranking_policy_identity() -> dict[str, Any]:
    return {
        "policy_version": PHASE9F_B_RANKING_POLICY_VERSION,
        "priority_order": [
            "exact_verified_reuse_precedence",
            "no_deal_breaker_gap",
            "fewer_deal_breaker_gaps",
            "required_core_coverage",
            "overall_canonical_alignment",
            "evidence_strength",
            "fewer_important_gaps",
            "preferred_coverage",
            "same_family_near_tie_prior",
            "stable_source_fingerprint",
        ],
        "role_family_prior_confidences": sorted(
            ROLE_FAMILY_PRIOR_CONFIDENCES
        ),
        "role_family_near_tie_tolerances": deepcopy(
            ROLE_FAMILY_NEAR_TIE_TOLERANCES
        ),
        "role_family_score_bonus": 0,
        "exact_verified_reuse": (
            "Exact current-JD/source artifact identity takes precedence; "
            "it is not a score or role-family bonus. Multiple valid exact "
            "proofs use immutable source identity only."
        ),
    }


def _exact_reuse_semantic_proof(
    proof: Any,
) -> dict[str, Any]:
    # Only exact-reuse state that can change B ordering is semantic.
    # Ineligible reason codes remain useful diagnostics, but switching from one
    # fail-closed reason to another cannot make a source more or less reusable
    # and therefore must not falsely stale B at D revalidation.
    state = (
        proof
        if isinstance(proof, dict)
        else ineligible_exact_verified_reuse("proof_unavailable")
    )
    eligible = state.get("eligible") is True
    return {
        "proof_version": _clean(state.get("proof_version")),
        "eligible": eligible,
        "proof_fingerprint": (
            _clean(state.get("proof_fingerprint")) if eligible else ""
        ),
    }


def prepare_ranking_context(
    *,
    exact_jd: dict[str, Any],
    current_base_resume: dict[str, Any] | None,
    current_base_artifact: dict[str, Any] | None,
    global_blueprints: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Validate and normalize one complete, read-only Phase 9F-B input scope."""
    jd = validate_exact_jd_snapshot(deepcopy(exact_jd))
    sources: list[dict[str, Any]] = []
    integrity_issues: list[dict[str, Any]] = []
    excluded_sources: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []

    if current_base_resume is not None:
        observations.append(
            _source_observation(
                "base_resume",
                current_base_resume,
                current_base_artifact,
            )
        )
        try:
            sources.append(
                normalize_base_resume_source(
                    deepcopy(current_base_resume),
                    deepcopy(current_base_artifact),
                )
            )
        except Phase9FBRankingError as exc:
            integrity_issues.append(deepcopy(exc.diagnostic))

    active_family_ids: set[str] = set()
    for blueprint in global_blueprints:
        if not isinstance(blueprint, dict):
            continue
        status = _clean(blueprint.get("status"))
        if status != "active":
            excluded_sources.append(
                {
                    "source_type": "global_blueprint",
                    "source_id": _clean(blueprint.get("blueprint_id")),
                    "status": status,
                    "reason": "superseded_or_inactive_blueprint",
                }
            )
            continue
        observations.append(_source_observation("global_blueprint", blueprint))
        role_family_id = _clean(blueprint.get("role_family_id"))
        if role_family_id in active_family_ids:
            integrity_issues.append(
                {
                    "code": "multiple_active_blueprints_for_role_family",
                    "message": (
                        "Multiple active Global Blueprints exist for one role family."
                    ),
                    "source_type": "global_blueprint",
                    "source_id": _clean(blueprint.get("blueprint_id")),
                }
            )
            continue
        active_family_ids.add(role_family_id)
        try:
            sources.append(normalize_active_blueprint_source(deepcopy(blueprint)))
        except Phase9FBRankingError as exc:
            integrity_issues.append(deepcopy(exc.diagnostic))

    sources.sort(
        key=lambda row: (
            row["source_type"],
            row["normalized_source_fingerprint"],
        )
    )
    observations.sort(
        key=lambda row: (
            row["source_type"],
            row["source_id"],
            row["source_fingerprint"],
        )
    )
    semantic_sources = [deepcopy(row["semantic_identity"]) for row in sources]
    exact_reuse_scope = [
        {
            "normalized_source_fingerprint": row["normalized_source_fingerprint"],
            "proof": _exact_reuse_semantic_proof(
                row.get("exact_verified_reuse")
                or ineligible_exact_verified_reuse("not_global_blueprint")
            ),
        }
        for row in sources
    ]
    duplicates = [
        value
        for value in {
            row["normalized_source_fingerprint"] for row in sources
        }
        if sum(
            row["normalized_source_fingerprint"] == value for row in sources
        )
        > 1
    ]
    if duplicates:
        integrity_issues.append(
            {
                "code": "duplicate_normalized_source_identity",
                "message": "The automatically eligible scope contains duplicate sources.",
                "source_type": "",
                "source_id": "",
            }
        )

    scoring_identity = {
        "scoring_policy_version": PHASE9F_B_SCORING_POLICY_VERSION,
        "scoring_version": SCORING_VERSION,
        "capability_taxonomy_version": get_default_taxonomy().version,
        "evidence_policy_version": PHASE9F_B_EVIDENCE_POLICY_VERSION,
        "retrieval_mode": "lexical",
        "fresh_target_only": True,
    }
    semantic_identity = {
        "format_version": PHASE9F_B_VERSION,
        "source_normalization_policy_version": (
            PHASE9F_B_SOURCE_POLICY_VERSION
        ),
        "exact_jd": deepcopy(jd["semantic_identity"]),
        "scoring": scoring_identity,
        "source_scope": semantic_sources,
        "exact_verified_reuse_scope": exact_reuse_scope,
        "ranking_policy": ranking_policy_identity(),
    }
    if integrity_issues:
        semantic_identity["invalid_source_observations"] = observations
    ranking_input_fingerprint = fingerprint_value(semantic_identity)
    status = (
        "integrity_failed"
        if integrity_issues
        else ("ready" if sources else "no_eligible_sources")
    )
    return {
        "status": status,
        "ranking_input_fingerprint": ranking_input_fingerprint,
        "semantic_identity": semantic_identity,
        "jd_provenance": deepcopy(jd["provenance"]),
        "source_provenance": [
            {
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "display_name": row["display_name"],
                **deepcopy(row["provenance"]),
            }
            for row in sources
        ],
        "integrity_issues": integrity_issues,
        "excluded_sources": excluded_sources,
        "_exact_jd": jd,
        "_normalized_sources": sources,
    }


def score_normalized_source(
    source: dict[str, Any],
    exact_jd: dict[str, Any],
) -> dict[str, Any]:
    """Run the Phase 9C fresh-target public scoring path for one source."""
    requirements = deepcopy(exact_jd["canonical_requirements"])
    keyword_match = build_deterministic_keyword_match(
        requirements=requirements,
        acronym_map=deepcopy(exact_jd["acronym_map"]),
        resume_profile=deepcopy(source["resume_profile_snapshot"]),
        raw_resume_text=str(source["resume_text_snapshot"]),
    )
    analysis = build_stable_analysis(
        jd_profile=deepcopy(exact_jd["jd_profile"]),
        keyword_match=keyword_match,
        raw_jd_text=str(exact_jd["raw_text"]),
        raw_resume_text=str(source["resume_text_snapshot"]),
        resume_profile=deepcopy(source["resume_profile_snapshot"]),
        retrieval_mode_override="lexical",
    )
    result_rows = [
        deepcopy(row)
        for row in analysis.get("canonical_requirements", []) or []
        if isinstance(row, dict)
    ]
    result_scope_fingerprint = canonical_requirement_scope_fingerprint(
        result_rows
    )
    expected_scope_fingerprint = exact_jd["semantic_identity"][
        "canonical_requirement_fingerprint"
    ]
    result_ids = sorted(
        _clean(row.get("requirement_id"))
        for row in result_rows
        if _clean(row.get("requirement_id"))
    )
    if (
        result_scope_fingerprint != expected_scope_fingerprint
        or result_ids
        != exact_jd["semantic_identity"]["canonical_requirement_ids"]
    ):
        raise Phase9FBRankingError(
            "Fresh scoring changed the frozen Phase 9F-A canonical requirement scope.",
            code="fresh_scoring_requirement_scope_mismatch",
            source_type=source["source_type"],
            source_id=source["source_id"],
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
    compact_results = [
        {
            "requirement_id": _clean(row.get("requirement_id")),
            "importance": _clean(row.get("importance")),
            "match_label": _clean(row.get("match_label")),
            "evidence_strength": int(row.get("evidence_strength") or 0),
        }
        for row in result_rows
    ]
    requirement_transparency = compact_requirement_transparency(
        result_rows,
        analysis.get("validation_warnings", []) or [],
    )
    scoring_identity = {
        "exact_jd": deepcopy(exact_jd["semantic_identity"]),
        "source": deepcopy(source["semantic_identity"]),
        "scoring_version": SCORING_VERSION,
        "capability_taxonomy_version": get_default_taxonomy().version,
        "evidence_policy_version": PHASE9F_B_EVIDENCE_POLICY_VERSION,
        "scoring_policy_version": PHASE9F_B_SCORING_POLICY_VERSION,
        "retrieval_mode": "lexical",
    }
    semantic_result = build_comparison_result_identity(
        canonical_requirement_results=compact_results,
        deterministic_alignment_score=int(
            analysis.get("deterministic_alignment_score") or 0
        ),
        required_core_coverage_score=int(
            analysis.get("required_core_coverage_score") or 0
        ),
        preferred_coverage_score=int(
            analysis.get("preferred_coverage_score") or 0
        ),
        evidence_strength_score=int(
            analysis.get("evidence_strength_score") or 0
        ),
        important_gaps=important_gaps,
    )
    candidate_analysis_snapshot = {
        "snapshot_version": PHASE9F_B_CANDIDATE_ANALYSIS_SNAPSHOT_VERSION,
        "source_identity": deepcopy(source["semantic_identity"]),
        "exact_jd_identity": deepcopy(exact_jd["semantic_identity"]),
        "resume_profile_snapshot": deepcopy(
            source["resume_profile_snapshot"]
        ),
        "resume_text_snapshot": str(source["resume_text_snapshot"]),
        "jd_profile_snapshot": deepcopy(exact_jd["jd_profile"]),
        "raw_jd_text_snapshot": str(exact_jd["raw_text"]),
        "keyword_match_snapshot": deepcopy(keyword_match),
        "stable_analysis_snapshot": deepcopy(analysis),
    }
    candidate_analysis_snapshot_fingerprint = fingerprint_value(
        candidate_analysis_snapshot
    )
    jd_role = exact_jd["semantic_identity"]["role_family"]
    if source["source_type"] == "base_resume":
        relationship = "neutral_base_resume"
    elif source["role_family_id"] == jd_role["role_family_id"]:
        relationship = "same_family"
    else:
        relationship = "cross_family"
    prior_eligible = bool(
        relationship == "same_family"
        and jd_role["confidence"] in ROLE_FAMILY_PRIOR_CONFIDENCES
    )
    return {
        "source_type": source["source_type"],
        "source_id": source["source_id"],
        "source_version": source["source_version"],
        "source_fingerprint": source["source_fingerprint"],
        "source_content_fingerprint": source["source_content_fingerprint"],
        "normalized_source_fingerprint": source[
            "normalized_source_fingerprint"
        ],
        "source_display_name": source["display_name"],
        "source_role_family_id": source["role_family_id"],
        "source_role_family_label": source["role_family_label"],
        "role_family_relationship": relationship,
        "role_family_prior_eligible": prior_eligible,
        "role_family_prior_applied": False,
        "ranking_reason": "canonical_metrics_order",
        "current_jd_alignment": semantic_result[
            "deterministic_alignment_score"
        ],
        "deterministic_alignment_score": semantic_result[
            "deterministic_alignment_score"
        ],
        "required_core_coverage_score": semantic_result[
            "required_core_coverage_score"
        ],
        "preferred_coverage_score": semantic_result[
            "preferred_coverage_score"
        ],
        "evidence_strength_score": semantic_result[
            "evidence_strength_score"
        ],
        "important_gap_count": len(important_gaps),
        "deal_breaker_gap_count": sum(
            row["importance"] == "deal_breaker" for row in important_gaps
        ),
        "important_gaps": important_gaps,
        "canonical_requirement_results": compact_results,
        # Transparency is deliberately outside semantic_result and therefore
        # cannot change comparison_result_fingerprint or ranking identity.
        "canonical_requirement_transparency": requirement_transparency,
        "canonical_requirement_scope_fingerprint": (
            result_scope_fingerprint
        ),
        "stable_input_fingerprint": fingerprint_value(scoring_identity),
        "stable_analysis_input_fingerprint": _clean(
            analysis.get("input_fingerprint")
        ),
        "comparison_result_fingerprint": fingerprint_value(semantic_result),
        # Captured from this existing scoring pass. These fields deliberately
        # remain outside RANKING_RESULT_IDENTITY_FIELDS, so adding the complete
        # snapshot cannot change Phase 9F-B ranking semantics or fingerprints.
        "candidate_analysis_snapshot": candidate_analysis_snapshot,
        "candidate_analysis_snapshot_fingerprint": (
            candidate_analysis_snapshot_fingerprint
        ),
        "scoring_version": SCORING_VERSION,
        "capability_taxonomy_version": get_default_taxonomy().version,
        "evidence_policy_version": PHASE9F_B_EVIDENCE_POLICY_VERSION,
        "exact_verified_reuse_eligible": bool(
            (source.get("exact_verified_reuse") or {}).get("eligible")
        ),
        "exact_verified_reuse_reason_code": _clean(
            (source.get("exact_verified_reuse") or {}).get("reason_code")
        ),
        "exact_verified_reuse_proof_fingerprint": _clean(
            (source.get("exact_verified_reuse") or {}).get("proof_fingerprint")
        ),
        "exact_verified_reuse": deepcopy(
            source.get("exact_verified_reuse")
            or ineligible_exact_verified_reuse("not_global_blueprint")
        ),
    }


def _strict_ranking_key(row: dict[str, Any]) -> tuple[Any, ...]:
    deal_breakers = int(row.get("deal_breaker_gap_count") or 0)
    return (
        0 if deal_breakers == 0 else 1,
        deal_breakers,
        -int(row.get("required_core_coverage_score") or 0),
        -int(row.get("deterministic_alignment_score") or 0),
        -int(row.get("evidence_strength_score") or 0),
        int(row.get("important_gap_count") or 0),
        -int(row.get("preferred_coverage_score") or 0),
        _clean(row.get("normalized_source_fingerprint")),
    )


def _within_role_family_near_tie(
    candidate: dict[str, Any],
    anchor: dict[str, Any],
) -> bool:
    if not candidate.get("role_family_prior_eligible"):
        return False
    tolerances = ROLE_FAMILY_NEAR_TIE_TOLERANCES
    if int(candidate.get("deal_breaker_gap_count") or 0) != int(
        anchor.get("deal_breaker_gap_count") or 0
    ):
        return False
    if (
        int(anchor.get("required_core_coverage_score") or 0)
        - int(candidate.get("required_core_coverage_score") or 0)
        > tolerances["required_core_coverage_points"]
    ):
        return False
    if (
        int(anchor.get("deterministic_alignment_score") or 0)
        - int(candidate.get("deterministic_alignment_score") or 0)
        > tolerances["overall_alignment_points"]
    ):
        return False
    if (
        int(anchor.get("evidence_strength_score") or 0)
        - int(candidate.get("evidence_strength_score") or 0)
        > tolerances["evidence_strength_points"]
    ):
        return False
    if (
        int(candidate.get("important_gap_count") or 0)
        - int(anchor.get("important_gap_count") or 0)
        > tolerances["important_gap_count"]
    ):
        return False
    if (
        int(anchor.get("preferred_coverage_score") or 0)
        - int(candidate.get("preferred_coverage_score") or 0)
        > tolerances["preferred_coverage_points"]
    ):
        return False
    return True


def order_scored_candidates(
    scored_candidates: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply the deterministic comparator and calibrated family prior."""
    exact = sorted(
        (
            deepcopy(row)
            for row in scored_candidates
            if row.get("exact_verified_reuse_eligible") is True
        ),
        key=lambda row: _clean(row.get("normalized_source_fingerprint")),
    )
    ordinary_input = [
        deepcopy(row)
        for row in scored_candidates
        if row.get("exact_verified_reuse_eligible") is not True
    ]
    if exact:
        for row in exact:
            row["role_family_prior_applied"] = False
            row["ranking_reason"] = "exact_verified_reuse_precedence"
        ordinary = order_scored_candidates(ordinary_input) if ordinary_input else []
        ordered = exact + ordinary
        for index, row in enumerate(ordered, start=1):
            row["rank"] = index
        return ordered

    remaining = sorted(
        ordinary_input,
        key=_strict_ranking_key,
    )
    ordered: list[dict[str, Any]] = []
    while remaining:
        anchor = remaining[0]
        near_tied_same_family = [
            row
            for row in remaining
            if _within_role_family_near_tie(row, anchor)
        ]
        selected = (
            sorted(near_tied_same_family, key=_strict_ranking_key)[0]
            if near_tied_same_family
            else anchor
        )
        if selected["normalized_source_fingerprint"] != anchor[
            "normalized_source_fingerprint"
        ]:
            selected["role_family_prior_applied"] = True
            selected["ranking_reason"] = (
                "same_family_prior_within_calibrated_near_tie"
            )
        elif not ordered:
            selected["ranking_reason"] = "best_canonical_metrics"
        ordered.append(selected)
        selected_fingerprint = selected["normalized_source_fingerprint"]
        remaining = [
            row
            for row in remaining
            if row["normalized_source_fingerprint"] != selected_fingerprint
        ]

    for index, row in enumerate(ordered, start=1):
        row["rank"] = index
    return ordered


def _public_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in context.items()
        if not key.startswith("_")
    }


def build_comparison_result_identity(
    *,
    canonical_requirement_results: Iterable[dict[str, Any]],
    deterministic_alignment_score: int,
    required_core_coverage_score: int,
    preferred_coverage_score: int,
    evidence_strength_score: int,
    important_gaps: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Build the authoritative semantic identity for one fresh comparison."""
    return {
        "canonical_requirement_results": deepcopy(
            list(canonical_requirement_results)
        ),
        "deterministic_alignment_score": int(
            deterministic_alignment_score
        ),
        "required_core_coverage_score": int(required_core_coverage_score),
        "preferred_coverage_score": int(preferred_coverage_score),
        "evidence_strength_score": int(evidence_strength_score),
        "important_gaps": deepcopy(list(important_gaps)),
    }


def validate_ranked_candidate_comparison_contract(
    candidate: Any,
) -> dict[str, Any]:
    """Validate one Phase 9F-B candidate comparison without rescoring it."""
    if not isinstance(candidate, dict):
        raise Phase9FBRankingError(
            "The Phase 9F-B ranked candidate is missing.",
            code="ranked_candidate_missing",
        )
    try:
        identity = build_comparison_result_identity(
            canonical_requirement_results=candidate[
                "canonical_requirement_results"
            ],
            deterministic_alignment_score=candidate[
                "deterministic_alignment_score"
            ],
            required_core_coverage_score=candidate[
                "required_core_coverage_score"
            ],
            preferred_coverage_score=candidate[
                "preferred_coverage_score"
            ],
            evidence_strength_score=candidate["evidence_strength_score"],
            important_gaps=candidate["important_gaps"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise Phase9FBRankingError(
            "The Phase 9F-B candidate comparison is incomplete.",
            code="ranked_candidate_comparison_incomplete",
        ) from exc
    expected = fingerprint_value(identity)
    if _clean(candidate.get("comparison_result_fingerprint")) != expected:
        raise Phase9FBRankingError(
            "The Phase 9F-B candidate comparison fingerprint is inconsistent.",
            code="ranked_candidate_comparison_fingerprint_mismatch",
        )
    return {
        "comparison_identity": identity,
        "comparison_result_fingerprint": expected,
    }


def validate_ranked_candidate_analysis_snapshot(
    candidate: Any,
) -> dict[str, Any]:
    """Validate a complete retained candidate analysis without rescoring."""
    validated_comparison = validate_ranked_candidate_comparison_contract(
        candidate
    )
    snapshot = candidate.get("candidate_analysis_snapshot")
    if not isinstance(snapshot, dict):
        raise Phase9FBRankingError(
            "The Phase 9F-B candidate analysis snapshot is missing.",
            code="candidate_analysis_snapshot_missing",
        )
    if _clean(snapshot.get("snapshot_version")) != (
        PHASE9F_B_CANDIDATE_ANALYSIS_SNAPSHOT_VERSION
    ):
        raise Phase9FBRankingError(
            "The Phase 9F-B candidate analysis snapshot version is unsupported.",
            code="candidate_analysis_snapshot_version_unsupported",
        )
    expected_fingerprint = fingerprint_value(snapshot)
    if _clean(candidate.get("candidate_analysis_snapshot_fingerprint")) != (
        expected_fingerprint
    ):
        raise Phase9FBRankingError(
            "The Phase 9F-B candidate analysis snapshot fingerprint is inconsistent.",
            code="candidate_analysis_snapshot_fingerprint_mismatch",
        )

    source_identity = snapshot.get("source_identity")
    exact_jd_identity = snapshot.get("exact_jd_identity")
    profile = snapshot.get("resume_profile_snapshot")
    resume_text = snapshot.get("resume_text_snapshot")
    jd_profile = snapshot.get("jd_profile_snapshot")
    raw_jd_text = snapshot.get("raw_jd_text_snapshot")
    keyword_match = snapshot.get("keyword_match_snapshot")
    analysis = snapshot.get("stable_analysis_snapshot")
    if not all(
        isinstance(value, dict)
        for value in (
            source_identity,
            exact_jd_identity,
            profile,
            jd_profile,
            keyword_match,
            analysis,
        )
    ) or not isinstance(resume_text, str) or not isinstance(raw_jd_text, str):
        raise Phase9FBRankingError(
            "The Phase 9F-B candidate analysis snapshot is incomplete.",
            code="candidate_analysis_snapshot_incomplete",
        )

    source_fields = {
        "source_type": candidate.get("source_type"),
        "source_id": candidate.get("source_id"),
        "source_version": candidate.get("source_version"),
        "source_version_fingerprint": candidate.get("source_fingerprint"),
        "source_content_fingerprint": candidate.get(
            "source_content_fingerprint"
        ),
    }
    if any(source_identity.get(key) != value for key, value in source_fields.items()):
        raise Phase9FBRankingError(
            "The retained analysis belongs to a different immutable source.",
            code="candidate_analysis_source_identity_mismatch",
        )
    if fingerprint_value(source_identity) != _clean(
        candidate.get("normalized_source_fingerprint")
    ):
        raise Phase9FBRankingError(
            "The retained analysis normalized-source identity is inconsistent.",
            code="candidate_analysis_normalized_source_mismatch",
        )
    if fingerprint_value(profile) != _clean(
        source_identity.get("resume_profile_fingerprint")
    ) or _sha256_text(resume_text) != _clean(
        source_identity.get("resume_text_sha256")
    ):
        raise Phase9FBRankingError(
            "The retained analysis resume profile or text is inconsistent.",
            code="candidate_analysis_resume_content_mismatch",
        )

    analysis_rows = [
        row
        for row in analysis.get("canonical_requirements", []) or []
        if isinstance(row, dict)
    ]
    compact_rows = [
        {
            "requirement_id": _clean(row.get("requirement_id")),
            "importance": _clean(row.get("importance")),
            "match_label": _clean(row.get("match_label")),
            "evidence_strength": int(row.get("evidence_strength") or 0),
        }
        for row in analysis_rows
    ]
    if compact_rows != validated_comparison["comparison_identity"][
        "canonical_requirement_results"
    ]:
        raise Phase9FBRankingError(
            "The retained analysis canonical outcomes differ from the ranked comparison.",
            code="candidate_analysis_outcome_mismatch",
        )
    metric_fields = (
        "deterministic_alignment_score",
        "required_core_coverage_score",
        "preferred_coverage_score",
        "evidence_strength_score",
    )
    if any(
        int(analysis.get(field) or 0) != int(candidate.get(field) or 0)
        for field in metric_fields
    ):
        raise Phase9FBRankingError(
            "The retained analysis metrics differ from the ranked comparison.",
            code="candidate_analysis_metric_mismatch",
        )
    if _clean(analysis.get("input_fingerprint")) != _clean(
        candidate.get("stable_analysis_input_fingerprint")
    ):
        raise Phase9FBRankingError(
            "The retained stable-analysis input fingerprint is inconsistent.",
            code="candidate_analysis_input_fingerprint_mismatch",
        )
    if canonical_requirement_scope_fingerprint(analysis_rows) != _clean(
        candidate.get("canonical_requirement_scope_fingerprint")
    ) or _clean(exact_jd_identity.get("canonical_requirement_fingerprint")) != _clean(
        candidate.get("canonical_requirement_scope_fingerprint")
    ):
        raise Phase9FBRankingError(
            "The retained analysis canonical requirement scope is inconsistent.",
            code="candidate_analysis_requirement_scope_mismatch",
        )
    if _sha256_text(raw_jd_text) != _clean(
        exact_jd_identity.get("raw_jd_sha256")
    ) or fingerprint_value(jd_profile) != _clean(
        exact_jd_identity.get("structured_profile_fingerprint")
    ):
        raise Phase9FBRankingError(
            "The retained analysis exact-JD content is inconsistent.",
            code="candidate_analysis_exact_jd_mismatch",
        )
    return {
        "candidate_analysis_snapshot": deepcopy(snapshot),
        "candidate_analysis_snapshot_fingerprint": expected_fingerprint,
    }


def build_ranking_result_identity(
    *,
    ranking_input_fingerprint: str,
    ranked_candidates: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Build the authoritative Phase 9F-B result identity without reranking."""
    rows = list(ranked_candidates)
    if not rows:
        raise Phase9FBRankingError(
            "A ranked Phase 9F-B result requires at least one candidate.",
            code="ranked_candidate_scope_empty",
        )
    try:
        semantic_ranked = [
            {key: row[key] for key in RANKING_RESULT_IDENTITY_FIELDS}
            for row in rows
        ]
    except (KeyError, TypeError) as exc:
        raise Phase9FBRankingError(
            "A ranked candidate is missing authoritative identity fields.",
            code="ranked_candidate_identity_incomplete",
        ) from exc
    return {
        "ranking_input_fingerprint": ranking_input_fingerprint,
        "ranked_candidates": semantic_ranked,
        "recommended_normalized_source_fingerprint": rows[0][
            "normalized_source_fingerprint"
        ],
    }


def validate_ranked_result_contract(
    result: Any,
    *,
    expected_ranking_input_fingerprint: str,
) -> dict[str, Any]:
    """Validate one current Phase 9F-B result without scoring or reranking."""
    if not isinstance(result, dict):
        raise Phase9FBRankingError(
            "The Phase 9F-B ranking result is missing.",
            code="ranking_result_missing",
        )
    if _clean(result.get("phase9f_b_version")) != PHASE9F_B_VERSION:
        raise Phase9FBRankingError(
            "The Phase 9F-B ranking result version is unsupported.",
            code="ranking_result_version_unsupported",
        )
    if _clean(result.get("status")) != "ranked":
        raise Phase9FBRankingError(
            "The Phase 9F-B result has no valid ranked winner.",
            code="ranking_result_not_ranked",
        )
    expected_input = _clean(expected_ranking_input_fingerprint)
    actual_input = _clean(result.get("ranking_input_fingerprint"))
    if not expected_input or actual_input != expected_input:
        raise Phase9FBRankingError(
            "The Phase 9F-B result is stale for the current semantic input.",
            code="ranking_result_stale",
        )
    semantic_identity = result.get("semantic_identity")
    if (
        not isinstance(semantic_identity, dict)
        or fingerprint_value(semantic_identity) != actual_input
    ):
        raise Phase9FBRankingError(
            "The Phase 9F-B ranking-input fingerprint is inconsistent.",
            code="ranking_input_fingerprint_mismatch",
        )

    rows = result.get("ranked_candidates")
    winner = result.get("recommended_source")
    if not isinstance(rows, list) or not rows or not all(
        isinstance(row, dict) for row in rows
    ):
        raise Phase9FBRankingError(
            "The Phase 9F-B ranked candidate scope is invalid.",
            code="ranked_candidate_scope_invalid",
        )
    expected_ranks = list(range(1, len(rows) + 1))
    try:
        actual_ranks = [int(row.get("rank") or 0) for row in rows]
    except (TypeError, ValueError) as exc:
        raise Phase9FBRankingError(
            "The Phase 9F-B candidate ranks are invalid.",
            code="ranked_candidate_order_invalid",
        ) from exc
    if actual_ranks != expected_ranks:
        raise Phase9FBRankingError(
            "The Phase 9F-B candidate ranks are ambiguous or incomplete.",
            code="ranked_candidate_order_invalid",
        )
    normalized = [
        _clean(row.get("normalized_source_fingerprint")) for row in rows
    ]
    if any(not value for value in normalized) or len(set(normalized)) != len(
        normalized
    ):
        raise Phase9FBRankingError(
            "The Phase 9F-B winner scope has duplicate or missing identities.",
            code="ranked_candidate_identity_ambiguous",
        )
    if not isinstance(winner, dict) or winner != rows[0]:
        raise Phase9FBRankingError(
            "The Phase 9F-B recommended source does not match rank one.",
            code="ranking_winner_mismatch",
        )

    identity = build_ranking_result_identity(
        ranking_input_fingerprint=actual_input,
        ranked_candidates=rows,
    )
    expected_result_fingerprint = fingerprint_value(identity)
    if _clean(result.get("ranking_fingerprint")) != expected_result_fingerprint:
        raise Phase9FBRankingError(
            "The Phase 9F-B ranking fingerprint is inconsistent.",
            code="ranking_result_fingerprint_mismatch",
        )
    return {
        "ranking_identity": identity,
        "ranking_fingerprint": expected_result_fingerprint,
        "recommended_source": deepcopy(winner),
    }


def rank_prepared_context(context: dict[str, Any]) -> dict[str, Any]:
    """Score a prepared context or return its fail-closed status."""
    public = _public_context(context)
    base_result = {
        "phase9f_b_version": PHASE9F_B_VERSION,
        **public,
        "recommended_source": None,
        "ranked_candidates": [],
        "zero_cost_diagnostics": {
            "model_call_count": 0,
            "embedding_call_count": 0,
            "chroma_read_count": 0,
            "chroma_write_count": 0,
            "persistence_write_count": 0,
        },
    }
    if context.get("status") != "ready":
        failure_identity = {
            "ranking_input_fingerprint": context.get(
                "ranking_input_fingerprint"
            ),
            "status": context.get("status"),
            "integrity_issues": context.get("integrity_issues") or [],
        }
        base_result["ranking_fingerprint"] = fingerprint_value(
            failure_identity
        )
        return base_result

    scored = []
    try:
        for source in context["_normalized_sources"]:
            scored.append(
                score_normalized_source(source, context["_exact_jd"])
            )
    except Phase9FBRankingError as exc:
        base_result["status"] = "integrity_failed"
        base_result["integrity_issues"] = [deepcopy(exc.diagnostic)]
        base_result["ranking_fingerprint"] = fingerprint_value(
            {
                "ranking_input_fingerprint": context.get(
                    "ranking_input_fingerprint"
                ),
                "status": "integrity_failed",
                "integrity_issues": base_result["integrity_issues"],
            }
        )
        return base_result

    ordered = order_scored_candidates(scored)
    ranking_identity = build_ranking_result_identity(
        ranking_input_fingerprint=context["ranking_input_fingerprint"],
        ranked_candidates=ordered,
    )
    base_result.update(
        {
            "status": "ranked",
            "ranked_candidates": ordered,
            "recommended_source": deepcopy(ordered[0]),
            "ranking_fingerprint": fingerprint_value(ranking_identity),
        }
    )
    return base_result


def rank_starting_resume_sources(
    *,
    exact_jd: dict[str, Any],
    current_base_resume: dict[str, Any] | None,
    current_base_artifact: dict[str, Any] | None,
    global_blueprints: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Prepare and rank the complete automatically eligible source scope."""
    context = prepare_ranking_context(
        exact_jd=exact_jd,
        current_base_resume=current_base_resume,
        current_base_artifact=current_base_artifact,
        global_blueprints=global_blueprints,
    )
    return rank_prepared_context(context)

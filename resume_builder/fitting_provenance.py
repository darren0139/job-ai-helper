"""Durable provenance for deterministic Phase 6C fit searches."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

# This identifies the search procedure that chose a rendered candidate.  It is
# intentionally separate from both the evidence-reduction contract and the
# render-state fingerprint: identical layout states remain render-cacheable.
PHASE6C_SEARCH_ALGORITHM_VERSION = (
    "phase6c-bounded-coarse-exact-fitting-v1"
)

# Historical Phase 6C.1 results used an exhaustive lowest-tier tournament and
# recorded this render-optimizer value in ``fitting_optimization_version``.
PHASE6C_LEGACY_EXHAUSTIVE_SEARCH_ALGORITHM_VERSION = (
    "phase6c-exhaustive-tiered-render-search-v1"
)
PHASE6C_LEGACY_EXHAUSTIVE_FITTING_OPTIMIZATION_VERSION = (
    "phase6c1-exact-safe-render-v1"
)
UNKNOWN_LEGACY_FITTING_SEARCH_ALGORITHM_VERSION = "unknown_legacy"

# A completed fit needs enough durable material to identify the *actual*
# deterministic invocation.  This is deliberately separate from a render
# state fingerprint: changing the search procedure must not invalidate a
# cache entry for an otherwise identical layout state.
FITTING_INPUT_SNAPSHOT_VERSION = "phase6c-fitting-input-snapshot-v2"
FITTING_INPUT_FINGERPRINT_VERSION = "phase6c-fitting-input-fingerprint-v1"


def _canonical_value(value: Any) -> Any:
    """Return JSON-safe deterministic data without changing list order/text."""
    if isinstance(value, dict):
        return {
            str(key): _canonical_value(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return deepcopy(value)
    return str(value)


_PROJECT_RENDER_FIELDS = (
    "title",
    "project_name",
    "name",
    "display_title",
    "subtitle",
    "resume_header_tools",
    "resume_header_context",
    "canonical_tools",
    "tools",
    "technologies",
    "tech_stack",
    "period",
    "draft_bullets",
    "compact_bullets",
)
_PROJECT_DECISION_FIELDS = (
    "priority",
    "project_fit_score",
    "matched_jd_requirements",
    "transferable_jd_requirements",
    "space_action",
)
_BULLET_EVIDENCE_FIELDS = (
    "bullet_index",
    "bullet_text",
    "supported_requirement_ids",
    "protected_requirement_ids",
    "unique_required_core_count",
    "evidence_value",
    "protect_during_fitting",
    "evidence_priority",
)
_SKILL_PRIORITY_FIELDS = (
    "skill",
    "jd_relevance",
    "evidence_strength",
    "required_match",
    "preferred_match",
)


def _canonical_project(project: Any) -> dict[str, Any] | None:
    if not isinstance(project, dict):
        return None
    result = {
        key: _canonical_value(project.get(key))
        for key in (*_PROJECT_RENDER_FIELDS, *_PROJECT_DECISION_FIELDS)
        if key in project
    }
    result["bullet_evidence_priorities"] = [
        {
            key: _canonical_value(row.get(key))
            for key in _BULLET_EVIDENCE_FIELDS
            if key in row
        }
        for row in project.get("bullet_evidence_priorities", []) or []
        if isinstance(row, dict)
    ]
    return result


def canonicalize_fitting_projects(
    projects: dict[str, Any] | None,
) -> dict[str, Any]:
    """Allowlist exactly the Projects fields the current fitter can observe.

    The output deliberately excludes generator/UI/debug payloads while keeping
    header fields, all displayed bullets, compact alternatives, and every
    Phase 6C evidence/protection input that affects candidate ordering.
    """
    source = projects if isinstance(projects, dict) else {}
    allocation = (
        ((source.get("deterministic_rule_debug") or {}).get("bullet_allocation"))
        if isinstance(source.get("deterministic_rule_debug"), dict)
        else {}
    )
    result = {
        "recommended_projects": [
            canonical
            for project in source.get("recommended_projects", []) or []
            if (canonical := _canonical_project(project)) is not None
        ],
    }
    if isinstance(allocation, dict) and "allocation_mode" in allocation:
        result["deterministic_rule_debug"] = {
            "bullet_allocation": {
                "allocation_mode": _canonical_value(
                    allocation.get("allocation_mode")
                )
            }
        }
    return result


def canonicalize_fitting_skills(
    skills: dict[str, Any] | None,
) -> dict[str, Any]:
    """Allowlist Skills fields used for rendering and deterministic removal."""
    source = skills if isinstance(skills, dict) else {}
    return {
        "skill_lines": [
            {
                key: _canonical_value(row.get(key))
                for key in ("category", "items")
                if key in row
            }
            for row in source.get("skill_lines", []) or []
            if isinstance(row, dict)
        ],
        "skill_priorities": [
            {
                key: _canonical_value(row.get(key))
                for key in _SKILL_PRIORITY_FIELDS
                if key in row
            }
            for row in source.get("skill_priorities", []) or []
            if isinstance(row, dict)
        ],
    }


def fitting_input_fingerprint(snapshot: dict[str, Any]) -> str:
    """Fingerprint the canonical Phase 6C invocation, excluding its own key."""
    payload = {
        key: value
        for key, value in snapshot.items()
        if key != "fitting_input_fingerprint"
    }
    encoded = json.dumps(
        _canonical_value(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_source_artifact_identity(
    *,
    source_docx_sha256: str,
    source_docx_byte_size: int,
    source_artifact_identity: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the exact source identity used by one fitter invocation.

    Phase 9F passes its already-validated immutable artifact identity here.
    Other callers still get the same sha256/byte-size contract without
    inventing a separate path-based identity scheme.
    """
    sha256 = str(source_docx_sha256 or "").strip().lower()
    try:
        byte_size = int(source_docx_byte_size)
    except (TypeError, ValueError) as exc:
        raise ValueError("source_docx_byte_size must be an integer") from exc
    if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
        raise ValueError("source_docx_sha256 must be a SHA-256 value")
    if byte_size < 0:
        raise ValueError("source_docx_byte_size must be non-negative")

    supplied = (
        source_artifact_identity
        if isinstance(source_artifact_identity, dict)
        else {}
    )
    supplied_sha256 = str(supplied.get("sha256") or "").strip().lower()
    supplied_size = supplied.get("byte_size")
    if supplied_sha256 and supplied_sha256 != sha256:
        raise ValueError("source artifact SHA-256 does not match the fitter source")
    if supplied_size is not None:
        try:
            supplied_byte_size = int(supplied_size)
        except (TypeError, ValueError) as exc:
            raise ValueError("source artifact byte size must be an integer") from exc
        if supplied_byte_size != byte_size:
            raise ValueError(
                "source artifact byte size does not match the fitter source"
            )

    result = {
        key: deepcopy(supplied[key])
        for key in ("policy_version", "artifact_type")
        if supplied.get(key) not in (None, "")
    }
    result.update(
        {
            "artifact_type": str(result.get("artifact_type") or "docx").lower(),
            "sha256": sha256,
            "byte_size": byte_size,
        }
    )
    return result


def build_fitting_input_snapshot(
    *,
    source_docx_sha256: str,
    source_docx_byte_size: int,
    source_artifact_identity: dict[str, Any] | None,
    caller_projects: dict[str, Any] | None,
    caller_skills: dict[str, Any] | None,
    prepared_projects: dict[str, Any] | None,
    prepared_skills: dict[str, Any] | None,
    fitter_invocation: dict[str, Any],
    fitting_policy_version: str,
) -> dict[str, Any]:
    """Capture the canonical, replayable input to the deterministic fitter.

    ``fitter_invocation`` is supplied by the fitter itself after its effective
    arguments are known.  The builder intentionally does not substitute UI or
    current-default values, so a durable snapshot cannot silently describe a
    different future invocation.
    """
    invocation = (
        deepcopy(fitter_invocation)
        if isinstance(fitter_invocation, dict)
        else None
    )
    if invocation is None:
        raise ValueError("fitter_invocation must be a mapping")
    snapshot = {
        "snapshot_version": FITTING_INPUT_SNAPSHOT_VERSION,
        "fitting_input_fingerprint_version": FITTING_INPUT_FINGERPRINT_VERSION,
        "fitting_policy_version": str(fitting_policy_version or "").strip(),
        "fitting_search_algorithm_version": (
            PHASE6C_SEARCH_ALGORITHM_VERSION
        ),
        "source_artifact": _canonical_source_artifact_identity(
            source_docx_sha256=source_docx_sha256,
            source_docx_byte_size=source_docx_byte_size,
            source_artifact_identity=source_artifact_identity,
        ),
        "caller_input": {
            "projects": canonicalize_fitting_projects(caller_projects),
            "skills": canonicalize_fitting_skills(caller_skills),
        },
        "prepared_initial_state": {
            "projects": canonicalize_fitting_projects(prepared_projects),
            "skills": canonicalize_fitting_skills(prepared_skills),
        },
        "fitter_invocation": _canonical_value(invocation),
    }
    snapshot["fitting_input_fingerprint"] = fitting_input_fingerprint(snapshot)
    return snapshot


def resolve_fitting_search_algorithm_version(
    fit_result: dict[str, Any] | None,
) -> str:
    """Read fit-search provenance without treating a missing value as current.

    The compatibility mapping is deliberately narrow.  A historical result is
    recognised as exhaustive only when its prior optimizer version is known to
    identify that algorithm; all other missing values remain unknown.
    """
    result = fit_result if isinstance(fit_result, dict) else {}
    canonical = str(
        result.get("fitting_search_algorithm_version") or ""
    ).strip()
    if canonical:
        return canonical

    optimization_version = str(
        result.get("fitting_optimization_version") or ""
    ).strip()
    if optimization_version == PHASE6C_LEGACY_EXHAUSTIVE_FITTING_OPTIMIZATION_VERSION:
        return PHASE6C_LEGACY_EXHAUSTIVE_SEARCH_ALGORITHM_VERSION
    return UNKNOWN_LEGACY_FITTING_SEARCH_ALGORITHM_VERSION


def normalise_fitting_search_algorithm_provenance(
    fit_result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return a read-side normalised fit result without rewriting storage."""
    if not isinstance(fit_result, dict):
        return fit_result
    normalised = deepcopy(fit_result)
    normalised["fitting_search_algorithm_version"] = (
        resolve_fitting_search_algorithm_version(normalised)
    )
    return normalised

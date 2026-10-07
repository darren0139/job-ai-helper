"""Deterministic Initial-vs-Tailored Job Match comparison contracts.

This module wraps the existing stable scorer output.  It does not resolve
requirements, change labels, or recompute the production score.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from analysis_stability.stable_evidence_scoring import (
    MATCH_VALUES,
    requirement_is_score_eligible,
)
from job_discovery.matching import MATCH_VERSION, current_match_versions
from tailoring.capability_taxonomy import TAXONOMY_PATH
from tailoring.phase8_score_explainability import build_score_breakdown
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.technology_registry import REGISTRY_PATH


JOB_MATCH_AB_VERSION = "job-match-session-ab-v1"
MATCH_RANK = {"none": 0, "weak": 1, "transferable": 2, "direct": 3}
POSITIVE_MATCHES = {"weak", "transferable", "direct"}
COMPARABILITY_FIELDS = (
    "jd_fingerprint",
    "job_match_contract",
    "scoring_version",
    "taxonomy_version",
    "taxonomy_fingerprint",
    "registry_version",
    "registry_fingerprint",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _normalise_jd(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def production_knowledge_fingerprints() -> dict[str, str]:
    """Return the established TQ-D3 byte-level knowledge fingerprints."""
    return {
        "taxonomy_fingerprint": fingerprint(TAXONOMY_PATH.read_bytes().hex()),
        "registry_fingerprint": fingerprint(REGISTRY_PATH.read_bytes().hex()),
    }


def current_ab_identity(raw_jd_text: str = "") -> dict[str, str]:
    versions = current_match_versions()
    identity = {
        "jd_fingerprint": (
            hashlib.sha256(_normalise_jd(raw_jd_text).encode("utf-8")).hexdigest()
            if _normalise_jd(raw_jd_text)
            else ""
        ),
        "job_match_contract": str(
            versions.get("match_contract_version") or MATCH_VERSION
        ),
        "match_version": str(versions.get("match_version") or ""),
        "scoring_version": str(versions.get("scoring_version") or ""),
        "taxonomy_version": str(versions.get("taxonomy_version") or ""),
        "registry_version": str(
            versions.get("technology_registry_version") or ""
        ),
    }
    identity.update(production_knowledge_fingerprints())
    return identity


def _preliminary_labels(analysis: dict[str, Any]) -> dict[str, str]:
    """Recover the scorer's pre-taxonomy label from its own cap warning."""
    output: dict[str, str] = {}
    for warning in analysis.get("validation_warnings", []) or []:
        if not isinstance(warning, dict):
            continue
        requirement_id = _clean(warning.get("requirement_id"))
        message = _clean(warning.get("message")).lower()
        if not requirement_id or not message.startswith("phase 6d capped "):
            continue
        remainder = message.removeprefix("phase 6d capped ")
        label = remainder.split(" to ", 1)[0].strip()
        if label in MATCH_RANK:
            output[requirement_id] = label
    return output


def _evidence_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        deepcopy(item)
        for item in row.get("evidence", []) or []
        if isinstance(item, dict)
    ]


def _evidence_provenance(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "evidence_id",
        "source",
        "section",
        "text",
        "matched_resume_term",
        "reason",
        "evidence_similarity",
    )
    return [
        {key: deepcopy(item.get(key)) for key in fields if item.get(key) is not None}
        for item in evidence
    ]


def _provenance_is_grounded(evidence: list[dict[str, Any]]) -> bool:
    return bool(
        evidence
        and any(
            _clean(item.get("text") or item.get("matched_resume_term"))
            and _clean(item.get("source") or item.get("evidence_id"))
            for item in evidence
        )
    )


def _taxonomy_status(row: dict[str, Any]) -> str:
    cap = _clean(row.get("capability_taxonomy_cap_status")).lower()
    source = _clean(row.get("capability_resolution_source")).lower()
    registry = row.get("technology_registry_resolution") or {}
    if cap == "applied":
        return "taxonomy_capped"
    if source in {"canonical_taxonomy", "technology_registry"}:
        return "resolved"
    if _clean(registry.get("status")).lower() == "resolved":
        return "recognized_unmapped"
    if cap == "unrecognised":
        return "unresolved"
    return cap or "unavailable"


def build_job_match_snapshot(
    *,
    role: str,
    stable_analysis: dict[str, Any],
    raw_jd_text: str,
    generation_snapshot_fingerprint: str = "",
) -> dict[str, Any]:
    """Freeze one scorer output for A/B use without changing that output."""
    if role not in {"initial", "tailored"}:
        raise ValueError("Job Match A/B snapshot role must be initial or tailored.")
    if not isinstance(stable_analysis, dict) or not stable_analysis:
        raise ValueError(f"The {role} stable analysis is missing.")

    identity = current_ab_identity(raw_jd_text)
    identity.update(
        scoring_version=_clean(stable_analysis.get("scoring_version")),
        taxonomy_version=_clean(
            stable_analysis.get("capability_taxonomy_version")
        ),
        registry_version=_clean(
            stable_analysis.get("technology_registry_version")
        ),
        stable_input_fingerprint=_clean(
            stable_analysis.get("input_fingerprint")
        ),
    )
    points = {
        _clean(item.get("requirement_id")): item
        for item in build_score_breakdown(stable_analysis).get(
            "requirements", []
        )
        or []
        if isinstance(item, dict) and _clean(item.get("requirement_id"))
    }
    preliminary = _preliminary_labels(stable_analysis)
    requirements: list[dict[str, Any]] = []
    seen: set[str] = set()
    blockers: list[str] = []
    for row in stable_analysis.get("canonical_requirements", []) or []:
        if not isinstance(row, dict):
            blockers.append(f"{role}:corrupt_requirement_row")
            continue
        requirement_id = _clean(row.get("requirement_id"))
        if not requirement_id:
            blockers.append(f"{role}:missing_requirement_id")
            continue
        if requirement_id in seen:
            blockers.append(f"{role}:duplicate_requirement_id:{requirement_id}")
            continue
        seen.add(requirement_id)
        final_label = _clean(row.get("match_label")).lower() or "none"
        if final_label not in MATCH_RANK:
            blockers.append(f"{role}:invalid_match_label:{requirement_id}")
            final_label = "none"
        evidence = _evidence_rows(row)
        if final_label in POSITIVE_MATCHES and not _provenance_is_grounded(evidence):
            blockers.append(
                f"{role}:missing_grounded_evidence_provenance:{requirement_id}"
            )
        contribution = points.get(requirement_id) or {}
        requirements.append(
            {
                "requirement_id": requirement_id,
                "requirement_text": _clean(
                    row.get("text") or row.get("atomic_focus")
                ),
                "importance": _clean(row.get("importance")).lower(),
                "score_eligible": bool(requirement_is_score_eligible(row)),
                "preliminary_match": preliminary.get(
                    requirement_id, final_label
                ),
                "final_match": final_label,
                "match_value": float(
                    row.get("match_value", MATCH_VALUES.get(final_label, 0.0))
                    or 0.0
                ),
                "evidence_strength": int(row.get("evidence_strength", 0) or 0),
                "evidence": evidence,
                "evidence_provenance": _evidence_provenance(evidence),
                "score_contribution": float(
                    contribution.get("overall_point_contribution", 0.0) or 0.0
                ),
                "taxonomy_capability_id": _clean(row.get("capability_id")),
                "taxonomy_status": _taxonomy_status(row),
                "taxonomy_cap_status": _clean(
                    row.get("capability_taxonomy_cap_status")
                ),
                "taxonomy_resolution_source": _clean(
                    row.get("capability_resolution_source")
                ),
                "registry_resolution": deepcopy(
                    row.get("technology_registry_resolution") or {}
                ),
                "diagnostics": {
                    "capability_retrieval": deepcopy(
                        row.get("capability_retrieval") or {}
                    ),
                    "capability_does_not_prove": deepcopy(
                        row.get("capability_does_not_prove") or []
                    ),
                    "capability_none_recovery": deepcopy(
                        row.get("capability_none_recovery") or {}
                    ),
                    "match_source": row.get("match_source"),
                    "match_similarity": row.get("match_similarity"),
                    "match_coverage": row.get("match_coverage"),
                    "match_overlap_count": row.get("match_overlap_count"),
                },
            }
        )

    return {
        "snapshot_version": JOB_MATCH_AB_VERSION,
        "role": role,
        "identity": identity,
        "generation_snapshot_fingerprint": _clean(
            generation_snapshot_fingerprint
        ),
        "score": int(
            stable_analysis.get("deterministic_alignment_score", 0) or 0
        ),
        "match_counts": {
            label: sum(
                1 for row in requirements if row["final_match"] == label
            )
            for label in MATCH_RANK
        },
        "requirements": requirements,
        "integrity_blockers": sorted(set(blockers)),
        "stable_analysis": deepcopy(stable_analysis),
    }


def _identity_blockers(
    initial: dict[str, Any], tailored: dict[str, Any]
) -> list[str]:
    left = initial.get("identity") or {}
    right = tailored.get("identity") or {}
    blockers: list[str] = []
    for field in COMPARABILITY_FIELDS:
        if not _clean(left.get(field)) or not _clean(right.get(field)):
            blockers.append(f"missing_identity:{field}")
        elif _clean(left.get(field)) != _clean(right.get(field)):
            blockers.append(f"identity_mismatch:{field}")
    return blockers


def build_job_match_ab_analysis(
    initial: dict[str, Any],
    tailored: dict[str, Any],
) -> dict[str, Any]:
    """Compare immutable snapshots by stable requirement ID, failing closed."""
    blockers = [
        *list(initial.get("integrity_blockers") or []),
        *list(tailored.get("integrity_blockers") or []),
        *_identity_blockers(initial, tailored),
    ]
    before_rows = {
        _clean(row.get("requirement_id")): row
        for row in initial.get("requirements", []) or []
        if isinstance(row, dict) and _clean(row.get("requirement_id"))
    }
    after_rows = {
        _clean(row.get("requirement_id")): row
        for row in tailored.get("requirements", []) or []
        if isinstance(row, dict) and _clean(row.get("requirement_id"))
    }
    if set(before_rows) != set(after_rows):
        blockers.append("canonical_requirement_identity_mismatch")

    if blockers:
        return {
            "comparison_version": JOB_MATCH_AB_VERSION,
            "status": "incompatible",
            "comparable": False,
            "blockers": sorted(set(blockers)),
            "initial": deepcopy(initial),
            "tailored": deepcopy(tailored),
            "summary": {},
            "requirements": [],
        }

    rows: list[dict[str, Any]] = []
    counts = {name: 0 for name in ("IMPROVED", "PRESERVED", "LOST", "STILL_GAP")}
    for requirement_id in before_rows:
        left = before_rows[requirement_id]
        right = after_rows[requirement_id]
        before_label = _clean(left.get("final_match")).lower() or "none"
        after_label = _clean(right.get("final_match")).lower() or "none"
        before_rank = MATCH_RANK.get(before_label, 0)
        after_rank = MATCH_RANK.get(after_label, 0)
        if after_rank > before_rank:
            classification = "IMPROVED"
        elif before_rank > 0 and after_rank < before_rank:
            classification = "LOST"
        elif before_rank > 0 and after_rank > 0:
            classification = "PRESERVED"
        else:
            classification = "STILL_GAP"
        counts[classification] += 1
        before_points = float(left.get("score_contribution", 0.0) or 0.0)
        after_points = float(right.get("score_contribution", 0.0) or 0.0)
        rows.append(
            {
                "requirement_id": requirement_id,
                "requirement_text": right.get("requirement_text") or left.get("requirement_text"),
                "importance": right.get("importance") or left.get("importance"),
                "score_eligible": bool(right.get("score_eligible")),
                "classification": classification,
                "match_transition": f"{before_label} -> {after_label}",
                "score_contribution_delta": round(after_points - before_points, 6),
                "initial": deepcopy(left),
                "tailored": deepcopy(right),
            }
        )

    summary = {
        "initial_score": int(initial.get("score", 0) or 0),
        "tailored_score": int(tailored.get("score", 0) or 0),
        "score_delta": int(tailored.get("score", 0) or 0)
        - int(initial.get("score", 0) or 0),
        "requirements_improved": counts["IMPROVED"],
        "requirements_preserved": counts["PRESERVED"],
        "requirements_lost": counts["LOST"],
        "requirements_still_gaps": counts["STILL_GAP"],
        "initial_match_counts": deepcopy(initial.get("match_counts") or {}),
        "tailored_match_counts": deepcopy(tailored.get("match_counts") or {}),
    }
    payload = {
        "comparison_version": JOB_MATCH_AB_VERSION,
        "status": "comparable",
        "comparable": True,
        "blockers": [],
        "initial": deepcopy(initial),
        "tailored": deepcopy(tailored),
        "summary": summary,
        "requirements": rows,
    }
    payload["comparison_fingerprint"] = fingerprint(payload)
    return payload


def inspect_job_match_ab_lifecycle(
    analysis: dict[str, Any] | None,
    *,
    current_identity: dict[str, Any] | None = None,
    current_generation_snapshot_fingerprint: str = "",
) -> dict[str, Any]:
    """Return the explicit session A/B lifecycle state."""
    if not isinstance(analysis, dict) or not isinstance(analysis.get("initial"), dict):
        return {"state": "no_initial_analysis", "comparable": False, "reasons": ["initial_missing"]}
    if not isinstance(analysis.get("tailored"), dict):
        return {"state": "initial_available_no_tailored_analysis", "comparable": False, "reasons": ["tailored_missing"]}
    if analysis.get("comparable") is not True:
        return {"state": "initial_tailored_identities_incompatible", "comparable": False, "reasons": list(analysis.get("blockers") or ["comparison_incompatible"])}

    expected_generation = _clean(
        (analysis.get("tailored") or {}).get("generation_snapshot_fingerprint")
    )
    observed_generation = _clean(current_generation_snapshot_fingerprint)
    if observed_generation and observed_generation != expected_generation:
        return {"state": "tailored_analysis_stale", "comparable": False, "reasons": ["fitted_generation_changed"]}

    current = current_identity or current_ab_identity()
    initial_identity = (analysis.get("initial") or {}).get("identity") or {}
    superseded = [
        field
        for field in COMPARABILITY_FIELDS
        if field != "jd_fingerprint"
        and _clean(current.get(field))
        and _clean(current.get(field)) != _clean(initial_identity.get(field))
    ]
    if superseded:
        return {
            "state": "current_analysis_generation_superseded",
            "comparable": False,
            "reasons": [f"current_identity_changed:{field}" for field in superseded],
        }
    return {"state": "both_analyses_available_and_comparable", "comparable": True, "reasons": []}

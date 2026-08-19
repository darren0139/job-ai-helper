"""Deterministic evidence rediscovery for fresh resume-to-JD comparisons.

This module is intentionally scoped to FRESH target scoring. It does not
replace the canonical stable scorer and it never imports historical Phase 8
answers, generation mappings, Blueprint scores, Chroma, embeddings, or model
outputs.

The existing stable scorer runs first. This adapter then asks the existing
versioned Phase 6D capability taxonomy whether CURRENTLY VISIBLE resume
evidence independently supports requirements that the lexical path missed.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from analysis_stability.stable_evidence_scoring import (
    MATCH_VALUES,
    build_stable_analysis,
    compute_deterministic_alignment,
)
from tailoring.capability_taxonomy import evaluate_evidence, get_default_taxonomy


FRESH_TARGET_EVIDENCE_POLICY_VERSION = (
    "phase9f-phase9c-fresh-target-evidence-v2"
)
FRESH_EVIDENCE_REDISCOVERY_VERSION = (
    "phase6d-fresh-visible-evidence-rediscovery-v1"
)

_LABEL_ORDER = {"none": 0, "weak": 1, "transferable": 2, "direct": 3}
_EVIDENCE_STRENGTH = {"none": 0, "weak": 2, "transferable": 3, "direct": 5}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _normalise(value: Any) -> str:
    text = _clean(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#]+", " ", text)
    return " ".join(text.split())


def _append_evidence(
    rows: list[dict[str, str]],
    seen: set[str],
    *,
    section: str,
    source: str,
    text: Any,
) -> None:
    cleaned = _clean(text)
    key = _normalise(cleaned)
    if not cleaned or not key or key in seen:
        return
    seen.add(key)
    rows.append({"section": section, "source": source, "text": cleaned})


def build_visible_resume_evidence_rows(
    *,
    resume_profile: dict[str, Any] | None,
    raw_resume_text: str = "",
) -> list[dict[str, str]]:
    """Build deterministic evidence rows from the current visible resume only."""
    profile = resume_profile if isinstance(resume_profile, dict) else {}
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    _append_evidence(
        rows,
        seen,
        section="summary",
        source="resume_profile.summary",
        text=profile.get("summary"),
    )

    for index, item in enumerate(profile.get("experience", []) or []):
        if not isinstance(item, dict):
            continue
        heading = " — ".join(
            value
            for value in (
                _clean(item.get("title")),
                _clean(item.get("company")),
                _clean(item.get("date")),
            )
            if value
        )
        _append_evidence(
            rows,
            seen,
            section="experience",
            source=f"resume_profile.experience[{index}]",
            text=heading,
        )
        for bullet_index, bullet in enumerate(item.get("bullets", []) or []):
            _append_evidence(
                rows,
                seen,
                section="experience",
                source=f"resume_profile.experience[{index}].bullets[{bullet_index}]",
                text=bullet,
            )

    for index, item in enumerate(profile.get("projects", []) or []):
        if not isinstance(item, dict):
            continue
        heading = " — ".join(
            value
            for value in (_clean(item.get("title")), _clean(item.get("date")))
            if value
        )
        _append_evidence(
            rows,
            seen,
            section="projects",
            source=f"resume_profile.projects[{index}]",
            text=heading,
        )
        for bullet_index, bullet in enumerate(item.get("bullets", []) or []):
            _append_evidence(
                rows,
                seen,
                section="projects",
                source=f"resume_profile.projects[{index}].bullets[{bullet_index}]",
                text=bullet,
            )

    for index, item in enumerate(profile.get("education", []) or []):
        if not isinstance(item, dict):
            continue
        combined = " — ".join(
            value
            for value in (
                _clean(item.get("degree")),
                _clean(item.get("school")),
                _clean(item.get("graduation_date") or item.get("date")),
            )
            if value
        )
        _append_evidence(
            rows,
            seen,
            section="education",
            source=f"resume_profile.education[{index}]",
            text=combined,
        )

    skills = profile.get("skills") or {}
    if isinstance(skills, dict):
        for category in sorted(skills, key=lambda value: _normalise(value)):
            values = skills.get(category, []) or []
            if not isinstance(values, list):
                continue
            for index, value in enumerate(values):
                _append_evidence(
                    rows,
                    seen,
                    section="skills",
                    source=f"resume_profile.skills.{category}[{index}]",
                    text=value,
                )
    elif isinstance(skills, list):
        for index, value in enumerate(skills):
            _append_evidence(
                rows,
                seen,
                section="skills",
                source=f"resume_profile.skills[{index}]",
                text=value,
            )

    # Raw text is fallback visibility, not a second semantic source.
    for line_index, line in enumerate(str(raw_resume_text or "").splitlines()):
        _append_evidence(
            rows,
            seen,
            section="raw_resume",
            source=f"raw_resume_text[{line_index}]",
            text=line,
        )

    return rows


def _best_taxonomy_support(
    requirement: dict[str, Any],
    evidence_rows: list[dict[str, str]],
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    taxonomy = get_default_taxonomy()
    best_decision: dict[str, Any] | None = None
    best_evidence: dict[str, str] | None = None
    best_rank = 0

    for evidence in evidence_rows:
        decision = evaluate_evidence(requirement, evidence["text"], taxonomy)
        label = str(decision.get("label") or "none")
        rank = _LABEL_ORDER.get(label, 0)
        if rank > best_rank:
            best_rank = rank
            best_decision = decision
            best_evidence = evidence

    return best_decision, best_evidence


def apply_fresh_taxonomy_evidence_rediscovery(
    requirements: list[dict[str, Any]],
    *,
    resume_profile: dict[str, Any] | None,
    raw_resume_text: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Upgrade under-recognised rows from current visible evidence only."""
    output = deepcopy(requirements)
    evidence_rows = build_visible_resume_evidence_rows(
        resume_profile=resume_profile,
        raw_resume_text=raw_resume_text,
    )
    upgrades: list[dict[str, Any]] = []

    for row in output:
        if not isinstance(row, dict):
            continue
        current_label = str(row.get("match_label") or "none")
        current_rank = _LABEL_ORDER.get(current_label, 0)
        if current_rank >= _LABEL_ORDER["direct"]:
            continue

        decision, evidence = _best_taxonomy_support(row, evidence_rows)
        if not decision or not evidence:
            continue

        new_label = str(decision.get("label") or "none")
        new_rank = _LABEL_ORDER.get(new_label, 0)
        if new_rank <= current_rank:
            continue

        reason = str(decision.get("reason") or "taxonomy_supported_visible_evidence")
        row["match_label"] = new_label
        row["match_value"] = MATCH_VALUES[new_label]
        row["evidence_strength"] = _EVIDENCE_STRENGTH[new_label]
        row["match_source"] = "present"
        row["evidence"] = [
            {
                "section": evidence["section"],
                "source": evidence["source"],
                "text": evidence["text"],
                "reason": (
                    "Deterministic fresh evidence rediscovery through the "
                    f"Phase 6D capability taxonomy: {reason}."
                ),
                "evidence_similarity": "1.000",
            }
        ]
        row["capability_id"] = decision.get("capability_id")
        row["capability_taxonomy_version"] = decision.get("taxonomy_version")
        row["capability_does_not_prove"] = list(
            decision.get("does_not_prove", []) or []
        )
        row["fresh_evidence_rediscovery"] = {
            "version": FRESH_EVIDENCE_REDISCOVERY_VERSION,
            "policy_version": FRESH_TARGET_EVIDENCE_POLICY_VERSION,
            "capability_id": decision.get("capability_id"),
            "taxonomy_version": decision.get("taxonomy_version"),
            "previous_label": current_label,
            "rediscovered_label": new_label,
            "rule": reason,
            "evidence_source": evidence["source"],
        }
        upgrades.append(
            {
                "requirement_id": _clean(row.get("requirement_id")),
                "previous_label": current_label,
                "rediscovered_label": new_label,
                "capability_id": decision.get("capability_id"),
                "rule": reason,
                "evidence_source": evidence["source"],
            }
        )

    report = {
        "rediscovery_version": FRESH_EVIDENCE_REDISCOVERY_VERSION,
        "evidence_policy_version": FRESH_TARGET_EVIDENCE_POLICY_VERSION,
        "visible_evidence_row_count": len(evidence_rows),
        "upgraded_requirement_count": len(upgrades),
        "upgraded_requirements": upgrades,
        "historical_phase8_answers_used": False,
        "generation_mappings_used": False,
        "model_call_count": 0,
        "embedding_call_count": 0,
        "chroma_call_count": 0,
    }
    return output, report


def build_fresh_target_analysis(
    *,
    jd_profile: dict[str, Any],
    keyword_match: dict[str, Any],
    raw_jd_text: str = "",
    raw_resume_text: str = "",
    resume_profile: dict[str, Any] | None = None,
    bullet_quality_score: int | float = 0,
    structure_score: int | float = 0,
    retrieval_mode_override: str | None = None,
) -> dict[str, Any]:
    """Run stable scoring plus deterministic current-evidence rediscovery."""
    analysis = build_stable_analysis(
        jd_profile=jd_profile,
        keyword_match=keyword_match,
        raw_jd_text=raw_jd_text,
        raw_resume_text=raw_resume_text,
        resume_profile=resume_profile,
        bullet_quality_score=bullet_quality_score,
        structure_score=structure_score,
        retrieval_mode_override=retrieval_mode_override,
    )

    rows, report = apply_fresh_taxonomy_evidence_rediscovery(
        analysis.get("canonical_requirements", []) or [],
        resume_profile=resume_profile,
        raw_resume_text=raw_resume_text,
    )
    score = compute_deterministic_alignment(
        rows,
        bullet_quality_score=bullet_quality_score,
        structure_score=structure_score,
    )

    base_input_fingerprint = str(analysis.get("input_fingerprint") or "")
    input_identity = {
        "base_stable_input_fingerprint": base_input_fingerprint,
        "fresh_target_evidence_policy_version": FRESH_TARGET_EVIDENCE_POLICY_VERSION,
        "fresh_evidence_rediscovery_version": FRESH_EVIDENCE_REDISCOVERY_VERSION,
        "capability_taxonomy_version": get_default_taxonomy().version,
    }
    analysis["base_stable_input_fingerprint"] = base_input_fingerprint
    analysis["input_fingerprint"] = hashlib.sha256(
        json.dumps(
            input_identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    analysis["fresh_target_evidence_policy_version"] = (
        FRESH_TARGET_EVIDENCE_POLICY_VERSION
    )
    analysis["fresh_evidence_rediscovery"] = report
    analysis["canonical_requirements"] = rows
    analysis.update(score)
    return analysis

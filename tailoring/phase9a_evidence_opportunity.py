"""Phase 9A: deterministic Evidence Opportunity Analysis."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from analysis_stability import build_stable_analysis
from tailoring.phase6d_ranking_adapter import (
    match_requirement_to_candidate,
)
from tailoring.phase8_verification import (
    build_resume_text_from_profile,
    compare_stable_analyses,
)


PHASE9A_VERSION = "phase9a-evidence-opportunity-v1"

_MATCH_RANK = {
    "none": 0,
    "weak": 1,
    "transferable": 2,
    "direct": 3,
}
_MATCH_VALUE = {
    "none": 0.0,
    "weak": 0.25,
    "transferable": 0.55,
    "direct": 1.0,
}
_IMPORTANCE_WEIGHT = {
    "deal_breaker": 36.0,
    "core": 36.0,
    "required": 30.0,
    "preferred": 12.0,
}

_STOPWORDS = {
    "a", "an", "and", "as", "at", "be", "by", "for", "from", "in",
    "including", "into", "is", "of", "on", "or", "the", "to", "with",
    "within", "work", "working", "experience", "knowledge",
}


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").replace("\u00a0", " ").split()
    ).strip()


def _normalise(value: Any) -> str:
    text = _clean(value).lower().replace("&", " and ")
    text = text.replace("row-level", "row level")
    text = text.replace("cross-functional", "cross functional")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return " ".join(text.split())


def _tokens(value: Any) -> set[str]:
    return {
        token
        for token in _normalise(value).split()
        if len(token) >= 2 and token not in _STOPWORDS
    }


def _normalise_multiline(value: Any) -> str:
    text = (
        str(value or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\u00a0", " ")
    )
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _importance(value: Any) -> str:
    result = _normalise(value).replace(" ", "_")
    return result if result in _IMPORTANCE_WEIGHT else "required"


def _label(value: Any) -> str:
    result = _normalise(value).replace(" ", "_")
    return result if result in _MATCH_RANK else "none"


def _evidence_lines(item: dict[str, Any]) -> list[str]:
    description = _normalise_multiline(item.get("description"))
    lines = [
        _clean(line.lstrip("•-* "))
        for line in description.split("\n")
        if _clean(line.lstrip("•-* "))
    ]
    if not lines and description:
        lines = [_clean(description)]
    return lines


def _evidence_text(item: dict[str, Any]) -> str:
    parts = [
        _clean(item.get("title")),
        *_evidence_lines(item),
        *[
            _clean(value)
            for value in item.get("skills", []) or []
            if _clean(value)
        ],
        *[
            _clean(value)
            for value in item.get("tools", []) or []
            if _clean(value)
        ],
        _clean(item.get("impact")),
    ]
    return "\n".join(part for part in parts if part)


def _requirement_text(requirement: dict[str, Any]) -> str:
    return _clean(
        requirement.get("text")
        or requirement.get("atomic_focus")
    )


def _fallback_match(
    requirement: dict[str, Any],
    evidence_text: str,
) -> dict[str, Any]:
    requirement_tokens = _tokens(
        " ".join(
            [
                _requirement_text(requirement),
                _clean(requirement.get("atomic_focus")),
                _clean(requirement.get("parent_text")),
            ]
        )
    )
    evidence_tokens = _tokens(evidence_text)
    if not requirement_tokens or not evidence_tokens:
        return {
            "label": "none",
            "reason": "no_lexical_support",
            "capability_id": None,
            "taxonomy_version": None,
        }

    overlap = requirement_tokens & evidence_tokens
    coverage = len(overlap) / max(1, len(requirement_tokens))
    if coverage >= 0.70 and len(overlap) >= 2:
        return {
            "label": "weak",
            "reason": "conservative_unrecognised_lexical_support",
            "capability_id": None,
            "taxonomy_version": None,
            "lexical_coverage": round(coverage, 3),
        }
    return {
        "label": "none",
        "reason": "insufficient_unrecognised_lexical_support",
        "capability_id": None,
        "taxonomy_version": None,
        "lexical_coverage": round(coverage, 3),
    }


def _match_evidence_item(
    item: dict[str, Any],
    requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    corpus = _evidence_text(item)
    matches: list[dict[str, Any]] = []

    for requirement in requirements:
        requirement_id = _clean(requirement.get("requirement_id"))
        if not requirement_id:
            continue

        decision = match_requirement_to_candidate(
            requirement=requirement,
            candidate_evidence_text=corpus,
        )
        if decision.get("label") is None:
            decision = _fallback_match(requirement, corpus)

        label = _label(decision.get("label"))
        if label == "none":
            continue

        matches.append(
            {
                "requirement_id": requirement_id,
                "requirement": _requirement_text(requirement),
                "importance": _importance(
                    requirement.get("importance")
                ),
                "match_label": label,
                "capability_id": decision.get("capability_id"),
                "reason": decision.get("reason"),
                "taxonomy_version": decision.get(
                    "taxonomy_version"
                ),
                "evidence_title": _clean(item.get("title")),
                "evidence_item_id": item.get("id"),
                "evidence_text": corpus,
            }
        )

    return matches


def _baseline_labels(
    stable_analysis: dict[str, Any],
) -> dict[str, str]:
    return {
        _clean(row.get("requirement_id")): _label(
            row.get("match_label")
        )
        for row in stable_analysis.get(
            "canonical_requirements",
            [],
        )
        or []
        if isinstance(row, dict)
        and _clean(row.get("requirement_id"))
    }


def _incremental_points(
    matches: list[dict[str, Any]],
    current_labels: dict[str, str],
) -> float:
    points = 0.0
    for match in matches:
        requirement_id = match["requirement_id"]
        new_label = _label(match.get("match_label"))
        current_label = current_labels.get(requirement_id, "none")
        if _MATCH_RANK[new_label] <= _MATCH_RANK[current_label]:
            continue
        importance = _importance(match.get("importance"))
        points += _IMPORTANCE_WEIGHT[importance] * (
            _MATCH_VALUE[new_label] - _MATCH_VALUE[current_label]
        )
    return round(points, 6)


def select_evidence_opportunities(
    *,
    stable_analysis: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    max_projects: int = 3,
) -> list[dict[str, Any]]:
    """Greedily select evidence items by uncovered weighted requirement gain."""
    requirements = [
        row
        for row in stable_analysis.get(
            "canonical_requirements",
            [],
        )
        or []
        if isinstance(row, dict)
    ]
    current_labels = _baseline_labels(stable_analysis)

    candidates: list[dict[str, Any]] = []
    for item in evidence_items:
        if not isinstance(item, dict):
            continue
        matches = _match_evidence_item(item, requirements)
        candidates.append(
            {
                "item": deepcopy(item),
                "matches": matches,
            }
        )

    selected: list[dict[str, Any]] = []
    remaining = list(candidates)

    while remaining and len(selected) < max(1, int(max_projects)):
        ranked = sorted(
            remaining,
            key=lambda candidate: (
                _incremental_points(
                    candidate["matches"],
                    current_labels,
                ),
                len(candidate["matches"]),
                _normalise(
                    candidate["item"].get("title")
                ),
            ),
            reverse=True,
        )
        best = ranked[0]
        gain = _incremental_points(
            best["matches"],
            current_labels,
        )
        if gain <= 0:
            break

        accepted_matches: list[dict[str, Any]] = []
        for match in best["matches"]:
            requirement_id = match["requirement_id"]
            new_label = _label(match.get("match_label"))
            current_label = current_labels.get(
                requirement_id,
                "none",
            )
            if _MATCH_RANK[new_label] <= _MATCH_RANK[current_label]:
                continue
            accepted_matches.append(match)
            current_labels[requirement_id] = new_label

        selected.append(
            {
                **best,
                "matches": accepted_matches,
                "incremental_points": gain,
            }
        )
        remaining.remove(best)

    return selected


def _merge_skills(
    profile: dict[str, Any],
    selected: list[dict[str, Any]],
    max_skills: int,
) -> None:
    skills = deepcopy(profile.get("skills") or {})
    if not isinstance(skills, dict):
        skills = {}

    values: list[str] = []
    for selected_item in selected:
        item = selected_item["item"]
        values.extend(item.get("skills", []) or [])
        values.extend(item.get("tools", []) or [])

    existing = {
        _normalise(value)
        for category_values in skills.values()
        if isinstance(category_values, list)
        for value in category_values
        if _normalise(value)
    }
    additions: list[str] = []
    for value in values:
        cleaned = _clean(value)
        key = _normalise(cleaned)
        if not key or key in existing:
            continue
        existing.add(key)
        additions.append(cleaned)
        if len(additions) >= max(0, int(max_skills)):
            break

    if additions:
        skills["Evidence-backed additions"] = additions
    profile["skills"] = skills


def build_opportunity_resume_profile(
    *,
    baseline_resume_profile: dict[str, Any],
    selected: list[dict[str, Any]],
    max_bullets_per_project: int,
    max_skills: int,
) -> dict[str, Any]:
    profile = deepcopy(baseline_resume_profile or {})
    projects = [
        deepcopy(project)
        for project in profile.get("projects", []) or []
        if isinstance(project, dict)
    ]

    for selected_item in selected:
        item = selected_item["item"]
        bullets = _evidence_lines(item)[
            : max(1, int(max_bullets_per_project))
        ]
        projects.append(
            {
                "title": _clean(item.get("title")),
                "date": _clean(item.get("period")),
                "bullets": bullets,
                "evidence_library_item_id": item.get("id"),
            }
        )

    profile["projects"] = projects
    _merge_skills(profile, selected, max_skills)
    return profile


def _opportunity_keyword_match(
    *,
    baseline_report: dict[str, Any],
    selected: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline = baseline_report.get("keyword_match") or {}
    present = [
        deepcopy(row)
        for row in baseline.get("present", []) or []
        if isinstance(row, dict)
    ]
    missing = [
        deepcopy(row)
        for row in baseline.get("missing", []) or []
        if isinstance(row, dict)
    ]

    added_requirement_keys: set[str] = set()
    for selected_item in selected:
        for match in selected_item["matches"]:
            requirement = _clean(match.get("requirement"))
            evidence_text = _clean(match.get("evidence_text"))
            if not requirement or not evidence_text:
                continue
            added_requirement_keys.add(_normalise(requirement))
            present.append(
                {
                    "keyword": requirement,
                    "category": "phase9a_evidence_opportunity",
                    "importance": match.get("importance", "required"),
                    "found_in": "evidence_library",
                    "matched_resume_term": evidence_text,
                    "match_type": match.get(
                        "match_label",
                        "weak",
                    ),
                    "evidence_type": match.get(
                        "match_label",
                        "weak",
                    ),
                    "match_reason": (
                        "Phase 9A selected a constrained Evidence Library "
                        "item with deterministic requirement support."
                    ),
                }
            )

    filtered_missing = [
        row
        for row in missing
        if _normalise(
            row.get("keyword")
            or row.get("requirement")
        )
        not in added_requirement_keys
    ]

    return {
        "present": present,
        "missing": filtered_missing,
        "opportunity_source": (
            "baseline_resume_plus_constrained_evidence_library"
        ),
    }


def build_opportunity_fingerprint(
    *,
    baseline_report: dict[str, Any],
    raw_jd_text: str,
    evidence_items: list[dict[str, Any]],
    max_projects: int,
    max_bullets_per_project: int,
    max_skills: int,
) -> str:
    payload = {
        "phase9a_version": PHASE9A_VERSION,
        "baseline_fingerprint": (
            baseline_report.get("stable_analysis") or {}
        ).get("input_fingerprint", ""),
        "raw_jd_text": _normalise_multiline(raw_jd_text),
        "evidence_items": evidence_items,
        "constraints": {
            "max_projects": int(max_projects),
            "max_bullets_per_project": int(
                max_bullets_per_project
            ),
            "max_skills": int(max_skills),
        },
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_evidence_opportunity_analysis(
    *,
    application_id: int,
    baseline_report: dict[str, Any],
    raw_jd_text: str,
    evidence_items: list[dict[str, Any]],
    max_projects: int = 3,
    max_bullets_per_project: int = 2,
    max_skills: int = 20,
) -> dict[str, Any]:
    baseline = baseline_report.get("stable_analysis")
    if not isinstance(baseline, dict):
        raise ValueError(
            "Run the stable résumé/JD analysis before Phase 9A."
        )

    canonical_jd_text = _normalise_multiline(raw_jd_text)
    if not canonical_jd_text:
        raise ValueError(
            "Phase 9A requires the original job-description text."
        )

    selected = select_evidence_opportunities(
        stable_analysis=baseline,
        evidence_items=evidence_items,
        max_projects=max_projects,
    )
    opportunity_profile = build_opportunity_resume_profile(
        baseline_resume_profile=baseline_report.get(
            "resume_profile",
            {},
        ),
        selected=selected,
        max_bullets_per_project=max_bullets_per_project,
        max_skills=max_skills,
    )
    opportunity_text = build_resume_text_from_profile(
        opportunity_profile
    )
    keyword_match = _opportunity_keyword_match(
        baseline_report=baseline_report,
        selected=selected,
    )

    potential = build_stable_analysis(
        jd_profile=baseline_report.get("jd_profile", {}) or {},
        keyword_match=keyword_match,
        raw_jd_text=canonical_jd_text,
        raw_resume_text=opportunity_text,
        resume_profile=opportunity_profile,
        bullet_quality_score=(
            baseline_report.get("bullets", {}) or {}
        ).get("bullet_quality_avg", 0),
        structure_score=(
            baseline_report.get("structure", {}) or {}
        ).get("structure_score", 0),
    )
    comparison = compare_stable_analyses(
        baseline,
        potential,
    )
    comparison_valid = bool(
        comparison.get("canonical_requirement_ids_stable")
    )

    selected_rows = []
    for selected_item in selected:
        item = selected_item["item"]
        selected_rows.append(
            {
                "evidence_item_id": item.get("id"),
                "title": _clean(item.get("title")),
                "category": _clean(item.get("category")),
                "period": _clean(item.get("period")),
                "incremental_points": selected_item.get(
                    "incremental_points",
                    0,
                ),
                "matched_requirements": [
                    {
                        "requirement_id": match.get(
                            "requirement_id"
                        ),
                        "requirement": match.get("requirement"),
                        "importance": match.get("importance"),
                        "match_label": match.get("match_label"),
                        "capability_id": match.get(
                            "capability_id"
                        ),
                        "reason": match.get("reason"),
                    }
                    for match in selected_item["matches"]
                ],
            }
        )

    unresolved = [
        {
            "requirement_id": row.get("requirement_id"),
            "requirement": row.get("text"),
            "importance": row.get("importance"),
        }
        for row in potential.get("canonical_requirements", []) or []
        if isinstance(row, dict)
        and _label(row.get("match_label")) == "none"
    ]

    return {
        "phase9a_version": PHASE9A_VERSION,
        "analysis_mode": "zero_cost_deterministic_forecast",
        "application_id": int(application_id),
        "opportunity_fingerprint": build_opportunity_fingerprint(
            baseline_report=baseline_report,
            raw_jd_text=canonical_jd_text,
            evidence_items=evidence_items,
            max_projects=max_projects,
            max_bullets_per_project=max_bullets_per_project,
            max_skills=max_skills,
        ),
        "constraints": {
            "max_projects": int(max_projects),
            "max_bullets_per_project": int(
                max_bullets_per_project
            ),
            "max_skills": int(max_skills),
        },
        "baseline_score": int(
            baseline.get(
                "deterministic_alignment_score",
                0,
            )
            or 0
        ),
        "potential_score": int(
            potential.get(
                "deterministic_alignment_score",
                0,
            )
            or 0
        ),
        "score_delta": int(
            potential.get(
                "deterministic_alignment_score",
                0,
            )
            or 0
        )
        - int(
            baseline.get(
                "deterministic_alignment_score",
                0,
            )
            or 0
        ),
        "comparison_valid": comparison_valid,
        "comparison": comparison,
        "selected_evidence": selected_rows,
        "selected_evidence_count": len(selected_rows),
        "unresolved_requirements": unresolved,
        "potential_stable_analysis": potential,
        "opportunity_resume_profile": opportunity_profile,
        "forecast_notice": (
            "This is a constrained evidence-backed forecast, not the score "
            "of a generated or downloaded résumé. Phase 8 remains the final "
            "verification of the actual fitted version."
        ),
    }

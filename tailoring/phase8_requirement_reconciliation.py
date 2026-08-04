"""Conservative Phase 8 reconciliation of final visible requirement evidence."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from analysis_stability.evidence_support import (
    classify_verified_evidence_support,
)
from tailoring.tailoring_generation_fingerprint import (
    get_effective_generation_sections,
)


RECONCILIATION_VERSION = "phase8-final-evidence-reconciliation-v2"

MATCH_RANK = {
    "none": 0,
    "weak": 1,
    "transferable": 2,
    "direct": 3,
}
MATCH_VALUE = {
    "none": 0.0,
    "weak": 0.2,
    "transferable": 0.55,
    "direct": 1.0,
}
EVIDENCE_STRENGTH = {
    "none": 0,
    "weak": 2,
    "transferable": 3,
    "direct": 5,
}
IMPORTANCE_WEIGHT = {
    "deal_breaker": 1.25,
    "required": 1.0,
    "core": 0.75,
    "preferred": 0.5,
}
IMPORTANT_REQUIREMENTS = {
    "deal_breaker",
    "required",
    "core",
}

_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "for",
    "from",
    "in",
    "including",
    "into",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "use",
    "using",
    "with",
    "within",
    "experience",
}

_TOKEN_ALIASES = {
    "accesses": "access",
    "accessing": "access",
    "applications": "application",
    "app": "application",
    "apps": "application",
    "authenticated": "authentication",
    "authenticating": "authentication",
    "collaborated": "collaboration",
    "collaborating": "collaboration",
    "collaborate": "collaboration",
    "databases": "database",
    "designed": "design",
    "designing": "design",
    "github": "github",
    "implemented": "implement",
    "implementing": "implement",
    "implementation": "implement",
    "policies": "policy",
    "postgresql": "postgres",
    "rls": "rowlevelsecurity",
    "secured": "secure",
    "security": "secure",
    "set-up": "setup",
    "teams": "team",
    "user-facing": "userfacing",
    "workflows": "workflow",
}


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").replace("\u00a0", " ").split()
    ).strip()


def _normalise(value: Any) -> str:
    text = _clean(value).lower().replace("&", " and ")
    text = text.replace("row-level security", "rowlevelsecurity")
    text = text.replace("row level security", "rowlevelsecurity")
    text = text.replace("user-facing", "userfacing")
    text = text.replace("set up", "setup")
    text = re.sub(r"[^a-z0-9+#.-]+", " ", text)
    return " ".join(text.split())


def _tokens(value: Any) -> set[str]:
    result: set[str] = set()
    for token in _normalise(value).split():
        token = token.strip(".-")
        if len(token) < 2 or token in _STOPWORDS:
            continue
        result.add(_TOKEN_ALIASES.get(token, token))
    return result


def _similarity(left: Any, right: Any) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    return max(
        overlap / len(left_tokens | right_tokens),
        overlap / min(len(left_tokens), len(right_tokens)),
    )


def _label(value: Any) -> str:
    result = _normalise(value).replace(" ", "_")
    return result if result in MATCH_RANK else "none"


def _importance(value: Any) -> str:
    result = _normalise(value).replace(" ", "_")
    return (
        result
        if result in IMPORTANCE_WEIGHT
        else "required"
    )


def _project_title(project: dict[str, Any]) -> str:
    return _clean(
        project.get("display_title")
        or project.get("title")
        or "Untitled Project"
    )


def _project_identity_keys(project: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    project_id = _clean(project.get("project_id")).lower()
    if project_id:
        keys.add(f"id:{project_id}")

    for value in (
        project.get("display_title"),
        project.get("title"),
    ):
        text = _clean(value)
        if not text:
            continue
        keys.add(f"title:{_normalise(text)}")
        base = re.sub(r"\s*\([^()]*\)\s*$", "", text).strip()
        if base:
            keys.add(f"base:{_normalise(base)}")
    return keys


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _verified_project_bullets(
    claim_lineage: dict[str, Any],
) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for row in claim_lineage.get(
        "verified_project_bullets",
        [],
    ) or []:
        if not isinstance(row, dict):
            continue
        bullet = _clean(row.get("bullet"))
        if not bullet:
            continue
        project = {
            "project_id": row.get("project_id"),
            "display_title": row.get("project"),
        }
        for key in _project_identity_keys(project):
            index.setdefault(key, []).append(bullet)
    return index


def _verified_skills(
    claim_lineage: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in claim_lineage.get("verified_skills", []) or []:
        if not isinstance(row, dict):
            continue
        skill = _clean(row.get("skill"))
        if not skill:
            continue
        result[_normalise(skill)] = row
    return result


def _effective_projects(
    generation_state: dict[str, Any],
) -> list[dict[str, Any]]:
    effective = get_effective_generation_sections(generation_state)
    projects = effective.get("projects")
    if not isinstance(projects, dict):
        return []
    return [
        project
        for project in projects.get(
            "recommended_projects",
            [],
        )
        or []
        if isinstance(project, dict)
    ]


def _effective_skills(
    generation_state: dict[str, Any],
) -> dict[str, Any]:
    effective = get_effective_generation_sections(generation_state)
    skills = effective.get("skills")
    return skills if isinstance(skills, dict) else {}


def _verified_bullets_for_project(
    project: dict[str, Any],
    verified_index: dict[str, list[str]],
) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for key in _project_identity_keys(project):
        for bullet in verified_index.get(key, []):
            normalised = _normalise(bullet)
            if normalised and normalised not in seen:
                seen.add(normalised)
                values.append(bullet)
    return values


def _visible_verified_skill_names(
    generation_state: dict[str, Any],
    claim_lineage: dict[str, Any],
) -> set[str]:
    verified = _verified_skills(claim_lineage)
    visible: set[str] = set()
    skills = _effective_skills(generation_state)

    for line in skills.get("skill_lines", []) or []:
        if not isinstance(line, dict):
            continue
        for value in line.get("items", []) or []:
            key = _normalise(value)
            if key and key in verified:
                visible.add(key)
    return visible


def _skill_requirement_support(
    generation_state: dict[str, Any],
    visible_verified_skills: set[str],
) -> dict[str, set[str]]:
    support: dict[str, set[str]] = {}

    for record in _walk_dicts(
        {
            "effective_skills": _effective_skills(generation_state),
            "generation_skills": generation_state.get("skills"),
        }
    ):
        skill = _normalise(record.get("skill"))
        requirement_ids = record.get("matched_requirement_ids")
        if (
            not skill
            or skill not in visible_verified_skills
            or not isinstance(requirement_ids, list)
        ):
            continue
        for requirement_id in requirement_ids:
            rid = _clean(requirement_id)
            if rid:
                support.setdefault(rid, set()).add(skill)
    return support


def _preserved_baseline_evidence(
    before_row: dict[str, Any],
) -> list[dict[str, Any]]:
    preserved: list[dict[str, Any]] = []
    for evidence in before_row.get("evidence", []) or []:
        if not isinstance(evidence, dict):
            continue
        source = _clean(evidence.get("source"))
        if source.startswith(
            (
                "resume_profile.experience",
                "resume_profile.education",
                "resume_profile.summary",
            )
        ):
            preserved.append(evidence)
    return preserved


def _best_mapping_support(
    *,
    requirement: dict[str, Any],
    generation_state: dict[str, Any],
    claim_lineage: dict[str, Any],
) -> dict[str, Any] | None:
    requirement_id = _clean(requirement.get("requirement_id"))
    if not requirement_id:
        return None

    verified_index = _verified_project_bullets(claim_lineage)
    visible_verified_skills = _visible_verified_skill_names(
        generation_state,
        claim_lineage,
    )
    skill_support = _skill_requirement_support(
        generation_state,
        visible_verified_skills,
    )
    matched_skills = sorted(
        skill_support.get(requirement_id, set())
    )

    candidates: list[dict[str, Any]] = []
    requirement_text = _clean(
        requirement.get("text")
        or requirement.get("atomic_focus")
    )
    requirement_tokens = _tokens(requirement_text)

    for project in _effective_projects(generation_state):
        verified_bullets = _verified_bullets_for_project(
            project,
            verified_index,
        )
        if not verified_bullets:
            continue

        for match in project.get("requirement_matches", []) or []:
            if not isinstance(match, dict):
                continue
            if _clean(match.get("requirement_id")) != requirement_id:
                continue

            mapping_label = _label(match.get("match_label"))
            if mapping_label == "none":
                continue

            snippets = [
                _clean(value)
                for value in match.get("evidence_snippets", []) or []
                if _clean(value)
            ]
            snippet_similarities = [
                max(
                    (_similarity(snippet, bullet) for bullet in verified_bullets),
                    default=0.0,
                )
                for snippet in snippets
            ]
            best_snippet_similarity = max(
                snippet_similarities,
                default=0.0,
            )
            strong_snippet_count = sum(
                similarity >= 0.72
                for similarity in snippet_similarities
            )

            final_evidence_text = " ".join(
                [
                    *verified_bullets,
                    *matched_skills,
                ]
            )
            final_tokens = _tokens(final_evidence_text)
            coverage = (
                len(requirement_tokens & final_tokens)
                / len(requirement_tokens)
                if requirement_tokens
                else 0.0
            )

            supported_label = classify_verified_evidence_support(
                coverage=coverage,
                best_similarity=best_snippet_similarity,
                strong_evidence_count=strong_snippet_count,
                has_matched_skills=bool(matched_skills),
            )
            if supported_label == "direct":
                reason = (
                    "The final verified bullets and Skills still cover most "
                    "of this requirement."
                )
            elif supported_label == "transferable":
                reason = (
                    "Part of the mapped evidence survived in the final "
                    "verified résumé, but not enough to preserve full direct "
                    "credit."
                )
            elif supported_label == "weak":
                reason = (
                    "A limited portion of the mapped evidence survived in "
                    "the final verified résumé."
                )
            else:
                continue

            final_rank = min(
                MATCH_RANK[mapping_label],
                MATCH_RANK[supported_label],
            )
            reconciled_label = next(
                label
                for label, rank in MATCH_RANK.items()
                if rank == final_rank
            )
            evidence_rows = [
                {
                    "section": "projects",
                    "text": bullet,
                    "source": (
                        "phase8_reconciliation."
                        f"{_clean(project.get('project_id')) or _normalise(_project_title(project))}"
                    ),
                    "reason": reason,
                    "evidence_similarity": f"{best_snippet_similarity:.3f}",
                }
                for bullet in verified_bullets
            ]
            evidence_rows.extend(
                {
                    "section": "skills",
                    "text": skill,
                    "source": "phase8_reconciliation.verified_skill",
                    "reason": reason,
                    "evidence_similarity": "1.000",
                }
                for skill in matched_skills
            )

            candidates.append(
                {
                    "requirement_id": requirement_id,
                    "project_id": _clean(project.get("project_id")),
                    "project": _project_title(project),
                    "mapping_label": mapping_label,
                    "supported_label": supported_label,
                    "reconciled_label": reconciled_label,
                    "best_snippet_similarity": round(
                        best_snippet_similarity,
                        3,
                    ),
                    "strong_snippet_count": strong_snippet_count,
                    "requirement_token_coverage": round(coverage, 3),
                    "verified_skills": matched_skills,
                    "reason": reason,
                    "evidence": evidence_rows,
                }
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda row: (
            -MATCH_RANK[row["reconciled_label"]],
            -float(row["requirement_token_coverage"]),
            -float(row["best_snippet_similarity"]),
            row["project"],
        )
    )
    return candidates[0]


def _alignment_band(score: int) -> str:
    if score < 50:
        return "weak alignment"
    if score < 65:
        return "partial alignment"
    if score < 80:
        return "strong alignment"
    return "very strong alignment"


def _boundary_status(score: int) -> dict[str, Any]:
    boundaries = (50, 65, 80)
    nearest = min(boundaries, key=lambda value: abs(score - value))
    margin = abs(score - nearest)
    return {
        "margin_points": margin,
        "nearest_boundary": nearest,
        "is_borderline": margin <= 3,
    }


def _recalculate_stable_summary(
    analysis: dict[str, Any],
) -> None:
    rows = [
        row
        for row in analysis.get("canonical_requirements", []) or []
        if isinstance(row, dict)
    ]

    required_rows = [
        row
        for row in rows
        if _importance(row.get("importance")) in IMPORTANT_REQUIREMENTS
    ]
    preferred_rows = [
        row
        for row in rows
        if _importance(row.get("importance")) == "preferred"
    ]

    def coverage(rows_to_score: list[dict[str, Any]]) -> int:
        denominator = sum(
            IMPORTANCE_WEIGHT[_importance(row.get("importance"))]
            * float(row.get("group_weight_fraction", 1.0) or 1.0)
            for row in rows_to_score
        )
        if denominator <= 0:
            return 0
        numerator = sum(
            IMPORTANCE_WEIGHT[_importance(row.get("importance"))]
            * float(row.get("group_weight_fraction", 1.0) or 1.0)
            * MATCH_VALUE[_label(row.get("match_label"))]
            for row in rows_to_score
        )
        return round(100 * numerator / denominator)

    credited = [
        row
        for row in rows
        if _label(row.get("match_label")) != "none"
    ]
    evidence_denominator = sum(
        IMPORTANCE_WEIGHT[_importance(row.get("importance"))]
        * float(row.get("group_weight_fraction", 1.0) or 1.0)
        for row in credited
    )
    evidence_score = (
        round(
            100
            * sum(
                IMPORTANCE_WEIGHT[_importance(row.get("importance"))]
                * float(row.get("group_weight_fraction", 1.0) or 1.0)
                * int(row.get("evidence_strength", 0) or 0)
                / 5.0
                for row in credited
            )
            / evidence_denominator
        )
        if evidence_denominator > 0
        else 0
    )

    required_score = coverage(required_rows)
    preferred_score = coverage(preferred_rows)
    weights = analysis.get("score_weights") or {
        "required_core_coverage": 0.8,
        "preferred_coverage": 0.1,
        "evidence_strength": 0.1,
    }
    alignment_score = round(
        required_score
        * float(weights.get("required_core_coverage", 0.8) or 0)
        + preferred_score
        * float(weights.get("preferred_coverage", 0.1) or 0)
        + evidence_score
        * float(weights.get("evidence_strength", 0.1) or 0)
    )

    analysis["deterministic_alignment_score"] = alignment_score
    analysis["alignment_band"] = _alignment_band(alignment_score)
    analysis["required_core_coverage_score"] = required_score
    analysis["preferred_coverage_score"] = preferred_score
    analysis["evidence_strength_score"] = evidence_score
    analysis["credited_requirement_count"] = len(credited)
    analysis["direct_requirement_count"] = sum(
        _label(row.get("match_label")) == "direct"
        for row in rows
    )
    analysis["transferable_requirement_count"] = sum(
        _label(row.get("match_label")) == "transferable"
        for row in rows
    )
    analysis["weak_requirement_count"] = sum(
        _label(row.get("match_label")) == "weak"
        for row in rows
    )
    analysis["required_core_requirement_count"] = len(required_rows)
    analysis["preferred_requirement_count"] = len(preferred_rows)
    analysis["boundary_status"] = _boundary_status(alignment_score)
    analysis["phase8_reconciliation_version"] = RECONCILIATION_VERSION


def reconcile_final_requirement_matches(
    *,
    before_analysis: dict[str, Any],
    after_analysis: dict[str, Any],
    generation_state: dict[str, Any],
    claim_lineage: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconcile verified final evidence for regressions and new matches.

    The raw stable scorer remains authoritative unless a saved generation
    mapping points to evidence that is still visible and claim-lineage
    verified in the final fitted résumé. This supports two cases:

    1. restore a match that appeared to regress after fitting; and
    2. recognise newly added final Projects/Skills evidence when both the
       baseline and raw final scorer still report ``none`` or a weaker label.
    """
    reconciled = deepcopy(after_analysis)

    before_rows = {
        _clean(row.get("requirement_id")): row
        for row in before_analysis.get(
            "canonical_requirements",
            [],
        )
        or []
        if isinstance(row, dict)
        and _clean(row.get("requirement_id"))
    }
    after_rows = {
        _clean(row.get("requirement_id")): row
        for row in reconciled.get(
            "canonical_requirements",
            [],
        )
        or []
        if isinstance(row, dict)
        and _clean(row.get("requirement_id"))
    }

    changes: list[dict[str, Any]] = []
    newly_supported: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for requirement_id in sorted(
        set(before_rows) & set(after_rows)
    ):
        before_row = before_rows[requirement_id]
        after_row = after_rows[requirement_id]
        before_label = _label(before_row.get("match_label"))
        raw_after_label = _label(after_row.get("match_label"))

        is_regression = (
            MATCH_RANK[raw_after_label]
            < MATCH_RANK[before_label]
        )

        # The previous reconciliation only entered the regression branch.
        # That meant a requirement that was ``none`` before tailoring and
        # still ``none`` in the raw final scorer could never receive credit,
        # even when final verified Projects/Skills directly supported it.
        if not is_regression:
            if MATCH_RANK[raw_after_label] >= MATCH_RANK["direct"]:
                continue

            mapping_support = _best_mapping_support(
                requirement=after_row,
                generation_state=generation_state,
                claim_lineage=claim_lineage,
            )
            if mapping_support is None:
                continue

            target_label = mapping_support["reconciled_label"]
            if (
                MATCH_RANK[target_label]
                <= MATCH_RANK[raw_after_label]
            ):
                continue

            reason = mapping_support["reason"]
            evidence = deepcopy(mapping_support["evidence"])
            after_row["match_label"] = target_label
            after_row["match_value"] = MATCH_VALUE[target_label]
            after_row["evidence_strength"] = EVIDENCE_STRENGTH[
                target_label
            ]
            after_row["evidence"] = evidence
            after_row["phase8_reconciliation"] = {
                "version": RECONCILIATION_VERSION,
                "support_type": "verified_new_generation_evidence",
                "baseline_label": before_label,
                "raw_after_label": raw_after_label,
                "reconciled_after_label": target_label,
                "reason": reason,
                "mapping_support": mapping_support,
            }
            newly_supported.append(
                {
                    "requirement_id": requirement_id,
                    "requirement": _clean(after_row.get("text")),
                    "importance": _importance(
                        after_row.get("importance")
                    ),
                    "before_label": before_label,
                    "raw_after_label": raw_after_label,
                    "reconciled_after_label": target_label,
                    "support_type": (
                        "verified_new_generation_evidence"
                    ),
                    "reason": reason,
                    "verified_project": mapping_support.get(
                        "project"
                    ),
                    "verified_skills": mapping_support.get(
                        "verified_skills",
                        [],
                    ),
                    "requirement_token_coverage": mapping_support.get(
                        "requirement_token_coverage"
                    ),
                    "best_snippet_similarity": mapping_support.get(
                        "best_snippet_similarity"
                    ),
                }
            )
            continue

        preserved = _preserved_baseline_evidence(before_row)
        mapping_support = _best_mapping_support(
            requirement=after_row,
            generation_state=generation_state,
            claim_lineage=claim_lineage,
        )

        target_label = raw_after_label
        reason = ""
        evidence: list[dict[str, Any]] = []
        support_type = ""

        if preserved:
            target_label = before_label
            support_type = "unchanged_resume_section"
            reason = (
                "The original supporting Work Experience, Education, or "
                "Summary evidence was not edited by tailoring and is still "
                "present in the final résumé."
            )
            evidence = deepcopy(preserved)
        elif mapping_support is not None:
            target_label = mapping_support["reconciled_label"]
            support_type = "verified_generation_mapping"
            reason = mapping_support["reason"]
            evidence = deepcopy(mapping_support["evidence"])

        if MATCH_RANK[target_label] > MATCH_RANK[raw_after_label]:
            after_row["match_label"] = target_label
            after_row["match_value"] = MATCH_VALUE[target_label]
            after_row["evidence_strength"] = EVIDENCE_STRENGTH[
                target_label
            ]
            after_row["evidence"] = evidence
            after_row["phase8_reconciliation"] = {
                "version": RECONCILIATION_VERSION,
                "support_type": support_type,
                "raw_after_label": raw_after_label,
                "reconciled_after_label": target_label,
                "reason": reason,
                "mapping_support": mapping_support,
            }
            changes.append(
                {
                    "requirement_id": requirement_id,
                    "requirement": _clean(after_row.get("text")),
                    "importance": _importance(
                        after_row.get("importance")
                    ),
                    "before_label": before_label,
                    "raw_after_label": raw_after_label,
                    "reconciled_after_label": target_label,
                    "support_type": support_type,
                    "reason": reason,
                    "verified_project": (
                        mapping_support.get("project")
                        if mapping_support
                        else None
                    ),
                    "verified_skills": (
                        mapping_support.get("verified_skills", [])
                        if mapping_support
                        else []
                    ),
                    "requirement_token_coverage": (
                        mapping_support.get(
                            "requirement_token_coverage"
                        )
                        if mapping_support
                        else None
                    ),
                    "best_snippet_similarity": (
                        mapping_support.get(
                            "best_snippet_similarity"
                        )
                        if mapping_support
                        else None
                    ),
                }
            )
        else:
            unresolved.append(
                {
                    "requirement_id": requirement_id,
                    "requirement": _clean(after_row.get("text")),
                    "importance": _importance(
                        after_row.get("importance")
                    ),
                    "before_label": before_label,
                    "raw_after_label": raw_after_label,
                    "reason": (
                        "No unchanged source-section evidence or sufficiently "
                        "verified final project/skill mapping survived."
                    ),
                }
            )

    _recalculate_stable_summary(reconciled)

    report = {
        "reconciliation_version": RECONCILIATION_VERSION,
        "reconciled_requirement_count": len(changes),
        "reconciled_requirements": changes,
        "newly_supported_requirement_count": len(newly_supported),
        "newly_supported_requirements": newly_supported,
        "unresolved_regression_count": len(unresolved),
        "unresolved_regressions": unresolved,
        "scoring_recalculated": True,
        "method": (
            "unchanged source-section floor plus verified final project/skill "
            "mapping reconciliation for regressions and newly added final "
            "evidence"
        ),
    }
    report["reconciliation_fingerprint"] = hashlib.sha256(
        json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return reconciled, report

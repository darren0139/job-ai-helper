"""
deterministic_project_rules.py

Deterministic evidence floors for Job AI Helper project ranking.

Purpose:
The LLM still performs nuanced project/JD analysis, but explicit evidence
cannot randomly disappear between otherwise identical runs.

This module does not invent experience. It only applies small minimum
component scores when both:
1. the project evidence explicitly contains a supported capability; and
2. the target JD explicitly asks for a related capability or domain.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any


def _normalise_text(value: Any) -> str:
    """Lowercase text and collapse punctuation/whitespace."""
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9+#./-]+", " ", text)
    return " ".join(text.split())


def _normalise_project_key(title: str) -> str:
    """Match titles such as 'QueryAI' and 'QueryAI (React, Team of 4)'."""
    text = str(title or "").lower().strip()
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"[-–—].*$", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _contains_any(
    text: str,
    terms: tuple[str, ...],
) -> bool:
    return any(
        _normalise_text(term) in text
        for term in terms
    )


def _candidate_text(
    candidate: dict[str, Any],
) -> str:
    """
    Build deterministic evidence text from the supplied candidate.

    Both resume and Evidence Library evidence may affect selection, matching
    the existing scoring-stage behaviour. Final bullet writing can still remain
    restricted to Evidence Library evidence.
    """
    return _normalise_text(
        json.dumps(
            {
                "title": candidate.get("title", ""),
                "display_title": candidate.get(
                    "display_title",
                    "",
                ),
                "resume_evidence": candidate.get(
                    "resume_evidence"
                ),
                "evidence_library_evidence": candidate.get(
                    "evidence_library_evidence"
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _append_unique(
    values: list[str],
    new_value: str,
) -> None:
    existing = {
        _normalise_text(value)
        for value in values
    }

    if _normalise_text(new_value) not in existing:
        values.append(new_value)


_RULES: tuple[dict[str, Any], ...] = (
    {
        "name": "access_control_configuration",
        "evidence_terms": (
            "row-level security",
            "row level security",
            "rls",
            "access control",
            "permission",
            "permissions",
            "authorization",
            "authentication workflow",
            "security policy",
            "security policies",
        ),
        "jd_terms": (
            "configuration",
            "quality assurance",
            " qa ",
            "attention to detail",
            "meticulous",
            "access control",
            "permission",
            "security",
            "operational evaluation",
        ),
        "transferable_requirement": (
            "secure configuration and access-control work"
        ),
        "minimum_responsibility_score": 2,
        "minimum_tool_domain_score": 1,
    },
    {
        "name": "quality_validation",
        "evidence_terms": (
            "quality assurance",
            "testing",
            "tested",
            "validation",
            "validated",
            "verification",
            "verified",
            "debugging",
            "debugged",
            "defect",
            "bug",
            "accuracy checking",
            "data verification",
        ),
        "jd_terms": (
            "quality assurance",
            " qa ",
            "testing",
            "validation",
            "verification",
            "bug",
            "defect",
            "attention to detail",
            "meticulous",
            "accuracy",
        ),
        "transferable_requirement": (
            "testing, validation, or correctness-sensitive work"
        ),
        "minimum_responsibility_score": 2,
        "minimum_tool_domain_score": 1,
    },
    {
        "name": "backend_configuration_integration",
        "evidence_terms": (
            "postgrest",
            "backend integration",
            "api integration",
            "database integration",
            "system integration",
            "configured",
            "configuration",
            "structured workflow",
        ),
        "jd_terms": (
            "configuration",
            "coordinate",
            "operations",
            "operational",
            "product-related problem",
            "integration",
            "maintain",
        ),
        "transferable_requirement": (
            "backend configuration and integration work"
        ),
        "minimum_responsibility_score": 1,
        "minimum_tool_domain_score": 1,
    },
    {
        "name": "gaming_product_domain",
        "evidence_terms": (
            "unity",
            "game engine",
            "gameplay",
            "mobile game",
            "published game",
            "fmod",
            "player progression",
        ),
        "jd_terms": (
            "game",
            "gaming",
            "shooting game",
            "gaming product",
            "gaming industry",
        ),
        "matched_requirement": (
            "basic knowledge of the gaming industry"
        ),
        "minimum_responsibility_score": 0,
        "minimum_tool_domain_score": 2,
    },
    {
        "name": "deployment_operations",
        "evidence_terms": (
            "docker",
            "containerised",
            "containerized",
            "kubernetes",
            "ci/cd",
            "deployment",
            "monitoring",
            "prometheus",
            "grafana",
            "live environment",
        ),
        "jd_terms": (
            "operations",
            "operational",
            "maintain",
            "deployment",
            "devops",
            "cloud",
            "monitoring",
            "live environment",
        ),
        "transferable_requirement": (
            "deployment, monitoring, or operational workflow experience"
        ),
        "minimum_responsibility_score": 2,
        "minimum_tool_domain_score": 2,
    },
)


def apply_deterministic_evidence_floors(
    *,
    ranked_rows: list[dict[str, Any]],
    project_candidates: list[dict[str, Any]],
    jd_profile: dict[str, Any],
    raw_jd_text: str = "",
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """
    Apply conservative deterministic score floors.

    Returns:
        updated_rows:
            Deep-copied ranking rows with component-score floors applied.

        debug_rows:
            A record of every deterministic rule that was applied.

    Important:
        This function does not recalculate final_score. The caller should run
        its existing _calculate_relevance_score() and
        _calculate_project_final_score() functions afterwards.
    """
    updated_rows = deepcopy(ranked_rows)

    candidates_by_key = {
        _normalise_project_key(
            candidate.get("title", "")
        ): candidate
        for candidate in project_candidates
    }

    jd_text = _normalise_text(
        str(raw_jd_text or "")
        + "\n"
        + json.dumps(
            jd_profile or {},
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    debug_rows: list[dict[str, Any]] = []

    for row in updated_rows:
        key = _normalise_project_key(
            row.get("title", "")
        )

        candidate = candidates_by_key.get(key)
        if candidate is None:
            continue

        evidence_text = _candidate_text(candidate)

        row.setdefault(
            "matched_jd_requirements",
            [],
        )
        row.setdefault(
            "transferable_jd_requirements",
            [],
        )

        for rule in _RULES:
            evidence_matches = _contains_any(
                evidence_text,
                rule["evidence_terms"],
            )
            jd_matches = _contains_any(
                jd_text,
                rule["jd_terms"],
            )

            if not (
                evidence_matches
                and jd_matches
            ):
                continue

            old_responsibility = int(
                row.get(
                    "responsibility_match_score",
                    0,
                )
                or 0
            )
            old_tool_domain = int(
                row.get(
                    "tool_domain_match_score",
                    0,
                )
                or 0
            )

            new_responsibility = max(
                old_responsibility,
                int(
                    rule.get(
                        "minimum_responsibility_score",
                        0,
                    )
                ),
            )
            new_tool_domain = max(
                old_tool_domain,
                int(
                    rule.get(
                        "minimum_tool_domain_score",
                        0,
                    )
                ),
            )

            row[
                "responsibility_match_score"
            ] = new_responsibility
            row[
                "tool_domain_match_score"
            ] = new_tool_domain

            direct_requirement = rule.get(
                "matched_requirement"
            )
            transferable_requirement = rule.get(
                "transferable_requirement"
            )

            if direct_requirement:
                _append_unique(
                    row["matched_jd_requirements"],
                    str(direct_requirement),
                )

            if transferable_requirement:
                _append_unique(
                    row[
                        "transferable_jd_requirements"
                    ],
                    str(transferable_requirement),
                )

            debug_rows.append(
                {
                    "project": (
                        row.get("display_title")
                        or row.get("title")
                        or "Untitled Project"
                    ),
                    "rule": rule["name"],
                    "responsibility_score_before": (
                        old_responsibility
                    ),
                    "responsibility_score_after": (
                        new_responsibility
                    ),
                    "tool_domain_score_before": (
                        old_tool_domain
                    ),
                    "tool_domain_score_after": (
                        new_tool_domain
                    ),
                }
            )

    return updated_rows, debug_rows

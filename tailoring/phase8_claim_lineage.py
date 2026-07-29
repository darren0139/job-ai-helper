"""Evidence-lineage verification for Phase 8 final résumé claims."""

from __future__ import annotations

import re
from typing import Any

from tailoring.tailoring_generation_fingerprint import (
    get_effective_generation_sections,
)


LINEAGE_VERSION = "phase8-claim-lineage-v2"

_BULLET_SIMILARITY_THRESHOLD = 0.34
_BULLET_TOKEN_COVERAGE_THRESHOLD = 0.65
_SKILL_SIMILARITY_THRESHOLD = 0.85

_GENERIC_CLAIM_TOKENS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "been",
    "being",
    "built",
    "build",
    "by",
    "completed",
    "contributed",
    "created",
    "developed",
    "for",
    "from",
    "helped",
    "implemented",
    "improved",
    "in",
    "including",
    "into",
    "is",
    "made",
    "of",
    "on",
    "or",
    "project",
    "provided",
    "small",
    "supporting",
    "team",
    "the",
    "to",
    "used",
    "using",
    "was",
    "were",
    "with",
    "worked",
}

_TOKEN_ALIASES = {
    "applications": "application",
    "assets": "asset",
    "backed": "backend",
    "centralised": "centralise",
    "centralising": "centralise",
    "centralized": "centralise",
    "centralizing": "centralise",
    "connected": "connect",
    "connecting": "connect",
    "databases": "database",
    "edited": "edit",
    "editing": "edit",
    "engines": "engine",
    "features": "feature",
    "games": "game",
    "integrated": "integration",
    "integrating": "integration",
    "managers": "manager",
    "policies": "policy",
    "postgresql": "postgres",
    "queries": "query",
    "released": "release",
    "releasing": "release",
    "scripts": "script",
    "scripting": "script",
    "services": "service",
    "systems": "system",
    "workflows": "workflow",
}

_EXPLICIT_ONLY_CATEGORY_TERMS = {
    "language",
    "languages",
    "programming",
    "programming language",
    "programming languages",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _normalise(value: Any) -> str:
    text = _clean(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return " ".join(text.split())


def _phrase_tokens(value: Any) -> set[str]:
    return {
        _TOKEN_ALIASES.get(token, token)
        for token in re.findall(
            r"[a-z0-9+#]+",
            _clean(value).lower().replace("&", " and "),
        )
        if len(token) >= 2
    }


def _meaningful_tokens(value: Any) -> set[str]:
    return {
        token
        for token in _phrase_tokens(value)
        if token not in _GENERIC_CLAIM_TOKENS
    }


def _similarity(left: Any, right: Any) -> float:
    left_tokens = _phrase_tokens(left)
    right_tokens = _phrase_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    return max(
        overlap / len(left_tokens | right_tokens),
        overlap / min(len(left_tokens), len(right_tokens)),
    )


def _base_title_key(value: Any) -> str:
    text = _clean(value)
    previous = None
    while text and text != previous:
        previous = text
        text = re.sub(r"\s*\([^()]*\)\s*$", "", text).strip()
    return _normalise(text)


def _identity_keys(record: dict[str, Any]) -> set[str]:
    keys: set[str] = set()

    project_id = _clean(record.get("project_id"))
    if project_id:
        keys.add(f"id:{project_id.lower()}")

    for field in (
        "title",
        "display_title",
        "canonical_title",
        "writer_title",
        "project_key",
        "exact_title_key",
        "base_title_key",
    ):
        value = _clean(record.get(field))
        if not value:
            continue
        exact = _normalise(value)
        base = _base_title_key(value)
        if exact:
            keys.add(f"title:{exact}")
        if base:
            keys.add(f"base:{base}")

    return keys


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _dedupe_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean(value)
        key = _normalise(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _evidence_record_texts(record: dict[str, Any]) -> list[str]:
    values: list[str] = []
    evidence_records = record.get("evidence_records")
    if isinstance(evidence_records, list):
        for evidence in evidence_records:
            if not isinstance(evidence, dict):
                continue
            text = _clean(evidence.get("text"))
            if text:
                values.append(text)
    return values


def _candidate_indexes(
    generation_state: dict[str, Any],
) -> tuple[dict[str, list[str]], list[str]]:
    by_identity: dict[str, list[str]] = {}
    all_evidence: list[str] = []
    seen_candidates: set[tuple[str, str]] = set()

    for record in _walk_dicts(generation_state):
        evidence = _evidence_record_texts(record)
        if not evidence:
            continue

        candidate_signature = (
            _clean(record.get("project_id")),
            _clean(
                record.get("display_title")
                or record.get("title")
                or record.get("canonical_title")
            ),
        )
        if candidate_signature in seen_candidates:
            continue
        seen_candidates.add(candidate_signature)

        title = _clean(
            record.get("display_title")
            or record.get("title")
            or record.get("canonical_title")
        )
        candidate_texts = [title, *evidence] if title else evidence
        candidate_texts = _dedupe_texts(candidate_texts)
        all_evidence.extend(candidate_texts)

        for key in _identity_keys(record):
            by_identity.setdefault(key, []).extend(candidate_texts)

    return (
        {
            key: _dedupe_texts(values)
            for key, values in by_identity.items()
        },
        _dedupe_texts(all_evidence),
    )


def _baseline_project_index(
    baseline_resume_profile: dict[str, Any] | None,
) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}

    for project in (baseline_resume_profile or {}).get("projects", []) or []:
        if not isinstance(project, dict):
            continue
        title = _clean(project.get("title"))
        bullets = [
            _clean(value)
            for value in project.get("bullets", []) or []
            if _clean(value)
        ]
        values = _dedupe_texts([title, *bullets])
        for key in _identity_keys(project):
            index.setdefault(key, []).extend(values)

    return {
        key: _dedupe_texts(values)
        for key, values in index.items()
    }


def _allocated_bullet_index(
    generation_state: dict[str, Any],
) -> dict[str, list[dict[str, str]]]:
    index: dict[str, list[dict[str, str]]] = {}

    for record in _walk_dicts(generation_state):
        bullets = record.get("allocated_blueprint_bullets")
        bullet_ids = record.get("allocated_bullet_ids")
        if isinstance(bullets, list):
            ids = bullet_ids if isinstance(bullet_ids, list) else []
            for position, bullet in enumerate(bullets):
                text = _clean(bullet)
                if not text:
                    continue
                bullet_id = (
                    _clean(ids[position])
                    if position < len(ids)
                    else ""
                )
                key = _normalise(text)
                index.setdefault(key, []).append(
                    {
                        "bullet_id": bullet_id,
                        "project_id": _clean(record.get("project_id")),
                        "project_title": _clean(
                            record.get("display_title")
                            or record.get("title")
                        ),
                        "source": "allocated_blueprint_bullets",
                    }
                )

        bullet_text = _clean(record.get("bullet_text"))
        bullet_id = _clean(record.get("bullet_id"))
        if bullet_text and bullet_id:
            key = _normalise(bullet_text)
            index.setdefault(key, []).append(
                {
                    "bullet_id": bullet_id,
                    "project_id": _clean(record.get("project_id")),
                    "project_title": _clean(
                        record.get("project_title")
                        or record.get("title")
                    ),
                    "source": "selection_trace",
                }
            )

    return index


def _project_source_bundle(
    project: dict[str, Any],
    candidate_index: dict[str, list[str]],
    baseline_index: dict[str, list[str]],
) -> tuple[list[str], list[str]]:
    sources: list[str] = []
    methods: list[str] = []

    identity_keys = _identity_keys(project)
    for key in sorted(identity_keys):
        candidate_sources = candidate_index.get(key, [])
        if candidate_sources:
            sources.extend(candidate_sources)
            methods.append(
                "candidate_project_id"
                if key.startswith("id:")
                else (
                    "candidate_base_title"
                    if key.startswith("base:")
                    else "candidate_exact_title"
                )
            )

        baseline_sources = baseline_index.get(key, [])
        if baseline_sources:
            sources.extend(baseline_sources)
            methods.append(
                "baseline_base_title"
                if key.startswith("base:")
                else "baseline_exact_title"
            )

    title = _clean(
        project.get("display_title")
        or project.get("title")
    )
    if title:
        sources.append(title)
        methods.append("stable_project_title")

    for match in project.get("requirement_matches", []) or []:
        if not isinstance(match, dict):
            continue
        snippets = match.get("evidence_snippets")
        if isinstance(snippets, list):
            sources.extend(
                _clean(value)
                for value in snippets
                if _clean(value)
            )
            if snippets:
                methods.append("requirement_evidence_snippets")

    return _dedupe_texts(sources), sorted(set(methods))


def _numbers_supported(claim: str, evidence_corpus: str) -> bool:
    claim_numbers = set(re.findall(r"\b\d+\b", claim))
    if not claim_numbers:
        return True
    evidence_numbers = set(re.findall(r"\b\d+\b", evidence_corpus))
    return claim_numbers.issubset(evidence_numbers)


def _bullet_support(
    project: dict[str, Any],
    bullet: str,
    allocated_index: dict[str, list[dict[str, str]]],
    sources: list[str],
    identity_methods: list[str],
) -> dict[str, Any]:
    bullet_key = _normalise(bullet)
    project_id = _clean(project.get("project_id"))

    allocations = allocated_index.get(bullet_key, [])
    compatible_allocations = [
        allocation
        for allocation in allocations
        if not project_id
        or not allocation.get("project_id")
        or allocation.get("project_id") == project_id
    ]
    if compatible_allocations:
        return {
            "supported": True,
            "support_method": "deterministic_bullet_allocation",
            "supporting_bullet_ids": sorted(
                {
                    allocation.get("bullet_id", "")
                    for allocation in compatible_allocations
                    if allocation.get("bullet_id")
                }
            ),
            "best_evidence_similarity": 1.0,
            "meaningful_token_coverage": 1.0,
            "identity_methods": identity_methods,
        }

    evidence_corpus = " ".join(sources)
    individual_sources = [*sources, evidence_corpus]
    best_similarity = max(
        (_similarity(bullet, source) for source in individual_sources),
        default=0.0,
    )

    claim_tokens = _meaningful_tokens(bullet)
    evidence_tokens = _meaningful_tokens(evidence_corpus)
    token_coverage = (
        len(claim_tokens & evidence_tokens) / len(claim_tokens)
        if claim_tokens
        else 0.0
    )
    numbers_supported = _numbers_supported(bullet, evidence_corpus)
    identity_matched = any(
        method.startswith("candidate_")
        or method.startswith("baseline_")
        for method in identity_methods
    )

    supported = bool(
        identity_matched
        and numbers_supported
        and (
            best_similarity >= _BULLET_SIMILARITY_THRESHOLD
            or (
                len(claim_tokens) >= 3
                and token_coverage >= _BULLET_TOKEN_COVERAGE_THRESHOLD
            )
        )
    )

    return {
        "supported": supported,
        "support_method": (
            "project_evidence_similarity"
            if supported
            else "manual_review_required"
        ),
        "supporting_bullet_ids": [],
        "best_evidence_similarity": round(best_similarity, 3),
        "meaningful_token_coverage": round(token_coverage, 3),
        "identity_methods": identity_methods,
        "numbers_supported": numbers_supported,
    }


def _baseline_evidence_texts(
    baseline_resume_profile: dict[str, Any] | None,
) -> list[str]:
    values: list[str] = []

    for record in _walk_dicts(baseline_resume_profile or {}):
        for field in (
            "title",
            "company",
            "degree",
            "school",
            "summary",
        ):
            text = _clean(record.get(field))
            if text:
                values.append(text)

        for field in ("bullets", "courses"):
            items = record.get(field)
            if isinstance(items, list):
                values.extend(
                    _clean(value)
                    for value in items
                    if _clean(value)
                )

    skills = (baseline_resume_profile or {}).get("skills", {}) or {}
    if isinstance(skills, dict):
        for items in skills.values():
            if isinstance(items, list):
                values.extend(
                    _clean(value)
                    for value in items
                    if _clean(value)
                )

    return _dedupe_texts(values)


def _skill_rankings(
    effective_skills: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    rankings: dict[str, dict[str, Any]] = {}

    for record in _walk_dicts(effective_skills):
        skill = _clean(record.get("skill"))
        if not skill:
            continue
        if (
            "evidence_strength" not in record
            and "ranking_version" not in record
        ):
            continue

        key = _normalise(record.get("skill_key") or skill)
        existing = rankings.get(key)
        if existing is None or int(
            record.get("evidence_strength", 0) or 0
        ) > int(existing.get("evidence_strength", 0) or 0):
            rankings[key] = record

    return rankings


def _supported_skill_additions(
    effective_skills: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    additions: dict[str, dict[str, Any]] = {}

    for record in _walk_dicts(effective_skills):
        values = record.get("evidence_supported_additions")
        if not isinstance(values, list):
            continue
        for addition in values:
            if not isinstance(addition, dict):
                continue
            skill = _clean(addition.get("skill"))
            if skill:
                additions[_normalise(skill)] = addition

    direct_values = effective_skills.get("evidence_supported_additions")
    if isinstance(direct_values, list):
        for addition in direct_values:
            if not isinstance(addition, dict):
                continue
            skill = _clean(addition.get("skill"))
            if skill:
                additions[_normalise(skill)] = addition

    return additions


def _explicit_only_category(category: str) -> bool:
    normalised = _normalise(category)
    return any(
        term in normalised
        for term in _EXPLICIT_ONLY_CATEGORY_TERMS
    )


def _exact_skill_evidence(
    skill: str,
    evidence_texts: list[str],
) -> tuple[bool, str]:
    skill_key = _normalise(skill)
    for source in evidence_texts:
        source_key = _normalise(source)
        if not source_key:
            continue
        if skill_key == source_key:
            return True, source
        if len(skill_key) >= 4 and skill_key in source_key:
            return True, source
    return False, ""


def _skill_support(
    *,
    category: str,
    skill: str,
    evidence_texts: list[str],
    rankings: dict[str, dict[str, Any]],
    additions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    key = _normalise(skill)

    exact_supported, exact_source = _exact_skill_evidence(
        skill,
        evidence_texts,
    )
    if exact_supported:
        return {
            "supported": True,
            "support_method": "explicit_evidence",
            "supporting_evidence": [exact_source],
            "best_evidence_similarity": 1.0,
        }

    addition = additions.get(key)
    if isinstance(addition, dict):
        evidence_titles = [
            _clean(value)
            for value in addition.get("evidence_titles", []) or []
            if _clean(value)
        ]
        reason = _clean(addition.get("reason"))
        return {
            "supported": True,
            "support_method": "evidence_supported_addition",
            "supporting_evidence": [
                *evidence_titles,
                *([reason] if reason else []),
            ],
            "best_evidence_similarity": 1.0,
        }

    ranking = rankings.get(key)
    if (
        isinstance(ranking, dict)
        and not _explicit_only_category(category)
    ):
        evidence_strength = int(
            ranking.get("evidence_strength", 0) or 0
        )
        selected_support = bool(
            ranking.get("selected_project_support")
        )
        resume_support = bool(ranking.get("resume_support"))
        evidence_titles = [
            _clean(value)
            for value in ranking.get("evidence_titles", []) or []
            if _clean(value)
        ]
        if (
            evidence_strength >= 2
            and (selected_support or resume_support)
            and evidence_titles
        ):
            return {
                "supported": True,
                "support_method": "deterministic_skill_ranking",
                "supporting_evidence": evidence_titles,
                "best_evidence_similarity": 1.0,
                "evidence_strength": evidence_strength,
                "selected_project_support_methods": list(
                    ranking.get(
                        "selected_project_support_methods",
                        [],
                    )
                    or []
                ),
            }

    best_source = ""
    best_similarity = 0.0
    for source in evidence_texts:
        similarity = _similarity(skill, source)
        if similarity > best_similarity:
            best_similarity = similarity
            best_source = source

    if (
        not _explicit_only_category(category)
        and best_similarity >= _SKILL_SIMILARITY_THRESHOLD
    ):
        return {
            "supported": True,
            "support_method": "high_similarity_evidence",
            "supporting_evidence": [best_source] if best_source else [],
            "best_evidence_similarity": round(best_similarity, 3),
        }

    return {
        "supported": False,
        "support_method": "manual_review_required",
        "supporting_evidence": [best_source] if best_source else [],
        "best_evidence_similarity": round(best_similarity, 3),
        "explicit_evidence_required": _explicit_only_category(category),
    }


def audit_claim_lineage_v2(
    baseline_resume_profile: dict[str, Any] | None,
    generation_state: dict[str, Any],
) -> dict[str, Any]:
    effective = get_effective_generation_sections(generation_state)
    effective_projects = effective.get("projects")
    effective_skills = effective.get("skills")
    if not isinstance(effective_projects, dict):
        effective_projects = {}
    if not isinstance(effective_skills, dict):
        effective_skills = {}

    projects = [
        project
        for project in effective_projects.get(
            "recommended_projects",
            [],
        )
        or []
        if isinstance(project, dict)
    ]
    skill_lines = [
        line
        for line in effective_skills.get("skill_lines", []) or []
        if isinstance(line, dict)
    ]

    candidate_index, candidate_evidence = _candidate_indexes(
        generation_state
    )
    baseline_index = _baseline_project_index(
        baseline_resume_profile
    )
    allocated_index = _allocated_bullet_index(generation_state)

    verified_bullets: list[dict[str, Any]] = []
    bullet_risks: list[dict[str, Any]] = []

    verified_bullet_texts: list[str] = []
    for project in projects:
        title = _clean(
            project.get("display_title")
            or project.get("title")
            or "Untitled Project"
        )
        sources, identity_methods = _project_source_bundle(
            project,
            candidate_index,
            baseline_index,
        )

        for index, bullet in enumerate(
            _project_bullets_for_lineage(project)
        ):
            support = _bullet_support(
                project,
                bullet,
                allocated_index,
                sources,
                identity_methods,
            )
            row = {
                "project": title,
                "project_id": _clean(project.get("project_id")),
                "bullet_index": index,
                "bullet": bullet,
                **support,
            }
            if support["supported"]:
                verified_bullets.append(row)
                verified_bullet_texts.append(bullet)
            else:
                row["reason"] = (
                    "No stable bullet allocation or sufficiently matching "
                    "source evidence was found for this final wording."
                )
                bullet_risks.append(row)

    evidence_texts = _dedupe_texts(
        [
            *_baseline_evidence_texts(baseline_resume_profile),
            *candidate_evidence,
            *verified_bullet_texts,
        ]
    )
    skill_metadata_source = {
        "effective_skills": effective_skills,
        "generation_skills": generation_state.get("skills"),
        "generation_state": generation_state,
    }
    rankings = _skill_rankings(skill_metadata_source)
    additions = _supported_skill_additions(
        skill_metadata_source
    )

    verified_skills: list[dict[str, Any]] = []
    skill_risks: list[dict[str, Any]] = []

    for line in skill_lines:
        category = _clean(line.get("category")) or "Uncategorised"
        for value in line.get("items", []) or []:
            skill = _clean(value)
            if not skill:
                continue
            support = _skill_support(
                category=category,
                skill=skill,
                evidence_texts=evidence_texts,
                rankings=rankings,
                additions=additions,
            )
            row = {
                "category": category,
                "skill": skill,
                **support,
            }
            if support["supported"]:
                verified_skills.append(row)
            else:
                row["reason"] = (
                    "The displayed skill lacks explicit source evidence or a "
                    "supported deterministic skill-ranking record."
                )
                skill_risks.append(row)

    return {
        "lineage_version": LINEAGE_VERSION,
        "verified_project_bullet_count": len(verified_bullets),
        "verified_project_bullets": verified_bullets,
        "project_bullet_review_risks": bullet_risks,
        "verified_skill_count": len(verified_skills),
        "verified_skills": verified_skills,
        "skill_review_risks": skill_risks,
        "claim_review_required_count": (
            len(bullet_risks) + len(skill_risks)
        ),
        "support_method_counts": _support_method_counts(
            verified_bullets,
            verified_skills,
        ),
        "interpretation": (
            "Stable bullet allocation, project identity, explicit evidence, "
            "and deterministic skill-ranking records are accepted. "
            "Programming-language claims still require explicit evidence."
        ),
    }


def _project_bullets_for_lineage(
    project: dict[str, Any],
) -> list[str]:
    for key in (
        "draft_bullets",
        "rewritten_bullets",
        "bullets",
        "allocated_blueprint_bullets",
    ):
        values = project.get(key)
        if isinstance(values, list):
            cleaned = [_clean(value) for value in values if _clean(value)]
            if cleaned:
                return cleaned
    return []


def _support_method_counts(
    verified_bullets: list[dict[str, Any]],
    verified_skills: list[dict[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in [*verified_bullets, *verified_skills]:
        method = _clean(row.get("support_method")) or "unknown"
        counts[method] = counts.get(method, 0) + 1
    return counts

"""
tailoring/project_section_tailor.py

Two-stage (Option B) Projects-section tailoring.

Stage 1:
    AI evaluates every project candidate against the target JD.
    Python recalculates scores, sorts the ranking, and selects the projects.

Stage 2:
    AI writes bullets only for the Python-selected projects.
    Evidence Library bullets are treated as the canonical blueprints.
    Resume evidence may inform project scoring but is not used for final
    bullet writing.

Public functions kept compatible with the existing app:
    - build_project_candidate_pool(...)
    - tailor_projects_section(...)
    - estimate_project_section_length(...)
"""

from __future__ import annotations

import json
import re
from typing import Any

from llm import ask_json
from utils.date_sorting import period_sort_value


# ---------------------------------------------------------------------------
# Stage 1 prompt: analyse and score every project candidate
# ---------------------------------------------------------------------------

PROJECT_CANDIDATE_SCORING_PROMPT = """
Instruction:
You are an evidence-based project-fit analyst for student and junior resumes.

Task:
Evaluate every supplied project candidate against the target job-description
profile. Do not write resume bullets and do not choose project titles directly.
Return component scores and a recommended number of projects to display.

Truthfulness rules:
- Use only the supplied project evidence and JD profile.
- Do not invent projects, skills, tools, dates, metrics, responsibilities, or impact.
- Evidence Library bullets and resume bullets are evidence, not permission to infer
  experience that is not written.
- Distinguish direct evidence from transferable evidence.
- A generic technical project is not automatically relevant to every technical job.
- Do not award points because a project is already in the resume.
- Do not subtract points because a project appears only in the Evidence Library.

Scoring rules:
- Score every candidate exactly once.
- All component scores must be integers from 0 to 5.
- must_have_match_score:
  Direct support for required skills, qualifications, or critical requirements.
- responsibility_match_score:
  Support for the actual work and responsibilities described by the JD.
- tool_domain_match_score:
  Support for named tools, technologies, platforms, product type, or industry domain.
- evidence_strength_score:
  Strength, specificity, and completeness of the supplied truthful evidence.
- impact_scope_score:
  Demonstrated result, ownership, team/product scope, publication, users, or workflow.
- matched_jd_requirements must contain only clearly supported direct matches.
- transferable_jd_requirements may contain related but indirect evidence.
- Do not put the same requirement in both matched and transferable lists.
- Reasons must name specific JD requirements or responsibilities.

Domain and transferable-evidence interpretation:
- tool_domain_match_score includes relevant industry, product type, platform, and technical environment; it is not limited to exact named tools.
- A completed game-development project is direct evidence of basic gaming-industry and game-product knowledge.
- A published game provides stronger gaming-product evidence than a generic software project.
- A custom game-engine project supports gaming-industry, game-development workflow, and technical systems knowledge.
- Game-development evidence does not by itself prove professional quality-assurance or live-operations experience.
- Explicit team-project and collaboration evidence may support collaboration requirements.
- Secure database, access-control, configuration, integration, and structured workflow evidence may support configuration or meticulous operational work as transferable evidence.
- Do not set every JD-fit component to zero when a project clearly supports the role's industry, product type, tools, responsibilities, or transferable competencies.
- Evidence strength and impact measure how well a project is documented; they must not replace actual role relevance.

Scoring consistency rules:
- If matched_jd_requirements is not empty, at least one of must_have_match_score,
  responsibility_match_score, or tool_domain_match_score must be greater than 0.
- If transferable_jd_requirements is not empty, at least one of
  responsibility_match_score or tool_domain_match_score should normally be greater
  than 0.
- When a project directly proves an industry or product-domain requirement, put the
  requirement in matched_jd_requirements, not transferable_jd_requirements.
- A game-development project directly supports a requirement for basic gaming-industry
  knowledge.
- A published game should receive a non-zero tool_domain_match_score for a gaming role.
- A custom game-engine project should receive a non-zero tool_domain_match_score for a
  gaming role.
- Do not give a project all-zero JD-fit scores while simultaneously saying that it
  supports a JD requirement.

Project-count rules:
- Python will select exactly the supplied maximum number of projects when enough candidates exist.
- Do not reduce the project count merely because no project proves every critical requirement.
- Rank the strongest available transferable projects when direct matches are limited.
- recommended_project_count must equal the supplied maximum, capped only by the number of available candidates.
- Bullet allocation happens later.

Output only valid JSON matching this schema:
{
  "candidate_project_scores": [
    {
      "title": "string",
      "matched_jd_requirements": ["string"],
      "transferable_jd_requirements": ["string"],
      "must_have_match_score": 0,
      "responsibility_match_score": 0,
      "tool_domain_match_score": 0,
      "evidence_strength_score": 0,
      "impact_scope_score": 0,
      "reason": "string"
    }
  ],
  "recommended_project_count": 0,
  "project_count_reason": "string",
  "unsupported_jd_skills": [
    {
      "skill": "string",
      "reason": "No clear project evidence found in the supplied candidate pool."
    }
  ],
  "notes_for_user": ["string"]
}
"""


# ---------------------------------------------------------------------------
# Stage 2 prompt: write bullets for already-selected projects only
# ---------------------------------------------------------------------------

PROJECT_BULLET_WRITING_PROMPT = """
Instruction:
You are an honest resume bullet editor for students and junior technical
applicants.

- Do not rewrite a grammatically correct canonical bullet merely to replace words
  with synonyms.
- If a canonical bullet is clear, truthful, non-repetitive, and reasonably concise,
  copy it exactly.
- A generic reason such as "improved clarity" is not sufficient when the only change
  is a synonym substitution.


Task:
Write the Projects-section bullets only for the supplied selected project
candidates. Project selection has already been completed by Python. Do not add,
remove, replace, or re-rank project titles.

Canonical-bullet rules:
- Treat Evidence Library bullets as the only user-approved canonical bullets.
- Do not select, copy, paraphrase, or reuse bullets extracted from the resume profile.
- Prefer selecting and reordering existing Evidence Library bullets over rewriting them.
- draft_bullets should normally be identical to selected_blueprint_bullets.
- Lightly rewrite an Evidence Library bullet only when needed to:
  1. improve clarity,
  2. remove repetition,
  3. make the bullet more concise,
  4. naturally use truthful JD wording, or
  5. combine overlapping Evidence Library evidence without changing meaning.
- Never rewrite merely to sound more impressive.
- Never add a result, metric, tool, responsibility, or skill that is not supplied.
- When no usable Evidence Library bullet exists, synthesise a bullet only from
  non-bullet Evidence Library fields such as description, tools, skills, impact,
  scope, and contribution.
- Do not use resume bullet wording as fallback evidence.
- Explain any synthesised bullet in rewrite_reason.

CAR and ordering rules:
- Preserve existing strong CAR bullets.
- Each final bullet should start with an action verb where practical.
- Keep truthful Context + Action + Result/Scope where the evidence supports it.
- Order bullets from strongest JD relevance to weakest.
- The final bullet must be the safest bullet to remove during page fitting.
- Do not split one idea into several weak bullets.
- Do not create a separate teamwork bullet when team size is already clear in the
  title unless collaboration is a major JD requirement.

Length and page-use rules:
- Use no more than the supplied maximum bullets per project.
- Prefer 4-6 total bullets across all selected projects when supported.
- Stronger projects may receive more bullets; weaker selected projects may receive
  one bullet.
- Do not aggressively shorten wording for page fit. The DOCX fitting stage removes
  complete lower-priority bullets one at a time.
- Bullets should usually be concise and resume-friendly, commonly 14-24 words, but
  preserving meaning is more important than meeting a fixed word count.

Output only valid JSON matching this schema:
{
  "project_bullet_plans": [
    {
      "title": "string",
      "selected_blueprint_bullets": ["string"],
      "rewritten_bullets": ["string"],
      "rewrite_reason": "string",
      "draft_bullets": ["string"]
    }
  ],
  "notes_for_user": ["string"]
}
"""


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------


def _normalise_project_key(title: str) -> str:
    """
    Normalise project names so titles such as:
    'QueryAI (React, Team of 4)' and 'QueryAI' match.
    """
    text = str(title or "").lower().strip()
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"[-–—].*$", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _clean_string_list(value: Any) -> list[str]:
    """Return a clean, deduplicated list of non-empty strings."""
    if not isinstance(value, list):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()

    for item in value:
        text = " ".join(str(item or "").split()).strip()
        key = text.lower()

        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)

    return cleaned


def _split_description_into_bullets(description: str) -> list[str]:
    """Convert newline or symbol-separated evidence text into clean bullets."""
    text = str(description or "").strip()

    if not text:
        return []

    text = text.replace("●", "\n").replace("•", "\n").replace("", "\n")
    bullets: list[str] = []

    for line in text.splitlines():
        cleaned = line.strip().lstrip("-*•● ").strip()
        if cleaned:
            bullets.append(cleaned)

    return _clean_string_list(bullets)


def _find_resume_project_lists(value: Any) -> list[dict[str, Any]]:
    """Recursively find likely project dictionaries in a resume profile."""
    found: list[dict[str, Any]] = []

    if isinstance(value, dict):
        for key, child in value.items():
            key_lower = str(key).lower()

            if "project" in key_lower and isinstance(child, list):
                for item in child:
                    if isinstance(item, dict):
                        found.append(item)

            found.extend(_find_resume_project_lists(child))

    elif isinstance(value, list):
        for item in value:
            found.extend(_find_resume_project_lists(item))

    return found


def _candidate_source(candidate: dict[str, Any]) -> str:
    """Return the public source label expected by the existing UI."""
    in_resume = bool(candidate.get("currently_in_resume"))
    in_library = bool(candidate.get("in_evidence_library"))

    if in_resume and in_library:
        return "both"
    if in_library:
        return "evidence_library"
    return "resume"


def _candidate_action(candidate: dict[str, Any]) -> str:
    """Return the initial action for a selected project."""
    if candidate.get("currently_in_resume"):
        return "keep"
    return "add"


def _safe_component_score(value: Any) -> int:
    """Convert an AI component score to a clamped integer from 0 to 5."""
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        numeric = 0

    return max(0, min(5, numeric))

def _calculate_project_final_score(
    row: dict[str, Any],
) -> int:
    """
    Calculate a deterministic 0-100 project-fit score.

    AI component scores remain primary. Direct and transferable
    match lists provide a small consistency fallback.
    """
    must_have = row["must_have_match_score"]
    responsibility = row["responsibility_match_score"]
    tool_domain = row["tool_domain_match_score"]
    evidence_strength = row["evidence_strength_score"]
    impact_scope = row["impact_scope_score"]

    component_relevance = (
        must_have * 7
        + responsibility * 5
        + tool_domain * 4
    )

    direct_match_count = len(
        row.get("matched_jd_requirements", [])
        or []
    )

    transferable_match_count = len(
        row.get("transferable_jd_requirements", [])
        or []
    )

    # Safeguard against inconsistent responses such as:
    # transferable match present, but every relevance score is zero.
    list_based_relevance = min(
        25,
        direct_match_count * 8
        + transferable_match_count * 4,
    )

    relevance_points = max(
        component_relevance,
        list_based_relevance,
    )

    if relevance_points == 0:
        return 0

    support_points = (
        evidence_strength * 3
        + impact_scope
    )

    return min(
        100,
        relevance_points + support_points,
    )
# def _calculate_project_final_score(
#     row: dict[str, Any],
# ) -> int:
#     """
#     Calculate a deterministic 0-100 project-fit score.

#     Evidence strength improves the score only after the project has
#     some actual JD relevance.
#     """
#     must_have = row["must_have_match_score"]
#     responsibility = row["responsibility_match_score"]
#     tool_domain = row["tool_domain_match_score"]
#     evidence_strength = row["evidence_strength_score"]
#     impact_scope = row["impact_scope_score"]

#     # JD relevance: maximum 80 points.
#     relevance_points = (
#         must_have * 7
#         + responsibility * 5
#         + tool_domain * 4
#     )

#     # Evidence quality: maximum 20 points.
#     support_points = (
#         evidence_strength * 3
#         + impact_scope
#     )

#     # Strong evidence alone must not make an irrelevant project win.
#     if relevance_points == 0:
#         return 0

#     return relevance_points + support_points

def _calculate_relevance_score(
    row: dict[str, Any],
) -> float:
    """
    Return a 0-5 relevance score with a consistency fallback
    for direct and transferable match lists.
    """
    component_score = (
        row["must_have_match_score"] * 7
        + row["responsibility_match_score"] * 5
        + row["tool_domain_match_score"] * 4
    ) / 16

    direct_match_count = len(
        row.get("matched_jd_requirements", [])
        or []
    )

    transferable_match_count = len(
        row.get("transferable_jd_requirements", [])
        or []
    )

    list_based_score = min(
        5.0,
        direct_match_count * 1.0
        + transferable_match_count * 0.5,
    )

    return round(
        max(component_score, list_based_score),
        2,
    )

# def _calculate_relevance_score(row: dict[str, Any]) -> float:
#     """Return a compatible 0-5 relevance score from the three JD-fit dimensions."""
#     weighted_total = (
#         row["must_have_match_score"] * 7
#         + row["responsibility_match_score"] * 5
#         + row["tool_domain_match_score"] * 4
#     )
#     return round(weighted_total / 16, 2)


# def _priority_from_ranking_row(row: dict[str, Any]) -> str:
#     """Convert the project-fit result into the priority used by page compaction."""
#     final_score = int(row.get("final_score", 0) or 0)
#     direct_matches = len(row.get("matched_jd_requirements", []) or [])

#     if final_score >= 70 or direct_matches >= 3:
#         return "high"
#     if final_score >= 40 or direct_matches >= 1:
#         return "medium"
#     return "low"
def _priority_from_ranking_row(
    row: dict[str, Any],
) -> str:
    """Convert project fit into page-compaction priority."""
    final_score = int(
        row.get("final_score", 0)
        or 0
    )

    direct_matches = len(
        row.get("matched_jd_requirements", [])
        or []
    )

    transferable_matches = len(
        row.get("transferable_jd_requirements", [])
        or []
    )

    if final_score >= 60 or direct_matches >= 2:
        return "high"

    if (
        final_score >= 20
        or direct_matches >= 1
        or transferable_matches >= 1
    ):
        return "medium"

    return "low"

# ---------------------------------------------------------------------------
# Candidate-pool construction
# ---------------------------------------------------------------------------


def _resume_project_to_candidate(project: dict[str, Any]) -> dict[str, Any] | None:
    """Convert one resume project dictionary into the shared candidate shape."""
    title = (
        project.get("display_title")
        or project.get("title")
        or project.get("name")
        or project.get("project_name")
        or ""
    )

    if not str(title).strip():
        return None

    bullets = (
        project.get("bullets")
        or project.get("draft_bullets")
        or project.get("description_bullets")
        or []
    )

    if isinstance(bullets, str):
        bullets = _split_description_into_bullets(bullets)
    else:
        bullets = _clean_string_list(bullets)

    description = (
        project.get("description")
        or project.get("summary")
        or project.get("details")
        or ""
    )

    if not bullets and description:
        bullets = _split_description_into_bullets(description)

    return {
        "title": str(title).strip(),
        "display_title": str(project.get("display_title") or title).strip(),
        "period": str(project.get("period") or project.get("date") or "").strip(),
        "sources": ["resume"],
        "currently_in_resume": True,
        "in_evidence_library": False,
        "resume_evidence": {
            "description": str(description).strip(),
            "bullets": bullets,
            "skills": project.get("skills") or project.get("technologies") or [],
            "tools": project.get("tools") or project.get("tech_stack") or [],
            "impact": str(project.get("impact") or project.get("scope") or "").strip(),
        },
        "evidence_library_evidence": None,
    }


def _evidence_item_to_candidate(item: dict[str, Any]) -> dict[str, Any] | None:
    """Convert one Project Evidence Library item into the shared candidate shape."""
    if str(item.get("category", "")).lower().strip() != "project":
        return None

    title = str(item.get("title", "")).strip()
    if not title:
        return None

    description = str(item.get("description", "")).strip()

    return {
        "title": title,
        "display_title": title,
        "period": str(item.get("period", "")).strip(),
        "sources": ["evidence_library"],
        "currently_in_resume": False,
        "in_evidence_library": True,
        "resume_evidence": None,
        "evidence_library_evidence": {
            "description": description,
            "bullets": _split_description_into_bullets(description),
            "skills": item.get("skills", []) or [],
            "tools": item.get("tools", []) or [],
            "impact": str(item.get("impact", "")).strip(),
        },
    }


def build_project_candidate_pool(
    *,
    resume_profile: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge resume projects and Project Evidence Library records."""
    candidates_by_key: dict[str, dict[str, Any]] = {}

    for resume_project in _find_resume_project_lists(resume_profile):
        candidate = _resume_project_to_candidate(resume_project)
        if not candidate:
            continue

        key = _normalise_project_key(candidate["title"])
        if key:
            candidates_by_key[key] = candidate

    for item in evidence_items:
        candidate = _evidence_item_to_candidate(item)
        if not candidate:
            continue

        key = _normalise_project_key(candidate["title"])
        if not key:
            continue

        if key in candidates_by_key:
            existing = candidates_by_key[key]
            existing["sources"] = sorted(
                set(existing.get("sources", []) + ["evidence_library"])
            )
            existing["in_evidence_library"] = True
            existing["evidence_library_evidence"] = candidate[
                "evidence_library_evidence"
            ]

            if len(candidate["display_title"]) > len(existing.get("display_title", "")):
                existing["display_title"] = candidate["display_title"]

            if not existing.get("period") and candidate.get("period"):
                existing["period"] = candidate["period"]
        else:
            candidates_by_key[key] = candidate

    return sorted(
        candidates_by_key.values(),
        key=lambda candidate: candidate.get("title", "").lower(),
    )


# ---------------------------------------------------------------------------
# Canonical-bullet preparation
# ---------------------------------------------------------------------------


def _candidate_canonical_bullets(candidate: dict[str, Any]) -> dict[str, list[str]]:
    """
    Use Evidence Library bullets as the only approved canonical
    bullet source.
    """
    library_evidence = (
        candidate.get("evidence_library_evidence")
        or {}
    )

    library_bullets = _clean_string_list(
        library_evidence.get("bullets", [])
    )

    return {
        "preferred_canonical_bullets": library_bullets,
        "alternate_resume_bullets": [],
        "all_approved_source_bullets": library_bullets,
    }



def _prepare_selected_candidate_for_writer(
    candidate: dict[str, Any],
    ranking_row: dict[str, Any],
) -> dict[str, Any]:
    """Create a compact, evidence-rich record for the bullet-writing call."""
    canonical = _candidate_canonical_bullets(candidate)

    return {
        "title": candidate.get("title", ""),
        "display_title": candidate.get("display_title", ""),
        "period": candidate.get("period", ""),
        "source": _candidate_source(candidate),
        "currently_in_resume": bool(candidate.get("currently_in_resume")),
        "in_evidence_library": bool(candidate.get("in_evidence_library")),
        "matched_jd_requirements": ranking_row.get("matched_jd_requirements", []),
        "transferable_jd_requirements": ranking_row.get(
            "transferable_jd_requirements", []
        ),
        "ranking_reason": ranking_row.get("reason", ""),
        **canonical,
        "evidence_library_evidence": candidate.get("evidence_library_evidence"),
    }


# ---------------------------------------------------------------------------
# Stage 1: AI analysis, Python scoring, sorting, and selection
# ---------------------------------------------------------------------------

def _find_missing_scoring_candidates(
    *,
    scoring_result: dict[str, Any],
    project_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Return candidates omitted from the AI scoring response.
    """
    returned_keys = {
        _normalise_project_key(row.get("title", ""))
        for row in scoring_result.get(
            "candidate_project_scores",
            [],
        )
        if isinstance(row, dict)
        and _normalise_project_key(row.get("title", ""))
    }

    return [
        candidate
        for candidate in project_candidates
        if _normalise_project_key(
            candidate.get("title", "")
        )
        not in returned_keys
    ]


def _build_complete_ranked_rows(
    *,
    scoring_result: dict[str, Any],
    project_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Recalculate every score in Python and return a complete deterministic ranking.

    Unknown AI rows are ignored. Missing candidate rows are added with zero scores so
    every candidate remains visible for debugging.
    """
    candidates_by_key = {
        _normalise_project_key(candidate.get("title", "")): candidate
        for candidate in project_candidates
        if _normalise_project_key(candidate.get("title", ""))
    }

    ai_rows_by_key: dict[str, dict[str, Any]] = {}

    for raw_row in scoring_result.get("candidate_project_scores", []) or []:
        if not isinstance(raw_row, dict):
            continue

        key = _normalise_project_key(raw_row.get("title", ""))
        if key and key in candidates_by_key and key not in ai_rows_by_key:
            ai_rows_by_key[key] = raw_row

    ranking_rows: list[dict[str, Any]] = []

    for key, candidate in candidates_by_key.items():
        raw_row = ai_rows_by_key.get(key, {})

        component_row = {
            "must_have_match_score": _safe_component_score(
                raw_row.get("must_have_match_score", 0)
            ),
            "responsibility_match_score": _safe_component_score(
                raw_row.get("responsibility_match_score", 0)
            ),
            "tool_domain_match_score": _safe_component_score(
                raw_row.get("tool_domain_match_score", 0)
            ),
            "evidence_strength_score": _safe_component_score(
                raw_row.get("evidence_strength_score", 0)
            ),
            "impact_scope_score": _safe_component_score(
                raw_row.get("impact_scope_score", 0)
            ),
        }

        matched = _clean_string_list(raw_row.get("matched_jd_requirements", []))
        transferable = _clean_string_list(
            raw_row.get("transferable_jd_requirements", [])
        )
        matched_lower = {item.lower() for item in matched}
        transferable = [
            item for item in transferable if item.lower() not in matched_lower
        ]

        # row = {
        #     "title": candidate.get("title", ""),
        #     "display_title": candidate.get("display_title")
        #     or candidate.get("title", ""),
        #     "source": _candidate_source(candidate),
        #     "currently_in_resume": bool(candidate.get("currently_in_resume")),
        #     "in_evidence_library": bool(candidate.get("in_evidence_library")),
        #     "matched_jd_requirements": matched,
        #     "transferable_jd_requirements": transferable,
        #     **component_row,
        #     "relevance_score": _calculate_relevance_score(component_row),
        #     "reason": str(raw_row.get("reason", "")).strip()
        #     or "The scoring response did not provide a project-specific reason.",
        # }
        # row["final_score"] = _calculate_project_final_score(row)
        row = {
            "title": candidate.get("title", ""),
            "display_title": (
                candidate.get("display_title")
                or candidate.get("title", "")
            ),
            "source": _candidate_source(candidate),
            "currently_in_resume": bool(
                candidate.get("currently_in_resume")
            ),
            "in_evidence_library": bool(
                candidate.get("in_evidence_library")
            ),
            "matched_jd_requirements": matched,
            "transferable_jd_requirements": transferable,
            **component_row,
            "reason": (
                str(raw_row.get("reason", "")).strip()
                or (
                    "The scoring response did not provide "
                    "a project-specific reason."
                )
            ),
        }

        # Calculate these only after the complete row contains
        # both component scores and requirement-match lists.
        row["relevance_score"] = _calculate_relevance_score(row)
        row["final_score"] = _calculate_project_final_score(row)

        ranking_rows.append(row)

    ranking_rows.sort(
        key=lambda item: (
            item.get("final_score", 0),
            len(
                item.get(
                    "matched_jd_requirements",
                    [],
                )
                or []
            ),
            len(
                item.get(
                    "transferable_jd_requirements",
                    [],
                )
                or []
            ),
            item.get("must_have_match_score", 0),
            item.get("responsibility_match_score", 0),
            item.get("tool_domain_match_score", 0),
            item.get("evidence_strength_score", 0),
            item.get("impact_scope_score", 0),
        ),
        reverse=True,
    )

    return ranking_rows






def _resolve_selected_project_count(
    *,
    scoring_result: dict[str, Any],
    ranked_rows: list[dict[str, Any]],
    max_projects: int,
) -> int:
    """
    Always select the configured number of projects when enough
    candidates are available.

    The AI evaluates project relevance, but Python controls the
    exact number selected.
    """
    if not ranked_rows:
        return 0

    return min(
        max_projects,
        len(ranked_rows),
    )


def _select_candidates_from_ranking(
    *,
    ranked_rows: list[dict[str, Any]],
    project_candidates: list[dict[str, Any]],
    selected_count: int,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return exact candidate/ranking pairs for the Python-selected top rows."""
    candidates_by_key = {
        _normalise_project_key(candidate.get("title", "")): candidate
        for candidate in project_candidates
        if _normalise_project_key(candidate.get("title", ""))
    }

    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for ranking_row in ranked_rows[:selected_count]:
        key = _normalise_project_key(ranking_row.get("title", ""))
        candidate = candidates_by_key.get(key)
        if candidate:
            selected.append((candidate, ranking_row))

    return selected


# ---------------------------------------------------------------------------
# Stage 2: bullet writing and deterministic result assembly
# ---------------------------------------------------------------------------


def _normalise_writer_plans(writer_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index valid writer plans by normalised project title."""
    plans: dict[str, dict[str, Any]] = {}

    for plan in writer_result.get("project_bullet_plans", []) or []:
        if not isinstance(plan, dict):
            continue

        key = _normalise_project_key(plan.get("title", ""))
        if key and key not in plans:
            plans[key] = plan

    return plans


def _filter_selected_blueprints(
    requested: Any,
    approved_source_bullets: list[str],
) -> list[str]:
    """Keep only blueprint bullets that actually came from supplied evidence."""
    approved_by_key = {
        " ".join(bullet.lower().split()): bullet for bullet in approved_source_bullets
    }
    selected: list[str] = []

    for bullet in _clean_string_list(requested):
        key = " ".join(bullet.lower().split())
        approved = approved_by_key.get(key)
        if approved and approved not in selected:
            selected.append(approved)

    return selected


def _build_project_from_writer_plan(
    *,
    candidate: dict[str, Any],
    ranking_row: dict[str, Any],
    writer_plan: dict[str, Any] | None,
    max_bullets_per_project: int,
) -> dict[str, Any]:
    """
    Build one complete recommended-project record.

    Python owns the project identity and ranking metadata. The AI contributes only
    the selected/rephrased bullet wording.
    """
    canonical = _candidate_canonical_bullets(candidate)
    approved_bullets = canonical["all_approved_source_bullets"]
    plan = writer_plan or {}

    selected_blueprints = _filter_selected_blueprints(
        plan.get("selected_blueprint_bullets", []),
        approved_bullets,
    )

    if not selected_blueprints:
        selected_blueprints = approved_bullets[:max_bullets_per_project]

    selected_blueprints = selected_blueprints[:max_bullets_per_project]

    draft_bullets = _clean_string_list(plan.get("draft_bullets", []))[
        :max_bullets_per_project
    ]
    rewritten_bullets = _clean_string_list(plan.get("rewritten_bullets", []))[
        :max_bullets_per_project
    ]
    rewrite_reason = str(plan.get("rewrite_reason", "")).strip()

    # When the AI changes canonical wording without explaining why, preserve the
    # exact approved bullets instead of silently accepting an unexplained rewrite.
    if draft_bullets and selected_blueprints:
        exact_blueprint_set = {
            " ".join(item.lower().split()) for item in selected_blueprints
        }
        contains_changed_wording = any(
            " ".join(item.lower().split()) not in exact_blueprint_set
            for item in draft_bullets
        )

        if contains_changed_wording and not rewrite_reason:
            draft_bullets = list(selected_blueprints)
            rewritten_bullets = []

    if not draft_bullets:
        draft_bullets = list(selected_blueprints)

    # A project may have descriptive evidence but no pre-existing bullet. In that
    # case the writer can create a truthful bullet. Keep that result only when a
    # reason is supplied; otherwise leave the project with no generated bullet and
    # surface the issue in notes later.
    if not draft_bullets and rewrite_reason:
        draft_bullets = _clean_string_list(plan.get("draft_bullets", []))[
            :max_bullets_per_project
        ]

    if draft_bullets and not selected_blueprints and not rewrite_reason:
        rewrite_reason = (
            "No canonical bullet was available; the final wording was synthesised "
            "from the supplied project evidence."
        )

    space_action = "single_bullet" if len(draft_bullets) <= 1 else "keep_full"

    return {
        "title": candidate.get("title", ""),
        "display_title": candidate.get("display_title")
        or candidate.get("title", ""),
        "period": candidate.get("period", ""),
        "source": _candidate_source(candidate),
        "action": _candidate_action(candidate),
        "priority": _priority_from_ranking_row(ranking_row),
        "space_action": space_action,
        "matched_jd_requirements": ranking_row.get(
            "matched_jd_requirements", []
        ),
        "transferable_jd_requirements": ranking_row.get(
            "transferable_jd_requirements", []
        ),
        "why_relevant": ranking_row.get("reason", ""),
        "selected_blueprint_bullets": selected_blueprints,
        "rewritten_bullets": rewritten_bullets,
        "rewrite_reason": rewrite_reason,
        "draft_bullets": draft_bullets,
        "project_fit_score": ranking_row.get("final_score", 0),
    }


def _build_projects_to_remove(
    *,
    project_candidates: list[dict[str, Any]],
    ranked_rows: list[dict[str, Any]],
    selected_keys: set[str],
) -> list[dict[str, str]]:
    """List current-resume projects that Python did not select."""
    rank_by_key = {
        _normalise_project_key(row.get("title", "")): (index, row)
        for index, row in enumerate(ranked_rows, start=1)
    }
    removed: list[dict[str, str]] = []

    for candidate in project_candidates:
        key = _normalise_project_key(candidate.get("title", ""))

        if not candidate.get("currently_in_resume") or key in selected_keys:
            continue

        rank_number, row = rank_by_key.get(key, (None, {}))
        rank_text = f"ranked #{rank_number}" if rank_number is not None else "not ranked"
        removed.append(
            {
                "title": candidate.get("display_title")
                or candidate.get("title", "Untitled Project"),
                "reason": (
                    f"Not selected by the Python top-project step ({rank_text}, "
                    f"fit score {row.get('final_score', 0)}/100). "
                    "Higher-ranked projects were more relevant to the target JD."
                ),
            }
        )

    return removed


def _sort_recommended_projects_latest_first(
    result: dict[str, Any],
) -> dict[str, Any]:
    """Sort final display by latest period without changing selected membership."""
    result["recommended_projects"] = sorted(
        result.get("recommended_projects", []),
        key=lambda project: period_sort_value(project.get("period", "")),
        reverse=True,
    )
    return result


# ---------------------------------------------------------------------------
# Public orchestration function
# ---------------------------------------------------------------------------


def tailor_projects_section(
    *,
    resume_profile: dict[str, Any],
    jd_profile: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    max_projects: int = 3,
    max_bullets_per_project: int = 2,
    keyword_match: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate a tailored Projects section using the Option B two-stage pipeline.

    The public return shape remains compatible with the existing Streamlit and
    DOCX-generation code.
    """
    if not resume_profile:
        raise ValueError("Missing resume profile. Analyze a resume first.")

    if not jd_profile:
        raise ValueError("Missing job description profile. Analyze a job description first.")

    project_candidates = build_project_candidate_pool(
        resume_profile=resume_profile,
        evidence_items=evidence_items,
    )

    if not project_candidates:
        raise ValueError(
            "No project candidates were found in the resume profile or Evidence Library."
        )

    scoring_user_prompt = f"""
MAXIMUM PROJECTS:
{max_projects}

COMBINED PROJECT CANDIDATE POOL:
{json.dumps(project_candidates, indent=2, ensure_ascii=False)}

TARGET JOB DESCRIPTION PROFILE:
{json.dumps(jd_profile, indent=2, ensure_ascii=False)}

CURRENT RESUME-JD KEYWORD ANALYSIS (context only):
{json.dumps(keyword_match or {}, indent=2, ensure_ascii=False)}

IMPORTANT:
- The keyword analysis describes the current resume, not necessarily the Evidence
  Library. Award project points only when the candidate's own evidence supports the
  requirement.
- Include every candidate exactly once in candidate_project_scores.
"""

    scoring_result = ask_json(
        PROJECT_CANDIDATE_SCORING_PROMPT,
        scoring_user_prompt,
        temperature=0.0,
        max_tokens=4200,
    )

    # Check whether the scoring AI returned one row for every
    # project in the combined candidate pool.
    missing_candidates = _find_missing_scoring_candidates(
        scoring_result=scoring_result,
        project_candidates=project_candidates,
    )

    # Make one bounded retry for omitted projects only.
    if missing_candidates:
        retry_user_prompt = f"""
The previous response omitted some required candidates.

SCORE ONLY THESE MISSING PROJECT CANDIDATES:
{json.dumps(missing_candidates, indent=2, ensure_ascii=False)}

TARGET JOB DESCRIPTION PROFILE:
{json.dumps(jd_profile, indent=2, ensure_ascii=False)}

IMPORTANT:
- Return exactly one candidate_project_scores row for every
supplied missing candidate.
- Do not return projects that are not listed above.
- Use the same 0-5 component scoring rubric.
"""

        retry_result = ask_json(
            PROJECT_CANDIDATE_SCORING_PROMPT,
            retry_user_prompt,
            temperature=0.0,
            max_tokens=2200,
        )

        scoring_result.setdefault(
            "candidate_project_scores",
            [],
        ).extend(
            retry_result.get(
                "candidate_project_scores",
                [],
            )
            or []
        )

        # Validate the combined first and retry responses.
        missing_candidates = _find_missing_scoring_candidates(
            scoring_result=scoring_result,
            project_candidates=project_candidates,
        )

        if missing_candidates:
            missing_titles = [
                candidate.get("display_title")
                or candidate.get("title")
                or "Untitled Project"
                for candidate in missing_candidates
            ]

            raise RuntimeError(
                "Project scoring remained incomplete after one retry. "
                f"Missing projects: {missing_titles}"
            )

    # Build the ranking only after every project has been scored.
    ranked_rows = _build_complete_ranked_rows(
        scoring_result=scoring_result,
        project_candidates=project_candidates,
    )

    selected_count = _resolve_selected_project_count(
        scoring_result=scoring_result,
        ranked_rows=ranked_rows,
        max_projects=max_projects,
    )

    selected_pairs = _select_candidates_from_ranking(
        ranked_rows=ranked_rows,
        project_candidates=project_candidates,
        selected_count=selected_count,
    )

    selected_writer_candidates = [
        _prepare_selected_candidate_for_writer(candidate, ranking_row)
        for candidate, ranking_row in selected_pairs
    ]

    writing_user_prompt = f"""
MAXIMUM BULLETS PER PROJECT:
{max_bullets_per_project}

PYTHON-SELECTED PROJECT CANDIDATES:
{json.dumps(selected_writer_candidates, indent=2, ensure_ascii=False)}

TARGET JOB DESCRIPTION PROFILE:
{json.dumps(jd_profile, indent=2, ensure_ascii=False)}

IMPORTANT:
- Return one project_bullet_plans row for each supplied selected candidate.
- Do not return any project not present in PYTHON-SELECTED PROJECT CANDIDATES.
- Preserve canonical bullets unless a specific allowed rewrite reason applies.
"""

    writer_result = ask_json(
        PROJECT_BULLET_WRITING_PROMPT,
        writing_user_prompt,
        temperature=0.0,
        max_tokens=2200,
    )

    writer_plans = _normalise_writer_plans(writer_result)
    recommended_projects: list[dict[str, Any]] = []

    for candidate, ranking_row in selected_pairs:
        key = _normalise_project_key(candidate.get("title", ""))
        recommended_projects.append(
            _build_project_from_writer_plan(
                candidate=candidate,
                ranking_row=ranking_row,
                writer_plan=writer_plans.get(key),
                max_bullets_per_project=max_bullets_per_project,
            )
        )

    selected_keys = {
        _normalise_project_key(project.get("title", ""))
        for project in recommended_projects
    }

    for index, row in enumerate(ranked_rows):
        if index < selected_count:
            row["recommendation"] = "include"
        elif row.get("final_score", 0) > 0:
            row["recommendation"] = "deprioritize"
        else:
            row["recommendation"] = "exclude"

    notes = _clean_string_list(scoring_result.get("notes_for_user", []))
    notes.extend(_clean_string_list(writer_result.get("notes_for_user", [])))
    notes.append(
        f"Python selected the top {selected_count} project(s) after recalculating "
        "and sorting the project-fit scores."
    )

    missing_writer_titles = [
        candidate.get("display_title") or candidate.get("title", "")
        for candidate, _ in selected_pairs
        if _normalise_project_key(candidate.get("title", "")) not in writer_plans
    ]

    if missing_writer_titles:
        notes.append(
            "The bullet-writing response omitted these selected projects, so their "
            f"canonical bullets were used as a fallback: {missing_writer_titles}."
        )

    no_bullet_titles = [
        project.get("display_title") or project.get("title", "")
        for project in recommended_projects
        if not project.get("draft_bullets")
    ]

    if no_bullet_titles:
        notes.append(
            "No usable canonical or generated bullet was available for: "
            f"{no_bullet_titles}. Add stronger Evidence Library bullets."
        )

    result = {
        "recommended_projects": recommended_projects,
        "candidate_project_ranking": ranked_rows,
        "projects_to_remove_or_deprioritize": _build_projects_to_remove(
            project_candidates=project_candidates,
            ranked_rows=ranked_rows,
            selected_keys=selected_keys,
        ),
        "unsupported_jd_skills": scoring_result.get(
            "unsupported_jd_skills", []
        )
        or [],
        "one_page_fit": {},
        "notes_for_user": _clean_string_list(notes),
        "selection_debug": {
            "selection_owner": "python",
            "ai_requested_project_count": scoring_result.get(
                "recommended_project_count"
            ),
            "selected_project_count": selected_count,
            "selected_titles_by_rank": [
                ranking_row.get("display_title") or ranking_row.get("title", "")
                for _, ranking_row in selected_pairs
            ],
            "project_count_reason": scoring_result.get("project_count_reason", ""),
        },
    }

    fit = estimate_project_section_length(
        result,
        max_projects=max_projects,
        max_total_bullets=max_projects * max_bullets_per_project,
    )
    result["one_page_fit"] = {
        "risk": fit["risk"],
        "reason": fit["reason"],
        "recommended_project_count": fit["project_count"],
        "recommended_bullet_count": fit["bullet_count"],
    }

    return _sort_recommended_projects_latest_first(result)


# ---------------------------------------------------------------------------
# Existing UI warning helper
# ---------------------------------------------------------------------------


def estimate_project_section_length(
    tailored_result: dict[str, Any],
    *,
    max_projects: int = 3,
    max_total_bullets: int = 6,
    max_words_per_bullet: int = 28,
) -> dict[str, Any]:
    """Estimate page risk; the generated PDF remains the final authority."""
    projects = tailored_result.get("recommended_projects", [])
    project_count = len(projects)
    bullet_count = 0
    long_bullets = 0

    for project in projects:
        bullets = project.get("draft_bullets", []) or []
        bullet_count += len(bullets)

        for bullet in bullets:
            if len(str(bullet).split()) > max_words_per_bullet:
                long_bullets += 1

    risk = "low"
    reasons: list[str] = []

    if project_count > max_projects:
        risk = "high"
        reasons.append(
            f"{project_count} projects exceeds the configured limit of {max_projects}."
        )

    if bullet_count > max_total_bullets:
        risk = "high"
        reasons.append(
            f"{bullet_count} bullets exceeds the configured limit of "
            f"{max_total_bullets}."
        )

    if long_bullets > 0 and risk != "high":
        risk = "medium"
        reasons.append(
            f"{long_bullets} bullet(s) may wrap across additional resume lines."
        )

    if bullet_count >= 7 and risk == "low":
        risk = "medium"
        reasons.append(
            f"{bullet_count} project bullets may be difficult to fit "
            "alongside the existing experience and education sections."
        )

    if not reasons:
        reasons.append("Project and bullet counts look one-page friendly.")

    return {
        "risk": risk,
        "project_count": project_count,
        "bullet_count": bullet_count,
        "long_bullets": long_bullets,
        "reason": " ".join(reasons),
    }

"""
tailoring/project_section_tailor.py

AI-assisted Projects Section tailoring.

Updated version:
- Period/date is optional.
- The AI may include period if known from resume or Evidence Library.
- Only the Projects section is changed later; Work Experience stays unchanged.
"""

from __future__ import annotations

import re
import json
from typing import Any

from llm import ask_json


PROJECT_SECTION_TAILOR_PROMPT = """
Instruction:
You are an expert resume editor for students and junior technical applicants.

Task:
Recommend a tailored Projects section for a target job description using:
1. the current resume profile,
2. the target job description profile,
3. the user's Evidence Library.

Critical truthfulness rules:
- Do not invent projects, tools, skills, metrics, companies, dates, or achievements.
- Only use evidence from the resume profile or evidence library.
- If a skill is in the job description but not supported by resume/evidence, mark it as a gap.
- You may rephrase for clarity, but the meaning must stay truthful.
- If impact is not quantified, use scope indicators instead of fake numbers.
- Keep wording suitable for a student or junior applicant.
- Preserve the exact project display title from the resume or Evidence Library when available.
- The display_title should include role, tools, team size, or publication details if they were provided.
- Do not simplify "QueryAI (React, Team of 4)" into "QueryAI".
- Do not add generic role labels such as "Programmer" unless explicitly provided.

Project selection and page-use rules:
- Create the strongest truthful Projects section for the target job.
- Use the full candidate pool from both the current resume profile and Evidence Library.
- Do not prefer a project only because it is already in the resume.
- Do not ignore a project only because it appears only in the Evidence Library.
- Select projects based on relevance to the target JD, strength of evidence, and usefulness for the role.
- Target up to 3 projects when at least 3 truthful and relevant candidates exist.
- Use available page space sensibly, but never invent, exaggerate, or pad weak points.
- Prefer 4-6 total project bullets when supported by truthful evidence.
- Use 5-7 total project bullets only when the selected projects are strongly relevant, the evidence is strong, and the bullets remain concise.
- Use fewer than 4 total bullets only if evidence is limited, relevance is weak, or there are not enough suitable selected bullets.- Highly relevant projects should usually have 2-3 bullets if there is enough truthful evidence.
- Moderately relevant projects should usually have 1-2 bullets.
- Use 1 bullet only when the project is lower priority, weakly related, or has limited evidence.
- If the original resume already has strong truthful bullets that match the JD, preserve or lightly rephrase them.
- If space is tight later, the DOCX fitting step will compact the section. Do not over-compact in this first recommendation.
- Each bullet should usually be 14-24 words.
- If a project period/date is known, include it. If unknown, leave period empty.
- If fewer than 4 total project bullets are used, explain why in notes_for_user.

Candidate coverage rules:
- Evaluate all project candidates found in the resume profile and Evidence Library.
- Include every project candidate in candidate_project_ranking, even if it is not selected.
- projects_to_remove_or_deprioritize should focus on projects currently in the resume that should be replaced, shortened, or removed.
- Evidence-only projects that are not selected should still appear in candidate_project_ranking with recommendation "deprioritize" or "exclude".

Candidate scoring rules:
- Score every project in the COMBINED PROJECT CANDIDATE POOL.
- relevance_score should measure how well the project matches the target JD.
- evidence_strength_score should measure how much truthful supporting evidence exists.
- final_score should be based on relevance_score and evidence_strength_score.
- Do not add points just because a project is already in the resume.
- Do not subtract points just because a project only appears in the Evidence Library.
- recommended_projects must be selected from the highest final_score candidates unless there is a clear one-page or truthfulness reason.
- If a lower-scoring project is selected over a higher-scoring project, explain why in notes_for_user.

Stricter scoring rules:
- final_score must equal relevance_score * 2 + evidence_strength_score.
- Relevance should matter more than evidence strength.
- A project with no specific matched_jd_requirements should usually have relevance_score 3 or lower.
- Do not recommend "include" for a project with empty matched_jd_requirements unless fewer than the allowed number of projects have clear JD matches.
- Reasons must reference specific JD requirements, not generic phrases like "technical skills are useful".
- For this output, candidate_project_ranking must be sorted from highest final_score to lowest final_score.

Canonical blueprint rules:
- Treat Evidence Library project bullets as the user-approved canonical blueprint when available.
- Prefer selecting existing canonical bullets instead of rewriting from scratch.
- Do not change canonical wording just to sound more tailored.
- Lightly rephrase a canonical bullet only if it improves clarity, reduces length, or naturally matches the JD wording without changing meaning.
- If a canonical bullet is already clear and relevant, preserve it closely.
- Any rewritten bullet must preserve the same meaning as the canonical bullet.
- If the resume is too long, reduce bullet count before heavily rewriting bullet wording.
- Do not split one idea into multiple weak bullets just to fill space.
- Do not create a separate collaboration/teamwork bullet if team size is already clear in the project title, unless the JD strongly emphasizes coordination or collaboration.
- Avoid repetitive bullets that say the same thing in different words.

CAR bullet rules:
- Each draft bullet should follow compact CAR structure where possible: Context + Action + Result/Scope.
- Start each bullet with a strong action verb.
- Include the technology, system, feature, or workflow involved when relevant.
- Include a truthful result, impact, or scope indicator.
- If no metric exists, use scope indicators such as team size, published product, system area, workflow supported, or user-facing feature.
- Do not write pure task bullets that only say what was done without context or scope.
- Do not invent measurable results.
- Keep each bullet concise and resume-friendly.

Unsupported JD skill rules:
- unsupported_jd_skills must include JD requirements that are not clearly supported by the resume or Evidence Library.
- Do not leave unsupported_jd_skills empty unless every major JD requirement has clear evidence.
- If evidence is only indirect or transferable, mention it in notes_for_user instead of treating it as fully supported.

Display order rules:
- candidate_project_ranking should be sorted by final_score from highest to lowest.
- recommended_projects should contain the selected projects, but final display order may be reverse chronological by period.
- Do not change project selection just to satisfy date order.

Output only valid JSON matching this schema:
{
  "recommended_projects": [
    {
      "title": "string",
      "display_title": "string",
      "period": "string",
      "source": "resume|evidence_library|both",
      "action": "keep|add|shorten|replace",
      "priority": "high|medium|low",
      "space_action": "keep_full|shorten|single_bullet|remove",
      "matched_jd_requirements": ["string"],
      "why_relevant": "string",
      "selected_blueprint_bullets": ["string"],
      "rewritten_bullets": ["string"],
      "rewrite_reason": "string",
      "draft_bullets": ["string"]
    }
  ],
"candidate_project_ranking": [
  {
    "title": "string",
    "display_title": "string",
    "source": "resume|evidence_library|both",
    "currently_in_resume": true,
    "in_evidence_library": true,
    "relevance_score": 0,
    "evidence_strength_score": 0,
    "final_score": 0,
    "recommendation": "include|deprioritize|exclude",
    "reason": "string"
  }
],
  "projects_to_remove_or_deprioritize": [
    {
      "title": "string",
      "reason": "string"
    }
  ],
  "unsupported_jd_skills": [
    {
      "skill": "string",
      "reason": "No clear evidence found in resume or evidence library."
    }
  ],
  "one_page_fit": {
    "risk": "low|medium|high",
    "reason": "string",
    "recommended_project_count": 0,
    "recommended_bullet_count": 0
  },
  "notes_for_user": ["string"]
}

Expected behavior:
- If three relevant projects exist, recommend up to three projects.
- Give stronger projects more bullets.
- Give weaker projects fewer bullets.
- Evidence Library projects can replace current resume projects when more relevant.
- Do not invent missing details.
- draft_bullets should usually be the same as selected_blueprint_bullets or a light rewrite of them.
- If draft_bullets differ from selected_blueprint_bullets, explain why in rewrite_reason.
"""


# Example of correct output:
# {
#   "recommended_projects": [
#     {
#       "title": "QueryAI",
#       "display_title": "QueryAI (React, Team of 4)",
#       "period": "Mar 2025 - Apr 2025",
#       "source": "both",
#       "action": "keep",
#       "priority": "high",
#       "space_action": "keep_full",
#       "matched_jd_requirements": ["team collaboration", "quality assurance", "database-backed workflows"],
#       "why_relevant": "Shows backend integration, access control, and team-built application workflows relevant to configuration and QA work.",
#       "draft_bullets": [
#         "Set up the project environment and integrated React with Supabase, supporting secure database-backed workflows for a team-built application.",
#         "Implemented backend query workflows using PostgREST, improving data retrieval and update reliability."
#       ]
#     },
#     {
#       "title": "CyberSphere",
#       "display_title": "CyberSphere (Unity Engine, Team of 2, Published on Google Play)",
#       "period": "Jan 2018 - Feb 2018",
#       "source": "both",
#       "action": "keep",
#       "priority": "high",
#       "space_action": "keep_full",
#       "matched_jd_requirements": ["gaming product", "quality assurance", "attention to detail"],
#       "why_relevant": "Shows practical game development experience and quality-focused gameplay/UI implementation.",
#       "draft_bullets": [
#         "Scripted gameplay features, UI elements, and high-score tracking for a published Unity mobile game."
#       ]
#     },
#     {
#       "title": "The Great Migration",
#       "display_title": "The Great Migration (C++ Custom Engine, Team of 8)",
#       "period": "Sep 2023 - Apr 2024",
#       "source": "both",
#       "action": "keep",
#       "priority": "medium",
#       "space_action": "single_bullet",
#       "matched_jd_requirements": ["gaming industry", "technical detail", "team collaboration"],
#       "why_relevant": "Shows game engine development, technical attention to detail, and collaboration in a larger team project.",
#       "draft_bullets": [
#         "Built a C++ asset manager for a custom game engine, centralising asset loading for an 8-person project."
#       ]
#     }
#   ],
#   "candidate_project_ranking": [
#     {
#       "title": "QueryAI",
#       "display_title": "QueryAI (React, Team of 4)",
#       "source": "both",
#       "priority": "high",
#       "recommendation": "include",
#       "reason": "Relevant to configuration-style workflows, database-backed systems, and team-built application quality."
#     },
#     {
#       "title": "CyberSphere",
#       "display_title": "CyberSphere (Unity Engine, Team of 2, Published on Google Play)",
#       "source": "both",
#       "priority": "high",
#       "recommendation": "include",
#       "reason": "Strongest direct game product project and useful for gaming operations roles."
#     },
#     {
#       "title": "The Great Migration",
#       "display_title": "The Great Migration (C++ Custom Engine, Team of 8)",
#       "source": "both",
#       "priority": "medium",
#       "recommendation": "include",
#       "reason": "Shows game engine systems, technical detail, and team collaboration."
#     },
#     {
#       "title": "Workout Buddy",
#       "display_title": "Workout Buddy (Android Studio, Team of 5)",
#       "source": "evidence_library",
#       "priority": "medium",
#       "recommendation": "deprioritize",
#       "reason": "Shows team coordination, but is less directly related to gaming operations than the game projects."
#     },
#     {
#       "title": "Job AI Helper",
#       "display_title": "Job AI Helper (Python, Streamlit, Solo)",
#       "source": "evidence_library",
#       "priority": "low",
#       "recommendation": "exclude",
#       "reason": "Useful AI project, but less relevant to a game operations QA role than game and configuration-related projects."
#     }
#   ],
#   "projects_to_remove_or_deprioritize": [
#     {
#       "title": "Workout Buddy",
#       "reason": "Less directly related to gaming operations and QA than CyberSphere or The Great Migration."
#     },
#     {
#       "title": "Job AI Helper",
#       "reason": "Strong technical project, but not as aligned with game operations QA for this specific job."
#     }
#   ],
#   "unsupported_jd_skills": [
#     {
#       "skill": "minimum 1 year of experience in quality assurance",
#       "reason": "No clear evidence found in resume or evidence library."
#     },
#     {
#       "skill": "live operations",
#       "reason": "No clear evidence found in resume or evidence library."
#     }
#   ],
#   "one_page_fit": {
#     "risk": "low",
#     "reason": "The section uses three projects with four total bullets, keeping the weaker third project compact.",
#     "recommended_project_count": 3,
#     "recommended_bullet_count": 4
#   },
#   "notes_for_user": [
#     "Used three projects because space is available and at least three relevant supported candidates exist.",
#     "Gave more detail to stronger projects and only one bullet to the third project."
#   ]
# }

def _normalise_project_key(title: str) -> str:
    """
    Normalise project names so:
    'QueryAI (React, Team of 4)' and 'QueryAI' are treated as the same project.
    """
    text = str(title or "").lower().strip()
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"[-–—].*$", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


_MONTH_TO_NUMBER = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _period_sort_value(period: str) -> tuple[int, int]:
    """
    Convert a project period into a sortable latest date.

    Examples:
    'Mar 2025 - Apr 2025' -> (2025, 4)
    'Sep 2023 - Apr 2024' -> (2024, 4)
    'Jan 2018 - Feb 2018' -> (2018, 2)
    Unknown dates go last.
    """
    text = str(period or "").lower().strip()

    if not text:
        return (0, 0)

    if "present" in text or "current" in text:
        return (9999, 12)

    matches = re.findall(
        r"(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)?\s*(20\d{2}|19\d{2})",
        text,
    )

    if not matches:
        return (0, 0)

    month_text, year_text = matches[-1]
    year = int(year_text)
    month = _MONTH_TO_NUMBER.get(month_text, 12) if month_text else 12

    return (year, month)


def _sort_recommended_projects_latest_first(result: dict[str, Any]) -> dict[str, Any]:
    """
    Sort only the final displayed recommended_projects by latest date first.

    Keep candidate_project_ranking as score/ranking order for debugging.
    """
    projects = result.get("recommended_projects", [])

    if isinstance(projects, list):
        result["recommended_projects"] = sorted(
            projects,
            key=lambda project: _period_sort_value(project.get("period", "")),
            reverse=True,
        )

    return result

def _split_description_into_bullets(description: str) -> list[str]:
    """
    Convert evidence description into clean bullet-like lines.
    Works for newline bullets and inline bullet symbols.
    """
    text = str(description or "").strip()

    if not text:
        return []

    # Handle cases like: "• did A • did B • did C"
    # text = text.replace("●", "\n").replace("•", "\n")
    text = text.replace("●", "\n").replace("•", "\n").replace("", "\n")

    bullets = []

    for line in text.splitlines():
        # cleaned = line.strip().lstrip("-*•● ").strip()
        cleaned = line.strip().lstrip("-*•● ").strip()

        if cleaned:
            bullets.append(cleaned)

    return bullets


def _find_resume_project_lists(value: Any) -> list[dict[str, Any]]:
    """
    Recursively find likely project dictionaries inside resume_profile.

    This is defensive because different extract_resume_profile outputs may use
    slightly different keys.
    """
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


def _resume_project_to_candidate(project: dict[str, Any]) -> dict[str, Any] | None:
    """Convert one resume project dict into a standard candidate shape."""
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

    description = (
        project.get("description")
        or project.get("summary")
        or project.get("details")
        or ""
    )

    if not bullets and description:
        bullets = _split_description_into_bullets(description)

    skills = project.get("skills") or project.get("technologies") or []
    tools = project.get("tools") or project.get("tech_stack") or []

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
            "skills": skills,
            "tools": tools,
            "impact": str(project.get("impact") or project.get("scope") or "").strip(),
        },
        "evidence_library_evidence": None,
    }


def _evidence_item_to_candidate(item: dict[str, Any]) -> dict[str, Any] | None:
    """Convert one Evidence Library item into a standard candidate shape."""
    category = str(item.get("category", "")).lower().strip()

    if category != "project":
        return None

    title = str(item.get("title", "")).strip()

    if not title:
        return None

    description = str(item.get("description", "")).strip()
    bullets = _split_description_into_bullets(description)

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
            "bullets": bullets,
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
    """
    Build one combined project candidate pool from resume projects + Evidence Library.

    This reduces LLM inconsistency because the model no longer has to infer
    and merge project candidates from two separate sections by itself.
    """
    candidates_by_key: dict[str, dict[str, Any]] = {}

    # 1. Add resume projects.
    for resume_project in _find_resume_project_lists(resume_profile):
        candidate = _resume_project_to_candidate(resume_project)

        if not candidate:
            continue

        key = _normalise_project_key(candidate["title"])

        if not key:
            continue

        candidates_by_key[key] = candidate

    # 2. Merge Evidence Library projects.
    for item in evidence_items:
        candidate = _evidence_item_to_candidate(item)

        if not candidate:
            continue

        key = _normalise_project_key(candidate["title"])

        if not key:
            continue

        if key in candidates_by_key:
            existing = candidates_by_key[key]

            existing["sources"] = sorted(set(existing.get("sources", []) + ["evidence_library"]))
            existing["in_evidence_library"] = True
            existing["evidence_library_evidence"] = candidate["evidence_library_evidence"]

            # Prefer evidence title if it contains fuller display info.
            if len(candidate["display_title"]) > len(existing.get("display_title", "")):
                existing["display_title"] = candidate["display_title"]

            if not existing.get("period") and candidate.get("period"):
                existing["period"] = candidate["period"]

        else:
            candidates_by_key[key] = candidate

    candidates = list(candidates_by_key.values())

    return sorted(candidates, key=lambda candidate: candidate.get("title", "").lower())
    # # Stable order: resume/evidence both first, then evidence-only, then resume-only.
    # def sort_key(candidate: dict[str, Any]) -> tuple[int, str]:
    #     sources = set(candidate.get("sources", []))

    #     if sources == {"resume", "evidence_library"}:
    #         source_rank = 0
    #     elif "evidence_library" in sources:
    #         source_rank = 1
    #     else:
    #         source_rank = 2

    #     return (source_rank, candidate.get("title", "").lower())

    # return sorted(candidates, key=sort_key)




def _postprocess_project_tailoring_result(
    result: dict[str, Any],
    *,
    project_candidates: list[dict[str, Any]],
    max_projects: int,
) -> dict[str, Any]:
    """
    Add debug notes and auto-fill removed/deprioritized current resume projects.
    """
    selected_keys = {
        _normalise_project_key(project.get("title", ""))
        for project in result.get("recommended_projects", [])
    }

    existing_removed_keys = {
        _normalise_project_key(project.get("title", ""))
        for project in result.get("projects_to_remove_or_deprioritize", [])
    }

    # Auto-fill resume projects that were not selected.
    auto_removed = []

    for candidate in project_candidates:
        candidate_key = _normalise_project_key(candidate.get("title", ""))

        if not candidate_key:
            continue

        if (
            candidate.get("currently_in_resume")
            and candidate_key not in selected_keys
            and candidate_key not in existing_removed_keys
        ):
            auto_removed.append(
                {
                    "title": candidate.get("display_title") or candidate.get("title"),
                    "reason": (
                        "Currently in the resume but not selected for this tailored version. "
                        "Another project was judged more relevant to the target job."
                    ),
                }
            )

    if auto_removed:
        result.setdefault("projects_to_remove_or_deprioritize", [])
        result["projects_to_remove_or_deprioritize"].extend(auto_removed)

    # Warn if selected projects do not match the AI's own score ranking.
    ranked = sorted(
        result.get("candidate_project_ranking", []),
        key=lambda item: item.get("final_score", 0),
        reverse=True,
    )

    result["candidate_project_ranking"] = ranked

    selected_titles = {
        _normalise_project_key(project.get("title", ""))
        for project in result.get("recommended_projects", [])
    }

    top_titles = {
        _normalise_project_key(project.get("title", ""))
        for project in ranked[:max_projects]
    }

    if ranked and not top_titles.issubset(selected_titles):
        result.setdefault("notes_for_user", []).append(
            "Debug note: selected projects do not exactly match the top scored candidates. "
            "Review candidate_project_ranking."
        )
    
    result = _sort_recommended_projects_latest_first(result)

    return result
    

def tailor_projects_section(
    *,
    resume_profile: dict[str, Any],
    jd_profile: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    max_projects: int = 3,
    max_bullets_per_project: int = 2,
) -> dict[str, Any]:
    """Generate a tailored Projects section recommendation."""
    if not resume_profile:
        raise ValueError("Missing resume profile. Analyze a resume first.")

    if not jd_profile:
        raise ValueError("Missing job description profile. Analyze a job description first.")


    project_candidates = build_project_candidate_pool(
      resume_profile=resume_profile,
      evidence_items=evidence_items,
    )


    user_prompt = f"""
PROJECT SELECTION GOAL:
Create the strongest truthful Projects section for this target job.
Use the page well, but do not force extra bullets if the evidence is weak.

IMPORTANT:
Use COMBINED PROJECT CANDIDATE POOL as the main source of project candidates and bullet wording.
When evidence_library_evidence.bullets exists, treat those bullets as the preferred master bullets.
The current resume profile is context, not a preference signal.
Do not choose a project just because it is already in the resume.
Do not ignore a project just because it only appears in the Evidence Library.

LIMITS:
- Maximum projects: {max_projects}
- Maximum bullets per project: {max_bullets_per_project}
- Prefer 4-6 total project bullets when supported by evidence.
- Do not invent, exaggerate, or pad content just to fill space.
- Preserve strong existing truthful bullets from the Evidence Library or resume when they match the job.
- If fewer than 4 total bullets are used, explain why in notes_for_user.

COMBINED PROJECT CANDIDATE POOL:
{json.dumps(project_candidates, indent=2, ensure_ascii=False)}


TARGET JOB DESCRIPTION PROFILE:
{json.dumps(jd_profile, indent=2, ensure_ascii=False)}

CURRENT RESUME PROJECT TITLES ONLY:
{json.dumps(
    [
        candidate.get("title", "")
        for candidate in project_candidates
        if candidate.get("currently_in_resume")
    ],
    indent=2,
    ensure_ascii=False,
)}

TASK:
Recommend a tailored Projects section for this target job.

Selection rules:
- Pick from COMBINED PROJECT CANDIDATE POOL only.
- For source:
  - use "resume" only if currently_in_resume is true and in_evidence_library is false
  - use "evidence_library" only if currently_in_resume is false and in_evidence_library is true
  - use "both" if currently_in_resume and in_evidence_library are both true
- For action:
  - use "keep" if the selected project is already in the resume
  - use "add" if the selected project only comes from Evidence Library
  - use "replace" if an Evidence Library project should replace a less relevant resume project
  - use "shorten" if an existing resume project should stay but with fewer/shorter bullets
- Include every candidate from COMBINED PROJECT CANDIDATE POOL in candidate_project_ranking.
"""

    result = ask_json(
    PROJECT_SECTION_TAILOR_PROMPT,
    user_prompt,
    temperature=0.0,
    max_tokens=2500,
    )

    result = _postprocess_project_tailoring_result(
    result,
    project_candidates=project_candidates,
    max_projects=max_projects,
    )


    return result

    # return ask_json(
    #     PROJECT_SECTION_TAILOR_PROMPT,
    #     user_prompt,
    #     temperature=0.0,
    #     max_tokens=2500,
    # )


def estimate_project_section_length(
    tailored_result: dict[str, Any],
    *,
    max_projects: int = 3,
    max_total_bullets: int = 6,
    max_words_per_bullet: int = 28,
) -> dict[str, Any]:
    """
    Estimate one-page fit using simple rules.

    This is not exact Word/PDF pagination. It is a warning system.
    """
    projects = tailored_result.get("recommended_projects", [])
    project_count = len(projects)
    bullet_count = 0
    long_bullets = 0

    for project in projects:
        bullets = project.get("draft_bullets", [])
        bullet_count += len(bullets)

        for bullet in bullets:
            if len(str(bullet).split()) > max_words_per_bullet:
                long_bullets += 1

    risk = "low"
    reasons: list[str] = []

    if project_count > max_projects:
        risk = "high"
        reasons.append(f"{project_count} projects exceeds recommended limit of {max_projects}.")

    if bullet_count > max_total_bullets:
        risk = "high"
        reasons.append(f"{bullet_count} bullets exceeds recommended limit of {max_total_bullets}.")

    if long_bullets > 0 and risk != "high":
        risk = "medium"
        reasons.append(f"{long_bullets} bullet(s) may be too long for a one-page resume.")

    if not reasons:
        reasons.append("Project count and bullet count look one-page friendly.")

    return {
        "risk": risk,
        "project_count": project_count,
        "bullet_count": bullet_count,
        "long_bullets": long_bullets,
        "reason": " ".join(reasons),
    }

"""
tailoring/skills_section_tailor.py

Generate a tailored Skills section using:
- current resume profile
- target JD profile
- evidence library

The output is meant to update only the Skills section in an edited DOCX copy.
It does not change work experience.
"""

from __future__ import annotations

import json
from typing import Any

from llm import ask_json
from tailoring.stable_tailoring_ranking import (
    build_deterministic_skills_result,
)


SKILLS_SECTION_TAILOR_PROMPT = """
Instruction:
You are an honest resume skills-section editor for students and junior technical applicants.

Task:
Create a tailored Skills section for the target job description.

Inputs:
1. Current resume profile
2. Target job description profile
3. User Evidence Library

Rules:
- Do not invent skills, tools, frameworks, or technologies.
- A skill/tool can be recommended only if it appears in the current resume profile or is clearly supported by the Evidence Library.
- Do not modify work experience.
- Prefer skills/tools required or preferred by the JD.
- Avoid overstuffing, but do not remove useful supported skills that are relevant to the JD.
- Use concise resume-friendly categories.
- Prefer stable, reusable skill names over overly tailored wording.
- Preserve important existing skills when they are relevant to the target JD.
- Prefer skills/tools supported by multiple evidence items or strong project evidence.
- If a JD skill is not supported by resume/evidence, put it under unsupported_jd_skills.
- If a skill is supported by evidence but missing from the current resume, put it under evidence_supported_additions.
- Keep output suitable for a one-page resume.
- Do not add generic soft skills unless clearly supported by project, internship, or teamwork evidence.
- Return one skill_priorities row for every item included in skill_lines.
- jd_relevance and evidence_strength must be integers from 0 to 5.
- required_match is true only when the skill directly supports a required JD item or core responsibility.
- preferred_match is true only when the skill directly supports a preferred JD item.
- Priority metadata is diagnostic only. Phase 6B Python recalculates the final
  supported skill pool, priorities, categories, and ordering.

Transferable evidence rules:
- If a JD requirement is not directly proven but has related evidence, do not mark it as fully unsupported.
- Put it in notes as "transferable evidence" instead.
- For example, game projects can support basic gaming industry knowledge, but not necessarily live operations.
- Do not list soft traits such as "Attention to Detail" as a hard skill line unless strongly supported; mention them in notes instead.

Strict QA evidence rules:
- Do not add Quality Assurance or QA under evidence_supported_additions unless the supplied evidence explicitly mentions testing, test cases, defect identification, bug reporting, regression testing, validation, or QA responsibilities.
- Game development alone does not prove quality-assurance experience.
- Game-development evidence may support gaming-industry knowledge, but QA must remain unsupported or be described only as transferable exposure when no explicit testing evidence exists.

Category consistency rules:
- Put SQL under Backend & Database, not Tools.
- Put PostgreSQL, Supabase, databases, APIs, and access-control technologies under
  Backend & Database.
- Put Git, GitHub, Visual Studio, Android Studio, Docker, and development utilities
  under Tools or Web & App as appropriate.

Recommended categories:
- Programming
- AI & Data
- Backend & Database
- Web & App
- Game & Engine
- Tools

Output only valid JSON matching this schema:
{
  "skill_lines": [
    {
      "category": "string",
      "items": ["string"]
    }
  ],
  "skill_priorities": [
    {
      "skill": "string",
      "jd_relevance": 0,
      "evidence_strength": 0,
      "required_match": false,
      "preferred_match": false,
      "reason": "string"
    }
  ],
  "evidence_supported_additions": [
    {
      "skill": "string",
      "evidence_titles": ["string"],
      "reason": "string"
    }
  ],
  "unsupported_jd_skills": [
    {
      "skill": "string",
      "reason": "No clear evidence found in resume or evidence library."
    }
  ],
  "notes": ["string"]
}
"""


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalise_skill_key(value: Any) -> str:
    return "".join(
        character.lower()
        for character in _clean_text(value)
        if character.isalnum()
    )


def _safe_score(value: Any) -> int:
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        numeric = 0
    return max(0, min(5, numeric))


def _normalise_skills_result(
    raw_result: dict[str, Any],
    *,
    resume_profile: dict[str, Any],
    jd_profile: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Clean the AI result and ensure every displayed skill has priority metadata."""
    result = dict(raw_result or {})
    clean_lines: list[dict[str, Any]] = []
    displayed_skills: list[str] = []
    seen_skills: set[str] = set()

    for raw_line in result.get("skill_lines", []) or []:
        if not isinstance(raw_line, dict):
            continue

        category = _clean_text(raw_line.get("category"))
        items: list[str] = []

        for raw_item in raw_line.get("items", []) or []:
            item = _clean_text(raw_item)
            key = _normalise_skill_key(item)
            if item and key and key not in seen_skills:
                items.append(item)
                displayed_skills.append(item)
                seen_skills.add(key)

        if category and items:
            clean_lines.append({"category": category, "items": items})

    result["skill_lines"] = clean_lines

    raw_priorities: dict[str, dict[str, Any]] = {}
    for raw_priority in result.get("skill_priorities", []) or []:
        if not isinstance(raw_priority, dict):
            continue
        skill = _clean_text(raw_priority.get("skill"))
        key = _normalise_skill_key(skill)
        if key and key not in raw_priorities:
            raw_priorities[key] = raw_priority

    required_text = json.dumps(
        {
            "required_skills": jd_profile.get("required_skills", []),
            "responsibilities": jd_profile.get("responsibilities", []),
            "tools_technologies": jd_profile.get("tools_technologies", []),
        },
        ensure_ascii=False,
    ).lower()
    preferred_text = json.dumps(
        jd_profile.get("preferred_skills", []),
        ensure_ascii=False,
    ).lower()
    evidence_text = json.dumps(
        {
            "resume_profile": resume_profile,
            "evidence_items": evidence_items,
        },
        ensure_ascii=False,
    ).lower()

    priorities: list[dict[str, Any]] = []

    for skill in displayed_skills:
        key = _normalise_skill_key(skill)
        raw_priority = raw_priorities.get(key, {})
        skill_lower = skill.lower()
        direct_required = skill_lower in required_text
        direct_preferred = skill_lower in preferred_text
        occurrence_count = evidence_text.count(skill_lower)

        ai_relevance = _safe_score(raw_priority.get("jd_relevance"))
        ai_evidence = _safe_score(raw_priority.get("evidence_strength"))

        jd_relevance = max(
            ai_relevance,
            5 if direct_required else 4 if direct_preferred else 0,
        )
        evidence_strength = max(
            ai_evidence,
            min(5, occurrence_count) if occurrence_count else 1,
        )

        priorities.append(
            {
                "skill": skill,
                "jd_relevance": jd_relevance,
                "evidence_strength": evidence_strength,
                "required_match": bool(
                    raw_priority.get("required_match") or direct_required
                ),
                "preferred_match": bool(
                    raw_priority.get("preferred_match") or direct_preferred
                ),
                "reason": _clean_text(raw_priority.get("reason"))
                or "Priority derived from the saved JD and supplied evidence.",
            }
        )

    result["skill_priorities"] = priorities
    return result


def tailor_skills_section(
    *,
    resume_profile: dict[str, Any],
    jd_profile: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    stable_analysis: dict[str, Any] | None = None,
    selected_projects_result: dict[str, Any] | None = None,
    max_items: int = 20,
    backend: str | None = None,
) -> dict[str, Any]:
    """Generate a tailored Skills section recommendation."""
    if not resume_profile:
        raise ValueError("Missing resume profile. Analyze a resume first.")

    if not jd_profile:
        raise ValueError("Missing job description profile. Analyze a job description first.")

    stable_analysis = stable_analysis or {}
    if not stable_analysis.get("canonical_requirements"):
        raise ValueError(
            "Phase 6B requires the Phase 6A.1C stable analysis. "
            "Analyze the resume again before generating Skills."
        )

    user_prompt = f"""
CURRENT RESUME PROFILE:
{json.dumps(resume_profile, indent=2, ensure_ascii=False)}

TARGET JOB DESCRIPTION PROFILE:
{json.dumps(jd_profile, indent=2, ensure_ascii=False)}

USER EVIDENCE LIBRARY:
{json.dumps(evidence_items, indent=2, ensure_ascii=False)}

PHASE 6A.1C CANONICAL REQUIREMENTS:
{json.dumps(stable_analysis.get("canonical_requirements", []), indent=2, ensure_ascii=False)}

PYTHON-SELECTED PROJECTS (context for final deterministic skill priorities):
{json.dumps((selected_projects_result or {}).get("recommended_projects", []), indent=2, ensure_ascii=False)}

TASK:
Create a concise tailored Skills section for this target job.
"""

    raw_result = ask_json(
        SKILLS_SECTION_TAILOR_PROMPT,
        user_prompt,
        temperature=0.0,
        max_tokens=2200,
        backend=backend,
        operation="tailor-skills",
    )

    normalised_result = _normalise_skills_result(
        raw_result,
        resume_profile=resume_profile,
        jd_profile=jd_profile,
        evidence_items=evidence_items,
    )

    return build_deterministic_skills_result(
        raw_result=normalised_result,
        resume_profile=resume_profile,
        evidence_items=evidence_items,
        stable_analysis=stable_analysis,
        selected_projects_result=selected_projects_result,
        max_items=max_items,
    )


def skill_lines_to_plain_text(skill_result: dict[str, Any]) -> str:
    """Convert skill_lines JSON into compact text lines."""
    lines: list[str] = []

    for row in skill_result.get("skill_lines", []):
        category = str(row.get("category", "")).strip()
        items = [str(item).strip() for item in row.get("items", []) if str(item).strip()]

        if category and items:
            lines.append(f"{category}: {', '.join(items)}")

    return "\n".join(lines)

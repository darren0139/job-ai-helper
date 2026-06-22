"""
tailoring/project_section_tailor.py

AI-assisted Projects Section tailoring.

Updated version:
- Period/date is optional.
- The AI may include period if known from resume or Evidence Library.
- Only the Projects section is changed later; Work Experience stays unchanged.
"""

from __future__ import annotations

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

One-page constraints:
- Recommend at most 3 projects.
- Recommend at most 2 bullets per project.
- Each bullet should be 18-28 words where possible.
- Prioritize projects that match required skills/tools from the JD.
- If space is limited, prefer stronger relevant projects over weaker unrelated projects.
- Recency is useful, but relevance should matter more than date.
- If a project period/date is known, include it. If unknown, leave period empty.

Output only valid JSON matching this schema:
{
  "recommended_projects": [
    {
      "title": "string",
      "display_title": "string",
      "period": "string",
      "source": "resume|evidence_library|both",
      "action": "keep|add|shorten|replace",
      "matched_jd_requirements": ["string"],
      "why_relevant": "string",
      "draft_bullets": ["string"]
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

Example of correct output:
{
  "recommended_projects": [
    {
      "title": "QueryAI",
      "display_title": "QueryAI (React, Team of 4)",
      "period": "Mar 2025 - Apr 2025",
      "source": "resume",
      "action": "keep",
      "matched_jd_requirements": ["React", "Supabase", "PostgreSQL"],
      "why_relevant": "Shows backend integration and database-backed application work.",
      "draft_bullets": [
        "Integrated React with Supabase/PostgreSQL, enabling authenticated database-backed workflows for a team-built query application.",
        "Implemented backend query workflows using PostgREST, supporting real-time database retrieval and updates."
      ]
    }
  ],
  "projects_to_remove_or_deprioritize": [],
  "unsupported_jd_skills": [],
  "one_page_fit": {
    "risk": "low",
    "reason": "The recommended section uses one project with two concise bullets.",
    "recommended_project_count": 1,
    "recommended_bullet_count": 2
  },
  "notes_for_user": [
    "Preserved the full project display title including tools and team size."
  ]
}



"""


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

    user_prompt = f"""
ONE-PAGE CONSTRAINTS:
- Maximum projects: {max_projects}
- Maximum bullets per project: {max_bullets_per_project}

CURRENT RESUME PROFILE:
{json.dumps(resume_profile, indent=2, ensure_ascii=False)}

TARGET JOB DESCRIPTION PROFILE:
{json.dumps(jd_profile, indent=2, ensure_ascii=False)}

USER EVIDENCE LIBRARY:
{json.dumps(evidence_items, indent=2, ensure_ascii=False)}

TASK:
Recommend a tailored Projects section for this target job.
"""

    return ask_json(
        PROJECT_SECTION_TAILOR_PROMPT,
        user_prompt,
        temperature=0.2,
        max_tokens=2500,
    )


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

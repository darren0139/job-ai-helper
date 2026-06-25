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
- Use fewer than 4 total bullets only if evidence is limited, relevance is weak, or the page is likely crowded.
- Highly relevant projects should usually have 2-3 bullets if there is enough truthful evidence.
- Moderately relevant projects should usually have 1-2 bullets.
- Use 1 bullet only when the project is lower priority, weakly related, or has limited evidence.
- If the original resume already has strong truthful bullets that match the JD, preserve or lightly rephrase them.
- If space is tight later, the DOCX fitting step will compact the section. Do not over-compact in this first recommendation.
- Each bullet should usually be 14-24 words.
- If a project period/date is known, include it. If unknown, leave period empty.
- If fewer than 4 total project bullets are used, explain why in notes_for_user.


Critical truthfulness rules:
- Evaluate all project candidates found in the resume profile and Evidence Library.
- Include every project candidate in candidate_project_ranking, even if it is not selected.
- projects_to_remove_or_deprioritize should focus on projects currently in the resume that should be replaced, shortened, or removed.
- Evidence-only projects that are not selected should still appear in candidate_project_ranking with recommendation "deprioritize" or "exclude".

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
      "draft_bullets": ["string"]
    }
  ],
    "candidate_project_ranking": [
    {
      "title": "string",
      "display_title": "string",
      "source": "resume|evidence_library|both",
      "priority": "high|medium|low",
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
PROJECT SELECTION GOAL:
Create the strongest truthful Projects section for this target job.
Use the page well, but do not force extra bullets if the evidence is weak.

LIMITS:
- Maximum projects: {max_projects}
- Maximum bullets per project: {max_bullets_per_project}
- Prefer 4-6 total project bullets when supported by evidence.
- Do not invent, exaggerate, or pad content just to fill space.
- Preserve strong existing truthful bullets when they match the job.
- Consider projects from both the current resume and Evidence Library equally.
- A project from the Evidence Library may replace a current resume project if it is more relevant.
- If fewer than 4 total bullets are used, explain why in notes_for_user.

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

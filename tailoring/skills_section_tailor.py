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

Transferable evidence rules:
- If a JD requirement is not directly proven but has related evidence, do not mark it as fully unsupported.
- Put it in notes as "transferable evidence" instead.
- For example, game projects can support basic gaming industry knowledge, but not necessarily live operations.
- Do not list soft traits such as "Attention to Detail" as a hard skill line unless strongly supported; mention them in notes instead.


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


def tailor_skills_section(
    *,
    resume_profile: dict[str, Any],
    jd_profile: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate a tailored Skills section recommendation."""
    if not resume_profile:
        raise ValueError("Missing resume profile. Analyze a resume first.")

    if not jd_profile:
        raise ValueError("Missing job description profile. Analyze a job description first.")

    user_prompt = f"""
CURRENT RESUME PROFILE:
{json.dumps(resume_profile, indent=2, ensure_ascii=False)}

TARGET JOB DESCRIPTION PROFILE:
{json.dumps(jd_profile, indent=2, ensure_ascii=False)}

USER EVIDENCE LIBRARY:
{json.dumps(evidence_items, indent=2, ensure_ascii=False)}

TASK:
Create a concise tailored Skills section for this target job.
"""

    return ask_json(
        SKILLS_SECTION_TAILOR_PROMPT,
        user_prompt,
        temperature=0.0,
        max_tokens=1600,
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

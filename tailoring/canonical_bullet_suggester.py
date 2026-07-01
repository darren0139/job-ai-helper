"""
tailoring/canonical_bullet_suggester.py

Suggest user-approved canonical project bullets for the Evidence Library.

This does not tailor bullets to one JD.
It converts raw project evidence into stable CAR-style master bullets.
"""

from __future__ import annotations

import json
from typing import Any

from llm import ask_json


CANONICAL_BULLET_SUGGESTION_PROMPT = """
Instruction:
You are an honest resume bullet editor for a student or junior technical applicant.

Task:
Convert the user's project evidence into canonical resume bullets.

These bullets will become the user's master Evidence Library bullets.
They should be reusable across multiple job applications.

Rules:
- Use only the provided evidence.
- Do not invent metrics, tools, dates, team sizes, companies, roles, or achievements.
- Follow compact CAR structure: Context, Action, Result/Scope.
- Start each bullet with a strong action verb where possible.
- Use metrics only if explicitly provided.
- If metrics are unavailable, use truthful scope indicators such as team size, project type, released product, system area, or tool used.
- Keep bullets reusable across multiple job applications.
- Do not over-tailor to one specific job description.
- Preserve important technologies and tools that are actually supported.
- Avoid repeated ideas.
- Avoid vague claims such as "showcasing ability" or "demonstrating skills" unless tied to concrete work.
- Usually generate 3-5 bullets.
- Each bullet should usually be 16-26 words.
- Keep wording suitable for a student or junior applicant.

Output:
Return only a valid JSON object matching this schema:
{
  "canonical_bullets": ["string"],
  "notes": ["string"]
}
"""


def suggest_canonical_project_bullets(
    *,
    title: str,
    period: str = "",
    description: str = "",
    skills: list[str] | None = None,
    tools: list[str] | None = None,
    impact: str = "",
) -> dict[str, Any]:
    """
    Suggest stable CAR-style canonical bullets from an Evidence Library project item.
    """
    skills = skills or []
    tools = tools or []

    if not title.strip():
        raise ValueError("Missing project title.")

    if not description.strip() and not impact.strip():
        raise ValueError("Add project evidence or impact before generating canonical bullets.")

    user_prompt = f"""
PROJECT TITLE:
{title}

PERIOD:
{period}

CURRENT DESCRIPTION / BULLETS:
{description}

SUPPORTED SKILLS:
{json.dumps(skills, indent=2, ensure_ascii=False)}

TOOLS / TECHNOLOGIES:
{json.dumps(tools, indent=2, ensure_ascii=False)}

IMPACT / SCOPE:
{impact}

TASK:
Suggest improved canonical Evidence Library bullets.
"""

    return ask_json(
        CANONICAL_BULLET_SUGGESTION_PROMPT,
        user_prompt,
        temperature=0.0,
        max_tokens=900,
    )


def canonical_bullets_to_description(result: dict[str, Any]) -> str:
    """
    Convert canonical_bullets JSON into Evidence Library description text.
    """
    bullets = result.get("canonical_bullets", [])

    return "\n".join(
        f"- {str(bullet).strip()}"
        for bullet in bullets
        if str(bullet).strip()
    )
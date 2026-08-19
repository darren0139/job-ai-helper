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
- Preserve every materially distinct supported contribution, feature, responsibility, or project outcome that could be useful on a resume.
- Do not target an arbitrary small bullet count and do not compress distinct supported evidence merely to reach a preferred count.
- For a substantial project, 5-12 canonical bullets is common. More than 12 is allowed when the supplied evidence genuinely contains more distinct resume-worthy contributions.
- Never create filler bullets to reach a count.
- Merge points only when they genuinely describe the same underlying contribution or would otherwise be materially repetitive.
- If a supported point is merged or omitted, explain that decision briefly in notes so the user can verify that no meaningful evidence was silently lost.
- Each bullet should usually be 16-30 words, but factual completeness takes priority over forcing every bullet into the same length.
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

Coverage requirement:
Before writing, account for all materially distinct supported contributions in
CURRENT DESCRIPTION / BULLETS, SUPPORTED SKILLS, TOOLS / TECHNOLOGIES, and
IMPACT / SCOPE. Preserve each distinct contribution as its own canonical bullet
unless it is genuinely overlapping with another point. Use notes to identify any
meaningful supplied point that was merged or omitted and why.
"""

    return ask_json(
        CANONICAL_BULLET_SUGGESTION_PROMPT,
        user_prompt,
        temperature=0.0,
        max_tokens=2000,
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
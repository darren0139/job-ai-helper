"""
tailoring/canonical_bullet_suggester.py

Suggest user-approved canonical project bullets for the Evidence Library.

This does not tailor bullets to one JD.
It converts raw project evidence into stable CAR-style master bullets.
"""

from __future__ import annotations

import json
import re
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
- Preserve SOURCE LINKAGE. When one supplied sentence or bullet explicitly connects an implementation to its purpose, behaviour, scope, or result, treat that as one accomplishment unless the evidence independently establishes separate work.
- Preserve SOURCE COVERAGE. Treat each explicit supplied description bullet/sentence as a presumptively distinct contribution until the evidence shows that it substantially duplicates another contribution or is merely a dependent detail/result of that same contribution.
- Perform a source-coverage pass before finalising: every explicit source contribution must end up as PRESERVED in a canonical bullet, MERGED into a clearly overlapping contribution, or OMITTED only because it is not materially resume-worthy or is unsupported. Never silently lose a source contribution.
- A merge requires substantial semantic overlap in the underlying work, not merely the same project, technology, subsystem, team, or broad topic.
- Skills, tools, header metadata, and project-level impact/scope may enrich a canonical bullet, but they do not by themselves justify absorbing a separate source contribution into another bullet.
- Do not move general project-level scope (for example team size, repository tooling, or overall project context) into a specific accomplishment unless the supplied evidence directly links that scope to that accomplishment or doing so is necessary to make the bullet understandable.
- Do not split one source accomplishment into multiple canonical bullets merely because it contains multiple clauses, technologies, implementation details, or result phrases.
- In particular, when the same technology/subsystem and the same source sentence connect an integration to the behaviour it supports, keep the integration and supported behaviour together. Example pattern: "Integrated X ..., supporting Y ..." is normally one canonical contribution, not two.
- Split a source point only when the supplied evidence independently supports separate work items that could each stand alone without borrowing context or impact from the other. If you split one supplied point into multiple bullets, explain why in notes.
- Prefer the most concrete supported result/scope wording already present in the evidence. Do not replace a specific supported outcome with a vaguer inferred abstraction such as "extended capabilities", "improved functionality", or "enhanced experience" when the source provides a more precise result.
- Do not promote a result clause, implementation detail, or feature consequence into a separate accomplishment unless the source evidence presents it as independently performed work.
- Do not target an arbitrary small bullet count and do not compress distinct supported evidence merely to reach a preferred count.
- For a substantial project, 5-12 canonical bullets can be common, but the correct count is the number of materially distinct evidence-backed accomplishments. Fewer bullets are correct when the project evidence contains fewer distinct accomplishments.
- Never create filler bullets to reach a count.
- Merge points when they genuinely describe the same underlying contribution, implementation-result chain, or would otherwise be materially repetitive.
- If a supported point is merged, omitted, or split, explain that decision briefly in notes so the user can verify that no meaningful evidence was silently lost or artificially duplicated.
- Each bullet should usually be 16-30 words, but factual completeness takes priority over forcing every bullet into the same length.
- Keep wording suitable for a student or junior applicant.

Output:
Return only a valid JSON object matching this schema:
{
  "canonical_bullets": ["string"],
  "source_coverage": [
    {
      "source_index": 1,
      "decision": "preserved | merged | omitted",
      "canonical_bullet_indexes": [1],
      "merged_with_source_indexes": [],
      "merge_relation": "",
      "reason": "string"
    }
  ],
  "notes": ["string"]
}

Source-coverage contract:
- Include exactly one source_coverage row for every numbered SOURCE CONTRIBUTION.
- source_index is the exact 1-based SOURCE CONTRIBUTION index.
- preserved and merged rows must reference at least one valid canonical bullet.
- omitted rows must reference no canonical bullets.
- merged and omitted rows require a concrete reason.
- A merged row must also provide merged_with_source_indexes and exactly one
  merge_relation from: duplicate, dependent_detail, same_accomplishment_restated.
- A merge is valid only when the source items describe the same underlying
  accomplishment. Shared project, technology, subsystem, team, workflow, or
  broad topic alone is not enough.
- Before merging, test whether the items have the same core action/work and the
  same primary work product/feature, and whether one is actually a duplicate,
  dependent detail/result, or restatement of the other.
- If both source items can stand as independent resume accomplishments, or they
  represent different evidence dimensions such as technical contribution,
  collaboration, ownership, scope, or outcome, preserve them separately.
- When uncertain whether a merge is justified, preserve the sources separately.
- If a preserved source is intentionally split across multiple canonical bullets,
  provide a concrete reason explaining the split.
- If there are no SOURCE CONTRIBUTIONS, return an empty source_coverage list.
"""


SOURCE_COVERAGE_DECISIONS = {"preserved", "merged", "omitted"}
SOURCE_COVERAGE_MERGE_RELATIONS = {
    "duplicate",
    "dependent_detail",
    "same_accomplishment_restated",
}
CANONICAL_SOURCE_COVERAGE_POLICY_VERSION = (
    "canonical-source-coverage-v2-strict-merge"
)


def extract_canonical_source_contributions(description: str) -> list[str]:
    """Extract source units without assuming any project or bullet count."""
    raw = str(description or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")
    bullet_pattern = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(?P<text>.+?)\s*$")
    has_bullets = any(
        bullet_pattern.match(line)
        for line in lines
        if line.strip()
    )

    if not has_bullets:
        # Evidence Library display semantics treat each non-empty description
        # line as one source contribution. Mirror that exact boundary here
        # instead of collapsing adjacent lines into one paragraph.
        return [
            " ".join(line.split()).strip()
            for line in lines
            if " ".join(line.split()).strip()
        ]

    contributions: list[str] = []
    current = ""
    for line in lines:
        cleaned = " ".join(line.split()).strip()
        if not cleaned:
            continue
        match = bullet_pattern.match(line)
        if match:
            if current:
                contributions.append(current)
            current = " ".join(match.group("text").split()).strip()
        elif current:
            current = f"{current} {cleaned}".strip()
        else:
            contributions.append(cleaned)
    if current:
        contributions.append(current)
    return contributions


def _normalise_source_coverage_result(
    result: dict[str, Any],
    *,
    source_contributions: list[str],
) -> dict[str, Any]:
    """Validate structured coverage and fail closed on silent source loss."""
    if not isinstance(result, dict):
        raise ValueError("Canonical bullet suggestion must be a JSON object.")

    bullets = [
        str(item).strip()
        for item in result.get("canonical_bullets", []) or []
        if str(item).strip()
    ]
    if not bullets:
        raise ValueError("Canonical bullet suggestion returned no usable bullets.")

    coverage = result.get("source_coverage")
    if not isinstance(coverage, list):
        raise ValueError(
            "Canonical bullet suggestion is incomplete: source_coverage is missing."
        )

    expected = set(range(1, len(source_contributions) + 1))
    seen: set[int] = set()
    normalised: list[dict[str, Any]] = []

    for row in coverage:
        if not isinstance(row, dict):
            raise ValueError(
                "Canonical bullet suggestion is incomplete: every source_coverage "
                "entry must be an object."
            )
        try:
            source_index = int(row.get("source_index"))
        except (TypeError, ValueError):
            raise ValueError(
                "Canonical bullet suggestion is incomplete: source_index must be "
                "a valid 1-based integer."
            ) from None

        if source_index not in expected:
            raise ValueError(
                f"Canonical bullet suggestion is incomplete: source_index "
                f"{source_index} is not a supplied source contribution."
            )
        if source_index in seen:
            raise ValueError(
                f"Canonical bullet suggestion is incomplete: duplicate "
                f"source_index {source_index}."
            )
        seen.add(source_index)

        decision = str(row.get("decision") or "").strip().lower()
        if decision not in SOURCE_COVERAGE_DECISIONS:
            raise ValueError(
                f"Canonical bullet suggestion is incomplete: source {source_index} "
                "must be preserved, merged, or omitted."
            )

        raw_indexes = row.get("canonical_bullet_indexes")
        if not isinstance(raw_indexes, list):
            raise ValueError(
                f"Canonical bullet suggestion is incomplete: source {source_index} "
                "canonical_bullet_indexes must be a list."
            )

        bullet_indexes: list[int] = []
        for value in raw_indexes:
            try:
                bullet_index = int(value)
            except (TypeError, ValueError):
                raise ValueError(
                    f"Canonical bullet suggestion is incomplete: source "
                    f"{source_index} has a non-integer bullet reference."
                ) from None
            if bullet_index < 1 or bullet_index > len(bullets):
                raise ValueError(
                    f"Canonical bullet suggestion is incomplete: source "
                    f"{source_index} references missing canonical bullet "
                    f"{bullet_index}."
                )
            if bullet_index not in bullet_indexes:
                bullet_indexes.append(bullet_index)

        reason = " ".join(str(row.get("reason") or "").split()).strip()
        if decision in {"preserved", "merged"} and not bullet_indexes:
            raise ValueError(
                f"Canonical bullet suggestion is incomplete: {decision} source "
                f"{source_index} must reference a canonical bullet."
            )
        if decision == "omitted" and bullet_indexes:
            raise ValueError(
                f"Canonical bullet suggestion is incomplete: omitted source "
                f"{source_index} cannot reference a canonical bullet."
            )
        if decision in {"merged", "omitted"} and not reason:
            raise ValueError(
                f"Canonical bullet suggestion is incomplete: {decision} source "
                f"{source_index} requires a concrete reason."
            )
        if decision == "preserved" and len(bullet_indexes) > 1 and not reason:
            raise ValueError(
                f"Canonical bullet suggestion is incomplete: preserved source "
                f"{source_index} split across multiple canonical bullets requires "
                "a concrete reason."
            )

        raw_merged_with = row.get("merged_with_source_indexes", [])
        if not isinstance(raw_merged_with, list):
            raise ValueError(
                f"Canonical bullet suggestion is incomplete: source {source_index} "
                "merged_with_source_indexes must be a list."
            )

        merged_with_source_indexes: list[int] = []
        for value in raw_merged_with:
            try:
                merged_source_index = int(value)
            except (TypeError, ValueError):
                raise ValueError(
                    f"Canonical bullet suggestion is incomplete: source "
                    f"{source_index} has a non-integer merged source reference."
                ) from None
            if merged_source_index not in expected:
                raise ValueError(
                    f"Canonical bullet suggestion is incomplete: source "
                    f"{source_index} references missing merged source "
                    f"{merged_source_index}."
                )
            if merged_source_index == source_index:
                raise ValueError(
                    f"Canonical bullet suggestion is incomplete: source "
                    f"{source_index} cannot merge with itself."
                )
            if merged_source_index not in merged_with_source_indexes:
                merged_with_source_indexes.append(merged_source_index)

        merge_relation = " ".join(
            str(row.get("merge_relation") or "").split()
        ).strip().lower()

        if decision == "merged":
            if not merged_with_source_indexes:
                raise ValueError(
                    f"Canonical bullet suggestion is incomplete: merged source "
                    f"{source_index} must identify merged_with_source_indexes."
                )
            if merge_relation not in SOURCE_COVERAGE_MERGE_RELATIONS:
                allowed = ", ".join(sorted(SOURCE_COVERAGE_MERGE_RELATIONS))
                raise ValueError(
                    f"Canonical bullet suggestion is incomplete: merged source "
                    f"{source_index} must use merge_relation from: {allowed}."
                )
        else:
            if merged_with_source_indexes:
                raise ValueError(
                    f"Canonical bullet suggestion is incomplete: {decision} source "
                    f"{source_index} cannot declare merged source references."
                )
            if merge_relation:
                raise ValueError(
                    f"Canonical bullet suggestion is incomplete: {decision} source "
                    f"{source_index} cannot declare merge_relation."
                )

        normalised.append(
            {
                "source_index": source_index,
                "decision": decision,
                "canonical_bullet_indexes": bullet_indexes,
                "merged_with_source_indexes": merged_with_source_indexes,
                "merge_relation": merge_relation,
                "reason": reason,
                "source_text": source_contributions[source_index - 1],
            }
        )

    missing = sorted(expected - seen)
    if missing:
        raise ValueError(
            "Canonical bullet suggestion is incomplete: source contribution(s) "
            + ", ".join(str(index) for index in missing)
            + " were not accounted for."
        )

    coverage_by_source = {
        row["source_index"]: row
        for row in normalised
    }
    for row in normalised:
        if row["decision"] != "merged":
            continue

        target_rows = [
            coverage_by_source[index]
            for index in row["merged_with_source_indexes"]
        ]
        if not any(target["decision"] == "preserved" for target in target_rows):
            raise ValueError(
                f"Canonical bullet suggestion is incomplete: merged source "
                f"{row['source_index']} must merge into at least one preserved "
                "source contribution."
            )

        shared_bullets = set(row["canonical_bullet_indexes"])
        target_bullets: set[int] = set()
        for target in target_rows:
            target_bullets.update(target["canonical_bullet_indexes"])
        if not shared_bullets.intersection(target_bullets):
            raise ValueError(
                f"Canonical bullet suggestion is incomplete: merged source "
                f"{row['source_index']} must share a canonical bullet with the "
                "source contribution it merges into."
            )

    model_notes = [
        " ".join(str(note).split()).strip()
        for note in result.get("notes", []) or []
        if " ".join(str(note).split()).strip()
    ]

    coverage_notes: list[str] = []
    for row in normalised:
        source_index = row["source_index"]
        decision = row["decision"]
        bullet_refs = ", ".join(
            str(index)
            for index in row["canonical_bullet_indexes"]
        )

        if decision == "preserved":
            if len(row["canonical_bullet_indexes"]) == 1:
                coverage_notes.append(
                    f"Source {source_index} → Preserved as bullet {bullet_refs}."
                )
            else:
                coverage_notes.append(
                    f"Source {source_index} → Preserved across bullets "
                    f"{bullet_refs}: {row['reason']}"
                )
        elif decision == "merged":
            merged_refs = ", ".join(
                str(index)
                for index in row["merged_with_source_indexes"]
            )
            coverage_notes.append(
                f"Source {source_index} → Merged with source(s) {merged_refs} "
                f"into bullet(s) {bullet_refs} "
                f"[{row['merge_relation']}]: {row['reason']}"
            )
        else:
            coverage_notes.append(
                f"Source {source_index} → Omitted: {row['reason']}"
            )

    return {
        **result,
        "canonical_bullets": bullets,
        "source_coverage": normalised,
        "notes": coverage_notes,
        "model_notes": model_notes,
        "source_coverage_policy_version": (
            CANONICAL_SOURCE_COVERAGE_POLICY_VERSION
        ),
    }


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

    source_contributions = extract_canonical_source_contributions(
        description
    )
    source_contribution_block = (
        "\n".join(
            f"{index}. {text}"
            for index, text in enumerate(source_contributions, start=1)
        )
        if source_contributions
        else "(none)"
    )

    user_prompt = f"""
PROJECT TITLE:
{title}

PERIOD:
{period}

CURRENT DESCRIPTION / BULLETS:
{description}

SOURCE CONTRIBUTIONS (authoritative 1-based indices):
{source_contribution_block}

SUPPORTED SKILLS:
{json.dumps(skills, indent=2, ensure_ascii=False)}

TOOLS / TECHNOLOGIES:
{json.dumps(tools, indent=2, ensure_ascii=False)}

IMPACT / SCOPE:
{impact}

TASK:
Suggest improved canonical Evidence Library bullets.

Coverage requirement:
Before writing, first identify the explicit source contributions in CURRENT
DESCRIPTION / BULLETS. Treat each source contribution as presumptively distinct,
then group only genuinely overlapping items into underlying contribution
clusters. A contribution cluster is one implementation/accomplishment together
with the purpose, behaviour, scope, or result that the source directly links to
it.

Run a source-coverage ledger before finalising the JSON:
- PRESERVED: represented by its own canonical bullet;
- MERGED: combined with another source contribution only because the underlying
  work substantially overlaps or one item is a dependent detail/result of the
  other;
- OMITTED: allowed only when the point is unsupported, materially non-resume-
  worthy, or fully redundant.

Every MERGED or OMITTED source contribution must be explained briefly in notes.
Do not output the internal ledger itself. Then write one canonical bullet per
materially distinct contribution cluster.

Account for all materially distinct supported contributions in CURRENT
DESCRIPTION / BULLETS, SUPPORTED SKILLS, TOOLS / TECHNOLOGIES, and IMPACT /
SCOPE. Preserve distinct contributions, but do not manufacture extra
contributions by splitting one implementation-result chain into multiple
bullets. When the source says that an implementation "supports", "enables",
"improves", "connects", "centralises", or otherwise causes/describes a result,
keep that relationship intact unless independent evidence proves separate work.

Prefer concrete source wording for results and scope over generic inferred
phrases. Use notes to identify every meaningful supplied source contribution
that was merged, omitted, or split and why. If an explicit source contribution
does not appear as its own canonical bullet and there is no corresponding note
explaining its merge/omission, the suggestion is incomplete.
"""

    result = ask_json(
        CANONICAL_BULLET_SUGGESTION_PROMPT,
        user_prompt,
        temperature=0.0,
        max_tokens=2000,
    )
    return _normalise_source_coverage_result(
        result,
        source_contributions=source_contributions,
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
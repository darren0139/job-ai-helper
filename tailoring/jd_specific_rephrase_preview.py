"""Optional JD-specific, evidence-preserving project-bullet rephrase preview.

Patch 2 policy:
- Canonical Evidence Library bullets remain immutable.
- A suggestion is preview-only until the user accepts it.
- Only bullet wording may change. Project title/header metadata is invariant.
- The frozen generation candidate/evidence payload is used; live Evidence Library
  rows are never consulted by this module.
- Fresh scoring is deterministic and diagnostic only. Historical Phase 8 answers
  are never used as inputs.
- Accepting a suggestion does not fit a DOCX and does not make another model call.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from typing import Any

from llm import ask_json
from tailoring.fresh_target_evidence_scoring import (
    FRESH_TARGET_EVIDENCE_POLICY_VERSION,
    FRESH_EVIDENCE_REDISCOVERY_VERSION,
    build_fresh_target_analysis,
)
from tailoring.phase8_claim_lineage import audit_claim_lineage_v2
from tailoring.phase8_verification import (
    build_final_resume_profile,
    build_resume_text_from_profile,
    compare_stable_analyses,
)


JD_REPHRASE_PREVIEW_VERSION = "phase9f-jd-rephrase-preview-v1"

JD_REPHRASE_PROMPT = """
Instruction:
You are a conservative resume bullet rephrase assistant.

Task:
Propose ONE alternative wording for the supplied CURRENT BULLET so it reads
naturally for the supplied target job description while preserving exactly the
same factual claim.

Evidence rules:
- Use only the supplied CANONICAL BULLET and FROZEN PROJECT EVIDENCE.
- The target JD is wording/context guidance, never evidence about the candidate.
- Do not add tools, metrics, users, responsibilities, outcomes, team scope,
  publication status, dates, domain experience, testing activity, ownership,
  or any other fact that is not supported by the frozen project evidence.
- Do not turn transferable evidence into direct professional experience.
- Do not invent QA, live operations, configuration, stakeholder, production,
  or gaming-industry work merely because the JD mentions it.
- Preserve all numbers exactly unless removing a redundant number does not
  change meaning. Never introduce a new number.
- Do not change the project title, subtitle, technology header, context groups,
  dates, project selection, or Skills section.
- Prefer the canonical wording when no useful evidence-preserving JD-specific
  rephrase exists.
- Return one sentence/bullet only.

Output only valid JSON:
{
  "suggested_bullet": "string",
  "reason": "short string",
  "jd_terms_used": ["string"],
  "evidence_preserved": true
}
"""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _normalise(value: Any) -> str:
    text = _clean(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return " ".join(text.split())


def _numbers(value: Any) -> set[str]:
    return set(re.findall(r"\b\d+(?:\.\d+)?\b", _clean(value)))


def _tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]+", _normalise(value))
        if len(token) >= 2
    }


def _collect_strings(value: Any) -> list[str]:
    output: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            output.extend(_collect_strings(child))
    elif isinstance(value, list):
        for child in value:
            output.extend(_collect_strings(child))
    elif isinstance(value, (str, int, float)):
        text = _clean(value)
        if text:
            output.append(text)
    return output


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = _clean(value)
        key = _normalise(text)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


def _project_key(project: dict[str, Any]) -> str:
    return _normalise(
        project.get("project_id")
        or project.get("title")
        or project.get("display_title")
    )


def _matching_frozen_records(
    generation: dict[str, Any],
    project: dict[str, Any],
) -> list[dict[str, Any]]:
    target_id = _clean(project.get("project_id"))
    target_title = _normalise(
        project.get("title") or project.get("display_title")
    )
    matches: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            record_id = _clean(value.get("project_id") or value.get("id"))
            title = _normalise(
                value.get("title")
                or value.get("display_title")
                or value.get("project_title")
            )
            if (
                (target_id and record_id and record_id == target_id)
                or (target_title and title and title == target_title)
            ):
                matches.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    # These are persisted from the exact frozen normal-generation inputs.
    walk(generation.get("candidate_pool"))
    walk(generation.get("project_inputs"))
    return matches


def build_rephrase_preview_context(
    *,
    generation: dict[str, Any],
    project_index: int,
    bullet_index: int,
    baseline_report: dict[str, Any],
) -> dict[str, Any]:
    projects = (
        (generation.get("projects") or {}).get("recommended_projects") or []
    )
    if not isinstance(projects, list) or not (
        0 <= int(project_index) < len(projects)
    ):
        raise ValueError("Selected project is unavailable.")

    project = projects[int(project_index)]
    if not isinstance(project, dict):
        raise ValueError("Selected project is invalid.")

    current_bullets = [
        _clean(value)
        for value in project.get("draft_bullets", []) or []
        if _clean(value)
    ]
    if not (0 <= int(bullet_index) < len(current_bullets)):
        raise ValueError("Selected project bullet is unavailable.")

    canonical_bullets = [
        _clean(value)
        for value in (
            project.get("selected_blueprint_bullets")
            or project.get("allocated_blueprint_bullets")
            or []
        )
        if _clean(value)
    ]
    canonical = (
        canonical_bullets[int(bullet_index)]
        if int(bullet_index) < len(canonical_bullets)
        else current_bullets[int(bullet_index)]
    )

    frozen_records = _matching_frozen_records(generation, project)
    evidence = _dedupe(
        [
            canonical,
            *current_bullets,
            _clean(project.get("title")),
            _clean(project.get("display_title")),
            _clean(project.get("subtitle")),
            _clean(project.get("period")),
            *_collect_strings(project.get("canonical_tools") or []),
            *_collect_strings(project.get("resume_header_tools") or []),
            *_collect_strings(project.get("resume_header_context") or []),
            *_collect_strings(project.get("requirement_matches") or []),
            *[
                text
                for record in frozen_records
                for text in _collect_strings(record)
            ],
        ]
    )

    return {
        "preview_version": JD_REPHRASE_PREVIEW_VERSION,
        "generation_id": _clean(generation.get("generation_id")),
        "project_index": int(project_index),
        "bullet_index": int(bullet_index),
        "project_id": _clean(project.get("project_id")),
        "project_title": _clean(
            project.get("display_title") or project.get("title")
        ),
        "canonical_bullet": canonical,
        "current_bullet": current_bullets[int(bullet_index)],
        "frozen_project_evidence": evidence,
        "jd_profile": deepcopy(baseline_report.get("jd_profile") or {}),
        "raw_jd_text": str(baseline_report.get("raw_jd_text") or ""),
        "historical_phase8_used": False,
        "live_evidence_library_used": False,
    }


_REPHRASE_NOVELTY_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "via",
    "with",
    "without",
}

# Narrow wording/action roots that may legitimately appear as paraphrases even
# when the exact surface form was not already present in the frozen evidence.
# Capability nouns and outcomes are intentionally NOT whitelisted here.
_REPHRASE_SAFE_PARAPHRASE_ROOTS = {
    "apply",
    "build",
    "configur",
    "connect",
    "creat",
    "develop",
    "implement",
    "integrate",
    "link",
    "provid",
    "refram",
    "set",
    "setup",
    "support",
    "use",
}


def _rephrase_token_root(token: str) -> str:
    value = str(token or "").strip().lower()
    if len(value) > 5 and value.endswith("ies"):
        return value[:-3] + "y"
    if len(value) > 5 and value.endswith("ing"):
        return value[:-3]
    if len(value) > 4 and value.endswith("ed"):
        return value[:-2]
    if len(value) > 3 and value.endswith("s"):
        return value[:-1]
    return value


def _rephrase_material_roots(tokens: set[str]) -> set[str]:
    roots: set[str] = set()
    for token in tokens:
        cleaned = str(token or "").strip().lower()
        if len(cleaned) < 3:
            continue
        if cleaned in _REPHRASE_NOVELTY_STOPWORDS:
            continue
        root = _rephrase_token_root(cleaned)
        if root and root not in _REPHRASE_SAFE_PARAPHRASE_ROOTS:
            roots.add(root)
    return roots


def validate_rephrase_suggestion(
    *,
    context: dict[str, Any],
    suggested_bullet: Any,
) -> dict[str, Any]:
    suggested = _clean(suggested_bullet)
    canonical = _clean(context.get("canonical_bullet"))
    current = _clean(context.get("current_bullet"))
    evidence = _clean(" ".join(context.get("frozen_project_evidence") or []))

    reasons: list[str] = []
    placeholder_values = {
        "string",
        "short string",
        "<string>",
        "placeholder",
        "example",
        "suggested bullet",
        "rewritten bullet",
        "resume bullet",
    }
    if _normalise(suggested) in {
        _normalise(value)
        for value in placeholder_values
    }:
        reasons.append("placeholder_output")
    if not suggested:
        reasons.append("empty_suggestion")
    if "\n" in str(suggested_bullet or ""):
        reasons.append("multiple_lines")
    if len(suggested.split()) < 6:
        reasons.append("too_short")
    if len(suggested.split()) > 45:
        reasons.append("too_long")

    allowed_numbers = _numbers(evidence)
    introduced_numbers = sorted(_numbers(suggested) - allowed_numbers)
    if introduced_numbers:
        reasons.append("introduced_number")

    evidence_tokens = _tokens(evidence)
    suggestion_tokens = _tokens(suggested)
    coverage = (
        len(evidence_tokens & suggestion_tokens) / len(suggestion_tokens)
        if suggestion_tokens
        else 0.0
    )
    # This is only a preview guard. The stronger final acceptance gate is the
    # existing deterministic Phase 8 claim-lineage audit.
    if suggestion_tokens and coverage < 0.35:
        reasons.append("low_evidence_token_overlap")

    # Token-overlap alone can miss a dangerous pattern where most of the
    # sentence is supported but one new capability phrase is invented.
    # Compare material content roots against the FULL frozen evidence plus the
    # canonical/current bullets. This is a deterministic preview guard only;
    # the stronger claim-lineage gate still runs before acceptance.
    source_tokens = (
        evidence_tokens
        | _tokens(canonical)
        | _tokens(current)
    )
    source_roots = {
        _rephrase_token_root(token)
        for token in source_tokens
        if _rephrase_token_root(token)
    }
    suggestion_material_roots = _rephrase_material_roots(
        suggestion_tokens
    )
    novel_material_roots = sorted(
        root
        for root in suggestion_material_roots
        if root not in source_roots
    )

    jd_tokens = _tokens(
        str(context.get("raw_jd_text") or "")
    )
    jd_roots = {
        _rephrase_token_root(token)
        for token in jd_tokens
        if _rephrase_token_root(token)
    }
    unsupported_jd_roots = sorted(
        root
        for root in novel_material_roots
        if root in jd_roots
    )

    if unsupported_jd_roots:
        reasons.append("unsupported_jd_term")
    elif len(novel_material_roots) >= 2:
        reasons.append("unsupported_material_terms")

    return {
        "suggested_bullet": suggested,
        "safe_for_lineage_evaluation": not reasons,
        "guard_reasons": reasons,
        "introduced_numbers": introduced_numbers,
        "unsupported_material_tokens": novel_material_roots,
        "unsupported_jd_tokens": unsupported_jd_roots,
        "evidence_token_coverage": round(coverage, 3),
        "same_as_canonical": _normalise(suggested) == _normalise(canonical),
        "same_as_current": _normalise(suggested) == _normalise(current),
    }


def suggest_jd_specific_rephrase(
    *,
    context: dict[str, Any],
    model: str | None = None,
    previous_suggestion: str = "",
    attempt_number: int = 1,
) -> dict[str, Any]:
    user_prompt = f"""
TARGET JD PROFILE:
{json.dumps(context.get("jd_profile") or {}, ensure_ascii=False, indent=2)}

TARGET JD TEXT:
{context.get("raw_jd_text") or ""}

PROJECT:
{context.get("project_title") or ""}

CANONICAL BULLET:
{context.get("canonical_bullet") or ""}

CURRENT BULLET:
{context.get("current_bullet") or ""}

FROZEN PROJECT EVIDENCE:
{json.dumps(context.get("frozen_project_evidence") or [], ensure_ascii=False, indent=2)}

PREVIOUS SUGGESTION TO AVOID REPEATING:
{previous_suggestion or "(none)"}

ATTEMPT:
{int(attempt_number)}

Return one evidence-preserving alternative. If no useful rewrite is available,
return the canonical bullet unchanged.
"""
    result = ask_json(
        JD_REPHRASE_PROMPT,
        user_prompt,
        temperature=0.2,
        max_tokens=500,
        model=model,
    )
    validation = validate_rephrase_suggestion(
        context=context,
        suggested_bullet=result.get("suggested_bullet"),
    )
    return {
        "preview_version": JD_REPHRASE_PREVIEW_VERSION,
        **validation,
        "reason": _clean(result.get("reason")),
        "jd_terms_used": [
            _clean(value)
            for value in result.get("jd_terms_used", []) or []
            if _clean(value)
        ],
        "model_evidence_preserved": bool(
            result.get("evidence_preserved", False)
        ),
        "attempt_number": int(attempt_number),
    }


_HEADER_FIELDS = (
    "title",
    "display_title",
    "subtitle",
    "period",
    "resume_header_tools",
    "resume_header_context",
    "canonical_tools",
)


def build_rephrased_generation_candidate(
    *,
    generation: dict[str, Any],
    project_index: int,
    bullet_index: int,
    accepted_bullet: str,
) -> dict[str, Any]:
    candidate = deepcopy(generation)
    # Evaluate semantic content, never a historical fitted representation.
    candidate["fit_result"] = None
    candidate["docx_path"] = ""
    candidate["pdf_path"] = ""

    projects_state = candidate.get("projects")
    if not isinstance(projects_state, dict):
        raise ValueError("The selected generation has no Projects payload.")
    projects = projects_state.get("recommended_projects")
    if not isinstance(projects, list) or not (
        0 <= int(project_index) < len(projects)
    ):
        raise ValueError("Selected project is unavailable.")

    project = projects[int(project_index)]
    if not isinstance(project, dict):
        raise ValueError("Selected project is invalid.")

    before_header = {
        field: deepcopy(project.get(field))
        for field in _HEADER_FIELDS
    }

    bullets = [
        _clean(value)
        for value in project.get("draft_bullets", []) or []
        if _clean(value)
    ]
    if not (0 <= int(bullet_index) < len(bullets)):
        raise ValueError("Selected project bullet is unavailable.")

    accepted = _clean(accepted_bullet)
    if not accepted:
        raise ValueError("Accepted bullet wording is empty.")

    bullets[int(bullet_index)] = accepted
    project["draft_bullets"] = bullets

    # Existing compact bullets correspond to the old full wording. Do not let
    # deterministic fitting silently substitute stale compact text.
    project["compact_bullets"] = []
    project["jd_rephrase_compact_invalidated"] = True

    overrides = deepcopy(project.get("jd_rephrase_overrides") or {})
    if not isinstance(overrides, dict):
        overrides = {}
    overrides[str(int(bullet_index))] = accepted
    project["jd_rephrase_overrides"] = overrides

    after_header = {
        field: deepcopy(project.get(field))
        for field in _HEADER_FIELDS
    }
    if before_header != after_header:
        raise ValueError(
            "JD-specific rephrasing may not modify project header metadata."
        )

    return candidate


def _semantic_generation_view(
    generation: dict[str, Any],
) -> dict[str, Any]:
    output = deepcopy(generation)
    output["fit_result"] = None
    output["docx_path"] = ""
    output["pdf_path"] = ""
    return output


def build_rephrase_fresh_score_comparison(
    *,
    baseline_report: dict[str, Any],
    current_generation: dict[str, Any],
    proposed_generation: dict[str, Any],
) -> dict[str, Any]:
    baseline_profile = deepcopy(
        baseline_report.get("resume_profile") or {}
    )

    current_semantic = _semantic_generation_view(current_generation)
    proposed_semantic = _semantic_generation_view(proposed_generation)

    current_profile = build_final_resume_profile(
        baseline_profile,
        current_semantic,
    )
    proposed_profile = build_final_resume_profile(
        baseline_profile,
        proposed_semantic,
    )

    def score(profile: dict[str, Any]) -> dict[str, Any]:
        return build_fresh_target_analysis(
            jd_profile=deepcopy(baseline_report.get("jd_profile") or {}),
            keyword_match=deepcopy(
                baseline_report.get("keyword_match") or {}
            ),
            raw_jd_text=str(
                baseline_report.get("raw_jd_text") or ""
            ),
            raw_resume_text=build_resume_text_from_profile(profile),
            resume_profile=profile,
            bullet_quality_score=(
                (baseline_report.get("bullets") or {}).get(
                    "bullet_quality_avg", 0
                )
            ),
            structure_score=(
                (baseline_report.get("structure") or {}).get(
                    "structure_score", 0
                )
            ),
            retrieval_mode_override="lexical",
        )

    try:
        before = score(current_profile)
        after = score(proposed_profile)
        comparison = compare_stable_analyses(before, after)
        return {
            "available": True,
            "before_score": comparison.get("before_score", 0),
            "after_score": comparison.get("after_score", 0),
            "score_delta": comparison.get("score_delta", 0),
            "required_core_coverage_delta": comparison.get(
                "required_core_coverage_delta", 0
            ),
            "preferred_coverage_delta": comparison.get(
                "preferred_coverage_delta", 0
            ),
            "evidence_strength_delta": comparison.get(
                "evidence_strength_delta", 0
            ),
            "important_regressions": deepcopy(
                comparison.get("important_regressions") or []
            ),
            "fresh_target_evidence_policy_version": (
                FRESH_TARGET_EVIDENCE_POLICY_VERSION
            ),
            "fresh_evidence_rediscovery_version": (
                FRESH_EVIDENCE_REDISCOVERY_VERSION
            ),
            "historical_phase8_used": False,
            "model_call_count": 0,
        }
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
            "fresh_target_evidence_policy_version": (
                FRESH_TARGET_EVIDENCE_POLICY_VERSION
            ),
            "fresh_evidence_rediscovery_version": (
                FRESH_EVIDENCE_REDISCOVERY_VERSION
            ),
            "historical_phase8_used": False,
            "model_call_count": 0,
        }


def evaluate_rephrase_candidate(
    *,
    baseline_report: dict[str, Any],
    current_generation: dict[str, Any],
    project_index: int,
    bullet_index: int,
    accepted_bullet: str,
) -> dict[str, Any]:
    proposed = build_rephrased_generation_candidate(
        generation=current_generation,
        project_index=project_index,
        bullet_index=bullet_index,
        accepted_bullet=accepted_bullet,
    )

    lineage = audit_claim_lineage_v2(
        baseline_report.get("resume_profile") or {},
        proposed,
    )
    target_project = (
        ((proposed.get("projects") or {}).get("recommended_projects") or [])
        [int(project_index)]
    )
    target_title = _clean(
        target_project.get("display_title")
        or target_project.get("title")
    )
    target_risks = [
        risk
        for risk in lineage.get("project_bullet_review_risks", []) or []
        if isinstance(risk, dict)
        and int(risk.get("bullet_index", -1)) == int(bullet_index)
        and _normalise(risk.get("project")) == _normalise(target_title)
    ]

    fresh_comparison = build_rephrase_fresh_score_comparison(
        baseline_report=baseline_report,
        current_generation=current_generation,
        proposed_generation=proposed,
    )

    return {
        "preview_version": JD_REPHRASE_PREVIEW_VERSION,
        "safe_to_accept": not target_risks,
        "target_claim_lineage_risks": target_risks,
        "claim_lineage": lineage,
        "fresh_score_comparison": fresh_comparison,
        "proposed_generation": proposed,
        "historical_phase8_used": False,
    }

# ---------------------------------------------------------------------------
# Patch 2.2 batch review helpers
# ---------------------------------------------------------------------------

JD_REPHRASE_BATCH_PREVIEW_VERSION = "jd-rephrase-batch-review-v2.2"

JD_REPHRASE_BATCH_PROMPT = """
Instruction:
You are a conservative resume bullet rephrase assistant reviewing multiple
project bullets together.

Task:
Return one proposed wording row for EVERY supplied bullet. Improve relevance and
clarity for the target JD while preserving exactly the same factual claim.

Evidence rules:
- Use only each bullet's canonical/current wording and its supplied frozen/stored
  project evidence.
- The target JD is wording/context guidance, never candidate evidence.
- Do not invent tools, metrics, users, responsibilities, outcomes, team scope,
  publication status, dates, domain experience, testing activity, ownership,
  clients, deployment, QA, live operations, robotics, or any other unsupported fact.
- Never turn transferable evidence into direct professional experience.
- Preserve numbers. Never introduce a number not present in that project's evidence.
- Do not change project titles, subtitles, technology headers, dates, project
  selection, or Skills.
- Consider the set of bullets together so the rewritten section is coherent and
  does not repeat the same JD phrase unnecessarily.
- If a bullet has no useful safe rewrite, return its CURRENT wording unchanged.
- Prefer the CURRENT wording unchanged over a merely cosmetic rewrite.
- Never borrow a JD capability, feature, or outcome as if the project proved it.
  Terms such as performance, responsiveness, cross-browser, real-time,
  scalability, availability, monitoring, or optimization may be used only when
  the supplied project evidence explicitly supports that same capability.
- The reason must describe the actual wording change only. Do not claim
  alignment to a JD concept that is absent from the proposed bullet or
  unsupported by the supplied project evidence.
- Keep project_index and bullet_index exactly as supplied.

Safe useful rephrasing guidance:
- You MAY replace a weak/general verb with an equivalent stronger verb when the
  factual meaning stays the same, for example "set up" -> "configured" or
  "connected" -> "integrated".
- You MAY reorder already-supported facts so the most JD-relevant proven fact
  appears earlier.
- You MAY emphasize an already-proven technology or capability when it is
  relevant to the JD.
- You MAY remove redundancy or tighten wording without changing the claim.
- Do NOT rewrite merely to make the bullet different. If the only available
  change is cosmetic or awkward, keep CURRENT wording unchanged.

ALLOWED EXAMPLE:
Before: Set up the React and Supabase project environment and connected the
frontend to the PostgreSQL-backed service.
After: Configured the React and Supabase project environment and integrated the
frontend with the PostgreSQL-backed service.
Why allowed: same facts, clearer verbs, no new capability.

NOT ALLOWED EXAMPLE:
Before: Implemented backend data access through PostgREST and applied
Row-Level Security policies to secure database operations.
Bad after: Implemented real-time PostgREST queries with responsive performance.
Why not allowed: "real-time", "responsive", and "performance" are new
capabilities unless the supplied project evidence explicitly proves them.

Output ONLY one valid JSON object with this contract:
- Top-level key: "suggestions" containing an array.
- Return one array item for EVERY supplied bullet.
- Each item must contain:
  - "project_index": integer copied exactly from the input.
  - "bullet_index": integer copied exactly from the input.
  - "suggested_bullet": the complete proposed resume bullet.
  - "reason": a brief explanation of the wording choice.
  - "jd_terms_used": an array containing only actual JD terms used.
  - "evidence_preserved": boolean.
- Never output literal placeholder values such as "string", "short string",
  "<string>", "placeholder", "example", or "suggested bullet".
"""


def build_rephrase_batch_contexts(
    *,
    generation: dict[str, Any],
    baseline_report: dict[str, Any],
    project_indices: list[int] | None = None,
) -> list[dict[str, Any]]:
    projects = (
        (generation.get("projects") or {}).get("recommended_projects") or []
    )
    if not isinstance(projects, list):
        return []

    if project_indices is None:
        selected = list(range(len(projects)))
    else:
        selected = []
        for raw_index in project_indices:
            index = int(raw_index)
            if 0 <= index < len(projects) and index not in selected:
                selected.append(index)

    contexts: list[dict[str, Any]] = []
    for project_index in selected:
        project = projects[project_index]
        if not isinstance(project, dict):
            continue
        bullets = [
            _clean(value)
            for value in project.get("draft_bullets", []) or []
            if _clean(value)
        ]
        for bullet_index in range(len(bullets)):
            contexts.append(
                build_rephrase_preview_context(
                    generation=generation,
                    project_index=project_index,
                    bullet_index=bullet_index,
                    baseline_report=baseline_report,
                )
            )
    return contexts


_REPHRASE_PROMPT_EVIDENCE_MAX_ITEMS = 24
_REPHRASE_PROMPT_EVIDENCE_MAX_CHARS = 6000
_LOCAL_REPHRASE_PROMPT_EVIDENCE_MAX_ITEMS = 16
_LOCAL_REPHRASE_PROMPT_EVIDENCE_MAX_CHARS = 4000


def _env_positive_int_or_default(
    name: str,
    default: int,
) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return max(1, int(default))

    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return max(1, int(default))

    return max(1, parsed)


def _rephrase_prompt_evidence_limits(
    model: str | None,
) -> tuple[int, int]:
    if not _is_local_ollama_rephrase_model(model):
        return (
            _REPHRASE_PROMPT_EVIDENCE_MAX_ITEMS,
            _REPHRASE_PROMPT_EVIDENCE_MAX_CHARS,
        )

    return (
        _env_positive_int_or_default(
            "OLLAMA_REPHRASE_PROMPT_EVIDENCE_MAX_ITEMS",
            _LOCAL_REPHRASE_PROMPT_EVIDENCE_MAX_ITEMS,
        ),
        _env_positive_int_or_default(
            "OLLAMA_REPHRASE_PROMPT_EVIDENCE_MAX_CHARS",
            _LOCAL_REPHRASE_PROMPT_EVIDENCE_MAX_CHARS,
        ),
    )


def _compact_prompt_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _select_prompt_evidence(
    *,
    evidence: list[Any],
    bullet_texts: list[str],
    jd_profile: dict[str, Any],
    raw_jd_text: str,
    max_items: int = _REPHRASE_PROMPT_EVIDENCE_MAX_ITEMS,
    max_chars: int = _REPHRASE_PROMPT_EVIDENCE_MAX_CHARS,
) -> list[str]:
    # Model-facing view only. Full frozen evidence remains in each preview
    # context and is still used by deterministic post-model validation.
    cleaned = _dedupe(
        [
            _clean(value)
            for value in evidence
            if _clean(value)
        ]
    )
    if not cleaned:
        return []

    bullet_values = _dedupe(
        [
            _clean(value)
            for value in bullet_texts
            if _clean(value)
        ]
    )
    bullet_tokens = _tokens(" ".join(bullet_values))
    jd_tokens = _tokens(
        " ".join(
            [
                _compact_prompt_json(jd_profile or {}),
                _clean(raw_jd_text),
            ]
        )
    )
    repeated_bullets = {
        _normalise(value)
        for value in bullet_values
        if _normalise(value)
    }

    ranked: list[
        tuple[int, int, int, int, int, int, str]
    ] = []
    for index, text in enumerate(cleaned):
        if _normalise(text) in repeated_bullets:
            continue

        tokens = _tokens(text)
        bullet_overlap = len(tokens & bullet_tokens)
        jd_overlap = len(tokens & jd_tokens)
        ranked.append(
            (
                1 if bullet_overlap else 0,
                bullet_overlap,
                1 if jd_overlap else 0,
                jd_overlap,
                len(text),
                index,
                text,
            )
        )

    ranked.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            -item[2],
            -item[3],
            item[4],
            item[5],
        )
    )

    selected: list[str] = []
    used_chars = 0
    for _bh, _bo, _jh, _jo, _length, _index, text in ranked:
        if len(selected) >= max(1, int(max_items)):
            break

        extra = len(text) + (1 if selected else 0)
        if used_chars + extra > max(1, int(max_chars)):
            continue

        selected.append(text)
        used_chars += extra

    if not selected:
        fitting = [
            text
            for text in cleaned
            if len(text) <= max(1, int(max_chars))
            and _normalise(text) not in repeated_bullets
        ]
        if fitting:
            selected.append(
                min(
                    fitting,
                    key=lambda value: (
                        len(value),
                        cleaned.index(value),
                    ),
                )
            )

    return selected


def _batch_rephrase_max_tokens(bullet_count: int) -> int:
    return max(
        420,
        min(
            2200,
            max(1, int(bullet_count)) * 180,
        ),
    )


_JD_REPHRASE_MEANINGFUL_ONLY_SUFFIX = """
MEANINGFUL-CHANGE POLICY:
- This is JD tailoring, not general copy-editing.
- Do NOT rewrite merely to swap equivalent verbs, prepositions, spelling
  variants, punctuation, or sentence order.
- Do NOT change a bullet only because another phrasing sounds more polished.
- Propose a change only when the wording materially surfaces or emphasizes a
  JD-relevant capability that is already explicitly supported by the frozen
  evidence for that project.
- Prefer leaving a strong/current bullet unchanged over cosmetic variation.
- Never introduce a JD capability that is not supported by the supplied
  evidence.
- If the only possible change is cosmetic, return the current bullet unchanged.
"""


_LOCAL_REPHRASE_CHANGED_ONLY_SUFFIX = """
LOCAL OLLAMA CONCISE OUTPUT OVERRIDE:
- Return ONLY bullets whose wording you actually changed under the
  MEANINGFUL-CHANGE POLICY.
- Omit every unchanged bullet from suggestions.
- For each changed bullet return ONLY project_index, bullet_index, and
  suggested_bullet.
- Do not return reason, jd_terms_used, evidence_preserved, commentary, or
  unchanged rows.
- If no bullet has a useful evidence-backed JD-alignment rewrite, return
  {"suggestions": []}.
- The application reconstructs omitted bullets as unchanged and still performs
  the normal deterministic preview guard and claim-lineage checks.

Output shape:
{
  "suggestions": [
    {
      "project_index": 0,
      "bullet_index": 0,
      "suggested_bullet": "changed wording only"
    }
  ]
}
"""


def _use_changed_only_rephrase_output(
    model: str | None,
) -> bool:
    return _is_local_ollama_rephrase_model(model)


def _batch_rephrase_output_max_tokens(
    model: str | None,
    bullet_count: int,
) -> int:
    if not _use_changed_only_rephrase_output(model):
        return _batch_rephrase_max_tokens(bullet_count)

    per_bullet = _env_positive_int_or_default(
        "OLLAMA_REPHRASE_OUTPUT_TOKENS_PER_BULLET",
        120,
    )
    return max(
        180,
        min(
            900,
            max(1, int(bullet_count)) * per_bullet,
        ),
    )


def _expand_sparse_local_rephrase_result(
    result: dict[str, Any],
    contexts: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = result.get("suggestions")
    if not isinstance(rows, list):
        rows = []

    by_key: dict[tuple[int, int], dict[str, Any]] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        try:
            key = (
                int(row.get("project_index")),
                int(row.get("bullet_index")),
            )
        except (TypeError, ValueError):
            continue

        by_key[key] = dict(row)

    expanded: list[dict[str, Any]] = []

    for context in contexts:
        project_index = int(context.get("project_index", 0))
        bullet_index = int(context.get("bullet_index", 0))
        key = (project_index, bullet_index)
        current_bullet = str(
            context.get("current_bullet")
            or context.get("canonical_bullet")
            or ""
        ).strip()

        row = by_key.get(key)

        if row is None:
            expanded.append(
                {
                    "project_index": project_index,
                    "bullet_index": bullet_index,
                    "suggested_bullet": current_bullet,
                    "reason": (
                        "No substantive evidence-backed JD-alignment "
                        "rewrite was proposed."
                    ),
                    "jd_terms_used": [],
                    "evidence_preserved": True,
                }
            )
            continue

        normalized = dict(row)
        normalized["project_index"] = project_index
        normalized["bullet_index"] = bullet_index
        normalized.setdefault(
            "suggested_bullet",
            current_bullet,
        )
        normalized.setdefault(
            "reason",
            (
                "Substantive JD-alignment rewrite proposed; the normal "
                "deterministic evidence and claim-lineage checks still apply."
            ),
        )
        normalized.setdefault("jd_terms_used", [])
        normalized.setdefault("evidence_preserved", True)
        expanded.append(normalized)

    normalized_result = dict(result)
    normalized_result["suggestions"] = expanded
    return normalized_result


def _group_batch_prompt_contexts(
    contexts: list[dict[str, Any]],
    *,
    max_evidence_items: int = _REPHRASE_PROMPT_EVIDENCE_MAX_ITEMS,
    max_evidence_chars: int = _REPHRASE_PROMPT_EVIDENCE_MAX_CHARS,
) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    first_context = next(
        (
            context
            for context in contexts
            if isinstance(context, dict)
        ),
        {},
    )
    jd_profile = first_context.get("jd_profile") or {}
    raw_jd_text = _clean(first_context.get("raw_jd_text"))

    for context in contexts:
        if not isinstance(context, dict):
            continue
        project_index = int(context.get("project_index", -1))
        bullet_index = int(context.get("bullet_index", -1))
        if project_index < 0 or bullet_index < 0:
            continue
        project = grouped.setdefault(
            project_index,
            {
                "project_index": project_index,
                "project_title": _clean(context.get("project_title")),
                "frozen_project_evidence": list(
                    context.get("frozen_project_evidence") or []
                ),
                "bullets": [],
            },
        )
        project["bullets"].append(
            {
                "bullet_index": bullet_index,
                "canonical_bullet": _clean(
                    context.get("canonical_bullet")
                ),
                "current_bullet": _clean(context.get("current_bullet")),
            }
        )

    for project in grouped.values():
        bullet_texts = [
            _clean(bullet.get("canonical_bullet"))
            for bullet in project.get("bullets", [])
            if isinstance(bullet, dict)
        ] + [
            _clean(bullet.get("current_bullet"))
            for bullet in project.get("bullets", [])
            if isinstance(bullet, dict)
        ]
        project["frozen_project_evidence"] = _select_prompt_evidence(
            evidence=list(project.get("frozen_project_evidence") or []),
            bullet_texts=bullet_texts,
            jd_profile=jd_profile if isinstance(jd_profile, dict) else {},
            raw_jd_text=raw_jd_text,
            max_items=max_evidence_items,
            max_chars=max_evidence_chars,
        )

    return [grouped[index] for index in sorted(grouped)]


def _suggest_jd_specific_rephrases_batch_single_call(
    *,
    contexts: list[dict[str, Any]],
    model: str | None = None,
    previous_suggestions: list[dict[str, Any]] | None = None,
    attempt_number: int = 1,
) -> dict[str, Any]:
    usable = [
        context
        for context in contexts
        if isinstance(context, dict)
        and int(context.get("project_index", -1)) >= 0
        and int(context.get("bullet_index", -1)) >= 0
    ]
    if not usable:
        raise ValueError("No project bullets are available for batch rephrasing.")

    first = usable[0]
    (
        prompt_evidence_max_items,
        prompt_evidence_max_chars,
    ) = _rephrase_prompt_evidence_limits(model)
    grouped_prompt_contexts = _group_batch_prompt_contexts(
        usable,
        max_evidence_items=prompt_evidence_max_items,
        max_evidence_chars=prompt_evidence_max_chars,
    )
    changed_only_output = _use_changed_only_rephrase_output(model)
    return_instruction = (
        "Return only safely changed rows. Omit unchanged bullets. "
        "Keep indexes unchanged."
        if changed_only_output
        else (
            "Return one row for every supplied bullet. Keep all indexes "
            "unchanged. Leave cosmetic-only rows unchanged."
        )
    )
    system_prompt = (
        JD_REPHRASE_BATCH_PROMPT
        + "\n\n"
        + _JD_REPHRASE_MEANINGFUL_ONLY_SUFFIX
        + (
            "\n\n"
            + _LOCAL_REPHRASE_CHANGED_ONLY_SUFFIX
            if changed_only_output
            else ""
        )
    )
    user_prompt = f"""
TARGET JD PROFILE:
{_compact_prompt_json(first.get("jd_profile") or {})}

TARGET JD TEXT:
{first.get("raw_jd_text") or ""}

PROJECTS AND BULLETS:
{_compact_prompt_json(grouped_prompt_contexts)}

PREVIOUS BATCH TO AVOID REPEATING:
{_compact_prompt_json(previous_suggestions or [])}

ATTEMPT:
{int(attempt_number)}

{return_instruction}
"""
    result = ask_json(
        system_prompt,
        user_prompt,
        temperature=0.2,
        max_tokens=_batch_rephrase_output_max_tokens(
            model,
            len(usable),
        ),
        route="rephrase",
        model=model,
    )
    if changed_only_output:
        result = _expand_sparse_local_rephrase_result(
            result,
            usable,
        )

    returned: dict[tuple[int, int], dict[str, Any]] = {}
    for row in result.get("suggestions", []) or []:
        if not isinstance(row, dict):
            continue
        try:
            key = (
                int(row.get("project_index", -1)),
                int(row.get("bullet_index", -1)),
            )
        except (TypeError, ValueError):
            continue
        if key not in returned:
            returned[key] = row

    suggestions: list[dict[str, Any]] = []
    for context in usable:
        key = (
            int(context["project_index"]),
            int(context["bullet_index"]),
        )
        row = returned.get(key) or {}
        proposed = row.get("suggested_bullet")
        if not _clean(proposed):
            proposed = context.get("current_bullet")
        validation = validate_rephrase_suggestion(
            context=context,
            suggested_bullet=proposed,
        )
        suggestions.append(
            {
                "batch_preview_version": JD_REPHRASE_BATCH_PREVIEW_VERSION,
                "preview_version": JD_REPHRASE_PREVIEW_VERSION,
                "project_index": key[0],
                "bullet_index": key[1],
                **validation,
                "reason": _clean(row.get("reason")),
                "jd_terms_used": [
                    _clean(value)
                    for value in row.get("jd_terms_used", []) or []
                    if _clean(value)
                ],
                "model_evidence_preserved": bool(
                    row.get("evidence_preserved", False)
                ),
                "attempt_number": int(attempt_number),
            }
        )

    return {
        "batch_preview_version": JD_REPHRASE_BATCH_PREVIEW_VERSION,
        "preview_version": JD_REPHRASE_PREVIEW_VERSION,
        "attempt_number": int(attempt_number),
        "suggestion_count": len(suggestions),
        "suggestions": suggestions,
        "historical_phase8_used": False,
        "live_evidence_library_used": False,
    }


def _is_local_ollama_rephrase_model(
    model: str | None,
) -> bool:
    cleaned = str(model or "").strip()
    return bool(
        cleaned.startswith(
            (
                "ollama/",
                "ollama_chat/",
            )
        )
        and ":cloud" not in cleaned.lower()
    )


def _is_groq_qwen_rephrase_model(
    model: str | None,
) -> bool:
    cleaned = str(model or "").strip()
    return cleaned.startswith("groq/qwen/")


def _groq_rephrase_batch_max_bullets() -> int:
    raw = os.getenv(
        "GROQ_REPHRASE_BATCH_MAX_BULLETS",
        "6",
    ).strip()

    try:
        parsed = int(raw)
    except ValueError:
        parsed = 6

    return max(1, parsed)


def _rephrase_batch_chunk_size(
    model: str | None,
    bullet_count: int,
) -> int:
    total = max(1, int(bullet_count))

    if _is_local_ollama_rephrase_model(model):
        return min(
            total,
            _ollama_rephrase_batch_max_bullets(),
        )

    if _is_groq_qwen_rephrase_model(model):
        return min(
            total,
            _groq_rephrase_batch_max_bullets(),
        )

    return total


def _ollama_rephrase_batch_max_bullets() -> int:
    raw = os.getenv(
        "OLLAMA_REPHRASE_BATCH_MAX_BULLETS",
        "3",
    ).strip()

    try:
        parsed = int(raw)
    except ValueError:
        parsed = 3

    return max(1, parsed)


def _suggestion_key(
    value: dict[str, Any],
) -> tuple[int, int] | None:
    try:
        project_index = int(value.get("project_index", -1))
        bullet_index = int(value.get("bullet_index", -1))
    except (TypeError, ValueError):
        return None

    if project_index < 0 or bullet_index < 0:
        return None

    return project_index, bullet_index


def _previous_suggestions_for_contexts(
    previous_suggestions: list[dict[str, Any]] | None,
    contexts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed = {
        key
        for context in contexts
        if isinstance(context, dict)
        for key in [_suggestion_key(context)]
        if key is not None
    }

    return [
        row
        for row in (previous_suggestions or [])
        if isinstance(row, dict)
        and _suggestion_key(row) in allowed
    ]


def suggest_jd_specific_rephrases_batch(
    *,
    contexts: list[dict[str, Any]],
    model: str | None = None,
    previous_suggestions: list[dict[str, Any]] | None = None,
    attempt_number: int = 1,
) -> dict[str, Any]:
    usable = [
        context
        for context in contexts
        if isinstance(context, dict)
        and _suggestion_key(context) is not None
    ]

    if not usable:
        raise ValueError(
            "No project bullets are available for batch rephrasing."
        )

    chunk_size = _rephrase_batch_chunk_size(
        model,
        len(usable),
    )

    if len(usable) <= chunk_size:
        result = _suggest_jd_specific_rephrases_batch_single_call(
            contexts=usable,
            model=model,
            previous_suggestions=previous_suggestions,
            attempt_number=attempt_number,
        )
        result["chunked_model_calls"] = False
        result["model_call_count"] = 1
        result["model_call_chunk_size"] = len(usable)
        return result

    combined: list[dict[str, Any]] = []
    call_count = 0

    for start in range(0, len(usable), chunk_size):
        chunk = usable[start : start + chunk_size]
        chunk_previous = _previous_suggestions_for_contexts(
            previous_suggestions,
            chunk,
        )

        result = _suggest_jd_specific_rephrases_batch_single_call(
            contexts=chunk,
            model=model,
            previous_suggestions=chunk_previous,
            attempt_number=attempt_number,
        )
        call_count += 1

        rows = result.get("suggestions", []) or []
        if isinstance(rows, list):
            combined.extend(
                row
                for row in rows
                if isinstance(row, dict)
            )

    return {
        "batch_preview_version": JD_REPHRASE_BATCH_PREVIEW_VERSION,
        "preview_version": JD_REPHRASE_PREVIEW_VERSION,
        "attempt_number": int(attempt_number),
        "suggestion_count": len(combined),
        "suggestions": combined,
        "historical_phase8_used": False,
        "live_evidence_library_used": False,
        "chunked_model_calls": True,
        "model_call_count": call_count,
        "model_call_chunk_size": chunk_size,
    }


def build_rephrased_generation_batch_candidate(
    *,
    generation: dict[str, Any],
    accepted_changes: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate = deepcopy(generation)
    seen: set[tuple[int, int]] = set()
    for raw_change in accepted_changes:
        if not isinstance(raw_change, dict):
            continue
        project_index = int(raw_change.get("project_index", -1))
        bullet_index = int(raw_change.get("bullet_index", -1))
        accepted = _clean(raw_change.get("accepted_bullet"))
        key = (project_index, bullet_index)
        if key in seen:
            raise ValueError("Duplicate batch rephrase target.")
        seen.add(key)
        candidate = build_rephrased_generation_candidate(
            generation=candidate,
            project_index=project_index,
            bullet_index=bullet_index,
            accepted_bullet=accepted,
        )
    if not seen:
        raise ValueError("No accepted rephrase changes were supplied.")
    return candidate


def evaluate_rephrase_batch_candidate(
    *,
    baseline_report: dict[str, Any],
    current_generation: dict[str, Any],
    accepted_changes: list[dict[str, Any]],
) -> dict[str, Any]:
    proposed = build_rephrased_generation_batch_candidate(
        generation=current_generation,
        accepted_changes=accepted_changes,
    )
    projects = (
        (proposed.get("projects") or {}).get("recommended_projects") or []
    )
    target_keys: set[tuple[str, int]] = set()
    for change in accepted_changes:
        project_index = int(change.get("project_index", -1))
        bullet_index = int(change.get("bullet_index", -1))
        if not (0 <= project_index < len(projects)):
            continue
        project = projects[project_index]
        if not isinstance(project, dict):
            continue
        title = _normalise(
            project.get("display_title") or project.get("title")
        )
        target_keys.add((title, bullet_index))

    lineage = audit_claim_lineage_v2(
        baseline_report.get("resume_profile") or {},
        proposed,
    )
    target_risks = [
        risk
        for risk in lineage.get("project_bullet_review_risks", []) or []
        if isinstance(risk, dict)
        and (
            _normalise(risk.get("project")),
            int(risk.get("bullet_index", -1)),
        ) in target_keys
    ]
    fresh_comparison = build_rephrase_fresh_score_comparison(
        baseline_report=baseline_report,
        current_generation=current_generation,
        proposed_generation=proposed,
    )
    return {
        "batch_preview_version": JD_REPHRASE_BATCH_PREVIEW_VERSION,
        "preview_version": JD_REPHRASE_PREVIEW_VERSION,
        "safe_to_accept": not target_risks,
        "target_claim_lineage_risks": target_risks,
        "claim_lineage": lineage,
        "fresh_score_comparison": fresh_comparison,
        "proposed_generation": proposed,
        "accepted_change_count": len(accepted_changes),
        "historical_phase8_used": False,
    }

# ---------------------------------------------------------------------------
# Patch 2.2n — deterministic score-gain review for generated bullets
# ---------------------------------------------------------------------------

JD_SCORE_OPTIMIZATION_VERSION = "jd-score-optimization-v2.2n"


def build_jd_score_optimization_review(
    *,
    generation: dict[str, Any],
    baseline_report: dict[str, Any],
    model: str | None = None,
    project_indices: list[int] | None = None,
    attempt_number: int = 1,
) -> dict[str, Any]:
    """Generate alternatives, then keep only verified positive-score gains.

    The model is only a proposal source. Existing preview guards, claim-lineage
    verification, and the pinned fresh deterministic scorer decide whether an
    alternative is eligible for this score-optimization review.
    """
    contexts = build_rephrase_batch_contexts(
        generation=generation,
        baseline_report=baseline_report,
        project_indices=project_indices,
    )
    if not contexts:
        return {
            "optimization_version": JD_SCORE_OPTIMIZATION_VERSION,
            "attempt_number": int(attempt_number),
            "opportunity_count": 0,
            "opportunities": [],
            "rejected_candidates": [],
            "suggestion_count": 0,
            "diagnostics": {
                "reviewed_bullet_count": 0,
                "normalized_suggestion_row_count": 0,
                "changed_proposal_count": 0,
                "unchanged_or_no_change_count": 0,
                "positive_opportunity_count": 0,
                "rejected_changed_proposal_count": 0,
                "model_call_count": 0,
            },
            "historical_phase8_used": False,
        }

    batch = suggest_jd_specific_rephrases_batch(
        contexts=contexts,
        model=model,
        attempt_number=int(attempt_number),
    )

    context_by_key = {
        (
            int(context.get("project_index", -1)),
            int(context.get("bullet_index", -1)),
        ): context
        for context in contexts
        if isinstance(context, dict)
    }

    reviewed_bullet_count = len(contexts)
    normalized_suggestions = [
        suggestion
        for suggestion in (
            batch.get("suggestions", []) or []
        )
        if isinstance(suggestion, dict)
    ]
    changed_proposal_count = 0
    unchanged_or_no_change_count = 0

    for diagnostic_suggestion in normalized_suggestions:
        diagnostic_key = (
            int(
                diagnostic_suggestion.get(
                    "project_index",
                    -1,
                )
            ),
            int(
                diagnostic_suggestion.get(
                    "bullet_index",
                    -1,
                )
            ),
        )
        diagnostic_context = context_by_key.get(
            diagnostic_key
        )
        if not isinstance(diagnostic_context, dict):
            continue

        diagnostic_before = _clean(
            diagnostic_context.get(
                "current_bullet"
            )
        )
        diagnostic_after = _clean(
            diagnostic_suggestion.get(
                "suggested_bullet"
            )
        )

        if (
            diagnostic_after
            and diagnostic_after
            != diagnostic_before
        ):
            changed_proposal_count += 1
        else:
            unchanged_or_no_change_count += 1

    accounted_rows = (
        changed_proposal_count
        + unchanged_or_no_change_count
    )
    if accounted_rows < reviewed_bullet_count:
        unchanged_or_no_change_count += (
            reviewed_bullet_count
            - accounted_rows
        )

    opportunities: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for suggestion in batch.get("suggestions", []) or []:
        if not isinstance(suggestion, dict):
            continue

        project_index = int(suggestion.get("project_index", -1))
        bullet_index = int(suggestion.get("bullet_index", -1))
        context = context_by_key.get((project_index, bullet_index))
        if not isinstance(context, dict):
            continue

        before = _clean(context.get("current_bullet"))
        after = _clean(suggestion.get("suggested_bullet"))
        changed = bool(after and after != before)

        if not changed:
            continue

        if not bool(
            suggestion.get(
                "safe_for_lineage_evaluation",
                False,
            )
        ):
            rejected.append(
                {
                    "project_index": project_index,
                    "bullet_index": bullet_index,
                    "before_bullet": before,
                    "after_bullet": after,
                    "reason": "preview_guard_failed",
                    "guard_reasons": deepcopy(
                        suggestion.get("guard_reasons") or []
                    ),
                }
            )
            continue

        evaluation = evaluate_rephrase_candidate(
            baseline_report=baseline_report,
            current_generation=generation,
            project_index=project_index,
            bullet_index=bullet_index,
            accepted_bullet=after,
        )
        if not bool(evaluation.get("safe_to_accept")):
            rejected.append(
                {
                    "project_index": project_index,
                    "bullet_index": bullet_index,
                    "before_bullet": before,
                    "after_bullet": after,
                    "reason": "claim_lineage_failed",
                    "claim_lineage_risks": deepcopy(
                        evaluation.get("target_claim_lineage_risks") or []
                    ),
                }
            )
            continue

        comparison = deepcopy(
            evaluation.get("fresh_score_comparison") or {}
        )
        if not bool(comparison.get("available")):
            rejected.append(
                {
                    "project_index": project_index,
                    "bullet_index": bullet_index,
                    "before_bullet": before,
                    "after_bullet": after,
                    "reason": "fresh_score_unavailable",
                    "fresh_score_comparison": comparison,
                }
            )
            continue

        score_delta = float(comparison.get("score_delta", 0) or 0)
        regressions = list(
            comparison.get("important_regressions") or []
        )
        if score_delta <= 0 or regressions:
            rejected.append(
                {
                    "project_index": project_index,
                    "bullet_index": bullet_index,
                    "before_bullet": before,
                    "after_bullet": after,
                    "reason": (
                        "important_regression"
                        if regressions
                        else "no_positive_score_gain"
                    ),
                    "fresh_score_comparison": comparison,
                }
            )
            continue

        opportunities.append(
            {
                "optimization_version": JD_SCORE_OPTIMIZATION_VERSION,
                "project_index": project_index,
                "bullet_index": bullet_index,
                "project_title": _clean(
                    context.get("project_title")
                    or f"Project {project_index + 1}"
                ),
                "before_bullet": before,
                "after_bullet": after,
                "accepted_change": {
                    "project_index": project_index,
                    "bullet_index": bullet_index,
                    "accepted_bullet": after,
                },
                "fresh_score_comparison": comparison,
                "preview_guard_safe": True,
                "claim_lineage_safe": True,
                "historical_phase8_used": False,
            }
        )

    opportunities.sort(
        key=lambda row: (
            -float(
                (row.get("fresh_score_comparison") or {}).get(
                    "score_delta",
                    0,
                )
                or 0
            ),
            int(row.get("project_index", 0)),
            int(row.get("bullet_index", 0)),
        )
    )

    no_change_details = []
    for diagnostic_suggestion in normalized_suggestions:
        diagnostic_key = (
            int(
                diagnostic_suggestion.get(
                    "project_index",
                    -1,
                )
            ),
            int(
                diagnostic_suggestion.get(
                    "bullet_index",
                    -1,
                )
            ),
        )
        diagnostic_context = context_by_key.get(
            diagnostic_key
        )
        if not isinstance(diagnostic_context, dict):
            continue

        diagnostic_before = _clean(
            diagnostic_context.get(
                "current_bullet"
            )
        )
        diagnostic_after = _clean(
            diagnostic_suggestion.get(
                "suggested_bullet"
            )
        )
        if (
            diagnostic_after
            and diagnostic_after
            != diagnostic_before
        ):
            continue

        model_reason = _clean(
            diagnostic_suggestion.get("reason")
        )
        reason_source = (
            "model"
            if model_reason
            else "fallback"
        )
        if not model_reason:
            model_reason = (
                "No specific no-change reason was returned by the model. "
                "The normalized optimizer row remained unchanged or was "
                "reconstructed as unchanged."
            )

        no_change_details.append(
            {
                "project_index": diagnostic_key[0],
                "bullet_index": diagnostic_key[1],
                "project_title": _clean(
                    diagnostic_context.get(
                        "project_title"
                    )
                ),
                "current_bullet": diagnostic_before,
                "reason": model_reason,
                "reason_source": reason_source,
                "jd_terms_used": [
                    _clean(value)
                    for value in (
                        diagnostic_suggestion.get(
                            "jd_terms_used"
                        )
                        or []
                    )
                    if _clean(value)
                ],
            }
        )
    return {
        "optimization_version": JD_SCORE_OPTIMIZATION_VERSION,
        "attempt_number": int(attempt_number),
        "opportunity_count": len(opportunities),
        "opportunities": opportunities,
        "rejected_candidates": rejected,
        "suggestion_count": int(
            batch.get("suggestion_count", 0) or 0
        ),
        "model_call_count": int(
            batch.get("model_call_count", 1) or 1
        ),
        "diagnostics": {
            "reviewed_bullet_count": int(
                reviewed_bullet_count
            ),
            "normalized_suggestion_row_count": int(
                len(normalized_suggestions)
            ),
            "changed_proposal_count": int(
                changed_proposal_count
            ),
            "unchanged_or_no_change_count": int(
                unchanged_or_no_change_count
            ),
            "positive_opportunity_count": int(
                len(opportunities)
            ),
            "rejected_changed_proposal_count": int(
                len(rejected)
            ),
            "model_call_count": int(
                batch.get("model_call_count", 1) or 1
            ),
                                   "no_change_details": no_change_details,
},
        "historical_phase8_used": False,
    }


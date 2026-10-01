"""Advisory automation and debug export for TQ-D2.5/TQ-D2.6."""

from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Any

from tailoring.capability_taxonomy import get_default_taxonomy
from taxonomy_discovery.technology_registry import (
    get_default_registry,
    registry_rows,
)
from taxonomy_discovery.research_proposals import (
    detect_possible_compound_requirement,
)

ASSISTED_REVIEW_VERSION = "capability-taxonomy-discovery-assisted-review-v1.2-registry-aware"

VALID_REVIEW_STATUSES = {
    "research_candidate",
    "existing_taxonomy_near_miss",
    "decomposition_issue",
    "scope_review",
    "defer",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _candidate_text(candidate: dict[str, Any]) -> str:
    observed = candidate.get("observed_terms", []) or []
    if observed:
        return _clean(observed[0])
    return _clean(candidate.get("normalised_observed_text"))


def _contexts(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in candidate.get("observation_contexts", []) or []
        if isinstance(row, dict)
    ]


def _retrieval_candidates(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for context in _contexts(candidate):
        retrieval = context.get("retrieval", {}) or {}
        if not isinstance(retrieval, dict):
            continue
        for row in retrieval.get("candidates", []) or []:
            if not isinstance(row, dict):
                continue
            capability_id = _clean(row.get("capability_id"))
            if not capability_id:
                continue
            try:
                score = (
                    float(row.get("lexical_score"))
                    if row.get("lexical_score") is not None
                    else None
                )
            except (TypeError, ValueError):
                score = None
            current = rows.get(capability_id)
            if (
                current is None
                or (
                    score is not None
                    and (
                        current.get("lexical_score") is None
                        or score > float(current["lexical_score"])
                    )
                )
            ):
                rows[capability_id] = {
                    "capability_id": capability_id,
                    "lexical_score": score,
                }

    return sorted(
        rows.values(),
        key=lambda row: (
            -1.0
            if row.get("lexical_score") is None
            else -float(row["lexical_score"]),
            str(row.get("capability_id") or ""),
        ),
    )


def _has_atomic_parent_context(candidate: dict[str, Any]) -> bool:
    text = _candidate_text(candidate)
    return any(
        bool(context.get("is_atomic"))
        and _clean(context.get("parent_text"))
        and _clean(context.get("parent_text")).lower() != text.lower()
        for context in _contexts(candidate)
    )


def _fragmentary(candidate: dict[str, Any]) -> bool:
    if not _has_atomic_parent_context(candidate):
        return False
    text = _candidate_text(candidate)
    words = re.findall(r"[A-Za-z0-9+#.-]+", text)
    lowered = text.lower()
    return (
        len(words) <= 3
        or lowered.endswith((",", ";", " and", " or", " to", " with"))
    )


def _scope_reason(text: str) -> str | None:
    patterns = (
        (
            r"\b(?:bachelor'?s?|master'?s?|diploma|degree|phd|doctorate)\b",
            "education_or_credential_scope",
        ),
        (
            r"\b(?:24\s*/\s*7|standby|on[- ]call|overtime|shift work|shift roles?)\b",
            "working_conditions_scope",
        ),
        (
            r"\b(?:visa|work authori[sz]ation|citizen(?:ship)?|security clearance)\b",
            "eligibility_or_clearance_scope",
        ),
    )
    for pattern, reason in patterns:
        if re.search(pattern, text, flags=re.I):
            return reason
    return None


def _duration_language(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:\d+\s*(?:[-–]\s*\d+)?|at least \d+|minimum of \d+)"
            r"\s*\+?\s*years?\b",
            text,
            flags=re.I,
        )
        and re.search(r"\bexperience\b", text, flags=re.I)
    )


def build_deterministic_suggestion(
    candidate: dict[str, Any],
) -> dict[str, Any]:
    registry = candidate.get("technology_registry_resolution", {}) or {}
    status = registry.get("status")

    base = {
        "assistant_version": ASSISTED_REVIEW_VERSION,
        "candidate_id": _clean(candidate.get("candidate_id")),
        "candidate_text": _candidate_text(candidate),
        "suggested_status": None,
        "suggested_target_capability_id": None,
        "confidence": "none",
        "reasons": [],
        "routing": "human_review",
        "advisory_only": True,
    }

    if status == "resolved":
        base.update(
            {
                "routing": "registry_resolved",
                "confidence": "high",
                "reasons": [
                    "The exact technology/terminology alias is recognized by the approved technology registry.",
                    "The registry has an approved deterministic mapping to "
                    + str(registry.get("capability_id"))
                    + ".",
                    "No human triage is required unless you want to override or audit the relationship.",
                ],
            }
        )
        return base

    if status == "recognized_unmapped":
        base.update(
            {
                "suggested_status": "research_candidate",
                "confidence": "medium",
                "reasons": [
                    "The technology/term is already recognized by the registry.",
                    "The registry intentionally has no approved canonical capability mapping yet.",
                    "Research/review can decide whether to map it to an existing capability or propose a new one.",
                ],
            }
        )
        return base

    text = _candidate_text(candidate)
    scope = _scope_reason(text)
    if scope:
        base.update(
            {
                "suggested_status": "scope_review",
                "confidence": "high",
                "reasons": [
                    f"Deterministic scope pattern: {scope}.",
                    "This looks more like hiring/education/working-condition scope than a reusable capability.",
                ],
            }
        )
        return base

    if _fragmentary(candidate):
        base.update(
            {
                "suggested_status": "decomposition_issue",
                "confidence": "high",
                "reasons": [
                    "The candidate is an atomic child with a larger parent requirement.",
                    "The child text is unusually short or syntactically fragmentary.",
                ],
            }
        )
        return base

    compound = detect_possible_compound_requirement(candidate)
    if compound.get("possible"):
        base.update(
            {
                "suggested_status": "decomposition_issue",
                "confidence": "medium",
                "reasons": [
                    "The non-atomic requirement contains multiple distinct capability/technology hints.",
                    "Detected hints: "
                    + ", ".join(compound.get("hints", []))
                    + ".",
                    "This is diagnostic-only; the JD parser/decomposition behavior is not changed on this branch.",
                ],
            }
        )
        return base

    retrieval = _retrieval_candidates(candidate)
    top = retrieval[0] if retrieval else None
    top_id = str(top.get("capability_id")) if top else None
    top_score = (
        float(top["lexical_score"])
        if top and top.get("lexical_score") is not None
        else None
    )
    second_score = (
        float(retrieval[1]["lexical_score"])
        if len(retrieval) > 1
        and retrieval[1].get("lexical_score") is not None
        else 0.0
    )
    margin = (
        top_score - second_score
        if top_score is not None
        else 0.0
    )

    if (
        _duration_language(text)
        and top_id == "experience.duration"
        and top_score is not None
    ):
        base.update(
            {
                "suggested_status": "existing_taxonomy_near_miss",
                "suggested_target_capability_id": "experience.duration",
                "confidence": "high",
                "reasons": [
                    "The requirement explicitly expresses a numeric years-of-experience constraint.",
                    f"Shadow retrieval ranks experience.duration first at {top_score:.3f}.",
                    (
                        f"The margin over the next candidate is {margin:.3f}; "
                        "the explicit duration pattern is the primary signal."
                    ),
                ],
            }
        )
        return base

    if (
        top_id
        and top_score is not None
        and top_score >= 0.70
        and margin >= 0.25
    ):
        base.update(
            {
                "suggested_status": "existing_taxonomy_near_miss",
                "suggested_target_capability_id": top_id,
                "confidence": "medium",
                "reasons": [
                    f"One existing capability is a comparatively strong lexical match ({top_score:.3f}).",
                    f"The margin over the next candidate is {margin:.3f}.",
                    "Lexical retrieval remains diagnostic-only; human confirmation is required.",
                ],
            }
        )
        return base

    base.update(
        {
            "suggested_status": "defer",
            "confidence": "low",
            "reasons": [
                "Neither the registry nor deterministic diagnostics provide a strong routing decision.",
                "Use taxonomy search or an optional local-Ollama second opinion before confirming a review.",
            ],
        }
    )
    return base


def taxonomy_catalog() -> list[dict[str, Any]]:
    taxonomy = get_default_taxonomy()
    rows: list[dict[str, Any]] = []
    for capability in taxonomy.capabilities:
        requirement = capability.get("requirement", {}) or {}
        rows.append(
            {
                "capability_id": _clean(capability.get("capability_id")),
                "label": _clean(capability.get("label")),
                "domain": _clean(capability.get("domain")),
                "requirement_terms": list(requirement.get("any_terms", []) or []),
            }
        )
    return rows


def search_taxonomy(
    query: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    needle = _clean(query).lower()
    if not needle:
        return []
    tokens = set(re.findall(r"[a-z0-9+#.-]+", needle))
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for row in taxonomy_catalog():
        haystack = " ".join(
            [
                row["capability_id"],
                row["label"],
                row["domain"],
                " ".join(row["requirement_terms"]),
            ]
        ).lower()
        score = 100 if needle in haystack else 0
        score += sum(1 for token in tokens if token in haystack)
        if score:
            scored.append((-score, row["capability_id"], row))
    scored.sort(key=lambda item: (item[0], item[1]))
    return [row for _, _, row in scored[: max(1, int(limit))]]


def local_ollama_models() -> dict[str, str]:
    from llm import get_model_options

    return {
        label: model_id
        for label, model_id in get_model_options().items()
        if str(model_id).startswith("ollama/")
        and ":cloud" not in str(model_id)
    }


_AI_SYSTEM = """You are a taxonomy discovery review assistant.
Return one JSON object only. Your output is advisory and cannot mutate data.

Allowed suggested_status:
research_candidate
existing_taxonomy_near_miss
decomposition_issue
scope_review
defer

If existing_taxonomy_near_miss is selected, target_capability_id must be an
existing capability ID from the supplied taxonomy catalogue. Otherwise target
must be null. Treat deterministic registry resolution as authoritative input:
if registry status is resolved, explain that no manual review is needed rather
than inventing a different target.
"""


def ask_local_ai_suggestion(
    candidate: dict[str, Any],
    *,
    model: str,
    deterministic_suggestion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model = _clean(model)
    if not model.startswith("ollama/") or ":cloud" in model:
        raise ValueError(
            "Assisted review is restricted to a local Ollama model."
        )

    from llm import ask_json

    payload = {
        "candidate": candidate,
        "deterministic_suggestion": deterministic_suggestion,
        "taxonomy_catalog": taxonomy_catalog(),
        "technology_registry": registry_rows(get_default_registry()),
    }
    raw = ask_json(
        _AI_SYSTEM,
        json.dumps(payload, ensure_ascii=False),
        model=model,
        route="analysis",
        max_tokens=900,
        temperature=0.0,
    )

    status = _clean(raw.get("suggested_status"))
    if status not in VALID_REVIEW_STATUSES:
        raise ValueError(
            f"Unsupported local-AI suggested_status: {status!r}"
        )

    target = _clean(raw.get("target_capability_id")) or None
    taxonomy_ids = {
        row["capability_id"]
        for row in taxonomy_catalog()
    }
    if status == "existing_taxonomy_near_miss":
        if not target or target not in taxonomy_ids:
            raise ValueError(
                "Local-AI near-miss target must be a current capability ID."
            )
    else:
        target = None

    reasons = raw.get("reasons")
    if not isinstance(reasons, list):
        one = _clean(raw.get("reason") or raw.get("reasoning_summary"))
        reasons = [one] if one else []

    confidence = raw.get("confidence")
    if isinstance(confidence, (int, float)):
        confidence_value: Any = round(
            max(0.0, min(1.0, float(confidence))),
            3,
        )
    else:
        confidence_value = _clean(confidence) or "unspecified"

    return {
        "assistant_version": ASSISTED_REVIEW_VERSION,
        "source": "local_ollama",
        "model": model,
        "candidate_id": _clean(candidate.get("candidate_id")),
        "suggested_status": status,
        "suggested_target_capability_id": target,
        "confidence": confidence_value,
        "reasons": [_clean(row) for row in reasons if _clean(row)][:6],
        "advisory_only": True,
    }


def build_debug_bundle(
    *,
    report: dict[str, Any],
    deterministic_suggestions: dict[str, dict[str, Any]],
    ai_suggestions: dict[str, dict[str, Any]],
    persisted_reviews: list[dict[str, Any]],
    ui_state: dict[str, Any],
    selected_candidate: dict[str, Any] | None,
    research_proposals: list[dict[str, Any]] | None = None,
    proposal_reviews: list[dict[str, Any]] | None = None,
) -> bytes:
    manifest = {
        "export_version": ASSISTED_REVIEW_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "discovery_version": report.get("discovery_version"),
        "triage_version": report.get("triage_version"),
        "technology_registry_version": report.get(
            "technology_registry_version"
        ),
        "taxonomy_version": report.get("taxonomy_version"),
        "match_version": report.get("match_version"),
        "scoring_version": report.get("scoring_version"),
        "candidate_count": report.get("candidate_count"),
        "registry_resolved_candidate_count": report.get(
            "registry_resolved_candidate_count"
        ),
        "manual_review_eligible_candidate_count": report.get(
            "manual_review_eligible_candidate_count"
        ),
        "human_reviewed_queue_count": report.get(
            "human_reviewed_queue_count"
        ),
        "pending_human_review_candidate_count": report.get(
            "pending_human_review_candidate_count"
        ),
        "manual_review_queue_count": report.get(
            "manual_review_queue_count"
        ),
    }

    files = {
        "manifest.json": manifest,
        "candidate_queue.json": report.get("candidates", []),
        "triage_summary.json": {
            key: report.get(key)
            for key in (
                "triage_status_counts",
                "candidate_count",
                "registry_resolved_candidate_count",
                "registry_recognized_unmapped_candidate_count",
                "registry_unresolved_candidate_count",
                "manual_review_eligible_candidate_count",
                "human_reviewed_queue_count",
                "pending_human_review_candidate_count",
                "manual_review_queue_count",
                "reviewed_candidate_count",
                "unreviewed_candidate_count",
            )
        },
        "technology_registry.json": registry_rows(),
        "deterministic_suggestions.json": deterministic_suggestions,
        "ai_suggestions.json": ai_suggestions,
        "persisted_reviews.json": persisted_reviews,
        "research_proposals.json": research_proposals or [],
        "proposal_reviews.json": proposal_reviews or [],
        "ui_state.json": ui_state,
    }
    if selected_candidate is not None:
        files["current_candidate.json"] = selected_candidate

    readme = """Capability Discovery Debug Bundle

Deterministic registry mappings may remove candidates from the manual review
queue, but they do not edit the canonical capability taxonomy or Job Match
snapshot. Deterministic and local-AI review suggestions are advisory until an
explicit human action saves a review.
"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr("README.txt", readme)
        for name, payload in files.items():
            archive.writestr(
                name,
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
            )
    return buffer.getvalue()

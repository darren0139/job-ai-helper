from __future__ import annotations

import json
import os
from typing import Any
from urllib import request


BROAD_MINING_REVIEW_ASSIST_VERSION = (
    "tqd3-broad-mining-review-assist-v1.0.0"
)

_ALLOWED_DECISIONS = {
    "research_further",
    "defer",
    "reject",
}
_ALLOWED_CONFIDENCE = {
    "high",
    "medium",
    "low",
}


def _supporting_source_count(
    candidate: dict[str, Any],
) -> int:
    urls = candidate.get("supporting_source_urls") or []
    return len(urls) if isinstance(urls, list) else 0


def _authority_counts(
    candidate: dict[str, Any],
) -> dict[str, int]:
    authority = candidate.get("source_authority")
    authority = authority if isinstance(authority, dict) else {}
    counts = authority.get("counts")
    counts = counts if isinstance(counts, dict) else {}

    def count(key: str) -> int:
        value = counts.get(key, 0)
        return int(value) if isinstance(value, (int, float)) else 0

    return {
        "primary_official": count("primary_official"),
        "first_party_other_technology": count(
            "first_party_other_technology"
        ),
        "secondary": count("secondary"),
        "unclassified": count("unclassified"),
    }


def _build_broad_mining_review_suggestion_v141(
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Build a conservative deterministic review suggestion.

    The suggestion is advisory only. It never persists a decision and never
    performs network/model calls.
    """
    if not isinstance(candidate, dict):
        raise TypeError("candidate must be a dict")

    status = str(candidate.get("status") or "")
    supporting = _supporting_source_count(candidate)
    counts = _authority_counts(candidate)
    primary = counts["primary_official"]
    secondary = counts["secondary"]
    unclassified = counts["unclassified"]
    has_primary = primary > 0

    decision = "defer"
    confidence = "low"
    reasons: list[str] = []

    if status == "ambiguous_registry_match":
        decision = "defer"
        confidence = "high"
        reasons.append(
            "Exact registry matching is ambiguous, so deterministic routing "
            "must not choose a new technology identity automatically."
        )
    elif status != "possible_new_technology":
        decision = "defer"
        confidence = "high"
        reasons.append(
            "Only possible-new or ambiguous candidates are reviewable in "
            "this queue."
        )
    elif has_primary and supporting >= 2:
        decision = "research_further"
        confidence = "high"
        reasons.append(
            "The candidate has primary-official evidence and multiple "
            "supporting sources."
        )
    elif has_primary:
        decision = "research_further"
        confidence = "medium"
        reasons.append(
            "The candidate has primary-official evidence, but supporting "
            "coverage is still limited."
        )
    elif supporting >= 3 and secondary >= 1:
        decision = "research_further"
        confidence = "medium"
        reasons.append(
            "The candidate has multiple supporting sources including known "
            "secondary evidence, but no primary-official source yet."
        )
    elif supporting == 0:
        decision = "defer"
        confidence = "high"
        reasons.append(
            "The candidate has no supporting source URLs."
        )
    elif unclassified >= supporting:
        decision = "defer"
        confidence = "medium"
        reasons.append(
            "All supporting sources remain unclassified by the deterministic "
            "source-authority rules."
        )
    else:
        decision = "defer"
        confidence = "medium"
        reasons.append(
            "Evidence is not strong enough for a deterministic "
            "research-further recommendation."
        )

    if primary:
        reasons.append(
            f"{primary} primary-official source(s) classified."
        )
    if secondary:
        reasons.append(
            f"{secondary} secondary source(s) classified."
        )
    if unclassified:
        reasons.append(
            f"{unclassified} source(s) remain unclassified."
        )

    return {
        "assist_version": BROAD_MINING_REVIEW_ASSIST_VERSION,
        "candidate_id": str(candidate.get("candidate_id") or ""),
        "suggested_decision": decision,
        "confidence": confidence,
        "reasons": reasons,
        "signals": {
            "candidate_status": status,
            "supporting_sources": supporting,
            "authority_counts": counts,
            "has_primary_official": has_primary,
        },
        "governance": {
            "network_calls": 0,
            "model_calls": 0,
            "automatic_persistence": False,
            "proposal_creation": False,
            "registry_mutations": 0,
            "taxonomy_mutations": 0,
            "scoring_influence": False,
        },
    }


def validate_ollama_candidate_review(
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(
            "Ollama candidate review must be a JSON object."
        )

    decision = str(
        payload.get("suggested_decision") or ""
    ).strip()
    confidence = str(
        payload.get("confidence") or ""
    ).strip()

    if decision not in _ALLOWED_DECISIONS:
        raise ValueError(
            "Ollama suggested_decision must be one of "
            "research_further, defer, reject."
        )
    if confidence not in _ALLOWED_CONFIDENCE:
        raise ValueError(
            "Ollama confidence must be high, medium, or low."
        )

    reasons = payload.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
    reasons = [
        str(value).strip()
        for value in reasons
        if str(value).strip()
    ]

    return {
        "suggested_decision": decision,
        "confidence": confidence,
        "reasons": reasons,
    }


def ask_local_ollama_candidate_review(
    candidate: dict[str, Any],
    *,
    model: str,
    deterministic_suggestion: dict[str, Any],
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    """Ask a local Ollama model for an advisory second opinion.

    This function is called only from an explicit UI action. It does not
    persist the returned suggestion.
    """
    model = str(model or "").strip()
    if not model:
        raise ValueError("Ollama model is required")

    base_url = (
        os.getenv(
            "OLLAMA_BASE_URL",
            "http://127.0.0.1:11434",
        )
        .strip()
        .rstrip("/")
    )

    prompt_payload = {
        "candidate": candidate,
        "deterministic_suggestion": deterministic_suggestion,
        "allowed_decisions": [
            "research_further",
            "defer",
            "reject",
        ],
        "instruction": (
            "Return JSON only. Review whether this untrusted mined "
            "technology candidate should be researched further, deferred, "
            "or rejected as noise. Do not invent sources. Do not decide "
            "registry inclusion, taxonomy truth, promotion, or scoring. "
            "Prefer defer when evidence is ambiguous."
        ),
    }

    body = json.dumps(
        {
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an advisory reviewer for untrusted software "
                        "technology mining evidence. Return strict JSON with "
                        "suggested_decision, confidence, and reasons."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        prompt_payload,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
        }
    ).encode("utf-8")

    req = request.Request(
        base_url + "/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(
        req,
        timeout=float(timeout_seconds),
    ) as response:
        raw = response.read().decode("utf-8")

    response_payload = json.loads(raw)
    message = (
        response_payload.get("message")
        if isinstance(response_payload, dict)
        else {}
    ) or {}
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError(
            "Ollama response did not contain message.content."
        )

    validated = validate_ollama_candidate_review(
        json.loads(content)
    )
    return {
        **validated,
        "model": model,
        "advisory_only": True,
        "automatic_persistence": False,
    }

TAXONOMY_COVERAGE_VERSION = (
    "tqd3-broad-mining-taxonomy-coverage-v1.0.0"
)


def _normalize_taxonomy_exact(value: Any) -> str:
    import unicodedata

    text = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    )
    return " ".join(text.split()).casefold()


def find_exact_capability_taxonomy_coverage(
    canonical_name: str,
    *,
    taxonomy_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Return conservative exact capability-taxonomy coverage.

    This does not mean the technology is already in the technology registry.
    It only records that the mined canonical name is explicitly represented
    by an existing capability label or requirement.any_terms alias.
    """
    from pathlib import Path

    normalized_name = _normalize_taxonomy_exact(
        canonical_name
    )
    path = (
        Path(taxonomy_path)
        if taxonomy_path is not None
        else (
            Path(__file__).resolve().parents[1]
            / "taxonomy"
            / "capability_taxonomy_v1.json"
        )
    )

    base = {
        "coverage_version": TAXONOMY_COVERAGE_VERSION,
        "matched": False,
        "capability_ids": [],
        "capability_labels": [],
        "match_terms": [],
        "taxonomy_version": "",
        "match_mode": "exact_only",
    }
    if not normalized_name or not path.exists():
        return base

    payload = json.loads(
        path.read_text(encoding="utf-8")
    )
    capabilities = payload.get("capabilities")
    capabilities = (
        capabilities
        if isinstance(capabilities, list)
        else []
    )

    matches: list[dict[str, str]] = []
    for capability in capabilities:
        if not isinstance(capability, dict):
            continue

        capability_id = str(
            capability.get("capability_id") or ""
        ).strip()
        capability_label = str(
            capability.get("label") or ""
        ).strip()

        terms: list[str] = []
        if capability_label:
            terms.append(capability_label)

        requirement = capability.get("requirement")
        if isinstance(requirement, dict):
            any_terms = requirement.get("any_terms")
            if isinstance(any_terms, list):
                terms.extend(
                    str(term)
                    for term in any_terms
                    if str(term).strip()
                )

        for term in terms:
            if (
                _normalize_taxonomy_exact(term)
                == normalized_name
            ):
                matches.append(
                    {
                        "capability_id":
                            capability_id,
                        "capability_label":
                            capability_label,
                        "match_term":
                            str(term),
                    }
                )
                break

    matches.sort(
        key=lambda row: (
            row["capability_id"],
            row["match_term"].casefold(),
        )
    )
    return {
        **base,
        "matched": bool(matches),
        "capability_ids": [
            row["capability_id"]
            for row in matches
        ],
        "capability_labels": [
            row["capability_label"]
            for row in matches
        ],
        "match_terms": [
            row["match_term"]
            for row in matches
        ],
        "taxonomy_version": str(
            payload.get("taxonomy_version") or ""
        ),
    }


def _derive_review_reason_code(
    suggestion: dict[str, Any],
) -> str:
    decision = str(
        suggestion.get("suggested_decision") or ""
    )
    confidence = str(
        suggestion.get("confidence") or ""
    )
    signals = suggestion.get("signals")
    signals = signals if isinstance(signals, dict) else {}
    counts = signals.get("authority_counts")
    counts = counts if isinstance(counts, dict) else {}
    supporting = int(
        signals.get("supporting_sources", 0)
        or 0
    )
    primary = int(
        counts.get("primary_official", 0)
        or 0
    )
    secondary = int(
        counts.get("secondary", 0)
        or 0
    )
    unclassified = int(
        counts.get("unclassified", 0)
        or 0
    )
    status = str(
        signals.get("candidate_status") or ""
    )

    if status == "ambiguous_registry_match":
        return "ambiguous_registry_match"
    if supporting == 0:
        return "no_supporting_sources"
    if (
        decision == "research_further"
        and confidence == "high"
        and primary > 0
    ):
        return "primary_official_multiple_sources"
    if (
        decision == "research_further"
        and primary > 0
    ):
        return "primary_official_limited_sources"
    if (
        decision == "research_further"
        and secondary > 0
    ):
        return "multiple_secondary_supported_sources"
    if (
        decision == "defer"
        and unclassified >= supporting
    ):
        return "all_sources_unclassified"
    return "mixed_or_insufficient_evidence"


def build_broad_mining_review_suggestion(
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Taxonomy-aware wrapper around the v1.4.1 deterministic suggestion."""
    suggestion = (
        _build_broad_mining_review_suggestion_v141(
            candidate
        )
    )
    suggestion = dict(suggestion)

    signals = suggestion.get("signals")
    signals = (
        dict(signals)
        if isinstance(signals, dict)
        else {}
    )
    canonical_name = str(
        candidate.get("canonical_name") or ""
    ).strip()
    taxonomy_coverage = (
        find_exact_capability_taxonomy_coverage(
            canonical_name
        )
    )
    signals["taxonomy_coverage"] = (
        taxonomy_coverage
    )
    suggestion["signals"] = signals

    suggestion["reason_code"] = (
        _derive_review_reason_code(
            suggestion
        )
    )

    status = str(
        candidate.get("status") or ""
    )
    supporting = int(
        signals.get("supporting_sources", 0)
        or 0
    )
    if (
        status == "possible_new_technology"
        and bool(
            taxonomy_coverage.get("matched")
        )
        and supporting >= 1
    ):
        capability_ids = ", ".join(
            taxonomy_coverage.get(
                "capability_ids",
                [],
            )
        )
        explanation = (
            "The canonical technology name already has an exact explicit "
            "match in the capability taxonomy"
            + (
                f" ({capability_ids})"
                if capability_ids
                else ""
            )
            + ". This is therefore a technology-registry coverage gap, "
            "not an unknown concept."
        )
        reasons = suggestion.get("reasons")
        reasons = (
            list(reasons)
            if isinstance(reasons, list)
            else []
        )
        suggestion["suggested_decision"] = (
            "research_further"
        )
        suggestion["confidence"] = "high"
        suggestion["reason_code"] = (
            "exact_capability_taxonomy_coverage"
        )
        suggestion["reasons"] = (
            [explanation] + reasons
        )

    return suggestion

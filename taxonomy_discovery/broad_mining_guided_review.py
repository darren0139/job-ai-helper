from __future__ import annotations

from typing import Any


GUIDED_REVIEW_VERSION = (
    "tqd3-guided-discovery-review-v1.0.0"
)

BUCKET_ALREADY_KNOWN = "already_known"
BUCKET_RECOMMENDED = "recommended"
BUCKET_NEEDS_VERIFICATION = "needs_verification"
BUCKET_OTHER_DISCOVERIES = "other_discoveries"
BUCKET_PARKED = BUCKET_OTHER_DISCOVERIES
BUCKET_CONFIRMED = "confirmed"
BUCKET_DISMISSED = "dismissed"


def _taxonomy_capabilities(
    suggestion: dict[str, Any],
) -> list[str]:
    signals = suggestion.get("signals")
    signals = signals if isinstance(signals, dict) else {}
    coverage = signals.get("taxonomy_coverage")
    coverage = coverage if isinstance(coverage, dict) else {}
    capability_ids = coverage.get("capability_ids")
    capability_ids = (
        capability_ids
        if isinstance(capability_ids, list)
        else []
    )
    return [
        str(value)
        for value in capability_ids
        if str(value).strip()
    ]


def _friendly_reason(
    candidate: dict[str, Any],
    suggestion: dict[str, Any],
) -> str:
    reason_code = str(
        suggestion.get("reason_code") or ""
    )
    capability_ids = _taxonomy_capabilities(
        suggestion
    )

    if reason_code == "exact_capability_taxonomy_coverage":
        if capability_ids:
            return (
                "Known capability already exists: "
                + ", ".join(capability_ids)
                + ". The technology registry is missing this identity."
            )
        return (
            "The capability taxonomy already covers this concept, "
            "but the technology registry does not."
        )

    if reason_code == "primary_official_multiple_sources":
        return (
            "Strong external evidence: primary-official evidence "
            "plus multiple supporting sources."
        )
    if reason_code == "primary_official_limited_sources":
        return (
            "Primary-official evidence exists, but supporting coverage "
            "is still limited."
        )
    if reason_code == "multiple_secondary_supported_sources":
        return (
            "Multiple credible sources support the technology, but "
            "primary-official evidence has not been confirmed yet."
        )
    if reason_code == "ambiguous_registry_match":
        return (
            "The name matches the registry ambiguously and needs "
            "disambiguation before routing."
        )
    if reason_code == "no_supporting_sources":
        return "No supporting source evidence is available yet."
    if reason_code == "all_sources_unclassified":
        return (
            "Current sources are not classified as authoritative enough "
            "for an automatic routing recommendation."
        )
    if reason_code == "mixed_or_insufficient_evidence":
        return (
            "Evidence is mixed or incomplete. Keep it parked unless "
            "you want to investigate it."
        )

    reasons = suggestion.get("reasons")
    if isinstance(reasons, list) and reasons:
        return str(reasons[0])
    return "No clear deterministic routing reason is available."


def _next_action(bucket: str) -> str:
    return {
        BUCKET_ALREADY_KNOWN: "No action",
        BUCKET_RECOMMENDED: "Confirm for verification",
        BUCKET_NEEDS_VERIFICATION: "Review, then confirm if useful",
        BUCKET_OTHER_DISCOVERIES: "No action now",
        BUCKET_CONFIRMED: "Ready for focused verification",
        BUCKET_DISMISSED: "No action",
    }.get(bucket, "Review")


def build_guided_review_item(
    candidate: dict[str, Any],
    suggestion: dict[str, Any],
    review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review = review if isinstance(review, dict) else {}
    status = str(candidate.get("status") or "")
    decision = str(review.get("decision") or "")
    suggested_decision = str(
        suggestion.get("suggested_decision") or ""
    )
    confidence = str(
        suggestion.get("confidence") or ""
    )

    if status == "already_known":
        bucket = BUCKET_ALREADY_KNOWN
    elif decision == "research_further":
        bucket = BUCKET_CONFIRMED
    elif decision == "reject":
        bucket = BUCKET_DISMISSED
    elif decision == "defer":
        bucket = BUCKET_OTHER_DISCOVERIES
    elif (
        suggested_decision == "research_further"
        and confidence == "high"
    ):
        bucket = BUCKET_RECOMMENDED
    elif suggested_decision == "research_further":
        bucket = BUCKET_NEEDS_VERIFICATION
    else:
        bucket = BUCKET_OTHER_DISCOVERIES

    signals = suggestion.get("signals")
    signals = signals if isinstance(signals, dict) else {}
    authority_counts = signals.get("authority_counts")
    authority_counts = (
        authority_counts
        if isinstance(authority_counts, dict)
        else {}
    )
    taxonomy_capabilities = _taxonomy_capabilities(
        suggestion
    )

    return {
        "guided_review_version": GUIDED_REVIEW_VERSION,
        "candidate_id": str(
            candidate.get("candidate_id") or ""
        ),
        "canonical_name": str(
            candidate.get("canonical_name") or ""
        ),
        "candidate_status": status,
        "bucket": bucket,
        "suggested_decision": suggested_decision,
        "confidence": confidence,
        "current_review": decision or "unreviewed",
        "reason_code": str(
            suggestion.get("reason_code") or ""
        ),
        "friendly_reason": _friendly_reason(
            candidate,
            suggestion,
        ),
        "next_action": _next_action(bucket),
        "taxonomy_capabilities":
            taxonomy_capabilities,
        "known_capability": bool(
            taxonomy_capabilities
        ),
        "supporting_sources": int(
            signals.get("supporting_sources", 0)
            or 0
        ),
        "primary_official_sources": int(
            authority_counts.get(
                "primary_official",
                0,
            )
            or 0
        ),
        "secondary_sources": int(
            authority_counts.get(
                "secondary",
                0,
            )
            or 0
        ),
        "unclassified_sources": int(
            authority_counts.get(
                "unclassified",
                0,
            )
            or 0
        ),
    }


def build_guided_review_summary(
    candidates: list[dict[str, Any]],
    suggestions: dict[str, dict[str, Any]],
    reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    review_index = {
        str(row.get("candidate_id") or ""): row
        for row in reviews
        if isinstance(row, dict)
        and str(row.get("candidate_id") or "")
    }

    items = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(
            candidate.get("candidate_id") or ""
        )
        suggestion = suggestions.get(
            candidate_id,
            {},
        )
        if not isinstance(suggestion, dict):
            suggestion = {}
        items.append(
            build_guided_review_item(
                candidate,
                suggestion,
                review_index.get(candidate_id),
            )
        )

    bucket_order = (
        BUCKET_CONFIRMED,
        BUCKET_RECOMMENDED,
        BUCKET_NEEDS_VERIFICATION,
        BUCKET_OTHER_DISCOVERIES,
        BUCKET_ALREADY_KNOWN,
        BUCKET_DISMISSED,
    )
    counts = {
        bucket: sum(
            1
            for item in items
            if item["bucket"] == bucket
        )
        for bucket in bucket_order
    }

    return {
        "guided_review_version": GUIDED_REVIEW_VERSION,
        "items": items,
        "counts": counts,
        "total": len(items),
        "next_step": (
            "verify_confirmed_candidates"
            if counts[BUCKET_CONFIRMED] > 0
            else "review_recommendations"
        ),
        "governance": {
            "network_calls": 0,
            "model_calls": 0,
            "automatic_review_persistence": False,
            "proposal_creation": False,
            "registry_mutations": 0,
            "taxonomy_mutations": 0,
            "scoring_influence": False,
        },
    }

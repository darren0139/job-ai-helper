"""Research proposal contract and approval-preview helpers for TQ-D2.7."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tailoring.capability_taxonomy import get_default_taxonomy
from taxonomy_discovery.technology_registry import (
    REGISTRY_PATH,
    get_default_registry,
    registry_rows,
)

PROPOSAL_CONTRACT_VERSION = "technology-registry-research-proposals-v1"
PROPOSAL_CLASSIFICATIONS = {
    "safe_mapping_candidate",
    "recognized_unmapped",
    "new_capability_candidate",
    "reject",
}
PROPOSAL_REVIEW_DECISIONS = {
    "unreviewed",
    "approve_mapping",
    "keep_unmapped",
    "new_capability_needed",
    "reject_proposal",
}

RESEARCH_CATEGORIES = (
    "programming_languages",
    "frontend",
    "backend_frameworks",
    "databases",
    "caching",
    "messaging_streaming",
    "containers",
    "kubernetes_ecosystem",
    "cloud_platforms",
    "ci_cd",
    "observability",
    "security_iam",
    "data_engineering",
    "ai_ml_llm",
    "mobile",
    "embedded_iot",
    "networking",
    "testing",
    "game_development",
    "distributed_systems",
)

_COMPOUND_HINTS = {
    "image_processing": (
        r"\bimage processing\b",
        r"\bcomputer vision\b",
    ),
    "database": (
        r"\bdatabases?\b",
        r"\bsql\b",
        r"\bnosql\b",
    ),
    "frontend": (
        r"\bfront[- ]?end\b",
        r"\buser interface\b",
        r"\bui\b",
    ),
    "backend": (
        r"\bback[- ]?end\b",
        r"\bserver[- ]side\b",
        r"\bapi development\b",
    ),
    "security": (
        r"\bsecurity\b",
        r"\bauthentication\b",
        r"\bauthori[sz]ation\b",
        r"\bidentity\b",
    ),
    "cloud": (
        r"\bcloud\b",
        r"\baws\b",
        r"\bazure\b",
        r"\bgcp\b",
    ),
    "testing": (
        r"\btesting\b",
        r"\btest automation\b",
        r"\bquality assurance\b",
    ),
    "operating_systems": (
        r"\boperating systems?\b",
        r"\bos[- ]level\b",
        r"\bkernel\b",
    ),
    "networking": (
        r"\bnetworking\b",
        r"\bnetwork protocols?\b",
        r"\btcp/?ip\b",
    ),
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _stable_id(prefix: str, *values: Any) -> str:
    raw = "\n".join(_clean(value) for value in values).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:20]}"


def compound_requirement_hints(text: str) -> list[str]:
    cleaned = _clean(text)
    if not re.search(r"\b(?:and|plus)\b|[,;/]", cleaned, flags=re.I):
        return []

    hits: set[str] = set()
    for name, patterns in _COMPOUND_HINTS.items():
        if any(re.search(pattern, cleaned, flags=re.I) for pattern in patterns):
            hits.add(name)

    # Multiple explicitly known technology aliases are also a useful signal.
    lowered = cleaned.lower()
    for row in registry_rows():
        technology_id = str(row.get("technology_id") or "")
        aliases = row.get("aliases", []) or []
        if any(
            re.search(
                rf"(?<![a-z0-9+#.]){re.escape(str(alias).lower())}(?![a-z0-9+#.])",
                lowered,
            )
            for alias in aliases
            if str(alias).strip()
        ):
            hits.add(f"technology:{technology_id}")

    return sorted(hits)


def detect_possible_compound_requirement(
    candidate: dict[str, Any],
) -> dict[str, Any]:
    contexts = [
        row
        for row in candidate.get("observation_contexts", []) or []
        if isinstance(row, dict)
    ]
    if any(bool(row.get("is_atomic")) for row in contexts):
        return {
            "possible": False,
            "hints": [],
            "reason": "candidate_is_already_atomic",
        }

    observed = candidate.get("observed_terms", []) or []
    text = _clean(
        observed[0]
        if observed
        else candidate.get("normalised_observed_text")
    )
    hints = compound_requirement_hints(text)
    return {
        "possible": len(hints) >= 2,
        "hints": hints,
        "reason": (
            "multiple_distinct_domain_or_technology_hints"
            if len(hints) >= 2
            else "insufficient_distinct_hints"
        ),
    }


def validate_proposal_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValueError("Research proposal bundle must be an object.")

    version = _clean(bundle.get("proposal_bundle_version"))
    if version != PROPOSAL_CONTRACT_VERSION:
        raise ValueError(
            f"Unsupported proposal_bundle_version: {version!r}"
        )

    taxonomy = get_default_taxonomy()
    registry = get_default_registry()

    if _clean(bundle.get("taxonomy_version")) != taxonomy.version:
        raise ValueError(
            "Proposal bundle taxonomy_version does not match the current taxonomy."
        )
    if _clean(bundle.get("registry_version")) != registry.version:
        raise ValueError(
            "Proposal bundle registry_version does not match the current registry."
        )

    proposals = bundle.get("proposals")
    if not isinstance(proposals, list):
        raise ValueError("Proposal bundle proposals must be a list.")

    taxonomy_ids = set(taxonomy.by_id())
    seen_ids: set[str] = set()
    cleaned_proposals: list[dict[str, Any]] = []

    for raw in proposals:
        if not isinstance(raw, dict):
            raise ValueError("Every proposal must be an object.")

        proposal_id = _clean(raw.get("proposal_id"))
        technology_id = _clean(raw.get("technology_id"))
        label = _clean(raw.get("label"))
        entry_kind = _clean(raw.get("entry_kind"))
        classification = _clean(raw.get("proposal_classification"))
        proposed_capability_id = (
            _clean(raw.get("proposed_capability_id")) or None
        )
        relationship_type = (
            _clean(raw.get("relationship_type")) or None
        )
        summary = _clean(raw.get("summary"))

        if not proposal_id:
            raise ValueError("Every proposal requires proposal_id.")
        if proposal_id in seen_ids:
            raise ValueError(f"Duplicate proposal_id: {proposal_id}")
        seen_ids.add(proposal_id)

        if not re.fullmatch(r"[a-z0-9_.-]+", technology_id):
            raise ValueError(
                f"{proposal_id}: invalid technology_id {technology_id!r}."
            )
        if not label:
            raise ValueError(f"{proposal_id}: missing label.")
        if entry_kind not in {
            "framework",
            "runtime",
            "platform",
            "product",
            "protocol",
            "tool",
            "language",
            "architecture_pattern",
        }:
            raise ValueError(f"{proposal_id}: invalid entry_kind.")
        if classification not in PROPOSAL_CLASSIFICATIONS:
            raise ValueError(
                f"{proposal_id}: invalid proposal_classification."
            )

        aliases = raw.get("aliases")
        if not isinstance(aliases, list) or not aliases:
            raise ValueError(
                f"{proposal_id}: aliases must be a non-empty list."
            )
        aliases = sorted(
            {
                _clean(alias)
                for alias in aliases
                if _clean(alias)
            }
        )
        if not aliases:
            raise ValueError(
                f"{proposal_id}: aliases must contain non-blank values."
            )

        confidence = raw.get("confidence")
        if not isinstance(confidence, (int, float)):
            raise ValueError(f"{proposal_id}: confidence must be numeric.")
        confidence = float(confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                f"{proposal_id}: confidence must be between 0 and 1."
            )

        sources = raw.get("sources")
        if not isinstance(sources, list):
            raise ValueError(f"{proposal_id}: sources must be a list.")
        cleaned_sources: list[dict[str, str]] = []
        for source in sources:
            if not isinstance(source, dict):
                raise ValueError(
                    f"{proposal_id}: every source must be an object."
                )
            title = _clean(source.get("title"))
            url = _clean(source.get("url"))
            publisher = _clean(source.get("publisher"))
            if not title or not re.match(r"^https?://", url):
                raise ValueError(
                    f"{proposal_id}: sources require title and http(s) URL."
                )
            cleaned_sources.append(
                {
                    "title": title,
                    "url": url,
                    "publisher": publisher,
                }
            )

        if classification == "safe_mapping_candidate":
            if proposed_capability_id not in taxonomy_ids:
                raise ValueError(
                    f"{proposal_id}: safe mapping target must be a current capability."
                )
            if relationship_type != "maps_to_capability":
                raise ValueError(
                    f"{proposal_id}: safe mapping requires maps_to_capability."
                )
            if not cleaned_sources:
                raise ValueError(
                    f"{proposal_id}: safe mapping requires at least one source."
                )
        elif classification == "new_capability_candidate":
            if proposed_capability_id is not None:
                raise ValueError(
                    f"{proposal_id}: new-capability proposal must not invent a current capability ID."
                )
            if not cleaned_sources:
                raise ValueError(
                    f"{proposal_id}: new capability proposal requires source evidence."
                )
        elif classification == "recognized_unmapped":
            proposed_capability_id = None
            relationship_type = None
        elif classification == "reject":
            proposed_capability_id = None
            relationship_type = None

        if not summary:
            raise ValueError(f"{proposal_id}: summary is required.")

        cleaned_proposals.append(
            {
                "proposal_id": proposal_id,
                "technology_id": technology_id,
                "label": label,
                "entry_kind": entry_kind,
                "aliases": aliases,
                "proposal_classification": classification,
                "proposed_capability_id": proposed_capability_id,
                "relationship_type": relationship_type,
                "confidence": round(confidence, 4),
                "summary": summary,
                "sources": cleaned_sources,
            }
        )

    return {
        "proposal_bundle_version": PROPOSAL_CONTRACT_VERSION,
        "taxonomy_version": taxonomy.version,
        "registry_version": registry.version,
        "research_method": _clean(bundle.get("research_method")),
        "proposals": cleaned_proposals,
    }


def build_research_handover(
    report: dict[str, Any],
) -> dict[str, Any]:
    taxonomy = get_default_taxonomy()
    registry = get_default_registry()

    taxonomy_catalog = [
        {
            "capability_id": str(row.get("capability_id") or ""),
            "label": str(row.get("label") or ""),
            "domain": str(row.get("domain") or ""),
        }
        for row in taxonomy.capabilities
    ]

    targets: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for candidate in report.get("candidates", []) or []:
        if not isinstance(candidate, dict):
            continue

        resolution = (
            candidate.get("technology_registry_resolution", {})
            or {}
        )
        registry_status = str(
            resolution.get("status") or "unresolved"
        )
        triage = candidate.get("triage", {}) or {}

        observed = candidate.get("observed_terms", []) or []
        text = _clean(
            observed[0]
            if observed
            else candidate.get("normalised_observed_text")
        )

        if registry_status == "resolved":
            continue

        if registry_status == "recognized_unmapped":
            key = (
                "technology",
                str(resolution.get("technology_id") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            targets.append(
                {
                    "target_type": "recognized_unmapped_technology",
                    "candidate_id": candidate.get("candidate_id"),
                    "technology_id": resolution.get("technology_id"),
                    "technology_label": resolution.get(
                        "technology_label"
                    ),
                    "requirement_text": text,
                    "current_review_status": triage.get("status"),
                    "requested_research": (
                        "Determine whether this technology can be safely "
                        "mapped to an existing canonical capability. If not, "
                        "classify it as recognized_unmapped or a genuine "
                        "new_capability_candidate."
                    ),
                }
            )
            continue

        if re.match(
            r"^(?:experience|knowledge|familiarity|proficiency)\s+"
            r"(?:with|of|in)\s+",
            text,
            flags=re.I,
        ):
            key = ("requirement", text.lower())
            if key in seen:
                continue
            seen.add(key)
            targets.append(
                {
                    "target_type": "unresolved_technology_like_requirement",
                    "candidate_id": candidate.get("candidate_id"),
                    "technology_id": None,
                    "technology_label": None,
                    "requirement_text": text,
                    "current_review_status": triage.get("status"),
                    "requested_research": (
                        "Identify the technology/term, aliases, category, "
                        "and whether an existing canonical capability is a "
                        "safe deterministic mapping."
                    ),
                }
            )

    return {
        "handover_version": "technology-registry-research-handover-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "proposal_contract_version": PROPOSAL_CONTRACT_VERSION,
        "taxonomy_version": taxonomy.version,
        "registry_version": registry.version,
        "research_categories": list(RESEARCH_CATEGORIES),
        "instructions": [
            (
                "Research current, widely used technologies and the explicit "
                "targets below. Prefer primary vendor/project documentation "
                "and reputable technical sources."
            ),
            (
                "Do not map a technology to a capability merely because they "
                "often co-occur. Use safe_mapping_candidate only when the "
                "technology requirement itself is a sufficiently reliable "
                "deterministic signal for the target capability."
            ),
            (
                "Use new_capability_candidate when the current taxonomy has "
                "a real semantic gap. Do not invent a proposed_capability_id "
                "that does not already exist."
            ),
            (
                "Every safe_mapping_candidate and new_capability_candidate "
                "must include source URLs."
            ),
            (
                "Return JSON conforming to "
                "taxonomy/technology_registry_research_proposals.schema.json."
            ),
        ],
        "current_taxonomy_catalog": taxonomy_catalog,
        "current_registry": registry_rows(registry),
        "research_targets": targets,
    }


def build_registry_vnext_preview(
    proposals: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_registry = json.loads(
        Path(REGISTRY_PATH).read_text(encoding="utf-8")
    )
    entries = [
        dict(entry)
        for entry in raw_registry.get("entries", []) or []
    ]
    by_id = {
        str(entry.get("technology_id") or ""): entry
        for entry in entries
    }

    review_index = {
        (
            str(row.get("proposal_id") or ""),
            str(row.get("proposal_bundle_version") or ""),
        ): row
        for row in reviews
    }

    applied: list[str] = []
    skipped: list[dict[str, str]] = []

    for proposal in proposals:
        proposal_id = str(proposal.get("proposal_id") or "")
        proposal_version = str(
            proposal.get("proposal_bundle_version")
            or PROPOSAL_CONTRACT_VERSION
        )
        review = review_index.get(
            (proposal_id, proposal_version),
            {},
        )
        decision = str(review.get("decision") or "unreviewed")
        if decision != "approve_mapping":
            continue

        if (
            proposal.get("proposal_classification")
            != "safe_mapping_candidate"
        ):
            skipped.append(
                {
                    "proposal_id": proposal_id,
                    "reason": (
                        "approve_mapping is only valid for "
                        "safe_mapping_candidate"
                    ),
                }
            )
            continue

        capability_id = _clean(
            proposal.get("proposed_capability_id")
        )
        if capability_id not in get_default_taxonomy().by_id():
            skipped.append(
                {
                    "proposal_id": proposal_id,
                    "reason": "target capability no longer exists",
                }
            )
            continue

        technology_id = _clean(proposal.get("technology_id"))
        entry = by_id.get(technology_id)
        relationship = {
            "relationship_type": "maps_to_capability",
            "capability_id": capability_id,
            "status": "approved",
        }

        if entry is None:
            entry = {
                "technology_id": technology_id,
                "label": _clean(proposal.get("label")),
                "entry_kind": _clean(proposal.get("entry_kind")),
                "aliases": list(proposal.get("aliases", []) or []),
                "status": "approved",
                "capability_relationships": [relationship],
                "notes": (
                    "D2.7 preview generated from a human-approved "
                    f"research proposal {proposal_id}."
                ),
            }
            entries.append(entry)
            by_id[technology_id] = entry
        else:
            existing_approved = [
                row
                for row in entry.get(
                    "capability_relationships",
                    [],
                )
                if isinstance(row, dict)
                and row.get("relationship_type")
                == "maps_to_capability"
                and row.get("status") == "approved"
            ]
            if existing_approved:
                existing_target = str(
                    existing_approved[0].get("capability_id")
                    or ""
                )
                if existing_target != capability_id:
                    skipped.append(
                        {
                            "proposal_id": proposal_id,
                            "reason": (
                                "existing approved mapping conflicts "
                                f"with {capability_id}"
                            ),
                        }
                    )
                    continue
            else:
                entry.setdefault(
                    "capability_relationships",
                    [],
                ).append(relationship)

            entry["aliases"] = sorted(
                {
                    _clean(alias)
                    for alias in (
                        list(entry.get("aliases", []) or [])
                        + list(proposal.get("aliases", []) or [])
                    )
                    if _clean(alias)
                }
            )

        applied.append(proposal_id)

    preview = dict(raw_registry)
    preview["registry_version"] = (
        f"{raw_registry.get('registry_version')}-d27-preview"
    )
    preview["description"] = (
        str(raw_registry.get("description") or "")
        + " D2.7 preview only; not production until promoted by a code patch."
    ).strip()
    preview["entries"] = sorted(
        entries,
        key=lambda row: str(row.get("technology_id") or ""),
    )

    return {
        "preview_version": "technology-registry-vnext-preview-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "applied_proposal_ids": applied,
        "skipped": skipped,
        "registry_preview": preview,
    }
def build_proposal_decision_suggestion(
    proposal: dict[str, Any],
) -> dict[str, Any]:
    """Translate a validated research classification into an advisory decision."""
    classification = _clean(
        proposal.get("proposal_classification")
    )
    confidence_raw = proposal.get("confidence")
    confidence = (
        float(confidence_raw)
        if isinstance(confidence_raw, (int, float))
        else 0.0
    )
    sources = [
        row
        for row in proposal.get("sources", []) or []
        if isinstance(row, dict)
    ]
    target = _clean(proposal.get("proposed_capability_id")) or None

    result = {
        "proposal_id": _clean(proposal.get("proposal_id")),
        "suggested_decision": "unreviewed",
        "confidence": "low",
        "reasons": [],
        "advisory_only": True,
        "source": "deterministic_python",
    }

    if classification == "safe_mapping_candidate":
        if (
            target
            and proposal.get("relationship_type")
            == "maps_to_capability"
            and sources
            and confidence >= 0.95
        ):
            result.update(
                {
                    "suggested_decision": "approve_mapping",
                    "confidence": "high",
                    "reasons": [
                        "Research classified this as a safe mapping candidate.",
                        f"The proposed target is an existing capability: {target}.",
                        f"Research confidence is {confidence:.2f} and source evidence is present.",
                        "Human confirmation is still required before it affects a registry-vNext preview.",
                    ],
                }
            )
        else:
            result.update(
                {
                    "suggested_decision": "unreviewed",
                    "confidence": "low",
                    "reasons": [
                        "The safe-mapping proposal does not meet the deterministic high-confidence review threshold.",
                    ],
                }
            )
        return result

    if classification == "recognized_unmapped":
        result.update(
            {
                "suggested_decision": "keep_unmapped",
                "confidence": "high",
                "reasons": [
                    "Research recognizes the technology but intentionally found no safe canonical mapping.",
                    "Keeping it unmapped preserves the conservative deterministic boundary.",
                ],
            }
        )
        return result

    if classification == "new_capability_candidate":
        result.update(
            {
                "suggested_decision": "new_capability_needed",
                "confidence": "high" if sources else "medium",
                "reasons": [
                    "Research found a semantic gap rather than a safe existing-capability mapping.",
                    "This routes the item to capability-taxonomy design instead of forcing an unsafe technology mapping.",
                ],
            }
        )
        return result

    if classification == "reject":
        result.update(
            {
                "suggested_decision": "reject_proposal",
                "confidence": "high",
                "reasons": [
                    "Research classified this item as unsuitable for the technology registry.",
                ],
            }
        )
        return result

    return result


_PROPOSAL_AI_SYSTEM = """You are reviewing an already-researched technology-registry proposal.
Your output is advisory only and cannot mutate any registry.

Allowed decisions:
approve_mapping
keep_unmapped
new_capability_needed
reject_proposal
unreviewed

Respect these constraints:
- approve_mapping is allowed only when proposal_classification is safe_mapping_candidate,
  proposed_capability_id exists, relationship_type is maps_to_capability, and source evidence is present.
- recognized_unmapped should normally remain keep_unmapped unless the supplied evidence clearly contradicts the research classification.
- new_capability_candidate should normally route to new_capability_needed, not invent a capability ID.
- reject proposals should not be turned into mappings without compelling supplied evidence.
- Do not browse the web. Review only the supplied proposal, current taxonomy catalogue,
  current registry, and deterministic suggestion.
Return one JSON object only with:
suggested_decision, confidence, reasons
"""


def ask_local_ai_proposal_review(
    proposal: dict[str, Any],
    *,
    model: str,
    deterministic_suggestion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Optional local-Ollama second opinion for a research proposal."""
    model = _clean(model)
    if not model.startswith("ollama/") or ":cloud" in model:
        raise ValueError(
            "Proposal AI review is restricted to a local Ollama model."
        )

    from llm import ask_json

    taxonomy = get_default_taxonomy()
    payload = {
        "proposal": proposal,
        "deterministic_suggestion": deterministic_suggestion,
        "current_taxonomy": [
            {
                "capability_id": _clean(row.get("capability_id")),
                "label": _clean(row.get("label")),
                "domain": _clean(row.get("domain")),
            }
            for row in taxonomy.capabilities
        ],
        "current_registry": registry_rows(),
    }

    raw = ask_json(
        _PROPOSAL_AI_SYSTEM,
        json.dumps(payload, ensure_ascii=False),
        model=model,
        route="analysis",
        max_tokens=700,
        temperature=0.0,
    )

    decision = _clean(raw.get("suggested_decision"))
    if decision not in PROPOSAL_REVIEW_DECISIONS:
        raise ValueError(
            f"Local AI returned unsupported proposal decision: {decision!r}"
        )

    classification = _clean(
        proposal.get("proposal_classification")
    )
    if decision == "approve_mapping":
        if (
            classification != "safe_mapping_candidate"
            or not _clean(proposal.get("proposed_capability_id"))
            or proposal.get("relationship_type")
            != "maps_to_capability"
            or not list(proposal.get("sources", []) or [])
        ):
            raise ValueError(
                "Local AI cannot approve a proposal that is not a validated safe mapping candidate."
            )

    confidence = raw.get("confidence")
    if isinstance(confidence, (int, float)):
        confidence_value: Any = round(
            max(0.0, min(1.0, float(confidence))),
            3,
        )
    else:
        confidence_value = _clean(confidence) or "unspecified"

    reasons = raw.get("reasons")
    if not isinstance(reasons, list):
        single = _clean(
            raw.get("reason") or raw.get("reasoning_summary")
        )
        reasons = [single] if single else []

    return {
        "proposal_id": _clean(proposal.get("proposal_id")),
        "suggested_decision": decision,
        "confidence": confidence_value,
        "reasons": [
            _clean(reason)
            for reason in reasons
            if _clean(reason)
        ][:6],
        "advisory_only": True,
        "source": "local_ollama",
        "model": model,
    }

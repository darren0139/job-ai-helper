from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable
from copy import deepcopy
from typing import Any

from taxonomy_discovery.tavily_research import (
    DEFAULT_MAX_RESULTS,
    TavilyResearchError,
    research_target_with_tavily,
)
from taxonomy_discovery.technology_registry import (
    TechnologyRegistry,
    get_default_registry,
    normalise,
)


BROAD_MINING_VERSION = "tqd3-broad-technology-mining-v1.1.0"
BROAD_MINING_SEED_VERSION = "software-technology-seeds-v1.0.0"
BROAD_MINING_QUESTION_VERSION = "tqd3-broad-mining-question-v1.0.1"
BROAD_MINING_QUERY_VERSION = "tqd3-broad-mining-query-v1.0.1"
MAX_MINING_BATCH_SEEDS = 4
MINING_TARGET_TYPE = "broad_technology_mining"

Transport = Callable[
    [str, dict[str, Any], dict[str, str], float],
    dict[str, Any],
]


_SEED_SPECS: tuple[dict[str, str], ...] = (
    {
        "seed_id": "programming_languages",
        "domain": "Programming languages",
        "scope": "General-purpose and widely used production programming languages.",
    },
    {
        "seed_id": "backend_runtimes_frameworks",
        "domain": "Backend runtimes & frameworks",
        "scope": "Server-side runtimes and frameworks used to build production services and APIs.",
    },
    {
        "seed_id": "frontend_frameworks",
        "domain": "Frontend frameworks",
        "scope": "Widely used web UI frameworks and frontend application platforms.",
    },
    {
        "seed_id": "relational_databases",
        "domain": "Relational databases",
        "scope": "Production relational database engines and managed relational database technologies.",
    },
    {
        "seed_id": "nosql_distributed_databases",
        "domain": "NoSQL & distributed databases",
        "scope": "Document, key-value, wide-column, graph, vector, and distributed database technologies.",
    },
    {
        "seed_id": "messaging_streaming",
        "domain": "Messaging & event streaming",
        "scope": "Message brokers, event streaming platforms, queues, and pub/sub technologies.",
    },
    {
        "seed_id": "cloud_platforms",
        "domain": "Cloud platforms & managed services",
        "scope": "Major cloud platforms and widely used managed application infrastructure services.",
    },
    {
        "seed_id": "containers_orchestration",
        "domain": "Containers & orchestration",
        "scope": "Container runtimes, orchestration platforms, and production container tooling.",
    },
    {
        "seed_id": "ci_cd_build",
        "domain": "CI/CD & build automation",
        "scope": "Continuous integration, delivery, deployment, and build automation technologies.",
    },
    {
        "seed_id": "observability_monitoring",
        "domain": "Observability & monitoring",
        "scope": "Metrics, logging, tracing, monitoring, and observability technologies.",
    },
    {
        "seed_id": "testing_qa",
        "domain": "Testing & QA tooling",
        "scope": "Automated testing, test runners, browser testing, API testing, and QA tooling.",
    },
    {
        "seed_id": "identity_auth",
        "domain": "Identity & authentication",
        "scope": "Authentication, authorization, identity providers, IAM, and federation technologies.",
    },
    {
        "seed_id": "data_engineering",
        "domain": "Data engineering & processing",
        "scope": "Batch/stream processing, orchestration, transformation, and data engineering platforms.",
    },
    {
        "seed_id": "ml_ai_tooling",
        "domain": "ML/AI engineering tooling",
        "scope": "Widely used machine-learning, model-serving, orchestration, and AI engineering technologies.",
    },
    {
        "seed_id": "infrastructure_as_code",
        "domain": "Infrastructure as code",
        "scope": "Infrastructure provisioning, configuration, and declarative environment management tooling.",
    },
    {
        "seed_id": "api_integration",
        "domain": "API & integration technologies",
        "scope": "API protocols, gateways, schemas, service integration, and interface technologies.",
    },
    {
        "seed_id": "security_tooling",
        "domain": "Security engineering tooling",
        "scope": "Application security, dependency scanning, secrets, policy, and security engineering technologies.",
    },
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _stable_seed_target_id(seed_id: str) -> str:
    digest = hashlib.sha256(
        f"{BROAD_MINING_SEED_VERSION}|{seed_id}".encode("utf-8")
    ).hexdigest()[:20]
    return f"tqdmin_{digest}"


_DISCOVERY_QUERY_TERMS = {
    "programming_languages": (
        "programming languages general purpose systems backend frontend"
    ),
    "backend_runtimes_frameworks": (
        "backend server runtimes web frameworks API frameworks"
    ),
    "frontend_frameworks": (
        "frontend web UI frameworks application frameworks"
    ),
    "relational_databases": (
        "relational database engines SQL databases managed relational"
    ),
    "nosql_distributed_databases": (
        "NoSQL document key-value wide-column graph vector databases"
    ),
    "messaging_streaming": (
        "message brokers event streaming platforms queues pub sub"
    ),
    "cloud_platforms": (
        "cloud platforms managed application infrastructure services"
    ),
    "containers_orchestration": (
        "container runtimes orchestration platforms container tooling"
    ),
    "ci_cd_build": (
        "CI CD continuous integration delivery build automation"
    ),
    "observability_monitoring": (
        "observability monitoring metrics logging tracing platforms"
    ),
    "testing_qa": (
        "automated testing browser testing API testing test runners"
    ),
    "identity_auth": (
        "identity authentication authorization IAM identity providers"
    ),
    "data_engineering": (
        "data engineering batch stream processing orchestration transformation"
    ),
    "ml_ai_tooling": (
        "machine learning AI engineering model serving orchestration tooling"
    ),
    "infrastructure_as_code": (
        "infrastructure as code provisioning configuration tools"
    ),
    "api_integration": (
        "API gateways protocols schemas integration technologies"
    ),
    "security_tooling": (
        "application security dependency scanning secrets policy tools"
    ),
}


def _research_question(domain: str, scope: str) -> str:
    return (
        f"Which concrete, named technologies are widely used in modern "
        f"software engineering for the domain '{domain}'? Scope: {scope} "
        "Return concrete project/product/technology names first. For each "
        "named technology, identify entity type, primary purpose, "
        "maintainer/vendor or standards body when applicable, authoritative "
        "supporting sources, and evidence of broad real-world production "
        "adoption. Prefer established technologies over niche or experimental "
        "projects. Use external facts only. Do not decide whether anything "
        "belongs in any internal taxonomy or technology registry."
    )


def _search_query(
    seed_id: str,
    domain: str,
    scope: str,
) -> str:
    terms = _clean(
        _DISCOVERY_QUERY_TERMS.get(seed_id)
        or f"{domain} {scope}"
    )
    return (
        f"{terms} widely used production technologies products projects "
        "comparison landscape"
    )


def build_broad_mining_queue() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in _SEED_SPECS:
        seed_id = _clean(spec["seed_id"])
        domain = _clean(spec["domain"])
        scope = _clean(spec["scope"])
        rows.append(
            {
                "broad_mining_version": BROAD_MINING_VERSION,
                "seed_version": BROAD_MINING_SEED_VERSION,
                "seed_id": seed_id,
                "target_id": _stable_seed_target_id(seed_id),
                "target_type": MINING_TARGET_TYPE,
                "target_key": seed_id,
                "label": domain,
                "domain": domain,
                "scope": scope,
                "research_question": _research_question(domain, scope),
                "research_question_version": BROAD_MINING_QUESTION_VERSION,
                "search_query": _search_query(seed_id, domain, scope),
                "research_query_version": BROAD_MINING_QUERY_VERSION,
                "research_profile": "broad_technology_ecosystem_external_facts",
                "requested_facts": [
                    "canonical_name",
                    "entity_type",
                    "primary_purpose",
                    "maintainer_vendor_or_standards_body",
                    "authoritative_sources",
                    "adoption_evidence",
                ],
                "tavily_eligible": True,
                "requires_human_review": True,
                "mutates_taxonomy": False,
                "mutates_registry": False,
                "influences_scoring": False,
                "automatic_promotion": False,
            }
        )
    return rows


def _selected_seed_rows(
    seeds: Iterable[dict[str, Any]],
    selected_seed_ids: Iterable[str],
) -> list[dict[str, Any]]:
    rows = [
        row
        for row in seeds
        if isinstance(row, dict)
        and _clean(row.get("seed_id"))
    ]
    by_id = {
        _clean(row["seed_id"]): row
        for row in rows
    }

    selected: list[str] = []
    seen: set[str] = set()
    for raw in selected_seed_ids:
        seed_id = _clean(raw)
        if seed_id and seed_id not in seen:
            seen.add(seed_id)
            selected.append(seed_id)

    if not selected:
        raise ValueError("Select at least one broad-mining seed domain.")

    if len(selected) > MAX_MINING_BATCH_SEEDS:
        raise ValueError(
            "Broad-mining batch exceeds safety limit "
            f"{MAX_MINING_BATCH_SEEDS}."
        )

    missing = [
        seed_id
        for seed_id in selected
        if seed_id not in by_id
    ]
    if missing:
        raise ValueError(
            "Unknown broad-mining seed ID(s): "
            + ", ".join(sorted(missing))
        )

    return [deepcopy(by_id[seed_id]) for seed_id in selected]


def research_selected_mining_seeds_with_tavily(
    seeds: Iterable[dict[str, Any]],
    *,
    selected_seed_ids: Iterable[str],
    api_key: str | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout_seconds: float = 30.0,
    transport: Transport | None = None,
) -> list[dict[str, Any]]:
    selected = _selected_seed_rows(seeds, selected_seed_ids)

    results: list[dict[str, Any]] = []
    for seed in selected:
        result = research_target_with_tavily(
            seed,
            api_key=api_key,
            max_results=max_results,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )
        result["broad_mining_version"] = BROAD_MINING_VERSION
        result["seed_version"] = BROAD_MINING_SEED_VERSION
        result["seed_id"] = seed["seed_id"]
        result["domain"] = seed["domain"]
        result["scope"] = seed["scope"]
        result["mining_governance"] = {
            "seed_research_only": True,
            "candidate_extraction": False,
            "candidate_deduplication": False,
            "proposal_creation": False,
            "requires_human_review": True,
            "taxonomy_mutations": 0,
            "registry_mutations": 0,
            "scoring_influence": False,
            "automatic_promotion": False,
        }
        results.append(result)

    return results


def registry_mentions_for_result(
    result: dict[str, Any],
    *,
    registry: TechnologyRegistry | None = None,
) -> list[dict[str, Any]]:
    registry = registry or get_default_registry()

    chunks = [
        _clean(result.get("answer")),
    ]
    structured = result.get("structured_output")
    if isinstance(structured, dict):
        for technology in structured.get("technologies", []) or []:
            if isinstance(technology, dict):
                chunks.append(_clean(technology.get("canonical_name")))
                chunks.append(_clean(technology.get("entity_type")))
                chunks.append(_clean(technology.get("primary_purpose")))
    for source in result.get("sources", []) or []:
        if isinstance(source, dict):
            chunks.append(_clean(source.get("title")))
            chunks.append(_clean(source.get("content")))
    haystack = "\n".join(chunk for chunk in chunks if chunk).lower()

    matches: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for entry in registry.entries:
        technology_id = _clean(entry.get("technology_id"))
        if not technology_id or technology_id in seen_ids:
            continue

        aliases = [
            _clean(alias)
            for alias in entry.get("aliases", []) or []
            if _clean(alias)
        ]
        label = _clean(entry.get("label"))
        if label:
            aliases.append(label)

        matched_aliases: list[str] = []
        for alias in aliases:
            alias_lower = alias.lower()
            if not alias_lower:
                continue
            # Keep punctuation-bearing technology names (C#, .NET, Node.js)
            # intact while using conservative token boundaries where possible.
            pattern = (
                r"(?<![a-z0-9])"
                + re.escape(alias_lower)
                + r"(?![a-z0-9])"
            )
            if re.search(pattern, haystack):
                matched_aliases.append(alias)

        if matched_aliases:
            seen_ids.add(technology_id)
            matches.append(
                {
                    "technology_id": technology_id,
                    "label": label,
                    "entry_kind": _clean(entry.get("entry_kind")),
                    "matched_aliases": sorted(
                        set(matched_aliases),
                        key=lambda value: value.lower(),
                    ),
                }
            )

    return sorted(
        matches,
        key=lambda row: (
            str(row.get("label") or "").lower(),
            str(row.get("technology_id") or ""),
        ),
    )

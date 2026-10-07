"""Read-only whole-corpus taxonomy coverage and local-first gap planning.

The audit reuses the production requirement resolver.  Local proposals are
review artifacts only: temporary copied knowledge is used for impact previews,
and no taxonomy, registry, Job Match snapshot, score, review, or publication is
written here.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

from analysis_stability.stable_evidence_scoring import (
    IMPORTANCE_WEIGHTS,
    _best_resume_evidence,
    _deterministic_weak_evidence_is_sufficient,
    build_resume_evidence_index,
    requirement_is_score_eligible,
)
from job_discovery.matching import current_match_versions
from tailoring.capability_taxonomy import (
    CapabilityTaxonomy,
    TAXONOMY_PATH,
    _validate_capability,
    get_default_taxonomy,
    normalise as taxonomy_normalise,
    temporary_taxonomy_scope,
)
from tailoring.production_requirement_resolver import (
    resolve_requirement_with_production_knowledge,
)
from taxonomy_discovery.candidate_refinement import (
    concept_key,
    phrase_present,
    technology_entities,
    route_candidate,
)
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.regression_corpus import (
    CORPUS_VERSION,
    export_saved_corpus,
    replay_current_corpus,
)
from taxonomy_discovery.research_atomicity import candidate_atomicity
from taxonomy_discovery.taxonomy_evolution import overlap_check
from taxonomy_discovery.technology_registry import (
    REGISTRY_PATH,
    TechnologyRegistry,
    _validate_registry,
    get_default_registry,
    normalise,
    resolve_requirement_text,
    temporary_registry_scope,
)


CORPUS_GAP_RESOLUTION_VERSION = "tqd3-corpus-gap-resolution-v1"
LOCAL_PROPOSAL_VERSION = "tqd3-local-gap-proposal-v1"
BULK_BOOTSTRAP_VERSION = "tqd3-bulk-technology-bootstrap-v1"
BULK_TECHNOLOGY_SEED_PATH = (
    Path(__file__).resolve().parent / "seeds" / "tqd3_bulk_technology_seed_v1.json"
)
CAPABILITY_CLOSURE_VERSION = "tqd3-capability-closure-v1"
CAPABILITY_CLOSURE_PROFILE_PATH = (
    Path(__file__).resolve().parent / "seeds" / "tqd3_capability_closure_profiles_v1.json"
)
JOB_MATCH_HEALTH_REPORT_VERSION = "tqd3-job-match-health-v1"
TRUE_GAP_TRIAGE_VERSION = "tqd3-true-job-match-gap-triage-v1"
TARGETED_TAXONOMY_CLEANUP_VERSION = "tqd3-targeted-taxonomy-cleanup-v1"

TARGETED_TAXONOMY_DECISIONS = {
    "SQL": {
        "disposition": "B",
        "disposition_label": "new_bounded_capability_justified",
        "reason": "SQL query construction and optimization is distinct from database design, data processing, and database authorization.",
        "relationship_decision": "contextual_only_after_capability_approval",
        "relationship_reason": "A bare SQL identity does not prove query-writing behavior; an unconditional SQL relationship is not review-ready.",
    },
    "network access control": {
        "disposition": "B",
        "disposition_label": "new_bounded_capability_justified",
        "reason": "Network admission and device-access policy is a bounded behavior not represented by database access control, packet analysis, or DNS/DHCP.",
        "relationship_decision": "not_applicable_capability_phrase",
        "relationship_reason": "The corpus uses the capability phrase itself rather than a technology identity.",
    },
    "Ansible": {
        "disposition": "B",
        "disposition_label": "new_bounded_capability_justified",
        "reason": "Infrastructure and configuration automation is distinct from manual configuration and application delivery pipelines.",
        "relationship_decision": "contextual_only_after_capability_approval",
        "relationship_reason": "Ansible can support configuration or infrastructure automation, but a bare product mention does not prove either behavior.",
    },
    "HCL BigFix": {
        "disposition": "D",
        "disposition_label": "research_still_insufficient",
        "reason": "The cached BigFix result found endpoint-management evidence but the governed authority rules accepted no subject-specific first-party definition.",
        "relationship_decision": "research_blocked",
        "relationship_reason": "BigFix must not map to endpoint management until identity, authority, and the relationship pass governed review.",
        "research_plan": [
            "Confirm HCL/BigFix first-party domain ownership through the governed authority registry.",
            "Verify the canonical product identity and endpoint-management scope from accepted first-party material.",
            "Re-evaluate BigFix -> endpoint management only after the capability is approved.",
        ],
    },
    "distributed systems": {
        "disposition": "D",
        "disposition_label": "research_still_insufficient",
        "reason": "Cached sources are supporting material only and do not establish a governed authoritative definition and safe phrase boundary.",
        "relationship_decision": "not_applicable_capability_concept",
        "relationship_reason": "This is a capability-boundary question, not a technology mapping.",
        "research_plan": [
            "Obtain an accepted authoritative definition covering coordination, partial failure, consistency, resilience, and scale.",
            "Validate positive and negative phrase boundaries against the known compound Web-platforms collision.",
        ],
    },
}

ACTIVE_TAXONOMY_CAPABILITY_IDS = (
    "quality.qa_testing",
    "language.modern_cpp",
    "fullstack.integration",
    "collaboration.cross_functional",
    "embedded.firmware",
    "operations.configuration",
    "frontend.ui_development",
    "data.processing",
    "backend.api_development",
)

TRUE_GAP_CATEGORIES = {
    "A": "genuine_candidate_evidence_gap",
    "B": "transferable_evidence_may_exist_matcher_did_not_connect",
    "C": "semantic_eligibility_problem",
    "D": "certification_or_credential_requirement",
    "E": "application_process_or_admin_requirement",
    "F": "compound_requirement_needing_decomposition",
    "G": "taxonomy_or_evidence_boundary_problem",
    "H": "resolver_or_matcher_problem",
    "I": "manual_or_ambiguous",
}

TECHNOLOGY_CONCEPT_ALIASES = {
    "Python": ("Python",),
    "Java": ("Java",),
    "C#": ("C#", "C Sharp"),
    "JavaScript": ("JavaScript",),
    "TypeScript": ("TypeScript",),
    "SQL": ("SQL",),
    "MongoDB": ("MongoDB",),
    "Elasticsearch": ("Elasticsearch", "Elastic Search"),
    "Node.js": ("Node.js", "NodeJS", "Node JS"),
    "React": ("React", "React.js", "ReactJS"),
    ".NET": (".NET", "Dotnet", "Dot Net"),
    "AWS": ("AWS", "Amazon Web Services"),
    "Azure": ("Azure", "Microsoft Azure"),
    "GCP": ("GCP", "Google Cloud Platform"),
    "C++": ("C++", "C++ programming language"),
}

CAPABILITY_DRAFT_DISPOSITIONS = (
    *(
        {
            "capability_id": capability_id,
            "disposition": "drop_duplicate_technology_semantics",
            "reason": "Technology identity and same-technology evidence should not be duplicated as a capability.",
        }
        for capability_id in (
            "language.python_development",
            "language.java_development",
            "language.csharp_development",
            "language.javascript_development",
            "language.typescript_development",
        )
    ),
    *(
        {
            "capability_id": capability_id,
            "disposition": "retain_capability_candidate",
            "reason": "The draft describes bounded behavior with evidence boundaries beyond technology identity.",
        }
        for capability_id in (
            "database.sql_querying",
            "network.access_control",
            "devops.infrastructure_automation",
            "operations.endpoint_management",
        )
    ),
    {
        "capability_id": "database.mongodb_engineering",
        "technology": "MongoDB",
        "disposition": "contextual_relationship",
        "reason": "MongoDB identity alone does not establish design, operations, processing, or application-development behavior.",
    },
    {
        "capability_id": "runtime.nodejs_development",
        "technology": "Node.js",
        "disposition": "contextual_relationship",
        "reason": "Node.js identity alone does not establish backend, API, or full-stack delivery.",
    },
    {
        "capability_id": "systems.distributed_systems",
        "disposition": "research_only_blocked",
        "reason": "The concept is capability-shaped, but current phrase matching has a known compound-requirement collision.",
    },
)

OPERATIONAL_ROUTES = (
    "phrase_or_alias_gap",
    "technology_identity_missing",
    "technology_relationship_missing",
    "possible_new_capability",
    "needs_decomposition",
    "local_resolver_issue",
    "manual_review",
    "noise_or_non_capability",
)

_ROUTE_TO_RESEARCH = {
    "phrase_or_alias_gap": "existing_capability_resolver_issue",
    "local_resolver_issue": "existing_capability_resolver_issue",
    "technology_identity_missing": "technology_identity",
    "technology_relationship_missing": "technology_relationship",
    "possible_new_capability": "possible_new_capability",
    "needs_decomposition": "insufficient_signal",
    "manual_review": "insufficient_signal",
    "noise_or_non_capability": "administrative_or_non_capability",
}

# A bounded local identity vocabulary for the common technologies named in the
# milestone.  It establishes identity/aliases only.  No capability relationship
# is inferred from this table.
_COMMON_IDENTITIES = {
    "python": {"canonical_name": "Python", "aliases": ["Python"], "technology_kind": "language"},
    "sql": {"canonical_name": "SQL", "aliases": ["SQL"], "technology_kind": "language"},
    "java": {"canonical_name": "Java", "aliases": ["Java"], "technology_kind": "language"},
    "javascript": {"canonical_name": "JavaScript", "aliases": ["JavaScript"], "technology_kind": "language"},
    "postgresql": {"canonical_name": "PostgreSQL", "aliases": ["PostgreSQL", "Postgres"], "technology_kind": "product"},
    "aws": {"canonical_name": "Amazon Web Services", "aliases": ["AWS", "Amazon Web Services"], "technology_kind": "platform"},
    "amazon web services": {"canonical_name": "Amazon Web Services", "aliases": ["AWS", "Amazon Web Services"], "technology_kind": "platform"},
    "azure": {"canonical_name": "Microsoft Azure", "aliases": ["Azure", "Microsoft Azure"], "technology_kind": "platform"},
    "microsoft azure": {"canonical_name": "Microsoft Azure", "aliases": ["Azure", "Microsoft Azure"], "technology_kind": "platform"},
    "gcp": {"canonical_name": "Google Cloud Platform", "aliases": ["GCP", "Google Cloud Platform"], "technology_kind": "platform"},
    "google cloud platform": {"canonical_name": "Google Cloud Platform", "aliases": ["GCP", "Google Cloud Platform"], "technology_kind": "platform"},
}


def _resolution(requirement: dict[str, Any]) -> dict[str, Any]:
    resolved = resolve_requirement_with_production_knowledge(requirement)
    decision = resolved.get("decision") or {}
    registry = resolved.get("registry_resolution") or {}
    status = "resolved" if decision.get("capability_id") else registry.get("status", "unresolved")
    return {
        "status": status,
        "resolution_source": resolved.get("resolution_source"),
        "capability_id": decision.get("capability_id"),
        "technology_id": registry.get("technology_id"),
        "technology_label": registry.get("technology_label"),
        "registry_status": registry.get("status") or "not_checked",
        "registry_reason": registry.get("reason"),
        "taxonomy_diagnostics": {
            key: deepcopy(value)
            for key, value in (resolved.get("taxonomy_diagnostics") or {}).items()
            if key != "capability_record"
        },
    }


def _weight(row: dict[str, Any]) -> float:
    importance = str(row.get("importance") or "").lower()
    fraction = float(row.get("group_weight_fraction", 1.0) or 1.0)
    return IMPORTANCE_WEIGHTS.get(importance, 0.0) * fraction


def _coverage(rows: list[dict[str, Any]], accepted: set[str]) -> dict[str, Any]:
    selected = [row for row in rows if str(row.get("importance") or "").lower() in accepted]
    denominator = sum(_weight(row) for row in selected)
    numerator = sum(_weight(row) for row in selected if row["current_resolution"]["status"] == "resolved")
    return {
        "resolved_weight": round(numerator, 6),
        "total_weight": round(denominator, 6),
        "percent": round(100.0 * numerator / denominator, 2) if denominator else 0.0,
    }


def _percent(numerator: int | float, denominator: int | float) -> float:
    return round(100.0 * numerator / denominator, 2) if denominator else 0.0


def _route_requirement_keys(row: dict[str, Any]) -> set[tuple[Any, Any]]:
    return {
        (source.get("job_id"), source.get("requirement_id"))
        for source in row.get("provenance", [])
        if source.get("job_id") is not None and source.get("requirement_id")
    }


def _technology_concept_present(text: str, aliases: tuple[str, ...]) -> bool:
    return any(phrase_present(text, alias) for alias in aliases)


_ADMIN_PROCESS_PATTERN = re.compile(
    r"\b(?:apply now|apply online|submi(?:t|tting)(?: your| an| the)? "
    r"(?:application|resume|cv)|application process|shortlisted|shortlisting|"
    r"by applying|(?:applicants?|candidates?|you) (?:hereby )?consent|"
    r"citizenship|citizen|work authori[sz]ation|eligible to work|visa|"
    r"notice period|salary|shift availability|rotating shifts|working hours|"
    r"coding assessment|online assessment|take home (?:test|assessment)|"
    r"pre employment (?:test|assessment|screening)|interview process|"
    r"ea licen[cs]e number)\b",
    re.I,
)
_ADDRESS_PATTERN = re.compile(
    r"\b\d+\s+[\w ]{1,65}\b(?:road|street|avenue|drive|boulevard|lane)\b|"
    r"\bsingapore\s+\d{6}\b",
    re.I,
)
_CREDENTIAL_PATTERN = re.compile(
    r"\b(?:certifications?|certified|certificates?|credentials?|licen[cs]e[sd]?|"
    r"degree(?!\s+of\b)|bachelors?|master(?:'s|s)?|phd|doctorate|diploma|"
    r"academic qualifications?|educational background)\b",
    re.I,
)
_SEMANTIC_ELIGIBILITY_PATTERN = re.compile(
    r"\b(?:our company|our mission(?![- ]critical)|our vision|about us|join our|"
    r"leading provider|"
    r"our clients include|equal opportunity employer|job description only|"
    r"other duties as assigned|this role reports to|"
    r"you(?:'ll| will) be a key member|throughout .{0,80}you will gain|"
    r"at .{0,60}we recognize)\b",
    re.I,
)
_TECHNICAL_REQUIREMENT_PATTERN = re.compile(
    r"\b(?:software|systems?|technical|technologies|data|database|security|"
    r"cybersecurity|vapt|penetration|threat modell?ing|devsecops|network|cloud|"
    r"code|coding|programming|api|backend|frontend|architecture|algorithm|"
    r"automation|deployment|integration|infrastructure|platform|application|"
    r"debug|troubleshoot|testing|quality assurance|qa|observability|monitoring|"
    r"protocol|firmware|machine learning|artificial intelligence|kubernetes|"
    r"aws|azure|gcp|python|java|javascript|typescript|sql)\b",
    re.I,
)


def _attention_area(text: str) -> str | None:
    checks = (
        ("generic preferred certifications", r"\bpreferred\b.*\bcertif|\bcertif\w*\b.*\bpreferred\b"),
        ("coding assessment requirements", r"\b(?:coding|online|technical) assessment\b|\btake home (?:test|assessment)\b"),
        ("degree/background requirements", r"\b(?:degree|bachelor|master(?:'s|s)?|phd|academic|educational background|computer science background)\b"),
        ("certifications", r"\b(?:certifications?|certified|certificates?|credentials?|licen[cs]e[sd]?)\b"),
        ("Kubernetes", r"\bkubernetes\b"),
        ("AWS architecture/implementation", r"\b(?:aws|amazon web services)\b.*\b(?:architect|architecture|implement|implementation|deploy|deployment|build)\w*\b|\b(?:architect|architecture|implement|implementation|deploy|deployment|build)\w*\b.*\b(?:aws|amazon web services)\b"),
        ("QA/software testing", r"\b(?:quality assurance|software testing|test automation|qa)\b"),
        ("DevSecOps", r"\bdevsecops\b"),
        ("cybersecurity/VAPT/threat modelling", r"\b(?:cybersecurity|vapt|vulnerability assessment|penetration testing|threat modell?ing)\b"),
        ("generic software-development experience", r"\b(?:software development|software engineering)\b.*\bexperience\b|\bexperience\b.*\b(?:software development|software engineering)\b"),
    )
    for label, pattern in checks:
        if re.search(pattern, text, re.I):
            return label
    return None


def _evidence_absence_reason(diagnostic: dict[str, Any]) -> str:
    if not diagnostic.get("historical_evidence_available"):
        return "Frozen Profile & Evidence context is unavailable; the audit fails closed and does not infer candidate evidence."
    candidate = diagnostic.get("best_compatible_evidence")
    if not candidate:
        return "No compatible saved Profile & Evidence row had deterministic lexical overlap with this requirement."
    if diagnostic.get("passes_production_weak_fallback_minima"):
        return (
            "A compatible saved evidence row met the production weak-fallback overlap minima, "
            "but the saved final production result remained none; inspect the recorded matcher, "
            "resolution, and evidence-policy guards."
        )
    missed = diagnostic.get("missed_weak_fallback_minima") or []
    return (
        "The best compatible saved evidence row was not selected because it missed production "
        "weak-fallback minimum " + ", ".join(missed) + "."
    )


def _taxonomy_effect(row: dict[str, Any]) -> tuple[bool, str]:
    diagnostics = row.get("scorer_diagnostics") or {}
    if row.get("taxonomy_cap_status") == "applied":
        return True, "Production taxonomy capped or rejected the preliminary match."
    if diagnostics.get("capability_evidence_reselection"):
        return True, "Production taxonomy selected a stronger compatible evidence row."
    if diagnostics.get("capability_none_recovery"):
        return True, "Production taxonomy recovered a grounded match from a preliminary none result."
    if row["current_resolution"].get("status") == "resolved":
        return False, "A capability resolves now, but the saved row records no taxonomy match intervention."
    return False, "No production taxonomy effect is recorded for this saved match result."


def _true_gap_category(
    row: dict[str, Any],
    *,
    operational_route: str,
    operational_reason: str,
) -> tuple[str, str, str]:
    text = row["requirement_text"]
    evidence = row.get("evidence_diagnostic") or {}
    resolution = row["current_resolution"]

    if _ADMIN_PROCESS_PATTERN.search(text) or _ADDRESS_PATTERN.search(text):
        return "E", "The text expresses application, assessment, eligibility, scheduling, notice, or address semantics.", "jd_semantic_eligibility_admin_filter"
    if _CREDENTIAL_PATTERN.search(text):
        return "D", "The requirement asks for a degree, certification, licence, or other credential.", "credential_evidence_and_policy"
    if operational_route == "needs_decomposition":
        return "F", "The existing deterministic atomicity route requires child requirements before matching.", "requirement_decomposition"
    if _SEMANTIC_ELIGIBILITY_PATTERN.search(text) or (
        operational_route == "noise_or_non_capability"
        and "Employer/organisation/marketing narrative" in operational_reason
    ):
        return "C", "The text appears to be employer narrative or non-requirement prose that should likely not contribute to Job Match.", "jd_semantic_eligibility"
    if row.get("taxonomy_cap_status") == "applied":
        return "G", "The saved production result records an active taxonomy evidence cap or rejection.", "taxonomy_evidence_boundary"
    if evidence.get("passes_production_weak_fallback_minima"):
        if resolution.get("status") == "resolved":
            return "G", "Compatible evidence met lexical minima for an existing capability but no grounded match survived its evidence boundary.", "taxonomy_evidence_boundary"
        return "H", "Compatible evidence met production fallback minima but the final saved matcher result remained none.", "resolver_or_matcher"
    best = evidence.get("best_compatible_evidence") or {}
    if int(best.get("overlap_count") or 0) >= 2 and (
        float(best.get("score") or 0.0) >= 0.20
        or float(best.get("requirement_coverage") or 0.0) >= 0.15
    ):
        return "B", "A compatible saved evidence row has a multi-token near match, but it remains below production credit minima.", "deterministic_evidence_linker"
    if operational_route == "local_resolver_issue":
        return "H", "The existing deterministic queue already identifies a production resolver boundary for this requirement.", "resolver_or_matcher"
    if (
        resolution.get("status") == "resolved"
        or row["technology_identity_resolution"].get("status") in {"resolved", "recognized_unmapped"}
        or operational_route in {
            "technology_identity_missing", "technology_relationship_missing",
            "possible_new_capability", "phrase_or_alias_gap",
        }
        or _TECHNICAL_REQUIREMENT_PATTERN.search(text)
    ):
        return "A", "The requirement is technically or capability shaped and no compatible saved evidence row meets grounded-match minima.", "candidate_profile_evidence"
    return "I", "The saved data does not support a safe automatic distinction between a real evidence gap and semantic noise.", "human_review"


def _eligibility_review(row: dict[str, Any], *, operational_route: str) -> dict[str, str]:
    text = row["requirement_text"]
    if _ADMIN_PROCESS_PATTERN.search(text) or _ADDRESS_PATTERN.search(text):
        return {"status": "likely_should_not_score", "reason": "Application/process/admin semantics."}
    if _CREDENTIAL_PATTERN.search(text):
        return {"status": "credential_policy_review", "reason": "Credential requirements need an explicit evidence and eligibility policy."}
    if _SEMANTIC_ELIGIBILITY_PATTERN.search(text):
        return {"status": "likely_should_not_score", "reason": "Employer narrative or non-requirement semantics."}
    if operational_route == "needs_decomposition":
        return {"status": "decompose_before_scoring", "reason": "Compound parent should not compete with its atomic children."}
    return {"status": "no_issue_identified", "reason": "No deterministic eligibility concern identified by this audit."}


def _quality_fix_ranking(triage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    impact = {"H": 100, "B": 95, "C": 90, "E": 90, "F": 85, "G": 80, "D": 55, "A": 25, "I": 15}
    impact_label = {
        "H": "high · grounded false-negative investigation",
        "B": "high · saved evidence near-match investigation",
        "C": "high · denominator and semantic precision",
        "E": "high · remove process text from match semantics",
        "F": "high · prevent compound-parent distortion",
        "G": "medium-high · evidence boundary correctness",
        "D": "medium · credential evidence/policy clarity",
        "A": "candidate-specific · evidence must be added by a human",
        "I": "manual · ambiguity must be resolved first",
    }
    action = {
        "H": "Reproduce the saved false negative through the production resolver/matcher and add a bounded regression before changing any gate.",
        "B": "Review the saved near-match and its source guard; improve evidence linking only when the evidence independently proves the requirement.",
        "C": "Review the extraction/semantic-eligibility boundary and exclude non-requirement prose in a separately approved scoring change.",
        "D": "Define whether and how Profile & Evidence credentials should ground this requirement before changing eligibility or matching.",
        "E": "Exclude application and process text at semantic eligibility in a separately approved scoring change.",
        "F": "Use the existing deterministic decomposition contract and score only valid atomic children once.",
        "G": "Review the existing capability evidence boundary against the compatible saved row; preserve conservative caps unless the row proves the capability.",
        "A": "Add truthful candidate evidence through Profile & Evidence or retain the no-evidence result.",
        "I": "Resolve the requirement meaning manually before changing deterministic policy.",
    }
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in triage_rows:
        target = row.get("attention_area") or concept_key(row["requirement_text"])
        grouped[(row["category_code"], target)].append(row)
    ranked = []
    for (category, target), group in grouped.items():
        required_core_weight = sum(
            _weight(row) for row in group
            if str(row.get("importance") or "").lower() in {"deal_breaker", "required", "core"}
        )
        ranked.append({
            "fix_target": target,
            "category_code": category,
            "primary_reason": TRUE_GAP_CATEGORIES[category],
            "recommended_fix_layer": group[0]["recommended_fix_layer"],
            "expected_job_match_quality_impact": impact_label[category],
            "recommended_action": action[category],
            "requirement_count": len(group),
            "job_count": len({row["job_id"] for row in group}),
            "required_core_weight": round(required_core_weight, 6),
            "example_requirement": sorted({row["requirement_text"] for row in group}, key=str.casefold)[0],
            "quality_priority_score": impact[category] * 1_000 + required_core_weight * 10 + len(group),
            "taxonomy_coverage_used_for_ranking": False,
        })
    ranked.sort(key=lambda row: (
        -row["quality_priority_score"], -row["job_count"],
        -row["requirement_count"], row["fix_target"].casefold(),
    ))
    for rank, row in enumerate(ranked[:20], 1):
        row["rank"] = rank
    return ranked[:20]


def _true_job_match_gap_triage(
    rows: list[dict[str, Any]],
    *,
    queue: list[dict[str, Any]],
) -> dict[str, Any]:
    route_by_key: dict[tuple[Any, Any], tuple[str, str]] = {}
    for queue_row in queue:
        if queue_row.get("parent_candidate_id"):
            continue
        for key in _route_requirement_keys(queue_row):
            route_by_key[key] = (
                str(queue_row.get("operational_route") or ""),
                str(queue_row.get("blocker_reason") or ""),
            )

    triage_rows = []
    eligibility_rows = []
    for row in rows:
        route, route_reason = route_by_key.get((row["job_id"], row["requirement_id"]), ("", ""))
        eligibility = _eligibility_review(row, operational_route=route)
        if eligibility["status"] != "no_issue_identified":
            eligibility_rows.append({
                "job_id": row["job_id"],
                "requirement_id": row["requirement_id"],
                "requirement_text": row["requirement_text"],
                "importance": row["importance"],
                "current_score_eligible": row["score_eligible"],
                **eligibility,
            })
        if not row["score_eligible"] or row["has_grounded_evidence_reference"]:
            continue
        category, reason, fix_layer = _true_gap_category(
            row, operational_route=route, operational_reason=route_reason
        )
        taxonomy_affected, taxonomy_effect = _taxonomy_effect(row)
        triage_rows.append({
            "category_code": category,
            "primary_reason": TRUE_GAP_CATEGORIES[category],
            "classification_reason": reason,
            "recommended_fix_layer": fix_layer,
            "attention_area": _attention_area(row["requirement_text"]),
            "requirement_text": row["requirement_text"],
            "job_id": row["job_id"],
            "snapshot_id": row["snapshot_id"],
            "requirement_id": row["requirement_id"],
            "importance": row["importance"],
            "group_weight_fraction": row.get("group_weight_fraction", 1.0),
            "score_eligible": row["score_eligible"],
            "current_match_result": {
                "label": row["match_label"],
                "value": row["match_value"],
                "source": (row.get("scorer_diagnostics") or {}).get("match_source"),
                "selected_evidence_count": len(row["selected_evidence"]),
            },
            "candidate_evidence_considered": deepcopy(row.get("evidence_diagnostic") or {}),
            "why_evidence_was_rejected_or_absent": _evidence_absence_reason(row.get("evidence_diagnostic") or {}),
            "taxonomy_result": deepcopy(row["current_resolution"]),
            "taxonomy_affected_match": taxonomy_affected,
            "taxonomy_effect": taxonomy_effect,
            "operational_route": route or "not_in_taxonomy_gap_queue",
            "eligibility_review": eligibility,
        })

    counts = Counter(row["category_code"] for row in triage_rows)
    summary_counts = {
        "genuine_evidence_gaps": counts["A"],
        "likely_matcher_misses": counts["B"] + counts["H"],
        "likely_semantic_eligibility_issues": counts["C"],
        "certifications_or_credentials": counts["D"],
        "admin_or_process": counts["E"],
        "decomposition": counts["F"],
        "taxonomy_boundary": counts["G"],
        "manual_or_ambiguous": counts["I"],
    }
    attention_rows = [row for row in triage_rows if row["attention_area"]]
    attention_rows.sort(key=lambda row: (
        str(row["attention_area"]).casefold(), -_weight(row),
        str(row["job_id"]), str(row["requirement_id"]),
    ))
    eligibility_counts = Counter(row["status"] for row in eligibility_rows)
    return {
        "triage_version": TRUE_GAP_TRIAGE_VERSION,
        "category_definitions": deepcopy(TRUE_GAP_CATEGORIES),
        "true_no_evidence_requirement_count": len(triage_rows),
        "classification_counts": {code: counts[code] for code in TRUE_GAP_CATEGORIES},
        "summary_counts": summary_counts,
        "requirements": triage_rows,
        "attention_gap_diagnostics": attention_rows,
        "top_20_job_match_quality_fixes": _quality_fix_ranking(triage_rows),
        "score_eligibility_audit": {
            "all_currently_score_eligible": all(row["score_eligible"] for row in rows),
            "total_requirements": len(rows),
            "current_score_eligible": sum(row["score_eligible"] for row in rows),
            "potential_review_count": len(eligibility_rows),
            "review_status_counts": dict(sorted(eligibility_counts.items())),
            "requirements": eligibility_rows,
            "behavior_changed": False,
        },
        "read_only": True,
        "scoring_semantics_changed": False,
    }


def _job_match_health_report(
    rows: list[dict[str, Any]],
    *,
    meaningful_keys: set[tuple[Any, Any]],
    queue: list[dict[str, Any]],
) -> dict[str, Any]:
    """Describe saved scorer outcomes separately from current taxonomy knowledge."""
    route_by_key: dict[tuple[Any, Any], str] = {}
    for queue_row in queue:
        if queue_row.get("parent_candidate_id"):
            continue
        for key in _route_requirement_keys(queue_row):
            route_by_key[key] = str(queue_row.get("operational_route") or "")

    eligible = [row for row in rows if row["score_eligible"]]
    ineligible = [row for row in rows if not row["score_eligible"]]
    meaningful = [
        row for row in rows
        if (row["job_id"], row["requirement_id"]) in meaningful_keys
    ]
    positive = [row for row in eligible if row["positive_grounded_evidence_match"]]
    no_evidence = [row for row in eligible if not row["has_grounded_evidence_reference"]]
    no_positive_match = [row for row in eligible if not row["positive_grounded_evidence_match"]]
    taxonomy_resolved = [row for row in eligible if row["current_resolution"]["status"] == "resolved"]
    recognized_unmapped = [
        row for row in eligible
        if row["technology_identity_resolution"].get("status") == "recognized_unmapped"
        and row["current_resolution"]["status"] != "resolved"
    ]
    unresolved = [row for row in eligible if row["current_resolution"]["status"] != "resolved"]
    capped = [row for row in eligible if row["taxonomy_cap_status"] == "applied"]
    capped_rejected = [row for row in capped if not row["positive_grounded_evidence_match"]]
    capped_positive = [row for row in capped if row["positive_grounded_evidence_match"]]
    unresolved_positive = [
        row for row in positive if row["current_resolution"]["status"] != "resolved"
    ]

    cross_tab = {
        category: {"evidence_positive": 0, "evidence_negative": 0, "total": 0}
        for category in (
            "taxonomy_resolved",
            "technology_recognized_unmapped",
            "taxonomy_unresolved",
            "contextual_or_non_capability",
        )
    }
    for row in eligible:
        key = (row["job_id"], row["requirement_id"])
        route = route_by_key.get(key, "")
        if row["current_resolution"]["status"] == "resolved":
            category = "taxonomy_resolved"
        elif row["technology_identity_resolution"].get("status") == "recognized_unmapped":
            category = "technology_recognized_unmapped"
        elif route in {"needs_decomposition", "manual_review", "noise_or_non_capability"}:
            category = "contextual_or_non_capability"
        else:
            category = "taxonomy_unresolved"
        evidence_key = (
            "evidence_positive" if row["positive_grounded_evidence_match"]
            else "evidence_negative"
        )
        cross_tab[category][evidence_key] += 1
        cross_tab[category]["total"] += 1

    concept_rows = []
    for concept, aliases in TECHNOLOGY_CONCEPT_ALIASES.items():
        selected = [
            row for row in rows
            if _technology_concept_present(row["requirement_text"], aliases)
        ]
        concept_rows.append({
            "concept": concept,
            "corpus_rows": len(selected),
            "score_eligible_rows": sum(row["score_eligible"] for row in selected),
            "positive_evidence_matches": sum(
                row["positive_grounded_evidence_match"] for row in selected
            ),
            "taxonomy_resolved_rows": sum(
                row["current_resolution"]["status"] == "resolved" for row in selected
            ),
            "identity_recognized_rows": sum(
                row["technology_identity_resolution"].get("status")
                in {"resolved", "recognized_unmapped"}
                for row in selected
            ),
            "recognized_unmapped_rows": sum(
                row["technology_identity_resolution"].get("status") == "recognized_unmapped"
                for row in selected
            ),
            "taxonomy_capped_rows": sum(row["taxonomy_cap_status"] == "applied" for row in selected),
            "true_no_evidence_rows": sum(
                row["score_eligible"] and not row["has_grounded_evidence_reference"]
                for row in selected
            ),
        })

    evidence_gap_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in meaningful:
        if row["score_eligible"] and not row["has_grounded_evidence_reference"]:
            evidence_gap_groups[concept_key(row["requirement_text"])].append(row)
    evidence_gaps = []
    for concept, group in evidence_gap_groups.items():
        evidence_gaps.append({
            "concept": concept,
            "occurrence_count": len(group),
            "job_count": len({row["job_id"] for row in group}),
            "required_core_weight": round(sum(
                _weight(row) for row in group
                if str(row.get("importance") or "").lower()
                in {"deal_breaker", "required", "core"}
            ), 6),
            "taxonomy_resolved_rows": sum(
                row["current_resolution"]["status"] == "resolved" for row in group
            ),
            "recognized_unmapped_rows": sum(
                row["technology_identity_resolution"].get("status") == "recognized_unmapped"
                for row in group
            ),
            "taxonomy_unresolved_rows": sum(
                row["current_resolution"]["status"] != "resolved" for row in group
            ),
            "example_requirement": sorted(
                {row["requirement_text"] for row in group}, key=str.casefold
            )[0],
        })
    evidence_gaps.sort(key=lambda row: (
        -row["required_core_weight"], -row["job_count"],
        -row["occurrence_count"], row["concept"],
    ))

    return {
        "report_version": JOB_MATCH_HEALTH_REPORT_VERSION,
        "semantic_definitions": {
            "score_eligible": "Production semantic eligibility; independent of taxonomy resolution.",
            "positive_grounded_evidence_match": "Final deterministic direct, transferable, or weak match with selected evidence.",
            "taxonomy_resolved": "Current production taxonomy or approved registry relationship supplied a capability_id.",
            "technology_recognized_unmapped": "Current registry recognized the identity but has no approved capability relationship.",
            "taxonomy_capped": "The production taxonomy lowered or rejected a pre-taxonomy positive match.",
        },
        "job_match_health": {
            "total_requirements": len(rows),
            "meaningful_requirements": len(meaningful),
            "score_eligible_requirements": len(eligible),
            "score_ineligible_requirements": len(ineligible),
            "positive_grounded_evidence_matches": len(positive),
            "direct_evidence_matches": sum(row["match_label"] == "direct" for row in positive),
            "transferable_evidence_matches": sum(row["match_label"] == "transferable" for row in positive),
            "weak_evidence_matches": sum(row["match_label"] == "weak" for row in positive),
            "no_evidence_requirements": len(no_evidence),
            "no_positive_grounded_match_requirements": len(no_positive_match),
            "taxonomy_capped_or_rejected_pre_cap_positive_matches": len(capped),
            "taxonomy_capped_but_still_positive_matches": len(capped_positive),
            "taxonomy_rejected_pre_cap_positive_matches": len(capped_rejected),
            "taxonomy_unresolved_positive_evidence_matches": len(unresolved_positive),
            "evidence_match_percent": _percent(len(positive), len(eligible)),
        },
        "taxonomy_knowledge": {
            "taxonomy_resolved_requirements": len(taxonomy_resolved),
            "technology_recognized_unmapped_requirements": len(recognized_unmapped),
            "taxonomy_unresolved_requirements": len(unresolved),
            "taxonomy_resolution_percent_of_score_eligible": _percent(
                len(taxonomy_resolved), len(eligible)
            ),
            "taxonomy_resolution_percent_of_meaningful": _percent(
                sum(row["current_resolution"]["status"] == "resolved" for row in meaningful),
                len(meaningful),
            ),
        },
        "cross_tab": [
            {"knowledge_state": category, **counts}
            for category, counts in cross_tab.items()
        ],
        "technology_concept_audit": concept_rows,
        "top_20_true_evidence_gaps": evidence_gaps[:20],
        "read_only": True,
        "scoring_semantics_changed": False,
        "production_mutations": 0,
    }


def _taxonomy_maintenance_priorities(
    queue: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rank taxonomy work by semantic/evidence utility, not resolution volume."""
    by_key = {(row["job_id"], row["requirement_id"]): row for row in rows}
    route_value = {
        "local_resolver_issue": 55,
        "needs_decomposition": 50,
        "possible_new_capability": 25,
        "technology_relationship_missing": 20,
        "manual_review": 15,
        "technology_identity_missing": 5,
    }
    route_reason = {
        "local_resolver_issue": "correct a deterministic resolver boundary or false classification",
        "possible_new_capability": "evaluate a bounded capability and evidence boundary",
        "needs_decomposition": "prevent compound requirements from collapsing into one semantic claim",
        "technology_relationship_missing": "improve capability provenance after boundary review",
        "manual_review": "resolve semantic ambiguity before changing deterministic knowledge",
        "technology_identity_missing": "improve identity metadata without claiming scoring coverage",
    }
    priorities = []
    capped_by_capability: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["taxonomy_cap_status"] != "applied":
            continue
        capability_id = str(
            row["current_resolution"].get("capability_id")
            or "snapshot_capability_requires_current_review"
        )
        capped_by_capability[capability_id].append(row)
    for capability_id, affected in capped_by_capability.items():
        priorities.append({
            "candidate_id": "existing_capability:" + capability_id,
            "concept": capability_id,
            "operational_route": "existing_capability_evidence_boundary",
            "maintenance_priority_score": 100 + len(affected) * 10,
            "usefulness_reasons": [
                "production evidence shows this taxonomy boundary actively caps or rejects positive matches"
            ],
            "positive_evidence_rows": sum(
                row["positive_grounded_evidence_match"] for row in affected
            ),
            "true_no_evidence_rows": sum(
                not row["has_grounded_evidence_reference"] for row in affected
            ),
            "taxonomy_capped_rows": len(affected),
            "required_core_impact": round(sum(
                _weight(row) for row in affected
                if str(row.get("importance") or "").lower()
                in {"deal_breaker", "required", "core"}
            ), 6),
            "job_count": len({row["job_id"] for row in affected}),
            "occurrences": len(affected),
        })

    disposition_concepts = {
        "network access control": "retain_capability_candidate",
        "sql": "retain_capability_candidate",
        "ansible": "retain_capability_candidate",
        "bigfix": "retain_capability_candidate",
        "sccm": "retain_capability_candidate",
        "distributed systems": "research_only_blocked",
        "mongodb": "contextual_relationship",
        "node.js": "contextual_relationship",
        "python": "drop_duplicate_technology_semantics",
        "java": "drop_duplicate_technology_semantics",
        "c#": "drop_duplicate_technology_semantics",
        "javascript": "drop_duplicate_technology_semantics",
        "typescript": "drop_duplicate_technology_semantics",
    }
    for queue_row in queue:
        if queue_row.get("parent_candidate_id") or queue_row.get("operational_route") == "noise_or_non_capability":
            continue
        affected = [by_key[key] for key in _route_requirement_keys(queue_row) if key in by_key]
        capped = sum(row["taxonomy_cap_status"] == "applied" for row in affected)
        positive = sum(row["positive_grounded_evidence_match"] for row in affected)
        no_evidence = sum(
            row["score_eligible"] and not row["has_grounded_evidence_reference"]
            for row in affected
        )
        route = str(queue_row.get("operational_route") or "")
        normalized_concept = normalise(queue_row["concept"])
        disposition = disposition_concepts.get(normalized_concept)
        reasons = []
        if capped:
            reasons.append("existing taxonomy cap/rejection shows direct evidence-boundary value")
        reasons.append(route_reason.get(route, "improve deterministic explanation and provenance"))
        priority_score = route_value.get(route, 10) + capped * 100
        if disposition == "retain_capability_candidate":
            priority_score = max(priority_score, 70)
            reasons.append("validated as a bounded capability candidate")
        elif disposition == "research_only_blocked":
            priority_score = min(priority_score, 20)
            reasons.append("research-only and blocked from publication")
        elif disposition == "contextual_relationship":
            priority_score = min(priority_score, 20)
            reasons.append("identity requires contextual relationship review")
        elif disposition == "drop_duplicate_technology_semantics":
            priority_score = 0
            reasons.append("drop as duplicate technology semantics")
        priorities.append({
            "candidate_id": queue_row["candidate_id"],
            "concept": queue_row["concept"],
            "operational_route": route,
            "maintenance_priority_score": priority_score,
            "usefulness_reasons": reasons,
            "positive_evidence_rows": positive,
            "true_no_evidence_rows": no_evidence,
            "taxonomy_capped_rows": capped,
            "required_core_impact": queue_row["required_core_impact"],
            "job_count": queue_row["job_count"],
            "occurrences": queue_row["occurrences"],
        })
    priorities.sort(key=lambda row: (
        -row["maintenance_priority_score"], -row["taxonomy_capped_rows"],
        -row["required_core_impact"], -row["job_count"], row["concept"],
    ))
    return priorities[:20]


def _candidate_base(group: list[dict[str, Any]]) -> dict[str, Any]:
    examples = sorted({row["requirement_text"] for row in group})
    text = examples[0]
    versions = current_match_versions()
    provenance = [deepcopy(row["provenance"]) for row in group]
    jobs = {row["job_id"] for row in group}
    importance = Counter(str(row.get("importance") or "unknown") for row in group)
    overlap = overlap_check(text)
    entities = technology_entities(text, [])
    gap = {
        "provenance": provenance,
        "job_count": len(jobs),
        "occurrence_count": len(group),
    }
    research_route, reason = route_candidate(gap, text, overlap, entities)
    candidate = {
        "normalized_cluster": concept_key(text),
        "concept_key": concept_key(text),
        "examples": examples,
        "occurrence_count": len(group),
        "job_count": len(jobs),
        "importance_distribution": dict(sorted(importance.items())),
        "provenance": provenance,
        "technology_terms": sorted({row["term"] for row in entities["concrete_entities"]}),
        "technology_entity_diagnostics": entities,
        "overlap": overlap,
        "routing_reason": reason,
        "candidate_route": research_route,
        "source_gap_ids": sorted({"corpus_gap_" + row["requirement_id"] for row in group}),
        "observed_job_count": len(jobs),
        "observed_occurrence_count": len(group),
        "recurrence_priority": "repeated_cross_job" if len(jobs) > 1 else "single_job",
        "current_versions": versions,
        "observed_scoring_versions": sorted({str(row["provenance"]["observed_versions"].get("scoring_version") or "unknown") for row in group}),
        "observed_taxonomy_versions": sorted({str(row["provenance"]["observed_versions"].get("taxonomy_version") or "unknown") for row in group}),
        "observed_registry_versions": sorted({str(row["provenance"]["observed_versions"].get("technology_registry_version") or "unknown") for row in group}),
    }
    candidate["candidate_fingerprint"] = fingerprint(candidate)
    candidate["candidate_id"] = "tqd3taxgap_" + candidate["candidate_fingerprint"][:24]
    return candidate


def _operational_route(candidate: dict[str, Any]) -> tuple[str, str]:
    research_route = candidate["candidate_route"]
    atomicity = candidate_atomicity(candidate)
    if atomicity["atomicity_status"] == "compound_requires_decomposition" or len(_compound_entities(candidate)) > 1:
        return "needs_decomposition", "Multiple concrete technology entities require deterministic atomic children"
    if research_route in {"ambiguous_or_noise", "insufficient_signal"} and _local_identity(candidate["concept_key"]):
        return "technology_identity_missing", "Bounded common-technology identity is absent from production registry"
    if research_route in {"administrative_or_non_capability", "ambiguous_or_noise"}:
        return "noise_or_non_capability", candidate["routing_reason"]
    if research_route == "existing_capability_resolver_issue":
        high = candidate["overlap"].get("high_overlap_candidates") or []
        ids = {row.get("capability_id") for row in high if row.get("capability_id")}
        safe = len(ids) == 1 and all(not row.get("unmet_requirement_groups") for row in high)
        return ("phrase_or_alias_gap" if safe else "local_resolver_issue",
                "One native capability has bounded phrase evidence" if safe else candidate["routing_reason"])
    mapped = {
        "technology_identity": "technology_identity_missing",
        "technology_relationship": "technology_relationship_missing",
        "possible_new_capability": "possible_new_capability",
    }
    if research_route == "insufficient_signal":
        text = " ".join(candidate.get("examples") or [])
        technical = bool(
            candidate.get("technology_terms")
            or candidate.get("overlap", {}).get("semantic_resolver_evidence")
            or re.search(
                r"\b(?:software|systems?|technical|technologies|data|database|security|cybersecurity|network|"
                r"cloud|code|coding|programming|api|backend|frontend|architecture|algorithm|automation|"
                r"deployment|integration|infrastructure|platform|application|debug|troubleshoot|testing|"
                r"observability|monitoring|protocol|firmware|machine learning|artificial intelligence|ai|ml)\b",
                text,
                re.I,
            )
        )
        return ("manual_review", candidate["routing_reason"]) if technical else (
            "noise_or_non_capability", "No deterministic technical capability signal"
        )
    return mapped.get(research_route, "manual_review"), candidate["routing_reason"]


def _local_identity(subject: str) -> dict[str, Any] | None:
    key = normalise(subject)
    direct = _COMMON_IDENTITIES.get(key)
    if direct:
        return deepcopy(direct)
    for row in _COMMON_IDENTITIES.values():
        if key in {normalise(value) for value in row["aliases"]}:
            return deepcopy(row)
    return None


def _compound_entities(candidate: dict[str, Any]) -> list[str]:
    """Find only configured/registered identities in an obvious entity list.

    This supplements the historical H.1 research atomicity diagnostic without
    broadening it. In particular, SQL is useful in ``Python and SQL`` here but
    remains outside the generic research entity detector.
    """
    text = " ".join(candidate.get("examples") or [candidate.get("concept_key", "")])
    names = list(candidate_atomicity(candidate)["detected_entities"])
    identity_keys = {normalise(name) for name in names}
    for identity in _COMMON_IDENTITIES.values():
        canonical_key = normalise(identity["canonical_name"])
        if canonical_key in identity_keys:
            continue
        matched = next((alias for alias in identity["aliases"] if phrase_present(text, alias)), None)
        if matched:
            names.append(matched)
            identity_keys.add(canonical_key)
    return sorted(dict.fromkeys(names), key=normalise)


def _local_plan(candidate: dict[str, Any], route: str, *, seed: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = resolve_requirement_text(candidate["examples"][0])
    if route == "phrase_or_alias_gap":
        ids = sorted({row["capability_id"] for row in candidate["overlap"].get("high_overlap_candidates", [])
                      if row.get("capability_id") and not row.get("unmet_requirement_groups")})
        if len(ids) == 1 and len(candidate["concept_key"].split()) >= 2:
            return {"possible": True, "resolution_type": "add_capability_phrase", "local_safe": True,
                    "target_capability_id": ids[0], "proposed_phrase": candidate["concept_key"],
                    "reason": "One existing capability has bounded native phrase evidence"}
    if route == "technology_identity_missing":
        terms = candidate.get("technology_terms") or [candidate["concept_key"]]
        identity = deepcopy(seed) if seed else next((_local_identity(term) for term in terms if _local_identity(term)), None)
        if identity:
            return {"possible": True, "resolution_type": "add_technology_identity", "local_safe": True,
                    "identity": identity, "reason": "Bounded common-technology identity vocabulary or reviewed bulk seed"}
    if route == "technology_relationship_missing":
        hypotheses = list((seed or {}).get("relationship_hypotheses") or [])
        valid = [
            row for row in hypotheses
            if isinstance(row, dict)
            and row.get("capability_id") in get_default_taxonomy().by_id()
            and row.get("safe_for_local_review", True) is True
            and not row.get("conflicting_capabilities")
            and row.get("external_research_recommended", False) is not True
        ]
        if len(valid) == 1:
            return {"possible": True, "resolution_type": "add_technology_relationship", "local_safe": True,
                    "technology_id": registry.get("technology_id"), "relationship": deepcopy(valid[0]),
                    "reason": "One explicit reviewed seed relationship hypothesis; production knowledge remains unchanged"}
    if route == "needs_decomposition":
        children = _compound_entities(candidate)
        if len(children) > 1:
            source_text = " ".join(candidate.get("examples") or [])
            if re.search(r"\b(?:such as|including|for example|e\.g\.?|or equivalent)\b", source_text, re.I):
                return {"possible": False, "resolution_type": None, "local_safe": False,
                        "reason": "Open-ended example list cannot prove complete deterministic decomposition"}
            return {"possible": True, "resolution_type": "deterministic_decomposition", "local_safe": True,
                    "atomic_children": children, "reason": "Multiple concrete entity boundaries are already known"}
    if route == "noise_or_non_capability":
        if candidate.get("parent_candidate_id"):
            return {"possible": False, "resolution_type": None, "local_safe": False,
                    "reason": "Atomic-child noise cannot reclassify its parent requirement"}
        return {"possible": True, "resolution_type": "mark_noise_non_capability", "local_safe": True,
                "reason": candidate["routing_reason"]}
    return {"possible": False, "resolution_type": None, "local_safe": False,
            "reason": "External governed research or manual review is required"}


def _queue_row(candidate: dict[str, Any], route: str, reason: str, *, seed: dict[str, Any] | None = None) -> dict[str, Any]:
    local = _local_plan(candidate, route, seed=seed)
    first = candidate["examples"][0]
    registry = resolve_requirement_text(first)
    importance = candidate.get("importance_distribution") or {}
    required_core = int(importance.get("required", 0)) + int(importance.get("core", 0)) + int(importance.get("deal_breaker", 0))
    external = route in {"technology_identity_missing", "technology_relationship_missing", "possible_new_capability"} and not local["possible"]
    priority = required_core * 1_000_000 + candidate["job_count"] * 1_000 + candidate["occurrence_count"]
    return {
        "candidate_id": candidate["candidate_id"],
        "concept": candidate["concept_key"],
        "example_jd_text": first,
        "job_ids": sorted({row.get("job_id") for row in candidate["provenance"] if row.get("job_id") is not None}),
        "job_count": candidate["job_count"],
        "occurrences": candidate["occurrence_count"],
        "importance": deepcopy(importance),
        "required_core_impact": required_core,
        "current_taxonomy_result": deepcopy(candidate["overlap"]),
        "current_registry_result": registry,
        "recommended_resolution_type": local["resolution_type"] or route,
        "operational_route": route,
        "local_resolution_possible": bool(local["possible"]),
        "local_safe": bool(local["local_safe"]),
        "external_research_required": external,
        "blocker_reason": reason if not local["possible"] else local["reason"],
        "local_plan": local,
        "parent_candidate_id": candidate.get("parent_candidate_id"),
        "source": candidate.get("source", "jd_corpus"),
        "provenance": deepcopy(candidate["provenance"]),
        "priority_score": priority,
        "candidate": candidate,
    }


def _child_candidate(parent: dict[str, Any], name: str) -> dict[str, Any]:
    provenance = [{**deepcopy(row), "parent_candidate_id": parent["candidate_id"],
                   "parent_requirement_text": parent["examples"][0]} for row in parent["provenance"]]
    group = [{
        "requirement_text": name,
        "requirement_id": row.get("requirement_id"),
        "job_id": row.get("job_id"),
        "importance": next(iter(parent.get("importance_distribution") or {"required": 1})),
        "provenance": row,
    } for row in provenance]
    child = _candidate_base(group)
    child["parent_candidate_id"] = parent["candidate_id"]
    child["parent_text"] = parent["examples"][0]
    child["source"] = "deterministic_decomposition"
    child["candidate_fingerprint"] = fingerprint({k: v for k, v in child.items() if k not in {"candidate_id", "candidate_fingerprint"}})
    child["candidate_id"] = "tqd3taxgap_" + child["candidate_fingerprint"][:24]
    return child


def _set_operational_route(candidate: dict[str, Any], route: str, reason: str) -> None:
    candidate["operational_route"] = route
    candidate["operational_reason"] = reason
    candidate["candidate_fingerprint"] = fingerprint({
        key: value for key, value in candidate.items()
        if key not in {"candidate_id", "candidate_fingerprint"}
    })
    candidate["candidate_id"] = "tqd3taxgap_" + candidate["candidate_fingerprint"][:24]


def _merge_atomic_children(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one atomic child queue item per concept across all parents."""
    parents = [row for row in rows if not row.get("parent_candidate_id")]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("parent_candidate_id"):
            grouped[row["concept"]].append(row)
    merged = []
    for concept, group in sorted(grouped.items()):
        if len(group) == 1:
            only = group[0]
            only["parent_candidate_ids"] = [only["parent_candidate_id"]]
            merged.append(only)
            continue
        row = deepcopy(group[0])
        provenance_index = {}
        for item in group:
            for source in item["provenance"]:
                key = (source.get("job_id"), source.get("snapshot_id"), source.get("requirement_id"),
                       source.get("parent_candidate_id"))
                provenance_index[key] = deepcopy(source)
        provenance = [provenance_index[key] for key in sorted(provenance_index, key=lambda value: tuple(str(v) for v in value))]
        parent_ids = sorted({source.get("parent_candidate_id") for source in provenance if source.get("parent_candidate_id")})
        importance = Counter()
        for item in group:
            importance.update(item.get("importance") or {})
        candidate = row["candidate"]
        candidate.update(
            provenance=provenance,
            occurrence_count=len(provenance),
            observed_occurrence_count=len(provenance),
            job_count=len({source.get("job_id") for source in provenance if source.get("job_id") is not None}),
            observed_job_count=len({source.get("job_id") for source in provenance if source.get("job_id") is not None}),
            importance_distribution=dict(sorted(importance.items())),
            parent_candidate_id=parent_ids[0],
            parent_candidate_ids=parent_ids,
            source_gap_ids=sorted({gap_id for item in group for gap_id in item["candidate"].get("source_gap_ids", [])}),
        )
        _set_operational_route(candidate, row["operational_route"], candidate["operational_reason"])
        refreshed = _queue_row(candidate, row["operational_route"], candidate["operational_reason"])
        refreshed["parent_candidate_id"] = parent_ids[0]
        refreshed["parent_candidate_ids"] = parent_ids
        merged.append(refreshed)
    return parents + merged


def audit_corpus_resolution(
    *,
    corpus: dict[str, Any] | None = None,
    db_path=None,
    replay_current: bool = False,
) -> dict[str, Any]:
    """Audit every saved canonical requirement against current production knowledge."""
    frozen = deepcopy(corpus) if corpus is not None else export_saved_corpus(db_path=db_path)
    if frozen.get("corpus_version") != CORPUS_VERSION:
        raise ValueError("Unsupported frozen Job Match corpus")
    if replay_current:
        frozen = replay_current_corpus(frozen)
    rows: list[dict[str, Any]] = []
    unresolved_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in frozen.get("jobs", []):
        versions = deepcopy(job.get("versions") or {})
        stable = job.get("baseline_stable_analysis") or {}
        context = (job.get("frozen_inputs") or {}).get("context")
        historical_evidence_available = bool(
            isinstance(context, dict)
            and isinstance(context.get("resume_profile"), dict)
            and isinstance(context.get("raw_resume_text"), str)
        )
        evidence_index = (
            build_resume_evidence_index(
                context.get("resume_profile"), context.get("raw_resume_text", "")
            )
            if historical_evidence_available else []
        )
        acronym_map = deepcopy(
            (stable.get("canonicalisation_debug") or {}).get("acronym_map") or {}
        )
        for requirement in job.get("requirements", []):
            raw = next((row for row in stable.get("canonical_requirements", [])
                        if row.get("requirement_id") == requirement.get("requirement_id")), requirement)
            score_eligible = requirement_is_score_eligible(raw)
            text = str(requirement.get("requirement_text") or "").strip()
            if not text:
                continue
            current = _resolution({"text": text, "atomic_focus": text})
            identity_resolution = resolve_requirement_text(text)
            match_label = str(raw.get("match_label") or requirement.get("match_label") or "none").lower()
            selected_evidence = deepcopy(
                raw.get("evidence")
                if isinstance(raw.get("evidence"), list)
                else requirement.get("selected_evidence") or []
            )
            best_evidence, best_score, best_coverage, best_overlap = _best_resume_evidence(
                raw, "", evidence_index, acronym_map
            ) if historical_evidence_available else (None, 0.0, 0.0, 0)
            passes_weak_minima = bool(
                best_evidence
                and _deterministic_weak_evidence_is_sufficient(
                    score=best_score,
                    focus_coverage=best_coverage,
                    overlap_count=best_overlap,
                )
            )
            evidence_diagnostic = {
                "historical_evidence_available": historical_evidence_available,
                "saved_evidence_row_count": len(evidence_index),
                "best_compatible_evidence": ({
                    "evidence_id": best_evidence.get("evidence_id"),
                    "section": best_evidence.get("section"),
                    "source": best_evidence.get("source"),
                    "text": best_evidence.get("text"),
                    "score": round(best_score, 6),
                    "requirement_coverage": round(best_coverage, 6),
                    "overlap_count": best_overlap,
                } if best_evidence else None),
                "passes_production_weak_fallback_minima": passes_weak_minima,
                "missed_weak_fallback_minima": (
                    [] if passes_weak_minima or not best_evidence
                    else ["combined score, requirement-coverage, or overlap gate"]
                ),
                "diagnostic_only": True,
                "scoring_influence": False,
            }
            row = {
                "job_id": job.get("job_id"),
                "snapshot_id": job.get("snapshot_id"),
                "requirement_id": requirement.get("requirement_id"),
                "requirement_text": text,
                "importance": requirement.get("importance"),
                "group_weight_fraction": raw.get("group_weight_fraction", 1.0),
                "score_eligible": score_eligible,
                "match_label": match_label,
                "match_value": float(raw.get("match_value", requirement.get("match_value", 0.0)) or 0.0),
                "selected_evidence": selected_evidence,
                "has_grounded_evidence_reference": bool(selected_evidence),
                "positive_grounded_evidence_match": bool(
                    score_eligible and match_label in {"direct", "transferable", "weak"}
                    and selected_evidence
                ),
                "taxonomy_cap_status": str(raw.get("capability_taxonomy_cap_status") or "unavailable"),
                "evidence_diagnostic": evidence_diagnostic,
                "scorer_diagnostics": {
                    "match_source": raw.get("match_source"),
                    "match_similarity": raw.get("match_similarity"),
                    "match_coverage": raw.get("match_coverage"),
                    "match_overlap_count": raw.get("match_overlap_count"),
                    "matched_keyword": raw.get("matched_keyword"),
                    "capability_none_recovery": deepcopy(raw.get("capability_none_recovery")),
                    "capability_evidence_reselection": deepcopy(raw.get("capability_evidence_reselection")),
                    "capability_retrieval": deepcopy(raw.get("capability_retrieval")),
                },
                "current_resolution": current,
                "technology_identity_resolution": identity_resolution,
                "provenance": {
                    "job_id": job.get("job_id"), "snapshot_id": job.get("snapshot_id"),
                    "requirement_id": requirement.get("requirement_id"),
                    "job_content_hash": job.get("job_content_hash"), "observed_versions": versions,
                },
            }
            rows.append(row)
            if score_eligible and current["status"] != "resolved":
                unresolved_groups[concept_key(text)].append(row)

    candidates: list[dict[str, Any]] = []
    queue: list[dict[str, Any]] = []
    noise_requirement_ids: set[tuple[Any, Any]] = set()
    for key in sorted(unresolved_groups):
        candidate = _candidate_base(unresolved_groups[key])
        route, reason = _operational_route(candidate)
        _set_operational_route(candidate, route, reason)
        candidates.append(candidate)
        queue.append(_queue_row(candidate, route, reason))
        if route == "noise_or_non_capability":
            noise_requirement_ids.update((row["job_id"], row["requirement_id"]) for row in unresolved_groups[key])
        if route == "needs_decomposition":
            for child_name in _compound_entities(candidate):
                if _resolution({"text": child_name, "atomic_focus": child_name})["status"] == "resolved":
                    continue
                child = _child_candidate(candidate, child_name)
                child_route, child_reason = _operational_route(child)
                _set_operational_route(child, child_route, child_reason)
                candidates.append(child)
                queue.append(_queue_row(child, child_route, child_reason))

    queue = _merge_atomic_children(queue)
    candidates = [row["candidate"] for row in queue]

    meaningful = [
        row for row in rows
        if row["score_eligible"]
        and (row["job_id"], row["requirement_id"]) not in noise_requirement_ids
    ]
    resolved = [row for row in meaningful if row["current_resolution"]["status"] == "resolved"]
    unresolved = [row for row in meaningful if row["current_resolution"]["status"] != "resolved"]
    queue.sort(key=lambda row: (-row["required_core_impact"], -row["job_count"], -row["occurrences"], row["concept"], row["candidate_id"]))
    for index, row in enumerate(queue, 1):
        row["priority_rank"] = index
    route_counts = Counter(row["operational_route"] for row in queue if not row.get("parent_candidate_id"))
    local_count = sum(row["local_safe"] for row in queue if row["operational_route"] != "noise_or_non_capability")
    local_safe_count = sum(row["local_safe"] for row in queue)
    required_core_taxonomy_coverage = _coverage(meaningful, {"deal_breaker", "required", "core"})
    preferred_taxonomy_coverage = _coverage(meaningful, {"preferred"})
    overall_taxonomy_coverage = _coverage(meaningful, {"deal_breaker", "required", "core", "preferred"})
    summary = {
        "total_requirements": len(rows),
        "meaningful_technical_requirements": len(meaningful),
        "score_eligible_requirements": sum(row["score_eligible"] for row in rows),
        "score_ineligible_requirements": sum(not row["score_eligible"] for row in rows),
        "taxonomy_resolved_requirements": len(resolved),
        "taxonomy_unresolved_requirements": len(unresolved),
        "positive_grounded_evidence_matches": sum(
            row["positive_grounded_evidence_match"] for row in rows
        ),
        "no_evidence_requirements": sum(
            row["score_eligible"] and not row["has_grounded_evidence_reference"]
            for row in rows
        ),
        # Compatibility aliases retained for saved consumers. These count
        # taxonomy resolution and must not be presented as scoring coverage.
        "resolved_scorable_requirements": len(resolved),
        "unresolved_technical_requirements": len(unresolved),
        "taxonomy_resolution_required_core_weighted_coverage": required_core_taxonomy_coverage,
        "taxonomy_resolution_supporting_preferred_weighted_coverage": preferred_taxonomy_coverage,
        "taxonomy_resolution_overall_weighted_coverage": overall_taxonomy_coverage,
        "required_core_weighted_coverage": required_core_taxonomy_coverage,
        "supporting_preferred_weighted_coverage": preferred_taxonomy_coverage,
        "overall_weighted_coverage": overall_taxonomy_coverage,
        "locally_resolvable_count": local_count,
        "local_safe_proposal_count": local_safe_count,
        "technology_identity_missing_count": route_counts["technology_identity_missing"],
        "relationship_missing_count": route_counts["technology_relationship_missing"],
        "capability_candidate_count": route_counts["possible_new_capability"],
        "decomposition_count": route_counts["needs_decomposition"],
        "research_required_count": sum(row["external_research_required"] for row in queue if not row.get("parent_candidate_id")),
        "manual_noise_count": route_counts["manual_review"] + route_counts["noise_or_non_capability"],
        "manual_review_count": route_counts["manual_review"],
        "noise_count": route_counts["noise_or_non_capability"],
    }
    meaningful_keys = {
        (row["job_id"], row["requirement_id"]) for row in meaningful
    }
    health_report = _job_match_health_report(
        rows, meaningful_keys=meaningful_keys, queue=queue
    )
    gap_triage = _true_job_match_gap_triage(rows, queue=queue)
    maintenance_priorities = _taxonomy_maintenance_priorities(queue, rows)
    top = [{key: deepcopy(row[key]) for key in ("candidate_id", "concept", "operational_route", "required_core_impact", "job_count", "occurrences", "example_jd_text")}
           for row in queue if row["operational_route"] != "noise_or_non_capability"][:30]
    return {
        "audit_version": CORPUS_GAP_RESOLUTION_VERSION,
        "corpus_version": frozen["corpus_version"],
        "current_versions": current_match_versions(),
        "summary": summary,
        "route_counts": dict(sorted(route_counts.items())),
        "top_unresolved_concepts": top,
        "job_match_health": health_report["job_match_health"],
        "taxonomy_knowledge": health_report["taxonomy_knowledge"],
        "evidence_taxonomy_cross_tab": health_report["cross_tab"],
        "technology_concept_audit": health_report["technology_concept_audit"],
        "top_20_true_evidence_gaps": health_report["top_20_true_evidence_gaps"],
        "true_job_match_gap_triage": gap_triage,
        "top_20_job_match_quality_fixes": gap_triage["top_20_job_match_quality_fixes"],
        "top_20_taxonomy_maintenance_priorities": maintenance_priorities,
        "metric_definitions": health_report["semantic_definitions"],
        "capability_draft_dispositions": deepcopy(list(CAPABILITY_DRAFT_DISPOSITIONS)),
        "requirements": rows,
        "candidates": candidates,
        "queue": queue,
        "corpus": frozen,
        "current_replay": deepcopy(frozen.get("current_replay") or {
            "explicit": False,
            "read_only": True,
        }),
        "read_only": True,
        "network_calls": 0,
        "model_calls": 0,
        "production_mutations": 0,
        "scoring_semantics_changed": False,
    }


def import_bulk_seed(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    """Validate a proposed broad seed list and return queue-ready dry-run rows."""
    raw_entries = payload.get("entries") if isinstance(payload, dict) else payload
    if not isinstance(raw_entries, list):
        raise ValueError("Bulk seed must be a list or an object with entries")
    allowed_kinds = {"framework", "runtime", "platform", "product", "protocol", "tool", "language", "architecture_pattern"}
    taxonomy_ids = set(get_default_taxonomy().by_id())
    registry = get_default_registry()
    production_aliases = {
        normalise(alias): entry["technology_id"]
        for entry in registry.entries
        for alias in entry.get("aliases", [])
    }
    cleaned = []
    seen = set()
    seen_aliases: dict[str, str] = {}
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            raise ValueError("Every bulk seed entry must be an object")
        name = " ".join(str(raw.get("canonical_name") or "").split())
        aliases = sorted({name, *(" ".join(str(value).split()) for value in raw.get("aliases", []) if str(value).strip())})
        kind = str(raw.get("technology_kind") or "").strip()
        if not name or not aliases or kind not in allowed_kinds:
            raise ValueError(f"Bulk seed entry {index} requires canonical_name, aliases, and a valid technology_kind")
        key = normalise(name)
        if key in seen:
            raise ValueError(f"Duplicate bulk seed identity: {name}")
        seen.add(key)
        canonical_resolution = resolve_requirement_text(name, registry=registry)
        canonical_owner = canonical_resolution.get("technology_id")
        for alias in aliases:
            alias_key = normalise(alias)
            seed_owner = seen_aliases.get(alias_key)
            if seed_owner and seed_owner != key:
                raise ValueError(f"Bulk seed alias collision: {alias!r} belongs to {seed_owner!r} and {name!r}")
            seen_aliases[alias_key] = key
            production_owner = production_aliases.get(alias_key)
            if production_owner and production_owner != canonical_owner:
                raise ValueError(
                    f"Bulk seed alias collision: {alias!r} is already owned by production technology {production_owner!r}"
                )
        relationships = raw.get("relationship_hypotheses", [])
        if not isinstance(relationships, list) or any(not isinstance(row, dict) or not row.get("capability_id") for row in relationships):
            raise ValueError(f"{name}: relationship_hypotheses must be capability objects")
        clean_relationships = []
        for relationship in relationships:
            capability_id = str(relationship["capability_id"]).strip()
            if capability_id not in taxonomy_ids:
                raise ValueError(f"{name}: unknown capability_id {capability_id!r}")
            relationship_type = str(relationship.get("relationship_type") or "maps_to_capability")
            if relationship_type != "maps_to_capability":
                raise ValueError(f"{name}: unsupported relationship_type {relationship_type!r}")
            conflicts = sorted({str(value).strip() for value in relationship.get("conflicting_capabilities", []) if str(value).strip()})
            unknown_conflicts = [value for value in conflicts if value not in taxonomy_ids]
            if unknown_conflicts:
                raise ValueError(f"{name}: unknown conflicting capabilities {unknown_conflicts}")
            safe = bool(relationship.get("safe_for_local_review", True)) and not conflicts
            clean_relationships.append({
                "capability_id": capability_id,
                "relationship_type": relationship_type,
                "reason": " ".join(str(relationship.get("reason") or relationship.get("basis") or
                                            "Curated seed hypothesis for human review").split()),
                "taxonomy_boundary_checks": sorted({
                    " ".join(str(value).split())
                    for value in relationship.get("taxonomy_boundary_checks", [])
                    if str(value).strip()
                }),
                "conflicting_capabilities": conflicts,
                "safe_for_local_review": safe,
                "external_research_recommended": bool(
                    relationship.get("external_research_recommended", not safe)
                ),
            })
        confidence = float(raw.get("confidence", 1.0))
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"{name}: confidence must be between 0 and 1")
        review_status = str(raw.get("review_status") or "proposed")
        if review_status not in {"proposed", "needs_research", "manual_review", "rejected"}:
            raise ValueError(f"{name}: unsupported review_status {review_status!r}")
        gap_route = raw.get("gap_route")
        if gap_route not in {None, "possible_new_capability", "manual_review"}:
            raise ValueError(f"{name}: unsupported gap_route {gap_route!r}")
        seed_id = "tqd3seed_" + fingerprint({"canonical_name": name, "aliases": aliases})[:20]
        cleaned.append({
            "seed_id": seed_id,
            "canonical_name": name,
            "aliases": aliases,
            "technology_kind": kind,
            "category": str(raw.get("category") or "uncategorized").strip(),
            "relationship_hypotheses": clean_relationships,
            "source": "bulk_seed",
            "confidence": confidence,
            "review_status": review_status,
            "gap_route": gap_route,
        })
    return {
        "seed_version": "tqd3-bulk-technology-seed-v1",
        "entries": cleaned,
        "seed_technology_count": len(raw_entries),
        "unique_canonical_technologies": len(cleaned),
        "aliases_proposed": sum(len(entry["aliases"]) for entry in cleaned),
        "alias_collisions": [],
        "dry_run": True,
        "production_mutations": 0,
        "network_calls": 0,
        "model_calls": 0,
    }


def load_bulk_technology_seed(path: str | Path = BULK_TECHNOLOGY_SEED_PATH) -> dict[str, Any]:
    """Load and validate the bundled proposal seed without creating knowledge."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    report = import_bulk_seed(payload)
    report["seed_path"] = str(Path(path).resolve())
    return report


def build_gap_resolution_queue(audit: dict[str, Any], *, bulk_seed=None, broad_candidates=None) -> dict[str, Any]:
    if audit.get("audit_version") != CORPUS_GAP_RESOLUTION_VERSION:
        raise ValueError("Unsupported corpus gap audit")
    rows = deepcopy(audit["queue"])
    candidates = deepcopy(audit["candidates"])
    seed_report = import_bulk_seed(bulk_seed) if bulk_seed is not None else None
    if seed_report:
        for seed in seed_report["entries"]:
            registry = resolve_requirement_text(seed["canonical_name"])
            route = "technology_relationship_missing" if registry["status"] == "recognized_unmapped" else "technology_identity_missing"
            text = seed["canonical_name"]
            group = [{"requirement_text": text, "requirement_id": "bulk_seed:" + normalise(text), "job_id": None,
                      "importance": "preferred", "provenance": {"job_id": None, "snapshot_id": None,
                      "requirement_id": "bulk_seed:" + normalise(text), "job_content_hash": None,
                      "observed_versions": current_match_versions(), "source": "bulk_seed"}}]
            candidate = _candidate_base(group)
            candidate.update(source="bulk_seed", bulk_seed=deepcopy(seed), operational_route=route,
                             operational_reason="Proposed bulk seed requires governed review")
            candidate["candidate_fingerprint"] = fingerprint({k: v for k, v in candidate.items() if k not in {"candidate_id", "candidate_fingerprint"}})
            candidate["candidate_id"] = "tqd3taxgap_" + candidate["candidate_fingerprint"][:24]
            candidates.append(candidate)
            rows.append(_queue_row(candidate, route, candidate["operational_reason"], seed=seed))
    if broad_candidates is not None:
        from taxonomy_discovery.broad_mining_candidates import (
            BROAD_MINING_CANDIDATE_VERSION,
            STATUS_ALREADY_KNOWN,
        )
        if not isinstance(broad_candidates, list):
            raise ValueError("Broad Mining candidates must be a list")
        for broad in broad_candidates:
            if not isinstance(broad, dict) or broad.get("candidate_version") != BROAD_MINING_CANDIDATE_VERSION:
                raise ValueError("Unsupported Broad Mining candidate")
            if (broad.get("governance") or {}).get("untrusted_research") is not True:
                raise ValueError("Broad Mining provenance must remain untrusted research")
            name = str(broad.get("canonical_name") or "").strip()
            if not name:
                raise ValueError("Broad Mining candidate canonical_name required")
            registry = resolve_requirement_text(name)
            if broad.get("status") == STATUS_ALREADY_KNOWN and registry.get("status") == "recognized_unmapped":
                route = "technology_relationship_missing"
                research_route = "technology_relationship"
            elif broad.get("status") == STATUS_ALREADY_KNOWN and registry.get("status") == "resolved":
                continue
            else:
                route = "technology_identity_missing"
                research_route = "technology_identity"
            provenance = {"job_id": None, "snapshot_id": None,
                "requirement_id": "broad_mining:" + str(broad.get("candidate_id") or normalise(name)),
                "job_content_hash": None, "observed_versions": current_match_versions(),
                "source": "broad_mining", "provider_request_ids": deepcopy(broad.get("provider_request_ids") or []),
                "target_ids": deepcopy(broad.get("target_ids") or []), "seed_ids": deepcopy(broad.get("seed_ids") or [])}
            candidate = _candidate_base([{"requirement_text": name, "requirement_id": provenance["requirement_id"],
                "job_id": None, "importance": "preferred", "provenance": provenance}])
            candidate.update(source="broad_mining", broad_mining_candidate=deepcopy(broad),
                             candidate_route=research_route,
                             routing_reason="Structured Broad Mining identity enters existing governed route")
            _set_operational_route(candidate, route, "Untrusted Broad Mining evidence requires governed verification")
            candidates.append(candidate)
            row = _queue_row(candidate, route, candidate["operational_reason"])
            row["local_plan"] = {"possible": False, "resolution_type": None, "local_safe": False,
                                 "reason": "Untrusted Broad Mining evidence cannot create local knowledge"}
            row["local_resolution_possible"] = False
            row["local_safe"] = False
            row["external_research_required"] = True
            row["recommended_resolution_type"] = route
            row["blocker_reason"] = row["local_plan"]["reason"]
            rows.append(row)
    rows.sort(key=lambda row: (-row["priority_score"], row["concept"], row["candidate_id"]))
    for index, row in enumerate(rows, 1):
        row["priority_rank"] = index
    return {"audit_version": audit["audit_version"], "rows": rows, "candidates": candidates,
            "seed": seed_report, "queue_fingerprint": fingerprint([{k: v for k, v in row.items() if k != "candidate"} for row in rows]),
            "network_calls": 0, "model_calls": 0, "production_mutations": 0}


def create_local_proposals(queue: dict[str, Any], *, selected_candidate_ids: list[str], explicit_creation=False) -> dict[str, Any]:
    if explicit_creation is not True:
        raise ValueError("Explicit local proposal creation required")
    selected = list(dict.fromkeys(selected_candidate_ids))
    by_id = {row["candidate_id"]: row for row in queue.get("rows", [])}
    if not selected or any(candidate_id not in by_id for candidate_id in selected):
        raise ValueError("Select known queue candidates")
    proposals = []
    skipped = []
    for candidate_id in selected:
        row = by_id[candidate_id]
        plan = row["local_plan"]
        if not plan.get("local_safe"):
            skipped.append({"candidate_id": candidate_id, "reason": plan.get("reason")})
            continue
        proposal = {
            "proposal_version": LOCAL_PROPOSAL_VERSION,
            "candidate_id": candidate_id,
            "candidate_fingerprint": row["candidate"]["candidate_fingerprint"],
            "concept": row["concept"],
            "resolution_type": plan["resolution_type"],
            "proposed_change": deepcopy(plan),
            "affected_requirement_keys": sorted({(p.get("job_id"), p.get("requirement_id")) for p in row["provenance"]}),
            "affected_jobs": row["job_ids"],
            "source_provenance": deepcopy(row["provenance"]),
            "current_versions": current_match_versions(),
            "status": "draft",
            "requires_human_review": True,
            "requires_human_approval": True,
            "approval": False,
            "publication": False,
        }
        proposal["proposal_fingerprint"] = fingerprint(proposal)
        proposal["proposal_id"] = "tqd3local_" + proposal["proposal_fingerprint"][:24]
        proposals.append(proposal)
    return {"proposal_version": LOCAL_PROPOSAL_VERSION, "proposals": proposals, "skipped": skipped,
            "approval": False, "publication": False, "production_mutations": 0,
            "network_calls": 0, "model_calls": 0}


def build_native_regression_handoff(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    """Adapt compatible local identity drafts to the existing registry contract.

    Other local actions deliberately remain unsupported until an existing
    governed draft contract can represent them without weakening its evidence
    requirements.
    """
    from taxonomy_discovery.research_proposals import (
        PROPOSAL_CONTRACT_VERSION,
        validate_proposal_bundle,
    )
    taxonomy = get_default_taxonomy()
    registry = get_default_registry()
    items = []
    unsupported = []
    for proposal in proposals:
        if proposal.get("resolution_type") != "add_technology_identity":
            unsupported.append({"proposal_id": proposal.get("proposal_id"),
                                "reason": "existing_native_draft_contract_unavailable"})
            continue
        identity = proposal["proposed_change"]["identity"]
        technology_id = re.sub(r"[^a-z0-9]+", ".", normalise(identity["canonical_name"])).strip(".")
        native = {
            "proposal_id": proposal["proposal_id"],
            "technology_id": technology_id,
            "label": identity["canonical_name"],
            "entry_kind": identity["technology_kind"],
            "aliases": identity["aliases"],
            "proposal_classification": "recognized_unmapped",
            "proposed_capability_id": None,
            "relationship_type": None,
            "confidence": 1.0,
            "summary": "Local deterministic identity draft; no capability relationship is asserted.",
            "sources": [],
            "governed_research": {"local_proposal_id": proposal["proposal_id"],
                                  "source_provenance": deepcopy(proposal["source_provenance"])},
        }
        bundle = validate_proposal_bundle({
            "proposal_bundle_version": PROPOSAL_CONTRACT_VERSION,
            "taxonomy_version": taxonomy.version,
            "registry_version": registry.version,
            "research_method": CORPUS_GAP_RESOLUTION_VERSION,
            "proposals": [native],
        })
        draft = {"kind": "technology", "draft_id": proposal["proposal_id"], "status": "draft",
                 "requires_human_approval": True, "proposal_bundle": bundle,
                 "local_proposal_fingerprint": proposal["proposal_fingerprint"]}
        items.append({"result_id": proposal["proposal_id"], "draft": draft})
    return {"result_drafts": items, "unsupported": unsupported,
            "uses_existing_bulk_regression": True, "approval": False,
            "publication": False, "production_mutations": 0}


def _temporary_knowledge(proposals: list[dict[str, Any]]) -> tuple[CapabilityTaxonomy, TechnologyRegistry]:
    taxonomy = get_default_taxonomy()
    capabilities = deepcopy(list(taxonomy.capabilities))
    registry = get_default_registry()
    entries = deepcopy(list(registry.entries))
    by_technology = {row["technology_id"]: row for row in entries}
    # Identities/aliases are applied first so a separate relationship draft can
    # safely depend on a new identity without proposal ordering becoming a
    # hidden contract.
    for proposal in proposals:
        change = proposal["proposed_change"]
        kind = proposal["resolution_type"]
        if kind != "add_technology_identity":
            continue
        identity = change["identity"]
        technology_id = change.get("technology_id") or re.sub(
            r"[^a-z0-9]+", ".", normalise(identity["canonical_name"])
        ).strip(".")
        entry = by_technology.get(technology_id)
        if entry is None:
            entry = {"technology_id": technology_id, "label": identity["canonical_name"],
                     "entry_kind": identity["technology_kind"], "aliases": [], "status": "approved",
                     "capability_relationships": [], "notes": "Temporary local proposal preview"}
            entries.append(entry)
            by_technology[technology_id] = entry
        entry["aliases"] = sorted(set(entry.get("aliases", []) + identity["aliases"]))

    for proposal in proposals:
        change = proposal["proposed_change"]
        kind = proposal["resolution_type"]
        if kind == "add_capability_phrase":
            entry = next(row for row in capabilities if row["capability_id"] == change["target_capability_id"])
            phrases = entry["requirement"].setdefault("any_terms", [])
            if change["proposed_phrase"] not in phrases:
                phrases.append(change["proposed_phrase"])
        elif kind == "add_technology_relationship":
            technology_id = change.get("technology_id")
            entry = by_technology.get(technology_id)
            if entry is None:
                raise ValueError("Relationship proposal requires a production or selected draft technology identity")
            relationship = change["relationship"]
            approved = [row for row in entry.get("capability_relationships", [])
                        if row.get("status") == "approved" and row.get("relationship_type") == "maps_to_capability"]
            if approved and any(row.get("capability_id") != relationship["capability_id"] for row in approved):
                raise ValueError("Relationship proposal conflicts with production knowledge")
            if not approved:
                entry.setdefault("capability_relationships", []).append({"capability_id": relationship["capability_id"],
                    "relationship_type": "maps_to_capability", "status": "approved"})
    shadow_taxonomy = CapabilityTaxonomy(taxonomy.version + "+local-preview", tuple(capabilities))
    _validate_registry({"registry_version": registry.version + "+local-preview", "entries": entries})
    shadow_registry = TechnologyRegistry(registry.version + "+local-preview", tuple(entries))
    return shadow_taxonomy, shadow_registry


def preview_local_resolution(audit: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare current and temporary draft knowledge using the native resolver."""
    if audit.get("audit_version") != CORPUS_GAP_RESOLUTION_VERSION or not proposals:
        raise ValueError("Current audit and selected local proposals required")
    if any(proposal.get("proposal_version") != LOCAL_PROPOSAL_VERSION or proposal.get("status") != "draft"
           or proposal.get("requires_human_approval") is not True for proposal in proposals):
        raise ValueError("Governed local draft proposals required")
    shadow_taxonomy, shadow_registry = _temporary_knowledge(proposals)
    source_ids = {tuple(key): proposal["proposal_id"] for proposal in proposals for key in proposal["affected_requirement_keys"]}
    decomposition = {tuple(key): proposal for proposal in proposals if proposal["resolution_type"] == "deterministic_decomposition"
                     for key in proposal["affected_requirement_keys"]}
    noise = {tuple(key) for proposal in proposals if proposal["resolution_type"] == "mark_noise_non_capability"
             for key in proposal["affected_requirement_keys"]}
    output = []
    with ExitStack() as stack:
        stack.enter_context(temporary_taxonomy_scope(shadow_taxonomy))
        stack.enter_context(temporary_registry_scope(shadow_registry))
        for row in audit["requirements"]:
            key = (row["job_id"], row["requirement_id"])
            before = deepcopy(row["current_resolution"])
            after = _resolution({"text": row["requirement_text"], "atomic_focus": row["requirement_text"]})
            child_resolutions = []
            if key in decomposition:
                for child in decomposition[key]["proposed_change"]["atomic_children"]:
                    child_resolutions.append({"text": child, "resolution": _resolution({"text": child, "atomic_focus": child})})
                if child_resolutions and all(item["resolution"]["status"] == "resolved" for item in child_resolutions):
                    after = {"status": "resolved", "resolution_source": "deterministic_decomposition",
                             "capability_id": None, "technology_id": None, "technology_label": None,
                             "registry_status": "decomposed", "registry_reason": "all_atomic_children_resolved",
                             "taxonomy_diagnostics": {}}
            excluded = key in noise
            semantic_fields = (
                "status", "resolution_source", "capability_id", "technology_id",
                "technology_label", "registry_status", "registry_reason",
            )
            changed = any(before.get(field) != after.get(field) for field in semantic_fields) or excluded
            output.append({"job_id": row["job_id"], "snapshot_id": row["snapshot_id"],
                           "requirement_id": row["requirement_id"], "requirement_text": row["requirement_text"],
                           "importance": row["importance"], "before": before, "after": after,
                           "changed": changed, "would_resolve": before["status"] != "resolved" and after["status"] == "resolved",
                           "would_exclude_as_noise": excluded, "child_resolutions": child_resolutions,
                           "responsible_proposal_id": source_ids.get(key) if changed else None})
    before_meaningful = [row for row in audit["requirements"]
                         if not any(not q.get("parent_candidate_id") and q["operational_route"] == "noise_or_non_capability" and
                                    (row["job_id"], row["requirement_id"]) in {(p.get("job_id"), p.get("requirement_id")) for p in q["provenance"]}
                                    for q in audit["queue"])]
    after_meaningful = []
    by_key = {(row["job_id"], row["requirement_id"]): row for row in output}
    for row in before_meaningful:
        key = (row["job_id"], row["requirement_id"])
        if key in noise:
            continue
        copied = deepcopy(row)
        copied["current_resolution"] = by_key[key]["after"]
        after_meaningful.append(copied)
    before_cov = _coverage(before_meaningful, {"deal_breaker", "required", "core", "preferred"})
    after_cov = _coverage(after_meaningful, {"deal_breaker", "required", "core", "preferred"})
    before_required = _coverage(before_meaningful, {"deal_breaker", "required", "core"})
    after_required = _coverage(after_meaningful, {"deal_breaker", "required", "core"})
    changed = [row for row in output if row["changed"]]
    intended = {(key[0], key[1]) for proposal in proposals for key in proposal["affected_requirement_keys"]}
    conflicts = [{"job_id": row["job_id"], "requirement_id": row["requirement_id"], "reason": "changed_outside_source_provenance"}
                 for row in changed if (row["job_id"], row["requirement_id"]) not in intended]
    return {
        "preview_version": "tqd3-local-gap-impact-preview-v1",
        "requirements_evaluated": len(output),
        "unresolved_before": sum(row["before"]["status"] != "resolved" for row in output),
        "would_resolve_after": sum(row["would_resolve"] for row in output),
        "affected_requirement_ids": [row["requirement_id"] for row in changed],
        "affected_jobs": sorted({row["job_id"] for row in changed}),
        "potential_new_taxonomy_resolutions": sum(row["would_resolve"] for row in output),
        "potential_new_matches": sum(row["would_resolve"] for row in output),
        "unchanged_requirements": sum(not row["changed"] for row in output),
        "conflicts_ambiguity": conflicts,
        "rows": output,
        "taxonomy_resolution_before_percent": before_cov["percent"],
        "projected_taxonomy_resolution_after_percent": after_cov["percent"],
        "required_core_taxonomy_resolution_before_percent": before_required["percent"],
        "required_core_taxonomy_resolution_after_percent": after_required["percent"],
        # Compatibility aliases: these percentages describe taxonomy
        # resolution, not score eligibility or evidence-match coverage.
        "coverage_before_percent": before_cov["percent"],
        "projected_coverage_after_percent": after_cov["percent"],
        "required_core_coverage_before_percent": before_required["percent"],
        "required_core_coverage_after_percent": after_required["percent"],
        "scoring_influence": False,
        "score_changes_claimed": False,
        "review_only": True,
        "approval": False,
        "publication": False,
        "production_mutations": 0,
        "network_calls": 0,
        "model_calls": 0,
    }


def _technology_id_for(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", ".", normalise(name)).strip(".")


def _seed_requirement_matches(audit: dict[str, Any], aliases: list[str]) -> list[dict[str, Any]]:
    """Return traceable corpus mentions without treating tiny prose tokens as aliases."""
    matched = []
    for requirement in audit["requirements"]:
        text = requirement["requirement_text"]
        text_key = normalise(text)
        padded_text = f" {text_key} "
        for alias in aliases:
            alias_key = normalise(alias)
            if text_key == alias_key or (
                len(alias_key) >= 3
                and alias_key not in {"and", "the", "for", "with", "go"}
                and f" {alias_key} " in padded_text
            ):
                matched.append(requirement)
                break
    return matched


def _bootstrap_proposal(
    seed: dict[str, Any],
    *,
    resolution_type: str,
    proposed_change: dict[str, Any],
    matched: list[dict[str, Any]],
    dependency_ids: list[str] | None = None,
) -> dict[str, Any]:
    keys = sorted({(row.get("job_id"), row.get("requirement_id")) for row in matched})
    jobs = sorted({row.get("job_id") for row in matched if row.get("job_id") is not None})
    proposal = {
        "proposal_version": LOCAL_PROPOSAL_VERSION,
        "bootstrap_version": BULK_BOOTSTRAP_VERSION,
        "candidate_id": seed["seed_id"],
        "candidate_fingerprint": fingerprint(seed),
        "concept": normalise(seed["canonical_name"]),
        "technology": seed["canonical_name"],
        "resolution_type": resolution_type,
        "proposed_change": deepcopy(proposed_change),
        "affected_requirement_keys": keys,
        "corpus_requirements_affected": [
            {"job_id": row.get("job_id"), "requirement_id": row.get("requirement_id"),
             "requirement_text": row.get("requirement_text"), "importance": row.get("importance")}
            for row in matched
        ],
        "affected_jobs": jobs,
        "source_provenance": [{"source": "bulk_seed", "seed_id": seed["seed_id"]}],
        "depends_on_proposal_ids": sorted(set(dependency_ids or [])),
        "current_versions": current_match_versions(),
        "status": "draft",
        "requires_human_review": True,
        "requires_human_approval": True,
        "approval": False,
        "publication": False,
    }
    proposal["proposal_fingerprint"] = fingerprint(proposal)
    proposal["proposal_id"] = "tqd3bootstrap_" + proposal["proposal_fingerprint"][:24]
    return proposal


def plan_bulk_technology_bootstrap(
    audit: dict[str, Any],
    *,
    seed: dict[str, Any] | list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prepare route-aware identity and relationship drafts for human review.

    The seed stays proposal input. Existing production knowledge determines
    whether an identity, alias, or relationship action is still needed.
    """
    if audit.get("audit_version") != CORPUS_GAP_RESOLUTION_VERSION:
        raise ValueError("Current corpus gap audit required")
    seed_report = load_bulk_technology_seed() if seed is None else import_bulk_seed(seed)
    registry = get_default_registry()
    taxonomy = get_default_taxonomy()
    registry_by_id = registry.by_id()
    groups = {key: [] for key in (
        "A_identity_only_safe", "B_relationship_safe_for_review",
        "C_needs_external_research", "D_possible_new_capability",
        "E_ambiguous_manual", "F_rejected_noise_or_no_change",
    )}
    identity_proposals: dict[str, dict[str, Any]] = {}
    relationship_proposals: list[dict[str, Any]] = []
    seed_rows = []

    for entry in seed_report["entries"]:
        matched = _seed_requirement_matches(audit, entry["aliases"])
        resolutions = [resolve_requirement_text(alias, registry=registry) for alias in entry["aliases"]]
        owner_ids = sorted({row.get("technology_id") for row in resolutions if row.get("technology_id")})
        ambiguous = any(row.get("status") == "ambiguous" for row in resolutions) or len(owner_ids) > 1
        production_id = owner_ids[0] if len(owner_ids) == 1 else None
        production_entry = registry_by_id.get(production_id) if production_id else None
        proposed_id = production_id or _technology_id_for(entry["canonical_name"])
        production_alias_keys = {normalise(value) for value in (production_entry or {}).get("aliases", [])}
        missing_aliases = [alias for alias in entry["aliases"] if normalise(alias) not in production_alias_keys]
        approved = [
            row for row in (production_entry or {}).get("capability_relationships", [])
            if row.get("relationship_type") == "maps_to_capability" and row.get("status") == "approved"
        ]
        row_summary = {
            "seed_id": entry["seed_id"],
            "technology": entry["canonical_name"],
            "category": entry["category"],
            "technology_kind": entry["technology_kind"],
            "aliases": entry["aliases"],
            "confidence": entry["confidence"],
            "review_status": entry["review_status"],
            "production_technology_id": production_id,
            "production_status": resolutions[0].get("status") if resolutions else "unresolved",
            "corpus_requirements_affected": len(matched),
            "jobs_affected": sorted({item.get("job_id") for item in matched if item.get("job_id") is not None}),
        }
        seed_rows.append(row_summary)
        if ambiguous or entry["review_status"] == "manual_review":
            groups["E_ambiguous_manual"].append({**row_summary, "reason": "ambiguous_identity_or_manual_seed_review"})
            continue
        if entry["review_status"] == "rejected":
            groups["F_rejected_noise_or_no_change"].append({**row_summary, "reason": "seed_marked_rejected"})
            continue

        identity_proposal = None
        if production_entry is None or missing_aliases:
            identity = {
                "canonical_name": entry["canonical_name"],
                "aliases": entry["aliases"] if production_entry is None else missing_aliases,
                "technology_kind": entry["technology_kind"],
                "source": "bulk_seed",
                "confidence": entry["confidence"],
                "review_status": entry["review_status"],
            }
            identity_proposal = _bootstrap_proposal(
                entry,
                resolution_type="add_technology_identity",
                proposed_change={
                    "possible": True,
                    "resolution_type": "add_technology_identity",
                    "local_safe": True,
                    "technology_id": proposed_id,
                    "identity": identity,
                    "reason": "Curated identity or non-colliding alias proposal; no capability mapping asserted",
                },
                matched=matched,
            )
            identity_proposals[proposed_id] = identity_proposal
            groups["A_identity_only_safe"].append({**row_summary, "proposal": identity_proposal,
                                                     "reason": identity_proposal["proposed_change"]["reason"]})

        hypotheses = entry["relationship_hypotheses"]
        if len(hypotheses) > 1:
            groups["E_ambiguous_manual"].append({**row_summary, "reason": "conflicting_relationship_candidates",
                                                  "relationship_hypotheses": hypotheses})
            continue
        if hypotheses:
            hypothesis = hypotheses[0]
            if approved and approved[0].get("capability_id") == hypothesis["capability_id"]:
                groups["F_rejected_noise_or_no_change"].append({**row_summary, "reason": "relationship_already_approved"})
                continue
            if approved and approved[0].get("capability_id") != hypothesis["capability_id"]:
                groups["E_ambiguous_manual"].append({
                    **row_summary,
                    "reason": "proposal_conflicts_with_approved_relationship",
                    "approved_capability_id": approved[0].get("capability_id"),
                    "relationship_hypothesis": hypothesis,
                })
                continue
            if hypothesis["conflicting_capabilities"]:
                groups["E_ambiguous_manual"].append({**row_summary, "reason": "conflicting_relationship_candidates",
                                                      "relationship_hypothesis": hypothesis})
                continue
            if hypothesis["safe_for_local_review"] and entry["review_status"] == "proposed":
                dependency_ids = [identity_proposal["proposal_id"]] if identity_proposal else []
                relationship = _bootstrap_proposal(
                    entry,
                    resolution_type="add_technology_relationship",
                    proposed_change={
                        "possible": True,
                        "resolution_type": "add_technology_relationship",
                        "local_safe": True,
                        "technology_id": proposed_id,
                        "technology": entry["canonical_name"],
                        "relationship": deepcopy(hypothesis),
                        "taxonomy_boundary_checks": deepcopy(hypothesis["taxonomy_boundary_checks"]),
                        "conflicting_capabilities": [],
                        "corpus_requirements_affected": len(matched),
                        "jobs_affected": row_summary["jobs_affected"],
                        "safe_for_local_review": True,
                        "external_research_recommended": False,
                        "reason": hypothesis["reason"],
                    },
                    matched=matched,
                    dependency_ids=dependency_ids,
                )
                relationship_proposals.append(relationship)
                groups["B_relationship_safe_for_review"].append({**row_summary, "proposal": relationship,
                                                                  "relationship_hypothesis": hypothesis,
                                                                  "reason": hypothesis["reason"]})
            elif entry.get("gap_route") == "possible_new_capability":
                groups["D_possible_new_capability"].append({**row_summary, "reason": "taxonomy_boundary_missing",
                                                             "relationship_hypothesis": hypothesis})
            else:
                groups["C_needs_external_research"].append({**row_summary, "reason": "relationship_boundary_requires_governed_research",
                                                             "relationship_hypothesis": hypothesis})
        elif entry.get("gap_route") == "possible_new_capability":
            groups["D_possible_new_capability"].append({**row_summary, "reason": "no_safe_current_taxonomy_capability"})
        elif production_entry is not None and not approved and matched:
            groups["C_needs_external_research"].append({**row_summary, "reason": "existing_identity_has_no_safe_relationship"})
        elif identity_proposal is None:
            groups["F_rejected_noise_or_no_change"].append({**row_summary, "reason": "identity_already_known_no_change"})

    local_proposals = list(identity_proposals.values()) + relationship_proposals
    report = {
        "bootstrap_version": BULK_BOOTSTRAP_VERSION,
        "seed": seed_report,
        "seed_rows": seed_rows,
        "groups": groups,
        "group_counts": {key: len(value) for key, value in groups.items()},
        "identity_only_proposals": list(identity_proposals.values()),
        "safe_relationship_proposals": relationship_proposals,
        "local_proposals": local_proposals,
        "taxonomy_version": taxonomy.version,
        "registry_version": registry.version,
        "review_only": True,
        "approval": False,
        "publication": False,
        "production_mutations": 0,
        "scoring_semantics_changed": False,
        "network_calls": 0,
        "model_calls": 0,
    }
    report["plan_fingerprint"] = fingerprint({key: value for key, value in report.items() if key != "plan_fingerprint"})
    return report


def select_bulk_bootstrap_proposals(
    plan: dict[str, Any],
    *,
    selected_proposal_ids: list[str],
    explicit_creation: bool = False,
) -> dict[str, Any]:
    """Select review drafts from groups A/B and pull required identity dependencies."""
    if explicit_creation is not True:
        raise ValueError("Explicit bulk bootstrap proposal creation required")
    proposals = {row["proposal_id"]: row for row in plan.get("local_proposals", [])}
    selected = list(dict.fromkeys(selected_proposal_ids))
    if not selected or any(proposal_id not in proposals for proposal_id in selected):
        raise ValueError("Select known identity or safe relationship proposals")
    required = set(selected)
    for proposal_id in list(required):
        required.update(proposals[proposal_id].get("depends_on_proposal_ids", []))
    output = [proposals[proposal_id] for proposal_id in proposals if proposal_id in required]
    return {
        "bootstrap_version": BULK_BOOTSTRAP_VERSION,
        "proposals": output,
        "explicitly_selected_proposal_ids": selected,
        "dependency_proposal_ids": sorted(required - set(selected)),
        "approval": False,
        "publication": False,
        "production_mutations": 0,
        "network_calls": 0,
        "model_calls": 0,
    }


def _preview_or_baseline(audit: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any]:
    if proposals:
        return preview_local_resolution(audit, proposals)
    overall = audit["summary"]["overall_weighted_coverage"]["percent"]
    required = audit["summary"]["required_core_weighted_coverage"]["percent"]
    return {
        "requirements_evaluated": len(audit["requirements"]),
        "would_resolve_after": 0,
        "affected_jobs": [],
        "unchanged_requirements": len(audit["requirements"]),
        "conflicts_ambiguity": [],
        "rows": [],
        "taxonomy_resolution_before_percent": overall,
        "projected_taxonomy_resolution_after_percent": overall,
        "required_core_taxonomy_resolution_before_percent": required,
        "required_core_taxonomy_resolution_after_percent": required,
        "coverage_before_percent": overall,
        "projected_coverage_after_percent": overall,
        "required_core_coverage_before_percent": required,
        "required_core_coverage_after_percent": required,
    }


def preview_bulk_technology_bootstrap(audit: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Build a cumulative, read-only coverage curve through native overlays."""
    if plan.get("bootstrap_version") != BULK_BOOTSTRAP_VERSION:
        raise ValueError("Current bulk bootstrap plan required")
    identities = plan["identity_only_proposals"]
    relationships = plan["safe_relationship_proposals"]
    identity_preview = _preview_or_baseline(audit, identities)
    relationship_preview = _preview_or_baseline(audit, identities + relationships)

    queue = build_gap_resolution_queue(audit)
    decomposition_ids = [
        row["candidate_id"] for row in queue["rows"]
        if row["operational_route"] == "needs_decomposition"
        and not row.get("parent_candidate_id") and row["local_safe"]
    ]
    decompositions = []
    if decomposition_ids:
        decompositions = create_local_proposals(
            queue, selected_candidate_ids=decomposition_ids, explicit_creation=True
        )["proposals"]
    decomposition_preview = _preview_or_baseline(audit, identities + relationships + decompositions)

    changed_by_key = {
        (row["job_id"], row["requirement_id"]): row
        for row in relationship_preview["rows"] if row["would_resolve"]
    }
    top_changes = []
    for relationship in relationships:
        intended = {tuple(key) for key in relationship["affected_requirement_keys"]}
        changed = [row for key, row in changed_by_key.items() if key in intended]
        required_core = sum(
            1 for row in changed if str(row.get("importance") or "").lower() in {"deal_breaker", "required", "core"}
        )
        top_changes.append({
            "proposal_id": relationship["proposal_id"],
            "technology": relationship["technology"],
            "capability_id": relationship["proposed_change"]["relationship"]["capability_id"],
            "newly_taxonomy_resolved_requirements": len(changed),
            "newly_scorable_requirements": len(changed),
            "required_core_requirements": required_core,
            "affected_jobs": sorted({row["job_id"] for row in changed}),
            "conflicts_ambiguity": [
                conflict for conflict in relationship_preview["conflicts_ambiguity"]
                if (conflict["job_id"], conflict["requirement_id"]) in intended
            ],
        })
    decomposition_by_id = {proposal["proposal_id"]: proposal for proposal in decompositions}
    decomposition_changed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in decomposition_preview["rows"]:
        proposal_id = row.get("responsible_proposal_id")
        if row["would_resolve"] and proposal_id in decomposition_by_id:
            decomposition_changed[proposal_id].append(row)
    for proposal_id, changed in decomposition_changed.items():
        proposal = decomposition_by_id[proposal_id]
        top_changes.append({
            "proposal_id": proposal_id,
            "technology": proposal["concept"],
            "capability_id": "deterministic_atomic_children",
            "newly_taxonomy_resolved_requirements": len(changed),
            "newly_scorable_requirements": len(changed),
            "required_core_requirements": sum(
                1 for row in changed
                if str(row.get("importance") or "").lower() in {"deal_breaker", "required", "core"}
            ),
            "affected_jobs": sorted({row["job_id"] for row in changed}),
            "conflicts_ambiguity": [],
        })
    top_changes.sort(key=lambda row: (
        -row["required_core_requirements"], -row["newly_taxonomy_resolved_requirements"], row["technology"].casefold()
    ))
    conflicts = (
        identity_preview["conflicts_ambiguity"]
        + relationship_preview["conflicts_ambiguity"]
        + decomposition_preview["conflicts_ambiguity"]
    )
    return {
        "preview_version": "tqd3-bulk-technology-bootstrap-impact-v1",
        "coverage_curve": [
            {"stage": "current_production", "taxonomy_resolution_overall_percent": audit["summary"]["taxonomy_resolution_overall_weighted_coverage"]["percent"],
             "overall_percent": audit["summary"]["taxonomy_resolution_overall_weighted_coverage"]["percent"],
             "required_core_percent": audit["summary"]["required_core_weighted_coverage"]["percent"],
             "newly_taxonomy_resolved_requirements": 0, "newly_scorable_requirements": 0},
            {"stage": "identity_only_proposals", "taxonomy_resolution_overall_percent": identity_preview["projected_coverage_after_percent"],
             "overall_percent": identity_preview["projected_coverage_after_percent"],
             "required_core_percent": identity_preview["required_core_coverage_after_percent"],
             "newly_taxonomy_resolved_requirements": identity_preview["would_resolve_after"],
             "newly_scorable_requirements": identity_preview["would_resolve_after"]},
            {"stage": "safe_relationship_proposals", "taxonomy_resolution_overall_percent": relationship_preview["projected_coverage_after_percent"],
             "overall_percent": relationship_preview["projected_coverage_after_percent"],
             "required_core_percent": relationship_preview["required_core_coverage_after_percent"],
             "newly_taxonomy_resolved_requirements": relationship_preview["would_resolve_after"],
             "newly_scorable_requirements": relationship_preview["would_resolve_after"]},
            {"stage": "decomposition_resolutions", "taxonomy_resolution_overall_percent": decomposition_preview["projected_coverage_after_percent"],
             "overall_percent": decomposition_preview["projected_coverage_after_percent"],
             "required_core_percent": decomposition_preview["required_core_coverage_after_percent"],
             "newly_taxonomy_resolved_requirements": decomposition_preview["would_resolve_after"],
             "newly_scorable_requirements": decomposition_preview["would_resolve_after"]},
        ],
        "identity_only": identity_preview,
        "safe_relationships": relationship_preview,
        "decomposition": decomposition_preview,
        "research_required_remainder": plan["group_counts"]["C_needs_external_research"],
        "possible_new_capability_remainder": plan["group_counts"]["D_possible_new_capability"],
        "top_20_highest_impact_changes": top_changes[:20],
        "newly_taxonomy_resolved_requirements": decomposition_preview["would_resolve_after"],
        "newly_scorable_requirements": decomposition_preview["would_resolve_after"],
        "affected_jobs": decomposition_preview["affected_jobs"],
        "new_matches": decomposition_preview["potential_new_matches"],
        "unchanged_requirements": decomposition_preview["unchanged_requirements"],
        "conflicts_ambiguity": conflicts,
        "false_positive_diagnostics": {
            "changed_outside_declared_corpus_mentions": conflicts,
            "ambiguous_after_overlay": [
                row for row in relationship_preview["rows"] if row["after"].get("status") == "ambiguous"
            ],
        },
        "review_only": True,
        "approval": False,
        "publication": False,
        "production_mutations": 0,
        "scoring_influence": False,
        "score_changes_claimed": False,
        "network_calls": 0,
        "model_calls": 0,
    }


def load_capability_closure_profiles(
    path: str | Path = CAPABILITY_CLOSURE_PROFILE_PATH,
) -> dict[str, Any]:
    """Load bounded closure hypotheses and validate them against current taxonomy."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("profile_version") != "tqd3-capability-closure-profiles-v1":
        raise ValueError("Unsupported capability closure profile version")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        raise ValueError("Capability closure profiles must be a list")
    taxonomy = get_default_taxonomy()
    taxonomy_ids = set(taxonomy.by_id())
    domains = {row["domain"] for row in taxonomy.capabilities}
    known_new_ids = {
        row.get("new_capability", {}).get("capability_id")
        for row in profiles if isinstance(row.get("new_capability"), dict)
    }
    seen: set[str] = set()
    alias_owners: dict[str, str] = {}
    cleaned = []
    for raw in profiles:
        if not isinstance(raw, dict):
            raise ValueError("Every capability closure profile must be an object")
        canonical = " ".join(str(raw.get("canonical_concept") or "").split())
        key = normalise(canonical)
        if not key or key in seen:
            raise ValueError(f"Duplicate or blank capability closure concept: {canonical!r}")
        seen.add(key)
        aliases = sorted({canonical, *(" ".join(str(value).split()) for value in raw.get("aliases", []) if str(value).strip())})
        for alias in aliases:
            alias_key = normalise(alias)
            owner = alias_owners.get(alias_key)
            if owner and owner != key:
                raise ValueError(f"Capability closure alias collision: {alias!r}")
            alias_owners[alias_key] = key
        failure_type = raw.get("failure_type")
        if failure_type not in {"identity_only_missing", "relationship_missing", "capability_missing", "contextual_ambiguous"}:
            raise ValueError(f"{canonical}: invalid failure_type")
        closest = list(dict.fromkeys(raw.get("closest_capability_ids") or []))
        if any(capability_id not in taxonomy_ids for capability_id in closest):
            raise ValueError(f"{canonical}: unknown closest capability")
        new_capability = deepcopy(raw.get("new_capability"))
        reference = raw.get("new_capability_ref")
        if reference and reference not in known_new_ids:
            raise ValueError(f"{canonical}: unknown new capability reference {reference!r}")
        if new_capability:
            required = {"capability_id", "label", "domain", "definition", "requirement_terms",
                        "does_not_prove", "boundaries", "overlap_risks"}
            if not required.issubset(new_capability):
                raise ValueError(f"{canonical}: incomplete new capability hypothesis")
            if new_capability["capability_id"] in taxonomy_ids or new_capability["domain"] not in domains:
                raise ValueError(f"{canonical}: invalid new capability identity/domain")
            if any(value not in taxonomy_ids for value in new_capability["overlap_risks"]):
                raise ValueError(f"{canonical}: unknown overlap risk")
        safe_capability = raw.get("safe_existing_capability_id")
        if safe_capability and safe_capability not in taxonomy_ids:
            raise ValueError(f"{canonical}: unknown safe relationship capability")
        cleaned.append({
            **deepcopy(raw),
            "canonical_concept": canonical,
            "aliases": aliases,
            "closest_capability_ids": closest,
        })
    return {
        "profile_version": payload["profile_version"],
        "profiles": cleaned,
        "profile_count": len(cleaned),
        "network_calls": 0,
        "model_calls": 0,
        "production_mutations": 0,
    }


def _profile_index(profile_report: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    aliases = {}
    capabilities = {}
    for profile in profile_report["profiles"]:
        for alias in profile["aliases"]:
            aliases[normalise(alias)] = profile
            aliases[_closure_match_key(alias)] = profile
        if profile.get("new_capability"):
            capabilities[profile["new_capability"]["capability_id"]] = profile["new_capability"]
    return aliases, capabilities


def _closure_match_key(value: str) -> str:
    """Match atomicized punctuation variants without broad substring matching."""
    return " ".join(re.sub(r"[^a-z0-9+#]+", " ", normalise(value)).split())


def _closure_candidate(
    rows: list[dict[str, Any]],
    *,
    capability: dict[str, Any],
) -> dict[str, Any]:
    representative = deepcopy(rows[0]["candidate"])
    provenance_index = {}
    for row in rows:
        for source in row["provenance"]:
            key = (source.get("job_id"), source.get("snapshot_id"), source.get("requirement_id"),
                   source.get("parent_candidate_id"))
            provenance_index[key] = deepcopy(source)
    provenance = [provenance_index[key] for key in sorted(provenance_index, key=lambda value: tuple(str(v) for v in value))]
    examples = sorted({example for row in rows for example in row["candidate"].get("examples", [])})
    representative.update(
        normalized_cluster=normalise(capability["label"]),
        concept_key=normalise(capability["label"]),
        examples=examples,
        provenance=provenance,
        occurrence_count=len(provenance),
        observed_occurrence_count=len(provenance),
        job_count=len({source.get("job_id") for source in provenance if source.get("job_id") is not None}),
        observed_job_count=len({source.get("job_id") for source in provenance if source.get("job_id") is not None}),
        candidate_route="possible_new_capability",
        routing_reason="Current taxonomy cannot represent this recurring requirement without semantic distortion",
        overlap=overlap_check(" ".join(capability["requirement_terms"])),
        source_gap_ids=sorted({gap_id for row in rows for gap_id in row["candidate"].get("source_gap_ids", [])}),
        operational_route="possible_new_capability",
        operational_reason="Candidate enters existing governed capability research",
    )
    representative["candidate_fingerprint"] = fingerprint({
        key: value for key, value in representative.items()
        if key not in {"candidate_id", "candidate_fingerprint"}
    })
    representative["candidate_id"] = "tqd3taxgap_" + representative["candidate_fingerprint"][:24]
    return representative


def build_capability_closure_matrix(
    audit: dict[str, Any],
    *,
    top_n: int = 30,
    bootstrap_plan: dict[str, Any] | None = None,
    profile_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Explain identity, relationship, and capability state for priority gaps."""
    if audit.get("audit_version") != CORPUS_GAP_RESOLUTION_VERSION:
        raise ValueError("Current corpus gap audit required")
    if not 1 <= int(top_n) <= 100:
        raise ValueError("top_n must be between 1 and 100")
    profiles = profile_report or load_capability_closure_profiles()
    profile_aliases, capability_definitions = _profile_index(profiles)
    bootstrap = bootstrap_plan or plan_bulk_technology_bootstrap(audit)
    taxonomy = get_default_taxonomy()
    taxonomy_by_id = taxonomy.by_id()
    registry = get_default_registry()
    bootstrap_identity_by_name = {
        normalise(row["technology"]): row for row in bootstrap["identity_only_proposals"]
    }
    seed_by_alias = {}
    for seed in bootstrap["seed"]["entries"]:
        for alias in seed["aliases"]:
            seed_by_alias[normalise(alias)] = seed

    priority_rows = [
        row for row in audit["queue"]
        if row["operational_route"] != "noise_or_non_capability"
    ]
    selected = list(priority_rows[:int(top_n)])
    required_profile_names = {
        "python", "sql", "amazon web services", "microsoft azure", "javascript", "mongodb",
        "typescript", "c#", ".net", "elasticsearch", "google cloud platform", "java",
        "node.js", "ansible", "hcl bigfix", "distributed systems",
    }
    selected_ids = {row["candidate_id"] for row in selected}
    for row in priority_rows:
        profile = profile_aliases.get(normalise(row["concept"])) or profile_aliases.get(_closure_match_key(row["concept"]))
        if profile and normalise(profile["canonical_concept"]) in required_profile_names and row["candidate_id"] not in selected_ids:
            selected.append(row)
            selected_ids.add(row["candidate_id"])

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    group_profiles: dict[str, dict[str, Any] | None] = {}
    for row in selected:
        profile = profile_aliases.get(normalise(row["concept"])) or profile_aliases.get(_closure_match_key(row["concept"]))
        canonical = normalise(profile["canonical_concept"]) if profile else normalise(row["concept"])
        grouped[canonical].append(row)
        group_profiles[canonical] = profile

    matrix = []
    relationship_drafts = []
    capability_groups: dict[str, dict[str, Any]] = {}
    research_candidates = []
    for canonical, rows in grouped.items():
        profile = group_profiles[canonical]
        aliases = profile["aliases"] if profile else sorted({row["concept"] for row in rows})
        seed = next((seed_by_alias.get(normalise(alias)) for alias in aliases if seed_by_alias.get(normalise(alias))), None)
        resolver = resolve_requirement_text(rows[0]["example_jd_text"], registry=registry)
        closest_ids = list((profile or {}).get("closest_capability_ids") or [])
        if not closest_ids:
            closest_ids = [
                item["capability_id"] for item in rows[0]["current_taxonomy_result"].get("concept_overlap", [])
                if item.get("capability_id") in taxonomy_by_id
            ][:5]
        closest = [{
            "capability_id": capability_id,
            "label": taxonomy_by_id[capability_id]["label"],
            "domain": taxonomy_by_id[capability_id]["domain"],
            "definition": taxonomy_by_id[capability_id].get("definition"),
            "does_not_prove": deepcopy(taxonomy_by_id[capability_id].get("does_not_prove") or []),
        } for capability_id in closest_ids]
        failure_type = (profile or {}).get("failure_type")
        safe_capability = (profile or {}).get("safe_existing_capability_id")
        if not failure_type:
            if rows[0]["operational_route"] == "possible_new_capability":
                failure_type = "capability_missing"
            elif safe_capability and resolver.get("status") == "unresolved":
                failure_type = "identity_only_missing"
            elif safe_capability:
                failure_type = "relationship_missing"
            else:
                failure_type = "contextual_ambiguous"
        affected_keys = sorted({
            (source.get("job_id"), source.get("requirement_id"))
            for row in rows for source in row["provenance"]
        })
        jobs = sorted({job_id for job_id, _ in affected_keys if job_id is not None})
        required_core = sum(row["required_core_impact"] for row in rows)
        new_capability = deepcopy((profile or {}).get("new_capability"))
        if not new_capability and (profile or {}).get("new_capability_ref"):
            new_capability = deepcopy(capability_definitions[(profile or {})["new_capability_ref"]])
        identity_proposal = next((
            proposal for name, proposal in bootstrap_identity_by_name.items()
            if name == normalise((seed or {}).get("canonical_name") or (profile or {}).get("canonical_concept") or canonical)
        ), None)
        identity_state = (
            "production_resolved" if resolver.get("status") == "resolved" else
            "production_recognized_unmapped" if resolver.get("status") == "recognized_unmapped" else
            "proposal_ready" if identity_proposal else
            "research_required"
        )
        relationship_state = (
            "production_approved" if resolver.get("status") == "resolved" else
            "safe_draft_ready" if safe_capability else
            "missing_requires_capability" if failure_type == "capability_missing" else
            "contextual" if failure_type == "contextual_ambiguous" else
            "research_required"
        )
        capability_state = (
            "current_capability_fits" if safe_capability else
            "possible_new_capability" if failure_type == "capability_missing" else
            "contextual_no_universal_capability"
        )
        matrix_row = {
            "normalized_concept": canonical,
            "display_concept": (profile or {}).get("canonical_concept") or rows[0]["concept"],
            "aliases": aliases,
            "failure_type": failure_type,
            "failure_type_code": {
                "identity_only_missing": "A",
                "relationship_missing": "B",
                "capability_missing": "C",
                "contextual_ambiguous": "D",
            }[failure_type],
            "identity": identity_state,
            "relationship": relationship_state,
            "capability": capability_state,
            "current_technology_identity_status": resolver.get("status"),
            "current_technology_id": resolver.get("technology_id"),
            "current_resolver_outcome": deepcopy(resolver),
            "current_candidate_routes": sorted({row["candidate"]["candidate_route"] for row in rows}),
            "operational_routes": sorted({row["operational_route"] for row in rows}),
            "relevant_existing_capabilities": closest,
            "appropriate_existing_capability_exists": bool(safe_capability),
            "safe_relationship_capability_id": safe_capability,
            "safe_relationship_can_be_proposed": bool(safe_capability),
            "relationship_research_required": bool((profile or {}).get("relationship_research_required", not safe_capability)),
            "taxonomy_lacks_appropriate_capability": failure_type == "capability_missing",
            "possible_new_capability_required": failure_type == "capability_missing",
            "why_existing_insufficient": (profile or {}).get(
                "why_existing_insufficient", "No deterministic current-taxonomy equivalence was established"
            ),
            "contextual_guidance": (profile or {}).get("contextual_guidance"),
            "candidate_definition": deepcopy(new_capability),
            "affected_requirement_keys": affected_keys,
            "affected_requirements": sorted({row["example_jd_text"] for row in rows}),
            "affected_jobs": jobs,
            "job_count": len(jobs),
            "occurrence_count": sum(row["occurrences"] for row in rows),
            "required_core_impact": required_core,
            "source_candidate_ids": sorted({row["candidate_id"] for row in rows}),
        }
        matrix.append(matrix_row)

        if safe_capability:
            technology_id = resolver.get("technology_id") or _technology_id_for(
                (seed or {}).get("canonical_name") or matrix_row["display_concept"]
            )
            seed_record = seed or {
                "seed_id": "tqd3closure_" + fingerprint(matrix_row["display_concept"])[:20],
                "canonical_name": matrix_row["display_concept"],
            }
            relationship = _bootstrap_proposal(
                seed_record,
                resolution_type="add_technology_relationship",
                proposed_change={
                    "possible": True,
                    "resolution_type": "add_technology_relationship",
                    "local_safe": True,
                    "technology_id": technology_id,
                    "technology": matrix_row["display_concept"],
                    "relationship": {
                        "capability_id": safe_capability,
                        "relationship_type": "maps_to_capability",
                        "reason": (profile or {}).get("relationship_rationale", "Current taxonomy boundary supports this relationship"),
                        "taxonomy_boundary_checks": (profile or {}).get("boundary_checks", []),
                        "conflicting_capabilities": [],
                        "safe_for_local_review": True,
                        "external_research_recommended": False,
                    },
                    "taxonomy_definition": closest[0] if closest else None,
                    "corpus_requirements_affected": len(affected_keys),
                    "jobs_affected": jobs,
                    "required_core_impact": required_core,
                    "external_research_recommended": False,
                    "reason": (profile or {}).get("relationship_rationale", "Current taxonomy boundary supports this relationship"),
                },
                matched=[
                    requirement for requirement in audit["requirements"]
                    if (requirement["job_id"], requirement["requirement_id"]) in set(affected_keys)
                ],
                dependency_ids=[identity_proposal["proposal_id"]] if identity_proposal else [],
            )
            relationship_drafts.append(relationship)

        if failure_type == "capability_missing":
            if new_capability:
                capability_id = new_capability["capability_id"]
                group = capability_groups.setdefault(capability_id, {
                    "definition": new_capability,
                    "rows": [],
                    "technologies": [],
                    "matrix_rows": [],
                })
                group["rows"].extend(rows)
                group["matrix_rows"].append(matrix_row)
                if seed:
                    group["technologies"].append({
                        "technology_id": resolver.get("technology_id") or _technology_id_for(seed["canonical_name"]),
                        "canonical_name": seed["canonical_name"],
                        "aliases": seed["aliases"],
                        "technology_kind": seed["technology_kind"],
                    })
            else:
                candidate = deepcopy(rows[0]["candidate"])
                candidate["candidate_route"] = "possible_new_capability"
                candidate["routing_reason"] = "Existing taxonomy lacks a confirmed non-overlapping capability definition"
                candidate["candidate_fingerprint"] = fingerprint({
                    key: value for key, value in candidate.items()
                    if key not in {"candidate_id", "candidate_fingerprint"}
                })
                candidate["candidate_id"] = "tqd3taxgap_" + candidate["candidate_fingerprint"][:24]
                research_candidates.append(candidate)

    capability_drafts = []
    for capability_id, group in capability_groups.items():
        definition = group["definition"]
        candidate = _closure_candidate(group["rows"], capability=definition)
        research_candidates.append(candidate)
        keys = sorted({key for matrix_row in group["matrix_rows"] for key in matrix_row["affected_requirement_keys"]})
        jobs = sorted({key[0] for key in keys if key[0] is not None})
        key_set = set(keys)
        potential_collateral = [
            {"job_id": requirement["job_id"], "requirement_id": requirement["requirement_id"],
             "requirement_text": requirement["requirement_text"]}
            for requirement in audit["requirements"]
            if (requirement["job_id"], requirement["requirement_id"]) not in key_set
            and any(phrase_present(requirement["requirement_text"], term)
                    for term in definition["requirement_terms"])
        ]
        draft = {
            "closure_draft_version": CAPABILITY_CLOSURE_VERSION,
            "draft_kind": "possible_new_capability_candidate",
            "status": "research_required",
            "publishable": False,
            "candidate": candidate,
            "candidate_capability_concept": definition["label"],
            "proposed_capability_id": capability_id,
            "candidate_definition": definition["definition"],
            "candidate_boundaries": definition["boundaries"],
            "does_not_prove": definition["does_not_prove"],
            "requirement_terms": definition["requirement_terms"],
            "closest_existing_capabilities": sorted({
                item["capability_id"] for row in group["matrix_rows"]
                for item in row["relevant_existing_capabilities"]
            }),
            "why_existing_insufficient": sorted({row["why_existing_insufficient"] for row in group["matrix_rows"]}),
            "overlap_risks": definition["overlap_risks"],
            "overlap_diagnostics": overlap_check(" ".join(definition["requirement_terms"])),
            "technologies": list({item["technology_id"]: item for item in group["technologies"]}.values()),
            "affected_requirement_keys": keys,
            "affected_jobs": jobs,
            "required_core_impact": sum(row["required_core_impact"] for row in group["matrix_rows"]),
            "estimated_corpus_impact": len(keys),
            "potential_collateral_requirements": potential_collateral,
            "scenario_preview_eligible": not potential_collateral,
            "scenario_blockers": (["taxonomy_phrase_would_match_outside_declared_gap_provenance"]
                                  if potential_collateral else []),
            "research_requirement": "Existing route-aware governed capability research with first-party/authoritative evidence",
            "requires_human_review": True,
            "requires_human_approval": True,
            "approval": False,
            "publication": False,
        }
        draft["draft_fingerprint"] = fingerprint(draft)
        draft["draft_id"] = "tqd3closure_" + draft["draft_fingerprint"][:24]
        capability_drafts.append(draft)

    matrix.sort(key=lambda row: (-row["required_core_impact"], -row["job_count"],
                                 -row["occurrence_count"], row["normalized_concept"]))
    counts = Counter(row["failure_type"] for row in matrix)
    report = {
        "closure_version": CAPABILITY_CLOSURE_VERSION,
        "matrix": matrix,
        "top_gap_count": len(matrix),
        "failure_type_counts": {
            "identity_only_missing": counts["identity_only_missing"],
            "relationship_missing": counts["relationship_missing"],
            "capability_missing": counts["capability_missing"],
            "contextual_ambiguous": counts["contextual_ambiguous"],
        },
        "safe_relationship_drafts": relationship_drafts,
        "possible_new_capability_drafts": capability_drafts,
        "research_candidates": research_candidates,
        "research_required_actions": sum(
            row["relationship_research_required"] or row["possible_new_capability_required"] for row in matrix
        ),
        "bootstrap_plan": bootstrap,
        "current_coverage": deepcopy(audit["summary"]),
        "review_only": True,
        "approval": False,
        "publication": False,
        "production_mutations": 0,
        "scoring_semantics_changed": False,
        "network_calls": 0,
        "model_calls": 0,
    }
    report["matrix_fingerprint"] = fingerprint({key: value for key, value in report.items() if key != "matrix_fingerprint"})
    return report


def _closure_scenario_knowledge(
    identity_proposals: list[dict[str, Any]],
    relationship_proposals: list[dict[str, Any]],
    capability_drafts: list[dict[str, Any]],
) -> tuple[CapabilityTaxonomy, TechnologyRegistry]:
    shadow_taxonomy, shadow_registry = _temporary_knowledge(identity_proposals + relationship_proposals)
    capabilities = deepcopy(list(shadow_taxonomy.capabilities))
    seen = {row["capability_id"] for row in capabilities}
    next_priority = max(row["priority"] for row in capabilities) + 1
    for index, draft in enumerate(sorted(capability_drafts, key=lambda row: row["proposed_capability_id"])):
        definition = draft["candidate_definition"]
        profile = next(
            row for row in load_capability_closure_profiles()["profiles"]
            if (row.get("new_capability") or {}).get("capability_id") == draft["proposed_capability_id"]
        )
        entry = {
            "capability_id": draft["proposed_capability_id"],
            "label": draft["candidate_capability_concept"],
            "domain": profile["new_capability"]["domain"],
            "priority": next_priority + index,
            "definition": definition,
            "requirement": {"any_terms": deepcopy(draft["requirement_terms"]), "all_terms": []},
            "evidence_tiers": [{
                "label": "direct",
                "any_terms": sorted({alias for technology in draft["technologies"] for alias in technology["aliases"]}
                                    or set(draft["requirement_terms"])),
                "reason": "hypothetical_closure_scenario_only",
                "concepts": [draft["proposed_capability_id"]],
            }],
            "does_not_prove": deepcopy(draft["does_not_prove"]),
        }
        _validate_capability(entry, seen)
        seen.add(entry["capability_id"])
        capabilities.append(entry)

    entries = deepcopy(list(shadow_registry.entries))
    by_id = {row["technology_id"]: row for row in entries}
    for draft in capability_drafts:
        for technology in draft["technologies"]:
            entry = by_id.get(technology["technology_id"])
            if entry is None:
                entry = {
                    "technology_id": technology["technology_id"],
                    "label": technology["canonical_name"],
                    "entry_kind": technology["technology_kind"],
                    "aliases": deepcopy(technology["aliases"]),
                    "status": "approved",
                    "capability_relationships": [],
                    "notes": "Temporary capability closure scenario",
                }
                entries.append(entry)
                by_id[technology["technology_id"]] = entry
            approved = [row for row in entry.get("capability_relationships", [])
                        if row.get("relationship_type") == "maps_to_capability" and row.get("status") == "approved"]
            if not approved:
                entry.setdefault("capability_relationships", []).append({
                    "capability_id": draft["proposed_capability_id"],
                    "relationship_type": "maps_to_capability",
                    "status": "approved",
                })
    taxonomy = CapabilityTaxonomy(shadow_taxonomy.version + "+closure-scenario", tuple(capabilities))
    with temporary_taxonomy_scope(taxonomy):
        _validate_registry({"registry_version": shadow_registry.version + "+closure-scenario", "entries": entries})
    registry = TechnologyRegistry(shadow_registry.version + "+closure-scenario", tuple(entries))
    return taxonomy, registry


def _preview_closure_scenario(
    audit: dict[str, Any],
    *,
    taxonomy: CapabilityTaxonomy,
    registry: TechnologyRegistry,
    intended_keys: set[tuple[Any, Any]],
) -> dict[str, Any]:
    output = []
    with temporary_taxonomy_scope(taxonomy), temporary_registry_scope(registry):
        for row in audit["requirements"]:
            before = deepcopy(row["current_resolution"])
            after = _resolution({"text": row["requirement_text"], "atomic_focus": row["requirement_text"]})
            semantic_fields = ("status", "resolution_source", "capability_id", "technology_id",
                               "technology_label", "registry_status", "registry_reason")
            changed = any(before.get(field) != after.get(field) for field in semantic_fields)
            output.append({
                "job_id": row["job_id"], "requirement_id": row["requirement_id"],
                "requirement_text": row["requirement_text"], "importance": row["importance"],
                "group_weight_fraction": row.get("group_weight_fraction", 1.0),
                "before": before, "after": after, "changed": changed,
                "would_resolve": before["status"] != "resolved" and after["status"] == "resolved",
            })
    noise_keys = {
        (source.get("job_id"), source.get("requirement_id"))
        for queue_row in audit["queue"]
        if not queue_row.get("parent_candidate_id") and queue_row["operational_route"] == "noise_or_non_capability"
        for source in queue_row["provenance"]
    }
    before_rows = [row for row in audit["requirements"] if (row["job_id"], row["requirement_id"]) not in noise_keys]
    by_key = {(row["job_id"], row["requirement_id"]): row for row in output}
    after_rows = []
    for row in before_rows:
        copied = deepcopy(row)
        copied["current_resolution"] = by_key[(row["job_id"], row["requirement_id"])]["after"]
        after_rows.append(copied)
    changed = [row for row in output if row["changed"]]
    conflicts = [
        {"job_id": row["job_id"], "requirement_id": row["requirement_id"],
         "requirement_text": row["requirement_text"], "reason": "changed_outside_declared_gap_provenance"}
        for row in changed if (row["job_id"], row["requirement_id"]) not in intended_keys
    ]
    before_overall = _coverage(before_rows, {"deal_breaker", "required", "core", "preferred"})
    after_overall = _coverage(after_rows, {"deal_breaker", "required", "core", "preferred"})
    before_required = _coverage(before_rows, {"deal_breaker", "required", "core"})
    after_required = _coverage(after_rows, {"deal_breaker", "required", "core"})
    return {
        "requirements_evaluated": len(output),
        "rows": output,
        "newly_taxonomy_resolved_requirements": sum(row["would_resolve"] for row in output),
        "newly_scorable_requirements": sum(row["would_resolve"] for row in output),
        "affected_jobs": sorted({row["job_id"] for row in changed}),
        "unchanged_requirements": sum(not row["changed"] for row in output),
        "conflicts_ambiguity": conflicts,
        "taxonomy_resolution_before_percent": before_overall["percent"],
        "taxonomy_resolution_after_percent": after_overall["percent"],
        "coverage_before_percent": before_overall["percent"],
        "coverage_after_percent": after_overall["percent"],
        "required_core_before_percent": before_required["percent"],
        "required_core_after_percent": after_required["percent"],
        "review_only": True,
        "hypothetical_research_required": True,
        "scoring_influence": False,
        "production_mutations": 0,
    }


def preview_capability_closure(audit: dict[str, Any], closure: dict[str, Any]) -> dict[str, Any]:
    """Preview safe relationships and research-dependent capabilities separately."""
    if closure.get("closure_version") != CAPABILITY_CLOSURE_VERSION:
        raise ValueError("Current capability closure matrix required")
    identities = closure["bootstrap_plan"]["identity_only_proposals"]
    relationships = closure["safe_relationship_drafts"]
    identity_preview = _preview_or_baseline(audit, identities)
    safe_preview = _preview_or_baseline(audit, identities + relationships)
    eligible_capability_drafts = [
        draft for draft in closure["possible_new_capability_drafts"]
        if draft.get("scenario_preview_eligible") is True
    ]
    taxonomy, registry = _closure_scenario_knowledge(
        identities, relationships, eligible_capability_drafts
    )
    intended = {
        tuple(key) for draft in eligible_capability_drafts
        for key in draft["affected_requirement_keys"]
    } | {
        tuple(key) for proposal in relationships for key in proposal["affected_requirement_keys"]
    } | {
        tuple(key) for proposal in identities for key in proposal["affected_requirement_keys"]
    }
    capability_preview = _preview_closure_scenario(
        audit, taxonomy=taxonomy, registry=registry, intended_keys=intended
    )
    changed_by_key = {
        (row["job_id"], row["requirement_id"]): row
        for row in capability_preview["rows"] if row["would_resolve"]
    }
    ranked = []
    for draft in closure["possible_new_capability_drafts"]:
        keys = {tuple(key) for key in draft["affected_requirement_keys"]}
        changed = [row for key, row in changed_by_key.items() if key in keys]
        ranked.append({
            "fix_id": draft["draft_id"],
            "fix_type": "possible_new_capability",
            "concept": draft["candidate_capability_concept"],
            "target": draft["proposed_capability_id"],
            "requirements_newly_taxonomy_resolved": len(changed),
            "requirements_newly_scorable": len(changed),
            "required_core_weight_impact": round(sum(
                IMPORTANCE_WEIGHTS.get(str(row["importance"] or "").lower(), 0.0)
                * float(row.get("group_weight_fraction", 1.0) or 1.0)
                for row in changed if str(row["importance"] or "").lower() in {"deal_breaker", "required", "core"}
            ), 6),
            "jobs_affected": sorted({row["job_id"] for row in changed}),
            "occurrence_count": draft["estimated_corpus_impact"],
            "semantic_confidence": "research_required",
            "regression_safety": (
                "hypothetical_only" if draft.get("scenario_preview_eligible") is True
                else "fail_closed_collateral_phrase_match"
            ),
        })
    for proposal in relationships:
        keys = {tuple(key) for key in proposal["affected_requirement_keys"]}
        changed = [row for key, row in changed_by_key.items() if key in keys]
        ranked.append({
            "fix_id": proposal["proposal_id"],
            "fix_type": "safe_existing_capability_relationship",
            "concept": proposal["technology"],
            "target": proposal["proposed_change"]["relationship"]["capability_id"],
            "requirements_newly_taxonomy_resolved": len(changed),
            "requirements_newly_scorable": len(changed),
            "required_core_weight_impact": round(sum(
                IMPORTANCE_WEIGHTS.get(str(row["importance"] or "").lower(), 0.0)
                * float(row.get("group_weight_fraction", 1.0) or 1.0)
                for row in changed if str(row["importance"] or "").lower() in {"deal_breaker", "required", "core"}
            ), 6),
            "jobs_affected": sorted({row["job_id"] for row in changed}),
            "occurrence_count": len(keys),
            "semantic_confidence": "local_boundary_supported",
            "regression_safety": "temporary_overlay_clean" if not capability_preview["conflicts_ambiguity"] else "review_conflicts",
        })
    ranked_capability_ids = {row["target"] for row in ranked if row["fix_type"] == "possible_new_capability"}
    ranked_relationship_concepts = {normalise(row["concept"]) for row in ranked
                                    if row["fix_type"] == "safe_existing_capability_relationship"}
    for matrix_row in closure["matrix"]:
        definition = matrix_row.get("candidate_definition") or {}
        if definition.get("capability_id") in ranked_capability_ids:
            continue
        if matrix_row.get("safe_relationship_capability_id") and normalise(matrix_row["display_concept"]) in ranked_relationship_concepts:
            continue
        ranked.append({
            "fix_id": "tqd3closure_action_" + fingerprint({
                "concept": matrix_row["normalized_concept"], "failure_type": matrix_row["failure_type"]
            })[:20],
            "fix_type": (
                "possible_new_capability_research"
                if matrix_row["failure_type"] == "capability_missing"
                else "contextual_decomposition_or_manual_review"
            ),
            "concept": matrix_row["display_concept"],
            "target": matrix_row.get("safe_relationship_capability_id") or "no_universal_mapping",
            "requirements_newly_taxonomy_resolved": 0,
            "requirements_newly_scorable": 0,
            "required_core_weight_impact": 0.0,
            "jobs_affected": [],
            "occurrence_count": matrix_row["occurrence_count"],
            "semantic_confidence": "research_required" if matrix_row["failure_type"] == "capability_missing" else "contextual_manual",
            "regression_safety": "fail_closed_no_resolution_claimed",
        })
    ranked.sort(key=lambda row: (
        -row["required_core_weight_impact"], -len(row["jobs_affected"]),
        -row["occurrence_count"], row["concept"].casefold()
    ))
    resolved_after = sum(row["after"]["status"] == "resolved" for row in capability_preview["rows"])
    meaningful = audit["summary"]["meaningful_technical_requirements"]
    return {
        "preview_version": "tqd3-capability-closure-impact-v1",
        "taxonomy_resolution_curve": [
            {"stage": "current_production", "overall_percent": audit["summary"]["taxonomy_resolution_overall_weighted_coverage"]["percent"],
             "required_core_percent": audit["summary"]["required_core_weighted_coverage"]["percent"]},
            {"stage": "identity_only", "overall_percent": identity_preview["projected_coverage_after_percent"],
             "required_core_percent": identity_preview["required_core_coverage_after_percent"]},
            {"stage": "safe_existing_capability_relationships", "overall_percent": safe_preview["projected_coverage_after_percent"],
             "required_core_percent": safe_preview["required_core_coverage_after_percent"]},
            {"stage": "research_dependent_new_capabilities", "overall_percent": capability_preview["coverage_after_percent"],
             "required_core_percent": capability_preview["required_core_after_percent"]},
        ],
        "coverage_curve": [
            {"stage": "current_production", "overall_percent": audit["summary"]["taxonomy_resolution_overall_weighted_coverage"]["percent"],
             "required_core_percent": audit["summary"]["required_core_weighted_coverage"]["percent"]},
            {"stage": "identity_only", "overall_percent": identity_preview["projected_coverage_after_percent"],
             "required_core_percent": identity_preview["required_core_coverage_after_percent"]},
            {"stage": "safe_existing_capability_relationships", "overall_percent": safe_preview["projected_coverage_after_percent"],
             "required_core_percent": safe_preview["required_core_coverage_after_percent"]},
            {"stage": "research_dependent_new_capabilities", "overall_percent": capability_preview["coverage_after_percent"],
             "required_core_percent": capability_preview["required_core_after_percent"]},
        ],
        "identity_only": identity_preview,
        "safe_relationships": safe_preview,
        "new_capability_scenario": capability_preview,
        "additional_coverage_potential_percent": round(
            capability_preview["coverage_after_percent"] - safe_preview["projected_coverage_after_percent"], 2
        ),
        "coverage_still_blocked_percent": round(100.0 - capability_preview["coverage_after_percent"], 2),
        "unresolved_meaningful_after_scenario": max(0, meaningful - resolved_after),
        "top_20_highest_impact_fixes": ranked[:20],
        "false_positive_collateral_matches": capability_preview["conflicts_ambiguity"],
        "blocked_capability_scenarios": [
            {"draft_id": draft["draft_id"], "concept": draft["candidate_capability_concept"],
             "blockers": draft["scenario_blockers"],
             "potential_collateral_requirements": draft["potential_collateral_requirements"]}
            for draft in closure["possible_new_capability_drafts"]
            if draft.get("scenario_preview_eligible") is not True
        ],
        "review_only": True,
        "approval": False,
        "publication": False,
        "production_mutations": 0,
        "scoring_semantics_changed": False,
        "network_calls": 0,
        "model_calls": 0,
    }


def _cached_research_summary(
    concept: str,
    saved_research_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    aliases = {
        "HCL BigFix": ("bigfix",),
        "distributed systems": ("distributed systems",),
        "SQL": ("sql", "sql querying"),
        "Ansible": ("ansible", "infrastructure automation"),
        "network access control": ("network access control",),
    }[concept]
    matches = []
    for saved in saved_research_rows:
        result = saved.get("result") if isinstance(saved, dict) else None
        if not isinstance(result, dict):
            continue
        candidate = result.get("candidate") or {}
        subject = normalise(candidate.get("normalized_cluster") or "")
        if not any(alias in subject for alias in aliases):
            continue
        matches.append({
            "research_result_id": result.get("research_result_id"),
            "provider_request_id": result.get("provider_request_id"),
            "candidate_route": result.get("candidate_route") or candidate.get("candidate_route"),
            "authoritative_definition_count": len(result.get("authoritative_evidence_summary") or []),
            "primary_definition_count": int((result.get("quality_diagnostics") or {}).get("primary_definitions") or 0),
            "recommended_next_action": result.get("recommended_next_action"),
            "conflicts_blockers": deepcopy(result.get("conflicts_blockers") or []),
            "review_decision": (saved.get("review") or {}).get("decision", "undecided"),
        })
    return {
        "saved_result_count": len(matches),
        "results": matches,
        "governed_authoritative_definition_available": any(
            row["authoritative_definition_count"] or row["primary_definition_count"]
            for row in matches
        ),
        "network_calls": 0,
        "model_calls": 0,
    }


def _cap_boundary_classification(row: dict[str, Any]) -> dict[str, Any]:
    capability_id = str((row.get("current_resolution") or {}).get("capability_id") or "")
    text = str(row.get("requirement_text") or "")
    without_list_marker = re.sub(r"^\s*\([a-z]\)\s+", "", text, flags=re.I)
    genuine_c_cpp = bool(re.search(
        r"(?<![a-z0-9+#])c(?:\+\+(?:11|14|17|20|23|26)?|11|17|23)?(?![a-z0-9+#])",
        without_list_marker.lower(),
    ))
    if capability_id == "language.modern_cpp" and not genuine_c_cpp:
        return {
            "classification": "resolver_boundary_issue",
            "reason": "A leading alphabetic list marker collided with the bare C requirement token.",
            "false_rejection": row.get("match_label") == "none",
            "recommended_action": "governed bare-C list-marker boundary proposal",
            "fixed": False,
        }
    if capability_id == "quality.qa_testing" and re.search(
        r"\b(?:penetration|security|vulnerability)\s+testing\b", text, re.I
    ):
        return {
            "classification": "resolver_boundary_issue",
            "reason": "A security-testing phrase reaches the broad QA testing boundary; the existing cap limits, but does not establish, equivalence.",
            "false_rejection": False,
            "recommended_action": "retain cap and review a separate cybersecurity boundary",
            "fixed": False,
        }
    return {
        "classification": "expected_semantic_protection",
        "reason": "The capability evidence policy conservatively limited evidence that did not prove the requested behavior.",
        "false_rejection": False,
        "recommended_action": "retain",
        "fixed": False,
    }


def build_targeted_taxonomy_cleanup(
    audit: dict[str, Any],
    *,
    saved_research_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prepare the final narrow taxonomy review without approving knowledge."""
    if audit.get("audit_version") != CORPUS_GAP_RESOLUTION_VERSION:
        raise ValueError("Current corpus gap audit required")
    saved_research_rows = list(saved_research_rows or [])
    closure = build_capability_closure_matrix(audit, top_n=100)
    matrix = {row["display_concept"]: row for row in closure["matrix"]}
    draft_by_id = {
        row["proposed_capability_id"]: row
        for row in closure["possible_new_capability_drafts"]
    }
    items = []
    for concept, decision in TARGETED_TAXONOMY_DECISIONS.items():
        if concept not in matrix:
            raise ValueError(f"Targeted concept absent from current corpus audit: {concept}")
        current = matrix[concept]
        research = _cached_research_summary(concept, saved_research_rows)
        capability = deepcopy(current.get("candidate_definition"))
        draft = draft_by_id.get((capability or {}).get("capability_id"))
        review_ready = decision["disposition"] == "B" and draft is not None
        blockers = []
        if decision["disposition"] == "D":
            blockers.append(decision["reason"])
        if concept == "HCL BigFix" and not research["governed_authoritative_definition_available"]:
            blockers.append("No governed subject-specific authoritative definition in cached research")
        if concept == "distributed systems":
            blockers.append("Known compound phrase collision remains unresolved")
        items.append({
            "candidate": concept,
            **deepcopy(decision),
            "current_knowledge": {
                "identity": current["identity"],
                "relationship": current["relationship"],
                "capability": current["capability"],
                "nearest_existing_capabilities": deepcopy(current["relevant_existing_capabilities"]),
                "why_existing_insufficient": current["why_existing_insufficient"],
            },
            "corpus_provenance": {
                "affected_requirement_keys": deepcopy(current["affected_requirement_keys"]),
                "affected_requirements": deepcopy(current["affected_requirements"]),
                "affected_jobs": deepcopy(current["affected_jobs"]),
                "occurrence_count": current["occurrence_count"],
                "required_core_impact": current["required_core_impact"],
            },
            "proposed_capability": capability if decision["disposition"] == "B" else None,
            "potential_collateral_requirements": deepcopy(
                (draft or {}).get("potential_collateral_requirements") or []
            ),
            "cached_research": research,
            "review_readiness": "READY FOR HUMAN REVIEW" if review_ready else "NOT READY",
            "review_blockers": blockers,
            "publication_dependencies": (
                ["governed capability research", "human approval", "fresh full-corpus regression"]
                if review_ready else []
            ),
            "approval": False,
            "publication": False,
        })

    active_caps = []
    for capability_id in ACTIVE_TAXONOMY_CAPABILITY_IDS:
        affected = [
            row for row in audit["requirements"]
            if row.get("taxonomy_cap_status") == "applied"
            and (row.get("current_resolution") or {}).get("capability_id") == capability_id
        ]
        findings = [{
            "job_id": row["job_id"],
            "requirement_id": row["requirement_id"],
            "requirement_text": row["requirement_text"],
            "resulting_match_label": row["match_label"],
            **_cap_boundary_classification(row),
        } for row in affected]
        active_caps.append({
            "capability_id": capability_id,
            "intervention_count": len(affected),
            "positive_after_cap": sum(row["match_label"] != "none" for row in affected),
            "rejected_after_cap": sum(row["match_label"] == "none" for row in affected),
            "findings": findings,
            "audit_status": "active" if affected else "no_current_intervention",
        })

    g_rows = [
        row for row in audit["true_job_match_gap_triage"]["requirements"]
        if row.get("category_code") == "G"
    ]
    boundary_rows = [{
        "job_id": row["job_id"],
        "requirement_id": row["requirement_id"],
        "requirement_text": row["requirement_text"],
        "capability_id": row["taxonomy_result"].get("capability_id"),
        "disposition": "retain_intentional_evidence_boundary",
        "reason": "Domain work does not prove a stated subjective interest; the current none result is conservative and correct.",
    } for row in g_rows]
    review_drafts = [
        deepcopy(draft_by_id[item["proposed_capability"]["capability_id"]])
        for item in items if item["review_readiness"] == "READY FOR HUMAN REVIEW"
    ]
    counts = Counter(item["disposition"] for item in items)
    report = {
        "cleanup_version": TARGETED_TAXONOMY_CLEANUP_VERSION,
        "targeted_items": items,
        "disposition_counts": {code: counts[code] for code in "ABCDEF"},
        "human_review_ready_proposals": review_drafts,
        "active_taxonomy_caps": active_caps,
        "active_intervention_count": sum(row["intervention_count"] for row in active_caps),
        "false_rejection_findings": [
            finding for row in active_caps for finding in row["findings"]
            if finding["false_rejection"]
        ],
        "false_rejections_fixed": 0,
        "g_boundary_rows": boundary_rows,
        "closure": closure,
        "review_only": True,
        "approval": False,
        "publication": False,
        "production_mutations": 0,
        "scoring_formula_changed": False,
        "global_thresholds_changed": False,
        "network_calls": 0,
        "model_calls": 0,
    }
    report["report_fingerprint"] = fingerprint({
        key: value for key, value in report.items() if key != "report_fingerprint"
    })
    return report


def _integrated_corpus_metrics(
    corpus: dict[str, Any],
    *,
    stored_requirements: int | None = None,
) -> dict[str, Any]:
    requirements = [row for job in corpus["jobs"] for row in job.get("requirements", [])]
    canonical = [
        row for job in corpus["jobs"]
        for row in (job.get("baseline_stable_analysis") or {}).get("canonical_requirements", [])
    ]
    eligible = [row for row in requirements if row.get("score_eligible")]
    positive = [
        row for row in eligible
        if row.get("match_label") in {"direct", "transferable", "weak"}
        and row.get("selected_evidence")
    ]
    recognized_unmapped = [
        row for row in eligible
        if (row.get("technology_registry_resolution") or {}).get("status") == "recognized_unmapped"
    ]
    resolved = [row for row in eligible if row.get("resolution_status") == "resolved"]
    capped = [row for row in canonical if row.get("capability_taxonomy_cap_status") == "applied"]
    return {
        "jobs": len(corpus["jobs"]),
        "stored_requirements": (
            int(stored_requirements)
            if stored_requirements is not None
            else sum(len(job.get("saved_requirements") or job.get("requirements", [])) for job in corpus["jobs"])
        ),
        "active_scoring_units": len(requirements),
        "score_eligible": len(eligible),
        "positive_grounded_matches": len(positive),
        "direct": sum(row.get("match_label") == "direct" for row in positive),
        "transferable": sum(row.get("match_label") == "transferable" for row in positive),
        "weak": sum(row.get("match_label") == "weak" for row in positive),
        "true_no_evidence": sum(not row.get("selected_evidence") for row in eligible),
        "taxonomy_resolved": len(resolved),
        "recognized_unmapped": len(recognized_unmapped),
        "taxonomy_unresolved": len(eligible) - len(resolved) - len(recognized_unmapped),
        "taxonomy_capped": len(capped),
        "taxonomy_rejected": sum(row.get("match_label") == "none" for row in capped),
    }


def _integrated_ranking(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    ordered = sorted(
        corpus["jobs"],
        key=lambda job: (
            -int((job.get("metrics") or {}).get("deterministic_alignment_score") or 0),
            int(job.get("job_id") or 0),
        ),
    )
    return [{
        "rank": index,
        "job_id": job["job_id"],
        "score": int((job.get("metrics") or {}).get("deterministic_alignment_score") or 0),
    } for index, job in enumerate(ordered, 1)]


def preview_targeted_taxonomy_cleanup(
    audit: dict[str, Any],
    cleanup: dict[str, Any],
) -> dict[str, Any]:
    """Replay approved-for-review capability hypotheses in copied knowledge."""
    if cleanup.get("cleanup_version") != TARGETED_TAXONOMY_CLEANUP_VERSION:
        raise ValueError("Current targeted cleanup report required")
    if cleanup.get("report_fingerprint") != fingerprint({
        key: value for key, value in cleanup.items() if key != "report_fingerprint"
    }):
        raise ValueError("Targeted cleanup report was edited")
    taxonomy_before = fingerprint(Path(TAXONOMY_PATH).read_bytes().hex())
    registry_before = fingerprint(Path(REGISTRY_PATH).read_bytes().hex())
    # Capability review must not silently approve the example technology
    # relationships.  Those remain separate contextual/research decisions.
    drafts = []
    for draft in cleanup["human_review_ready_proposals"]:
        copied = deepcopy(draft)
        copied["technologies"] = []
        drafts.append(copied)
    if not drafts:
        raise ValueError("At least one human-review-ready capability draft required")
    taxonomy, registry = _closure_scenario_knowledge([], [], drafts)
    with temporary_taxonomy_scope(taxonomy), temporary_registry_scope(registry):
        proposed = replay_current_corpus(audit["corpus"])
    if fingerprint(Path(TAXONOMY_PATH).read_bytes().hex()) != taxonomy_before:
        raise RuntimeError("Production taxonomy changed during temporary preview")
    if fingerprint(Path(REGISTRY_PATH).read_bytes().hex()) != registry_before:
        raise RuntimeError("Production registry changed during temporary preview")

    baseline = audit["corpus"]
    intended_keys = {
        tuple(key)
        for item in cleanup["targeted_items"]
        if item["review_readiness"] == "READY FOR HUMAN REVIEW"
        for key in item["corpus_provenance"]["affected_requirement_keys"]
    }
    before_rows = {
        (job["job_id"], row["requirement_id"]): row
        for job in baseline["jobs"] for row in job.get("requirements", [])
    }
    after_rows = {
        (job["job_id"], row["requirement_id"]): row
        for job in proposed["jobs"] for row in job.get("requirements", [])
    }
    fields = (
        "resolution_status", "resolution_source", "capability_id", "technology_id",
        "match_label", "match_value", "selected_evidence", "score_eligible",
    )
    changes = []
    for key in sorted(set(before_rows) | set(after_rows)):
        before, after = before_rows.get(key), after_rows.get(key)
        changed_fields = [field for field in fields if (before or {}).get(field) != (after or {}).get(field)]
        if not changed_fields:
            continue
        changes.append({
            "job_id": key[0],
            "requirement_id": key[1],
            "requirement_text": (after or before or {}).get("requirement_text"),
            "changed_fields": changed_fields,
            "before": before,
            "after": after,
            "intended": key in intended_keys,
        })

    before_ranking = _integrated_ranking(baseline)
    after_ranking = _integrated_ranking(proposed)
    before_rank = {row["job_id"]: row for row in before_ranking}
    after_rank = {row["job_id"]: row for row in after_ranking}
    score_changes = [{
        "job_id": job_id,
        "before": before_rank[job_id]["score"],
        "after": after_rank[job_id]["score"],
        "delta": after_rank[job_id]["score"] - before_rank[job_id]["score"],
    } for job_id in sorted(before_rank)
        if before_rank[job_id]["score"] != after_rank[job_id]["score"]]
    rank_changes = [{
        "job_id": job_id,
        "before": before_rank[job_id]["rank"],
        "after": after_rank[job_id]["rank"],
    } for job_id in sorted(before_rank)
        if before_rank[job_id]["rank"] != after_rank[job_id]["rank"]]
    false_positives = [
        row for row in changes
        if not row["intended"]
        and (row["before"] or {}).get("match_label") == "none"
        and (row["after"] or {}).get("match_label") in {"direct", "transferable", "weak"}
    ]
    baseline_metrics = _integrated_corpus_metrics(baseline)
    temporary_metrics = _integrated_corpus_metrics(
        proposed,
        stored_requirements=baseline_metrics["stored_requirements"],
    )
    return {
        "preview_version": "tqd3-targeted-taxonomy-integrated-regression-v1",
        "scoring_identity": current_match_versions(),
        "baseline_metrics": baseline_metrics,
        "temporary_metrics": temporary_metrics,
        "baseline_ranking": before_ranking,
        "temporary_ranking": after_ranking,
        "requirement_changes": changes,
        "new_taxonomy_resolutions": sum(
            (row["before"] or {}).get("resolution_status") != "resolved"
            and (row["after"] or {}).get("resolution_status") == "resolved"
            for row in changes
        ),
        "positive_matches_changed": sum(
            (row["before"] or {}).get("match_label") != (row["after"] or {}).get("match_label")
            for row in changes
        ),
        "taxonomy_caps_delta": (
            temporary_metrics["taxonomy_capped"]
            - baseline_metrics["taxonomy_capped"]
        ),
        "taxonomy_rejects_delta": (
            temporary_metrics["taxonomy_rejected"]
            - baseline_metrics["taxonomy_rejected"]
        ),
        "job_score_changes": score_changes,
        "rank_changes": rank_changes,
        "collateral_matches": [row for row in changes if not row["intended"]],
        "false_positive_matches": false_positives,
        "production_taxonomy_mutated": False,
        "production_registry_mutated": False,
        "scoring_formula_changed": False,
        "global_thresholds_changed": False,
        "review_only": True,
        "approval": False,
        "publication": False,
        "network_calls": 0,
        "model_calls": 0,
    }


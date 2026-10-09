"""Read-only contextual hypotheses over native registry, evidence and replay.

No profile is a production mapping. Full-phrase predicates are review hypotheses,
not research evidence or authority. Only explicit offline validation activates them.
"""
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
from pathlib import Path
import re
from threading import RLock

from analysis_stability import stable_evidence_scoring as scoring
from tailoring import production_requirement_resolver as resolver
from tailoring.capability_taxonomy import get_default_taxonomy
from taxonomy_discovery import maintenance_service as maintenance, corpus_gap_resolution as gaps
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery import technology_registry as registry
from taxonomy_discovery.regression_corpus import replay_current_corpus, duplicate_credit_violations
from taxonomy_discovery.technology_identity_remediation import _records, _receipt
from taxonomy_discovery.offline_execution import offline_execution

PROFILES = {
    "mongodb_schema_design": {"technology_id": "mongodb", "capability_id": "database.design",
        "pattern": r"(?:design|create|implement)\s+(?:a\s+)?(?:MongoDB\s+(?:database\s+)?schemas?|(?:database\s+)?schemas?\s+(?:using|with|in)\s+MongoDB)",
        "boundary": "Explicit database schema design, not generic persistence, administration, querying, or technology familiarity"},
    "node_api_implementation": {"technology_id": "node.js", "capability_id": "backend.api_development",
        "pattern": r"(?:build|develop|implement|create)\s+(?:backend\s+)?(?:REST\s+)?APIs?\s+(?:using|with|in)\s+(?:Node\.js|NodeJS|Node\s+JS)",
        "boundary": "Explicit API implementation, not framework familiarity, frontend development, or runtime identity"},
}
NEGATIVE_BOUNDARIES = ["technology only", "experience with technology", "unrelated activity", "OR/one-of/example lists",
    "negation", "mixed/compound obligations", "unproven technology-specific evidence", ".NET normalization/scope"]


def _implementation():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def eligible(text, profile):
    """Bound the entire requirement; never scan arbitrary mentions for a mapping."""
    value = str(text).strip().rstrip(".")
    return bool(re.fullmatch(PROFILES[profile]["pattern"], value, re.I))


def context(requirement, technology_id):
    text = requirement.get("atomic_focus") or requirement.get("text", "")
    if technology_id == "dotnet" or any(re.search(r"(?<!\w)\.NET\b", p.get("raw_parent_text", ""), re.I)
            for p in requirement.get("source_provenance", [])):
        return "normalization_or_scope", None, "BLOCKED_BY_PARSER_OR_NORMALIZATION", "Do not validate relationships through corrupted NET text or mixed .NET parent scope"
    for name, p in PROFILES.items():
        if p["technology_id"] == technology_id and eligible(text, name) and p["capability_id"] in get_default_taxonomy().by_id():
            return name, p["capability_id"], "NEEDS_SCOPE_REVIEW", "Bounded existing-capability hypothesis; negative evidence fixtures and native replay required"
    lower = text.lower()
    if technology_id == "mongodb":
        activities = []
        for family, pattern in (("administration", r"\b(?:administration|administer|backup|replication)\b"),
            ("querying", r"\b(?:query|queries|querying|crud)\b"), ("data_modelling", r"\b(?:schema|data model|modelling|modeling)\b"),
            ("persistence_usage", r"\b(?:persistence|persist|data solutions|database usage)\b")):
            if re.search(pattern, lower):
                activities.append(family)
        if len(activities) > 1:
            return "+".join(activities), None, "NEEDS_SCOPE_REVIEW", "Multiple database activities; preserve their boundaries instead of forcing one database.design relationship"
        if activities:
            return activities[0], None, "NEEDS_CAPABILITY_RESEARCH", "No native capability equivalence proven for this activity; database.design is not a universal database-use capability"
    if scoring._preserves_coherent_parent(text) or re.search(r"\b(?:or|such as|etc|frameworks|one or more)\b|[,;/]", lower):
        return "compound_or_example_scope", None, "BLOCKED_BY_PARSER_OR_NORMALIZATION", "Preserve native parent scope; identity mentions do not establish independent capability obligations"
    return "identity_or_unbounded_activity", None, "NO_RELATIONSHIP_JUSTIFIED", "Identity/familiarity or broad activity supplies no bounded existing-capability relationship"


def build_inventory(snapshot, actions, gap_rows):
    """Partition native relationship actions by technology AND requirement context."""
    raw = _records(snapshot["audit"]["corpus"])
    native = {(r["job_id"], r["requirement_id"]): r for r in snapshot["audit"]["requirements"]}
    by_candidate = {r["candidate_id"]: r for r in gap_rows}
    groups, inventory = {}, []
    for action in actions:
        if action["fix_layer"] != maintenance.RELATIONSHIP_GAP:
            continue
        source = by_candidate[action["candidate_id"]]
        identity = deepcopy(source.get("technology_identity") or {})
        if not identity.get("technology_id"):
            found = [registry.resolve_requirement_text(t) for t in source["candidate"].get("technology_terms", [])]
            known = {r["technology_id"]: r for r in found if r.get("technology_id")}
            if len(known) == 1:
                identity = next(iter(known.values()))
        traces = []
        for k in action["requirement_keys"]:
            key = k["job_id"], k["requirement_id"]
            row = raw[key]
            technology_id = identity.get("technology_id")
            family, capability, decision, why = context(row, technology_id)
            trace = {**k, "text": row["text"], "importance": row["importance"],
                "weight": gaps._weight(native[key]), "source_provenance": deepcopy(row.get("source_provenance", [])),
                "current_resolution": deepcopy(native[key]["current_resolution"]), "current_registry": deepcopy(row.get("technology_registry_resolution")),
                "technology_id": technology_id, "technology_label": identity.get("technology_label"),
                "context": family, "existing_capability_id": capability, "decision": decision, "why": why}
            traces.append(trace)
            group_key = technology_id or "unresolved:" + action["concept"], family, capability, decision
            group = groups.setdefault(group_key, {"technology_id": technology_id, "technology": identity.get("technology_label") or action["concept"],
                "context": family, "existing_capability_id": capability, "decision": decision, "why": why,
                "candidate_ids": set(), "action_ids": set(), "requirements": {}})
            group["candidate_ids"].add(action["candidate_id"]); group["action_ids"].add(action["action_id"])
            group["requirements"][key] = trace
        inventory.append({"action_id": action["action_id"], "candidate_id": action["candidate_id"], "concept": action["concept"],
            "technology_identity": deepcopy(identity), "taxonomy_overlaps": deepcopy(action["existing_taxonomy_overlaps"]),
            "candidate_capability_ids": sorted({r["existing_capability_id"] for r in traces if r["existing_capability_id"]}),
            "research_state": action["research_state"], "research_status": deepcopy(source["research_status"]),
            "readiness": deepcopy(source["readiness"]), "requirements": traces})
    candidates = []
    for key, group in sorted(groups.items(), key=lambda v: str(v[0])):
        rows = [group["requirements"][k] for k in sorted(group["requirements"])]
        unresolved = [r for r in rows if r["current_resolution"]["status"] != "resolved"]
        group.update(candidate_ids=sorted(group["candidate_ids"]), action_ids=sorted(group["action_ids"]), requirements=rows,
            relationship_id="contextreview_" + fingerprint(key)[:24], unique_unresolved_requirements=len(unresolved),
            jobs_affected=len({r["job_id"] for r in unresolved}),
            required_core_weight=round(sum(r["weight"] for r in unresolved if r["importance"] in {"required", "core", "deal_breaker"}), 6),
            estimated_impact=0, validated_impact=None, negative_boundaries=NEGATIVE_BOUNDARIES,
            profile=group["context"] if group["context"] in PROFILES else None,
            category="HIGH_CONFIDENCE_EXISTING_CAPABILITY_RELATIONSHIP" if group["context"] in PROFILES else
                "NEW_CAPABILITY_NEEDED" if group["decision"] == "NEEDS_CAPABILITY_RESEARCH" else
                "PARSER_STRUCTURE_BLOCKED" if group["decision"] == "BLOCKED_BY_PARSER_OR_NORMALIZATION" else "AMBIGUOUS_RELATIONSHIP",
            temporary_validation_possible=group["context"] in PROFILES,
            approval=False, publication=False)
        candidates.append(group)
    candidates.sort(key=lambda c: (-c["unique_unresolved_requirements"], -c["required_core_weight"], -c["jobs_affected"],
        not bool(c["existing_capability_id"]), not c["temporary_validation_possible"], c["relationship_id"]))
    for rank, c in enumerate(candidates, 1):
        c["rank"] = rank
    return maintenance._seal({"audit_fingerprint": snapshot["audit_fingerprint"], "implementation_fingerprint": _implementation(),
        "actions": inventory, "action_count": len(inventory), "candidates": candidates,
        "category_counts": dict(Counter(c["category"] for c in candidates)),
        "unique_requirement_count": len({(r["job_id"], r["requirement_id"]) for a in inventory for r in a["requirements"]}),
        "estimated_directly_resolved": 0, "validated_directly_resolved": None}, "inventory_fingerprint")


# Context-local hypothetical native registry lookup. Other threads/contexts keep
# the native lookup while this explicit offline preview is active. Refcounts
# prevent overlapping preview teardown from removing another preview's binding.
_active = ContextVar("contextual_relationship_review", default=())
_lock = RLock()
_users = 0
_native_lookup = None


def _lookup(text, **kwargs):
    profiles = [p for p in _active.get() if eligible(text, p)]
    if len(profiles) != 1:
        return _native_lookup(text, **kwargs)
    p = PROFILES[profiles[0]]
    native_registry = kwargs.get("registry") or registry.get_default_registry()
    entries = deepcopy(list(native_registry.entries))
    entry = next((e for e in entries if e["technology_id"] == p["technology_id"]), None)
    if entry is None:
        return _native_lookup(text, **kwargs)
    entry["aliases"] = list(dict.fromkeys(entry["aliases"] + [text]))
    # The native hypothetical mapping representation requires this status.
    # It exists only in a copied context-local registry; no human approval occurs.
    entry["capability_relationships"] = [{"capability_id": p["capability_id"], "relationship_type": "maps_to_capability", "status": "approved"}]
    shadow = registry.TechnologyRegistry(native_registry.version, tuple(entries))
    with registry.temporary_registry_scope(shadow):
        return _native_lookup(text, registry=shadow)


@contextmanager
def temporary_context_scope(profiles):
    global _users, _native_lookup
    if any(p not in PROFILES for p in profiles):
        raise ValueError("Unknown bounded contextual profile")
    with _lock:
        if not _users:
            _native_lookup = resolver.resolve_requirement_text
            resolver.resolve_requirement_text = _lookup
        _users += 1
    token = _active.set(tuple(sorted(set(profiles))))
    try:
        yield
    finally:
        _active.reset(token)
        with _lock:
            _users -= 1
            if not _users and resolver.resolve_requirement_text is _lookup:
                resolver.resolve_requirement_text = _native_lookup


def validate(snapshot, inventory, *, explicit_execution=False, db_path=None):
    if explicit_execution is not True:
        raise ValueError("Explicit offline relationship validation required")
    maintenance._require_current(snapshot, db_path)
    maintenance._intact(inventory, "inventory_fingerprint")
    if inventory["audit_fingerprint"] != snapshot["audit_fingerprint"] or inventory["implementation_fingerprint"] != _implementation():
        raise ValueError("Stale relationship inventory")
    baseline = snapshot["audit"]["summary"]
    profiles = sorted({c["profile"] for c in inventory["candidates"] if c["profile"]})
    reports = []
    # Empty combined replay is meaningful: no forced mapping merely to show gains.
    for selected in ([p] for p in profiles):
        reports.append(_replay_report(snapshot, selected))
    combined = _replay_report(snapshot, profiles)
    negatives = _negative_checks(profiles)
    decisions = []
    for c in inventory["candidates"]:
        replay = next((r for r in reports if r["profiles"] == [c["profile"]]), None)
        ready = (replay and replay["validation_status"] == "clean_temporary_replay" and
            bool(replay["newly_resolved"]) and all(n["passed"] for n in negatives) and not replay["evidence_label_deltas"])
        decisions.append({"relationship_id": c["relationship_id"], "decision": "READY_FOR_CONTEXTUAL_RELATIONSHIP_IMPLEMENTATION" if ready else c["decision"],
            "validated_impact": len(replay["newly_resolved"]) if replay else 0})
    report = {"audit_fingerprint": snapshot["audit_fingerprint"], "implementation_fingerprint": _implementation(),
        "inventory_fingerprint": inventory["inventory_fingerprint"], "profiles": profiles, "candidate_replays": reports, "combined": combined,
        "negative_checks": negatives, "candidate_decisions": decisions,
        "baseline": {k: baseline[k] for k in ("taxonomy_resolved_requirements", "taxonomy_unresolved_requirements", "required_core_weighted_coverage", "overall_weighted_coverage")},
        "production_writes": 0, "model_calls": 0, "network_calls": 0, "approval": False, "publication": False}
    maintenance._require_current(snapshot, db_path)
    return maintenance._seal(report, "validation_fingerprint")


def _negative_checks(profiles):
    examples = ("MongoDB", "Experience with MongoDB", "Administer MongoDB", "Query MongoDB", "Node.js", "Experience with Node.js",
        "Develop frontend interfaces using Node.js", "Build APIs using Node.js or Python", "Do not build APIs using Node.js",
        "Build APIs using tools such as Node.js", "Design MongoDB schema or PostgreSQL schema", "NET", ".NET")
    checks = []
    for text in examples:
        before = resolver.resolve_requirement_with_production_knowledge({"text": text})
        with temporary_context_scope(profiles):
            after = resolver.resolve_requirement_with_production_knowledge({"text": text})
        checks.append({"text": text, "passed": before == after, "before": before, "after": after})
    return checks


def report_current(snapshot, inventory, report):
    try:
        maintenance._intact(report, "validation_fingerprint")
        return (report["audit_fingerprint"] == snapshot["audit_fingerprint"] and
            report["inventory_fingerprint"] == inventory["inventory_fingerprint"] and
            report["implementation_fingerprint"] == _implementation() and maintenance.currentness(snapshot)["current"])
    except (KeyError, ValueError):
        return False


def _replay_report(snapshot, profiles):
    before = snapshot["audit"]["corpus"]
    original = _records(before)
    with offline_execution("Contextual relationship validation is offline"), temporary_context_scope(profiles):
        after = replay_current_corpus(before)
        audit = gaps.audit_corpus_resolution(corpus=after)
    if after["current_replay"]["jobs_blocked"]:
        raise ValueError("Complete frozen inputs required")
    updated = _records(after)
    bres = {(r["job_id"], r["requirement_id"]): r["current_resolution"] for r in snapshot["audit"]["requirements"]}
    ares = {(r["job_id"], r["requirement_id"]): r["current_resolution"] for r in audit["requirements"]}
    changed, unexpected, affected = [], [], []
    for key in sorted(original.keys() | updated.keys()):
        b, a = _receipt(original.get(key)), _receipt(updated.get(key))
        allowed = any(eligible((original.get(key) or {}).get("atomic_focus") or (original.get(key) or {}).get("text", ""), p) for p in profiles)
        row = {"job_id": key[0], "requirement_id": key[1], "before": b, "after": a,
            "newly_resolved": (bres.get(key) or {}).get("status") != "resolved" and (ares.get(key) or {}).get("status") == "resolved",
            "newly_unresolved": (bres.get(key) or {}).get("status") == "resolved" and (ares.get(key) or {}).get("status") != "resolved"}
        if allowed:
            affected.append(row)
        if b != a or bres.get(key) != ares.get(key):
            changed.append(row)
            if not allowed or any((b or {}).get(f) != (a or {}).get(f) for f in ("text", "importance", "group_weight_fraction", "source_provenance", "atomic_group_id")):
                unexpected.append({"job_id": key[0], "requirement_id": key[1], "reason": "outside_context_or_changed_parsing_allocation"})
    before_jobs = {j["job_id"]: j for j in before["jobs"]}
    for j in after["jobs"]:
        known = set(duplicate_credit_violations(before_jobs[j["job_id"]]["baseline_stable_analysis"], j["frozen_inputs"]["context"]))
        unexpected.extend({"job_id": j["job_id"], "reason": v} for v in duplicate_credit_violations(j["baseline_stable_analysis"], j["frozen_inputs"]["context"]) if v not in known)
    return {"profiles": profiles, "affected_requirements": affected, "changed_requirements": changed,
        "newly_resolved": [{"job_id": r["job_id"], "requirement_id": r["requirement_id"]} for r in changed if r["newly_resolved"]],
        "newly_unresolved": [{"job_id": r["job_id"], "requirement_id": r["requirement_id"]} for r in changed if r["newly_unresolved"]],
        "overlay": {k: audit["summary"][k] for k in ("taxonomy_resolved_requirements", "taxonomy_unresolved_requirements", "required_core_weighted_coverage", "overall_weighted_coverage")},
        "job_score_deltas": [{"job_id": j["job_id"], "before": before_jobs[j["job_id"]]["metrics"], "after": j["metrics"]} for j in after["jobs"] if j["metrics"] != before_jobs[j["job_id"]]["metrics"]],
        "evidence_label_deltas": [{"job_id": r["job_id"], "requirement_id": r["requirement_id"], "before": (r["before"] or {}).get("match_label"),
            "after": (r["after"] or {}).get("match_label")} for r in changed if (r["before"] or {}).get("match_label") != (r["after"] or {}).get("match_label")],
        "before_ranking": gaps._integrated_ranking(before), "after_ranking": gaps._integrated_ranking(after),
        "unexpected_changes": unexpected, "validation_status": "blocked" if unexpected else "clean_temporary_replay"}

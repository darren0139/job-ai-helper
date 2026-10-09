"""Governed identity-only adapter over native proposals, registry and corpus replay.

Artifacts are review receipts, never publication authority or candidate evidence.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from taxonomy_discovery import maintenance_service as maintenance
from taxonomy_discovery import corpus_gap_resolution as gaps
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.regression_corpus import replay_current_corpus, duplicate_credit_violations
from taxonomy_discovery.technology_registry import (
    TechnologyRegistry, get_default_registry, normalise, resolve_requirement_text,
    temporary_registry_scope,
)
from taxonomy_discovery.offline_execution import offline_execution


def _implementation():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def inspect_identity_gap(snapshot, candidate_id, *, db_path=None):
    maintenance._require_current(snapshot, db_path)
    row = next((r for r in snapshot["gap_rows"] if r["candidate_id"] == candidate_id), None)
    if not row or row["fix_layer"] != maintenance.IDENTITY_GAP:
        raise ValueError("Existing technology identity gap required; relationship/manual routes are separate")
    candidate = row["candidate"]
    terms = candidate.get("technology_terms") or [row["concept"]]
    resolutions = [resolve_requirement_text(t) for t in terms]
    if any(r["status"] != "unresolved" for r in resolutions):
        raise ValueError("Production identity already recognized or ambiguous; use relationship/manual review")
    return deepcopy(row)


def prepare_identity_proposal(snapshot, candidate_id, *, explicit_execution=False,
                              canonical_label=None, entry_kind=None, aliases=None, db_path=None):
    if explicit_execution is not True:
        raise ValueError("Explicit identity proposal preparation required")
    row = inspect_identity_gap(snapshot, candidate_id, db_path=db_path)
    candidate = row["candidate"]
    local = gaps._local_identity(row["concept"])
    label = canonical_label or (local or {}).get("canonical_name")
    kind = entry_kind or (local or {}).get("technology_kind")
    if not label or not kind:
        raise ValueError("No bounded local identity record; explicit identity details require human review")
    observed = candidate.get("technology_terms") or [row["concept"]]
    observed_keys = {normalise(t) for t in observed}
    selected = aliases if aliases is not None else [a for a in (local or {}).get("aliases", [label]) if normalise(a) in observed_keys]
    if (not selected or (not local and normalise(label) not in observed_keys)
            or any(normalise(a) not in observed_keys for a in selected)
            or kind not in {"language", "product", "platform", "framework", "runtime", "technology"}):
        raise ValueError("Aliases and label must be bounded observed entity terms; broad/invented aliases forbidden")
    registry = get_default_registry()
    technology_id = gaps._technology_id_for(label)
    collisions = [{"alias": alias, "technology_id": e["technology_id"]}
        for alias in selected for e in registry.entries
        if normalise(alias) in {normalise(a) for a in e["aliases"]}]
    if collisions or technology_id in registry.by_id():
        raise ValueError("Alias/identity collision with production registry")
    native = gaps._bootstrap_proposal(
        {"seed_id": candidate_id, "canonical_name": label},
        resolution_type="add_technology_identity",
        proposed_change={"technology_id": technology_id, "identity": {
            "canonical_name": label, "technology_kind": kind, "aliases": sorted(set(selected))}},
        matched=row["requirements"])
    proposal = {**native, "candidate_fingerprint": fingerprint(candidate),
        "audit_fingerprint": snapshot["audit_fingerprint"], "production_identity": snapshot["manifest"],
        "implementation_fingerprint": _implementation(),
        "canonical_technology_id": technology_id, "canonical_label": label,
        "aliases": sorted(set(selected)), "alias_collisions": collisions,
        "source_gap_ids": candidate.get("source_gap_ids", []),
        "affected_requirement_ids": sorted({r["requirement_id"] for r in row["requirements"]}),
        "affected_job_ids": sorted({r["job_id"] for r in row["requirements"]}),
        "current_registry_version": registry.version,
        "current_registry_fingerprint": fingerprint(registry.entries),
        "review_status": "pending_human_review", "validation_status": "not_validated",
        "estimated_impact": {"requirements": len(row["requirements"]), "jobs": len(row["job_ids"]),
            "impact_kind": "mentioned_requirements_not_direct_resolutions", "estimated_directly_resolvable": 0,
            "unresolved_required_core_weight": sum(gaps._weight(r) for r in row["requirements"]
                if r["importance"] in {"required", "core", "deal_breaker"})},
        "production_writes": 0, "model_calls": 0, "network_calls": 0}
    proposal.pop("proposal_fingerprint")
    proposal["proposal_id"] = "identitydraft_" + fingerprint(proposal)[:24]
    return maintenance._seal(proposal, "proposal_fingerprint")


def _check(snapshot, proposal, db_path):
    maintenance._intact(proposal, "proposal_fingerprint")
    row = inspect_identity_gap(snapshot, proposal["candidate_id"], db_path=db_path)
    if (proposal["audit_fingerprint"] != snapshot["audit_fingerprint"]
            or proposal["production_identity"] != snapshot["manifest"]
            or proposal["candidate_fingerprint"] != fingerprint(row["candidate"])
            or proposal["implementation_fingerprint"] != _implementation()):
        raise ValueError("Stale identity proposal; prepare a new preview")
    expected = prepare_identity_proposal(snapshot, proposal["candidate_id"], explicit_execution=True,
        canonical_label=proposal["canonical_label"], entry_kind=proposal["proposed_change"]["identity"]["technology_kind"],
        aliases=proposal["aliases"], db_path=db_path)
    if expected != proposal:
        raise ValueError("Identity-only proposal contract changed; prepare a new preview")
    return row


def _records(corpus):
    return {(j["job_id"], r["requirement_id"]): r for j in corpus["jobs"]
            for r in j["baseline_stable_analysis"]["canonical_requirements"]}


def _receipt(row):
    if row is None:
        return None
    weight = gaps._weight(row) if row.get("score_eligible", True) else 0.0
    return {**{k: deepcopy(row.get(k)) for k in (
        "requirement_id", "text", "atomic_focus", "importance", "score_eligible", "match_label",
        "match_value", "evidence", "capability_id", "capability_resolution_source",
        "technology_registry_resolution", "capability_taxonomy_cap_status", "validation_warnings",
        "capability_does_not_prove", "parent_requirement_id", "atomic_group_id", "group_weight_fraction",
        "structured_match_kind", "structured_match_group_mode", "structured_match_status", "source_provenance")},
        "weight": weight, "weighted_evidence_contribution": weight * float(row.get("match_value") or 0)}


def validate_identity_proposal(snapshot, proposal, *, explicit_execution=False, db_path=None):
    if explicit_execution is not True:
        raise ValueError("Explicit temporary registry validation required")
    detail = _check(snapshot, proposal, db_path)
    before = snapshot["audit"]["corpus"]
    registry = get_default_registry()
    # Native local proposal overlay builds copied entries. Keep production version:
    # this is private hypothetical knowledge, identified by the proposal fingerprint.
    _, native_registry = gaps._temporary_knowledge([proposal])
    shadow = TechnologyRegistry(registry.version, native_registry.entries)
    with offline_execution("Identity validation is offline"), temporary_registry_scope(shadow):
        after = replay_current_corpus(before)
        overlay_audit = gaps.audit_corpus_resolution(corpus=after)
        atomic_identity = resolve_requirement_text(proposal["canonical_label"])
    if after["current_replay"]["jobs_blocked"]:
        raise ValueError("Incomplete frozen inputs; validation unavailable")
    original, updated = _records(before), _records(after)
    affected = {tuple(k) for k in proposal["affected_requirement_keys"]}
    changes, receipts, unexpected = [], [], []
    before_res = {(r["job_id"], r["requirement_id"]): r["current_resolution"] for r in snapshot["audit"]["requirements"]}
    after_res = {(r["job_id"], r["requirement_id"]): r["current_resolution"] for r in overlay_audit["requirements"]}
    for key in sorted(original.keys() | updated.keys()):
        b, a = _receipt(original.get(key)), _receipt(updated.get(key))
        changed = b != a or before_res.get(key) != after_res.get(key)
        receipt = {"job_id": key[0], "requirement_id": key[1], "before": b, "after": a,
            "before_resolution": before_res.get(key), "after_resolution": after_res.get(key),
            "identity_changed": (b or {}).get("technology_registry_resolution") != (a or {}).get("technology_registry_resolution"),
            "canonicalization_changed": any((b or {}).get(k) != (a or {}).get(k) for k in ("text", "atomic_focus", "parent_requirement_id", "atomic_group_id")),
            "newly_resolved": (before_res.get(key) or {}).get("status") != "resolved" and (after_res.get(key) or {}).get("status") == "resolved",
            "newly_unresolved": (before_res.get(key) or {}).get("status") == "resolved" and (after_res.get(key) or {}).get("status") != "resolved",
            "compound_provenance": [p for p in detail["candidate"].get("provenance", []) if (p.get("job_id"), p.get("requirement_id")) == key],
            "still_unresolved_reason": (after_res.get(key) or {}).get("registry_reason") if (after_res.get(key) or {}).get("status") != "resolved" else None}
        receipt["native_components_before"] = ((b or {}).get("technology_registry_resolution") or {}).get("native_component_resolution")
        receipt["native_components_after"] = ((a or {}).get("technology_registry_resolution") or {}).get("native_component_resolution")
        if changed:
            changes.append(receipt)
            if key not in affected:
                unexpected.append({"job_id": key[0], "requirement_id": key[1], "reason": "changed_outside_candidate_provenance"})
            if any((b or {}).get(k) != (a or {}).get(k) for k in ("match_label", "evidence", "weighted_evidence_contribution", "capability_id", "capability_taxonomy_cap_status")):
                unexpected.append({"job_id": key[0], "requirement_id": key[1], "reason": "identity_only_draft_changed_evidence_capability_or_credit"})
        if key in affected:
            receipts.append(receipt)
    before_rank, after_rank = gaps._integrated_ranking(before), gaps._integrated_ranking(after)
    ranking_changes = [{"before": b, "after": a} for b in before_rank for a in after_rank if b["job_id"] == a["job_id"] and b != a]
    unexpected.extend({"job_id": c["after"]["job_id"], "reason": "identity_only_draft_changed_score_or_rank"} for c in ranking_changes)
    existing_invariants = []
    before_jobs = {j["job_id"]: j for j in before["jobs"]}
    for job in after["jobs"]:
        baseline_violations = set(duplicate_credit_violations(before_jobs[job["job_id"]]["baseline_stable_analysis"],
            before_jobs[job["job_id"]]["frozen_inputs"]["context"]))
        existing_invariants.extend({"job_id": job["job_id"], "reason": reason} for reason in sorted(baseline_violations))
        unexpected.extend({"job_id": job["job_id"], "reason": reason} for reason in duplicate_credit_violations(
            job["baseline_stable_analysis"], job["frozen_inputs"]["context"]) if reason not in baseline_violations)
    def metrics(audit):
        s = audit["summary"]
        return {k: s[k] for k in ("meaningful_technical_requirements", "taxonomy_resolved_requirements", "taxonomy_unresolved_requirements", "required_core_weighted_coverage", "overall_weighted_coverage")}
    _check(snapshot, proposal, db_path)
    report = {"proposal_id": proposal["proposal_id"], "proposal_fingerprint": proposal["proposal_fingerprint"],
        "audit_fingerprint": snapshot["audit_fingerprint"], "production_identity": snapshot["manifest"],
        "validation_status": "blocked" if unexpected else "ready_for_human_review",
        "estimated_impact": proposal["estimated_impact"], "validated_impact": {
            "atomic_identity_recognized": atomic_identity["technology_id"] == proposal["canonical_technology_id"],
            "requirements_with_recognized_native_component": sum(any(c["registry_resolution"].get("technology_id") == proposal["canonical_technology_id"]
                for c in (r["native_components_after"] or {}).get("components", [])) for r in receipts),
            "affected_parent_identities_recognized": sum((r["after"] or {}).get("technology_registry_resolution", {}).get("technology_id") == proposal["canonical_technology_id"] for r in receipts),
            "newly_resolved": sum(r["newly_resolved"] for r in changes),
            "newly_unresolved": sum(r["newly_unresolved"] for r in changes)},
        "atomic_identity_resolution": atomic_identity, "baseline": metrics(snapshot["audit"]), "temporary_overlay": metrics(overlay_audit),
        "affected_requirement_receipts": receipts, "all_changed_rows": changes, "unexpected_changes": unexpected,
        "existing_baseline_invariant_warnings": existing_invariants,
        "before_ranking": before_rank, "after_ranking": after_rank, "ranking_changes": ranking_changes,
        "canonicalization": [{"job_id": j["job_id"], "before": b["baseline_stable_analysis"].get("canonicalisation_debug"),
            "after": j["baseline_stable_analysis"].get("canonicalisation_debug")} for b in before["jobs"] for j in after["jobs"] if b["job_id"] == j["job_id"]],
        "review_status": "pending_human_review", "approval": False, "publication": False,
        "production_writes": 0, "model_calls": 0, "network_calls": 0}
    return maintenance._seal(report, "validation_fingerprint")


def markdown_report(proposal, report):
    return "# Technology identity — temporary validation\n\nHuman review required; no approval or publication.\n\n" + "\n\n".join(
        f"## {name}\n\n```json\n{json.dumps(value, indent=2)}\n```" for name, value in (
            ("Identity proposal", proposal), ("Estimated impact", report["estimated_impact"]),
            ("Validated impact", report["validated_impact"]), ("Baseline", report["baseline"]),
            ("Temporary overlay", report["temporary_overlay"]), ("Affected requirements", report["affected_requirement_receipts"]),
            ("All changed rows", report["all_changed_rows"]), ("Unexpected changes", report["unexpected_changes"]),
            ("Ranking", report["after_ranking"])))

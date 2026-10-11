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
        return {k: s[k] for k in ("meaningful_technical_requirements", "taxonomy_resolved_requirements", "taxonomy_unresolved_requirements",
            "capability_resolved_requirements", "technology_identity_resolved_requirements", "knowledge_resolved_requirements",
            "required_core_weighted_coverage", "overall_weighted_coverage")}
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


def prepare_identity_batch(snapshot, concepts, *, historical_pairs=(), explicit_execution=False, db_path=None):
    """Bounded local maintenance over existing proposals; not research or approval.

    Historical receipts supply identity details only. Every identity is checked
    again against native aliases, current corpus and complete-scope negatives.
    """
    from tailoring.requirement_scope import technology_identity_scope
    if explicit_execution is not True:
        raise ValueError("Explicit identity batch preparation required")
    maintenance._require_current(snapshot, db_path)
    native = get_default_registry()
    historical = {}
    for proposal, receipt in historical_pairs:
        maintenance._intact(proposal, "proposal_fingerprint")
        maintenance._intact(receipt, "validation_fingerprint")
        if (receipt.get("proposal_fingerprint") != proposal["proposal_fingerprint"]
                or receipt.get("validation_status") != "ready_for_human_review"
                or receipt.get("unexpected_changes") or proposal.get("resolution_type") != "add_technology_identity"):
            raise ValueError("Invalid historical identity receipt")
        historical[normalise(proposal["canonical_label"])] = proposal
    proposals, candidates, selected_ids = [], [], set()
    for concept in dict.fromkeys(concepts):
        local = gaps._local_identity(concept)
        candidate = {"identity": concept, "production_before": resolve_requirement_text(concept),
                     "temporary_decision": "DEFERRED", "production_decision": "NOT_PUBLISHED"}
        candidates.append(candidate)
        if not local or normalise(concept) in {"net", ".net", "microservices", "distributed systems", "cloud security"}:
            candidate["reason"] = "No bounded local identity definition; scope/normalization review required"
            continue
        label, aliases = local["canonical_name"], local["aliases"]
        tid = gaps._technology_id_for(label)
        if tid in selected_ids:
            candidate["reason"] = "Duplicate identity selection"
            continue
        selected_ids.add(tid)
        matched = gaps._seed_requirement_matches(snapshot["audit"], aliases)
        # The generic bootstrap helper deliberately excludes tiny prose tokens.
        # Selected local entity aliases containing digits (e.g. S3) have a
        # bounded native mention predicate; this is provenance, never resolution.
        short_entities = tuple(a for a in aliases if len(normalise(a)) == 2
                               and any(c.isdigit() for c in a))
        if short_entities:
            extra = [r for r in snapshot["audit"]["requirements"]
                     if gaps._technology_concept_present(r["requirement_text"], short_entities)]
            matched = list({(r["job_id"], r["requirement_id"]): r for r in matched + extra}.values())
        candidate.update(technology_id=tid, aliases=aliases, requirements_affected=len(matched))
        if not matched:
            candidate["reason"] = "No traceable current corpus mentions"
            continue
        owners = {normalise(a): e["technology_id"] for e in native.entries for a in e["aliases"]}
        collisions = [{"alias": a, "owner": owners[normalise(a)]} for a in aliases if normalise(a) in owners]
        candidate["collision_status"] = collisions or "CLEAR"
        if collisions or tid in native.by_id():
            candidate["reason"] = "Existing identity/alias: separate relationship or manual workflow"
            continue
        old = historical.get(normalise(label))
        if old and old["proposed_change"]["identity"] != local:
            raise ValueError("Historical identity details differ; manual review required")
        source = {"seed_id": "identitybatch_" + tid, "canonical_name": label}
        proposal = gaps._bootstrap_proposal(source, resolution_type="add_technology_identity",
            proposed_change={"technology_id": tid, "identity": deepcopy(local)}, matched=matched)
        _, temporary = gaps._temporary_knowledge([proposal])
        temporary = TechnologyRegistry(native.version, temporary.entries)
        def complete(text):
            row = {"text": text, "atomic_focus": text, "importance": "core", "source_provenance": [{
                "parent_occurrence_id": "bounded_negative_fixture", "parent_text": text,
                "raw_parent_text": text, "source": "raw_jd.requirements"}]}
            return technology_identity_scope(row, registry=temporary)["identity_resolved"]
        positive = all(resolve_requirement_text(a, registry=temporary).get("technology_id") == tid
                       and complete(a) for a in aliases)
        negative_texts = [a + "ish" for a in aliases] + ["prefix" + a for a in aliases] + [
            f"{concept} for building internal tools", f"{concept} for architecting cloud solutions",
            f"Build APIs using {concept}", f"Experience with {concept} and teamwork"]
        negative = all(not complete(text) for text in negative_texts)
        candidate.update(proposal_source="historical_revalidated" if old else "existing_local_identity_vocabulary",
            historical_proposal_fingerprint=old.get("proposal_fingerprint") if old else None,
            normalization={a: normalise(a) for a in aliases}, negative_cases=negative_texts,
            temporary_decision="INDIVIDUALLY_VALIDATED" if positive and negative else "UNSAFE",
            proposal_id=proposal["proposal_id"])
        if positive and negative:
            proposals.append(proposal)
    return maintenance._seal({"audit_fingerprint": snapshot["audit_fingerprint"],
        "production_identity": snapshot["manifest"], "implementation_fingerprint": _implementation(),
        "candidates": candidates, "proposals": proposals, "approval": False, "publication": False}, "batch_fingerprint")


def validate_identity_batch(snapshot, batch, *, explicit_execution=False, db_path=None):
    """Native full frozen replay. Neither versions nor diagnostics are evidence."""
    from tailoring.requirement_scope import technology_identity_scope
    if explicit_execution is not True:
        raise ValueError("Explicit combined identity replay required")
    maintenance._require_current(snapshot, db_path)
    maintenance._intact(batch, "batch_fingerprint")
    if (batch["audit_fingerprint"] != snapshot["audit_fingerprint"]
            or batch["implementation_fingerprint"] != _implementation()):
        raise ValueError("Stale identity batch")
    before = snapshot["audit"]["corpus"]
    _, shadow = gaps._temporary_knowledge(batch["proposals"])
    shadow = TechnologyRegistry(get_default_registry().version, shadow.entries)
    expected = {k for k, r in _records(before).items()
                if technology_identity_scope(r, registry=shadow)["identity_resolved"]
                and not r.get("capability_id")}
    with offline_execution("Technology maintenance forbids external research"), temporary_registry_scope(shadow):
        after = replay_current_corpus(before)
        audit = gaps.audit_corpus_resolution(corpus=after)
    report = _batch_replay_receipt(snapshot["audit"], audit, expected_identity_keys=expected)
    report.update(batch_fingerprint=batch["batch_fingerprint"], audit_fingerprint=snapshot["audit_fingerprint"],
                  production_identity=snapshot["manifest"], implementation_fingerprint=_implementation())
    maintenance._require_current(snapshot, db_path)
    return maintenance._seal(report, "validation_fingerprint"), audit


def _batch_replay_receipt(before_audit, after_audit, *, expected_identity_keys):
    before, after = before_audit["corpus"], after_audit["corpus"]
    original, updated = _records(before), _records(after)
    unexpected, evidence, capabilities = [], [], []
    for key in sorted(original.keys() | updated.keys()):
        b, a = _receipt(original.get(key)), _receipt(updated.get(key))
        # Native registry metadata may change with an identity publication. All
        # actual capability, evidence, allocation and provenance fields stay pinned.
        for row in (b, a):
            if row is not None:
                row.pop("technology_registry_resolution", None)
        if b != a:
            evidence.append(list(key))
        if (original.get(key) or {}).get("capability_id") != (updated.get(key) or {}).get("capability_id"):
            capabilities.append(list(key))
    bres = {(r["job_id"], r["requirement_id"]): r["current_resolution"] for r in before_audit["requirements"]}
    ares = {(r["job_id"], r["requirement_id"]): r["current_resolution"] for r in after_audit["requirements"]}
    identities = {k for k, r in ares.items() if r["knowledge_status"] == "TECHNOLOGY_IDENTITY_RESOLVED"}
    if identities != expected_identity_keys:
        unexpected = [list(k) for k in sorted(identities ^ expected_identity_keys)]
    newly = [list(k) for k in sorted(ares) if ares[k]["status"] == "resolved" and bres.get(k, {}).get("status") != "resolved"]
    unresolved = [list(k) for k in sorted(bres) if bres[k]["status"] == "resolved" and ares.get(k, {}).get("status") != "resolved"]
    rankings = gaps._integrated_ranking(before), gaps._integrated_ranking(after)
    violations = [{"job_id": j["job_id"], "reason": v} for j in after["jobs"]
                  for v in duplicate_credit_violations(j["baseline_stable_analysis"], j["frozen_inputs"]["context"])]
    blocked = after.get("current_replay", {}).get("jobs_blocked", 0)
    clean = not (evidence or capabilities or unexpected or unresolved or violations or blocked or rankings[0] != rankings[1])
    return {"validation_status": "VALIDATED_SAFE" if clean else "UNSAFE", "new_identity_resolutions": newly,
        "new_capability_resolutions": capabilities, "newly_unresolved": unresolved, "unexpected_changes": unexpected,
        "evidence_deltas": evidence, "ranking_deltas": [] if rankings[0] == rankings[1] else rankings,
        "frozen_or_duplicate_violations": violations, "jobs_blocked": blocked, "jobs_replayed": len(after["jobs"]),
        "baseline": before_audit["summary"], "temporary": after_audit["summary"], "ranking": rankings[1],
        "provider_calls": 0, "network_calls": 0, "model_calls": 0, "approval": False, "publication": False}


def publish_identity_batch(snapshot, batch, validation, *, explicit_publish=False, authorized_ids=(), db_path=None):
    """Explicit human-authorized native registry file update, no local DB writes.

    The existing atomic knowledge replacement is reused. This is a repository
    maintenance adapter, not an automatic UI approval/publication path.
    """
    from taxonomy_discovery import technology_registry as registry_module
    from taxonomy_discovery.governed_publication import _next_version
    from database.technology_registry_proposal_manager import _replace_knowledge
    if explicit_publish is not True:
        raise ValueError("Explicit human-authorized identity publication required")
    maintenance._require_current(snapshot, db_path)
    maintenance._intact(batch, "batch_fingerprint")
    maintenance._intact(validation, "validation_fingerprint")
    selected = {p["proposed_change"]["technology_id"] for p in batch["proposals"]}
    individually_safe = {c.get("technology_id") for c in batch["candidates"]
                         if c["temporary_decision"] == "INDIVIDUALLY_VALIDATED"}
    if (set(authorized_ids) != selected or not selected
            or selected != individually_safe
            or validation["validation_status"] != "VALIDATED_SAFE"
            or validation["batch_fingerprint"] != batch["batch_fingerprint"]
            or validation["production_identity"] != snapshot["manifest"]
            or batch["audit_fingerprint"] != snapshot["audit_fingerprint"]
            or validation["implementation_fingerprint"] != _implementation()):
        raise ValueError("Current individually/combined-safe batch and exact authorization required")
    for proposal in batch["proposals"]:
        change = proposal["proposed_change"]
        if (proposal["resolution_type"] != "add_technology_identity"
                or set(change) != {"technology_id", "identity"}
                or change["identity"] != gaps._local_identity(proposal["technology"])):
            raise ValueError("Identity proposal differs from bounded local definition")
    path = Path(registry_module.REGISTRY_PATH)
    original = path.read_bytes()
    raw = json.loads(original)
    _, shadow = gaps._temporary_knowledge(batch["proposals"])
    entries = deepcopy(list(shadow.entries))
    if any(e.get("capability_relationships") for e in entries if e["technology_id"] in selected):
        raise ValueError("Identity publication cannot create capability mappings")
    for entry in entries:
        if entry["technology_id"] in selected:
            entry["notes"] = "Explicitly authorized identity-only maintenance; no capability mapping."
    raw.update(entries=entries, registry_version=_next_version(raw["registry_version"], "technology-registry-v"))
    encoded = (json.dumps(raw, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    _replace_knowledge(path, original, encoded, registry_module.load_registry)
    return {"identities_added": sorted(selected), "version_before": snapshot["manifest"]["technology_registry_version"],
        "version_after": raw["registry_version"], "artifact_hash_before": hashlib.sha256(original).hexdigest(),
        "artifact_hash_after": hashlib.sha256(encoded).hexdigest(), "batch_fingerprint": batch["batch_fingerprint"],
        "validation_fingerprint": validation["validation_fingerprint"], "explicit_human_authorization": True,
        "publication": True, "capability_mappings_added": 0}

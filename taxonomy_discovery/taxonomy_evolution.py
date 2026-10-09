"""H.0 research inputs, proposal-only drafts and offline taxonomy review.

There is deliberately no production taxonomy writer or automatic researcher.
"""

from taxonomy_discovery.offline_execution import offline_execution
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import re

from tailoring.capability_taxonomy import (CapabilityTaxonomy, TAXONOMY_PATH,
    _validate_capability, classify_requirement_record, get_default_taxonomy, load_taxonomy, normalise)
from rag.capability_taxonomy_rag import lexical_retrieve
from job_discovery.matching import _default_stable_builder, current_match_versions
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.regression_corpus import (CORPUS_VERSION, compare_regression_corpus,
    requirement_records, job_metrics, duplicate_credit_violations)
from taxonomy_discovery.source_authority import classify_candidate_source_url, PRIMARY_OFFICIAL, FIRST_PARTY_OTHER
from taxonomy_discovery.taxonomy_gaps import GAP_VERSION
from taxonomy_discovery.technology_registry import resolve_requirement_text, get_default_registry
from taxonomy_discovery.research_targets import _strict_unknown_terms
from taxonomy_discovery.candidate_refinement import (concept_key, semantic_overlap,
    technology_entities, route_candidate, capability_context, REFINEMENT_VERSION)

PROPOSAL_VERSION = "tqd3-taxonomy-proposal-v1"
ROUTES = ("technology_identity", "technology_relationship", "existing_capability_resolver_issue",
    "possible_new_capability", "ambiguous_or_noise", "administrative_or_non_capability", "insufficient_signal")
DECISIONS = ("undecided", "research_more", "defer", "reject", "approve_for_publication")


def overlap_check(text, *, taxonomy=None):
    taxonomy = taxonomy or get_default_taxonomy()
    exact = classify_requirement_record({"text":text},taxonomy)
    semantic_text=capability_context(text)
    supported_canonical=classify_requirement_record({"text":semantic_text},taxonomy)
    registry_resolution = resolve_requirement_text(text)
    lexical = lexical_retrieve(text, taxonomy=taxonomy, top_k=5)
    words = set(normalise(text).split()) - {"experience","with","the","and","of","in","a","to","knowledge","required"}
    concepts = []
    for entry in taxonomy.capabilities:
        phrases = [entry["label"], *(entry.get("requirement") or {}).get("any_terms", [])]
        for values in (entry.get("evidence_concepts") or {}).values():
            phrases.extend(values)
        phrases.extend([entry.get("definition", "")])
        tokens = set(normalise(" ".join(phrases)).split())
        common = sorted(words & tokens)
        if common:
            concepts.append({"capability_id":entry["capability_id"],"domain":entry["domain"],
                "common_concepts":common,"score":round(len(common)/max(1,len(words)),6)})
    concepts.sort(key=lambda r:(-r["score"],r["capability_id"]))
    high = semantic_overlap(semantic_text,taxonomy)
    conflicts = sorted({r["domain"] for r in high}) if len({r["domain"] for r in high}) > 1 else []
    exact_ids = [exact["capability_id"]] if exact else [registry_resolution["capability_id"]] if registry_resolution["status"] == "resolved" else []
    return {"taxonomy_version":taxonomy.version,"exact_matches":exact_ids, "existing_registry_resolution":registry_resolution,
        "canonical_match":exact["capability_id"] if exact else None,
        "semantic_resolver_evidence":bool(supported_canonical or registry_resolution["status"]=="resolved" or high),
        "canonical_match_product_context_conflict":bool(exact and not supported_canonical),
        "requirement_phrase_product_context_conflict":bool(semantic_overlap(text,taxonomy) and not high),
        "token_overlap_is_lexical_only":True,
        "lexical_retrieval":lexical, "high_overlap_candidates":high, "concept_overlap":concepts[:5],
        "conflicting_domains":conflicts, "vector_retrieval":"disabled_offline_no_embeddings",
        "diagnostic_only":True, "automatic_equivalence":False}


def gap_candidates(artifact):
    if artifact.get("gap_version") != GAP_VERSION:
        raise ValueError("Unsupported governed gap schema")
    candidates = []
    for gap in artifact["observations"]:
        if gap.get("research_input_only") is not True or not gap.get("gap_id"):
            raise ValueError("Gap must retain research-input-only provenance")
        candidate = deepcopy(gap)  # Preserve all Phase G fields, including observed versions.
        text = " ".join(gap.get("examples") or [gap.get("normalized_cluster", "")])
        overlap = overlap_check(text)
        entities=technology_entities(text,gap.get("technology_terms",[]))
        route,reason=route_candidate(gap,text,overlap,entities)
        candidate.update(concept_key=concept_key(gap["normalized_cluster"]),routing_reason=reason,
            refinement_version=REFINEMENT_VERSION,technology_entity_diagnostics=entities,
            observed_job_count=gap["job_count"],observed_occurrence_count=gap["occurrence_count"],
            recurrence_priority="repeated_cross_job" if gap["job_count"]>1 else "single_job",
            research_priority="repeated_cross_job_review" if gap["job_count"]>1 else "single_job_review",
            review_priority="repeated_cross_job_review" if gap["job_count"]>1 else "single_job_review")
        candidate.update(candidate_route=route, overlap=overlap,
            current_versions=current_match_versions(), source_gap_ids=[gap["gap_id"]],
            observed_scoring_versions=sorted({p.get("observed_versions",{}).get("scoring_version", "unknown") for p in gap.get("provenance",[])}),
            observed_taxonomy_versions=sorted({p.get("observed_versions",{}).get("taxonomy_version", "unknown") for p in gap.get("provenance",[])}),
            observed_registry_versions=sorted({p.get("observed_versions",{}).get("technology_registry_version", "unknown") for p in gap.get("provenance",[])}))
        candidate["candidate_fingerprint"] = fingerprint(candidate)
        candidate["candidate_id"] = "tqd3taxgap_"+candidate["candidate_fingerprint"][:24]
        candidates.append(candidate)
    return candidates


def research_target(candidate, *, domain_hypothesis=None):
    if candidate.get("candidate_fingerprint") != fingerprint({k:v for k,v in candidate.items() if k not in {"candidate_fingerprint","candidate_id"}}):
        raise ValueError("Candidate fingerprint stale/edited")
    if candidate["candidate_route"] != "possible_new_capability":
        raise ValueError("Only possible-new-capability inputs enter taxonomy research")
    target = {"candidate":deepcopy(candidate),"domain_hypothesis":domain_hypothesis,
        "questions":[
            f"Does {candidate['normalized_cluster']} represent a distinct software-engineering capability, rather than a technology or administrative requirement?",
            "What common industry terminology and first-party definitions describe this capability?",
            "What boundaries distinguish it from the listed existing taxonomy overlap candidates?",
            "What observable candidate evidence would demonstrate it, and what does not prove it?"],
        "current_versions":current_match_versions(),"research_input_only":True}
    target["target_fingerprint"] = fingerprint(target)
    return target


def research_with_transport(target, *, transport, explicit_execution=False, authority_registry_path=None):
    """Injected transport only in H.0; no configured live provider/default network path."""
    if explicit_execution is not True or not callable(transport):
        raise ValueError("Research requires explicit execution and an injected transport")
    if fingerprint({k:v for k,v in target.items() if k != "target_fingerprint"}) != target["target_fingerprint"]:
        raise ValueError("Research target edited")
    if target["current_versions"] != current_match_versions():
        raise ValueError("Research target stale")
    raw = transport(deepcopy(target))
    if not isinstance(raw,dict) or not raw.get("request_id") or not isinstance(raw.get("results"),list):
        raise ValueError("Raw research request identity/results required")
    subject = {"canonical_name":target["candidate"]["normalized_cluster"]}
    classified = [{"evidence":deepcopy(row), "classification":classify_candidate_source_url(subject,row.get("url",""),registry_path=authority_registry_path)}
        for row in raw["results"] if isinstance(row,dict)]
    return {"target":deepcopy(target), "raw_provider_evidence":deepcopy(raw),
        "request_id":raw["request_id"],"sources":classified,"evidence_fingerprint":fingerprint(raw),
        "created_at":datetime.now(timezone.utc).isoformat(),"approval":False}


def proposal_fingerprint(proposal):
    # IDs/timestamps/derived fingerprints are not capability semantics. Everything
    # else, including source provenance, research/overlap and native evidence tiers, is material.
    return fingerprint({k:v for k,v in proposal.items() if k not in {"proposal_id","proposal_fingerprint","created_at"}})


def draft_proposal(candidate, research, *, capability_id, label, domain, definition,
                   match_concepts, does_not_prove, evidence_expectations, aliases=None, parent=None):
    if candidate["candidate_route"] != "possible_new_capability":
        raise ValueError("Overlap/technology/admin routes cannot become capability drafts")
    research_target(candidate)  # Validate retained candidate identity before deriving a draft.
    target=research.get("target",{})
    if target.get("target_fingerprint") != fingerprint({k:v for k,v in target.items() if k!="target_fingerprint"}):
        raise ValueError("Research target fingerprint stale/edited")
    if research.get("evidence_fingerprint") != fingerprint(research.get("raw_provider_evidence")):
        raise ValueError("Research evidence fingerprint stale/edited")
    if research.get("target",{}).get("candidate",{}).get("candidate_fingerprint") != candidate["candidate_fingerprint"]:
        raise ValueError("Research does not belong to this gap candidate")
    if research["target"]["current_versions"] != current_match_versions():
        raise ValueError("Research base versions stale")
    proposal = {"proposal_schema_version":PROPOSAL_VERSION,"taxonomy_base_version":get_default_taxonomy().version,
        "taxonomy_base_fingerprint":fingerprint(get_default_taxonomy().capabilities),
        "taxonomy_base_bytes_fingerprint":fingerprint(TAXONOMY_PATH.read_bytes().hex()),
        "current_versions":current_match_versions(),"proposed_capability_id":capability_id,"proposed_label":label,
        "domain":domain,"parent":parent,"definition":definition,"positive_match_concepts":deepcopy(match_concepts),
        "aliases":deepcopy(aliases or []),"does_not_prove":deepcopy(does_not_prove),
        "evidence_expectations":deepcopy(evidence_expectations),"source_gap_ids":deepcopy(candidate["source_gap_ids"]),
        "source_provenance":deepcopy(candidate["provenance"]), "occurrence_count":candidate["occurrence_count"],
        "distinct_job_count":candidate["job_count"],"examples":deepcopy(candidate["examples"]),
        "gap_candidate":deepcopy(candidate), "research_evidence":deepcopy(research),
        "overlap":deepcopy(candidate["overlap"]),"proposal_status":"proposal_only",
        "created_at":datetime.now(timezone.utc).isoformat()}
    proposal["proposal_fingerprint"] = proposal_fingerprint(proposal)
    proposal["proposal_id"] = "tqd3taxproposal_"+proposal["proposal_fingerprint"][:24]
    _entry(proposal, get_default_taxonomy(), set(get_default_taxonomy().by_id()))
    return proposal


def _entry(proposal, base, seen):
    if proposal.get("proposal_schema_version") != PROPOSAL_VERSION or proposal.get("proposal_status") != "proposal_only":
        raise ValueError("Schema requires a proposal-only draft")
    if proposal.get("proposal_fingerprint") != proposal_fingerprint(proposal):
        raise ValueError("Proposal fingerprint stale/edited")
    if proposal.get("proposal_id") != "tqd3taxproposal_"+proposal["proposal_fingerprint"][:24]:
        raise ValueError("Proposal identity does not match its semantics")
    if proposal["taxonomy_base_version"] != base.version:
        raise ValueError("Proposal base taxonomy stale")
    if proposal.get("taxonomy_base_fingerprint") != fingerprint(base.capabilities) or proposal.get("taxonomy_base_bytes_fingerprint") != fingerprint(TAXONOMY_PATH.read_bytes().hex()):
        raise ValueError("Proposal base taxonomy contents changed")
    if fingerprint(load_taxonomy(TAXONOMY_PATH).capabilities) != fingerprint(base.capabilities):
        raise ValueError("Loaded production taxonomy differs from cached base; refresh before review")
    if proposal.get("domain") not in {r["domain"] for r in base.capabilities}:
        raise ValueError("Invalid domain: H.0 requires an existing domain")
    parent = proposal.get("parent")
    if parent and (parent not in base.by_id() or base.by_id()[parent]["domain"] != proposal["domain"]):
        raise ValueError("Invalid parent/domain reference")
    for field in ("positive_match_concepts", "aliases", "does_not_prove"):
        values = proposal.get(field)
        if not isinstance(values,list) or any(not isinstance(v,str) or not v.strip() for v in values):
            raise ValueError("Invalid string concepts/boundaries/aliases")
    if not proposal["positive_match_concepts"] or not proposal["does_not_prove"] or not str(proposal.get("definition","")).strip():
        raise ValueError("Definition, positive concepts and explicit boundaries required")
    expectations = proposal.get("evidence_expectations")
    if not isinstance(expectations,dict) or not isinstance(expectations.get("policy_references"),list) or not expectations["policy_references"] or any(not isinstance(p,str) or not p.strip() for p in expectations["policy_references"]):
        raise ValueError("Evidence expectations/policy references required")
    entry = {"capability_id":proposal["proposed_capability_id"],"label":proposal["proposed_label"],
        "domain":proposal["domain"], "priority":max(r["priority"] for r in base.capabilities)+1,
        "definition":proposal["definition"], "parent":parent,
        "requirement":{"any_terms":proposal["positive_match_concepts"]+proposal["aliases"]},
        "evidence_tiers":deepcopy(expectations.get("evidence_tiers")),"does_not_prove":proposal["does_not_prove"]}
    if not isinstance(entry["evidence_tiers"],list) or any(not isinstance(t,dict) for t in entry["evidence_tiers"]):
        raise ValueError("Evidence tiers must be a list of objects")
    _validate_capability(entry,seen)
    # Tighten schema where the historical loader allowed loosely typed tiers.
    for tier in entry["evidence_tiers"]:
        for key in ("any_terms","all_terms"):
            if key in tier and (not isinstance(tier[key],list) or any(not isinstance(t,str) or not t.strip() for t in tier[key])):
                raise ValueError("Invalid evidence-tier terms")
        groups = tier.get("all_groups",[])
        if not isinstance(groups,list) or any(not isinstance(g,list) or not g or any(not isinstance(t,str) or not t.strip() for t in g) for g in groups):
            raise ValueError("Invalid evidence-tier groups")
        if tier["label"] != "none" and not any(tier.get(k) for k in ("any_terms","all_terms","all_groups")):
            raise ValueError("Positive evidence tiers require explicit predicates")
    return entry


def temporary_overlay(proposals):
    if not proposals:
        raise ValueError("Explicit selected review/test proposals required")
    base = get_default_taxonomy()
    entries = deepcopy(list(base.capabilities))
    seen = set(base.by_id())
    for proposal in sorted(proposals,key=lambda p:p["proposal_id"]):
        entries.append(_entry(proposal,base,seen))
    identity = fingerprint({"base":base.version,"base_capabilities":base.capabilities,
        "proposals":sorted(p["proposal_fingerprint"] for p in proposals)})
    return CapabilityTaxonomy(version=base.version+"+proposal-"+identity[:24],capabilities=tuple(entries))


def temporary_regression(corpus, proposals):
    """Compare current production vs isolated vNext, preserving frozen inputs and original violations."""
    if corpus.get("corpus_version") != CORPUS_VERSION:
        raise ValueError("Unsupported frozen corpus")
    overlay = temporary_overlay(proposals)
    baseline = deepcopy(corpus)
    with offline_execution('Offline taxonomy review'):
        for job in baseline["jobs"]:
            if not job["replay_available"]:
                continue
            inputs=job["frozen_inputs"]
            violations=duplicate_credit_violations(job["baseline_stable_analysis"],inputs["context"])
            from job_discovery.matching import build_profile_evidence_context
            if build_profile_evidence_context(inputs["evidence_snapshot"]) != inputs["context"]:
                violations.append("Frozen context disagrees with evidence")
            if violations:
                # Do not erase snapshot invariant failures by constructing a cleaner baseline.
                job["original_invariant_violations"] = violations
            stable=_default_stable_builder(raw_jd_text=inputs["raw_jd_text"],jd_profile=inputs["jd_profile"],context=inputs["context"])
            job["baseline_stable_analysis"]=stable
            job["requirements"]=requirement_records(stable,job_id=job["job_id"],snapshot_id=job["snapshot_id"])
            job["metrics"]=job_metrics(stable,job["requirements"])
            job["versions"]={"taxonomy_version":stable["capability_taxonomy_version"],"scoring_version":stable["scoring_version"],
                "technology_registry_version":stable["technology_registry_version"]}
    report=compare_regression_corpus(baseline,temporary_taxonomy=overlay)
    by_cap={p["proposed_capability_id"]:p["proposal_id"] for p in proposals}
    for job in report["jobs"]:
        original=next(j for j in baseline["jobs"] if j["job_id"]==job["job_id"] and j["snapshot_id"]==job["snapshot_id"])
        if original.get("original_invariant_violations"):
            job["duplicate_credit_violations"]=job.get("duplicate_credit_violations",[])+original["original_invariant_violations"]
            job["classification"]="hard_regression/invariant_violation"
        for change in job.get("requirement_changes",[]):
            ids={by_cap[r["capability_id"]] for r in (change.get("before"),change.get("after")) if r and r.get("capability_id") in by_cap}
            change["responsible_proposal_ids"]=sorted(ids)
            change["selected_tranche_proposal_ids"]=sorted(p["proposal_id"] for p in proposals)
            change["interaction_review_required"]=len(proposals)>1
    report.update(classification_counts=dict(Counter(j["classification"] for j in report["jobs"])),
        proposal_fingerprints=sorted(p["proposal_fingerprint"] for p in proposals),
        current_versions=current_match_versions(), corpus_fingerprint=fingerprint(corpus),
        production_taxonomy_bytes_fingerprint=fingerprint(TAXONOMY_PATH.read_bytes().hex()),
        affected_jobs=[j["job_id"] for j in report["jobs"] if j.get("requirement_changes")],
        single_or_tranche="single" if len(proposals)==1 else "tranche", review_only=True)
    report["regression_fingerprint"]=fingerprint(report)
    return report


def publication_preflight(proposals, decisions, regression, *, corpus, authority_registry_path=None):
    """Pure test/review preflight. A green result exposes no production writer."""
    blockers=[]
    try:
        overlay=temporary_overlay(proposals)
    except (ValueError,TypeError,KeyError) as exc:
        return {"eligible_for_future_publication":False,"blockers":[str(exc)],
            "production_writes":0,"publication_available":False,"all_or_nothing":True}
    if regression.get("regression_fingerprint") != fingerprint({k:v for k,v in regression.items() if k!="regression_fingerprint"}):
        blockers.append("Regression report fingerprint invalid")
    if regression.get("current_versions") != current_match_versions() or regression.get("corpus_fingerprint") != fingerprint(corpus):
        blockers.append("Regression inputs/versions stale")
    if regression.get("production_taxonomy_bytes_fingerprint") != fingerprint(TAXONOMY_PATH.read_bytes().hex()):
        blockers.append("Production taxonomy changed")
    if regression.get("proposal_fingerprints") != sorted(p["proposal_fingerprint"] for p in proposals):
        blockers.append("Regression tranche differs")
    if overlay and regression.get("temporary_taxonomy_identity") != overlay.version:
        blockers.append("Temporary taxonomy identity differs")
    if not regression.get("jobs") or any(not j.get("available") or j.get("duplicate_credit_violations") or j["classification"]=="hard_regression/invariant_violation" for j in regression.get("jobs",[])):
        blockers.append("Regression unavailable or hard invariant failed")
    for proposal in proposals:
        pid=proposal["proposal_id"]
        decision=decisions.get(pid,{})
        if decision.get("decision") != "approve_for_publication" or not str(decision.get("reviewer","")).strip() or decision.get("proposal_fingerprint") != proposal["proposal_fingerprint"]:
            blockers.append(pid+": explicit current human approval required")
        if decision.get("regression_fingerprint") != regression.get("regression_fingerprint"):
            blockers.append(pid+": human must review this regression report")
        if proposal.get("current_versions") != current_match_versions():
            blockers.append(pid+": draft knowledge versions stale")
        if not proposal.get("source_gap_ids") or not proposal.get("source_provenance") or not proposal.get("distinct_job_count"):
            blockers.append(pid+": source gap provenance missing")
        provenance=proposal.get("source_provenance",[])
        if any(not all(p.get(k) is not None for k in ("job_id","snapshot_id","requirement_id","job_content_hash","observed_versions")) for p in provenance):
            blockers.append(pid+": incomplete source provenance")
        if len({p.get("job_id") for p in provenance}) != proposal.get("distinct_job_count") or proposal.get("occurrence_count",0) < len(provenance):
            blockers.append(pid+": provenance counts inconsistent")
        fresh_overlap=overlap_check(" ".join(proposal["positive_match_concepts"]))
        if fresh_overlap["exact_matches"] or fresh_overlap["high_overlap_candidates"] or proposal["overlap"].get("conflicting_domains"):
            blockers.append(pid+": overlap/conflict unresolved or proposal obsolete")
        research=proposal.get("research_evidence",{})
        if not research.get("raw_provider_evidence") or research.get("evidence_fingerprint") != fingerprint(research.get("raw_provider_evidence")):
            blockers.append(pid+": raw research evidence missing/edited")
        subject={"canonical_name":proposal.get("gap_candidate",{}).get("normalized_cluster","")}
        raw_sources=research.get("raw_provider_evidence",{}).get("results",[])
        if not any(isinstance(s,dict) and classify_candidate_source_url(subject,s.get("url",""),registry_path=authority_registry_path)["authority"] in {PRIMARY_OFFICIAL,FIRST_PARTY_OTHER}
                   and any(normalise(term) in normalise(s.get("content","")) for term in proposal["positive_match_concepts"]) for s in raw_sources):
            blockers.append(pid+": first-party supporting evidence required")
    return {"eligible_for_future_publication":not blockers,"blockers":blockers,
        "production_writes":0,"publication_available":False,"all_or_nothing":True}

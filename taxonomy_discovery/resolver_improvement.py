"""Proposal-only resolver phrase support, evaluated with the native temporary scope."""
from copy import deepcopy
from tailoring.capability_taxonomy import CapabilityTaxonomy, get_default_taxonomy, normalise, _contains
from taxonomy_discovery.corpus_expansion import fingerprint

RESOLVER_DRAFT_VERSION = "tqd3-resolver-improvement-h1.2-v1"
PRODUCT_CONTEXT_GUARD = "exclude_recognized_multiword_technology_spans"


def resolver_draft(result):
    c = result["candidate"]
    from tailoring.requirement_scope import API_RECOGNITION_FALLBACK, bounded_api_development_scope
    bounded=c.get('requested_recognition_rule')==API_RECOGNITION_FALLBACK
    local = result["existing_capability_assessment"]
    hypotheses = local["high_overlap_candidates"]
    ids = {r["capability_id"] for r in hypotheses}
    if bounded:
        if not bounded_api_development_scope(c.get('recognition_requirement',{})) or c.get('examples')!=[c['recognition_requirement']['text']]:
            raise ValueError('Complete source-bound API obligation required')
        ids={'backend.api_development'}
    if len(ids)!=1 or any(r.get("unmet_requirement_groups") for r in hypotheses):
        raise ValueError("Resolver improvement requires one unambiguous supported existing capability")
    cid = next(iter(ids))
    entry = get_default_taxonomy().by_id()[cid]
    matched = sorted({p for r in hypotheses for p in r["matched_requirement_phrases"]})
    # Extend a whole native multiword phrase only when the observed text contains
    # its regular plural variant. Keep all native evidence and matcher guards.
    variants = sorted({normalise(p)+"s" for p in matched if len(normalise(p).split())>=2
                       and not normalise(p).endswith("s") and any(_contains(t,normalise(p)+"s") for t in c["examples"])})
    if not variants and not bounded:
        raise ValueError("No supported minimal resolver phrase normalization; manual investigation required")
    draft = {"kind":"resolver_improvement","resolver_draft_version":RESOLVER_DRAFT_VERSION,
        "governed_research":{"research_result_id":result["research_result_id"],"result_fingerprint":result["result_fingerprint"]},
        "candidate_id":c["candidate_id"],"candidate_fingerprint":c["candidate_fingerprint"],
        "source_gap_ids":deepcopy(c["source_gap_ids"]),"source_job_snapshot_provenance":deepcopy(c["provenance"]),
        "current_versions":deepcopy(result["current_versions"]),"knowledge_fingerprint":result["knowledge_fingerprint"],
        "target_capability_id":cid,"observed_requirement_text":deepcopy(c["examples"]),"normalized_concept":c["concept_key"],
        "proposed_resolver_change":{"type":"native_requirement_phrase_plural_support","add_requirement_phrases":variants,
            "product_context_guard":PRODUCT_CONTEXT_GUARD,"phrase_boundary":"whole_normalized_phrase"},
        "proposal_rationale":"Observed regular plural of an existing whole native requirement phrase; no new capability or evidence policy.",
        "deterministic_supporting_evidence":deepcopy(hypotheses),"requirement_phrase_evidence":matched,
        "does_not_match":deepcopy(entry.get("does_not_prove",[])),"guard_conditions":deepcopy(entry["requirement"]),
        "status":"proposal_only","requires_human_review":True,"requires_human_approval":True}
    if bounded:
        draft['proposed_resolver_change']={'type':'bounded_recognition_fallback',
            'rule':deepcopy(API_RECOGNITION_FALLBACK),'product_context_guard':PRODUCT_CONTEXT_GUARD,
            'phrase_boundary':'complete_requirement'}
        draft['proposal_rationale']='Additive complete-scope fallback after all existing native knowledge; no legacy tightening.'
    draft["draft_fingerprint"] = fingerprint(draft)
    draft["resolver_draft_id"] = "tqd3resolver_"+draft["draft_fingerprint"][:24]
    return draft


def resolver_overlay(draft):
    from taxonomy_discovery.governed_research import knowledge_fingerprint
    from job_discovery.matching import current_match_versions
    if draft.get("draft_fingerprint") != fingerprint({k:v for k,v in draft.items() if k not in {"draft_fingerprint","resolver_draft_id"}}):
        raise ValueError("Resolver draft edited")
    if draft.get("resolver_draft_version") != RESOLVER_DRAFT_VERSION or draft.get("status") != "proposal_only" or draft.get("requires_human_review") is not True:
        raise ValueError("Governed resolver draft required")
    if draft.get("resolver_draft_id") != "tqd3resolver_"+draft["draft_fingerprint"][:24] or draft.get("kind") != "resolver_improvement":
        raise ValueError("Resolver identity edited")
    if draft["current_versions"] != current_match_versions() or draft["knowledge_fingerprint"] != knowledge_fingerprint():
        raise ValueError("Resolver knowledge stale")
    base = get_default_taxonomy()
    entries = deepcopy(list(base.capabilities))
    entry = next(e for e in entries if e["capability_id"] == draft["target_capability_id"])
    if entry["requirement"] != draft["guard_conditions"]:
        raise ValueError("Native matcher guard changed")
    if draft['proposed_resolver_change'].get('type')=='bounded_recognition_fallback':
        from tailoring.requirement_scope import API_RECOGNITION_FALLBACK
        if (draft['target_capability_id']!='backend.api_development' or
                draft['proposed_resolver_change']!={'type':'bounded_recognition_fallback',
                    'rule':API_RECOGNITION_FALLBACK,'product_context_guard':PRODUCT_CONTEXT_GUARD,
                    'phrase_boundary':'complete_requirement'}):
            raise ValueError('Unsupported bounded recognition policy')
        if entry['requirement'].get('recognition_fallback_rules'):
            raise ValueError('Recognition fallback already exists; duplicate/conflict')
        entry['requirement']['recognition_fallback_rules']=[deepcopy(API_RECOGNITION_FALLBACK)]
        return CapabilityTaxonomy('tqd3-temporary-resolver-'+draft['draft_fingerprint'][:24],tuple(entries))
    if not set(draft["requirement_phrase_evidence"]).issubset(entry["requirement"].get("any_terms",[])):
        raise ValueError("Supporting phrases are not native target requirements")
    phrases = draft["proposed_resolver_change"]["add_requirement_phrases"]
    if draft["proposed_resolver_change"].get("product_context_guard") != PRODUCT_CONTEXT_GUARD or draft["proposed_resolver_change"].get("phrase_boundary") != "whole_normalized_phrase":
        raise ValueError("Safe product-context and whole-phrase guards required")
    if not phrases or any(p not in {normalise(q)+"s" for q in draft["requirement_phrase_evidence"]} for p in phrases):
        raise ValueError("Unsupported resolver phrase change")
    entry["requirement"]["contextual_phrase_variants"] = [
        {"phrase":p,"product_context_guard":PRODUCT_CONTEXT_GUARD} for p in phrases]
    return CapabilityTaxonomy("tqd3-temporary-resolver-"+draft["draft_fingerprint"][:24],tuple(entries))


def validate_bounded_regression_controls(draft, regression):
    if draft['proposed_resolver_change'].get('type')!='bounded_recognition_fallback':return
    from taxonomy_discovery import governed_requirement_resolution as review
    # Current, deterministic controls bound to the same source/draft semantics.
    row={'text':draft['observed_requirement_text'][0]}
    controls=review.preview(review.propose(row),explicit_execution=True)
    receipt=regression.get('recognition_policy_controls') or {}
    if (not controls['validation_passed'] or receipt.get('validation_passed') is not True
            or receipt.get('controls_fingerprint')!=fingerprint(controls['controls'])):
        raise ValueError('Missing/stale bounded recognition control receipt')

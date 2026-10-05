"""H.1 bounded, explicit research of refined gaps. No production writer."""
from copy import deepcopy
from datetime import datetime, timezone
import re
import os
from unittest.mock import patch
from urllib.parse import urlsplit

from job_discovery.matching import current_match_versions
from tailoring.capability_taxonomy import get_default_taxonomy, classify_requirement_record
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.candidate_refinement import candidate_report, candidate_csv
from taxonomy_discovery.taxonomy_evolution import gap_candidates, research_with_transport, overlap_check
from taxonomy_discovery.source_authority import classify_candidate_source_url, PRIMARY_OFFICIAL, FIRST_PARTY_OTHER
from taxonomy_discovery.focused_verification import _definition_sentences, _configured_safe_identity_aliases
from taxonomy_discovery.source_authority import load_source_authority_registry
from taxonomy_discovery.technology_registry import get_default_registry, resolve_requirement_text, normalise

RESEARCH_VERSION = "tqd3-governed-research-h1-v1"
INTERPRETATION_VERSION = "tqd3-governed-interpretation-h1.1-v1"
PLAN_VERSION = "tqd3-governed-research-plan-h1-v1"
MAX_BATCH = 3
MAX_ATTEMPTS = 2
ELIGIBLE_ROUTES = ("existing_capability_resolver_issue", "technology_relationship",
                   "technology_identity", "possible_new_capability")
SOURCE_CLASSES = ("first_party_official_docs", "first_party_official_repository",
                  "authoritative_supporting", "secondary_supporting")


def knowledge_fingerprint():
    return fingerprint({"taxonomy":get_default_taxonomy().capabilities, "registry":get_default_registry().entries})


def prepare_gap_review(*, db_path=None, corpus=None, gaps=None):
    """Same native artifacts as export -> gaps -> taxonomy-candidates CLI; no saves."""
    from taxonomy_discovery.regression_corpus import export_saved_corpus
    from taxonomy_discovery.taxonomy_gaps import aggregate_corpus_gaps
    frozen = deepcopy(corpus) if corpus is not None else None
    if gaps is None:
        frozen = frozen if frozen is not None else export_saved_corpus(db_path=db_path)
        gaps = aggregate_corpus_gaps(frozen)
    candidates = gap_candidates(gaps)
    report = candidate_report(candidates)
    return {"corpus": frozen, "gaps": deepcopy(gaps), "candidates": candidates,
            "report": report, "csv": candidate_csv(report), "current_versions": current_match_versions(),
            "artifact_fingerprint": fingerprint({"corpus": frozen, "gaps": gaps, "report": report})}


def validate_candidate(candidate):
    fp = fingerprint({k:v for k,v in candidate.items() if k not in {"candidate_id", "candidate_fingerprint"}})
    if candidate.get("candidate_fingerprint") != fp or candidate.get("candidate_id") != "tqd3taxgap_"+fp[:24]:
        raise ValueError("Candidate identity stale/edited")
    if candidate.get("candidate_route") not in ELIGIBLE_ROUTES:
        raise ValueError("Refined route is not eligible for research")
    if candidate.get("current_versions") != current_match_versions():
        raise ValueError("Candidate knowledge versions changed; refresh Gap Review")


def _questions(candidate, subject):
    route = candidate["candidate_route"]
    if route == "technology_identity":
        return [f"What concrete technology is {subject}; what is its canonical name and official maintainer?",
                f"What official documentation or official repository defines {subject}, its documented aliases and engineering uses?"]
    if route == "technology_relationship":
        return [f"What official documentation defines {subject} and its engineering responsibilities?",
                f"What documented integration and usage semantics support or contradict the existing capability hypotheses for {subject}?"]
    if route == "existing_capability_resolver_issue":
        return [f"What authoritative definitions and boundaries describe {subject}, including decomposition of compound requirements?"]
    return [f"What primary technical definitions and common engineering terminology describe {subject}?",
            f"What responsibilities, adjacent boundaries, non-proving examples and observable implementation evidence distinguish {subject}?"]


def research_plan(candidates, *, selected_candidate_ids, external_resolver=False, research_round=0):
    if type(research_round) is not int or not 0 <= research_round <= 3:
        raise ValueError("Research round must be 0 to 3; explicit follow-up only")
    selected = sorted(set(selected_candidate_ids))
    if not selected or len(selected) > MAX_BATCH:
        raise ValueError("Select 1 to 3 research candidates explicitly")
    by_id = {c["candidate_id"]: c for c in candidates}
    if any(cid not in by_id for cid in selected):
        raise ValueError("Unknown selected candidate")
    targets = []
    for cid in selected:
        c = by_id[cid]
        validate_candidate(c)
        from taxonomy_discovery.research_atomicity import candidate_atomicity
        atomicity = candidate_atomicity(c)
        if atomicity["atomicity_status"] == "compound_requires_decomposition":
            raise ValueError("Needs decomposition before research")
        names = atomicity["detected_entities"]
        # Multiple entities must be decomposed by the human before identity research.
        subject = names[0] if len(names) == 1 else c["concept_key"]
        t = {"candidate": deepcopy(c), "subject": subject, "questions": _questions(c, subject),
             "research_round":research_round,
             "current_versions": current_match_versions(), "research_input_only": True,
             "preferred_source_classes": list(SOURCE_CLASSES), "reason": c["routing_reason"],
             "external_requested": c["candidate_route"] != "existing_capability_resolver_issue" or bool(external_resolver),
             "requires_decomposition": atomicity["atomicity_status"] == "compound_requires_decomposition"}
        t["target_fingerprint"] = fingerprint(t)
        targets.append(t)
    plan = {"plan_version": PLAN_VERSION, "current_versions": current_match_versions(), "knowledge_fingerprint":knowledge_fingerprint(),
            "targets": targets, "maximum_candidates": MAX_BATCH, "queries_per_candidate": 1,
            "maximum_attempts_per_candidate": MAX_ATTEMPTS}
    plan["plan_fingerprint"] = fingerprint(plan)
    return plan


def tavily_transport(target, *, explicit_execution=False):
    """One existing Search-adapter query. Called only inside explicit executor."""
    if explicit_execution is not True:
        raise ValueError("Explicit execution required before provider adapter")
    from taxonomy_discovery.tavily_research import research_target_with_tavily
    adapted = {"target_id": "h1_"+target["target_fingerprint"][:24], "tavily_eligible": True,
               "research_question": "\n".join(target["questions"])}
    if target["research_round"]:
        from taxonomy_discovery.source_authority import candidate_official_domains
        adapted.update(research_profile="first_party_definition_rescue_v1",
            search_query=f'"{target["subject"]}" official documentation definition. '+" ".join(target["questions"]),
            include_domains=candidate_official_domains({"canonical_name":target["subject"]}))
    response = research_target_with_tavily(adapted, preserve_raw_response=True)
    raw = deepcopy(response["raw_provider_response"])
    # Retain original provider response alongside the adapter request identity.
    return {"request_id": response["provider_request_id"], "results": raw.get("results", []),
            "raw_response": raw, "request_payload": response["request_payload"],
            "provider_metadata": {k:v for k,v in response.items() if k not in {"raw_provider_response", "sources"}}}


def classify_sources(subject, raw, *, authority_registry_path=None):
    classified = []
    official_repos = set()
    # Exact repository links in subject-specific, first-party definitions prove
    # provenance. A hostname, stars, random owner or provider label never does.
    for row in raw.get("results", []):
        if not isinstance(row, dict):
            continue
        authority = classify_candidate_source_url({"canonical_name": subject}, row.get("url", ""), registry_path=authority_registry_path)
        content = "\n".join(str(row.get(k) or "") for k in ("content", "raw_content"))
        parsed = urlsplit(str(row.get("url") or ""))
        if authority["authority"] == PRIMARY_OFFICIAL and parsed.scheme in {"http", "https"} and parsed.hostname != "github.com" and _definition_sentences(subject, content):
            official_repos.update(m.lower().removesuffix(".git") for m in re.findall(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", content))
    for row in raw.get("results", []):
        if not isinstance(row, dict):
            continue
        authority = classify_candidate_source_url({"canonical_name": subject}, row.get("url", ""), registry_path=authority_registry_path)
        url = urlsplit(str(row.get("url") or ""))
        repo = "/".join(url.path.strip("/").split("/")[:2]).lower().removesuffix(".git")
        if url.scheme not in {"https", "http"}:
            source_class = "secondary_supporting"
        elif url.hostname == "learn.microsoft.com" and re.match(r"/(?:[a-z]{2}-[a-z]{2}/)?answers/",url.path,re.I):
            source_class = "secondary_supporting"  # Community answers are not official product definitions.
        elif url.hostname == "github.com":
            source_class = "first_party_official_repository" if repo in official_repos else "secondary_supporting"
        elif authority["authority"] == PRIMARY_OFFICIAL:
            source_class = "first_party_official_docs"
        elif authority["authority"] == FIRST_PARTY_OTHER:
            source_class = "authoritative_supporting"
        else:
            source_class = "secondary_supporting"
        classified.append({"evidence": deepcopy(row), "classification": authority, "source_class": source_class})
    return classified


def interpret(target, research, *, authority_registry_path=None):
    c, subject = target["candidate"], target["subject"]
    from taxonomy_discovery.research_atomicity import candidate_atomicity
    atomicity = candidate_atomicity(c)
    raw = research["raw_provider_evidence"]
    rules = load_source_authority_registry(authority_registry_path)
    aliases = _configured_safe_identity_aliases(subject, rules)
    sources = classify_sources(subject, raw, authority_registry_path=authority_registry_path)
    definitions, conflicts = [], []
    for s in sources:
        content = "\n".join(str(s["evidence"].get(k) or "") for k in ("content", "raw_content"))
        primary = s["source_class"] in SOURCE_CLASSES[:2] or (c["candidate_route"] == "possible_new_capability" and s["source_class"] == "authoritative_supporting")
        sentences = sorted({sentence for name in aliases for sentence in _definition_sentences(name,content)}) if primary else []
        s["accepted_definition_sentences"] = sentences
        definitions.extend(sentences)
        if primary and any(re.search(re.escape(name)+r"\s+is\s+(?:not|a different)\b", content, re.I) for name in aliases):
            conflicts.append("Contradictory first-party identity evidence")
    local = overlap_check(" ".join(c["examples"]))
    ids = set(local["exact_matches"]) | {r["capability_id"] for r in local["high_overlap_candidates"]}
    local["governed_capability_definitions"] = [deepcopy(get_default_taxonomy().by_id()[cid]) for cid in sorted(ids)]
    local["requirement_decomposition_context"] = deepcopy(c["examples"])
    known = resolve_requirement_text(subject)
    supported = sorted({r["capability_id"] for sentence in definitions
                        if (r := classify_requirement_record({"text":sentence}, get_default_taxonomy()))})
    blockers = list(conflicts)
    if target["requires_decomposition"] or atomicity["atomicity_status"] == "compound_requires_decomposition":
        blockers.append("Multiple technology entities require explicit decomposition")
    if not definitions and c["candidate_route"] != "existing_capability_resolver_issue":
        blockers.append("No affirmative subject-specific first-party definition")
    identity_supported = bool(definitions) and not blockers
    action = "research_more"
    if c["candidate_route"] == "existing_capability_resolver_issue":
        action = "no_change" if local["exact_matches"] else "resolver_improvement" if local["high_overlap_candidates"] else "requirement_decomposition_review"
    elif not blockers:
        if known["status"] == "resolved":
            action = "no_change"
        elif c["candidate_route"] == "technology_identity":
            action = "technology_identity_proposal"
        elif c["candidate_route"] == "technology_relationship":
            action = "relationship_proposal" if len(supported) == 1 else "research_more"
            if len(supported) != 1:
                blockers.append("Relationship to one existing capability is not established")
        elif not local["exact_matches"] and not local["high_overlap_candidates"] and any(
                s["source_class"] in {"first_party_official_docs", "authoritative_supporting"}
                and any(re.search(r"\b(?:capability|practice|engineering (?:discipline|activity|process))\b", sentence, re.I)
                        for sentence in s["accepted_definition_sentences"]) for s in sources):
            # Distinctness is explicitly UNVERIFIED; primary evidence permits a
            # governed draft for review, never a new production concept.
            action = "new_capability_proposal"
        elif local["exact_matches"] or local["high_overlap_candidates"]:
            action = "requirement_decomposition_review"
        else:
            blockers.append("Distinct engineering capability is not established by entity/repository evidence")
    rules = load_source_authority_registry(authority_registry_path)
    canonical = next((r["canonical_name"] for r in rules.get("technology_domains",[]) if r.get("canonical_name")
        and normalise(subject) in {normalise(a) for a in r.get("technology_aliases",[])}),subject)
    return {"atomicity":atomicity,"sources": sources, "authoritative_evidence_summary": definitions,
            "supporting_evidence_summary": [s["evidence"] for s in sources if s["source_class"] not in SOURCE_CLASSES[:2]],
            "identity_finding": {"canonical_name": canonical, "verified": identity_supported,
                "maintainer":"Not inferred; review first-party definitions and ownership evidence",
                "official_repositories":[s["evidence"].get("url") for s in sources if s["source_class"] == "first_party_official_repository"]},
            "relationship_finding": {"verified":action == "relationship_proposal" or known["status"] == "resolved",
                "supported_existing_capability_ids": supported, "relationship_type": "maps_to_capability", "production_knowledge": known},
            "existing_capability_assessment": local,
            "possible_new_capability_assessment": {"distinctness": "unverified_requires_human_review", "recurrence_is_metadata_only": True},
            "aliases": _configured_safe_identity_aliases(subject, rules), "conflicts_blockers": blockers,
            "quality_diagnostics": {"primary_definitions": len(definitions), "provider_labels_ignored": True, "popularity_ignored": True},
            "recommended_next_action": action}


def validate_result(result, *, allow_stale_authority=False):
    if result.get("result_fingerprint") != fingerprint({k:v for k,v in result.items() if k not in {"result_fingerprint", "research_result_id"}}):
        raise ValueError("Research result fingerprint stale/edited")
    if result.get("research_result_id") != "tqd3h1_"+result["result_fingerprint"][:24]:
        raise ValueError("Research result identity edited")
    validate_candidate(result["candidate"])
    if result["current_versions"] != current_match_versions():
        raise ValueError("Research knowledge stale")
    if result["knowledge_fingerprint"] != knowledge_fingerprint():
        raise ValueError("Research knowledge contents changed")
    raw = result["research"]["raw_provider_evidence"]
    local_only = result["candidate_route"] == "existing_capability_resolver_issue" and raw.get("provider") == "local_deterministic" and not raw.get("results")
    if not allow_stale_authority and not local_only and result["authority_rules_fingerprint"] != fingerprint(load_source_authority_registry(result.get("authority_registry_path"))):
        raise ValueError("Source authority rules changed; refresh research interpretation")
    if result["research"].get("evidence_fingerprint") != fingerprint(result["research"]["raw_provider_evidence"]):
        raise ValueError("Raw evidence fingerprint edited")


def interpretation_cache_key(target, authority_registry_path=None):
    return fingerprint({"target":target,"research_version":RESEARCH_VERSION,"interpretation_version":INTERPRETATION_VERSION,
        "knowledge_fingerprint":knowledge_fingerprint(),"authority_rules":load_source_authority_registry(authority_registry_path)})


def re_evaluate_saved_evidence(result, *, explicit_execution=False, authority_registry_path=None, persist=False, db_path=None):
    """Pure by default; explicit local save appends lineage, never repeats Search."""
    if explicit_execution is not True:
        raise ValueError("Explicit saved-evidence re-evaluation required")
    validate_result(result,allow_stale_authority=True)
    path = authority_registry_path if authority_registry_path is not None else result.get("authority_registry_path")
    rules = load_source_authority_registry(path)
    updated = deepcopy(result)
    target = result["research"]["target"]
    updated.update(interpret(target,result["research"],authority_registry_path=path))
    updated.update(interpretation_version=INTERPRETATION_VERSION,authority_registry_path=str(path) if path else None,
        authority_rules_version=rules.get("version"),authority_rules_fingerprint=fingerprint(rules),
        cache_key=interpretation_cache_key(target,path),approval=False,
        interpretation_lineage={"previous_research_result_id":result["research_result_id"],"previous_result_fingerprint":result["result_fingerprint"]},
        re_evaluated_at=datetime.now(timezone.utc).isoformat())
    updated.pop("research_result_id",None); updated.pop("result_fingerprint",None)
    updated["result_fingerprint"] = fingerprint(updated)
    updated["research_result_id"] = "tqd3h1_"+updated["result_fingerprint"][:24]
    if persist:
        from database.taxonomy_discovery_review_manager import save_governed_research_result, list_governed_research_results
        if not any(row["result"] == result for row in list_governed_research_results(db_path=db_path)):
            raise ValueError("Original saved research record required for persisted re-evaluation")
        return save_governed_research_result(updated,db_path=db_path)
    return updated


def execute_plan(plan, candidates, *, explicit_execution=False, transport=None, db_path=None, authority_registry_path=None):
    from database.taxonomy_discovery_review_manager import list_governed_research_results, save_governed_research_result
    if explicit_execution is not True:
        raise ValueError("Explicit execution required before research")
    if plan.get("plan_version") != PLAN_VERSION or plan.get("plan_fingerprint") != fingerprint({k:v for k,v in plan.items() if k != "plan_fingerprint"}):
        raise ValueError("Research plan stale/edited")
    if not 1 <= len(plan["targets"]) <= MAX_BATCH or len({t["candidate"]["candidate_id"] for t in plan["targets"]}) != len(plan["targets"]):
        raise ValueError("Research batch limit/selection invalid")
    by_id = {c["candidate_id"]:c for c in candidates}
    saved = list_governed_research_results(db_path=db_path)
    from taxonomy_discovery.research_atomicity import candidate_atomicity
    for t in plan["targets"]:
        if candidate_atomicity(t["candidate"])["atomicity_status"] == "compound_requires_decomposition":
            raise ValueError("Needs decomposition before research")
    # Global configuration failure must precede any candidate execution. Fake
    # transports and local-only/cached work never require a real provider key.
    def raw_match(t):
        return next((row["result"] for row in saved if row["result"]["candidate_fingerprint"] == t["candidate"]["candidate_fingerprint"]
            and row["result"]["research"]["target"].get("research_round",0) == t.get("research_round",0)
            and row["result"]["research"]["target"].get("external_requested") == t["external_requested"]
            and row["result"]["research"]["target"].get("questions") == t["questions"]),None)
    for t in plan["targets"]:
        if t["external_requested"] and not raw_match(t) and any(
                row["result"]["candidate"].get("source_gap_ids") == t["candidate"].get("source_gap_ids")
                and row["result"]["candidate"].get("normalized_cluster") == t["candidate"].get("normalized_cluster")
                and row["result"]["candidate"].get("provenance") == t["candidate"].get("provenance")
                and row["result"]["research"]["target"].get("research_round",0) == t.get("research_round",0)
                and row["result"]["research"]["target"].get("external_requested") for row in saved):
            raise ValueError("Saved evidence exists for this gap under earlier candidate inputs. Re-evaluate saved evidence; no external request was sent.")
    if transport is None and any(t["external_requested"] and not raw_match(t) for t in plan["targets"]):
        from taxonomy_discovery.tavily_research import tavily_api_key_from_env
        if not tavily_api_key_from_env():
            raise ValueError("Tavily research is not configured. TAVILY_API_KEY is unavailable.")
    output, failures = [], []
    for t in plan["targets"]:
        cid = t["candidate"]["candidate_id"]
        try:
            validate_candidate(t["candidate"])
            if cid not in by_id or by_id[cid] != t["candidate"] or plan["current_versions"] != current_match_versions() or plan["knowledge_fingerprint"] != knowledge_fingerprint():
                raise ValueError("Selected candidate or knowledge changed; no substitution")
            if t["target_fingerprint"] != fingerprint({k:v for k,v in t.items() if k != "target_fingerprint"}):
                raise ValueError("Target edited")
            cache_key = interpretation_cache_key(t,authority_registry_path)
            cached = next((row["result"] for row in saved if row["result"]["cache_key"] == cache_key), None)
            if cached:
                validate_result(cached)
                output.append(cached)
                continue
            prior = raw_match(t)
            if prior:
                output.append(re_evaluate_saved_evidence(prior,explicit_execution=True,authority_registry_path=authority_registry_path,persist=True,db_path=db_path))
                continue
            if not t["external_requested"] or t["requires_decomposition"]:
                raw = {"request_id":"local_"+t["target_fingerprint"], "results":[], "provider":"local_deterministic"}
                research = {"target":deepcopy(t), "raw_provider_evidence":raw, "request_id":raw["request_id"], "evidence_fingerprint":fingerprint(raw), "approval":False}
            else:
                for attempt in range(MAX_ATTEMPTS):
                    # Recheck immediately before EACH potentially paid attempt.
                    validate_candidate(t["candidate"])
                    if plan["knowledge_fingerprint"] != knowledge_fingerprint():
                        raise ValueError("Knowledge changed before request attempt")
                    try:
                        research = research_with_transport(t, transport=transport or (lambda target: tavily_transport(target, explicit_execution=True)),
                            explicit_execution=True, authority_registry_path=authority_registry_path)
                        break
                    except Exception as exc:
                        from urllib.error import HTTPError, URLError
                        from taxonomy_discovery.tavily_research import TavilyResearchError
                        cause = exc.__cause__
                        retryable = isinstance(exc, (TimeoutError, ConnectionError, OSError)) or (
                            isinstance(exc,TavilyResearchError) and (
                                isinstance(cause,HTTPError) and (cause.code == 429 or cause.code >= 500)
                                or isinstance(cause,URLError) and not isinstance(cause,HTTPError)))
                        if not retryable or attempt+1 == MAX_ATTEMPTS:
                            raise
            result = {"research_version":RESEARCH_VERSION, "research_plan_fingerprint":plan["plan_fingerprint"],
                      "interpretation_version":INTERPRETATION_VERSION,"authority_rules_version":load_source_authority_registry(authority_registry_path).get("version"),
                      "candidate_id":cid, "candidate_fingerprint":t["candidate"]["candidate_fingerprint"],
                      "candidate_route":t["candidate"]["candidate_route"], "candidate":deepcopy(t["candidate"]),
                      "source_gap_provenance":deepcopy(t["candidate"]["provenance"]), "current_versions":current_match_versions(),
                      "taxonomy_version":t["current_versions"]["taxonomy_version"],
                      "registry_version":t["current_versions"]["technology_registry_version"],
                      "executed_at":datetime.now(timezone.utc).isoformat(), "questions":t["questions"],
                      "knowledge_fingerprint":knowledge_fingerprint(),
                      "authority_registry_path":str(authority_registry_path) if authority_registry_path else None,
                      "authority_rules_fingerprint":fingerprint(load_source_authority_registry(authority_registry_path)),
                      "research":research, "provider_request_id":research["request_id"], "cache_key":cache_key,
                      "approval":False, **interpret(t,research,authority_registry_path=authority_registry_path)}
            result["result_fingerprint"] = fingerprint(result)
            result["research_result_id"] = "tqd3h1_"+result["result_fingerprint"][:24]
            output.append(save_governed_research_result(result, db_path=db_path))
        except Exception as exc:
            failures.append({"candidate_id":cid, "error":str(exc)})
    return {"results":output, "failures":failures, "maximum_candidates":MAX_BATCH, "approval":False}


def create_draft(result, *, explicit_creation=False, capability_fields=None):
    """Native proposal contracts, with material research identity/provenance."""
    if explicit_creation is not True:
        raise ValueError("Explicit draft creation required")
    validate_result(result)
    provenance = {"research_result_id":result["research_result_id"], "result_fingerprint":result["result_fingerprint"],
                  "source_gap_provenance":deepcopy(result["source_gap_provenance"])}
    action = result["recommended_next_action"]
    if result["conflicts_blockers"]:
        raise ValueError("Research blockers require more research")
    if action == "resolver_improvement":
        from taxonomy_discovery.resolver_improvement import resolver_draft
        return resolver_draft(result)
    if action == "new_capability_proposal":
        from taxonomy_discovery.taxonomy_evolution import draft_proposal, proposal_fingerprint
        p = draft_proposal(result["candidate"], result["research"], **(capability_fields or {}))
        p["governed_research"] = provenance
        p["proposal_fingerprint"] = proposal_fingerprint(p)
        p["proposal_id"] = "tqd3taxproposal_"+p["proposal_fingerprint"][:24]
        return {"kind":"capability", "proposal":p, "status":"draft", "requires_human_approval":True}
    if action not in {"technology_identity_proposal", "relationship_proposal"}:
        raise ValueError("Recommendation does not warrant a knowledge proposal")
    from taxonomy_discovery.research_proposals import validate_proposal_bundle, PROPOSAL_CONTRACT_VERSION
    subject = result["identity_finding"]["canonical_name"]
    entries = [e for e in get_default_registry().entries if normalise(subject) in {normalise(a) for a in e["aliases"]}]
    if len(entries) > 1:
        raise ValueError("Identity ambiguous")
    entry = entries[0] if entries else None
    cap = result["relationship_finding"]["supported_existing_capability_ids"][0] if action == "relationship_proposal" else None
    pid = "h1proposal_"+result["result_fingerprint"][:24]
    p = {"proposal_id":pid, "technology_id":entry["technology_id"] if entry else "h1."+fingerprint(subject)[:16],
         "label":subject, "entry_kind":entry["entry_kind"] if entry else "tool", "aliases":result["aliases"],
         "proposal_classification":"safe_mapping_candidate" if cap else "recognized_unmapped",
         "proposed_capability_id":cap, "relationship_type":"maps_to_capability" if cap else None,
         "confidence":0.8, "summary":"H.1 research draft; explicit human review required.",
         "sources":[{"url":s["evidence"]["url"], "title":s["evidence"].get("title") or subject,
                     "publisher":s["classification"]["hostname"]} for s in result["sources"] if s["accepted_definition_sentences"]],
         "governed_research":provenance}
    bundle = validate_proposal_bundle({"proposal_bundle_version":PROPOSAL_CONTRACT_VERSION,
        "taxonomy_version":get_default_taxonomy().version, "registry_version":get_default_registry().version,
        "research_method":RESEARCH_VERSION, "proposals":[p]})
    return {"kind":"technology", "draft_id":pid, "status":"draft", "requires_human_approval":True, "proposal_bundle":bundle}


def temporary_impact(corpus, draft):
    with patch.dict(os.environ, {"CAPABILITY_RAG_MODE":"off"}), patch("socket.socket.connect", side_effect=RuntimeError("Offline preview forbids network")):
        return _temporary_impact(corpus, draft)


def _temporary_impact(corpus, draft):
    from taxonomy_discovery.regression_corpus import CORPUS_VERSION
    if not corpus or corpus.get("corpus_version") != CORPUS_VERSION or not corpus.get("jobs") or any(not j.get("replay_available") for j in corpus["jobs"]):
        raise ValueError("Compatible frozen corpus required; no historical reconstruction")
    if draft["kind"] == "capability":
        from taxonomy_discovery.taxonomy_evolution import temporary_regression
        report = temporary_regression(corpus, [draft["proposal"]])
        report.update(draft_fingerprint=fingerprint(draft), knowledge_fingerprint=knowledge_fingerprint(), score_increase_is_correctness=False)
        report.pop("regression_fingerprint", None)
        report["regression_fingerprint"] = fingerprint(report)
        return report
    from taxonomy_discovery.regression_corpus import compare_regression_corpus, build_regression_corpus, duplicate_credit_violations
    from job_discovery.matching import _default_stable_builder
    if draft["kind"] == "resolver_improvement":
        from taxonomy_discovery.resolver_improvement import resolver_overlay
        from tailoring.capability_taxonomy import temporary_taxonomy_scope
        shadow = resolver_overlay(draft)
        scope = temporary_taxonomy_scope(shadow)
    else:
        from taxonomy_discovery.focused_verification_preview import _shadow_registry
        from taxonomy_discovery.research_proposals import validate_proposal_bundle
        from taxonomy_discovery.technology_registry import temporary_registry_scope, TechnologyRegistry
        validate_proposal_bundle(draft["proposal_bundle"])
        copied = _shadow_registry(draft)
        shadow = TechnologyRegistry("tqd3-temporary-registry-"+fingerprint(draft)[:24], copied.entries)
        scope = temporary_registry_scope(shadow)
    # Use the native current-production baseline and native offline replay.
    snapshots = []
    for job in corpus["jobs"]:
        inputs = job["frozen_inputs"]
        from job_discovery.matching import build_profile_evidence_context
        if build_profile_evidence_context(inputs["evidence_snapshot"]) != inputs["context"]:
            raise ValueError("Frozen evidence/context mismatch")
        stable = _default_stable_builder(raw_jd_text=inputs["raw_jd_text"], jd_profile=inputs["jd_profile"], context=inputs["context"])
        snapshots.append({"id":job["snapshot_id"], "discovered_job_id":job["job_id"], "job_content_hash":job["job_content_hash"],
            "raw_jd_text":inputs["raw_jd_text"], "jd_profile":inputs["jd_profile"], "evidence_snapshot":inputs["evidence_snapshot"],
            "evidence_fingerprint":inputs["context"]["evidence_fingerprint"], "stable_analysis":stable})
    baseline = build_regression_corpus(snapshots)
    with scope:
        report = compare_regression_corpus(baseline)
    for job, original in zip(report["jobs"], corpus["jobs"]):
        violations = duplicate_credit_violations(original["baseline_stable_analysis"], original["frozen_inputs"]["context"])
        if violations:
            job["duplicate_credit_violations"] = job.get("duplicate_credit_violations", []) + violations
            job["classification"] = "hard_regression/invariant_violation"
        elif job["classification"] == "expected_improvement":
            job["classification"] = "requires_review"
        for change in job.get("requirement_changes", []):
            change["responsible_draft_id"] = draft.get("draft_id") or draft.get("resolver_draft_id")
    from collections import Counter
    report["classification_counts"] = dict(Counter(j["classification"] for j in report["jobs"]))
    report.update(review_only=True, score_increase_is_correctness=False,
                  temporary_knowledge_identity=shadow.version,
                  current_versions=current_match_versions(), knowledge_fingerprint=knowledge_fingerprint(),
                  corpus_fingerprint=fingerprint(corpus), draft_fingerprint=fingerprint(draft),
                  affected_jobs=[j["job_id"] for j in report["jobs"] if j.get("requirement_changes")])
    if draft["kind"] == "resolver_improvement":
        from taxonomy_discovery.candidate_refinement import product_context_names
        from tailoring.capability_taxonomy import PRODUCT_CONTEXT_GUARD_VERSION
        names = product_context_names()
        report["resolver_guard_contract_version"] = PRODUCT_CONTEXT_GUARD_VERSION
        report["resolver_product_context_names"] = names
        report["resolver_product_context_fingerprint"] = fingerprint(names)
        source_ids = {(p["job_id"],p["requirement_id"]) for p in draft["source_job_snapshot_provenance"]}
        changes = [(j,c) for j in report["jobs"] for c in j.get("requirement_changes",[])]
        report.update(temporary_resolver_identity=shadow.version,
            affected_requirement_ids=[c["requirement_id"] for _,c in changes],
            newly_resolved_count=sum(c["newly_resolved"] for _,c in changes),
            unchanged_count=sum(len(j["requirements"]) for j in baseline["jobs"])-len(changes),
            unexpectedly_changed_requirements=[{"job_id":j["job_id"],**c} for j,c in changes
                if (j["job_id"],c["requirement_id"]) not in source_ids or (c.get("after") or {}).get("capability_id") != draft["target_capability_id"]])
        unexpected_ids = {(c["job_id"],c["requirement_id"]) for c in report["unexpectedly_changed_requirements"]}
        report["intended_changed_requirements"] = [{"job_id":j["job_id"],**c} for j,c in changes
            if (j["job_id"],c["requirement_id"]) not in unexpected_ids]
        report["publication_blockers"] = (["unexpected_requirement_changes"] if unexpected_ids else []) + (
            ["missing_or_invalid_regression"] if not report["jobs"] or any(not j.get("available") for j in report["jobs"]) else []) + (
            ["duplicate_credit_violations"] if any(j.get("duplicate_credit_violations") for j in report["jobs"]) else [])
    else:
        report["temporary_registry_identity"] = shadow.version
    report["regression_fingerprint"] = fingerprint(report)
    return report


def canary_status():
    """Read-only live knowledge checks; never run or inject a fixture on render."""
    return {"C++ canonical/current published mapping": {
        "canonical":(classify_requirement_record({"text":"C++"},get_default_taxonomy()) or {}).get("capability_id"),
        "registry":resolve_requirement_text("C++")},
        "React registry-only real-evidence canary": {"registry":resolve_requirement_text("React"),
            "evidence_test":"Not executed on render; tests/test_tqd3_integration_canaries.py"},
        "isolated unresolved -> verified -> approved -> test-published -> resolved":
            "TEST / TEMPORARY ONLY; not executed on render; positive fixture is not evidence verifying Apache ActiveMQ",
        "Production registry mutated":"No", "Broad Mining fixtures injected":False}

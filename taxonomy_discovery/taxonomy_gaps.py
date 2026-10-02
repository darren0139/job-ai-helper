"""Corpus-derived research inputs, using existing exact observation aggregation."""
from collections import Counter
from copy import deepcopy

from tailoring.capability_taxonomy import classify_requirement_record, get_default_taxonomy, normalise
from taxonomy_discovery.observations import build_unresolved_observations, aggregate_unresolved_observations
from taxonomy_discovery.regression_corpus import CORPUS_VERSION
from taxonomy_discovery.research_targets import _strict_unknown_terms
from taxonomy_discovery.technology_registry import get_default_registry, resolve_requirement_text

GAP_VERSION = "tqd3-corpus-taxonomy-gap-inputs-v1"


def aggregate_corpus_gaps(corpus):
    if corpus.get("corpus_version") != CORPUS_VERSION:
        raise ValueError("Unsupported regression corpus")
    taxonomy, registry = get_default_taxonomy(), get_default_registry()
    observations, excluded = [], []
    seen = set()
    for job in corpus["jobs"]:
        for row in job["requirements"]:
            if not row.get("score_eligible") or row.get("resolution_status") == "resolved":
                continue
            provenance = (job["job_id"], job["snapshot_id"], row.get("requirement_id"))
            if provenance in seen:
                continue
            seen.add(provenance)
            diagnostic = {"taxonomy_version": taxonomy.version, "rows": [{"status":"unresolved",
                "requirement_id":row.get("requirement_id"),"requirement_text":row.get("requirement_text"),
                "importance":row.get("importance"),"match_label":row.get("match_label")} ]}
            try:
                created = build_unresolved_observations(diagnostic, discovered_job_id=job["job_id"],
                                                       job_content_hash=job.get("job_content_hash"))
            except (ValueError, TypeError) as exc:
                excluded.append({"job_id":job["job_id"],"snapshot_id":job["snapshot_id"],"reason":str(exc)})
                continue
            for observation in created:
                observation.update(snapshot_id=job["snapshot_id"], observed_versions=deepcopy(job["versions"]),
                                   retrieval_suggestions=deepcopy(row.get("retrieval_suggestions", [])))
                observations.append(observation)
    gaps = []
    for candidate in aggregate_unresolved_observations(observations):
        group = candidate["observations"]
        examples = candidate["observed_terms"]
        resolutions = [resolve_requirement_text(text, registry=registry) for text in examples]
        canonical = [classify_requirement_record({"text":text},taxonomy) for text in examples]
        terms = sorted({term for text in examples for term in _strict_unknown_terms(text, registry=registry)})
        terms += sorted({r.get("technology_label") for r in resolutions if r.get("technology_label")})
        if any(canonical) or any(r["status"] == "resolved" for r in resolutions):
            route = "resolver_issue/already_covered"
        elif any(r["status"] == "ambiguous" for r in resolutions):
            route = "ambiguous/noise"
        elif any(r["status"] == "recognized_unmapped" for r in resolutions):
            route = "technology_relationship"
        elif terms:
            route = "technology_identity"
        elif len(normalise(examples[0]).split()) < 2:
            route = "ambiguous/noise"
        else:
            route = "capability_gap"
        suggestions = {}
        for observation in group:
            for suggestion in observation["retrieval_suggestions"]:
                if isinstance(suggestion, dict) and suggestion.get("capability_id"):
                    suggestions[suggestion["capability_id"]] = deepcopy(suggestion)
        gaps.append({"gap_id":candidate["candidate_id"],"normalized_cluster":candidate["normalised_observed_text"],
            "occurrence_count":candidate["observation_count"],"job_count":candidate["job_count"],"examples":examples,
            "importance_distribution":dict(Counter(o["importance"] for o in group)),
            "retrieval_suggestions":[suggestions[k] for k in sorted(suggestions)],"technology_terms":sorted(set(terms)),
            "provenance":[{"job_id":o["discovered_job_id"],"snapshot_id":o["snapshot_id"],
                           "requirement_id":o["requirement_id"],"job_content_hash":o["job_content_hash"],
                           "observed_versions":o["observed_versions"]} for o in group],
            "taxonomy_version":taxonomy.version,"registry_version":registry.version,
            "recommended_research_route":route,"research_input_only":True,"requires_human_review":True})
    return {"gap_version":GAP_VERSION,"observations":gaps,"excluded":excluded,
            "taxonomy_version":taxonomy.version,"registry_version":registry.version,
            "governance":{"research_input_only":True,"automatic_research":False,"proposal_creation":False,
                          "taxonomy_mutations":0,"registry_mutations":0,"candidate_evidence_mutations":0,
                          "scoring_influence":False,"model_calls":0,"network_calls":0}}

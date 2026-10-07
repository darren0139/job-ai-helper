"""Minimum H.1.1 research-scope guard; no requirement splitting or writes."""
import re
from copy import deepcopy
from taxonomy_discovery.candidate_refinement import technology_entities, phrase_present
from taxonomy_discovery.technology_registry import get_default_registry
from tailoring.capability_taxonomy import normalise

ATOMICITY_VERSION = "tqd3-research-atomicity-h1.1-v1"
# Review hints only, never identity/authority assertions.
_LIST_HINTS = ("AWS Glue", "Azure Data Factory", "Google Dataflow", "Databricks", "Mercurial", "Groovy")


def candidate_atomicity(candidate):
    text = " ".join(candidate.get("examples") or [candidate.get("normalized_cluster", "")])
    entries = get_default_registry().by_id()
    entities = technology_entities(text, candidate.get("technology_terms", []))["concrete_entities"]
    names = {entries[e["technology_id"]]["label"] if e.get("technology_id") in entries else e["term"] for e in entities}
    names.update(n for n in _LIST_HINTS if phrase_present(text,n))
    # A full product name and its nested acronym/vendor are one scope, not two.
    names = sorted(n for n in names if not any(normalise(n) != normalise(other) and phrase_present(other,n) for other in names))
    key = normalise(text)
    relation = "alternative_list" if len(names)>2 and re.search(r"\bor\b",key) else "or" if re.search(r"\bor\b",key) else "example_list" if re.search(r"\b(?:including|such as|e g)\b",key) or "," in text else "and" if re.search(r"\band\b",key) else "unknown"
    if len(names)>1:
        status = "compound_requires_decomposition"
    elif candidate.get("candidate_route") in {"existing_capability_resolver_issue","possible_new_capability"}:
        status = "coherent_capability_concept"
    elif len(names)==1:
        status = "atomic"
    else:
        status = "uncertain"
    return {"atomicity_version":ATOMICITY_VERSION,"atomicity_status":status,"logical_relation":relation,
        "detected_entities":names,"detected_concepts":[candidate.get("concept_key")],
        "parent_candidate_id":candidate.get("candidate_id"),"parent_text":candidate.get("normalized_cluster"),
        "source_provenance":deepcopy(candidate.get("provenance",[])),"automatic_decomposition":False}

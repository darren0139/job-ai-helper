"""H.0.1 deterministic review semantics; no production resolver changes."""
import csv
import io
import re
from collections import Counter, defaultdict
from copy import deepcopy

from tailoring.capability_taxonomy import normalise
from taxonomy_discovery.research_targets import _strict_unknown_terms
from taxonomy_discovery.source_authority import load_source_authority_registry
from taxonomy_discovery.technology_registry import get_default_registry

REFINEMENT_VERSION = "tqd3-taxonomy-candidate-refinement-v1"
_WRAPPER = re.compile(r"^(?:knowledge of|experience with|experience in|proficiency in|familiarity with|understanding of)\s+", re.I)
# Discovery hints identify entities for review, never identity verification or approval.
# Native registry/authority aliases take precedence. Plain names/acronyms cannot
# safely be inferred from capitalization alone, so this small positive vocabulary
# covers common product/service/language names without admitting arbitrary initials.
_ENTITY_HINTS = "PostgreSQL AWS GCP Redis Elasticsearch DynamoDB EC2 S3 BigFix SCCM PyTorch TensorFlow FastAPI Express.js ROS PowerShell Java Python TypeScript JavaScript HTML CSS".split()
_ENTITY_HINTS += ["Amazon Web Services", "Google Cloud Platform", "Microsoft SQL Server"]
_GENERIC = {"e.g","eg","etc","it","os","ms","bi","gui","api","ai","ml","genai","crud"}
_CONCEPT_KINDS = {"architecture_pattern","capability","concept","methodology"}


def concept_key(text):
    text = str(text or "").strip()
    text = _WRAPPER.sub("", text, count=1)
    return normalise(text)


def phrase_present(text, phrase):
    """Whole normalized phrase; only native plural 'web services' variation."""
    text=normalise(text).replace("web services", "web service")
    phrase=normalise(phrase).replace("web services", "web service")
    return bool(phrase and (" "+phrase+" ") in (" "+text+" "))


def semantic_overlap(text, taxonomy):
    key=concept_key(text)
    # An explicit level qualifier does not remove the integration activity.
    key=re.sub(r"\bsoftware system level integration\b","software integration",key)
    strong=[]
    for entry in taxonomy.capabilities:
        matcher=entry.get("requirement") or {}
        phrases=[p for p in matcher.get("any_terms",[]) if len(normalise(p).split())>=2]
        matches=[p for p in phrases if phrase_present(key,p)]
        if not matches:
            continue
        missing=[g for g in matcher.get("all_groups",[]) if not any(phrase_present(key,p) for p in g)]
        strong.append({"capability_id":entry["capability_id"],"domain":entry["domain"],
            "matched_requirement_phrases":matches,"unmet_requirement_groups":deepcopy(missing),
            "basis":"native_requirement_phrase","investigation_only":True})
    return strong


def capability_context(text):
    """A requirement phrase inside a multiword product name is not capability evidence."""
    key=normalise(text)
    for entity in technology_entities(text,[])["concrete_entities"]:
        term=normalise(entity["term"])
        if len(term.split())>1:
            key=re.sub(r"(?<!\w)"+re.escape(term)+r"(?!\w)"," ",key)
    return key


def technology_entities(text, proposed_terms):
    registry=get_default_registry()
    names={normalise(n):n for n in _ENTITY_HINTS}
    for rule in load_source_authority_registry().get("technology_domains",[]):
        for name in rule.get("technology_aliases",[]):
            names.setdefault(normalise(name),name)
    concept_aliases={}
    entries={}
    for entry in registry.entries:
        for alias in entry.get("aliases",[]):
            key=normalise(alias)
            if entry.get("entry_kind") in _CONCEPT_KINDS:
                concept_aliases[key]=alias
            else:
                names[key]=alias
                entries[key]=entry
    entities,concepts,rejected={},{},{}
    for key,name in names.items():
        if key not in _GENERIC and phrase_present(text,name):
            entities[key]={"term":name,"basis":"native_registry_alias" if key in entries else "local_entity_or_authority_hint",
                "registry_status":"recognized" if key in entries else "unverified_entity",
                "technology_id":entries.get(key,{}).get("technology_id")}
    for key,name in concept_aliases.items():
        if phrase_present(text,name):
            concepts[key]=name
    for term in set(proposed_terms or []) | set(_strict_unknown_terms(text,registry=registry)):
        key=normalise(term)
        if key in _GENERIC or term.lower().strip(".,") in _GENERIC:
            rejected[key]={"term":term,"reason":"generic computing acronym or prose abbreviation"}
        elif key in concept_aliases:
            concepts[key]=term
        elif not phrase_present(text,term):
            rejected[key]={"term":term,"reason":"proposed entity term not supported by source text"}
        elif key in names:
            entities.setdefault(key,{"term":names[key],"basis":"local_entity_or_authority_hint","registry_status":"unverified_entity","technology_id":None})
        elif re.search(r"[a-z][A-Z]|[A-Za-z][+#]|\.(?:js|net)\b",term):
            entities[key]={"term":term,"basis":"concrete_entity_lexical_shape","registry_status":"unverified_entity","technology_id":None}
        else:
            rejected[key]={"term":term,"reason":"no concrete entity evidence; initials/title-case prose alone insufficient"}
    return {"concrete_entities":[entities[k] for k in sorted(entities)],
        "capability_concepts":[concepts[k] for k in sorted(concepts)],"rejected_terms":[rejected[k] for k in sorted(rejected)]}


def route_candidate(gap, text, overlap, entities):
    key=concept_key(text)
    # Privacy/data vocabulary also describes technical controls. Administrative
    # evidence must identify an application action or an applicant consent notice.
    admin=(r"\b(apply now|apply online|submit(?:ting)? (?:your |an |the )?(?:application|resume|cv)|shortlisted|shortlisting|"
        r"(?:you|applicants|candidates) (?:hereby )?consent|by applying|application process|"
        r"citizenship|citizen|work authori[sz]ation|eligible to work|salary|visa|postal code|"
        r"shift availability|rotating shifts|willing to work shifts|working hours)\b")
    address=r"\b\d+\s+[\w ]{1,65}\b(?:road|street|avenue|drive|boulevard|lane)\b|\bsingapore\s+\d{6}\b"
    credentials=r"\b(degree|bachelor|master.s|phd|academic qualifications?|diploma|credentials?|certifications?|certified)\b"
    duration=r"\b\d+(?:\s*[-–]\s*\d+)?\+?\s*(?:years?|yrs?|months?)\b|\b(?:years?|months?) (?:of )?experience\b"
    narrative=r"\b(we are|our company|our mission|our vision|about us|join our|a part of|the company|the organisation|the organization|leading provider|strives to|burden of diseases|our clients include)\b"
    soft=r"\b(team player|passionate|motivated|enthusiasm|self starter|dynamic personality|communication skills|interpersonal|collaborative team|positive attitude|fast paced|work independently)\b"
    if re.search(admin,text,re.I) or re.search(address,text,re.I):
        return "administrative_or_non_capability","Application/eligibility/scheduling/address boilerplate"
    if re.search(credentials,text,re.I) or re.search(duration,text,re.I):
        # Existing native requirement predicates support an investigation only.
        exact=overlap.get("canonical_match")
        if exact and (exact.startswith("credential.") or exact=="experience.duration"):
            return "existing_capability_resolver_issue","Explicit native credential/duration requirement; no technical expansion"
        return "administrative_or_non_capability","Duration/credential requirement without a supported exact existing type"
    if re.search(narrative,text,re.I):
        return "administrative_or_non_capability","Employer/organisation/marketing narrative"
    if re.search(soft,text,re.I):
        return "ambiguous_or_noise","Generic soft-skill/motivation prose"
    if overlap["semantic_resolver_evidence"]:
        return "existing_capability_resolver_issue","Native canonical/registry resolution or explicit native requirement phrase; human investigation"
    if entities["concrete_entities"]:
        relationship=any(e["registry_status"]=="recognized" for e in entities["concrete_entities"])
        return ("technology_relationship" if relationship else "technology_identity"),"Concrete entity evidence; identity/relationship still requires research"
    if not gap.get("provenance") or not gap.get("job_count") or not gap.get("occurrence_count"):
        return "insufficient_signal","Missing source occurrence/job provenance"
    if (len(key.split())<2 and not entities["capability_concepts"]) or re.fullmatch(r"(?:and|or|including|such as|relevant|related|various|other|etc|e g)(?:\s+\w+)?",key):
        return "ambiguous_or_noise","Fragment without a distinct capability activity/concept"
    # Positive technical nouns/activities, not a bag of generic software tokens.
    meaningful=r"\b(protocols?|algorithms?|lattices?|concurrency|distributed|microservices?|access control|cloud security|data analysis|image processing|computer vision|machine learning|ai orchestration|neural networks?|cryptograph\w*|debugg\w*|deploy(?:ment|ments|ing|ed|s)?|test automation|observability|fault tolerance|load balancing|query optim\w*|performance tun\w*|systems? integration|software integration|network routing|storage replication|pipeline orchestration|event driven|database design|software design|architecture design)\b"
    if re.search(meaningful,key) or entities["capability_concepts"]:
        return "possible_new_capability","Meaningful technical activity/concept; distinctness unverified, recurrence is priority only"
    return "insufficient_signal","Technical vocabulary alone does not establish a distinct capability"


def candidate_report(candidates):
    groups=defaultdict(list)
    for c in candidates:
        groups[c["concept_key"]].append(c)
    concepts=[]
    for key, group in sorted(groups.items()):
        provenance=[deepcopy(p) for c in group for p in c.get("provenance",[])]
        unique={(p.get("job_id"),p.get("snapshot_id"),p.get("requirement_id")):p for p in provenance}
        jobs={p.get("job_id") for p in provenance if p.get("job_id") is not None}
        routes=sorted({c["candidate_route"] for c in group})
        concepts.append({"concept_key":key,"candidate_ids":[c["candidate_id"] for c in group],
            "source_gap_ids":sorted({g for c in group for g in c["source_gap_ids"]}),
            "occurrence_count":sum(c["occurrence_count"] for c in group),"distinct_requirement_count":len(unique),
            "distinct_job_count":len(jobs),"examples":sorted({e for c in group for e in c["examples"]}),
            "candidate_routes":routes,"route_conflict":len(routes)>1,
            "technology_terms":sorted({e["term"] for c in group for e in c["technology_entity_diagnostics"]["concrete_entities"]}),
            "strongest_overlap_diagnostics":[{"candidate_id":c["candidate_id"],"overlap":deepcopy(c["overlap"])}
                for c in sorted(group,key=lambda c:(not bool(c["overlap"]["semantic_resolver_evidence"]),c["candidate_id"]))],
            "current_versions":[deepcopy(c["current_versions"]) for c in group],"provenance":provenance,
            "recurrence_priority":"repeated_cross_job" if len(jobs)>1 else "single_job",
            "requires_human_review":True})
    return {"refinement_version":REFINEMENT_VERSION,"source_observations":len(candidates),"concept_count":len(concepts),
        "candidate_route_counts":dict(Counter(c["candidate_route"] for c in candidates)),
        "recurrence_counts":dict(Counter(c["recurrence_priority"] for c in concepts)),
        "concepts":concepts,"candidates":deepcopy(candidates),"research_input_only":True,
        "model_calls":0,"network_calls":0,"production_mutations":0,"automatic_proposals":False,"automatic_approval":False}


def candidate_csv(report):
    out=io.StringIO(newline="")
    writer=csv.DictWriter(out,fieldnames=["concept_key","candidate_id","source_gap_ids","candidate_route","routing_reason",
        "observed_job_count","observed_occurrence_count","recurrence_priority","research_priority","examples","concrete_technology_terms"])
    writer.writeheader()
    for c in report["candidates"]:
        row={k:c.get(k) for k in writer.fieldnames}
        for key in ("source_gap_ids","examples"):
            row[key]=" | ".join(c[key])
        row["concrete_technology_terms"]=" | ".join(e["term"] for e in c["technology_entity_diagnostics"]["concrete_entities"])
        writer.writerow(row)
    return out.getvalue()

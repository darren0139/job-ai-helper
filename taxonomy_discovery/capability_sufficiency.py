"""Deterministic capability support bundles for the native research interpreter.

No provider, persistence, semantic mappings, scoring or approval lives here.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.source_authority import capability_source_governance

SUFFICIENCY_VERSION = "tqd3-capability-sufficiency-v2.1"
FIELDS = ("definition", "boundaries", "responsibilities", "inclusions", "exclusions", "evidence_predicates")
MISSING = {"definition": "DEFINITION_MISSING", "boundaries": "BOUNDARY_MISSING",
           "responsibilities": "RESPONSIBILITIES_MISSING", "inclusions": "BOUNDARY_MISSING",
           "exclusions": "EXCLUSIONS_MISSING", "evidence_predicates": "EVIDENCE_PREDICATES_MISSING"}
STOP = set("a an the is are of to and or for with that this it as in by be can must should involves includes consists collection practice system systems".split())


def _subject_pattern(subject):
    # Exact lexical identity, with bounded grammatical noun-phrase variation.
    # No synonyms, arbitrary intervening words, or document-wide token matching.
    variants = [re.escape(subject)]
    words = re.findall(r"[A-Za-z]+", subject)
    if " ".join(words).lower() == subject.lower() and len(words) == 2:
        def noun(word):
            return re.escape(word[:-1]) + "s?" if word.endswith("s") and not word.endswith("ss") else re.escape(word)
        first, last = map(noun, words)
        variants.extend([first + r"\s+" + last,
                         last + r"\s+(?:of|in|for)\s+(?:the\s+)?" + first])
    if subject.lower().endswith(" systems"):
        variants.append(re.escape(subject[:-1]))
    return (r"\b(?:" + "|".join(variants) + r")\b"
            r"(?!\s+(?:alliance|association|council|consortium|committee)\b)")


def document_blocks(text):
    """Recover sentence-local units when retrieval has flattened a PDF.

    Normal paragraphs remain untouched. Oversized paragraphs are split only at
    sentence punctuation, never by a character window. Synthetic units cannot
    inherit heading scope or bind their neighbours. Raw evidence stays raw.
    """
    for block in re.split(r"\n\s*\n|\[\.\.\.\]", str(text or "")):
        block = block.strip()
        if len(block) <= 2500:
            yield block, False
        else:
            for sentence in re.split(r"(?<=[.!?])\s+", block):
                sentence = sentence.strip()
                # Flattened bibliographies/reference lists are not engineering
                # assertions; their labels can otherwise leak neighbouring titles.
                if re.match(r"^(?:References?\s*:|\[[A-Za-z][A-Za-z0-9]*\])", sentence, re.I):
                    continue
                yield sentence, True


def subject_blocks(subject, text):
    """Local paragraphs or one body after an explicit heading; fail closed.

    Flattened long blocks get sentence-local association only. New headings,
    omitted passages and non-subject units cannot extend inherited scope.
    """
    heading = ""
    for index, (block, recovered) in enumerate(document_blocks(text)):
        if recovered:
            heading = ""
        if not block:
            heading = ""
            continue
        if block.startswith("#") and "\n" not in block and not recovered:
            heading = block.lstrip("# ")
            continue
        pieces = re.split(r"(?m)^#{1,6}\s+", block)
        for part in pieces:
            if (part and len(part) <= 2500
                    and re.search(_subject_pattern(subject), heading + "\n" + part, re.I)):
                yield index, heading, part
            heading = ""


def extract_support(subject, source):
    full = str(source.get("raw_content") or "").strip()
    text = full or str(source.get("content") or "")
    support = {field: [] for field in FIELDS}
    assertions = []
    for block_id, heading, block in subject_blocks(subject, text):
        for sentence in re.split(r"(?<=[.!?])\s+|\n", block):
            sentence = sentence.strip()
            if not sentence:
                continue
            # Preserve original text, including negation and qualifiers.
            row = {"text": sentence, "paragraph": block_id, "heading": heading,
                   "paragraph_fingerprint": fingerprint(block), "url": source.get("url"),
                   "retrieved_document_text": bool(full)}
            local = re.search(_subject_pattern(subject), sentence, re.I) or (
                re.search(_subject_pattern(subject), heading, re.I)
                and re.match(r"(?:This practice|This capability|It)\b", sentence, re.I))
            defining_subject = _subject_pattern(subject) + r"(?:\s*\([^)]{1,40}\))?"
            if heading and re.search(_subject_pattern(subject), heading, re.I):
                defining_subject = "(?:" + defining_subject + r"|^(?:This practice|This capability|It))"
            if (local and re.search(defining_subject + r"\s+(?:is|are|refers to|means|describes|involves|consists of|comprises)\b", sentence, re.I)
                    and not re.search(r"\b(?:is|are|means)\s+(?:not|never)\b", sentence, re.I)):
                support["definition"].append(row)
            if re.search(r"\b(?:bounded context|boundaries|scope|trade.?offs?|distinct from|independent\w*|only|excludes|does not|must not|shared responsibility|split of.*duties)\b", sentence, re.I):
                support["boundaries"].append(row)
            if re.search(r"\b(?:responsib\w* (?:for|to)|(?:design|implement|maintain|configure|enforce|monitor|deploy|coordinate)\w*\s+\w+)\b", sentence, re.I):
                support["responsibilities"].append(row)
            if (re.search(r"\b(?:includes?|consists of|comprises|covers|encompasses)\s+(?!not\b)\w+", sentence, re.I)
                    and not re.search(r"\b(?:not|never)\s+include", sentence, re.I)):
                support["inclusions"].append(row)
            if re.search(r"\b(?:does not prove|does not establish|must not imply|not sufficient|insufficient|excludes|does not include|is not)\b", sentence, re.I):
                support["exclusions"].append(row)
            if (re.search(r"\b(?:evidence|demonstrat\w*|artifacts?|deliverables?|records?|documented|configuration|logs?|tests?|polic(?:y|ies)|diagrams?)\b", sentence, re.I)
                    and re.search(r"\b(?:implemented|configured|designed|deployed|tested|validated|enforced|demonstrat\w*|record\w*|document\w*)\b", sentence, re.I)
                    and not re.search(r"\b(?:alone|only|not|never|without)\b", sentence, re.I)):
                support["evidence_predicates"].append(row)
            claim_subject = "(?:" + _subject_pattern(subject) + r"|^(?:It|This practice|This capability))"
            match = re.search(claim_subject + r"\s+(is|are|includes?|does not include|excludes)\s+(.+)", sentence, re.I)
            if match:
                negative = bool(re.search(r"\b(?:is not|are not|does not include)\b", match.group(), re.I))
                negative = negative or match[1].lower() == "excludes"
                role = "meaning" if match[1].lower() in {"is", "are"} else "membership"
                obj = re.sub(r"^not\s+", "", match[2].lower())
                obj = re.sub(r"^(?:a|an|the)\s+", "", obj).rstrip(".!?")
                for proposition in re.split(r",|\s+and\s+", obj) if role == "membership" else [obj]:
                    assertions.append(((role, proposition.strip()), negative))
    return support, assertions, bool(full)


def evaluate_capability_support(subject, sources, *, candidate, overlap, atomicity, known,
                                authority_registry_path=None):
    accepted = {field: [] for field in FIELDS}
    tentative = {field: [] for field in FIELDS}
    origins = {}
    tentative_origins = set()
    diagnostics = []
    document_origins = {}
    claims = {}
    conflicts = []
    for source in sources:
        evidence = source["evidence"]
        governance = capability_source_governance(evidence.get("url", ""), subject, registry_path=authority_registry_path)
        support, assertions, full = extract_support(subject, evidence)
        origin = governance.get("origin_id")
        if governance.get("conflict"):
            conflicts.append(governance["conflict"])
        content = str(evidence.get("raw_content") or evidence.get("content") or "")
        references = sorted(set(re.findall(r"\b(?:NIST\s+SP\s+\d+(?:-\d+)?|RFC\s+\d+|ISO(?:/IEC)?\s+\d+)\b", content, re.I)
                                + [u.rstrip(".,;)") for u in re.findall(r"https?://[^\s<>]+", content)]))[:3]
        diagnostic = {"url": evidence.get("url"), "governance": governance, "support": support,
                      "explicit_references": references,
                      "raw_evidence_fingerprint": fingerprint(evidence), "retrieved_document_text": full}
        source["capability_support"] = diagnostic
        diagnostics.append(diagnostic)
        if not governance["governed"]:
            continue
        tentative_origins.add(origin)
        if full:
            bound_text = " ".join(block for _, _, block in subject_blocks(subject, content))
            document_key = fingerprint(" ".join(bound_text.lower().split()))
            # Even separately declared origins cannot turn an exact syndicated
            # document into independent corroboration.
            origin = document_origins.setdefault(document_key, origin)
            diagnostic["effective_origin_id"] = origin
        for _, _, block in subject_blocks(subject, content):
            for sentence in re.split(r"(?<=[.!?])\s+|\n", block):
                implication = re.search(r"\b(?:using|usage|use of|mention of)\b[^.!?]*\b(?:alone|automatically|always)\b[^.!?]*\b(?:proves?|demonstrates?)\b", sentence, re.I)
                if implication and not re.search(r"\b(?:not|never)\b", implication.group(), re.I):
                    conflicts.append("Unsafe broader implication from technology use")
        for field in FIELDS:
            enriched = [{**r, "origin_id": origin} for r in support[field]]
            tentative[field].extend(enriched)
            if full:
                accepted[field].extend(enriched)
        if full:
            item = origins.setdefault(origin, {"kind": governance["kind"], "fields": set(), "definition_tokens": set()})
            item["fields"].update(f for f in FIELDS if support[f])
            for row in support["definition"]:
                tokens = set(re.findall(r"[a-z]{3,}", row["text"].lower())) - STOP - set(subject.lower().split())
                item["definition_tokens"].update(tokens)
        # Contradictions in governed snippets also block (never improve eligibility).
        for obj, negative in assertions:
            claims.setdefault(obj, set()).add(negative)
        for row in support["definition"]:
            if re.search(r"\b(?:is|are)\s+(?:a|an|the)\s+(?:software tool|programming language|software product|runtime|software framework)\b", row["text"], re.I):
                conflicts.append("Capability / technology identity confusion")
    if any(len(polarity) > 1 for polarity in claims.values()):
        conflicts.append("Contradictory governed source semantics")
    if overlap["exact_matches"] or overlap["high_overlap_candidates"]:
        conflicts.append("Existing taxonomy overlap requires human boundary review")
    if atomicity["atomicity_status"] == "compound_requires_decomposition":
        conflicts.append("Candidate requires decomposition")
    elif atomicity["atomicity_status"] not in {"atomic", "coherent_capability_concept"}:
        conflicts.append("Candidate atomicity / coherence unresolved")
    if known.get("technology_id"):
        conflicts.append("Capability / technology identity confusion")
    # Definition heads must share bounded meaning, not just the subject name.
    defining = [o for o in origins.values() if "definition" in o["fields"]]
    for index, left in enumerate(defining):
        for right in defining[index + 1:]:
            if len(left["definition_tokens"] & right["definition_tokens"]) < 2:
                conflicts.append("Candidate scope drift / definition convergence unresolved")
    normative = any(o["kind"] == "normative" and "definition" in o["fields"] for o in origins.values())
    strong = [o for o in origins.values() if o["kind"] in {"normative", "strong_technical"}]
    convergence = len([o for o in strong if {"definition", "boundaries"} <= o["fields"]]) >= 2
    corroboration = any("definition" in o["fields"] for o in strong) and any(
        {"boundaries", "responsibilities", "evidence_predicates", "exclusions"} <= other["fields"]
        for origin, o in origins.items() if o in strong
        for other_origin, other in origins.items() if other_origin != origin)
    path = "normative" if normative else "independent_convergence" if convergence else "independent_corroboration" if corroboration else None
    missing = list(dict.fromkeys(MISSING[f] for f in FIELDS if not accepted[f]))
    if not path:
        missing.append("AUTHORITY_INSUFFICIENT")
    if conflicts:
        missing.append("DISTINCTNESS_UNCERTAIN")
    eligible = bool(path) and all(accepted.values()) and not conflicts and bool(candidate.get("provenance"))
    return {"version": SUFFICIENCY_VERSION, "fields": {f: {"status": "supported" if accepted[f] else "missing",
                "evidence": accepted[f], "tentative_evidence": tentative[f]} for f in FIELDS},
            "independent_governed_origins": len(origins), "origin_ids": sorted(origins),
            "tentative_governed_origin_ids": sorted(tentative_origins),
            "support_path": path, "conflicts": sorted(set(conflicts)), "missing_evidence": missing,
            "source_diagnostics": diagnostics, "outcome": "eligible_for_human_review" if eligible else "research_more",
            "eligible_for_human_review": eligible, "human_review_required": True,
            "automatic_approval": False, "automatic_publication": False}


def escalation_plan(subject, bundle, *, research_round=1):
    """One deficiency, one query, bounded explicit execution; no lead fetch here."""
    if bundle.get("eligible_for_human_review"):
        return {"missing_evidence": [], "chosen_deficiency": None, "query": None,
                "reason": "Sufficient for human review; no additional research planned",
                "planned_domains": [], "planned_scopes": [], "authoritative_leads": [],
                "call_budget": 0, "maximum_rounds": 3, "automatic_execution": False,
                "discovered_domains_are_governed": False}
    missing = bundle.get("missing_evidence", [])
    priority = ["DEFINITION_MISSING", "BOUNDARY_MISSING", "RESPONSIBILITIES_MISSING",
                "EVIDENCE_PREDICATES_MISSING", "EXCLUSIONS_MISSING", "DISTINCTNESS_UNCERTAIN", "AUTHORITY_INSUFFICIENT"]
    chosen = next((m for m in priority if m in missing), "DISTINCTNESS_UNCERTAIN")
    terms = {"DEFINITION_MISSING": "normative definition architecture overview",
             "BOUNDARY_MISSING": "scope boundaries architecture guidance",
             "RESPONSIBILITIES_MISSING": "engineering responsibilities implementation guidance",
             "EVIDENCE_PREDICATES_MISSING": "implementation documentation demonstrable project artifacts evidence",
             "EXCLUSIONS_MISSING": "limitations non-proving examples exclusions",
             "DISTINCTNESS_UNCERTAIN": "comparisons adjacent concepts anti-examples distinctions",
             "AUTHORITY_INSUFFICIENT": "primary standards government professional definition"}
    leads = []
    # Only explicit references from governed documents; leads never inherit authority.
    for diagnostic in bundle.get("source_diagnostics", []):
        if not diagnostic["governance"]["governed"]:
            continue
        leads.extend(diagnostic.get("explicit_references", []))
        for field in diagnostic["support"].values():
            for row in field:
                for ref in re.findall(r"\b(?:NIST\s+SP\s+\d+(?:-\d+)?|RFC\s+\d+|ISO(?:/IEC)?\s+\d+)\b", row["text"], re.I):
                    leads.append(ref)
                for url in re.findall(r"https?://[^\s<>]+", row["text"]):
                    leads.append(url.rstrip(".,;)"))
    leads = sorted(set(leads))[:3]
    query = f"{subject} {terms[chosen]}"
    domains = []
    if "AUTHORITY_INSUFFICIENT" in missing and leads:
        chosen = "AUTHORITY_INSUFFICIENT"
        query = f"{leads[0]} {subject} primary source scope implementation"
        if leads[0].upper().startswith("NIST"):
            domains = ["nist.gov"]
        elif leads[0].upper().startswith("RFC"):
            domains = ["rfc-editor.org"]
        elif leads[0].startswith("https://"):
            domains = [urlsplit(leads[0]).hostname]
    scopes = leads[:1] if leads and chosen == "AUTHORITY_INSUFFICIENT" else []
    if "AUTHORITY_INSUFFICIENT" in missing and not leads:
        governed_documents = [d for d in bundle.get("source_diagnostics", [])
                              if d["governance"]["governed"] and d["support"]["definition"]]
        if governed_documents and not bundle.get("independent_governed_origins"):
            chosen = "AUTHORITY_INSUFFICIENT"
            document = governed_documents[0]
            deficient = next((f for f in ("boundaries", "responsibilities", "evidence_predicates", "exclusions")
                              if not bundle.get("fields", {}).get(f, {}).get("tentative_evidence")), "evidence_predicates")
            query = f"{document['url']} {subject} {terms[MISSING[deficient]]}"
            domains = [urlsplit(document["url"]).hostname]
            scopes = [document["governance"]["scope"]]
    return {"missing_evidence": missing, "chosen_deficiency": chosen, "query": query,
            "reason": "Target missing support: " + chosen, "authoritative_leads": leads,
            "planned_domains": domains, "planned_scopes": scopes, "primary_source_must_be_retrieved": True,
            "call_budget": 1 if research_round <= 2 else 0, "maximum_rounds": 3,
            "automatic_execution": False, "discovered_domains_are_governed": False}

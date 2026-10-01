"""TQ-D3 v1.6: explicit Search, immutable evidence, deterministic draft interpretation.

No model, approval, publishing, scoring, or production knowledge writes.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from database.taxonomy_discovery_review_manager import (
    list_focused_verification_results, save_focused_verification_result,
)
from tailoring.capability_taxonomy import classify_requirement_record, get_default_taxonomy
from taxonomy_discovery.focused_verification_targets import (
    FOCUSED_VERIFICATION_TARGET_VERSION, TARGET_REGISTRY_RELATIONSHIP,
    TARGET_TECHNOLOGY_IDENTITY, TARGET_IDENTITY_DISAMBIGUATION,
)
from taxonomy_discovery.research_proposals import PROPOSAL_CONTRACT_VERSION, validate_proposal_bundle
from taxonomy_discovery.source_authority import (
    PRIMARY_OFFICIAL, classify_candidate_source_url, load_source_authority_registry,
)
from taxonomy_discovery.tavily_research import build_tavily_search_request, research_target_with_tavily
from taxonomy_discovery.technology_registry import get_default_registry, normalise, resolve_requirement_text

FOCUSED_VERIFICATION_VERSION = "tqd3-focused-verification-v1.6.1"
MAX_FOCUSED_BATCH = 3


def focused_target_signature(target: dict[str, Any]) -> str:
    """Execution context excludes changing display/source-count metadata."""
    return json.dumps({key: target.get(key) for key in (
        "target_version", "target_id", "candidate_id", "canonical_name", "route",
        "questions", "taxonomy_capability_ids",
    )}, sort_keys=True)


def focused_search_target(target: dict[str, Any]) -> dict[str, Any]:
    """Adapt the v1.5 questions verbatim to the existing focused Search adapter."""
    if target.get("target_version") != FOCUSED_VERIFICATION_TARGET_VERSION:
        raise ValueError("Unsupported focused target version")
    if target.get("governance", {}).get("generated_from_confirmed_candidate") is not True:
        raise ValueError("Only confirmed candidates may execute")
    if target.get("route") not in {
        TARGET_TECHNOLOGY_IDENTITY, TARGET_REGISTRY_RELATIONSHIP, TARGET_IDENTITY_DISAMBIGUATION
    }:
        raise ValueError("Unsupported focused verification route")
    if not all(target.get(key) for key in ("target_id", "candidate_id", "canonical_name")):
        raise ValueError("Focused target identity is incomplete")
    questions = target.get("questions")
    if not isinstance(questions, list) or not questions or any(
        not isinstance(q, str) or not q.strip() for q in questions
    ):
        raise ValueError("Focused target questions are required")
    adapted = {
        "target_id": target["target_id"], "target_type": target["route"],
        "label": target["canonical_name"], "tavily_eligible": True,
        "research_question": "\n".join(questions),
        "research_question_version": target["target_version"],
    }
    build_tavily_search_request(adapted)  # Validate the whole batch before execution.
    return adapted


def execute_focused_verification(targets, *, selected_target_ids, explicit_execution=False,
                                 research_more=False, db_path=None, api_key=None, transport=None):
    if explicit_execution is not True:
        raise ValueError("Focused verification requires explicit execution")
    by_id = {t["target_id"]: t for t in targets}
    selected = list(dict.fromkeys(selected_target_ids))
    if not selected or len(selected) > MAX_FOCUSED_BATCH:
        raise ValueError(f"Select between 1 and {MAX_FOCUSED_BATCH} focused targets")
    if any(tid not in by_id for tid in selected):
        raise ValueError("Unknown selected focused target")
    adapted = {tid: focused_search_target(by_id[tid]) for tid in selected}
    saved = list_focused_verification_results(db_path=db_path)
    output = []
    for tid in selected:
        existing = next((row for row in saved if focused_target_signature(row["result"].get("target", {}))
                         == focused_target_signature(by_id[tid])), None)
        if existing and not research_more:
            output.append(existing)
            continue
        result = research_target_with_tavily(
            adapted[tid], api_key=api_key, transport=transport, preserve_raw_response=True
        )
        result.update({"verification_version": FOCUSED_VERIFICATION_VERSION,
                       "candidate_id": by_id[tid]["candidate_id"], "target": deepcopy(by_id[tid]),
                       "completed_at": datetime.now(timezone.utc).isoformat()})
        # Save each completion immediately so a later batch failure cannot lose evidence.
        output.append(save_focused_verification_result(result, db_path=db_path))
    return output


def _definition_sentences(name: str, content: str) -> list[str]:
    # Deliberately limited to affirmative, subject-specific statements. A page's
    # navigation, search answer, or name mention alone does not verify an identity.
    pattern = re.compile(r"^" + re.escape(name) + r"\s+(?:is\s+(?:an?|the)\s+|provides\s+|supports\s+)", re.I)
    return [sentence.strip() for sentence in re.split(r"[\n.!?](?:\s+|$)", content)
            if pattern.search(sentence.strip()) and not re.search(
                r"\b(?:not|never|unrelated|deprecated|formerly|different|discontinued)\b", sentence, re.I)]



def _configured_safe_identity_aliases(
    name: str,
    rules: dict[str, Any],
) -> list[str]:
    """Return only human-versioned exact identity aliases; never trust provider alias prose."""
    key = normalise(name)
    aliases = {name}
    for rule in rules.get("technology_domains", []) or []:
        if not isinstance(rule, dict):
            continue
        technology_aliases = {
            normalise(value)
            for value in rule.get("technology_aliases", []) or []
            if str(value or "").strip()
        }
        if key not in technology_aliases:
            continue
        aliases.update(
            str(value).strip()
            for value in rule.get("safe_identity_aliases", []) or []
            if str(value or "").strip()
        )
    return sorted(aliases, key=str.casefold)


def interpret_focused_verification(result: dict[str, Any], *, authority_registry_path=None) -> dict[str, Any]:
    target = result["target"]
    name = target["canonical_name"]
    registry = get_default_registry()
    taxonomy = get_default_taxonomy()
    known = resolve_requirement_text(name, registry=registry)
    exact_entries = [entry for entry in registry.entries if
                     normalise(name) in {normalise(entry.get("label")),
                                         *(normalise(a) for a in entry.get("aliases", []))}]
    canonical_capability = classify_requirement_record({"text": name}, taxonomy)
    raw_sources = result.get("raw_provider_response", {}).get("results", [])
    raw_sources = raw_sources if isinstance(raw_sources, list) else []
    sources = []
    definitions = []
    contradictory = False
    for raw in raw_sources:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "")
        classification = classify_candidate_source_url(
            {"canonical_name": name}, url, registry_path=authority_registry_path
        )  # Never adopt provider maintainer or authoritative claims as domain rules.
        sentences = _definition_sentences(name, str(raw.get("content") or ""))
        official = classification["authority"] == PRIMARY_OFFICIAL and urlsplit(url).scheme in {"http", "https"}
        content = str(raw.get("content") or "")
        if official and re.search(re.escape(name) + r"\s+(?:is\s+not|is\s+a\s+different)\b", content, re.I):
            contradictory = True
        accepted = official and bool(sentences)
        sources.append({"title": str(raw.get("title") or name), "url": url,
                        "classification": classification, "identity_supported": accepted,
                        "evidence_sentences": sentences if accepted else []})
        if accepted:
            definitions.extend(sentences)
    primary = [s for s in sources if s["identity_supported"]]
    capabilities = set(target.get("taxonomy_capability_ids", []))
    supported = set()
    for sentence in definitions:
        capability = classify_requirement_record({"text": sentence}, taxonomy)
        if capability:
            supported.add(capability["capability_id"])
    if len(exact_entries) > 1 or known["status"] == "ambiguous":
        outcome = "ambiguous_identity"
    elif known["status"] == "resolved":
        outcome = "no_change"
    elif contradictory:
        outcome = "ambiguous_identity"
    elif not primary:
        outcome = "insufficient_evidence"
    elif target["route"] == TARGET_REGISTRY_RELATIONSHIP:
        if len(capabilities) != 1 or not capabilities.issubset(taxonomy.by_id()):
            outcome = "ambiguous_identity"
        else:
            canonical_capability_id = (canonical_capability or {}).get("capability_id")
            internally_supported = canonical_capability_id in capabilities
            externally_supported = supported == capabilities
            if internally_supported or externally_supported:
                outcome = "verified_registry_relationship"
            else:
                outcome = "needs_more_research"
    else:
        outcome = "verified_identity"
    # Safe aliases come only from exact local identity knowledge or explicit,
    # versioned identity-alias rules. Provider-proposed aliases remain untrusted.
    entry = exact_entries[0] if len(exact_entries) == 1 else None
    rules = load_source_authority_registry(authority_registry_path)
    aliases = set(_configured_safe_identity_aliases(name, rules))
    if entry:
        aliases.update(str(value).strip() for value in entry.get("aliases", []) if str(value).strip())
    aliases = sorted(aliases, key=str.casefold)
    official_hosts = {s["classification"]["hostname"] for s in primary}
    organizations = sorted({rule["organization_aliases"][0]
                            for rule in rules.get("organization_domains", [])
                            if rule.get("organization_aliases") and any(
                                host == domain or host.endswith("." + domain)
                                for host in official_hosts for domain in rule.get("official_domains", []))})
    return {"version": FOCUSED_VERIFICATION_VERSION, "target_id": target["target_id"],
            "candidate_id": target["candidate_id"], "canonical_name": name,
            "outcome": outcome, "sources": sources, "authoritative_sources": primary,
            "safe_aliases": aliases, "recognized_first_party_organizations": organizations,
            "maintainer": "Not inferred; review first-party evidence",
            "existing_registry_knowledge": known, "existing_entry": deepcopy(entry),
            "existing_taxonomy_knowledge": canonical_capability,
            "supported_capability_ids": sorted(supported),
            "relationship_evidence": {
                "canonical_name_capability_id": (canonical_capability or {}).get("capability_id"),
                "external_supported_capability_ids": sorted(supported),
                "target_capability_ids": sorted(capabilities),
                "basis": (
                    "exact_internal_taxonomy"
                    if outcome == "verified_registry_relationship"
                    and (canonical_capability or {}).get("capability_id") in capabilities
                    else "official_source_content"
                    if outcome == "verified_registry_relationship"
                    else "none"
                ),
            },
            "proposed_capability_id": next(iter(capabilities)) if outcome == "verified_registry_relationship" else None,
            "model_calls": 0, "scoring_influence": False}


def build_focused_draft(result: dict[str, Any], interpretation: dict[str, Any]) -> dict[str, Any]:
    outcome = interpretation["outcome"]
    entry = interpretation["existing_entry"]
    action = "research_more"
    if outcome == "no_change":
        action = "no_change"
    elif outcome == "verified_registry_relationship":
        action = "add_technology_capability_relationship"
    elif outcome == "verified_identity":
        if entry:
            action = "add_safe_alias" if interpretation["canonical_name"] not in entry["aliases"] else "route_to_capability_research"
        else:
            action = "add_technology_identity"
    identity = json.dumps({"request": result["provider_request_id"], "interpretation": interpretation}, sort_keys=True)
    draft_id = "tqd3draft_" + hashlib.sha256(identity.encode()).hexdigest()[:24]
    proposal = None
    if action in {"add_technology_identity", "add_safe_alias", "add_technology_capability_relationship"}:
        name = interpretation["canonical_name"]
        technology_id = entry["technology_id"] if entry else "focused." + hashlib.sha256(normalise(name).encode()).hexdigest()[:16]
        proposal = {
            "proposal_id": draft_id, "technology_id": technology_id, "label": name,
            "entry_kind": (
                entry.get("entry_kind", "tool")
                if entry
                else "language"
                if str(interpretation.get("proposed_capability_id") or "").startswith("language.")
                else "tool"
            ),
            "aliases": interpretation["safe_aliases"],
            "proposal_classification": "safe_mapping_candidate" if action == "add_technology_capability_relationship" else "recognized_unmapped",
            "proposed_capability_id": interpretation["proposed_capability_id"],
            "relationship_type": "maps_to_capability" if interpretation["proposed_capability_id"] else None,
            "confidence": 0.8, "summary": f"Focused verification draft: {action}. Human review required.",
            "sources": [{"title": s["title"], "url": s["url"], "publisher": s["classification"]["hostname"]}
                        for s in interpretation["authoritative_sources"]],
        }
    bundle = validate_proposal_bundle({
        "proposal_bundle_version": PROPOSAL_CONTRACT_VERSION,
        "taxonomy_version": get_default_taxonomy().version,
        "registry_version": get_default_registry().version,
        "research_method": f"{FOCUSED_VERIFICATION_VERSION}; request={result['provider_request_id']}; target={result['target_id']}",
        "proposals": [proposal] if proposal else [],
    })
    return {"draft_id": draft_id, "target_id": result["target_id"], "candidate_id": result["candidate_id"],
            "provider_request_id": result["provider_request_id"], "action": action, "status": "draft",
            "requires_human_approval": True, "proposal_bundle": bundle,
            "registry_mutations": 0, "taxonomy_mutations": 0, "scoring_influence": False}

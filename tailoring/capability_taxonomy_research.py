"""Offline proposals; no scoring, network, DB, or taxonomy mutation.

HumanReview is produced by explicit local review, never imported from provider
JSON. Its fingerprint binds content, not authentication. Trusted local receipts
must be stored separately from untrusted research imports by the admin caller.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib
import ipaddress
import json
import math
from pathlib import Path
import re
from typing import Protocol
from urllib.parse import urlsplit
from tailoring.capability_taxonomy import get_default_taxonomy

SCHEMA_VERSION = "capability-taxonomy-research-handover-v1"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "taxonomy/capability_taxonomy_research_handover_schema_v1.json"


class CapabilityResearchProvider(Protocol):
    provider_name: str
    def search(self, query: str, *, administrative: bool = False, max_results: int = 5) -> list[dict]: ...


def build_research_queries(terms: list[str]) -> list[dict]:
    """Explicit, de-identified capability phrases only; no report objects."""
    if not isinstance(terms, list) or len(terms) > 50:
        raise ValueError("Expected at most 50 capability phrases")
    rows, seen = [], set()
    for term in terms:
        if not isinstance(term, str):
            raise ValueError("Capability phrases must be strings")
        term = " ".join(term.split())
        if len(term) > 300 or "@" in term or "://" in term:
            raise ValueError("Supply a short de-identified capability phrase")
        if term and term.casefold() not in seen:
            seen.add(term.casefold())
            rows.append({"observed_term": term, "query": f"{term} official documentation technical definition"})
    return rows


def _validate(value, schema, path="$", depth=0):
    # Implements precisely the subset used by the shipped JSON Schema.
    if depth > 20:
        raise ValueError("Proposal nesting limit")
    kind = schema.get("type")
    expected = {"object": dict, "array": list, "string": str}
    if kind in expected and type(value) is not expected[kind]:
        raise ValueError(f"{path}: expected {kind}")
    if kind == "number" and (type(value) not in (int, float) or not math.isfinite(value)):
        raise ValueError(f"{path}: expected finite number, not boolean")
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"{path}: invalid constant")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: invalid enum")
    if kind == "object":
        if set(value) != set(schema["properties"]):
            raise ValueError(f"{path}: missing or unknown fields")
        for key, child in schema["properties"].items():
            _validate(value[key], child, path + "." + key, depth + 1)
    elif kind == "array":
        if not schema["minItems"] <= len(value) <= schema["maxItems"]:
            raise ValueError(f"{path}: array bounds")
        for i, child in enumerate(value):
            _validate(child, schema["items"], f"{path}[{i}]", depth + 1)
    elif kind == "string":
        if not schema["minLength"] <= len(value) <= schema["maxLength"] or not value.strip():
            raise ValueError(f"{path}: string bounds")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise ValueError(f"{path}: invalid identifier")
    elif kind == "number" and not schema["minimum"] <= value <= schema["maximum"]:
        raise ValueError(f"{path}: number bounds")


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Timezone-aware ISO timestamp required") from None


def _source_url(value, *, approvable):
    try:
        url = urlsplit(value)
        host = (url.hostname or "").lower()
        if url.scheme not in {"http", "https"} or not host or url.username or url.password or url.fragment:
            raise ValueError()
        _ = url.port
        if approvable:
            if host in {"localhost", "example.com", "example.org", "example.net"} or host.endswith((".invalid", ".localhost", ".test", ".example", ".local")):
                raise ValueError()
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError()
            if address is None and ("." not in host or not re.fullmatch(r"[a-z0-9.-]+", host)):
                raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("Invalid or placeholder research source URL") from None


def validate_research_handover(payload, taxonomy=None, *, approvable=False):
    taxonomy = taxonomy or get_default_taxonomy()
    _validate(payload, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    _timestamp(payload["generated_at"])
    if payload["taxonomy_base_version"] != taxonomy.version:
        raise ValueError("Stale taxonomy base version")
    candidates = payload["candidates"]
    ids = [c["candidate_id"] for c in candidates]
    proposed = [c["proposed_capability_id"] for c in candidates]
    if len(set(ids)) != len(ids) or len(set(proposed)) != len(proposed):
        raise ValueError("Duplicate candidate/capability ID")
    existing = set(taxonomy.by_id())
    for candidate in candidates:
        pid = candidate["proposed_capability_id"]
        if (candidate["intent"] == "create" and pid in existing) or (candidate["intent"] == "update" and pid not in existing):
            raise ValueError("Create/update intent conflicts with existing taxonomy")
        rels = candidate["relationships"]
        rel_ids = [r["relationship_id"] for r in rels]
        if len(set(rel_ids)) != len(rel_ids) or "candidate" in rel_ids:
            raise ValueError("Duplicate/reserved relationship ID")
        for rel in rels:
            target, resolution = rel["target_capability_id"], rel["target_resolution"]
            if target == pid:
                raise ValueError("Self relationship")
            if resolution == "existing" and target not in existing:
                raise ValueError("Missing existing relationship target")
            if resolution == "proposed" and target not in proposed:
                raise ValueError("Missing proposed relationship target")
            if resolution == "unresolved" and approvable:
                raise ValueError("Unresolved relationships cannot be approved")
            if rel["relationship"] in {"related_to", "commonly_used_technology", "non_equivalent_to"} and rel["runtime_support_level"] != "none":
                raise ValueError("Related technology is not executable evidence support")
        sources = candidate["research"]["sources"]
        if len({s["source_id"] for s in sources}) != len(sources):
            raise ValueError("Duplicate source ID")
        supported = set()
        for source in sources:
            _source_url(source["url"], approvable=approvable)
            for claim in source["supports"]:
                rid = claim["relationship_id"]
                if rid not in set(rel_ids) | {"candidate"}:
                    raise ValueError("Claim references unknown relationship")
                supported.add(rid)
        if not set(rel_ids).issubset(supported) or "candidate" not in supported:
            raise ValueError("Each relationship and candidate need linked source claims")
    return deepcopy(payload)


def proposal_fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class HumanReview:
    proposal_fingerprint: str
    reviewer_identity: str
    reviewed_at: str
    rationale: str


def review_proposal(payload, *, reviewer_identity, reviewed_at, rationale, explicit_human_confirmation=False, taxonomy=None):
    if explicit_human_confirmation is not True:
        raise ValueError("Explicit local human review confirmation required")
    validate_research_handover(payload, taxonomy, approvable=True)
    if not isinstance(reviewer_identity, str) or not 1 <= len(reviewer_identity.strip()) <= 200:
        raise ValueError("Reviewer identity required")
    if not isinstance(rationale, str) or not 20 <= len(rationale.strip()) <= 4000:
        raise ValueError("Substantive review rationale required")
    _timestamp(reviewed_at)
    return HumanReview(proposal_fingerprint(payload), reviewer_identity.strip(), reviewed_at, rationale.strip())


def reviewed_change_proposal(payload, review, taxonomy=None):
    if type(review) is not HumanReview:
        raise ValueError("Provider approval is not a trusted local HumanReview")
    validate_research_handover(payload, taxonomy, approvable=True)
    if review.proposal_fingerprint != proposal_fingerprint(payload):
        raise ValueError("Reviewed proposal changed; approval invalid")
    return {"kind": "reviewed_taxonomy_change_proposal", "proposal": deepcopy(payload),
            "human_review": asdict(review), "installs_taxonomy": False}

"""Pure canonical Candidate Context exports; never read or update a database."""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from database.application_profile_manager import build_work_application_payload

CANDIDATE_CONTEXT_VERSION = "candidate-context-bundle-v1"
_EVIDENCE_FIELDS = (
    "id", "evidence_id", "project_id", "category", "title", "display_title",
    "subtitle", "period", "description", "bullets", "canonical_bullets",
    "skills", "tools", "resume_header_tools", "resume_header_context",
    "impact", "scope", "source_type", "source", "source_metadata",
    "provenance", "created_at", "updated_at",
)


def context_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)


def context_fingerprint(value: Any) -> str:
    return hashlib.sha256(context_json(value).encode("utf-8")).hexdigest()


def build_generation_candidate_context(generation: dict) -> dict:
    """Export the already-frozen source facts; omit scores and model claims."""
    pool = generation.get("candidate_pool") or []
    if not isinstance(pool, list):
        raise ValueError("Frozen candidate pool is unavailable.")
    evidence = []
    for candidate in pool:
        item = {key: deepcopy(candidate[key]) for key in _EVIDENCE_FIELDS if key in candidate}
        for source in ("resume_evidence", "evidence_library_evidence"):
            if isinstance(candidate.get(source), dict):
                item[source] = {key: deepcopy(candidate[source][key]) for key in _EVIDENCE_FIELDS if key in candidate[source]}
        evidence.append(item)
    profile = {"projects": deepcopy((generation.get("project_inputs") or {}).get("resume_projects") or [])}
    from tailoring.stable_tailoring_ranking import build_candidate_evidence_profile
    payload = _context_payload(profile, evidence)
    # These are the same record/project IDs consumed by project_relevance;
    # canonical source text above remains exact, while this existing projection
    # records the ranker's normalized evidence text without treating it as raw.
    payload["project_evidence_profile"] = build_candidate_evidence_profile(pool)
    payload["profile_fidelity"] = "frozen_generation_resume_projects_only"
    payload["context_fingerprint"] = context_fingerprint({k: v for k, v in payload.items() if k != "context_fingerprint"})
    return payload


def _context_payload(canonical_profile: dict, evidence: list[dict]) -> dict:
    evidence = deepcopy(evidence)
    for item in evidence:
        if not any(item.get(key) is not None for key in ("id", "evidence_id", "project_id")):
            item["evidence_id"] = "context_" + context_fingerprint(item)
    evidence.sort(key=lambda item: (str(item.get("id", item.get("evidence_id", ""))), context_json(item)))
    payload = {
        "schema_version": CANDIDATE_CONTEXT_VERSION,
        "profile": deepcopy(canonical_profile),
        "evidence_library": evidence,
        "source_fingerprints": {
            "profile": context_fingerprint(canonical_profile),
            "evidence_library": context_fingerprint(evidence),
        },
    }
    return {**payload, "context_fingerprint": context_fingerprint(payload)}


def build_candidate_context(profile: dict, evidence_items: list[dict]) -> dict:
    # Reuse the profile's existing supported-field boundary, but do not use the
    # Work export's lossy evidence projection (it strips IDs/header provenance).
    canonical_profile = build_work_application_payload(profile, evidence_items=[])[
        "application_profile"
    ]
    evidence = [
        {key: deepcopy(item[key]) for key in _EVIDENCE_FIELDS if key in item}
        for item in evidence_items
    ]
    return _context_payload(canonical_profile, evidence)


def candidate_context_downloads(profile: dict, evidence_items: list[dict]) -> dict[str, str]:
    bundle = build_candidate_context(profile, evidence_items)
    # Fenced JSON in Markdown preserves canonical text exactly, including
    # whitespace, nested provenance, ordered bullets and technical punctuation.
    def markdown(title: str, value: Any) -> str:
        body = context_json(value)
        fence = "`" * max(3, 1 + max(map(len, re.findall(r"`+", body)), default=0))
        return f"# {title}\n\n{fence}json\n{body}\n{fence}\n"

    return {
        "candidate_profile.json": context_json(bundle["profile"]),
        "candidate_profile.md": markdown("Candidate Profile", bundle["profile"]),
        "evidence_library.json": context_json(bundle["evidence_library"]),
        "evidence_library.md": markdown("Evidence Library", bundle["evidence_library"]),
        "candidate_context.json": context_json(bundle),
    }

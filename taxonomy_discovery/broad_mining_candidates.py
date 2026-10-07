"""Deterministic candidate extraction for TQ-D3 Broad Mining."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from taxonomy_discovery.source_authority import enrich_candidates_with_source_authority


BROAD_MINING_CANDIDATE_VERSION = "tqd3-broad-mining-candidates-v1.0.0"

STATUS_ALREADY_KNOWN = "already_known"
STATUS_POSSIBLE_NEW = "possible_new_technology"
STATUS_AMBIGUOUS = "ambiguous_registry_match"

_WS_RE = re.compile(r"\s+")


def _clean(value: Any) -> str:
    return _WS_RE.sub(" ", str(value or "")).strip()


def _exact_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", _clean(value))
    return text.casefold()


def default_registry_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "taxonomy"
        / "technology_registry_v1.json"
    )


def _load_registry_entries(
    registry_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    path = (
        Path(registry_path).expanduser().resolve()
        if registry_path is not None
        else default_registry_path()
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError(
            "Technology registry must contain an entries array"
        )
    return [
        deepcopy(row)
        for row in rows
        if isinstance(row, dict)
    ]


def build_exact_registry_alias_index(
    registry_path: str | Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}

    for entry in _load_registry_entries(registry_path):
        technology_id = _clean(entry.get("technology_id"))
        label = _clean(entry.get("label"))
        entry_kind = _clean(
            entry.get("entry_kind") or entry.get("kind")
        )
        status = _clean(entry.get("status"))

        aliases: list[str] = []
        for raw in [label, *(entry.get("aliases") or [])]:
            alias = _clean(raw)
            if alias and alias not in aliases:
                aliases.append(alias)

        match = {
            "technology_id": technology_id,
            "label": label,
            "entry_kind": entry_kind,
            "status": status,
            "matched_aliases": [],
        }

        for alias in aliases:
            key = _exact_key(alias)
            if not key:
                continue
            bucket = index.setdefault(key, [])

            existing = next(
                (
                    row
                    for row in bucket
                    if row["technology_id"] == technology_id
                ),
                None,
            )
            if existing is None:
                existing = deepcopy(match)
                bucket.append(existing)
            if alias not in existing["matched_aliases"]:
                existing["matched_aliases"].append(alias)

    for bucket in index.values():
        bucket.sort(
            key=lambda row: (
                row.get("technology_id") or "",
                row.get("label") or "",
            )
        )

    return index


def _candidate_id(canonical_name: str) -> str:
    digest = hashlib.sha256(
        (
            BROAD_MINING_CANDIDATE_VERSION
            + "|"
            + _exact_key(canonical_name)
        ).encode("utf-8")
    ).hexdigest()[:20]
    return f"tqdmincand_{digest}"


def _supporting_urls(row: dict[str, Any]) -> list[str]:
    raw = row.get("supporting_source_urls")
    if not isinstance(raw, list):
        raw = row.get("authoritative_source_urls")
    if not isinstance(raw, list):
        return []

    result: list[str] = []
    seen: set[str] = set()
    for value in raw:
        url = _clean(value)
        if url and url not in seen:
            seen.add(url)
            result.append(url)
    return result


def _iter_results(
    results: dict[str, Any] | Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(results, dict):
        return [results]
    return [
        row
        for row in results
        if isinstance(row, dict)
    ]


def extract_broad_mining_candidates(
    results: dict[str, Any] | Iterable[dict[str, Any]],
    *,
    registry_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Extract deterministic candidates from structured research output.

    ONLY structured_output.technologies[].canonical_name is compared against
    exact registry labels/aliases after Unicode/case/whitespace normalization.
    Purpose, evidence, maintainer text, and source prose are never scanned.
    """

    alias_index = build_exact_registry_alias_index(registry_path)
    merged: dict[str, dict[str, Any]] = {}

    for result in _iter_results(results):
        structured = result.get("structured_output")
        if not isinstance(structured, dict):
            continue
        technologies = structured.get("technologies")
        if not isinstance(technologies, list):
            continue

        domain = _clean(result.get("domain"))
        seed_id = _clean(result.get("seed_id"))
        target_id = _clean(result.get("target_id"))
        request_id = _clean(result.get("provider_request_id"))

        for row in technologies:
            if not isinstance(row, dict):
                continue

            canonical_name = _clean(row.get("canonical_name"))
            if not canonical_name:
                continue

            key = _exact_key(canonical_name)
            matches = deepcopy(alias_index.get(key, []))

            if len(matches) == 1:
                status = STATUS_ALREADY_KNOWN
            elif len(matches) > 1:
                status = STATUS_AMBIGUOUS
            else:
                status = STATUS_POSSIBLE_NEW

            candidate = merged.get(key)
            if candidate is None:
                candidate = {
                    "candidate_id": _candidate_id(canonical_name),
                    "candidate_version": BROAD_MINING_CANDIDATE_VERSION,
                    "canonical_name": canonical_name,
                    "normalized_name": key,
                    "status": status,
                    "entity_types": [],
                    "primary_purposes": [],
                    "maintainers_vendors_or_standards_bodies": [],
                    "adoption_evidence": [],
                    "supporting_source_urls": [],
                    "registry_matches": matches,
                    "domains": [],
                    "seed_ids": [],
                    "target_ids": [],
                    "provider_request_ids": [],
                    "governance": {
                        "untrusted_research": True,
                        "requires_human_review": True,
                        "proposal_creation": False,
                        "taxonomy_mutations": 0,
                        "registry_mutations": 0,
                        "scoring_influence": False,
                        "automatic_promotion": False,
                    },
                }
                merged[key] = candidate
            elif candidate["status"] != status:
                raise ValueError(
                    "Candidate registry status changed for exact same "
                    f"canonical name: {canonical_name}"
                )

            for field_name, value in (
                ("entity_types", row.get("entity_type")),
                ("primary_purposes", row.get("primary_purpose")),
                (
                    "maintainers_vendors_or_standards_bodies",
                    row.get(
                        "maintainer_vendor_or_standards_body"
                    ),
                ),
                ("adoption_evidence", row.get("adoption_evidence")),
                ("domains", domain),
                ("seed_ids", seed_id),
                ("target_ids", target_id),
                ("provider_request_ids", request_id),
            ):
                clean_value = _clean(value)
                if (
                    clean_value
                    and clean_value not in candidate[field_name]
                ):
                    candidate[field_name].append(clean_value)

            for url in _supporting_urls(row):
                if url not in candidate["supporting_source_urls"]:
                    candidate["supporting_source_urls"].append(url)

    candidates = list(merged.values())
    candidates.sort(
        key=lambda row: (
            {
                STATUS_POSSIBLE_NEW: 0,
                STATUS_AMBIGUOUS: 1,
                STATUS_ALREADY_KNOWN: 2,
            }.get(row["status"], 9),
            row["canonical_name"].casefold(),
        )
    )
    return candidates


def build_broad_mining_candidate_report(
    results: dict[str, Any] | Iterable[dict[str, Any]],
    *,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    candidates = extract_broad_mining_candidates(
        results,
        registry_path=registry_path,
    )
    candidates = enrich_candidates_with_source_authority(
        candidates
    )
    counts = {
        STATUS_ALREADY_KNOWN: 0,
        STATUS_POSSIBLE_NEW: 0,
        STATUS_AMBIGUOUS: 0,
    }
    for row in candidates:
        if row["status"] in counts:
            counts[row["status"]] += 1

    return {
        "candidate_version": BROAD_MINING_CANDIDATE_VERSION,
        "candidate_count": len(candidates),
        "status_counts": counts,
        "candidates": candidates,
        "matching_contract": {
            "source_field": "structured_output.technologies[].canonical_name",
            "registry_match": "exact_label_or_alias_only",
            "normalization": "unicode_nfkc_casefold_whitespace",
            "prose_scanning": False,
            "fuzzy_matching": False,
            "semantic_matching": False,
        },
        "governance": {
            "untrusted_research": True,
            "requires_human_review": True,
            "proposal_creation": False,
            "taxonomy_mutations": 0,
            "registry_mutations": 0,
            "scoring_influence": False,
            "automatic_promotion": False,
        },
    }

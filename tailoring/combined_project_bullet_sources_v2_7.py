"""V2.7 deterministic admission of exact Base and Library project bullet evidence.

Base is the confirmed selected résumé, not a generic latest résumé. Source
ownership survives allocation. No new factual claims or inferred skill evidence.
"""
from __future__ import annotations
from typing import Any

POLICY_VERSION = "phase9f-combined-project-bullet-sources-v2.7"


def _lines(obj: Any) -> list[str]:
    if obj is None:
        return []
    if not isinstance(obj, list) or any(not isinstance(x, str) for x in obj):
        raise ValueError("Source project bullets must be a list of strings")
    return [" ".join(x.split()) for x in obj if x.strip()]


def source_bullet_records(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Stable, source-neutral union; exact repeats become one owned-by-both row."""
    if not isinstance(candidate, dict):
        raise ValueError("Candidate must be a dict")
    resume = candidate.get("resume_evidence") or {}
    library = candidate.get("evidence_library_evidence") or {}
    if not isinstance(resume, dict) or not isinstance(library, dict):
        raise ValueError("Source evidence must be a dict")
    # An unattested resume evidence record is not authority for another project.
    if resume and candidate.get("currently_in_resume") is False:
        raise ValueError("Resume evidence ownership contradicts project candidate")
    if library and candidate.get("in_evidence_library") is False:
        raise ValueError("Library evidence ownership contradicts project candidate")
    found: dict[str, dict[str, Any]] = {}
    for source, evidence in (("base", resume), ("library", library)):
        for index, bullet in enumerate(_lines(evidence.get("bullets", [])), start=1):
            key = bullet.casefold()
            if key in found:
                if source not in found[key]["sources"]:
                    found[key]["sources"].append(source)
                continue
            found[key] = {"text": bullet, "sources": [source], "source_index": index}
    # Preserve legacy single-source order and lead-bullet behavior. Only
    # mixed-source pools use neutral, reproducible ordering on equal evidence.
    if resume and library:
        return sorted(found.values(), key=lambda row: row["text"].casefold())
    return list(found.values())


def bullet_sources(candidate: dict[str, Any], bullet: str) -> list[str]:
    key = " ".join(str(bullet).split()).casefold()
    for row in source_bullet_records(candidate):
        if row["text"].casefold() == key:
            return list(row["sources"])
    return []

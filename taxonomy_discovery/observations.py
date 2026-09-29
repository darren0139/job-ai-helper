"""TQ-D1/TQ-D2 deterministic taxonomy-discovery observations.

This module does not research, infer aliases, mutate the taxonomy, or affect
candidate scoring. It only observes whether the current deterministic taxonomy
recognizes score-eligible canonical JD requirements and aggregates unresolved
observations conservatively.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from copy import deepcopy
from typing import Any

from analysis_stability.stable_evidence_scoring import (
    requirement_is_score_eligible,
)
from tailoring.capability_taxonomy import (
    CapabilityTaxonomy,
    classify_requirement_record,
    get_default_taxonomy,
    normalise,
)


DISCOVERY_VERSION = "capability-taxonomy-discovery-v1"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:20]}"


def _requirement_text(row: dict[str, Any]) -> str:
    return _clean(
        row.get("atomic_focus")
        or row.get("text")
        or row.get("parent_text")
    )


def build_taxonomy_resolution_diagnostics(
    stable_analysis: dict[str, Any],
    *,
    taxonomy: CapabilityTaxonomy | None = None,
) -> dict[str, Any]:
    """Classify requirements using canonical then snapshot-pinned registry resolution.

    This function never re-queries today's registry for old snapshots. Canonical
    taxonomy remains authoritative; registry resolution is honored only when it
    was pinned into the same stable-analysis row.
    """
    taxonomy = taxonomy or get_default_taxonomy()
    output_rows: list[dict[str, Any]] = []

    for row in stable_analysis.get("canonical_requirements", []) or []:
        if not isinstance(row, dict) or not requirement_is_score_eligible(row):
            continue
        requirement_text = _requirement_text(row)
        capability = classify_requirement_record(row, taxonomy)
        canonical_id = (
            _clean(capability.get("capability_id"))
            if isinstance(capability, dict) else ""
        )
        registry_resolution = row.get("technology_registry_resolution")
        registry_resolution = (
            registry_resolution if isinstance(registry_resolution, dict) else {}
        )
        registry_id = ""
        if (
            not canonical_id
            and row.get("capability_resolution_source") == "technology_registry"
            and registry_resolution.get("status") == "resolved"
        ):
            registry_id = _clean(
                registry_resolution.get("capability_id") or row.get("capability_id")
            )
        capability_id = canonical_id or registry_id
        if canonical_id:
            source = "canonical_taxonomy"
            reason = "canonical_capability_resolved"
        elif registry_id:
            source = "technology_registry"
            reason = "technology_registry_resolved"
        else:
            source = "unresolved"
            reason = "no_canonical_capability_resolved"
        output_rows.append({
            "requirement_id": _clean(row.get("requirement_id")),
            "requirement_text": requirement_text,
            "importance": _clean(row.get("importance")),
            "match_label": _clean(row.get("match_label") or "none").lower(),
            "status": "resolved" if capability_id else "unresolved",
            "capability_id": capability_id or None,
            "taxonomy_version": taxonomy.version,
            "resolution_source": source,
            "technology_registry_version": _clean(
                registry_resolution.get("registry_version")
                or stable_analysis.get("technology_registry_version")
            ) or None,
            "technology_id": _clean(registry_resolution.get("technology_id")) or None,
            "reason": reason,
        })

    resolved_count = sum(1 for row in output_rows if row["status"] == "resolved")
    return {
        "discovery_version": DISCOVERY_VERSION,
        "taxonomy_version": taxonomy.version,
        "technology_registry_version": _clean(
            stable_analysis.get("technology_registry_version")
        ) or None,
        "eligible_requirement_count": len(output_rows),
        "resolved_count": resolved_count,
        "unresolved_count": len(output_rows) - resolved_count,
        "rows": output_rows,
    }

def build_unresolved_observations(
    taxonomy_resolution: dict[str, Any],
    *,
    discovered_job_id: int,
    job_content_hash: str,
) -> list[dict[str, Any]]:
    """Create stable provenance-preserving observations from unresolved rows only."""
    job_id = int(discovered_job_id or 0)
    content_hash = _clean(job_content_hash)
    taxonomy_version = _clean(taxonomy_resolution.get("taxonomy_version"))

    if job_id <= 0:
        raise ValueError("A positive discovered_job_id is required.")
    if not content_hash:
        raise ValueError("job_content_hash is required.")
    if not taxonomy_version:
        raise ValueError("taxonomy_version is required.")

    observations: list[dict[str, Any]] = []
    for row in taxonomy_resolution.get("rows", []) or []:
        if not isinstance(row, dict) or row.get("status") != "unresolved":
            continue

        requirement_text = _clean(row.get("requirement_text"))
        normalised_text = normalise(requirement_text)
        if not requirement_text or not normalised_text:
            continue

        identity = {
            "discovered_job_id": job_id,
            "job_content_hash": content_hash,
            "requirement_id": _clean(row.get("requirement_id")),
            "normalised_observed_text": normalised_text,
            "taxonomy_version": taxonomy_version,
        }
        observations.append(
            {
                "observation_id": _stable_id("taxobs", identity),
                "discovered_job_id": job_id,
                "job_content_hash": content_hash,
                "requirement_id": identity["requirement_id"],
                "requirement_text": requirement_text,
                "normalised_observed_text": normalised_text,
                "importance": _clean(row.get("importance")),
                "match_label": _clean(row.get("match_label") or "none").lower(),
                "taxonomy_version": taxonomy_version,
                "resolution_reason": _clean(
                    row.get("reason")
                    or "no_canonical_capability_resolved"
                ),
            }
        )

    return sorted(
        observations,
        key=lambda item: (
            item["discovered_job_id"],
            item["requirement_id"],
            item["observation_id"],
        ),
    )


def aggregate_unresolved_observations(
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate exact deterministic normalized text only; do no semantic merging."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw in observations or []:
        if not isinstance(raw, dict):
            continue
        taxonomy_version = _clean(raw.get("taxonomy_version"))
        normalised_text = _clean(raw.get("normalised_observed_text"))
        if taxonomy_version and normalised_text:
            groups[(taxonomy_version, normalised_text)].append(deepcopy(raw))

    candidates: list[dict[str, Any]] = []
    for (taxonomy_version, normalised_text), group in sorted(groups.items()):
        ordered = sorted(
            group,
            key=lambda item: (
                int(item.get("discovered_job_id", 0) or 0),
                _clean(item.get("requirement_id")),
                _clean(item.get("observation_id")),
            ),
        )
        candidate_identity = {
            "taxonomy_version": taxonomy_version,
            "normalised_observed_text": normalised_text,
        }
        observed_terms = sorted(
            {
                _clean(item.get("requirement_text"))
                for item in ordered
                if _clean(item.get("requirement_text"))
            },
            key=lambda value: (value.casefold(), value),
        )
        job_ids = sorted(
            {
                int(item.get("discovered_job_id", 0) or 0)
                for item in ordered
                if int(item.get("discovered_job_id", 0) or 0) > 0
            }
        )
        candidates.append(
            {
                "candidate_id": _stable_id("taxcand", candidate_identity),
                "taxonomy_version": taxonomy_version,
                "normalised_observed_text": normalised_text,
                "observed_terms": observed_terms,
                "observation_count": len(ordered),
                "job_count": len(job_ids),
                "discovered_job_ids": job_ids,
                "observations": ordered,
            }
        )

    return candidates


def build_discovery_report(
    snapshots: list[dict[str, Any]],
    *,
    match_version: str,
    scoring_version: str,
    taxonomy_version: str,
    taxonomy: CapabilityTaxonomy | None = None,
) -> dict[str, Any]:
    """Build a deterministic cross-job report from latest compatible snapshots."""
    taxonomy = taxonomy or get_default_taxonomy()
    snapshot_rows: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    eligible_count = 0
    resolved_count = 0

    for snapshot in sorted(
        [item for item in snapshots or [] if isinstance(item, dict)],
        key=lambda item: (
            int(item.get("discovered_job_id", 0) or 0),
            int(item.get("id", 0) or 0),
        ),
    ):
        stable_analysis = snapshot.get("stable_analysis") or {}
        resolution = build_taxonomy_resolution_diagnostics(
            stable_analysis,
            taxonomy=taxonomy,
        )
        eligible_count += int(resolution.get("eligible_requirement_count", 0) or 0)
        resolved_count += int(resolution.get("resolved_count", 0) or 0)

        job_observations = build_unresolved_observations(
            resolution,
            discovered_job_id=int(snapshot.get("discovered_job_id", 0) or 0),
            job_content_hash=_clean(snapshot.get("job_content_hash")),
        )
        observations.extend(job_observations)
        snapshot_rows.append(
            {
                "snapshot_id": int(snapshot.get("id", 0) or 0),
                "discovered_job_id": int(
                    snapshot.get("discovered_job_id", 0) or 0
                ),
                "job_content_hash": _clean(snapshot.get("job_content_hash")),
                "eligible_requirement_count": resolution[
                    "eligible_requirement_count"
                ],
                "resolved_count": resolution["resolved_count"],
                "unresolved_count": resolution["unresolved_count"],
            }
        )

    observations = sorted(
        observations,
        key=lambda item: (
            item["discovered_job_id"],
            item["requirement_id"],
            item["observation_id"],
        ),
    )
    candidates = aggregate_unresolved_observations(observations)

    return {
        "discovery_version": DISCOVERY_VERSION,
        "match_version": _clean(match_version),
        "scoring_version": _clean(scoring_version),
        "taxonomy_version": _clean(taxonomy_version),
        "snapshot_count": len(snapshot_rows),
        "eligible_requirement_count": eligible_count,
        "resolved_requirement_count": resolved_count,
        "unresolved_observation_count": len(observations),
        "candidate_count": len(candidates),
        "snapshots": snapshot_rows,
        "observations": observations,
        "candidates": candidates,
    }

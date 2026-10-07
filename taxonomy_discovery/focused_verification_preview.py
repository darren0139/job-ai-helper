"""Read-only requirement resolution against temporary draft knowledge; no scoring."""
from __future__ import annotations

from copy import deepcopy

from analysis_stability.stable_evidence_scoring import requirement_is_score_eligible
from tailoring.capability_taxonomy import classify_requirement_record, get_default_taxonomy
from taxonomy_discovery.technology_registry import (
    TechnologyRegistry, _validate_registry, get_default_registry, resolve_requirement_text,
)


def _shadow_registry(draft):
    registry = get_default_registry()
    entries = deepcopy(list(registry.entries))
    if draft.get("status") != "draft" or draft.get("requires_human_approval") is not True:
        raise ValueError("A governed draft is required")
    bundle = draft["proposal_bundle"]
    if bundle["registry_version"] != registry.version or bundle["taxonomy_version"] != get_default_taxonomy().version:
        raise ValueError("Draft knowledge versions are stale")
    for proposal in bundle["proposals"]:
        entry = next((e for e in entries if e["technology_id"] == proposal["technology_id"]), None)
        if entry is None:
            entry = {"technology_id": proposal["technology_id"], "label": proposal["label"],
                     "entry_kind": proposal["entry_kind"], "aliases": [], "capability_relationships": []}
            entries.append(entry)
        entry["aliases"] = sorted(set(entry["aliases"] + proposal["aliases"]))
        if proposal["proposal_classification"] == "safe_mapping_candidate":
            approved = [r for r in entry["capability_relationships"] if
                        r.get("status") == "approved" and r.get("relationship_type") == "maps_to_capability"]
            if any(r["capability_id"] != proposal["proposed_capability_id"] for r in approved):
                raise ValueError("Draft conflicts with authoritative production mapping")
            if not approved:
                # The production resolver understands approved relationships. This
                # hypothetical status exists only in this private, copied overlay.
                entry["capability_relationships"].append({
                    "status": "approved", "relationship_type": "maps_to_capability",
                    "capability_id": proposal["proposed_capability_id"],
                })
    _validate_registry({"registry_version": registry.version, "entries": entries})
    return TechnologyRegistry(registry.version, tuple(entries))


def _resolve(row, registry, taxonomy):
    if (row.get("structured_match_kind") == "programming_language_group"
            and row.get("structured_match_group_mode") == "any"
            and row.get("structured_match_status") in {"applied", "confirmed_existing_direct"}):
        return {"status": "not_applicable", "capability_id": None, "source": "structured_any_language_group"}
    capability = classify_requirement_record(row, taxonomy)
    if capability:
        return {"status": "resolved", "capability_id": capability["capability_id"], "source": "canonical_taxonomy"}
    resolution = resolve_requirement_text(str(row.get("atomic_focus") or row.get("text") or ""), registry=registry)
    return {**resolution, "source": "technology_registry" if resolution["status"] == "resolved" else "unresolved"}


def build_focused_impact_preview(draft, snapshots):
    """Replay saved requirement text with current production knowledge, then draft.

    This is a current-knowledge comparison, not a recomputation of historical
    scores or candidate evidence. Missing/invalid context fails the entire preview closed.
    """
    unavailable = {"available": False, "reason": "Compatible saved Job Match requirements are unavailable",
                   "rows": [], "scoring_influence": False, "score_changes_claimed": False}
    if not snapshots:
        return unavailable
    try:
        shadow = _shadow_registry(draft)
    except (ValueError, KeyError, TypeError) as exc:
        return {**unavailable, "reason": str(exc)}
    taxonomy = get_default_taxonomy()
    production = get_default_registry()
    output = []
    for snapshot in snapshots:
        if not isinstance(snapshot, dict) or snapshot.get("taxonomy_version") != taxonomy.version:
            return unavailable
        analysis = snapshot.get("stable_analysis")
        if not isinstance(analysis, dict) or not isinstance(analysis.get("canonical_requirements"), list):
            return unavailable
        seen = set()
        for row in analysis["canonical_requirements"]:
            if not isinstance(row, dict):
                return unavailable
            if not requirement_is_score_eligible(row):
                continue
            rid = row.get("requirement_id")
            if not rid or rid in seen or not (row.get("atomic_focus") or row.get("text")):
                return unavailable
            seen.add(rid)
            before = _resolve(row, production, taxonomy)
            after = _resolve(row, shadow, taxonomy)
            output.append({"snapshot_id": snapshot.get("id"), "job_id": snapshot.get("discovered_job_id"),
                           "requirement_id": rid, "requirement_text": row.get("atomic_focus") or row.get("text"),
                           "before": before, "after": after, "changed": before != after,
                           "would_resolve": before["status"] != "resolved" and after["status"] == "resolved",
                           "responsible_draft_id": draft["draft_id"] if before != after else None})
    if not output:
        return unavailable
    return {"available": True, "comparison": "Current production knowledge versus temporary draft knowledge",
            "requirements_evaluated": len(output),
            "unresolved_before": sum(r["before"]["source"] == "unresolved" for r in output),
            "would_resolve_after": sum(r["would_resolve"] for r in output),
            "changed_requirement_ids": [r["requirement_id"] for r in output if r["changed"]],
            "unchanged_requirements": sum(not r["changed"] for r in output), "rows": output,
            "scoring_influence": False, "score_changes_claimed": False}


def load_focused_preview_snapshots():
    from database.job_match_manager import list_latest_compatible_job_match_snapshots
    from job_discovery.matching import current_match_versions
    versions = current_match_versions()
    return list_latest_compatible_job_match_snapshots(
        match_version=versions["match_version"], scoring_version=versions["scoring_version"],
        taxonomy_version=versions["taxonomy_version"], read_only=True,
    )

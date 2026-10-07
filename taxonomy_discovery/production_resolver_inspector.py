"""Read-only diagnostics for current production requirement resolution."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sqlite3
from typing import Any, Callable

from database.job_match_manager import (
    DB_PATH,
    get_discovered_job_metadata_read_only,
    get_latest_job_match_snapshot,
)
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.production_requirement_resolver import (
    resolve_requirement_with_production_knowledge,
)
from taxonomy_discovery.technology_registry import (
    get_default_registry,
    resolve_requirement_text,
)


WEB_SERVICES_REQUIREMENT = "Knowledge of web services, API, REST, and gRPC"
AWS_REQUIREMENT = (
    "Hands-on experience with Amazon Web Services "
    "(EC2, Cognito, S3, DynamoDB, etc.)"
)


def current_production_versions() -> dict[str, str]:
    """Return runtime-loaded knowledge and scoring identities."""
    from job_discovery.matching import current_match_versions

    versions = current_match_versions()
    return {
        "taxonomy_version": str(versions["taxonomy_version"]),
        "technology_registry_version": str(
            versions["technology_registry_version"]
        ),
        "scoring_version": str(versions["scoring_version"]),
        "match_version": str(versions["match_version"]),
        "match_contract_version": str(versions["match_contract_version"]),
    }


def inspect_requirement_text(text: str) -> dict[str, Any]:
    """Inspect one requirement through the shared production resolver helper."""
    requirement_text = " ".join(str(text or "").split()).strip()
    if not requirement_text:
        raise ValueError("Requirement text is required.")

    requirement = {
        "text": requirement_text,
        "atomic_focus": requirement_text,
    }
    resolved = resolve_requirement_with_production_knowledge(requirement)
    decision = resolved["decision"]
    registry = resolved.get("registry_resolution") or {}
    taxonomy_diagnostics = dict(resolved["taxonomy_diagnostics"])
    taxonomy_diagnostics.pop("capability_record", None)
    rejected_rules = taxonomy_diagnostics.get("rejected_candidate_rules") or []
    blocked_rule = rejected_rules[0] if rejected_rules else {}

    capability_id = decision.get("capability_id")
    capability = get_default_taxonomy().by_id().get(str(capability_id or ""))
    resolution_source = str(resolved["resolution_source"])
    reason = (
        registry.get("reason")
        if resolution_source == "unresolved" and registry
        else taxonomy_diagnostics.get("reason")
        if resolution_source == "canonical_taxonomy"
        else registry.get("reason")
    )

    return {
        "requirement_text": requirement_text,
        "normalized_requirement_text": taxonomy_diagnostics.get(
            "normalized_requirement_text"
        ),
        "resolution_source": resolution_source,
        "capability_id": capability_id,
        "capability_label": (
            str(capability.get("label") or "") if capability else None
        ),
        "technology_id": registry.get("technology_id"),
        "canonical_technology_name": registry.get("technology_label"),
        "matched_phrase": taxonomy_diagnostics.get("matched_phrase"),
        "matched_alias": registry.get("matched_alias"),
        "matched_taxonomy_rule_type": taxonomy_diagnostics.get(
            "matched_taxonomy_rule_type"
        ),
        "contextual_phrase_rule": taxonomy_diagnostics.get(
            "contextual_phrase_rule"
        ),
        "product_context_guard": taxonomy_diagnostics.get(
            "product_context_guard"
        ),
        "guard_contract_version": taxonomy_diagnostics.get(
            "guard_contract_version"
        ),
        "excluded_product_spans": taxonomy_diagnostics.get(
            "excluded_product_spans", []
        ),
        "blocked_contextual_phrase": blocked_rule.get("phrase"),
        "blocked_product_context_guard": blocked_rule.get(
            "product_context_guard"
        ),
        "blocked_guard_contract_version": blocked_rule.get(
            "guard_contract_version"
        ),
        "reason": reason,
        "taxonomy_version": decision.get("taxonomy_version"),
        "registry_version": (
            registry.get("registry_version")
            or get_default_registry().version
        ),
        "match_label_applicability": (
            "Not applicable at requirement-resolution-only level."
        ),
        "resolver_diagnostics": {
            "taxonomy": taxonomy_diagnostics,
            "technology_registry": registry or None,
            "winning_resolver_source": resolution_source,
            "final_capability_id": capability_id,
            "final_technology_id": registry.get("technology_id"),
        },
    }


def _persisted_requirement_row(row: dict[str, Any]) -> dict[str, Any]:
    registry = row.get("technology_registry_resolution") or {}
    evidence = [
        item for item in row.get("evidence", []) or [] if isinstance(item, dict)
    ]
    evidence_ids = [
        item.get("evidence_id") or item.get("id")
        for item in evidence
        if item.get("evidence_id") or item.get("id")
    ]
    evidence_summary = " | ".join(
        str(item.get("text") or item.get("description") or "").strip()
        for item in evidence[:2]
        if str(item.get("text") or item.get("description") or "").strip()
    )
    return {
        "requirement_id": row.get("requirement_id"),
        "requirement_text": row.get("text"),
        "atomic_focus": row.get("atomic_focus"),
        "importance": row.get("importance"),
        "resolution_source": row.get("capability_resolution_source"),
        "resolution_status": row.get("resolution_status"),
        "capability_id": row.get("capability_id"),
        "technology_id": (
            row.get("technology_registry_technology_id")
            or registry.get("technology_id")
        ),
        "match_label": row.get("match_label"),
        "evidence_strength": row.get("evidence_strength"),
        "selected_evidence_ids": evidence_ids or None,
        "selected_evidence_summary": evidence_summary or None,
    }


def _persisted_execution_metadata(snapshot: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    tokens = ("model", "network", "provider", "request_id")
    for section_name in ("snapshot", "stable_analysis", "summary"):
        section = snapshot if section_name == "snapshot" else snapshot.get(section_name)
        if not isinstance(section, dict):
            continue
        for key, value in section.items():
            if any(token in str(key).lower() for token in tokens):
                metadata[f"{section_name}.{key}"] = deepcopy(value)
    return metadata


def inspect_saved_job_match(
    discovered_job_id: int,
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load a latest persisted Job Match snapshot without recomputation."""
    job_id = int(discovered_job_id)
    if job_id <= 0:
        raise ValueError("Discovered job ID must be a positive integer.")
    path = db_path or DB_PATH
    try:
        snapshot = get_latest_job_match_snapshot(
            job_id,
            db_path=path,
            read_only=True,
        )
        job = get_discovered_job_metadata_read_only(job_id, db_path=path)
    except (OSError, ValueError, sqlite3.Error) as exc:
        return {
            "status": "unavailable",
            "discovered_job_id": job_id,
            "message": f"Saved Job Match data is unavailable: {exc}",
        }
    if snapshot is None:
        return {
            "status": "not_found",
            "discovered_job_id": job_id,
            "message": "No saved Job Match snapshot exists for this job ID.",
            "job_metadata": deepcopy(job),
        }

    stable = snapshot.get("stable_analysis") or {}
    requirements = [
        deepcopy(row)
        for row in stable.get("canonical_requirements", []) or []
        if isinstance(row, dict)
    ]
    current = current_production_versions()
    stored_registry = str(stable.get("technology_registry_version") or "")
    stale_reasons: list[str] = []
    comparisons = (
        ("taxonomy_version", current["taxonomy_version"], "taxonomy version differs"),
        ("scoring_version", current["scoring_version"], "scoring version differs"),
        ("match_version", current["match_version"], "match pipeline version differs"),
    )
    for field, current_value, reason in comparisons:
        if str(snapshot.get(field) or "") != current_value:
            stale_reasons.append(reason)
    if stored_registry != current["technology_registry_version"]:
        stale_reasons.append("technology registry version differs")
    if job and str(job.get("content_hash") or "") != str(
        snapshot.get("job_content_hash") or ""
    ):
        stale_reasons.append("stored job description has changed")

    snapshot_metadata = {
        "snapshot_id": snapshot.get("id"),
        "created_at": snapshot.get("created_at"),
        "taxonomy_version": snapshot.get("taxonomy_version"),
        "technology_registry_version": stored_registry or None,
        "scoring_version": snapshot.get("scoring_version"),
        "match_version": snapshot.get("match_version"),
        "job_content_hash": snapshot.get("job_content_hash"),
        "evidence_fingerprint": snapshot.get("evidence_fingerprint"),
        "currentness_status": (
            "historical_or_stale" if stale_reasons else "latest_saved_current_versions"
        ),
        "currentness_limit": (
            "Current Profile & Evidence fingerprint is not recomputed by this inspector."
        ),
        "stale_reasons": stale_reasons,
    }
    job_metadata = {
        "discovered_job_id": job_id,
        "title": (job or {}).get("title"),
        "company": (job or {}).get("company"),
        "lifecycle_status": (job or {}).get("lifecycle_status"),
        "last_event": (job or {}).get("last_event"),
        "currently_visible_in_job_finder": (
            (job or {}).get("lifecycle_status") == "active" if job else None
        ),
    }
    return {
        "status": "found",
        "discovered_job_id": job_id,
        "job_metadata": job_metadata,
        "snapshot_metadata": snapshot_metadata,
        "persisted_requirements": requirements,
        "requirement_rows": [_persisted_requirement_row(row) for row in requirements],
        "persisted_execution_metadata": _persisted_execution_metadata(snapshot),
    }


def run_production_canaries(
    *,
    inspector: Callable[[str], dict[str, Any]] = inspect_requirement_text,
) -> dict[str, Any]:
    """Run pinned, deterministic resolver checks against current knowledge."""
    rows: list[dict[str, Any]] = []

    web = inspector(WEB_SERVICES_REQUIREMENT)
    web_ok = (
        web.get("resolution_source") == "canonical_taxonomy"
        and web.get("capability_id") == "backend.api_development"
        and web.get("matched_phrase") == "web services"
        and web.get("product_context_guard")
        == "exclude_recognized_multiword_technology_spans"
        and web.get("guard_contract_version")
        == "native-product-context-guard-v1"
    )
    rows.append(
        {
            "canary": "Web services/API/REST/gRPC",
            "expected": "canonical_taxonomy -> backend.api_development",
            "actual": f"{web.get('resolution_source')} -> {web.get('capability_id')}",
            "status": "PASS" if web_ok else "FAIL",
        }
    )

    aws = inspector(AWS_REQUIREMENT)
    aws_ok = (
        aws.get("capability_id") != "backend.api_development"
        and aws.get("resolution_source") == "unresolved"
        and "amazon web services" in (aws.get("excluded_product_spans") or [])
    )
    rows.append(
        {
            "canary": "Amazon Web Services",
            "expected": "unresolved; product guard blocks backend.api_development",
            "actual": f"{aws.get('resolution_source')} -> {aws.get('capability_id')}",
            "status": "PASS" if aws_ok else "FAIL",
        }
    )

    cpp = inspector("C++")
    cpp_registry = resolve_requirement_text("C++")
    cpp_ok = (
        cpp.get("capability_id") == "language.modern_cpp"
        and cpp_registry.get("technology_id") == "focused.cedb1bac7efcd7db"
        and cpp_registry.get("capability_id") == "language.modern_cpp"
    )
    rows.append(
        {
            "canary": "C++",
            "expected": "language.modern_cpp; registry identity focused.cedb1bac7efcd7db",
            "actual": (
                f"{cpp.get('resolution_source')} -> {cpp.get('capability_id')}; "
                f"registry {cpp_registry.get('technology_id')}"
            ),
            "status": "PASS" if cpp_ok else "FAIL",
        }
    )

    react = inspector("React")
    react_ok = (
        react.get("resolution_source") == "technology_registry"
        and react.get("technology_id") == "react"
        and react.get("capability_id") == "frontend.ui_development"
    )
    rows.append(
        {
            "canary": "React",
            "expected": "technology_registry -> frontend.ui_development",
            "actual": (
                f"{react.get('resolution_source')} -> {react.get('capability_id')}"
            ),
            "status": "PASS" if react_ok else "FAIL",
        }
    )

    return {
        "all_passed": all(row["status"] == "PASS" for row in rows),
        "rows": rows,
        "details": {"web_services": web, "aws": aws, "cpp": cpp, "react": react},
    }

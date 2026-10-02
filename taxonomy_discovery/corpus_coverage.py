"""Read-only coverage and explicit zero-cost current Job Match snapshot backfill.

Profiles are reused only for exact stored JD text or a compatible same-hash Job
Match snapshot. Existing snapshot evidence is preserved. A job without snapshots
may freeze the current canonical Evidence Library; historical evidence is never
reconstructed from a model-generated résumé report.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from database import job_match_manager as store
from database.analysis_cache_manager import (
    ANALYSIS_CACHE_VERSION, ANALYSIS_PIPELINE_CONTRACT_VERSION,
    PHASE9F_D_BASELINE_PIPELINE_CONTRACT_VERSION,
    _normalise_source_text,
)
from database.user_profile_manager import get_all_evidence_items_for_snapshot
from job_discovery.matching import (
    _default_stable_builder, _identity, _match_contract_version,
    _JD_PROFILE_REUSE_COMPATIBLE_MATCH_CONTRACTS,
    build_profile_evidence_context, current_match_versions, summarize_stable_match,
)
from taxonomy_discovery.regression_corpus import build_regression_corpus, duplicate_credit_violations

COVERAGE_VERSION = "tqd3-job-match-corpus-coverage-v1"
PROFILE_FIELDS = ("required_skills", "preferred_skills", "responsibilities", "soft_skills", "tools_technologies", "deal_breakers")


def _text(value):
    # Reuse the existing exact-input cache's transport/whitespace identity.
    # No case folding, punctuation removal, semantic or fuzzy JD matching.
    return _normalise_source_text(value)


def _profile_valid(profile):
    return isinstance(profile, dict) and any(k in profile for k in PROFILE_FIELDS) and all(
        isinstance(profile[k], list) and all(isinstance(v, str) for v in profile[k])
        for k in PROFILE_FIELDS if k in profile)


def _json(value, default=None):
    try:
        return json.loads(value) if value else default
    except (ValueError, TypeError):
        return default


def _rows(conn, table, required):
    columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    if not set(required).issubset(columns):
        return []
    return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]


def _cached_profiles(conn):
    profiles = defaultdict(list)
    for table in ("job_descriptions", "job_description_versions"):
        for row in _rows(conn, table, ("id", "raw_text", "jd_profile_json")):
            profile = _json(row["jd_profile_json"])
            if _profile_valid(profile) and _text(row["raw_text"]):
                profiles[_text(row["raw_text"])].append((profile, {"table":table,"id":row["id"]}, True))
    for row in _rows(conn, "application_analysis_versions", ("id", "report_json", "cache_version", "pipeline_contract_version")):
        if row.get("status", "active") != "active":
            continue
        report = _json(row["report_json"], {})
        if not isinstance(report, dict):
            continue
        profile, text = report.get("jd_profile"), _text(report.get("raw_jd_text"))
        compatible = row["cache_version"] == ANALYSIS_CACHE_VERSION and row["pipeline_contract_version"] in {
            ANALYSIS_PIPELINE_CONTRACT_VERSION, PHASE9F_D_BASELINE_PIPELINE_CONTRACT_VERSION}
        if text and _profile_valid(profile):
            profiles[text].append((profile, {"table":"application_analysis_versions","id":row["id"]}, compatible))
    return profiles


def _evidence_context(snapshot):
    evidence = snapshot.get("evidence_snapshot")
    if not isinstance(evidence, list) or not evidence or not all(isinstance(r, dict) for r in evidence):
        return None
    try:
        context = build_profile_evidence_context(evidence)
    except (ValueError, KeyError, TypeError):
        return None
    if not snapshot.get("evidence_fingerprint") or context["evidence_fingerprint"] != snapshot["evidence_fingerprint"]:
        return None
    return context


def _coverage_plan(*, db_path=None):
    path = Path(db_path or store.DB_PATH).resolve()
    versions = current_match_versions()
    report_rows, plans = [], {}
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")  # One consistent, read-only view of the stored inputs.
        jobs = _rows(conn, "discovered_jobs", ("id", "description", "content_hash"))
        if not {"id", "description", "content_hash"}.issubset({r[1] for r in conn.execute("PRAGMA table_info(discovered_jobs)")}):
            raise ValueError("Discovered Job Finder data unavailable or incompatible")
        raw_snapshots = _rows(conn, "job_match_snapshots", ("id", "discovered_job_id", "job_content_hash", "jd_profile_json", "evidence_snapshot_json", "stable_analysis_json"))
        by_job = defaultdict(list)
        for raw in raw_snapshots:
            decoded = store._decode_row(raw)
            if not isinstance(decoded.get("stable_analysis"),dict):
                decoded["stable_analysis"] = {}
            by_job[raw["discovered_job_id"]].append(decoded)
        caches = _cached_profiles(conn)
        current_evidence = None
        try:
            current_evidence = get_all_evidence_items_for_snapshot(read_only=True, db_path=path)
        except (sqlite3.OperationalError, ValueError, TypeError):
            pass
        try:
            library_context = build_profile_evidence_context(current_evidence) if current_evidence else None
        except (ValueError, KeyError, TypeError):
            library_context = None
        for job in jobs:
            snapshots = by_job[job["id"]]
            latest = snapshots[-1] if snapshots else None
            matching = [s for s in reversed(snapshots) if s.get("job_content_hash") == job["content_hash"]]
            source = next((s for s in matching if _match_contract_version(s.get("match_version")) in
                _JD_PROFILE_REUSE_COMPATIBLE_MATCH_CONTRACTS and _profile_valid(s.get("jd_profile"))), None)
            profile = deepcopy(source["jd_profile"]) if source else None
            profile_source = {"table":"job_match_snapshots","id":source["id"]} if source else None
            legacy = bool(matching and not source)
            conflict = False
            if profile is None:
                exact = caches.get(_text(job["description"]), [])
                compatible = [r for r in exact if r[2]]
                variants = {json.dumps(r[0], sort_keys=True) for r in compatible}
                conflict = len(variants) > 1
                if compatible and not conflict:
                    profile, profile_source, _ = deepcopy(compatible[-1])
                legacy = legacy or bool(exact and not compatible)
            evidence_source = source or latest
            context = _evidence_context(evidence_source) if evidence_source else library_context
            provenance = {"table":"job_match_snapshots","id":evidence_source["id"]} if evidence_source else {
                "table":"user_evidence","selection":"complete_canonical_library_frozen_for_new_current_snapshot"}
            replayable = False
            replay_blockers = []
            if latest:
                frozen = {**latest, "raw_jd_text":job["description"] if latest["job_content_hash"] == job["content_hash"] else None}
                try:
                    exported = build_regression_corpus([frozen])["jobs"][0]
                    replayable, replay_blockers = exported["replay_available"], exported["replay_blockers"]
                except (KeyError, TypeError, ValueError):
                    replay_blockers = ["Malformed saved snapshot"]
            def current_analysis(snapshot):
                stable = snapshot.get("stable_analysis") or {}
                return isinstance(stable,dict) and all(snapshot.get(k) == versions[k] for k in ("match_version", "scoring_version", "taxonomy_version")) and all(
                    stable.get(k) == versions[v] for k,v in (("scoring_version","scoring_version"),("capability_taxonomy_version","taxonomy_version"),
                                                          ("technology_registry_version","technology_registry_version"))) and isinstance(stable.get("canonical_requirements"),list)
            analysis_current = bool(latest and current_analysis(latest))
            stale_hash = bool(latest and latest["job_content_hash"] != job["content_hash"])
            row = {"discovered_job_id":job["id"],"title":job.get("title"),"company":job.get("company"),
                "lifecycle_status":job.get("lifecycle_status"),"current_jd_content_hash":job["content_hash"],
                "saved_snapshot_id":latest["id"] if latest else None,"snapshot_count":len(snapshots),
                "saved_jd_profile_available":bool(latest and _profile_valid(latest.get("jd_profile"))),
                "reusable_jd_profile_available":profile is not None,"evidence_snapshot_available":context is not None,
                "profile_source":profile_source,"evidence_source":provenance if context else None,
                "snapshot_versions":{k:latest.get(k) for k in ("match_version","scoring_version","taxonomy_version")} if latest else {},
                "replayable":replayable,"analysis_current":analysis_current,"snapshot_hash_mismatch":stale_hash,
                "backfill_eligible":False,"model_required":False,"replay_blockers":replay_blockers}
            if latest:
                row["snapshot_versions"]["technology_registry_version"] = (latest.get("stable_analysis") or {}).get("technology_registry_version")
            if len(_text(job["description"])) < 100 or not job["content_hash"]:
                state, reason = "missing_or_invalid_jd", "Current JD missing/too short or content hash absent"
            elif conflict:
                state, reason = "other_blocker", "Conflicting exact cached JD profiles; human review required"
            elif profile is None:
                state = "legacy_incompatible" if legacy else "requires_jd_extraction"
                reason = "No compatible saved JD extraction for current content; fresh extraction required"
                row["model_required"] = True
            elif context is None:
                state, reason = "other_blocker", "Existing candidate evidence snapshot missing/invalid; historical evidence cannot be reconstructed"
            else:
                identity = _identity(job, context, versions)
                existing_current = next((s for s in reversed(snapshots) if all(s.get(k) == v for k,v in identity.items()) and current_analysis(s)), None)
                row["backfill_eligible"] = existing_current is None
                state = "replayable_snapshot" if replayable else "stale_snapshot_backfillable" if latest else "cached_inputs_backfillable"
                reason = "Current compatible snapshot can be reused" if existing_current else "Exact persisted JD profile and existing candidate evidence permit deterministic current snapshot"
                plans[job["id"]] = {"job":deepcopy(job),"jd_profile":profile,"context":deepcopy(context),
                    "identity":identity,"reuse_snapshot_id":existing_current["id"] if existing_current else None,
                    "provenance":{"jd_profile_source":profile_source,"evidence_source":provenance,
                                  "source_snapshot_id":latest["id"] if latest else None,
                                  "source_jd_content_hash":job["content_hash"],"evidence_fingerprint":context["evidence_fingerprint"]}}
            row.update(status=state,reason=reason)
            report_rows.append(row)
    summary = {"discovered_jobs":len(report_rows),"existing_snapshots":sum(bool(r["saved_snapshot_id"]) for r in report_rows),
        "snapshot_records":len(raw_snapshots),"replayable_jobs_before":sum(r["replayable"] for r in report_rows),
        "reusable_jd_profiles":sum(r["reusable_jd_profile_available"] for r in report_rows),
        "zero_cost_backfillable":sum(r["backfill_eligible"] for r in report_rows),"model_required":sum(r["model_required"] for r in report_rows),
        "stale_hash_mismatched":sum(r["snapshot_hash_mismatch"] for r in report_rows),
        "stale_snapshot_jobs":sum(bool(r["saved_snapshot_id"]) and not r["analysis_current"] for r in report_rows),
        "blocked":sum(not r["model_required"] and r["status"] in {"missing_or_invalid_jd","other_blocker","legacy_incompatible"} for r in report_rows),
        "unavailable_or_invalid":sum(r["status"] in {"missing_or_invalid_jd","other_blocker","legacy_incompatible"} for r in report_rows),
        "coverage_reason_counts":dict(Counter(r["reason"] for r in report_rows)),"state_counts":dict(Counter(r["status"] for r in report_rows)),
        "lifecycle_counts":dict(Counter(str(r["lifecycle_status"] or "unspecified") for r in report_rows))}
    return {"coverage_version":COVERAGE_VERSION,**summary,"jobs":report_rows,"current_versions":versions,"read_only":True}, plans


def corpus_coverage(*, db_path=None):
    return _coverage_plan(db_path=db_path)[0]


def coverage_csv(report):
    out = io.StringIO(newline="")
    fields = ("discovered_job_id","title","company","lifecycle_status","current_jd_content_hash","saved_snapshot_id",
              "reusable_jd_profile_available","evidence_snapshot_available","status","replayable","backfill_eligible","model_required","reason")
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(report["jobs"])
    return out.getvalue()


def deterministic_backfill(*, db_path=None, execute=False):
    """Dry-run by default. Explicit execution saves only proven reusable inputs."""
    report, plans = _coverage_plan(db_path=db_path)
    result = {"dry_run":execute is not True,"would_create":sum(p["reuse_snapshot_id"] is None for p in plans.values()),
              "would_reuse":sum(p["reuse_snapshot_id"] is not None for p in plans.values()),
              "skipped":len(report["jobs"])-len(plans),"created":0,"reused":0,"jobs":[],"network_calls":0,"model_calls":0}
    if execute is not True:
        result["jobs"] = [{"discovered_job_id":r["discovered_job_id"],"action":"create" if r["backfill_eligible"] else
            "reuse" if r["discovered_job_id"] in plans else "skip","reason":r["reason"]} for r in report["jobs"]]
        return result
    with patch.dict(os.environ, {"CAPABILITY_RAG_MODE":"off"}), patch("socket.socket.connect",side_effect=RuntimeError("Deterministic backfill forbids network")):
        for jid, plan in plans.items():
            if plan["reuse_snapshot_id"]:
                result["reused"] += 1
                result["jobs"].append({"discovered_job_id":jid,"action":"reused","snapshot_id":plan["reuse_snapshot_id"]})
                continue
            stable = _default_stable_builder(raw_jd_text=plan["job"]["description"],jd_profile=plan["jd_profile"],context=plan["context"])
            if duplicate_credit_violations(stable, plan["context"]):
                raise ValueError(f"Deterministic invariant failed for job {jid}; snapshot not written")
            if current_match_versions() != report["current_versions"]:
                raise ValueError("Resolver versions changed; rerun backfill preview")
            # Re-read before every save. Never use a stale dry-run/previous job's
            # mutable inputs after the source JD, cache, or evidence changes.
            _, current_plans = _coverage_plan(db_path=db_path)
            current = current_plans.get(jid)
            if current != plan:
                if current and current["reuse_snapshot_id"]:
                    result["reused"] += 1
                    continue
                raise ValueError(f"Stored inputs changed for job {jid}; rerun backfill preview")
            summary = summarize_stable_match(stable)
            summary["deterministic_backfill_provenance"] = deepcopy(plan["provenance"])
            saved = store.save_job_match_snapshot(**plan["identity"], jd_profile=plan["jd_profile"],
                evidence_snapshot=plan["context"]["evidence_items"],stable_analysis=stable,summary=summary,db_path=db_path)
            result["created"] += 1
            result["jobs"].append({"discovered_job_id":jid,"action":"created","snapshot_id":saved["id"],"provenance":plan["provenance"]})
    return result


def model_required_queue(*, db_path=None, limit=25):
    if not isinstance(limit,int) or not 1 <= limit <= 100:
        raise ValueError("Model queue limit must be between 1 and 100")
    report = corpus_coverage(db_path=db_path)
    jobs = [{"discovered_job_id":r["discovered_job_id"],"title":r["title"],"company":r["company"],
             "reason":r["reason"],"job_state":"stale" if r["saved_snapshot_id"] else "new", "lifecycle_status":r["lifecycle_status"]}
            for r in report["jobs"] if r["model_required"]]
    jobs.sort(key=lambda r:(r["lifecycle_status"] != "active", r["discovered_job_id"]))
    return {"model_required_jobs":len(jobs),"estimated_model_analyses":len(jobs),"selected_estimated_model_analyses":min(limit,len(jobs)),
            "limit":limit,"jobs":jobs[:limit],"queue_only":True,"model_calls":0,"network_calls":0,
            "lifecycle_counts":dict(Counter(str(j["lifecycle_status"] or "unspecified") for j in jobs)),
            "ordering":"active_jobs_first_then_discovered_job_id"}

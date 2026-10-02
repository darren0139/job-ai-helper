"""Frozen Job Match corpus and offline comparison using the production matcher."""
from __future__ import annotations

import csv
import io
import os
from collections import Counter
from copy import deepcopy
from unittest.mock import patch

from analysis_stability.stable_evidence_scoring import requirement_is_score_eligible, build_resume_evidence_index
from database.job_match_manager import list_latest_job_match_corpus_snapshots
from job_discovery.matching import _default_stable_builder, build_profile_evidence_context, current_match_versions

CORPUS_VERSION = "tqd3-job-match-regression-corpus-v1"
SCORE_FIELDS = ("deterministic_alignment_score", "required_core_coverage_score", "preferred_coverage_score", "evidence_strength_score")


def requirement_records(stable, *, job_id, snapshot_id):
    """Use snapshot-pinned knowledge; never reinterpret the exported baseline."""
    output = []
    for row in stable.get("canonical_requirements", []):
        registry = row.get("technology_registry_resolution") or {}
        capability = row.get("capability_id") or row.get("canonical_capability_id") or row.get("taxonomy_capability_id")
        output.append({
            "job_id": job_id, "snapshot_id": snapshot_id, "requirement_id": row.get("requirement_id"),
            "requirement_text": row.get("atomic_focus") or row.get("text"), "importance": row.get("importance"),
            "score_eligible": requirement_is_score_eligible(row), "capability_id": capability,
            "resolution_status": "resolved" if capability else registry.get("status", "unresolved"),
            "resolution_source": row.get("capability_resolution_source") or ("resolved_unspecified" if capability else "unresolved"),
            "technology_id": registry.get("technology_id") or row.get("technology_registry_technology_id"),
            "technology_registry_resolution": deepcopy(registry),
            "match_label": row.get("match_label", "none"), "match_value": row.get("match_value", 0),
            "selected_evidence": deepcopy(row.get("evidence", [])),
            "retrieval_suggestions": deepcopy((row.get("capability_retrieval") or {}).get("candidates", [])),
            "scoring_version": stable.get("scoring_version"), "taxonomy_version": stable.get("capability_taxonomy_version"),
            "registry_version": stable.get("technology_registry_version"),
        })
    return output


def job_metrics(stable, requirements):
    eligible = [r for r in requirements if r["score_eligible"]]
    counts = Counter(r["match_label"] for r in eligible)
    return {**{k: stable.get(k) for k in SCORE_FIELDS},
        "resolved_count": sum(r["resolution_status"] == "resolved" for r in eligible),
        "unresolved_count": sum(r["resolution_status"] != "resolved" for r in eligible),
        **{label + "_count": counts[label] for label in ("direct", "transferable", "weak", "none")}}


def build_regression_corpus(snapshots):
    jobs = []
    for snapshot in snapshots:
        stable = deepcopy(snapshot.get("stable_analysis") or {})
        job_id, sid = snapshot.get("discovered_job_id"), snapshot.get("id")
        requirements = requirement_records(stable, job_id=job_id, snapshot_id=sid)
        evidence = snapshot.get("evidence_snapshot")
        context = build_profile_evidence_context(evidence) if isinstance(evidence, list) else None
        problems = []
        if not isinstance(stable.get("canonical_requirements"), list) or not all(stable.get(k) for k in
                ("scoring_version", "capability_taxonomy_version", "technology_registry_version")):
            problems.append("Pinned baseline analysis or resolver versions unavailable")
        if not snapshot.get("raw_jd_text"):
            problems.append("Original JD text unavailable or job content changed")
        if not isinstance(snapshot.get("jd_profile"), dict) or not snapshot.get("jd_profile"):
            problems.append("Saved JD profile unavailable")
        if context is None:
            problems.append("Frozen evidence snapshot unavailable")
        elif snapshot.get("evidence_fingerprint") and context["evidence_fingerprint"] != snapshot["evidence_fingerprint"]:
            problems.append("Frozen evidence fingerprint mismatch")
        jobs.append({"job_id": job_id, "snapshot_id": sid, "created_at": snapshot.get("created_at"),
            "job_content_hash": snapshot.get("job_content_hash"), "evidence_fingerprint": snapshot.get("evidence_fingerprint"),
            "requirements": requirements, "metrics": job_metrics(stable, requirements), "baseline_stable_analysis": stable,
            "versions": {"scoring_version": stable.get("scoring_version") or snapshot.get("scoring_version"),
                         "taxonomy_version": stable.get("capability_taxonomy_version") or snapshot.get("taxonomy_version"),
                         "technology_registry_version": stable.get("technology_registry_version")},
            "frozen_inputs": {"raw_jd_text": snapshot.get("raw_jd_text"), "jd_profile": deepcopy(snapshot.get("jd_profile")),
                              "context": context, "evidence_snapshot": deepcopy(evidence)},
            "jd_provenance": snapshot.get("raw_jd_provenance", "explicit_fixture"),
            "replay_available": not problems, "replay_blockers": problems})
    return {"corpus_version": CORPUS_VERSION, "jobs": jobs, "job_count": len(jobs),
            "current_versions_at_export": current_match_versions(), "read_only": True}


def export_saved_corpus(*, db_path=None):
    return build_regression_corpus(list_latest_job_match_corpus_snapshots(db_path=db_path))


def corpus_csv(corpus):
    buffer = io.StringIO(newline="")
    columns = ["job_id", "snapshot_id", "requirement_id", "requirement_text", "importance", "capability_id",
               "resolution_status", "resolution_source", "technology_id", "match_label", "match_value",
               "selected_evidence", "scoring_version", "taxonomy_version", "registry_version", *SCORE_FIELDS,
               "resolved_count", "unresolved_count", "direct_count", "transferable_count", "weak_count", "none_count"]
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    import json
    for job in corpus["jobs"]:
        for row in job["requirements"]:
            writer.writerow({**row, **job["metrics"], "selected_evidence": json.dumps(row["selected_evidence"], ensure_ascii=False)})
    return buffer.getvalue()


def duplicate_credit_violations(stable, context):
    problems = []
    ids = [r.get("requirement_id") for r in stable.get("canonical_requirements", [])]
    problems += ["duplicate_requirement_id:" + str(rid) for rid, count in Counter(ids).items() if count > 1]
    allowed = {r["evidence_id"] for r in build_resume_evidence_index(context["resume_profile"], context["raw_resume_text"])}
    credited = 0
    for row in stable.get("canonical_requirements", []):
        evidence_ids = [e.get("evidence_id") for e in row.get("evidence", [])]
        if len(evidence_ids) != len(set(evidence_ids)):
            problems.append("duplicate_selected_evidence:" + str(row.get("requirement_id")))
        if any(eid not in allowed for eid in evidence_ids):
            problems.append("evidence_not_in_frozen_resume:" + str(row.get("requirement_id")))
        if requirement_is_score_eligible(row) and row.get("match_label", "none") != "none":
            credited += 1
            if not evidence_ids:
                problems.append("credit_without_evidence:" + str(row.get("requirement_id")))
    if stable.get("credited_requirement_count", credited) != credited:
        problems.append("credited_requirement_count_mismatch")
    return problems


def compare_regression_corpus(corpus):
    if corpus.get("corpus_version") != CORPUS_VERSION:
        raise ValueError("Unsupported regression corpus")
    comparisons = []
    # This is the existing deterministic builder, using saved JD extraction and
    # frozen evidence, with retrieval explicitly disabled. No extractor is called.
    with patch.dict(os.environ, {"CAPABILITY_RAG_MODE": "off"}), \
            patch("socket.socket.connect", side_effect=RuntimeError("Offline corpus forbids network")):
        for job in corpus["jobs"]:
            base = {"job_id": job["job_id"], "snapshot_id": job["snapshot_id"]}
            if not job["replay_available"]:
                comparisons.append({**base, "classification": "requires_review", "available": False, "blockers": job["replay_blockers"]})
                continue
            inputs = deepcopy(job["frozen_inputs"])
            context = inputs["context"]
            if build_profile_evidence_context(inputs["evidence_snapshot"]) != context:
                comparisons.append({**base, "classification": "hard_regression/invariant_violation", "available": False,
                                    "blockers": ["Frozen context disagrees with frozen evidence"]})
                continue
            stable = _default_stable_builder(raw_jd_text=inputs["raw_jd_text"], jd_profile=inputs["jd_profile"], context=context)
            after = requirement_records(stable, job_id=job["job_id"], snapshot_id=job["snapshot_id"])
            before_by_id = {r["requirement_id"]: r for r in job["requirements"]}
            after_by_id = {r["requirement_id"]: r for r in after}
            changes = []
            fields = ("resolution_status", "resolution_source", "capability_id", "technology_id", "match_label", "match_value", "selected_evidence", "score_eligible")
            for rid in sorted(set(before_by_id) | set(after_by_id)):
                before, current = before_by_id.get(rid), after_by_id.get(rid)
                changed = [k for k in fields if (before or {}).get(k) != (current or {}).get(k)]
                if changed or before is None or current is None:
                    changes.append({"requirement_id": rid, "changed_fields": changed, "before": before, "after": current,
                        "newly_resolved": bool(current and current["resolution_status"] == "resolved" and (not before or before["resolution_status"] != "resolved")),
                        "newly_unresolved": bool(before and before["resolution_status"] == "resolved" and (not current or current["resolution_status"] != "resolved"))})
            metrics = job_metrics(stable, after)
            deltas = {k: metrics[k] - job["metrics"][k] if isinstance(metrics[k], (int, float)) and isinstance(job["metrics"].get(k), (int, float)) else None for k in SCORE_FIELDS}
            versions = {"scoring_version": stable.get("scoring_version"), "taxonomy_version": stable.get("capability_taxonomy_version"),
                        "technology_registry_version": stable.get("technology_registry_version")}
            version_changes = {k: {"before": job["versions"].get(k), "after": v} for k, v in versions.items() if job["versions"].get(k) != v}
            violations = duplicate_credit_violations(stable, context) + duplicate_credit_violations(job["baseline_stable_analysis"], context)
            if violations or any(c["newly_unresolved"] for c in changes):
                classification = "hard_regression/invariant_violation"
            elif any(v not in (0, None) for v in deltas.values()):
                classification = "requires_review"
            elif changes and all(c["before"] and c["after"] and c["newly_resolved"] and
                    set(c["changed_fields"]).issubset({"resolution_status", "resolution_source", "capability_id", "technology_id"}) for c in changes):
                classification = "expected_improvement"
            elif changes or version_changes:
                classification = "requires_review"
            else:
                classification = "unchanged"
            comparisons.append({**base, "available": True, "classification": classification,
                "requirement_changes": changes, "job_score_deltas": deltas, "version_changes": version_changes,
                "duplicate_credit_violations": violations, "before_metrics": job["metrics"], "after_metrics": metrics})
    return {"corpus_version": CORPUS_VERSION, "jobs": comparisons, "classification_counts": dict(Counter(j["classification"] for j in comparisons)),
            "network_calls": 0, "model_calls": 0, "embeddings": 0, "production_mutations": 0}

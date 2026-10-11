"""Read-only views of saved native analyses; no scoring or requirement inference."""
from __future__ import annotations

from copy import deepcopy
from contextlib import closing
import json
import sqlite3
from pathlib import Path

from database import db_manager
from job_discovery.matching import current_match_versions
from tailoring.job_match_ab_analysis import current_ab_identity
from tailoring.phase8_score_explainability import build_score_breakdown
from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint
from tailoring.phase9e_blueprint_selection import fingerprint_value


PENDING = "The current analysis could not confidently determine whether this represents a resume evidence gap."


def explain_requirement(row, *, knowledge_status=None):
    """NONE/unresolved is never sufficient proof of a candidate deficiency."""
    label = str(row.get("match_label") or "none").lower()
    if label == "direct":
        state, message = "MATCHED_DIRECT", "Your resume contains accepted direct evidence for this requirement."
    elif label == "transferable":
        state, message = "MATCHED_TRANSFERABLE", "Related experience provides transferable evidence for part of this requirement."
    else:
        # The current frozen policy has no proved deficiency/limitation rows.
        # Future proofs need a governed producer integration, not a new inference here.
        state, message = "UNKNOWN_REVIEW_PENDING", PENDING
    if knowledge_status == "PROVEN_TAXONOMY_GAP" and label == "direct":
        message = "This requirement is not yet represented by a calibrated taxonomy capability, but your resume contains accepted direct evidence for it."
    registry = row.get("technology_registry_resolution") or {}
    knowledge = knowledge_status or row.get("knowledge_status") or (
        "CAPABILITY_RESOLVED" if row.get("capability_id") and row.get("capability_resolution_source") in {"canonical_taxonomy", "technology_registry"} else
        "TECHNOLOGY_IDENTITY_RESOLVED" if row.get("capability_resolution_source") == "technology_identity" else "DEFERRED")
    if knowledge == "TECHNOLOGY_IDENTITY_RESOLVED" and label == "none":
        message = "The technology is recognized, but no accepted resume evidence was selected. " + PENDING
    negative = row.get("negative_evidence_status")
    diagnostic = None
    if negative == "CANDIDATE_REJECTED":
        diagnostic = "A potentially related resume item was evaluated but did not satisfy the current matching threshold. The current contract cannot confidently classify this as a confirmed resume evidence gap."
    elif negative == "SEARCHED_BUT_SCOPE_LIMITED":
        diagnostic = "The analysis did not select qualifying evidence, but the requirement's evaluation scope is not sufficiently established to classify this as a confirmed resume gap."
    return {"state": state, "knowledge_status": knowledge, "explanation": message,
            "diagnostic": diagnostic,
            "knowledge_state": "DEFERRED_BUT_EVALUABLE" if knowledge in {"DEFERRED", "UNRESOLVED"} and label in {"direct", "transferable"} and row.get("evidence") else knowledge,
            "evidence_scope": "Recorded evidence supports the selected component; whole-parent completeness is not inferred."}


def build_analysis_receipt(stable_analysis, *, raw_jd_text, provenance, identity=None, knowledge=None):
    """Format the actual saved result using the existing Phase 8 arithmetic view."""
    if not isinstance(stable_analysis, dict) or not stable_analysis.get("canonical_requirements") or not raw_jd_text:
        raise ValueError("Saved analysis/JD unavailable; no recomputation was attempted.")
    stable = deepcopy(stable_analysis)
    versions = current_match_versions()
    stale = any(stable.get(field) != versions[key] for field, key in (
        ("scoring_version", "scoring_version"), ("capability_taxonomy_version", "taxonomy_version"),
        ("technology_registry_version", "technology_registry_version")))
    breakdown = build_score_breakdown(stable) if stable.get("scoring_version") == versions["scoring_version"] else None
    # Do not present reconstructed contributions as historical truth if parity fails.
    points = {r["requirement_id"]: r for r in breakdown["requirements"]} if breakdown and breakdown["score_parity"] else {}
    rows = []
    seen = set()
    for native in stable["canonical_requirements"]:
        rid = native.get("requirement_id")
        if not rid or rid in seen:
            raise ValueError("Saved requirement IDs missing or duplicated.")
        seen.add(rid)
        rows.append({"native": deepcopy(native), "requirement_id": rid,
                     "contribution": deepcopy(points.get(rid)),
                     **explain_requirement(native, knowledge_status=(knowledge or {}).get(rid))})
    return {"provenance": provenance, "identity": deepcopy(identity or {}),
            "versions": {key: stable.get(key) for key in (
                "scoring_version", "capability_taxonomy_version", "technology_registry_version",
                "technology_registry_resolution_version", "jd_structure_inference_version")},
            "jd_fingerprint": current_ab_identity(raw_jd_text)["jd_fingerprint"],
            "canonical_requirement_fingerprint": canonical_requirement_scope_fingerprint(stable["canonical_requirements"]),
            "raw_jd_text": raw_jd_text, "stable_analysis": stable,
            "score": stable.get("deterministic_alignment_score"), "requirements": rows,
            "currentness": "Stale historical analysis" if stale else "Historical analysis",
            "contribution_status": "available" if points else "Historical contributions unavailable / parity not established"}


def job_finder_receipt(snapshot, raw_jd_text):
    return build_analysis_receipt(snapshot.get("stable_analysis"), raw_jd_text=raw_jd_text,
        provenance="JOB_FINDER_INITIAL_MATCH", identity={k: deepcopy(snapshot.get(k)) for k in (
            "id", "discovered_job_id", "job_content_hash", "evidence_fingerprint", "match_version", "scoring_version", "taxonomy_version")})


def load_application_initial(application_id, *, db_path=None):
    """Read the authoritative existing reference with mode=ro; never initialize DBs."""
    path = Path(db_path or db_manager.DB_PATH).resolve()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        app = conn.execute("SELECT * FROM applications WHERE id=?", (int(application_id),)).fetchone()
        if app is None:
            raise ValueError("Application unavailable")
        binding = json.loads(app["entry_binding_json"] or "{}") if "entry_binding_json" in app.keys() else {}
        if binding:
            if binding.get("binding_fingerprint") != fingerprint_value({k: v for k, v in binding.items() if k != "binding_fingerprint"}):
                raise ValueError("Initial binding integrity mismatch")
            initial_id = binding["initial_analysis_id"]
            source = "JOB_FINDER_INITIAL_MATCH"
        else:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='phase9f_application_confirmations'").fetchone():
                raise ValueError("No authoritative Initial Analysis reference")
            confirmation = conn.execute("SELECT confirmation_snapshot_json FROM phase9f_application_confirmations WHERE application_id=?", (int(application_id),)).fetchone()
            if confirmation is None:
                raise ValueError("No authoritative Initial Analysis reference")
            initial_id = json.loads(confirmation[0])["initial_analysis"]["analysis_id"]
            source = "PHASE9F_BASELINE_INITIAL_ANALYSIS"
        saved = conn.execute("SELECT report_json FROM application_analysis_versions WHERE application_id=? AND analysis_id=?", (int(application_id), initial_id)).fetchall()
        if len(saved) != 1:
            raise ValueError("Initial Analysis reference unavailable or ambiguous")
        report = json.loads(saved[0][0])
        if binding and (report.get("stable_analysis") != binding["snapshot"]["stable_analysis"] or report.get("raw_jd_text") != binding["raw_jd_text"]):
            raise ValueError("Frozen initial receipt integrity mismatch")
    view = build_analysis_receipt(report.get("stable_analysis"), raw_jd_text=report.get("raw_jd_text"), provenance=source,
        identity={"application_id": int(application_id), "initial_analysis_id": initial_id,
                  "saved_snapshot_id": binding.get("snapshot", {}).get("id"),
                  "discovered_job_id": binding.get("discovered_job_id"),
                  "jd_hash": binding.get("raw_jd_sha256"),
                  "evidence_fingerprint": binding.get("snapshot", {}).get("evidence_fingerprint"),
                  "input_fingerprint": (report.get("stable_analysis") or {}).get("input_fingerprint")})
    return view


def compare_analysis_receipts(initial, final):
    """Use native stable IDs and generation scope, with no score-based causality."""
    blockers = []
    for field in ("jd_fingerprint", "canonical_requirement_fingerprint"):
        if not initial.get(field) or initial.get(field) != final.get(field):
            blockers.append(field + " mismatch")
    for field in ("scoring_version", "capability_taxonomy_version", "technology_registry_version", "jd_structure_inference_version", "technology_registry_resolution_version"):
        left, right = initial["stable_analysis"].get(field), final["stable_analysis"].get(field)
        if not left or left != right:
            blockers.append(field + " mismatch/unavailable")
    if initial["identity"].get("application_id") != final["identity"].get("application_id") or not initial["identity"].get("application_id"):
        blockers.append("Application identity mismatch/unavailable")
    before = {r["requirement_id"]: r for r in initial["requirements"]}
    after = {r["requirement_id"]: r for r in final["requirements"]}
    if set(before) != set(after):
        blockers.append("Requirement ID mismatch")
    if blockers:
        return {"comparable": False, "blockers": blockers, "requirements": []}
    rows = []
    for rid, left in before.items():
        right = after[rid]
        evidence_changed = left["native"].get("evidence") != right["native"].get("evidence")
        a, b = left.get("contribution"), right.get("contribution")
        delta = b["overall_point_contribution"] - a["overall_point_contribution"] if a and b else None
        unchanged = not evidence_changed and left["native"].get("match_label") == right["native"].get("match_label") and delta == 0
        rows.append({"requirement_id": rid, "initial": deepcopy(left), "final": deepcopy(right),
                     "contribution_delta": delta, "evidence_changed": evidence_changed,
                     "reason": "UNCHANGED" if unchanged else "UNKNOWN"})
    return {"comparable": True, "blockers": [], "requirements": rows}

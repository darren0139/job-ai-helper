"""Passive Streamlit presentation of frozen analysis receipts."""
from __future__ import annotations

import json
from contextlib import closing
import sqlite3
from pathlib import Path

from database import db_manager
from tailoring.initial_analysis_explainer import (
    build_analysis_receipt, compare_analysis_receipts, explain_requirement,
    job_finder_receipt, load_application_initial,
)
from taxonomy_discovery.coverage_presentation import render_jd_taxonomy_status


def _evidence(row):
    return " | ".join(str(e.get("text") or e.get("matched_resume_term") or "")
                      for e in row.get("evidence", []) if isinstance(e, dict))


def render_analysis_receipt(st, view, *, taxonomy=None, show_taxonomy=True):
    native = view["stable_analysis"]
    st.caption(view["currentness"] + " · The saved result is shown without recomputation.")
    cols = st.columns(4)
    for col, label, key in zip(cols, ("Job Match", "Required/core", "Preferred", "Evidence strength"),
                               ("deterministic_alignment_score", "required_core_coverage_score", "preferred_coverage_score", "evidence_strength_score")):
        col.metric(label, native.get(key, "Unavailable"))
    if show_taxonomy:
        taxonomy = render_jd_taxonomy_status(st, raw_jd_text=view["raw_jd_text"], stable_analysis=native,
                                            job_id=view["identity"].get("discovered_job_id"))
    knowledge = {}
    if taxonomy:
        knowledge.update({r["requirement_id"]: "PROVEN_TAXONOMY_GAP" for r in taxonomy["proven_gaps"]})
        knowledge.update({r["requirement_id"]: "NOT_TAXONOMY_ADDRESSABLE" for r in taxonomy["routes"]
                          if r["destination"] == "No capability-discovery action"})
    display = []
    for row in view["requirements"]:
        n = row["native"]
        semantics = explain_requirement(n, knowledge_status=knowledge.get(row["requirement_id"]))
        contribution = row.get("contribution") or {}
        registry = n.get("technology_registry_resolution") or {}
        display.append({
            "Requirement": n.get("text"), "Requirement ID": row["requirement_id"],
            "Importance": n.get("importance"), "Weight": contribution.get("effective_weight"),
            "Score eligible": n.get("score_eligible"),
            "Allocation": contribution.get("group_weight_fraction"),
            "Knowledge": semantics["knowledge_state"], "Evidence": n.get("match_label"),
            "Selected evidence": _evidence(n),
            "Source": " | ".join(str(e.get("source") or "") for e in n.get("evidence", []) if isinstance(e, dict)),
            "Match value": n.get("match_value"), "Contribution": contribution.get("overall_point_contribution"),
            "Capability": n.get("capability_id"), "Technology": registry.get("technology_id") or n.get("technology_id"),
            "Resolver": n.get("capability_resolution_source"),
            "Cap / rejection": n.get("capability_taxonomy_cap_reason") or n.get("capability_taxonomy_cap_status"),
            "Analysis status": "Review pending" if semantics["state"] == "UNKNOWN_REVIEW_PENDING" else semantics["state"],
            "Explanation": semantics["explanation"],
        })
    st.dataframe(display, hide_index=True, width="stretch")
    st.caption("Evidence supports its recorded scope. Whole-parent completeness is not inferred from component credit.")
    with st.expander("Analysis diagnostics"):
        st.write("Provenance", view["provenance"])
        st.write("Contribution receipt", view["contribution_status"])
        # Selected evidence only: never expose rejected candidate text as accepted evidence.
        diagnostics = {**view, "requirements": [
            {**r, "native": {k: v for k, v in r["native"].items()
                            if k not in {"capability_retrieval", "rejected_candidate"}}}
            for r in view["requirements"]]}
        diagnostics.pop("stable_analysis", None)
        diagnostics["native_validation_warnings"] = native.get("validation_warnings", [])
        st.json(diagnostics)
        st.download_button("Download analysis report", json.dumps(diagnostics, indent=2, default=str),
                           file_name="initial_analysis.json", mime="application/json", on_click="ignore")


def render_job_finder_explainer(st, snapshot, raw_jd_text, *, taxonomy=None):
    try:
        # Job Finder already displays this JD's status above the saved score.
        render_analysis_receipt(st, job_finder_receipt(snapshot, raw_jd_text),
                                taxonomy=taxonomy, show_taxonomy=False)
    except (ValueError, KeyError, TypeError) as exc:
        st.warning("Saved analysis unavailable — " + str(exc))


def render_application_initial_analysis(st, application_id):
    """Never use the refreshed current application report as Initial Analysis."""
    try:
        initial = load_application_initial(application_id)
    except (ValueError, KeyError, TypeError, sqlite3.Error, OSError) as exc:
        st.caption("Initial Analysis unavailable — " + str(exc))
        return
    with st.expander("Initial Analysis"):
        render_analysis_receipt(st, initial)
    with st.expander("Initial vs Tailored Analysis"):
        path = Path(db_manager.DB_PATH).resolve()
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='application_tailoring_verifications'").fetchone():
                st.caption("No saved Phase 8 final analysis yet.")
                return
            record = conn.execute("SELECT result_json FROM application_tailoring_verifications WHERE application_id=? ORDER BY created_at DESC,id DESC LIMIT 1", (int(application_id),)).fetchone()
        if record is None:
            st.caption("No saved Phase 8 final analysis yet.")
            return
        try:
            result = json.loads(record[0])
            final_snapshot = (result.get("job_match_ab") or {}).get("tailored") or {}
            if result.get("application_id") != int(application_id) or not final_snapshot.get("identity", {}).get("jd_fingerprint"):
                raise ValueError("Saved final application/JD identity unavailable")
            final = build_analysis_receipt(result["after_stable_analysis"], raw_jd_text=initial["raw_jd_text"],
                provenance="PHASE8_FINAL_EVIDENCE", identity={"application_id": int(application_id), "generation_id": result.get("generation_id")})
            # Use the saved final JD identity, never substitute the Initial JD.
            final["jd_fingerprint"] = final_snapshot["identity"]["jd_fingerprint"]
            comparison = compare_analysis_receipts(initial, final)
            if not comparison["comparable"]:
                st.warning("Saved analyses are incompatible; comparison withheld.")
                st.write(comparison["blockers"])
                return
            st.caption("Saved Phase 8 final evidence · Changes do not imply a cause unless provenance proves it.")
            score_cols = st.columns(2)
            score_cols[0].metric("Frozen Initial Job Match", initial["score"])
            score_cols[1].metric("Saved final Job Match", final["score"])
            st.dataframe([{
                "Requirement ID": r["requirement_id"], "Requirement": r["initial"]["native"].get("text"),
                "Initial evidence": r["initial"]["native"].get("match_label"), "Final evidence": r["final"]["native"].get("match_label"),
                "Initial selected evidence": _evidence(r["initial"]["native"]), "Final selected evidence": _evidence(r["final"]["native"]),
                "Initial source": " | ".join(str(e.get("source") or "") for e in r["initial"]["native"].get("evidence", []) if isinstance(e, dict)),
                "Final source": " | ".join(str(e.get("source") or "") for e in r["final"]["native"].get("evidence", []) if isinstance(e, dict)),
                "Initial state": r["initial"]["state"], "Final state": r["final"]["state"],
                "Initial contribution": (r["initial"].get("contribution") or {}).get("overall_point_contribution"),
                "Final contribution": (r["final"].get("contribution") or {}).get("overall_point_contribution"),
                "Contribution change": r["contribution_delta"], "Evidence changed": r["evidence_changed"], "Reason": r["reason"],
            } for r in comparison["requirements"]], hide_index=True, width="stretch")
        except (ValueError, KeyError, TypeError) as exc:
            st.warning("Saved final comparison unavailable — " + str(exc))

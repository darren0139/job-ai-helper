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
    from analysis_stability.requirement_presentation import score_text, assessment_label, render_requirement_context
    native = view["stable_analysis"]
    st.caption(view["currentness"] + " · The saved result is shown without recomputation.")
    cols = st.columns(4)
    for col, label, key in zip(cols, ("Job Match", "Required/core", "Preferred", "Evidence strength"),
                               ("deterministic_alignment_score", "required_core_coverage_score", "preferred_coverage_score", "evidence_strength_score")):
        col.metric(label, score_text(native.get(key)))
    render_requirement_context(st, native)
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
            "Assessment basis": assessment_label(n),
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
    from tailoring.unresolved_requirement_review_ui import render_unresolved_requirement_review
    render_unresolved_requirement_review(st,view)
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


def render_application_initial_analysis(st, application_id, *, resume_only=False, show_comparison=True):
    """Never use the refreshed current application report as Initial Analysis."""
    try:
        initial = load_application_initial(application_id, resume_only=True) if resume_only else load_application_initial(application_id)
    except (ValueError, KeyError, TypeError, sqlite3.Error, OSError) as exc:
        with st.expander("Initial Résumé Analysis" if resume_only else "Initial Analysis"):
            if str(exc) in {"No authoritative Initial Analysis reference", "No authoritative Initial Resume Analysis reference"}:
                st.write("Not established yet")
                st.caption("Run Analyze Resume to establish this application's frozen starting analysis.")
            else:
                st.caption("Initial Analysis unavailable — " + str(exc))
        return
    with st.expander("Initial Résumé Analysis" if resume_only else "Initial Analysis"):
        if initial["provenance"] in {"EXACT_SAVED_REUSE", "FRESH_ANALYSIS"}:
            st.caption("Analysis origin: " + {"EXACT_SAVED_REUSE": "Reused exact saved analysis",
                                            "FRESH_ANALYSIS": "Fresh analysis"}[initial["provenance"]])
        render_analysis_receipt(st, initial)
    if not show_comparison:
        return
    render_initial_tailored_comparison(st, application_id, initial=initial, resume_only=resume_only)


def render_selected_base_analysis(st, effective_report):
    """Passive view of the source decision's native receipt; no persistence."""
    from tailoring.document_grounded_analysis import selected_base_analysis
    try:
        selected = selected_base_analysis(effective_report)
        if selected['same_as_initial']:
            st.caption('Selected base is the original Application résumé. '
                       'Using frozen Initial Résumé Analysis: '
                       + str(selected['stable_analysis']['deterministic_alignment_score']) + '.')
        else:
            with st.expander('Selected Base Analysis'):
                st.caption('The selected résumé is the working baseline. Initial Résumé Analysis remains immutable.')
                view = build_analysis_receipt(selected['stable_analysis'],
                    raw_jd_text=effective_report['raw_jd_text'], provenance='SELECTED_DOCUMENT_RECEIPT',
                    identity=selected['starting_context'])
                view['document_analysis'] = selected['document_analysis']
                render_analysis_receipt(st, view, show_taxonomy=False)
        return selected
    except (ValueError, KeyError, TypeError) as exc:
        st.warning('Selected Base Analysis unavailable — ' + str(exc))
        return None


def render_initial_tailored_comparison(st, application_id, *, initial=None, resume_only=True):
    if initial is None:
        try:
            initial = load_application_initial(application_id, resume_only=resume_only)
        except (ValueError, sqlite3.Error, OSError):
            return
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
            if resume_only and not result.get('document_analysis'):
                raise ValueError('Saved final analysis has no actual-document provenance')
            if resume_only:
                from tailoring.phase9e_blueprint_selection import fingerprint_value
                authority = result['document_analysis']
                if (authority['initial'] != initial['document_analysis']
                    or authority['initial']['identity'] != authority['final']['identity']
                    or authority['final']['stable_analysis_fingerprint'] != fingerprint_value(result['after_stable_analysis'])):
                    raise ValueError('Saved final document authority is incompatible with the frozen initial')
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


def render_discovery_history(st, application_id):
    try:
        historical = load_application_initial(application_id)
        if historical['provenance'] == 'JOB_FINDER_INITIAL_MATCH':
            with st.expander('Discovery Match'):
                st.caption('Candidate Profile & Evidence match · This is not the selected résumé document score.')
                render_analysis_receipt(st, historical, show_taxonomy=False)
        elif not historical.get('document_grounded'):
            with st.expander('Discovery / historical match'):
                st.caption('Historical provenance · Document grounding is not established.')
                render_analysis_receipt(st, historical, show_taxonomy=False)
    except (ValueError, KeyError, TypeError, sqlite3.Error, OSError):
        pass


def render_tailoring_evidence_opportunities(st, report):
    from database.user_profile_manager import get_all_evidence_items_for_snapshot
    from tailoring.document_grounded_analysis import build_tailoring_evidence_opportunities, validate_document_report
    with st.expander('Evidence available for tailoring'):
        st.caption('Additional grounded material may support tailoring. It does not increase the current résumé score; no projected score is calculated.')
        if not (report.get('meta') or {}).get('document_analysis'):
            st.caption('Current résumé analysis is not established; requirement-level document comparison needs explicit Analyze Resume.')
            return
        try:
            validate_document_report(report)
            items = get_all_evidence_items_for_snapshot(read_only=True, db_path=db_manager.DB_PATH)
            rows = build_tailoring_evidence_opportunities(report, items)
            st.dataframe([{'Requirement': r['requirement'], 'Current résumé': r['current_resume'],
                'Additional grounded evidence': 'Available' if r['additional_grounded_evidence'] else 'Review pending' if r['state']=='REVIEW_PENDING' else 'Not established',
                'Potential action': r['state'],
                'Evidence': ' | '.join(str(e['title'] or e['evidence_item_id']) for e in r['additional_grounded_evidence'])} for r in rows], hide_index=True, width='stretch')
        except (ValueError, sqlite3.Error, OSError) as exc:
            st.caption('Evidence review pending — ' + str(exc))


def render_application_bound_jd(st, application_id):
    """Read the existing exact binding/report; never initialize or backfill data."""
    try:
        path = Path(db_manager.DB_PATH).resolve()
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            app = conn.execute("SELECT * FROM applications WHERE id=?", (int(application_id),)).fetchone()
            if app is None:
                return
            binding = json.loads(app["entry_binding_json"] or "{}") if "entry_binding_json" in app.keys() else {}
            if not binding and "initial_analysis_binding_json" in app.keys():
                binding = json.loads(app["initial_analysis_binding_json"] or "{}")
            report = json.loads(app["report_json"] or "{}")
            if "initial_analysis_id" in app.keys() and app["initial_analysis_id"]:
                saved = conn.execute("SELECT report_json FROM application_analysis_versions WHERE application_id=? AND analysis_id=?",
                                     (application_id, app["initial_analysis_id"])).fetchone()
                if saved:
                    report = json.loads(saved[0])
            raw = binding.get("raw_jd_text") or report.get("raw_jd_text")
            if not raw:
                return
            profile = report.get("jd_profile") or {}
            with st.expander("Job description"):
                st.write(binding.get("title") or profile.get("job_title") or app["job_title"] or "Job description")
                st.write(binding.get("company") or profile.get("company") or app["company"] or "")
                source_url = binding.get("source_url") or ((report.get("meta") or {}).get("jd_user_inputs") or {}).get("source_url")
                if source_url:
                    st.write("Source: " + source_url)
                if binding.get("discovered_job_id"):
                    st.caption("Source job: " + str(binding["discovered_job_id"]))
                st.text(raw)
                with st.expander("Job description diagnostics"):
                    st.json({"application_id": int(application_id), "jd_fingerprint": binding.get("raw_jd_sha256"),
                             "canonical_requirement_fingerprint": binding.get("canonical_requirement_fingerprint")})
    except (ValueError, KeyError, TypeError, sqlite3.Error, OSError) as exc:
        st.caption("Bound job description unavailable — " + str(exc))

"""Read-only selected-base vs saved Phase 8 comparison for Phase 9F sessions.

The Phase 9F-B chosen source is *not* an explicitly uploaded Initial Resume.
Never score on a UI read, switch source identities, or infer causality.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import closing
from pathlib import Path
import json
import sqlite3
from typing import Any


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def load_latest_phase8_read_only(application_id: int, *, db_path: Any = None) -> dict[str, Any] | None:
    """Read the latest saved final receipt with SQLite URI mode=ro: zero writes."""
    if db_path is None:
        from database import db_manager
        db_path = db_manager.DB_PATH
    path = Path(db_path).resolve()
    if not path.is_file():
        return None
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='application_tailoring_verifications'"
        ).fetchone()
        if table is None:
            return None
        saved = conn.execute(
            "SELECT result_json FROM application_tailoring_verifications "
            "WHERE application_id=? ORDER BY created_at DESC, id DESC LIMIT 1",
            (int(application_id),),
        ).fetchone()
    if saved is None:
        return None
    value = json.loads(saved[0])
    if not isinstance(value, dict):
        raise ValueError("Saved Phase 8 verification record has invalid content")
    return value


def verify_selected_base_phase8_pair(base: dict[str, Any], final: dict[str, Any], *, application_id: int) -> dict[str, Any]:
    """Require exact frozen B analysis as the actual Phase 8 'before' input.

    Do not silently reconcile versions, compare against unrelated Initial analyses,
    or substitute a later scorer for the saved source baseline.
    """
    if not isinstance(base, dict) or not isinstance(final, dict):
        raise ValueError("Selected-base and Phase 8 receipts are required")
    if not isinstance(base.get("selected"), dict) or not base.get("confirmation_id"):
        raise ValueError("Selected Base confirmation provenance is missing")
    before = base.get("analysis")
    phase8_before = final.get("before_stable_analysis")
    after = final.get("after_stable_analysis")
    if not all(isinstance(row, dict) and isinstance(row.get("canonical_requirements"), list)
               for row in (before, phase8_before, after)):
        raise ValueError("One of the saved requirement analyses is unavailable")
    if int(final.get("application_id") or 0) != int(application_id):
        raise ValueError("Phase 8 verification belongs to a different Application Session")
    if not _clean(final.get("generation_id")) or not _clean(final.get("verification_fingerprint")):
        raise ValueError("Phase 8 fitted generation or verification identity missing")
    if final.get("comparison_valid") is not True:
        raise ValueError("Phase 8 did not verify a comparable canonical requirement scope")

    # Deep equality requires the exact pre-tailoring evidence and metrics, not
    # merely the same total score. This also blocks silently refreshed baselines.
    if before != phase8_before:
        # Explicit document workflows preserve Initial as the primary before,
        # and may store a *second* verified selected-base branch. Only accept
        # that branch when its native baseline matches the confirmed B receipt.
        selected_branch = final.get("selected_base_analysis") or {}
        selected_ab = final.get("selected_base_job_match_ab") or {}
        if (not isinstance(selected_branch, dict)
                or selected_branch.get("stable_analysis") != before
                or not isinstance(selected_ab, dict)
                or selected_ab.get("comparable") is not True):
            raise ValueError(
                "Saved Phase 8 before-analysis differs from the confirmed Phase 9F Base "
                "and no compatible selected-base branch is saved."
            )
    base_ids = [_clean(r.get("requirement_id")) for r in before["canonical_requirements"]
                if isinstance(r, dict)]
    final_ids = [_clean(r.get("requirement_id")) for r in after["canonical_requirements"]
                 if isinstance(r, dict)]
    if (not base_ids or any(not rid for rid in base_ids + final_ids)
            or len(base_ids) != len(set(base_ids))
            or len(final_ids) != len(set(final_ids))
            or set(base_ids) != set(final_ids)):
        raise ValueError("Confirmed Base and final requirement IDs are missing or inconsistent")
    for field in (
        "scoring_version", "capability_taxonomy_version", "technology_registry_version",
        "jd_structure_inference_version", "technology_registry_resolution_version",
    ):
        if not before.get(field) or before.get(field) != after.get(field):
            raise ValueError("Incompatible saved Phase 8 scoring identity: " + field)
    from analysis_stability.requirement_presentation import score_value
    before_score = score_value(before)
    after_score = score_value(after)
    if before_score is None or after_score is None:
        raise ValueError("One of the saved Job Match scores is explicitly unavailable")
    return {
        "source_name": _clean(base["selected"].get("source_display_name")) or "Selected Base",
        "source_type": _clean(base["selected"].get("source_type")),
        "before": deepcopy(before),
        "after": deepcopy(after),
        "before_score": before_score,
        "after_score": after_score,
        "score_delta": after_score - before_score,
        "generation_id": _clean(final["generation_id"]),
        "verification_fingerprint": _clean(final["verification_fingerprint"]),
        "fit_one_page": final.get("fit_one_page") is True,
        "approved": _clean(final.get("generation_status")).lower() == "approved",
        "comparison_valid": True,
    }


def _evidence_text(row: dict[str, Any]) -> str:
    snippets = []
    for item in row.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        value = item.get("text") or item.get("snippet") or item.get("evidence_text")
        if isinstance(value, str) and value.strip():
            snippets.append(value.strip())
    return " | ".join(dict.fromkeys(snippets))


def requirement_delta_rows(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Describe recorded label/evidence changes; never infer their cause."""
    left = {str(r["requirement_id"]): r for r in before["canonical_requirements"]}
    right = {str(r["requirement_id"]): r for r in after["canonical_requirements"]}
    if left.keys() != right.keys():
        raise ValueError("Requirement identities differ")
    rows = []
    for rid, a in left.items():
        b = right[rid]
        original = _clean(a.get("match_label") or "none").lower()
        revised = _clean(b.get("match_label") or "none").lower()
        changed = (original != revised or a.get("evidence") != b.get("evidence"))
        rows.append({
            "Requirement": _clean(a.get("text")),
            "Importance": _clean(a.get("importance")),
            "Base match": original,
            "Tailored match": revised,
            "Evidence changed": "Yes" if changed else "No",
            "Base selected evidence": _evidence_text(a),
            "Tailored selected evidence": _evidence_text(b),
            "Requirement ID": rid,
        })
    return rows


def render_selected_base_vs_tailored(st: Any, application_id: int, *, preview_only: bool = False, comparison_only: bool = False, verified_result: dict[str, Any] | None = None) -> bool:
    """Show selected-base analysis before tailoring or its exact verified Phase 8 comparison."""
    from tailoring.phase9f_session_handoff import load_confirmed_source_view
    from analysis_stability.requirement_presentation import score_text, score_value
    from tailoring.initial_analysis_explainer import build_analysis_receipt, compare_analysis_receipts

    try:
        base = load_confirmed_source_view(application_id)
    except (ValueError, TypeError, KeyError, sqlite3.Error, OSError) as exc:
        st.warning("Selected Base receipt unavailable: " + str(exc))
        return False
    if base is None:
        return False

    try:
        receipt = build_analysis_receipt(
            base["analysis"], raw_jd_text=base["raw_jd_text"],
            provenance="PHASE9F_CONFIRMED_SELECTED_BASE",
            identity={"application_id": int(application_id),
                      "phase9f_confirmation_id": base["confirmation_id"]},
        )
    except (ValueError, KeyError, TypeError) as exc:
        st.warning("Saved Base requirement-level receipt unavailable: " + str(exc))
        return True
    if not comparison_only:
        st.subheader("Selected Base Analysis")
        st.caption(
            "This is the confirmed Phase 9F Base/Blueprint selected for tailoring "
            "against the exact JD. It is separate from an explicitly frozen Initial Résumé Analysis."
        )
        selected = base["selected"]
        st.write("**Selected source:** " + _clean(selected.get("source_display_name")))
        columns = st.columns(4)
        for column, label, field in zip(
            columns,
            ("Base Job Match", "Required/Core", "Preferred", "Evidence strength"),
            ("deterministic_alignment_score", "required_core_coverage_score",
             "preferred_coverage_score", "evidence_strength_score"),
        ):
            column.metric(label, score_text(score_value(base["analysis"], field)))

        with st.expander("Preview: Selected Base analysis (requirements and evidence)", expanded=False):
            rows = [{
                "Requirement": row["native"].get("text"),
                "Importance": row["native"].get("importance"),
                "Match": row["native"].get("match_label"),
                "Selected evidence": _evidence_text(row["native"]),
                "Capability": row["native"].get("capability_id"),
                "Requirement ID": row["requirement_id"],
            } for row in receipt["requirements"]]
            st.dataframe(rows, hide_index=True, width="stretch")
            st.caption("Original saved Phase 9F-B requirement evidence. This preview makes no new match claims.")

        # The full presenter itself contains a diagnostics expander. Render it only
        # in an ordinary container, never nested inside our own expander.
        if st.checkbox("Show full Selected Base analysis (score arithmetic and evidence diagnostics)",
                       key=f"phase9f_full_selected_base_receipt_{application_id}"):
            from tailoring.initial_analysis_explainer_ui import render_analysis_receipt
            with st.container(border=True):
                render_analysis_receipt(st, receipt, show_taxonomy=False)

    if preview_only:
        return True
    with st.expander("Selected Base vs Tailored — saved Phase 8 comparison", expanded=True):
        try:
            final = (verified_result if verified_result is not None
                     else load_latest_phase8_read_only(application_id))
        except (ValueError, sqlite3.Error, OSError, json.JSONDecodeError) as exc:
            st.warning("Saved Phase 8 final receipt unavailable: " + str(exc))
            return True
        if final is None:
            st.info("No saved Phase 8 verification yet. Build and Fit, then verify the fitted résumé to see a Base-to-Tailored comparison.")
            return True
        try:
            pair = verify_selected_base_phase8_pair(base, final, application_id=application_id)
            final_receipt = build_analysis_receipt(
                pair["after"], raw_jd_text=base["raw_jd_text"],
                provenance="PHASE8_SAVED_TAILORED_RESULT",
                identity={"application_id": int(application_id),
                          "generation_id": pair["generation_id"]},
            )
            compared = compare_analysis_receipts(receipt, final_receipt)
            if not compared["comparable"]:
                raise ValueError("Incompatible native evidence comparison: " + ", ".join(compared["blockers"]))
        except (ValueError, KeyError, TypeError) as exc:
            st.warning("Base-to-Tailored score withheld: " + str(exc))
            return True

        metrics = st.columns(3)
        metrics[0].metric("Selected Base Job Match", score_text(pair["before_score"]))
        metrics[1].metric("Saved Tailored Job Match", score_text(pair["after_score"]))
        metrics[2].metric("Observed difference", f"{pair['score_delta']:+g} points")
        st.caption(
            "Same Application, exact confirmed Phase 9F Base, canonical JD, and saved scorer identity. "
            "This is a saved Phase 8 result, not a new scoring run. Differences do not prove tailoring caused a gain."
        )
        st.caption(f"Verified generation {pair['generation_id'][:12]} · "
                   f"{'Approved' if pair['approved'] else 'Draft/not approved'} · "
                   f"{'One-page fit verified' if pair['fit_one_page'] else 'One-page fit not verified'}")
        delta_rows = requirement_delta_rows(pair["before"], pair["after"])
        native_changes = {str(row.get("requirement_id")): row
                          for row in compared.get("requirements", []) if isinstance(row, dict)}
        for row in delta_rows:
            change = native_changes.get(str(row["Requirement ID"]), {})
            left = (change.get("initial") or {}).get("contribution") or {}
            right = (change.get("final") or {}).get("contribution") or {}
            row["Base point contribution"] = left.get("overall_point_contribution")
            row["Tailored point contribution"] = right.get("overall_point_contribution")
            row["Contribution change"] = change.get("contribution_delta")
        if delta_rows:
            st.dataframe(delta_rows, hide_index=True, width="stretch")
            st.caption("A blank contribution indicates that historical score-arithmetic parity could not be established; no points are invented.")
    return True

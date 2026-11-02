"""Read-only score math for frozen Initial/Discovery/Selected Base analyses.

The calculations are delegated to the same saved-analysis receipt builder as Phase 8.
No job/resume analysis, model execution or persistence occurs here.
"""
from __future__ import annotations

import csv
import io
from typing import Any

from tailoring.phase8_score_explainability import build_score_breakdown, build_score_receipt


def initial_score_math(view: dict[str, Any]) -> dict[str, Any] | None:
    """Only expose reconstructed arithmetic when the saved scorer reconciles."""
    if view.get("contribution_status") != "available":
        return None
    native = view.get("stable_analysis")
    if not isinstance(native, dict):
        return None
    breakdown = build_score_breakdown(native)
    receipt = build_score_receipt(breakdown)
    if not all(
        receipt.get(key, False)
        for key in (
            "score_parity", "component_subtotal_parity", "requirement_subtotal_parity",
            "maximum_score_parity", "jd_requirement_max_total_parity",
        )
    ):
        return None
    if receipt["stored_scorer_score"] != view.get("score"):
        return None
    receipt["_source_breakdown"] = breakdown  # UI-local provenance; not persisted.
    return receipt


def _score_map_csv(receipt: dict[str, Any]) -> str:
    columns = ("requirement_id", "requirement", "importance", "match_label",
               "match_value", "effective_weight", "coverage_max_final_points",
               "evidence_max_final_points", "max_final_points",
               "current_final_points", "gap_to_max")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for row in receipt.get("jd_requirements", []):
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def render_initial_score_math(st: Any, view: dict[str, Any]) -> None:
    """Component tables for the already-saved, parity-validated Initial score."""
    from tailoring.score_component_tables_ui import render_component_tables

    with st.expander("How this Job Match /100 is calculated", expanded=False):
        receipt = initial_score_math(view)
        if receipt is None:
            st.warning(
                "Exact historical score contributions are unavailable or do not "
                "reconcile with the saved scorer. No alternate score was calculated."
            )
            return

        st.markdown(f"**How {receipt['stored_scorer_score']}/100 was computed**")
        arithmetic = [
            f"{row['label']}: {row['score']:.2f} × {row['weight']:.0%} "
            f"= {row['weighted_points']:.2f} points"
            for row in receipt["components"]
        ]
        arithmetic.append(
            f"Subtotal: {receipt['subtotal_before_rounding']:.2f} / "
            f"{receipt['maximum_score']:.2f}"
        )
        arithmetic.append(f"Rounded Job Match: {receipt['stored_scorer_score']}/100")
        st.code("\n".join(arithmetic), language="text")
        st.caption(
            "Required/core and preferred coverage are separate weighted pools. "
            "Evidence strength is the native scored evidence component. "
            "This is not an ATS probability."
        )
        render_component_tables(
            st, receipt, breakdown=receipt.get("_source_breakdown"),
            key_prefix="initial_job_match", origin=str(view.get("provenance") or "initial_saved_analysis"),
            legacy_csv=_score_map_csv(receipt),
        )

        if st.checkbox("Show advanced original score map", key="initial_score_advanced_map_v1"):
            st.dataframe(
                [
                    {"Pool": row["label"], "Requirements": row["requirement_count"],
                     "Denominator": row["denominator_display"],
                     "Reference maximum /100": round(row["max_final_points"], 3)}
                    for row in receipt["pools"]
                ], hide_index=True, width="stretch",
            )
            st.caption(
                "Legacy 'Total max' is a nominal coverage + equal evidence reference "
                "allocation, NOT a hard per-requirement earned-points ceiling. "
                "Evidence is actually attributed by strength among credited rows. "
                "Atomic children share their parent's weight."
            )
            st.dataframe(
                [
                    {"Requirement": row["requirement"], "Requirement ID": row["requirement_id"],
                     "Importance": row["importance"], "Evidence match": row["match_label"],
                     "Match value": row["match_value"],
                     "Adjusted weight": round(row["effective_weight"], 4),
                     "Coverage reference": round(row["coverage_max_final_points"], 3),
                     "Evidence reference": round(row["evidence_max_final_points"], 3),
                     "Total reference": round(row["max_final_points"], 3),
                     "Blended earned": round(row["current_final_points"], 3),
                     "Gap to reference (clamped)": round(row["gap_to_max"], 3)}
                    for row in receipt["jd_requirements"]
                ], hide_index=True, width="stretch",
            )
            st.caption(
                f"Requirement earned subtotal: {receipt['requirement_subtotal']:.2f} "
                f"= component subtotal {receipt['subtotal_before_rounding']:.2f} "
                f"(reconciled). Reference allocations total "
                f"{receipt['jd_requirement_max_total']:.2f}/100."
            )
            st.download_button(
                "Download initial JD score map (CSV)",
                data=_score_map_csv(receipt).encode("utf-8-sig"),
                file_name="initial_job_match_score_map.csv", mime="text/csv",
                on_click="ignore",
            )

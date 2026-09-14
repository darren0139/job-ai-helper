"""Streamlit rendering for Phase 8 score explainability."""
from __future__ import annotations

import csv
import html
import io

from typing import Any

import streamlit as st

PHASE8_SCORE_RECEIPT_UI_VERSION = "phase8-score-receipt-ui-v5"

from tailoring.phase8_score_explainability import (
    build_phase8_explainability,
    build_score_receipt,
)


def _component_table(breakdown: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "Component": row.get("label", ""),
            "Component score": round(float(row.get("score", 0.0)), 1),
            "Weight": f"{100 * float(row.get('weight', 0.0)):.0f}%",
            "Weighted points": round(float(row.get("weighted_points", 0.0)), 2),
        }
        for row in breakdown.get("components", []) or []
    ]



def _requirement_math_table(
    breakdown: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "Requirement": row.get("requirement", ""),
            "Importance": row.get("importance", ""),
            "Match": row.get("match_label", ""),
            "Match value": round(float(row.get("match_value", 0.0)), 2),
            "Importance weight": round(
                float(row.get("importance_weight", 0.0)), 2
            ),
            "Atomic-adjusted weight": round(
                float(row.get("effective_weight", 0.0)), 3
            ),
            "Coverage pts": round(
                float(row.get("overall_coverage_points", 0.0)), 3
            ),
            "Evidence pts": round(
                float(row.get("overall_evidence_points", 0.0)), 3
            ),
            "Final pts": round(
                float(row.get("overall_point_contribution", 0.0)), 3
            ),
        }
        for row in breakdown.get("requirements", []) or []
        if isinstance(row, dict)
    ]


def _compact_requirement_text(
    value: object,
    *,
    limit: int = 96,
) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def _jd_score_map_table(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "#": int(row.get("index", 0) or 0),
            "JD requirement": _compact_requirement_text(row.get("requirement", "")),
            "Importance": row.get("importance", ""),
            "Match": row.get("match_label", ""),
            "Max pts": round(float(row.get("max_final_points", 0.0)), 3),
            "Earned": round(float(row.get("current_final_points", 0.0)), 3),
            "Gap": round(float(row.get("gap_to_max", 0.0)), 3),
        }
        for row in receipt.get("jd_requirements", []) or []
        if isinstance(row, dict)
    ]


def _jd_score_map_csv(receipt: dict[str, Any]) -> str:
    fieldnames = [
        "index",
        "requirement_id",
        "canonical_jd_requirement",
        "importance",
        "current_match",
        "match_value",
        "importance_weight",
        "atomic_adjusted_weight",
        "coverage_raw_earned",
        "coverage_raw_max",
        "coverage_max_final_points",
        "evidence_max_final_points",
        "max_of_final_100",
        "currently_earned",
        "gap_to_max",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in receipt.get("jd_requirements", []) or []:
        if not isinstance(row, dict):
            continue
        writer.writerow(
            {
                "index": int(row.get("index", 0) or 0),
                "requirement_id": row.get("requirement_id", ""),
                "canonical_jd_requirement": row.get("requirement", ""),
                "importance": row.get("importance", ""),
                "current_match": row.get("match_label", ""),
                "match_value": row.get("match_value", 0.0),
                "importance_weight": row.get("importance_weight", 0.0),
                "atomic_adjusted_weight": row.get("effective_weight", 0.0),
                "coverage_raw_earned": row.get("coverage_raw_earned", 0.0),
                "coverage_raw_max": row.get("coverage_raw_max", 0.0),
                "coverage_max_final_points": row.get(
                    "coverage_max_final_points", 0.0
                ),
                "evidence_max_final_points": row.get(
                    "evidence_max_final_points", 0.0
                ),
                "max_of_final_100": row.get("max_final_points", 0.0),
                "currently_earned": row.get("current_final_points", 0.0),
                "gap_to_max": row.get("gap_to_max", 0.0),
            }
        )
    return output.getvalue()


def _html_cell(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def _score_explanation_report_html(receipt: dict[str, Any]) -> str:
    final_score = int(receipt.get("final_score", 0) or 0)
    subtotal = float(receipt.get("subtotal_before_rounding", 0.0) or 0.0)
    maximum = float(receipt.get("maximum_score", 0.0) or 0.0)

    component_rows: list[str] = []
    component_terms: list[str] = []
    for row in receipt.get("components", []) or []:
        if not isinstance(row, dict):
            continue
        score = float(row.get("score", 0.0) or 0.0)
        weight = float(row.get("weight", 0.0) or 0.0)
        weighted = float(row.get("weighted_points", 0.0) or 0.0)
        component_terms.append(f"{weighted:.2f}")
        component_rows.append(
            "<tr>"
            f"<td>{_html_cell(row.get('label', ''))}</td>"
            f"<td>{score:.2f}</td>"
            f"<td>{weight * 100:.0f}%</td>"
            f"<td>{weighted:.2f}</td>"
            "</tr>"
        )

    pool_rows: list[str] = []
    for row in receipt.get("pools", []) or []:
        if not isinstance(row, dict):
            continue
        pool_rows.append(
            "<tr>"
            f"<td>{_html_cell(row.get('label', ''))}</td>"
            f"<td>{int(row.get('requirement_count', 0) or 0)}</td>"
            f"<td>{_html_cell(row.get('denominator_display', ''))}</td>"
            f"<td>{float(row.get('weight', 0.0) or 0.0) * 100:.0f}%</td>"
            f"<td>{float(row.get('max_final_points', 0.0) or 0.0):.2f}</td>"
            "</tr>"
        )

    jd_rows: list[str] = []
    for row in receipt.get("jd_requirements", []) or []:
        if not isinstance(row, dict):
            continue
        jd_rows.append(
            "<tr>"
            f"<td>{int(row.get('index', 0) or 0)}</td>"
            f"<td class='requirement'>{_html_cell(row.get('requirement', ''))}</td>"
            f"<td>{_html_cell(row.get('importance', ''))}</td>"
            f"<td>{_html_cell(row.get('match_label', ''))}</td>"
            f"<td>{float(row.get('max_final_points', 0.0) or 0.0):.3f}</td>"
            f"<td>{float(row.get('current_final_points', 0.0) or 0.0):.3f}</td>"
            f"<td>{float(row.get('gap_to_max', 0.0) or 0.0):.3f}</td>"
            "</tr>"
        )

    opportunities = sorted(
        [
            row
            for row in receipt.get("jd_requirements", []) or []
            if isinstance(row, dict)
            and float(row.get("gap_to_max", 0.0) or 0.0) > 1e-6
        ],
        key=lambda row: float(row.get("gap_to_max", 0.0) or 0.0),
        reverse=True,
    )
    opportunity_rows: list[str] = []
    for row in opportunities:
        opportunity_rows.append(
            "<tr>"
            f"<td>{_html_cell(row.get('requirement', ''))}</td>"
            f"<td>{_html_cell(row.get('importance', ''))}</td>"
            f"<td>{_html_cell(row.get('match_label', ''))}</td>"
            f"<td>{float(row.get('gap_to_max', 0.0) or 0.0):.3f}</td>"
            f"<td>{_html_cell(_alignment_opportunity_hint(row.get('match_label', '')))}</td>"
            "</tr>"
        )

    subtotal_terms = " + ".join(component_terms) if component_terms else "0.00"

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Phase 8 score explanation — {final_score}/100</title>
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; margin: 32px; color: #111; line-height: 1.4; }}
  h1, h2 {{ margin-bottom: 8px; }}
  .summary {{ border: 1px solid #bbb; border-radius: 8px; padding: 16px; margin: 16px 0 24px; }}
  .equation {{ font-family: Consolas, "Courier New", monospace; white-space: pre-wrap; }}
  table {{ width: 100%; border-collapse: collapse; table-layout: fixed; margin: 12px 0 24px; font-size: 12px; }}
  th, td {{ border: 1px solid #bbb; padding: 6px 8px; text-align: left; vertical-align: top; overflow-wrap: anywhere; word-break: break-word; }}
  th {{ background: #f1f1f1; }}
  td.requirement {{ width: 48%; }}
  .note {{ color: #444; font-size: 12px; }}
  @media print {{
    body {{ margin: 12mm; }}
    table {{ page-break-inside: auto; }}
    tr {{ page-break-inside: avoid; page-break-after: auto; }}
    h2 {{ page-break-after: avoid; }}
  }}
</style>
</head>
<body>
<h1>Phase 8 score explanation</h1>
<div class="summary">
<strong>Final deterministic role-alignment score: {final_score}/100</strong>
<div class="equation">Subtotal earned: {subtotal_terms} = {subtotal:.2f}
Maximum possible score: {maximum:.2f}
Rounded final score: round({subtotal:.2f}) = {final_score}/100</div>
</div>
<h2>Score receipt</h2>
<table><thead><tr><th>Component</th><th>Component score</th><th>Weight</th><th>Weighted points</th></tr></thead><tbody>{''.join(component_rows)}</tbody></table>
<h2>Where the 100 points come from</h2>
<table><thead><tr><th>Pool</th><th>JD requirements</th><th>Denominator</th><th>Final weight</th><th>Maximum points</th></tr></thead><tbody>{''.join(pool_rows)}</tbody></table>
<h2>Canonical JD requirement score map</h2>
<table><thead><tr><th>#</th><th>Canonical JD requirement</th><th>Importance</th><th>Current match</th><th>Max points</th><th>Earned</th><th>Gap</th></tr></thead><tbody>{''.join(jd_rows)}</tbody></table>
<h2>Largest current alignment opportunities</h2>
<table><thead><tr><th>Canonical JD requirement</th><th>Importance</th><th>Current match</th><th>Gap</th><th>Interpretation</th></tr></thead><tbody>{''.join(opportunity_rows)}</tbody></table>
<p class="note">This is a deterministic internal role-alignment score, not an ATS pass probability or hiring likelihood. Improve only truthful résumé evidence. Requirements for capabilities you do not yet have should be treated as possible learning targets, not as claims to add without evidence.</p>
</body>
</html>
'''


def _score_pool_table(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "Pool": row.get("label", ""),
            "JD requirements": int(row.get("requirement_count", 0) or 0),
            "Denominator": row.get("denominator_display", ""),
            "Final weight": (
                f"{float(row.get('weight', 0.0) or 0.0) * 100:.0f}%"
            ),
            "Maximum final points": round(
                float(row.get("max_final_points", 0.0)), 2
            ),
        }
        for row in receipt.get("pools", []) or []
        if isinstance(row, dict)
    ]


def _alignment_opportunity_hint(match_label: str) -> str:
    label = str(match_label or "none").strip().lower()
    if label == "none":
        return (
            "No credited match. If you already have this capability, add "
            "truthful direct evidence; otherwise treat it as a learning target."
        )
    if label == "weak":
        return (
            "Related evidence exists. Strengthen it with a direct, truthful "
            "example if you have one, or deepen the skill."
        )
    if label == "transferable":
        return (
            "Transferable evidence exists. Direct role-relevant experience or "
            "evidence would close more of this gap."
        )
    return "Direct evidence is already credited for this requirement."


def _alignment_opportunity_table(
    receipt: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = [
        row
        for row in receipt.get("jd_requirements", []) or []
        if isinstance(row, dict)
        and float(row.get("gap_to_max", 0.0) or 0.0) > 1e-6
    ]
    rows.sort(
        key=lambda row: float(row.get("gap_to_max", 0.0) or 0.0),
        reverse=True,
    )
    return [
        {
            "Canonical JD requirement": row.get("requirement", ""),
            "Importance": row.get("importance", ""),
            "Current match": row.get("match_label", ""),
            "Gap to max": round(
                float(row.get("gap_to_max", 0.0)), 3
            ),
            "How to interpret it": _alignment_opportunity_hint(
                str(row.get("match_label") or "none")
            ),
        }
        for row in rows
    ]


def _render_score_receipt(
    breakdown: dict[str, Any],
    *,
    key_prefix: str,
) -> None:
    receipt = build_score_receipt(breakdown)
    final_score = int(receipt.get("final_score", 0) or 0)
    rows = receipt.get("components", []) or []

    st.markdown(f"##### How {final_score}/100 was computed")

    lines: list[str] = []
    weighted_terms: list[str] = []
    for row in rows:
        label = str(row.get("label") or "")
        score = float(row.get("score", 0.0) or 0.0)
        weight = float(row.get("weight", 0.0) or 0.0)
        weighted_points = float(row.get("weighted_points", 0.0) or 0.0)
        weighted_terms.append(f"{weighted_points:.2f}")
        lines.append(
            f"{label:<24} {score:>6.2f} × {weight * 100:>3.0f}%"
            f" = {weighted_points:>6.2f}"
        )

    subtotal = float(receipt.get("subtotal_before_rounding", 0.0) or 0.0)
    maximum = float(receipt.get("maximum_score", 0.0) or 0.0)
    subtotal_equation = " + ".join(weighted_terms) if weighted_terms else "0.00"
    lines.extend(
        [
            "-" * 68,
            f"Subtotal earned          {subtotal_equation} = {subtotal:.2f}",
            f"Maximum possible score                         = {maximum:.2f}",
            f"Rounded final score       round({subtotal:.2f}) = "
            f"{final_score}/100",
        ]
    )
    st.code("\n".join(lines), language="text")

    requirement_subtotal = float(
        receipt.get("requirement_subtotal", 0.0) or 0.0
    )
    if receipt.get("requirement_subtotal_parity", False):
        st.caption(
            "Requirement-level earned subtotal: "
            f"{requirement_subtotal:.2f} ✓ — reconciles to the component subtotal."
        )
    else:
        st.warning(
            "Requirement-level earned subtotal does not reconcile to the "
            "component subtotal. Treat the receipt as diagnostic until investigated."
        )

    st.caption(
        "This is a deterministic internal role-alignment score, not an ATS pass "
        "probability or hiring likelihood."
    )

    with st.expander(
        "Which JD requirements make up the 100 points?",
        expanded=False,
    ):
        st.write(
            "The 100-point maximum is allocated from the canonical requirements "
            "extracted from this job description. Required/Core and Preferred "
            "requirements form separate coverage denominators; every scored "
            "requirement also receives an equal share of the Evidence Strength "
            "maximum."
        )
        st.dataframe(
            _score_pool_table(receipt),
            hide_index=True,
            width="stretch",
        )

        if not receipt.get("maximum_score_parity", False):
            st.warning(
                "The active component weights do not sum to a 100-point maximum."
            )
        elif not receipt.get("jd_requirement_max_total_parity", False):
            st.warning(
                "The JD requirement allocation does not reconcile to the active "
                "component maximum. Treat this view as diagnostic."
            )
        else:
            st.caption(
                "JD requirement maximum shares reconcile to "
                f"{float(receipt.get('maximum_score', 0.0)):.2f}/100 ✓"
            )

        st.dataframe(
            _jd_score_map_table(receipt),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Long requirement text is shortened only in this on-screen table. "
            "Use the full-text view or downloads below for the complete canonical "
            "JD wording."
        )
        st.caption(
            "Atomic children share their parent's importance weight, so splitting "
            "one JD statement does not create extra maximum points."
        )

        export_left, export_right = st.columns(2)
        with export_left:
            st.download_button(
                "Download JD score map CSV",
                data=_jd_score_map_csv(receipt).encode("utf-8-sig"),
                file_name="phase8_jd_score_map.csv",
                mime="text/csv",
                key=f"{key_prefix}_jd_score_map_csv",
            )
        with export_right:
            st.download_button(
                "Download printable score explanation",
                data=_score_explanation_report_html(receipt).encode("utf-8"),
                file_name="phase8_score_explanation.html",
                mime="text/html",
                key=f"{key_prefix}_score_explanation_html",
            )
        st.caption(
            "These human-readable exports are separate from the technical "
            "Phase 8 Verification JSON download."
        )

    with st.expander("Show full JD requirement text", expanded=False):
        for row in receipt.get("jd_requirements", []) or []:
            if not isinstance(row, dict):
                continue
            index = int(row.get("index", 0) or 0)
            importance = str(row.get("importance") or "")
            match_label = str(row.get("match_label") or "none")
            st.markdown(
                f"**#{index} · {importance} · {match_label}**"
            )
            st.write(str(row.get("requirement") or ""))

    with st.expander(
        "Largest current alignment opportunities",
        expanded=False,
    ):
        opportunities = _alignment_opportunity_table(receipt)
        if opportunities:
            st.write(
                "These are the largest gaps in this deterministic score. If you "
                "already have a capability, improve only truthful resume evidence. "
                "If you do not have it, treat the requirement as a possible learning "
                "target rather than adding an unsupported claim."
            )
            st.dataframe(
                opportunities,
                hide_index=True,
                width="stretch",
            )
        else:
            st.caption(
                "No remaining requirement-level point gaps were found."
            )

    with st.expander("Show requirement-level math", expanded=False):
        st.dataframe(
            _requirement_math_table(breakdown),
            hide_index=True,
            width="stretch",
        )


def _render_breakdown(label: str, breakdown: dict[str, Any]) -> None:
    scorer_score = int(breakdown.get("scorer_score", 0) or 0)
    reconstructed = int(breakdown.get("reconstructed_score", 0) or 0)
    st.markdown(f"**{label}: {scorer_score}/100**")
    st.dataframe(_component_table(breakdown), hide_index=True, width="stretch")
    _render_score_receipt(
        breakdown,
        key_prefix="".join(
            char.lower() if char.isalnum() else "_"
            for char in label
        ),
    )
    if not breakdown.get("score_parity", False):
        st.warning(
            "The explainability reconstruction did not match the stored scorer score. "
            "Treat this tabulation as diagnostic until investigated."
        )


def render_phase8_score_explainability(result: dict[str, Any]) -> None:
    payload = build_phase8_explainability(result)
    before = payload["before"]
    after = payload["after"]

    st.markdown("#### Score explanation")
    st.caption(
        "After fitting is the verified/reconciled result used by Phase 8. "
        "Before fitting remains available for comparison."
    )
    after_tab, before_tab = st.tabs(["After fitting", "Before fitting"])
    with after_tab:
        _render_breakdown("Verified after fitting", after)
    with before_tab:
        _render_breakdown("Baseline before fitting", before)

    changed = payload.get("changed_requirements", []) or []
    if changed:
        st.markdown("#### What changed")
        st.dataframe(
            [
                {
                    "Requirement": row.get("requirement", ""),
                    "Importance": row.get("importance", ""),
                    "Before": row.get("before", ""),
                    "Raw after": row.get("raw_after", ""),
                    "Verified after": row.get("verified_after", ""),
                    "Change": row.get("change_symbol", ""),
                    "Overall-point Δ": row.get("overall_point_delta", 0.0),
                    "Evidence after fitting": row.get("evidence_after", ""),
                }
                for row in changed
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("No requirement label changed after fitting.")

    with st.expander("How the /100 score is calculated", expanded=False):
        st.write(
            "Each canonical JD requirement receives a deterministic match value. "
            "Required/Core and Preferred coverage are weighted separately, then "
            "Evidence Strength contributes 10%."
        )
        st.dataframe(
            [
                {"Match label": label.title(), "Match value": value}
                for label, value in (after.get("match_values", {}) or {}).items()
            ],
            hide_index=True,
            width="stretch",
        )
        st.dataframe(
            [
                {
                    "Importance": label.replace("_", " ").title(),
                    "Weight": weight,
                }
                for label, weight in (after.get("importance_weights", {}) or {}).items()
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(str(after.get("formula") or ""))

    all_rows = payload.get("requirement_changes", []) or []
    with st.expander(f"All scored requirements ({len(all_rows)})", expanded=False):
        st.dataframe(
            [
                {
                    "Requirement ID": row.get("requirement_id", ""),
                    "Requirement": row.get("requirement", ""),
                    "Importance": row.get("importance", ""),
                    "Before": row.get("before", ""),
                    "Raw after": row.get("raw_after", ""),
                    "Verified after": row.get("verified_after", ""),
                    "Before points": row.get("before_overall_points", 0.0),
                    "After points": row.get("after_overall_points", 0.0),
                    "Point Δ": row.get("overall_point_delta", 0.0),
                    "Evidence after fitting": row.get("evidence_after", ""),
                }
                for row in all_rows
            ],
            hide_index=True,
            width="stretch",
        )

    reconciled = payload.get("reconciled_requirements", []) or []
    with st.expander("Advanced Phase 8 reconciliation diagnostics", expanded=False):
        if reconciled:
            st.dataframe(
                [
                    {
                        "Requirement": row.get("requirement", ""),
                        "Before": row.get("before", ""),
                        "Raw after": row.get("raw_after", ""),
                        "Reconciled after": row.get("verified_after", ""),
                        "Evidence after fitting": row.get("evidence_after", ""),
                    }
                    for row in reconciled
                ],
                hide_index=True,
                width="stretch",
            )
        else:
            st.caption("No raw-after labels needed reconciliation for this snapshot.")
        baseline = result.get("before_stable_analysis", {}) or {}
        final = result.get("after_stable_analysis", {}) or {}
        st.json(
            {
                "phase8_version": result.get("phase8_version"),
                "scoring_version_before": baseline.get("scoring_version"),
                "scoring_version_after": final.get("scoring_version"),
                "taxonomy_version_before": baseline.get("capability_taxonomy_version"),
                "taxonomy_version_after": final.get("capability_taxonomy_version"),
                "comparison_valid": result.get("comparison_valid"),
                "verified_generation_snapshot_fingerprint": result.get(
                    "verified_generation_snapshot_fingerprint"
                ),
            }
        )

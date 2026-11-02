"""Read-only component receipts and exports for saved Job Match analyses.

UI-only: no matching, LLM calls, persistence, or production scoring changes.
"""
from __future__ import annotations

import csv
import io
import json
import math
from typing import Any
from tailoring.session_table_ui_v2 import render_session_table
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

_VERSION = "score-component-tables-ui-v1"
_PARITY = (
    "score_parity", "component_subtotal_parity", "requirement_subtotal_parity",
    "maximum_score_parity", "jd_requirement_max_total_parity",
)
_COVERAGE_FIELDS = (
    "requirement_id", "requirement", "importance", "match_label", "match_value",
    "effective_weight", "coverage_reference_points", "coverage_earned_points",
    "coverage_gap_to_reference_points",
)
_EVIDENCE_FIELDS = (
    "requirement_id", "requirement", "match_label", "evidence_strength_0_to_5",
    "evidence_earned_points",
)
_OVERALL_FIELDS = (
    "component", "raw_score_percent", "component_weight_percent", "earned_points",
    "component_max_points",
)


def _number(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite score value")
    return number


def _csv(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return output.getvalue().encode("utf-8-sig")


def _component_by_kind(receipt: dict[str, Any], kind: str) -> dict[str, Any]:
    hits = [row for row in receipt.get("components", ()) if row.get("kind") == kind]
    if len(hits) != 1:
        raise ValueError(f"Missing or duplicate native {kind} component")
    return hits[0]


def _safe_receipt(receipt: dict[str, Any]) -> None:
    if not isinstance(receipt, dict) or not all(receipt.get(key) is True for key in _PARITY):
        raise ValueError("Native score parity is unavailable")
    components = receipt.get("components")
    rows = receipt.get("jd_requirements")
    if not isinstance(components, list) or not isinstance(rows, list):
        raise ValueError("Native score rows are missing")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("Malformed requirement receipt")
    stored = int(receipt["stored_scorer_score"])
    subtotal = _number(receipt["subtotal_before_rounding"])
    if stored != int(max(0, min(100, round(subtotal)))):
        raise ValueError("Stored score does not match native subtotal")
    if abs(sum(_number(row["weighted_points"]) for row in components) - subtotal) > 1e-6:
        raise ValueError("Component contribution total does not reconcile")
    _component_by_kind(receipt, "required_core")
    _component_by_kind(receipt, "preferred")
    _component_by_kind(receipt, "evidence")


def build_component_tables(
    receipt: dict[str, Any], *, breakdown: dict[str, Any] | None = None,
    origin: str = "saved-analysis",
) -> dict[str, Any]:
    """Return native-derived table rows without assigning new scoring authority.

    `max_final_points`/`evidence_max_final_points` in legacy receipts are
    *reference allocations*, not hard per-requirement earned-point ceilings.
    """
    _safe_receipt(receipt)
    required: list[dict[str, Any]] = []
    preferred: list[dict[str, Any]] = []
    legacy_anomalies: list[str] = []
    for row in receipt["jd_requirements"]:
        importance = str(row.get("importance") or "").strip().lower()
        if importance not in ("deal_breaker", "required", "core", "preferred"):
            raise ValueError("Unknown native importance kind")
        match = _number(row["match_value"])
        reference = _number(row["coverage_max_final_points"])
        # This is a restatement of the scorer's native coverage allocation,
        # not the legacy blended current_final_points.
        earned = reference * match
        group = preferred if importance == "preferred" else required
        group.append({
            "requirement_id": str(row.get("requirement_id") or ""),
            "requirement": str(row.get("requirement") or ""),
            "importance": importance,
            "match_label": str(row.get("match_label") or "none"),
            "match_value": match,
            "effective_weight": _number(row["effective_weight"]),
            "coverage_reference_points": reference,
            "coverage_earned_points": earned,
            "coverage_gap_to_reference_points": max(0., reference-earned),
        })
        if _number(row["current_final_points"]) > _number(row["max_final_points"]) + 1e-8:
            legacy_anomalies.append(str(row.get("requirement_id") or ""))
    components = {
        kind: _component_by_kind(receipt, kind)
        for kind in ("required_core", "preferred", "evidence")
    }
    for group, kind in ((required, "required_core"), (preferred, "preferred")):
        observed = sum(row["coverage_earned_points"] for row in group)
        expected = _number(components[kind]["weighted_points"])
        if abs(observed-expected) > 2e-4:
            raise ValueError(f"{kind} earned coverage disagrees with native receipt")

    evidence_rows: list[dict[str, Any]] = []
    evidence_detail = "aggregate_only"
    expected_evidence = _number(components["evidence"]["weighted_points"])
    if isinstance(breakdown, dict) and isinstance(breakdown.get("requirements"), list):
        source = breakdown["requirements"]
        receipt_ids = [str(row.get("requirement_id") or "") for row in receipt["jd_requirements"]]
        src_ids = [str(row.get("requirement_id") or "") for row in source if isinstance(row, dict)]
        if len(src_ids) == len(source) == len(receipt_ids) and src_ids == receipt_ids:
            proposal = []
            try:
                for row in source:
                    proposal.append({
                        "requirement_id": str(row["requirement_id"]),
                        "requirement": str(row.get("requirement") or ""),
                        "match_label": str(row.get("match_label") or "none"),
                        "evidence_strength_0_to_5": int(row.get("evidence_strength", 0)),
                        "evidence_earned_points": _number(row["overall_evidence_points"]),
                    })
                if abs(sum(x["evidence_earned_points"] for x in proposal)-expected_evidence) <= 2e-4:
                    evidence_rows = proposal
                    evidence_detail = "native_proportional_allocation"
            except (KeyError, ValueError, TypeError):
                pass
    if not evidence_rows:
        evidence_rows = [{
            "requirement_id": "",
            "requirement": "Saved aggregate evidence component",
            "match_label": "",
            "evidence_strength_0_to_5": "",
            "evidence_earned_points": expected_evidence,
        }]

    overall: list[dict[str, Any]] = [
        {
            "component": components[kind]["label"],
            "raw_score_percent": _number(components[kind]["score"]),
            "component_weight_percent": 100. * _number(components[kind]["weight"]),
            "earned_points": _number(components[kind]["weighted_points"]),
            "component_max_points": 100. * _number(components[kind]["weight"]),
        }
        for kind in ("required_core", "preferred", "evidence")
    ]
    overall.append({
        "component": "Subtotal before rounding", "raw_score_percent": "",
        "component_weight_percent": "",
        "earned_points": _number(receipt["subtotal_before_rounding"]),
        "component_max_points": _number(receipt["maximum_score"]),
    })
    overall.append({
        "component": "Saved rounded Job Match /100", "raw_score_percent": "",
        "component_weight_percent": "",
        "earned_points": int(receipt["stored_scorer_score"]),
        "component_max_points": 100,
    })

    return {
        "required_core": required,
        "preferred": preferred,
        "evidence_strength": evidence_rows,
        "overall": overall,
        "evidence_detail": evidence_detail,
        "over_allocation_reference_ids": legacy_anomalies,
        "component_scores": components,
        "manifest": {
            "ui_version": _VERSION,
            "origin": str(origin),
            "native_receipt_version": str(receipt.get("version") or "unknown"),
            "native_explainability_version": str((breakdown or {}).get("explainability_version") or "unknown"),
            "stored_score": int(receipt["stored_scorer_score"]),
            "subtotal_before_rounding": _number(receipt["subtotal_before_rounding"]),
            "precision": "raw source numeric values retained in CSV; UI rounded only",
            "evidence_detail": evidence_detail,
            "legacy_reference_allocation_exceedances": legacy_anomalies,
            "parity": {key: True for key in _PARITY},
        },
    }


def component_exports(
    tables: dict[str, Any], *, legacy_csv: str | bytes | None = None,
) -> dict[str, bytes]:
    files = {
        "required_core.csv": _csv(tables["required_core"], _COVERAGE_FIELDS),
        "preferred.csv": _csv(tables["preferred"], _COVERAGE_FIELDS),
        "evidence_strength.csv": _csv(tables["evidence_strength"], _EVIDENCE_FIELDS),
        "overall.csv": _csv(tables["overall"], _OVERALL_FIELDS),
        "manifest.json": (json.dumps(tables["manifest"], ensure_ascii=False, indent=2, sort_keys=True)+"\n").encode("utf-8"),
    }
    if legacy_csv is not None:
        files["legacy_score_map.csv"] = (legacy_csv.encode("utf-8-sig") if isinstance(legacy_csv, str) else legacy_csv)
    return files


def component_zip(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name in sorted(files):
            if "/" in name or "\\" in name or name not in {
                "required_core.csv", "preferred.csv", "evidence_strength.csv",
                "overall.csv", "manifest.json", "legacy_score_map.csv",
            }:
                raise ValueError("Unexpected export member")
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, files[name])
    return output.getvalue()


def summary_card_csv(summary: dict[str, Any]) -> bytes:
    """Export cached/saved card percentages, without inferred weighted points."""
    fields = ("component", "saved_value", "unit")
    rows = []
    for label, key, unit in (
        ("Job Match", "deterministic_alignment_score", "/100"),
        ("Required/Core coverage", "required_core_coverage_score", "%"),
        ("Preferred coverage", "preferred_coverage_score", "%"),
        ("Evidence strength", "evidence_strength_score", "%"),
    ):
        rows.append({"component": label, "saved_value": summary.get(key, ""), "unit": unit})
    return _csv(rows, fields)


def _overall_display_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Arrow-compatible display only; preserve original receipt/CSV data."""
    def nullable_number(value: Any) -> float | None:
        return None if value is None or value == "" else _number(value)

    return [
        {
            "Component": str(row["component"]),
            "Raw score (%)": nullable_number(row["raw_score_percent"]),
            "Weight (%)": nullable_number(row["component_weight_percent"]),
            "Weighted points earned": round(_number(row["earned_points"]), 4),
            "Category allocation (pts)": nullable_number(row["component_max_points"]),
        }
        for row in rows
    ]


def _native_category_points_label(receipt: dict[str, Any], component: dict[str, Any]) -> str:
    """Format one saved native component's earned points / allocated pool points.

    This is only a display of existing weighted_points and weight × maximum_score;
    it neither caps individual requirement earnings nor recomputes Job Match.
    """
    earned = _number(component["weighted_points"])
    maximum = _number(receipt["maximum_score"]) * _number(component["weight"])
    return f"{earned:.3f} / {maximum:g} pts"


def render_component_tables(
    st: Any, receipt: dict[str, Any], *, breakdown: dict[str, Any] | None = None,
    key_prefix: str, origin: str, legacy_csv: str | bytes | None = None,
) -> bool:
    """Reusable Streamlit presentation, parity gated and free of scorer calls."""
    try:
        tables = build_component_tables(receipt, breakdown=breakdown, origin=origin)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        st.warning(f"Component tables unavailable: native saved score receipt did not reconcile ({type(exc).__name__}).")
        return False
    exports = component_exports(tables, legacy_csv=legacy_csv)
    st.markdown("#### Score components and contribution tables")
    st.caption(
        "These four tables use one saved, parity-verified native scoring receipt. "
        "Each category shows earned / available points from the native scoring receipt "
        "(for example 7.765 / 80 pts). The final Job Match is /100. "
        "Per-requirement reference allocations are not hard earning caps; no score is recalculated."
    )
    for kind, title, filename in (
        ("required_core", "Required/Core coverage", "required_core.csv"),
        ("preferred", "Preferred coverage", "preferred.csv"),
        ("evidence_strength", "Evidence strength", "evidence_strength.csv"),
        ("overall", "Overall Job Match", "overall.csv"),
    ):
        component_key = "evidence" if kind == "evidence_strength" else kind
        component = tables["component_scores"].get(component_key)
        if kind == "overall":
            st.markdown(f"##### {title} · {receipt['stored_scorer_score']}/100")
            st.caption(
                f"Final calculation · exact subtotal "
                f"{receipt['subtotal_before_rounding']:.4f} /100 "
                f"→ saved rounded Job Match {receipt['stored_scorer_score']}/100."
            )
            render_session_table(st, _overall_display_rows(tables[kind]), key=f"{key_prefix}_overall")
            st.caption("The saved rounded score is authoritative; it is not an ATS acceptance probability.")
        else:
            category_label = _native_category_points_label(receipt, component)
            st.markdown(f"##### {title} · {category_label}")
            st.caption(
                f"{component['score']:.2f}% raw × {component['weight']:.0%} "
                f"= {category_label} of category allocation"
            )
            if kind in ("required_core", "preferred"):
                pools = [row for row in receipt.get("pools", ()) if row.get("kind") == kind]
                if pools:
                    st.caption(
                        f"{len(tables[kind])} requirements · "
                        f"{pools[0].get('denominator_display')} · "
                        f"{component['weight']:.0%} of final score"
                    )
                st.caption(
                    "Coverage earned = native coverage reference allocation × match value. "
                    "Evidence points are shown separately; references are not blended earning caps."
                )
                display = [
                    {"Requirement": row["requirement"], "Match": row["match_label"],
                     "Match value": row["match_value"],
                     "Coverage earned (pts)": round(row["coverage_earned_points"], 3),
                     "Reference allocation (pts)": round(row["coverage_reference_points"], 3),
                     "Requirement ID": row["requirement_id"]}
                    for row in tables[kind]
                ]
                display.append({
                    "Requirement": f"TOTAL {title} ({len(tables[kind])} requirements) · {category_label}",
                    "Match": "", "Match value": None,
                    "Coverage earned (pts)": round(sum(row["coverage_earned_points"] for row in tables[kind]), 3),
                    "Reference allocation (pts)": round(sum(row["coverage_reference_points"] for row in tables[kind]), 3),
                    "Requirement ID": "",
                })
                render_session_table(st, display, key=f"{key_prefix}_{kind}")
                st.caption("The TOTAL row sums the native requirement-level coverage contributions.")
            else:
                if tables["evidence_detail"] == "native_proportional_allocation":
                    st.caption("Native evidence points attributed proportionally to credited requirements, not equal caps.")
                else:
                    st.caption("Only a saved aggregate is available; per-requirement evidence allocation is not inferred.")
                display = [
                    {"Requirement": row["requirement"],
                     "Evidence strength (0–5)": (
                         int(row["evidence_strength_0_to_5"])
                         if row["evidence_strength_0_to_5"] != "" else None
                     ),
                     "Evidence contribution (pts)": round(row["evidence_earned_points"], 3),
                     "Requirement ID": row["requirement_id"]}
                    for row in tables[kind]
                ]
                display.append({
                    "Requirement": f"TOTAL evidence strength · {category_label}",
                    "Evidence strength (0–5)": None,
                    "Evidence contribution (pts)": round(sum(row["evidence_earned_points"] for row in tables[kind]), 3),
                    "Requirement ID": "",
                })
                render_session_table(st, display, key=f"{key_prefix}_{kind}")
                st.caption("The TOTAL row reconciles to the saved evidence component, not an invented evidence score.")
        st.download_button(
            f"Export {title} (CSV)", data=exports[filename],
            file_name=filename, mime="text/csv", key=f"{key_prefix}_{kind}_score_csv",
            on_click="ignore",
        )
        st.divider()
    if tables["over_allocation_reference_ids"]:
        st.info("Some blended per-requirement earnings exceed their nominal reference allocations. These reference shares are not hard scoring caps; the native proportional evidence attribution remains unchanged.")
    st.download_button(
        "Export all score breakdowns (ZIP)", data=component_zip(exports),
        file_name="job_match_component_breakdowns.zip", mime="application/zip",
        key=f"{key_prefix}_score_component_zip", on_click="ignore",
    )
    return True

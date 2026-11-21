"""Streamlit UI for Phase 8 tailored-résumé verification."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st
from tailoring.phase8_row_ui import render_phase8_rows

from database.tailoring_generation_control import (
    get_application_generation_control,
    is_phase9f_normal_generation_approvable,
    list_tailoring_generations,
)
from database.tailoring_verification_manager import (
    get_latest_tailoring_verification,
    save_tailoring_verification,
)
from tailoring.tailoring_generation_fingerprint import (
    generation_matches_phase9e_binding,
)
from tailoring.phase8_verification import (
    build_phase8_verification,
    refresh_phase8_readiness,
)
from tailoring.phase8_auto_verification import (
    phase8_verification_is_current,
    phase8_verification_refresh_reason,
)
from tailoring.phase8_score_explainability_ui import (
    render_phase8_score_explainability,
)


def _label(state: dict[str, Any]) -> str:
    status = str(state.get("status") or "draft").title()
    short_id = str(state.get("generation_id") or "")[:8]
    pages = (state.get("fit_result") or {}).get("page_count", "—")
    return f"{status} · {short_id} · {pages} page(s)"


def _evidence_summary(row: dict[str, Any]) -> str:
    values: list[str] = []
    for item in row.get("evidence_provenance", []) or []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or item.get("evidence_id") or "").strip()
        text = str(item.get("text") or item.get("matched_resume_term") or "").strip()
        value = " · ".join(part for part in (source, text) if part)
        if value and value not in values:
            values.append(value)
    return " | ".join(values)


def _snapshot_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "Requirement ID": row.get("requirement_id", ""),
            "Requirement": row.get("requirement_text", ""),
            "Importance": row.get("importance", ""),
            "Eligible": row.get("score_eligible", False),
            "Preliminary": row.get("preliminary_match", "none"),
            "Final": row.get("final_match", "none"),
            "Contribution": round(float(row.get("score_contribution", 0.0) or 0.0), 3),
            "Evidence / provenance": _evidence_summary(row),
            "Taxonomy": row.get("taxonomy_status", ""),
            "Capability": row.get("taxonomy_capability_id", ""),
            "Resolver": row.get("taxonomy_resolution_source", ""),
            "Registry": (row.get("registry_resolution") or {}).get("status", ""),
        }
        for row in snapshot.get("requirements", []) or []
        if isinstance(row, dict)
    ]


def _render_document_comparison(analysis, label):
    st.markdown('#### ' + label)
    if not analysis or analysis.get('comparable') is not True:
        st.warning('Compatible saved analyses are unavailable; comparison withheld.')
        return
    summary = analysis['summary']
    cols = st.columns(3)
    cols[0].metric(label.split(' vs ')[0], summary['initial_score'])
    cols[1].metric('Final', summary['tailored_score'])
    cols[2].metric('Job Match Δ', summary['score_delta'])
    render_phase8_rows(st, [{
        'Requirement ID': row['requirement_id'], 'Requirement': row.get('requirement_text'),
        'Importance': row.get('importance'), 'Match transition': row.get('match_transition'),
        'Classification': row.get('classification'),
        'Contribution Δ': row.get('score_contribution_delta'),
        'Baseline evidence': _evidence_summary(row.get('initial') or {}),
        'Final evidence': _evidence_summary(row.get('tailored') or {}),
    } for row in analysis.get('requirements', [])])
    with st.expander(label + ' diagnostics'):
        if st.checkbox('Load comparison diagnostics (large)', value=False,
                       key='session_v2_comparison_diag_' + label):
            st.json(analysis)


def _render_job_match_ab(result: dict[str, Any], *, baseline_mode: str = "initial") -> None:
    if result.get('document_analysis'):
        selected_only = (result.get('starting_document_contract') or {}).get('mode') == 'selected_base_docx_only'
        st.markdown('### Step 6 — Final Résumé Analysis / Phase8')
        if selected_only:
            st.info('This Tailor Resume handoff has a frozen actual Selected Base DOCX and a fitted final DOCX. '
                    'There is no separately uploaded Initial DOCX. The document comparison below is '
                    'Selected Base vs Final, not Initial vs Final.')
        st.caption('Phase 8 evaluates the actual final document. Available Profile/Evidence alone receives no document credit.')
        final = (result.get('job_match_ab') or {}).get('tailored') or {}
        cols = st.columns(4)
        native = result.get('after_stable_analysis') or {}
        for col, label, key in zip(cols, ('Job Match', 'Required/Core', 'Preferred', 'Evidence strength'),
                ('deterministic_alignment_score', 'required_core_coverage_score', 'preferred_coverage_score', 'evidence_strength_score')):
            col.metric(label, native.get(key, 'Unavailable'))
        render_phase8_rows(st, _snapshot_rows(final))
        # Initial explainability already appears in Step 1. Reuse the existing
        # native arithmetic formatter for Final alone, without a duplicate
        # initial/before-fitting panel in document sessions.
        from tailoring.phase8_score_explainability import build_score_breakdown
        from tailoring.phase8_score_explainability_ui import _render_breakdown
        _render_breakdown('Final Résumé Analysis', build_score_breakdown(native))
        st.markdown('### Step 7 — Analysis comparison')
        st.caption('Saved native receipts use the same JD, scorer, taxonomy and registry. Changes alone do not prove their cause.')
        # Present comparisons from saved document identities, not the page
        # where the application was originally created.
        from tailoring.phase9f_explainer_stage_v2_1 import document_phase8_comparison_sections
        for label, saved_analysis in document_phase8_comparison_sections(result):
            _render_document_comparison(saved_analysis, label)
        if not isinstance(result.get('selected_base_analysis'), dict):
            st.caption('No separately verified Selected Base receipt is saved for this generation.')
        return
    analysis = result.get("job_match_ab") or {}
    lifecycle = result.get("job_match_ab_lifecycle") or {}
    selected_base_mode = baseline_mode == "selected_base"
    baseline_name = "Selected Base" if selected_base_mode else "Saved Baseline"
    if not isinstance(analysis, dict) or not analysis:
        st.warning("No persisted Initial Job Match analysis is available yet.")
        return
    if analysis.get("comparable") is not True:
        st.error(
            f"{baseline_name} and Tailored Job Match analyses are not comparable. "
             + ("The saved Selected Base and final result must share the exact JD/scorer/requirements. "
         "Reverify the selected fitted generation; do not rerun Analyze Resume." if selected_base_mode else
         "The saved before-tailoring and final receipts have incompatible identities; comparison is withheld.")
        )
        st.json({"state": lifecycle.get("state"), "blockers": analysis.get("blockers", [])})
        return

    initial = analysis.get("initial") or {}
    tailored = analysis.get("tailored") or {}
    summary = analysis.get("summary") or {}
    st.markdown("#### Job Match — Selected Base vs Tailored" if selected_base_mode else
                "#### Initial vs Tailored Analysis" if result.get('document_analysis') else
                "#### Job Match — Saved Baseline vs Tailored")
    st.caption(
        "Both views use the same JD, scorer, taxonomy, and technology registry. "
        "Requirements are joined by stable requirement ID."
    )
    initial_tab, tailored_tab, comparison_tab = st.tabs(
        ["Selected Base Job Match", "Tailored Job Match", "Selected Base vs Tailored"]
        if selected_base_mode else
        ["Initial Résumé Analysis", "Tailored Résumé Analysis", "Initial vs Tailored"]
        if result.get('document_analysis') else
        ["Saved Baseline Job Match", "Tailored Job Match", "Saved Baseline vs Tailored"]
    )
    with initial_tab:
        counts = initial.get("match_counts") or {}
        cols = st.columns(4)
        cols[0].metric("Score", initial.get("score", 0))
        cols[1].metric("Direct", counts.get("direct", 0))
        cols[2].metric("Transferable", counts.get("transferable", 0))
        cols[3].metric("Weak / none", f"{counts.get('weak', 0)} / {counts.get('none', 0)}")
        from tailoring.phase9f_explainer_clarity_v2_2 import compact_snapshot_rows
        render_phase8_rows(st, compact_snapshot_rows(initial))
        with st.expander("Detailed Selected Base/Saved Baseline requirement provenance", expanded=False):
            render_phase8_rows(st, _snapshot_rows(initial))
    with tailored_tab:
        counts = tailored.get("match_counts") or {}
        cols = st.columns(4)
        cols[0].metric("Score", tailored.get("score", 0))
        cols[1].metric("Direct", counts.get("direct", 0))
        cols[2].metric("Transferable", counts.get("transferable", 0))
        cols[3].metric("Weak / none", f"{counts.get('weak', 0)} / {counts.get('none', 0)}")
        from tailoring.phase9f_explainer_clarity_v2_2 import compact_snapshot_rows
        render_phase8_rows(st, compact_snapshot_rows(tailored))
        with st.expander("Detailed Tailored requirement provenance", expanded=False):
            render_phase8_rows(st, _snapshot_rows(tailored))
    with comparison_tab:
        score_cols = st.columns(4)
        score_cols[0].metric(baseline_name + " score", summary.get("initial_score", 0))
        score_cols[1].metric(
            "Tailored score",
            summary.get("tailored_score", 0),
            delta=summary.get("score_delta", 0),
        )
        score_cols[2].metric("Improved", summary.get("requirements_improved", 0))
        score_cols[3].metric("Lost", summary.get("requirements_lost", 0))
        st.caption(
            "Preserved: "
            f"{summary.get('requirements_preserved', 0)} · Still gaps: "
            f"{summary.get('requirements_still_gaps', 0)}"
        )
        rows = []
        for row in analysis.get("requirements", []) or []:
            if not isinstance(row, dict):
                continue
            left = row.get("initial") or {}
            right = row.get("tailored") or {}
            rows.append(
                {
                    "Requirement ID": row.get("requirement_id", ""),
                    "Requirement": row.get("requirement_text", ""),
                    "Importance": row.get("importance", ""),
                    "Classification": row.get("classification", ""),
                    "Match transition": row.get("match_transition", ""),
                    "Delta reason": next((r.get('delta_reason', '') for r in (result.get('comparison') or {}).get('improved_requirements', []) if r['requirement_id'] == row.get('requirement_id')), ''),
                    "Contribution Δ": round(
                        float(row.get("score_contribution_delta", 0.0) or 0.0), 3
                    ),
                    baseline_name + " provenance": _evidence_summary(left),
                    "Tailored provenance": _evidence_summary(right),
                    baseline_name + " taxonomy": left.get("taxonomy_status", ""),
                    "Tailored taxonomy": right.get("taxonomy_status", ""),
                    baseline_name + " resolver": left.get("taxonomy_resolution_source", ""),
                    "Tailored resolver": right.get("taxonomy_resolution_source", ""),
                    "Capability / registry": (
                        right.get("taxonomy_capability_id")
                        or (right.get("registry_resolution") or {}).get("capability_id")
                        or ""
                    ),
                }
            )
        from tailoring.phase9f_explainer_clarity_v2_2 import compact_comparison_rows
        st.caption(f"{baseline_name} is the saved pre-tailoring source; Tailored is the verified Phase 8 fitted document. Matching scores mean no measured coverage improvement, even if wording changed.")
        render_phase8_rows(st, compact_comparison_rows(rows, baseline_name))
        with st.expander("Full requirement IDs, provenance and point contributions", expanded=False):
            render_phase8_rows(st, rows)
        with st.expander("Résumé comparison taxonomy and resolver diagnostics"):
            st.json(
                [
                    {
                        "requirement_id": row.get("requirement_id", ""),
                        "initial_registry": (row.get("initial") or {}).get(
                            "registry_resolution", {}
                        ),
                        "tailored_registry": (row.get("tailored") or {}).get(
                            "registry_resolution", {}
                        ),
                        "initial_diagnostics": (row.get("initial") or {}).get(
                            "diagnostics", {}
                        ),
                        "tailored_diagnostics": (row.get("tailored") or {}).get(
                            "diagnostics", {}
                        ),
                    }
                    for row in analysis.get("requirements", []) or []
                    if isinstance(row, dict)
                ]
            )


def _phase9f_execution_uses_legacy_private_stages(
    execution: dict[str, Any] | None,
) -> bool:
    if not isinstance(execution, dict):
        return False
    outputs = execution.get("stage_outputs") or {}
    if any(
        key in outputs
        for key in (
            "generation_settings",
            "projects",
            "skills",
            "fitting",
            "fitting_attempts",
        )
    ):
        return True
    if outputs.get("normal_lifecycle_adapter_version") == (
        "phase9f-f-normal-generation-lifecycle-v1"
    ):
        return False
    return bool(
        str(execution.get("generation_id") or "").strip()
    )




def _render_final_improvement_verdict_v1(result: dict[str, Any], *, baseline_mode: str) -> None:
    """Read-only verdict from the saved Phase 8 native A/B receipts."""
    from tailoring.phase8_final_improvement_verdict_v1 import build_final_improvement_verdict

    audit = build_final_improvement_verdict(result, baseline_mode=baseline_mode)
    base_only = (result.get("starting_document_contract") or {}).get("mode") == "selected_base_docx_only"
    st.markdown("### Final check — Tailored vs Selected Base" if base_only
                else "### Final check — Tailored vs Initial and Selected Base")
    st.caption(
        "Uses saved Phase 8 Job Match evidence for each baseline under the same JD "
        "and scorer. It does not rescore, approve, or modify the final DOCX."
    )
    status = audit.get("status")
    if status == "improved_vs_both" and base_only:
        st.success("Verified improvement against the frozen Selected Base DOCX. The final document scored higher "
                   "and preserved Required/Core strength.")
    elif status == "improved_vs_both":
        st.success("Verified improvement against both Initial and Selected Base: higher Job Match score "
                   "for the actual final document, with no Required/Core evidence regression.")
    elif status == "required_core_regression":
        st.warning("Required/Core evidence regressed in at least one baseline comparison. "
                   "The final résumé cannot be certified as improved.")
    elif status == "worse_against_a_baseline":
        st.warning("The final résumé scores lower than the verified Selected Base." if base_only
                   else "The final résumé scores lower than at least one verified baseline.")
    elif status == "unchanged_vs_both":
        st.info("Final and Selected Base have equal Job Match scores." if base_only
                else "Final and both baselines have equal Job Match scores.")
    elif status == "not_improved_vs_both":
        st.info("Review the verified Selected Base score difference below." if base_only
                else "Final did not score higher than both baselines. Review the separate deltas below.")
    elif status == "partial_comparison_only":
        st.info("Partial comparison only. An actual-document or second baseline receipt is missing; "
                "overall résumé improvement is not certified.")
    else:
        st.warning("Final improvement cannot be verified safely from the saved evidence receipts.")

    rows = []
    for name in (("Selected Base",) if base_only else ("Initial", "Selected Base")):
        comp = (audit.get("comparisons") or {}).get(name) or {}
        rows.append({
            "Baseline": name,
            "Verified": bool(comp.get("verified")),
            "Baseline Job Match": comp.get("before_score") if comp.get("verified") else None,
            "Final Job Match": comp.get("after_score") if comp.get("verified") else None,
            "Score delta": comp.get("delta") if comp.get("verified") else None,
            "Required/Core regressions": len(comp.get("hard_regressions") or []),
            "Assessment": comp.get("assessment") or "unavailable",
            "Basis": ("Frozen Selected Base DOCX" if base_only and comp.get("verified") else
                      comp.get("alias_of") or comp.get("reason") or "Independent saved receipt"),
        })
    render_phase8_rows(st, rows)
    with st.expander("Final comparison evidence and limitations", expanded=False):
        st.caption("Only document-grounded final DOCX comparisons can earn the full improved verdict. "
                   "Legacy reconstructed-profile comparisons remain diagnostic.")
        for reason in audit.get("reasons") or []:
            st.write("- " + str(reason))
        for name, comp in (audit.get("comparisons") or {}).items():
            regressions = comp.get("hard_regressions") or []
            if regressions:
                st.write("**" + str(name) + ": Required/Core evidence regressions**")
                render_phase8_rows(st, regressions)


def _phase8_score_banner(result: dict[str, Any]) -> tuple[str, str]:
    """Describe displayed native scores, without changing the saved Phase 8 verdict.

    Historical receipts can say 'maintained' when the native score declined.
    A banner must not imply approval or infer hard coverage from a total score.
    """
    import math

    verdict = str(result.get("verdict") or "review_required")
    message = str(result.get("verdict_message") or "").strip()
    comparison = result.get("comparison") or {}
    if verdict == "invalid_canonical_mismatch":
        return "error", message or "Canonical requirement identity is invalid."
    if not result.get("comparison_valid", True) or not isinstance(comparison, dict):
        return "warning", "Native Job Match comparison is unavailable or incompatible; approval is not inferred."
    if comparison.get("canonical_requirement_ids_stable") is False:
        return "warning", "Canonical requirements changed; score comparisons cannot be trusted."
    try:
        values = [comparison[key] for key in ("before_score", "after_score")]
        if any(isinstance(value, bool) for value in values):
            raise ValueError("boolean score")
        before, after = (float(value) for value in values)
        if not all(math.isfinite(value) and value.is_integer() for value in (before, after)):
            raise ValueError("non-integer score")
        before, after = int(before), int(after)
        delta = after - before
        if "score_delta" in comparison:
            saved_delta = comparison["score_delta"]
            if isinstance(saved_delta, bool) or float(saved_delta) != delta:
                raise ValueError("inconsistent saved delta")
    except (KeyError, ValueError, TypeError, OverflowError):
        return "warning", "Native Job Match values are missing or inconsistent; verify the saved receipt."

    hard_regressed = bool(comparison.get("important_regressions")) or verdict == "regression_detected"
    if hard_regressed:
        return "warning", (
            "Required/Core evidence regressed. Review the individual requirements before approval."
        )
    if delta < 0:
        hard_note = (
            "No individual Required/Core regression was recorded. "
            if comparison.get("important_regressions") == [] else
            "Required/Core evidence needs separate verification. "
        )
        return "warning", (
            f"Job Match decreased from {before} to {after} ({delta:+d} points). "
            + hard_note + "This does not authorize approval."
        )
    if verdict == "improved" and delta > 0:
        return "success", message or f"Job Match improved from {before} to {after}."
    if verdict == "maintained" and delta == 0:
        return "info", message or f"Job Match remained {after}."
    if verdict in {"improved", "maintained"}:
        return "warning", (
            f"Job Match changed from {before} to {after} ({delta:+d} points), "
            "but the saved verdict disagrees. Review before approval."
        )
    return "warning", message or "Phase 8 evidence requires review before approval."

def _render_result(result: dict[str, Any]) -> None:
    from tailoring.phase9f_explainer_stage_v2_1 import phase8_baseline_mode
    baseline_mode = phase8_baseline_mode(result)
    comparison = result.get("comparison", {}) or {}
    lineage = result.get("claim_lineage", {}) or {}

    banner_kind, banner_text = _phase8_score_banner(result)
    getattr(st, banner_kind)(banner_text)

    comparison_valid = bool(result.get("comparison_valid", True))
    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric(
        ("Selected Base Job Match" if (result.get('starting_document_contract') or {}).get('mode') == 'selected_base_docx_only' else "Initial Job Match") if result.get('document_analysis') else
        "Selected Base Job Match" if baseline_mode == "selected_base" else "Before score",
        comparison.get("before_score", 0),
    )
    metric2.metric(
        "Final Job Match" if result.get('document_analysis') else "After score",
        comparison.get("after_score", 0),
        delta=(
            comparison.get("score_delta", 0)
            if comparison_valid
            else None
        ),
    )
    metric3.metric(
        "Required/Core Δ",
        (
            comparison.get("required_core_coverage_delta", 0)
            if comparison_valid
            else "Invalid"
        ),
    )
    metric4.metric(
        "Claim reviews",
        lineage.get("claim_review_required_count", 0),
    )

    _render_job_match_ab(result, baseline_mode=baseline_mode)
    # The Saved Selected Base comparison is already in the three Phase 8 tabs.
    # Avoid showing a second, duplicate wide comparison directly underneath.
    if not result.get('document_analysis'):
        render_phase8_score_explainability(
            result,
            baseline_label=("Selected Base before tailoring" if baseline_mode == "selected_base"
                            else "Baseline before fitting"),
        )

    reconciliation = (
        result.get("requirement_reconciliation", {}) or {}
    )
    reconciled_rows = (
        reconciliation.get("reconciled_requirements", []) or []
    )
    unresolved_rows = (
        reconciliation.get("unresolved_regressions", []) or []
    )
    newly_supported_rows = (
        reconciliation.get("newly_supported_requirements", []) or []
    )
    if reconciled_rows:
        st.warning(
            f"Phase 8 reconciled {len(reconciled_rows)} requirement match(es) using saved generation mappings. "
            "This is not independent proof that the exact JD activity was performed. "
            "Review each evidence snippet, especially deployment/configuration claims, before relying on the reconciled score."
        )
        with st.expander(
            "Final evidence reconciliation",
            expanded=False,
        ):
            render_phase8_rows(st, reconciled_rows, label='Final evidence reconciliation')
    if newly_supported_rows:
        st.info(
            "Phase 8 confirmed "
            f"{len(newly_supported_rows)} additional requirement match(es) "
            "from claim-lineage-verified final Projects and Skills."
        )
        with st.expander(
            "New final evidence matches",
            expanded=False,
        ):
            render_phase8_rows(st, newly_supported_rows, label='New final evidence matches')
    if unresolved_rows:
        st.warning(
            f"{len(unresolved_rows)} regression(s) could not be reconciled "
            "and remain genuine review items."
        )

    if not comparison_valid:
        added = comparison.get("added_requirements", []) or []
        removed = comparison.get("removed_requirements", []) or []
        st.error(
            "The canonical JD requirement set changed, so the displayed "
            "before/after scores are diagnostic only and must not be used for "
            "blueprint approval."
        )
        with st.expander(
            "Canonical requirement mismatch",
            expanded=True,
        ):
            st.write(
                f"Added requirement IDs: {len(added)} · "
                f"Removed requirement IDs: {len(removed)}"
            )
            if added:
                st.write("**Added after reconstruction**")
                render_phase8_rows(st, added)
            if removed:
                st.write("**Missing after reconstruction**")
                render_phase8_rows(st, removed)

    if result.get("blueprint_ready"):
        st.success(
            "Blueprint readiness: Passed. This approved one-page version "
            "maintained or improved alignment without detected evidence loss."
        )
    elif result.get("approval_ready"):
        st.success(
            "Phase 8 pre-approval verification: Passed. This exact fitted "
            "version is ready for approval."
        )
        st.caption(
            "Blueprint readiness will become complete after this exact "
            "verified version is approved."
        )
    else:
        st.caption(
            "Phase 8 approval readiness has not passed every verification gate."
        )
        st.json(result.get("approval_readiness_reasons", {}))

    improved = comparison.get("improved_requirements", []) or []
    regressed = comparison.get("regressed_requirements", []) or []
    if improved:
        with st.expander(
            f"Improved requirements ({len(improved)})",
            expanded=False,
        ):
            render_phase8_rows(st, improved)
    if regressed:
        with st.expander(
            f"Regressed requirements ({len(regressed)})",
            expanded=True,
        ):
            render_phase8_rows(st, regressed)

    bullet_risks = (
        lineage.get("project_bullet_review_risks", []) or []
    )
    skill_risks = lineage.get("skill_review_risks", []) or []
    if bullet_risks or skill_risks:
        with st.expander(
            "Evidence-lineage review",
            expanded=True,
        ):
            if bullet_risks:
                st.write("**Project bullets needing review**")
                render_phase8_rows(st, bullet_risks, label='Project bullets needing review')
            if skill_risks:
                st.write("**Skills needing review**")
                render_phase8_rows(st, skill_risks, label='Skills needing review')

    # V3.6.1: transparent read-only Initial AND Selected Base approval floor.
    # The authoritative approval function also recomputes actual DOCX bytes.
    from tailoring.phase9f_v361_approval_floor import assess_phase9f_approval_floor
    doc = result.get('document_analysis') or {}
    floor_preview = assess_phase9f_approval_floor(
        result, generation_id=str(result.get('generation_id') or ''),
        docx_sha256=str(doc.get('final_document_sha256') or ''),
    )
    st.markdown('#### Base no-regression approval floor')
    if floor_preview.get('ready'):
        if len(floor_preview['comparisons']) == 1:
            baseline_name = next(iter(floor_preview['comparisons']))
            st.success(f'The existing fitted résumé meets the {baseline_name} score and preserves Required/Core strength.')
        else:
            st.success('The existing fitted résumé meets both starting-résumé scores and preserves Required/Core strength.')
        render_phase8_rows(st, [{
            'Baseline': name,
            'Before': comparison['before'],
            'Existing fitted résumé': comparison['after'],
            'Job Match Δ': comparison['delta'],
            'Required/Core losses': len(comparison.get('hard_regressions') or []),
        } for name, comparison in floor_preview['comparisons'].items()])
    else:
        hold = str(floor_preview.get('reason') or 'Unknown verification hold')
        st.warning('No-regression NOT certified: '+hold)
        if hold == 'Missing Phase 8 actual fitted DOCX analysis receipt':
            st.caption('Next check: open/download the Phase 8 Verification JSON and look for '
                       '`document_analysis.final_document_sha256`. This saved result does not '
                       'establish an actual-document baseline; inspecting selection receipts cannot create one. '
                       'A new authorized Phase 8 verification may require valid frozen starting documents.')
        elif 'hash' in hold.lower() or 'digest' in hold.lower():
            st.caption('Next check: compare the saved fitted generation ID, its SHA-256, and the Phase 8 '
                       'receipt. Do not overwrite the original DOCX or bypass the approval hold. '
                       'This UI checks receipt consistency; the approval action separately hashes the actual file.')
        elif 'Initial:' in hold or 'Selected Base:' in hold or 'Selected Base identity' in hold:
            st.caption('Next check: inspect the native Initial and Selected Base comparison receipts in '
                       'Phase 8. A score copied from a project-only proxy cannot certify the missing baseline.')
        else:
            st.caption('Next check: inspect the Phase 8 Verification JSON and verification-manager status. '
                       'The application cannot infer missing authority from a high proxy score.')
    st.caption('Receipt preview only. For current Phase 9F normal generations, approval independently rechecks the saved fitted DOCX bytes and current Phase 8 verification.')

    _render_final_improvement_verdict_v1(result, baseline_mode=baseline_mode)

    with st.expander("Phase 8 technical details", expanded=False):
        if st.checkbox("Load Phase 8 diagnostic JSON (large)", value=False,
                       key="session_v2_phase8_full_diagnostics"):
            st.json(result)
        else:
            st.caption("Load full diagnostics only when needed.")

    st.download_button(
        "Download Phase 8 Verification JSON",
        data=json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8"),
        file_name=(
            "phase8_verification_"
            f"{str(result.get('generation_id') or '')[:8]}.json"
        ),
        mime="application/json",
        width="stretch",
    )


def render_phase8_verification(
    *,
    application_id: int,
    baseline_report: dict[str, Any],
    raw_jd_text: str,
    phase9f_execution: dict[str, Any] | None = None,
    required_phase9e_binding: dict[str, Any] | None = None,
    preferred_generation_id: str = "",
) -> None:
    st.divider()
    st.subheader("Phase 8 — Fitted Résumé Verification")
    st.caption(
        "Automatically verifies the exact fitted résumé against the "
        "baseline and explains the deterministic score. It makes no model "
        "or embedding calls and never auto-approves."
    )

    versions = list_tailoring_generations(application_id)
    eligible = [
        state
        for state in versions
        if isinstance(state.get("fit_result"), dict)
        and is_phase9f_normal_generation_approvable(state)
        and (
            not required_phase9e_binding
            or generation_matches_phase9e_binding(
                state,
                required_phase9e_binding,
            )
        )
    ]
    phase9f_generation_id = str(
        (phase9f_execution or {}).get("generation_id") or ""
    ).strip()
    phase9f_legacy_private = _phase9f_execution_uses_legacy_private_stages(
        phase9f_execution
    )
    # Normal F lifecycle generations are verified while still Drafts.
    # Historical private-stage F rows keep their old approval-first behavior
    # below so persisted legacy sessions remain recoverable.
    if phase9f_generation_id and phase9f_legacy_private:
        eligible = [
            state
            for state in eligible
            if str(state.get("generation_id") or "") == phase9f_generation_id
        ]
    if not eligible:
        st.info(
            "Generate and fit a tailored résumé DOCX before running Phase 8."
        )
        return

    control = get_application_generation_control(application_id)
    approved = control.get("approved_generation")
    approved_id = (
        str(approved.get("generation_id") or "")
        if isinstance(approved, dict)
        else ""
    )
    preferred_id = str(preferred_generation_id or "").strip()
    default_generation_id = preferred_id or approved_id
    default_index = next(
        (
            index
            for index, state in enumerate(eligible)
            if str(state.get("generation_id") or "")
            == default_generation_id
        ),
        0,
    )
    by_id = {
        str(state["generation_id"]): state
        for state in eligible
    }
    selected_id = st.selectbox(
        "Fitted version",
        options=list(by_id),
        index=default_index,
        format_func=lambda value: _label(by_id[value]),
        key=f"phase8_generation_{application_id}",
    )
    selected = by_id[selected_id]

    status_col, pages_col, cost_col = st.columns(3)
    status_col.metric(
        "Status",
        str(selected.get("status") or "draft").title(),
    )
    pages_col.metric(
        "Pages",
        (selected.get("fit_result") or {}).get(
            "page_count",
            "—",
        ),
    )
    cost_col.metric(
        "Verification cost",
        "$0.000000",
    )

    def _execute_selected_verification() -> dict[str, Any]:
        if phase9f_generation_id and phase9f_legacy_private:
            from database.phase9f_tailoring_execution_manager import (
                run_or_reuse_phase9f_tailoring_phase8,
            )
            phase9f_result = run_or_reuse_phase9f_tailoring_phase8(
                application_id=application_id
            )
            return {"cache_status": phase9f_result.get("cache_status")}

        if (phase9f_execution or
                (selected.get('generation_settings') or {}).get('phase9f_f_normal_lifecycle')):
            from database.phase9f_tailoring_execution_manager import (
                run_or_reuse_phase9f_normal_generation_phase8,
            )
            phase9f_result = run_or_reuse_phase9f_normal_generation_phase8(
                application_id=application_id,
                generation_id=selected_id,
            )
            return {"cache_status": phase9f_result.get("cache_status")}

        result = build_phase8_verification(
            baseline_report=baseline_report,
            generation_state=selected,
            raw_jd_text=raw_jd_text,
        )
        return save_tailoring_verification(
            application_id=application_id,
            generation_id=selected_id,
            result=result,
        )

    def _cache_message(saved: dict[str, Any], *, automatic: bool) -> str:
        cache_status = str(saved.get("cache_status") or "")
        prefix = "Automatic Phase 8 verification" if automatic else "Phase 8 verification"
        if cache_status == "hit_refreshed":
            return f"{prefix}: reused the saved analysis and refreshed lifecycle readiness."
        if cache_status == "hit":
            return f"{prefix}: reused the current exact-snapshot verification."
        return f"{prefix}: saved a new zero-cost verification for the exact fitted snapshot."

    latest = get_latest_tailoring_verification(application_id, selected_id)
    if not phase8_verification_is_current(latest, selected):
        refresh_reason = phase8_verification_refresh_reason(latest, selected)
        st.caption(
            "Automatically verifying the exact fitted résumé because the "
            f"current Phase 8 status is: {refresh_reason}."
        )
        try:
            with st.spinner(
                "Automatically verifying the exact fitted résumé deterministically..."
            ):
                auto_saved = _execute_selected_verification()
            latest = get_latest_tailoring_verification(application_id, selected_id)
            if phase8_verification_is_current(latest, selected):
                st.success(_cache_message(auto_saved, automatic=True))
            else:
                latest = None
                st.warning(
                    "Automatic Phase 8 verification completed, but the current exact "
                    "fitted snapshot could not be confirmed. The stale result is hidden."
                )
        except ValueError as exc:
            latest = None
            st.warning(f"Automatic Phase 8 verification could not complete: {exc}")
        except Exception as exc:
            latest = None
            st.error(f"Automatic Phase 8 verification failed: {exc}")

    if phase8_verification_is_current(latest, selected):
        st.caption(
            "✓ Phase 8 is current for this exact fitted snapshot. Approval remains "
            "a separate explicit user action."
        )

    if st.button(
        "Re-run Phase 8 verification",
        width="stretch",
        key=f"phase8_verify_{application_id}_{selected_id}",
        help=(
            "Diagnostic/recovery action. Normal fitted snapshots are verified automatically."
        ),
    ):
        try:
            with st.spinner("Re-running deterministic Phase 8 verification..."):
                manual_saved = _execute_selected_verification()
            st.session_state[f"phase8_flash_{application_id}"] = _cache_message(
                manual_saved,
                automatic=False,
            )
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(f"Phase 8 verification failed: {exc}")

    flash = st.session_state.pop(f"phase8_flash_{application_id}", "")
    if flash:
        st.success(flash)

    if isinstance(latest, dict):
        refreshed_latest = (
            latest
            if phase9f_generation_id
            else refresh_phase8_readiness(latest, selected)
        )
        mutable_fields = (
            "generation_status",
            "fit_one_page",
            "page_count",
            "blueprint_ready",
            "blueprint_readiness_reasons",
        )
        readiness_changed = any(
            latest.get(field) != refreshed_latest.get(field)
            for field in mutable_fields
        )
        if readiness_changed and not phase9f_generation_id:
            refreshed_latest = save_tailoring_verification(
                application_id=application_id,
                generation_id=selected_id,
                result=refreshed_latest,
            )
            refreshed_latest.pop("cache_status", None)
        _render_result(refreshed_latest)
    else:
        st.caption(
            "No saved verification exists for this fitted version yet."
        )

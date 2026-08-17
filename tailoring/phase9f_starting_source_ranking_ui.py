"""Read-only Streamlit UI for Phase 9F-B starting-source ranking."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import streamlit as st

from database.global_blueprint_manager import (
    list_active_global_blueprints_read_only,
)
from database.db_manager import get_application_by_id
from database.global_master_resume_manager import (
    get_current_global_master_resume,
    get_global_master_resume_artifact,
)
from resume_builder.docx_projects_skills_replacer import pdf_to_preview_html
from tailoring.phase9f_starting_source_artifacts import (
    Phase9FBArtifactError,
    resolve_starting_source_artifacts,
)
from tailoring.phase9f_starting_source_ranking import (
    canonical_json,
    prepare_ranking_context,
    rank_prepared_context,
)
from tailoring.phase9f_starting_source_provenance import (
    Phase9FBProvenanceError,
    build_blueprint_provenance_debug_bundle,
    compact_artifact_resolution,
    load_blueprint_provenance_read_only,
)
from tailoring.phase9f_starting_source_transparency import (
    build_ranking_transparency,
    build_requirement_comparison_csv,
)
from tailoring.phase9f_tailoring_intensity_ui import (
    render_phase9f_tailoring_intensity,
)
from tailoring.phase9f_application_confirmation_ui import (
    render_phase9f_application_confirmation,
)


RANKING_RESULT_STATE_KEY = "phase9f_b_ranking_result"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _load_immutable_source_scope() -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
    list[dict[str, Any]],
]:
    """Read the current Base Resume and active Blueprints without writes."""
    current_base = get_current_global_master_resume()
    artifact = None
    if current_base is not None:
        artifact = get_global_master_resume_artifact(
            str(current_base.get("master_version_id") or ""),
            "original",
        )
    blueprints = list_active_global_blueprints_read_only()
    return current_base, artifact, blueprints


def _result_is_current(
    result: Any,
    ranking_input_fingerprint: str,
) -> bool:
    return bool(
        isinstance(result, dict)
        and _clean(result.get("ranking_input_fingerprint"))
        == _clean(ranking_input_fingerprint)
    )


def _render_integrity_diagnostics(context: dict[str, Any]) -> None:
    st.error(
        "Starting-source ranking failed closed because an automatically "
        "eligible immutable source did not pass integrity validation. No "
        "source was recommended."
    )
    for issue in context.get("integrity_issues", []) or []:
        source = " / ".join(
            value
            for value in (
                _clean(issue.get("source_type")),
                _clean(issue.get("source_id")),
            )
            if value
        )
        prefix = f"{source}: " if source else ""
        st.warning(prefix + _clean(issue.get("message")))
    with st.expander("Phase 9F-B integrity diagnostics", expanded=False):
        st.json(
            {
                "status": context.get("status"),
                "ranking_input_fingerprint": context.get(
                    "ranking_input_fingerprint"
                ),
                "integrity_issues": context.get("integrity_issues") or [],
                "zero_cost": {
                    "model_call_count": 0,
                    "embedding_call_count": 0,
                    "chroma_read_count": 0,
                    "chroma_write_count": 0,
                    "persistence_write_count": 0,
                },
            }
        )


def _render_pdf_bytes(content: bytes) -> None:
    with tempfile.TemporaryDirectory(prefix="phase9f_b_preview_") as name:
        path = Path(name) / "starting_source_preview.pdf"
        path.write_bytes(content)
        st.markdown(
            pdf_to_preview_html(
                path,
                max_width=820,
                max_pages=5,
                zoom=1.35,
                include_download=False,
            ),
            unsafe_allow_html=True,
        )


def _render_winner_transparency(transparency: dict[str, Any]) -> None:
    explanation = transparency.get("winner_explanation") or {}
    if not explanation:
        return
    with st.container(border=True):
        st.markdown("#### Why this source ranked #1")
        st.write(_clean(explanation.get("headline")))
        summary_lines = explanation.get("summary_lines", []) or []
        if summary_lines:
            st.markdown(
                "\n".join(f"- {_clean(line)}" for line in summary_lines)
            )
        failed_checks = explanation.get("failed_near_tie_checks", []) or []
        if failed_checks:
            details = "; ".join(
                f"{_clean(row.get('metric'))} difference "
                f"{int(row.get('difference') or 0)} exceeds "
                f"{int(row.get('tolerance') or 0)}"
                for row in failed_checks
            )
            st.caption(
                "The same-family prior was not applied because: " + details + "."
            )
        if explanation.get("role_family_prior_applied"):
            st.caption(
                "The role-family prior selected the winner only after every "
                "calibrated near-tie check passed. It did not alter a score."
            )


def _render_pairwise_transparency(transparency: dict[str, Any]) -> None:
    pairwise = transparency.get("pairwise_comparison") or {}
    if not pairwise:
        return
    with st.expander("Why #1 beat #2", expanded=False):
        st.caption(
            "The comparator follows the displayed priority order. This is not "
            "a hidden weighted sum."
        )
        metric_rows = []
        for row in pairwise.get("metric_comparisons", []) or []:
            winner_value = str(int(row.get("winner_value") or 0))
            runner_value = str(int(row.get("runner_up_value") or 0))
            if row.get("metric_key") == "deal_breaker_free":
                winner_value = (
                    "Yes" if int(row.get("winner_value") or 0) else "No"
                )
                runner_value = (
                    "Yes" if int(row.get("runner_up_value") or 0) else "No"
                )
            favored = _clean(row.get("favored")).replace("_", " ").title()
            metric_rows.append(
                {
                    "Metric": _clean(row.get("metric")),
                    _clean(pairwise.get("winner_name")): winner_value,
                    _clean(pairwise.get("runner_up_name")): runner_value,
                    "Favored": favored,
                }
            )
        st.dataframe(metric_rows, width="stretch", hide_index=True)
        st.write(
            "**Role-family relationship:** "
            f"#1 {_clean(pairwise.get('winner_role_family_relationship'))}; "
            f"#2 {_clean(pairwise.get('runner_up_role_family_relationship'))}."
        )
        st.write(
            "**Same-family prior eligibility:** "
            f"#1 {'eligible' if pairwise.get('winner_role_family_prior_eligible') else 'not eligible'}; "
            f"#2 {'eligible' if pairwise.get('runner_up_role_family_prior_eligible') else 'not eligible'}."
        )
        st.write(
            f"**Near-tie outcome:** {_clean(pairwise.get('near_tie_status')).replace('_', ' ')}"
        )
        st.caption(_clean(pairwise.get("role_family_prior_reason")))
        checks = pairwise.get("near_tie_checks", []) or []
        if checks:
            st.dataframe(
                [
                    {
                        "Near-tie check": _clean(row.get("metric")),
                        "Difference": int(row.get("difference") or 0),
                        "Tolerance": int(row.get("tolerance") or 0),
                        "Within tolerance": bool(row.get("within_tolerance")),
                    }
                    for row in checks
                ],
                width="stretch",
                hide_index=True,
            )
        st.info(_clean(pairwise.get("role_family_statement")))


def _render_requirement_transparency(transparency: dict[str, Any]) -> None:
    with st.expander("Compare requirement evidence", expanded=False):
        st.caption(
            "Each row is one canonical JD requirement evaluated against one "
            "immutable source. Supporting text is the scorer-selected, clipped "
            "résumé evidence—not the complete résumé."
        )
        rows = transparency.get("requirement_comparison", []) or []
        if not rows:
            st.info(
                "This cached comparison predates the transparency fields. "
                "Use Recompute comparison to populate evidence without changing "
                "the semantic scope or ranking fingerprint."
            )
            return
        st.dataframe(
            [
                {
                    "Requirement ID": _clean(row.get("requirement_id")),
                    "Requirement": _clean(row.get("requirement_text")),
                    "Importance": _clean(row.get("importance")).title(),
                    "Source": (
                        f"#{int(row.get('source_rank') or 0)} "
                        f"{_clean(row.get('source_name'))}"
                    ),
                    "Match": _clean(row.get("match_label")).title(),
                    "Evidence strength": int(
                        row.get("evidence_strength") or 0
                    ),
                    "Evidence section": _clean(row.get("evidence_section")),
                    "Supporting evidence": _clean(
                        row.get("supporting_evidence")
                    ),
                    "Matched keyword": _clean(row.get("matched_keyword")),
                    "Deterministic reason": _clean(
                        row.get("deterministic_reason")
                    ),
                    "Taxonomy cap": _clean(row.get("taxonomy_cap_status")),
                }
                for row in rows
            ],
            width="stretch",
            hide_index=True,
            height=520,
        )
        st.download_button(
            "Download requirement comparison CSV",
            data=build_requirement_comparison_csv(transparency),
            file_name=(
                "phase9f_b_requirement_comparison_"
                f"{_clean(transparency.get('ranking_fingerprint'))[:12]}.csv"
            ),
            mime="text/csv",
            key="phase9f_b_download_requirement_comparison_csv",
        )
        st.caption(
            "Keywords and skills help locate evidence. Repeating a keyword does "
            "not add points; the existing stable scorer assigns one canonical "
            "match label and evidence strength per requirement."
        )


def _render_ranking_policy(transparency: dict[str, Any]) -> None:
    with st.expander("How ranking works", expanded=False):
        st.caption(
            "This is a deterministic priority comparator, not a weighted score."
        )
        priority = transparency.get("priority_order", []) or []
        st.markdown(
            "\n".join(
                f"{int(row.get('position') or 0)}. {_clean(row.get('label'))}"
                for row in priority
            )
        )
        tolerances = transparency.get("near_tie_tolerances") or {}
        labels = {
            "deal_breaker_gap_count": "Deal-breaker gap difference",
            "required_core_coverage_points": "Required/Core",
            "overall_alignment_points": "Current JD alignment",
            "evidence_strength_points": "Evidence strength",
            "important_gap_count": "Important-gap difference",
            "preferred_coverage_points": "Preferred coverage",
        }
        st.write("**Calibrated near-tie tolerances**")
        st.dataframe(
            [
                {
                    "Metric": labels.get(key, key),
                    "Maximum difference": int(value or 0),
                }
                for key, value in tolerances.items()
            ],
            width="stretch",
            hide_index=True,
        )
        st.info(_clean(transparency.get("role_family_statement")))


def _render_candidate_inspection(
    *,
    result: dict[str, Any],
    context: dict[str, Any],
    current_base: dict[str, Any] | None,
    current_base_artifact: dict[str, Any] | None,
    blueprints: list[dict[str, Any]],
) -> None:
    candidates = result.get("ranked_candidates", []) or []
    normalized = {
        _clean(row.get("normalized_source_fingerprint")): row
        for row in context.get("_normalized_sources", []) or []
        if isinstance(row, dict)
    }
    by_fingerprint = {
        _clean(row.get("normalized_source_fingerprint")): row
        for row in candidates
        if isinstance(row, dict)
    }
    options = [
        _clean(row.get("normalized_source_fingerprint"))
        for row in candidates
        if _clean(row.get("normalized_source_fingerprint")) in normalized
    ]
    if not options:
        return

    with st.expander("Inspect ranked resume sources", expanded=False):
        state_key = "phase9f_b_inspect_source"
        if st.session_state.get(state_key) not in options:
            st.session_state[state_key] = options[0]
        selected_fingerprint = st.selectbox(
            "Ranked resume source",
            options,
            key=state_key,
            format_func=lambda value: (
                f"#{int(by_fingerprint[value].get('rank') or 0)} - "
                f"{_clean(by_fingerprint[value].get('source_display_name'))}"
            ),
        )
        selected = by_fingerprint[selected_fingerprint]
        st.caption(
            "Read-only inspection of the immutable source used by this "
            "comparison. Preview, download, provenance inspection, and "
            "navigation do not alter the ranking."
        )

        selected_blueprint = None
        blueprint_provenance = None
        provenance_error = ""
        if selected.get("source_type") == "global_blueprint":
            matches = [
                row
                for row in blueprints
                if _clean(row.get("blueprint_id"))
                == _clean(selected.get("source_id"))
                and _clean(row.get("blueprint_fingerprint"))
                == _clean(selected.get("source_fingerprint"))
            ]
            if len(matches) == 1:
                selected_blueprint = matches[0]
                try:
                    blueprint_provenance = (
                        load_blueprint_provenance_read_only(
                            selected_blueprint
                        )
                    )
                except (Phase9FBProvenanceError, ValueError) as exc:
                    provenance_error = str(exc)
            else:
                provenance_error = (
                    "The selected Blueprint identity is missing or ambiguous."
                )

        base_preview = None
        if selected.get("source_type") == "base_resume" and current_base:
            base_preview = get_global_master_resume_artifact(
                str(current_base.get("master_version_id") or ""),
                "preview_pdf",
            )
        resolved = None
        artifact_error = ""
        try:
            resolved = resolve_starting_source_artifacts(
                ranked_candidate=selected,
                normalized_source=normalized[selected_fingerprint],
                current_base_artifact=current_base_artifact,
                current_base_preview_artifact=base_preview,
                global_blueprints=blueprints,
                blueprint_provenance=blueprint_provenance,
            )
        except (OSError, Phase9FBArtifactError, ValueError) as exc:
            artifact_error = str(exc)
            st.info(f"This immutable source artifact is unavailable: {exc}")

        preview = (resolved or {}).get("preview_pdf")
        if isinstance(preview, dict):
            st.caption(_clean(preview.get("provenance_label")))
            try:
                _render_pdf_bytes(preview["artifact_bytes"])
            except (OSError, RuntimeError, ValueError) as exc:
                st.info(
                    "The rasterized PDF preview is unavailable: "
                    f"{exc}"
                )
        else:
            st.info(
                "No existing PDF artifact is available for rasterized preview."
            )

        with st.container(horizontal=True):
            for artifact in (resolved or {}).get("artifacts", []) or []:
                artifact_type = _clean(artifact.get("artifact_type")).upper()
                st.download_button(
                    f"Download {artifact_type}",
                    data=artifact["artifact_bytes"],
                    file_name=_clean(artifact.get("filename")),
                    mime=_clean(artifact.get("media_type")),
                    key=(
                        "phase9f_b_download_source_"
                        f"{selected_fingerprint[:12]}_"
                        f"{_clean(artifact.get('artifact_kind'))}_"
                        f"{artifact_type.lower()}"
                    ),
                    )

        if selected_blueprint is None:
            st.divider()
            st.write("**Current comparison and lifecycle provenance**")
            score_columns = st.columns(2)
            score_columns[0].metric(
                "Current JD alignment",
                int(selected.get("deterministic_alignment_score") or 0),
            )
            score_columns[1].metric(
                "Historical Blueprint/source score",
                "Not applicable",
            )
            source_provenance = next(
                (
                    row
                    for row in result.get("source_provenance", []) or []
                    if _clean(row.get("source_type")) == "base_resume"
                    and _clean(row.get("source_id"))
                    == _clean(selected.get("source_id"))
                ),
                {},
            )
            st.caption(
                "The Base Resume has immutable master-resume provenance and an "
                "authoritative artifact hash. Historical Phase 8/9B/9C/9D "
                "Blueprint provenance is not applicable and was not fabricated. "
                f"Version {int(selected.get('source_version') or 0)} · created "
                f"{_clean(source_provenance.get('created_at')) or 'date unavailable'}."
            )
            return

        st.divider()
        st.write("**Global Blueprint provenance**")
        if blueprint_provenance is None:
            st.warning(
                "The Blueprint provenance chain is unavailable: "
                f"{provenance_error or 'unknown read-only resolution error'}"
            )
            return

        identity = blueprint_provenance.get("blueprint_identity") or {}
        family = blueprint_provenance.get("blueprint_role_family") or {}
        source_application = (
            blueprint_provenance.get("source_application") or {}
        )
        phase8 = blueprint_provenance.get("phase8_verification") or {}
        phase9b = blueprint_provenance.get("phase9b_candidate") or {}
        phase9c = blueprint_provenance.get("phase9c_evaluation") or {}
        st.write(
            f"**{_clean(identity.get('display_name')) or 'Global Blueprint'}** "
            f"· version {int(identity.get('version_number') or 0)} · "
            f"{_clean(identity.get('status'))}"
        )
        st.caption(
            f"{_clean(family.get('role_family_label'))} · Blueprint "
            f"`{_clean(identity.get('blueprint_id'))}` · fingerprint "
            f"`{_clean(identity.get('blueprint_fingerprint'))}`"
        )

        score_columns = st.columns(2)
        score_columns[0].metric(
            "Current JD alignment",
            int(selected.get("deterministic_alignment_score") or 0),
        )
        historical_score = (
            (phase9b.get("score_summary") or {}).get(
                "approved_tailored_score"
            )
        )
        score_columns[1].metric(
            "Historical Blueprint/source score",
            historical_score if historical_score is not None else "—",
        )
        st.caption(
            "Current JD alignment is the fresh deterministic Phase 9F-B "
            "score against the currently analysed JD and is used for ranking. "
            "The historical Blueprint/source score is provenance from the "
            "workflow that created the Blueprint and never affects the winner."
        )

        with st.container(horizontal=True):
            if st.button(
                "Open in Blueprint Library",
                key=(
                    "phase9f_b_open_blueprint_"
                    f"{_clean(identity.get('blueprint_id'))}"
                ),
            ):
                st.session_state["phase9d_inspect_blueprint_id"] = _clean(
                    identity.get("blueprint_id")
                )
                st.session_state["phase9d_evaluation_id"] = _clean(
                    phase9c.get("evaluation_id")
                )
                st.session_state["_pending_navigation_page"] = (
                    "Blueprint Library"
                )
                st.rerun()

            source_application_id = int(
                source_application.get("application_id") or 0
            )
            if source_application.get("resolved") is True:
                if st.button(
                    "Open source Application Session",
                    key=(
                        "phase9f_b_open_source_application_"
                        f"{source_application_id}"
                    ),
                ):
                    saved = get_application_by_id(source_application_id)
                    if saved is None:
                        st.error(
                            "The exact source Application Session is no "
                            "longer available."
                        )
                    else:
                        if saved.get("report") is None:
                            st.session_state.pop("latest_report", None)
                        else:
                            st.session_state["latest_report"] = saved[
                                "report"
                            ]
                        st.session_state["cover_letter"] = saved.get(
                            "cover_letter", ""
                        )
                        st.session_state["resume_filename"] = saved.get(
                            "resume_filename", ""
                        )
                        st.session_state["current_application_id"] = (
                            source_application_id
                        )
                        st.session_state["revision_history"] = []
                        st.session_state["analysis_chat"] = []
                        st.session_state["input_reset_counter"] = int(
                            st.session_state.get("input_reset_counter", 0)
                        ) + 1
                        st.session_state["_pending_navigation_page"] = (
                            "Application Sessions"
                        )
                        st.rerun()
            else:
                st.button(
                    "Source Application unavailable",
                    disabled=True,
                    key=(
                        "phase9f_b_missing_source_application_"
                        f"{_clean(identity.get('blueprint_id'))}"
                    ),
                )

        source_jd_tab, phase8_tab, phase9c_tab = st.tabs(
            ["Source JD", "Phase 8 verification", "Phase 9C evaluation"]
        )
        with source_jd_tab:
            st.json(blueprint_provenance.get("source_jd") or {})
        with phase8_tab:
            st.json(phase8)
        with phase9c_tab:
            st.json(phase9c)

        artifact_debug = compact_artifact_resolution(
            resolved,
            error=artifact_error,
        )
        debug_bundle = build_blueprint_provenance_debug_bundle(
            ranking_result=result,
            ranked_candidate=selected,
            blueprint_provenance=blueprint_provenance,
            artifact_resolution=artifact_debug,
        )
        st.download_button(
            "Download Blueprint provenance/debug JSON",
            data=canonical_json(debug_bundle),
            file_name=(
                "phase9f_b_blueprint_provenance_"
                f"{_clean(identity.get('blueprint_id'))[:12]}.json"
            ),
            mime="application/json",
            key=(
                "phase9f_b_download_blueprint_provenance_"
                f"{_clean(identity.get('blueprint_id'))}"
            ),
        )
        missing_links = list(
            blueprint_provenance.get("missing_provenance_links") or []
        )
        if missing_links:
            st.warning(
                "Missing immutable provenance links: "
                + ", ".join(missing_links)
                + ". No identity was guessed."
            )


def _render_ranked_result(
    result: dict[str, Any],
    *,
    exact_jd: dict[str, Any],
    context: dict[str, Any],
    current_base: dict[str, Any] | None,
    current_base_artifact: dict[str, Any] | None,
    blueprints: list[dict[str, Any]],
) -> None:
    winner = result.get("recommended_source") or {}
    transparency = build_ranking_transparency(result)
    st.success(
        "Recommended starting source: "
        f"{_clean(winner.get('source_display_name')) or 'Immutable resume source'}"
    )
    st.caption(
        f"{_clean(winner.get('source_type'))} | version "
        f"{int(winner.get('source_version') or 0)} | "
        f"ID {_clean(winner.get('source_id'))}"
    )

    with st.container(horizontal=True):
        st.metric(
            "Current JD alignment",
            int(winner.get("deterministic_alignment_score") or 0),
            border=True,
        )
        st.metric(
            "Required/Core",
            f"{int(winner.get('required_core_coverage_score') or 0)}%",
            border=True,
        )
        st.metric(
            "Preferred",
            f"{int(winner.get('preferred_coverage_score') or 0)}%",
            border=True,
        )
        st.metric(
            "Evidence strength",
            f"{int(winner.get('evidence_strength_score') or 0)}%",
            border=True,
        )

    relationship = _clean(winner.get("role_family_relationship"))
    if winner.get("role_family_prior_applied"):
        st.info(
            "The same-family prior selected this source only within the "
            "calibrated near-tie window. It did not change the canonical score."
        )
    else:
        st.caption(
            "Role-family relationship: "
            f"{relationship or 'unavailable'} | Ranking reason: "
            f"{_clean(winner.get('ranking_reason'))}"
        )

    _render_winner_transparency(transparency)
    _render_pairwise_transparency(transparency)

    source_context = {
        (_clean(row.get("source_type")), _clean(row.get("source_id"))): row
        for row in transparency.get("source_context", []) or []
    }
    rows = []
    for candidate in result.get("ranked_candidates", []) or []:
        context_row = source_context.get(
            (
                _clean(candidate.get("source_type")),
                _clean(candidate.get("source_id")),
            ),
            {},
        )
        rows.append(
            {
                "Rank": int(candidate.get("rank") or 0),
                "Starting source": _clean(
                    candidate.get("source_display_name")
                ),
                "Type": _clean(candidate.get("source_type")),
                "Version": int(candidate.get("source_version") or 0),
                "Frozen/created": _clean(
                    context_row.get("frozen_or_created_at")
                ),
                "Current JD alignment": int(
                    candidate.get("deterministic_alignment_score") or 0
                ),
                "Required/Core": int(
                    candidate.get("required_core_coverage_score") or 0
                ),
                "Preferred": int(
                    candidate.get("preferred_coverage_score") or 0
                ),
                "Evidence strength": int(
                    candidate.get("evidence_strength_score") or 0
                ),
                "Important gaps": int(
                    candidate.get("important_gap_count") or 0
                ),
                "Deal-breaker gaps": int(
                    candidate.get("deal_breaker_gap_count") or 0
                ),
                "Role family": _clean(
                    candidate.get("role_family_relationship")
                ),
                "Family prior applied": bool(
                    candidate.get("role_family_prior_applied")
                ),
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)
    st.caption(
        "Source version and frozen/created date are provenance context only. "
        "Source age never changes the canonical score or ranking."
    )

    _render_requirement_transparency(transparency)
    _render_ranking_policy(transparency)

    _render_candidate_inspection(
        result=result,
        context=context,
        current_base=current_base,
        current_base_artifact=current_base_artifact,
        blueprints=blueprints,
    )

    with st.expander("Phase 9F-B ranking diagnostics", expanded=False):
        st.caption(
            "This is a transient, read-only deterministic result. Historical "
            "Blueprint approval scores are not used for Current JD alignment."
        )
        diagnostics = {
            "phase9f_b_version": result.get("phase9f_b_version"),
            "status": result.get("status"),
            "ranking_input_fingerprint": result.get(
                "ranking_input_fingerprint"
            ),
            "ranking_fingerprint": result.get("ranking_fingerprint"),
            "semantic_identity": result.get("semantic_identity"),
            "jd_provenance": result.get("jd_provenance"),
            "source_provenance": result.get("source_provenance"),
            "ranked_candidates": result.get("ranked_candidates"),
            "excluded_sources": result.get("excluded_sources"),
            "zero_cost_diagnostics": result.get("zero_cost_diagnostics"),
            "transparency": transparency,
        }
        st.json(diagnostics)
        st.caption(
            "This JSON already includes the deterministic transparency "
            "explanation, pairwise comparison, requirement evidence, ranking "
            "policy, fingerprints, and zero-cost diagnostics."
        )
        st.download_button(
            "Download Phase 9F-B ranking JSON",
            data=canonical_json(diagnostics),
            file_name=(
                "phase9f_b_ranking_"
                f"{_clean(result.get('ranking_fingerprint'))[:12]}.json"
            ),
            mime="application/json",
            key="phase9f_b_download_ranking_json",
        )

    recommendation = render_phase9f_tailoring_intensity(
        result,
        expected_ranking_input_fingerprint=_clean(
            context.get("ranking_input_fingerprint")
        ),
    )
    render_phase9f_application_confirmation(
        phase9f_a_snapshot=exact_jd,
        ranking_result=result,
        phase9f_c_recommendation=recommendation,
    )


def render_phase9f_starting_source_ranking(
    exact_jd: dict[str, Any],
) -> None:
    """Render transient Phase 9F-B ranking after a current Phase 9F-A analysis."""
    st.divider()
    st.subheader("Starting resume recommendation")
    st.caption(
        "Compare the current Base Resume and ACTIVE Global Blueprints against "
        "this exact JD using fresh canonical scoring. No application or "
        "tailoring decision is created in this phase."
    )

    try:
        current_base, artifact, blueprints = _load_immutable_source_scope()
        context = prepare_ranking_context(
            exact_jd=exact_jd,
            current_base_resume=current_base,
            current_base_artifact=artifact,
            global_blueprints=blueprints,
        )
    except Exception as exc:
        st.error(
            "Could not read the immutable starting-source registries: "
            f"{exc}"
        )
        return

    cached = st.session_state.get(RANKING_RESULT_STATE_KEY)
    current_fingerprint = _clean(context.get("ranking_input_fingerprint"))
    cache_is_current = _result_is_current(cached, current_fingerprint)

    if context.get("status") == "integrity_failed":
        if isinstance(cached, dict) and not cache_is_current:
            st.warning(
                "The previous ranking is historical/stale and cannot be used "
                "for the current source scope."
            )
        _render_integrity_diagnostics(context)
        return
    if context.get("status") == "no_eligible_sources":
        st.info(
            "No current Base Resume or eligible ACTIVE Global Blueprint is "
            "available. No source was manufactured or recommended."
        )
        return

    if cache_is_current:
        st.success(
            "Starting-source comparison is up to date for the exact current "
            "JD and immutable source scope."
        )
        result = cached
        if st.button(
            "Recompute comparison",
            width="stretch",
            key="phase9f_b_compare_sources",
        ):
            result = rank_prepared_context(context)
            st.session_state[RANKING_RESULT_STATE_KEY] = result
            st.caption(
                "Recomputed deterministically from the unchanged semantic "
                "inputs; no persisted record was created."
            )
        else:
            st.caption(
                "Reused the exact transient Phase 9F-B result because the JD, "
                "source scope, scorer, taxonomy, and ranking policy are unchanged."
            )
        _render_ranked_result(
            result,
            exact_jd=exact_jd,
            context=context,
            current_base=current_base,
            current_base_artifact=artifact,
            blueprints=blueprints,
        )
        return

    if isinstance(cached, dict):
        st.warning(
            "The previous starting-source ranking is historical/stale because "
            "the complete semantic ranking input changed."
        )

    if st.button(
        "Compare starting resume sources",
        type="primary",
        width="stretch",
        key="phase9f_b_compare_sources",
    ):
        result = rank_prepared_context(context)
        st.session_state[RANKING_RESULT_STATE_KEY] = result
        _render_ranked_result(
            result,
            exact_jd=exact_jd,
            context=context,
            current_base=current_base,
            current_base_artifact=artifact,
            blueprints=blueprints,
        )
    else:
        st.info(
            "Ready for a zero-cost deterministic comparison. This action "
            "makes no model, embedding, Chroma, or persistence calls."
        )

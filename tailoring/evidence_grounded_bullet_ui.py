"""Thin project-first controls for evidence-grounded single-bullet tailoring."""
from __future__ import annotations

import json

import streamlit as st

from ai_providers import (
    CONFIGURED_LLM_PROVIDER,
    GITHUB_COPILOT_PROVIDER,
    REWRITE_PROVIDER_OPTIONS,
    provider_display_name,
)
from tailoring.candidate_context import context_json
from tailoring.evidence_grounded_bullet_tailoring import (
    BULLET_TAILORING_VERSION,
    apply_grounded_bullet,
    build_grounded_baseline_suggestion,
    evaluate_grounded_bullet,
    list_grounded_bullet_opportunities,
    prepare_bullet_target,
    suggest_grounded_bullet,
)


def _support_phrase(label: object) -> str:
    value = str(label or "").strip().lower()
    if value == "direct":
        return "Direct evidence"
    if value == "transferable":
        return "Transferable evidence"
    return value.title() or "Unknown support"


def _normalise_preview_text(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def _requirement_label(row: dict) -> str:
    importance = str(row.get("importance") or "").strip().title()
    text = str(row.get("text") or "").strip()
    support = _support_phrase(row.get("match_label"))
    parts = [value for value in (text, importance, support) if value]
    return " · ".join(parts)


def _find_selected_bullet(opportunities: dict, selected: tuple[int, int] | None) -> dict | None:
    if not selected:
        return None
    project_index, bullet_index = selected
    for project in opportunities.get("projects") or []:
        if int(project.get("project_index", -1)) != int(project_index):
            continue
        for bullet in project.get("bullets") or []:
            if int(bullet.get("bullet_index", -1)) == int(bullet_index):
                return {"project": project, "bullet": bullet}
    return None


def _build_step2_diagnostics(
    *, application_id, generation: dict, opportunities: dict, selected: tuple[int, int] | None,
    report: dict | None = None,
) -> dict:
    """Return one deterministic, read-only snapshot for Step 2 debugging."""
    projects = opportunities.get("projects") or []
    actionable_projects = [project for project in projects if project.get("bullets")]
    already_strong_projects = [
        project for project in projects if project.get("already_strong_bullets")
    ]
    unavailable_projects = [
        project for project in projects
        if not project.get("bullets") and not project.get("already_strong_bullets")
    ]
    return {
        "schema_version": "grounded-bullet-step2-diagnostics-v3",
        "policy_version": BULLET_TAILORING_VERSION,
        "application_id": application_id,
        "generation_id": generation.get("generation_id"),
        "selected_bullet": (
            {"project_index": int(selected[0]), "bullet_index": int(selected[1])}
            if selected is not None
            else None
        ),
        "summary": {
            "project_count": len(projects),
            "actionable_project_count": len(actionable_projects),
            "already_strong_project_count": len(already_strong_projects),
            "unavailable_project_count": len(unavailable_projects),
            "opportunity_count": int(opportunities.get("opportunity_count") or 0),
            "already_strong_count": int(opportunities.get("already_strong_count") or 0),
            "unavailable_requirement_count": len(
                opportunities.get("unavailable_requirements") or []
            ),
        },
        # Keep the full deterministic opportunity rows intact. In particular,
        # each project's diagnostic contains every bullet/source-mapping check,
        # including successful mappings for projects that are currently ready.
        "projects": projects,
        "unavailable_requirements": opportunities.get("unavailable_requirements") or [],
        "ui_sections": (
            _step2_ui_sections(report=report or {}, opportunities=opportunities)
            if report is not None
            else {}
        ),
    }


def _diagnostics_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _importance_sort_key(row: dict) -> tuple[int, str]:
    order = {"deal_breaker": 0, "required": 1, "core": 2, "preferred": 3}
    return (
        order.get(str(row.get("importance") or "").strip().lower(), 9),
        str(row.get("text") or "").strip().lower(),
    )


def _step2_ui_sections(*, report: dict, opportunities: dict) -> dict:
    """Classify Step 2 rows without changing scoring or evidence authority."""
    analysis = report.get("stable_analysis") or {}
    canonical = analysis.get("canonical_requirements") or []
    by_id = {
        str(row.get("requirement_id") or ""): row
        for row in canonical
        if row.get("requirement_id")
    }

    unsupported_gaps: list[dict] = []
    weak_support: list[dict] = []
    other_unavailable_requirements: list[dict] = []
    for row in opportunities.get("unavailable_requirements") or []:
        requirement_id = str(row.get("requirement_id") or "")
        source = by_id.get(requirement_id, {})
        merged = {
            **row,
            "match_label": str(source.get("match_label") or "none").strip().lower(),
            "semantic_type": source.get("semantic_type") or "candidate_requirement",
            "score_eligible": bool(source.get("score_eligible", True)),
            "tailoring_eligible": bool(source.get("tailoring_eligible", True)),
        }
        if not merged["score_eligible"]:
            continue
        if merged["match_label"] == "none":
            unsupported_gaps.append(merged)
        elif merged["match_label"] == "weak":
            weak_support.append(merged)
        else:
            other_unavailable_requirements.append(merged)

    for rows in (unsupported_gaps, weak_support, other_unavailable_requirements):
        rows.sort(key=_importance_sort_key)

    filtered = (
        (analysis.get("canonicalisation_debug") or {}).get("filtered_non_requirement_rows")
        or []
    )
    non_scored_context: list[dict] = []
    seen_context: set[tuple[str, str]] = set()
    for row in filtered:
        semantic_type = str(row.get("semantic_type") or "").strip().lower()
        if semantic_type not in {"role_context", "training_outcome"}:
            continue
        text = str(row.get("text") or "").strip()
        key = (semantic_type, " ".join(text.casefold().split()))
        if not text or key in seen_context:
            continue
        seen_context.add(key)
        non_scored_context.append({
            "text": text,
            "semantic_type": semantic_type,
            "eligibility_rule": row.get("eligibility_rule"),
            "source": row.get("source"),
        })

    projects = opportunities.get("projects") or []
    actionable_projects = [project for project in projects if project.get("bullets")]
    already_strong_projects = [
        project for project in projects if project.get("already_strong_bullets")
    ]
    unavailable_projects = [
        project for project in projects
        if not project.get("bullets") and not project.get("already_strong_bullets")
    ]
    fallback_codes = {"fallback_only", "no_grounded_project_relationship"}
    fallback_projects = [
        project for project in unavailable_projects
        if str((project.get("diagnostic") or {}).get("code") or "") in fallback_codes
    ]
    blocked_projects = [
        project for project in unavailable_projects
        if project not in fallback_projects
    ]

    return {
        "actionable_projects": actionable_projects,
        "already_strong_projects": already_strong_projects,
        "fallback_projects": fallback_projects,
        "blocked_projects": blocked_projects,
        "unsupported_gaps": unsupported_gaps,
        "weak_support": weak_support,
        "other_unavailable_requirements": other_unavailable_requirements,
        "non_scored_context": non_scored_context,
    }


def _context_type_label(value: object) -> str:
    labels = {
        "role_context": "Role context",
        "training_outcome": "Training / onboarding",
    }
    key = str(value or "").strip().lower()
    return labels.get(key, key.replace("_", " ").title() or "Not scored")


def _render_requirement_rows(rows: list[dict], *, include_match: bool = False) -> None:
    for row in rows:
        importance = str(row.get("importance") or "").strip().title()
        text = str(row.get("text") or "").strip()
        suffix = ""
        if include_match:
            suffix = f" — {_support_phrase(row.get('match_label'))}"
        st.markdown(f"- **{importance or 'JD'}** · {text}{suffix}")


def _build_applied_change_notice(
    *, project_title: str, previous_bullet: str, applied_bullet: str,
    before_label: str, after_label: str, source_generation_id: str,
    new_generation_id: str, suggestion_kind: str,
) -> dict:
    return {
        "project_title": str(project_title or "").strip(),
        "previous_bullet": str(previous_bullet or "").strip(),
        "applied_bullet": str(applied_bullet or "").strip(),
        "before_label": str(before_label or "none").strip().lower(),
        "after_label": str(after_label or "none").strip().lower(),
        "source_generation_id": str(source_generation_id or "").strip(),
        "new_generation_id": str(new_generation_id or "").strip(),
        "suggestion_kind": str(suggestion_kind or "").strip(),
    }


def _render_apply_confirmation(
    *,
    heading: str,
    project_title: str,
    previous_bullet: str,
    proposed_bullet: str,
    before_label: str,
    after_label: str,
    cancel_label: str,
    confirm_label: str,
    key_prefix: str,
) -> tuple[bool, bool]:
    # Review-only confirmation panel. It must not mutate résumé state.
    with st.container(border=True):
        st.markdown(f"##### {heading}")
        st.write(f"**Project:** {project_title}")

        left, right = st.columns(2)
        with left:
            st.caption("CURRENT")
            st.write(previous_bullet)
        with right:
            st.caption("PROPOSED")
            st.write(proposed_bullet)

        st.write(
            f"**Expected deterministic result:** "
            f"{str(before_label or 'none').title()} → "
            f"{str(after_label or 'none').title()}"
        )
        st.caption(
            "No résumé data changes until you confirm. Confirming creates a "
            "new working draft; the source generation remains preserved."
        )

        cancel_col, confirm_col = st.columns(2)
        with cancel_col:
            cancelled = st.button(
                cancel_label,
                key=f"{key_prefix}_cancel",
            )
        with confirm_col:
            confirmed = st.button(
                confirm_label,
                key=f"{key_prefix}_confirm",
                type="primary",
            )
    return cancelled, confirmed


def _render_applied_change_notice(*, application_id, generation: dict) -> None:
    notice_key = f"grounded_bullet_last_applied_{application_id}"
    notice = st.session_state.get(notice_key)
    if not isinstance(notice, dict):
        return

    current_generation_id = str(generation.get("generation_id") or "")
    new_generation_id = str(notice.get("new_generation_id") or "")
    if new_generation_id and current_generation_id != new_generation_id:
        return

    project_title = str(notice.get("project_title") or "Project")
    previous_bullet = str(notice.get("previous_bullet") or "")
    applied_bullet = str(notice.get("applied_bullet") or "")
    before_label = str(notice.get("before_label") or "none").title()
    after_label = str(notice.get("after_label") or "none").title()

    st.success(
        f"✓ Applied Step 2 change for {project_title}. "
        f"Target match improved {before_label} → {after_label}."
    )
    with st.container(border=True):
        st.markdown("##### Last Step 2 change")
        left, right = st.columns(2)
        with left:
            st.caption("PREVIOUS")
            st.write(previous_bullet)
        with right:
            st.caption("APPLIED")
            st.write(applied_bullet)
        st.caption(
            "The opportunity may now disappear from Section 1 because the new "
            "draft is re-scored immediately. If the applied bullet reached its "
            "evidence-supported ceiling, it will move to Already strong."
        )
        if st.button(
            "Dismiss applied-change summary",
            key=f"{notice_key}_dismiss_{current_generation_id}",
        ):
            st.session_state.pop(notice_key, None)
            st.rerun()


def render_grounded_bullet_tailoring(
    *, application_id, generation, report, model,
    before_model_call=None, after_model_call=None,
):
    with st.expander("Step 2 — Strengthen Project Evidence for This Job", expanded=True):
        st.info(
            "Projects & Skills selected ✓  |  Now: strengthen only bullets whose deterministic "
            "JD coverage can improve  |  Next: Build and Fit Résumé. A verified grounded "
            "replacement is available without AI; optional AI polish never creates missing "
            "experience and remains preview-only until you Apply."
        )
        try:
            opportunities = list_grounded_bullet_opportunities(
                generation=generation,
                report=report,
            )
        except ValueError as exc:
            st.warning(str(exc))
            return None

        prefix = f"grounded_bullet_{application_id}_{generation['generation_id']}"
        selection_key = prefix + "_selected_bullet"
        diagnostics_visible_key = prefix + "_diagnostics_visible"
        notice_key = f"grounded_bullet_last_applied_{application_id}"
        projects = opportunities.get("projects") or []
        if not projects:
            st.info("A current editable project draft is required.")
            return None

        _render_applied_change_notice(
            application_id=application_id,
            generation=generation,
        )

        sections = _step2_ui_sections(report=report, opportunities=opportunities)
        diagnostics_payload = _build_step2_diagnostics(
            application_id=application_id,
            generation=generation,
            opportunities=opportunities,
            selected=st.session_state.get(selection_key),
            report=report,
        )
        with st.expander("Debug diagnostics", expanded=False):
            st.caption(
                "Reviewer-only, read-only Step 2 snapshot. It does not call a model or change "
                "the draft. It includes project/source mappings, rejection reasons, score gaps, "
                "and non-scored JD context."
            )
            show_label = (
                "Hide complete diagnostics"
                if st.session_state.get(diagnostics_visible_key)
                else "Show complete diagnostics"
            )
            if st.button(show_label, key=prefix + "_toggle_diagnostics"):
                st.session_state[diagnostics_visible_key] = not bool(
                    st.session_state.get(diagnostics_visible_key)
                )
                st.rerun()
            st.download_button(
                "Download Step 2 diagnostics JSON",
                _diagnostics_json(diagnostics_payload),
                file_name=(
                    f"step2_grounded_bullet_diagnostics_app_{application_id}_"
                    f"{generation.get('generation_id') or 'unknown'}.json"
                ),
                mime="application/json",
                key=prefix + "_download_diagnostics",
            )
            if st.session_state.get(diagnostics_visible_key):
                st.json(diagnostics_payload, expanded=False)

        # ------------------------------------------------------------------
        # 1. Genuine score-improving rewrite opportunities.
        # ------------------------------------------------------------------
        st.markdown("#### 1. Score-improving opportunities")
        st.caption(
            "A rewrite is offered only when the current bullet is below the strongest "
            "deterministic match supported by that same bullet's frozen source evidence."
        )
        actionable_projects = sections["actionable_projects"]
        if not actionable_projects:
            st.success(
                "✓ No score-improving project-bullet rewrites are needed for this draft."
            )
        for project in actionable_projects:
            title = str(project.get("title") or "Untitled project")
            st.markdown(f"**{title}**")
            for bullet in project.get("bullets") or []:
                with st.container(border=True):
                    st.write(str(bullet.get("current_bullet") or ""))
                    for row in bullet.get("requirements") or []:
                        st.markdown(
                            f"- **{row.get('text')}**  "
                            f"{_support_phrase(row.get('current_match_label'))} → "
                            f"{_support_phrase(row.get('safe_evidence_ceiling'))}"
                        )
                    if st.button(
                        "Strengthen this bullet",
                        key=(
                            prefix
                            + f"_choose_{project['project_index']}_{bullet['bullet_index']}"
                        ),
                    ):
                        st.session_state[selection_key] = (
                            int(project["project_index"]),
                            int(bullet["bullet_index"]),
                        )

        selected = _find_selected_bullet(
            opportunities,
            st.session_state.get(selection_key),
        )
        if selected is not None:
            project = selected["project"]
            bullet = selected["bullet"]
            project_index = int(project["project_index"])
            bullet_index = int(bullet["bullet_index"])
            requirement_rows = bullet.get("requirements") or []

            st.markdown("##### Selected score-improving rewrite")
            st.write(f"**Project:** {project.get('title')}")
            st.write(f"**Current bullet:** {bullet.get('current_bullet')}")

            if len(requirement_rows) == 1:
                requirement = requirement_rows[0]
                requirement_id = requirement["requirement_id"]
                st.write(f"**Target requirement:** {requirement.get('text')}")
                st.caption(
                    f"Importance: {str(requirement.get('importance') or '').title()} · "
                    f"Potential: {_support_phrase(requirement.get('current_match_label'))} → "
                    f"{_support_phrase(requirement.get('safe_evidence_ceiling'))}"
                )
            else:
                requirement_ids = [row["requirement_id"] for row in requirement_rows]
                by_id = {row["requirement_id"]: row for row in requirement_rows}
                requirement_id = st.radio(
                    "Which supported JD requirement should this bullet strengthen?",
                    requirement_ids,
                    format_func=lambda rid: _requirement_label(by_id[rid]),
                    key=prefix + f"_requirement_{project_index}_{bullet_index}",
                )
                requirement = by_id[requirement_id]

            try:
                target = prepare_bullet_target(
                    generation=generation,
                    report=report,
                    project_index=project_index,
                    bullet_index=bullet_index,
                    requirement_id=requirement_id,
                )
            except ValueError as exc:
                st.warning(str(exc))
                target = None

            if target is not None and target["status"] == "ready":
                records = target["evidence_records"]
                st.markdown("##### Grounded evidence for this rewrite")
                if len(records) == 1:
                    evidence_id = records[0]["evidence_id"]
                    st.write(records[0]["text"])
                    st.caption(
                        f"Evidence ceiling: {_support_phrase(records[0].get('support_label'))}"
                    )
                else:
                    record_by_id = {row["evidence_id"]: row for row in records}
                    evidence_id = st.radio(
                        "Grounded evidence row",
                        list(record_by_id),
                        format_func=lambda eid: record_by_id[eid]["text"],
                        key=prefix + "_evidence_" + target["target_fingerprint"],
                    )

                with st.expander("Technical details", expanded=False):
                    st.caption(f"Evidence ID: {evidence_id}")
                    st.json(target["relationship"], expanded=False)
                    st.download_button(
                        "Download frozen Candidate Context",
                        context_json(target["candidate_context"]),
                        file_name="frozen_candidate_context.json",
                        mime="application/json",
                        key=prefix + "_context_" + target["target_fingerprint"],
                    )

                # Build and verify a zero-model baseline first. The exact frozen
                # evidence row is the candidate wording, so AI is optional polish
                # rather than a dependency of the score-improvement workflow.
                try:
                    grounded = build_grounded_baseline_suggestion(
                        generation=generation,
                        report=report,
                        project_index=project_index,
                        bullet_index=bullet_index,
                        requirement_id=requirement_id,
                        evidence_id=evidence_id,
                    )
                    grounded_evaluation = evaluate_grounded_bullet(
                        generation=generation,
                        report=report,
                        suggestion=grounded,
                    )
                except Exception as exc:
                    grounded = None
                    grounded_evaluation = None
                    st.error(f"Could not build the grounded replacement: {exc}")

                if grounded and grounded_evaluation:
                    st.markdown("##### Grounded replacement — no AI required")
                    grounded_candidate = str(
                        (grounded.get("response") or {}).get("candidate_bullet", "")
                    )
                    st.write(grounded_candidate)

                    before_label = str(
                        (grounded_evaluation.get("target_before") or {}).get(
                            "match_label"
                        ) or "none"
                    ).title()
                    after_label = str(
                        (grounded_evaluation.get("target_after") or {}).get(
                            "match_label"
                        ) or "none"
                    ).title()
                    claim_reviews = int(
                        (grounded_evaluation.get("claim_lineage") or {}).get(
                            "claim_review_required_count", 0
                        ) or 0
                    )
                    regressions = (
                        (grounded_evaluation.get("comparison") or {}).get(
                            "important_regressions"
                        ) or []
                    )

                    if grounded_evaluation.get("safe_to_apply"):
                        st.success(
                            "Deterministic verification passed. You can apply this "
                            "grounded replacement without using a model."
                        )
                    else:
                        st.error(
                            "Grounded replacement is blocked: "
                            + ", ".join(
                                grounded_evaluation.get("reasons")
                                or ["verification failed"]
                            )
                        )

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Target match", f"{before_label} → {after_label}")
                    c2.metric("Claim reviews", claim_reviews)
                    c3.metric("Protected regressions", len(regressions))

                    grounded_confirm_key = (
                        prefix
                        + "_confirm_grounded_apply_"
                        + target["target_fingerprint"]
                    )
                    if st.button(
                        "Review & apply grounded replacement",
                        key=prefix
                        + "_review_apply_grounded_"
                        + target["target_fingerprint"],
                        disabled=not grounded_evaluation.get("safe_to_apply", False),
                        type="primary",
                    ):
                        st.session_state[grounded_confirm_key] = True
                        st.rerun()

                    if st.session_state.get(grounded_confirm_key):
                        grounded_cancelled, grounded_confirmed = (
                            _render_apply_confirmation(
                                heading="Confirm this résumé change",
                                project_title=str(
                                    project.get("title") or "Project"
                                ),
                                previous_bullet=str(
                                    target.get("current_bullet") or ""
                                ),
                                proposed_bullet=grounded_candidate,
                                before_label=str(
                                    (
                                        grounded_evaluation.get(
                                            "target_before"
                                        )
                                        or {}
                                    ).get("match_label")
                                    or "none"
                                ),
                                after_label=str(
                                    (
                                        grounded_evaluation.get(
                                            "target_after"
                                        )
                                        or {}
                                    ).get("match_label")
                                    or "none"
                                ),
                                cancel_label="Cancel grounded apply",
                                confirm_label=(
                                    "Confirm apply grounded replacement"
                                ),
                                key_prefix=grounded_confirm_key,
                            )
                        )
                        if grounded_cancelled:
                            st.session_state.pop(
                                grounded_confirm_key, None
                            )
                            st.rerun()

                        if grounded_confirmed:
                            applied_result = apply_grounded_bullet(
                                application_id=application_id,
                                source_generation_id=generation[
                                    "generation_id"
                                ],
                                suggestion=grounded,
                            )
                            st.session_state.pop(
                                grounded_confirm_key, None
                            )
                            applied_generation = (
                                applied_result.get("generation")
                                if isinstance(applied_result, dict)
                                else None
                            ) or {}
                            st.session_state[notice_key] = (
                                _build_applied_change_notice(
                                    project_title=str(
                                        project.get("title") or "Project"
                                    ),
                                    previous_bullet=str(
                                        target.get("current_bullet") or ""
                                    ),
                                    applied_bullet=grounded_candidate,
                                    before_label=str(
                                        (
                                            grounded_evaluation.get(
                                                "target_before"
                                            )
                                            or {}
                                        ).get("match_label")
                                        or "none"
                                    ),
                                    after_label=str(
                                        (
                                            grounded_evaluation.get(
                                                "target_after"
                                            )
                                            or {}
                                        ).get("match_label")
                                        or "none"
                                    ),
                                    source_generation_id=str(
                                        generation.get(
                                            "generation_id"
                                        )
                                        or ""
                                    ),
                                    new_generation_id=str(
                                        applied_generation.get(
                                            "generation_id"
                                        )
                                        or ""
                                    ),
                                    suggestion_kind=str(
                                        grounded.get(
                                            "suggestion_kind"
                                        )
                                        or grounded.get("status")
                                        or "grounded"
                                    ),
                                )
                            )
                            return applied_result

                # Successful AI previews are cached by exact target + evidence +
                # explicit provider identity. Providers never silently fall back.
                with st.expander(
                    "Optional: Polish this grounded replacement with AI",
                    expanded=False,
                ):
                    provider_labels = list(REWRITE_PROVIDER_OPTIONS)
                    selected_provider_label = st.selectbox(
                        "Polish provider",
                        provider_labels,
                        index=0,
                        key=prefix
                        + "_polish_provider_"
                        + target["target_fingerprint"],
                    )
                    provider_id = REWRITE_PROVIDER_OPTIONS[
                        selected_provider_label
                    ]
                    provider_model = (
                        model
                        if provider_id == CONFIGURED_LLM_PROVIDER
                        else "auto"
                    )
                    preview_key = (
                        prefix
                        + "_ai_preview_"
                        + target["target_fingerprint"]
                        + evidence_id
                        + provider_id
                        + provider_model
                    )

                    if provider_id == CONFIGURED_LLM_PROVIDER:
                        st.caption(
                            f"Provider: Current Rephrase model · `{model}`. "
                            "This uses the existing configured LLM route. If it "
                            "fails, the verified grounded replacement above remains "
                            "available; there is no automatic provider fallback."
                        )
                    elif provider_id == GITHUB_COPILOT_PROVIDER:
                        st.caption(
                            "Provider: GitHub Copilot · model `auto`. Uses the "
                            "signed-in Copilot account. One click sends one prompt; "
                            "there are no automatic retries, no OpenAI fallback, "
                            "and no Job AI/file/shell tools are exposed."
                        )

                    if st.button(
                        "Polish grounded wording with AI",
                        key=prefix
                        + "_polish_"
                        + target["target_fingerprint"]
                        + "_"
                        + provider_id,
                    ):
                        try:
                            # The existing LiteLLM route owns Job AI's token/cost
                            # ledger. Copilot has separate account usage, so it must
                            # not create a fake LiteLLM usage entry.
                            if (
                                provider_id == CONFIGURED_LLM_PROVIDER
                                and callable(before_model_call)
                            ):
                                before_model_call()
                            generated = suggest_grounded_bullet(
                                generation=generation,
                                report=report,
                                project_index=project_index,
                                bullet_index=bullet_index,
                                requirement_id=requirement_id,
                                evidence_id=evidence_id,
                                model=provider_model,
                                provider=provider_id,
                            )
                            st.session_state[preview_key] = generated
                            if (
                                provider_id == CONFIGURED_LLM_PROVIDER
                                and callable(after_model_call)
                                and generated.get("model_call_count")
                            ):
                                after_model_call()
                        except Exception as exc:
                            st.warning(
                                "AI polish was unavailable. The deterministic "
                                "grounded replacement is still usable. "
                                f"Details: {exc}"
                            )

                    suggestion = st.session_state.get(preview_key)
                    if suggestion:
                        suggestion_provider = provider_display_name(
                            suggestion.get("provider") or provider_id
                        )
                        st.markdown(
                            f"##### Review {suggestion_provider} wording"
                        )
                        candidate = str(
                            (suggestion.get("response") or {}).get(
                                "candidate_bullet", ""
                            )
                        )
                        grounded_text = str(
                            (grounded.get("response") or {}).get(
                                "candidate_bullet", ""
                            ) if grounded else ""
                        )
                        candidate_unchanged = (
                            _normalise_preview_text(candidate)
                            == _normalise_preview_text(grounded_text)
                        )

                        left, right = st.columns(2)
                        with left:
                            st.caption("GROUNDED BASELINE")
                            st.write(grounded_text)
                        with right:
                            st.caption(
                                suggestion_provider.upper()
                                + " POLISH"
                            )
                            st.write(candidate)

                        try:
                            evaluation = evaluate_grounded_bullet(
                                generation=generation,
                                report=report,
                                suggestion=suggestion,
                            )
                            ai_before_label = str(
                                (evaluation.get("target_before") or {}).get(
                                    "match_label"
                                ) or "none"
                            ).title()
                            ai_after_label = str(
                                (evaluation.get("target_after") or {}).get(
                                    "match_label"
                                ) or "none"
                            ).title()
                            ai_before_points = float(
                                (evaluation.get("target_points_before") or {}).get(
                                    "component_coverage_points", 0.0
                                ) or 0.0
                            )
                            ai_after_points = float(
                                (evaluation.get("target_points_after") or {}).get(
                                    "component_coverage_points", 0.0
                                ) or 0.0
                            )
                            ai_claim_reviews = int(
                                (evaluation.get("claim_lineage") or {}).get(
                                    "claim_review_required_count", 0
                                ) or 0
                            )
                            ai_regressions = (
                                (evaluation.get("comparison") or {}).get(
                                    "important_regressions"
                                ) or []
                            )

                            if candidate_unchanged:
                                st.info(
                                    f"{suggestion_provider} returned the same "
                                    "wording as the grounded replacement. No "
                                    "additional AI Apply is needed; use the "
                                    "grounded replacement above."
                                )
                            elif evaluation.get("safe_to_apply"):
                                st.success(
                                    f"{suggestion_provider} polish passed the "
                                    "same deterministic verifier."
                                )
                            else:
                                st.error(
                                    f"{suggestion_provider} polish is blocked: "
                                    + ", ".join(
                                        evaluation.get("reasons")
                                        or ["verification failed"]
                                    )
                                    + ". The grounded replacement above remains "
                                    "available."
                                )

                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric(
                                "Target match",
                                f"{ai_before_label} → {ai_after_label}",
                            )
                            c2.metric(
                                "Target points",
                                f"{ai_before_points:.2f} → {ai_after_points:.2f}",
                            )
                            c3.metric("Claim reviews", ai_claim_reviews)
                            c4.metric(
                                "Protected regressions",
                                len(ai_regressions),
                            )

                            clear_col, apply_col = st.columns(2)
                            with clear_col:
                                if st.button(
                                    "Discard AI polish",
                                    key=prefix
                                    + "_discard_ai_"
                                    + target["target_fingerprint"]
                                    + "_"
                                    + provider_id,
                                ):
                                    st.session_state.pop(preview_key, None)
                                    st.rerun()
                            with apply_col:
                                ai_confirm_key = (
                                    prefix
                                    + "_confirm_ai_apply_"
                                    + target["target_fingerprint"]
                                    + "_"
                                    + provider_id
                                )
                                if st.button(
                                    "Review & apply AI-polished bullet",
                                    key=prefix
                                    + "_review_apply_ai_"
                                    + target["target_fingerprint"]
                                    + "_"
                                    + provider_id,
                                    disabled=(
                                        candidate_unchanged
                                        or not evaluation.get(
                                            "safe_to_apply", False
                                        )
                                    ),
                                    type="primary",
                                ):
                                    st.session_state[ai_confirm_key] = True
                                    st.rerun()

                                if (
                                    not candidate_unchanged
                                    and st.session_state.get(ai_confirm_key)
                                ):
                                    ai_cancelled, ai_confirmed = (
                                        _render_apply_confirmation(
                                            heading=(
                                                "Confirm AI-polished "
                                                "résumé change"
                                            ),
                                            project_title=str(
                                                project.get("title")
                                                or "Project"
                                            ),
                                            previous_bullet=str(
                                                target.get(
                                                    "current_bullet"
                                                )
                                                or ""
                                            ),
                                            proposed_bullet=candidate,
                                            before_label=str(
                                                (
                                                    evaluation.get(
                                                        "target_before"
                                                    )
                                                    or {}
                                                ).get("match_label")
                                                or "none"
                                            ),
                                            after_label=str(
                                                (
                                                    evaluation.get(
                                                        "target_after"
                                                    )
                                                    or {}
                                                ).get("match_label")
                                                or "none"
                                            ),
                                            cancel_label=(
                                                "Cancel AI-polished apply"
                                            ),
                                            confirm_label=(
                                                "Confirm apply AI-polished "
                                                "bullet"
                                            ),
                                            key_prefix=ai_confirm_key,
                                        )
                                    )
                                    if ai_cancelled:
                                        st.session_state.pop(
                                            ai_confirm_key, None
                                        )
                                        st.rerun()

                                    if ai_confirmed:
                                        applied_result = (
                                            apply_grounded_bullet(
                                                application_id=application_id,
                                                source_generation_id=generation[
                                                    "generation_id"
                                                ],
                                                suggestion=suggestion,
                                            )
                                        )
                                        st.session_state.pop(
                                            ai_confirm_key, None
                                        )
                                        applied_generation = (
                                            applied_result.get("generation")
                                            if isinstance(
                                                applied_result, dict
                                            )
                                            else None
                                        ) or {}
                                        st.session_state[notice_key] = (
                                            _build_applied_change_notice(
                                                project_title=str(
                                                    project.get("title")
                                                    or "Project"
                                                ),
                                                previous_bullet=str(
                                                    target.get(
                                                        "current_bullet"
                                                    )
                                                    or ""
                                                ),
                                                applied_bullet=candidate,
                                                before_label=str(
                                                    (
                                                        evaluation.get(
                                                            "target_before"
                                                        )
                                                        or {}
                                                    ).get("match_label")
                                                    or "none"
                                                ),
                                                after_label=str(
                                                    (
                                                        evaluation.get(
                                                            "target_after"
                                                        )
                                                        or {}
                                                    ).get("match_label")
                                                    or "none"
                                                ),
                                                source_generation_id=str(
                                                    generation.get(
                                                        "generation_id"
                                                    )
                                                    or ""
                                                ),
                                                new_generation_id=str(
                                                    applied_generation.get(
                                                        "generation_id"
                                                    )
                                                    or ""
                                                ),
                                                suggestion_kind=str(
                                                    suggestion.get(
                                                        "suggestion_kind"
                                                    )
                                                    or suggestion.get(
                                                        "status"
                                                    )
                                                    or "ai_polish"
                                                ),
                                            )
                                        )
                                        return applied_result
                        except Exception as exc:
                            st.error(str(exc))
            elif target is not None:
                st.warning(
                    "This target no longer has a score-improving frozen-evidence path. "
                    "The draft may have changed; refresh Step 2 before generating."
                )

        # ------------------------------------------------------------------
        # 2. Grounded bullets that should not spend a model call.
        # ------------------------------------------------------------------
        st.markdown("#### 2. Already strong")
        st.caption(
            "These bullets already express the strongest deterministic match their frozen "
            "evidence can support. They remain useful résumé content, but a score-oriented "
            "rewrite would not improve their JD coverage."
        )
        already_strong_projects = sections["already_strong_projects"]
        if not already_strong_projects:
            st.caption("No already-at-ceiling project bullets to show.")
        for project in already_strong_projects:
            st.markdown(f"**{project.get('title') or 'Untitled project'}**")
            for bullet in project.get("already_strong_bullets") or []:
                with st.container(border=True):
                    st.write(str(bullet.get("current_bullet") or ""))
                    for row in bullet.get("requirements") or []:
                        st.markdown(
                            f"- ✓ **{row.get('text')}** — "
                            f"{_support_phrase(row.get('current_match_label'))}; "
                            "already at evidence-supported ceiling"
                        )

        # ------------------------------------------------------------------
        # 3. Real evidence-bearing gaps, separate from weak/other states.
        # ------------------------------------------------------------------
        unsupported_gaps = sections["unsupported_gaps"]
        st.markdown(f"#### 3. Unsupported evidence-bearing JD gaps ({len(unsupported_gaps)})")
        st.caption(
            "These are scored qualifications or responsibilities for which the current stable "
            "analysis gives no credited evidence. Rewriting cannot manufacture them."
        )
        if unsupported_gaps:
            with st.expander("View unsupported JD gaps", expanded=False):
                _render_requirement_rows(unsupported_gaps)
            if st.button("Review Evidence Library", key=prefix + "_review_evidence_library"):
                st.session_state["_pending_navigation_page"] = "Profile & Evidence"
                st.rerun()
        else:
            st.success("✓ No fully unsupported evidence-bearing JD gaps are present.")

        if sections["weak_support"]:
            with st.expander(
                f"Weakly supported JD items ({len(sections['weak_support'])})",
                expanded=False,
            ):
                st.caption(
                    "These have some credited evidence, so they are not classified as unsupported gaps."
                )
                _render_requirement_rows(sections["weak_support"], include_match=True)

        if sections["other_unavailable_requirements"]:
            with st.expander(
                "Other JD items not available for selected-project bullet rewriting",
                expanded=False,
            ):
                st.caption(
                    "These may already be supported elsewhere in the résumé, but no exact selected-project "
                    "bullet is a safe rewrite target for them."
                )
                _render_requirement_rows(
                    sections["other_unavailable_requirements"], include_match=True
                )

        # ------------------------------------------------------------------
        # 4. Non-evidence-bearing JD context excluded upstream.
        # ------------------------------------------------------------------
        context_rows = sections["non_scored_context"]
        st.markdown(f"#### 4. Role context / training — not scored ({len(context_rows)})")
        st.caption(
            "These statements describe the working environment or what you will learn after joining. "
            "They are intentionally excluded from résumé evidence scoring and bullet tailoring."
        )
        if context_rows:
            with st.expander("View non-scored JD context", expanded=False):
                for row in context_rows:
                    st.markdown(
                        f"- **{_context_type_label(row.get('semantic_type'))}** · "
                        f"{row.get('text')}"
                    )
        else:
            st.caption("No role-context or training statements were excluded for this JD.")

        # ------------------------------------------------------------------
        # 5. Selected fallback projects with no proven JD coverage.
        # ------------------------------------------------------------------
        fallback_projects = sections["fallback_projects"]
        st.markdown(f"#### 5. Fallback projects — no proven JD coverage ({len(fallback_projects)})")
        st.caption(
            "These projects may still be included for résumé completeness, but the current deterministic "
            "analysis does not prove a selected JD requirement from their project evidence."
        )
        for project in fallback_projects:
            with st.container(border=True):
                st.markdown(f"**{project.get('title') or 'Untitled project'}**")
                st.caption(
                    str(
                        (project.get("diagnostic") or {}).get("message")
                        or "No proven JD coverage from this project's evidence."
                    )
                )
        if not fallback_projects:
            st.caption("No fallback projects without proven JD coverage are selected.")

        if sections["blocked_projects"]:
            with st.expander(
                f"Other unavailable projects ({len(sections['blocked_projects'])})",
                expanded=False,
            ):
                st.caption(
                    "These are not fallback-only cases. See Debug diagnostics for the exact deterministic reason."
                )
                for project in sections["blocked_projects"]:
                    diagnostic = project.get("diagnostic") or {}
                    st.markdown(f"**{project.get('title') or 'Untitled project'}**")
                    st.caption(str(diagnostic.get("message") or "Unavailable for safe rewriting."))

        st.info(
            "Done reviewing Step 2? Continue below to Build and Fit Résumé Document. "
            "Only applied bullet changes affect the application draft."
        )
    return None

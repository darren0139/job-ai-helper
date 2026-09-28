from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd
import streamlit as st

from database.taxonomy_discovery_review_manager import (
    delete_review,
    list_reviews,
    save_review,
)
from taxonomy_discovery.assisted_review import (
    ASSISTED_REVIEW_VERSION,
    ask_local_ai_suggestion,
    build_debug_bundle,
    build_deterministic_suggestion,
    local_ollama_models,
    search_taxonomy,
)
from taxonomy_discovery.technology_registry import registry_rows
from taxonomy_discovery.research_proposals import (
    PROPOSAL_CONTRACT_VERSION,
    PROPOSAL_REVIEW_DECISIONS,
    ask_local_ai_proposal_review,
    build_proposal_decision_suggestion,
    build_registry_vnext_preview,
    build_research_handover,
    validate_proposal_bundle,
)
from database.technology_registry_proposal_manager import (
    import_proposal_bundle,
    list_proposal_reviews,
    list_proposals,
    save_proposal_review,
)
from taxonomy_discovery.triage import (
    TRIAGE_STATUSES,
    TRIAGE_VERSION,
    build_triage_report,
)

PATCH_MARKER = "tqd2.6-technology-registry-ui-v1"

STATUS_LABELS = {
    "unreviewed": "Unreviewed",
    "research_candidate": "Research candidate",
    "existing_taxonomy_near_miss": "Existing taxonomy near miss",
    "decomposition_issue": "Decomposition issue",
    "scope_review": "Scope review",
    "defer": "Defer",
}

QUEUE_OPTIONS = (
    "Needs human review",
    "Registry recognized but unmapped",
    "No registry match",
    "Direct candidate evidence",
    "Atomic with parent context",
    "High lexical signal (>= 0.50)",
    "All candidates including registry-resolved",
)


def _candidate_text(candidate: dict[str, Any]) -> str:
    observed = candidate.get("observed_terms", []) or []
    return str(
        observed[0]
        if observed
        else candidate.get("normalised_observed_text") or ""
    )


def _candidate_label(candidate: dict[str, Any]) -> str:
    registry = candidate.get("technology_registry_resolution", {}) or {}
    if registry.get("status") == "resolved":
        prefix = "[Registry resolved]"
    else:
        status = str(
            (candidate.get("triage", {}) or {}).get(
                "status",
                "unreviewed",
            )
        )
        prefix = f"[{STATUS_LABELS.get(status, status)}]"
    return f"{prefix} {_candidate_text(candidate)}"


def _top_lexical_score(candidate: dict[str, Any]) -> float | None:
    values: list[float] = []
    for context in candidate.get("observation_contexts", []) or []:
        retrieval = (context or {}).get("retrieval", {}) or {}
        score = retrieval.get("lexical_top_score")
        if isinstance(score, (int, float)):
            values.append(float(score))
    return max(values) if values else None


def _matches_queue(candidate: dict[str, Any], queue: str) -> bool:
    registry_status = str(
        (
            candidate.get("technology_registry_resolution", {})
            or {}
        ).get("status")
        or "unresolved"
    )
    flags = set(candidate.get("diagnostic_flags", []) or [])

    if queue == "Needs human review":
        return registry_status != "resolved"
    if queue == "Registry recognized but unmapped":
        return registry_status == "recognized_unmapped"
    if queue == "No registry match":
        return registry_status == "unresolved"
    if queue == "Direct candidate evidence":
        return (
            registry_status != "resolved"
            and "candidate_match_direct" in flags
        )
    if queue == "Atomic with parent context":
        return (
            registry_status != "resolved"
            and "atomic_parent_context_available" in flags
        )
    if queue == "High lexical signal (>= 0.50)":
        score = _top_lexical_score(candidate)
        return (
            registry_status != "resolved"
            and score is not None
            and score >= 0.50
        )
    return True


def _target_options(candidate: dict[str, Any]) -> list[str]:
    values: set[str] = set()
    registry = candidate.get("technology_registry_resolution", {}) or {}
    registry_target = str(registry.get("capability_id") or "").strip()
    if registry_target:
        values.add(registry_target)

    for context in candidate.get("observation_contexts", []) or []:
        if not isinstance(context, dict):
            continue

        resolved = str(context.get("capability_id") or "").strip()
        if resolved:
            values.add(resolved)

        retrieval = context.get("retrieval", {}) or {}
        for row in retrieval.get("candidates", []) or []:
            if isinstance(row, dict):
                capability_id = str(
                    row.get("capability_id") or ""
                ).strip()
                if capability_id:
                    values.add(capability_id)

        for sibling in context.get("atomic_siblings", []) or []:
            if isinstance(sibling, dict):
                capability_id = str(
                    sibling.get("capability_id") or ""
                ).strip()
                if capability_id:
                    values.add(capability_id)

    return sorted(values)


def _render_registry_resolution(
    candidate: dict[str, Any],
) -> None:
    registry = candidate.get("technology_registry_resolution", {}) or {}
    status = registry.get("status")

    if status == "resolved":
        st.success(
            "Technology registry resolved this candidate: "
            f"{registry.get('technology_label')} → "
            f"{registry.get('capability_id')} "
            f"({registry.get('reason')}). "
            "It is removed from the default manual-review queue."
        )
    elif status == "recognized_unmapped":
        st.info(
            "Technology registry recognizes "
            f"{registry.get('technology_label')}, but there is no approved "
            "canonical capability mapping yet. It stays in the review/research queue."
        )
    elif status == "ambiguous":
        st.warning(
            "Technology registry produced an ambiguous result. "
            "Keep this candidate in human review."
        )
    else:
        st.caption(
            "Technology registry: no exact approved alias match."
        )


def _render_observation(
    observation: dict[str, Any],
    context: dict[str, Any],
    *,
    index: int,
) -> None:
    with st.expander(
        f"Observation {index} · job {observation.get('discovered_job_id')}",
        expanded=index == 1,
    ):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Importance", str(observation.get("importance") or "—"))
        c2.metric(
            "Candidate match",
            str(observation.get("match_label") or "—"),
        )
        c3.metric(
            "Semantic type",
            str(context.get("semantic_type") or "—"),
        )
        c4.metric("Atomic", "Yes" if context.get("is_atomic") else "No")

        requirement = str(
            observation.get("requirement_text") or ""
        ).strip()
        parent = str(context.get("parent_text") or "").strip()

        st.markdown("**Requirement**")
        st.write(requirement or "—")
        if parent and parent != requirement:
            st.markdown("**Parent/source requirement**")
            st.info(parent)

        retrieval = context.get("retrieval", {}) or {}
        st.markdown("##### Shadow taxonomy retrieval")
        st.caption(
            "Diagnostic only. Lexical retrieval does not affect scoring "
            "and is not an automatic taxonomy decision."
        )
        top = retrieval.get("top_candidate") or {}
        r1, r2, r3 = st.columns(3)
        r1.metric(
            "Top capability",
            str(top.get("capability_id") or "None"),
        )
        score = top.get("lexical_score")
        r2.metric(
            "Lexical score",
            (
                f"{float(score):.3f}"
                if isinstance(score, (int, float))
                else "—"
            ),
        )
        r3.metric(
            "Exact capability",
            str(retrieval.get("exact_capability_id") or "None"),
        )

        if retrieval.get("candidates"):
            with st.expander("Retrieval candidates", expanded=False):
                st.dataframe(
                    retrieval["candidates"],
                    width="stretch",
                    hide_index=True,
                )

        siblings = context.get("atomic_siblings", []) or []
        if siblings:
            with st.expander(
                f"Atomic/source siblings ({len(siblings)})",
                expanded=False,
            ):
                st.dataframe(
                    siblings,
                    width="stretch",
                    hide_index=True,
                )

        with st.expander("Raw diagnostics", expanded=False):
            st.json(
                {
                    "observation": observation,
                    "context": context,
                }
            )


def render_capability_discovery_review() -> None:
    st.divider()
    st.header("Capability Discovery")
    st.caption(
        f"TQ-D2.5/TQ-D2.6/TQ-D2.7 · {TRIAGE_VERSION} · technology registry "
        "+ deterministic diagnostics + explicit human review. "
        "No taxonomy mutation and no Tavily calls."
    )

    try:
        report = build_triage_report()
    except Exception as exc:
        st.error(f"Unable to build Capability Discovery report: {exc}")
        return

    candidates = [
        row
        for row in report.get("candidates", []) or []
        if isinstance(row, dict)
    ]
    deterministic_suggestions = {
        str(row.get("candidate_id") or ""): (
            build_deterministic_suggestion(row)
        )
        for row in candidates
        if str(row.get("candidate_id") or "")
    }

    ai_key = "taxonomy_discovery_ai_suggestions_registry_v1"
    ai_suggestions = st.session_state.setdefault(ai_key, {})

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Raw candidates", int(report.get("candidate_count") or 0))
    m2.metric(
        "Registry resolved",
        int(report.get("registry_resolved_candidate_count") or 0),
    )
    m3.metric(
        "Human reviewed",
        int(report.get("human_reviewed_queue_count") or 0),
        help=(
            "Confirmed human decisions among candidates that were eligible "
            "for the manual review queue."
        ),
    )
    m4.metric(
        "Needs review",
        int(
            report.get("pending_human_review_candidate_count")
            if report.get("pending_human_review_candidate_count") is not None
            else report.get("manual_review_queue_count")
            or 0
        ),
        help=(
            "Registry-unresolved candidates that still have triage status "
            "unreviewed. This number drops after a review is confirmed."
        ),
    )

    (
        overview_tab,
        registry_tab,
        research_tab,
        debug_tab,
    ) = st.tabs(
        [
            "Review Queue",
            "Technology Registry",
            "Research Proposals",
            "Debug / Export",
        ]
    )

    selected_candidate: dict[str, Any] | None = None
    selected_statuses: list[str] = ["unreviewed"]
    queue = "Needs human review"
    search_text = ""

    with overview_tab:
        high_confidence = [
            row
            for row in candidates
            if (
                (
                    row.get("technology_registry_resolution", {})
                    or {}
                ).get("status")
                != "resolved"
                and deterministic_suggestions.get(
                    str(row.get("candidate_id") or ""),
                    {},
                ).get("confidence")
                == "high"
                and deterministic_suggestions.get(
                    str(row.get("candidate_id") or ""),
                    {},
                ).get("suggested_status")
                not in (None, "defer")
                and (
                    row.get("triage", {}) or {}
                ).get("status", "unreviewed")
                == "unreviewed"
            )
        ]

        with st.expander(
            "Assisted batch review · "
            f"{len(high_confidence)} high-confidence suggestion(s)",
            expanded=False,
        ):
            st.caption(
                "Nothing is saved automatically. Select only suggestions "
                "you agree with, then explicitly confirm the batch."
            )
            batch_lookup = {
                str(row.get("candidate_id") or ""): row
                for row in high_confidence
            }
            selected_batch = st.multiselect(
                "High-confidence suggestions",
                list(batch_lookup),
                format_func=lambda candidate_id: (
                    f"{_candidate_text(batch_lookup[candidate_id])} → "
                    f"{deterministic_suggestions[candidate_id].get('suggested_status')}"
                    + (
                        " → "
                        + str(
                            deterministic_suggestions[candidate_id].get(
                                "suggested_target_capability_id"
                            )
                        )
                        if deterministic_suggestions[candidate_id].get(
                            "suggested_target_capability_id"
                        )
                        else ""
                    )
                ),
            )
            if st.button(
                "Accept selected suggestions",
                disabled=not selected_batch,
            ):
                for candidate_id in selected_batch:
                    row = batch_lookup[candidate_id]
                    suggestion = deterministic_suggestions[candidate_id]
                    save_review(
                        candidate_id=candidate_id,
                        taxonomy_version=str(
                            row.get("taxonomy_version")
                            or report.get("taxonomy_version")
                            or ""
                        ),
                        triage_status=str(
                            suggestion.get("suggested_status") or "defer"
                        ),
                        target_capability_id=(
                            suggestion.get(
                                "suggested_target_capability_id"
                            )
                        ),
                        notes=(
                            "Accepted deterministic assisted suggestion "
                            f"{ASSISTED_REVIEW_VERSION}: "
                            + " | ".join(
                                suggestion.get("reasons", []) or []
                            )
                        ),
                    )
                st.success(
                    f"Saved {len(selected_batch)} confirmed review(s)."
                )
                st.rerun()

        f1, f2, f3 = st.columns([2, 2, 3])
        with f1:
            selected_statuses = st.multiselect(
                "Review status",
                list(TRIAGE_STATUSES),
                default=["unreviewed"],
                format_func=lambda value: STATUS_LABELS.get(
                    value,
                    value,
                ),
            )
        with f2:
            queue = st.selectbox("Queue", QUEUE_OPTIONS)
        with f3:
            search_text = st.text_input(
                "Search",
                placeholder="Kafka, React, degree, experience...",
            )

        needle = search_text.strip().lower()
        filtered: list[dict[str, Any]] = []
        for candidate in candidates:
            triage = candidate.get("triage", {}) or {}
            registry_status = (
                candidate.get("technology_registry_resolution", {})
                or {}
            ).get("status")

            # Registry-resolved candidates are hidden from the normal human
            # review queue even though their persisted triage status remains
            # "unreviewed". They can still be inspected through the all-candidates queue.
            if (
                queue != "All candidates including registry-resolved"
                and registry_status == "resolved"
            ):
                continue

            status = str(triage.get("status") or "unreviewed")
            if (
                selected_statuses
                and status not in selected_statuses
                and registry_status != "resolved"
            ):
                continue
            if not _matches_queue(candidate, queue):
                continue
            if (
                needle
                and needle not in _candidate_text(candidate).lower()
            ):
                continue
            filtered.append(candidate)

        st.caption(
            f"{len(filtered)} candidate(s) in the current queue."
        )
        st.dataframe(
            [
                {
                    "candidate": _candidate_text(row),
                    "registry_status": (
                        row.get("technology_registry_resolution", {})
                        or {}
                    ).get("status"),
                    "registry_target": (
                        row.get("technology_registry_resolution", {})
                        or {}
                    ).get("capability_id"),
                    "review_status": (
                        row.get("triage", {}) or {}
                    ).get("status"),
                    "suggestion": deterministic_suggestions.get(
                        str(row.get("candidate_id") or ""),
                        {},
                    ).get("suggested_status"),
                    "confidence": deterministic_suggestions.get(
                        str(row.get("candidate_id") or ""),
                        {},
                    ).get("confidence"),
                }
                for row in filtered
            ],
            width="stretch",
            hide_index=True,
        )

        if not filtered:
            st.info("No candidates match the current filters.")
        else:
            selected_index = st.selectbox(
                "Inspect candidate",
                range(len(filtered)),
                format_func=lambda index: _candidate_label(
                    filtered[index]
                ),
            )
            selected_candidate = filtered[int(selected_index)]
            candidate = selected_candidate
            candidate_id = str(
                candidate.get("candidate_id") or ""
            )
            triage = candidate.get("triage", {}) or {}
            suggestion = deterministic_suggestions[candidate_id]

            st.divider()
            st.subheader(_candidate_text(candidate))
            _render_registry_resolution(candidate)

            st.markdown("### Assisted suggestion")
            if suggestion.get("routing") == "registry_resolved":
                st.caption(
                    "No manual review is required for this candidate under "
                    "the current approved registry relationship."
                )
            else:
                s1, s2, s3 = st.columns(3)
                s1.metric(
                    "Suggested status",
                    str(
                        suggestion.get("suggested_status")
                        or "No suggestion"
                    ),
                )
                s2.metric(
                    "Confidence",
                    str(suggestion.get("confidence") or "none"),
                )
                s3.metric(
                    "Suggested target",
                    str(
                        suggestion.get(
                            "suggested_target_capability_id"
                        )
                        or "None"
                    ),
                )
                for reason in suggestion.get("reasons", []) or []:
                    st.markdown(f"- {reason}")

                if (
                    suggestion.get("suggested_status")
                    not in (None, "defer")
                    and suggestion.get("confidence")
                    in {"high", "medium"}
                ):
                    if st.button(
                        "Accept deterministic suggestion",
                        key=f"accept_det_{candidate_id}",
                    ):
                        save_review(
                            candidate_id=candidate_id,
                            taxonomy_version=str(
                                candidate.get("taxonomy_version")
                                or report.get("taxonomy_version")
                                or ""
                            ),
                            triage_status=str(
                                suggestion.get("suggested_status")
                            ),
                            target_capability_id=(
                                suggestion.get(
                                    "suggested_target_capability_id"
                                )
                            ),
                            notes=(
                                "Accepted deterministic suggestion "
                                f"{ASSISTED_REVIEW_VERSION}: "
                                + " | ".join(
                                    suggestion.get("reasons", []) or []
                                )
                            ),
                        )
                        st.rerun()

            flags = candidate.get("diagnostic_flags", []) or []
            if flags:
                st.markdown("**Deterministic diagnostic signals**")
                st.code(
                    " · ".join(str(flag) for flag in flags),
                    language=None,
                )

            observations = candidate.get("observations", []) or []
            contexts = candidate.get("observation_contexts", []) or []
            for index, (observation, context) in enumerate(
                zip(observations, contexts),
                start=1,
            ):
                if isinstance(observation, dict) and isinstance(context, dict):
                    _render_observation(
                        observation,
                        context,
                        index=index,
                    )

            registry_status = (
                candidate.get("technology_registry_resolution", {})
                or {}
            ).get("status")

            if registry_status != "resolved":
                with st.expander(
                    "Optional local-Ollama second opinion",
                    expanded=False,
                ):
                    local_models = local_ollama_models()
                    if not local_models:
                        st.info(
                            "No local Ollama model is configured in the model catalogue."
                        )
                    else:
                        labels = list(local_models)
                        label = st.selectbox(
                            "Local Ollama model",
                            labels,
                            key=f"ollama_model_{candidate_id}",
                        )
                        model = local_models[label]
                        st.caption(
                            "This is advisory only. It cannot save a review "
                            "or mutate the taxonomy unless you explicitly accept it."
                        )
                        if st.button(
                            "Ask Ollama for second opinion",
                            key=f"ask_ollama_{candidate_id}",
                        ):
                            try:
                                with st.spinner(
                                    "Asking local Ollama..."
                                ):
                                    ai_suggestions[candidate_id] = (
                                        ask_local_ai_suggestion(
                                            candidate,
                                            model=model,
                                            deterministic_suggestion=suggestion,
                                        )
                                    )
                                st.session_state[ai_key] = ai_suggestions
                                st.rerun()
                            except Exception as exc:
                                st.error(
                                    f"Local AI suggestion failed: {exc}"
                                )

                        ai = ai_suggestions.get(candidate_id)
                        if isinstance(ai, dict):
                            st.json(ai)
                            if st.button(
                                "Accept Ollama suggestion",
                                key=f"accept_ollama_{candidate_id}",
                            ):
                                save_review(
                                    candidate_id=candidate_id,
                                    taxonomy_version=str(
                                        candidate.get("taxonomy_version")
                                        or report.get("taxonomy_version")
                                        or ""
                                    ),
                                    triage_status=str(
                                        ai.get("suggested_status")
                                        or "defer"
                                    ),
                                    target_capability_id=(
                                        ai.get(
                                            "suggested_target_capability_id"
                                        )
                                    ),
                                    notes=(
                                        "Accepted local-Ollama suggestion "
                                        f"{ai.get('model')}: "
                                        + " | ".join(
                                            ai.get("reasons", []) or []
                                        )
                                    ),
                                )
                                st.rerun()

                st.divider()
                st.markdown("### Human review")
                current_status = str(
                    triage.get("status") or "unreviewed"
                )
                status_index = (
                    list(TRIAGE_STATUSES).index(current_status)
                    if current_status in TRIAGE_STATUSES
                    else 0
                )

                target_options = _target_options(candidate)
                taxonomy_query = st.text_input(
                    "Search full taxonomy",
                    placeholder="messaging, container, frontend...",
                    key=f"taxonomy_search_{candidate_id}",
                )
                matches = search_taxonomy(taxonomy_query)
                if matches:
                    st.dataframe(
                        matches,
                        width="stretch",
                        hide_index=True,
                    )
                    for row in matches:
                        capability_id = str(
                            row.get("capability_id") or ""
                        )
                        if (
                            capability_id
                            and capability_id not in target_options
                        ):
                            target_options.append(capability_id)
                    target_options.sort()

                current_target = str(
                    triage.get("target_capability_id") or ""
                ).strip()
                if (
                    current_target
                    and current_target not in target_options
                ):
                    target_options.append(current_target)
                    target_options.sort()

                choices = (
                    [""] + target_options + ["Other / manual entry"]
                )
                current_target_index = (
                    choices.index(current_target)
                    if current_target in choices
                    else 0
                )

                with st.form(
                    f"human_review_{candidate_id}"
                ):
                    status = st.selectbox(
                        "Review status",
                        list(TRIAGE_STATUSES),
                        index=status_index,
                        format_func=lambda value: STATUS_LABELS.get(
                            value,
                            value,
                        ),
                    )
                    target_choice = st.selectbox(
                        "Target capability",
                        choices,
                        index=current_target_index,
                        help=(
                            "Required only for Existing taxonomy near miss."
                        ),
                    )
                    manual_target = ""
                    if target_choice == "Other / manual entry":
                        manual_target = st.text_input(
                            "Manual target capability ID"
                        )
                    notes = st.text_area(
                        "Review notes",
                        value=str(triage.get("notes") or ""),
                    )
                    submitted = st.form_submit_button("Save review")

                if submitted:
                    target = (
                        manual_target.strip()
                        if target_choice == "Other / manual entry"
                        else target_choice.strip()
                    )
                    try:
                        save_review(
                            candidate_id=candidate_id,
                            taxonomy_version=str(
                                candidate.get("taxonomy_version")
                                or report.get("taxonomy_version")
                                or ""
                            ),
                            triage_status=status,
                            target_capability_id=target,
                            notes=notes,
                        )
                    except Exception as exc:
                        st.error(f"Review not saved: {exc}")
                    else:
                        st.rerun()

                if triage.get("reviewed_at"):
                    if st.button(
                        "Clear persisted review",
                        key=f"clear_review_{candidate_id}",
                    ):
                        delete_review(
                            candidate_id,
                            str(
                                candidate.get("taxonomy_version")
                                or report.get("taxonomy_version")
                                or ""
                            ),
                        )
                        st.rerun()

    with registry_tab:
        rows = registry_rows()
        r1, r2, r3 = st.columns(3)
        r1.metric("Registry entries", len(rows))
        r2.metric(
            "Mapped entries",
            sum(1 for row in rows if row["mapping_status"] == "mapped"),
        )
        r3.metric(
            "Recognized / unmapped",
            sum(
                1
                for row in rows
                if row["mapping_status"] == "recognized_unmapped"
            ),
        )
        st.caption(
            "This is a conservative bootstrap registry, not an attempt to "
            "enumerate every modern technology. Only approved mappings can "
            "remove a candidate from the manual-review queue."
        )
        registry_search = st.text_input(
            "Search registry",
            placeholder="Kafka, React, container...",
        ).strip().lower()
        visible_rows = [
            row
            for row in rows
            if (
                not registry_search
                or registry_search
                in json.dumps(row, ensure_ascii=False).lower()
            )
        ]
        st.dataframe(
            visible_rows,
            width="stretch",
            hide_index=True,
        )

    with research_tab:
        st.subheader("TQ-D2.7 Research Proposals")
        st.caption(
            "Research output is untrusted proposal data. Importing it does "
            "not change the production registry. Only explicit proposal "
            "decisions can appear in a downloadable registry-vNext preview."
        )

        handover = build_research_handover(report)
        st.download_button(
            "Download research handover JSON",
            data=json.dumps(
                handover,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            file_name="technology_registry_research_handover.json",
            mime="application/json",
        )
        st.caption(
            "Use this handover in another ChatGPT/Tavily research session. "
            "Ask that session to return JSON conforming to the bundled "
            "research proposal schema."
        )

        uploaded = st.file_uploader(
            "Import researched proposal bundle",
            type=["json"],
            key="technology_registry_research_bundle",
        )
        if uploaded is not None:
            try:
                imported_payload = json.loads(
                    uploaded.getvalue().decode("utf-8")
                )
                validated_bundle = validate_proposal_bundle(
                    imported_payload
                )
                st.success(
                    "Proposal bundle validates against the current "
                    "taxonomy and registry versions."
                )
                if st.button(
                    "Persist imported proposals",
                    key="persist_technology_registry_proposals",
                ):
                    count = import_proposal_bundle(
                        validated_bundle
                    )
                    st.success(
                        f"Persisted {count} research proposal(s)."
                    )
                    st.rerun()
            except Exception as exc:
                st.error(f"Proposal bundle rejected: {exc}")

        proposals = list_proposals(
            proposal_bundle_version=PROPOSAL_CONTRACT_VERSION
        )
        proposal_reviews = list_proposal_reviews(
            proposal_bundle_version=PROPOSAL_CONTRACT_VERSION
        )
        review_index = {
            str(row.get("proposal_id") or ""): row
            for row in proposal_reviews
        }

        decision_counts = {
            decision: sum(
                1
                for row in proposal_reviews
                if row.get("decision") == decision
            )
            for decision in PROPOSAL_REVIEW_DECISIONS
        }
        reviewed_count = sum(
            value
            for decision, value in decision_counts.items()
            if decision != "unreviewed"
        )

        p1, p2, p3, p4, p5, p6 = st.columns(6)
        p1.metric("Imported", len(proposals))
        p2.metric(
            "Pending",
            max(0, len(proposals) - reviewed_count),
        )
        p3.metric(
            "Approved",
            decision_counts.get("approve_mapping", 0),
        )
        p4.metric(
            "Keep unmapped",
            decision_counts.get("keep_unmapped", 0),
        )
        p5.metric(
            "New capability",
            decision_counts.get(
                "new_capability_needed",
                0,
            ),
        )
        p6.metric(
            "Rejected",
            decision_counts.get("reject_proposal", 0),
        )

        if not proposals:
            st.info(
                "No researched proposal bundle has been imported yet. "
                "Download the handover JSON, research it externally, then "
                "import the returned proposal bundle here."
            )
        else:
            proposal_suggestions = {
                str(row.get("proposal_id") or ""): (
                    build_proposal_decision_suggestion(row)
                )
                for row in proposals
            }

            st.markdown("### Proposal review queue")
            st.caption(
                "Python recommendations are deterministic translations of "
                "the validated research classification. They use zero AI "
                "credits and never save without an explicit click."
            )

            q1, q2, q3 = st.columns([2, 2, 3])
            with q1:
                classification_filter = st.multiselect(
                    "Classification",
                    sorted(
                        {
                            str(
                                row.get(
                                    "proposal_classification"
                                )
                                or ""
                            )
                            for row in proposals
                        }
                    ),
                    default=[],
                    placeholder="All classifications",
                )
            with q2:
                decision_filter = st.multiselect(
                    "Current decision",
                    list(PROPOSAL_REVIEW_DECISIONS),
                    default=[],
                    placeholder="All decisions",
                )
            with q3:
                proposal_search = st.text_input(
                    "Search proposals",
                    placeholder=(
                        "Pulsar, CI/CD, MongoDB, observability..."
                    ),
                    key="technology_registry_proposal_search",
                )

            needle = proposal_search.strip().lower()
            filtered_proposals: list[dict[str, Any]] = []
            for row in proposals:
                pid = str(row.get("proposal_id") or "")
                classification = str(
                    row.get("proposal_classification") or ""
                )
                current = str(
                    review_index.get(pid, {}).get(
                        "decision",
                        "unreviewed",
                    )
                )
                if (
                    classification_filter
                    and classification not in classification_filter
                ):
                    continue
                if (
                    decision_filter
                    and current not in decision_filter
                ):
                    continue
                if needle and needle not in json.dumps(
                    row,
                    ensure_ascii=False,
                ).lower():
                    continue
                filtered_proposals.append(row)

            grid_rows: list[dict[str, Any]] = []
            for row in filtered_proposals:
                pid = str(row.get("proposal_id") or "")
                suggestion = proposal_suggestions[pid]
                current = str(
                    review_index.get(pid, {}).get(
                        "decision",
                        "unreviewed",
                    )
                )
                grid_rows.append(
                    {
                        "select": False,
                        "proposal_id": pid,
                        "technology": str(row.get("label") or ""),
                        "classification": str(
                            row.get(
                                "proposal_classification"
                            )
                            or ""
                        ),
                        "proposed_target": str(
                            row.get("proposed_capability_id")
                            or ""
                        ),
                        "research_confidence": float(
                            row.get("confidence") or 0.0
                        ),
                        "current_decision": current,
                        "python_recommendation": str(
                            suggestion.get(
                                "suggested_decision"
                            )
                            or "unreviewed"
                        ),
                        "python_confidence": str(
                            suggestion.get("confidence") or ""
                        ),
                    }
                )

            if not grid_rows:
                st.info(
                    "No proposals match the current filters."
                )
            else:
                use_all_recommended = st.checkbox(
                    (
                        "Select all filtered, unreviewed proposals "
                        "that have a Python recommendation"
                    ),
                    value=False,
                    key="technology_registry_select_all_recommended",
                    help=(
                        "This visibly checks every currently filtered row "
                        "that is still unreviewed and has a deterministic "
                        "Python recommendation. Already-reviewed proposals "
                        "are never bulk-overwritten."
                    ),
                )

                auto_selectable_ids = {
                    str(row["proposal_id"])
                    for row in grid_rows
                    if (
                        row["python_recommendation"] != "unreviewed"
                        and row["current_decision"] == "unreviewed"
                    )
                }

                # Make the bulk selection visible in the table itself.
                # A separate editor key per filtered proposal set prevents
                # checkbox edits from one filter from leaking into another.
                for row in grid_rows:
                    row["select"] = bool(
                        use_all_recommended
                        and str(row["proposal_id"])
                        in auto_selectable_ids
                    )

                grid_signature = hashlib.sha256(
                    "\n".join(
                        str(row["proposal_id"])
                        for row in grid_rows
                    ).encode("utf-8")
                ).hexdigest()[:12]
                selection_mode = (
                    "bulk" if use_all_recommended else "manual"
                )

                grid_df = pd.DataFrame(grid_rows)
                edited_grid = st.data_editor(
                    grid_df,
                    width="stretch",
                    hide_index=True,
                    disabled=[
                        "proposal_id",
                        "technology",
                        "classification",
                        "proposed_target",
                        "research_confidence",
                        "current_decision",
                        "python_recommendation",
                        "python_confidence",
                    ],
                    column_config={
                        "select": st.column_config.CheckboxColumn(
                            "Select",
                            help=(
                                "Select proposals for an explicit "
                                "bulk review action."
                            ),
                        ),
                        "proposal_id": None,
                    },
                    key=(
                        "technology_registry_proposal_review_grid_"
                        f"{selection_mode}_{grid_signature}"
                    ),
                )

                selected_ids = [
                    str(row["proposal_id"])
                    for _, row in edited_grid.iterrows()
                    if bool(row["select"])
                ]
                actionable_selected_ids = [
                    pid
                    for pid in selected_ids
                    if (
                        str(
                            review_index.get(pid, {}).get(
                                "decision",
                                "unreviewed",
                            )
                        )
                        == "unreviewed"
                        and str(
                            proposal_suggestions.get(
                                pid,
                                {},
                            ).get(
                                "suggested_decision",
                                "unreviewed",
                            )
                        )
                        != "unreviewed"
                    )
                ]

                decision_summary: dict[str, int] = {}
                for pid in actionable_selected_ids:
                    decision = str(
                        proposal_suggestions[pid].get(
                            "suggested_decision"
                        )
                        or "unreviewed"
                    )
                    decision_summary[decision] = (
                        decision_summary.get(decision, 0) + 1
                    )

                if decision_summary:
                    summary_text = " · ".join(
                        f"{count} {decision}"
                        for decision, count in sorted(
                            decision_summary.items()
                        )
                    )
                    st.caption(
                        f"{len(selected_ids)} proposal(s) selected. "
                        f"{len(actionable_selected_ids)} actionable: "
                        f"{summary_text}"
                    )
                else:
                    st.caption(
                        f"{len(selected_ids)} proposal(s) selected. "
                        "No unreviewed Python recommendations are "
                        "currently actionable."
                    )

                if st.button(
                    (
                        "Apply Python-recommended decisions to "
                        f"{len(actionable_selected_ids)} selected"
                    ),
                    disabled=not actionable_selected_ids,
                    key="apply_python_proposal_recommendations",
                ):
                    applied = 0
                    skipped = (
                        len(selected_ids)
                        - len(actionable_selected_ids)
                    )
                    for pid in actionable_selected_ids:
                        suggestion = proposal_suggestions.get(
                            pid,
                            {},
                        )
                        suggested_decision = str(
                            suggestion.get(
                                "suggested_decision"
                            )
                            or "unreviewed"
                        )
                        save_proposal_review(
                            proposal_id=pid,
                            proposal_bundle_version=(
                                PROPOSAL_CONTRACT_VERSION
                            ),
                            decision=suggested_decision,
                            notes=(
                                "Accepted deterministic Python "
                                "proposal-review suggestion: "
                                + " | ".join(
                                    suggestion.get(
                                        "reasons",
                                        [],
                                    )
                                    or []
                                )
                            ),
                        )
                        applied += 1

                    st.success(
                        f"Saved {applied} explicit proposal decision(s); "
                        f"skipped {skipped} non-actionable selection(s)."
                    )
                    st.rerun()

            st.divider()
            st.markdown("### Proposal detail inspector")
            proposal_id = st.selectbox(
                "Inspect research proposal",
                [
                    str(row.get("proposal_id") or "")
                    for row in filtered_proposals
                ]
                or [
                    str(row.get("proposal_id") or "")
                    for row in proposals
                ],
                format_func=lambda value: next(
                    (
                        f"{row.get('label')} · "
                        f"{row.get('proposal_classification')}"
                        for row in proposals
                        if row.get("proposal_id") == value
                    ),
                    value,
                ),
                key="technology_registry_proposal_inspector",
            )
            proposal = next(
                row
                for row in proposals
                if row.get("proposal_id") == proposal_id
            )
            review = review_index.get(proposal_id, {})
            deterministic_proposal_suggestion = (
                proposal_suggestions[proposal_id]
            )

            a, b, c, d = st.columns(4)
            a.metric(
                "Classification",
                str(proposal.get("proposal_classification")),
            )
            b.metric(
                "Proposed target",
                str(
                    proposal.get("proposed_capability_id")
                    or "None"
                ),
            )
            c.metric(
                "Research confidence",
                str(proposal.get("confidence")),
            )
            d.metric(
                "Python recommendation",
                str(
                    deterministic_proposal_suggestion.get(
                        "suggested_decision"
                    )
                    or "unreviewed"
                ),
            )

            for reason in (
                deterministic_proposal_suggestion.get(
                    "reasons",
                    [],
                )
                or []
            ):
                st.markdown(f"- {reason}")

            st.markdown("**Research summary**")
            st.write(proposal.get("summary") or "—")
            st.markdown("**Aliases**")
            st.write(", ".join(proposal.get("aliases", []) or []))

            sources = proposal.get("sources", []) or []
            if sources:
                st.markdown("**Sources supplied by research**")
                st.dataframe(
                    sources,
                    width="stretch",
                    hide_index=True,
                )

            proposal_ai_key = (
                "technology_registry_proposal_ai_suggestions_v1"
            )
            proposal_ai_suggestions = (
                st.session_state.setdefault(
                    proposal_ai_key,
                    {},
                )
            )

            with st.expander(
                "Optional local-Ollama proposal second opinion",
                expanded=False,
            ):
                local_models = local_ollama_models()
                if not local_models:
                    st.info(
                        "No local Ollama model is configured."
                    )
                else:
                    model_label = st.selectbox(
                        "Local Ollama model",
                        list(local_models),
                        key=f"proposal_ollama_model_{proposal_id}",
                    )
                    model = local_models[model_label]
                    st.caption(
                        "This is advisory only and uses your local "
                        "Ollama runtime, not OpenAI credits."
                    )
                    if st.button(
                        "Ask Ollama to review this proposal",
                        key=f"ask_ollama_proposal_{proposal_id}",
                    ):
                        try:
                            with st.spinner(
                                "Asking local Ollama..."
                            ):
                                proposal_ai_suggestions[
                                    proposal_id
                                ] = ask_local_ai_proposal_review(
                                    proposal,
                                    model=model,
                                    deterministic_suggestion=(
                                        deterministic_proposal_suggestion
                                    ),
                                )
                            st.session_state[
                                proposal_ai_key
                            ] = proposal_ai_suggestions
                            st.rerun()
                        except Exception as exc:
                            st.error(
                                f"Local proposal AI review failed: {exc}"
                            )

                    ai_result = proposal_ai_suggestions.get(
                        proposal_id
                    )
                    if isinstance(ai_result, dict):
                        st.json(ai_result)
                        if st.button(
                            "Accept Ollama proposal decision",
                            key=f"accept_ollama_proposal_{proposal_id}",
                        ):
                            save_proposal_review(
                                proposal_id=proposal_id,
                                proposal_bundle_version=(
                                    PROPOSAL_CONTRACT_VERSION
                                ),
                                decision=str(
                                    ai_result.get(
                                        "suggested_decision"
                                    )
                                    or "unreviewed"
                                ),
                                notes=(
                                    "Accepted local-Ollama proposal "
                                    "review suggestion "
                                    f"{ai_result.get('model')}: "
                                    + " | ".join(
                                        ai_result.get(
                                            "reasons",
                                            [],
                                        )
                                        or []
                                    )
                                ),
                            )
                            st.rerun()

            current_decision = str(
                review.get("decision") or "unreviewed"
            )
            decision_values = list(
                PROPOSAL_REVIEW_DECISIONS
            )
            decision_index = (
                decision_values.index(current_decision)
                if current_decision in decision_values
                else 0
            )

            with st.form(
                f"proposal_review_{proposal_id}"
            ):
                decision = st.selectbox(
                    "Proposal decision",
                    decision_values,
                    index=decision_index,
                )
                notes = st.text_area(
                    "Proposal review notes",
                    value=str(review.get("notes") or ""),
                )
                save_proposal = st.form_submit_button(
                    "Save proposal decision"
                )

            if save_proposal:
                if (
                    decision == "approve_mapping"
                    and proposal.get("proposal_classification")
                    != "safe_mapping_candidate"
                ):
                    st.error(
                        "Only safe_mapping_candidate proposals can be "
                        "approved as deterministic mappings."
                    )
                else:
                    save_proposal_review(
                        proposal_id=proposal_id,
                        proposal_bundle_version=(
                            PROPOSAL_CONTRACT_VERSION
                        ),
                        decision=decision,
                        notes=notes,
                    )
                    st.rerun()

            preview = build_registry_vnext_preview(
                proposals,
                list_proposal_reviews(
                    proposal_bundle_version=(
                        PROPOSAL_CONTRACT_VERSION
                    )
                ),
            )
            st.download_button(
                "Download registry vNext preview JSON",
                data=json.dumps(
                    preview,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                file_name=(
                    "technology_registry_vnext_preview.json"
                ),
                mime="application/json",
            )
            st.caption(
                "Preview only. It contains only explicitly approved "
                "mapping proposals plus the existing production registry. "
                "Downloading it does not change technology_registry_v1.json."
            )

    with debug_tab:
        ui_state = {
            "review_status_filter": list(selected_statuses),
            "queue": queue,
            "search": search_text,
            "selected_candidate_id": (
                str(selected_candidate.get("candidate_id") or "")
                if selected_candidate
                else None
            ),
        }
        persisted_reviews = list_reviews(
            taxonomy_version=str(
                report.get("taxonomy_version") or ""
            )
        )
        debug_zip = build_debug_bundle(
            report=report,
            deterministic_suggestions=deterministic_suggestions,
            ai_suggestions=(
                ai_suggestions
                if isinstance(ai_suggestions, dict)
                else {}
            ),
            persisted_reviews=persisted_reviews,
            ui_state=ui_state,
            selected_candidate=selected_candidate,
            research_proposals=list_proposals(
                proposal_bundle_version=PROPOSAL_CONTRACT_VERSION
            ),
            proposal_reviews=list_proposal_reviews(
                proposal_bundle_version=PROPOSAL_CONTRACT_VERSION
            ),
        )
        st.download_button(
            "Download full discovery debug ZIP",
            data=debug_zip,
            file_name="capability_discovery_debug_bundle.zip",
            mime="application/zip",
        )

        if selected_candidate is not None:
            candidate_id = str(
                selected_candidate.get("candidate_id") or ""
            )
            payload = {
                "candidate": selected_candidate,
                "deterministic_suggestion": (
                    deterministic_suggestions.get(candidate_id)
                ),
                "ai_suggestion": (
                    ai_suggestions.get(candidate_id)
                    if isinstance(ai_suggestions, dict)
                    else None
                ),
                "ui_state": ui_state,
            }
            st.download_button(
                "Download current candidate debug JSON",
                data=json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                file_name=(
                    f"capability_discovery_candidate_{candidate_id}.json"
                ),
                mime="application/json",
            )

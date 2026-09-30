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
from taxonomy_discovery.classification import (
    CLASSIFICATION_CLASSES,
    CLASSIFICATION_VERSION,
    build_classification_report,
)
from taxonomy_discovery.research_targets import (
    RESEARCH_TARGET_TYPES,
    RESEARCH_TARGET_VERSION,
    TARGET_CAPABILITY_CONCEPT,
    TARGET_TECHNOLOGY_IDENTITY,
    TARGET_TECHNOLOGY_RELATIONSHIP,
    build_research_target_report,
)

PATCH_MARKER = "tqd2.6-technology-registry-ui-v1"
TQD3_UI_MARKER = "tqd3-classification-readonly-ui-v1.1.0"
TQD3_RESEARCH_TARGET_UI_MARKER = "tqd3-research-target-readonly-ui-v1.2.0"
TQD3_RESEARCH_TARGET_SELECTION_UI_MARKER = "tqd3-research-target-clickable-table-v1.2.2"

TQD3_CLASS_LABELS = {
    "A_existing_capability_near_miss": "A · Existing capability near miss",
    "B_technology_or_registry": "B · Technology / registry",
    "C_decomposition_or_structure": "C · Decomposition / JD structure",
    "D_subjective_or_defer": "D · Subjective / defer",
    "E_new_capability_research_candidate": "E · New capability research candidate",
    "U_unclassified": "U · Unclassified",
}

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



def _markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""

    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            key_text = str(key)
            if key_text not in seen:
                seen.add(key_text)
                columns.append(key_text)

    def cell(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list, tuple, set)):
            text = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
            )
        else:
            text = str(value)
        return (
            text.replace("\\", "\\\\")
            .replace("|", "\\|")
            .replace("\r", " ")
            .replace("\n", "<br>")
        )

    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| "
        + " | ".join(cell(row.get(column)) for column in columns)
        + " |"
        for row in rows
    ]
    return "\n".join([header, divider, *body]) + "\n"


def _render_readonly_selection_export(
    *,
    summary_rows: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
    key_prefix: str,
    filename_stem: str,
) -> None:
    if not summary_rows:
        return

    summary_df = pd.DataFrame(summary_rows)
    csv_data = summary_df.to_csv(index=False)
    markdown_data = _markdown_table(summary_rows)
    html_data = summary_df.to_html(index=False, escape=True)
    json_data = (
        json.dumps(
            raw_rows,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    with st.expander(
        "Selected rows · debug / export",
        expanded=False,
    ):
        st.caption(
            "Local download only. Exporting does not review, research, "
            "mutate, score, or call any model/network service."
        )
        e1, e2, e3, e4 = st.columns(4)
        e1.download_button(
            "CSV",
            data=csv_data,
            file_name=f"{filename_stem}.csv",
            mime="text/csv",
            key=f"{key_prefix}_csv",
        )
        e2.download_button(
            "Markdown",
            data=markdown_data,
            file_name=f"{filename_stem}.md",
            mime="text/markdown",
            key=f"{key_prefix}_markdown",
        )
        e3.download_button(
            "HTML",
            data=html_data,
            file_name=f"{filename_stem}.html",
            mime="text/html",
            key=f"{key_prefix}_html",
        )
        e4.download_button(
            "Full JSON",
            data=json_data,
            file_name=f"{filename_stem}.json",
            mime="application/json",
            key=f"{key_prefix}_json",
        )

        with st.expander(
            "Preview selected full records",
            expanded=False,
        ):
            st.json(raw_rows)


_REVIEW_DECISION_GUIDE = [
    {
        "decision": "Existing taxonomy near miss",
        "choose_when": (
            "One existing canonical capability clearly expresses the same "
            "reusable concept and the miss is mainly terminology/matching."
        ),
        "avoid_when": (
            "Several capabilities are similarly plausible, the wording is "
            "broader/narrower in meaning, or the item is mainly a technology."
        ),
        "effect": (
            "Save an existing capability target for matcher/terminology "
            "improvement; do not create a new capability."
        ),
    },
    {
        "decision": "Research candidate",
        "choose_when": (
            "The requirement appears to describe a reusable technical/work "
            "capability that is materially absent from the current taxonomy."
        ),
        "avoid_when": (
            "It is primarily a product/framework/tool, subjective wording, "
            "a parser/decomposition problem, or still too ambiguous."
        ),
        "effect": (
            "Route for downstream research/proposal work. Saving the review "
            "does not itself mutate the taxonomy or scoring."
        ),
    },
    {
        "decision": "Decomposition issue",
        "choose_when": (
            "The JD structure/parser combined unrelated requirements, split "
            "one requirement incorrectly, or admitted the wrong text."
        ),
        "avoid_when": (
            "The requirement text itself is coherent and the problem is only "
            "taxonomy terminology or missing knowledge."
        ),
        "effect": (
            "Route to JD-structure/decomposition work rather than taxonomy "
            "growth."
        ),
    },
    {
        "decision": "Scope review",
        "choose_when": (
            "The wording is subjective, administrative, eligibility-related, "
            "or needs a policy decision about whether it belongs in taxonomy."
        ),
        "avoid_when": (
            "There is already a clear technical capability or technology "
            "routing decision."
        ),
        "effect": (
            "Hold for explicit human policy/scope judgment; no production "
            "knowledge is changed."
        ),
    },
    {
        "decision": "Defer",
        "choose_when": (
            "Evidence is weak, one-off, ambiguous, tied between plausible "
            "routes, or there is not enough information to justify a change."
        ),
        "avoid_when": (
            "A clear existing-capability, decomposition, scope, or research "
            "route is already supported."
        ),
        "effect": (
            "Leave unresolved for now. Defer is a valid conservative outcome, "
            "not a failure."
        ),
    },
]


def _candidate_recurrence(candidate: dict[str, Any]) -> tuple[int, int]:
    observations = [
        row
        for row in candidate.get("observations", []) or []
        if isinstance(row, dict)
    ]
    explicit_jobs = candidate.get("job_count")
    explicit_observations = candidate.get("observation_count")
    job_ids = {
        str(row.get("discovered_job_id"))
        for row in observations
        if row.get("discovered_job_id") is not None
    }
    job_count = (
        int(explicit_jobs)
        if isinstance(explicit_jobs, (int, float))
        else len(job_ids)
    )
    observation_count = (
        int(explicit_observations)
        if isinstance(explicit_observations, (int, float))
        else len(observations)
    )
    return job_count, observation_count


def _render_reviewer_guidance(
    candidate: dict[str, Any],
    suggestion: dict[str, Any],
    tqd3_classification: dict[str, Any] | None,
) -> None:
    classification = (
        tqd3_classification
        if isinstance(tqd3_classification, dict)
        else {}
    )
    class_id = str(classification.get("class_id") or "")
    class_label = TQD3_CLASS_LABELS.get(
        class_id,
        class_id or "Not classified",
    )

    registry = (
        candidate.get("technology_registry_resolution", {})
        or {}
    )
    registry_status = str(registry.get("status") or "unresolved")
    registry_target = str(
        registry.get("capability_id")
        or registry.get("technology_id")
        or ""
    )
    job_count, observation_count = _candidate_recurrence(candidate)
    lexical_score = _top_lexical_score(candidate)
    flags = [
        str(value)
        for value in candidate.get("diagnostic_flags", []) or []
    ]

    with st.expander(
        "Reviewer Guidance · how to decide",
        expanded=True,
    ):
        st.caption(
            "The goal is not to decide whether a requirement is 'good' or "
            "'bad'. Decide which downstream route is justified by the "
            "evidence. When evidence is ambiguous, Defer is valid."
        )

        g1, g2, g3, g4 = st.columns(4)
        g1.metric("TQ-D3 route", class_label)
        g2.metric(
            "Python suggestion",
            str(
                suggestion.get("suggested_status")
                or "No suggestion"
            ),
        )
        g3.metric(
            "Suggestion confidence",
            str(suggestion.get("confidence") or "none"),
        )
        g4.metric(
            "Seen",
            f"{job_count} job(s) / {observation_count} obs",
        )

        st.dataframe(
            [
                {
                    "signal": "Technology registry",
                    "value": (
                        registry_status
                        + (
                            f" → {registry_target}"
                            if registry_target
                            else ""
                        )
                    ),
                },
                {
                    "signal": "Top lexical retrieval",
                    "value": (
                        f"{lexical_score:.3f}"
                        if isinstance(lexical_score, float)
                        else "None"
                    ),
                },
                {
                    "signal": "Diagnostic flags",
                    "value": ", ".join(flags) if flags else "None",
                },
            ],
            width="stretch",
            hide_index=True,
        )

        if class_id == "A_existing_capability_near_miss":
            st.info(
                "TQ-D3 sees a possible existing-capability near miss. "
                "Choose Existing taxonomy near miss only when one capability "
                "clearly preserves the requirement's meaning."
            )
        elif class_id == "B_technology_or_registry":
            st.warning(
                "TQ-D3 sees a technology/registry issue. Do not create a "
                "capability named after the product/framework/tool. Use the "
                "Research Targets / registry relationship path when needed."
            )
        elif class_id == "C_decomposition_or_structure":
            st.warning(
                "TQ-D3 sees a likely JD decomposition/structure issue. "
                "Prefer Decomposition issue rather than growing taxonomy."
            )
        elif class_id == "D_subjective_or_defer":
            st.info(
                "TQ-D3 sees subjective/general wording. Prefer Scope review "
                "or Defer unless concrete reusable technical meaning is "
                "independently supported."
            )
        elif class_id == "E_new_capability_research_candidate":
            st.info(
                "TQ-D3 sees a recurrent candidate for research. Confirm that "
                "it is reusable, materially distinct from existing taxonomy, "
                "and not merely a technology name before choosing Research "
                "candidate."
            )
        elif class_id == "U_unclassified":
            st.warning(
                "TQ-D3 intentionally failed closed. Do not guess. Inspect "
                "retrieval/registry evidence and Defer if no route is clearly "
                "supported."
            )

        st.markdown("**What makes a good review**")
        st.markdown(
            "- Preserve the meaning of the JD requirement; do not map only "
            "because a keyword overlaps.\n"
            "- Keep technology identity/relationship questions separate from "
            "canonical capabilities.\n"
            "- Do not use candidate résumé evidence to decide what the "
            "taxonomy means.\n"
            "- Require one clearly justified existing capability before using "
            "Existing taxonomy near miss.\n"
            "- Prefer Defer over inventing certainty from weak, tied, or "
            "one-off evidence."
        )

        st.markdown("**Decision guide**")
        suggested_status = str(
            suggestion.get("suggested_status") or ""
        )
        suggested_label = STATUS_LABELS.get(
            suggested_status,
            suggested_status,
        )
        for guide in _REVIEW_DECISION_GUIDE:
            decision = str(guide.get("decision") or "Decision")
            with st.expander(
                decision,
                expanded=bool(
                    suggested_label
                    and decision == suggested_label
                ),
            ):
                st.markdown("**Choose when**")
                st.write(str(guide.get("choose_when") or "—"))
                st.markdown("**Avoid when**")
                st.write(str(guide.get("avoid_when") or "—"))
                st.markdown("**Effect**")
                st.write(str(guide.get("effect") or "—"))

        st.caption(
            "Saving a human review records a routing decision. It does not "
            "directly mutate the canonical taxonomy/technology registry or "
            "change candidate scoring."
        )

def _render_tqd3_classification_tab(
    triage_report: dict[str, Any],
) -> None:
    st.subheader("TQ-D3 Unresolved Requirement Classification")
    st.caption(
        f"{CLASSIFICATION_VERSION} · deterministic read-only routing. "
        "No model/network calls, no taxonomy/registry mutation, "
        "and no scoring influence."
    )

    try:
        classification_report = build_classification_report(triage_report)
    except Exception as exc:
        st.error(f"Unable to build TQ-D3 classification report: {exc}")
        return

    governance = classification_report.get("governance", {}) or {}
    if any(
        (
            int(governance.get("model_calls", 0) or 0) != 0,
            int(governance.get("network_calls", 0) or 0) != 0,
            int(governance.get("taxonomy_mutations", 0) or 0) != 0,
            int(governance.get("registry_mutations", 0) or 0) != 0,
            bool(governance.get("scoring_influence", False)),
        )
    ):
        st.error(
            "TQ-D3 governance invariant failed; the read-only inspector "
            "will not render."
        )
        return

    rows = [
        row
        for row in classification_report.get("candidates", []) or []
        if isinstance(row, dict)
    ]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Persistent unresolved",
        int(
            classification_report.get(
                "persistent_unresolved_candidate_count", 0
            )
            or 0
        ),
    )
    m2.metric(
        "Research eligible",
        int(classification_report.get("research_queue_count", 0) or 0),
    )
    m3.metric(
        "Registry-resolved skipped",
        int(
            classification_report.get(
                "skipped_registry_resolved_count", 0
            )
            or 0
        ),
    )
    m4.metric(
        "Version",
        str(classification_report.get("classification_version") or "—"),
    )

    st.info(
        "Read-only diagnostic routing. A class is not an approved taxonomy "
        "or registry change. Research eligibility only means the candidate "
        "may enter the later research/mining queue."
    )

    counts = classification_report.get("class_counts", {}) or {}
    st.dataframe(
        [
            {
                "class": TQD3_CLASS_LABELS.get(class_id, class_id),
                "count": int(counts.get(class_id, 0) or 0),
            }
            for class_id in CLASSIFICATION_CLASSES
        ],
        width="stretch",
        hide_index=True,
    )

    f1, f2, f3 = st.columns([3, 2, 4])
    with f1:
        selected_classes = st.multiselect(
            "TQ-D3 classes (multi-select)",
            list(CLASSIFICATION_CLASSES),
            default=[],
            format_func=lambda value: TQD3_CLASS_LABELS.get(
                value, value
            ),
            placeholder="All classes",
            key="tqd3_class_filter",
        )
    with f2:
        research_filter = st.selectbox(
            "Research eligibility",
            ("All", "Eligible", "Not eligible"),
            key="tqd3_research_filter",
        )
    with f3:
        search_text = st.text_input(
            "Search TQ-D3",
            placeholder=(
                "troubleshoot, documentation, AngularJS, Agile..."
            ),
            key="tqd3_classification_search",
        )

    needle = search_text.strip().lower()
    filtered: list[dict[str, Any]] = []
    for candidate in rows:
        result = candidate.get("tqd3_classification", {}) or {}
        class_id = str(result.get("class_id") or "")
        eligible = bool(result.get("research_eligible", False))
        if selected_classes and class_id not in selected_classes:
            continue
        if research_filter == "Eligible" and not eligible:
            continue
        if research_filter == "Not eligible" and eligible:
            continue
        if (
            needle
            and needle
            not in json.dumps(
                candidate,
                ensure_ascii=False,
                sort_keys=True,
            ).lower()
        ):
            continue
        filtered.append(candidate)

    st.caption(
        f"{len(filtered)} classified candidate(s) match the current filters."
    )

    grid_rows: list[dict[str, Any]] = []
    for candidate in filtered:
        result = candidate.get("tqd3_classification", {}) or {}
        signals = result.get("signals", {}) or {}
        near_miss = signals.get("near_miss") or {}
        grid_rows.append(
            {
                "class": TQD3_CLASS_LABELS.get(
                    str(result.get("class_id") or ""),
                    str(result.get("class_id") or ""),
                ),
                "candidate": _candidate_text(candidate),
                "rule": str(result.get("rule_id") or ""),
                "research_eligible": bool(
                    result.get("research_eligible", False)
                ),
                "near_miss_target": str(
                    near_miss.get("capability_id") or ""
                ),
                "registry_technology": str(
                    signals.get("registry_technology_id") or ""
                ),
                "jobs": int(signals.get("job_count", 0) or 0),
                "observations": int(
                    signals.get("observation_count", 0) or 0
                ),
            }
        )

    if not grid_rows:
        st.info("No TQ-D3 candidates match the current filters.")
        return

    st.caption(
        "Select one or more candidates. One row opens the inspector; "
        "multiple rows show a read-only selection summary."
    )
    table_event = st.dataframe(
        grid_rows,
        width="stretch",
        hide_index=True,
        key="tqd3_classification_table",
        on_select="rerun",
        selection_mode="multi-row",
    )

    selection = getattr(table_event, "selection", None)
    if selection is None and isinstance(table_event, dict):
        selection = table_event.get("selection")

    if isinstance(selection, dict):
        selected_rows = list(selection.get("rows", []) or [])
    elif selection is not None:
        selected_rows = list(getattr(selection, "rows", []) or [])
    else:
        selected_rows = []

    if not selected_rows:
        st.info(
            "Select one or more TQ-D3 candidate rows above. Select exactly "
            "one row to inspect its details."
        )
        return

    valid_selected_rows = [
        int(index)
        for index in selected_rows
        if 0 <= int(index) < len(filtered)
    ]
    if len(valid_selected_rows) != len(selected_rows):
        st.warning(
            "One or more selected rows are no longer available under the "
            "current filters. Reselect the rows."
        )
        return

    if len(valid_selected_rows) > 1:
        selected_candidates = [
            filtered[index]
            for index in valid_selected_rows
        ]
        st.info(
            f"{len(selected_candidates)} TQ-D3 candidates selected. "
            "This is a read-only selection; no review, taxonomy, registry, "
            "or research action is performed."
        )
        selected_summary_rows = [
            {
                "class": TQD3_CLASS_LABELS.get(
                    str(
                        (row.get("tqd3_classification") or {}).get(
                            "class_id"
                        )
                        or ""
                    ),
                    str(
                        (row.get("tqd3_classification") or {}).get(
                            "class_id"
                        )
                        or ""
                    ),
                ),
                "candidate": _candidate_text(row),
                "research_eligible": bool(
                    (row.get("tqd3_classification") or {}).get(
                        "research_eligible",
                        False,
                    )
                ),
            }
            for row in selected_candidates
        ]
        st.dataframe(
            selected_summary_rows,
            width="stretch",
            hide_index=True,
        )
        _render_readonly_selection_export(
            summary_rows=selected_summary_rows,
            raw_rows=selected_candidates,
            key_prefix="tqd3_classification_selection",
            filename_stem="tqd3_classification_selection",
        )
        return

    candidate = filtered[valid_selected_rows[0]]
    result = candidate.get("tqd3_classification", {}) or {}
    signals = result.get("signals", {}) or {}

    st.divider()
    st.markdown(f"### {_candidate_text(candidate)}")
    d1, d2, d3, d4 = st.columns(4)
    class_id = str(result.get("class_id") or "")
    d1.metric(
        "TQ-D3 class",
        TQD3_CLASS_LABELS.get(class_id, class_id or "—"),
    )
    d2.metric(
        "Research eligible",
        "Yes" if result.get("research_eligible") else "No",
    )
    d3.metric(
        "Human review",
        "Required" if result.get("requires_human_review") else "No",
    )
    d4.metric(
        "Affects scoring",
        "Yes" if result.get("influences_scoring") else "No",
    )

    st.markdown("**Rule**")
    st.code(str(result.get("rule_id") or "—"), language=None)
    st.markdown("**Why this class**")
    st.write(str(result.get("rationale") or "—"))
    st.markdown("**Recommended next action**")
    st.write(str(result.get("next_action") or "—"))

    near_miss = signals.get("near_miss")
    if isinstance(near_miss, dict) and near_miss:
        st.markdown("**Existing-capability near-miss signal**")
        st.json(near_miss)

    aliases = signals.get("registry_alias_mentions") or []
    if aliases:
        st.markdown("**Technology-registry alias signals**")
        st.dataframe(aliases, width="stretch", hide_index=True)

    with st.expander("TQ-D3 deterministic signals", expanded=False):
        st.json(signals)

    with st.expander("Underlying discovery diagnostics", expanded=False):
        st.json(
            {
                "candidate_id": candidate.get("candidate_id"),
                "observed_terms": candidate.get("observed_terms"),
                "diagnostic_flags": candidate.get("diagnostic_flags", []),
                "technology_registry_resolution": candidate.get(
                    "technology_registry_resolution", {}
                ),
                "observations": candidate.get("observations", []),
                "observation_contexts": candidate.get(
                    "observation_contexts", []
                ),
            }
        )

def _render_tqd3_research_targets_tab(
    triage_report: dict[str, Any],
) -> None:
    st.subheader("TQ-D3 Research Targets")
    st.caption(
        f"{RESEARCH_TARGET_VERSION} · dry-run extraction of the exact "
        "research units that a later Tavily phase may consume. This tab "
        "makes zero Tavily/model/network calls and cannot mutate the "
        "taxonomy, registry, or scoring."
    )

    try:
        classification_report = build_classification_report(
            triage_report
        )
        target_report = build_research_target_report(
            classification_report
        )
    except Exception as exc:
        st.error(f"Unable to build TQ-D3 research-target report: {exc}")
        return

    governance = target_report.get("governance", {}) or {}
    if any(
        (
            int(governance.get("tavily_calls", 0) or 0) != 0,
            int(governance.get("model_calls", 0) or 0) != 0,
            int(governance.get("network_calls", 0) or 0) != 0,
            int(governance.get("taxonomy_mutations", 0) or 0) != 0,
            int(governance.get("registry_mutations", 0) or 0) != 0,
            bool(governance.get("scoring_influence", False)),
        )
    ):
        st.error(
            "TQ-D3 research-target governance invariant failed; "
            "the dry-run queue will not render."
        )
        return

    targets = [
        row
        for row in target_report.get("targets", []) or []
        if isinstance(row, dict)
    ]
    type_counts = target_report.get("type_counts", {}) or {}

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Research targets", len(targets))
    m2.metric(
        "Technology relationships",
        int(
            type_counts.get(
                TARGET_TECHNOLOGY_RELATIONSHIP,
                0,
            )
            or 0
        ),
    )
    m3.metric(
        "Technology identities",
        int(
            type_counts.get(
                TARGET_TECHNOLOGY_IDENTITY,
                0,
            )
            or 0
        ),
    )
    m4.metric(
        "Capability concepts",
        int(
            type_counts.get(
                TARGET_CAPABILITY_CONCEPT,
                0,
            )
            or 0
        ),
    )

    st.info(
        "Dry run only. A research target is a focused question for a later "
        "research phase, not approved production knowledge. Known mapped "
        "technologies are excluded; known unmapped technologies are reduced "
        "to relationship questions; strict unknown technical terms can be "
        "queued for identity research; E-class candidates become capability "
        "concept questions."
    )

    f1, f2 = st.columns([2, 4])
    with f1:
        selected_types = st.multiselect(
            "Target types (multi-select)",
            list(RESEARCH_TARGET_TYPES),
            default=[],
            placeholder="All target types",
            key="tqd3_target_type_filter",
        )
    with f2:
        search_text = st.text_input(
            "Search research targets",
            placeholder="Node.js, C#, SQL, documentation...",
            key="tqd3_research_target_search",
        )

    needle = search_text.strip().lower()
    filtered = []
    for row in targets:
        if (
            selected_types
            and row.get("target_type") not in selected_types
        ):
            continue
        if (
            needle
            and needle
            not in json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
            ).lower()
        ):
            continue
        filtered.append(row)

    st.caption(
        f"{len(filtered)} focused target(s) match the current filters."
    )
    display_rows = [
        {
            "target_type": row.get("target_type"),
            "label": row.get("label"),
            "routing_reason": row.get("routing_reason"),
            "source_class": row.get("source_class_id"),
            "source_candidates": len(
                row.get("source_candidate_ids", []) or []
            ),
            "source_jobs": row.get("source_job_count"),
            "source_observations": row.get(
                "source_observation_count"
            ),
            "tavily_eligible": row.get("tavily_eligible"),
        }
        for row in filtered
    ]

    if not display_rows:
        st.info("No research targets match the current filters.")
        return

    st.caption(
        "Select one or more rows. One row opens the inspector; multiple "
        "rows show a read-only batch summary for the future Tavily phase."
    )
    table_event = st.dataframe(
        display_rows,
        width="stretch",
        hide_index=True,
        key="tqd3_research_target_table",
        on_select="rerun",
        selection_mode="multi-row",
    )

    selection = getattr(table_event, "selection", None)
    if selection is None and isinstance(table_event, dict):
        selection = table_event.get("selection")

    if isinstance(selection, dict):
        selected_rows = list(selection.get("rows", []) or [])
    elif selection is not None:
        selected_rows = list(getattr(selection, "rows", []) or [])
    else:
        selected_rows = []

    if not selected_rows:
        st.info(
            "Select one or more research-target rows above. Select exactly "
            "one row to open its details."
        )
        return

    valid_selected_rows = [
        int(index)
        for index in selected_rows
        if 0 <= int(index) < len(filtered)
    ]
    if len(valid_selected_rows) != len(selected_rows):
        st.warning(
            "One or more selected rows are no longer available under the "
            "current filters. Reselect the rows."
        )
        return

    if len(valid_selected_rows) > 1:
        selected_targets = [
            filtered[index]
            for index in valid_selected_rows
        ]
        st.info(
            f"{len(selected_targets)} research targets selected. "
            "This is a read-only batch selection; Tavily remains disabled "
            "in TQ-D3 v1.2.x. Select exactly one row to inspect details."
        )
        selected_summary_rows = [
            {
                "target_type": row.get("target_type"),
                "label": row.get("label"),
                "routing_reason": row.get("routing_reason"),
                "source_class": row.get("source_class_id"),
                "tavily_eligible": row.get("tavily_eligible"),
            }
            for row in selected_targets
        ]
        st.dataframe(
            selected_summary_rows,
            width="stretch",
            hide_index=True,
        )
        _render_readonly_selection_export(
            summary_rows=selected_summary_rows,
            raw_rows=selected_targets,
            key_prefix="tqd3_research_target_selection",
            filename_stem="tqd3_research_target_selection",
        )
        return

    target = filtered[valid_selected_rows[0]]

    st.divider()
    st.markdown(f"### {target.get('label')}")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Target type", str(target.get("target_type") or "—"))
    d2.metric(
        "Tavily eligible",
        "Yes" if target.get("tavily_eligible") else "No",
    )
    d3.metric(
        "Human review",
        "Required"
        if target.get("requires_human_review")
        else "No",
    )
    d4.metric(
        "Affects scoring",
        "Yes" if target.get("influences_scoring") else "No",
    )

    st.markdown("**Research question**")
    st.write(target.get("research_question") or "—")
    st.markdown("**Routing reason**")
    st.code(str(target.get("routing_reason") or "—"), language=None)
    st.markdown("**Source terms**")
    st.write(target.get("source_terms") or [])

    with st.expander(
        "TQ-D3 research-target diagnostics",
        expanded=False,
    ):
        st.json(target)

def render_capability_discovery_review() -> None:
    st.divider()
    st.header("Capability Discovery")
    st.caption(
        f"TQ-D2.5/TQ-D2.6/TQ-D2.7/TQ-D3 · {TRIAGE_VERSION} · "
        f"{CLASSIFICATION_VERSION} · technology registry + deterministic "
        "diagnostics + explicit human review. No taxonomy mutation and "
        "no Tavily calls."
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

    classification_by_candidate_id: dict[
        str,
        dict[str, Any],
    ] = {}
    try:
        review_classification_report = build_classification_report(
            report
        )
        classification_by_candidate_id = {
            str(row.get("candidate_id") or ""): row
            for row in (
                review_classification_report.get("candidates", [])
                or []
            )
            if (
                isinstance(row, dict)
                and str(row.get("candidate_id") or "")
            )
        }
    except Exception:
        # Reviewer Guidance is supplemental. Classification diagnostics
        # should never block the existing human review workflow.
        classification_by_candidate_id = {}

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
        classification_tab,
        research_targets_tab,
        registry_tab,
        research_tab,
        debug_tab,
    ) = st.tabs(
        [
            "Review Queue",
            "TQ-D3 Classification",
            "Research Targets",
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
            with st.expander(
                "How to use deterministic Python-assisted review",
                expanded=False,
            ):
                st.markdown(
                    "This is **rule-based Python assistance**, not an AI/model "
                    "decision. It only surfaces unresolved, unreviewed "
                    "candidates where the deterministic rules have a "
                    "high-confidence, non-Defer suggestion."
                )
                st.markdown(
                    "1. Read each `candidate → suggested status → target` "
                    "entry.\n"
                    "2. Open the candidate in the Review Queue if you need "
                    "the evidence, diagnostics, or Reviewer Guidance.\n"
                    "3. Select **only** suggestions whose route and target you "
                    "personally agree with.\n"
                    "4. Click **Accept selected suggestions** to save those "
                    "human-confirmed triage decisions.\n"
                    "5. Nothing is saved for unselected rows, and the Python "
                    "assistant cannot mutate taxonomy/registry/scoring."
                )
                st.info(
                    "If this section shows 0 high-confidence suggestions, "
                    "review candidates manually. Do not lower the evidence "
                    "standard just to create batch suggestions."
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
        queue_rows = [
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
        ]

        if not filtered:
            st.info("No candidates match the current filters.")
        else:
            st.caption(
                "Click one row to inspect and review that candidate. "
                "Until a row is selected, the first filtered candidate is "
                "shown. Review/save actions remain single-candidate only."
            )
            table_event = st.dataframe(
                queue_rows,
                width="stretch",
                hide_index=True,
                key="taxonomy_discovery_review_queue_table",
                on_select="rerun",
                selection_mode="single-row",
            )

            selection = getattr(table_event, "selection", None)
            if selection is None and isinstance(table_event, dict):
                selection = table_event.get("selection")

            if isinstance(selection, dict):
                selected_rows = list(selection.get("rows", []) or [])
            elif selection is not None:
                selected_rows = list(
                    getattr(selection, "rows", []) or []
                )
            else:
                selected_rows = []

            selected_index = (
                int(selected_rows[0])
                if selected_rows
                else 0
            )
            if (
                selected_index < 0
                or selected_index >= len(filtered)
            ):
                selected_index = 0

            selected_candidate = filtered[selected_index]
            candidate = selected_candidate
            candidate_id = str(
                candidate.get("candidate_id") or ""
            )
            triage = candidate.get("triage", {}) or {}
            suggestion = deterministic_suggestions[candidate_id]

            st.divider()
            st.subheader(_candidate_text(candidate))
            _render_registry_resolution(candidate)

            classified_candidate = (
                classification_by_candidate_id.get(
                    candidate_id,
                    {},
                )
                or {}
            )
            _render_reviewer_guidance(
                candidate,
                suggestion,
                (
                    classified_candidate.get(
                        "tqd3_classification",
                        {},
                    )
                    or {}
                ),
            )

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

    with classification_tab:
        _render_tqd3_classification_tab(report)

    with research_targets_tab:
        _render_tqd3_research_targets_tab(report)

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

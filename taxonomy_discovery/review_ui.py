from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd
import streamlit as st

from database.tavily_usage_manager import (
    current_month_usage_summary,
    tavily_monthly_credit_budget,
)
from database.taxonomy_discovery_review_manager import (
    delete_review,
    list_reviews,
    save_review,
    BROAD_MINING_CANDIDATE_REVIEW_DECISIONS,
    delete_broad_mining_candidate_review,
    list_broad_mining_candidate_reviews,
    save_broad_mining_candidate_review,
)
from database.taxonomy_discovery_review_manager import (
    list_broad_mining_research_artifacts,
    load_latest_broad_mining_research_results,
    save_broad_mining_research_results,
)
from taxonomy_discovery.focused_verification_targets import (
    build_focused_verification_targets,
    dump_focused_verification_targets_json,
)
from taxonomy_discovery.focused_verification_ui import render_focused_verification
from taxonomy_discovery.broad_mining_discovery_catalog import (
    build_discovery_catalog,
    find_discovery_exact,
)
from taxonomy_discovery.broad_mining_guided_review import (
    build_guided_review_summary,
)
from taxonomy_discovery.broad_mining_review_assist import (
    BROAD_MINING_REVIEW_ASSIST_VERSION,
    ask_local_ollama_candidate_review,
    build_broad_mining_review_suggestion,
)
from taxonomy_discovery.broad_mining_export import (
    BROAD_MINING_EXPORT_VERSION,
    build_broad_mining_candidate_summary_csv,
    build_broad_mining_debug_zip,
)
from taxonomy_discovery.broad_mining_candidates import (
    build_broad_mining_candidate_report,
)
from taxonomy_discovery.broad_mining import (
    BROAD_MINING_SEED_VERSION,
    BROAD_MINING_VERSION,
    MAX_MINING_BATCH_SEEDS,
    build_broad_mining_queue,
    registry_mentions_for_result,
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
from taxonomy_discovery.tavily_account_usage import (
    TavilyUsageError,
    fetch_tavily_account_usage,
)
from taxonomy_discovery.tavily_research_agent import (
    MAX_BROAD_RESEARCH_BATCH_SEEDS,
    TAVILY_RESEARCH_MODEL,
    TavilyResearchAgentError,
    research_selected_broad_mining_with_tavily,
)
from taxonomy_discovery.tavily_research import (
    DEFAULT_MAX_BATCH_TARGETS,
    DEFAULT_MAX_RESULTS,
    TAVILY_RESEARCH_VERSION,
    TavilyResearchError,
    research_selected_targets_with_tavily,
    tavily_api_key_from_env,
)

PATCH_MARKER = "tqd2.6-technology-registry-ui-v1"
TQD3_UI_MARKER = "tqd3-classification-readonly-ui-v1.1.0"
TQD3_RESEARCH_TARGET_UI_MARKER = "tqd3-research-target-readonly-ui-v1.2.0"
TQD3_RESEARCH_TARGET_SELECTION_UI_MARKER = "tqd3-research-target-clickable-table-v1.2.2"
TQD3_TAVILY_RESEARCH_UI_MARKER = "tqd3-tavily-research-ui-v1.1.0"

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



def _render_tavily_local_usage(
    *, planned_credits: int | None,
) -> None:
    summary = current_month_usage_summary()
    credits = float(summary.get("credits") or 0)
    calls = int(summary.get("call_count") or 0)
    zero_calls = int(summary.get("zero_credit_call_count") or 0)
    month = str(summary.get("billing_month") or "current month")
    budget = tavily_monthly_credit_budget()

    usage_text = (
        f"Local tracked Tavily usage {month}: {credits:g} credit(s) "
        f"across {calls} call(s)"
    )
    if zero_calls:
        usage_text += f" · {zero_calls} zero-credit call(s)"
    if planned_credits is None:
        usage_text += (
            " · current Research-task credits will be measured "
            "from official Tavily key usage after completion."
        )
    else:
        usage_text += (
            f" · estimated current action: ~{int(planned_credits)} credit(s)."
        )
    st.caption(usage_text)

    if budget is not None and planned_credits is not None:
        estimated_remaining = (
            float(budget) - credits - float(planned_credits)
        )
        st.caption(
            "Configured local monthly credit budget: "
            f"{budget:g} · estimated remaining after this action: "
            f"{estimated_remaining:g}."
        )
    elif budget is not None:
        st.caption(
            "Configured local monthly credit budget: "
            f"{budget:g}. Broad Research cost is measured after "
            "completion rather than estimated up front."
        )
    else:
        st.caption(
            "Optional: set TAVILY_MONTHLY_CREDIT_BUDGET to your plan's "
            "monthly credit allowance to show an estimated remaining balance."
        )

    st.caption(
        "Local ledger only: this tracks live Tavily calls made through this "
        "Job AI Helper installation. It cannot see Tavily usage from other "
        "apps, machines, API keys, or the Tavily website."
    )

def _render_tqd3_tavily_research_controls(
    selected_targets: list[dict[str, Any]],
) -> None:
    if not selected_targets:
        return

    selected_target_ids = [
        str(row.get("target_id") or "")
        for row in selected_targets
        if str(row.get("target_id") or "")
    ]
    eligible_targets = [
        row
        for row in selected_targets
        if bool(row.get("tavily_eligible", False))
    ]
    api_key_configured = bool(tavily_api_key_from_env())

    st.markdown("### Tavily research")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Selected targets", len(selected_targets))
    c2.metric("Planned Tavily calls", len(selected_targets))
    c3.metric("Max sources / target", DEFAULT_MAX_RESULTS)
    c4.metric(
        "API key",
        "Configured" if api_key_configured else "Missing",
    )

    st.caption(
        f"{TAVILY_RESEARCH_VERSION} · one Tavily Search request per "
        "selected research target. Results are untrusted research evidence "
        "only and require human review before any proposal or production "
        "change."
    )
    _render_tavily_local_usage(
        planned_credits=len(selected_targets),
    )

    blocking_reasons: list[str] = []
    if not api_key_configured:
        blocking_reasons.append(
            "Set TAVILY_API_KEY in the environment and restart Streamlit."
        )
    if len(eligible_targets) != len(selected_targets):
        blocking_reasons.append(
            "One or more selected targets are not Tavily-eligible."
        )
    if len(selected_targets) > DEFAULT_MAX_BATCH_TARGETS:
        blocking_reasons.append(
            "Selection exceeds the Tavily batch safety limit of "
            f"{DEFAULT_MAX_BATCH_TARGETS} targets."
        )
    if len(selected_target_ids) != len(selected_targets):
        blocking_reasons.append(
            "One or more selected targets has no stable target_id."
        )

    if blocking_reasons:
        for reason in blocking_reasons:
            st.warning(reason)

    if st.button(
        f"Research {len(selected_targets)} selected target(s) with Tavily",
        key="tqd3_run_selected_tavily_research",
        disabled=bool(blocking_reasons),
        type="primary",
    ):
        try:
            with st.spinner(
                f"Running {len(selected_targets)} Tavily search request(s)..."
            ):
                batch_results = research_selected_targets_with_tavily(
                    selected_targets,
                    selected_target_ids=selected_target_ids,
                    max_results=DEFAULT_MAX_RESULTS,
                )
        except (ValueError, TavilyResearchError) as exc:
            st.error(f"Tavily research failed: {exc}")
        except Exception as exc:
            st.error(
                "Unexpected Tavily research error. No taxonomy, registry, "
                f"or scoring change was made: {exc}"
            )
        else:
            state_key = "tqd3_tavily_research_results_v1"
            result_state = st.session_state.setdefault(
                state_key,
                {},
            )
            if not isinstance(result_state, dict):
                result_state = {}

            for result in batch_results:
                target_id = str(result.get("target_id") or "")
                if target_id:
                    result_state[target_id] = result

            st.session_state[state_key] = result_state
            st.success(
                f"Stored {len(batch_results)} untrusted Tavily research "
                "result(s) in this Streamlit session."
            )
            st.rerun()

    result_state = st.session_state.get(
        "tqd3_tavily_research_results_v1",
        {},
    )
    if not isinstance(result_state, dict):
        result_state = {}

    visible_results = [
        result_state[target_id]
        for target_id in selected_target_ids
        if isinstance(result_state.get(target_id), dict)
    ]
    if not visible_results:
        return

    st.warning(
        "These are untrusted research results. They do not approve a "
        "mapping, create a capability, mutate the technology registry, or "
        "change scoring."
    )
    st.markdown("#### Tavily research results")

    for result in visible_results:
        label = str(
            result.get("target_label")
            or result.get("target_id")
            or "Research result"
        )
        source_count = int(result.get("source_count") or 0)
        with st.expander(
            f"{label} · {source_count} source(s)",
            expanded=len(visible_results) == 1,
        ):
            st.markdown("**Research question**")
            st.write(result.get("research_question") or "—")
            st.markdown("**Tavily answer**")
            st.write(result.get("answer") or "No answer returned.")

            sources = [
                row
                for row in result.get("sources", []) or []
                if isinstance(row, dict)
            ]
            if sources:
                st.markdown("**Sources**")
                st.dataframe(
                    [
                        {
                            "title": row.get("title"),
                            "url": row.get("url"),
                            "score": row.get("score"),
                            "content": row.get("content"),
                        }
                        for row in sources
                    ],
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("Tavily returned no usable source URLs.")

            with st.expander(
                "Research diagnostics",
                expanded=False,
            ):
                st.json(result)

    st.download_button(
        "Download selected Tavily research JSON",
        data=json.dumps(
            visible_results,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        file_name="tqd3_selected_tavily_research.json",
        mime="application/json",
        key="tqd3_download_selected_tavily_research",
    )

def _render_tqd3_research_targets_tab(
    triage_report: dict[str, Any],
) -> None:
    st.subheader("TQ-D3 Research Targets")
    st.caption(
        f"{RESEARCH_TARGET_VERSION} · deterministic extraction plus "
        f"{TAVILY_RESEARCH_VERSION} · optional explicit Tavily research. "
        "Extraction makes zero network calls; Tavily runs only after "
        "you select targets and click the research button. No automatic "
        "taxonomy, registry, proposal, or scoring change is performed."
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
        "A research target is a focused question, not approved production "
        "knowledge. Known mapped technologies are excluded; known unmapped "
        "technologies become relationship questions; strict unknown technical "
        "terms can become identity questions; E-class candidates become "
        "capability concept questions. Tavily results remain untrusted until "
        "human review."
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
        "rows show a batch summary. Any Tavily network call requires an "
        "explicit click after selection."
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

    selected_targets = [
        filtered[index]
        for index in valid_selected_rows
    ]
    _render_tqd3_tavily_research_controls(selected_targets)

    if len(valid_selected_rows) > 1:
        st.info(
            f"{len(selected_targets)} research targets selected. "
            "Use the explicit Tavily research control above to research "
            "this batch, or select exactly one row to inspect details."
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



def _render_tavily_official_usage() -> None:
    st.markdown("#### Tavily account usage")
    st.caption(
        "Official key/account usage is fetched only when you explicitly "
        "click Refresh. It is separate from the local Job AI Helper ledger."
    )
    if st.button(
        "Refresh Tavily account usage",
        key="tqd3_refresh_tavily_official_usage",
    ):
        try:
            with st.spinner("Refreshing Tavily account usage..."):
                snapshot = fetch_tavily_account_usage()
        except TavilyUsageError as exc:
            st.error(f"Tavily usage refresh failed: {exc}")
        except Exception as exc:
            st.error(f"Unexpected Tavily usage refresh error: {exc}")
        else:
            st.session_state[
                "tqd3_tavily_official_usage_v1"
            ] = snapshot
            st.rerun()

    snapshot = st.session_state.get(
        "tqd3_tavily_official_usage_v1"
    )
    if not isinstance(snapshot, dict):
        return

    key = snapshot.get("key")
    key = key if isinstance(key, dict) else {}
    account = snapshot.get("account")
    account = account if isinstance(account, dict) else {}

    u1, u2, u3, u4 = st.columns(4)
    u1.metric(
        "Key usage",
        key.get("usage")
        if key.get("usage") is not None
        else "—",
    )
    u2.metric(
        "Key limit",
        key.get("limit")
        if key.get("limit") is not None
        else "—",
    )
    u3.metric(
        "Search usage",
        key.get("search_usage")
        if key.get("search_usage") is not None
        else "—",
    )
    u4.metric(
        "Research usage",
        key.get("research_usage")
        if key.get("research_usage") is not None
        else "—",
    )
    plan = str(account.get("current_plan") or "").strip()
    if plan:
        st.caption(
            "Account plan: "
            f"{plan} · plan usage "
            f"{account.get('plan_usage')} / "
            f"{account.get('plan_limit')}"
        )

def _render_tqd3_broad_mining_tab() -> None:

    if not st.session_state.get(
        "tqd3_broad_mining_persistence_hydrated_v1"
    ):
        if not st.session_state.get(
            "tqd3_broad_mining_results_v1"
        ):
            saved_raw_results = (
                load_latest_broad_mining_research_results(
                    limit=100
                )
            )
            if saved_raw_results:
                saved_state = {
                    str(
                        row.get("target_id")
                        or row.get("target_key")
                        or row.get("seed_id")
                        or row.get("domain")
                        or index
                    ): row
                    for index, row in enumerate(
                        saved_raw_results
                    )
                    if isinstance(row, dict)
                }
                st.session_state[
                    "tqd3_broad_mining_results_v1"
                ] = saved_state
                saved_signature = tuple(
                    sorted(
                        str(
                            row.get("provider_request_id")
                            or row.get("target_id")
                            or row.get("seed_id")
                            or ""
                        )
                        for row in saved_raw_results
                        if isinstance(row, dict)
                    )
                )
                st.session_state[
                    "tqd3_broad_mining_persisted_signature_v1"
                ] = saved_signature
        st.session_state[
            "tqd3_broad_mining_persistence_hydrated_v1"
        ] = True

    # Persistence is normal runtime state, not a manual recovery path.
    # If this Streamlit session has no Broad Mining results, restore the
    # newest saved raw research for each seed from local SQLite. This performs
    # no Tavily/network/model call.
    if not st.session_state.get(
        "tqd3_broad_mining_results_v1"
    ):
        auto_saved_results = (
            load_latest_broad_mining_research_results(
                limit=100
            )
        )
        if auto_saved_results:
            auto_saved_state = {
                str(
                    row.get("target_id")
                    or row.get("target_key")
                    or row.get("seed_id")
                    or row.get("domain")
                    or index
                ): row
                for index, row in enumerate(
                    auto_saved_results
                )
                if isinstance(row, dict)
            }
            if auto_saved_state:
                st.session_state[
                    "tqd3_broad_mining_results_v1"
                ] = auto_saved_state
                st.session_state[
                    "tqd3_broad_mining_persisted_signature_v1"
                ] = tuple(
                    sorted(
                        str(
                            row.get("provider_request_id")
                            or row.get("target_id")
                            or row.get("seed_id")
                            or ""
                        )
                        for row in auto_saved_results
                        if isinstance(row, dict)
                    )
                )
    raw_persist_state = st.session_state.get(
        "tqd3_broad_mining_results_v1"
    ) or {}
    if isinstance(raw_persist_state, dict):
        current_persist_results = [
            row
            for row in raw_persist_state.values()
            if isinstance(row, dict)
        ]
    elif isinstance(raw_persist_state, list):
        current_persist_results = [
            row
            for row in raw_persist_state
            if isinstance(row, dict)
        ]
    else:
        current_persist_results = []
    current_persist_signature = tuple(
        sorted(
            str(
                row.get("provider_request_id")
                or row.get("target_id")
                or row.get("seed_id")
                or ""
            )
            for row in current_persist_results
        )
    )
    if (
        current_persist_results
        and current_persist_signature
        != st.session_state.get(
            "tqd3_broad_mining_persisted_signature_v1"
        )
    ):
        try:
            persisted_rows = (
                save_broad_mining_research_results(
                    current_persist_results
                )
            )
            st.session_state[
                "tqd3_broad_mining_persisted_signature_v1"
            ] = current_persist_signature
            if persisted_rows:
                st.caption(
                    f"Saved {len(persisted_rows)} raw Broad Mining "
                    "research artifact(s) to local SQLite."
                )
        except Exception as persistence_exc:
            st.warning(
                "Broad Mining results are available, but local persistence "
                f"failed: {persistence_exc}"
            )
    st.subheader("TQ-D3 Broad Technology Mining")
    st.caption(
        f"{BROAD_MINING_VERSION} · {BROAD_MINING_SEED_VERSION} · "
        "proactive ecosystem seed research for widely used software "
        "technologies. This stage collects untrusted seed evidence only."
    )
    st.info(
        "This complements JD-driven Research Targets. Select broad domains "
        "to research widely used technologies that may not have appeared in "
        "your current JDs yet. Completed research is persisted locally in SQLite and automatically restored without a Tavily call. Saved research does not add "
        "technologies, create proposals, mutate the registry/taxonomy, or "
        "change scoring."
    )

    queue = build_broad_mining_queue()
    persisted_rows = list_broad_mining_research_artifacts(
        limit=100
    )
    persisted_seed_metadata = {}
    for persisted_row in persisted_rows:
        persisted_seed_id = str(
            persisted_row.get("seed_id") or ""
        ).strip()
        if (
            persisted_seed_id
            and persisted_seed_id
            not in persisted_seed_metadata
        ):
            # list_broad_mining_research_artifacts is newest-first, so
            # setdefault-style behavior keeps the latest artifact per seed.
            persisted_seed_metadata[
                persisted_seed_id
            ] = persisted_row

    enriched_queue = []
    for row in queue:
        enriched = dict(row)
        seed_id = str(enriched.get("seed_id") or "")
        persisted = persisted_seed_metadata.get(seed_id)
        if persisted:
            enriched["research_status"] = "Researched"
            enriched["last_researched"] = str(
                persisted.get("updated_at") or ""
            )
            enriched["saved_technologies"] = int(
                persisted.get("technology_count") or 0
            )
            enriched["saved_sources"] = int(
                persisted.get("source_count") or 0
            )
        else:
            enriched["research_status"] = "Not researched"
            enriched["last_researched"] = ""
            enriched["saved_technologies"] = 0
            enriched["saved_sources"] = 0
        enriched_queue.append(enriched)

    total_domain_count = len(enriched_queue)
    researched_count = sum(
        1
        for row in enriched_queue
        if row.get("research_status") == "Researched"
    )
    remaining_domain_count = (
        total_domain_count - researched_count
    )

    coverage_col1, coverage_col2, coverage_col3 = st.columns(3)
    coverage_col1.metric(
        "Total domains",
        total_domain_count,
    )
    coverage_col2.metric(
        "Researched",
        researched_count,
    )
    coverage_col3.metric(
        "Remaining",
        remaining_domain_count,
    )

    if persisted_seed_metadata:
        st.markdown("### Researched domains")
        st.caption(
            "These results are loaded from local SQLite. Viewing them makes "
            "no Tavily call. Research again is always an explicit action."
        )

        researched_table_rows = []
        for seed_id, persisted in persisted_seed_metadata.items():
            label = next(
                (
                    str(row.get("domain") or "")
                    for row in enriched_queue
                    if str(row.get("seed_id") or "")
                    == seed_id
                ),
                str(persisted.get("domain") or seed_id),
            )
            researched_table_rows.append(
                {
                    "domain": label,
                    "status": "Researched",
                    "last_researched": str(
                        persisted.get("updated_at") or ""
                    ),
                    "technologies": int(
                        persisted.get("technology_count")
                        or 0
                    ),
                    "sources": int(
                        persisted.get("source_count") or 0
                    ),
                    "model": str(
                        persisted.get("research_model")
                        or ""
                    ),
                    "artifact_id": str(
                        persisted.get("artifact_id") or ""
                    ),
                }
            )

        researched_table_rows.sort(
            key=lambda row: str(
                row.get("domain") or ""
            ).casefold()
        )
        st.dataframe(
            researched_table_rows,
            width="stretch",
            hide_index=True,
        )

        researched_options = {
            str(row["domain"]): str(
                row.get("seed_id") or ""
            )
            for row in enriched_queue
            if row.get("research_status")
            == "Researched"
        }
        if researched_options:
            researched_domain_label = st.selectbox(
                "Researched domain actions",
                list(researched_options),
                key="tqd3_researched_domain_action",
                help=(
                    "View loads the saved result locally. Research again "
                    "only prepares the domain below; Tavily is not called "
                    "until you explicitly start Broad Mining."
                ),
            )
            researched_seed_id = researched_options[
                researched_domain_label
            ]
            action_col1, action_col2 = st.columns(2)

            if action_col1.button(
                "View saved result",
                key="tqd3_view_saved_broad_result",
            ):
                saved_results = (
                    load_latest_broad_mining_research_results(
                        limit=100
                    )
                )
                selected_saved_result = next(
                    (
                        result
                        for result in saved_results
                        if str(
                            result.get("seed_id") or ""
                        )
                        == researched_seed_id
                    ),
                    None,
                )
                if selected_saved_result is None:
                    st.warning(
                        "The saved artifact could not be loaded."
                    )
                else:
                    result_key = str(
                        selected_saved_result.get(
                            "target_id"
                        )
                        or selected_saved_result.get(
                            "target_key"
                        )
                        or selected_saved_result.get(
                            "seed_id"
                        )
                        or researched_seed_id
                    )
                    st.session_state[
                        "tqd3_broad_mining_results_v1"
                    ] = {
                        result_key: selected_saved_result
                    }
                    st.session_state[
                        "tqd3_broad_mining_persisted_signature_v1"
                    ] = tuple(
                        [
                            str(
                                selected_saved_result.get(
                                    "provider_request_id"
                                )
                                or selected_saved_result.get(
                                    "target_id"
                                )
                                or selected_saved_result.get(
                                    "seed_id"
                                )
                                or ""
                            )
                        ]
                    )
                    st.success(
                        "Loaded the saved result locally. "
                        "No Tavily call was made."
                    )
                    st.rerun()

            if action_col2.button(
                "Research again",
                key="tqd3_prepare_reresearch_broad_domain",
            ):
                st.session_state[
                    "tqd3_hide_researched_domains"
                ] = False
                st.session_state[
                    "tqd3_broad_mining_search"
                ] = researched_domain_label
                st.session_state[
                    "tqd3_reresearch_prepared_seed_v1"
                ] = researched_seed_id
                st.rerun()

            if (
                st.session_state.get(
                    "tqd3_reresearch_prepared_seed_v1"
                )
                == researched_seed_id
            ):
                st.info(
                    "Research again is prepared below. Select the domain "
                    "row, then explicitly click the Tavily Research button. "
                    "No Tavily call has been made yet."
                )


    saved_review_research = (
        load_latest_broad_mining_research_results(
            limit=100
        )
    )
    if saved_review_research:
        mined_candidate_report = (
            build_broad_mining_candidate_report(
                saved_review_research
            )
        )
        if isinstance(mined_candidate_report, dict):
            mined_candidates = (
                mined_candidate_report.get("candidates")
                or mined_candidate_report.get(
                    "candidate_rows"
                )
                or mined_candidate_report.get("rows")
                or []
            )
        elif isinstance(
            mined_candidate_report,
            list,
        ):
            mined_candidates = mined_candidate_report
        else:
            mined_candidates = []

        mined_candidates = [
            candidate
            for candidate in mined_candidates
            if isinstance(candidate, dict)
        ]
        reviewable_candidates = [
            candidate
            for candidate in mined_candidates
            if str(candidate.get("status") or "")
            in {
                "possible_new_technology",
                "ambiguous_registry_match",
            }
        ]
        already_known_count = sum(
            1
            for candidate in mined_candidates
            if str(candidate.get("status") or "")
            == "already_known"
        )
        persisted_candidate_reviews = {
            str(row.get("candidate_id") or ""): row
            for row in list_broad_mining_candidate_reviews()
            if str(row.get("candidate_id") or "")
        }


        candidate_review_suggestions = {
            str(candidate.get("candidate_id") or ""):
                build_broad_mining_review_suggestion(
                    candidate
                )
            for candidate in reviewable_candidates
            if str(candidate.get("candidate_id") or "")
        }


        guided_review_summary = (
            build_guided_review_summary(
                mined_candidates,
                candidate_review_suggestions,
                list(
                    persisted_candidate_reviews.values()
                ),
            )
        )
        guided_items = guided_review_summary[
            "items"
        ]
        guided_counts = guided_review_summary[
            "counts"
        ]

        st.markdown("### Discovery & verification")
        st.caption(
            "Follow the steps in order. The normal workflow does not require "
            "you to understand source-authority fields, candidate IDs, or "
            "internal routing codes."
        )
        st.markdown(
            "**1. Discover** ✓  →  "
            "**2. Review recommendations** ← You are here  →  "
            "**3. Verify candidates**  →  "
            "**4. Review proposed changes**  →  "
            "**5. Publish**"
        )

        g1, g2, g3, g4, g5 = st.columns(5)
        g1.metric(
            "Already handled",
            guided_counts.get(
                "already_known",
                0,
            ),
            help=(
                "The technology registry already knows these. "
                "No action is needed."
            ),
        )
        g2.metric(
            "Strong suggestions",
            guided_counts.get(
                "recommended",
                0,
            ),
            help=(
                "Strong deterministic evidence says these are worth "
                "focused verification."
            ),
        )
        g3.metric(
            "Suggested",
            guided_counts.get(
                "needs_verification",
                0,
            ),
            help=(
                "Likely worth verifying, but current evidence is incomplete."
            ),
        )
        g4.metric(
            "Other discoveries",
            guided_counts.get(
                "other_discoveries",
                0,
            ),
            help=(
                "No action is required now. Parked does not mean rejected."
            ),
        )
        g5.metric(
            "Ready to verify",
            guided_counts.get(
                "confirmed",
                0,
            ),
            help=(
                "You already confirmed these for the focused "
                "verification stage."
            ),
        )

        st.info(
            "**How this works:** Strong suggestions are the easiest "
            "candidates to verify next. Suggested candidates are also "
            "worth verifying, but current evidence is incomplete. "
            "Other discoveries are still retained and searchable; "
            "they are simply not prioritized yet. You can send any of "
            "them to verification at any time."
        )

        recommended_items = [
            item
            for item in guided_items
            if item.get("bucket")
            == "recommended"
        ]
        needs_verification_items = [
            item
            for item in guided_items
            if item.get("bucket")
            == "needs_verification"
        ]
        other_discovery_items = [
            item
            for item in guided_items
            if item.get("bucket")
            == "other_discoveries"
        ]
        confirmed_items = [
            item
            for item in guided_items
            if item.get("bucket")
            == "confirmed"
        ]

        if recommended_items:
            st.markdown(
                "#### Recommended for verification"
            )
            st.caption(
                "These are the strongest candidates. Confirming them only "
                "marks them ready for focused verification; it does not add "
                "anything to the production registry or taxonomy."
            )
            st.dataframe(
                [
                    {
                        "technology":
                            item["canonical_name"],
                        "why":
                            item["friendly_reason"],
                        "known_capability":
                            ", ".join(
                                item[
                                    "taxonomy_capabilities"
                                ]
                            )
                            or "—",
                        "sources":
                            item[
                                "supporting_sources"
                            ],
                        "next":
                            item["next_action"],
                    }
                    for item
                    in recommended_items
                ],
                width="stretch",
                hide_index=True,
            )
            if st.button(
                "Confirm all strong recommendations",
                key=(
                    "tqd3_guided_confirm_all_strong"
                ),
                type="primary",
            ):
                candidate_index = {
                    str(
                        candidate.get(
                            "candidate_id"
                        )
                        or ""
                    ): candidate
                    for candidate
                    in reviewable_candidates
                }
                confirmed_now = 0
                for item in recommended_items:
                    candidate_id = str(
                        item.get("candidate_id")
                        or ""
                    )
                    candidate = (
                        candidate_index.get(
                            candidate_id
                        )
                    )
                    if candidate is None:
                        continue
                    save_broad_mining_candidate_review(
                        candidate=candidate,
                        decision="research_further",
                        notes=(
                            "Confirmed from Guided Technology Review: "
                            + str(
                                item.get(
                                    "friendly_reason"
                                )
                                or ""
                            )
                        ),
                    )
                    confirmed_now += 1
                st.success(
                    f"Confirmed {confirmed_now} strong "
                    "recommendation(s) for focused verification."
                )
                st.rerun()
        else:
            st.success(
                "No strong recommendations are waiting for confirmation."
            )

        if needs_verification_items:
            with st.expander(
                "Suggested candidates",
                expanded=True,
            ):
                st.caption(
                    "These are plausible technologies, but the current "
                    "evidence is incomplete. Needs verification does not "
                    "mean low-quality technology. Select only the ones you "
                    "want the next stage to verify."
                )
                guided_medium_options = {
                    (
                        item["canonical_name"]
                        + " — "
                        + item["friendly_reason"]
                    ): item
                    for item
                    in needs_verification_items
                }
                guided_medium_selected = (
                    st.multiselect(
                        "Choose suggested candidates",
                        list(
                            guided_medium_options
                        ),
                        key=(
                            "tqd3_guided_medium_select"
                        ),
                    )
                )
                if st.button(
                    "Add selected to verification",
                    disabled=not (
                        guided_medium_selected
                    ),
                    key=(
                        "tqd3_guided_confirm_medium"
                    ),
                ):
                    candidate_index = {
                        str(
                            candidate.get(
                                "candidate_id"
                            )
                            or ""
                        ): candidate
                        for candidate
                        in reviewable_candidates
                    }
                    confirmed_medium = 0
                    for label in (
                        guided_medium_selected
                    ):
                        item = (
                            guided_medium_options[
                                label
                            ]
                        )
                        candidate = (
                            candidate_index.get(
                                item["candidate_id"]
                            )
                        )
                        if candidate is None:
                            continue
                        save_broad_mining_candidate_review(
                            candidate=candidate,
                            decision=(
                                "research_further"
                            ),
                            notes=(
                                "Confirmed from Guided Technology Review "
                                "after user selection: "
                                + item[
                                    "friendly_reason"
                                ]
                            ),
                        )
                        confirmed_medium += 1
                    st.success(
                        f"Confirmed {confirmed_medium} "
                        "candidate(s) for focused verification."
                    )
                    st.rerun()

        st.markdown("#### Other discoveries")
        st.caption(
            "All discoveries are retained. These candidates are not "
            "prioritized by the deterministic rules, but they remain "
            "available for future JD-driven verification. Selecting one "
            "here only adds it to the verification queue; it does not call "
            "Tavily or change the registry/taxonomy."
        )

        if other_discovery_items:
            other_options = {
                (
                    item["canonical_name"]
                    + " — "
                    + item["friendly_reason"]
                ): item
                for item in other_discovery_items
            }
            other_selected = st.multiselect(
                "Choose other discoveries",
                list(other_options),
                key="tqd3_guided_other_discovery_select",
            )
            if st.button(
                "Send selected other discoveries to verification",
                disabled=not other_selected,
                key="tqd3_guided_confirm_other_discoveries",
            ):
                candidate_index = {
                    str(
                        candidate.get(
                            "candidate_id"
                        )
                        or ""
                    ): candidate
                    for candidate
                    in reviewable_candidates
                }
                added = 0
                for label in other_selected:
                    item = other_options[label]
                    candidate = candidate_index.get(
                        item["candidate_id"]
                    )
                    if candidate is None:
                        continue
                    save_broad_mining_candidate_review(
                        candidate=candidate,
                        decision="research_further",
                        notes=(
                            "User explicitly sent an Other Discovery "
                            "to focused verification: "
                            + item["friendly_reason"]
                        ),
                    )
                    added += 1
                st.success(
                    f"Added {added} other discovery candidate(s) "
                    "to the verification queue."
                )
                st.rerun()

            show_other = st.toggle(
                "Show all other discoveries",
                value=False,
                key="tqd3_guided_show_other_discoveries",
            )
            if show_other:
                st.dataframe(
                    [
                        {
                            "technology":
                                item["canonical_name"],
                            "why_not_prioritized":
                                item["friendly_reason"],
                            "sources":
                                item["supporting_sources"],
                            "action":
                                "Can be verified any time",
                        }
                        for item
                        in other_discovery_items
                    ],
                    width="stretch",
                    hide_index=True,
                )
        else:
            st.success(
                "No unprioritized discoveries remain."
            )

        discovery_catalog = build_discovery_catalog(
            guided_review_summary
        )
        with st.expander(
            "Discovery catalog",
            expanded=False,
        ):
            st.caption(
                "Every discovered technology is retained here, including "
                "Other discoveries. Exact-name catalog matches are "
                "recognition-only: they can help a future JD trigger "
                "verification, but they do not prove a capability mapping "
                "or affect scoring."
            )
            discovery_query = st.text_input(
                "Search all discovered technologies",
                key="tqd3_discovery_catalog_search",
            )
            if discovery_query.strip():
                exact_hits = find_discovery_exact(
                    discovery_query,
                    discovery_catalog,
                )
                if exact_hits:
                    st.dataframe(
                        exact_hits,
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    filtered_catalog = [
                        row
                        for row
                        in discovery_catalog["items"]
                        if discovery_query.casefold()
                        in str(
                            row.get(
                                "canonical_name"
                            )
                            or ""
                        ).casefold()
                    ]
                    st.dataframe(
                        filtered_catalog,
                        width="stretch",
                        hide_index=True,
                    )
            else:
                st.dataframe(
                    discovery_catalog["items"],
                    width="stretch",
                    hide_index=True,
                )

        if confirmed_items:
            st.success(
                f"{len(confirmed_items)} candidate(s) are confirmed "
                "and ready for Step 3: focused verification. "
                "Only these confirmed candidates become narrow "
                "verification targets below."
            )

        focused_target_report = (
            build_focused_verification_targets(
                guided_review_summary
            )
        )
        if focused_target_report["count"]:
            st.markdown(
                "### Step 3 · Focused verification"
            )
            st.caption(
                "These targets are generated deterministically from the "
                "candidates you marked Ready to verify. No Tavily or model "
                "call is made when these targets are generated, and they do "
                "not change the registry, taxonomy, or scoring."
            )

            fv1, fv2, fv3 = st.columns(3)
            fv1.metric(
                "Ready candidates",
                focused_target_report[
                    "count"
                ],
            )
            fv2.metric(
                "Registry relationship targets",
                focused_target_report[
                    "route_counts"
                ].get(
                    "technology_registry_relationship",
                    0,
                ),
            )
            fv3.metric(
                "Identity targets",
                focused_target_report[
                    "route_counts"
                ].get(
                    "technology_identity",
                    0,
                )
                + focused_target_report[
                    "route_counts"
                ].get(
                    "technology_identity_disambiguation",
                    0,
                ),
            )

            st.dataframe(
                [
                    {
                        "technology":
                            row[
                                "canonical_name"
                            ],
                        "route":
                            row["route"],
                        "existing_capability":
                            ", ".join(
                                row[
                                    "taxonomy_capability_ids"
                                ]
                            )
                            or "—",
                        "why":
                            row[
                                "source_summary"
                            ][
                                "friendly_reason"
                            ],
                    }
                    for row
                    in focused_target_report[
                        "targets"
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

            st.download_button(
                "Download focused verification targets JSON",
                data=(
                    dump_focused_verification_targets_json(
                        focused_target_report
                    )
                ),
                file_name=(
                    "tqd3_focused_verification_targets.json"
                ),
                mime="application/json",
                key=(
                    "tqd3_download_focused_verification_targets"
                ),
            )

            render_focused_verification(focused_target_report)

        st.caption(
            "Need the underlying evidence, source counts, reason codes, "
            "Ollama second opinions, or candidate IDs? Use the Advanced "
            "review tools below."
        )
        with st.expander(
            "Advanced assisted review · deterministic Python",
            expanded=False,
        ):
            st.caption(
                "Confidence measures routing-evidence strength, not whether "
                "a technology is real or important. Deterministic review uses "
                "source signals plus exact capability-taxonomy coverage. A "
                "taxonomy-covered technology can still be a technology-registry "
                "gap. No fuzzy/semantic matching is used, and suggestions "
                "never save automatically."
            )

            assist_decision_filter = st.multiselect(
                "Suggested decision",
                [
                    "research_further",
                    "defer",
                ],
                default=[],
                format_func=lambda value: (
                    "Research further"
                    if value == "research_further"
                    else "Defer"
                ),
                key="tqd3_mined_assist_decision_filter",
            )
            assist_confidence_filter = st.multiselect(
                "Suggestion confidence",
                ["high", "medium", "low"],
                default=[],
                key="tqd3_mined_assist_confidence_filter",
            )
            primary_filter = st.selectbox(
                "Primary-official evidence",
                [
                    "All",
                    "Has primary official",
                    "No primary official",
                ],
                key="tqd3_mined_assist_primary_filter",
            )

            assist_rows = []
            for candidate in reviewable_candidates:
                candidate_id = str(
                    candidate.get("candidate_id") or ""
                )
                review = persisted_candidate_reviews.get(
                    candidate_id,
                    {},
                )
                suggestion = (
                    candidate_review_suggestions.get(
                        candidate_id,
                        {},
                    )
                )
                if (
                    assist_decision_filter
                    and suggestion.get(
                        "suggested_decision"
                    )
                    not in assist_decision_filter
                ):
                    continue
                if (
                    assist_confidence_filter
                    and suggestion.get("confidence")
                    not in assist_confidence_filter
                ):
                    continue
                has_primary = bool(
                    (
                        suggestion.get("signals")
                        or {}
                    ).get(
                        "has_primary_official",
                        False,
                    )
                )
                if (
                    primary_filter
                    == "Has primary official"
                    and not has_primary
                ):
                    continue
                if (
                    primary_filter
                    == "No primary official"
                    and has_primary
                ):
                    continue

                assist_signals = (
                    suggestion.get("signals")
                    or {}
                )
                authority_counts = (
                    assist_signals.get(
                        "authority_counts"
                    )
                    or {}
                )
                taxonomy_coverage = (
                    assist_signals.get(
                        "taxonomy_coverage"
                    )
                    or {}
                )
                taxonomy_capabilities = ", ".join(
                    taxonomy_coverage.get(
                        "capability_ids",
                        [],
                    )
                    if isinstance(
                        taxonomy_coverage,
                        dict,
                    )
                    else []
                )
                suggestion_reasons = (
                    suggestion.get("reasons")
                    or []
                )
                assist_rows.append(
                    {
                        "select": False,
                        "canonical_name": str(
                            candidate.get(
                                "canonical_name"
                            )
                            or ""
                        ),
                        "candidate_status": str(
                            candidate.get("status")
                            or ""
                        ),
                        "suggested_decision": str(
                            suggestion.get(
                                "suggested_decision"
                            )
                            or ""
                        ),
                        "confidence": str(
                            suggestion.get(
                                "confidence"
                            )
                            or ""
                        ),
                        "primary_official": has_primary,
                        "supporting_sources": int(
                            assist_signals.get(
                                "supporting_sources",
                                0,
                            )
                            or 0
                        ),
                        "primary_official_sources": int(
                            authority_counts.get(
                                "primary_official",
                                0,
                            )
                            or 0
                        ),
                        "secondary_sources": int(
                            authority_counts.get(
                                "secondary",
                                0,
                            )
                            or 0
                        ),
                        "unclassified_sources": int(
                            authority_counts.get(
                                "unclassified",
                                0,
                            )
                            or 0
                        ),
                        "taxonomy_covered": bool(
                            taxonomy_coverage.get(
                                "matched",
                                False,
                            )
                            if isinstance(
                                taxonomy_coverage,
                                dict,
                            )
                            else False
                        ),
                        "taxonomy_capability":
                            taxonomy_capabilities,
                        "reason_code": str(
                            suggestion.get(
                                "reason_code"
                            )
                            or ""
                        ),
                        "suggestion_reason": (
                            str(
                                suggestion_reasons[0]
                            )
                            if suggestion_reasons
                            else ""
                        ),
                        "current_review": str(
                            review.get("decision")
                            or "unreviewed"
                        ),
                        "candidate_id": candidate_id,
                    }
                )

            select_high_confidence = st.checkbox(
                "Select all filtered high-confidence unreviewed suggestions",
                value=False,
                key="tqd3_select_high_confidence_mined_suggestions",
            )
            for row in assist_rows:
                row["select"] = bool(
                    select_high_confidence
                    and row["confidence"] == "high"
                    and row["current_review"]
                    == "unreviewed"
                )

            if assist_rows:
                assist_df = pd.DataFrame(
                    assist_rows
                )
                edited_assist_df = st.data_editor(
                    assist_df,
                    width="stretch",
                    hide_index=True,
                    disabled=[
                        "canonical_name",
                        "candidate_status",
                        "suggested_decision",
                        "confidence",
                        "primary_official",
                        "supporting_sources",
                        "primary_official_sources",
                        "secondary_sources",
                        "unclassified_sources",
                        "taxonomy_covered",
                        "taxonomy_capability",
                        "reason_code",
                        "suggestion_reason",
                        "current_review",
                        "candidate_id",
                    ],
                    column_config={
                        "select":
                            st.column_config.CheckboxColumn(
                                "Select",
                                help=(
                                    "Explicitly select deterministic "
                                    "suggestions to save as human-confirmed "
                                    "candidate reviews."
                                ),
                            ),
                    },
                    key="tqd3_mined_assisted_review_grid",
                )
                selected_assist_ids = [
                    str(row["candidate_id"])
                    for _, row
                    in edited_assist_df.iterrows()
                    if bool(row["select"])
                    and str(
                        row["current_review"]
                    )
                    == "unreviewed"
                ]
                st.caption(
                    f"{len(selected_assist_ids)} unreviewed suggestion(s) "
                    "selected for explicit confirmation."
                )

                if st.button(
                    "Accept selected deterministic suggestions",
                    disabled=not selected_assist_ids,
                    key="tqd3_accept_mined_deterministic_suggestions",
                ):
                    candidate_index = {
                        str(
                            candidate.get(
                                "candidate_id"
                            )
                            or ""
                        ): candidate
                        for candidate in reviewable_candidates
                    }
                    saved_count = 0
                    for candidate_id in selected_assist_ids:
                        candidate = candidate_index[
                            candidate_id
                        ]
                        suggestion = (
                            candidate_review_suggestions[
                                candidate_id
                            ]
                        )
                        save_broad_mining_candidate_review(
                            candidate=candidate,
                            decision=str(
                                suggestion.get(
                                    "suggested_decision"
                                )
                            ),
                            notes=(
                                "Accepted deterministic Broad Mining "
                                "review suggestion "
                                f"{BROAD_MINING_REVIEW_ASSIST_VERSION}: "
                                + " | ".join(
                                    suggestion.get(
                                        "reasons",
                                        [],
                                    )
                                    or []
                                )
                            ),
                        )
                        saved_count += 1
                    st.success(
                        f"Saved {saved_count} human-confirmed "
                        "candidate review(s)."
                    )
                    st.rerun()
            else:
                st.info(
                    "No candidates match the assisted-review filters."
                )
        show_advanced_review = st.toggle(
            "Show advanced candidate review queue",
            value=False,
            key="tqd3_show_advanced_candidate_review",
            help=(
                "Shows the technical review queue, source-authority "
                "details, reason codes, and individual review tools."
            ),
        )
        if show_advanced_review:
            st.markdown("### Mined candidate review queue")
            st.caption(
                "This queue is derived deterministically from saved Broad Mining "
                "research. Decisions are local human-review state only. "
                "'Research further' records routing intent; it does not call "
                "Tavily, create a proposal, mutate the registry/taxonomy, or "
                "change scoring. Already-known candidates are excluded from "
                "the review queue."
            )

            research_further_count = sum(
                1
                for candidate in reviewable_candidates
                if (
                    persisted_candidate_reviews.get(
                        str(
                            candidate.get("candidate_id")
                            or ""
                        ),
                        {},
                    ).get("decision")
                    == "research_further"
                )
            )
            deferred_count = sum(
                1
                for candidate in reviewable_candidates
                if (
                    persisted_candidate_reviews.get(
                        str(
                            candidate.get("candidate_id")
                            or ""
                        ),
                        {},
                    ).get("decision")
                    == "defer"
                )
            )
            rejected_count = sum(
                1
                for candidate in reviewable_candidates
                if (
                    persisted_candidate_reviews.get(
                        str(
                            candidate.get("candidate_id")
                            or ""
                        ),
                        {},
                    ).get("decision")
                    == "reject"
                )
            )
            unreviewed_count = (
                len(reviewable_candidates)
                - research_further_count
                - deferred_count
                - rejected_count
            )

            rq1, rq2, rq3, rq4, rq5 = st.columns(5)
            rq1.metric(
                "Reviewable",
                len(reviewable_candidates),
            )
            rq2.metric(
                "Research further",
                research_further_count,
            )
            rq3.metric("Deferred", deferred_count)
            rq4.metric("Rejected", rejected_count)
            rq5.metric("Unreviewed", unreviewed_count)
            if already_known_count:
                st.caption(
                    f"{already_known_count} already-known candidate(s) "
                    "omitted from this queue."
                )

            if reviewable_candidates:
                review_queue_rows = []
                for candidate in reviewable_candidates:
                    candidate_id = str(
                        candidate.get("candidate_id") or ""
                    )
                    review = persisted_candidate_reviews.get(
                        candidate_id,
                        {},
                    )
                    source_urls = (
                        candidate.get(
                            "supporting_source_urls"
                        )
                        or []
                    )
                    if not isinstance(source_urls, list):
                        source_urls = []
                    review_queue_rows.append(
                        {
                            "canonical_name": str(
                                candidate.get(
                                    "canonical_name"
                                )
                                or ""
                            ),
                            "candidate_status": str(
                                candidate.get("status")
                                or ""
                            ),
                            "entity_type": str(
                                candidate.get(
                                    "entity_type"
                                )
                                or ""
                            ),
                            "supporting_sources": len(
                                source_urls
                            ),
                            "review_decision": str(
                                review.get("decision")
                                or "unreviewed"
                            ),
                            "candidate_id": candidate_id,
                        }
                    )

                decision_order = {
                    "unreviewed": 0,
                    "research_further": 1,
                    "defer": 2,
                    "reject": 3,
                }
                review_queue_rows.sort(
                    key=lambda row: (
                        decision_order.get(
                            str(
                                row.get(
                                    "review_decision"
                                )
                                or "unreviewed"
                            ),
                            9,
                        ),
                        str(
                            row.get(
                                "canonical_name"
                            )
                            or ""
                        ).casefold(),
                    )
                )
                st.dataframe(
                    review_queue_rows,
                    width="stretch",
                    hide_index=True,
                )

                candidate_by_label = {
                    (
                        str(
                            candidate.get(
                                "canonical_name"
                            )
                            or candidate.get(
                                "candidate_id"
                            )
                            or "candidate"
                        )
                        + " · "
                        + str(
                            candidate.get("status")
                            or ""
                        )
                    ): candidate
                    for candidate in reviewable_candidates
                }
                selected_candidate_label = st.selectbox(
                    "Candidate to review",
                    list(candidate_by_label),
                    key="tqd3_mined_candidate_review_select",
                )
                selected_candidate = (
                    candidate_by_label[
                        selected_candidate_label
                    ]
                )
                selected_candidate_id = str(
                    selected_candidate.get(
                        "candidate_id"
                    )
                    or ""
                )
                existing_candidate_review = (
                    persisted_candidate_reviews.get(
                        selected_candidate_id,
                        {},
                    )
                )

                details_col1, details_col2 = st.columns(2)
                details_col1.write(
                    "**Candidate:** "
                    + str(
                        selected_candidate.get(
                            "canonical_name"
                        )
                        or ""
                    )
                )
                details_col1.write(
                    "**Candidate status:** "
                    + str(
                        selected_candidate.get(
                            "status"
                        )
                        or ""
                    )
                )
                details_col2.write(
                    "**Entity type:** "
                    + str(
                        selected_candidate.get(
                            "entity_type"
                        )
                        or ""
                    )
                )
                details_col2.write(
                    "**Candidate ID:** "
                    + selected_candidate_id
                )

                with st.expander(
                    "Source authority evidence",
                    expanded=False,
                ):
                    st.json(
                        selected_candidate.get(
                            "source_authority"
                        )
                        or {}
                    )
                    supporting_urls = (
                        selected_candidate.get(
                            "supporting_source_urls"
                        )
                        or []
                    )
                    if supporting_urls:
                        st.write(
                            {
                                "supporting_source_urls":
                                supporting_urls
                            }
                        )


                with st.expander(
                    "Optional local-Ollama second opinion",
                    expanded=False,
                ):
                    st.caption(
                        "Advisory only. Ollama runs only after an explicit click "
                        "and does not save a review automatically."
                    )
                    mined_local_models = local_ollama_models()
                    if not mined_local_models:
                        st.info(
                            "No local Ollama model is configured in the model "
                            "catalogue."
                        )
                    else:
                        mined_model_label = st.selectbox(
                            "Local Ollama model",
                            list(mined_local_models),
                            key=(
                                "tqd3_mined_candidate_ollama_model_"
                                + selected_candidate_id
                            ),
                        )
                        mined_model = mined_local_models[
                            mined_model_label
                        ]
                        if st.button(
                            "Ask Ollama for candidate second opinion",
                            key=(
                                "tqd3_ask_mined_candidate_ollama_"
                                + selected_candidate_id
                            ),
                        ):
                            try:
                                with st.spinner(
                                    "Asking local Ollama..."
                                ):
                                    mined_ai_result = (
                                        ask_local_ollama_candidate_review(
                                            selected_candidate,
                                            model=mined_model,
                                            deterministic_suggestion=(
                                                candidate_review_suggestions.get(
                                                    selected_candidate_id,
                                                    {},
                                                )
                                            ),
                                        )
                                    )
                                mined_ai_state = (
                                    st.session_state.setdefault(
                                        "tqd3_mined_candidate_ai_suggestions_v1",
                                        {},
                                    )
                                )
                                if not isinstance(
                                    mined_ai_state,
                                    dict,
                                ):
                                    mined_ai_state = {}
                                mined_ai_state[
                                    selected_candidate_id
                                ] = mined_ai_result
                                st.session_state[
                                    "tqd3_mined_candidate_ai_suggestions_v1"
                                ] = mined_ai_state
                                st.rerun()
                            except Exception as exc:
                                st.error(
                                    "Local Ollama candidate review failed: "
                                    f"{exc}"
                                )

                        mined_ai_state = st.session_state.get(
                            "tqd3_mined_candidate_ai_suggestions_v1",
                            {},
                        )
                        if isinstance(
                            mined_ai_state,
                            dict,
                        ):
                            mined_ai_result = (
                                mined_ai_state.get(
                                    selected_candidate_id
                                )
                            )
                        else:
                            mined_ai_result = None
                        if isinstance(
                            mined_ai_result,
                            dict,
                        ):
                            st.json(mined_ai_result)
                            st.caption(
                                "Copy this advisory decision into the human "
                                "review form only if you agree with it."
                            )
                decision_labels = {
                    "research_further":
                        "Research further",
                    "defer": "Defer",
                    "reject": "Reject",
                }
                existing_decision = str(
                    existing_candidate_review.get(
                        "decision"
                    )
                    or "research_further"
                )
                decision_values = list(
                    BROAD_MINING_CANDIDATE_REVIEW_DECISIONS
                )
                decision_index = (
                    decision_values.index(
                        existing_decision
                    )
                    if existing_decision
                    in decision_values
                    else 0
                )

                with st.form(
                    "tqd3_mined_candidate_review_form"
                ):
                    selected_decision = st.selectbox(
                        "Review decision",
                        decision_values,
                        index=decision_index,
                        format_func=lambda value: (
                            decision_labels.get(
                                value,
                                value,
                            )
                        ),
                    )
                    review_notes = st.text_area(
                        "Review notes",
                        value=str(
                            existing_candidate_review.get(
                                "notes"
                            )
                            or ""
                        ),
                        help=(
                            "Record why this candidate should be researched "
                            "further, deferred, or rejected."
                        ),
                    )
                    save_candidate_review = (
                        st.form_submit_button(
                            "Save candidate review"
                        )
                    )

                if save_candidate_review:
                    try:
                        save_broad_mining_candidate_review(
                            candidate=selected_candidate,
                            decision=selected_decision,
                            notes=review_notes,
                        )
                    except Exception as exc:
                        st.error(
                            "Candidate review not saved: "
                            f"{exc}"
                        )
                    else:
                        st.success(
                            "Candidate review saved locally. "
                            "No Tavily call or proposal creation occurred."
                        )
                        st.rerun()

                if existing_candidate_review:
                    if st.button(
                        "Clear candidate review",
                        key=(
                            "tqd3_clear_mined_candidate_review_"
                            + selected_candidate_id
                        ),
                    ):
                        delete_broad_mining_candidate_review(
                            selected_candidate_id
                        )
                        st.rerun()
            else:
                st.info(
                    "No possible-new or ambiguous Broad Mining "
                    "candidates are currently available for review."
                )

    export_research = (
        load_latest_broad_mining_research_results(
            limit=100
        )
    )
    if export_research:
        export_artifacts = (
            list_broad_mining_research_artifacts(
                limit=100
            )
        )
        export_candidate_report = (
            build_broad_mining_candidate_report(
                export_research
            )
        )
        export_candidate_rows = (
            export_candidate_report.get(
                "candidates",
                [],
            )
            if isinstance(
                export_candidate_report,
                dict,
            )
            else []
        )
        export_suggestions = {
            str(candidate.get("candidate_id") or ""):
                build_broad_mining_review_suggestion(
                    candidate
                )
            for candidate in export_candidate_rows
            if (
                isinstance(candidate, dict)
                and str(
                    candidate.get("candidate_id")
                    or ""
                )
            )
        }
        export_reviews = (
            list_broad_mining_candidate_reviews()
        )
        export_zip = build_broad_mining_debug_zip(
            research_artifacts=export_artifacts,
            raw_research=export_research,
            candidate_report=export_candidate_report,
            candidate_reviews=export_reviews,
            suggestions=export_suggestions,
        )
        export_summary_csv = (
            build_broad_mining_candidate_summary_csv(
                export_candidate_report,
                export_reviews,
                export_suggestions,
            )
        )

        with st.expander(
            "Broad Mining export / debug",
            expanded=False,
        ):
            st.caption(
                "Export the complete persisted Broad Mining state. Downloads "
                "are local only and make no Tavily/Ollama/OpenAI call, create "
                "no proposal, and perform no registry/taxonomy/scoring "
                "mutation."
            )
            ex1, ex2, ex3 = st.columns(3)
            ex1.metric(
                "Saved domains",
                len(export_research),
            )
            ex2.metric(
                "Candidates",
                len(export_candidate_rows),
            )
            ex3.metric(
                "Human reviews",
                len(export_reviews),
            )

            d1, d2, d3 = st.columns(3)
            d1.download_button(
                "Download full debug ZIP",
                data=export_zip,
                file_name=(
                    "tqd3_broad_mining_full_debug.zip"
                ),
                mime="application/zip",
                key="tqd3_broad_mining_full_debug_zip",
                type="primary",
            )
            d2.download_button(
                "Candidate summary CSV",
                data=export_summary_csv,
                file_name=(
                    "tqd3_broad_mining_candidate_summary.csv"
                ),
                mime="text/csv",
                key="tqd3_broad_mining_candidate_summary_csv",
            )
            d3.download_button(
                "All candidates JSON",
                data=json.dumps(
                    export_candidate_report,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                file_name=(
                    "tqd3_broad_mining_candidates.json"
                ),
                mime="application/json",
                key="tqd3_broad_mining_candidates_json",
            )

            d4, d5, d6 = st.columns(3)
            d4.download_button(
                "Raw research JSON",
                data=json.dumps(
                    export_research,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                file_name=(
                    "tqd3_broad_mining_raw_research.json"
                ),
                mime="application/json",
                key="tqd3_broad_mining_raw_research_json",
            )
            d5.download_button(
                "Candidate reviews JSON",
                data=json.dumps(
                    export_reviews,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                file_name=(
                    "tqd3_broad_mining_candidate_reviews.json"
                ),
                mime="application/json",
                key="tqd3_broad_mining_reviews_json",
            )
            d6.download_button(
                "Deterministic suggestions JSON",
                data=json.dumps(
                    export_suggestions,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                file_name=(
                    "tqd3_broad_mining_review_suggestions.json"
                ),
                mime="application/json",
                key="tqd3_broad_mining_suggestions_json",
            )

            with st.expander(
                "Preview export manifest",
                expanded=False,
            ):
                st.json(
                    {
                        "export_version":
                            BROAD_MINING_EXPORT_VERSION,
                        "saved_domains":
                            len(export_research),
                        "candidate_count":
                            len(export_candidate_rows),
                        "human_review_count":
                            len(export_reviews),
                        "files_in_debug_zip": [
                            "README.txt",
                            "export_manifest.json",
                            "research_artifacts.json",
                            "raw_research.json",
                            "candidate_report.json",
                            "candidate_reviews.json",
                            "deterministic_review_suggestions.json",
                            "candidate_summary.csv",
                        ],
                    }
                )
    hide_researched = st.toggle(
        "Hide already researched domains",
        value=True,
        key="tqd3_hide_researched_domains",
        help=(
            "Researched domains remain saved locally. Turn this off only "
            "when you intentionally want to inspect or research one again."
        ),
    )
    if hide_researched:
        queue = [
            row
            for row in enriched_queue
            if row.get("research_status") != "Researched"
        ]
        if researched_count:
            st.caption(
                f"{researched_count} researched domain(s) hidden. "
                "Turn off 'Hide already researched domains' to view or "
                "research them again."
            )
    else:
        queue = enriched_queue
        if researched_count:
            st.caption(
                "Researched domains are visible. Selecting one and running "
                "Broad Mining will make a new Tavily Research call."
            )
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Remaining selectable domains", len(queue))
    q2.metric(
        "Research batch limit",
        MAX_BROAD_RESEARCH_BATCH_SEEDS,
    )
    q3.metric(
        "API key",
        "Configured" if tavily_api_key_from_env() else "Missing",
    )
    q4.metric("Candidate extraction", "Available")

    _render_tavily_official_usage()

    search_text = st.text_input(
        "Search mining domains",
        placeholder="messaging, databases, observability...",
        key="tqd3_broad_mining_search",
    ).strip().lower()

    filtered = [
        row
        for row in queue
        if (
            not search_text
            or search_text in json.dumps(
                row,
                ensure_ascii=False,
            ).lower()
        )
    ]

    table_event = st.dataframe(
        [
            {
                "domain": row["domain"],
                "scope": row["scope"],
                "seed_id": row["seed_id"],
                "tavily_eligible": row["tavily_eligible"],
            }
            for row in filtered
        ],
        width="stretch",
        hide_index=True,
        key="tqd3_broad_mining_table",
        on_select="rerun",
        selection_mode="multi-row",
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

    valid_selected_rows = [
        int(index)
        for index in selected_rows
        if isinstance(index, int)
        and 0 <= int(index) < len(filtered)
    ]
    selected_seeds = [
        filtered[index]
        for index in valid_selected_rows
    ]

    if not selected_seeds:
        st.caption(
            "Select one or more seed domains to prepare broad Tavily research."
        )
        return

    st.markdown("### Broad mining research")

    saved_artifacts = list_broad_mining_research_artifacts(
        limit=100
    )
    with st.expander(
        "Saved broad-mining research",
        expanded=False,
    ):
        st.caption(
            "Completed raw Broad Mining research is stored in the existing "
            "local taxonomy-discovery SQLite database. Candidate extraction, "
            "registry matching, and source authority are recomputed when "
            "rendered. No Tavily call is made when loading saved research."
        )
        if saved_artifacts:
            st.dataframe(
                [
                    {
                        "domain": row.get("domain"),
                        "technologies": row.get(
                            "technology_count",
                            0,
                        ),
                        "sources": row.get(
                            "source_count",
                            0,
                        ),
                        "model": row.get(
                            "research_model",
                            "",
                        ),
                        "saved_at": row.get("updated_at"),
                        "artifact_id": row.get(
                            "artifact_id"
                        ),
                    }
                    for row in saved_artifacts
                ],
                width="stretch",
                hide_index=True,
            )
            if st.button(
                "Reload latest saved research",
                key="tqd3_reload_saved_broad_mining",
            ):
                loaded_saved_results = (
                    load_latest_broad_mining_research_results(
                        limit=100
                    )
                )
                reloaded_state = {
                    str(
                        row.get("target_id")
                        or row.get("target_key")
                        or row.get("seed_id")
                        or row.get("domain")
                        or index
                    ): row
                    for index, row in enumerate(
                        loaded_saved_results
                    )
                    if isinstance(row, dict)
                }
                st.session_state[
                    "tqd3_broad_mining_results_v1"
                ] = reloaded_state
                st.session_state.pop(
                    "tqd3_broad_mining_persisted_signature_v1",
                    None,
                )
                st.success(
                    "Loaded saved Broad Mining research from local SQLite. "
                    "No Tavily call was made."
                )
                st.rerun()
        else:
            st.caption(
                "No saved Broad Mining research artifacts yet."
            )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Selected domains", len(selected_seeds))
    m2.metric("Planned Research tasks", len(selected_seeds))
    m3.metric("Research model", TAVILY_RESEARCH_MODEL)
    m4.metric(
        "Candidate extraction",
        "Enabled",
    )
    _render_tavily_local_usage(
        planned_credits=None,
    )

    selected_seed_ids = [
        str(row.get("seed_id") or "")
        for row in selected_seeds
    ]

    blocking: list[str] = []
    if not tavily_api_key_from_env():
        blocking.append(
            "Set TAVILY_API_KEY in the environment and restart Streamlit."
        )
    if len(selected_seeds) > MAX_BROAD_RESEARCH_BATCH_SEEDS:
        blocking.append(
            "Selection exceeds the Tavily Research safety limit of "
            f"{MAX_BROAD_RESEARCH_BATCH_SEEDS} domains."
        )

    if blocking:
        for reason in blocking:
            st.warning(reason)

    if st.button(
        f"Research {len(selected_seeds)} broad domain(s) with "
        f"Tavily Research ({TAVILY_RESEARCH_MODEL})",
        key="tqd3_run_broad_mining",
        disabled=bool(blocking),
        type="primary",
    ):
        try:
            with st.spinner(
                f"Running {len(selected_seeds)} Tavily Research task(s)..."
            ):
                batch_results = research_selected_broad_mining_with_tavily(
                    queue,
                    selected_seed_ids=selected_seed_ids,
                    model=TAVILY_RESEARCH_MODEL,
                )
        except (
            ValueError,
            TavilyResearchError,
            TavilyResearchAgentError,
        ) as exc:
            st.error(f"Broad mining research failed: {exc}")
        except Exception as exc:
            st.error(
                "Unexpected broad mining error. No taxonomy, registry, "
                f"proposal, or scoring change was made: {exc}"
            )
        else:
            state_key = "tqd3_broad_mining_results_v1"
            state = st.session_state.setdefault(state_key, {})
            if not isinstance(state, dict):
                state = {}
            for result in batch_results:
                seed_id = str(result.get("seed_id") or "")
                if seed_id:
                    state[seed_id] = result
            st.session_state[state_key] = state
            st.success(
                f"Stored {len(batch_results)} broad mining result(s) "
                "in this Streamlit session."
            )
            st.rerun()

    state = st.session_state.get(
        "tqd3_broad_mining_results_v1",
        {},
    )
    if not isinstance(state, dict):
        state = {}

    visible_results = [
        state[seed_id]
        for seed_id in selected_seed_ids
        if isinstance(state.get(seed_id), dict)
    ]
    if not visible_results:
        return

    st.warning(
        "Broad mining results are untrusted structured research evidence. "
        "Candidate extraction and exact registry dedupe are deterministic "
        "and read-only. Proposal creation and registry promotion remain "
        "disabled pending human review."
    )

    for result in visible_results:
        domain = str(
            result.get("domain")
            or result.get("target_label")
            or result.get("seed_id")
            or "Mining result"
        )
        source_count = int(result.get("source_count") or 0)
        with st.expander(
            f"{domain} · {source_count} source(s)",
            expanded=len(visible_results) == 1,
        ):
            st.markdown("**Research input**")
            st.write(result.get("research_question") or "—")
            st.caption(
                "Tavily Research model: "
                f"{result.get('research_model') or '—'} · "
                "provider-returned structured output remains untrusted."
            )

            structured = result.get("structured_output")
            technologies = (
                structured.get("technologies", [])
                if isinstance(structured, dict)
                else []
            )
            st.markdown("**Structured technologies**")
            if technologies:
                st.dataframe(
                    technologies,
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.caption(
                    "Tavily Research returned no structured "
                    "technology rows."
                )

            candidate_report = (
                build_broad_mining_candidate_report([result])
            )
            candidate_rows = candidate_report.get(
                "candidates",
                [],
            )

            st.markdown("**Mining candidates**")
            st.caption(
                "Candidate status uses the exact canonical technology name "
                "returned in structured research and compares it only with "
                "an exact registry label/alias. It does not scan purpose or "
                "adoption prose, use fuzzy matching, or mutate the registry. "
                "Provider source labels are not trusted as authority judgments; "
                "source authority is classified separately with versioned "
                "candidate/maintainer domain rules."
            )

            if candidate_rows:
                display_candidates = []
                for candidate in candidate_rows:
                    registry_matches = candidate.get(
                        "registry_matches",
                        [],
                    )
                    display_candidates.append(
                        {
                            "canonical_name": candidate.get(
                                "canonical_name"
                            ),
                            "status": candidate.get("status"),
                            "entity_type": ", ".join(
                                candidate.get(
                                    "entity_types",
                                    [],
                                )
                            ),
                            "registry_match": ", ".join(
                                str(match.get("label") or "")
                                for match in registry_matches
                                if isinstance(match, dict)
                                and str(
                                    match.get("label") or ""
                                ).strip()
                            ),
                            "supporting_sources": len(
                                candidate.get(
                                    "supporting_source_urls",
                                    [],
                                )
                            ),
                            "primary_official_sources": (
                                candidate.get("source_authority", {})
                                .get("counts", {})
                                .get("primary_official", 0)
                            ),
                            "other_first_party_sources": (
                                candidate.get("source_authority", {})
                                .get("counts", {})
                                .get("first_party_other_technology", 0)
                            ),
                            "secondary_sources": (
                                candidate.get("source_authority", {})
                                .get("counts", {})
                                .get("secondary", 0)
                            ),
                            "unclassified_sources": (
                                candidate.get("source_authority", {})
                                .get("counts", {})
                                .get("unclassified", 0)
                            ),
                            "has_primary_official": (
                                candidate.get("source_authority", {})
                                .get("has_primary_official", False)
                            ),
                            "candidate_id": candidate.get(
                                "candidate_id"
                            ),
                        }
                    )

                st.dataframe(
                    display_candidates,
                    width="stretch",
                    hide_index=True,
                )

                new_count = sum(
                    1
                    for candidate in candidate_rows
                    if candidate.get("status")
                    == "possible_new_technology"
                )
                known_count = sum(
                    1
                    for candidate in candidate_rows
                    if candidate.get("status")
                    == "already_known"
                )
                ambiguous_count = sum(
                    1
                    for candidate in candidate_rows
                    if candidate.get("status")
                    == "ambiguous_registry_match"
                )
                st.caption(
                    f"Possible new: {new_count} · "
                    f"Already known: {known_count} · "
                    f"Ambiguous exact matches: {ambiguous_count}. "
                    "These are untrusted candidates only; proposal creation "
                    "and registry promotion remain separate human-reviewed "
                    "stages."
                )
            else:
                st.caption(
                    "No structured technology candidates were returned."
                )

            sources = [
                row
                for row in result.get("sources", []) or []
                if isinstance(row, dict)
            ]
            if sources:
                st.markdown("**Sources**")
                st.dataframe(
                    [
                        {
                            "title": row.get("title"),
                            "url": row.get("url"),
                            "favicon": row.get("favicon"),
                        }
                        for row in sources
                    ],
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info(
                    "Tavily Research returned no usable source URLs."
                )

            with st.expander("Mining diagnostics", expanded=False):
                st.json(result)

    st.download_button(
        "Download selected broad-mining JSON",
        data=json.dumps(
            visible_results,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        file_name="tqd3_selected_broad_mining.json",
        mime="application/json",
        key="tqd3_download_broad_mining",
    )

def render_capability_discovery_review() -> None:
    st.divider()
    st.header("Capability Discovery")
    st.caption(
        f"TQ-D2.5/TQ-D2.6/TQ-D2.7/TQ-D3 · {TRIAGE_VERSION} · "
        f"{CLASSIFICATION_VERSION} · technology registry + deterministic "
        "diagnostics + explicit human review. Tavily research runs only "
        "after an explicit Research Targets action; no automatic taxonomy "
        "or registry mutation is performed."
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
        broad_mining_tab,
        registry_tab,
        research_tab,
        debug_tab,
    ) = st.tabs(
        [
            "Review Queue",
            "TQ-D3 Classification",
            "Research Targets",
            "Broad Mining",
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

    with broad_mining_tab:
        _render_tqd3_broad_mining_tab()

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

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from database.db_manager import create_empty_application_session
from database.job_match_manager import (
    init_job_match_schema,
    list_current_job_match_snapshots,
)
from database.job_discovery_manager import (
    delete_hide_rule,
    delete_target_company,
    get_job_discovery_lifecycle_counts,
    get_job_discovery_source_counts,
    get_recent_discovery_runs,
    init_job_discovery_schema,
    mark_expired_jobs,
    list_discovered_jobs,
    list_hide_rules,
    list_target_companies,
    set_hide_rule_enabled,
    set_target_company_enabled,
    upsert_hide_rule,
    upsert_target_company,
)
from job_discovery.hide_filters import job_identity, partition_hidden_jobs, rule_description
from job_discovery.faceted_search import (
    apply_job_finder_filters,
    company_counts,
    employment_type_counts,
    filter_jobs_by_companies,
    filter_jobs_by_employment_types,
    filter_jobs_by_entry_level,
    filter_jobs_by_events,
    filter_jobs_by_freshness,
    filter_jobs_by_lifecycle,
    filter_jobs_by_max_explicit_minimum_experience,
    filter_jobs_by_sources,
    source_counts,
)
from job_discovery.pipeline import refresh_job_sources
from job_discovery.ranking import lexical_relevance
from job_discovery.matching import (
    analyze_job_match,
    current_evidence_context,
    current_match_versions,
    inspect_job_match,
    inspect_job_matches,
)
from job_discovery.match_ranking import best_match_sort_key
from job_discovery.batch_matching import (
    classify_batch_jobs,
    match_display_label,
    select_pending_batch_jobs,
)
from job_discovery.result_pagination import paginate_jobs
from job_discovery.location_display import display_job_location
from job_discovery.ui_busy import render_busy_overlay
from job_discovery.view_performance import (
    clamp_page,
    match_state_cache_key,
)
from job_discovery.text_utils import matches_query


SOURCE_LABELS = {
    "mycareersfuture": "MyCareersFuture",
    "careers_gov": "Careers@Gov",
    "greenhouse": "Greenhouse company boards",
    "lever": "Lever company boards",
    "ashby": "Ashby company boards",
    "smartrecruiters": "SmartRecruiters company boards",
}


ATS_PROVIDER_LABELS = {
    "greenhouse": "Greenhouse",
    "lever": "Lever",
    "ashby": "Ashby",
    "smartrecruiters": "SmartRecruiters",
}


def _split_identifiers(value: str) -> list[str]:
    values: list[str] = []
    for line in str(value or "").replace(",", "\n").splitlines():
        cleaned = line.strip()
        if cleaned and cleaned not in values:
            values.append(cleaned)
    return values


def _safe_timestamp(value: Any) -> float:
    raw = str(value or "").strip()
    if not raw:
        return 0.0
    try:
        if raw.isdigit() and len(raw) >= 12:
            return float(raw) / 1000.0
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (ValueError, OSError, OverflowError):
        return 0.0


@st.cache_data(
    ttl=20,
    show_spinner=False,
)
def _cached_query_jobs_v16(
    active_query: str,
) -> list[dict[str, Any]]:
    """Cache the expensive 10k-row local index scan across page reruns."""
    query = str(active_query or "").strip()
    if not query:
        return []

    all_jobs = list_discovered_jobs(
        limit=10000
    )
    return [
        job
        for job in all_jobs
        if matches_query(
            query,
            job.get("title"),
            job.get("company"),
            job.get("description"),
        )
    ]


def _job_event_label(job: dict[str, Any]) -> str:
    lifecycle = str(job.get("lifecycle_status") or "active").lower()
    event = str(job.get("last_event") or "unchanged").lower()
    if lifecycle == "removed":
        return "REMOVED"
    if lifecycle == "expired":
        return "EXPIRED"
    return {
        "new": "NEW",
        "changed": "CHANGED",
        "reactivated": "REACTIVATED",
    }.get(event, "ACTIVE")


def _freshness_timestamp(job: dict[str, Any]) -> float:
    return _safe_timestamp(job.get("posted_at")) or _safe_timestamp(job.get("first_seen_at"))


def _is_entry_level(job: dict[str, Any]) -> bool:
    minimum = job.get("experience_years_min")
    if minimum is not None:
        try:
            if float(minimum) <= 2.0:
                return True
        except (TypeError, ValueError):
            pass
    text = " ".join(
        str(job.get(key) or "")
        for key in ("title", "seniority", "employment_type", "description")
    ).lower()
    return any(
        marker in text
        for marker in (
            "entry level",
            "entry-level",
            "fresh graduate",
            "fresh grad",
            "graduate programme",
            "graduate program",
            "junior ",
            "intern",
            "0-2 years",
            "0 - 2 years",
            "1-2 years",
            "1 - 2 years",
        )
    )


def _salary_label(job: dict[str, Any]) -> str:
    low = job.get("salary_min")
    high = job.get("salary_max")
    if low is None and high is None:
        return ""
    currency = str(job.get("salary_currency") or "").strip()
    period = str(job.get("salary_period") or "").strip()

    def fmt(value: Any) -> str:
        try:
            number = float(value)
            return f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}"
        except (TypeError, ValueError):
            return str(value or "")

    if low is not None and high is not None:
        amount = f"{fmt(low)}–{fmt(high)}"
    else:
        amount = fmt(low if low is not None else high)
    return " ".join(part for part in (currency, amount, period) if part)


def _handoff_to_new_application(job: dict[str, Any]) -> None:
    session_name = f"{job.get('title') or 'Job'} @ {job.get('company') or 'Unknown Company'}"
    application_id = create_empty_application_session(
        degree="",
        session_name=session_name,
    )
    st.session_state["current_application_id"] = application_id
    next_suffix = int(st.session_state.get("input_reset_counter", 0)) + 1
    st.session_state["input_reset_counter"] = next_suffix
    st.session_state[f"jd_text_{next_suffix}"] = str(job.get("description") or "")
    st.session_state[f"jd_company_{next_suffix}"] = str(job.get("company") or "")
    st.session_state[f"jd_job_title_{next_suffix}"] = str(job.get("title") or "")
    st.session_state[f"jd_location_{next_suffix}"] = str(job.get("location") or "")
    st.session_state[f"jd_source_url_{next_suffix}"] = str(
        job.get("source_url") or job.get("apply_url") or ""
    )
    st.session_state[f"jd_preferred_requirements_{next_suffix}"] = ""
    st.session_state["_pending_navigation_page"] = "Application Sessions"
    st.session_state["flash_message"] = (
        f"Created application session #{application_id} from Job Finder. "
        "Review the prefilled JD, upload your résumé, then click Analyze Resume."
    )
    st.rerun()



def _render_target_company_registry() -> None:
    targets = list_target_companies(include_disabled=True)

    st.markdown("#### Target companies")
    st.caption(
        "Save each ATS company once. Enabled targets are used automatically when you refresh "
        "Greenhouse, Lever, Ashby, or SmartRecruiters."
    )

    if targets:
        display_rows = [
            {
                "Company": str(target.get("company_name") or ""),
                "Provider": ATS_PROVIDER_LABELS.get(
                    str(target.get("ats_provider") or ""),
                    str(target.get("ats_provider") or ""),
                ),
                "Identifier": str(target.get("ats_identifier") or ""),
                "Enabled": "Yes" if target.get("enabled") else "No",
                "Careers URL": str(target.get("careers_url") or ""),
            }
            for target in targets
        ]
        st.dataframe(display_rows, width="stretch", hide_index=True)
    else:
        st.info("No ATS target companies saved yet.")

    with st.form("job_finder_target_company_form", clear_on_submit=True):
        form_col1, form_col2 = st.columns(2)
        with form_col1:
            company_name = st.text_input(
                "Company name",
                placeholder="Example Pte Ltd",
            )
            provider = st.selectbox(
                "ATS provider",
                options=list(ATS_PROVIDER_LABELS),
                format_func=lambda value: ATS_PROVIDER_LABELS[value],
            )
        with form_col2:
            identifier = st.text_input(
                "Board/site identifier or careers URL",
                placeholder="example or https://jobs.lever.co/example",
                help=(
                    "You can paste the provider careers URL or enter only its identifier. "
                    "Job AI Helper stores the normalized identifier."
                ),
            )
            careers_url = st.text_input(
                "Careers URL to remember (optional)",
                placeholder="https://...",
            )
        enabled = st.checkbox("Enabled", value=True)
        submitted = st.form_submit_button("Save target company", type="primary")
        if submitted:
            try:
                target_id = upsert_target_company(
                    company_name=company_name,
                    ats_provider=provider,
                    ats_identifier=identifier,
                    careers_url=careers_url,
                    enabled=enabled,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success(f"Saved target company #{target_id}.")
                st.rerun()

    targets = list_target_companies(include_disabled=True)
    if targets:
        st.markdown("##### Manage saved target")
        target_by_id = {int(target["id"]): target for target in targets}
        selected_id = st.selectbox(
            "Saved target",
            options=list(target_by_id),
            format_func=lambda target_id: (
                f"{target_by_id[target_id].get('company_name') or target_by_id[target_id].get('ats_identifier')} "
                f"— {ATS_PROVIDER_LABELS.get(str(target_by_id[target_id].get('ats_provider') or ''), str(target_by_id[target_id].get('ats_provider') or ''))} "
                f"({target_by_id[target_id].get('ats_identifier')})"
            ),
            key="job_finder_manage_target_id",
        )
        selected = target_by_id[int(selected_id)]
        manage_col1, manage_col2 = st.columns(2)
        with manage_col1:
            next_enabled = not bool(selected.get("enabled"))
            if st.button(
                "Disable target" if selected.get("enabled") else "Enable target",
                key=f"job_finder_toggle_target_{selected_id}",
                width="stretch",
            ):
                set_target_company_enabled(int(selected_id), next_enabled)
                st.rerun()
        with manage_col2:
            if st.button(
                "Delete target",
                key=f"job_finder_delete_target_{selected_id}",
                width="stretch",
            ):
                delete_target_company(int(selected_id))
                st.rerun()




HIDE_RULE_OPTIONS = {
    "Title contains": "title_keyword",
    "Description contains": "description_keyword",
    "Company equals": "company",
    "Seniority contains": "seniority_keyword",
    "Employment type contains": "employment_type_keyword",
    "Minimum experience greater than": "experience_min_above",
}


def _render_hide_rule_manager() -> None:
    st.caption(
        "Hide rules only affect Job Finder visibility. Jobs remain stored for lifecycle, "
        "history, diagnostics, and later review."
    )

    choice = st.selectbox(
        "Rule type",
        options=list(HIDE_RULE_OPTIONS),
        key="job_finder_hide_rule_type",
    )
    rule_type = HIDE_RULE_OPTIONS[choice]
    if rule_type == "experience_min_above":
        value: Any = st.number_input(
            "Hide jobs whose explicit minimum experience is greater than",
            min_value=0.0,
            max_value=30.0,
            value=3.0,
            step=0.5,
            key="job_finder_hide_experience_threshold",
        )
    else:
        placeholders = {
            "title_keyword": "Senior",
            "description_keyword": "security clearance",
            "company": "Example Recruitment Agency",
            "seniority_keyword": "Director",
            "employment_type_keyword": "Contract",
        }
        value = st.text_input(
            "Rule value",
            placeholder=placeholders.get(rule_type, ""),
            key="job_finder_hide_rule_value",
        )

    if st.button("Add hide rule", key="job_finder_add_hide_rule"):
        try:
            upsert_hide_rule(rule_type=rule_type, value=value)
            st.success("Hide rule saved.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    rules = list_hide_rules(include_disabled=True)
    if not rules:
        st.info("No persistent hide rules yet.")
        return

    st.write("#### Saved rules")
    for rule in rules:
        rule_id = int(rule["id"])
        enabled = bool(rule.get("enabled"))
        row = st.columns([0.14, 0.66, 0.20])
        with row[0]:
            new_enabled = st.checkbox(
                "On",
                value=enabled,
                key=f"job_hide_rule_enabled_{rule_id}",
            )
            if new_enabled != enabled:
                set_hide_rule_enabled(rule_id, new_enabled)
                st.rerun()
        with row[1]:
            st.caption(rule_description(rule))
        with row[2]:
            if st.button(
                "Delete",
                key=f"job_hide_rule_delete_{rule_id}",
                width="stretch",
            ):
                delete_hide_rule(rule_id)
                st.rerun()


def render_job_finder() -> None:
    init_job_discovery_schema()
    init_job_match_schema()
    mark_expired_jobs()

    st.divider()
    st.header("Job Finder")
    st.caption(
        "Search once, then narrow the indexed results with live filters. "
        "Changing a source, company, date, experience or employment filter immediately updates the results; "
        "it never contacts an external site."
    )

    # Query submission is intentionally separate from live filters. This mirrors
    # a conventional search engine: the text query is submitted, while facets
    # can be changed repeatedly without creating a new search snapshot.
    with st.form("job_finder_query_form_v123", clear_on_submit=False):
        query_input = st.text_input(
            "Search jobs",
            key="job_finder_query_draft_v123",
            placeholder="Software Engineer, AI Engineer, Backend Developer...",
            help="Submit the text query. Source/company/date filters are applied live afterwards.",
        )
        search_clicked = st.form_submit_button(
            "Search",
            type="primary",
            width="stretch",
        )

    if search_clicked:
        cleaned_query = query_input.strip()
        if cleaned_query:
            st.session_state["job_finder_active_query_v123"] = cleaned_query
        else:
            st.session_state.pop("job_finder_active_query_v123", None)

    active_query = str(st.session_state.get("job_finder_active_query_v123") or "").strip()
    if active_query and query_input.strip() and query_input.strip() != active_query:
        st.caption(
            f'Results are still for **"{active_query}"**. Press Search to apply the edited query.'
        )

    # Refresh is data ingestion, not a search filter. V1.2.4 keeps source
    # refresh selection completely separate from the live search facets below.
    #
    # V1.2.5 keeps refresh feedback OUTSIDE the expander so a long network
    # operation never looks like a dead button after Streamlit reruns.
    refresh_feedback_slot = st.empty()
    last_refresh_feedback = str(
        st.session_state.get("job_finder_last_refresh_feedback_v125") or ""
    ).strip()
    if last_refresh_feedback:
        refresh_feedback_slot.success(last_refresh_feedback)

    if st.checkbox(
        "Load source management & refresh",
        value=False,
        key="job_finder_load_source_management_v16",
        help="Loads refresh controls and the target-company registry only when needed.",
    ):
        st.caption(
            "Refresh updates the local index. ATS companies can be refreshed concurrently, "
            "while database writes remain serialized for SQLite safety."
        )
        refresh_sources = st.multiselect(
            "Sources to refresh",
            options=list(SOURCE_LABELS),
            default=[],
            format_func=lambda value: SOURCE_LABELS.get(value, value),
            key="job_finder_refresh_sources_v124",
            help="Choose only the external providers you want to contact.",
        )

        enabled_targets = list_target_companies(include_disabled=False)
        eligible_targets = [
            target
            for target in enabled_targets
            if str(target.get("ats_provider") or "") in refresh_sources
        ]
        target_by_key = {
            f"{target.get('ats_provider')}:{target.get('ats_identifier')}": target
            for target in eligible_targets
            if str(target.get("ats_identifier") or "").strip()
        }
        selected_refresh_targets: list[str] = []
        if target_by_key:
            selected_refresh_targets = st.multiselect(
                "Companies to fetch (refresh only, optional)",
                options=list(target_by_key),
                default=[],
                format_func=lambda key: (
                    f"{target_by_key[key].get('company_name') or target_by_key[key].get('ats_identifier')} "
                    f"— {ATS_PROVIDER_LABELS.get(str(target_by_key[key].get('ats_provider') or ''), str(target_by_key[key].get('ats_provider') or ''))}"
                ),
                key="job_finder_refresh_targets_v124",
                help=("This controls network fetching only; it does NOT filter displayed results. " "Leave blank to refresh all enabled registered companies for the selected ATS provider(s)."),
            )

        target_selection: dict[str, list[str]] = {}
        for key in selected_refresh_targets:
            target = target_by_key.get(key)
            if not target:
                continue
            provider = str(target.get("ats_provider") or "").strip()
            identifier = str(target.get("ats_identifier") or "").strip()
            if provider and identifier:
                target_selection.setdefault(provider, []).append(identifier)

        settings_col1, settings_col2 = st.columns(2)
        with settings_col1:
            max_pages = st.number_input(
                "Max pages per paginated source",
                min_value=1,
                max_value=10,
                value=3,
                step=1,
                key="job_finder_max_pages_v124",
            )
            max_workers = st.slider(
                "Parallel source/company fetches",
                min_value=1,
                max_value=6,
                value=4,
                step=1,
                key="job_finder_refresh_workers_v124",
                help="Independent HTTP fetches run in parallel; SQLite writes still happen one at a time.",
            )
        with settings_col2:
            min_refresh_interval = st.number_input(
                "Skip if refreshed within (minutes)",
                min_value=0,
                max_value=120,
                value=15,
                step=5,
                key="job_finder_refresh_min_interval_v124",
                help="Set to 0 to disable freshness skipping.",
            )
            force_full_refresh = st.checkbox(
                "Force full refresh",
                value=False,
                key="job_finder_force_full_refresh_v124",
                help=(
                    "Ignore the recent-refresh skip and force SmartRecruiters to re-fetch every job detail. "
                    "Normally SmartRecruiters reuses stored detail when its listing summary is unchanged."
                ),
            )

        target_overrides: dict[str, list[str]] = {}
        with st.expander("Advanced: one-off ATS identifiers", expanded=False):
            st.caption(
                "One-off identifiers override the saved registry for that provider for this refresh only."
            )
            if "greenhouse" in refresh_sources:
                target_overrides["greenhouse"] = _split_identifiers(
                    st.text_area("One-off Greenhouse board tokens", key="job_targets_greenhouse_v124", height=70)
                )
            if "lever" in refresh_sources:
                target_overrides["lever"] = _split_identifiers(
                    st.text_area("One-off Lever site names", key="job_targets_lever_v124", height=70)
                )
            if "ashby" in refresh_sources:
                target_overrides["ashby"] = _split_identifiers(
                    st.text_area("One-off Ashby board names", key="job_targets_ashby_v124", height=70)
                )
            if "smartrecruiters" in refresh_sources:
                target_overrides["smartrecruiters"] = _split_identifiers(
                    st.text_area("One-off SmartRecruiters company identifiers", key="job_targets_smartrecruiters_v124", height=70)
                )

        query_required = any(
            source in {"mycareersfuture", "careers_gov"}
            for source in refresh_sources
        )
        refresh_disabled = not bool(refresh_sources) or (query_required and not bool(active_query))
        refresh_clicked = st.button(
            "Refresh selected sources",
            width="stretch",
            disabled=refresh_disabled,
            key="job_finder_refresh_button_v124",
        )
        if query_required and not active_query:
            st.caption("Submit a search query before refreshing MyCareersFuture or Careers@Gov.")
        elif not refresh_sources:
            st.caption("Select at least one source to refresh.")

        if refresh_clicked:
            refresh_scope = ", ".join(
                SOURCE_LABELS.get(source, source) for source in refresh_sources
            )
            target_scope = (
                f" Selected company targets: {len(selected_refresh_targets)}."
                if selected_refresh_targets
                else " All enabled companies for selected ATS providers will be considered."
            )
            started_message = (
                f"Refreshing: {refresh_scope}.{target_scope} "
                "Search-result filters are unchanged."
            )
            refresh_feedback_slot.info(started_message)
            st.toast("Job source refresh started.", icon="🔄")

            saved_by_provider = {
                str(target.get("ats_provider") or "")
                for target in enabled_targets
                if target.get("ats_identifier")
            }
            missing_target_sources = [
                source
                for source in ("greenhouse", "lever", "ashby", "smartrecruiters")
                if (
                    source in refresh_sources
                    and not target_overrides.get(source)
                    and source not in saved_by_provider
                )
            ]
            if missing_target_sources:
                st.caption(
                    "No enabled registry targets or one-off identifiers exist for: "
                    + ", ".join(SOURCE_LABELS[source] for source in missing_target_sources)
                    + "."
                )

            progress_rows: dict[str, dict[str, Any]] = {}
            with st.status("Refreshing job sources...", expanded=True) as status:
                progress_slot = st.empty()

                def _refresh_progress(event: dict[str, Any]) -> None:
                    key = str(event.get("source_key") or "source")
                    phase = str(event.get("phase") or "")
                    summary = event.get("summary") if isinstance(event.get("summary"), dict) else {}
                    if phase == "queued":
                        row = {"Source/company": key, "State": "Queued", "Jobs": "", "Details": ""}
                    elif phase == "skipped":
                        row = {"Source/company": key, "State": "Skipped", "Jobs": 0, "Details": summary.get("error", "")}
                    elif phase == "completed":
                        reused = int(summary.get("detail_reused", 0) or 0)
                        fetched = int(summary.get("detail_fetched", 0) or 0)
                        detail_text = f"detail fetched {fetched}, reused {reused}" if (fetched or reused) else ""
                        row = {
                            "Source/company": key,
                            "State": "Done",
                            "Jobs": int(summary.get("fetched_count", 0) or 0),
                            "Details": detail_text,
                        }
                    else:
                        row = {"Source/company": key, "State": "Error", "Jobs": 0, "Details": summary.get("error", "")}
                    progress_rows[key] = row
                    progress_slot.dataframe(list(progress_rows.values()), width="stretch", hide_index=True)

                summaries = refresh_job_sources(
                    query=active_query,
                    selected_sources=list(refresh_sources),
                    max_pages=int(max_pages),
                    target_overrides=target_overrides,
                    target_selection=target_selection,
                    max_workers=int(max_workers),
                    min_refresh_interval_minutes=int(min_refresh_interval),
                    force_full_refresh=bool(force_full_refresh),
                    progress_callback=_refresh_progress,
                )
                error_count = sum(1 for summary in summaries if summary.get("status") == "error")
                skipped_count = sum(1 for summary in summaries if summary.get("status") == "skipped")
                completed_count = sum(1 for summary in summaries if summary.get("status") == "ok")
                status.update(
                    label=(
                        f"Refresh complete — {completed_count} completed, "
                        f"{skipped_count} skipped, {error_count} failed."
                    ),
                    state="error" if error_count else "complete",
                )

            _cached_query_jobs_v16.clear()
            refresh_summary_text = (
                f"Last refresh: {completed_count} completed, "
                f"{skipped_count} skipped, {error_count} failed."
            )
            st.session_state["job_finder_last_refresh_feedback_v125"] = refresh_summary_text
            if error_count:
                refresh_feedback_slot.warning(refresh_summary_text)
                st.toast("Job source refresh finished with errors.", icon="⚠️")
            else:
                refresh_feedback_slot.success(refresh_summary_text)
                st.toast("Job source refresh complete.", icon="✅")

            for summary in summaries:
                if summary.get("status") == "skipped":
                    st.caption(f"{summary['source_key']}: skipped — {summary.get('error', '')}")
                elif summary.get("status") == "ok":
                    snapshot_label = "complete snapshot" if summary.get("snapshot_complete") else "partial/search snapshot"
                    detail_bits = ""
                    if summary.get("detail_fetched") or summary.get("detail_reused"):
                        detail_bits = (
                            f", detail fetched {summary.get('detail_fetched', 0)}, "
                            f"reused {summary.get('detail_reused', 0)}"
                        )
                    st.write(
                        f"{summary['source_key']}: fetched {summary['fetched_count']}, "
                        f"new {summary['new']}, changed {summary['changed']}, "
                        f"reactivated {summary.get('reactivated', 0)}, unchanged {summary['unchanged']}, "
                        f"removed {summary.get('removed', 0)}{detail_bits}, "
                        f"{summary.get('duration_seconds', 0):.1f}s ({snapshot_label})."
                    )
                else:
                    st.warning(f"{summary['source_key']}: {summary.get('error', 'Refresh failed')}")

        st.write("### Target company registry")
        _render_target_company_registry()

    if st.checkbox(
        "Load job discovery diagnostics",
        value=False,
        key="job_finder_load_diagnostics_v16",
        help="Runs stored-record/lifecycle/run diagnostics only when enabled.",
    ):
        st.write("### Stored records")
        st.dataframe(get_job_discovery_source_counts(), width="stretch")
        st.write("### Lifecycle state")
        st.dataframe(get_job_discovery_lifecycle_counts(), width="stretch")
        st.write("### Recent refresh runs")
        st.dataframe(get_recent_discovery_runs(limit=30), width="stretch")
        st.write("### Hide rules")
        st.dataframe(list_hide_rules(include_disabled=True), width="stretch")
        st.caption(
            "MyCareersFuture is intentionally isolated because its website JSON endpoint is not a documented "
            "third-party developer API. If it changes, its adapter can fail without breaking the rest of Job AI Helper."
        )

    if not active_query:
        st.info(
            "Enter a search term and press Search. After that, source/company/date/experience filters "
            "will update results immediately without another Search click."
        )
        return

    # Query results are stable across Previous/Next reruns. Cache the
    # expensive 10k-row local index scan briefly; source refresh invalidates it.
    query_jobs = _cached_query_jobs_v16(
        active_query
    )

    st.divider()
    result_head_col, clear_col = st.columns([0.78, 0.22])
    with result_head_col:
        st.subheader(f'Results for "{active_query}"')
    with clear_col:
        clear_filters = st.button(
            "Clear filters",
            width="stretch",
            key="job_finder_clear_filters_v123",
            help="Reset live result filters without clearing the search query.",
        )

    if clear_filters:
        st.session_state["job_finder_filter_sources_v123"] = []
        st.session_state["job_finder_filter_companies_v123"] = []
        st.session_state["job_finder_filter_freshness_v123"] = "Any time"
        st.session_state["job_finder_filter_experience_v123"] = "Any"
        st.session_state["job_finder_filter_employment_v123"] = []
        st.session_state["job_finder_filter_lifecycle_v123"] = ["active"]
        st.session_state["job_finder_filter_events_v123"] = []
        st.session_state["job_finder_filter_entry_v123"] = False
        st.session_state["job_finder_show_hidden_v123"] = False
        st.rerun()

    active_hide_rules = list_hide_rules(
        include_disabled=False
    )
    visible_jobs, hidden_jobs = partition_hidden_jobs(
        query_jobs,
        active_hide_rules,
    )
    hidden_count = len(hidden_jobs)

    filter_defaults = {
        "job_finder_filter_sources_v123": [],
        "job_finder_filter_companies_v123": [],
        "job_finder_filter_freshness_v123": "Any time",
        "job_finder_filter_experience_v123": "Any",
        "job_finder_filter_employment_v123": [],
        "job_finder_filter_lifecycle_v123": ["active"],
        "job_finder_filter_events_v123": [],
        "job_finder_filter_entry_v123": False,
        "job_finder_show_hidden_v123": False,
    }
    for _filter_key, _filter_default in filter_defaults.items():
        if _filter_key not in st.session_state:
            if isinstance(_filter_default, list):
                st.session_state[_filter_key] = list(_filter_default)
            else:
                st.session_state[_filter_key] = _filter_default

    def _reset_result_page_v15() -> None:
        st.session_state["job_finder_page_v15"] = 1
        st.session_state.pop(
            "_job_finder_match_state_cache_v15",
            None,
        )

    def _clear_result_filters_v15() -> None:
        for _filter_key, _filter_default in filter_defaults.items():
            if isinstance(_filter_default, list):
                st.session_state[_filter_key] = list(_filter_default)
            else:
                st.session_state[_filter_key] = _filter_default
        _reset_result_page_v15()

    st.write("### Filters")
    st.caption(
        "Filter changes are applied atomically when you press **Apply filters**. "
        "This prevents partial/stale reruns while several controls are changing."
    )

    with st.form(
        "job_finder_filters_form_v15",
        clear_on_submit=False,
    ):
        show_hidden = st.checkbox(
            "Show hidden jobs",
            key="job_finder_show_hidden_v123",
            help=(
                "Hidden jobs remain stored. Enable this only when you want "
                "them included in the result set."
            ),
        )

        facetable_preview = (
            visible_jobs + hidden_jobs
            if show_hidden
            else visible_jobs
        )

        source_count_map = source_counts(
            facetable_preview
        )
        selected_sources = st.multiselect(
            "Filter results by source",
            options=list(SOURCE_LABELS),
            format_func=lambda value: (
                f"{SOURCE_LABELS.get(value, value)} "
                f"({source_count_map.get(value, 0)})"
            ),
            key="job_finder_filter_sources_v123",
            help="Leave blank for All sources.",
        )

        company_count_map = company_counts(
            facetable_preview
        )
        company_options = sorted(
            company_count_map,
            key=lambda value: (
                -company_count_map[value],
                value.casefold(),
            ),
        )
        selected_companies = st.multiselect(
            "Filter results by company",
            options=company_options,
            format_func=lambda value: (
                f"{value} ({company_count_map.get(value, 0)})"
            ),
            key="job_finder_filter_companies_v123",
            help=(
                "Leave blank for All companies. Source + company are applied "
                "together when the form is submitted."
            ),
        )

        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            freshness = st.selectbox(
                "Date posted",
                options=[
                    "Any time",
                    "Today",
                    "Last 3 days",
                    "Last 7 days",
                    "Last 14 days",
                ],
                key="job_finder_filter_freshness_v123",
            )
        with filter_col2:
            experience_choice = st.selectbox(
                "Maximum explicit minimum experience",
                options=[
                    "Any",
                    "1 year",
                    "2 years",
                    "3 years",
                    "5 years",
                ],
                key="job_finder_filter_experience_v123",
                help=(
                    "Unknown experience remains visible. A job is excluded only "
                    "when its parsed explicit minimum is above the ceiling."
                ),
            )
        with filter_col3:
            lifecycle_filter = st.multiselect(
                "Availability",
                options=[
                    "active",
                    "removed",
                    "expired",
                ],
                format_func=lambda value: value.title(),
                key="job_finder_filter_lifecycle_v123",
            )

        detail_col1, detail_col2 = st.columns(2)
        with detail_col1:
            event_filter = st.multiselect(
                "Last refresh event",
                options=[
                    "new",
                    "changed",
                    "reactivated",
                    "unchanged",
                ],
                format_func=lambda value: value.title(),
                key="job_finder_filter_events_v123",
                help="Leave blank for All refresh events.",
            )
        with detail_col2:
            entry_only = st.checkbox(
                "Entry / junior / graduate only",
                key="job_finder_filter_entry_v123",
            )

        employment_count_map = employment_type_counts(
            facetable_preview
        )
        employment_options = sorted(
            employment_count_map,
            key=lambda value: (
                -employment_count_map[value],
                value.casefold(),
            ),
        )
        selected_employment = st.multiselect(
            "Employment type",
            options=employment_options,
            format_func=lambda value: (
                f"{value} ({employment_count_map.get(value, 0)})"
            ),
            key="job_finder_filter_employment_v123",
            help="Leave blank for All employment types.",
        )

        apply_col, clear_col = st.columns(2)
        with apply_col:
            st.form_submit_button(
                "Apply filters",
                type="primary",
                width="stretch",
                on_click=_reset_result_page_v15,
            )
        with clear_col:
            st.form_submit_button(
                "Clear filters",
                width="stretch",
                on_click=_clear_result_filters_v15,
            )

    facetable_jobs = (
        visible_jobs + hidden_jobs
        if show_hidden
        else visible_jobs
    )

    freshness_days = {
        "Today": 1,
        "Last 3 days": 3,
        "Last 7 days": 7,
        "Last 14 days": 14,
    }.get(freshness)

    experience_ceiling = {
        "Any": None,
        "1 year": 1.0,
        "2 years": 2.0,
        "3 years": 3.0,
        "5 years": 5.0,
    }[experience_choice]

    authoritative_filters = apply_job_finder_filters(
        facetable_jobs,
        selected_sources=selected_sources,
        selected_companies=selected_companies,
        max_age_days=freshness_days,
        max_experience_years=experience_ceiling,
        selected_lifecycle_statuses=lifecycle_filter,
        selected_events=event_filter,
        selected_employment_types=selected_employment,
        entry_only=entry_only,
    )
    jobs = authoritative_filters["jobs"]
    filter_trace = [
        {
            "Stage": "Text query + hide preference",
            "Jobs": len(facetable_jobs),
        },
        *authoritative_filters["trace"][1:],
    ]

    st.caption(
        f"{len(query_jobs)} indexed job(s) match the text query · "
        f"{len(facetable_jobs)} after hide preference · "
        f"{len(jobs)} after applied filters."
    )
    if hidden_count:
        st.caption(
            (
                f"{hidden_count} hidden job(s) are included."
                if show_hidden
                else f"{hidden_count} hidden job(s) are suppressed."
            )
        )

    if st.checkbox(
        "Load hide / exclusion rule manager",
        value=False,
        key="job_finder_load_hide_manager_v16",
        help="Loads the full hide-rule editor only when enabled.",
    ):
        _render_hide_rule_manager()

    active_filter_bits: list[str] = []
    if selected_sources:
        active_filter_bits.append(
            "Source: " + ", ".join(SOURCE_LABELS.get(value, value) for value in selected_sources)
        )
    if selected_companies:
        active_filter_bits.append("Company: " + ", ".join(selected_companies))
    if freshness != "Any time":
        active_filter_bits.append(f"Date: {freshness}")
    if experience_choice != "Any":
        active_filter_bits.append(f"Experience: ≤ {experience_choice} explicit minimum")
    if lifecycle_filter:
        active_filter_bits.append(
            "Availability: "
            + ", ".join(value.title() for value in lifecycle_filter)
        )
    if event_filter:
        active_filter_bits.append("Event: " + ", ".join(value.title() for value in event_filter))
    if selected_employment:
        active_filter_bits.append("Employment: " + ", ".join(selected_employment))
    if entry_only:
        active_filter_bits.append("Entry/junior/graduate")
    if show_hidden:
        active_filter_bits.append("Showing hidden")

    if active_filter_bits:
        st.caption("Active filters · " + " · ".join(active_filter_bits))
    else:
        st.caption("No optional live filters are active. Source and company are currently All.")

    with st.expander("Filter pipeline diagnostics", expanded=False):
        st.caption(
            "Authoritative filter pipeline. Every count below is recomputed "
            "from the same post-query/post-hide base set on every Streamlit "
            "rerun. The final count is the exact input to sorting."
        )
        st.dataframe(filter_trace, width="stretch", hide_index=True)
        if freshness_days is not None:
            st.caption(
                "Freshness uses posted_at when available and falls back to first_seen_at when "
                "a source did not provide a posting date."
            )
        if experience_ceiling is not None:
            st.caption(
                "Experience is conservative: jobs with no parsed explicit minimum remain visible."
            )

    filtered_jobs = list(jobs)
    total_filtered_jobs = len(filtered_jobs)

    navigation_busy = bool(
        st.session_state.pop(
            "_job_finder_navigation_busy_v16",
            False,
        )
    )
    navigation_busy_slot = st.empty()
    if navigation_busy:
        with navigation_busy_slot.container():
            render_busy_overlay(
                st,
                "Loading the requested Job Finder page...",
            )

    if st.session_state.pop(
        "_job_finder_best_match_after_batch_v15",
        False,
    ):
        st.session_state["job_finder_sort_v1"] = "Best match"
        st.session_state["job_finder_page_v15"] = 1

    if "job_finder_sort_v1" not in st.session_state:
        st.session_state["job_finder_sort_v1"] = "Search relevance"
    if "job_finder_page_size_v15" not in st.session_state:
        st.session_state["job_finder_page_size_v15"] = 20

    def _reset_view_page_v16() -> None:
        st.session_state["job_finder_page_v15"] = 1
        st.session_state[
            "_job_finder_navigation_busy_v16"
        ] = True

    with st.form(
        "job_finder_view_form_v15",
        clear_on_submit=False,
    ):
        view_col1, view_col2 = st.columns(2)
        with view_col1:
            sort_choice = st.selectbox(
                "Sort results by",
                options=[
                    "Search relevance",
                    "Best match",
                    "Newest",
                ],
                key="job_finder_sort_v1",
                help=(
                    "Sort is applied to the complete filtered result set before "
                    "pagination. Press Apply sort / page size to commit changes."
                ),
            )
        with view_col2:
            page_size = int(
                st.selectbox(
                    "Results per page",
                    options=[10, 20, 30, 50],
                    key="job_finder_page_size_v15",
                )
            )

        st.form_submit_button(
            "Apply sort / page size",
            width="stretch",
            on_click=_reset_view_page_v16,
        )

    match_context = current_evidence_context()
    evidence_count = int(
        match_context.get("evidence_item_count", 0) or 0
    )
    match_versions = current_match_versions()

    def _cached_match_states_v16(
        job_rows: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        cache_key = match_state_cache_key(
            job_rows,
            evidence_fingerprint=str(
                match_context.get("evidence_fingerprint") or ""
            ),
            versions=match_versions,
        )
        cache = st.session_state.get(
            "_job_finder_match_state_cache_v15"
        )
        if not isinstance(cache, dict):
            cache = {}

        cached = cache.get(cache_key)
        if isinstance(cached, dict):
            return cached

        states = inspect_job_matches(
            job_rows,
            context=match_context,
            versions=match_versions,
        )
        cache[cache_key] = states

        while len(cache) > 8:
            oldest_key = next(iter(cache))
            cache.pop(oldest_key, None)

        st.session_state[
            "_job_finder_match_state_cache_v15"
        ] = cache
        return states

    all_match_states: dict[int, dict[str, Any]] | None = None

    if sort_choice == "Best match":
        with st.spinner(
            "Loading lightweight match summaries for Best Match sorting..."
        ):
            all_match_states = _cached_match_states_v16(
                filtered_jobs
            )

        def _current_snapshot_for_sort(
            job: dict[str, Any],
        ) -> dict[str, Any] | None:
            state = (all_match_states or {}).get(
                int(job.get("id", 0) or 0),
                {},
            )
            if state.get("status") != "current":
                return None
            snapshot = state.get("snapshot")
            return snapshot if isinstance(snapshot, dict) else None

        sorted_jobs = sorted(
            filtered_jobs,
            key=lambda job: best_match_sort_key(
                _current_snapshot_for_sort(job),
                search_relevance=lexical_relevance(
                    job,
                    active_query,
                ),
                freshness_timestamp=(
                    _safe_timestamp(job.get("posted_at"))
                    or _safe_timestamp(job.get("last_seen_at"))
                ),
                discovered_job_id=int(job.get("id", 0) or 0),
            ),
            reverse=True,
        )
    elif sort_choice == "Newest":
        sorted_jobs = sorted(
            filtered_jobs,
            key=lambda job: (
                _safe_timestamp(job.get("posted_at"))
                or _safe_timestamp(job.get("last_seen_at")),
                lexical_relevance(job, active_query),
                -int(job.get("id", 0) or 0),
            ),
            reverse=True,
        )
    else:
        sorted_jobs = sorted(
            filtered_jobs,
            key=lambda job: (
                lexical_relevance(job, active_query),
                _safe_timestamp(job.get("posted_at"))
                or _safe_timestamp(job.get("last_seen_at")),
                -int(job.get("id", 0) or 0),
            ),
            reverse=True,
        )

    total_pages = max(
        1,
        (len(sorted_jobs) + page_size - 1) // page_size,
    )
    current_page = clamp_page(
        int(
            st.session_state.get(
                "job_finder_page_v15",
                1,
            )
            or 1
        ),
        total_pages,
    )
    st.session_state["job_finder_page_v15"] = current_page

    def _move_page_v16(delta: int) -> None:
        current = int(
            st.session_state.get(
                "job_finder_page_v15",
                1,
            )
            or 1
        )
        st.session_state["job_finder_page_v15"] = clamp_page(
            current + int(delta),
            total_pages,
        )
        st.session_state[
            "_job_finder_navigation_busy_v16"
        ] = True

    nav_col1, nav_col2, nav_col3 = st.columns(
        [0.2, 0.6, 0.2]
    )
    with nav_col1:
        st.button(
            "← Previous",
            key="job_finder_prev_page_v15",
            disabled=(current_page <= 1),
            width="stretch",
            on_click=_move_page_v16,
            args=(-1,),
        )
    with nav_col2:
        st.markdown(
            f"<div style='text-align:center; padding-top:0.45rem;'>"
            f"<strong>Page {current_page} of {total_pages}</strong>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with nav_col3:
        st.button(
            "Next →",
            key="job_finder_next_page_v15",
            disabled=(current_page >= total_pages),
            width="stretch",
            on_click=_move_page_v16,
            args=(1,),
        )

    page_result = paginate_jobs(
        sorted_jobs,
        page=current_page,
        page_size=page_size,
    )
    page_jobs = page_result["jobs"]
    page_start_index = int(page_result["start_index"])

    first_visible = page_start_index + 1 if page_jobs else 0
    last_visible = int(page_result["end_index"])

    st.write(f"### {total_filtered_jobs} matching job(s)")
    st.caption(
        f"Showing {first_visible}–{last_visible} · "
        f"Page {current_page}/{total_pages} · "
        f"Applied sort: {sort_choice}."
    )

    if sort_choice == "Best match":
        page_match_states = {
            int(job.get("id", 0) or 0): (all_match_states or {}).get(
                int(job.get("id", 0) or 0),
                {
                    "status": "none",
                    "snapshot": None,
                    "stale_reasons": [],
                },
            )
            for job in page_jobs
        }
    else:
        page_match_states = _cached_match_states_v16(
            page_jobs
        )

    if navigation_busy:
        navigation_busy_slot.empty()

    integrity_errors: list[str] = []

    if selected_sources:
        allowed_sources = {
            str(value or "").strip().casefold()
            for value in selected_sources
        }
        wrong_sources = sorted(
            {
                str(job.get("source") or "").strip()
                for job in page_jobs
                if str(job.get("source") or "").strip().casefold()
                not in allowed_sources
            }
        )
        if wrong_sources:
            integrity_errors.append(
                "source mismatch: " + ", ".join(wrong_sources)
            )

    if selected_companies:
        allowed_companies = {
            str(value or "").strip().casefold()
            for value in selected_companies
        }
        wrong_companies = sorted(
            {
                str(job.get("company") or "").strip()
                for job in page_jobs
                if str(job.get("company") or "").strip().casefold()
                not in allowed_companies
            }
        )
        if wrong_companies:
            integrity_errors.append(
                "company mismatch: " + ", ".join(wrong_companies)
            )

    if integrity_errors:
        st.error(
            "Rendered-result filter integrity failure · "
            + " · ".join(integrity_errors)
        )

    show_view_diagnostics = st.checkbox(
        "Show view / sort diagnostics",
        value=False,
        key="job_finder_show_view_diagnostics_v15",
    )

    if show_view_diagnostics:
        diagnostic_rows = []
        for offset, diagnostic_job in enumerate(
            page_jobs,
            start=1,
        ):
            state = page_match_states.get(
                int(diagnostic_job.get("id", 0) or 0),
                {},
            )
            snapshot = (
                state.get("snapshot")
                if state.get("status") == "current"
                else None
            )
            summary = (
                snapshot.get("summary")
                if isinstance(snapshot, dict)
                and isinstance(snapshot.get("summary"), dict)
                else {}
            )
            diagnostic_rows.append(
                {
                    "Rank": page_start_index + offset,
                    "Title": str(diagnostic_job.get("title") or ""),
                    "Company": str(diagnostic_job.get("company") or ""),
                    "Source": str(diagnostic_job.get("source") or ""),
                    "Match state": str(state.get("status") or "none"),
                    "Ranking status": str(summary.get("ranking_status") or ""),
                    "Alignment": (
                        summary.get("deterministic_alignment_score")
                        if summary
                        else None
                    ),
                    "Important taxonomy %": (
                        summary.get("important_taxonomy_coverage_pct")
                        if summary
                        else None
                    ),
                    "Search relevance": round(
                        lexical_relevance(
                            diagnostic_job,
                            active_query,
                        ),
                        2,
                    ),
                    "Posted": str(
                        diagnostic_job.get("posted_at") or ""
                    ),
                }
            )

        st.dataframe(
            diagnostic_rows,
            width="stretch",
            hide_index=True,
        )

    if not page_jobs:
        st.info("No jobs are available on this page.")
        return

    if all_match_states is not None:
        visible_match_coverage = classify_batch_jobs(
            sorted_jobs,
            all_match_states,
        )
        visible_coverage_label = "Filtered-result Candidate Match coverage"
    else:
        visible_match_coverage = classify_batch_jobs(
            page_jobs,
            page_match_states,
        )
        visible_coverage_label = "Current-page Candidate Match coverage"

    st.write(f"#### {visible_coverage_label}")
    coverage_col1, coverage_col2, coverage_col3, coverage_col4 = st.columns(4)
    coverage_col1.metric(
        "Current",
        visible_match_coverage["current_count"],
    )
    coverage_col2.metric(
        "Stale",
        visible_match_coverage["stale_count"],
    )
    coverage_col3.metric(
        "Not analyzed",
        visible_match_coverage["not_analyzed_count"],
    )
    coverage_col4.metric(
        "Not analyzable",
        visible_match_coverage["not_analyzable_count"],
    )

    if all_match_states is not None:
        analyzable_total = (
            visible_match_coverage["current_count"]
            + visible_match_coverage["pending_count"]
        )
        st.caption(
            f"Best Match currently has current candidate-fit snapshots for "
            f"{visible_match_coverage['current_count']}/{max(1, analyzable_total)} "
            "analyzable filtered jobs. Missing/stale jobs can be processed from "
            "Batch candidate matching below."
        )
    else:
        st.caption(
            "This coverage is for the current page only. Choose Best Match or "
            "select All filtered results in Batch candidate matching to load "
            "full filtered-set coverage."
        )

    st.write("### Page results")

    result_rows: list[dict[str, Any]] = []
    page_job_by_id: dict[int, dict[str, Any]] = {}

    for offset, result_job in enumerate(page_jobs, start=1):
        job_id = int(result_job.get("id", 0) or 0)
        page_job_by_id[job_id] = result_job
        state = page_match_states.get(job_id, {})
        snapshot = (
            state.get("snapshot")
            if state.get("status") == "current"
            else None
        )
        summary = (
            snapshot.get("summary")
            if isinstance(snapshot, dict)
            and isinstance(snapshot.get("summary"), dict)
            else {}
        )
        match_label = match_display_label(
            result_job,
            state,
        )

        result_rows.append(
            {
                "Rank": page_start_index + offset,
                "Title": str(result_job.get("title") or ""),
                "Company": str(result_job.get("company") or ""),
                "Source": SOURCE_LABELS.get(
                    str(result_job.get("source") or ""),
                    str(result_job.get("source") or ""),
                ),
                "Location": display_job_location(result_job),
                "Match": match_label,
                "Alignment": (
                    summary.get("deterministic_alignment_score")
                    if summary
                    else None
                ),
                "Important taxonomy %": (
                    summary.get("important_taxonomy_coverage_pct")
                    if summary
                    else None
                ),
                "Posted": str(result_job.get("posted_at") or ""),
            }
        )

    st.dataframe(
        result_rows,
        width="stretch",
        hide_index=True,
    )

    page_job_ids = [
        int(job.get("id", 0) or 0)
        for job in page_jobs
        if int(job.get("id", 0) or 0) > 0
    ]
    selected_job_key = "job_finder_selected_job_v16"
    if st.session_state.get(selected_job_key) not in page_job_ids:
        st.session_state[selected_job_key] = page_job_ids[0]

    def _selected_job_label_v16(job_id: int) -> str:
        option_job = page_job_by_id.get(int(job_id), {})
        option_offset = page_job_ids.index(int(job_id)) + 1
        return (
            f"#{page_start_index + option_offset} · "
            f"{option_job.get('title') or 'Untitled'} — "
            f"{option_job.get('company') or 'Unknown Company'}"
        )

    selected_job_id = int(
        st.selectbox(
            "Open job details",
            options=page_job_ids,
            format_func=_selected_job_label_v16,
            key=selected_job_key,
            help=(
                "Only this selected job renders the full description, match "
                "metrics, diagnostics and actions."
            ),
        )
    )
    job = page_job_by_id[selected_job_id]
    page_offset = page_job_ids.index(selected_job_id) + 1
    display_rank = page_start_index + page_offset

    st.divider()
    st.subheader(
        f"#{display_rank} · "
        f"{job.get('title') or 'Untitled'} — "
        f"{job.get('company') or 'Unknown Company'}"
    )

    score = lexical_relevance(job, active_query)
    state_label = _job_event_label(job)
    hidden_reasons = list(job.get("_hide_reasons") or [])
    source_label = SOURCE_LABELS.get(
        str(job.get("source") or ""),
        str(job.get("source") or ""),
    )

    if hidden_reasons:
        st.warning("Hidden because: " + " · ".join(hidden_reasons))

    st.markdown(
        f"**Source:** {source_label} · **State:** {state_label}"
    )
    meta = [
        display_job_location(job),
        str(job.get("employment_type") or ""),
    ]
    if any(meta):
        st.caption(" · ".join(part for part in meta if part))

    scope = str(job.get("source_scope") or "").strip()
    if scope and ":" in scope:
        st.caption(f"Source scope: {scope}")

    lifecycle_bits = [
        f"first seen {job.get('first_seen_at')}" if job.get("first_seen_at") else "",
        f"last seen {job.get('last_seen_at')}" if job.get("last_seen_at") else "",
        f"last changed {job.get('last_changed_at')}" if job.get("last_changed_at") else "",
        f"removed {job.get('removed_at')}" if job.get("removed_at") else "",
    ]
    st.caption(" · ".join(bit for bit in lifecycle_bits if bit))
    st.caption(f"Deterministic search relevance: {score:.1f}")

    st.markdown("#### Candidate evidence match")
    match_state = page_match_states.get(
        selected_job_id,
        {
            "status": "none",
            "snapshot": None,
            "stale_reasons": [],
        },
    )

    analyze_label = (
        "Refresh Match"
        if match_state.get("status") == "stale"
        else "Analyze Match"
    )
    analyze_clicked = st.button(
        analyze_label,
        key=f"job_finder_analyze_match_v16_{selected_job_id}",
        disabled=(
            evidence_count <= 0
            or len(str(job.get("description") or "").strip()) < 100
        ),
    )

    if analyze_clicked:
        match_busy_slot = st.empty()
        with match_busy_slot.container():
            render_busy_overlay(
                st,
                "Analyzing the selected job...",
            )
        try:
            with st.status(
                "Analyzing requirements against Profile & Evidence...",
                expanded=True,
            ) as match_status:
                match_result = analyze_job_match(
                    job,
                    context=match_context,
                )
                st.session_state.pop(
                    "_job_finder_match_state_cache_v15",
                    None,
                )
                match_status.update(
                    label="Candidate evidence match ready.",
                    state="complete",
                )
            match_state = {
                "status": "current",
                "snapshot": match_result.get("snapshot"),
                "stale_reasons": [],
            }
        except (ValueError, RuntimeError) as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(f"Unexpected job-match error: {exc}")
        finally:
            match_busy_slot.empty()

    if match_state.get("status") == "stale":
        st.warning(
            "Saved match is stale: "
            + ", ".join(
                match_state.get("stale_reasons")
                or ["cache identity changed"]
            )
            + ". Refresh Match to recompute it."
        )
    elif match_state.get("status") == "none":
        st.caption(
            "Not analyzed yet. Search relevance is not candidate fit; "
            "Analyze Match uses your full Profile & Evidence library."
        )

    snapshot = (
        match_state.get("snapshot")
        if match_state.get("status") == "current"
        else None
    )

    if isinstance(snapshot, dict):
        match_summary = snapshot.get("summary") or {}
        ranking_eligible = bool(
            match_summary.get("ranking_eligible")
        )
        raw_alignment = int(
            match_summary.get(
                "deterministic_alignment_score",
                0,
            )
            or 0
        )

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        metric_col1.metric("Alignment", f"{raw_alignment}/100")
        metric_col2.metric(
            "Required/core",
            f"{int(match_summary.get('required_core_coverage_score', 0) or 0)}%",
        )
        metric_col3.metric(
            "Preferred",
            f"{int(match_summary.get('preferred_coverage_score', 0) or 0)}%",
        )
        metric_col4.metric(
            "Evidence strength",
            f"{int(match_summary.get('evidence_strength_score', 0) or 0)}%",
        )

        quality_col1, quality_col2, quality_col3, quality_col4 = st.columns(4)
        quality_col1.metric(
            "Important taxonomy",
            f"{int(match_summary.get('important_taxonomy_coverage_pct', 0) or 0)}%",
        )
        quality_col2.metric(
            "Overall taxonomy",
            f"{int(match_summary.get('overall_taxonomy_coverage_pct', 0) or 0)}%",
        )
        quality_col3.metric(
            "Taxonomy gaps",
            int(match_summary.get("taxonomy_gap_count", 0) or 0),
        )
        quality_col4.metric(
            "Ranking status",
            "Eligible" if ranking_eligible else "Provisional",
        )

        if not ranking_eligible:
            ranking_quality = (
                match_summary.get("ranking_quality")
                if isinstance(match_summary.get("ranking_quality"), dict)
                else {}
            )
            min_important = round(
                float(
                    ranking_quality.get(
                        "minimum_important_taxonomy_coverage",
                        0.75,
                    )
                    or 0.75
                )
                * 100
            )
            min_overall = round(
                float(
                    ranking_quality.get(
                        "minimum_overall_taxonomy_coverage",
                        0.65,
                    )
                    or 0.65
                )
                * 100
            )
            st.warning(
                f"Provisional alignment: {raw_alignment}/100. "
                "It stays visible but does not drive the trusted Best Match "
                f"tier until taxonomy coverage reaches ≥{min_important}% "
                f"important and ≥{min_overall}% overall."
            )

        important_evidence_gaps = (
            match_summary.get("important_evidence_gaps")
            or []
        )
        if important_evidence_gaps:
            st.write("**Important evidence gaps**")
            st.dataframe(
                [
                    {
                        "Importance": gap.get("importance"),
                        "Requirement": gap.get("text"),
                        "Capability": gap.get("capability_id"),
                    }
                    for gap in important_evidence_gaps
                ],
                width="stretch",
                hide_index=True,
            )

        important_taxonomy_gaps = (
            match_summary.get("important_taxonomy_gaps")
            or []
        )
        if important_taxonomy_gaps:
            st.write("**Important taxonomy gaps**")
            st.dataframe(
                [
                    {
                        "Importance": gap.get("importance"),
                        "Requirement": gap.get("text"),
                        "Capability": gap.get("capability_id"),
                    }
                    for gap in important_taxonomy_gaps
                ],
                width="stretch",
                hide_index=True,
            )

        load_full_diagnostics = st.checkbox(
            "Load full match diagnostics",
            value=False,
            key=f"job_finder_full_match_diag_v16_{selected_job_id}",
            help=(
                "Loads the full saved snapshot only for this selected job."
            ),
        )
        if load_full_diagnostics:
            full_state = inspect_job_match(
                job,
                context=match_context,
                versions=match_versions,
            )
            full_snapshot = (
                full_state.get("snapshot")
                if full_state.get("status") == "current"
                else None
            )
            if isinstance(full_snapshot, dict):
                st.json(
                    {
                        "snapshot_id": full_snapshot.get("id"),
                        "job_content_hash": full_snapshot.get("job_content_hash"),
                        "evidence_fingerprint": full_snapshot.get("evidence_fingerprint"),
                        "match_version": full_snapshot.get("match_version"),
                        "scoring_version": full_snapshot.get("scoring_version"),
                        "taxonomy_version": full_snapshot.get("taxonomy_version"),
                        "summary": full_snapshot.get("summary") or {},
                        "canonical_requirements": (
                            (full_snapshot.get("stable_analysis") or {}).get(
                                "canonical_requirements",
                                [],
                            )
                        ),
                        "validation_warnings": (
                            (full_snapshot.get("stable_analysis") or {}).get(
                                "validation_warnings",
                                [],
                            )
                        ),
                    }
                )

    salary = _salary_label(job)
    if salary:
        st.write(f"**Salary:** {salary}")
    if job.get("seniority"):
        st.write(
            f"**Seniority / experience:** {job.get('seniority')}"
        )

    st.text_area(
        "Normalized job description",
        value=str(job.get("description") or ""),
        height=220,
        disabled=True,
        key=f"job_description_preview_v16_{selected_job_id}",
    )

    action_col1, action_col2, action_col3, action_col4 = st.columns(
        [1.45, 1.10, 0.75, 0.85]
    )
    with action_col1:
        if st.button(
            "Use in new Application Session",
            key=f"job_finder_use_v16_{selected_job_id}",
            width="stretch",
            disabled=len(str(job.get("description") or "").strip()) < 100,
        ):
            _handoff_to_new_application(job)

    with action_col2:
        source_url = str(
            job.get("source_url") or job.get("apply_url") or ""
        ).strip()
        if source_url:
            st.link_button(
                "Open original posting",
                source_url,
                width="stretch",
            )
        else:
            st.button(
                "No source URL",
                key=f"job_finder_no_url_v16_{selected_job_id}",
                disabled=True,
                width="stretch",
            )

    with action_col3:
        if st.button(
            "Hide job",
            key=f"job_finder_hide_job_v16_{selected_job_id}",
            width="stretch",
            disabled=bool(hidden_reasons),
        ):
            upsert_hide_rule(
                rule_type="job",
                value=job_identity(job),
                label=(
                    f"{job.get('title') or 'Untitled'} — "
                    f"{job.get('company') or 'Unknown Company'}"
                ),
            )
            st.rerun()

    with action_col4:
        company_name = str(job.get("company") or "").strip()
        if st.button(
            "Hide company",
            key=f"job_finder_hide_company_v16_{selected_job_id}",
            width="stretch",
            disabled=not company_name or bool(hidden_reasons),
        ):
            upsert_hide_rule(
                rule_type="company",
                value=company_name,
                label=company_name,
            )
            st.rerun()

    previous_batch_feedback = str(
        st.session_state.get(
            "job_finder_batch_rank_feedback_v17",
            "",
        )
        or ""
    ).strip()
    if previous_batch_feedback:
        st.success(previous_batch_feedback)

    with st.expander(
        "Batch candidate matching",
        expanded=False,
    ):
        if "job_finder_batch_scope_v17" not in st.session_state:
            st.session_state["job_finder_batch_scope_v17"] = "Current page"
        if "job_finder_batch_chunk_size_v17" not in st.session_state:
            st.session_state["job_finder_batch_chunk_size_v17"] = 25

        with st.form(
            "job_finder_batch_form_v17",
            clear_on_submit=False,
        ):
            batch_scope = st.radio(
                "Batch analysis scope",
                options=[
                    "Current page",
                    "All filtered results",
                ],
                horizontal=True,
                key="job_finder_batch_scope_v17",
            )
            batch_chunk_size = int(
                st.selectbox(
                    "Safe batch size",
                    options=[10, 25, 50],
                    key="job_finder_batch_chunk_size_v17",
                    help=(
                        "Analyze next batch processes at most this many "
                        "missing/stale jobs. Completed snapshots persist "
                        "immediately, so the next run resumes automatically."
                    ),
                )
            )
            confirm_long_batch = st.checkbox(
                "I understand Analyze all missing/stale may make many "
                "model-backed JD extraction calls and take a long time.",
                value=False,
                key="job_finder_confirm_long_batch_v17",
            )

            button_col1, button_col2 = st.columns(2)
            with button_col1:
                analyze_next_clicked = st.form_submit_button(
                    "Analyze next missing/stale batch",
                    type="primary",
                    width="stretch",
                    disabled=(evidence_count <= 0),
                )
            with button_col2:
                analyze_all_clicked = st.form_submit_button(
                    "Analyze all missing/stale",
                    width="stretch",
                    disabled=(evidence_count <= 0),
                )

        batch_source_jobs = (
            page_jobs
            if batch_scope == "Current page"
            else sorted_jobs
        )

        if batch_scope == "Current page":
            batch_match_states = page_match_states
        else:
            if all_match_states is None:
                with st.spinner(
                    "Loading lightweight match coverage for all filtered jobs..."
                ):
                    all_match_states = _cached_match_states_v16(
                        sorted_jobs
                    )
            batch_match_states = all_match_states or {}

        batch_coverage = classify_batch_jobs(
            batch_source_jobs,
            batch_match_states,
        )

        batch_metric1, batch_metric2, batch_metric3, batch_metric4 = st.columns(4)
        batch_metric1.metric(
            "Current",
            batch_coverage["current_count"],
        )
        batch_metric2.metric(
            "Stale",
            batch_coverage["stale_count"],
        )
        batch_metric3.metric(
            "Not analyzed",
            batch_coverage["not_analyzed_count"],
        )
        batch_metric4.metric(
            "Not analyzable",
            batch_coverage["not_analyzable_count"],
        )

        st.caption(
            f"{batch_scope}: {batch_coverage['pending_count']} missing/stale "
            "analyzable job(s) remain. Current snapshots are skipped rather "
            "than recomputed."
        )

        if batch_coverage["not_analyzable_count"]:
            st.caption(
                f"{batch_coverage['not_analyzable_count']} job(s) cannot be "
                "analyzed because their persisted ID/content hash/normalized "
                "description is not sufficient for the current Job Match contract."
            )

        if analyze_next_clicked or analyze_all_clicked:
            pending_jobs = list(
                batch_coverage["pending_jobs"]
            )

            if not pending_jobs:
                st.success(
                    "No missing/stale analyzable jobs remain in this scope."
                )
            elif (
                analyze_all_clicked
                and len(pending_jobs) > batch_chunk_size
                and not confirm_long_batch
            ):
                st.warning(
                    "Confirm the long-batch checkbox before analyzing all "
                    f"{len(pending_jobs)} remaining jobs. Use Analyze next "
                    f"missing/stale batch to process only {batch_chunk_size}."
                )
            else:
                jobs_to_process = (
                    pending_jobs
                    if analyze_all_clicked
                    else select_pending_batch_jobs(
                        batch_source_jobs,
                        batch_match_states,
                        limit=batch_chunk_size,
                    )
                )

                batch_busy_slot = st.empty()
                with batch_busy_slot.container():
                    render_busy_overlay(
                        st,
                        (
                            "Analyzing "
                            f"{len(jobs_to_process)} missing/stale job(s)..."
                        ),
                    )

                ready = 0
                unexpectedly_current = 0
                refreshed = 0
                failed = 0

                try:
                    with st.status(
                        "Candidate Match batch in progress...",
                        expanded=True,
                    ) as batch_status:
                        progress = st.progress(0.0)
                        progress_text = st.empty()

                        for index, batch_job in enumerate(
                            jobs_to_process,
                            start=1,
                        ):
                            title = str(
                                batch_job.get("title")
                                or f"Job #{batch_job.get('id')}"
                            )
                            company = str(
                                batch_job.get("company")
                                or "Unknown company"
                            )
                            progress_text.caption(
                                f"{index}/{len(jobs_to_process)} · "
                                f"{title} — {company}"
                            )

                            try:
                                match_result = analyze_job_match(
                                    batch_job,
                                    context=match_context,
                                    versions=match_versions,
                                )
                            except Exception as exc:
                                failed += 1
                                batch_status.write(
                                    f"Failed {title} — {company}: {exc}"
                                )
                            else:
                                ready += 1
                                if match_result.get("cache_hit"):
                                    unexpectedly_current += 1
                                else:
                                    refreshed += 1

                            progress.progress(
                                index / max(1, len(jobs_to_process))
                            )

                        progress_text.empty()
                        batch_status.update(
                            label="Candidate Match batch complete.",
                            state="error" if failed else "complete",
                        )
                finally:
                    batch_busy_slot.empty()

                st.session_state.pop(
                    "_job_finder_match_state_cache_v15",
                    None,
                )

                attempted = len(jobs_to_process)
                feedback = (
                    f"Batch complete: {ready}/{attempted} ready · "
                    f"{refreshed} analyzed/refreshed"
                    + (
                        f" · {unexpectedly_current} became current before processing"
                        if unexpectedly_current
                        else ""
                    )
                    + (f" · {failed} failed" if failed else "")
                    + ". Re-run this batch action to resume; already-current "
                    "snapshots will be skipped."
                )

                st.session_state[
                    "job_finder_batch_rank_feedback_v17"
                ] = feedback
                st.session_state[
                    "_job_finder_best_match_after_batch_v15"
                ] = True
                st.rerun()

    if evidence_count:
        st.caption(
            f"Candidate evidence match uses all "
            f"{evidence_count} item(s) in Profile & Evidence."
        )
    else:
        st.warning(
            "Profile & Evidence is empty. Add truthful evidence before "
            "using Analyze Match."
        )


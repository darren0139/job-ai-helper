from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from database.db_manager import create_empty_application_session
from database.job_match_manager import init_job_match_schema
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
    inspect_job_match,
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

    with st.expander("Source management & refresh", expanded=False):
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

    with st.expander("Job discovery diagnostics", expanded=False):
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

    # Query is the stable base result set. Everything below is a live facet.
    all_jobs = list_discovered_jobs(limit=10000)
    query_jobs = [
        job
        for job in all_jobs
        if matches_query(
            active_query,
            job.get("title"),
            job.get("company"),
            job.get("description"),
        )
    ]

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

    # Persistent hide rules are a preference layer, not a temporary facet.
    # Show hidden bypasses that preference for inspection without deleting rules.
    show_hidden = st.checkbox(
        "Show hidden jobs",
        value=False,
        key="job_finder_show_hidden_v123",
        help="Hidden jobs remain stored. Turn this on to inspect them temporarily.",
    )
    active_hide_rules = list_hide_rules(include_disabled=False)
    visible_jobs, hidden_jobs = partition_hidden_jobs(query_jobs, active_hide_rules)
    hidden_count = len(hidden_jobs)
    facetable_jobs = visible_jobs + hidden_jobs if show_hidden else visible_jobs
    filter_trace: list[dict[str, Any]] = [
        {"Stage": "Text query + hide preference", "Jobs": len(facetable_jobs)}
    ]

    st.caption(
        f"{len(query_jobs)} indexed job(s) match the text query before live filters. "
        + (
            f"{hidden_count} hidden job(s) are included for inspection."
            if show_hidden
            else f"{hidden_count} job(s) are suppressed by persistent hide rules."
        )
    )

    st.write("### Filters")

    # SOURCE FACET: blank = All, and every change reruns Streamlit immediately.
    source_count_map = source_counts(facetable_jobs)
    selected_sources = st.multiselect(
        "Filter results by source",
        options=list(SOURCE_LABELS),
        default=[],
        format_func=lambda value: (
            f"{SOURCE_LABELS.get(value, value)} ({source_count_map.get(value, 0)})"
        ),
        key="job_finder_filter_sources_v123",
        help="Leave blank for All sources. Remove a source and its jobs disappear immediately.",
    )
    jobs = filter_jobs_by_sources(facetable_jobs, selected_sources)
    filter_trace.append({"Stage": "Source", "Jobs": len(jobs)})

    # COMPANY FACET: options come from the currently selected source scope.
    company_count_map = company_counts(jobs)
    company_options = sorted(
        company_count_map,
        key=lambda value: (-company_count_map[value], value.casefold()),
    )
    existing_companies = list(st.session_state.get("job_finder_filter_companies_v123", []))
    valid_companies = [value for value in existing_companies if value in company_count_map]
    if valid_companies != existing_companies:
        st.session_state["job_finder_filter_companies_v123"] = valid_companies

    selected_companies = st.multiselect(
        "Filter results by company",
        options=company_options,
        default=[],
        format_func=lambda value: f"{value} ({company_count_map.get(value, 0)})",
        key="job_finder_filter_companies_v123",
        help="Leave blank for All companies in the current source scope.",
    )
    jobs = filter_jobs_by_companies(jobs, selected_companies)
    filter_trace.append({"Stage": "Company", "Jobs": len(jobs)})

    if selected_companies:
        selected_company_names = {
            str(value or "").strip().casefold()
            for value in selected_companies
            if str(value or "").strip()
        }
        unexpected_companies = sorted(
            {
                str(job.get("company") or "").strip()
                for job in jobs
                if str(job.get("company") or "").strip().casefold()
                not in selected_company_names
            },
            key=str.casefold,
        )
        if unexpected_companies:
            st.error(
                "Company filter integrity check failed. Unexpected displayed companies: "
                + ", ".join(unexpected_companies)
            )
        else:
            st.caption(
                "Company result filter active: "
                + ", ".join(selected_companies)
                + f" · {len(jobs)} query-matching job(s) remain before other filters."
            )

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        freshness = st.selectbox(
            "Date posted",
            options=["Any time", "Today", "Last 3 days", "Last 7 days", "Last 14 days"],
            index=0,
            key="job_finder_filter_freshness_v123",
        )
    with filter_col2:
        experience_choice = st.selectbox(
            "Maximum explicit minimum experience",
            options=["Any", "1 year", "2 years", "3 years", "5 years"],
            index=0,
            key="job_finder_filter_experience_v123",
            help=(
                "Jobs with an unknown parsed minimum are kept. A job is excluded only when its explicit "
                "minimum is above your selected ceiling."
            ),
        )
    with filter_col3:
        lifecycle_filter = st.multiselect(
            "Availability",
            options=["active", "removed", "expired"],
            default=["active"],
            format_func=lambda value: value.title(),
            key="job_finder_filter_lifecycle_v123",
            help="Active is the normal current-job view. Add Removed/Expired when reviewing history.",
        )

    freshness_days = {
        "Today": 1,
        "Last 3 days": 3,
        "Last 7 days": 7,
        "Last 14 days": 14,
    }.get(freshness)
    jobs = filter_jobs_by_freshness(jobs, freshness_days)
    filter_trace.append({"Stage": "Posting freshness", "Jobs": len(jobs)})

    experience_ceiling = {
        "Any": None,
        "1 year": 1.0,
        "2 years": 2.0,
        "3 years": 3.0,
        "5 years": 5.0,
    }[experience_choice]
    jobs = filter_jobs_by_max_explicit_minimum_experience(jobs, experience_ceiling)
    filter_trace.append({"Stage": "Experience ceiling", "Jobs": len(jobs)})

    jobs = filter_jobs_by_lifecycle(jobs, lifecycle_filter)
    filter_trace.append({"Stage": "Availability", "Jobs": len(jobs)})

    detail_col1, detail_col2 = st.columns(2)
    with detail_col1:
        event_filter = st.multiselect(
            "Last refresh event",
            options=["new", "changed", "reactivated", "unchanged"],
            default=[],
            format_func=lambda value: value.title(),
            key="job_finder_filter_events_v123",
            help="Leave blank for All refresh events.",
        )
    with detail_col2:
        entry_only = st.checkbox(
            "Entry / junior / graduate only",
            value=False,
            key="job_finder_filter_entry_v123",
        )

    jobs = filter_jobs_by_events(jobs, event_filter)
    filter_trace.append({"Stage": "Last refresh event", "Jobs": len(jobs)})

    employment_count_map = employment_type_counts(jobs)
    employment_options = sorted(
        employment_count_map,
        key=lambda value: (-employment_count_map[value], value.casefold()),
    )
    existing_employment = list(st.session_state.get("job_finder_filter_employment_v123", []))
    valid_employment = [value for value in existing_employment if value in employment_count_map]
    if valid_employment != existing_employment:
        st.session_state["job_finder_filter_employment_v123"] = valid_employment

    selected_employment = st.multiselect(
        "Employment type",
        options=employment_options,
        default=[],
        format_func=lambda value: f"{value} ({employment_count_map.get(value, 0)})",
        key="job_finder_filter_employment_v123",
        help="Leave blank for All employment types.",
    )
    jobs = filter_jobs_by_employment_types(jobs, selected_employment)
    filter_trace.append({"Stage": "Employment type", "Jobs": len(jobs)})

    jobs = filter_jobs_by_entry_level(jobs, entry_only)
    filter_trace.append({"Stage": "Entry / junior / graduate", "Jobs": len(jobs)})

    with st.expander("Hide / exclusion rules", expanded=False):
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
            "These counts are recomputed on every Streamlit rerun. Changing any result filter "
            "should change the applicable stage immediately without pressing Search."
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

    jobs.sort(
        key=lambda job: (
            lexical_relevance(job, active_query),
            _safe_timestamp(job.get("posted_at")),
            _safe_timestamp(job.get("last_seen_at")),
        ),
        reverse=True,
    )

    result_limit = st.slider(
        "Maximum results shown",
        10,
        250,
        75,
        step=5,
        key="job_finder_result_limit_v123",
    )
    total_after_filters = len(jobs)
    jobs = jobs[: int(result_limit)]

    st.write(f"### {total_after_filters} result(s)")
    if not jobs:
        st.info(
            "No jobs match the current live filters. Remove a filter or clear filters; "
            "you do not need to press Search again unless you want a different text query."
        )
        return

    match_context = current_evidence_context()
    evidence_count = int(match_context.get("evidence_item_count", 0) or 0)
    if evidence_count:
        st.caption(
            f"Candidate evidence match uses all {evidence_count} item(s) in Profile & Evidence. "
            "Analyzing a new/stale job may call the configured analysis model for JD extraction; "
            "the taxonomy/evidence score after extraction is deterministic and cached."
        )
    else:
        st.warning(
            "Profile & Evidence is empty. Add truthful evidence before using Analyze Match."
        )

    for job in jobs:
        score = lexical_relevance(job, active_query)
        state_label = _job_event_label(job)
        hidden_reasons = list(job.get("_hide_reasons") or [])
        hidden_prefix = "[HIDDEN] " if hidden_reasons else ""
        source_label = SOURCE_LABELS.get(
            str(job.get("source") or ""),
            str(job.get("source") or ""),
        )
        label = (
            f"{hidden_prefix}[{state_label}] {job.get('title') or 'Untitled'} — "
            f"{job.get('company') or 'Unknown Company'}"
        )

        with st.expander(label):
            if hidden_reasons:
                st.warning("Hidden because: " + " · ".join(hidden_reasons))

            st.markdown(f"**Source:** {source_label}")
            meta = [
                str(job.get("location") or ""),
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
            match_state = inspect_job_match(job, context=match_context)
            analyze_label = (
                "Refresh Match"
                if match_state.get("status") == "stale"
                else "Analyze Match"
            )
            analyze_clicked = st.button(
                analyze_label,
                key=f"job_finder_analyze_match_v200_{job['id']}",
                disabled=(
                    evidence_count <= 0
                    or len(str(job.get("description") or "").strip()) < 100
                ),
                help=(
                    "On a cache miss this runs the existing two-pass JD extractor, then "
                    "the shared deterministic taxonomy/evidence scorer. It does not run "
                    "the old LLM keyword-match step."
                ),
            )
            if analyze_clicked:
                try:
                    with st.status(
                        "Analyzing requirements against Profile & Evidence...",
                        expanded=True,
                    ) as match_status:
                        match_result = analyze_job_match(
                            job,
                            context=match_context,
                        )
                        if match_result.get("cache_hit"):
                            match_status.write("Reused current cached match snapshot.")
                        else:
                            match_status.write(
                                "JD profile extracted; deterministic taxonomy/evidence scoring completed."
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

            if match_state.get("status") == "stale":
                st.warning(
                    "Saved match is stale: "
                    + ", ".join(match_state.get("stale_reasons") or ["cache identity changed"])
                    + ". Refresh Match to recompute it."
                )
            elif match_state.get("status") == "none":
                st.caption(
                    "Not analyzed yet. Search relevance is not candidate fit; Analyze Match "
                    "uses your full Profile & Evidence library."
                )

            snapshot = (
                match_state.get("snapshot")
                if match_state.get("status") == "current"
                else None
            )
            if isinstance(snapshot, dict):
                match_summary = snapshot.get("summary") or {}
                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                metric_col1.metric(
                    "Alignment",
                    f"{int(match_summary.get('deterministic_alignment_score', 0) or 0)}/100",
                )
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

                important_gaps = match_summary.get("important_gaps") or []
                if important_gaps:
                    st.write("**Important evidence gaps**")
                    st.dataframe(
                        [
                            {
                                "Importance": gap.get("importance"),
                                "Requirement": gap.get("text"),
                                "Capability": gap.get("capability_id"),
                            }
                            for gap in important_gaps
                        ],
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.caption("No unmatched required/core/deal-breaker rows in this snapshot.")

                with st.expander("Match diagnostics", expanded=False):
                    st.json(
                        {
                            "snapshot_id": snapshot.get("id"),
                            "job_content_hash": snapshot.get("job_content_hash"),
                            "evidence_fingerprint": snapshot.get("evidence_fingerprint"),
                            "match_version": snapshot.get("match_version"),
                            "scoring_version": snapshot.get("scoring_version"),
                            "taxonomy_version": snapshot.get("taxonomy_version"),
                            "summary": match_summary,
                            "canonical_requirements": (
                                (snapshot.get("stable_analysis") or {}).get(
                                    "canonical_requirements",
                                    [],
                                )
                            ),
                            "validation_warnings": (
                                (snapshot.get("stable_analysis") or {}).get(
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
                st.write(f"**Seniority / experience:** {job.get('seniority')}")

            st.text_area(
                "Normalized job description",
                value=str(job.get("description") or ""),
                height=220,
                disabled=True,
                key=f"job_description_preview_v123_{job['id']}",
            )

            action_col1, action_col2, action_col3, action_col4 = st.columns(
                [1.45, 1.10, 0.75, 0.85]
            )
            with action_col1:
                if st.button(
                    "Use in new Application Session",
                    key=f"job_finder_use_v123_{job['id']}",
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
                        key=f"job_finder_no_url_v123_{job['id']}",
                        disabled=True,
                        width="stretch",
                    )
            with action_col3:
                if st.button(
                    "Hide job",
                    key=f"job_finder_hide_job_v123_{job['id']}",
                    width="stretch",
                    disabled=bool(hidden_reasons),
                    help="Hide only this source/job ID. The stored job is not deleted.",
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
                    key=f"job_finder_hide_company_v123_{job['id']}",
                    width="stretch",
                    disabled=not company_name or bool(hidden_reasons),
                    help="Hide all jobs whose normalized company name exactly matches this company.",
                ):
                    upsert_hide_rule(
                        rule_type="company",
                        value=company_name,
                        label=company_name,
                    )
                    st.rerun()


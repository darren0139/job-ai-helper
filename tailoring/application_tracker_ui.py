from __future__ import annotations

from datetime import date
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from database.application_tracking_manager import (
    STATUS_LABELS,
    STATUS_OPTIONS,
    add_manual_tracked_job,
    list_application_status_history,
    list_application_tracking_rows,
    normalise_status,
    status_label,
    update_application_tracking,
)
from tailoring.application_tracker_export import (
    build_application_tracker_workbook,
)


DISPLAY_STATUS_OPTIONS = [STATUS_LABELS[value] for value in STATUS_OPTIONS]
STATUS_CHART_TYPES = ("Bar", "Donut")
WEEKLY_CHART_TYPES = ("Line", "Bar")
COHORT_CHART_TYPES = ("Stacked Bar", "Grouped Bar")
HISTORY_CHART_TYPES = ("Line", "Stacked Bar")


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _to_iso_date(value: Any) -> str | None:
    resolved = _to_date(value)
    return resolved.isoformat() if resolved else None


def tracker_rows_to_dataframe(
    rows: list[dict[str, Any]],
) -> pd.DataFrame:
    records = []
    for row in rows:
        records.append(
            {
                "tracked_job_id": int(row["tracked_job_id"]),
                "application_id": row.get("application_id"),
                "company": row.get("company") or "",
                "job_title": row.get("job_title") or "",
                "location": row.get("location") or "",
                "overall_score": row.get("overall_score"),
                "applied": bool(row.get("applied")),
                "applied_at": _to_date(row.get("applied_at")),
                "status": status_label(row.get("status")),
                "completed": bool(row.get("completed")),
                "completed_at": _to_date(row.get("completed_at")),
                "notes": row.get("notes") or "",
                "job_url": row.get("job_url") or "",
                "source_type": row.get("source_type") or "",
            }
        )
    return pd.DataFrame(records)


def compute_tracker_metrics(
    rows: list[dict[str, Any]] | pd.DataFrame,
) -> dict[str, int]:
    frame = (
        rows.copy()
        if isinstance(rows, pd.DataFrame)
        else tracker_rows_to_dataframe(rows)
    )
    if frame.empty:
        return {
            "tracked": 0,
            "applied": 0,
            "active": 0,
            "interviews": 0,
            "offers": 0,
            "completed": 0,
        }

    statuses = frame["status"].astype(str)
    applied = frame["applied"].fillna(False).astype(bool)
    completed = frame["completed"].fillna(False).astype(bool)
    active = applied & ~completed & ~statuses.isin(["Rejected", "Withdrawn"])
    return {
        "tracked": int(len(frame)),
        "applied": int(applied.sum()),
        "active": int(active.sum()),
        "interviews": int((statuses == "Interview").sum()),
        "offers": int((statuses == "Offer").sum()),
        "completed": int(completed.sum()),
    }


def _comparable_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    comparable = frame.copy()
    for column in ("applied_at", "completed_at"):
        comparable[column] = comparable[column].map(
            lambda value: _to_iso_date(value) or ""
        )
    comparable["application_id"] = comparable["application_id"].map(
        lambda value: "" if pd.isna(value) else str(int(value))
    )
    comparable["overall_score"] = comparable["overall_score"].map(
        lambda value: "" if pd.isna(value) else str(int(value))
    )
    comparable = comparable.fillna("")
    return comparable.sort_values("tracked_job_id").reset_index(drop=True)


def tracker_has_unsaved_changes(
    original: pd.DataFrame,
    edited: pd.DataFrame,
) -> bool:
    left = _comparable_frame(original)
    right = _comparable_frame(edited)
    if list(left.columns) != list(right.columns):
        return True
    return not left.equals(right)



def normalise_tracker_editor_lifecycle(
    original: pd.DataFrame,
    edited: pd.DataFrame,
) -> pd.DataFrame:
    # Resolve the effective lifecycle state implied by the latest edit.
    normalized = edited.copy()
    if normalized.empty:
        return normalized

    originals: dict[int, dict[str, Any]] = {}
    for row in original.to_dict(orient="records"):
        originals[int(row["tracked_job_id"])] = row

    for index, row in normalized.iterrows():
        tracked_job_id = int(row["tracked_job_id"])
        prior = originals.get(tracked_job_id, {})

        applied = bool(row.get("applied"))
        prior_applied = bool(prior.get("applied"))
        status = status_label(row.get("status"))
        prior_status = status_label(prior.get("status") or "Not Applied")
        applied_at = _to_date(row.get("applied_at"))

        applied_changed = applied != prior_applied
        status_changed = status != prior_status

        if status_changed:
            if status == "Not Applied":
                applied = False
                applied_at = None
            else:
                applied = True
                if applied_at is None:
                    applied_at = date.today()
        elif applied_changed:
            if applied:
                if status == "Not Applied":
                    status = "Applied"
                if applied_at is None:
                    applied_at = date.today()
            else:
                status = "Not Applied"
                applied_at = None
        else:
            if status != "Not Applied":
                applied = True
                if applied_at is None:
                    applied_at = date.today()
            elif applied:
                status = "Applied"
                if applied_at is None:
                    applied_at = date.today()

        normalized.at[index, "applied"] = applied
        normalized.at[index, "applied_at"] = applied_at
        normalized.at[index, "status"] = status

    return normalized

def _persist_editor_frame(frame: pd.DataFrame) -> int:
    updated = 0
    for row in frame.to_dict(orient="records"):
        update_application_tracking(
            tracked_job_id=int(row["tracked_job_id"]),
            applied=bool(row.get("applied")),
            applied_at=_to_iso_date(row.get("applied_at")),
            status=normalise_status(row.get("status")),
            completed=bool(row.get("completed")),
            completed_at=_to_iso_date(row.get("completed_at")),
            notes=str(row.get("notes") or ""),
        )
        updated += 1
    return updated


def _render_tracker_tab(rows: list[dict[str, Any]]) -> pd.DataFrame:
    st.caption(
        "Application Sessions and manually added jobs share one tracker. "
        "Applied and completed dates are editable, so older applications can "
        "be backfilled accurately."
    )

    original = tracker_rows_to_dataframe(rows)
    if original.empty:
        st.info("No tracked jobs yet. Add one in **Add Job / JD**.")
        return original

    visible_columns = [
        "tracked_job_id",
        "application_id",
        "company",
        "job_title",
        "location",
        "overall_score",
        "applied",
        "applied_at",
        "status",
        "completed",
        "completed_at",
        "notes",
        "job_url",
        "source_type",
    ]
    editor_frame = original[visible_columns].copy()

    edited = st.data_editor(
        editor_frame,
        column_config={
            "tracked_job_id": None,
            "application_id": st.column_config.NumberColumn(
                "Application ID",
                format="%d",
            ),
            "company": st.column_config.TextColumn("Company"),
            "job_title": st.column_config.TextColumn("Role"),
            "location": st.column_config.TextColumn("Location"),
            "overall_score": st.column_config.NumberColumn(
                "Match Score",
                format="%d",
            ),
            "applied": st.column_config.CheckboxColumn("Applied"),
            "applied_at": st.column_config.DateColumn(
                "Applied Date",
                format="DD MMM YYYY",
                help=(
                    "If Applied is checked and this is blank, saving defaults "
                    "it to today. You can always choose an earlier date."
                ),
            ),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=DISPLAY_STATUS_OPTIONS,
                required=True,
            ),
            "completed": st.column_config.CheckboxColumn("Complete"),
            "completed_at": st.column_config.DateColumn(
                "Completed Date",
                format="DD MMM YYYY",
            ),
            "notes": st.column_config.TextColumn("Notes"),
            "job_url": st.column_config.LinkColumn("Job URL"),
            "source_type": st.column_config.TextColumn("Source"),
        },
        disabled=[
            "application_id",
            "company",
            "job_title",
            "location",
            "overall_score",
            "job_url",
            "source_type",
        ],
        hide_index=True,
        width="stretch",
        key="application_tracker_editor_v2",
    )

    effective_edited = normalise_tracker_editor_lifecycle(
        editor_frame,
        edited,
    )
    lifecycle_adjusted = tracker_has_unsaved_changes(
        edited,
        effective_edited,
    )
    changed = tracker_has_unsaved_changes(editor_frame, effective_edited)
    if lifecycle_adjusted:
        st.caption(
            "Lifecycle preview normalized automatically: checking Applied promotes "
            "Not Applied to Applied, while advanced statuses remain applied. "
            "Save Changes to persist the normalized row."
        )
    save_col, export_col = st.columns(2)

    with save_col:
        if st.button(
            "Save Changes",
            type="primary",
            width="stretch",
            disabled=not changed,
        ):
            count = _persist_editor_frame(effective_edited)
            st.session_state["application_tracker_flash"] = (
                f"Saved {count} tracked job row(s)."
            )
            st.rerun()

    with export_col:
        persisted_rows = rows
        history = list_application_status_history(
            [int(row["tracked_job_id"]) for row in persisted_rows]
        )
        workbook = build_application_tracker_workbook(
            persisted_rows,
            history,
        )
        st.download_button(
            "Export Excel",
            data=workbook,
            file_name="job_application_tracker.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            width="stretch",
            disabled=changed,
            help=(
                "Save table edits first so SQLite, charts, and Excel export "
                "all use the same persisted data."
            ),
        )

    if changed:
        st.info(
            "Analytics reflects the effective unsaved tracker edits below. "
            "Save Changes before exporting so SQLite and Excel stay in sync."
        )

    return effective_edited


def _render_add_job_tab() -> None:
    st.caption(
        "Add a job directly to the tracker without creating a fake résumé "
        "Application Session. You can analyse or tailor it later."
    )

    with st.form("application_tracker_add_job_form", clear_on_submit=True):
        company = st.text_input("Company")
        role = st.text_input("Role")
        location = st.text_input("Location")
        job_url = st.text_input("Job URL")
        job_description = st.text_area(
            "Job description",
            height=240,
            placeholder="Paste the JD here if you want it stored with the tracked job.",
        )

        left, right = st.columns(2)
        with left:
            applied = st.checkbox("Already applied", value=False)
            applied_date = st.date_input(
                "Applied date",
                value=None,
                help="Leave blank if you have not applied.",
            )
        with right:
            status = st.selectbox(
                "Current status",
                DISPLAY_STATUS_OPTIONS,
                index=0,
            )
            completed = st.checkbox("Complete / closed", value=False)
            completed_date = st.date_input(
                "Completed date",
                value=None,
            )

        notes = st.text_area("Notes", height=100)

        submitted = st.form_submit_button(
            "Add Job",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    try:
        tracked_job_id = add_manual_tracked_job(
            company=company,
            job_title=role,
            location=location,
            job_url=job_url,
            job_description=job_description,
            applied=applied,
            applied_at=applied_date,
            status=normalise_status(status),
            completed=completed,
            completed_at=completed_date,
            notes=notes,
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    st.session_state["application_tracker_flash"] = (
        f"Added tracked job #{tracked_job_id}: {role.strip()} @ {company.strip()}."
    )
    st.rerun()


def _analytics_frame(
    rows: list[dict[str, Any]],
    preview_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    frame = (
        preview_frame.copy()
        if isinstance(preview_frame, pd.DataFrame)
        else tracker_rows_to_dataframe(rows)
    )
    if frame.empty:
        return frame

    companies = sorted(
        value for value in frame["company"].dropna().unique().tolist()
        if str(value).strip()
    )
    statuses = DISPLAY_STATUS_OPTIONS

    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        selected_companies = st.multiselect(
            "Company",
            options=companies,
            default=[],
            placeholder="All companies",
            key="tracker_analytics_company_filter",
        )
    with filter_col2:
        selected_statuses = st.multiselect(
            "Status",
            options=statuses,
            default=[],
            placeholder="All statuses",
            key="tracker_analytics_status_filter",
        )

    if selected_companies:
        frame = frame[frame["company"].isin(selected_companies)]
    if selected_statuses:
        frame = frame[frame["status"].isin(selected_statuses)]

    applied_dates = pd.to_datetime(frame["applied_at"], errors="coerce")
    valid_dates = applied_dates.dropna()
    if not valid_dates.empty:
        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()
        chosen = st.date_input(
            "Applied date range",
            value=(min_date, max_date),
            key="tracker_analytics_date_range",
        )
        if isinstance(chosen, tuple) and len(chosen) == 2:
            start_date, end_date = chosen
            mask = (
                applied_dates.isna()
                | (
                    (applied_dates.dt.date >= start_date)
                    & (applied_dates.dt.date <= end_date)
                )
            )
            frame = frame[mask]

    return frame


def _status_counts(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["Status", "Applications"])
    return (
        frame["status"]
        .value_counts()
        .rename_axis("Status")
        .reset_index(name="Applications")
    )


def _weekly_applied(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["Week", "Applications"])
    working = frame.copy()
    working["applied_date"] = pd.to_datetime(
        working["applied_at"],
        errors="coerce",
    )
    working = working[working["applied_date"].notna()]
    if working.empty:
        return pd.DataFrame(columns=["Week", "Applications"])
    working["Week"] = (
        working["applied_date"]
        .dt.to_period("W-MON")
        .apply(lambda period: period.start_time.date().isoformat())
    )
    return (
        working.groupby("Week", as_index=False)
        .size()
        .rename(columns={"size": "Applications"})
    )


def _weekly_cohort(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["Week", "Status", "Applications"])
    working = frame.copy()
    working["applied_date"] = pd.to_datetime(
        working["applied_at"],
        errors="coerce",
    )
    working = working[working["applied_date"].notna()]
    if working.empty:
        return pd.DataFrame(columns=["Week", "Status", "Applications"])
    working["Week"] = (
        working["applied_date"]
        .dt.to_period("W-MON")
        .apply(lambda period: period.start_time.date().isoformat())
    )
    return (
        working.groupby(["Week", "status"], as_index=False)
        .size()
        .rename(
            columns={
                "status": "Status",
                "size": "Applications",
            }
        )
    )


def _history_weekly(
    tracked_job_ids: list[int],
) -> pd.DataFrame:
    history = list_application_status_history(tracked_job_ids)
    if not history:
        return pd.DataFrame(columns=["Week", "Status", "Transitions"])

    frame = pd.DataFrame(history)
    frame["occurred"] = pd.to_datetime(frame["occurred_at"], errors="coerce")
    frame = frame[frame["occurred"].notna()].copy()
    if frame.empty:
        return pd.DataFrame(columns=["Week", "Status", "Transitions"])

    frame["Week"] = (
        frame["occurred"]
        .dt.to_period("W-MON")
        .apply(lambda period: period.start_time.date().isoformat())
    )
    frame["Status"] = frame["to_status"].map(status_label)
    return (
        frame.groupby(["Week", "Status"], as_index=False)
        .size()
        .rename(columns={"size": "Transitions"})
    )


def _render_analytics_tab(
    rows: list[dict[str, Any]],
    preview_frame: pd.DataFrame | None = None,
) -> None:
    st.caption(
        "Charts use the effective Tracker preview, including unsaved lifecycle edits. "
        "Status-history charts still use persisted transition events."
    )

    frame = _analytics_frame(rows, preview_frame=preview_frame)
    if frame.empty:
        st.info("No tracked jobs match the current filters.")
        return

    metrics = compute_tracker_metrics(frame)
    columns = st.columns(6)
    labels = [
        ("Tracked", "tracked"),
        ("Applied", "applied"),
        ("Active", "active"),
        ("Interviews", "interviews"),
        ("Offers", "offers"),
        ("Completed", "completed"),
    ]
    for column, (label, key) in zip(columns, labels):
        column.metric(label, metrics[key])

    status_counts = _status_counts(frame)
    st.subheader("Status distribution")
    status_chart_type = st.radio(
        "Status chart type",
        STATUS_CHART_TYPES,
        horizontal=True,
        key="tracker_status_chart_type",
        label_visibility="collapsed",
    )
    if status_chart_type == "Donut":
        status_chart = (
            alt.Chart(status_counts)
            .mark_arc(innerRadius=55)
            .encode(
                theta=alt.Theta("Applications:Q"),
                color=alt.Color("Status:N", legend=alt.Legend(title=None)),
                tooltip=["Status:N", "Applications:Q"],
            )
            .properties(height=320)
        )
    else:
        status_chart = (
            alt.Chart(status_counts)
            .mark_bar()
            .encode(
                x=alt.X("Applications:Q", title="Applications"),
                y=alt.Y(
                    "Status:N",
                    title=None,
                    sort="-x",
                    axis=alt.Axis(labelLimit=220),
                ),
                tooltip=["Status:N", "Applications:Q"],
            )
            .properties(height=max(220, len(status_counts) * 38))
        )
    st.altair_chart(status_chart, width="stretch")

    weekly = _weekly_applied(frame)
    st.subheader("Applications by week")
    weekly_chart_type = st.radio(
        "Weekly applications chart type",
        WEEKLY_CHART_TYPES,
        horizontal=True,
        key="tracker_weekly_chart_type",
        label_visibility="collapsed",
    )
    if weekly.empty:
        st.info("Add or edit Applied Dates to build the weekly trend.")
    else:
        weekly_base = alt.Chart(weekly).encode(
            x=alt.X(
                "Week:T",
                title="Week",
                axis=alt.Axis(format="%d %b"),
            ),
            y=alt.Y(
                "Applications:Q",
                title="Applications",
                axis=alt.Axis(tickMinStep=1),
            ),
            tooltip=[
                alt.Tooltip("Week:T", title="Week", format="%d %b %Y"),
                "Applications:Q",
            ],
        )
        weekly_chart = (
            weekly_base.mark_bar()
            if weekly_chart_type == "Bar"
            else weekly_base.mark_line(point=True)
        ).properties(height=300)
        st.altair_chart(weekly_chart, width="stretch")

    cohort = _weekly_cohort(frame)
    st.subheader("Weekly application cohorts")
    cohort_chart_type = st.radio(
        "Cohort chart type",
        COHORT_CHART_TYPES,
        horizontal=True,
        key="tracker_cohort_chart_type",
        label_visibility="collapsed",
    )
    st.caption(
        "Groups jobs by application week and current status. Choose stacked "
        "for composition or grouped for side-by-side comparison."
    )
    if cohort.empty:
        st.info("Applied dates are needed for the weekly cohort chart.")
    else:
        cohort_base = alt.Chart(cohort).mark_bar()
        if cohort_chart_type == "Grouped Bar":
            cohort_chart = cohort_base.encode(
                x=alt.X(
                    "Week:T",
                    title="Application week",
                    axis=alt.Axis(format="%d %b"),
                ),
                xOffset=alt.XOffset("Status:N"),
                y=alt.Y(
                    "Applications:Q",
                    title="Applications",
                    axis=alt.Axis(tickMinStep=1),
                ),
                color=alt.Color("Status:N", legend=alt.Legend(title=None)),
                tooltip=[
                    alt.Tooltip("Week:T", format="%d %b %Y"),
                    "Status:N",
                    "Applications:Q",
                ],
            )
        else:
            cohort_chart = cohort_base.encode(
                x=alt.X(
                    "Week:T",
                    title="Application week",
                    axis=alt.Axis(format="%d %b"),
                ),
                y=alt.Y(
                    "Applications:Q",
                    title="Applications",
                    stack="zero",
                    axis=alt.Axis(tickMinStep=1),
                ),
                color=alt.Color("Status:N", legend=alt.Legend(title=None)),
                tooltip=[
                    alt.Tooltip("Week:T", format="%d %b %Y"),
                    "Status:N",
                    "Applications:Q",
                ],
            )
        st.altair_chart(cohort_chart.properties(height=320), width="stretch")

    tracked_job_ids = [
        int(value)
        for value in frame["tracked_job_id"].tolist()
    ]
    history = _history_weekly(tracked_job_ids)
    st.subheader("Pipeline stage changes over time")
    history_chart_type = st.radio(
        "Pipeline history chart type",
        HISTORY_CHART_TYPES,
        horizontal=True,
        key="tracker_history_chart_type",
        label_visibility="collapsed",
    )
    st.caption(
        "This event view records persisted status changes. Historical transitions "
        "that happened before V2 cannot be reconstructed exactly."
    )
    if history.empty:
        st.info("No status transitions have been recorded yet.")
    else:
        history_base = alt.Chart(history).encode(
            x=alt.X(
                "Week:T",
                title="Week",
                axis=alt.Axis(format="%d %b"),
            ),
            y=alt.Y(
                "Transitions:Q",
                title="Status changes",
                axis=alt.Axis(tickMinStep=1),
            ),
            color=alt.Color("Status:N", legend=alt.Legend(title=None)),
            tooltip=[
                alt.Tooltip("Week:T", format="%d %b %Y"),
                "Status:N",
                "Transitions:Q",
            ],
        )
        history_chart = (
            history_base.mark_bar()
            if history_chart_type == "Stacked Bar"
            else history_base.mark_line(point=True)
        ).properties(height=320)
        st.altair_chart(history_chart, width="stretch")


def render_application_tracker() -> None:
    st.header("Application Tracker")
    st.caption(
        "Track real-world job applications independently from résumé preparation. "
        "SQLite remains the source of truth for the table, analytics, and Excel export."
    )

    flash = st.session_state.pop("application_tracker_flash", "")
    if flash:
        st.success(flash)

    rows = list_application_tracking_rows()
    tracker_tab, add_tab, analytics_tab = st.tabs(
        ["Tracker", "Add Job / JD", "Analytics"]
    )

    with tracker_tab:
        analytics_preview = _render_tracker_tab(rows)

    with add_tab:
        _render_add_job_tab()

    with analytics_tab:
        _render_analytics_tab(
            rows,
            preview_frame=analytics_preview,
        )

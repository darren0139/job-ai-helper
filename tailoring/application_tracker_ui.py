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


def _render_tracker_tab(rows: list[dict[str, Any]]) -> None:
    st.caption(
        "Application Sessions and manually added jobs share one tracker. "
        "Applied and completed dates are editable, so older applications can "
        "be backfilled accurately."
    )

    original = tracker_rows_to_dataframe(rows)
    if original.empty:
        st.info("No tracked jobs yet. Add one in **Add Job / JD**.")
        return

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

    changed = tracker_has_unsaved_changes(editor_frame, edited)
    save_col, export_col = st.columns(2)

    with save_col:
        if st.button(
            "Save Changes",
            type="primary",
            width="stretch",
            disabled=not changed,
        ):
            count = _persist_editor_frame(edited)
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
            "Preview analytics can reflect unsaved table edits, but save them "
            "before exporting so the database and workbook stay in sync."
        )


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


def _analytics_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = tracker_rows_to_dataframe(rows)
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


def _render_analytics_tab(rows: list[dict[str, Any]]) -> None:
    st.caption(
        "These charts are derived from persisted tracker data. Status-history "
        "analytics become more useful as future status transitions are recorded."
    )

    frame = _analytics_frame(rows)
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

    left, right = st.columns(2)
    with left:
        st.subheader("Status distribution")
        bar = (
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
        st.altair_chart(bar, width="stretch")

    with right:
        st.subheader("Status share")
        donut = (
            alt.Chart(status_counts)
            .mark_arc(innerRadius=55)
            .encode(
                theta=alt.Theta("Applications:Q"),
                color=alt.Color("Status:N", legend=alt.Legend(title=None)),
                tooltip=["Status:N", "Applications:Q"],
            )
            .properties(height=300)
        )
        st.altair_chart(donut, width="stretch")

    weekly = _weekly_applied(frame)
    st.subheader("Applications by week")
    if weekly.empty:
        st.info("Add or edit Applied Dates to build the weekly trend.")
    else:
        line = (
            alt.Chart(weekly)
            .mark_line(point=True)
            .encode(
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
            .properties(height=300)
        )
        st.altair_chart(line, width="stretch")

    cohort = _weekly_cohort(frame)
    st.subheader("Weekly application cohorts")
    st.caption(
        "Each bar groups jobs by the week you applied and stacks them by their "
        "current status."
    )
    if cohort.empty:
        st.info("Applied dates are needed for the weekly cohort chart.")
    else:
        stacked = (
            alt.Chart(cohort)
            .mark_bar()
            .encode(
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
            .properties(height=320)
        )
        st.altair_chart(stacked, width="stretch")

    tracked_job_ids = [
        int(value)
        for value in frame["tracked_job_id"].tolist()
    ]
    history = _history_weekly(tracked_job_ids)
    st.subheader("Pipeline stage changes over time")
    st.caption(
        "This event view records when statuses changed. Historical transitions "
        "that happened before V2 cannot be reconstructed exactly."
    )
    if history.empty:
        st.info("No status transitions have been recorded yet.")
    else:
        history_chart = (
            alt.Chart(history)
            .mark_line(point=True)
            .encode(
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
            .properties(height=320)
        )
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
        _render_tracker_tab(rows)

    with add_tab:
        _render_add_job_tab()

    with analytics_tab:
        _render_analytics_tab(rows)

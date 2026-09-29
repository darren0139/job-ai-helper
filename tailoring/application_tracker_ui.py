"""Streamlit Application Tracker table, dashboard, and Excel export."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from database.application_tracking_manager import (
    list_application_tracking_rows,
    update_application_tracking,
)
from tailoring.application_tracker_export import (
    STATUS_LABELS,
    build_application_tracker_workbook,
)


LABEL_TO_STATUS = {label: status for status, label in STATUS_LABELS.items()}
STATUS_OPTIONS = list(STATUS_LABELS.values())
EDITABLE_FIELDS = ("applied", "status", "completed", "notes")


def build_tracker_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Create the editor/dashboard dataframe from canonical tracker rows."""
    return pd.DataFrame(
        [
            {
                "application_id": int(row.get("application_id") or 0),
                "company": str(row.get("company") or ""),
                "job_title": str(row.get("job_title") or ""),
                "location": str(row.get("location") or ""),
                "overall_score": row.get("overall_score"),
                "applied": bool(row.get("applied")),
                "applied_at": str(row.get("applied_at") or ""),
                "status": STATUS_LABELS.get(
                    str(row.get("status") or "not_applied"),
                    "Not Applied",
                ),
                "completed": bool(row.get("completed")),
                "completed_at": str(row.get("completed_at") or ""),
                "notes": str(row.get("notes") or ""),
            }
            for row in rows
        ],
        columns=[
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
        ],
    )


def normalise_tracker_preview(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the same lightweight status/applied rules used during persistence."""
    effective = frame.copy()
    if effective.empty:
        return effective
    statuses = effective["status"].fillna("Not Applied").astype(str)
    applied = effective["applied"].fillna(False).astype(bool)
    implied_applied = statuses != "Not Applied"
    effective["applied"] = applied | implied_applied
    effective.loc[applied & ~implied_applied, "status"] = "Applied"
    return effective


def build_tracker_metrics(frame: pd.DataFrame) -> dict[str, int]:
    frame = normalise_tracker_preview(frame)
    if frame.empty:
        return {
            "tracked": 0,
            "applied": 0,
            "active": 0,
            "interviews": 0,
            "completed": 0,
        }
    applied = frame["applied"].fillna(False).astype(bool)
    completed = frame["completed"].fillna(False).astype(bool)
    statuses = frame["status"].fillna("Not Applied").astype(str)
    return {
        "tracked": int(len(frame)),
        "applied": int(applied.sum()),
        "active": int((applied & ~completed).sum()),
        "interviews": int((statuses == "Interview").sum()),
        "completed": int(completed.sum()),
    }


def _canonical_editor_values(row: dict[str, Any]) -> dict[str, Any]:
    display_status = str(row.get("status") or "Not Applied")
    status = LABEL_TO_STATUS.get(display_status, "not_applied")
    applied = bool(row.get("applied"))
    if status != "not_applied":
        applied = True
    elif applied:
        status = "applied"
    return {
        "applied": applied,
        "status": status,
        "completed": bool(row.get("completed")),
        "notes": str(row.get("notes") or "").strip(),
    }


def _find_changed_rows(
    edited: pd.DataFrame,
    persisted_rows: list[dict[str, Any]],
) -> list[tuple[int, dict[str, Any]]]:
    originals = {
        int(row["application_id"]): {
            "applied": bool(row.get("applied")),
            "status": str(row.get("status") or "not_applied"),
            "completed": bool(row.get("completed")),
            "notes": str(row.get("notes") or "").strip(),
        }
        for row in persisted_rows
    }
    changed: list[tuple[int, dict[str, Any]]] = []
    for editor_row in edited.to_dict("records"):
        application_id = int(editor_row.get("application_id") or 0)
        values = _canonical_editor_values(editor_row)
        if originals.get(application_id) != values:
            changed.append((application_id, values))
    return changed


def _render_visualisations(frame: pd.DataFrame) -> None:
    frame = normalise_tracker_preview(frame)
    st.subheader("Application progress")
    metrics = build_tracker_metrics(frame)
    metric_cols = st.columns(5)
    metric_cols[0].metric("Tracked Jobs", metrics["tracked"])
    metric_cols[1].metric("Applied", metrics["applied"])
    metric_cols[2].metric("Active", metrics["active"])
    metric_cols[3].metric("Interviews", metrics["interviews"])
    metric_cols[4].metric("Completed", metrics["completed"])

    applied = frame[frame["applied"].fillna(False).astype(bool)].copy()
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.write("#### Status distribution")
        if applied.empty:
            st.info("Mark an application as applied to populate this chart.")
        else:
            status_counts = (
                applied["status"]
                .fillna("Applied")
                .value_counts()
                .rename_axis("Status")
                .reset_index(name="Applications")
                .set_index("Status")
            )
            st.bar_chart(status_counts)

    with chart_col2:
        st.write("#### Applications by week")
        if applied.empty:
            st.info("Applied dates will appear here after you save applications.")
        else:
            applied["applied_date"] = pd.to_datetime(
                applied["applied_at"],
                errors="coerce",
            )
            applied = applied.dropna(subset=["applied_date"])
            if applied.empty:
                st.info("Save applied checkboxes to create application dates.")
            else:
                applied["week_start"] = (
                    applied["applied_date"]
                    .dt.to_period("W-SUN")
                    .dt.start_time
                    .dt.normalize()
                )
                weekly = (
                    applied.groupby("week_start")
                    .size()
                    .rename("Applications")
                    .to_frame()
                )
                st.line_chart(weekly)


def render_application_tracker() -> None:
    """Render the editable tracker, live preview charts, and Excel export."""
    st.header("Application Tracker")
    st.caption(
        "Track what happened after résumé preparation. Application Sessions stay "
        "separate from real-world submission status."
    )

    flash = st.session_state.pop("application_tracker_flash", "")
    if flash:
        st.success(flash)

    rows = list_application_tracking_rows()
    if not rows:
        st.info(
            "No analyzed Application Sessions are available yet. Create or analyze "
            "a job first, then return here to track whether you applied."
        )
        return

    persisted_frame = build_tracker_dataframe(rows)
    edited_frame = st.data_editor(
        persisted_frame,
        key="application_tracker_editor",
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        column_order=[
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
        ],
        column_config={
            "application_id": None,
            "company": st.column_config.TextColumn("Company"),
            "job_title": st.column_config.TextColumn("Role"),
            "location": st.column_config.TextColumn("Location"),
            "overall_score": st.column_config.NumberColumn("Match Score", format="%d"),
            "applied": st.column_config.CheckboxColumn("Applied"),
            "applied_at": st.column_config.TextColumn("Applied Date"),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=STATUS_OPTIONS,
                required=True,
            ),
            "completed": st.column_config.CheckboxColumn("Complete"),
            "completed_at": st.column_config.TextColumn("Completed Date"),
            "notes": st.column_config.TextColumn("Notes", width="large"),
        },
        disabled=[
            "company",
            "job_title",
            "location",
            "overall_score",
            "applied_at",
            "completed_at",
        ],
    )

    changed = _find_changed_rows(edited_frame, rows)
    save_col, export_col = st.columns([1, 1])
    with save_col:
        if st.button(
            "Save Changes",
            type="primary",
            width="stretch",
            disabled=not changed,
        ):
            for application_id, values in changed:
                update_application_tracking(
                    application_id=application_id,
                    applied=values["applied"],
                    status=values["status"],
                    completed=values["completed"],
                    notes=values["notes"],
                )
            st.session_state.pop("application_tracker_editor", None)
            st.session_state["application_tracker_flash"] = (
                f"Saved {len(changed)} application tracking update(s)."
            )
            st.rerun()

    with export_col:
        workbook = build_application_tracker_workbook(rows)
        st.download_button(
            "Export Excel",
            data=workbook,
            file_name="job_application_tracker.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
            disabled=bool(changed),
            help=(
                "Save table changes first so the exported workbook exactly matches "
                "the persisted tracker."
            ),
        )

    if changed:
        st.info(
            "Preview charts below include your unsaved table edits. Save Changes "
            "before exporting so SQLite, charts, and Excel remain in sync."
        )

    _render_visualisations(edited_frame)

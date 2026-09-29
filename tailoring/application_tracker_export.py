from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from database.application_tracking_manager import status_label


APPLICATION_COLUMNS = [
    "Tracked Job ID",
    "Application ID",
    "Company",
    "Role",
    "Location",
    "Match Score",
    "Applied",
    "Applied Date",
    "Status",
    "Complete",
    "Completed Date",
    "Notes",
    "Job URL",
    "Source",
]


def _applications_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    records = []
    for row in rows:
        records.append(
            {
                "Tracked Job ID": row.get("tracked_job_id"),
                "Application ID": row.get("application_id"),
                "Company": row.get("company") or "",
                "Role": row.get("job_title") or "",
                "Location": row.get("location") or "",
                "Match Score": row.get("overall_score"),
                "Applied": bool(row.get("applied")),
                "Applied Date": row.get("applied_at") or "",
                "Status": status_label(row.get("status")),
                "Complete": bool(row.get("completed")),
                "Completed Date": row.get("completed_at") or "",
                "Notes": row.get("notes") or "",
                "Job URL": row.get("job_url") or "",
                "Source": row.get("source_type") or "",
            }
        )
    return pd.DataFrame(records, columns=APPLICATION_COLUMNS)


def _summary_frame(applications: pd.DataFrame) -> pd.DataFrame:
    total = len(applications)
    applied = int(applications["Applied"].sum()) if total else 0
    completed = int(applications["Complete"].sum()) if total else 0
    status_counts = (
        applications["Status"].value_counts().to_dict()
        if total
        else {}
    )
    active = 0
    if total:
        active = int(
            (
                applications["Applied"]
                & ~applications["Complete"]
                & ~applications["Status"].isin(["Rejected", "Withdrawn"])
            ).sum()
        )

    metrics = [
        ("Tracked Jobs", total),
        ("Applied", applied),
        ("Active", active),
        ("Interviews", int(status_counts.get("Interview", 0))),
        ("Offers", int(status_counts.get("Offer", 0))),
        ("Rejected", int(status_counts.get("Rejected", 0))),
        ("Withdrawn", int(status_counts.get("Withdrawn", 0))),
        ("Completed", completed),
        ("Application Rate", applied / total if total else 0.0),
        ("Interview Rate", status_counts.get("Interview", 0) / applied if applied else 0.0),
        ("Offer Rate", status_counts.get("Offer", 0) / applied if applied else 0.0),
    ]
    return pd.DataFrame(metrics, columns=["Metric", "Value"])


def _weekly_frames(
    applications: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if applications.empty:
        empty_trend = pd.DataFrame(columns=["Week", "Applications"])
        empty_cohort = pd.DataFrame(columns=["Week", "Status", "Applications"])
        return empty_trend, empty_cohort

    working = applications.copy()
    working["Applied Date Parsed"] = pd.to_datetime(
        working["Applied Date"],
        errors="coerce",
    )
    working = working[working["Applied Date Parsed"].notna()].copy()
    if working.empty:
        empty_trend = pd.DataFrame(columns=["Week", "Applications"])
        empty_cohort = pd.DataFrame(columns=["Week", "Status", "Applications"])
        return empty_trend, empty_cohort

    working["Week"] = (
        working["Applied Date Parsed"]
        .dt.to_period("W-MON")
        .apply(lambda period: period.start_time.date().isoformat())
    )
    trend = (
        working.groupby("Week", as_index=False)
        .size()
        .rename(columns={"size": "Applications"})
    )
    cohort = (
        working.groupby(["Week", "Status"], as_index=False)
        .size()
        .rename(columns={"size": "Applications"})
    )
    return trend, cohort


def _history_frame(status_history: list[dict[str, Any]]) -> pd.DataFrame:
    columns = [
        "Tracked Job ID",
        "Application ID",
        "Company",
        "Role",
        "From Status",
        "To Status",
        "Occurred At",
    ]
    records = [
        {
            "Tracked Job ID": row.get("tracked_job_id"),
            "Application ID": row.get("application_id"),
            "Company": row.get("company") or "",
            "Role": row.get("job_title") or "",
            "From Status": status_label(row.get("from_status") or "not_applied"),
            "To Status": status_label(row.get("to_status") or "not_applied"),
            "Occurred At": row.get("occurred_at") or "",
        }
        for row in status_history
    ]
    return pd.DataFrame(records, columns=columns)


def _format_workbook(writer: pd.ExcelWriter) -> None:
    workbook = writer.book
    for worksheet in workbook.worksheets:
        worksheet.freeze_panes = "A2"
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
        for column_cells in worksheet.columns:
            max_length = 0
            column_index = column_cells[0].column
            for cell in column_cells:
                value = "" if cell.value is None else str(cell.value)
                max_length = max(max_length, len(value))
            worksheet.column_dimensions[
                get_column_letter(column_index)
            ].width = min(max(max_length + 2, 10), 50)


def build_application_tracker_workbook(
    rows: list[dict[str, Any]],
    status_history: list[dict[str, Any]] | None = None,
) -> bytes:
    applications = _applications_frame(rows)
    summary = _summary_frame(applications)
    weekly_trend, weekly_cohort = _weekly_frames(applications)
    history = _history_frame(status_history or [])

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        applications.to_excel(writer, sheet_name="Applications", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)
        weekly_trend.to_excel(writer, sheet_name="Weekly Trend", index=False)
        weekly_cohort.to_excel(writer, sheet_name="Weekly Cohort", index=False)
        history.to_excel(writer, sheet_name="Status History", index=False)
        _format_workbook(writer)
    return buffer.getvalue()

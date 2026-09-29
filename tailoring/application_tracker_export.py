"""Excel export for the persisted Application Tracker dataset."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
from openpyxl.styles import Font


STATUS_LABELS = {
    "not_applied": "Not Applied",
    "applied": "Applied",
    "screening": "Screening",
    "interview": "Interview",
    "offer": "Offer",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}


def _applications_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    records = []
    for row in rows:
        records.append(
            {
                "Application ID": int(row.get("application_id") or 0),
                "Company": str(row.get("company") or ""),
                "Role": str(row.get("job_title") or ""),
                "Location": str(row.get("location") or ""),
                "Match Score": row.get("overall_score"),
                "Applied": bool(row.get("applied")),
                "Applied Date": str(row.get("applied_at") or ""),
                "Status": STATUS_LABELS.get(
                    str(row.get("status") or "not_applied"),
                    str(row.get("status") or "Not Applied"),
                ),
                "Complete": bool(row.get("completed")),
                "Completed Date": str(row.get("completed_at") or ""),
                "Notes": str(row.get("notes") or ""),
            }
        )
    return pd.DataFrame(
        records,
        columns=[
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
        ],
    )


def _summary_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    total = len(rows)
    applied = sum(bool(row.get("applied")) for row in rows)
    active = sum(
        bool(row.get("applied")) and not bool(row.get("completed"))
        for row in rows
    )
    completed = sum(bool(row.get("completed")) for row in rows)
    interviews = sum(str(row.get("status") or "") == "interview" for row in rows)
    offers = sum(str(row.get("status") or "") == "offer" for row in rows)
    rejected = sum(str(row.get("status") or "") == "rejected" for row in rows)

    def rate(numerator: int, denominator: int) -> float:
        return round((numerator / denominator), 4) if denominator else 0.0

    return pd.DataFrame(
        [
            ("Tracked Jobs", total),
            ("Applied", applied),
            ("Active", active),
            ("Completed", completed),
            ("Interview", interviews),
            ("Offer", offers),
            ("Rejected", rejected),
            ("Application Rate", rate(applied, total)),
            ("Interview Rate", rate(interviews, applied)),
            ("Offer Rate", rate(offers, applied)),
        ],
        columns=["Metric", "Value"],
    )


def _weekly_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    applied_dates = pd.to_datetime(
        [str(row.get("applied_at") or "") for row in rows if row.get("applied")],
        errors="coerce",
    )
    applied_dates = applied_dates[~applied_dates.isna()]
    if len(applied_dates) == 0:
        return pd.DataFrame(columns=["Week Starting", "Applications"])

    week_starts = applied_dates.to_period("W-SUN").start_time.normalize()
    counts = pd.Series(week_starts).value_counts().sort_index()
    return pd.DataFrame(
        {
            "Week Starting": counts.index,
            "Applications": counts.values,
        }
    )


def _format_sheet(worksheet) -> None:
    if worksheet.max_row >= 1:
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

    for column_cells in worksheet.columns:
        values = [str(cell.value or "") for cell in column_cells]
        width = min(max([len(value) for value in values] + [8]) + 2, 45)
        worksheet.column_dimensions[column_cells[0].column_letter].width = width


def build_application_tracker_workbook(rows: list[dict[str, Any]]) -> bytes:
    """Return an in-memory .xlsx snapshot from the canonical tracker rows."""
    applications = _applications_dataframe(rows)
    summary = _summary_dataframe(rows)
    weekly = _weekly_dataframe(rows)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        applications.to_excel(writer, sheet_name="Applications", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)
        weekly.to_excel(writer, sheet_name="Weekly Trend", index=False)

        for worksheet in writer.book.worksheets:
            _format_sheet(worksheet)

        summary_sheet = writer.book["Summary"]
        for row_index in (9, 10, 11):
            summary_sheet.cell(row=row_index, column=2).number_format = "0.0%"

        weekly_sheet = writer.book["Weekly Trend"]
        for cell in weekly_sheet["A"][1:]:
            cell.number_format = "yyyy-mm-dd"

    return buffer.getvalue()

from __future__ import annotations

import re


_MONTH_TO_NUMBER = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def period_sort_value(period: str) -> tuple[int, int]:
    """
    Convert a project period into a sortable latest date.

    Examples:
    'Mar 2025 - Apr 2025' -> (2025, 4)
    'Sep 2023 - Apr 2024' -> (2024, 4)
    'Jan 2018 - Feb 2018' -> (2018, 2)
    Unknown dates go last.
    """
    text = str(period or "").lower().strip()

    if not text:
        return (0, 0)

    if "present" in text or "current" in text:
        return (9999, 12)

    matches = re.findall(
        r"(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)?\s*(20\d{2}|19\d{2})",
        text,
    )

    if not matches:
        return (0, 0)

    month_text, year_text = matches[-1]
    year = int(year_text)
    month = _MONTH_TO_NUMBER.get(month_text, 12) if month_text else 12

    return (year, month)
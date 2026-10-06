"""Pure pagination helpers for Job Finder result rendering."""

from __future__ import annotations

from typing import Any, Iterable


def paginate_jobs(
    jobs: Iterable[dict[str, Any]],
    *,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    rows = [dict(job) for job in jobs]
    safe_page_size = max(1, int(page_size or 1))
    total = len(rows)
    total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
    safe_page = min(max(1, int(page or 1)), total_pages)

    start_index = (safe_page - 1) * safe_page_size
    end_index = min(start_index + safe_page_size, total)

    return {
        "jobs": rows[start_index:end_index],
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": total_pages,
        "start_index": start_index,
        "end_index": end_index,
    }

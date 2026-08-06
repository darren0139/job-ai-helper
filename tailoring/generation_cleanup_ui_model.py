"""Pure helpers for the Phase 7G saved-version cleanup interface."""

from __future__ import annotations

from typing import Any


CLEANUP_FILTER_OPTIONS = (
    "Drafts",
    "Archived",
    "All deletable",
)


def cleanup_status(state: dict[str, Any]) -> str:
    """Return a normalised generation status."""
    return str(state.get("status") or "draft").strip().lower()


def filter_cleanup_versions(
    versions: list[dict[str, Any]],
    status_filter: str,
) -> list[dict[str, Any]]:
    """Return deletable versions matching the requested UI filter."""
    if status_filter not in CLEANUP_FILTER_OPTIONS:
        raise ValueError(f"Unsupported cleanup filter: {status_filter!r}")

    allowed = {
        "Drafts": {"draft"},
        "Archived": {"archived"},
        "All deletable": {"draft", "archived"},
    }[status_filter]

    return [
        state
        for state in versions
        if cleanup_status(state) in allowed
    ]


def cleanup_option_label(state: dict[str, Any]) -> str:
    """Build a compact multiselect label for a deletable version."""
    status = cleanup_status(state).title()
    generation_id = str(state.get("generation_id") or "")[:8]
    kind = str(state.get("generation_kind") or "manual")
    updated_at = str(state.get("updated_at") or "")
    return f"{status} · {kind} · {generation_id} · {updated_at}"


def build_cleanup_rows(
    versions: list[dict[str, Any]],
    *,
    loaded_generation_id: str = "",
) -> list[dict[str, Any]]:
    """Build display rows for the cleanup preview table."""
    loaded_id = str(loaded_generation_id or "")
    rows: list[dict[str, Any]] = []

    for state in versions:
        generation_id = str(state.get("generation_id") or "")
        fit_result = state.get("fit_result")
        page_count_value = (
            fit_result.get("page_count", "—")
            if isinstance(fit_result, dict)
            else "—"
        )
        page_count = (
            str(page_count_value)
            if page_count_value not in (None, "")
            else "—"
        )
        rows.append(
            {
                "Status": cleanup_status(state).title(),
                "ID": generation_id[:8],
                "Type": str(state.get("generation_kind") or "manual"),
                "Updated": str(state.get("updated_at") or ""),
                "Pages": page_count,
                "Loaded": "Yes" if generation_id == loaded_id else "",
            }
        )

    return rows


def selected_cleanup_versions(
    versions: list[dict[str, Any]],
    selected_generation_ids: list[str] | tuple[str, ...],
) -> list[dict[str, Any]]:
    """Resolve selected IDs while preserving the visible version order."""
    selected = {
        str(value or "").strip()
        for value in selected_generation_ids
        if str(value or "").strip()
    }
    return [
        state
        for state in versions
        if str(state.get("generation_id") or "") in selected
        and cleanup_status(state) in {"draft", "archived"}
    ]

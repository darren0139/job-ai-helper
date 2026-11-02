"""Shared, read-only Streamlit table presentation for Application Sessions.

Static modes bypass the browser's interactive dataframe canvas. All modes
receive the same saved rows; no score, database, or receipt is changed.
"""
from __future__ import annotations

import hashlib
import inspect
from contextlib import nullcontext
from pathlib import Path
from typing import Any

MODE_KEY = "job_ai_application_table_mode_v2"
SCROLL = "Scrollable (recommended)"
PAGED = "Paginated (12 rows)"
INTERACTIVE = "Interactive (canvas)"
OPTIONS = (SCROLL, PAGED, INTERACTIVE)


def render_session_table_controls(st: Any, *, application_id: int | None = None) -> str:
    """One session-wide setting; configured once above Step 1."""
    st.markdown("##### Requirements table display")
    st.caption("Applies to Initial Analysis, score breakdowns, Step 2 and Phase 8. "
               "Scrollable and Paginated avoid the interactive canvas renderer.")
    mode = st.radio("Table display mode", OPTIONS, key=MODE_KEY, horizontal=True)
    return mode if mode in OPTIONS else SCROLL


def _mode(st: Any) -> str:
    # The Application Session renders its global control before its tables.
    # Elsewhere (e.g. Job Finder and isolated historical AppTest tests), the
    # control is absent: preserve the old interactive-table presentation.
    # session_tables_v2_0_1_missing_control_fallback
    state = getattr(st, "session_state", None)
    missing = object()
    try:
        mode = state.get(MODE_KEY, missing)
    except (AttributeError, TypeError, ValueError):
        return INTERACTIVE
    if mode is missing or not isinstance(mode, str):
        return INTERACTIVE
    return mode if mode in OPTIONS else SCROLL


# Cross-page setting is independent of the Application Session control.
# One selection is shared by Job Finder and Capability Discovery.
CROSS_PAGE_MODE_KEY = "job_ai_cross_page_table_mode_v3"


def render_cross_page_table_controls(st: Any) -> str:
    """One global display choice for read-only cross-page grids."""
    st.caption("Table display: static modes avoid the browser dataframe canvas.")
    result = st.radio("Read-only table display", OPTIONS,
                      key=CROSS_PAGE_MODE_KEY, horizontal=True)
    return result if isinstance(result, str) and result in OPTIONS else SCROLL


def _cross_page_mode(st: Any) -> str:
    state = getattr(st, "session_state", None)
    missing = object()
    try:
        result = state.get(CROSS_PAGE_MODE_KEY, missing)
    except (AttributeError, TypeError, ValueError):
        return INTERACTIVE  # Legacy minimal test doubles only.
    if result is missing:
        return SCROLL  # Real Streamlit without a previous selection.
    if not isinstance(result, str):
        return INTERACTIVE  # unittest.mock.Mock fallback contract.
    return result if result in OPTIONS else SCROLL


def render_cross_page_table(
    st: Any, rows: Any, *, key: str, height: int = 420,
    hide_index: bool = True, width: str = "stretch",
) -> None:
    """Read-only table with the shared cross-page mode; never edits rows."""
    render_session_table(st, rows, key="cross_v3_" + key,
                         height=height, hide_index=hide_index,
                         width=width, mode=_cross_page_mode(st))


def _slice_rows(rows: Any, start: int, stop: int) -> Any:
    if hasattr(rows, "iloc"):
        return rows.iloc[start:stop]
    return rows[start:stop]


def render_session_table(
    st: Any, rows: Any, *, key: str, page_size: int = 40, height: int = 420,
    hide_index: bool = True, width: str = "stretch", mode: str | None = None,
) -> None:
    """Display rows without mutating them; use static table by default.

    Bounded static DOM: scroll within one page of up to 40 rows and paginate
    larger datasets, preventing large rows from accumulating in the browser.
    """
    try:
        count = len(rows)
    except (TypeError, ValueError):
        st.caption("No table rows to display.")
        return
    if count == 0:
        st.caption("No table rows to display.")
        return
    # Existing test doubles and older Streamlit clients may expose only
    # dataframe(). Preserve their original full-table contract; production
    # Streamlit has both table() and container().
    if not (callable(getattr(st, "table", None)) and
            callable(getattr(st, "container", None))):
        st.dataframe(rows, hide_index=hide_index, width=width)
        return
    mode = _mode(st) if mode is None else (mode if mode in OPTIONS else SCROLL)
    if mode == INTERACTIVE:
        st.dataframe(rows, hide_index=hide_index, width=width, height=height)
        return
    effective_size = 12 if mode == PAGED else max(1, min(50, int(page_size)))
    page_count = (count + effective_size - 1) // effective_size
    page = 1
    if page_count > 1:
        page = int(st.number_input(
            "Table page", min_value=1, max_value=page_count, value=1, step=1,
            key="session_v2_page_" + key,
        ))
        page = max(1, min(page, page_count))
    shown = _slice_rows(rows, (page-1)*effective_size, page*effective_size)
    # Real Streamlit's container scopes table-height scrolling. A fake/mock
    # st used by focused tests can still exercise the static table path.
    box = st.container(height=height, border=True)
    if hasattr(box, "__enter__") and hasattr(box, "__exit__"):
        with box:
            st.table(shown)
    else:
        st.table(shown)
    if page_count > 1:
        st.caption(f"Rows {(page-1)*effective_size+1}–{min(count,page*effective_size)} "
                   f"of {count}; page {page}/{page_count}.")


def render_session_dataframe(
    st: Any, rows: Any, *, hide_index: bool = True, width: str = "stretch",
    height: int = 420,
) -> None:
    """Drop-in replacement for existing st.dataframe calls in receipt views."""
    caller = inspect.currentframe().f_back
    try:
        # A comparison presenter can run twice at the same source line for
        # Initial-vs-Final and Selected-Base-vs-Final. Include its own label so
        # their paging widgets never collide in one Streamlit rerun.
        label = str(caller.f_locals.get("label", ""))[:120]
        location = (Path(caller.f_code.co_filename).name, caller.f_lineno, label)
    finally:
        del caller
    # Add a cheap content discriminator for repeat invocations of one callsite
    # (for example Initial vs Final and Selected Base vs Final comparisons).
    try:
        discriminator = str(rows[0].get("Requirement ID", "")) + ":" + str(len(rows)) if rows else "empty"
    except (AttributeError, IndexError, TypeError, ValueError):
        discriminator = str(type(rows).__name__)
    digest = hashlib.sha256(repr((location, discriminator)).encode("utf-8")).hexdigest()[:16]
    render_session_table(st, rows, key=digest, hide_index=hide_index,
                         width=width, height=height)

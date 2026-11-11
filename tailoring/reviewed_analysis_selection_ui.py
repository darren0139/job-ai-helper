"""Reviewed-scope choice in the existing Application Sessions analysis section."""
import sqlite3

from analysis_stability.requirement_presentation import score_text, score_value
from database import reviewed_analysis_selection as selection


def _change(st, application_id, token, restore):
    action = selection.restore_ordinary_analysis if restore else selection.save_and_select_reviewed_analysis
    try:
        action(application_id, expected_token=token)
    except (ValueError, KeyError, TypeError) as error:
        st.session_state[f"review419_error_{application_id}"] = str(error)
    except sqlite3.Error:
        st.session_state[f"review419_error_{application_id}"] = "Selection was not saved. Reload before retrying."


def render_reviewed_analysis_selection(st, application_id):
    if not selection.enabled():
        return
    try:
        state = selection.get_reviewed_selection(application_id)
    except (ValueError, KeyError, TypeError):
        return
    if state is None:
        return
    with st.expander("Reviewed exclusions", expanded=True):
        error = st.session_state.pop(f"review419_error_{application_id}", "")
        if error:
            st.warning(error)
        st.caption("This saved selection applies only to this application. The original analysis and tailoring baseline remain available.")
        selected = state["selected"]
        if selected:
            stable = selected["report"]["stable_analysis"]
            st.metric("Selected reviewed Job Match", score_text(score_value(stable)))
            scope = stable["effective_requirement_scope"]
            st.caption(f"{len(scope['excluded_requirement_ids'])} reviewed exclusions · {scope['version']}")
        elif state.get("stale"):
            st.warning("The reviewed selection is out of date. The ordinary analysis is current for this view.")
        if not selected:
            st.button("Save and select reviewed analysis", key=f"review419_save_{application_id}",
                      on_click=_change, args=(st, application_id, state["token"], False))
        if selected or state.get("stale"):
            st.button("Return to ordinary analysis", key=f"review419_restore_{application_id}",
                      on_click=_change, args=(st, application_id, state["token"], True))

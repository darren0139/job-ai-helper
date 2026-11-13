"""JD interpretation in the Application Sessions workflow."""
import hashlib
import os
import sqlite3

from analysis_stability.jd_knowledge_preview import build_jd_knowledge, load_pinned_jd
from database import db_manager


UNDERSTANDING = {
    "COMPLETE_GENERIC_SOURCE_PARENT": "Complete parent verified",
    "PARTIAL_OR_SCOPED__FULL_PARENT_UNVERIFIED": "Partial or scoped",
    "COMPLETE_MEANING_NOT_ESTABLISHED": "Unresolved",
}


def _compound_lines(node, depth=0):
    heading = " ".join(str(value) for value in (node.get("operator"), node.get("action"),
                                                 node.get("text")) if value)
    if not node.get("children"):
        heading += " — " + ("Verified component" if node.get("complete") else "Unverified component")
    yield "  " * depth + heading
    for child in node.get("children", []):
        yield from _compound_lines(child, depth + 1)


def render_application_jd_knowledge(st, application_id):
    if os.environ.get("JOB_AI_HELPER_JD_KNOWLEDGE") == "0":
        return
    with st.expander("Job requirements", expanded=True):
        st.caption("Interpretation of the pinned original JD. Saved Job Match and applicant evidence stay separate.")
        try:
            raw = load_pinned_jd(application_id, db_manager.DB_PATH)
            source_hash = hashlib.sha256(raw.encode()).hexdigest()
            key = f"jd_knowledge_{application_id}_{source_hash}"
            cached = st.session_state.get("jd_knowledge_active_view")
            if not cached or cached[0] != key:
                cached = (key, build_jd_knowledge(raw))
                st.session_state["jd_knowledge_active_view"] = cached
            result = cached[1]
        except (OSError, ValueError, sqlite3.Error):
            st.caption("Job requirements unavailable. Open an application with a pinned original JD.")
            return

        if result["reviews"]:
            st.caption("Reviewed knowledge for this exact original posting.")
        else:
            st.caption("Ordinary resolver results. This posting has no historical review binding.")
        items = result["requirements"]
        st.dataframe([{
            "Requirement": item["text"], "Importance": item["importance"],
            "Classification": (item["basis"] or item["type"] or "Unclassified").replace("_", " ").title(),
            "Knowledge": item["status"].replace("_", " ").title(),
            "Whole requirement": UNDERSTANDING[item["understanding"]],
            "Capabilities": ", ".join(item["capabilities"]),
            "Technologies": ", ".join(item["technologies"]),
        } for item in items], hide_index=True, width="stretch")
        if result["reviews"]:
            with st.expander("Source reviews and exclusions"):
                st.dataframe([{
                    "Review": review["number"], "Source wording": review["text"],
                    "Recorded classification": review["classification"],
                    "Verified scope": review["scope"].replace("_", " "),
                    "Binding": review["binding"], "Exclusions": ", ".join(review["exclusions"]),
                } for review in result["reviews"]], hide_index=True, width="stretch")

        with st.expander("Requirement details and local review"):
            if not items:
                st.caption("The resolver found no requirements in this source.")
                return
            by_id = {item["id"]: item for item in items}
            selected = st.selectbox("Requirement", list(by_id), key=key + "_requirement",
                                    format_func=lambda value: by_id[value]["text"])
            item = by_id[selected]
            st.text(item["parent"])
            if item["compound"]:
                st.text("\n".join(_compound_lines(item["compound"])))
            if item["understanding"] != "COMPLETE_GENERIC_SOURCE_PARENT":
                notes = st.session_state.setdefault("jd_knowledge_local_notes", {})
                note_key = (key, selected)
                with st.form(key + "_" + selected):
                    note = st.text_area("Local review note", value=notes.get(note_key, ""), max_chars=400)
                    if st.form_submit_button("Save note for this session"):
                        notes[note_key] = note
                if notes.get(note_key):
                    st.text(notes[note_key])
                st.caption("Notes stay in this browser session and apply only to this application and JD version.")

from __future__ import annotations

import streamlit as st

from tailoring.generation_cleanup_ui_model import build_cleanup_rows


VERSIONS = [
    {
        "generation_id": "draft-with-pages",
        "status": "draft",
        "generation_kind": "projects_skills",
        "updated_at": "2026-08-05T00:00:00",
        "fit_result": {"page_count": 1},
    },
    {
        "generation_id": "draft-without-pages",
        "status": "draft",
        "generation_kind": "projects_skills",
        "updated_at": "2026-08-05T00:01:00",
        "fit_result": {},
    },
]

# These are the three cleanup tables rendered by generation_controls_ui:
# filtered rows, deletion preview, and the clear-all-drafts preview.
for heading in ("Filtered versions", "Deletion preview", "All drafts"):
    st.write(heading)
    st.dataframe(
        build_cleanup_rows(VERSIONS),
        hide_index=True,
        width="stretch",
    )

"""Streamlit management page for persistent Blueprint tags."""

from __future__ import annotations

from typing import Any

import streamlit as st

from database.global_blueprint_tag_manager import (
    create_blueprint_tag,
    init_global_blueprint_tag_registry,
    list_blueprint_lane_tag_usage,
    list_blueprint_tag_events,
    list_blueprint_tags,
    update_blueprint_tag,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def render_blueprint_tag_library() -> None:
    init_global_blueprint_tag_registry()

    st.header("Blueprint Tag Library")
    st.caption(
        "Manage the stable tag vocabulary used by Blueprint variant lanes. "
        "System tags drive deterministic auto-detection. Custom tags can be "
        "assigned manually to lanes and used in lane matching."
    )

    flash = st.session_state.pop("blueprint_tag_library_flash", "")
    if flash:
        st.success(flash)

    tags = list_blueprint_tags(include_inactive=True)
    st.subheader("Tag library")
    st.dataframe(
        [
            {
                "Tag": row["label"],
                "ID": row["tag_id"],
                "Category": row["category"],
                "Status": "active" if row["is_active"] else "inactive",
                "Type": "system" if row["is_system"] else "custom",
                "Automatic detection": (
                    "Yes" if row["is_system"] and row["tag_id"] != "generalist"
                    else "No"
                ),
                "Lane usage": row["lane_usage_count"],
                "Aliases": ", ".join(row["aliases"]),
            }
            for row in tags
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "System tag IDs and labels are stable. Custom tags are user-managed. "
        "A custom tag must be removed from all lanes before it can be deactivated."
    )

    with st.expander("Create custom tag", expanded=False):
        label = st.text_input(
            "Tag label",
            key="blueprint_tag_create_label",
        )
        category = st.text_input(
            "Category",
            value="Custom",
            key="blueprint_tag_create_category",
        )
        description = st.text_area(
            "Description",
            key="blueprint_tag_create_description",
        )
        aliases = st.text_area(
            "Aliases",
            key="blueprint_tag_create_aliases",
            help="Optional. Enter aliases separated by commas or new lines.",
        )
        actor = st.text_input(
            "Actor label",
            value="Local user",
            key="blueprint_tag_create_actor",
        )
        if st.button(
            "Create tag",
            key="blueprint_tag_create",
            disabled=not _clean(label),
        ):
            try:
                created = create_blueprint_tag(
                    label=label,
                    category=category,
                    description=description,
                    aliases=aliases,
                    actor_label=actor,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["blueprint_tag_library_flash"] = (
                    f"Created custom Blueprint tag {created['label']}."
                )
                st.rerun()

    custom_tags = [row for row in tags if not row["is_system"]]
    st.subheader("Edit custom tag")
    if not custom_tags:
        st.info("No custom Blueprint tags exist yet.")
    else:
        by_id = {row["tag_id"]: row for row in custom_tags}
        selected_id = st.selectbox(
            "Custom tag",
            options=list(by_id),
            format_func=lambda value: (
                f"{by_id[value]['label']} · "
                f"{'active' if by_id[value]['is_active'] else 'inactive'}"
            ),
            key="blueprint_tag_edit_id",
        )
        selected = by_id[selected_id]
        edited_label = st.text_input(
            "Label",
            value=selected["label"],
            key=f"blueprint_tag_edit_label_{selected_id}",
        )
        edited_category = st.text_input(
            "Category",
            value=selected["category"],
            key=f"blueprint_tag_edit_category_{selected_id}",
        )
        edited_description = st.text_area(
            "Description",
            value=selected["description"],
            key=f"blueprint_tag_edit_description_{selected_id}",
        )
        edited_aliases = st.text_area(
            "Aliases",
            value=", ".join(selected["aliases"]),
            key=f"blueprint_tag_edit_aliases_{selected_id}",
        )
        edited_active = st.checkbox(
            "Active",
            value=selected["is_active"],
            key=f"blueprint_tag_edit_active_{selected_id}",
        )
        edit_actor = st.text_input(
            "Editor label",
            value="Local user",
            key=f"blueprint_tag_edit_actor_{selected_id}",
        )
        if st.button(
            "Save tag",
            key=f"blueprint_tag_save_{selected_id}",
        ):
            try:
                updated = update_blueprint_tag(
                    tag_id=selected_id,
                    label=edited_label,
                    category=edited_category,
                    description=edited_description,
                    aliases=edited_aliases,
                    is_active=edited_active,
                    actor_label=edit_actor,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["blueprint_tag_library_flash"] = (
                    f"Updated Blueprint tag {updated['label']}."
                )
                st.rerun()

    st.divider()
    st.subheader("Blueprint lane usage")
    usage = list_blueprint_lane_tag_usage()
    if usage:
        st.dataframe(
            [
                {
                    "Role family": row["role_family_label"],
                    "Variant lane": row["variant_label"],
                    "Version": row["version_number"],
                    "Availability": row["availability_status"],
                    "Tags": ", ".join(row["tags"]) or "Unclassified",
                }
                for row in usage
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No Blueprint lanes exist yet.")

    with st.expander("Recent tag metadata events", expanded=False):
        events = list_blueprint_tag_events(limit=50)
        if events:
            st.json(events)
        else:
            st.caption("No tag metadata events have been recorded yet.")

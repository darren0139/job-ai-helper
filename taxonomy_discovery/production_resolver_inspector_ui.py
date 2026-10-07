"""Streamlit UI for the read-only production resolver inspector."""

from __future__ import annotations

from typing import Any, Callable

from taxonomy_discovery.production_resolver_inspector import (
    WEB_SERVICES_REQUIREMENT,
    current_production_versions,
    inspect_requirement_text,
    inspect_saved_job_match,
    run_production_canaries,
)


def _show_requirement_result(st: Any, result: dict[str, Any]) -> None:
    source = result.get("resolution_source")
    if source == "canonical_taxonomy":
        st.success("✅ Resolved by current production taxonomy")
    elif source == "technology_registry":
        st.success("✅ Resolved by current production technology registry")
    else:
        st.info("⚪ Unresolved by current production knowledge")
    if result.get("excluded_product_spans"):
        st.warning("🛡 Product-context guard blocked a false-positive phrase match")

    st.json(
        {
            key: result.get(key)
            for key in (
                "requirement_text",
                "normalized_requirement_text",
                "resolution_source",
                "capability_id",
                "capability_label",
                "technology_id",
                "canonical_technology_name",
                "matched_phrase",
                "matched_alias",
                "matched_taxonomy_rule_type",
                "contextual_phrase_rule",
                "product_context_guard",
                "guard_contract_version",
                "excluded_product_spans",
                "blocked_contextual_phrase",
                "blocked_product_context_guard",
                "blocked_guard_contract_version",
                "reason",
                "taxonomy_version",
                "registry_version",
                "match_label_applicability",
            )
        }
    )
    with st.expander("Show resolver diagnostics"):
        st.json(result.get("resolver_diagnostics") or {})


def render_production_resolver_inspector(
    *,
    version_loader: Callable[[], dict[str, str]] = current_production_versions,
    requirement_inspector: Callable[[str], dict[str, Any]] = inspect_requirement_text,
    snapshot_inspector: Callable[[int], dict[str, Any]] = inspect_saved_job_match,
    canary_runner: Callable[[], dict[str, Any]] = run_production_canaries,
) -> None:
    """Render explicit, deterministic inspection controls with no auto-runs."""
    import streamlit as st

    st.subheader("🧪 Production Resolver Inspector")
    st.caption(
        "Read-only diagnostics for current production taxonomy and technology "
        "registry. No model, Tavily, network, or persistence writes."
    )
    versions = version_loader()
    st.markdown("**Current production knowledge**")
    st.write(
        {
            "Taxonomy": versions["taxonomy_version"],
            "Registry": versions["technology_registry_version"],
            "Scorer": versions["scoring_version"],
        }
    )

    requirement_tab, snapshot_tab, canary_tab = st.tabs(
        ["Requirement text", "Saved Job Match", "Production canaries"]
    )

    with requirement_tab:
        requirement_text = st.text_area(
            "Requirement text",
            value=WEB_SERVICES_REQUIREMENT,
            key="tqd3_production_resolver_requirement",
        )
        if st.button(
            "Inspect current production resolution",
            key="tqd3_production_resolver_inspect",
        ):
            try:
                st.session_state["tqd3_production_resolver_result"] = (
                    requirement_inspector(requirement_text)
                )
            except Exception as exc:
                st.session_state.pop("tqd3_production_resolver_result", None)
                st.error(f"Requirement inspection failed closed: {exc}")
        result = st.session_state.get("tqd3_production_resolver_result")
        if result:
            _show_requirement_result(st, result)

    with snapshot_tab:
        job_id = st.number_input(
            "Discovered job ID",
            min_value=1,
            value=566,
            step=1,
            key="tqd3_production_resolver_job_id",
        )
        if st.button(
            "Inspect saved Job Match",
            key="tqd3_production_resolver_snapshot",
        ):
            try:
                st.session_state["tqd3_production_resolver_snapshot_result"] = (
                    snapshot_inspector(int(job_id))
                )
            except Exception as exc:
                st.session_state.pop(
                    "tqd3_production_resolver_snapshot_result", None
                )
                st.error(f"Saved Job Match inspection failed closed: {exc}")
        saved = st.session_state.get("tqd3_production_resolver_snapshot_result")
        if saved:
            if saved.get("status") != "found":
                st.warning(saved.get("message") or "Saved snapshot unavailable.")
            else:
                metadata = saved["snapshot_metadata"]
                if metadata.get("currentness_status") == "historical_or_stale":
                    st.warning("⚠ Snapshot is historical or stale")
                else:
                    st.success("✅ Latest saved snapshot uses current knowledge versions")
                st.markdown("**Job metadata**")
                st.json(saved["job_metadata"])
                st.markdown("**Snapshot metadata**")
                st.json(metadata)
                st.markdown("**Persisted requirements**")
                st.dataframe(
                    saved["requirement_rows"],
                    hide_index=True,
                    width="stretch",
                )
                if saved.get("persisted_execution_metadata"):
                    st.markdown("**Persisted provider / execution metadata**")
                    st.json(saved["persisted_execution_metadata"])
                with st.expander("Show persisted requirement records"):
                    st.json(saved["persisted_requirements"])

    with canary_tab:
        if st.button(
            "Run production resolver canaries",
            key="tqd3_production_resolver_canaries",
        ):
            try:
                st.session_state["tqd3_production_resolver_canary_result"] = (
                    canary_runner()
                )
            except Exception as exc:
                st.session_state.pop(
                    "tqd3_production_resolver_canary_result", None
                )
                st.error(f"Production canaries failed closed: {exc}")
        canaries = st.session_state.get("tqd3_production_resolver_canary_result")
        if canaries:
            if canaries.get("all_passed"):
                st.success("✅ All production resolver canaries passed")
            else:
                st.error("FAIL — one or more production resolver canaries failed")
            st.dataframe(canaries.get("rows") or [], hide_index=True, width="stretch")
            with st.expander("Show canary resolver diagnostics"):
                st.json(canaries.get("details") or {})

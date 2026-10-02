"""Expose frozen corpus diagnostics inside Capability Discovery."""
import json
from taxonomy_discovery.taxonomy_gaps import aggregate_corpus_gaps
from taxonomy_discovery.corpus_coverage import corpus_coverage, coverage_csv, deterministic_backfill


def render_corpus_coverage():
    import streamlit as st
    with st.expander("Corpus Coverage"):
        try:
            report = corpus_coverage()
        except (ValueError, OSError) as exc:
            st.info(f"Corpus coverage unavailable: {exc}")
            return
        except Exception as exc:
            st.error(f"Corpus coverage failed closed: {exc}")
            return
        columns = st.columns(5)
        for column, label, key in zip(columns,
                ("Discovered jobs","Replayable corpus","Zero-cost backfillable","Model-required","Blocked"),
                ("discovered_jobs","replayable_jobs_before","zero_cost_backfillable","model_required","blocked")):
            column.metric(label,report[key])
        st.caption("Coverage includes all persisted discovered jobs, including expired or UI-filtered results. Existing snapshots and exact cached JD profiles are assessed without research or model calls.")
        st.download_button("Download coverage report",data=json.dumps(report,indent=2)+"\n",file_name="tqd3_corpus_coverage.json",mime="application/json")
        st.download_button("Download coverage CSV",data=coverage_csv(report),file_name="tqd3_corpus_coverage.csv",mime="text/csv")
        if st.button("Dry-run deterministic backfill",key="tqd3_backfill_dry_run"):
            try:
                st.json(deterministic_backfill())
            except Exception as exc:
                st.error(f"Backfill preview failed closed: {exc}")
        st.caption("Backfill uses only stored compatible JD profiles and existing candidate evidence. It saves current Job Match snapshots and leaves taxonomy, registry and candidate evidence unchanged.")
        if st.button("Execute deterministic snapshot backfill",key="tqd3_backfill_execute",disabled=not report["zero_cost_backfillable"]):
            try:
                with st.spinner("Saving deterministic snapshots from existing local inputs..."):
                    result = deterministic_backfill(execute=True)
                st.json(result)
                st.success(f"Created {result['created']} snapshot(s); reused {result['reused']}.")
            except Exception as exc:
                st.error(f"Backfill stopped: {exc}. Earlier completed snapshots remain saved.")
        render_model_expansion()


def render_model_expansion():
    import streamlit as st
    from taxonomy_discovery.corpus_expansion import model_plan, execution_preview, model_run
    st.subheader("Controlled corpus expansion")
    size = st.selectbox("Bounded plan size", [25, 50], key="tqd3_model_plan_size")
    if st.button("Generate software-only model plan", key="tqd3_model_plan_generate"):
        try:
            st.session_state["tqd3_model_plan"] = model_plan(software_only=True, limit=size)
        except Exception as exc:
            st.error(f"Planning failed closed: {exc}")
    plan = st.session_state.get("tqd3_model_plan")
    if not plan:
        return
    st.json(plan["summary"])
    st.dataframe(plan["jobs"], hide_index=True, width="stretch")
    st.download_button("Download model plan", data=json.dumps(plan, indent=2)+"\n",
                       file_name="tqd3_model_plan.json", mime="application/json")
    batch = st.selectbox("Execution batch limit", [25, 50], key="tqd3_model_execution_size")
    try:
        preview = execution_preview(plan, limit=batch)
    except Exception as exc:
        st.error(f"Plan is unavailable or stale: {exc}")
        return
    st.json({k:v for k,v in preview.items() if k != "jobs"})
    st.warning(f"Explicit execution may attempt at most {preview['maximum_jd_analysis_tasks']} JD-analysis tasks. Each native task uses extraction and review; HTTP retry counts are provider-dependent.")
    confirmed = st.checkbox("I reviewed this plan and authorize this bounded JD analysis batch", key="tqd3_model_confirm")
    if st.button("Run bounded JD analysis batch", key="tqd3_model_execute", disabled=not confirmed or not preview["jobs_remaining"]) and confirmed:
        try:
            def save_receipt(value):
                st.session_state["tqd3_model_receipt"] = value
            model_run(plan, limit=batch, execute=True, receipt_callback=save_receipt)
        except Exception as exc:
            st.error(f"Batch stopped: {exc}. Completed extractions and snapshots remain saved.")
    receipt = st.session_state.get("tqd3_model_receipt")
    if receipt:
        st.json(receipt)
        st.download_button("Download batch receipt", data=json.dumps(receipt, indent=2)+"\n",
                           file_name="tqd3_model_run.json", mime="application/json")


def render_corpus_research_inputs():
    render_corpus_coverage()
    from taxonomy_discovery.taxonomy_evolution_ui import render_taxonomy_evolution
    render_taxonomy_evolution()
    import streamlit as st
    with st.expander("Job Match corpus · governed taxonomy-gap research inputs"):
        st.caption("Upload a frozen corpus export to inspect unresolved clusters. These observations require human review and do not create proposals or execute research.")
        uploaded = st.file_uploader("Frozen Job Match corpus JSON", type=["json"], key="tqd3_gap_corpus")
        if uploaded is None:
            return
        try:
            report = aggregate_corpus_gaps(json.loads(uploaded.getvalue()))
        except (ValueError, KeyError, TypeError) as exc:
            st.error(f"Corpus diagnostics unavailable: {exc}")
            return
        st.dataframe([{"Cluster":r["normalized_cluster"],"Requirements":r["occurrence_count"],"Jobs":r["job_count"],
                       "Initial Phase-G research route":r["recommended_research_route"],"Technology terms":", ".join(r["technology_terms"])}
                      for r in report["observations"]],hide_index=True,width="stretch")
        st.download_button("Download governed gap research inputs", data=json.dumps(report,indent=2,ensure_ascii=False)+"\n",
                           file_name="tqd3_taxonomy_gap_inputs.json",mime="application/json")
        with st.expander("Advanced / gap provenance"):
            st.json(report)

"""Expose frozen corpus diagnostics inside Capability Discovery."""
import json
from taxonomy_discovery.taxonomy_gaps import aggregate_corpus_gaps


def render_corpus_research_inputs():
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
                       "Research route":r["recommended_research_route"],"Technology terms":", ".join(r["technology_terms"])}
                      for r in report["observations"]],hide_index=True,width="stretch")
        st.download_button("Download governed gap research inputs", data=json.dumps(report,indent=2,ensure_ascii=False)+"\n",
                           file_name="tqd3_taxonomy_gap_inputs.json",mime="application/json")
        with st.expander("Advanced / gap provenance"):
            st.json(report)

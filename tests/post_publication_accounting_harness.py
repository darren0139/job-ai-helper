import streamlit as st
from taxonomy_discovery.coverage_presentation import render_jd_taxonomy_status

render_jd_taxonomy_status(st,raw_jd_text=st.session_state['raw_jd'],
                         stable_analysis=st.session_state['stable'],job_id=146)

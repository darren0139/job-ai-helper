"""Static offline AppTest entry point; avoids temporary script writes."""
import streamlit as st
from tailoring.unresolved_requirement_review_ui import render_unresolved_requirement_review

render_unresolved_requirement_review(st,st.session_state['view'])

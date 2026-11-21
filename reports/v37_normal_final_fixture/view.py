from pathlib import Path
import json,runpy
import streamlit as st
root=Path('C:\\Users\\Admin\\Documents\\GitHub\\Job-AI-Helper')
fixture=json.loads((Path.cwd()/'fixture.json').read_bytes())
st.session_state['phase9f_auto_bestof_run_mode_2']={'generation_id':fixture['generation_id'],'mode':'v35-relevance','manual_existing_fit_trial':True}
st.info('Disposable synthetic fixture. Current normal app.py; source-only Best-of inspection, no comparison result supplied.')
runpy.run_path(str(root/'app.py'),run_name='__main__')

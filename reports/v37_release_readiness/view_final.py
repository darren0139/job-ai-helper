import json,hashlib,runpy
from pathlib import Path
import streamlit as st
root=Path(__file__).resolve().parents[2]
saved=json.loads((root/'reports/v37_real_bullet_quality/native_trial.json').read_text(encoding='utf-8'))
source=json.loads((root/'reports/v37_normal_integration/completion_review/real-source-ui.json').read_text(encoding='utf-8'))
result=saved['result'];generation=result['generation_id']
mode='v35-relevance|library_tie=False'
context=hashlib.sha256((generation+'|'+result['a_docx_sha256']+'|'+source['jd']+'|'+mode).encode()).hexdigest()[:16]
st.session_state['phase9f_auto_bestof_run_mode_156']={'generation_id':generation,'mode':'v35-relevance','manual_existing_fit_trial':True}
st.session_state['phase9f_auto_bestof_receipt_156_'+context]=result
st.caption('Disposable App156 snapshot and saved offline 31/31 trial receipt. No new optimization, native measurement or approval.')

if st.query_params.get('public')!='1' and not st.session_state.get('release_fixture_loaded'):
 from database.db_manager import get_application_by_id
 from database.tailoring_version_manager import get_restorable_application_tailoring
 app=get_application_by_id(156)
 restored=get_restorable_application_tailoring(156)
 if not restored or restored['generation_id']!=generation:raise ValueError('Disposable existing generation mismatch')
 st.session_state['latest_report']=app['report']
 st.session_state['current_application_id']=156
 st.session_state['resume_filename']=app['resume_filename']
 for name,field in [('project_candidate_pool','candidate_pool'),('debug_project_tailor_inputs','project_inputs'),('tailored_projects_fit','fit_estimate'),('tailored_projects_result','projects'),('tailored_skills_result','skills'),('tailored_resume_fit_result','fit_result')]:
  st.session_state[name+'_156']=restored[field]
 st.session_state['tailored_generation_id_156']=generation
 st.session_state['tailored_resume_copy_path_156']=restored['docx_path']
 st.session_state['restored_tailoring_settings_156']=restored['generation_settings']
 st.session_state['phase9f_open_bestof_156_'+generation]=True
 st.session_state['release_fixture_loaded']=True

st.session_state.setdefault('navigation_page','Application Sessions')

import tailoring.bullet_choice_lab as lab
import tailoring.bullet_choice_lab_ui as lab_ui
if st.query_params.get('public')=='1':
 st.session_state['navigation_page']='Bullet-Choice Benchmark Lab'
 lab.DATA=root/'reports/v37_release_readiness/public_view'
 lab_ui.DATA=lab.DATA
else:
 lab_ui.DATA=root/'reports/v37_release_readiness/lab_view'
runpy.run_path(str(root/'app.py'),run_name='__main__')

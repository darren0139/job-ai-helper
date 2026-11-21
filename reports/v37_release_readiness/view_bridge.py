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

from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading
@st.cache_resource
def review_bridge():
 from tailoring.ui_review_capture_ui import _sessions
 registry=_sessions()
 class Handler(BaseHTTPRequestHandler):
  def do_POST(self):
   command=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
   session=registry['release-capture-controller']
   def navigate():
    p=session.page;p.bring_to_front()
    if not getattr(session,'_events_installed',False):
     session._review_events=[];session._events_installed=True
     p.on('pageerror',lambda e:session._review_events.append({'kind':'pageerror','message':str(e)}))
     p.on('console',lambda e:session._review_events.append({'kind':'console','message':e.text}) if e.type=='error' else None)

    if command['action']=='load':
     p.get_by_role('heading',name='Available Source Wordings — Estimated JD Relevance',exact=True).wait_for(timeout=60000)
    if command['action']=='load':
     box=p.get_by_test_id('stSelectbox').filter(has=p.get_by_text('Comparison project',exact=True)).last;box.evaluate("e=>e.scrollIntoView({block:'center'})");box.locator('[data-baseweb=select]').click(force=True);p.keyboard.type('Job AI Helper');p.get_by_role('option').filter(has_text='Job AI Helper').first.click(force=True);p.wait_for_timeout(2000)
     source=p.get_by_test_id('stSelectbox').filter(has=p.get_by_text('Source wording to explain',exact=True)).last
     if 'Added automated unit tests' not in source.inner_text():
      source.evaluate("e=>e.scrollIntoView({block:'center'})");source.locator('[data-baseweb=select]').click(force=True);source.get_by_role('combobox').fill('automated unit tests');p.get_by_role('option').filter(has_text='Added automated unit tests').first.click(force=True)
     assert 'Added automated unit tests' in source.inner_text();p.wait_for_timeout(2000)
    if command['action']=='project':
     box=p.get_by_test_id('stSelectbox').filter(has=p.get_by_text('Comparison project',exact=True)).last;box.evaluate("e=>e.scrollIntoView({block:'center'})");box.locator('[data-baseweb=select]').click(force=True);p.keyboard.type(command['value']);p.get_by_role('option').filter(has_text=command['value']).first.click(force=True);p.wait_for_timeout(1500)
    if command['action']=='identical':
     box=p.get_by_test_id('stSelectbox').filter(has=p.get_by_text('Related Evidence Library wording',exact=True)).last;box.evaluate("e=>e.scrollIntoView({block:'center'})");box.evaluate("e=>e.scrollIntoView({block:'center'})");box.locator('[data-baseweb=select]').click(force=True);p.keyboard.press('End');p.keyboard.press('Enter');p.wait_for_timeout(1500)
    if command['action']=='expand':
     p.get_by_text('Advanced Diagnostics — JD ranking and detailed evidence',exact=True).click(force=True);p.wait_for_timeout(1000)
    if command['action']=='narrow':
     p.set_viewport_size({'width':760,'height':1100});button=p.locator('[data-testid=stSidebarCollapseButton] button').first
     if button.is_visible():button.click(force=True)
     p.get_by_text('Estimated JD Relevance — individual wording',exact=True).evaluate("e=>{e.scrollIntoView({block:'start'});document.querySelector('[data-testid=stMain]').scrollTop-=80}")
     check=p.evaluate("()=>{const m=document.querySelector('[data-testid=stMain]');return {client:m.clientWidth,scroll:m.scrollWidth,body:document.body.innerText.slice(-5000)}}")
     check['events']=getattr(session,'_review_events',[]);check['exceptions']=p.get_by_test_id('stException').all_text_contents();(root/'reports/v37_ui_review_capture/narrow.json').write_text(json.dumps(check),encoding='utf-8')
    if command['action']=='benchmark':p.get_by_text('Bullet-Choice Benchmark Lab',exact=True).first.click(force=True);p.wait_for_timeout(1500)
   try:
    session.call(navigate)
    data=json.dumps({'ok':True,'exceptions':session.call(lambda:session.page.get_by_test_id('stException').all_text_contents())}).encode()
   except Exception as e:
    data=json.dumps({'error':type(e).__name__+': '+str(e)}).encode()
   self.send_response(200);self.end_headers();self.wfile.write(data)
  def log_message(self,*_):pass
 server=ThreadingHTTPServer(('127.0.0.1',8718),Handler)
 threading.Thread(target=server.serve_forever,daemon=True).start()
 return server
if st.query_params.get('review_controller')=='1':
 st.session_state['ui_review_capture_id']='release-capture-controller'
 review_bridge()

if not st.session_state.get('release_fixture_loaded'):
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
import tailoring.bullet_choice_lab_ui as lab_ui
lab_ui.DATA=root/'reports/v37_release_readiness/lab_view'
runpy.run_path(str(root/'app.py'),run_name='__main__')

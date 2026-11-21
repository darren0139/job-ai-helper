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
if st.query_params.get('review_controller')=='1':
 st.session_state['ui_review_capture_id']='fixture-capture-controller'
 from tailoring.ui_review_capture_ui import _sessions
 command_file=root/'reports/v37_ui_review_capture/command_acceptance.json'
 if command_file.exists():
  command=json.loads(command_file.read_text(encoding='utf-8'))
  session=_sessions().get('fixture-capture-controller')
  if session and session.active and command.get('id')!=st.session_state.get('last_review_command'):
   st.session_state['last_review_command']=command['id']
   def navigate():
    p=session.page;p.bring_to_front()
    if not getattr(session,'_events_installed',False):
     session._review_events=[];session._events_installed=True
     p.on('pageerror',lambda e:session._review_events.append({'kind':'pageerror','message':str(e)}))
     p.on('console',lambda e:session._review_events.append({'kind':'console','message':e.text}) if e.type=='error' else None)

    if command['action']=='load':
     p.get_by_text('Application Sessions',exact=True).first.click();p.wait_for_timeout(1000);p.locator('.st-key-load_app_156 button').click();p.get_by_text('Open Best-of résumé comparison',exact=True).wait_for(timeout=120000);
     if not p.get_by_role('checkbox',name='Open Best-of résumé comparison',exact=True).is_checked():p.get_by_text('Open Best-of résumé comparison',exact=True).click()
     p.get_by_role('heading',name='Available Source Wordings — Estimated JD Relevance',exact=True).wait_for(timeout=120000)
    if command['action']=='load':
     box=p.get_by_test_id('stSelectbox').filter(has=p.get_by_text('Comparison project',exact=True)).last;box.evaluate("e=>e.scrollIntoView({block:'center'})");box.locator('[data-baseweb=select]').click();p.keyboard.type('Job AI Helper');p.get_by_role('option').filter(has_text='Job AI Helper').first.click();p.wait_for_timeout(2000)
     source=p.get_by_test_id('stSelectbox').filter(has=p.get_by_text('Source wording to explain',exact=True)).last
     if 'Added automated unit tests' not in source.inner_text():
      source.evaluate("e=>e.scrollIntoView({block:'center'})");source.locator('[data-baseweb=select]').click();source.get_by_role('combobox').fill('automated unit tests');p.get_by_role('option').filter(has_text='Added automated unit tests').first.click()
     assert 'Added automated unit tests' in source.inner_text();p.wait_for_timeout(2000)
    if command['action']=='project':
     box=p.get_by_test_id('stSelectbox').filter(has=p.get_by_text('Comparison project',exact=True)).last;box.evaluate("e=>e.scrollIntoView({block:'center'})");box.locator('[data-baseweb=select]').click();p.keyboard.type(command['value']);p.get_by_role('option').filter(has_text=command['value']).first.click();p.wait_for_timeout(1500)
    if command['action']=='identical':
     box=p.get_by_test_id('stSelectbox').filter(has=p.get_by_text('Related Evidence Library wording',exact=True)).last;box.evaluate("e=>e.scrollIntoView({block:'center'})");box.evaluate("e=>e.scrollIntoView({block:'center'})");box.locator('[data-baseweb=select]').click();p.keyboard.press('End');p.keyboard.press('Enter');p.wait_for_timeout(1500)
    if command['action']=='expand':
     p.get_by_text('Advanced Diagnostics — JD ranking and detailed evidence',exact=True).click();p.wait_for_timeout(1000)
    if command['action']=='narrow':
     p.set_viewport_size({'width':760,'height':1100});button=p.locator('[data-testid=stSidebarCollapseButton] button').first
     if button.is_visible():button.click()
     p.get_by_text('Estimated JD Relevance — individual wording',exact=True).evaluate("e=>{e.scrollIntoView({block:'start'});document.querySelector('[data-testid=stMain]').scrollTop-=80}")
     check=p.evaluate("()=>{const m=document.querySelector('[data-testid=stMain]');return {client:m.clientWidth,scroll:m.scrollWidth,body:document.body.innerText.slice(-5000)}}")
     check['events']=getattr(session,'_review_events',[]);check['exceptions']=p.get_by_test_id('stException').all_text_contents();(root/'reports/v37_ui_review_capture/narrow.json').write_text(json.dumps(check),encoding='utf-8')
    if command['action']=='benchmark':p.get_by_text('Bullet-Choice Benchmark Lab',exact=True).first.click();p.wait_for_timeout(1500)
   session.call(navigate)
runpy.run_path(str(root/'app.py'),run_name='__main__')

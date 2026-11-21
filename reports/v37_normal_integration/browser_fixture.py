"""Actual complete app plus clearly identified, disposable visual fixture data."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import json,runpy,sqlite3
import streamlit as st
work=Path('C:\\Users\\Admin\\Documents\\GitHub\\Job-AI-Helper\\reports\\v37_b4_workspace')
fixture=json.loads((work/'fixture.json').read_bytes())
saved=json.loads((work/'comparison-export.json').read_bytes())
assert sha256(Path(fixture['docx']).read_bytes()).hexdigest()==saved['a_docx_sha256']
assert saved['generation_id']==fixture['generation_id']
with sqlite3.connect((work/'app/data/applications.db').as_uri()+'?mode=ro',uri=True) as c:
 report=json.loads(c.execute('select report_json from applications where id=2').fetchone()[0])
jd=report['raw_jd_text'];mode='v35-relevance'
context=sha256((fixture['generation_id']+'|'+saved['a_docx_sha256']+'|'+jd+'|'+mode+'|library_tie=False').encode()).hexdigest()[:16]
st.session_state['phase9f_auto_bestof_run_mode_2']={'generation_id':fixture['generation_id'],'mode':mode,'library_tie_preference':False}
st.session_state[f'phase9f_auto_bestof_receipt_2_{context}']={'status':'not_run','proposal':saved['proposal'],
 'a_docx_sha256':saved['a_docx_sha256'],'reason':'Exact saved selection receipt; missing native snapshots are not reconstructed.'}
view=st.sidebar.selectbox('Diagnostic fixture view',['Saved selection from real bounded comparison','Synthetic multi-project UI demonstration'],key='b4_fixture_view')
case=st.sidebar.selectbox('Synthetic membership case',['Base included; Library excluded','Library included; Base excluded','Both included','Both excluded','Receipt unavailable'],key='b4_fixture_case') if view.startswith('Synthetic') else None
banner='SYNTHETIC UI DEMONSTRATION — no measured optimization decision or native result' if case else 'READ-ONLY SAVED SELECTION — exact earlier receipt; native snapshots not reconstructed'
st.markdown('<style>.b4-fixture-banner{position:fixed;top:46px;left:0;right:0;z-index:999999;background:#fff3cd;color:#503900;text-align:center;padding:5px;font-size:12px}</style><div class="b4-fixture-banner">'+banner+'</div>',unsafe_allow_html=True)
runpy.run_path('C:\\Users\\Admin\\Documents\\GitHub\\Job-AI-Helper\\app.py',run_name='__main__')
if case:
 from tests.test_v37_b4_pair_comparison import multi_fixture
 from tailoring.phase9f_bullet_inspector import render_bullet_inspector
 demo_jd,demo_report,calc=multi_fixture()
 for row in calc['rows']:
  row['project']='DEMO '+row['project']
  row['words']=len(row['bullet'].split())
  if row['project']=='DEMO Tool':
   row['in_proposed_b']=(case=='Both included' or case.startswith('Base included') and 'Selected Base' in row['sources'] or case.startswith('Library included') and 'Evidence Library' in row['sources'])
 if case=='Receipt unavailable':calc['status']='unavailable'
 st.divider();st.warning('Synthetic multi-project demonstration. Membership is a display fixture, not an observed optimizer outcome. No native score is supplied.')
 render_bullet_inspector(st,calc=calc,audit={},proposal={'mathematical_certificate':{'constraints':{'max_changed_memberships':8,'word_budget':40}}},
   result={'status':'not_run'},baseline_report=demo_report,raw_jd_text=demo_jd,projects={},application_id=0,context='synthetic')

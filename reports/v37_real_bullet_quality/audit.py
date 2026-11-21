"""Read-only real-corpus audit. No scorer/optimizer calls in this inventory."""
from pathlib import Path
from hashlib import sha256
import sys,json,csv,itertools,os
r=Path(__file__).resolve().parents[2];sys.path[:0]=[str(r),str(r/'reports/v37_bestof_release_ui_workspace')]
from sandbox import enable
enable();os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
from tailoring.phase9f_v37_corpus_benchmark import load_case,readonly_db
from tailoring.phase9f_bullet_inspector import inspector_rows
from tailoring.phase9f_v365_jd_evidence import rank_bullets,requirement_catalog
from tailoring.phase9f_bullet_relevance_diagnostic import compare_ranked_bullets
from tailoring.phase9e_blueprint_selection import fingerprint_value
from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint
out=Path(__file__).resolve().parent

from evidence_binding import bind

all_cases=[];inventory=[];pools=[]
with readonly_db(r/'data/applications.db') as db:
 for app in [156,154,149]:
  generation=db.execute('select max(id) from application_tailoring_versions where application_id=?',(app,)).fetchone()[0]
  try:case=load_case(db,generation,r)
  except Exception as e:inventory.append({'application':app,'eligible':False,'reason':str(e)});continue
  receipts=db.execute('select id,result_json from application_tailoring_verifications where application_id=? and generation_id=? order by id desc',(app,case['generation_id'])).fetchall()
  result={};reason='No saved verification for this generation';receipt={};vid=None
  for rec in receipts:
   v=json.loads(rec['result_json']);candidate,why=bind(case,v)
   if candidate:result=candidate;receipt=v;vid=rec['id'];reason=why;break
   reason=why
  rows,_=inspector_rows({},case['audit'])
  for row in rows:
   row['saved_jd_ids']=sorted({rid for g in case['audit']['projects'] if g['project']==row['project'] for final in g['final'] if final['text']==row['bullet'] for rid in final.get('jd_requirement_ids',[])})
  catalog=requirement_catalog(case['baseline'],case['projects']);ranked=rank_bullets(rows,catalog,raw_jd_text=case['raw_jd_text'],result=result,selection_recorded=False)
  before=rank_bullets(rows,catalog,raw_jd_text=case['raw_jd_text'],result={},selection_recorded=False)
  item={'application':app,'generation_row':generation,'generation_id':case['generation_id'],'company':case['company'],'job':case['title'],'eligible':True,'eligible_wordings':len(rows),'projects':len(case['audit']['projects']),'docx_sha256':case['audit']['docx_sha256'],'jd_sha256':sha256(case['raw_jd_text'].encode()).hexdigest(),'verification_row':vid,'native_evidence_binding':reason,'native_attributed_bullets_before':sum(bool(v['native_requirement_ids']) for v in before),'native_attributed_bullets_after':sum(bool(v['native_requirement_ids']) for v in ranked),'native_score':receipt.get('after_stable_analysis',{}).get('deterministic_alignment_score'),'selected_base_native_score':(receipt.get('selected_base_analysis') or {}).get('stable_analysis',{}).get('deterministic_alignment_score')}
  inventory.append(item)
  pairs=[]
  for a in ranked:
   if 'Selected Base' not in a['sources']:continue
   for b in ranked:
    if b['project']!=a['project'] or 'Evidence Library' not in b['sources'] or a['bullet']==b['bullet']:continue
    judgement=compare_ranked_bullets(a,b,catalog)
    links={v['id'] for z in [a,b] for v in z['jd_links']}
    pairs.append({'application':app,'generation_row':generation,'project':a['project'],'base':a,'library':b,'jd_requirements':[catalog[k] for k in sorted(links)],'jd_text':case['raw_jd_text'],'diagnostic':judgement,'membership':{'existing_doc_base':a['in_actual_a'],'existing_doc_library':b['in_actual_a'],'optimized_proposal_base':None,'optimized_proposal_library':None},'membership_limit':'Existing fitted membership is document-audited. A separate saved Best-of proposal is not present in this DB generation record; source-neutral research slates are not substituted.','pair_scope':'Same-project source comparison. Replacement equivalence is not established merely by project identity.','native_binding':reason,'source_receipt':item,'owner_expected_outcome':'','reviewer_notes':''})
  # Deterministic spread over projects; no outcome quotas or hand-assigned winners.
  groups={name:[p for p in pairs if p['project']==name] for name in sorted({p['project'] for p in pairs})}
  spread=[v for batch in itertools.zip_longest(*groups.values()) for v in batch if v]
  pools.append(iter(spread))
 while len(all_cases)<20 and pools:
  alive=[]
  for pool in pools:
   try:all_cases.append(next(pool));alive.append(pool)
   except StopIteration:pass
   if len(all_cases)==20:break
  pools=alive
for i,c in enumerate(all_cases,1):c['case_id']=f'R{i:02d}'
(out/'inventory.json').write_text(json.dumps(inventory,indent=2,ensure_ascii=False),encoding='utf-8')
(out/'cases.json').write_text(json.dumps(all_cases,indent=2,ensure_ascii=False),encoding='utf-8')
with (out/'owner_review.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['case_id','application','project','base_wording','library_wording','diagnostic_judgment','expected_outcome','reviewer_notes']);w.writeheader()
 for c in all_cases:w.writerow({'case_id':c['case_id'],'application':c['application'],'project':c['project'],'base_wording':c['base']['bullet'],'library_wording':c['library']['bullet'],'diagnostic_judgment':c['diagnostic']['outcome'],'expected_outcome':'','reviewer_notes':''})
print(json.dumps(inventory,indent=2,ensure_ascii=True));print('Review cases',len(all_cases))

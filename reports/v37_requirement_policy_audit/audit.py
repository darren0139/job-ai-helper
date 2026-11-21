from pathlib import Path
import csv,json,hashlib,sqlite3,subprocess,sys
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));OUT=Path(__file__).resolve().parent
from analysis_stability import stable_evidence_scoring as s
from analysis_stability import reviewed_jd_exclusions as rev
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[Path.home()/'Downloads'/d/n for d,n in [('jd_policy_phase2d2d_v17','complete_review_419.csv'),('jd_policy_phase2d4e_diagnostic_v1','complete_review_419.csv'),('jd_policy_phase2d4e_diagnostic_v1','review_419_gate.csv')]]
read=lambda p:list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
a,b,g=map(read,paths);gates={r['Review #']:r for r in g};manifest=rev._manifest();exclusions=[x for v in manifest['sources'].values() for x in v]
c=sqlite3.connect((ROOT/'data/applications.db').as_uri()+'?mode=ro',uri=True);c.execute('pragma query_only=on')
reports=[]
for aid,raw in c.execute('select id,report_json from applications where report_json is not null'):
 try:r=json.loads(raw)
 except (ValueError,TypeError):continue
 reports.append((aid,r))
results=[]
for r in a:
 text=r['Exact unresolved wording'];rid=r['Requirement ID'];sha=r['Raw JD SHA256'];hits=[]
 for aid,report in reports:
  for q in (report.get('stable_analysis') or {}).get('canonical_requirements',[]):
   if q['requirement_id']==rid or q['text']==text:
    hits.append({'application_id':aid,'id':q['requirement_id'],'importance':q['importance'],'semantic_type':q.get('semantic_type'),'match_label':q.get('match_label'),'strength':q.get('evidence_strength'),'source_sha_matches':hashlib.sha256(report.get('raw_jd_text','').encode()).hexdigest()==sha})
 results.append({'review':r['Review #'],'job':r['Job ID'],'requirement_id':rid,'text':text,'parent':r['Full raw source parent'],'section':r['JD section'],'source_sha256':sha,'original_importance':r['Original native importance'],'original_purpose':r['Original native JD purpose'],'classification':r['User review classification'],'confirmation':r['Review confirmation status'],'refinement':r['Later suggested refinement (unconfirmed)'],'lane':r['Proposed lane (working only)'],'gate':gates[r['Review #']]['consolidated_gate'],'flags':r['Repair/inspection flags'],'current_isolated_importance':s._classify_raw_importance(text),'isolated_probe_is_not_full_jd_replay':True,'exclusion_manifest_membership':[e for e in exclusions if e['id']==rid],'application_snapshot_matches':hits})
app=dict(reports)[156];stable=app['stable_analysis'];rows=stable['canonical_requirements'];stake=next(q for q in rows if 'stakeholder' in q['text'].lower());current=s.canonicalise_requirements(app['jd_profile'],app['raw_jd_text'])
score,numerator,denom=s._weighted_coverage(rows,{'core','required','deal_breaker'})
raw42=json.loads((paths[1].parent/'full_raw_42_jds.json').read_text(encoding='utf-8'));selected_sources=[]
for item in raw42:
 if item['job_id'] in [240,158]:
  raw=item['jd'];rawsha=hashlib.sha256(raw.encode()).hexdigest();parsed=s.canonicalise_requirements({},raw)
  selected_sources.append({'job':item['job_id'],'raw_sha256':rawsha,'exact_matches_review_source':any(r['source_sha256']==rawsha for r in results),'requirements':[q for q in parsed['requirements'] if any(r['job']==str(item['job_id']) and (r['requirement_id']==q['requirement_id'] or r['text']==q['text']) for r in results)],'parsed_from':'archived full_raw_42_jds.json; empty profile, ordinary current parser; not applicant scoring'})
common=['Review #','Job ID','Requirement ID','Exact unresolved wording','User review classification','Review confirmation status','Raw JD SHA256']
differences=[{'review':x['Review #'],'field':k,'old':x[k],'later':y[k]} for x,y in zip(a,b) for k in common if x[k]!=y[k]]
core_support=[r for r in results if r['original_importance']=='core' and 'Supporting' in r['classification']]
summary={'rows':len(a),'later_rows':len(b),'confirmation_counts':dict(Counter(r['Review confirmation status'] for r in a)),'gate_counts':dict(Counter(r['consolidated_gate'] for r in g)),'shared_field_differences':differences,'core_to_supporting_count':len(core_support),'core_to_supporting_confirmed':sum(r['confirmation']=='CONFIRMED_IN_CHAT' for r in core_support),'confirmed_core_support_still_core_isolated':[r['review'] for r in core_support if r['confirmation']=='CONFIRMED_IN_CHAT' and r['current_isolated_importance']=='core'],'exact_source_snapshot_core_support':[{'review':r['review'],'hits':[x for x in r['application_snapshot_matches'] if x['source_sha_matches'] and x['importance']=='core']} for r in core_support if any(x['source_sha_matches'] and x['importance']=='core' for x in r['application_snapshot_matches'])],'manifest_exclusion_count':len(exclusions),'manifest_sources':len(manifest['sources']),'manifest_withheld_sources':manifest['withheld_sources'],'application_reports_scanned':len(reports)}
receipt={'schema_version':1,'summary':summary,'sources':[{'path':str(p),'sha256':h(p)} for p in paths],'reviews':results,'selected_full_jd_replays':selected_sources,'app156':{'raw_jd_sha256':hashlib.sha256(app['raw_jd_text'].encode()).hexdigest(),'source_lines':[{'line':i,'text':line} for i,line in enumerate(app['raw_jd_text'].splitlines(),1) if 'stakeholder' in line.lower()],'saved_score':stable['deterministic_alignment_score'],'scorer':stable['scoring_version'],'stakeholder_requirement':{k:v for k,v in stake.items() if k not in ['capability_retrieval']},'current_parser_requirement':[q for q in current['requirements'] if q['requirement_id']==stake['requirement_id']],'hard_coverage_unrounded':score,'hard_numerator':numerator,'hard_denominator':denom,'stakeholder_weight':3.0,'score_weights':stable['score_weights']},'preservation':{'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'index_sha256':h(ROOT/'.git/index'),'db_sha256':h(ROOT/'data/applications.db')},'source_hashes':{n:h(ROOT/n) for n in ['analysis_stability/stable_evidence_scoring.py','analysis_stability/reviewed_jd_exclusions.py','database/reviewed_analysis_selection.py','tailoring/phase9f_v37_guarded_evaluation.py','tailoring/capability_taxonomy.py']}}
(OUT/'audit.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=True),encoding='utf-8');print(json.dumps(summary,ensure_ascii=True)[:5200]);print('source replay',[(r['job'],r['exact_matches_review_source'],len(r['requirements'])) for r in selected_sources]);print('App156 hard denominator',denom,'numerator',numerator)

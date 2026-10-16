"""Offline descriptive backlog audit; no scorer, provider, DB writes or gold reads."""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
from copy import deepcopy
from difflib import SequenceMatcher
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import unicodedata

os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP','True')
os.environ.setdefault('CAPABILITY_RAG_MODE','off')
from database.analysis_cache_manager import _normalise_source_text
from analysis_stability.stable_evidence_scoring import requirement_is_score_eligible
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge
from tailoring.capability_taxonomy import get_default_taxonomy
from taxonomy_discovery.technology_registry import get_default_registry
from taxonomy_discovery.unresolved_multidimensional_triage import predicate_observations
from taxonomy_discovery.unresolved_adjudication import fingerprint, NAC

ROOT=Path(__file__).resolve().parents[1]
VERSION='unresolved-backlog-clustering-v1'
FIELDS=('requirement_id','text','atomic_focus','importance','score_eligible','sources','parent_text','source_provenance','decomposition','scope','parent_requirement_id','atomic_group_id','group_weight_fraction','scoring_parent_occurrence_id','is_atomic')
PATTERNS={
 'activity_cues':r'\b(?:build\w*|develop\w*|implement\w*|maintain\w*|design\w*|deploy\w*|test\w*|integrat\w*|monitor\w*|analys[ei]\w*|analyz\w*|automat\w*|configur\w*|debug\w*|troubleshoot\w*|ingest\w*|transform\w*)\b',
 'familiarity_exposure_cues':r'\b(?:familiarity|exposure|knowledge of|experience with|proficiency)\b',
 'optional_or_alternative_cues':r'\b(?:preferred|advantageous|desirable|optional|or|such as|one or more)\b',
 'professional_behavior_cues':r'\b(?:collaborat\w*|communicat\w*|teamwork|stakeholders|mentoring|leadership|learn\w*|passion|motivat\w*|interpersonal|problem.solving|analytical|adaptab\w*)\b',
 'credential_or_duration_cues':r'\b(?:degree|diploma|certifi\w*|bachelor|master|years? of|years? experience|background in)\b',
 'generic_technical_cues':r'\b(?:software|systems?|technical|technology|technologies|engineering|solutions?|platforms?)\b',
 'negative_scope_cues':r'\b(?:not required|without|no experience|do not|not expected|excluded)\b'}
DESTINATIONS={
 'activity_cues':'Capability predicates/native resolver; verify activity and exclusions',
 'technology_activity_cooccurrence':'Contextual relationships/native resolver; not an approved mapping',
 'technology_alias_candidates':'Technology registry/identity scope; candidates are not full resolution',
 'familiarity_exposure_cues':'Identity scope and qualification boundaries',
 'optional_or_alternative_cues':'JD extraction/decomposition and nonmandatory scope',
 'professional_behavior_cues':'Professional requirement handling; not automatic technical capabilities',
 'credential_or_duration_cues':'Credential/eligibility handling',
 'generic_technical_cues':'Source-scope/provenance review before narrower diagnosis',
 'negative_scope_cues':'Requirement exclusions/source-scope preservation',
 'parent_scope_differs':'Source-scope/decomposition; difference alone is not a defect',
 'parent_not_verified':'Provenance preservation/source recovery',
 'normalization_artifacts':'Native normalization/source preservation',
 'existing_predicate_observations':'Existing capability predicates/native selector; no credit inferred',
 'no_specific_cue':'Manual source investigation; no forced route'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def sha_text(text):return hashlib.sha256(text.encode()).hexdigest()
def normal(text):return ' '.join(unicodedata.normalize('NFKC',str(text)).replace('\u200b','').casefold().split())
def tokens(text):return set(re.findall(r'[\w]+(?:\+\+|#)?',normal(text)))


def similar(a,b,*,quarantine=False):
    x,y=normal(a),normal(b)
    if x==y:return True
    tx,ty=tokens(x),tokens(y)
    if not tx or not ty:return False
    if quarantine and min(len(tx),len(ty))<=2:
        shorter,longer=(x,y) if len(tx)<=len(ty) else (y,x)
        return bool(re.search(r'(?<![\w+#])'+re.escape(shorter)+r'(?![\w+#])',longer))
    ratio=min(len(tx),len(ty))/max(len(tx),len(ty));jac=len(tx&ty)/len(tx|ty)
    return ratio>=(.60 if quarantine else .75) and (jac>=(.70 if quarantine else .82) or
        (min(len(tx),len(ty))>=4 and SequenceMatcher(None,x,y,autojunk=False).ratio()>=(.88 if quarantine else .92)))


def protected_sources():
    # No receipt template, prior recommendation, review bucket or expected route.
    p=json.loads((ROOT/'reports/unresolved_independent_review_packet_v5.json').read_text(encoding='utf-8'))
    if p['packet_fingerprint']!=fingerprint({k:v for k,v in p.items() if k!='packet_fingerprint'}):raise ValueError('V5 packet integrity')
    keys={tuple(c['key']) for c in p['cases']}|NAC
    corpus=json.loads((ROOT/'tests/fixtures/confirmed_taxonomy_coverage.json').read_text(encoding='utf-8'))
    if fingerprint(corpus)!=p['source_fingerprint']:raise ValueError('Protected source changed')
    selected=[(j['job_id'],r) for j in corpus['snapshot']['audit']['corpus']['jobs'] for r in j['baseline_stable_analysis']['canonical_requirements'] if (j['job_id'],r['requirement_id']) in keys]
    if len(selected)!=40:raise ValueError('All protected forty identities required')
    result={'keys':keys,'texts':[r.get('atomic_focus') or r['text'] for _,r in selected],
      'families':{(j,r.get('scoring_parent_occurrence_id')) for j,r in selected if r.get('scoring_parent_occurrence_id')},
      'parent_texts':list({r['parent_text'] for _,r in selected if r.get('parent_text')}),'source_fingerprint':p['source_fingerprint']}
    # Recovery cache is accessed for neutral source provenance ONLY. No previous
    # recommendation, inherited answer or reviewer decision is consulted.
    recovered=json.loads((ROOT/'reports/unresolved_gold_decision_review_v3.json').read_text(encoding='utf-8'))
    if recovered['source_fingerprint']!=p['source_fingerprint']:raise ValueError('Protected recovery source changed')
    for row in recovered['cases']:
        if tuple(row['key']) not in keys:continue
        for parent in row['source_context']['parent_provenance']:
            if not parent.get('raw_parent_verified_in_jd'):continue
            if parent.get('raw_parent_text'):result['parent_texts'].append(parent['raw_parent_text'])
            if parent.get('parent_occurrence_id'):result['families'].add((row['key'][0],parent['parent_occurrence_id']))
    result['parent_texts']=sorted(set(result['parent_texts']))
    return result


def preservation():
    text=(ROOT/'docs/unresolved_independent_review_readiness_v5.md').read_text(encoding='utf-8')
    hashes=json.loads(text.split('```json\n')[-1].split('\n```')[0])['protected_hashes']
    for name in ('docs/unresolved_independent_review_packet_v5.md','reports/unresolved_independent_review_packet_v5.json','reports/unresolved_independent_review_receipts_template_v5.json','docs/unresolved_independent_review_readiness_v5.md','taxonomy_discovery/unresolved_independent_review.py','scripts/prepare_unresolved_independent_review_v5.py','tests/test_unresolved_independent_review_v5.py'):
        hashes[name]=sha(ROOT/name)
    if any(sha(ROOT/name)!=h for name,h in hashes.items()):raise ValueError('Protected prior bytes changed')
    return hashes


def read_database(path):
    """One read transaction, fixed SELECTs, mode=ro/query_only; no migrations."""
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'discovered_jobs','job_match_snapshots'}.issubset(tables):raise ValueError('Snapshot tables unavailable')
        jobs=[dict(r) for r in c.execute('SELECT id,content_hash,lifecycle_status,description FROM discovered_jobs')]
        snapshots=[dict(r) for r in c.execute("SELECT id,discovered_job_id,job_content_hash,match_version,scoring_version,taxonomy_version,created_at,json_extract(stable_analysis_json,'$.canonical_requirements') requirements_json FROM job_match_snapshots WHERE json_valid(stable_analysis_json) ORDER BY id")]
        apps=[];info={}
        if {'applications','application_analysis_versions'}.issubset(tables):
            for name,query in {
                'analysis_versions':'SELECT COUNT(*) FROM application_analysis_versions',
                'archived_analysis_versions':"SELECT COUNT(*) FROM application_analysis_versions WHERE status!='active'",
                'orphaned_analysis_versions':'SELECT COUNT(*) FROM application_analysis_versions WHERE application_id NOT IN (SELECT id FROM applications)',
                'unversioned_application_reports':"SELECT COUNT(*) FROM applications WHERE report_json IS NOT NULL AND report_json!='' AND id NOT IN (SELECT application_id FROM application_analysis_versions)"}.items():info[name]=c.execute(query).fetchone()[0]
            apps=[dict(r) for r in c.execute("SELECT v.id,v.application_id,v.created_at,v.cache_version,v.pipeline_contract_version,json_extract(v.report_json,'$.raw_jd_text') raw_jd_text,json_extract(v.report_json,'$.stable_analysis.canonical_requirements') requirements_json,json_extract(v.report_json,'$.stable_analysis.scoring_version') scoring_version,json_extract(v.report_json,'$.stable_analysis.capability_taxonomy_version') taxonomy_version FROM application_analysis_versions v JOIN applications a ON a.id=v.application_id WHERE v.status='active' AND v.id IN (SELECT MAX(id) FROM application_analysis_versions WHERE status='active' GROUP BY application_id) AND json_valid(v.report_json)")]
        info.update(database_user_version=c.execute('PRAGMA user_version').fetchone()[0],sqlite_runtime=sqlite3.sqlite_version,
          journal_mode=c.execute('PRAGMA journal_mode').fetchone()[0],query_only=c.execute('PRAGMA query_only').fetchone()[0],
          snapshot_rows_total=c.execute('SELECT COUNT(*) FROM job_match_snapshots').fetchone()[0],
          snapshot_invalid_json=c.execute('SELECT COUNT(*) FROM job_match_snapshots WHERE NOT json_valid(stable_analysis_json)').fetchone()[0])
    return jobs,snapshots,apps,info


def canon(s):
    rows=json.loads(s.get('requirements_json') or '[]')
    if not isinstance(rows,list) or any(not isinstance(r,dict) or not r.get('requirement_id') for r in rows):raise ValueError('Canonical rows unavailable')
    if len({r['requirement_id'] for r in rows})!=len(rows):raise ValueError('Duplicate canonical ID inside snapshot')
    return rows


def stored_unresolved(r):
    k=r.get('knowledge_resolution') or {}
    return not (r.get('capability_id') or k.get('status')=='resolved' or r.get('knowledge_status') in ('CAPABILITY_RESOLVED','TECHNOLOGY_IDENTITY_RESOLVED') or k.get('knowledge_status')=='TECHNOLOGY_IDENTITY_RESOLVED')


def quarantine_reason(req,jid,p):
    if (jid,req['requirement_id']) in p['keys']:return 'protected_key'
    if jid is not None and (jid,req.get('scoring_parent_occurrence_id')) in p['families']:return 'shared_protected_parent'
    surfaces=[req.get('atomic_focus') or req.get('text') or '',req.get('parent_text') or '']
    surfaces += [s.get('raw_parent_text') or '' for s in req.get('source_provenance',[]) if isinstance(s,dict)]
    for text in surfaces:
        if not text:continue
        if any(normal(text)==normal(x) for x in p['texts']):return 'protected_exact_text'
        # A short independent clause can expose a protected parent even where
        # child-versus-parent length makes a near-text threshold inapplicable.
        if len(tokens(text))>=3 and any(normal(text).rstrip('. ') in normal(x) or
            (len(tokens(x))>=3 and normal(x).rstrip('. ') in normal(text)) for x in p['parent_texts']):
            return 'protected_parent_clause_containment'
        if any(similar(text,x,quarantine=True) for x in p['texts']+p['parent_texts']):return 'protected_near_text_or_parent'
    return None


def observations(req,native,jd):
    text=req.get('atomic_focus') or req.get('text') or '';flags=[n for n,p in PATTERNS.items() if re.search(p,text,re.I)];entities=[]
    for e in get_default_registry().entries:
        if e.get('entry_kind')=='architecture_pattern':continue
        spans=[m.group() for alias in e['aliases'] for m in re.finditer(r'(?<![\w+#])'+re.escape(alias)+r'(?![\w+#])',text,re.I)]
        if spans:entities.append({'technology_id':e['technology_id'],'literal_alias_spans':sorted(set(spans))})
    if entities:flags.append('technology_alias_candidates')
    if entities and 'activity_cues' in flags:flags.append('technology_activity_cooccurrence')
    parent=req.get('parent_text') or '';provenance=req.get('source_provenance') or []
    available=bool(parent and jd and ' '.join(parent.split()) in ' '.join(jd.split()))
    verified=bool(provenance and jd and all(isinstance(p,dict) and p.get('raw_parent_text') and ' '.join(p['raw_parent_text'].split()) in ' '.join(jd.split()) for p in provenance))
    if parent and normal(parent)!=normal(text):flags.append('parent_scope_differs')
    if not verified:flags.append('parent_not_verified')
    if '\u200b' in text or '\ufffd' in text or re.search(r'^\([a-z]\)',text):flags.append('normalization_artifacts')
    taxonomy=get_default_taxonomy().by_id();fits=predicate_observations(text,[{'capability_id':cid} for cid in taxonomy],taxonomy)
    if fits:flags.append('existing_predicate_observations')
    return {'dimensions':sorted(flags or ['no_specific_cue']),'technology_alias_candidates':entities,
      'predicate_observations':[{'capability_id':f['capability_id'],'exact_spans':f['exact_spans'],'status':f['status']} for f in fits],
      'parent_source_available':available,'parent_provenance_verified':verified,
      'native_scope':(native.get('identity_scope') or {}).get('category','NOT_RECORDED'),
      'native_registry_reason':(native.get('registry_resolution') or {}).get('reason'),
      'native_taxonomy_status':(native.get('taxonomy_diagnostics') or {}).get('status')}


def unsafe_text(text):return bool(re.search(r'(?i)(sk-[\w-]{10,}|api[_ -]?key\s*[:=]|[\w.+-]+@[\w.-]+\.[a-z]{2,}|(?<!\d)\+?\d[\d ()-]{7,}\d(?!\d))',text))


def analyze(records,p,resolve=resolve_requirement_with_production_knowledge):
    counts=Counter();excluded=Counter();knowledge=Counter();rows={};seen=set();texts=[];resolved_none=0
    def identity_of(record):
        req=record['requirement']
        return (record['job_key'],req['requirement_id'],normal(req.get('atomic_focus') or req.get('text') or ''))
    # Any protected view quarantines all copies of that same occurrence.
    blocked={identity_of(record):reason for record in records
             if (reason:=quarantine_reason(record['requirement'],record.get('job_id'),p))}
    for record in records:
        req=record['requirement'];text=req.get('atomic_focus') or req.get('text') or ''
        counts['canonical_records']+=1;counts['stored_knowledge_unresolved']+=stored_unresolved(req)
        counts['stored_applicant_none']+=req.get('match_label','none')=='none'
        native=resolve({k:deepcopy(req[k]) for k in FIELDS if k in req});knowledge[native['knowledge_status']]+=1
        if native['status']=='resolved':resolved_none+=req.get('match_label','none')=='none';continue
        counts['current_knowledge_unresolved_records']+=1
        counts['eligible_unresolved_records']+=requirement_is_score_eligible(req)
        counts['unresolved_with_stored_positive_match']+=req.get('match_label','none')!='none'
        identity=(record['job_key'],req['requirement_id'],normal(text));texts.append(normal(text))
        counts['duplicate_current_record_views']+=identity in seen;seen.add(identity)
        reason=blocked.get(identity)
        if reason:excluded[reason]+=1;continue
        if unsafe_text(text):excluded['privacy_sensitive_text']+=1;continue
        column='stable_analysis_json::canonical_requirements' if record['source_table']=='job_match_snapshots' else 'report_json::stable_analysis.canonical_requirements'
        ref=f"{record['source_table']}[id={record['snapshot_id']}].{column}[requirement_id={req['requirement_id']}]"
        provenance={'source_reference':ref,'application_id':record.get('application_id'),'snapshot_id':record['snapshot_id'],'source_versions':record['source_versions']}
        obs=observations(req,native,record.get('raw_jd_text'))
        variant=fingerprint({k:req.get(k) for k in ('parent_text','source_provenance','decomposition','scope','group_weight_fraction')})
        provenance['native_scope']=obs['native_scope'];provenance['scope_provenance_fingerprint']=variant
        if identity in rows:
            old=rows[identity];old['record_provenance'].append(provenance)
            old['dimensions']=sorted(set(old['dimensions'])|set(obs['dimensions']))
            old['parent_source_available'] &= obs['parent_source_available']
            old['parent_provenance_verified'] &= obs['parent_provenance_verified']
            if old['native_scope']!=obs['native_scope']:old['native_scope']='MULTIPLE_NATIVE_SCOPE_OBSERVATIONS'
            continue
        rows[identity]={'job_key':record['job_key'],'job_id':record.get('job_id'),'requirement_id':req['requirement_id'],
          'requirement_text':text,'normalized_text_fingerprint':fingerprint(normal(text)), 'importance':req.get('importance'),
          'source_reference':ref,'source_versions':record['source_versions'],'record_provenance':[provenance],
          'stored_match_label':req.get('match_label','none'),'score_eligible':requirement_is_score_eligible(req),
          'group_weight_fraction':req.get('group_weight_fraction'),**obs}
    items=list(rows.values())
    return {'counts':dict(counts),'knowledge_counts':dict(knowledge),'knowledge_resolved_but_stored_applicant_none':resolved_none,
      'distinct_unresolved_occurrences':len(seen),'unique_unresolved_normalized_texts':len(set(texts)),
      'quarantine_excluded_record_counts':dict(excluded),'development_occurrences':len(items),
      'development_unique_texts':len({r['normalized_text_fingerprint'] for r in items}),
      'development_distinct_job_or_jd_keys':len({r['job_key'] for r in items}),
      'clusters':clusters(items),'near_duplicate_groups':near_groups(items)}


def near_groups(rows):
    exact={}
    for r in rows:exact.setdefault(r['normalized_text_fingerprint'],[]).append(r)
    groups=[]
    for members in sorted(exact.values(),key=lambda g:g[0]['normalized_text_fingerprint']):
        row=members[0];ids=[e['technology_id'] for e in row['technology_alias_candidates']]
        negative=bool(re.search(PATTERNS['negative_scope_cues'],row['requirement_text'],re.I))
        group=next((g for g in groups if g['ids']==ids and g['negative']==negative and all(similar(row['requirement_text'],t) for t in g['texts'])),None)
        if group is None:group={'ids':ids,'negative':negative,'texts':[],'rows':[]};groups.append(group)
        group['texts'].append(row['requirement_text']);group['rows'].extend(members)
    output=[]
    for g in groups:
        if len(g['rows'])<2:continue
        output.append({'group_id':'wording_'+fingerprint(sorted(r['normalized_text_fingerprint'] for r in g['rows']))[:12],
          'occurrences':len(g['rows']),'unique_texts':len(g['texts']),
          'distinct_job_or_jd_keys':len({r['job_key'] for r in g['rows']}),
          'member_references':[{'job_key':r['job_key'],'requirement_id':r['requirement_id'],'source_reference':r['source_reference']} for r in g['rows']],
          'shared_defect_not_inferred':True})
    return sorted(output,key=lambda g:(-g['distinct_job_or_jd_keys'],-g['occurrences'],g['group_id']))


def clusters(rows):
    members=defaultdict(list)
    for r in rows:
        for flag in r['dimensions']:members[flag].append(r)
        for t in r['technology_alias_candidates']:members['technology:'+t['technology_id']].append(r)
        for p in r['predicate_observations']:members['predicate:'+p['capability_id']].append(r)
    output=[]
    for name,group in members.items():
        dest=DESTINATIONS.get(name,DESTINATIONS['technology_alias_candidates' if name.startswith('technology:') else 'existing_predicate_observations'])
        examples=[{k:r[k] for k in ('job_key','job_id','requirement_id','requirement_text','source_reference','source_versions','importance','native_scope','parent_source_available','parent_provenance_verified')}
          for r in sorted(group,key=lambda r:(not r['parent_provenance_verified'],str(r['job_key']),r['requirement_id'])) if len(r['requirement_text'])<=360][:3]
        output.append({'cluster_id':'desc_'+fingerprint(name)[:12],'title':name.replace('_',' '),'dimension':name,
          'occurrences':len(group),'raw_record_views':sum(len(r['record_provenance']) for r in group),
          'unique_normalized_texts':len({r['normalized_text_fingerprint'] for r in group}),
          'distinct_job_or_jd_keys':len({r['job_key'] for r in group}),
          'native_scope_counts':dict(Counter(r['native_scope'] for r in group)),
          'native_registry_reason_counts':dict(Counter(str(r['native_registry_reason']) for r in group)),
          'native_taxonomy_status_counts':dict(Counter(str(r['native_taxonomy_status']) for r in group)),
          'parent_source_available_count':sum(r['parent_source_available'] for r in group),
          'verified_parent_provenance_count':sum(r['parent_provenance_verified'] for r in group),
          'multiple_scope_provenance_view_count':sum(len({p['scope_provenance_fingerprint'] for p in r['record_provenance']})>1 for r in group),
          'source_readiness':('SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION' if any(r['parent_provenance_verified'] for r in group)
                             else 'PARENT_PROVENANCE_VERIFICATION_NEEDED' if any(r['parent_source_available'] for r in group)
                             else 'SOURCE_RECOVERY_REQUIRED'),
          'representatives':examples,'investigate_existing_subsystem_first':dest,
          'investigation_suitability':'RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW' if len({r['job_key'] for r in group})>=2 else 'SINGLE_JD_OBSERVATION',
          'uncertainties':['Dimensions overlap; counts are not additive or approved routes.',
            'Aliases, source cues and predicate observations do not prove a defect or full qualification.',
            'Similar wording can have different exclusions, parent scope and causal blockers.'],
          'false_positive_risk':'HIGH if converted into automatic mappings/credits',
          'complexity':'SOURCE_AND_NATIVE_CONTRACT_REVIEW_REQUIRED'})
    output.sort(key=lambda c:(-c['distinct_job_or_jd_keys'],-c['unique_normalized_texts'],-c['verified_parent_provenance_count'],c['dimension']))
    for i,c in enumerate(output,1):c['descriptive_priority_rank']=i
    return output


def build_report(jobs,snapshots,apps,inventory,p):
    jobmap={j['id']:j for j in jobs};latest={}
    for s in snapshots:
        if s['discovered_job_id'] not in latest or s['id']>latest[s['discovered_job_id']]['id']:latest[s['discovered_job_id']]=s
    scopes=defaultdict(list);selection=Counter();history=Counter();all_keys=[];historical_unresolved=[]
    for s in snapshots:
        for req in canon(s):
            all_keys.append((s['discovered_job_id'],req['requirement_id'],normal(req.get('atomic_focus') or req.get('text') or '')))
            history['canonical_records']+=1;history['stored_unresolved_records']+=stored_unresolved(req)
            if stored_unresolved(req):historical_unresolved.append(all_keys[-1])
    for jid,s in sorted(latest.items()):
        job=jobmap.get(jid);scope='active_same_hash'
        if not job:scope='orphaned_discovered_job'
        elif s['job_content_hash']!=job['content_hash']:scope='stale_job_content'
        elif job['lifecycle_status']!='active':scope='inactive_job'
        selection[scope]+=1
        for req in canon(s):scopes[scope].append({'job_key':f'job:{jid}','job_id':jid,'snapshot_id':s['id'],'source_table':'job_match_snapshots',
          'source_versions':{k:s.get(k) for k in ('scoring_version','taxonomy_version','match_version','created_at')},
          'requirement':req,'raw_jd_text':job['description'] if job and scope in ('active_same_hash','inactive_job') else None})
    for s in apps:
        jd=s.get('raw_jd_text') or ''
        if not jd:selection['application_source_unavailable']+=1;continue
        doc=fingerprint(_normalise_source_text(jd))
        for req in canon(s):scopes['application_latest_active'].append({'job_key':'application-jd:'+doc,'job_id':None,'application_id':s['application_id'],
          'snapshot_id':s['id'],'source_table':'application_analysis_versions',
          'source_versions':{k:s.get(k) for k in ('scoring_version','taxonomy_version','cache_version','pipeline_contract_version','created_at')},
          'requirement':req,'raw_jd_text':jd})
    analyzed={k:analyze(v,p) for k,v in scopes.items() if k in ('active_same_hash','inactive_job','application_latest_active')}
    history.update(distinct_job_requirement_text_occurrences=len(set(all_keys)),repeated_snapshot_record_views=len(all_keys)-len(set(all_keys)),superseded_snapshot_rows=len(snapshots)-len(latest))
    history.update(stored_unresolved_distinct_occurrences=len(set(historical_unresolved)),
                   stored_unresolved_duplicate_snapshot_views=len(historical_unresolved)-len(set(historical_unresolved)))
    versions=Counter((s.get('match_version'),s.get('scoring_version'),s.get('taxonomy_version')) for s in latest.values())
    report={'schema_version':VERSION,'source_inventory':inventory,'selection':dict(selection),'latest_snapshot_job_count':len(latest),
      'active_jobs_without_selected_snapshot':sum(j['lifecycle_status']=='active' and j['id'] not in latest for j in jobs),
      'application_latest_active_analysis_count':len(apps),'application_distinct_jd_documents':len({fingerprint(_normalise_source_text(s.get('raw_jd_text') or '')) for s in apps if s.get('raw_jd_text')}),
      'application_version_distribution':[{'scoring_version':v[0],'taxonomy_version':v[1],'cache_version':v[2],'pipeline_contract_version':v[3],'analyses':n}
        for v,n in sorted(Counter(tuple(s.get(k) for k in ('scoring_version','taxonomy_version','cache_version','pipeline_contract_version')) for s in apps).items())],
      'latest_snapshot_versions':[{'match_version':v[0],'scoring_version':v[1],'taxonomy_version':v[2],'jobs':n} for v,n in sorted(versions.items())],
      'snapshot_history_counts':dict(history),'scopes':analyzed,
      'excluded_unavailable_scopes':{k:{'jobs':selection[k],'canonical_records':len(scopes[k])} for k in ('orphaned_discovered_job','stale_job_content')},
      'protected_benchmark_size':len(p['keys']),'protected_source_fingerprint':p['source_fingerprint'],
      'native_knowledge_versions':{'taxonomy':get_default_taxonomy().version,'registry':get_default_registry().version},
      'no_reviewer_decisions_accessed_for_analysis':True,'model_calls':0,'network_calls':0,'database_writes':0,'scoring_changes':0,
      'limitations':['Current knowledge rechecked on latest stored canonical inputs; no parser, evidence or scoring replay.',
        'Job Finder jobs and application JD documents are separate scopes; no invented combined job total.',
        'Unanalyzed active jobs have unknown requirement backlog; absent snapshots do not mean zero gaps.',
        'Latest active application analysis is not proof of current selected resume/session binding.',
        'Knowledge unresolved is not a true taxonomy gap or missing applicant evidence.',
        'Quarantine is deliberately conservative, not semantic duplicate adjudication.',
        'Cues are observations, not affirmed duties; negative scope/alternatives require human review.']}
    report['input_inventory_fingerprint']=fingerprint({'jobs':[(j['id'],j['content_hash'],j['lifecycle_status'],sha_text(j.get('description') or '')) for j in jobs],
      'snapshots':[(s['id'],s['discovered_job_id'],s['job_content_hash'],sha_text(s.get('requirements_json') or '')) for s in snapshots],
      'applications':[(s['id'],s['application_id'],sha_text(s.get('requirements_json') or ''),sha_text(s.get('raw_jd_text') or '')) for s in apps]})
    return report


def markdown(r):
    lines=['# Unresolved backlog clustering V1','',
      '**Descriptive investigation only. No requirements were fixed. No clusters are approved routes or root causes.**','',
      'This development report is not a V5 reviewer packet; do not distribute it as independent review material.','',
      '## Source selection','',
      'SQLite mode=ro/query_only in one read transaction, without schema initialization. Latest Job Finder snapshot '
      'means maximum ID per discovered job, matching the existing corpus API. Active backlog requires an active '
      'existing job and equal snapshot/current JD content hashes. Expired, changed-source and superseded snapshots '
      'are separate history. Current knowledge is rechecked using the existing pure production resolver on stored '
      'canonical inputs. Stored match labels/eligibility remain historical metadata, not newly calculated scores.','',
      'Application views select the maximum active version ID per existing application. Exact transport-normalized '
      'JD fingerprints group these into document views, not guessed Job Finder job IDs. Repeated application views '
      'are collapsed while preserving provenance. Archived/orphaned analyses and unversioned reports are separately '
      'counted, not silently current. Missing source/analysis means unknown backlog. No resume evidence or full JD export.','',
      '```json',json.dumps({k:r[k] for k in ('source_inventory','selection','latest_snapshot_job_count','active_jobs_without_selected_snapshot','application_latest_active_analysis_count','application_distinct_jd_documents','application_version_distribution','snapshot_history_counts','latest_snapshot_versions')},indent=2),'```','',
      '## Backlog scopes — do not sum them','',
      '| Scope | Canonical views | Knowledge unresolved | Distinct occurrences | Unique wording | Development occurrences | Development jobs/JD documents |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for name,s in r['scopes'].items():lines.append('| '+' | '.join(map(str,[name,s['counts']['canonical_records'],s['counts'].get('current_knowledge_unresolved_records',0),s['distinct_unresolved_occurrences'],s['unique_unresolved_normalized_texts'],s['development_occurrences'],s['development_distinct_job_or_jd_keys']]))+' |')
    lines+=['','Occurrences use job/JD key + requirement ID + normalized text. This includes professional/credential '
      'requirements and is NOT the old meaningful-technical denominator or proven taxonomy-gap count. Analysis-only '
      'NFKC/case folding/whitespace/zero-width normalization preserves punctuation/C#/C++; production is unchanged.','',
      '## Quarantine and wording grouping','',
      'Forty protected keys derive from blinded V5 IDs and existing protected-control IDs, with text/family data '
      'from the frozen canonical source only. No reviewer decisions, gold answers or previous recommendations are '
      'used. Keys, shared parents, exact/near texts and protected parent surfaces are removed before descriptions '
      'or examples. Only exclusion counts are reported. Protected content is not used to design improvements.','',
      'The hash-pinned recovery cache supplies only verified original parent surfaces and occurrence IDs. '
      'No recommendation or reviewer-decision field is accessed. A clause of at least three tokens contained '
      'in a protected parent is quarantined even when length differences defeat fuzzy thresholds.','',
      'Quarantine: exact normalization; whole-boundary short protected phrases; token Jaccard >=0.70 or character '
      'ratio >=0.88, token-length ratio >=0.60. It intentionally overexcludes. Development near groups use '
      'complete-link comparisons, identical technology-candidate/negative-scope signatures, Jaccard >=0.82 or '
      'character ratio >=0.92, token-length ratio >=0.75. No transitive chaining or shared-defect inference.','']
    for name,s in r['scopes'].items():
        lines+=['### '+name,'','```json',json.dumps({k:s[k] for k in ('quarantine_excluded_record_counts','knowledge_counts','knowledge_resolved_but_stored_applicant_none','counts')},indent=2),'```','']
    lines+=['## Overlapping descriptions and investigation order','',
      'Sort: distinct jobs/JD documents, unique wording, verified-parent count, stable dimension name. No opaque '
      'impact score or invented score gains. Counts overlap. Aliases are not resolved identities; word cues are '
      'not affirmative duties; predicate observations reuse the existing report-only observer, including '
      'conjunction/exclusion/custom-policy boundaries, and are not production resolution or evidence credits.','']
    for name,s in r['scopes'].items():
        lines+=['### '+name,'','| Rank | Description | Occurrences | Unique wording | Jobs/JD documents | Verified parent | Inspect first |','|---:|---|---:|---:|---:|---:|---|']
        for c in s['clusters']:lines.append('| '+' | '.join(str(x).replace('|','\\|') for x in [c['descriptive_priority_rank'],c['title'],c['occurrences'],c['unique_normalized_texts'],c['distinct_job_or_jd_keys'],c['verified_parent_provenance_count'],c['investigate_existing_subsystem_first']])+' |')
        for c in s['clusters'][:12]:
            lines+=['','#### '+c['title'],'',f"Native scopes: {c['native_scope_counts']}. Parent available {c['parent_source_available_count']}/{c['occurrences']}; verified {c['verified_parent_provenance_count']}. "
              +c['investigation_suitability']+'. Source readiness: '+c['source_readiness']+'.','']
            for e in c['representatives']:lines+=['> '+e['requirement_text'],'',f"Source `{e['source_reference']}`; job/JD `{e['job_key']}`; requirement `{e['requirement_id']}`.",'']
            lines+=['High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.','']
    lines+=['## Generalization hypotheses and validation strategy','',
      '- Recurrent provenance/parent-scope observations may justify source preservation investigation first. '
      'Availability alone is not a parser defect. Inspect exact native traces.',
      '- Recurrent technology/activity cues may justify contextual knowledge review only after identity/activity '
      'are verified. Do not approve universal technology mappings.',
      '- Existing predicate observations may justify testing native wording/exclusion boundaries. Frequency '
      'does not justify new taxonomy entries or credit for adjacent skills.',
      '- Missing technical recognition, insufficient source evidence, legitimate professional meaning and '
      'applicant relevance without full qualification are distinct issues. This audit does not causally '
      'adjudicate those families. No applicant evidence is inspected or invented.',
      '- A later approved fix needs independent development JD documents, genuinely unseen requirements, '
      'false-positive/negation/alternative controls, native resolver invariants and parent-weight conservation. '
      'Reuse deterministic Job Match for exact versioned score/label/cap/ranking comparisons under temporary '
      'state. Phase 8 lineage must support claims; Phase 9E project selection needs regression coverage where '
      'a later evidence/selection change is relevant. Keep the frozen forty/V5 reserved for independent evaluation.',
      '- No live benchmark, models, embeddings, downloads or research were run.','', '## Limits and preservation','']
    lines.extend('- '+x for x in r['limitations'])
    if 'analyst_summary' in r:
        lines+=['','## Findings and recommended next investigation','']
        lines.extend('- '+s for s in r['analyst_summary']['observations'])
        lines+=['','Recommended order is descriptive, not a production-remediation plan:','']
        lines.extend(f"{i}. {s}" for i,s in enumerate(r['analyst_summary']['recommended_investigations'],1))
    if 'focused_validation' in r:
        lines+=['','## Focused validation','',json.dumps(r['focused_validation'],indent=2),'']
    lines+=['',f"Protected prior hashes unchanged: {len(r.get('protected_hashes',{}))}; database bytes unchanged: {r.get('database_bytes_unchanged')}. "
      'No DB writes, scoring/knowledge changes, commits, pushes, merges or branch switches.','']
    return '\n'.join(lines)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',type=Path,default=ROOT/'data/applications.db');args=p.parse_args(argv)
    outputs=[ROOT/'reports/unresolved_backlog_clustering_v1.json',ROOT/'docs/unresolved_backlog_clustering_v1.md']
    if any(x.exists() for x in outputs):p.error('Preserve versioned reports; no overwrite')
    hashes=preservation();before=sha(args.db)
    jobs,snapshots,apps,info=read_database(args.db)
    report=build_report(jobs,snapshots,apps,info,protected_sources())
    report['database_sha256_before']=before;report['database_sha256_after']=sha(args.db)
    report['database_bytes_unchanged']=before==report['database_sha256_after']
    if not report['database_bytes_unchanged']:raise ValueError('DB changed concurrently; do not freeze ambiguous results')
    if any(sha(ROOT/name)!=h for name,h in hashes.items()):raise ValueError('Protected artifact changed')
    report['protected_hashes']=hashes;report['fingerprint']=fingerprint(report)
    outputs[0].write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');outputs[1].write_text(markdown(report),encoding='utf-8')
    print(json.dumps({'scopes':{k:{'unresolved':s['counts'].get('current_knowledge_unresolved_records',0),'unique_texts':s['unique_unresolved_normalized_texts'],'development':s['development_occurrences']} for k,s in report['scopes'].items()},'protected_hashes':len(hashes)}))


if __name__=='__main__':main()

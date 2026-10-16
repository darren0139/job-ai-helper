"""Explicit offline read-only diagnostics; no model execution mode exists."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from database.job_match_manager import list_latest_job_match_corpus_snapshots
from taxonomy_discovery import unresolved_adjudication as a
from taxonomy_discovery import unresolved_gold_review as gold
from taxonomy_discovery.unresolved_source_review import recover
from taxonomy_discovery import unresolved_multidimensional_triage as triage
from taxonomy_discovery.maintenance_service import production_identity
from scripts.adjudicate_unresolved_requirements import prepare


def verify_handover(handover, report_path):
    based=handover['based_on']; report=json.loads(report_path.read_text(encoding='utf-8'))
    if hashlib.sha256(report_path.read_bytes()).hexdigest()!=based['report_sha256']:raise ValueError('V3 handover SHA mismatch')
    for k in ('source_fingerprint','parent_manifest_fingerprint'):
        if report[k]!=based[k]:raise ValueError('Handover source identity mismatch')
    identity=production_identity()
    if any(identity.get(k)!=v for k,v in based['production_knowledge_identity'].items()):raise ValueError('Production knowledge changed; review new handover')
    if based['parent_manifest_fingerprint']!=gold.original()['fingerprint']:raise ValueError('Frozen manifest mismatch')
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--handover',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--limit',type=int,default=40)
    p.add_argument('--job-id',type=int)
    args=p.parse_args(argv)
    output=args.output.resolve()
    if not 1<=args.limit<=40:p.error('Selection must be bounded to 1..40')
    if output.suffix!='.json' or gold.ROOT in output.parents and 'reports' not in output.relative_to(gold.ROOT).parts:p.error('Output must be JSON in reports/ or an external artifact directory')
    if output.exists() or output.with_suffix('.md').exists():p.error('Preserve existing reports; select new output paths')
    handover=json.loads(args.handover.read_text(encoding='utf-8'))
    v3=verify_handover(handover,gold.ROOT/handover['based_on']['v3_report_repo_path'])
    parent=gold.original();cases,_=prepare(parent)
    if v3['source_fingerprint']!=parent['source_fingerprint']:raise ValueError('Frozen source mismatch')
    protected=[gold.ORIGINAL,gold.ROOT/'tests/fixtures/unresolved_adjudication_benchmark_v2.json',a.SOURCE,
        gold.ROOT/'taxonomy/capability_taxonomy_v1.json',gold.ROOT/'taxonomy/technology_registry_v1.json',
        gold.ROOT/'tailoring/production_requirement_resolver.py',gold.ROOT/'analysis_stability/stable_evidence_scoring.py']
    hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in protected}
    db=gold.ROOT/'data/applications.db';db_before=hashlib.sha256(db.read_bytes()).hexdigest()
    snapshots=list_latest_job_match_corpus_snapshots(db_path=db)
    by_job={s['discovered_job_id']:s for s in snapshots}
    occurrences={(o['job_id'],o['requirement']['requirement_id']):o for o in a.load_occurrences()}
    rows=[];contexts={}
    for case,e in zip(cases,parent['expectations']):
        if args.job_id is not None and case['job_id']!=args.job_id:continue
        if len(rows)>=args.limit:break
        key=(case['job_id'],case['requirement_id']);source=recover(case,by_job.get(case['job_id']));contexts[key]=source
        if source.get('native_requirement'):
            full=next(r for r in by_job[case['job_id']]['stable_analysis']['canonical_requirements'] if r['requirement_id']==case['requirement_id'])
            for field in ('atomic_group_id','structured_match_required_terms','structured_match_group_mode'):
                if field in full:source['native_requirement'][field]=full[field]
        mentions=handover.get('illustrative_not_gold',{}).get(str(parent['expectations'].index(e)+1),{}).get('mentioned_not_verified_in_registry_candidates',[])
        row=triage.build(occurrences[key],source,e['acceptable_routes'],mentions)
        triage.validate(row,occurrences[key],source,e['acceptable_routes']);rows.append(row)
    if not rows:raise ValueError('No matching frozen cases')
    triage.validate_batch(rows)
    if hashes!={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in protected}:raise ValueError('Protected input changed during report')
    db_after=hashlib.sha256(db.read_bytes()).hexdigest();records_verified=False
    if db_before!=db_after:
        # External writers may alter the file. Compare only the cited context
        # via the same read-only ownership API, never assert DB byte immutability.
        latest={s['discovered_job_id']:s for s in list_latest_job_match_corpus_snapshots(db_path=db)}
        for case in cases:
            key=(case['job_id'],case['requirement_id'])
            if key in contexts:
                check=recover(case,latest.get(case['job_id']))
                if check.get('native_requirement'):
                    full=next(r for r in latest[case['job_id']]['stable_analysis']['canonical_requirements'] if r['requirement_id']==case['requirement_id'])
                    for field in ('atomic_group_id','structured_match_required_terms','structured_match_group_mode'):
                        if field in full:check['native_requirement'][field]=full[field]
                if check!=contexts[key]:raise ValueError('Cited source changed during report; retry review')
        records_verified=True
    report={'schema_version':triage.SCHEMA,'rows':rows,'summary':{'cases':len(rows),
        'primary_proposals':dict(Counter(r['primary_route']['route'] for r in rows)),
        'inherited_gold_count':sum(r['primary_route']['status']=='INHERITED_CONTROL' for r in rows),
        'frozen_corpus_inherited_gold_count':2,'new_gold_labels':0,'scoring_children_created':0},
        'integrity':{'protected_hashes':hashes,'protected_inputs_unchanged':True,
            'handover_sha256':hashlib.sha256(args.handover.read_bytes()).hexdigest(),
            'v3_sha256':handover['based_on']['report_sha256'],'db_before_sha256':db_before,'db_after_sha256':db_after,
            'db_file_changed':db_before!=db_after,'cited_records_reverified_if_changed':records_verified,
            'database_access':'Existing snapshot API mode=ro'},
        'model_calls':0,'network_calls':0,'embedding_calls':0,'production_writes':0}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
    lines=['# Multidimensional unresolved triage V1','', 'Diagnostic proposals only. No gold imports, scoring children or production changes.','',
        '| Job / requirement | Primary proposal/status | Technologies | Activity/source | Structure | Human review | Remediation |', '|---|---|---|---|---|---|---|']
    for r in rows:
        cells=[f"{r['job_id']} / {r['requirement_id']}",r['primary_route'],r['technology_candidates'],r['activity'],r['structure']['type'],r['human_review']['status'],r['remediation_candidate']]
        lines.append('| '+' | '.join(str(v).replace('|','\\|').replace('\n',' ') for v in cells)+' |')
    lines+=['','Detailed source fingerprints, native structure and unchanged allocations are in the JSON report.','']
    output.with_suffix('.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(report['summary'],indent=2))


if __name__=='__main__':main()

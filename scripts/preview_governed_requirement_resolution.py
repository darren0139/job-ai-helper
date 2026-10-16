"""Offline native before/after preview on quarantined Job Finder development data."""
import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path

os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP','True')
os.environ.setdefault('CAPABILITY_RAG_MODE','off')
from scripts import cluster_unresolved_backlog_v1 as backlog
from scripts.investigate_existing_predicate_backlog_v2 import active_records
from taxonomy_discovery import governed_requirement_resolution as review
from taxonomy_discovery.offline_execution import offline_execution

ROOT=Path(__file__).resolve().parents[1]


def run(db):
    before=backlog.sha(db)
    manifest=json.loads((ROOT/'reports/unresolved_existing_predicate_investigation_v2_manifest.json').read_text(encoding='utf-8'))
    protected=backlog.protected_sources()
    jobs,snapshots,_,_=backlog.read_database(db)
    prior=json.loads((ROOT/'reports/unresolved_backlog_clustering_v1.json').read_text(encoding='utf-8'))
    limit=prior['source_inventory']['snapshot_rows_total']
    snapshots=[s for s in snapshots if s['id']<=limit]
    if len(snapshots)!=limit:raise ValueError('Original snapshot inventory missing; no cohort substitution')
    # Later analyses are excluded; prove every original source input is intact.
    _,_,apps,_=backlog.read_database(db)
    inventory=review.fingerprint({'jobs':[(j['id'],j['content_hash'],j['lifecycle_status'],backlog.sha_text(j.get('description') or '')) for j in jobs],
        'snapshots':[(s['id'],s['discovered_job_id'],s['job_content_hash'],backlog.sha_text(s.get('requirements_json') or '')) for s in snapshots],
        'applications':[(s['id'],s['application_id'],backlog.sha_text(s.get('requirements_json') or ''),backlog.sha_text(s.get('raw_jd_text') or '')) for s in apps]})
    selected=active_records(jobs,snapshots)
    original_active_inventory_matched=True
    if inventory!=prior['input_inventory_fingerprint']:
        baseline=backlog.analyze(selected,protected)
        if baseline!=prior['scopes']['active_same_hash']:
            raise ValueError('Original V1 active-snapshot inventory changed; no substitution')
    development=[];excluded=Counter()
    for record in selected:
        req=record['requirement']
        reason=backlog.quarantine_reason(req,record['job_id'],protected)
        if reason:excluded[reason]+=1;continue
        if backlog.unsafe_text(req.get('text') or '') or any(backlog.unsafe_text(p.get('raw_parent_text',''))
                for p in req.get('source_provenance',[]) if isinstance(p,dict)):
            excluded['privacy_sensitive_source']+=1;continue
        development.append(record)
    source=next(r for r in development if r['job_id']==146 and r['requirement']['requirement_id']=='req_9270e95898c8')
    proposal=review.propose(source['requirement'])
    validation=review.preview(proposal,explicit_execution=True)
    comparisons=review.compare_inputs([r['requirement'] for r in development],proposal)
    changes=[];newly_resolved=[];newly_unresolved=[]
    for record,comparison in zip(development,comparisons):
        if comparison['knowledge_changed']:
            change={'job_id':record['job_id'],'snapshot_id':record['snapshot_id'],**comparison}
            change['review_state']='VALIDATED_BOUNDED_API_SCOPE' if bounded(record['requirement']) and comparison['after']['capability_id']=='backend.api_development' else 'NEEDS_HUMAN_REVIEW'
            changes.append(change)
            if comparison['before']['status']=='unresolved' and comparison['after']['status']=='resolved':newly_resolved.append(change)
            if comparison['before']['status']=='resolved' and comparison['after']['status']=='unresolved':newly_unresolved.append(change)
    allowed={'tailoring/capability_taxonomy.py','tailoring/requirement_scope.py','tailoring/initial_analysis_explainer_ui.py',
        'tailoring/production_requirement_resolver.py','tailoring/phase6d_stable_scoring_adapter.py',
        'taxonomy_discovery/resolver_improvement.py','taxonomy_discovery/governed_research.py',
        'taxonomy_discovery/governed_publication.py','database/taxonomy_discovery_review_manager.py',
        'taxonomy_discovery/production_resolver_inspector_ui.py'}
    unexpected=[name for name,h in manifest['protected_hashes'].items() if name not in allowed and backlog.sha(ROOT/name)!=h]
    if unexpected:raise ValueError('Protected prior work changed: '+str(unexpected))
    if before!=backlog.sha(db):raise ValueError('Database changed during preview')
    body={'schema_version':review.VERSION,'proposal':proposal,'validation':validation,
        'scope':'Job Finder latest active same-content-hash snapshots only; application scope not added',
        'selected_canonical':len(selected),'development_canonical':len(development),
        'development_jobs':len({r['job_id'] for r in development}),
        'source_inventory_fingerprint':inventory,
        'original_global_inventory_fingerprint':prior['input_inventory_fingerprint'],
        'global_inventory_unchanged':inventory==prior['input_inventory_fingerprint'],
        'original_active_inventory_matched':original_active_inventory_matched,
        'source_cohort_fingerprint':review.fingerprint([{'job_id':r['job_id'],'snapshot_id':r['snapshot_id'],
            'input':review.requirement_input(r['requirement'])} for r in development]),
        'baseline_development_unresolved':sum(r['before']['status']=='unresolved' for r in comparisons),
        'candidate_development_unresolved':sum(r['after']['status']=='unresolved' for r in comparisons),
        'unchanged':len(development)-len(changes),'changed':changes,'newly_resolved':newly_resolved,
        'newly_unresolved':newly_unresolved,'distinct_jobs_affected':len({r['job_id'] for r in changes}),
        'unexpected_status_changes':[r for r in changes if r['review_state']=='NEEDS_HUMAN_REVIEW'],
        'quarantine_exclusions':dict(excluded),'database_sha256_before':before,'database_sha256_after':backlog.sha(db),
        'snapshots_unchanged':True,'protected_prior_files_checked':len(manifest['protected_hashes'])-len(allowed),
        'model_calls':0,'network_calls':0,'database_writes':0,'scoring_recalculations':0,
        'activation_performed':False,'approval_performed':False,
        'limitations':['Knowledge recognition only, not an evidence-match, score or ranking replay.',
            'Newly recognized bounded wording is a proposed policy, not independently reviewed human gold.',
            'Publication remains blocked by the existing governor contract; no saved analysis was rewritten.']}
    return {**body,'fingerprint':review.fingerprint(body)}


def bounded(row):return bool(review.bounded_api_development_scope(review.requirement_input(row)))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=ROOT/'data/applications.db')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/governed_requirement_resolution_v1_preview.json')
    args=parser.parse_args(argv)
    if args.output.exists():parser.error('Preserve existing preview report; no overwrite')
    with offline_execution('Governed requirement preview is offline'):report=run(args.db)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('development_canonical','development_jobs','baseline_development_unresolved',
        'candidate_development_unresolved','unchanged','distinct_jobs_affected','newly_resolved','newly_unresolved','unexpected_status_changes')},ensure_ascii=False))


if __name__=='__main__':main()

"""Read-only UI recovery over existing governed research and publication receipts."""
from pathlib import Path
import hashlib

from database import taxonomy_discovery_review_manager as store
from taxonomy_discovery import governed_publication as publication
from taxonomy_discovery import governed_requirement_resolution as review
from taxonomy_discovery.corpus_expansion import fingerprint


def _published(saved, inp, *, db_path=None):
    """Verify a completed release, not the old draft's pre-release currentness.

    Existing publication receipts remain the authority. A rule alone is never
    a publication receipt, and the publication writer is never invoked here.
    """
    from tailoring import capability_taxonomy as taxonomy
    result=saved['result'];draft=saved.get('draft') or {};decision=saved.get('review') or {}
    draft_fp=fingerprint(draft);rid=result['research_result_id']
    receipts=[r for r in publication.list_publications(db_path=db_path)
              if r.get('research_result_id')==rid or r.get('draft_fingerprint')==draft_fp
              or r.get('draft_id')==draft.get('resolver_draft_id') and draft.get('resolver_draft_id')]
    if not receipts:return None
    blockers=[]
    receipt=receipts[-1]
    from taxonomy_discovery.governed_research import _validate_saved_integrity
    try:
        # Currentness checks for an unpublished candidate intentionally reject
        # its own completed release. Reuse the saved-integrity validator only.
        _validate_saved_integrity(result)
    except (ValueError,KeyError,TypeError) as exc:blockers.append('Published source receipt invalid: '+str(exc))
    if len(receipts)!=1:blockers.append('Multiple publication receipts claim this draft/source')
    report=decision.get('regression') or {}
    expected={'publication_contract_version':publication.PUBLICATION_VERSION,'status':'published',
        'publication_id':'tqd3pub_'+draft_fp[:24],'kind':'resolver_improvement',
        'research_result_id':rid,'source_result_fingerprint':result.get('result_fingerprint'),
        'candidate_id':result.get('candidate',{}).get('candidate_id'),
        'candidate_fingerprint':result.get('candidate',{}).get('candidate_fingerprint'),
        'draft_id':draft.get('resolver_draft_id'),'draft_fingerprint':draft_fp,'idempotency_key':draft_fp,
        'regression_fingerprint':report.get('regression_fingerprint'),'review_id':fingerprint(decision),
        'reviewer':decision.get('reviewer'),'approval_timestamp':decision.get('updated_at')}
    for key,value in expected.items():
        if receipt.get(key)!=value or value is None:blockers.append('Publication receipt '+key+' mismatch')
    if decision.get('decision')!='approve_for_publication' or not decision.get('reviewer') or not receipt.get('publication_timestamp'):
        blockers.append('Original human approval/publication timestamp missing or invalid')
    if report.get('draft_fingerprint')!=draft_fp or report.get('regression_fingerprint')!=fingerprint(
            {k:v for k,v in report.items() if k!='regression_fingerprint'}):
        blockers.append('Published draft/regression fingerprint mismatch')
    if publication.latest_impact(rid,db_path=db_path)!=report:
        blockers.append('Saved regression differs from the publication approval')
    if result.get('candidate',{}).get('recognition_requirement')!=inp:
        blockers.append('Published source requirement input fingerprint changed')
    change={'capability_id':draft.get('target_capability_id'),
            'recognition_fallback_rules':[draft.get('proposed_resolver_change',{}).get('rule')]}
    if (draft.get('kind')!='resolver_improvement' or change['capability_id']!='backend.api_development'
            or change['recognition_fallback_rules']!=[review.API_RECOGNITION_FALLBACK]
            or receipt.get('change_applied')!=change):
        blockers.append('Published capability/rule identity mismatch')
    path=Path(taxonomy.TAXONOMY_PATH).resolve()
    path_matches=Path(receipt.get('production_artifact') or '').resolve()==path
    if not path_matches:
        blockers.append('Publication artifact path mismatch')
    actual_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash!=receipt.get('artifact_hash_after'):blockers.append('Publication artifact SHA-256 mismatch')
    native=taxonomy.get_default_taxonomy()
    if receipt.get('version_after')!=native.version or taxonomy.load_taxonomy(path).version!=native.version:
        blockers.append('Published/native taxonomy version mismatch')
    if receipt.get('version_before')!=report.get('current_versions',{}).get('taxonomy_version'):
        blockers.append('Publication baseline taxonomy version mismatch')
    try:
        if path_matches and not publication._present(receipt):blockers.append('Published native knowledge is not present')
    except (KeyError,ValueError,TypeError,OSError) as exc:blockers.append('Publication presence check failed: '+str(exc))
    resolved=review.resolve_requirement_with_production_knowledge(inp)
    if resolved['decision'].get('capability_id')!=change['capability_id']:
        blockers.append('Current native resolution does not select the published capability')
    if blockers:
        return {'status':'publication_mismatch','message':'Publication receipt/artifact mismatch — review required',
                'blockers':list(dict.fromkeys(blockers)),'publication':receipt,'review':decision,
                'native':review.summarize(resolved)}
    return {'status':'published','message':'Published — taxonomy '+native.version.rsplit('-',1)[-1]+' active',
            'publication':receipt,'approval':{'receipt':decision,'draft_fingerprint':draft_fp},
            'saved_governed':{'result':result,'draft':draft},'governed_regression':report,
            'native':review.summarize(resolved),'blockers':[],
            'readiness':{'ready':False,'published':True,'blockers':[],
                         'version_before':receipt['version_before'],'version_after':receipt['version_after']}}


def store_identity():
    """Cheap invalidation token for SQLite/WAL and exact native artifact bytes."""
    from tailoring import capability_taxonomy as taxonomy
    path=store._resolved_path()
    def stat(p):
        try:
            s=p.stat()
            return (s.st_mtime_ns,s.st_ctime_ns,s.st_size)
        except FileNotFoundError:return None
    artifact=Path(taxonomy.TAXONOMY_PATH).resolve()
    return (str(path),stat(path),stat(Path(str(path)+'-wal')),str(artifact),stat(artifact))


def _unapproved(saved, inp, *, db_path=None):
    """Read existing validation receipts, without replay or approval authority."""
    result=saved['result'];draft=saved.get('draft');decision=saved.get('review') or {}
    pending={'status':'pending','message':'Saved draft pending review; persisted approval could not be found.'}
    if not draft or decision.get('decision') not in (None,'undecided'):
        return {**pending,'message':'Saved review decision: '+str(decision.get('decision') or 'pending')+'. No active approval.'}
    report=publication.latest_impact(result['research_result_id'],db_path=db_path)
    if not report:return pending
    blockers=[]
    from taxonomy_discovery.governed_research import validate_result
    try:validate_result(result)
    except (ValueError,KeyError,TypeError) as exc:blockers.append(str(exc))
    if result.get('candidate',{}).get('recognition_requirement')!=inp:blockers.append('Saved validation source input changed')
    if report.get('draft_fingerprint')!=fingerprint(draft):blockers.append('Saved validation draft fingerprint changed')
    if report.get('regression_fingerprint')!=fingerprint({k:v for k,v in report.items() if k!='regression_fingerprint'}):
        blockers.append('Saved validation regression fingerprint changed')
    if report.get('current_versions')!=review.current_match_versions() or report.get('knowledge_fingerprint')!=review.knowledge_fingerprint():
        blockers.append('Saved validation native knowledge/scoring identity changed')
    controls=report.get('recognition_policy_controls') or {}
    jobs=report.get('jobs') or []
    if (report.get('review_only') is not True or not report.get('corpus_fingerprint') or not jobs
            or report.get('publication_blockers')!=[] or report.get('unexpectedly_changed_requirements')!=[]
            or any(j.get('available') is not True or j.get('duplicate_credit_violations')!=[]
                   or j.get('classification')=='hard_regression/invariant_violation' for j in jobs)
            or controls.get('validation_passed') is not True or not controls.get('controls_fingerprint')):
        blockers.append('Saved validation receipt is incomplete or blocked')
    if blockers:return {'status':'stale','message':'Saved validation requires revalidation','blockers':blockers}
    return {'status':'validated','message':'Validated draft — awaiting human approval; persisted approval could not be found.',
            'saved_governed':{'result':result,'draft':draft},'governed_regression':report}


def recover(row, identity, *, db_path=None):
    """Require exact source/input linkage, then defer authority to the governor.

    No draft construction, score replay, schema initialization or writes.
    A stale approval is diagnostic history, never an actionable approval.
    """
    inp=review.requirement_input(row)
    keys={'job_id':identity.get('discovered_job_id'),'snapshot_id':identity.get('id'),
          'requirement_id':inp.get('requirement_id'),'job_content_hash':identity.get('job_content_hash')}
    missing={'status':'missing','message':'Persisted approval could not be found for this exact source.'}
    if not all(keys.values()):
        return {**missing,'message':'Persisted approval could not be found: exact job, snapshot, requirement and source hash are required.'}
    matches=[]
    for saved in store.list_governed_research_results(db_path=db_path):
        result=saved['result']
        if any(all(p.get(k)==v for k,v in keys.items()) for p in result.get('source_gap_provenance',[])):
            matches.append(saved)
    if not matches:return missing
    # Do not revive an older approval over a more recent decision for this source.
    matches.sort(key=lambda x:(x.get('review',{}).get('updated_at',''),x['result'].get('research_result_id','')),reverse=True)
    saved=matches[0];decision=saved.get('review') or {};draft=saved.get('draft')
    published=_published(saved,inp,db_path=db_path)
    if published:return published
    if decision.get('decision')!='approve_for_publication':return _unapproved(saved,inp,db_path=db_path)
    result=saved['result'];rid=result['research_result_id']
    readiness=publication.prepare_publication(rid,db_path=db_path)
    blockers=list(readiness.get('blockers',[]))
    expected=result.get('candidate',{}).get('recognition_requirement')
    if expected!=inp:
        blockers.append('Source requirement input fingerprint changed: saved '+fingerprint(expected)+'; current '+fingerprint(inp))
    regression=decision.get('regression') or {}
    if draft and regression.get('draft_fingerprint')!=fingerprint(draft):
        blockers.append('Draft fingerprint changed: approved '+str(regression.get('draft_fingerprint'))+'; saved '+fingerprint(draft))
    if regression.get('current_versions')!=review.current_match_versions():
        blockers.append('Native versions changed: saved '+str(regression.get('current_versions'))+'; current '+str(review.current_match_versions()))
    if regression.get('knowledge_fingerprint')!=review.knowledge_fingerprint():
        blockers.append('Knowledge fingerprint changed: saved '+str(regression.get('knowledge_fingerprint'))+'; current '+review.knowledge_fingerprint())
    if blockers or not readiness.get('ready'):
        return {'status':'stale','message':'Previously approved — requires revalidation',
                'blockers':list(dict.fromkeys(blockers)),'review':decision,'draft':draft,
                'readiness':{**readiness,'ready':False,'blockers':list(dict.fromkeys(blockers))}}
    return {'status':'ready','message':'Validated → Approved → Ready for publication',
            'saved_governed':{'result':result,'draft':draft},'governed_regression':regression,
            'approval':{'receipt':decision,'draft_fingerprint':regression['draft_fingerprint']},
            'readiness':readiness}

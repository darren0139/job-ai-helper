"""Explicit experimental recovery of one already-approved bounded quality proxy.

No published scorer/threshold changes, taxonomy additions or UI activation.
This separate diagnostic identity is never admissible as v1.17 or v1.21.
"""
from copy import deepcopy
import re

from job_discovery import coordinated_preview as preview, developer_comparison as gate
from job_discovery.coordinated_sources import fingerprint, verified_projection_ledger
from job_discovery.coordinated_preview_model import analysis_view
from tailoring.capability_taxonomy import evaluate_capability_evidence,normalise

SCORING_VERSION='stable-evidence-v1.24-phase6d28'
POLICY_VERSION='owned-quality-proxy-semantic-recovery-v1'
NAMESPACE='developer-evidence-relevance-v1'
CAPABILITY='quality.attention_detail'
REASON='deterministic_quality_proxy_capped_at_weak'
GOALS={'pipeline consistency','row level security','rls','data integrity','access control'}
UNCERTAIN=re.compile(r'\b(?:not|never|no|without|planned|planning|proposed|would|could|will|may|might|tutorial|course|example|hypothetical|colleague|colleagues|vendor|they|their|others|another|someone)\b',re.I)
THIRD_PARTY=re.compile(r'\b(?:team|teammates|team members)\s+(?:implemented|applied|enforced|verified|validated|improved)\b',re.I)
ACTIVITY=re.compile(r'\b(?:implemented|applied|enforced|verified|validated|improved|improving|ensured|ensuring)\b')
TRAIT=re.compile(r'(?:(?:good|strong|excellent|high) )?attention to detail(?: and quality)?(?: is (?:a )?(?:desired|required|preferred) attribute)?')


def _key(record):
    return tuple(record.get(k) for k in ('source','section','text','evidence_id'))


def _goals(text):
    words=' '+normalise(text)+' '
    return {g for g in GOALS if ' '+g+' ' in words}


def _activity(text):
    if UNCERTAIN.search(text) or THIRD_PARTY.search(text): return set()
    goals=set()
    for clause in re.split(r'[.;!?\n]',text):
        clause=normalise(clause)
        for action in ACTIVITY.finditer(clause):
            tail=clause[action.end():].strip()
            # The quality goal must be this action's immediate object. An
            # unrelated implementation verb cannot borrow a later noun phrase.
            goals.update(g for g in GOALS if re.match(r'(?:the )?'+re.escape(g)+r'\b',tail))
    return goals


def _trait_requirement(row):
    if not TRAIT.fullmatch(normalise(row.get('atomic_focus') or row.get('text',''))): return False
    parents=[s.get('raw_parent_text') or s.get('parent_text') for s in row.get('source_provenance',[])
             if s.get('contributes_scoring_allocation',True)]
    return bool(parents) and all(p and TRAIT.fullmatch(normalise(p)) for p in parents)


def evaluate(request, *, session_enabled=False, baseline=None):
    """Explicit developer action only; returned preview has no persistence route."""
    if not gate.enabled() or session_enabled is not True:
        raise ValueError('Evidence relevance preview is OFF')
    baseline=baseline or preview.run_comparison(request,developer_enabled=True)
    preview.retained_comparison(baseline,request)
    if (baseline.published.scoring_version!=preview.native.SCORING_VERSION or
            baseline.gated.scoring_version!=preview.PROJECTED_SCORER_VERSION or
            baseline.authority!=request.projection['authority'] or
            analysis_view(baseline.published_analysis)!=baseline.published or
            analysis_view(baseline.gated_analysis)!=baseline.gated):
        raise ValueError('Current base comparison contract required')
    context=request.projection['context']
    ledger=verified_projection_ledger(request.projection,context['resume_profile'],context['raw_resume_text'])
    index=preview.native.build_resume_evidence_index(context['resume_profile'],context['raw_resume_text'])
    out=deepcopy(baseline.gated_analysis); changes=[]
    occurrence_map={_key(r):r for r in ledger['occurrences']}
    taxonomy=preview.native.get_default_taxonomy()
    # Bind the finite activity predicate to the existing approved WEAK concept set.
    approved=next(t for t in taxonomy.by_id()[CAPABILITY]['evidence_tiers'] if t['reason']==REASON)
    if not GOALS<=set(approved['any_terms']): raise ValueError('Quality proxy contract changed')
    for row in out['canonical_requirements']:
        if (row.get('match_label')!='none' or row.get('evidence') or row.get('coordinated_action_receipt')
                or row.get('capability_id')!=CAPABILITY or row.get('capability_resolution_source')!='canonical_taxonomy'
                or row.get('capability_taxonomy_cap_status')!='not_needed' or not _trait_requirement(row)
                or request.projection['raw_only_text'].strip()):
            continue
        for record in index:
            if record.get('section') not in ('projects','experience') or not re.search(r'\.bullets\[\d+\]$',record.get('source','')):
                continue
            if not preview.native._evidence_source_is_requirement_compatible(row,record): continue
            original=occurrence_map.get(_key(record))
            owners={o['library_item_id'] for o in (original or {}).get('library_origins',[])}
            if len(owners)!=1 or not original.get('container'): continue
            goals=_activity(record['text'])
            if not goals: continue
            # Negative/uncertain statements cannot be combined away by choosing a
            # positive bullet. Other records supply vetoes only, never support.
            if any(r.get('container')==original['container'] and
                   (UNCERTAIN.search(r['text']) or THIRD_PARTY.search(r['text'])) and
                   (_goals(r['text']) & goals or 'attention to detail' in normalise(r['text']))
                   for r in ledger['occurrences']):
                continue
            decision=evaluate_capability_evidence(CAPABILITY,row,record['text'],taxonomy)
            if decision.get('label')!='weak' or decision.get('reason')!=REASON: continue
            reference={**deepcopy(record),'reason':'One original authored technical quality activity supports only the existing WEAK quality proxy.'}
            row.update(match_label='weak',match_value=preview.native.MATCH_VALUES['weak'],evidence_strength=2,
                evidence=[reference],match_source='experimental_owned_quality_proxy')
            receipt={'policy_version':POLICY_VERSION,'capability_id':CAPABILITY,'existing_taxonomy_reason':REASON,
                'ceiling':'weak','library_item_id':next(iter(owners)),
                'source_reference':fingerprint(_key(record)),
                'original_occurrence_references':sorted(fingerprint(o['occurrence_id']) for o in original['library_origins']),
                'goals':sorted(goals),'combined_support_records':False,'baseline_label':'none'}
            row['experimental_relevance_receipt']=receipt
            changes.append({'requirement_id':row['requirement_id'],'before':'NONE','after':'WEAK',**receipt})
            break  # exactly one independently sufficient original record
    geometry=lambda a:[tuple(r.get(k) for k in ('requirement_id','text','importance','atomic_group_id','group_weight_fraction')) for r in a['canonical_requirements']]
    if geometry(out)!=geometry(baseline.gated_analysis): raise ValueError('Requirement geometry changed')
    out.update(preview.native.compute_deterministic_alignment(out['canonical_requirements'],
        bullet_quality_score=out.get('bullet_quality_component',0),structure_score=out.get('structure_component',0)))
    out.update(scoring_version=SCORING_VERSION,experimental_evidence_relevance_policy_version=POLICY_VERSION,
        base_scoring_version=preview.PROJECTED_SCORER_VERSION,development_preview_only=True,preview_namespace=NAMESPACE,
        input_fingerprint=fingerprint({'request':request.identity,'base':baseline.gated_analysis['input_fingerprint'],
            'policy':POLICY_VERSION,'version':SCORING_VERSION,'changes':changes}))
    return {'identity':request.identity,'baseline':baseline,'experimental_analysis':out,
        'experimental_view':analysis_view(out),'changes':changes,'policy_version':POLICY_VERSION,
        'development_preview_only':True,'persistence_eligible':False,'promotion_approved':False}


def evaluate_eligible_recovery(request, *, session_enabled=False, baseline=None):
    """Explicit v1.25 comparison; shared native pipeline, no alternate matcher.

    Reuses v1.24's verified original-record quality correction. Eligibility-first
    selection is restricted to fallback WEAK candidates without a capability.
    Unexpected positive changes fail closed rather than redefining a credit rule.
    """
    from analysis_stability.coordinated_runtime import (
        ELIGIBLE_WEAK_FALLBACK, ELIGIBLE_WEAK_SCORER, ELIGIBLE_WEAK_POLICY,
    )
    prior = evaluate(request, session_enabled=session_enabled, baseline=baseline)
    baseline = prior['baseline']
    context = request.projection['context']
    token = ELIGIBLE_WEAK_FALLBACK.set(True)
    try:
        out = preview.gated.build_coordinated_analysis(
            source_projection=request.projection, jd_profile=deepcopy(request.jd_profile),
            keyword_match={}, raw_jd_text=request.raw_jd_text,
            resume_profile=deepcopy(context['resume_profile']),
            raw_resume_text=context['raw_resume_text'], retrieval_mode_override='off')
    finally:
        ELIGIBLE_WEAK_FALLBACK.reset(token)
    before = baseline.gated_analysis['canonical_requirements']
    rows = out['canonical_requirements']
    ledger = verified_projection_ledger(request.projection, context['resume_profile'], context['raw_resume_text'])
    originals = {_key(r):r for r in ledger['occurrences']}
    geometry = lambda rs: [{k:r.get(k) for k in ('requirement_id','text','importance',
        'source_provenance','atomic_group_id','group_weight_fraction')} for r in rs]
    if geometry(before) != geometry(rows):
        raise ValueError('Eligible fallback changed requirement geometry')
    changes = []
    for old, row in zip(before, rows):
        if row['match_label'] != old['match_label'] or row.get('evidence') != old.get('evidence'):
            if (old['match_label'] != 'none' or row['match_label'] != 'weak'
                    or row.get('capability_id') or row.get('coordinated_action_receipt')
                    or len(row.get('evidence', [])) != 1):
                raise ValueError('Eligible fallback exceeded the existing WEAK recovery contract')
            selected = row['evidence'][0]
            original = originals.get(_key(selected), {})
            owners = {o['library_item_id'] for o in original.get('library_origins', [])}
            if len(owners) != 1:
                raise ValueError('Eligible fallback lacks one verified original evidence owner')
            row['eligible_weak_fallback_receipt'] = {
                'policy_version': ELIGIBLE_WEAK_POLICY, 'before': 'NONE', 'after': 'WEAK',
                'source_reference': fingerprint(_key(selected)), 'combined_support_records': False,
                'library_item_id': next(iter(owners)),
                'original_occurrence_references': sorted(fingerprint(o['occurrence_id']) for o in original['library_origins']),
                'existing_thresholds_unchanged': True, 'canonical_identity_inferred': False}
            changes.append({'requirement_id': row['requirement_id'], **row['eligible_weak_fallback_receipt']})
    # Carry only the independently validated v1.24 correction, with its own
    # original-record receipt. It cannot replace a new result or a quarantine.
    prior_rows = {r['requirement_id']:r for r in prior['experimental_analysis']['canonical_requirements']}
    for index, row in enumerate(rows):
        inherited = prior_rows[row['requirement_id']]
        if inherited.get('experimental_relevance_receipt') and row['match_label'] == 'none':
            rows[index] = deepcopy(inherited)
    out.update(preview.native.compute_deterministic_alignment(rows,
        bullet_quality_score=out.get('bullet_quality_component',0),
        structure_score=out.get('structure_component',0)))
    out['input_fingerprint'] = fingerprint({'native':out['input_fingerprint'],
        'request':request.identity, 'inherited_policy':POLICY_VERSION, 'changes':changes,
        'inherited_changes':prior['changes']})
    return {'identity':request.identity,'baseline':baseline,'experimental_analysis':out,
        'experimental_view':analysis_view(out),'changes':changes,
        'inherited_changes':prior['changes'],'policy_version':ELIGIBLE_WEAK_POLICY,
        'scoring_version':ELIGIBLE_WEAK_SCORER,'development_preview_only':True,
        'persistence_eligible':False,'promotion_approved':False}

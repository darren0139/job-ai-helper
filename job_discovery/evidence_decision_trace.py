"""Read-only projections of retained native receipts; never re-match candidates."""
from copy import deepcopy
import math

from job_discovery import coordinated_preview as preview
from job_discovery.coordinated_sources import fingerprint, verified_projection_ledger
from job_discovery.coordinated_preview_model import analysis_view

SCHEMA = 'evidence-decision-trace-v1'
UNKNOWN = 'NOT_OBSERVABLE'
MAX_PAIRS = 20000
REVIEW_CATEGORIES = ('Insufficient trace to determine', 'Correct NONE',
    'Possible candidate-selection miss', 'Possible capability-resolution miss',
    'Possibly restrictive threshold or ceiling', 'Correct policy rejection', 'Potential reviewer disagreement')
WARNING_CODES = {'subjective_requirement_requires_explicit_evidence','positive_match_not_found_in_resume_profile',
    'qualified_evidence_capped','atomic_clause_promoted','partial_phrase_not_atomic_proof',
    'low_evidence_overlap_capped','insufficient_atomic_coverage','insufficient_weak_evidence_context',
    'explicit_subjective_evidence_found','deterministic_weak_fallback','duplicate_requirement_id',
    'invalid_match_label','missing_evidence','taxonomy_cap_applied'}


def recovery_identity_reference(raw):
    """A native precondition reference from final fields, never an attempt log."""
    if raw.get('coordinated_action_receipt') or raw.get('match_label')!='none': return UNKNOWN
    if not raw.get('capability_id') or raw.get('capability_resolution_source')!='canonical_taxonomy':
        return 'FINAL_FIELDS_FAIL_NATIVE_RECOVERY_IDENTITY_PRECONDITION'
    return 'IDENTITY_PRECONDITION_MET_OTHER_ELIGIBILITY_AND_ATTEMPTS_NOT_ESTABLISHED'


class TraceBounded(ValueError):
    """A bounded trace can be unavailable without disabling existing exports."""


def _key(record):
    return tuple(record.get(k) for k in ('source', 'section', 'text', 'evidence_id'))


def _number(value):
    return value if type(value) in (int,float) and math.isfinite(value) else None


def _code(value):
    # Native reason strings are not safe enums. Preserve their identities only.
    return fingerprint(value) if value is not None else None


def _audit(raw, key):
    receipt = raw.get(key)
    if not receipt or receipt.get('status') not in {'recovered_from_none','stronger_single_row_selected'}:
        return {'attempted': UNKNOWN, 'status': UNKNOWN, 'selected_reference': None,
                'coverage': None, 'overlap': None, 'reason_fingerprint': None}
    statuses = {'recovered_from_none','stronger_single_row_selected'}
    return {'attempted': True, 'status':receipt.get('status') if receipt.get('status') in statuses else UNKNOWN,
        'selected_reference':fingerprint([receipt.get('selected_evidence_source'),receipt.get('selected_evidence_id')]),
        'coverage':_number(receipt.get('selected_requirement_coverage')),
        'overlap':_number(receipt.get('selected_requirement_overlap_count')),
        'reason_fingerprint':_code(receipt.get('taxonomy_reason'))}


def build(request, comparison):
    """Accept only a current retained comparison and replay-verified originals.

    Rebuilds source indexing only. No selector, taxonomy evaluator, scorer, DB,
    model, retrieval or network calls. No caller-owned object is mutated.
    """
    from job_discovery import developer_debug_export as safe
    from analysis_stability import coordinated_conflicts as conflicts
    preview.retained_comparison(comparison,request)
    if (comparison.authority!=request.projection['authority'] or
            comparison.published.scoring_version!=preview.native.SCORING_VERSION or
            comparison.gated.scoring_version!=preview.PROJECTED_SCORER_VERSION):
        raise ValueError('Trace authority or scorer identity differs')
    if (analysis_view(comparison.published_analysis)!=comparison.published or
            analysis_view(comparison.gated_analysis)!=comparison.gated):
        raise ValueError('Trace receipt identity differs')
    projection=request.projection; context=projection['context']
    ledger=verified_projection_ledger(projection,context['resume_profile'],context['raw_resume_text'])
    index=preview.native.build_resume_evidence_index(context['resume_profile'],context['raw_resume_text'])
    ledger=conflicts.attach_index_coverage(ledger,index)
    items=sorted(r['id'] for r in projection['evidence_items'])
    maps=[{r['requirement_id']:r for r in a['canonical_requirements']}
          for a in (comparison.published_analysis,comparison.gated_analysis)]
    ids=sorted(set(maps[0])|set(maps[1]))
    if len(ids)*len(items)*2>MAX_PAIRS:
        raise TraceBounded('Trace exceeds bounded requirement/record pairs')
    # Index rows are not ownership proofs. Map by exact verified occurrence only.
    origins={}
    for occurrence in ledger['occurrences']:
        if occurrence['index_status']=='INDEXED_ORIGINAL':
            origins.setdefault(_key(occurrence),[]).extend(occurrence.get('library_origins',[]))
    by_item={i:[r for r in projection['originals'] if r['library_item_id']==i] for i in items}
    indexed={i:set() for i in items}
    for key,records in origins.items():
        for r in records:
            indexed[r['library_item_id']].add(r['occurrence_id'])
    output=[]; matrix=[]
    known_capabilities=set(preview.native.get_default_taxonomy().by_id())
    for rid in ids:
        sides={}
        for side,raw,analysis in zip(('published','experimental'),(m.get(rid) for m in maps),
                                    (comparison.published_analysis,comparison.gated_analysis)):
            if raw is None:
                sides[side]={'status':'ABSENT_REQUIREMENT_GEOMETRY'}; continue
            receipt=raw.get('coordinated_action_receipt') or {}
            recovery=_audit(raw,'capability_none_recovery')
            reselection=_audit(raw,'capability_evidence_reselection')
            selected=raw.get('evidence') or []  # quarantined positive is NOT accepted
            selected_keys={_key(e) for e in selected}
            selected_items=set(); unresolved_selected=[]
            for key in selected_keys:
                owners={r['library_item_id'] for r in origins.get(key,[])}
                if len(owners)==1: selected_items.update(owners)
                else: unresolved_selected.append(fingerprint(key))
            pairs=[]
            for item_id in items:
                originals=by_item[item_id]; original_ids={r['occurrence_id'] for r in originals}
                events=[]; proofs=[]
                for event in receipt.get('compatibility_events',[]):
                    # Events retain source+ID only; do not disambiguate by ID alone.
                    keys=[k for k in origins if k[0]==event.get('source') and k[3]==event.get('evidence_id')]
                    owners={r['library_item_id'] for k in keys for r in origins[k]}
                    if owners=={item_id}:
                        events.append({'stage':safe._enum(event.get('stage'),{'keyword_selection','link_selection',
                            'single_row_reselection','none_recovery','linked','structured','validated_lexical_cap',
                            'reselected','capability_capped','recovered','post_recovery_invariant'}),
                            'admitted':event.get('admitted') is True})
                for proof in receipt.get('proofs',{}).values():
                    owners={r['library_item_id'] for r in origins.get(_key(proof['record']),[])}
                    if owners!={item_id}: continue
                    p=proof.get('proof') or {}
                    proofs.append({'reference_fingerprint':fingerprint(_key(proof['record'])),
                        'admission':safe._enum(proof.get('admission'),{'COMPLETE','ELIGIBLE_PARTIAL','REVIEW_REQUIRED'}),
                        'supported_action_count':len(p.get('supported_actions',[])),
                        'missing_action_count':len(p.get('missing_actions',[])),
                        'technical_scope_fingerprint':fingerprint(p.get('technical_scope'))})
                statuses=['SOURCE_AVAILABLE']
                if not indexed[item_id]: statuses.append('SOURCE_NOT_INDEXED')
                if not any(r.get('structured_source') for r in originals):
                    # raw aliases hold origins, so check their exact occurrence IDs.
                    emitted=any(original_ids & {o['occurrence_id'] for o in a['origins']} for a in projection['raw_aliases'])
                    if not emitted: statuses.append('SOURCE_NOT_PROJECTED')
                if events: statuses.append('CANDIDATE_CONSIDERED')
                if any(not e['admitted'] for e in events): statuses.append('NATIVE_COMPATIBILITY_FILTER_REJECTED')
                if item_id in selected_items: statuses.append('EVIDENCE_ACCEPTED')
                if any(p['missing_action_count']>0 for p in proofs): statuses.append('ACTION_PROOF_INCOMPLETE')
                if any(p['admission']=='REVIEW_REQUIRED' for p in proofs): statuses.append('ADMISSION_REVIEW_REQUIRED')
                if proofs: statuses.append('ACTION_PROOF_EVALUATED')
                for name,audit in (('RECOVERY_ATTEMPTED',recovery),('RESELECTION_ATTEMPTED',reselection)):
                    matching=[k for k in origins if fingerprint([k[0],k[3]])==audit['selected_reference']]
                    owners={r['library_item_id'] for k in matching for r in origins[k]}
                    if audit['attempted'] is True and owners=={item_id}: statuses.append(name)
                if not events and item_id not in selected_items: statuses.append(UNKNOWN)
                pair={'requirement_id':safe._id(rid),'side':side,'library_item_id':item_id,
                    'source_reference':fingerprint(['library-item',item_id,originals]),
                    'original_occurrence_count':len(originals),'indexed_original_occurrences':len(indexed[item_id]),
                    'original_occurrence_references':[fingerprint(r['occurrence_id']) for r in originals],
                    'statuses':statuses,'accepted':True if item_id in selected_items else None if unresolved_selected else False,
                    'considered':True if events or item_id in selected_items else UNKNOWN,
                    'rejected':True if any(not e['admitted'] for e in events) else UNKNOWN,
                    'not_selected_finally':False if item_id in selected_items else None if unresolved_selected else True,
                    'events':events,'action_proofs':proofs,'evaluated_threshold':None,'candidate_score':None}
                pairs.append(pair)
                matrix.append({k:pair[k] for k in ('requirement_id','side','library_item_id','source_reference',
                    'original_occurrence_count','indexed_original_occurrences','accepted','considered','rejected','not_selected_finally')}
                    | {'stage_statuses':'|'.join(statuses)})
            cap=raw.get('capability_taxonomy_cap_status')
            sides[side]={'status':'PARTIAL','importance':safe._importance(raw.get('importance')),
                'parent_id':safe._id(raw.get('atomic_group_id')),'allocation':raw.get('group_weight_fraction'),
                'label':safe._enum(str(raw.get('match_label')).upper(),{'DIRECT','TRANSFERABLE','WEAK','NONE','REVIEW_REQUIRED'})
                    if raw.get('match_label') is not None else 'REVIEW_REQUIRED',
                'credit':next(r.contribution for r in (comparison.published if side=='published' else comparison.gated).requirements if r.requirement_id==rid),
                'original_records':len(items),'projected_records':sum(any(r.get('structured_source') for r in by_item[i])
                    or any(o['library_item_id']==i for a in projection['raw_aliases'] for o in a['origins']) for i in items),
                'indexed_records':sum(bool(indexed[i]) for i in items),
                'observably_considered_records':sum(p['considered'] is True for p in pairs),
                'considered_total':UNKNOWN,'admitted_records':None if unresolved_selected else len(selected_items),
                'attributed_admitted_records':len(selected_items),
                'observably_filter_rejected_records':sum(p['rejected'] is True for p in pairs),
                'rejected_total':UNKNOWN,'not_evaluated_total':UNKNOWN,
                'not_selected_records':None if unresolved_selected else sum(p['not_selected_finally'] is True for p in pairs),
                'unattributed_selected_references':unresolved_selected,
                'recovery':recovery,'reselection':reselection,
                'recovery_identity_reference':recovery_identity_reference(raw),
                'retained_native_warning_codes':[safe._enum(w.get('code'),WARNING_CODES)
                    for w in analysis.get('validation_warnings',[]) if w.get('requirement_id')==rid],
                'native_link_source':safe._enum(raw.get('match_source'),{'present','missing','unmatched',
                    'explicit_resume_evidence','capability_none_recovery'}),
                'capability_identity_fingerprint':_code(raw.get('capability_id')),
                'capability_id':safe._enum(raw.get('capability_id'),known_capabilities),
                'capability_resolution':safe._enum(raw.get('capability_resolution_source'),{'canonical_taxonomy','technology_registry','unresolved'}),
                'taxonomy_ceiling':safe._enum(cap,{'applied','not_needed','unrecognised','disabled','not_applicable_structured_any_language_group'}),
                'native_reason_code': 'CAPABILITY_CEILING' if cap=='applied' else
                    'NATIVE_FINAL_REFERENCE_ACCEPTED' if selected else 'NO_ACCEPTED_REFERENCE_REASON_NOT_RETAINED',
                'native_reason_fingerprint':_code(raw.get('match_reason')),
                'observed_final_row_metrics':{k:_number(raw.get(k)) for k in ('match_similarity','match_coverage','match_overlap_count')},
                'metric_role':'RETAINED_KEYWORD_LINK_VALUES_NOT_CANDIDATE_SCORES',
                'disposition':safe._enum(receipt.get('disposition','PUBLISHED_NUMERIC'),safe.DISPOSITIONS),
                'contradiction_quarantined':bool((receipt.get('scoped_conflict') or {}).get('quarantine')),
                'native_receipt_fingerprint':fingerprint(raw),'records':pairs}
        output.append({'requirement_id':safe._id(rid),'sides':sides})
    return {'schema_version':SCHEMA,'input_identity':request.identity,'authority':request.projection['authority'],
        'projection_fingerprint':fingerprint(projection),'implementation_identity':preview.source_revision(),
        'source_text_included':False,'requirements':output,'matrix':matrix,
        'analysis_summary':{side:{k:v for k,v in view.summary().items() if k!='rating_band'}
            for side,view in (('published',comparison.published),('experimental',comparison.gated))},
        'geometry_comparable':not any(r['Geometry difference'] for r in safe.review_rows(comparison)),
        'credit_role':'STANDALONE_NATIVE_CONTRIBUTIONS_NOT_CROSS_GEOMETRY_DELTAS',
        'coverage':{'status':'PARTIAL','requirements':len(ids),'original_records':len(items),
            'pairs':len(matrix),'unknown_consideration_pairs':sum(p['considered']==UNKNOWN for p in matrix),
            'exhaustive_rejections_available':False,'native_matching_rerun':False},
        'configured_threshold_reference':{'role':'CONFIGURED_ONLY_NOT_PROOF_OF_EVALUATION',
            'identifier':'_deterministic_weak_evidence_is_sufficient',
            'score':preview.native._DETERMINISTIC_WEAK_MIN_SCORE,
            'coverage':preview.native._DETERMINISTIC_WEAK_MIN_COVERAGE,
            'overlap':preview.native._DETERMINISTIC_WEAK_MIN_OVERLAP}}


def private_pair(request, comparison, requirement_id, item_id, *, consent=False):
    """Separate explicit original-candidate excerpt, never automatically all records."""
    if consent is not True: raise ValueError('Separate original-candidate privacy consent required')
    trace=build(request,comparison)
    if not any(r['requirement_id']==requirement_id for r in trace['requirements']):
        raise ValueError('Unknown requirement')
    item=next((i for i in request.projection['evidence_items'] if i['id']==item_id),None)
    if item is None: raise ValueError('Unknown original record')
    rows=[r for r in trace['matrix'] if r['requirement_id']==requirement_id and r['library_item_id']==item_id]
    return {'privacy':'PRIVATE_UNREDACTED_ORIGINAL_CANDIDATE_NOT_ASSERTED_ACCEPTED_OR_REJECTED',
        'input_identity':request.identity,'requirement_id':requirement_id,'library_item_id':item_id,
        'accepted_sides':[r['side'] for r in rows if r['accepted']],
        'original_excerpts':[r['original_text'][:2000] for r in request.projection['originals'] if r['library_item_id']==item_id],
        'requirement_excerpts':[r.text[:2000] for v in (comparison.published,comparison.gated)
                                for r in v.requirements if r.requirement_id==requirement_id]}

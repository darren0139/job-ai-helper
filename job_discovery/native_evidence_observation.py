"""Bounded, explicit current-thread observation of actual native decisions.

No replaced functions, altered locals, replayed hypothetical decisions or UI.
Observation runs the existing comparison once and restores the caller's trace.
"""
import inspect
import math
import sys

from job_discovery import coordinated_preview as preview, developer_comparison as gate
from job_discovery.coordinated_sources import fingerprint, verified_projection_ledger
from tailoring import capability_taxonomy as taxonomy

VERSION='native-evidence-observation-v1'
MAX_EVENTS=20000


def _line(function, marker, *, following_continue=False):
    lines,start=inspect.getsourcelines(function)
    matches=[i for i,line in enumerate(lines) if line.strip().startswith(marker)]
    if len(matches)!=1: raise ValueError('Native observation point changed')
    index=matches[0]
    if following_continue:
        index+=1
        if lines[index].strip()!='continue': raise ValueError('Native rejection point changed')
    return start+index


def observe(request, *, session_enabled=False):
    if not gate.enabled() or session_enabled is not True:
        raise ValueError('Native observation requires explicit developer consent')
    if sys.gettrace() is not None:
        raise ValueError('Native observation cannot replace an active debugger/coverage trace')
    n=preview.native
    comparison_line=_line(n._best_resume_evidence,'if score > best_score:')
    rejection_line=_line(n._apply_capability_none_recovery,'if recovered_label == "weak"',following_continue=True)
    watched={f.__code__:f.__name__ for f in (n._best_resume_evidence,
        n._deterministic_weak_evidence_is_sufficient,n._evidence_source_is_requirement_compatible,
        n._apply_capability_none_recovery,taxonomy._evaluate_capability_record)}
    events=[]; dropped=0; errors=0

    def emit(frame,kind,requirement,record,metrics=None,decision=None):
        nonlocal dropped
        if not isinstance(requirement,dict) or not requirement.get('requirement_id'): return
        if len(events)>=MAX_EVENTS: dropped+=1; return
        parent=frame; side='published'
        while parent:
            if parent.f_code is preview.gated.build_coordinated_analysis.__code__: side='experimental'; break
            parent=parent.f_back
        reference=(fingerprint(tuple(record.get(k) for k in ('source','section','text','evidence_id')))
                   if isinstance(record,dict) else None)
        event={'side':side,'requirement_id':requirement['requirement_id'],'event':kind,
            'native_function':watched[frame.f_code],'record_reference':reference,
            'metrics':{k:v for k,v in (metrics or {}).items() if type(v) in (int,float,bool) and math.isfinite(v)}}
        if decision is not None:
            event['taxonomy_label']=decision.get('label') if decision.get('label') in ('none','weak','transferable','direct') else None
            reason=decision.get('reason')
            event['taxonomy_reason_fingerprint']=fingerprint(reason)
            event['taxonomy_reason_code']=reason if reason in ('deterministic_quality_proxy_capped_at_weak',
                'explicit_attention_to_detail','explicit_negative_evidence') else 'OTHER_NATIVE_REASON'
        events.append(event)

    def local(frame,event,arg):
        nonlocal errors
        try:
            values=frame.f_locals; name=watched[frame.f_code]
            if name=='_best_resume_evidence' and event=='line' and frame.f_lineno==comparison_line:
                emit(frame,'CANDIDATE_COMPARED',values['requirement'],values['row'],
                     {k:values[k] for k in ('score','focus_coverage','overlap_count')})
            elif name=='_deterministic_weak_evidence_is_sufficient' and event=='return':
                parent=frame.f_back; p=parent.f_locals
                record=p.get('best') or p.get('best_evidence')
                emit(frame,'WEAK_THRESHOLD_EVALUATED',p.get('requirement'),record,
                    {k:values[k] for k in ('score','focus_coverage','overlap_count')} | {'passed':arg,
                     'minimum_score':n._DETERMINISTIC_WEAK_MIN_SCORE,
                     'minimum_coverage':n._DETERMINISTIC_WEAK_MIN_COVERAGE,
                     'minimum_overlap':n._DETERMINISTIC_WEAK_MIN_OVERLAP})
            elif name=='_evidence_source_is_requirement_compatible' and event=='return':
                emit(frame,'SOURCE_COMPATIBILITY_EVALUATED',values.get('requirement'),values.get('row'),{'allowed':arg})
            elif name=='_apply_capability_none_recovery' and event=='line' and frame.f_lineno==rejection_line:
                emit(frame,'RECOVERY_WEAK_ZERO_OVERLAP_REJECTED',values['row'],values['best_row'],
                     {'overlap':values['best_overlap'],'coverage':values['best_coverage']},values['best_decision'])
            elif name=='_evaluate_capability_record' and event=='return' and isinstance(arg,dict):
                parent=frame.f_back
                while parent and parent.f_code not in (n._apply_capability_none_recovery.__code__,n._apply_capability_single_row_reselection.__code__):
                    if parent.f_code is preview.run_comparison.__code__: break
                    parent=parent.f_back
                if parent and parent.f_code in (n._apply_capability_none_recovery.__code__,n._apply_capability_single_row_reselection.__code__):
                    emit(frame,'CAPABILITY_EVIDENCE_EVALUATED',values.get('requirement'),parent.f_locals.get('evidence_row'),decision=arg)
        except Exception:
            errors+=1  # never change scorer control flow; disclose observation failure
        return local

    def global_trace(frame,event,arg):
        return local if frame.f_code in watched else None

    try:
        sys.settrace(global_trace)
        comparison=preview.run_comparison(request,developer_enabled=True)
    finally:
        sys.settrace(None)
    context=request.projection['context']
    ledger=verified_projection_ledger(request.projection,context['resume_profile'],context['raw_resume_text'])
    owners={}
    for occurrence in ledger['occurrences']:
        key=fingerprint(tuple(occurrence.get(k) for k in ('source','section','text','evidence_id')))
        owners.setdefault(key,set()).update(o['library_item_id'] for o in occurrence.get('library_origins',[]))
    for event in events:
        original_owners=owners.get(event['record_reference'],set())
        event['library_owner_ids']=sorted(original_owners) if len(original_owners)==1 else []
        event['owner_status']='EXACT_SINGLE_ORIGINAL' if len(original_owners)==1 else 'UNATTRIBUTED_OR_AMBIGUOUS'
    return comparison,{'schema_version':VERSION,'input_identity':request.identity,
        'implementation_identity':preview.source_revision(),'events':events,
        'dropped_events':dropped,'observer_errors':errors,'source_text_included':False}

"""Explicit, input-scoped inspection of retained original evidence decisions."""
import json
import streamlit as st
from job_discovery import evidence_decision_trace as trace

STATE='developer_evidence_trace_v1'


def render(request,comparison,selected_ids,*,synthetic=False):
    state_key=STATE+'_synthetic' if synthetic else STATE
    def key(name): return ('developer_synthetic_trace_' if synthetic else 'developer_trace_')+name
    st.subheader('Evidence Decision Trace')
    st.caption(('Synthetic explicit-library authority. ' if synthetic else 'Frozen Job Finder library authority only. ')+
               'Application Session/document and Phase 8 sources are excluded. '
               'A missing accepted reference is not a rejection trace. No matching is rerun.')
    state=st.session_state.get(state_key)
    if state and state['identity']!=request.identity:
        st.session_state.pop(state_key,None); state=None
    if st.button('Build retained evidence trace',key=key('build')):
        try:
            state={'identity':request.identity,'trace':trace.build(request,comparison),'reviews':{}}
            st.session_state[state_key]=state
        except (ValueError,KeyError,TypeError):
            st.session_state.pop(state_key,None); state=None
            st.warning('Trace unavailable: source/receipt verification failed or input exceeds the diagnostic bound.')
    if state is None:
        st.caption('Build explicitly from the retained comparison. No new score or saved result is produced.'); return
    data=state['trace']; coverage=data['coverage']
    st.download_button('Download share-safe evidence trace JSON',json.dumps(data,sort_keys=True,indent=2,allow_nan=False),
        file_name='evidence_decision_trace.json',mime='application/json',on_click='ignore',key=key('download'))
    st.caption(f"{coverage['original_records']} original library records · {coverage['requirements']} requirements · "
               f"{coverage['unknown_consideration_pairs']} pairs with unobservable consideration · partial trace")
    st.info('Successful recovery/reselection and coordinated events are observable when retained. '
            'Unsuccessful native candidate histories are not retained; unknowns are not rejection counts.')
    summary=[]
    for row in data['requirements']:
        for side,value in row['sides'].items():
            if value['status']=='ABSENT_REQUIREMENT_GEOMETRY': continue
            summary.append({'Requirement ID':row['requirement_id'],'Side':side,
                **{k:value[k] for k in ('importance','parent_id','allocation','label','disposition',
                    'original_records','projected_records','indexed_records','observably_considered_records',
                    'admitted_records','observably_filter_rejected_records','not_selected_records',
                    'taxonomy_ceiling','native_reason_code','status')},
                'Recovery attempted':str(value['recovery']['attempted']),'Reselection attempted':str(value['reselection']['attempted']),
                'Considered total':value['considered_total'],'Rejected total':value['rejected_total'],
                'Not evaluated total':value['not_evaluated_total']})
    st.dataframe(summary,hide_index=True,width='stretch',height=260,
        column_config={'Requirement ID':st.column_config.TextColumn(width='medium',pinned=True)},
        alt='Per-requirement observed evidence coverage; incomplete counts are explicitly unknown')
    available=[r['requirement_id'] for r in data['requirements']]
    options=[r for r in available if r in selected_ids] if selected_ids else available
    if not options: st.info('No selected identity exists in this trace.'); return
    rid=st.selectbox('Trace requirement (uses checkbox selections when present)',options,key=key('requirement'))
    requirement=next(r for r in data['requirements'] if r['requirement_id']==rid)
    pairs=[r for r in data['matrix'] if r['requirement_id']==rid]
    st.dataframe([{k:str(v) if k in ('considered','rejected') else v for k,v in r.items()} for r in pairs],
        hide_index=True,width='stretch',alt='Original-record decisions, with observed filter rejection separate from final selection')
    item=st.selectbox('Original library record',[i for i in sorted({r['library_item_id'] for r in pairs})],key=key('record'))
    pair_key=trace.fingerprint([request.identity,rid,item])
    if state.get('pair')!=pair_key:
        state.pop('private',None); state['pair']=pair_key
    with st.expander('Selected record native stages and threshold/recovery receipts',expanded=False):
        for side,value in requirement['sides'].items():
            if value['status']=='ABSENT_REQUIREMENT_GEOMETRY': st.write(side,value); continue
            pair=next(r for r in value['records'] if r['library_item_id']==item)
            st.write(side)
            st.json({'record':pair,'recovery':value['recovery'],'reselection':value['reselection'],
                'taxonomy_ceiling':value['taxonomy_ceiling'],'disposition':value['disposition'],
                'contradiction_quarantined':value['contradiction_quarantined'],
                'observed_final_row_metrics':value['observed_final_row_metrics'],
                'metric_role':value['metric_role'],'native_link_source':value['native_link_source'],
                'retained_native_warning_codes':value['retained_native_warning_codes'],
                'recovery_identity_reference':value['recovery_identity_reference'],
                'threshold_reference':data['configured_threshold_reference']})
            analysis=comparison.published_analysis if side=='published' else comparison.gated_analysis
            native=next(r for r in analysis['canonical_requirements'] if r['requirement_id']==rid)
            st.write('Local native explanation (excluded from share-safe exports)',
                     {k:native.get(k) for k in ('match_source','match_reason','capability_id','capability_resolution_source')})
            st.caption('Configured threshold values are reference information, not proof of a candidate evaluation. '
                       'Filter rejection applies to an observed occurrence/stage, not necessarily the whole record.')
    with st.expander('Independent local pair review — no scoring effect',expanded=False):
        category=st.selectbox('Reviewer interpretation',trace.REVIEW_CATEGORIES,key=key('review_category'))
        if st.button('Record local diagnostic review',key=key('review_save')):
            state['reviews'][pair_key]={'requirement_id':rid,'library_item_id':item,'category':category}
        if pair_key in state['reviews']: st.write(state['reviews'][pair_key])
        st.caption('An explicit reviewer annotation, not proof or an approval. Session memory only; never saved to applications or policy.')
    with st.expander('Private original-candidate excerpts — separate consent',expanded=False):
        consent=st.checkbox('I consent to preview private original-candidate excerpts',key=key('private_consent'))
        if not consent: state.pop('private',None)
        st.caption('Unredacted wording from this one original record. Not asserted accepted or rejected. '
                   'Different from the accepted-only selected excerpt export. Review before sharing.')
        if st.button('Preview original candidate',key=key('private_preview'),disabled=not consent):
            state['private']=json.dumps(trace.private_pair(request,comparison,rid,item,consent=consent),ensure_ascii=False,indent=2)
        if consent and state.get('private'):
            st.warning('PRIVATE — original candidate excerpts, no guaranteed redaction.')
            st.code(state['private'],language='json')
            st.download_button('Download private original-candidate excerpts',state['private'],
                file_name='private_original_candidate.json',mime='application/json',on_click='ignore',key=key('private_download'))

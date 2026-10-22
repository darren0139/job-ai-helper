"""Native review table and explicit local exports. No scoring/storage routes."""
import json
import streamlit as st
from job_discovery import developer_debug_export as debug
from job_discovery import developer_batch_audit as batch

EXPORT_STATE='developer_real_debug_exports_v1'
SELECTION='developer_real_review_selected'


def clear_exports():
    st.session_state.pop(EXPORT_STATE,None)
    st.session_state.pop(SELECTION,None)
    st.session_state.pop('developer_evidence_trace_v1',None)


def render_scope(loaded):
    context=loaded['context']; retro=loaded.get('mode')=='RETROSPECTIVE_FROZEN_INPUTS_V1'
    with st.container(border=True):
        st.markdown('**Comparison scope**')
        st.caption('Input authority: frozen Job Finder library · Current Application Session included: No · Phase 8 included: No')
        if retro:
            st.caption('Comparing original frozen Job Finder evidence with fresh scoring implementations. '
                       'Current Application Session and Phase 8 results are not included.')
        st.caption('Job Finder library snapshots, actual résumé documents, application-local preferences and Phase 8 '
                   'before/after sources are not interchangeable. Cross-workflow score differences may be expected.')
        cols=st.columns(3)
        cols[0].write('Application '+str(loaded['application_id']))
        cols[1].write('Source job '+str(context.get('discovered_job_id')))
        cols[2].write('Evidence snapshot '+str(context.get('source_snapshot_id')))
        st.caption('Archived: '+str(loaded['saved']['versions'].get('scoring_version'))+
                   ' · Current report differs: '+('Yes' if context.get('current_application_report_differs') else 'No'))
        if context.get('current_application_report_differs'):
            st.warning('The current application report/overrides differ from the frozen handoff. '
                       'They are excluded; this is not a current Application Session result.')
        with st.expander('Archived historical reference — separate from fresh diagnostics',expanded=False):
            st.write({'Versions':loaded['saved']['versions'],'Saved alignment':loaded['saved']['score'],
                      'Saved receipt identity':loaded['saved']['identity']})
            st.caption('Original saved result. No historical-to-fresh score delta is calculated.')


def _scores(result,stats):
    c=result['comparison']
    for col,label,view in zip(st.columns(2),('Published diagnostic','Experimental diagnostic'),(c.published,c.gated)):
        with col,st.container(border=True):
            st.markdown('**'+label+'**'); st.caption(view.scoring_version)
            if stats['comparative_geometry_withheld']:
                st.warning('Alignment unavailable — incompatible comparative geometry.')
            elif not view.score_available:
                st.warning('Alignment unavailable — REVIEW_REQUIRED; null is not zero.')
            else:
                st.metric('Alignment',f'{view.alignment}%')
            counts=view.summary()['counts']
            st.caption(' · '.join(f'{key}: {counts[key]}' for key in ('DIRECT','TRANSFERABLE','WEAK','NONE','REVIEW_REQUIRED')))
            st.caption('Required/core: '+str(view.required_core if view.required_core is not None else 'Unavailable')+
                       ' · Preferred: '+str(view.preferred if view.preferred is not None else 'Unavailable')+
                       ' · Evidence strength: '+str(view.evidence_strength if view.evidence_strength is not None else 'Unavailable'))
    st.caption(f"{stats['identical_rows']} identical rows · {stats['changed_labels']} changed labels · "
        f"{stats['changed_sources']} changed sources · {stats['geometry_mismatches']} geometry mismatches · "
        f"{stats['withheld_scores']} withheld scores · {stats['requiring_review']} requiring review")
    if stats['identical_rows']==stats['total_requirements']:
        st.info('No requirement-level scoring differences detected for this input.')
    st.caption('Identical labels or scores do not establish overall scoring correctness. '
               'Native evidence, source authority and independent expectations still require review.')
    if stats['geometry_mismatches']:
        st.warning('Incompatible requirement geometry/allocation. No numeric improvement or downgrade is inferred.')


def render_results(loaded,result):
    identity=result['identity']; cache=st.session_state.get(EXPORT_STATE)
    if cache and cache['identity']!=identity: clear_exports(); cache=None
    rows=debug.review_rows(result['comparison']); stats=debug.summary(result)
    _scores(result,stats)
    st.subheader(f"Requirement Review · {len(rows)} requirements")
    st.caption('Checkboxes select local diagnostic inspection only. They never approve evidence or update saved results. '
               'Blank/null credits mean unavailable, never zero. Scroll horizontally for additional columns.')
    search=st.text_input('Search requirements by text or ID',key='developer_real_search')
    cols=st.columns(4); labels=['All','DIRECT','TRANSFERABLE','WEAK','NONE','REVIEW_REQUIRED']
    published=cols[0].selectbox('Published label',labels,key='developer_real_published')
    experimental=cols[1].selectbox('Experimental label',labels,key='developer_real_experimental')
    discrepancy=cols[2].selectbox('Discrepancy',['All','Identical','Changed','Source difference','Geometry difference','Credit difference'],key='developer_real_discrepancy')
    review=cols[3].selectbox('Review state',['All','Requires review','No review flag'],key='developer_real_review_state')
    # Preserve the existing diagnostic filter key/semantics for saved sessions.
    category=st.selectbox('Real requirement filter',['All','Changed','Conflict','Withheld','Geometry difference',
        'DIRECT','TRANSFERABLE','WEAK','NONE','REVIEW_REQUIRED'],key='developer_real_filter')
    visible=debug.filter_rows(batch.filter_requirements(rows,category),search=search,published=published,
                              experimental=experimental,discrepancy=discrepancy,review=review)
    if st.session_state.get('developer_real_review_identity')!=identity:
        st.session_state[SELECTION]=[]; st.session_state['developer_real_review_identity']=identity
    selected=set(st.session_state.get(SELECTION,[])) & {r['Requirement ID'] for r in rows}
    revkey='developer_real_review_revision'; controls=st.columns(3)
    for i,(label,values) in enumerate((('Select all visible',{r['Requirement ID'] for r in visible}),
        ('Clear selection',set()),('Select changed or flagged',{r['Requirement ID'] for r in rows if r['Changed or flagged']}))):
        if controls[i].button(label,key='developer_real_review_action_'+str(i)):
            selected=selected|values if i==0 else values
            st.session_state[revkey]=st.session_state.get(revkey,0)+1
    fields=('Requirement ID','Requirement','Importance','Published','Experimental','Published credit',
            'Experimental credit','Difference','Source/conflict status')
    data=[{'Select':r['Requirement ID'] in selected,**{k:r[k] for k in fields}} for r in visible]
    if stats['comparative_geometry_withheld']:
        for row in data: row['Published credit']=row['Experimental credit']=None
    if data:
        widget='developer_real_editor_'+debug.fingerprint([identity,search,published,experimental,discrepancy,review,
            category,st.session_state.get(revkey,0)])[:16]
        edited=st.data_editor(data,hide_index=True,width='stretch',height=440,num_rows='fixed',key=widget,
            disabled=list(fields),column_order=['Select',*fields],
            column_config={'Select':st.column_config.CheckboxColumn(width='small',pinned=True),
                'Requirement ID':st.column_config.TextColumn(width='medium'),
                'Requirement':st.column_config.TextColumn(width='large'),
                'Published':st.column_config.TextColumn(label='Published label',width='small'),
                'Experimental':st.column_config.TextColumn(label='Experimental label',width='small'),
                'Published credit':st.column_config.NumberColumn(format='%.3f',help='Null means unavailable'),
                'Experimental credit':st.column_config.NumberColumn(format='%.3f',help='Null means unavailable')},
            alt='Visible checkboxes select exact requirement IDs; all evidence and scoring columns are read-only')
        selected=set(batch.merge_selection(selected,edited,[r['Requirement ID'] for r in visible]))
    else: st.info('No requirements match these filters. Hidden selections are retained.')
    st.session_state[SELECTION]=sorted(selected)
    st.caption(f'{len(visible)} of {len(rows)} displayed · {len(selected)} selected, including hidden selections.')
    with st.expander(f'Selected requirement inspection · {len(selected)}',expanded=False,on_change='rerun') as details:
        if details.open:
            for rid in sorted(selected):
                row=next(r for r in rows if r['Requirement ID']==rid)
                with st.expander(rid+' · '+row['Requirement'],expanded=False,on_change='rerun') as receipt:
                    if not receipt.open: continue
                    st.write(row)
                    c=result['comparison']
                    for side,view,analysis in (('Published',c.published,c.published_analysis),('Experimental',c.gated,c.gated_analysis)):
                        r=next((r for r in view.requirements if r.requirement_id==rid),None)
                        if r is None: st.info(side+' counterpart unavailable. No inferred text mapping.'); continue
                        raw=next(r for r in analysis['canonical_requirements'] if r['requirement_id']==rid)
                        st.write(side,{'Native label':r.native_label,'Disposition':r.disposition,
                            'Supported actions':r.supported_actions,'Missing actions':r.missing_actions,
                            'Technical scope':r.technical_scope,'Parent allocation':r.allocation,
                            'Standalone credit':r.contribution,'Capability ID':raw.get('capability_id')})
                        with st.expander(side+' original source and evaluation receipts',expanded=False):
                            st.json({'evidence':r.evidence,'conflict':r.conflict,'receipt':r.receipt,
                                     'source_provenance':raw.get('source_provenance')})
    from job_discovery.evidence_trace_ui import render as render_trace
    render_trace(loaded['request'],result['comparison'],sorted(selected))
    with st.expander('Metadata diagnostics · classification only · NO-GO',expanded=False,on_change='rerun') as metadata:
        if metadata.open:
            for version,receipt in result['metadata'].items():
                st.write(version); st.dataframe(receipt['lines'],hide_index=True,width='stretch',alt='Local metadata classifications, not scores')
    render_exports(loaded,result,sorted(selected))


def render_exports(loaded,result,selected):
    st.subheader('Debug export and source integrity')
    st.caption('Explicit local exports from retained results. No scoring, persistence or external submission. '
               'Share-safe bundles omit requirement/evidence wording; selected private excerpts are separate.')
    if st.button('Export Comparison Debug',key='developer_real_debug_build'):
        try:
            report=debug.build_report(loaded,result); data,zipdata=debug.bundle(report)
            st.session_state[EXPORT_STATE]={'identity':result['identity'],'report':report,'json':data,'zip':zipdata}
        except (ValueError,KeyError,TypeError):
            st.session_state.pop(EXPORT_STATE,None)
            st.error('Debug export unavailable: receipt/schema validation failed. No private error payload exported.')
    cache=st.session_state.get(EXPORT_STATE)
    if cache and cache['identity']==result['identity'] and 'report' in cache:
        cols=st.columns(2)
        cols[0].download_button('Download share-safe JSON',cache['json'],file_name='comparison_debug.json',mime='application/json',on_click='ignore')
        cols[1].download_button('Download share-safe ZIP',cache['zip'],file_name='comparison_debug.zip',mime='application/zip',on_click='ignore')
        with st.expander('Copy concise diagnostic summary',expanded=False):
            st.caption('Use the native copy button on this text block.')
            st.code(debug.concise_summary(cache['report']),language='text')
    with st.expander('Source-integrity identities',expanded=False):
        st.write({'Input identity':result['identity'],'Fresh request identity':result['comparison'].identity,
                  'Saved JD fingerprint':loaded['context'].get('raw_jd_sha256'),
                  'Frozen evidence fingerprint':loaded['context'].get('evidence_fingerprint')})
    with st.expander('Private selected excerpts — optional, not share-safe',expanded=False):
        optin=st.checkbox('I understand selected excerpts may contain private information',key='developer_real_private_optin')
        st.caption('No guaranteed redaction. Preview before sharing. Excerpts are capped at 2,000 characters each; '
                   'raw résumé documents, arbitrary metadata and database rows are never exported.')
        cache=st.session_state.setdefault(EXPORT_STATE,{'identity':result['identity']})
        if not optin or cache.get('private_ids')!=selected:
            cache.pop('private',None); cache.pop('private_ids',None)
        if st.button('Preview selected private excerpts',key='developer_real_private_preview',disabled=not optin or not selected):
            private=debug.selected_excerpts(result,selected,opted_in=optin)
            cache['private']=json.dumps(private,ensure_ascii=False,indent=2); cache['private_ids']=selected
        if optin and cache.get('private'):
            st.warning('PRIVATE — unredacted selected excerpts. This is not the share-safe debug bundle.')
            st.code(cache['private'],language='json')
            st.download_button('Download private selected excerpts',cache['private'],file_name='private_selected_excerpts.json',mime='application/json',on_click='ignore')


def render_failure_export(loaded, code):
    st.caption('No successful comparison result exists. Debug export contains only the public failure code and input identity.')
    if st.button('Export Comparison Debug',key='developer_real_debug_failure'):
        report=debug.failure_report(loaded,code); data,zipped=debug.bundle(report)
        st.session_state[EXPORT_STATE]={'identity':loaded['identity'],'failure_json':data,'failure_zip':zipped}
    cached=st.session_state.get(EXPORT_STATE,{})
    if cached.get('identity')==loaded['identity'] and 'failure_json' in cached:
        st.download_button('Download failure JSON',cached['failure_json'],file_name='comparison_failure.json',mime='application/json',on_click='ignore')
        st.download_button('Download failure ZIP',cached['failure_zip'],file_name='comparison_failure.zip',mime='application/zip',on_click='ignore')

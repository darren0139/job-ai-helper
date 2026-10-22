"""One isolated main-app diagnostics page; session-local, explicit evaluation."""
import streamlit as st
from job_discovery import developer_comparison as adapter
from scripts.coordinated_job_match_preview_inputs import synthetic_cases


def render_developer_comparison():
    st.header('Developer Job Match comparison')
    if not adapter.enabled():
        st.session_state.pop(adapter.STATE, None)
        st.session_state.pop('developer_real_comparison_v1', None)
        st.session_state.pop('developer_real_applications_v1', None)
        from job_discovery.developer_review_ui import clear_exports
        clear_exports()
        st.session_state.pop('developer_evidence_trace_v1_synthetic',None)
        st.info('Developer comparison OFF. Set JOB_AI_DEVELOPER_COMPARISON=1 before launch.')
        return
    st.warning('Experimental · Developer diagnostics · Never saved or used for ranking')
    consent = st.toggle('Enable this session comparison', key='developer_job_match_ui_v1_enabled', value=False)
    real_tab,synthetic_tab,batch_tab=st.tabs(['Real Application Comparison','Synthetic Comparison','Synthetic Batch Audit'])
    with real_tab:
        render_real_comparison(consent)
    with synthetic_tab:
        render_synthetic_comparison(consent)
    with batch_tab:
        from job_discovery.developer_batch_ui import render_batch_audit
        render_batch_audit(consent)


def render_synthetic_comparison(consent):
    st.subheader('Synthetic comparison')
    st.caption('Published scores below are fresh synthetic evaluations, not saved Job Match results.')
    cases = synthetic_cases()
    case_id = st.selectbox('Synthetic example', [c['id'] for c in cases], key='developer_job_match_ui_v1_case',
        format_func=lambda key: key+' — '+next(c['theme'] for c in cases if c['id'] == key))
    if not consent:
        st.session_state.pop(adapter.STATE, None)
    result = st.session_state.get(adapter.STATE)
    try:
        if result:
            adapter.require_current(result, case_id)
    except (ValueError, KeyError, TypeError, OSError):
        st.session_state.pop(adapter.STATE, None)
        result = None
        st.info('Inputs or implementation changed; explicitly run again.')
    if st.button('Run comparison', key='developer_job_match_ui_v1_run', disabled=not consent):
        st.session_state.pop(adapter.STATE, None)
        try:
            with st.spinner('Evaluating isolated synthetic evidence'):
                result = adapter.evaluate(case_id, session_enabled=consent)
            st.session_state[adapter.STATE] = result
        except Exception:
            result = None
            st.error('Comparison unavailable: evaluation or validation failed. No result was published. '
                     'Diagnostic status: EVALUATION_FAILED. Check the local developer test run.')
    if not result:
        st.session_state.pop('developer_evidence_trace_v1_synthetic',None)
        st.info('No comparison available. Enable this session and explicitly run a synthetic example.')
        return
    comparison = result['comparison']
    for col, title, view in zip(st.columns(2), ('Published · gate OFF', 'Experimental · source-aware'),
                               (comparison.published, comparison.gated)):
        with col:
            st.subheader(title)
            st.caption(view.scoring_version)
            st.caption('Fresh synthetic evaluation · '+comparison.authority+' · Ranking ineligible')
            if view.score_available:
                st.metric('Synthetic alignment', f'{view.alignment}%')
            else:
                st.warning('Whole-JD alignment unavailable — review required; no numeric score or band.')
            st.write(view.summary()['counts'])
    st.caption('v1.21 uses the v1.20 coordinated evaluator with verified library-source projection. '
               'Different decomposition/allocation can prevent row-by-row numeric comparison. '
               'NONE is a governed result; REVIEW_REQUIRED credit stays null.')
    rows = adapter.requirement_rows(comparison)
    status = st.selectbox('Diagnostic category', ['All', 'REVIEW_REQUIRED', 'Changed', 'NONE', 'WEAK', 'DIRECT'],
                          key='developer_job_match_ui_v1_filter')
    visible = [r for r in rows if status == 'All' or
               (status == 'Changed' and r['Difference'] != 'Same label/allocation; inspect source receipts') or
               status in (r['Published'], r['Experimental'])]
    st.dataframe(visible, hide_index=True, width='stretch',
        column_config={'Requirement': st.column_config.TextColumn(width='large'),
                       'Requirement ID': st.column_config.TextColumn(width='medium')},
        alt='Exact requirement identities, published and experimental labels and nullable credits')
    from job_discovery.developer_batch_ui import render_multi_review
    render_multi_review(result, 'developer_single_review_'+case_id)
    if visible:
        selected = st.selectbox('Inspect requirement', [r['Requirement ID'] for r in visible],
            key='developer_job_match_ui_v1_requirement',
            format_func=lambda rid: next(r['Requirement'] for r in visible if r['Requirement ID'] == rid))
        for name, view, analysis in (('Published', comparison.published, comparison.published_analysis),
                                    ('Experimental', comparison.gated, comparison.gated_analysis)):
            row = next((r for r in view.requirements if r.requirement_id == selected), None)
            st.subheader(name+' requirement')
            if row is None:
                st.info('Unavailable in this decomposition. No similar-text substitution.')
                continue
            st.write(row.text)
            st.write({'Requirement ID': row.requirement_id, 'Label': row.label.value,
                'Native label': row.native_label, 'Disposition': row.disposition,
                'Allocation': row.allocation, 'Contribution': row.contribution,
                'Missing actions': list(row.missing_actions), 'Supported actions': list(row.supported_actions),
                'Technical scope': row.technical_scope})
            if row.label.value == 'REVIEW_REQUIRED':
                st.warning('Contribution unavailable. Incomplete evidence does not prove absence of experience.')
            if row.evidence:
                st.dataframe(list(row.evidence), hide_index=True, width='stretch', alt='Selected original evidence and source identity')
            raw = next(r for r in analysis['canonical_requirements'] if r['requirement_id'] == selected)
            with st.expander(name+' source, conflict and scoring receipts', expanded=False):
                st.json({'source_provenance': raw.get('source_provenance'), 'receipt': row.receipt,
                         'conflict': row.conflict, 'capability_id': raw.get('capability_id'),
                         'score_eligible': raw.get('score_eligible')})
    from job_discovery.evidence_trace_ui import render as render_trace
    from scripts.coordinated_job_match_preview_inputs import preview_inputs
    render_trace(adapter.preview.prepare_comparison(**preview_inputs(case_id)),comparison,[selected] if visible else [],synthetic=True)
    st.subheader('JD metadata diagnostics · NO-GO')
    st.caption('Classification only, using the same original JD. v1.22/v1.23 scores are not evaluated here. '
               'Ambiguous content remains unresolved; these exclusions never affect the published result.')
    version = st.selectbox('Metadata experiment', list(result['metadata']), key='developer_job_match_ui_v1_metadata')
    metadata = result['metadata'][version]
    st.dataframe([{k: r.get(k) for k in ('source', 'raw_text', 'classification', 'reason', 'admitted')}
                  for r in metadata['lines']], hide_index=True, width='stretch', alt='Experimental JD line classifications with unresolved ambiguity')
    if any(r['classification'].startswith('AMBIGUOUS') for r in metadata['lines']):
        st.warning('Ambiguous JD lines require review; no confirmed exclusion is asserted for them.')
    with st.expander('Sanitized diagnostic export', expanded=False):
        text = st.checkbox('Include selected synthetic requirement/JD text', value=False, key='developer_job_match_ui_v1_export_text')
        st.caption('Default excludes raw JD/résumé text and full receipts. In-memory download only.')
        st.download_button('Download sanitized JSON', adapter.diagnostic_export(result, case_id, include_synthetic_text=text),
            file_name='developer_job_match_comparison.json', mime='application/json', on_click='ignore')


def render_real_comparison(consent):
    """One selected, authorized handoff. Store at most one loaded/result pair."""
    from job_discovery import developer_real_comparison as real
    from job_discovery import developer_batch_audit as batch
    from job_discovery.developer_review_ui import clear_exports,render_scope,render_results
    st.subheader('Real Application Comparison (Read Only)')
    st.caption('Developer diagnostic only — does not update Job Match, Application Sessions or Phase 8.')
    if not consent or not adapter.enabled():
        st.session_state.pop(real.STATE, None)
        st.session_state.pop(real.INDEX, None)
        clear_exports()
        st.info('Opt in above to list saved applications. No real inputs loaded.')
        return
    if st.button('Browse saved applications', key='developer_real_browse'):
        clear_exports()
        st.session_state.pop(real.STATE, None)
        st.session_state.pop(real.INDEX, None)
        try:
            st.session_state[real.INDEX] = real.list_applications(session_enabled=consent)
        except real.Blocked as exc:
            st.warning(str(exc))
    applications = st.session_state.get(real.INDEX)
    if applications is None:
        st.caption('Browsing is explicit and separate from synthetic comparison; only identifying context is listed.')
        return
    choices = {a['id']: a for a in applications}
    selector,admission=st.columns([3,2])
    selected = selector.selectbox('Saved application', [None, *choices], key='developer_real_app',
        format_func=lambda key: 'Select one application' if key is None else
        f"{key} · {choices[key]['session_name'] or choices[key]['job_title'] or 'Saved application'}")
    mode = admission.selectbox('Comparison admission', ['Strict current-version comparison',
        'Retrospective Frozen Evidence Comparison'], key='developer_real_mode')
    retrospective = mode == 'Retrospective Frozen Evidence Comparison'
    if retrospective:
        st.warning(real.RETROSPECTIVE_LABEL)
    state = st.session_state.get(real.STATE)
    if state and (state['loaded']['application_id'] != selected or
                  (state['loaded'].get('mode') == real.RETROSPECTIVE) != retrospective):
        st.session_state.pop(real.STATE, None)
        clear_exports()
        state = None
    if selected is None:
        st.info('No application selected. No real comparison runs automatically.')
        return
    load_action,compare_action=st.columns(2)
    if load_action.button('Load saved comparison inputs', key='developer_real_load'):
        clear_exports()
        st.session_state.pop(real.STATE, None)
        state = None
        try:
            loader = real.load_retrospective if retrospective else real.load
            state = {'loaded': loader(selected, session_enabled=consent)}
            st.session_state[real.STATE] = state
        except real.Blocked as exc:
            st.warning(str(exc))
    compare_requested=compare_action.button('Compare loaded application',key='developer_real_compare',disabled=not state)
    if not state:
        return
    try:
        real.require_current(state['loaded'],session_enabled=consent)
    except real.Blocked as exc:
        st.session_state.pop(real.STATE,None)
        clear_exports()
        st.warning(str(exc))
        return
    loaded=state['loaded']
    if compare_requested:
        state.pop('result',None)
        state.pop('diagnostic_exception',None)
        clear_exports()
        try:
            with st.spinner('Comparing frozen evidence in memory'):
                state['result']=real.evaluate(loaded,session_enabled=consent)
        except real.Blocked as exc:
            st.warning(str(exc))
        except Exception:
            state['diagnostic_exception']='COMPARISON_FAILED'
            st.error('Comparison failed. Diagnostic code: COMPARISON_FAILED. No raw private error was published.')
    render_scope(loaded)
    result=state.get('result')
    if not result:
        if state.get('diagnostic_exception'):
            st.caption('Retry explicit Load and Compare. No result or score was saved.')
            from job_discovery.developer_review_ui import render_failure_export
            render_failure_export(loaded,state['diagnostic_exception'])
        return
    if result['identity']!=loaded['identity'] or result['comparison'].identity!=loaded['request'].identity:
        state.pop('result',None)
        clear_exports()
        st.warning('STALE: comparison receipt differs from the loaded source. Explicitly compare again.')
        return
    render_results(loaded,result)

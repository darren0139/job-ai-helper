"""Native multi-selection and explicit, resumable UI chunks. No background runs."""
import json
import streamlit as st
from job_discovery import developer_batch_audit as batch
from job_discovery import developer_comparison as adapter

STATE = 'developer_job_match_ui_v11_batch'
EXPORT = 'developer_job_match_ui_v11_downloads'


def render_multi_review(result, prefix):
    rows = batch.review_rows(result['comparison'])
    category = st.selectbox('Multi-review filter', ['All', 'Changed', 'Source difference', 'Conflict', 'Withheld',
        'Geometry difference', 'Missing counterpart', 'DIRECT', 'WEAK', 'TRANSFERABLE', 'NONE', 'REVIEW_REQUIRED'], key=prefix+'_filter')
    visible = batch.filter_requirements(rows, category)
    key = prefix+'_selected'
    selected = set(st.session_state.get(key, []))
    ids = {r['Requirement ID'] for r in rows}
    selected &= ids
    revision_key = prefix+'_selection_revision'
    cols = st.columns(3)
    actions = ((cols[0], 'Select all displayed', {r['Requirement ID'] for r in visible}),
               (cols[1], 'Clear selection', set()),
               (cols[2], 'Select changed or flagged', {r['Requirement ID'] for r in rows if r['Changed or flagged']}))
    for index, (col, label, values) in enumerate(actions):
        if col.button(label, key=prefix+'_action_'+str(index)):
            selected = values if index else selected | values
            st.session_state[revision_key] = st.session_state.get(revision_key, 0)+1
    widget_key = prefix+'_editor_'+batch.fingerprint([result['identity'], category,
        sorted(r['Requirement ID'] for r in visible), st.session_state.get(revision_key, 0)])[:12]
    if visible:
        data = [{'Select': r['Requirement ID'] in selected, **r} for r in visible]
        edited = st.data_editor(data, hide_index=True, width='stretch', num_rows='fixed', key=widget_key,
            disabled=[column for column in data[0] if column != 'Select'],
            column_config={'Select': st.column_config.CheckboxColumn(help='Inspection only; never approves or changes evidence'),
                           'Requirement': st.column_config.TextColumn(width='large')},
            alt='Select exact requirement identities for inspection; all scoring fields are read-only')
        selected = set(batch.merge_selection(selected, edited, [r['Requirement ID'] for r in visible]))
    st.session_state[key] = sorted(selected)
    st.caption(f'{len(selected)} requirements selected, including selections hidden by the filter. Selection never changes scores.')
    if selected:
        with st.expander('Selected requirement details · '+result['case_id'], expanded=False, on_change='rerun') as details:
            for r in rows:
                if not details.open or r['Requirement ID'] not in selected: continue
                with st.expander(r['Requirement ID']+' · '+r['Requirement'], expanded=False, on_change='rerun') as receipt:
                    if not receipt.open: continue
                    st.write(r)
                    comparison = result['comparison']
                    for side, view, raw in (('Published', comparison.published, comparison.published_analysis),
                                            ('Experimental', comparison.gated, comparison.gated_analysis)):
                        row = next((item for item in view.requirements if item.requirement_id == r['Requirement ID']), None)
                        if row:
                            st.write(side, {'Native label': row.native_label, 'Missing actions': row.missing_actions,
                                'Supported actions': row.supported_actions, 'Technical scope': row.technical_scope})
                            st.json({'evidence': row.evidence, 'conflict': row.conflict, 'receipt': row.receipt,
                                'source_provenance': next(item.get('source_provenance') for item in raw['canonical_requirements']
                                    if item['requirement_id'] == row.requirement_id)})
                        else:
                            st.info(side+' counterpart unavailable. No inferred geometry mapping.')
        text = st.checkbox('Include synthetic wording in selected export', key=prefix+'_include_text', value=False)
        st.download_button('Download selected requirements', batch.selected_export(result, sorted(selected), include_text=text),
            file_name=result['case_id']+'_selected_requirements.json', mime='application/json', key=prefix+'_download', on_click='ignore')


def render_batch_audit(consent):
    st.subheader('Synthetic batch audit')
    st.caption('COMPLETED means evaluation finished, not that evidence or policy passed. '
               'Run queues a preset and evaluates a bounded chunk; Continue explicitly runs the next chunk. '
               'Stop cancels pending cases between chunks. An active synchronous case cannot be forcibly interrupted.')
    if not consent:
        st.session_state.pop(STATE, None)
        st.session_state.pop(EXPORT, None)
    presets = {'Quick · 3': batch.QUICK, 'Extended · 10': batch.EXTENDED,
               'Complete · 38': tuple(c['id'] for c in batch.registry()), 'Custom': ()}
    preset = st.selectbox('Batch preset', list(presets), key='developer_batch_preset')
    chosen = st.multiselect('Custom cases', [c['id'] for c in batch.registry()], key='developer_batch_custom') if preset == 'Custom' else presets[preset]
    chunk = st.selectbox('Cases per explicit step', [1, 2, 3], key='developer_batch_chunk')
    current = st.session_state.get(STATE)
    if current:
        try: batch.require_current(current)
        except (ValueError, KeyError, OSError):
            st.session_state.pop(STATE, None); st.session_state.pop(EXPORT, None)
            current = None
            st.warning('Batch source/implementation changed; start a new batch. Prior downloads cleared.')
    cols = st.columns(4)
    selected_run = cols[0].button('Run selected', key='developer_batch_run', disabled=not consent or not chosen)
    all_run = cols[1].button('Run all 38', key='developer_batch_all', disabled=not consent)
    pending = current and len(current['entries']) < len(current['requested'])
    proceed = cols[2].button('Continue next chunk', key='developer_batch_continue', disabled=not consent or not pending)
    stop = cols[3].button('Stop pending cases', key='developer_batch_stop', disabled=not pending)
    if stop:
        st.session_state['developer_batch_stopped'] = True
        st.info('Stopped between chunks. Completed receipts retained; Continue explicitly resumes them.')
    if selected_run or all_run:
        current = batch.new_batch(list(presets['Complete · 38'] if all_run else chosen))
        st.session_state[STATE] = current
    if (selected_run or all_run or proceed) and current:
        st.session_state.pop(EXPORT, None)
        st.session_state['developer_batch_stopped'] = False
        progress = st.progress(len(current['entries'])/len(current['requested']), text='Starting explicit chunk')
        def update(case_id, status, done, total):
            progress.progress(done/total, text=f'{case_id}: {status} · {done}/{total} attempted')
        try:
            batch.run_chunk(current, session_enabled=consent, limit=chunk,
                should_stop=lambda: st.session_state.get('developer_batch_stopped', False), progress=update)
        except (ValueError, OSError):
            st.error('Batch unavailable: source identity or execution boundary changed. Start a new batch.')
        else:
            st.rerun()  # Refresh pending controls; this rerun cannot evaluate another chunk.
    if not current:
        st.info('No batch evaluated. The complete registry contains 38 cases; discovery is not execution.')
        st.info('AI reviewer OFF / not configured. No model or provider is invoked. Only deterministic receipt triage is available.')
        return
    summaries = [batch.summary(key, current['entries'].get(key, {})) for key in current['requested']]
    st.caption('Retained batch: '+', '.join(current['requested'])+'. Presets configure the next Run; they do not relabel retained results.')
    completed = sum(row['Execution'] == 'COMPLETED' for row in summaries)
    errors = sum(row['Execution'] == 'ERROR' for row in summaries)
    st.write({'Completed': completed, 'Errors': errors, 'Pending': len(summaries)-completed-errors,
              'Retained receipt bytes': current['retained_bytes']})
    category = st.selectbox('Batch results filter', ['All','Changed scores','Changed evidence labels','Suspicious metadata',
        'Withheld','Errors','Unchanged'], key='developer_batch_results_filter')
    def show(row):
        if category == 'All': return True
        if category == 'Errors': return row['Execution'] == 'ERROR'
        if category == 'Changed scores': return row.get('Changed scores', False)
        if category == 'Changed evidence labels': return bool(row.get('Changed labels'))
        if category == 'Suspicious metadata': return bool(row.get('Metadata warnings'))
        if category == 'Withheld': return row.get('Withheld', False)
        return row['Execution'] == 'COMPLETED' and row['Priority'] == 'NORMAL' and not row['Changed scores']
    st.dataframe([r for r in summaries if show(r)], hide_index=True, width='stretch', alt='Per-case synthetic batch statuses, nullable scores, geometry, conflicts and triage')
    inspected = st.multiselect('Inspect completed cases', [key for key in current['requested']
        if current['entries'].get(key, {}).get('status') == 'COMPLETED'], key='developer_batch_inspect')
    for key in inspected:
        entry = current['entries'][key]
        with st.expander('Case '+key+' · findings and multi-requirement review', expanded=False, on_change='rerun') as details:
            if details.open:
                st.json(entry['findings'])
                render_multi_review(entry['result'], 'developer_batch_review_'+key)
    st.info('AI reviewer OFF / not configured. A future advisory reviewer may consume only the sanitized batch schema; '
            'it cannot change labels, scores, sources, approvals or settings. No model call occurs here.')
    text = st.checkbox('Include raw synthetic JD/requirement text in batch exports', value=False, key='developer_batch_export_text')
    export_key = batch.fingerprint([current['revision'], sorted(current['entries']), text])
    saved = st.session_state.get(EXPORT)
    if saved and saved['identity'] != export_key:
        st.session_state.pop(EXPORT, None); saved = None
    if st.button('Prepare batch downloads', key='developer_batch_prepare_export'):
        try:
            saved = {'identity': export_key, 'files': batch.export_bundle(current, include_text=text)}
            st.session_state[EXPORT] = saved
        except (ValueError, OSError):
            st.error('Export unavailable: input identity or size bound failed.')
    if saved:
        for extension, mime in (('csv','text/csv'), ('json','application/json'), ('zip','application/zip')):
            st.download_button('Download batch '+extension.upper(), saved['files'][extension],
                file_name='synthetic_batch_audit.'+extension, mime=mime, key='developer_batch_download_'+extension, on_click='ignore')

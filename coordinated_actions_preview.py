"""Isolated Streamlit development page; only safe fixtures and synthetic evidence."""
import os

# Must precede project imports. No main app startup, database or saved candidate access.
os.environ.update(PYTHON_DOTENV_DISABLED='true', CAPABILITY_RAG_MODE='off',
                  LITELLM_LOCAL_MODEL_COST_MAP='True', STREAMLIT_BROWSER_GATHER_USAGE_STATS='false')
import streamlit as st
from scripts.coordinated_acceptance import parents, scenarios, comparison, analyze
from scripts import coordinated_batch_dashboard as dashboard
from scripts import coordinated_conflict_acceptance as realistic_dashboard

st.set_page_config(page_title='Coordinated-action acceptance', layout='wide')
st.title('Coordinated-action acceptance')
st.caption('Synthetic development preview · Default-OFF production gate · No save action')
revision = dashboard.revision_key()
dashboard.prepare_revision(revision)
if st.session_state.get('acceptance_batch', {}).get('revision', revision) != revision:
    st.session_state.pop('acceptance_batch', None)
    st.warning('Inputs, source code or policy identity changed. Run the batch again.')
if st.session_state.get('realistic_batch', {}).get('revision', revision) != revision:
    st.session_state.pop('realistic_batch', None)


def compact_rows(rows):
    return [{'Row': str(i+1), 'Label': row['match_label'] or 'REVIEW_REQUIRED',
             'Weight': row['group_weight_fraction'],
             'Contribution': (None if row['match_value'] is None else
                              row['group_weight_fraction']*row['match_value'])}
            for i, row in enumerate(rows)]


def show_details(result, checks, diagnostic_key='batch_full_json'):
    st.subheader('Selected acceptance scenario')
    st.caption(str(result['job_id'])+' · '+result['scenario'])
    st.write('Original JD requirement')
    st.write(result['after_rows'][0]['coordinated_action_receipt']['obligation']['raw_parent_text'])
    st.write('Synthetic résumé evidence')
    for text in result['synthetic_evidence']:
        st.write(text)
    for heading, rows in (('Before — original rows', result['before_rows']),
                          ('After — corrected complete parent', result['after_rows'])):
        if not rows:
            continue  # realistic historical labels are observations, not fabricated rows
        st.write(heading)
        st.dataframe(compact_rows(rows), hide_index=True, width='stretch',
                     alt=heading+' with labels, allocation and contribution')
        for i, row in enumerate(rows, 1):
            st.write(str(i)+'. '+row['text'])
    pending = [row for row in result['after']['canonical_requirements']
               if row.get('coordinated_action_receipt', {}).get('disposition') == 'REVIEW_REQUIRED']
    score = result['after']['deterministic_alignment_score']
    if score is None:
        st.warning('Score withheld pending policy review — alignment unavailable')
        for row in pending:
            st.caption('Pending: '+row['text'])
    else:
        st.metric('Synthetic whole-JD alignment', str(score)+'%')
    for affected in result['after']['canonical_requirements']:
        conflict = (affected.get('coordinated_action_receipt') or {}).get('scoped_conflict')
        if not conflict or not conflict['quarantine']:
            continue
        st.warning('Scoped conflict — contribution unavailable: '+affected['text'])
        st.write({'Conflict status': conflict['status'], 'Conflict reason': conflict['reason'],
                  'Selected positive source': conflict['selected_positive']['source']})
        st.write('Selected positive original: '+conflict['selected_positive']['text'])
        st.dataframe([{'Contradictory source': f['negative_original']['source'],
                       'Original text': f['negative_original'].get('original_text', 'Unavailable original text'),
                       'Project/source relationship': f.get('relationship', 'Uncertain source coverage'),
                       'Finding': f['status'], 'Reason': f['reason']}
                      for f in conflict['findings']], hide_index=True, width='stretch',
                     alt='Original contradictory sources and their relationship to the selected positive')
        with st.expander('Scoped conflict and original-occurrence receipts', expanded=False):
            st.json(conflict)
    if result['after'].get('original_source_occurrence_ledger'):
        with st.expander('Original source occurrence coverage', expanded=False):
            st.json(result['after']['original_source_occurrence_ledger'])
    for row in result['after_rows']:
        receipt = row['coordinated_action_receipt']
        st.write({'Native label': receipt['native_label'], 'Capped label': row['match_label'],
                  'Disposition': receipt['disposition'],
                  'Parent allocation': receipt['parent_allocation'],
                  'Contribution': receipt['synthetic_parent_contribution']})
        st.write('Each original source is assessed separately; actions are never joined between rows.')
        st.dataframe([{'Source': p['record']['source'], 'Evidence ID': key,
                       'Supported actions': ', '.join(p['proof'].get('supported_actions', [])),
                       'Missing actions': ', '.join(p['proof'].get('missing_actions', [])),
                       'Technical scope': p['proof'].get('technical_scope'),
                       'Admission': p['admission'],
                       'Selected': key in {r['evidence_id'] for r in row.get('evidence', [])}}
                      for key, p in receipt['proofs'].items()], hide_index=True, width='stretch')
        st.write('Required technical scope: '+receipt['obligation'].get('object', 'Unsupported'))
        exclusion = receipt.get('r1_exclusion')
        if exclusion:
            st.write({'R1 disposition policy': exclusion['policy_version'],
                      'R1 eligible': exclusion['eligible'], 'R1 reason': exclusion['reason']})
            with st.expander('R1 exact original source receipts', expanded=False):
                st.json(exclusion)
        if receipt['stages']:
            st.dataframe([{'Stage': s['stage'], 'Native': s['native_label'], 'Capped': s['capped_label'],
                           'Verified source': s['source_verified']} for s in receipt['stages']],
                         hide_index=True, width='stretch')
        elif not (exclusion or {}).get('eligible'):
            st.info('No admissible source: the filtered scoring stages were not entered. '
                    'Original source and admission receipts remain available below.')
    with st.expander('Independent expectation checks (only exact covered inputs)', expanded=False):
        if checks:
            st.json(checks)
        else:
            st.write('No exact independently reviewed expectation covers this input. No PASS is inferred.')
    with st.expander('Full source-selection, recovery and final-invariant JSON', expanded=False):
        if st.checkbox('Load full selected diagnostic JSON', key=diagnostic_key):
            st.json(result)


st.subheader('Batch overview')
st.caption('This button explicitly evaluates P3 for synthetic inputs only. The production gate stays OFF.')
if st.button('Run all 60 synthetic scenarios', key='run_acceptance_batch', type='primary'):
    progress = st.progress(0.0, text='Preparing synthetic scenarios')
    try:
        st.session_state['acceptance_batch'] = dashboard.run_batch(
            revision, lambda done, total, name: progress.progress(done/total, text=f'{done}/{total} · {name}'))
    except Exception as error:
        st.error('Batch setup failed: '+type(error).__name__+': '+str(error))
    finally:
        progress.empty()

batch = st.session_state.get('acceptance_batch')
if batch:
    stats = dashboard.totals(batch)
    st.markdown(f"**{stats['total']} scenarios** · **DIRECT {stats['DIRECT']}** · "
                f"**WEAK {stats['WEAK']}** · **NONE {stats['NONE']}** · "
                f"**REVIEW_REQUIRED {stats['REVIEW_REQUIRED']}**")
    st.markdown(f"Whole-JD scores withheld: **{stats['withheld']}** · "
                f"Exceptions: **{stats['exceptions']}** · "
                f"Stage 2E reference mismatches: **{stats['reference_mismatches']}**")
    st.caption(f"Historical Stage 2E reference: {stats['reference_mismatches']} differences; "
               'the 14 R1 changes are expected and the historical reference is preserved.')
    st.caption(f"Current Stage 2G expectations: {stats['current_mismatches']} mismatches. "
               'Historical agreement and current expectation agreement are shown separately.')
    st.caption(f"Independent receipt expectations: {stats['independent_agreements']}/{stats['independent_checks']} "
               f"checks agree across {stats['independent_covered_cases']} scenarios. "
               'Uncovered scenarios are not automatically marked PASS.')
    if stats['current_mismatches'] or stats['unexpected_historical_changes']:
        st.error('Unexpected acceptance difference — expectations have not been updated.')
    if stats['reference_mismatches']:
        with st.expander('Historical Stage 2E differences (including expected R1 changes)', expanded=False):
            st.dataframe([{**r, 'Expected': dashboard.reference_expectation(r['Job'].split(' / ')[1], r['Scenario'])}
                          for r in batch['rows'] if r['Stage 2E reference'] == 'MISMATCH'])
    if stats['independent_agreements'] != stats['independent_checks']:
        st.error('An independent expectation disagrees. Inspect the selected source receipts.')
    if batch['errors']:
        st.error('Scenario exceptions are separate from policy review outcomes.')
        with st.expander('Exceptions', expanded=False):
            st.dataframe(batch['errors'], hide_index=True)
    jobs = st.multiselect('Job / artifact filter', sorted({r['Job'] for r in batch['rows']}), key='batch_jobs')
    names = st.multiselect('Scenario filter', list(dict.fromkeys(r['Scenario'] for r in batch['rows'])), key='batch_scenarios')
    dispositions = st.multiselect('Disposition filter', sorted({r['Disposition'] for r in batch['rows']}), key='batch_dispositions')
    filtered = dashboard.filter_rows(batch['rows'], jobs, names, dispositions)
    st.caption(f'{len(filtered)} of {len(batch["rows"])} scenarios shown. Select a row to inspect its stored analysis.')
    if filtered:
        # A filter-specific widget key prevents a previous row offset selecting
        # a different case after filtering; detail lookup always uses stable IDs.
        import hashlib
        grid_key = 'batch_grid_'+hashlib.sha256((revision+str([r['Case'] for r in filtered])).encode()).hexdigest()[:16]
        st.session_state['batch_grid_key'] = grid_key
        display = [{**r, 'Alignment %': ('Unavailable' if r.get('Alignment %') is None else str(r['Alignment %'])+'%')}
                   for r in filtered]
        event = st.dataframe(display, hide_index=True, width='stretch', height=440,
            key=grid_key, on_select='rerun', selection_mode='single-row',
            column_config={'Case': None,
                'Job': st.column_config.TextColumn('Job / artifact', width='small', pinned=True),
                'Scenario': st.column_config.TextColumn(width='medium', pinned=True),
                'Before rows': st.column_config.NumberColumn('Rows before', width='small'),
                'After rows': st.column_config.NumberColumn('Rows after', width='small'),
                'Before contribution': st.column_config.NumberColumn('Before credit', format='%.2f', width='small'),
                'After contribution': st.column_config.NumberColumn('After credit', format='%.2f', width='small'),
                'Alignment %': st.column_config.TextColumn('JD alignment', width='small', help='Unavailable for withheld or failed outcomes'),
                'Missing actions': st.column_config.TextColumn('Missing actions', width='medium')},
            alt='All synthetic acceptance outcomes; click one row to inspect its original receipts')
        keys = [r['Case'] for r in filtered]
        lookup = {r['Case']: r for r in filtered}
        if st.session_state.get('batch_inspect') not in keys:
            st.session_state['batch_inspect'] = keys[0]
        selected_rows = event.selection.rows
        click = (grid_key, tuple(selected_rows))
        if selected_rows and click != st.session_state.get('batch_last_click'):
            st.session_state['batch_inspect'] = keys[selected_rows[0]]
        st.session_state['batch_last_click'] = click
        chosen = st.selectbox('Inspect a result (also selectable in the table)', keys,
            format_func=lambda key: lookup[key]['Job']+' — '+lookup[key]['Scenario'], key='batch_inspect')
        if chosen in batch['details']:
            show_details(batch['details'][chosen], batch['expectations'][chosen])
        else:
            st.error(next(e['Exception'] for e in batch['errors'] if e['Case'] == chosen))
    else:
        st.info('No scenarios match these filters.')
else:
    st.info('Run the batch to populate the overview. No batch analyses run on page load.')

st.divider()
st.subheader('Stage 2I — realistic multi-record profiles')
st.caption('The original Stage 2H profiles are unchanged. Stage 2I expectations are a separate independent delta.')
if st.button('Run all 38 realistic profiles', key='run_realistic_batch'):
    with st.spinner('Evaluating synthetic originals and scoped conflicts'):
        st.session_state['realistic_batch'] = realistic_dashboard.run_batch(revision)
realistic_batch = st.session_state.get('realistic_batch')
if realistic_batch:
    st.write({'Realistic outcomes': realistic_batch['counts'], 'Whole-JD withheld': realistic_batch['withheld'],
              'Exceptions': len(realistic_batch['errors']),
              'Stage 2I expectation mismatches': realistic_batch['expectation_mismatches']})
    if realistic_batch['errors']:
        st.error('Realistic scenario exceptions remain separate from policy review.')
        st.json(realistic_batch['errors'])
    job_filter = st.multiselect('Realistic job filter', sorted({r['Job'] for r in realistic_batch['rows']}), key='realistic_jobs')
    disposition_filter = st.multiselect('Realistic disposition filter', sorted({r['Disposition'] for r in realistic_batch['rows']}), key='realistic_dispositions')
    realistic_rows = [r for r in realistic_batch['rows'] if (not job_filter or r['Job'] in job_filter)
                      and (not disposition_filter or r['Disposition'] in disposition_filter)]
    if realistic_rows:
        import hashlib
        real_grid = 'realistic_grid_'+hashlib.sha256((revision+str([r['Case'] for r in realistic_rows])).encode()).hexdigest()[:16]
        event = st.dataframe([{**r, 'Alignment %': 'Unavailable' if r['Alignment %'] is None else str(r['Alignment %'])+'%'}
                              for r in realistic_rows], hide_index=True, width='stretch',
            key=real_grid, selection_mode='single-row', on_select='rerun',
            column_config={'Case': st.column_config.TextColumn(width='small', pinned=True),
                           'Scenario': st.column_config.TextColumn(width='large')},
            alt='All realistic profiles with actual current outcomes and independent historical/current expectations')
        keys = [r['Case'] for r in realistic_rows]
        if st.session_state.get('realistic_inspect') not in keys:
            st.session_state['realistic_inspect'] = keys[0]
        click = (real_grid, tuple(event.selection.rows))
        if event.selection.rows and click != st.session_state.get('realistic_last_click'):
            st.session_state['realistic_inspect'] = keys[event.selection.rows[0]]
        st.session_state['realistic_last_click'] = click
        chosen = st.selectbox('Inspect realistic profile', keys, key='realistic_inspect')
        show_details(realistic_batch['details'][chosen], [], diagnostic_key='realistic_full_json')
    else:
        st.info('No realistic profiles match these filters.')
st.divider()
st.subheader('Single-scenario comparison')
available = parents()
choices = [str(p['job_id'])+' — '+p['obligation']['object_family'] for p in available]
selected = st.selectbox('Source parent', choices)
parent = available[choices.index(selected)]
scenario = st.selectbox('Synthetic scenario', list(scenarios(parent)))
enabled = st.toggle('Evaluate gated P3 correction', value=False)
st.write(parent['original_raw_parent'])
st.write({'Synthetic evidence': scenarios(parent)[scenario]})


@st.cache_data(max_entries=80, show_spinner=False)
def evaluate(pid, name, enable, revision):
    p = next(p for p in parents() if p['parent_occurrence_id'] == pid)
    if not enable:
        before = analyze(p, scenarios(p)[name], False)
        return {'before_rows': [r for r in before['canonical_requirements']
                                if r.get('scoring_parent_occurrence_id') == pid]}
    return comparison(p, name)


result = evaluate(parent['parent_occurrence_id'], scenario, enabled, revision)
left, right = st.columns(2)
with left:
    st.subheader('Before — existing analysis')
    st.dataframe(compact_rows(result['before_rows']), hide_index=True, width='stretch')
    for i, row in enumerate(result['before_rows'], 1):
        st.write(str(i)+'. '+row['text'])
with right:
    st.subheader('After — gated correction')
    if not enabled:
        st.info('Feature OFF. Enable the synthetic comparison to inspect P3 results.')
    else:
        after = result['after']
        if after['deterministic_alignment_score'] is None:
            st.warning('Score withheld pending policy review')
        else:
            st.success('All numeric dispositions governed for this synthetic input')
            st.metric('Synthetic JD alignment', str(after['deterministic_alignment_score'])+'%')
        for row in result['after_rows']:
            receipt = row['coordinated_action_receipt']
            st.write(row['text'])
            st.write({'Native label': receipt['native_label'], 'P3 label': row['match_label'],
                      'Status': receipt['disposition'], 'Parent allocation': receipt['parent_allocation'],
                      'Contribution': receipt['synthetic_parent_contribution']})
            st.dataframe([{'Source': p['record']['source'], 'Evidence ID': key,
                           'Supported': ', '.join(p['proof'].get('supported_actions', [])),
                           'Missing': ', '.join(p['proof'].get('missing_actions', [])),
                           'Technical scope': p['proof'].get('technical_scope'),
                           'Admission': p['admission']}
                          for key, p in receipt['proofs'].items()])
            with st.expander('Original sources, scope and stage receipts'):
                st.json(receipt)
        st.caption('Development-only identity: '+after['scoring_version']+'. Persistence is blocked.')

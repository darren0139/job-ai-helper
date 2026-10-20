"""Standalone developer-only comparison; no Job Finder or application startup."""
import os
os.environ.update(PYTHON_DOTENV_DISABLED='true', CAPABILITY_RAG_MODE='off',
                  LITELLM_LOCAL_MODEL_COST_MAP='True', STREAMLIT_BROWSER_GATHER_USAGE_STATS='false')

import hashlib
import streamlit as st
from job_discovery import coordinated_preview as controller
from job_discovery.coordinated_preview_model import export_comparison, Label
from scripts.coordinated_job_match_preview_inputs import synthetic_cases, preview_inputs

st.set_page_config(page_title='Developer Job Match comparison', layout='wide')
st.title('Developer Job Match comparison')
st.caption('Synthetic library simulation only · Published v1.17 stays OFF · No saved matches or Application Session changes')
st.caption('Run separately with: streamlit run coordinated_job_match_preview.py')
enabled = st.toggle('Enable developer comparison', value=False, key='developer_preview_enabled')
cases = synthetic_cases()
case_id = st.selectbox('Synthetic profile', [c['id'] for c in cases], key='developer_case',
                       format_func=lambda value: value+' — '+next(c['theme'] for c in cases if c['id']==value))
request = controller.prepare_comparison(**preview_inputs(case_id))
stored = st.session_state.get(controller.PREVIEW_SESSION_KEY)
if stored is not None and stored.identity != request.identity:
    st.session_state.pop(controller.PREVIEW_SESSION_KEY, None)
    st.info('Inputs or preview policy changed. Explicitly run the comparison again.')
if st.button('Run developer comparison', key='run_developer_comparison', disabled=not enabled):
    try:
        with st.spinner('Comparing separate published and gated receipts'):
            st.session_state[controller.PREVIEW_SESSION_KEY] = controller.run_comparison(request, developer_enabled=enabled)
    except (ValueError, TypeError, KeyError) as error:
        st.error('Comparison unavailable: '+str(error))

result = st.session_state.get(controller.PREVIEW_SESSION_KEY)
if not enabled:
    st.info('Developer comparison OFF. No analysis runs on page load.')
elif result is None:
    st.info('Run the comparison to inspect the synthetic evidence. No saved analysis is loaded.')
else:
    result = controller.retained_comparison(result, request)
    st.caption('Evidence authority: '+result.authority+' · Not an uploaded-document score · Never eligible for Job Match ranking')
    left, right = st.columns(2)
    for column, heading, view in ((left,'Published OFF result',result.published), (right,'Gated source-aware result',result.gated)):
        with column:
            st.subheader(heading)
            st.caption(view.scoring_version)
            st.write('Review-required requirements: '+str(view.review_count))
            if view.score_available:
                st.metric('Synthetic alignment', str(view.alignment)+'%')
            else:
                st.warning('Whole-JD alignment unavailable — review required. No overall percentage or rating band.')
            st.write(view.summary()['counts'])
    side = st.radio('Requirement receipt', ['Gated', 'Published OFF'], horizontal=True, key='developer_receipt_side')
    view = result.gated if side == 'Gated' else result.published
    labels = st.multiselect('Labels', [label.value for label in Label], key='developer_label_filter')
    rows = [r for r in view.requirements if not labels or r.label.value in labels]
    if rows:
        grid_key = 'developer_grid_'+hashlib.sha256((result.identity+side+str([r.requirement_id for r in rows])).encode()).hexdigest()[:16]
        event = st.dataframe([r.table_record() for r in rows], key=grid_key, width='stretch', hide_index=True,
            on_select='rerun', selection_mode='single-row',
            column_config={'Requirement':st.column_config.TextColumn(width='large'),
                           'Credit':st.column_config.NumberColumn(help='Null means unavailable; zero is governed NONE.')},
            alt='Requirement labels, allocation and nullable governed credit')
        keys = [r.requirement_id for r in rows]
        if st.session_state.get('developer_inspect') not in keys:
            st.session_state['developer_inspect'] = keys[0]
        click = (grid_key,tuple(event.selection.rows))
        if event.selection.rows and click != st.session_state.get('developer_last_click'):
            st.session_state['developer_inspect'] = keys[event.selection.rows[0]]
        st.session_state['developer_last_click'] = click
        selected = st.selectbox('Inspect requirement',keys,key='developer_inspect',
            format_func=lambda key: next(r.text for r in rows if r.requirement_id==key))
        row = next(r for r in rows if r.requirement_id==selected)
        st.subheader(row.text)
        st.write({'Label':row.label.value,'Native label':row.native_label,'Disposition':row.disposition,
                  'Allocation':row.allocation,'Contribution':'Unavailable' if row.contribution is None else row.contribution,
                  'Supported actions in selected original':list(row.supported_actions),
                  'Missing/unproven actions':list(row.missing_actions),'Technical scope':row.technical_scope})
        if row.label.value == 'REVIEW_REQUIRED':
            st.warning('Contribution unavailable. Missing support is not a finding that the candidate lacks experience.')
        if row.evidence:
            st.write('Selected original evidence')
            st.dataframe(list(row.evidence),hide_index=True,width='stretch',alt='Selected original source text and evidence ID')
        if row.conflict and row.conflict.get('quarantine'):
            st.warning('Scoped contradiction or uncertain original scope: '+row.conflict['reason'])
            st.dataframe([{'Source':f['negative_original']['source'],
                'Original text':f['negative_original'].get('original_text','Unavailable'),
                'Relationship':f.get('relationship','Uncertain coverage'),'Reason':f['reason']}
                for f in row.conflict['findings']],hide_index=True,width='stretch',alt='Contrary originals with source and project relationship')
        with st.expander('Original proofs, missing actions and conflict receipts', expanded=False):
            st.json(row.receipt)
        with st.expander('Canonical library origins and raw alias coverage', expanded=False):
            st.json(result.gated_analysis['original_source_occurrence_ledger'])
    else:
        st.info('No requirements match the selected labels.')
    with st.expander('Export developer comparison', expanded=False):
        st.caption('Separate preview schema. Null stays null. Persistence is rejected.')
        st.download_button('Download comparison JSON',export_comparison(result),
            file_name='developer_job_match_comparison.json',mime='application/json',on_click='ignore')

"""Normal-app Benchmark Lab. Execution is explicit; receipts are read-only by default."""
from tailoring.bullet_choice_estimated import term_labels
import csv
from io import StringIO, BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from tailoring.bullet_choice_lab import DATA, ROOT, MAX_CASES, load_dataset, run_benchmarks, save_run, compare_runs

PAGE='Bullet-Choice Benchmark Lab'


def exports(run):
    text=StringIO();writer=csv.writer(text)
    writer.writerow(['case_id','dataset','split','expected_control','estimated_outcome','pass','native_impact'])
    for r in run['rows']:writer.writerow([r['case_id'],r['dataset'],r['split'],r['expected'],r['estimated']['outcome'],r['pass'],r['native_impact']])
    payload=json.dumps(run,indent=2,ensure_ascii=False).encode('utf-8');csv_data=text.getvalue().encode('utf-8-sig')
    buffer=BytesIO()
    with ZipFile(buffer,'w',ZIP_DEFLATED) as z:
        z.writestr('run.json',payload);z.writestr('results.csv',csv_data)
        z.writestr('availability.json',json.dumps(run.get('optional_data',{}),indent=2))
        z.writestr('limits.txt','Controlled agreement is not real-world accuracy. Estimates, verified evidence and native outcomes are separate. No native experiment was performed by this run.')
    return payload,csv_data,buffer.getvalue()


def render_estimated(st, result):
    st.info('Estimated JD relevance · '+result['outcome'])
    st.write(result['reason'])
    st.caption('Wording-only estimate · '+result['version']+' · not verified experience, native score credit or optimizer input.')
    words=result.get('word_counts',{})
    if words:
        st.caption(f"Words: Base {words['base']}, Library {words['library']}. Word efficiency is secondary to useful support; no page-fit benefit has been measured.")
    for row in result.get('requirements',[]):
        with st.expander(row['importance'].replace('_',' ').title()+' · '+row['text']):
            for role in ('base','library'):
                value=row[role]
                st.write(role.title()+' · '+value['coverage'].replace('_',' ')+' · '+value['action_status'].replace('_',' '))
                st.caption('Matched wording facets: '+(', '.join(term_labels(value['lexical_terms'])) or 'None'))
                st.caption('Missing wording facets: '+(', '.join(term_labels(value['missing_terms'])) or 'None'))
                if value.get('alternative_satisfied'):
                    st.caption('One-or-more alternative matched; optional alternatives: '+', '.join(term_labels(value['optional_alternatives']))+'. Keyword overlap does not verify proficiency.')
                if value.get('alternative_satisfied'):
                    st.caption('One-or-more alternative matched; optional alternatives, not missing capabilities: '+', '.join(term_labels(value['optional_alternatives']))+'. Keyword recognition does not verify proficiency.')
                if value.get('alternative_satisfied'):
                    st.caption('One-or-more alternative matched; optional alternatives: '+(', '.join(term_labels(value['optional_alternatives'])) or 'None')+'. This is wording relevance, not verified proficiency.')
                if value.get('capability_id'):st.caption('Taxonomy hint: '+value['capability_id']+' · '+str(value['taxonomy_label'])+'; not authoritative credit.')
            if row['already_supported_elsewhere_estimate']:st.caption('Estimated coverage already present in surrounding selected wording.')
    st.caption(result.get('limits',''))


def render_page(st):
    st.title(PAGE)
    st.caption('Local, explicit and bounded. Controlled benchmark agreement is not proven real-world accuracy. No native rendering or model calls.')
    try:packet=load_dataset()
    except (ValueError,OSError) as exc:st.error(str(exc));return
    if packet['optional_data']['real']['status']=='unavailable':
        st.warning('20 real cases unavailable: optional private fixture is not installed. Synthetic and corpus controls remain available. Missing real cases are not passes; saved history is historical only.')
    cases={c['id']:c for c in packet['cases']}
    runs=sorted((DATA/'runs').glob('*.json'),reverse=True) if (DATA/'runs').exists() else []
    latest=None
    if runs:
        pending=st.session_state.pop('bcl_pending_saved',None)
        if pending and Path(pending) in runs:
            st.session_state['bcl_saved_run']=Path(pending)
        picked=st.selectbox('Saved benchmark run / version',runs,format_func=lambda p:p.name,key='bcl_saved_run')
        try:latest=json.loads(picked.read_text(encoding='utf-8'))
        except (ValueError,OSError):st.warning('Latest saved run is unreadable; run a bounded batch to create a fresh receipt.')
    tabs=st.tabs(['Benchmark Overview','Run Benchmarks','Test Results','JD & Bullet Comparison Explorer','Best-of Optimizer Evaluation','Previous vs Current','Exports and Optional Review'])
    with tabs[1]:
        st.subheader('Run Benchmarks')
        datasets=st.multiselect('Datasets',['synthetic','corpus','real'],default=['synthetic','corpus','real'],key='bcl_datasets')
        split=st.selectbox('JD group',['All','development','held_out','fresh_validation','observation'],key='bcl_split')
        ids=st.multiselect('Specific cases (optional)',list(cases),key='bcl_ids')
        limit=st.number_input('Maximum cases',min_value=1,max_value=MAX_CASES,value=MAX_CASES,key='bcl_limit')
        selectors=st.checkbox('Exercise actual Best-of selector boundary',value=True,key='bcl_selectors')
        all_button=st.button('Run All Benchmarks',type='primary',key='bcl_all')
        selected_button=st.button('Run selected benchmarks',key='bcl_selected')
        if all_button or selected_button:
            with st.spinner('Running bounded local benchmarks…'):
                try:
                    result=run_benchmarks(**({} if all_button else dict(datasets=datasets,case_ids=ids,split=None if split=='All' else split,limit=int(limit),selectors=selectors)))
                    saved=save_run(result)
                except (ValueError,OSError) as exc:st.error('Benchmark failed closed: '+str(exc))
                else:
                    st.session_state['bcl_pending_saved']=str(saved);st.session_state['bcl_last_path']=str(saved);st.rerun()
        st.caption('Run All is bounded to 116 comparisons and seven selector contracts; 65-second batch deadline, eight-second subprocess limit per selector. Cached/displayed results never rerun on refresh.')
    if not latest:
        with tabs[0]:st.info('No saved results. Open Run Benchmarks and choose Run All Benchmarks.')
        return
    summary=latest['summary']
    with tabs[0]:
        st.subheader('Benchmark Overview')
        with st.container(horizontal=True):
            st.metric('Executed / available',f"{latest['executed']} / {sum(latest['available'].values())}")
            st.metric('Controlled correct / evaluated',f"{summary['correct']} / {summary['controlled_denominator']}")
            st.metric('Controlled incorrect',summary['incorrect'])
            st.metric('Withheld / executed',f"{summary['withheld']} / {latest['executed']}")
        st.write(f"Decisive controlled agreement: {summary['decisive_correct']} / {summary['decisive_denominator']}. Independently reviewed real cases: {summary['independently_reviewed_real']}. Real-world accuracy: unavailable.")
        st.caption(f"Abstentions: {summary['withheld']} / {latest['executed']} executed. Unsupported capability assertion cases: {summary.get('unsupported_capability_assertion_cases','not recorded')}; Core expected-coverage failures: {summary.get('required_core_expected_coverage_failures','not recorded')}; negative-control failures: {summary.get('negative_control_failures','not recorded')}. These are controlled-rule checks, not independently verified factual accuracy.")
        st.caption('Version '+latest['evaluator_version']+' · dataset '+latest['dataset_version']+' · '+latest['dataset_sha256'])
        st.write('Available datasets',dict(latest['available']))
        st.write('Corpus source inventory',packet['cohort_inventory'])
        st.caption(packet['expectation_authority']);st.caption(packet['split_policy'])
        st.caption('Displayed saved result: '+str(picked))
    with tabs[2]:
        st.subheader('Test Results')
        for sp in ('development','held_out','fresh_validation','observation'):
            group=[r for r in latest['rows'] if r['split']==sp]
            st.write(f"{sp}: {sum(r['pass'] is True for r in group)} passed, {sum(r['pass'] is False for r in group)} failed, {sum(r['pass'] is None for r in group)} unlabelled / {len(group)} executed.")
        show=st.selectbox('Result filter',['All','Failed','Withheld','Unlabelled real'],key='bcl_result_filter')
        failure=st.selectbox('Failure type',['All','Estimated-relevance evaluator / controlled coverage'],key='bcl_failure_type')
        rows=[r for r in latest['rows'] if (failure=='All' or r['failure_type']==failure) and (show=='All' or show=='Failed' and r['pass'] is False or show=='Withheld' and r['estimated']['outcome']=='Indeterminate' or show=='Unlabelled real' and r['expected'] is None)]
        for row in rows[:MAX_CASES]:
            with st.expander(row['case_id']+' · '+str(row['pass'])+' · '+row['estimated']['outcome']):
                if row['case_id'] not in cases:
                    st.caption('Historical case unavailable: optional private source fixture is not installed. Not evaluated in the current dataset.')
                    continue
                case=cases[row['case_id']]
                st.write('JD: '+case['jd_id'])
                for requirement in case['requirements']:st.write(requirement['importance']+' · '+requirement['text'])
                st.write('Base: '+case['base']);st.write('Library: '+case['library'])
                st.write('Expected controlled outcome: '+str(row['expected'])+'; actual: '+row['estimated']['outcome'])
                st.write(row['estimated']['reason']);st.caption(row['failure_type'] or 'No controlled failure recorded; real cases remain unlabelled.')
                st.caption('Missing expected coverage: '+(', '.join(row['missing_expected_coverage']) or 'None'))
                if row['pass'] is False:
                    st.caption('Current failure remains. Inspect performed-action recognition and matched/missing facets in the explorer. No automatic fix or selector objective change was applied.')
    with tabs[3]:
        st.subheader('JD & Bullet Comparison Explorer')
        dataset=st.selectbox('Explorer dataset',['synthetic','corpus','real'],key='bcl_explorer_dataset')
        categories=['All']+sorted({c['category'] for c in cases.values() if c['dataset']==dataset})
        category=st.selectbox('JD category',categories,key='bcl_category_'+dataset)
        executed={r['case_id']:r for r in latest['rows']}
        available=[k for k,c in cases.items() if c['dataset']==dataset and k in executed and (category=='All' or c['category']==category)]
        if available:
            cid=st.selectbox('Case',available,key='bcl_case_'+dataset);case=cases[cid];row=executed[cid]
            st.write(case['jd_id']+' · '+case['category']+' · '+case['split'])
            with st.container(horizontal=True):
                with st.container(border=True):st.markdown('**Base wording**');st.write(case['base'])
                with st.container(border=True):st.markdown('**Library wording**');st.write(case['library'])
            if dataset!='real':st.caption('Synthetic test wordings; not applicant experience. Expected: '+case['expected']+' · '+case['rationale'])
            render_estimated(st,row['estimated'])
            with st.expander('Full actual JD and requirement source'):
                st.text(case['jd_text']);st.json(case['source']);st.caption(row['requirement_origin'])
            st.markdown('#### Verified Evidence')
            if row['verified']:
                st.write('Saved verified diagnostic: '+row['verified']['outcome'])
                st.caption('Conditional on recorded document citation exposure; this is not a new attestation or fair observation of every alternative.')
                for role in ('base','library'):
                    original=case['source_case'][role]
                    st.write(role.title()+' provenance: '+', '.join(original['sources']))
                    for link in original['jd_links']:
                        if link.get('native_evidence'):st.write(link['text']+' ['+link['importance']+']');st.json(link['native_evidence'])
                st.write('Saved membership',row['saved_membership'])
            else:st.caption('No authoritative applicant evidence supplied for synthetic controls; none is fabricated.')
            st.markdown('#### Measured Native Impact');st.write(row['native_impact'])
        else:st.info('Dataset not executed in this saved batch.')
    with tabs[4]:
        st.subheader('Best-of Optimizer Evaluation')
        st.caption('Real production build_certified_optimization, explicit controlled saved-link evaluator seam. These are selection-rule conformance tests, not semantic linking accuracy or native document verification.')
        st.write(f"{summary['selector_pass']} passed; {summary['selector_fail']} failed; {summary['selector_unavailable']} unavailable / {len(latest['selector_results'])} requested contracts.")
        for trial in latest['selector_results']:
            with st.expander(trial['case_id']+' · '+str(trial['pass'])):
                st.write(trial.get('scope',trial.get('reason','')));st.write('Exact selected wording',trial.get('membership',[]));st.json(trial)
        native=ROOT/'reports/v37_real_bullet_quality/native_trial.json'
        if native.exists():
            with st.expander('Existing saved native whole-document experiment — not rerun'):
                saved=json.loads(native.read_text(encoding='utf-8'));result=saved['result']
                st.write(f"App156 existing fitted {result['a_score']} → candidate {result['b_score']}; winner {result['winner']}.")
                st.caption('Selected Base comparison unavailable. This whole-document tie is not any bullet causal delta. No automatic approval.');st.json(saved['artifact_checks'])
    with tabs[5]:
        st.subheader('Previous vs Current')
        earlier=[p for p in runs if p<picked]
        if earlier:
            previous=st.selectbox('Previous saved run',earlier[:15],format_func=lambda p:p.name,key='bcl_previous')
            st.json(compare_runs(json.loads(previous.read_text(encoding='utf-8')),latest))
        else:st.info('Only one saved run; no compatible previous/current comparison yet.')
        st.caption('Old citation-only v1.1 is a different assessment mode; its abstentions are not a competitive accuracy baseline. Initial wording-v1 baseline is saved separately for compatible regression checks.')
    with tabs[6]:
        st.subheader('Exports and Optional Review')
        payload,table,bundle=exports(latest)
        st.download_button('Download benchmark JSON',data=payload,file_name='bullet_choice_run.json',mime='application/json',key='bcl_json')
        st.download_button('Download results CSV',data=table,file_name='bullet_choice_results.csv',mime='text/csv',key='bcl_csv')
        st.download_button('Download benchmark ZIP',data=bundle,file_name='bullet_choice_run.zip',mime='application/zip',key='bcl_zip')
        cid=st.selectbox('Optional case review',list(cases),key='bcl_review_case')
        label=st.selectbox('Optional owner label',['Not reviewed','Base stronger','Library stronger','Equivalent','Complementary','Insufficient evidence'],key='bcl_owner_label')
        notes=st.text_area('Reviewer notes',key='bcl_owner_notes',max_chars=4000)
        if st.button('Save separate owner review',disabled=label=='Not reviewed',key='bcl_save_review'):
            import uuid
            directory=DATA/'reviews';directory.mkdir(exist_ok=True)
            (directory/(uuid.uuid4().hex+'.json')).write_text(json.dumps({'case_id':cid,'dataset_sha256':latest['dataset_sha256'],'owner_label':label,'notes':notes,'authority':'optional owner input; never generated expectation'},indent=2),encoding='utf-8')
            st.success('Review saved separately. Frozen expectations and benchmark metrics unchanged.')

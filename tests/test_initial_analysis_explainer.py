from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tailoring import initial_analysis_explainer as explainer
from tailoring.phase8_score_explainability import build_score_breakdown
from tests import test_shared_application_session_identity as shared
from tests.test_phase8_score_explainability import row
from job_discovery.matching import current_match_versions
from tests.governed_review_fixtures import isolated_taxonomy


def analysis():
    versions = current_match_versions()
    return {"deterministic_alignment_score": 73,
            "scoring_version": versions['scoring_version'],
            "capability_taxonomy_version": versions['taxonomy_version'],
            "technology_registry_version": versions['technology_registry_version'],
            "jd_structure_inference_version": 'native-generation',
            "technology_registry_resolution_version": 'native-resolution',
            "canonical_requirements": [row('a','Required direct','required','direct',1,5),
                                       row('b','Core transferable','core','transferable',.55,3),
                                       row('c','Preferred weak','preferred','weak',.2,2)]}


def receipt(native=None):
    return explainer.build_analysis_receipt(native or analysis(), raw_jd_text='A fixed exact job description',
        provenance='JOB_FINDER_INITIAL_MATCH', identity={'application_id':7})


class InitialAnalysisFormatterTests(unittest.TestCase):
    def test_job_finder_reuses_reviewed_taxonomy_without_duplicate_heading(self):
        from unittest.mock import Mock
        from tailoring.initial_analysis_explainer_ui import render_job_finder_explainer
        fixture=Path(__file__).resolve().parent/'fixtures'/'per_jd_scoring_audit.json'
        bundle=json.loads(fixture.read_text(encoding='utf-8'))
        job=next(j for j in bundle['snapshot']['audit']['corpus']['jobs'] if j['job_id']==163)
        native=job['baseline_stable_analysis']
        direct=next(r for r in native['canonical_requirements'] if r['match_label']=='direct')
        reviewed={'proven_gaps':[{'requirement_id':direct['requirement_id']}], 'routes':[]}
        st=Mock()
        st.columns.return_value=[Mock() for _ in range(4)]
        st.expander.return_value.__enter__=Mock()
        st.expander.return_value.__exit__=Mock(return_value=False)
        with patch('tailoring.initial_analysis_explainer_ui.render_jd_taxonomy_status') as render_taxonomy:
            render_job_finder_explainer(st, {'id':1,'discovered_job_id':163,'stable_analysis':native},
                job['frozen_inputs']['raw_jd_text'], taxonomy=reviewed)
        render_taxonomy.assert_not_called()
        st.warning.assert_not_called()
        displayed=st.dataframe.call_args.args[0]
        row=next(r for r in displayed if r['Requirement ID']==direct['requirement_id'])
        self.assertEqual(row['Knowledge'],'PROVEN_TAXONOMY_GAP')
        self.assertEqual(row['Evidence'],'direct')

    def test_nac_reviewed_gap_and_direct_are_independent_in_ui(self):
        # The reviewed coverage receipt below belongs to the frozen v1.5 artifact.
        self.enterContext(isolated_taxonomy())
        from streamlit.testing.v1 import AppTest
        fixture=Path(__file__).resolve().parent/'fixtures'/'per_jd_scoring_audit.json'
        bundle=json.loads(fixture.read_text(encoding='utf-8'))
        job=next(j for j in bundle['snapshot']['audit']['corpus']['jobs'] if j['job_id']==163)
        view=explainer.build_analysis_receipt(job['baseline_stable_analysis'],raw_jd_text=job['frozen_inputs']['raw_jd_text'],
            provenance='JOB_FINDER_INITIAL_MATCH',identity={'discovered_job_id':163})
        app=AppTest.from_string('''
import streamlit as st
from tailoring.initial_analysis_explainer_ui import render_analysis_receipt
render_analysis_receipt(st,st.session_state['receipt'])
''',default_timeout=30)
        app.session_state['receipt']=view
        app.session_state['tm_coverage_receipt']=bundle
        with patch('taxonomy_discovery.coverage_presentation.maintenance.currentness',return_value={'current':True,'blockers':[]}):
            app.run()
        self.assertFalse(app.exception)
        table=next(frame.value for frame in app.dataframe if 'Analysis status' in frame.value.columns)
        gaps=table[table['Knowledge']=='PROVEN_TAXONOMY_GAP']
        self.assertEqual(len(gaps),2)
        self.assertTrue(all(gaps['Evidence']=='direct'))
        self.assertFalse(any('Global' in m.label for m in app.metric))

    def test_all_frozen_34_and_18_controls_preserve_native_semantics(self):
        fixtures=Path(__file__).resolve().parent/'fixtures'
        controls=json.loads((fixtures/'initial_analysis_controls.json').read_text(encoding='utf-8'))
        bundle=json.loads((fixtures/'per_jd_scoring_audit.json').read_text(encoding='utf-8'))
        native={(j['job_id'],r['requirement_id']):r for j in bundle['snapshot']['audit']['corpus']['jobs']
                for r in j['baseline_stable_analysis']['canonical_requirements']}
        self.assertEqual(len(controls['ambiguous']),34)
        for control in controls['ambiguous']:
            source=native[control['job_id'],control['requirement_id']]
            original=deepcopy(source)
            result=explainer.explain_requirement(source)
            self.assertEqual(result['state'],'UNKNOWN_REVIEW_PENDING')
            self.assertEqual(source,original)
            self.assertEqual(source['match_label'],'none')
        self.assertEqual(len(controls['positive_controls']),18)
        labels=[]
        for control in controls['positive_controls']:
            source=native[control['job_id'],control['requirement_id']]
            original=deepcopy(source)
            result=explainer.explain_requirement(source)
            labels.append(source['match_label'])
            self.assertEqual(result['state'],'MATCHED_'+control['evidence_label'].upper())
            self.assertIn('whole-parent completeness is not inferred',result['evidence_scope'])
            self.assertEqual(source,original)
        self.assertEqual(labels.count('transferable'),17)
        self.assertEqual(labels.count('direct'),1)

    def test_review_pending_streamlit_table_does_not_expose_rejected_item(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_string('''
import streamlit as st
from tailoring.initial_analysis_explainer_ui import render_analysis_receipt
render_analysis_receipt(st,st.session_state['receipt'])
''',default_timeout=30)
        view=receipt()
        view['requirements'][2]['native']['rejected_candidate']={'text':'PRIVATE REJECTED ITEM'}
        app.session_state['receipt']=view
        app.run()
        self.assertFalse(app.exception)
        table=next(frame.value for frame in app.dataframe if 'Analysis status' in frame.value.columns)
        self.assertEqual(table.iloc[2]['Analysis status'],'Review pending')
        self.assertNotIn('PRIVATE REJECTED ITEM',str(table))
        self.assertIn(explainer.PENDING,table.iloc[2]['Explanation'])

    def test_saved_score_evidence_ids_and_contributions_unchanged(self):
        native = analysis()
        native['canonical_requirements'][0]['evidence'][0].update(evidence_id='evidence-1',source='resume')
        original = deepcopy(native)
        view = receipt(native)
        self.assertEqual(view['score'],73)
        self.assertEqual(native,original)
        points = build_score_breakdown(native)['requirements']
        self.assertEqual([r['contribution'] for r in view['requirements']],points)
        self.assertEqual([r['native'] for r in view['requirements']],native['canonical_requirements'])

    def test_representative_knowledge_evidence_cases_are_orthogonal(self):
        for knowledge in ('CAPABILITY_RESOLVED','TECHNOLOGY_IDENTITY_RESOLVED','PROVEN_TAXONOMY_GAP','NOT_TAXONOMY_ADDRESSABLE'):
            for label in ('direct','transferable','none'):
                with self.subTest(knowledge=knowledge,label=label):
                    native = row('r','Recorded requirement','required',label,0,0)
                    result = explainer.explain_requirement(native, knowledge_status=knowledge)
                    self.assertEqual(result['knowledge_status'],knowledge)
                    self.assertEqual(result['state'],{'direct':'MATCHED_DIRECT','transferable':'MATCHED_TRANSFERABLE','none':'UNKNOWN_REVIEW_PENDING'}[label])
        nac=explainer.explain_requirement({'match_label':'direct'},knowledge_status='PROVEN_TAXONOMY_GAP')
        self.assertIn('accepted direct evidence',nac['explanation'])
        self.assertNotIn('lack',nac['explanation'])

    def test_rejected_and_scope_limited_search_never_claim_deficiency(self):
        for status in ('CANDIDATE_REJECTED','SEARCHED_BUT_SCOPE_LIMITED'):
            native={'match_label':'none','negative_evidence_status':status,'evidence':[]}
            result=explainer.explain_requirement(native)
            self.assertEqual(result['state'],'UNKNOWN_REVIEW_PENDING')
            self.assertEqual(result['explanation'],explainer.PENDING)
            self.assertTrue(result['diagnostic'])
            self.assertEqual(native['evidence'],[])

    def test_component_preferred_and_supporting_are_not_whole_parent_claims(self):
        for importance in ('required','preferred','supporting'):
            for label in ('direct','transferable'):
                result=explainer.explain_requirement(row('r','Compound scope',importance,label,0,0))
                self.assertIn('whole-parent completeness is not inferred',result['evidence_scope'])
                self.assertNotIn('fully satisfy',result['explanation'])

    def test_stale_receipt_remains_historical_and_does_not_rebuild(self):
        native=analysis()
        native['scoring_version']='historical'
        with patch('analysis_stability.build_stable_analysis',side_effect=AssertionError('No scoring')):
            view=receipt(native)
        self.assertEqual(view['score'],73)
        self.assertEqual(view['currentness'],'Stale historical analysis')
        self.assertIsNone(view['requirements'][0]['contribution'])

    def test_comparison_joins_ids_and_never_infers_cause_from_score(self):
        initial=receipt()
        final=deepcopy(initial)
        final['requirements']=list(reversed(final['requirements']))
        result=explainer.compare_analysis_receipts(initial,final)
        self.assertTrue(result['comparable'])
        self.assertEqual([r['requirement_id'] for r in result['requirements']],['a','b','c'])
        self.assertTrue(all(r['reason']=='UNCHANGED' for r in result['requirements']))
        final['requirements'][0]['native']['evidence']=[{'text':'Different accepted item','source':'resume'}]
        result=explainer.compare_analysis_receipts(initial,final)
        self.assertEqual(result['requirements'][2]['reason'],'UNKNOWN')

    def test_mismatched_generations_and_applications_fail_closed(self):
        initial=receipt()
        for field in ('jd_fingerprint','canonical_requirement_fingerprint'):
            final=deepcopy(initial); final[field]='different'
            self.assertFalse(explainer.compare_analysis_receipts(initial,final)['comparable'])
        final=deepcopy(initial); final['identity']['application_id']=8
        self.assertFalse(explainer.compare_analysis_receipts(initial,final)['comparable'])
        final=deepcopy(initial); final['stable_analysis']['scoring_version']='other'
        self.assertFalse(explainer.compare_analysis_receipts(initial,final)['comparable'])


class InitialAnalysisPersistenceTests(unittest.TestCase):
    setUp=shared.SharedApplicationSessionIdentityTests.setUp
    counts=shared.SharedApplicationSessionIdentityTests.counts
    draft=shared.SharedApplicationSessionIdentityTests.draft
    confirm=shared.SharedApplicationSessionIdentityTests.confirm

    def test_authoritative_job_finder_initial_survives_configuration_and_report_changes(self):
        from database import db_manager
        target=self.draft()
        before=explainer.load_application_initial(target)
        self.confirm(target)
        self.assertEqual(explainer.load_application_initial(target),before)
        self.assertEqual(self.counts()['application_analysis_versions'],1)
        connection=db_manager._connect()
        connection.execute("UPDATE applications SET report_json='{}' WHERE id=?",(target,))
        connection.commit(); connection.close()
        self.assertEqual(explainer.load_application_initial(target),before)
        self.assertEqual(before['score'],self.snapshot['stable_analysis']['deterministic_alignment_score'])
        self.assertEqual(before['identity']['saved_snapshot_id'],self.snapshot['id'])

    def test_phase9f_only_uses_exact_native_initial_reference(self):
        result=self.confirm()
        view=explainer.load_application_initial(result['confirmation']['application_id'])
        self.assertEqual(view['provenance'],'PHASE9F_BASELINE_INITIAL_ANALYSIS')
        self.assertEqual(view['identity']['initial_analysis_id'],result['confirmation']['confirmation_snapshot']['initial_analysis']['analysis_id'])

    def test_saved_phase8_ui_compares_authoritative_initial_and_rejects_wrong_jd(self):
        from database import db_manager
        from database.tailoring_verification_manager import init_tailoring_verifications
        from streamlit.testing.v1 import AppTest
        from tailoring.job_match_ab_analysis import current_ab_identity
        target=self.draft()
        self.confirm(target)
        original=explainer.load_application_initial(target)
        init_tailoring_verifications()
        result={'application_id':target,'generation_id':'saved-generation',
                'after_stable_analysis':original['stable_analysis'],
                'job_match_ab':{'tailored':{'identity':current_ab_identity(original['raw_jd_text'])}}}
        connection=db_manager._connect()
        connection.execute("INSERT INTO application_tailoring_verifications(application_id,verification_id,generation_id,phase8_version,verification_mode,verification_fingerprint,result_json,created_at) VALUES (?,'v','saved-generation','native','zero_cost_deterministic','fp',?,'now')",(target,json.dumps(result)))
        connection.commit(); connection.close()
        app=AppTest.from_string('''
import streamlit as st
from database import db_manager
from pathlib import Path
from tailoring.initial_analysis_explainer_ui import render_application_initial_analysis
db_manager.DB_PATH=Path(st.session_state['database'])
render_application_initial_analysis(st,st.session_state['application'])
''',default_timeout=30)
        app.session_state['database']=str(self.database_path); app.session_state['application']=target
        counts=self.counts()
        with patch('tailoring.phase8_verification.build_phase8_verification',side_effect=AssertionError('No Phase 8 execution')):
            app.run()
        self.assertFalse(app.exception)
        comparison=next(frame.value for frame in app.dataframe if 'Contribution change' in frame.value.columns)
        self.assertTrue(all(comparison['Reason']=='UNCHANGED'))
        self.assertEqual(self.counts(),counts)
        self.assertEqual(explainer.load_application_initial(target),original)
        result['job_match_ab']['tailored']['identity']['jd_fingerprint']='wrong'
        connection=db_manager._connect()
        connection.execute('UPDATE application_tailoring_verifications SET result_json=?',(json.dumps(result),))
        connection.commit(); connection.close()
        app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('incompatible' in str(w.value) for w in app.warning))
        self.assertFalse(any('Contribution change' in frame.value.columns for frame in app.dataframe))

    def test_passive_streamlit_render_does_not_write_or_call_providers(self):
        from streamlit.testing.v1 import AppTest
        target=self.draft()
        counts=self.counts()
        app=AppTest.from_string('''
import streamlit as st
from database import db_manager
from pathlib import Path
from tailoring.initial_analysis_explainer_ui import render_application_initial_analysis
db_manager.DB_PATH=Path(st.session_state['database'])
render_application_initial_analysis(st,st.session_state['application'])
''',default_timeout=30)
        app.session_state['database']=str(self.database_path)
        app.session_state['application']=target
        with patch('litellm.completion',side_effect=AssertionError('No model')), \
             patch('litellm.embedding',side_effect=AssertionError('No embedding')), \
             patch('analysis_stability.build_stable_analysis',side_effect=AssertionError('No scorer')):
            app.run(); app.run()
        self.assertFalse(app.exception)
        self.assertEqual(self.counts(),counts)
        displayed=next(frame.value for frame in app.dataframe if 'Analysis status' in frame.value.columns)
        native=self.snapshot['stable_analysis']['canonical_requirements']
        self.assertEqual(list(displayed['Evidence']),[r['match_label'] for r in native])
        self.assertEqual(list(displayed['Analysis status']),[
            'Review pending' if explainer.explain_requirement(r)['state']=='UNKNOWN_REVIEW_PENDING'
            else explainer.explain_requirement(r)['state'] for r in native])
        self.assertTrue(any(metric.label=='Job Match' for metric in app.metric))

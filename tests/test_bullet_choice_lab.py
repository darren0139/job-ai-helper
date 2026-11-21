"""Focused benchmark contracts; no models, live DB or native rendering."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import unittest
from zipfile import ZipFile

from tailoring.bullet_choice_estimated import estimate_pair, action_status
from tailoring.bullet_choice_lab import load_dataset, compare_runs, run_benchmarks, selector_case, FROZEN_SHA256
from tailoring.bullet_choice_lab_ui import exports


class EstimatedControls(unittest.TestCase):
    def test_setup_and_negative_controls(self):
        self.assertEqual(action_status('Set up React and Supabase services.'),'performed_claim')
        for s in ('Planning to set up React services.','Did not set up React services.','Interested in setting up React.','Tools: Set up React services.','Keywords: automated tests'):
            self.assertNotEqual(action_status(s),'performed_claim',s)
        self.assertEqual(action_status('Designed test plans for API services.'),'performed_claim')

    def test_bound_native_setup_keeps_binding_and_negation(self):
        from tailoring.phase9f_bullet_relevance_diagnostic import compare_ranked_bullets
        req={'r':{'text':'Frontend application development','importance':'preferred'}}
        def row(text,source,native):
            return {'project':'Tool','bullet':text,'sources':[source],'jd_links':[{'id':'r','text':req['r']['text'],'importance':'preferred','status':'Native document evidence','native_evidence':{'existing':{'match_label':'direct','strength':5,'excerpt':text}}}] if native else []}
        base=row('Set up the React and Supabase environment.','Selected Base',True)
        other=row('Built unrelated tooling.','Evidence Library',False)
        got=compare_ranked_bullets(base,other,req)
        self.assertEqual(got['base_support']['r'],[3,5])
        for text in ('Planning to set up React.','Did not set up React.','Interested in setting up React.','React Supabase'):
            self.assertFalse(compare_ranked_bullets(row(text,'Selected Base',True),other,req)['base_support'])
        base['jd_links'][0]['native_evidence']['existing']['excerpt']='Different wording'
        self.assertFalse(compare_ranked_bullets(base,other,req)['base_support'])

    def test_keyword_repetition_negation_and_compound(self):
        q=[{'id':'r','text':'Execute unit testing and integration testing','importance':'core'}]
        got=estimate_pair('Executed unit testing.','Tools: unit testing integration testing',q)
        self.assertEqual(got['outcome'],'Base stronger')
        self.assertEqual(got['requirements'][0]['base']['coverage'],'partial_wording_support')
        self.assertFalse(got['requirements'][0]['library']['supported_facets'])
        self.assertEqual(estimate_pair('Executed unit testing.','Executed unit testing. Executed unit testing.',q)['outcome'],'Equivalent')

    def test_complementary_core_and_preferred_and_unknown_evidence(self):
        qs=[{'id':'a','text':'Build Python APIs','importance':'core'},{'id':'b','text':'Create React interfaces','importance':'core'}]
        self.assertEqual(estimate_pair('Built Python APIs.','Created React interfaces.',qs)['outcome'],'Complementary')
        qs[1]['importance']='preferred'
        self.assertEqual(estimate_pair('Built Python APIs.','Created React interfaces.',qs)['outcome'],'Base stronger')
        self.assertEqual(estimate_pair('Python','React',qs)['outcome'],'Indeterminate')

    def test_identity_bounds_and_source_immutability(self):
        qs=[{'id':'a','text':'Build Python APIs','importance':'core'}];original=deepcopy(qs)
        got=estimate_pair('Built Python APIs.','Implemented Java services.',qs)
        self.assertFalse(got['requirements'][0]['library']['verified'])
        self.assertEqual(qs,original)
        self.assertEqual(estimate_pair('x'*2001,'a',qs)['outcome'],'Indeterminate')
        self.assertEqual(estimate_pair('Built Python APIs.','Built React interfaces.',qs+[{'id':'a','text':'React interfaces','importance':'preferred'}])['outcome'],'Indeterminate')

    def test_irrelevance_aliases_and_redundant_surrounding_evidence(self):
        q=[{'id':'a','text':'Build Python APIs','importance':'core'}]
        self.assertEqual(estimate_pair('Built Python APIs.','Designed camera hardware.',q)['outcome'],'Base stronger')
        r=estimate_pair('Built Python APIs.','Designed camera hardware.',q,selected=['Built Python APIs.'])
        self.assertTrue(r['requirements'][0]['already_supported_elsewhere_estimate'])
        self.assertEqual(r['outcome'],'Equivalent')
        # Ordinary inflection equivalence is diagnostic normalization, not native credit.
        q=[{'id':'r','text':'Execute unit tests','importance':'core'}]
        self.assertEqual(estimate_pair('Executed unit tests.','Implemented unit testing.',q)['outcome'],'Equivalent')
        q=[{'id':'r','text':'Develop Java applications','importance':'core'}]
        self.assertFalse(estimate_pair('Developed JavaScript applications.','Built unrelated tools.',q)['requirements'][0]['base']['supported_facets'])

    def test_word_cost_does_not_override_useful_coverage(self):
        qs=[{'id':'a','text':'Build Python APIs','importance':'core'},{'id':'b','text':'Design PostgreSQL schemas','importance':'preferred'}]
        result=estimate_pair('Built Python APIs.','Built Python APIs and designed PostgreSQL schemas for transactional records.',qs)
        self.assertEqual(result['outcome'],'Library stronger')
        self.assertGreater(result['word_counts']['library'],result['word_counts']['base'])


class LabContracts(unittest.TestCase):
    def test_frozen_cases_and_split_identities(self):
        packet=load_dataset();cs=packet['cases']
        self.assertEqual(len([c for c in cs if c['dataset']=='synthetic' and c['split']!='fresh_validation']),60)
        self.assertEqual(len([c for c in cs if c['split']=='fresh_validation']),12)
        anchors=[c for c in cs if c['dataset']=='corpus'];self.assertEqual(len(anchors),24)
        self.assertEqual(len({c['jd_id'] for c in anchors}),8)
        dev={(c['base'],c['library']) for c in cs if c['split']=='development'}
        held={(c['base'],c['library']) for c in cs if c['split']=='held_out'}
        self.assertFalse(dev & held)

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'data/bullet_choice_benchmark/v1.json').is_file(),
                         'Optional private 20-case fixture is not installed; not a benchmark pass')
    def test_optional_private_real_case_identities(self):
        real=[c for c in load_dataset()['cases'] if c['dataset']=='real']
        self.assertEqual(len(real),20)
        self.assertEqual({c['id'] for c in real},{f'R{i:02}' for i in range(1,21)})
        self.assertTrue(all(c['expected'] is None for c in real))

    def test_one_case_bounded_no_native_score_and_exports(self):
        r=run_benchmarks(datasets=('synthetic',),case_ids=('S01-1',),selectors=False,limit=1)
        self.assertEqual(r['executed'],1);self.assertEqual(r['summary']['correct'],1)
        self.assertIsNone(r['summary']['real_accuracy'])
        payload,table,bundle=exports(r)
        with ZipFile(BytesIO(bundle)) as z:
            self.assertIsNone(z.testzip());self.assertEqual(z.read('run.json'),payload);self.assertEqual(z.read('results.csv'),table)
        with self.assertRaises(ValueError):run_benchmarks(limit=117)

    def test_actual_selector_complementary_contract(self):
        r=selector_case('complementary')
        self.assertTrue(r['pass'],r)
        self.assertEqual(len(r['membership']),2)
        self.assertIn('mathematical_certificate',r['trace'])

    def test_actual_word_budget_contract_has_valid_sized_source(self):
        r=selector_case('word_budget')
        self.assertTrue(r['pass'],r)
        self.assertLess(len(r['input_audit']['projects'][0]['library'][0]['text']),1200)

    def test_regression_and_incompatible_run_detection(self):
        before={'dataset_sha256':'a','eligibility_version':'v','rows':[{'case_id':'x','pass':True,'estimated':{'outcome':'Base stronger'}}]}
        after=deepcopy(before);after['rows'][0]['pass']=False
        self.assertEqual(compare_runs(before,after)['regressions'],['x'])
        after['dataset_sha256']='other'
        self.assertEqual(compare_runs(before,after)['status'],'incompatible')

    def test_normal_navigation_and_page_render(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'app.py').read_text(encoding='utf-8')
        self.assertIn('"Taxonomy Maintenance",\n            "Bullet-Choice Benchmark Lab",',source)
        self.assertIn('elif page == "Bullet-Choice Benchmark Lab":',source)
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_string('import streamlit as st\nfrom tailoring.bullet_choice_lab_ui import render_page\nrender_page(st)').run(timeout=30)
        self.assertFalse(app.exception,list(app.exception))
        self.assertTrue(any(b.label=='Run All Benchmarks' for b in app.button))


if __name__=='__main__':unittest.main()

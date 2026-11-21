from copy import deepcopy
import unittest
from tailoring.phase9f_bullet_relevance_diagnostic import compare_ranked_bullets, selection_alignment


def row(source, ids=(), text='Performed testing', project='Tool'):
    return {'project': project, 'bullet': text, 'sources': [source], 'jd_links': [
        {'id': rid, 'text': rid, 'importance': 'core', 'status': 'Native document evidence',
         'native_evidence': {'existing': {'match_label': 'weak', 'strength': 2, 'excerpt': text}}} for rid in ids]}


class RelevanceTests(unittest.TestCase):
    def test_relevance_leader_inclusion_agrees_but_does_not_prove_cause(self):
        self.assertIn('agrees with saved inclusion',selection_alignment('Library has stronger supported JD relevance.',False,True,True))
    def test_relevance_leader_exclusion_is_not_explained_by_generic_objective(self):
        self.assertIn('no isolated exclusion cause',selection_alignment('Base has stronger supported JD relevance.',False,True,True))
    def test_both_selected_or_unknown_do_not_invent_winner(self):
        self.assertIn('neither defeated',selection_alignment('Library has stronger',True,True,True))
        self.assertIn('unavailable',selection_alignment('Library has stronger',False,True,False))
    def test_ineligible_or_unclassified_requirements_never_get_diagnostic_credit(self):
        for fields in [{'evidence_eligible':False},{'score_eligible':False},{'importance':'unknown'}]:
            catalog={'testing':{'text':'testing','importance':'core',**fields}}
            result=compare_ranked_bullets(row('Selected Base',text='Built a tool'),row('Evidence Library',['testing']),catalog)
            self.assertFalse(result['library_support'])
    def test_zero_strength_native_label_does_not_establish_verified_support(self):
        a=row('Selected Base',text='Built a tool');b=row('Evidence Library',['testing'])
        b['jd_links'][0]['native_evidence']['existing']['strength']=0
        self.assertFalse(compare_ranked_bullets(a,b,{'testing':{'text':'testing','importance':'core'}})['library_support'])
    def setUp(self): self.catalog = {r: {'text': r, 'importance': 'core'} for r in ['testing','api']}
    def test_library_core_leader(self):
        r=compare_ranked_bullets(row('Selected Base',text='Built tool'),row('Evidence Library',['testing']),self.catalog)
        self.assertEqual(r['outcome'],'Library has stronger supported JD relevance.')
        self.assertEqual(r['native_impact'],'unmeasured')
    def test_base_core_leader_despite_library_keywords(self):
        r=compare_ranked_bullets(row('Selected Base',['api']),row('Evidence Library',text='API Python SQL testing'),self.catalog)
        self.assertEqual(r['outcome'],'Base has stronger supported JD relevance.')
    def test_complementary(self):
        r=compare_ranked_bullets(row('Selected Base',['api']),row('Evidence Library',['testing'],text='Wrote tests'),self.catalog)
        self.assertTrue(r['outcome'].startswith('Different complementary'))
    def test_negation(self):
        r=compare_ranked_bullets(row('Selected Base'),row('Evidence Library',['testing'],text='Did not perform testing'),self.catalog)
        self.assertFalse(r['library_support']);self.assertTrue(r['warnings'])
    def test_shared_exact(self):
        r=compare_ranked_bullets(row('Selected Base'),row('Evidence Library'),self.catalog)
        self.assertEqual(r['outcome'],'Comparable relevance / tie.')
    def test_cross_project(self):
        self.assertEqual(compare_ranked_bullets(row('Selected Base'),row('Evidence Library',project='Other'),self.catalog)['outcome'],'Not a valid competing pair.')
    def test_redundancy_preserves_inputs(self):
        a=row('Selected Base',['api']);b=row('Evidence Library',['testing'],text='Wrote tests');before=deepcopy((a,b))
        r=compare_ranked_bullets(a,b,self.catalog,[row('Selected Base',['api'],text='Built other API evidence')])
        self.assertEqual(r['already_supported_elsewhere'],['api']);self.assertEqual((a,b),before)
    def test_compound_terminology_is_not_native_credit(self):
        cat={'testing':{'text':'Execute unit, integration, system and user acceptance testing','importance':'core'}}
        r=compare_ranked_bullets(row('Selected Base',text='Built regression testing and GitHub Actions CI'),row('Evidence Library',text='Added automated unit tests and GitHub Actions CI'),cat)
        self.assertEqual(r['explicit_testing_terms']['library'],['unit testing'])
        self.assertIn('system testing',r['unestablished_testing_terms']['library'])
        self.assertTrue(r['outcome'].startswith('Insufficient'))
    def test_keyword_list_with_native_weak_label_is_still_not_performed_evidence(self):
        r=compare_ranked_bullets(row('Selected Base'),row('Evidence Library',['testing'],text='Testing Python CI SQL'),self.catalog)
        self.assertFalse(r['library_support'])
    def test_preferred_evidence_is_secondary_to_core(self):
        cat={**self.catalog,'bonus':{'text':'bonus','importance':'preferred'}}
        a=row('Selected Base',['api']);b=row('Evidence Library',['testing'],text='Performed bonus testing')
        b['jd_links'][0].update(id='bonus',text='bonus',importance='preferred')
        r=compare_ranked_bullets(a,b,cat)
        self.assertEqual(r['outcome'],'Base has stronger supported JD relevance.')

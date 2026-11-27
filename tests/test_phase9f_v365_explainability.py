"""V3.6.5 UI evidence transparency tests; purely read-only, no production writes."""
from __future__ import annotations

import unittest
from pathlib import Path
from tailoring.phase9f_v365_jd_evidence import (
    audit_fragment, requirement_catalog, explain_bullet, compare_source_pair,
)
from tailoring.phase9f_v364_decision_explorer import render_compact_decision_explorer

RAW=('Execute unit, integration, system and user acceptance testing. '
     'Using configuration management, integration and build automation tools to deploy applications. '
     'Proficiency in one or more backend languages (Java/.NET/Python/PHP). '
     'Proficiency in database will be an added advantage.')

def req(rid,text,importance='core'):
    return {'requirement_id':rid,'text':text,'parent_text':text,'importance':importance}

def catalog():
    return requirement_catalog({'stable_analysis':{'canonical_requirements':[
        req('testing','Execute unit, integration, system and user acceptance testing'),
        req('deploy','Using configuration management, integration and build automation tools to deploy applications'),
        req('backend','Proficiency in one or more backend languages (Java/.NET/Python/PHP)'),
        req('database','Proficiency in database will be an added advantage','preferred'),
    ]}}, {})

class JDEvidence(unittest.TestCase):
    def test_known_parser_clipping_shapes_are_suspect(self):
        # Synthetic grammar analogues, NOT the original corpus 566/632 source text.
        for bad in ('and deploy applications','with the software','deploy the system and'):
            with self.subTest(bad=bad):
                obj=audit_fragment(bad,parent_sentence='Develop and deploy applications',raw_jd_text='Develop and deploy applications')
                self.assertEqual(obj['status'],'suspect')
                self.assertFalse(obj['eligible_for_bonus_explanation'])

    def test_missing_parent_is_unverified_not_safe(self):
        self.assertEqual(audit_fragment('Python',raw_jd_text='Python')['status'],'unverified')
        self.assertFalse(audit_fragment('Python',raw_jd_text='Python')['eligible_for_bonus_explanation'])
        mismatch = audit_fragment('Docker', parent_sentence='Python', raw_jd_text='Python')
        self.assertEqual(mismatch['status'], 'unverified')
        self.assertEqual(mismatch['source_status'], 'source_span_mismatch')
        self.assertEqual(mismatch['grammar_status'], 'no_boundary_warning')

    def test_corpus_parent_weight_cannot_be_inflated_by_ui(self):
        # The explanation must not create synthetic child requirements or change score.
        row={'bullet':'Added automated unit tests with Python','saved_jd_ids':['testing'],
             'in_proposed_b':True,'words':7}
        got=explain_bullet(row,catalog(),raw_jd_text=RAW,selected_rows=[row])
        self.assertEqual(len(got['jd_links']),1)
        self.assertIn('unit',got['matched_terms'])
        self.assertFalse(got['jd_links'][0]['independent_evidence_verified'])
        self.assertNotIn('native_score',got)

    def test_same_saved_deploy_link_does_not_prove_database_wording(self):
        row={'bullet':'Implemented backend data access using PostgREST and Row-Level Security',
             'saved_jd_ids':['deploy'],'words':11,'in_proposed_b':True}
        got=explain_bullet(row,catalog(),raw_jd_text=RAW,selected_rows=[row])
        self.assertEqual(got['suspect_link_ids'],['deploy'])
        self.assertIn('backend',got['unlinked_jd_term_cues'])
        self.assertFalse(got['jd_links'][0]['literal_corroboration'])

    def test_jd_wide_keywords_versus_linked_evidence_are_separate(self):
        pair={'base_bullet':'Implemented PostgREST data access with Row-Level Security policies',
              'library_bullet':'Implemented backend access through PostgREST with Row-Level Security',
              'base_words':10,'library_words':9,'shared_saved_jd_ids':['deploy']}
        got=compare_source_pair(pair,catalog(),raw_jd_text=RAW)
        self.assertIn('backend',got['only_library_terms'])
        self.assertIn('backend',got['library']['unlinked_jd_term_cues'])
        self.assertEqual(got['library_words_saved'],1)
        self.assertIn('No native',got['verdict'])

    def test_tech_matches_are_separate_from_saved_link_credit(self):
        row={'bullet':'Implemented backend Python tooling','saved_jd_ids':['deploy'],'words':5}
        got=explain_bullet(row,catalog(),raw_jd_text=RAW)
        self.assertIn('python',got['jd_wide_technology_cues'])
        self.assertIn('python',got['unlinked_jd_term_cues'])
        self.assertEqual(got['suspect_link_ids'],['deploy'])

    def test_generic_added_advantage_is_never_keyword_signal(self):
        row={'bullet':'Added tests, used Python','saved_jd_ids':['testing'], 'words':5}
        got=explain_bullet(row,catalog(),raw_jd_text=RAW)
        self.assertNotIn('added',got['jd_wide_term_cues'])
        self.assertNotIn('advantage',got['jd_wide_term_cues'])

    def test_bonus_cues_do_not_create_scoring_credit(self):
        row={'bullet':'Developed a PostgreSQL database', 'saved_jd_ids':[],'words':5}
        got=explain_bullet(row,catalog(),raw_jd_text=RAW)
        self.assertEqual(got['preferred_link_ids'],[])
        self.assertTrue(any(cue['text'].startswith('Proficiency in database')
                            for cue in got['possible_unlinked_bonus_cues']))
        self.assertIn('not independent',got['claim_limit'])

    def test_frozen_catalog_missing_metadata_is_unknown(self):
        row={'bullet':'React frontend development','saved_jd_ids':['wrong'], 'words':3}
        got=explain_bullet(row,{},raw_jd_text=RAW)
        self.assertEqual(got['unresolved_jd_ids'],['wrong'])
        self.assertFalse(got['jd_links'])

class FakeCtx:
    def __init__(self,owner,label):self.owner=owner;self.label=label
    def __enter__(self):self.owner.active.append(self.label);return self
    def __exit__(self,*args):self.owner.active.pop();return False
    def __getattr__(self, name):
        # Native Streamlit containers expose the same text and widget methods.
        # Return calls to the parent recording fixture, preserving expander scope.
        return getattr(self.owner, name)

class FakeStreamlit:
    def __init__(self):self.session_state={};self.logs=[];self.expander_args=[];self.active=[]
    def markdown(self,*args,**kwargs):self.logs.append(str(args))
    def caption(self,*args,**kwargs):self.logs.append(str(args))
    def info(self,*args,**kwargs):self.logs.append(str(args))
    def warning(self,*args,**kwargs):self.logs.append(str(args))
    def write(self,*args,**kwargs):self.logs.append(str(args))
    def divider(self,*args,**kwargs):pass
    def expander(self,label,**kwargs):self.expander_args.append((label,kwargs));return FakeCtx(self,label)
    def selectbox(self,label,options,**kwargs):return list(options)[0]
    def checkbox(self,label,*,key,value=False,on_change=None,args=(),**kwargs):
        # Simulate native checkbox ownership across reruns. The navigation
        # helper persists view preferences separately from business state.
        return self.session_state.setdefault(key, value)
    def radio(self,label,options,**kwargs):return list(options)[0]
    def container(self, **kwargs): return FakeCtx(self, "comparison")
    def table(self,*args,**kwargs): self.logs.append(str(args))
    def json(self,*args,**kwargs): self.logs.append(str(args))
    def columns(self,columns,**kwargs):return [self,self]
    def button(self,*args,**kwargs):return False
    def download_button(self,*args,**kwargs):pass
    def dataframe(self,*args,**kwargs):
        if not any('Advanced:' in label for label in self.active):
            raise AssertionError('No wide tables allowed in primary Decision Explorer')

class RenderTests(unittest.TestCase):
    def test_main_view_shows_resolved_jd_text_and_no_table(self):
        st=FakeStreamlit()
        row={'project':'QueryAI','bullet':'Implemented backend access through PostgREST',
             'sources':['Evidence Library'], 'in_actual_a':False,'in_proposed_b':True,
             'saved_jd_ids':['deploy'],'jd_terms':['added','backend'],'words':7,
             'potential_new_jd_ids':[]}
        calc={'status':'available','summary':{'eligible_wordings':1,'selected_bullets_in_b':1,
            'actual_a_bullets_in_pool':0,'proxy_points_baseline':0,'proxy_points_proposed':0,
            'word_cost_baseline':0,'word_cost_proposed':7},'rows':[row],
            'source_competitions':[]}
        result={'status':'verified','winner':'existing_final','a_score':31,'b_score':31}
        render_compact_decision_explorer(st,calc=calc,result=result,proposal={},audit={},
            projects={},application_id=156,context='test',
            baseline_report={'stable_analysis':{'canonical_requirements':list(
                {'requirement_id':r['id'],'text':r['text'],'parent_text':r['parent'],
                 'importance':r['importance']} for r in catalog().values())}},
            raw_jd_text=RAW)
        combined=' '.join(st.logs)
        self.assertIn('Using configuration management',combined)
        self.assertIn('Other JD-wide keyword cues',combined)
        self.assertIn('backend',combined)
        self.assertIn('Keep the existing fitted résumé',combined)
        self.assertIn('Native per-bullet impact is unknown',combined)

    def test_wide_source_tables_moved_to_advanced_export(self):
        source=(Path(__file__).parents[1]/'tailoring'/'phase9f_automatic_bestof_v30_ui.py').read_text('utf-8')
        self.assertIn("Advanced fitting and optimizer receipt', expanded=False",source)
        self.assertIn("'candidate_wording_diagnostics': _source_comparison_rows",source)
        # Historical receipt table is explicitly inside the collapsed advanced panel.
        advanced = source.index("Advanced fitting and optimizer receipt', expanded=False")
        self.assertNotIn('st.dataframe', source[:advanced])
        self.assertEqual(source.count('st.dataframe('), 1)
        self.assertIn('st.dataframe(history,hide_index=True,use_container_width=True)', source[advanced:])
        self.assertIn('baseline_report=baseline_report, raw_jd_text=raw_jd_text',source)
        self.assertNotIn("alternatives', expanded=True",source)

if __name__=='__main__':unittest.main()

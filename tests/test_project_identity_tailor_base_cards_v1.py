"""Cross-user portable fixtures: no credentials, private DB or paid model."""
from copy import deepcopy
import unittest
from tailoring.project_title_resolution_v1 import resolve_project, mutually_resolve_project, registry_scope
from tailoring.project_identity import build_selected_project_identity_index, match_evidence_project_to_selected
from tailoring.project_section_tailor import build_project_candidate_pool
from tailoring.phase9f_independent_bullet_scores_v312b214b import build_independent_bullet_scores
from tests.test_v312b214b_independent_bullet_scores import fixture, evaluator, JD, PYTHON, P1
from tests.test_phase9f_project_bullet_sources_v2_3 import fixture as source_fixture
from tailoring.phase9f_project_bullet_sources_v2_3 import build_project_bullet_source_view

class ProjectRobustness(unittest.TestCase):
    def test_unique_subtitle_aliases(self):
        for long in ['Game Name -Shooter', 'Game Name — Shooter', 'Game Name: Shooter', 'Game Name (Shooter)']:
            base = {'title':'Game Name'}; library = {'title':long}
            self.assertIs(resolve_project(base, [library])[0], library)
            self.assertIs(resolve_project(library, [base])[0], base)
        self.assertIsNotNone(resolve_project({'title':'QueryAI'}, [{'title':'Query AI'}])[0])
        self.assertIsNotNone(resolve_project({'title':'Job-AI-Helper'}, [{'title':'Job AI Helper'}])[0])

    def test_negative_and_ambiguous(self):
        cases = [({'title':'Game Name'}, [{'title':'Game Name 2'}]),
                 ({'title':'Game Name - Shooter'}, [{'title':'Game Name - Racing'}]),
                 ({'title':'Game Name'}, [{'title':'Game Name - Shooter'}, {'title':'Game Name - Racing'}]),
                 ({'title':'Game Name','project_id':'a'}, [{'title':'Game Name','project_id':'b'}]),
                 ({'title':'Final Year Project'}, [{'title':'Final Year Project - Shooter'}])]
        for left, rows in cases:
            self.assertIsNone(resolve_project(left, rows)[0], (left,rows))
        a,b,c = {'title':'Game Name'}, {'title':'Game Name - Shooter'}, {'title':'Game Name - Racing'}
        self.assertIsNone(mutually_resolve_project(a,[a],[b,c])[0])

    def test_skills_title_support(self):
        selected = [{'title':'Game Name','display_title':'Game Name — Shooter'}]
        evidence = [{'title':'Game Name','subtitle':'Shooter'}]
        index = build_selected_project_identity_index(selected_projects=selected,evidence_items=evidence)
        self.assertTrue(match_evidence_project_to_selected(evidence[0],index)[0])
        evidence.append({'title':'Game Name','subtitle':'Racing'})
        selected = [{'title':'Game Name'}]
        index = build_selected_project_identity_index(selected_projects=selected,evidence_items=evidence)
        self.assertFalse(match_evidence_project_to_selected(evidence[0],index)[0])

    def test_pool_preserves_both_sources(self):
        for title, subtitle in [('Game Name -Shooter',''), ('Game Name: Shooter',''), ('Game Name','Shooter')]:
            base = {'projects':[{'title':'Game Name','bullets':['Built gameplay.']}]}
            library = [{'category':'project','title':title,'subtitle':subtitle,'description':'Implemented collision.'}]
            before = deepcopy((base,library))
            rows = build_project_candidate_pool(resume_profile=base,evidence_items=library)
            self.assertEqual(len(rows),1,rows)
            self.assertTrue(rows[0]['currently_in_resume'] and rows[0]['in_evidence_library'])
            self.assertEqual(rows[0]['resume_evidence']['bullets'],['Built gameplay.'])
            self.assertEqual(rows[0]['evidence_library_evidence']['bullets'],['Implemented collision.'])
            self.assertEqual((base,library),before)

    def test_ambiguous_pool_never_overwrites(self):
        base = {'projects':[{'title':'Game Name','bullets':['Built gameplay.']}]}
        library = [{'category':'project','title':title,'description':title+' implementation.'}
                   for title in ('Game Name - Shooter','Game Name - Racing')]
        with self.assertRaisesRegex(ValueError,'Ambiguous project titles'):
            build_project_candidate_pool(resume_profile=base,evidence_items=library)

    def test_conflicting_source_ids_never_merge(self):
        base = {'projects':[{'title':'Game Name','project_id':'a','bullets':['Built gameplay.']}]}
        library = [{'category':'project','title':'Game Name','project_id':'b','description':'Different work.'}]
        with self.assertRaisesRegex(ValueError,'Ambiguous project titles'):
            build_project_candidate_pool(resume_profile=base,evidence_items=library)

    def test_source_view_alias_does_not_change_source_ownership(self):
        p,c=source_fixture(); c[0]['title']='Job AI Helper — System'
        result=build_project_bullet_source_view(p,c)
        self.assertEqual(result['projects'][0]['source'],'both',result)
        p['recommended_projects'][0]['source']='resume'
        self.assertFalse(build_project_bullet_source_view(p,c)['projects'])

    def test_card_scores_alias_and_stale_guard(self):
        a,p,r=fixture(); p['candidate_project_ranking'][0]['display_title']=P1+' — Workflow'
        before=deepcopy((a,p,r))
        got=build_independent_bullet_scores(a,p,r,JD,evaluator=evaluator)
        self.assertEqual(got['status'],'available',got)
        self.assertEqual(next(x['standalone_weighted_points'] for x in got['bullets'] if x['project']==P1 and x['wording']==PYTHON),9.0)
        self.assertEqual((a,p,r),before)
        r['raw_jd_text']='Different JD'
        self.assertEqual(build_independent_bullet_scores(a,p,r,JD,evaluator=evaluator)['status'],'unavailable')

    def test_registry_scope_changes_on_master_update(self):
        master={'master_version_id':'m1','master_version_fingerprint':'f1','artifact_sha256':'a1'}
        old=registry_scope(master,[])
        self.assertNotEqual(old,registry_scope(dict(master,master_version_id='m2'),[]))
        self.assertNotEqual(old,registry_scope(dict(master,artifact_sha256='a2'),[]))
        self.assertNotEqual(old,registry_scope(master,[{'blueprint_id':'b','status':'active'}]))

if __name__ == '__main__': unittest.main()

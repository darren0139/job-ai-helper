"""Saved EDB-56 accounting projection; no live writes, policy edits or research."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from database import job_match_manager as manager
from job_discovery.matching import summarize_stable_match
from job_discovery.match_ranking import build_ranking_quality
from tailoring import capability_taxonomy as taxonomy
from taxonomy_discovery import coverage_presentation as coverage
from taxonomy_discovery.observations import build_taxonomy_resolution_diagnostics
from tests.governed_review_fixtures import isolated_taxonomy
from tests.network_guard_support import block_external_network_allow_loopback

FIXTURE=Path(__file__).with_name('fixtures')/'post_publication_accounting_snapshot56.json'


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(isolated_taxonomy(published=True))
        self.fixture=json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.analysis=deepcopy(self.fixture['stable_analysis'])
        self.target=next(r for r in self.analysis['canonical_requirements'] if r['requirement_id']=='req_9270e95898c8')
        self.enterContext(block_external_network_allow_loopback())

    def app(self, analysis=None):
        app=AppTest.from_file(Path(__file__).with_name('post_publication_accounting_harness.py'),default_timeout=45)
        app.session_state['raw_jd']='Public EDB Job 146 accounting test context'
        app.session_state['stable']=analysis or self.analysis
        return app

    def test_exact_saved_disagreement_and_corrected_derivation(self):
        old=self.fixture['saved_summary'];self.assertEqual(old['taxonomy_resolution']['resolved_count'],6)
        self.assertEqual(self.target['knowledge_status'],'CAPABILITY_RESOLVED')
        oldrow=next(r for r in old['taxonomy_resolution']['rows'] if r['requirement_id']==self.target['requirement_id'])
        self.assertEqual(oldrow['status'],'unresolved');self.assertIsNone(oldrow['capability_id'])
        frozen=deepcopy(self.analysis)
        summary=summarize_stable_match(self.analysis);diag=summary['taxonomy_resolution']
        self.assertEqual((diag['eligible_requirement_count'],diag['resolved_count'],diag['unresolved_count']),(43,7,36))
        row=next(r for r in diag['rows'] if r['requirement_id']==self.target['requirement_id'])
        self.assertEqual((row['status'],row['capability_id']),('resolved','backend.api_development'))
        self.assertEqual(row['reason'],'approved_complete_rest_api_development_obligation')
        self.assertEqual(row['recognition_rule'],self.target['capability_recognition_rule'])
        self.assertEqual(diag['accounting_stage'],'final_native_capability_resolution_with_pinned_fallback')
        self.assertEqual(self.analysis,frozen)  # includes all parent/source/evidence/eligibility fields
        self.assertEqual(summary['deterministic_alignment_score'],20)
        changed=[r['requirement_id'] for r in diag['rows'] if r['status']!=next(
            x['status'] for x in old['taxonomy_resolution']['rows'] if x['requirement_id']==r['requirement_id'])]
        self.assertEqual(changed,['req_9270e95898c8'])

    def test_ranking_keeps_43_row_weighted_denominator_and_thresholds(self):
        old=self.fixture['saved_summary']['ranking_quality']
        summary=summarize_stable_match(self.analysis);quality=summary['ranking_quality']
        self.assertEqual(quality,build_ranking_quality(summary['taxonomy_resolution']))
        for field in ('eligible_requirement_count','important_requirement_count','minimum_overall_taxonomy_coverage',
                      'minimum_important_taxonomy_coverage','minimum_eligible_requirements','ranking_version'):
            self.assertEqual(quality[field],old[field],field)
        self.assertFalse(quality['ranking_eligible']);self.assertEqual(quality['ranking_status'],old['ranking_status'])
        self.assertEqual((quality['resolved_requirement_count'],quality['taxonomy_gap_count']),(7,36))
        self.assertAlmostEqual(quality['overall_taxonomy_coverage'],21/128,places=6)
        self.assertAlmostEqual(quality['important_taxonomy_coverage'],21/127,places=6)
        self.assertEqual((quality['overall_taxonomy_coverage_pct'],quality['important_taxonomy_coverage_pct']),(16,17))

    def test_missing_wrong_or_stale_pinned_rule_cannot_invent_resolution(self):
        for field,value in [('capability_recognition_rule',{}),('capability_id','database.design'),
                ('knowledge_status','UNRESOLVED'),('capability_resolution_source','technology_registry'),
                ('capability_taxonomy_version','phase6d-capability-taxonomy-v1.5')]:
            with self.subTest(field=field):
                analysis=deepcopy(self.analysis)
                target=next(r for r in analysis['canonical_requirements'] if r['requirement_id']==self.target['requirement_id'])
                target[field]=value
                diag=build_taxonomy_resolution_diagnostics(analysis)
                self.assertEqual(diag['resolved_count'],6)
        analysis=deepcopy(self.analysis);analysis['capability_taxonomy_version']='phase6d-capability-taxonomy-v1.5'
        self.assertEqual(build_taxonomy_resolution_diagnostics(analysis)['resolved_count'],6)
        for text in ('Do not develop RESTful APIs','Develop RESTful APIs and gRPC services'):
            analysis=deepcopy(self.analysis);row=next(r for r in analysis['canonical_requirements'] if r['requirement_id']==self.target['requirement_id'])
            row.update(text=text,atomic_focus=text,parent_text=text,source_provenance=[])
            self.assertNotEqual(next(r for r in build_taxonomy_resolution_diagnostics(analysis)['rows']
                if r['requirement_id']==row['requirement_id']).get('reason'),'approved_complete_rest_api_development_obligation')

    def test_csharp_javascript_rows_match_native_counter_not_review_routes(self):
        frozen=deepcopy(self.analysis)
        view=coverage.jd_coverage(None,None,raw_jd_text='Public EDB Job 146 accounting test context',stable_analysis=self.analysis,job_id=146)
        self.assertEqual((view['percentage'],view['denominator'],view['analysis_item_count']),(100,7,43))
        self.assertEqual((view['capability_resolved'],len(view['capability_rows'])),(7,7))
        self.assertEqual((view['technology_identity_resolved'],len(view['technology_identity_rows'])),(2,2))
        self.assertEqual({r['Technology ID'] for r in view['technology_identity_rows']},{'csharp','javascript'})
        self.assertEqual({r['Requirement'] for r in view['technology_identity_rows']},{'C#','JavaScript'})
        self.assertFalse(view['reviewed_accounting']);self.assertEqual(view['routes'],[]);self.assertEqual(view['breakdown'],{})
        self.assertEqual(view['additional_analysis_items'],36);self.assertEqual(self.analysis,frozen)

    def test_ui_nonempty_identity_and_capability_tables_explain_zero_review_rows(self):
        app=self.app()
        with patch.object(coverage.maintenance,'run_corpus_audit',side_effect=AssertionError('No replay')):
            app.run();app.run()
        self.assertFalse(app.exception)
        self.assertEqual([m.value for m in app.metric],['100.00%','0 currently established'])
        identities=next(f.value for f in app.dataframe if 'Technology ID' in f.value.columns)
        self.assertEqual(set(identities['Technology ID']),{'csharp','javascript'})
        self.assertEqual(len(next(f.value for f in app.dataframe if 'Capability' in f.value.columns)),7)
        self.assertTrue(any('No compatible reviewed unresolved-remediation route rows' in x.value for x in app.info))
        self.assertTrue(any('7 of 43' in x.value and 'Confirmed subset only' in x.value for x in app.caption))
        self.assertEqual(len(app.json),0);self.assertTrue(all(len(f.value)>0 for f in app.dataframe))

    def test_zero_legitimate_native_details_do_not_render_empty_tables(self):
        analysis=deepcopy(self.analysis)
        analysis['canonical_requirements']=[next(r for r in analysis['canonical_requirements'] if r['knowledge_status']=='UNRESOLVED')]
        app=self.app(analysis);app.run();self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe),0);self.assertEqual(len(app.json),0)
        self.assertTrue(any('No technology-identity-only' in x.value for x in app.caption))
        self.assertTrue(any('No capability-resolved' in x.value for x in app.caption))
        self.assertEqual(app.metric[0].value,'Not enough classified capability requirements yet')

    def test_snapshot_roundtrip_and_old_saved_structures_remain_unchanged(self):
        directory=Path(self.enterContext(tempfile.TemporaryDirectory()));db=directory/'app.sqlite3'
        common=dict(discovered_job_id=146,job_content_hash='isolated-source',match_version='isolated-match',
                    scoring_version=self.analysis['scoring_version'],jd_profile={},evidence_snapshot=[],db_path=db)
        historical=deepcopy(self.analysis);historical['capability_taxonomy_version']='phase6d-capability-taxonomy-v1.5'
        old=manager.save_job_match_snapshot(**common,evidence_fingerprint='historical',
            taxonomy_version=historical['capability_taxonomy_version'],stable_analysis=historical,summary=self.fixture['saved_summary'])
        frozen=deepcopy(old)
        corrected=summarize_stable_match(self.analysis)
        manager.save_job_match_snapshot(**common,evidence_fingerprint='new',taxonomy_version=self.analysis['capability_taxonomy_version'],
            stable_analysis=self.analysis,summary=corrected)
        reloaded=manager.get_job_match_snapshot(**{k:v for k,v in common.items() if k not in ('jd_profile','evidence_snapshot')},
            evidence_fingerprint='new',taxonomy_version=self.analysis['capability_taxonomy_version'])
        self.assertEqual(reloaded['stable_analysis'],self.analysis)
        self.assertEqual(reloaded['summary'],corrected)
        self.assertEqual(reloaded['summary']['taxonomy_resolution']['resolved_count'],7)
        old_again=manager.get_job_match_snapshot(**{k:v for k,v in common.items() if k not in ('jd_profile','evidence_snapshot')},
            evidence_fingerprint='historical',taxonomy_version=historical['capability_taxonomy_version'])
        self.assertEqual(old_again,frozen);self.assertEqual(old_again['summary']['taxonomy_resolution']['resolved_count'],6)

    def test_fresh_native_producer_then_summary_agree_without_policy_change(self):
        from analysis_stability.stable_evidence_scoring import build_stable_analysis
        text=self.target['text'];evidence=self.target['evidence'][0]['text']
        native=build_stable_analysis(jd_profile={'responsibilities':[text]},
            keyword_match={'present':[],'missing':[{'keyword':text}]},
            resume_profile={'projects':[{'name':'Documented backend work','bullets':[evidence]}],
                            'experience':[],'education':[],'skills':{}},raw_resume_text=evidence)
        target=next(r for r in native['canonical_requirements'] if r['text']==text)
        self.assertEqual(target['knowledge_status'],'CAPABILITY_RESOLVED')
        self.assertEqual(target['capability_id'],'backend.api_development')
        frozen=deepcopy(native);summary=summarize_stable_match(native)
        diagnostic=next(r for r in summary['taxonomy_resolution']['rows'] if r['requirement_id']==target['requirement_id'])
        self.assertEqual(diagnostic['capability_id'],target['capability_id']);self.assertEqual(diagnostic['status'],'resolved')
        self.assertEqual(native,frozen)

    def test_current_postgrest_evidence_policy_is_documented_not_changed(self):
        decision=taxonomy.evaluate_capability_evidence('backend.api_development',self.target,self.target['evidence'][0]['text'])
        self.assertEqual((decision['label'],decision['reason']),('direct','explicit_backend_api_implementation'))
        self.assertEqual(self.fixture['target_evidence_recovery']['selected_requirement_coverage'],0)
        self.assertEqual(self.fixture['target_evidence_recovery']['selected_requirement_overlap_count'],0)
        # Existing protocol completeness remains fail-closed for gRPC.
        compound={**self.target,'text':'Knowledge of API, REST, and gRPC','atomic_focus':'Knowledge of API, REST, and gRPC'}
        self.assertEqual(taxonomy.evaluate_capability_evidence('backend.api_development',compound,
            self.target['evidence'][0]['text'])['label'],'none')


if __name__=='__main__':unittest.main()

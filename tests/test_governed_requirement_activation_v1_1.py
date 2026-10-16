"""Actual governor, isolated native artifacts, no invented real approvals/gold."""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from taxonomy_discovery import governed_requirement_resolution as g, governed_publication as pub
from taxonomy_discovery.regression_corpus import build_regression_corpus
from tests.test_tqd3_regression_corpus import frozen_snapshot
from database.taxonomy_discovery_review_manager import save_governed_research_review, list_governed_research_results
from tailoring import capability_taxonomy as t
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge as resolve
from tailoring.capability_taxonomy import temporary_taxonomy_scope
from tests.governed_review_fixtures import write_taxonomy


def isolated_lifecycle(directory):
    row={'requirement_id':'req_9270e95898c8','text':'Design and develop RESTful APIs','importance':'core'}
    snapshot=frozen_snapshot(row['text']);snapshot.update(id=40,discovered_job_id=146)
    # Explicit test source, no candidate evidence qualification asserted.
    corpus=build_regression_corpus([snapshot])
    saved=g.create_local_governed_draft(row,[{'job_id':146,'snapshot_id':40,'requirement_id':row['requirement_id'],
        'job_content_hash':'isolated-test-source'}],explicit_execution=True,db_path=directory/'review.sqlite3')
    regression=g.validate_governed_draft(saved,corpus,explicit_execution=True,db_path=directory/'review.sqlite3')
    return row,saved,regression


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.directory=Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.path=self.directory/'taxonomy.json';write_taxonomy(self.path)
        self.stack.enter_context(patch.object(t,'TAXONOMY_PATH',self.path))
        self.db=self.directory/'review.sqlite3';t.get_default_taxonomy.cache_clear()
        self.addCleanup(t.get_default_taxonomy.cache_clear)

    def approve(self,saved,regression):
        return save_governed_research_review(saved['result']['research_result_id'],
            result_fingerprint=saved['result']['result_fingerprint'],decision='approve_for_publication',
            reviewer='ISOLATED TEST REVIEWER',notes='Test-only approval, not a real human or independent gold receipt',
            regression=regression,db_path=self.db)

    def test_real_persist_preview_approve_publish_reload_rollback(self):
        before=self.path.read_bytes();row,saved,regression=isolated_lifecycle(self.directory)
        self.assertEqual(resolve(row)['status'],'unresolved')
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(regression['publication_blockers'],[])
        self.assertEqual(regression['unexpectedly_changed_requirements'],[])
        self.assertFalse(pub.prepare_publication(saved['result']['research_result_id'],db_path=self.db)['ready'])
        self.approve(saved,regression)
        self.assertTrue(pub.prepare_publication(saved['result']['research_result_id'],db_path=self.db)['ready'])
        receipt=pub.publish_approved_change(saved['result']['research_result_id'],explicit_publish=True,
                                           db_path=self.db)
        self.assertEqual(receipt['status'],'published')
        t.get_default_taxonomy.cache_clear()
        current=resolve(row)
        self.assertEqual(current['decision']['capability_id'],'backend.api_development')
        self.assertEqual(current['recognition_rule'],g.API_RECOGNITION_FALLBACK)
        published=json.loads(self.path.read_text(encoding='utf-8'))
        old=json.loads(before)
        entry=lambda x:next(c for c in x['capabilities'] if c['capability_id']=='backend.api_development')
        self.assertEqual(entry(published)['requirement']['contextual_phrase_variants'],entry(old)['requirement']['contextual_phrase_variants'])
        self.assertNotEqual(published['taxonomy_version'],old['taxonomy_version'])
        self.assertEqual(resolve({'text':'Experience building RESTful APIs'})['decision']['capability_id'],'backend.api_development')
        self.assertEqual(resolve({'text':'Knowledge of REST APIs'})['status'],'unresolved')
        rollback=pub.rollback_recognition_publication(receipt['publication_id'],explicit_rollback=True,
            reviewer='ISOLATED TEST REVIEWER',db_path=self.db)
        self.assertEqual(rollback['status'],'rolled_back')
        self.assertEqual(resolve(row)['status'],'unresolved')
        self.assertNotEqual(t.get_default_taxonomy().version,old['taxonomy_version'])
        self.assertEqual(pub.list_linkage_receipts(db_path=self.db),[])

    def test_unapproved_rejected_stale_and_missing_controls_fail_closed(self):
        row,saved,regression=isolated_lifecycle(self.directory);before=self.path.read_bytes()
        with self.assertRaises(ValueError):pub.publish_approved_change(saved['result']['research_result_id'],db_path=self.db,refresh_jobs=False)
        bad=deepcopy(regression);bad.pop('recognition_policy_controls');bad.pop('regression_fingerprint')
        bad['regression_fingerprint']=g.fingerprint(bad)
        with self.assertRaises(ValueError):self.approve(saved,bad)
        save_governed_research_review(saved['result']['research_result_id'],result_fingerprint=saved['result']['result_fingerprint'],
            decision='reject',reviewer='ISOLATED TEST REVIEWER',db_path=self.db)
        self.assertFalse(pub.prepare_publication(saved['result']['research_result_id'],db_path=self.db)['ready'])
        self.approve(saved,regression)
        raw=json.loads(before);raw['taxonomy_version']='phase6d-capability-taxonomy-v99.0';self.path.write_text(json.dumps(raw),encoding='utf-8')
        self.assertFalse(pub.prepare_publication(saved['result']['research_result_id'],db_path=self.db)['ready'])

    def test_atomic_failure_preserves_native_artifact(self):
        row,saved,regression=isolated_lifecycle(self.directory);self.approve(saved,regression)
        before=self.path.read_bytes()
        with patch('database.technology_registry_proposal_manager.os.replace',side_effect=OSError('isolated staging failure')):
            with self.assertRaises(OSError):pub.publish_approved_change(saved['result']['research_result_id'],explicit_publish=True,db_path=self.db,refresh_jobs=False)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(resolve(row)['status'],'unresolved')

    def test_legacy_resolutions_preserved_and_unknown_rule_rejected(self):
        proposal=g.propose({'text':'Design and develop RESTful APIs'})
        texts=['Read REST API documentation','Experience developing web services',
            'Knowledge of Application Programming Interfaces (APIs) for web services using REST and RESTful web services',
            'Preferably experienced in web service access and development and USB audio processing to enhance software capabilities']
        comparisons=g.compare_inputs([{'text':text} for text in texts],proposal)
        self.assertTrue(all(x['after']==x['before'] for x in comparisons))
        entry=deepcopy(t.get_default_taxonomy().by_id()['backend.api_development'])
        entry['requirement']['recognition_fallback_rules']=[g.API_RECOGNITION_FALLBACK,g.API_RECOGNITION_FALLBACK]
        with self.assertRaises(ValueError):t._validate_capability(entry,set())

    def test_unseen_complete_scope_and_negatives(self):
        proposal=g.propose({'text':'Design and develop RESTful APIs'})
        positives=['Design and develop RESTful APIs','Develop RESTful API endpoints',
            'Build RESTful API services','Experience implementing RESTful APIs']
        self.assertTrue(all(r['after']['capability_id']=='backend.api_development'
            for r in g.compare_inputs([{'text':x} for x in positives],proposal)))
        with temporary_taxonomy_scope(g.preview_taxonomy(proposal)):
            for text in ['Read REST API documentation','Familiarity with REST API concepts',
                    'Product API services','Do not develop REST APIs','No API-development responsibility',
                    'Market RESTful APIs','RESTful APIs','Build RESTful APIs and gRPC services',
                    'Build RESTful APIs or gRPC services']:
                self.assertIsNone(t.classify_requirement_fallback_diagnostics({'text':text}),text)
        cases=[('YOU WILL CREATE RESTFUL APIS.',True),('Hands-on experience developing RESTful APIs.',True),
            ('You will implement REST APIs.',True),('Market RESTful APIs to customers',False),
            ('Develop RESTful APIs; operate SAP',False),('Never implement RESTful APIs',False),
            ('Experience building RESTful APIs or MQTT services',False)]
        for (text,expected),result in zip(cases,g.compare_inputs([{'text':x} for x,_ in cases],proposal)):
            self.assertEqual(result['after']['capability_id']=='backend.api_development',expected,text)

    def test_historical_false_positive_controls_current_paths(self):
        from analysis_stability.stable_evidence_scoring import build_stable_analysis
        self.assertNotEqual(resolve({'text':'(c) Front-end frameworks such as React, Node.js, or Angular 2'})['decision']['capability_id'],'language.modern_cpp')
        self.assertEqual(resolve({'text':'C++ development'})['decision']['capability_id'],'language.modern_cpp')
        for requirement,evidence in [('Experience in agile development teams','Frontend development'),('Knowledge of code reviews','code integration')]:
            stable=build_stable_analysis(jd_profile={'required_skills':[requirement]},keyword_match={'present':[],'missing':[{'keyword':requirement}]},
                resume_profile={'skills':{'skills':[evidence]},'projects':[],'experience':[],'education':[]},raw_resume_text=evidence)
            self.assertTrue(all(r['match_label']=='none' for r in stable['canonical_requirements']))
        for requirement,evidence in [('Experience in agile development teams','Worked in agile development teams using Scrum.'),
                ('Knowledge of code reviews','Performed code reviews and reviewed pull requests.')]:
            stable=build_stable_analysis(jd_profile={'required_skills':[requirement]},keyword_match={'present':[],'missing':[{'keyword':requirement}]},
                resume_profile={'skills':{'skills':[evidence]},'projects':[],'experience':[],'education':[]},raw_resume_text=evidence)
            # Explicit source statements preserve the existing lower-strength
            # distinction; a skills source is not verified employment credit.
            self.assertTrue(all(r['match_label']=='weak' for r in stable['canonical_requirements']))

    def test_streamlit_actual_isolated_validation_approval_and_publication(self):
        from streamlit.testing.v1 import AppTest
        snapshot=frozen_snapshot('Design and develop RESTful APIs')
        snapshot.update(id=40,discovered_job_id=146)
        corpus=build_regression_corpus([snapshot])
        app=AppTest.from_file(Path(__file__).with_name('governed_requirement_review_harness.py'),default_timeout=60)
        app.session_state['view']={'identity':{'discovered_job_id':146,'id':40,'job_content_hash':'same-hash'},
            'provenance':'ISOLATED_HISTORICAL_INSPECTOR_TEST',
            'requirements':[{'native':{'requirement_id':'req_9270e95898c8','text':'Design and develop RESTful APIs',
                                     'importance':'core','parent_text':'Design and develop RESTful APIs'}}]}
        button=lambda label:next(b for b in app.button if b.label==label)
        with patch.dict('os.environ',{'TAXONOMY_DISCOVERY_REVIEW_DB':str(self.db)}),\
             patch('taxonomy_discovery.regression_corpus.export_saved_corpus',return_value=corpus):
            app.run();button('Preview proposed correction').click().run();button('Validate draft').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(button('Approve validated draft').disabled)
            next(x for x in app.text_input if x.label=='Reviewer').set_value('ISOLATED TEST REVIEWER').run()
            next(x for x in app.checkbox if 'approve this exact' in x.label).check().run()
            button('Approve validated draft').click().run();button('Review approval readiness').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(button('Publish approved correction').disabled)
            next(x for x in app.checkbox if 'authorize publication' in x.label).check().run()
            button('Publish approved correction').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any('Published knowledge version' in x.value for x in app.success))
        self.assertEqual(resolve({'text':'Design and develop RESTful APIs'})['decision']['capability_id'],'backend.api_development')


if __name__=='__main__':unittest.main()

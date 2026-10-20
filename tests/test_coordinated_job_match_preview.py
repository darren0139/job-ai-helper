"""Application adapter expectations are independent of v1.20 fixture outputs."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from analysis_stability import stable_evidence_scoring as native
from analysis_stability import coordinated_integration as integration
from analysis_stability.coordinated_runtime import assert_analysis_publishable
from database import job_match_manager as matches, analysis_cache_manager as cache
from job_discovery import coordinated_preview as preview
from job_discovery.coordinated_preview_model import analysis_view, export_comparison, Label, reject_preview_ranking
from job_discovery.coordinated_sources import PROJECTED_SCORER_VERSION, verified_projection_ledger
from scripts.coordinated_job_match_preview_inputs import preview_inputs
from tailoring.jd_user_input_overrides import refresh_application_session_analysis_report

FIXTURE=Path(__file__).with_name('fixtures')/'coordinated_library_projection_v1.json'


def selected(result, family):
    return next(r for r in result.gated_analysis['canonical_requirements']
                if r.get('coordinated_action_receipt',{}).get('obligation',{}).get('object_family')==family)


class ComparisonAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected=json.loads(FIXTURE.read_text())
        cls.results={}
        for case_id in cls.expected['selected_labels']:
            request=preview.prepare_comparison(**preview_inputs(case_id))
            cls.results[case_id]=preview.run_comparison(request,developer_enabled=True)

    def test_independent_application_labels_and_parent_withholding(self):
        for case_id,label in self.expected['selected_labels'].items():
            result=self.results[case_id]
            family='backend' if case_id.startswith('B') else 'cloud' if case_id.startswith('C') else 'fullstack' if case_id.startswith('F') else 'embedded'
            row=selected(result,family)
            self.assertEqual((row['match_label'] or 'REVIEW_REQUIRED').upper(),label,case_id)
            self.assertEqual(result.gated.scoring_version,PROJECTED_SCORER_VERSION)
            self.assertEqual(result.published.scoring_version,native.SCORING_VERSION)
            if case_id in self.expected['conflicted_cases']:
                affected=[r for r in result.gated.requirements if r.conflict and r.conflict.get('quarantine')]
                self.assertEqual(len(affected),1,case_id)
                self.assertIsNone(affected[0].contribution)
                self.assertIsNone(result.gated.alignment)
            if case_id=='C03':
                self.assertEqual(row['match_label'],'direct')
                self.assertIsNone(selected(result,'backend')['match_value'])

    def test_e23_keeps_raw_text_but_only_its_verified_scoped_aliases(self):
        result=self.results['E23']
        ledger=result.gated_analysis['original_source_occurrence_ledger']
        denial=self.expected['same_project_denial']
        original=next(r for r in ledger['occurrences'] if r['kind']=='BULLET' and r['text']==denial)
        raw=next(r for r in ledger['occurrences'] if r['kind']=='RAW_TEXT' and r['text']==denial)
        self.assertEqual(original['container'],'resume_profile.projects[1]')
        self.assertIn(original['occurrence_id'],raw['verified_alias_occurrences'])
        self.assertTrue(raw['library_origins'][0]['library_item_id'])
        self.assertEqual(selected(result,'embedded')['match_label'],'direct')

    def test_e24_duplicate_originals_and_no_fallback(self):
        result=self.results['E24']
        ledger=result.gated_analysis['original_source_occurrence_ledger']['occurrences']
        conflict=selected(result,'embedded')['coordinated_action_receipt']['scoped_conflict']
        text=conflict['selected_positive']['text']
        originals=[r for r in ledger if r['kind']=='BULLET' and r['text']==text]
        self.assertEqual(len(originals),2)
        self.assertEqual(len({r['library_origins'][0]['library_item_id'] for r in originals}),2)
        self.assertEqual(conflict['selected_positive']['source'],'resume_profile.projects[0].bullets[0]')
        self.assertEqual(conflict['selection_policy'],'UNCHANGED_NATIVE_SELECTION_NO_LEDGER_FALLBACK')

    def test_raw_only_and_unindexed_denials_are_never_silently_clean(self):
        for field in ('raw_only_text','unindexed_notes'):
            inputs=preview_inputs('E23')
            if field=='raw_only_text':inputs[field]=self.expected['same_project_denial']
            else:inputs['evidence_items'][0][field]=self.expected['same_project_denial']
            result=preview.run_comparison(preview.prepare_comparison(**inputs),developer_enabled=True)
            row=selected(result,'embedded')
            self.assertIsNone(row['match_value'])
            self.assertEqual(row['coordinated_action_receipt']['scoped_conflict']['status'],'UNCERTAIN_SCOPE')

    def test_nullable_summary_table_export_and_rank_are_not_saved_summary(self):
        result=self.results['E04']
        self.assertEqual(result.gated.review_count,1)
        self.assertFalse(result.gated.score_available)
        for field in ('alignment','required_core','preferred','evidence_strength','rating_band'):
            self.assertIsNone(result.gated.summary()[field])
        rows=[r.table_record() for r in result.gated.requirements if r.label==Label.REVIEW_REQUIRED]
        self.assertTrue(rows)
        self.assertTrue(all(r['Credit'] is None and r['Credit display']=='Unavailable' for r in rows))
        exported=json.loads(export_comparison(result))
        self.assertIsNone(exported['gated_view']['alignment'])
        self.assertIsNone(exported['stable_analysis']['deterministic_alignment_score'])
        self.assertFalse(exported['ranking_eligible'])
        self.assertEqual(result.gated.summary()['counts']['REVIEW_REQUIRED'],1)
        with self.assertRaisesRegex(ValueError,'never eligible'):reject_preview_ranking(result)
        from job_discovery.matching import summarize_stable_match
        from job_discovery.match_ranking import best_match_sort_key
        with self.assertRaisesRegex(ValueError,'cannot be persisted'):summarize_stable_match(result.gated_analysis)
        with self.assertRaisesRegex(ValueError,'never eligible'):best_match_sort_key({'summary':result.gated.summary()})
        with self.assertRaisesRegex(ValueError,'never eligible'):best_match_sort_key(json.loads(export_comparison(result)))
        # Even a fully numeric developer receipt is never a saved ranking input.
        self.assertFalse(self.results['E23'].gated.ranking_eligible)

    def test_forged_review_zero_is_rejected_in_all_presentations(self):
        for field in ('match_value','synthetic_parent_contribution','deterministic_alignment_score','alignment_band'):
            analysis=deepcopy(self.results['E04'].gated_analysis)
            row=next(r for r in analysis['canonical_requirements'] if r.get('coordinated_action_receipt',{}).get('disposition')=='REVIEW_REQUIRED')
            if field=='match_value':row[field]=0
            elif field=='synthetic_parent_contribution':row['coordinated_action_receipt'][field]=0
            else:analysis[field]=0
            with self.subTest(field=field), self.assertRaises(ValueError):analysis_view(analysis)
            with self.assertRaises(ValueError):export_comparison(replace(self.results['E04'],gated_analysis=analysis))

    def test_published_summary_unchanged_and_transferable_remains_distinct(self):
        from job_discovery.matching import summarize_stable_match
        result=self.results['E23']
        published=result.published_analysis
        self.assertEqual(summarize_stable_match(published)['deterministic_alignment_score'],published['deterministic_alignment_score'])
        copied=deepcopy(published)
        row=copied['canonical_requirements'][0]
        row.update(match_label='transferable',match_value=native.MATCH_VALUES['transferable'])
        self.assertEqual(analysis_view(copied).requirements[0].label,Label.TRANSFERABLE)

    def test_controller_cannot_use_production_load_save_rank_or_model_routes(self):
        from job_discovery import matching, match_ranking
        with patch.object(matching,'analyze_job_match',side_effect=AssertionError('Saved pipeline forbidden')), \
             patch.object(matching,'current_evidence_context',side_effect=AssertionError('Live library forbidden')), \
             patch.object(matching,'summarize_stable_match',side_effect=AssertionError('Numeric-only summary forbidden')), \
             patch.object(match_ranking,'best_match_sort_key',side_effect=AssertionError('Ranking forbidden')), \
             patch.object(matches,'_connect',side_effect=AssertionError('DB forbidden')), \
             patch.object(cache,'_connect',side_effect=AssertionError('DB forbidden')):
            inputs=preview_inputs('E04'); inputs.pop('jd_profile')
            extractor=Mock(return_value={})
            request=preview.prepare_comparison(**inputs,jd_profile_extractor=extractor)
            result=preview.run_comparison(request,developer_enabled=True)
            extractor.assert_called_once_with(inputs['raw_jd_text'])
            for _ in range(2):self.assertIs(preview.retained_comparison(result,request),result)
            extractor.assert_called_once()
        with self.assertRaises(ValueError):preview.run_comparison(request)
        with self.assertRaises(ValueError):preview.prepare_comparison(**inputs)

    def test_preview_refresh_is_rejected_not_downgraded(self):
        for case_id in ('E04','E23'):
            result=self.results[case_id]
            report={'stable_analysis':result.gated_analysis,**preview_inputs(case_id)}
            frozen=deepcopy(report)
            with patch('tailoring.jd_user_input_overrides.build_stable_analysis',side_effect=AssertionError('No rebuild')):
                with self.assertRaisesRegex(ValueError,'isolated comparison'):
                    refresh_application_session_analysis_report(report)
            self.assertEqual(report,frozen)
            with self.assertRaisesRegex(ValueError,'isolated comparison'):
                refresh_application_session_analysis_report(json.loads(export_comparison(result)))

    def test_cache_identity_tracks_inputs_policy_and_source_without_reuse(self):
        inputs=preview_inputs('E23'); request=preview.prepare_comparison(**inputs)
        with patch.object(preview,'source_revision',return_value='source-change'):
            changed=preview.prepare_comparison(**inputs)
            self.assertNotEqual(request.identity,changed.identity)
            with self.assertRaisesRegex(ValueError,'stale'):
                preview.retained_comparison(self.results['E23'],request)
        changed_inputs=deepcopy(inputs);changed_inputs['evidence_items'][0]['id']=555
        self.assertNotEqual(request.identity,preview.prepare_comparison(**changed_inputs).identity)
        changed_inputs=deepcopy(inputs);changed_inputs['raw_jd_text']+='\nOriginal JD change.'
        self.assertNotEqual(request.identity,preview.prepare_comparison(**changed_inputs).identity)
        self.assertNotEqual(self.results['E23'].gated_analysis['input_fingerprint'],self.results['E23'].published_analysis['input_fingerprint'])

    def test_library_document_authority_is_not_interchangeable(self):
        request=preview.prepare_comparison(**preview_inputs('E23'))
        projection=deepcopy(request.projection);projection['authority']='ACTUAL_RESUME_DOCUMENT'
        with self.assertRaisesRegex(ValueError,'authority'):
            verified_projection_ledger(projection,projection['context']['resume_profile'],projection['context']['raw_resume_text'])
        with self.assertRaises(TypeError):preview.prepare_comparison(**preview_inputs('E23'),resume_text='document')

    def test_all_gated_versions_and_internal_connection_insert_reject_persistence(self):
        for version in ('stable-evidence-v1.18-phase6d22','stable-evidence-v1.19-phase6d23',integration.IDENTITIES['scoring_version'],PROJECTED_SCORER_VERSION):
            stable={'scoring_version':version,'canonical_requirements':[]}
            with self.assertRaises(ValueError):assert_analysis_publishable(stable)
            with patch.object(matches,'init_job_match_schema',side_effect=AssertionError('DB forbidden')):
                with self.assertRaisesRegex(ValueError,'cannot be persisted'):
                    matches.save_job_match_snapshot(discovered_job_id=1,job_content_hash='x',evidence_fingerprint='x',match_version='x',
                        scoring_version=version,taxonomy_version='x',jd_profile={},evidence_snapshot=[],stable_analysis=stable,summary={})
            with patch.object(cache,'init_analysis_cache',side_effect=AssertionError('DB forbidden')):
                with self.assertRaises(ValueError):cache.save_analysis_snapshot(application_id=1,input_fingerprint='x',report={'stable_analysis':stable},analysis_model='offline')
                with self.assertRaises(ValueError):cache.persist_explicit_application_analysis(application_id=1,input_fingerprint='x',
                    report={'raw_jd_text':'synthetic','stable_analysis':stable},analysis_model='offline',resume_filename='x',raw_jd_text='synthetic')
            connection=Mock()
            with self.assertRaisesRegex(ValueError,'cannot be persisted'):
                cache.insert_analysis_snapshot_with_connection(connection,application_id=1,input_fingerprint='x',report={'stable_analysis':stable},
                    analysis_model='offline',resume_filename='x',analysis_id='x',created_at='x')
            connection.execute.assert_not_called()
        with patch.object(cache,'init_analysis_cache',side_effect=AssertionError('DB forbidden')):
            with self.assertRaises(ValueError):cache.save_analysis_snapshot(application_id=1,input_fingerprint='x',
                report=json.loads(export_comparison(self.results['E23'])),analysis_model='offline')

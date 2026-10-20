"""Independent admission oracle; original scoring/ownership oracles stay frozen."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from analysis_stability import stable_evidence_scoring as n
from analysis_stability import jd_metadata_policy as p
from analysis_stability.coordinated_runtime import assert_analysis_publishable
from analysis_stability.coordinated_integration import canonicalise_coordinated_requirements
from job_discovery.coordinated_sources import build_library_projection

FIXTURE = Path(__file__).with_name('fixtures')/'jd_metadata_admission_v1.json'


def cases():
    fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
    return [dict(c, raw=(fixture['metadata']+fixture['core'] if c.get('layout') == 'metadata_then_core'
                        else fixture['core']+fixture['metadata'] if c.get('layout') == 'core_then_metadata'
                        else c['raw'])) for c in fixture['cases']]


def canonical(raw, profile=None):
    token = p.ACTIVE.set(p.classify(raw))
    try:
        return canonicalise_coordinated_requirements(profile or {}, raw)
    finally:
        p.ACTIVE.reset(token)


class MetadataAdmissionTests(unittest.TestCase):
    def test_independent_line_oracle_and_exact_raw_offsets(self):
        for case in cases():
            with self.subTest(case=case['id']):
                receipt = p.classify(case['raw'])
                self.assertEqual(receipt['raw_jd_text'], case['raw'])
                self.assertEqual([r['line_index'] for r in receipt['lines'] if r['classification']=='ADMINISTRATIVE_METADATA'],case['admin'])
                self.assertEqual([r['line_index'] for r in receipt['ambiguous_content']],case['ambiguous'])
                for index in case.get('admit', []):
                    self.assertTrue(receipt['lines'][index-1]['admitted'])
                for row in receipt['lines']:
                    self.assertEqual(case['raw'][slice(*row['raw_span'])],row['raw_text'])

    def test_first_wrong_transformation_is_raw_section_admission(self):
        before, after = cases()[:2]
        old_first = n.canonicalise_requirements({}, before['raw'])
        old_last = n.canonicalise_requirements({}, after['raw'])
        self.assertEqual(len(old_first['requirements']),3)
        self.assertEqual(len(old_last['requirements']),7)
        source = next(r for r in n._requirement_sources({},after['raw'])[0] if r['text']=='Period: Permanent')
        self.assertEqual(source['source'],'raw_jd.requirements')
        self.assertEqual(source['grounding']['section_heading'],'Job Requirements:')
        self.assertEqual(source['grounding']['line_index'],8)
        for case in (before,after):
            rows=canonical(case['raw'])['requirements']
            self.assertEqual([r['text'] for r in rows],['Design and maintain backend services','Develop REST APIs','Proficiency in Python'])
            self.assertEqual([r['group_weight_fraction'] for r in rows],[1,1,1])

    def test_frozen_job359_removes_exact_observed_metadata_without_reallocating_survivors(self):
        corpus=json.loads((FIXTURE.parent/'per_jd_scoring_audit.json').read_text(encoding='utf-8'))
        raw=next(j for j in corpus['snapshot']['audit']['corpus']['jobs'] if j['job_id']==359)['frozen_inputs']['raw_jd_text']
        old=canonicalise_coordinated_requirements({},raw)['requirements']
        new=canonical(raw)['requirements']
        expected={'Period','Permanent','Location','Jurong East (Shuttle service provided at selected MRT station)','Mon\u2013Fri 8am\u20135:30pm'}
        self.assertEqual({r['text'] for r in old}-{r['text'] for r in new},expected)
        old_by_id={r['requirement_id']:r for r in old}
        for row in new:
            self.assertEqual(row,old_by_id[row['requirement_id']])
        self.assertEqual(sum(r['group_weight_fraction'] for r in old),29)
        self.assertEqual(sum(r['group_weight_fraction'] for r in new),24)

    def test_vertical_metadata_profile_reentry_and_no_profile_only_fallback(self):
        profile={'required_skills':['Period','Permanent','Location','Jurong East','Mon\u2013Fri 8am\u20135:30pm']}
        for case in cases():
            rows=canonical(case['raw'],profile)['requirements']
            self.assertFalse(any(r['text'] in profile['required_skills'] for r in rows),case['id'])
        self.assertEqual(canonical(next(c['raw'] for c in cases() if c['id']=='metadata_only'),profile)['requirements'],[])
        # The published profile-only compatibility route remains available.
        self.assertTrue(n.canonicalise_requirements(profile)['requirements'])

    def test_legitimate_eligibility_technical_preference_and_duplicate_allocation(self):
        by_id={c['id']:c for c in cases()}
        for cid,count in (('eligibility',2),('technical_boundaries',3),('no_responsibilities',1),('field_with_obligation',2)):
            rows=canonical(by_id[cid]['raw'])['requirements']
            self.assertEqual(len(rows),count,cid)
            self.assertTrue(all(r['score_eligible'] for r in rows),cid)
        duplicate=canonical(by_id['duplicate_sections']['raw'])['requirements']
        self.assertEqual(len(duplicate),2)
        self.assertEqual([r['importance'] for r in duplicate],['core','preferred'])
        self.assertEqual([r['group_weight_fraction'] for r in duplicate],[1,1])
        self.assertEqual(len(duplicate[0]['source_provenance']),2)
        self.assertEqual(sum(x['contributes_scoring_allocation'] for x in duplicate[0]['source_provenance']),1)

    def test_default_off_context_reset_and_identity_separation(self):
        raw=cases()[1]['raw']
        kwargs=dict(jd_profile={},keyword_match={},raw_jd_text=raw,resume_profile={},retrieval_mode_override='off')
        original=n.build_stable_analysis(**kwargs)
        with self.assertRaisesRegex(ValueError,'defaults OFF'):p.build_metadata_preview(**kwargs)
        proposed=p.build_metadata_preview(**kwargs,developer_enabled=True)
        self.assertEqual(original,n.build_stable_analysis(**kwargs))
        self.assertEqual(n.SCORING_VERSION,'stable-evidence-v1.17-phase6d21')
        self.assertEqual(proposed['scoring_version'],p.SCORER_VERSION)
        self.assertNotEqual(proposed['input_fingerprint'],original['input_fingerprint'])
        self.assertEqual(len(proposed['canonical_requirements']),3)
        self.assertIsNone(p.ACTIVE.get())
        with patch('analysis_stability.coordinated_integration.build_coordinated_analysis',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):p.build_metadata_preview(**kwargs,developer_enabled=True)
        self.assertIsNone(p.ACTIVE.get())
        with self.assertRaisesRegex(ValueError,'original raw JD'):p.build_metadata_preview(**{**kwargs,'raw_jd_text':''},developer_enabled=True)

    def test_ambiguity_and_empty_requirement_set_withhold_not_none(self):
        from job_discovery.coordinated_preview_model import analysis_view
        for case in cases():
            if case['ambiguous'] or case['id']=='metadata_only':
                result=p.build_metadata_preview(developer_enabled=True,jd_profile={},keyword_match={},
                    raw_jd_text=case['raw'],resume_profile={},retrieval_mode_override='off')
                for field in ('deterministic_alignment_score','required_core_coverage_score','preferred_coverage_score','evidence_strength_score','alignment_band'):
                    self.assertIsNone(result[field],(case['id'],field))
                self.assertFalse(analysis_view(result).score_available)
                ambiguous={r['raw_text'] for r in result['jd_metadata_classification']['ambiguous_content']}
                self.assertFalse(ambiguous & {r['text'] for r in result['canonical_requirements']})

    def test_projected_e23_conflicts_and_companion_parent_under_new_gate(self):
        from scripts.coordinated_job_match_preview_inputs import preview_inputs
        for cid,expected,family in [('E23','direct','embedded'),('E04',None,'embedded'),('E05',None,'embedded'),('E24',None,'embedded'),('B05',None,'backend'),('C03','direct','cloud')]:
            inputs=preview_inputs(cid)
            projection=build_library_projection(inputs['evidence_items'],raw_only_text=inputs['raw_only_text'])
            result=p.build_metadata_preview(developer_enabled=True,source_projection=projection,
                jd_profile=inputs['jd_profile'],keyword_match={},raw_jd_text=inputs['raw_jd_text'],
                resume_profile=projection['context']['resume_profile'],raw_resume_text=projection['context']['raw_resume_text'],retrieval_mode_override='off')
            rows={r['coordinated_action_receipt']['obligation']['object_family']:r for r in result['canonical_requirements'] if r.get('coordinated_action_receipt')}
            self.assertEqual(rows[family]['match_label'],expected,cid)
            if cid=='C03':self.assertIsNone(rows['backend']['match_value'])
            if cid!='E23':self.assertIsNone(result['deterministic_alignment_score'],cid)
            self.assertIn('original_source_occurrence_ledger',result)

    def test_mixed_inline_metadata_is_retained_for_review_and_stop_section_does_not_erase_obligations(self):
        raw='Job Requirements:\nProficiency in Python.\nLocation: Jurong East; Must be available for rotating shifts.'
        receipt=p.classify(raw)
        self.assertEqual(receipt['ambiguous_content'][0]['reason'],'mixed_administrative_field_and_obligation_requires_review')
        self.assertEqual(len(canonical(raw)['requirements']),1)
        result=p.build_metadata_preview(developer_enabled=True,jd_profile={},keyword_match={},raw_jd_text=raw,resume_profile={},retrieval_mode_override='off')
        self.assertIsNone(result['deterministic_alignment_score'])
        self.assertIsNone(result['boundary_status'])
        self.assertIn('Must be available',result['jd_metadata_classification']['ambiguous_content'][0]['raw_text'])
        self.assertEqual(len(canonical('Benefits:\nMust be available for rotating shifts.')['requirements']),1)

    def test_publication_refresh_summary_ranking_reject_new_identity_before_io(self):
        from database import analysis_cache_manager as cache,job_match_manager as matches
        from job_discovery.matching import summarize_stable_match
        from job_discovery.match_ranking import best_match_sort_key
        from tailoring.jd_user_input_overrides import refresh_application_session_analysis_report
        bare={'scoring_version':p.SCORER_VERSION}
        for fn in (assert_analysis_publishable,summarize_stable_match,best_match_sort_key):
            with self.assertRaises(ValueError):fn(bare)
        with self.assertRaises(ValueError):refresh_application_session_analysis_report({'stable_analysis':bare})
        connection=Mock()
        with self.assertRaises(ValueError):cache.insert_analysis_snapshot_with_connection(connection,application_id=1,input_fingerprint='synthetic',report={'stable_analysis':bare},analysis_model='offline',resume_filename='synthetic',analysis_id='synthetic',created_at='synthetic')
        connection.execute.assert_not_called()
        with patch.object(matches,'_connect',side_effect=AssertionError('DB forbidden')):
            with self.assertRaises(ValueError):matches.save_job_match_snapshot(discovered_job_id=1,job_content_hash='synthetic',evidence_fingerprint='synthetic',match_version='synthetic',scoring_version=p.SCORER_VERSION,taxonomy_version='synthetic',jd_profile={},evidence_snapshot=[],stable_analysis=bare,summary={})

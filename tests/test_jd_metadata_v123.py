"""Independent v1.23 contracts; previous reference expectations stay immutable."""
from copy import deepcopy
import json
from pathlib import Path
from scripts.historical_source_fixtures import read_source, V122, SCORER_PATH, POLICY_PATH
import types
import unittest
from unittest.mock import Mock,patch

from analysis_stability import stable_evidence_scoring as n,jd_metadata_policy as v22,jd_metadata_v123 as p
from analysis_stability.coordinated_integration import canonicalise_coordinated_requirements

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/jd_metadata_v123_expectations.json'


def jobs():
    corpus=json.loads((ROOT/'tests/fixtures/per_jd_scoring_audit.json').read_text(encoding='utf-8'))
    return {j['job_id']:j['frozen_inputs']['raw_jd_text'] for j in corpus['snapshot']['audit']['corpus']['jobs']}


def canonical(raw):
    token=v22.ACTIVE.set(p.classify(raw))
    try:return canonicalise_coordinated_requirements({},raw)['requirements']
    finally:v22.ACTIVE.reset(token)


def build(raw,**kwargs):
    return p.build_metadata_preview(developer_enabled=True,jd_profile={},keyword_match={},raw_jd_text=raw,
        resume_profile={},retrieval_mode_override='off',**kwargs)


class MetadataV123Tests(unittest.TestCase):
    def test_independent_historical_line_expectations(self):
        corpus=jobs()
        cases=json.loads(FIXTURE.read_text(encoding='utf-8'))['cases']
        receipts={j:p.classify(corpus[j]) for j in {c['job_id'] for c in cases}}
        for case in cases:
            row=receipts[case['job_id']]['lines'][case['line']-1]
            self.assertEqual(row['raw_text'],case['original_text'])
            self.assertEqual(row['classification'],case['expected'],case)

    def test_job35_recovers_four_qualifications_not_heading_or_contract(self):
        raw=jobs()[35];rows=canonical(raw)
        texts={r['text'] for r in rows}
        for value in ('Strong analytical, reasoning and problem-solving skills','Meticulous with an eye for detail',
                      'Good oral and written communication skills','Team player who is proactive and collaborative'):
            self.assertIn(value,texts)
        self.assertNotIn('Skillset',texts)
        self.assertFalse(any('2-Year Contract' in text for text in texts))
        self.assertEqual(len(rows),20)
        self.assertEqual(sum(r['group_weight_fraction'] for r in rows),16)
        self.assertEqual(p.classify(raw)['unresolved_classifications'],[])

    def test_job48_recovers_three_duties_and_exact_native_parent_allocations(self):
        raw=jobs()[48]
        baseline={r['requirement_id']:r for r in canonicalise_coordinated_requirements({},raw)['requirements']}
        rows=canonical(raw)
        self.assertEqual(len(rows),16)
        self.assertEqual(sum(r['group_weight_fraction'] for r in rows),13)
        self.assertFalse(any(r['text']=='Other responsibilities include' for r in rows))
        for row in rows:
            old=baseline[row['requirement_id']]
            for field in ('requirement_id','atomic_group_id','scoring_parent_occurrence_id','group_weight_fraction','importance'):
                self.assertEqual(row[field],old[field],(row['text'],field))

    def test_metadata_45_359_stays_excluded(self):
        for jid in (45,359):
            raw=jobs()[jid];rows=canonical(raw)
            self.assertFalse(any(r['text'].startswith('Period') for r in rows))
            self.assertFalse(any(r['text'] in ('Permanent','Location','Mon\u2013Fri 8am\u20135:30pm') or 'Shuttle service' in r['text'] for r in rows))
        self.assertEqual(len(canonical(jobs()[359])),24)
        receipt=p.classify(jobs()[359])
        for index in (1,2,4):
            self.assertEqual(receipt['lines'][index-1]['classification'],'ADMINISTRATIVE_METADATA')
            self.assertIn('alias_of',receipt['lines'][index-1])

    def test_eligibility_technical_boundaries_and_administrative_adjacency(self):
        raw='Job Requirements:\nLocation: Jurong East\nExperience developing location-based applications.\nExperience with permanent data storage.\nExperience with periodic system maintenance.\nJob Information:\nMust be available for rotating shifts.\nA candidate must be willing to work on-site in Jurong East.'
        rows=canonical(raw)
        self.assertEqual(len(rows),5)
        self.assertTrue(any('on-site' in r['text'] for r in rows))
        self.assertTrue(any('rotating shifts' in r['text'] for r in rows))
        self.assertFalse(any(r['text']=='Location: Jurong East' for r in rows))
        self.assertEqual(p.classify(raw)['unresolved_classifications'],[])

    def test_unknown_heading_requires_grounded_context_and_two_children(self):
        for raw in ('Strange offerings:\nPython\nDocker','Skillset:\nTeam player',
                    'Job Information:\nNovel catalogue:\nStrong analytical skills\nGood communication skills'):
            result=build(raw)
            self.assertIsNone(result['deterministic_alignment_score'])
            self.assertTrue(result['jd_metadata_classification']['unresolved_classifications'])
        raw='Required Qualifications:\nCandidate strengths:\nExperience in Python.\nKnowledge of Docker.'
        rows=canonical(raw)
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['importance']=='required' for r in rows))

    def test_preferred_duplicates_wrapped_and_nested_source_receipts(self):
        raw='Preferred Qualifications:\nSkillset:\n- Experience in Python\n  with automated testing.\n  a) Knowledge of Docker.\nPreferred Qualifications:\n- Knowledge of Docker.'
        receipt=p.classify(raw)
        for record in receipt['lines']:
            self.assertEqual(raw[slice(*record['raw_span'])],record['raw_text'])
        rows=canonical(raw)
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['importance']=='preferred' for r in rows))
        self.assertEqual(sum(r['group_weight_fraction'] for r in rows),2)
        duplicate=next(r for r in rows if 'Docker' in r['text'])
        self.assertEqual(len(duplicate['source_provenance']),2)
        self.assertEqual(sum(s['contributes_scoring_allocation'] for s in duplicate['source_provenance']),1)

    def test_mixed_and_genuinely_ambiguous_content_keeps_null_scores(self):
        for raw in ('Job Requirements:\nProficiency in Python.\nLocation: Jurong East; Must be available for rotating shifts.',
                    'Job Requirements:\nProficiency in Python.\nThis is a 2-Year Contract where the candidate must work on-site.',
                    'Requirements:\nMysterious arrangements:\nSome operational arrangement'):
            result=build(raw)
            self.assertTrue(result['jd_metadata_classification']['unresolved_classifications'])
            for field in ('deterministic_alignment_score','required_core_coverage_score','preferred_coverage_score','evidence_strength_score','alignment_band','boundary_status'):
                self.assertIsNone(result[field])
        harmless=build('Job Requirements:\nProficiency in Python.\nThis is a 2-Year Contract.')
        self.assertIsNotNone(harmless['deterministic_alignment_score'])

    def test_administrative_boundary_does_not_silently_drop_bare_technical_content(self):
        for separator in ('\n','\n\n'):
            raw='Job Requirements:\nProficiency in Python.\nLocation: Jurong East'+separator+'Docker'
            result=build(raw)
            unresolved=result['jd_metadata_classification']['unresolved_classifications']
            self.assertEqual(unresolved[0]['raw_text'],'Docker')
            self.assertEqual(unresolved[0]['reason'],'unestablished_candidate_content_after_administrative_boundary')
            self.assertIsNone(result['deterministic_alignment_score'])
        self.assertEqual(len(canonical('Job Information:\nLocation: East\nSkillset:\nStrong analytical skills.\nGood communication skills.')),2)
        invite='Job Requirements:\nProficiency in Python.\nPeriod: December, extendable\nThose with relevant skillsets and interests may apply.'
        self.assertEqual(len(canonical(invite)),1)
        self.assertEqual(p.classify(invite)['lines'][-1]['classification'],'NON_REQUIREMENT_CONTEXT')
        notice='Job Requirements:\nProficiency in Python.\nPeriod: December, extendable\nPlease note that only shortlisted applicants will be notified.'
        self.assertEqual(p.classify(notice)['lines'][-1]['classification'],'ADMINISTRATIVE_METADATA')
        self.assertIsNotNone(build(notice)['deterministic_alignment_score'])
        compound=notice[:-1]+'; candidates must be available for rotating shifts.'
        self.assertIsNone(build(compound)['deterministic_alignment_score'])

    def test_no_candidate_cues_erased_as_organisation_context(self):
        for text in ('The company is a group where you must develop software.',
                     'Software Engineer proficient in Python',
                     'As a software engineer, you must maintain permanent storage.',
                     'The candidate is a developer with strong communication skills.'):
            receipt=p.classify(text)
            self.assertNotEqual(receipt['lines'][0]['classification'],'NON_REQUIREMENT_CONTEXT')

    def test_source_projection_conflicts_and_independent_cloud_credit(self):
        from scripts.coordinated_job_match_preview_inputs import preview_inputs
        from job_discovery.coordinated_sources import build_library_projection
        for cid,family,label in [('E23','embedded','direct'),('E04','embedded',None),('E05','embedded',None),
                                 ('E24','embedded',None),('B05','backend',None),('C03','cloud','direct')]:
            inputs=preview_inputs(cid)
            projection=build_library_projection(inputs['evidence_items'],raw_only_text=inputs['raw_only_text'])
            out=p.build_metadata_preview(developer_enabled=True,source_projection=projection,jd_profile={},keyword_match={},
                raw_jd_text=inputs['raw_jd_text'],resume_profile=projection['context']['resume_profile'],
                raw_resume_text=projection['context']['raw_resume_text'],retrieval_mode_override='off')
            rows={r['coordinated_action_receipt']['obligation']['object_family']:r for r in out['canonical_requirements'] if r.get('coordinated_action_receipt')}
            self.assertEqual(rows[family]['match_label'],label,cid)
            if cid=='C03':self.assertIsNone(rows['backend']['match_value'])
            if cid!='E23':self.assertIsNone(out['deterministic_alignment_score'])
            self.assertIn('original_source_occurrence_ledger',out)

    def test_v22_checkpoint_isolation_and_module_bytes(self):
        import analysis_stability
        source=read_source(V122, SCORER_PATH)
        historical=types.ModuleType('analysis_stability.checkpoint_native')
        historical.__package__='analysis_stability'
        historical.__file__=str(ROOT/'analysis_stability/stable_evidence_scoring.py')
        exec(compile(source,historical.__file__,'exec'),historical.__dict__)
        old_policy=read_source(V122, POLICY_PATH)
        self.assertEqual(old_policy.replace(b'\r\n',b'\n'),(ROOT/'analysis_stability/jd_metadata_policy.py').read_bytes().replace(b'\r\n',b'\n'))
        for jid in (35,48,359):
            kwargs=dict(jd_profile={},keyword_match={},raw_jd_text=jobs()[jid],resume_profile={},retrieval_mode_override='off')
            current=v22.build_metadata_preview(developer_enabled=True,**kwargs)
            with patch.object(analysis_stability,'stable_evidence_scoring',historical):
                baseline=v22.build_metadata_preview(developer_enabled=True,**kwargs)
            self.assertEqual(current,baseline,jid)

    def test_default_off_cache_identity_determinism_and_exception_reset(self):
        raw='Requirements:\nProficiency in Python.'
        kwargs=dict(jd_profile={},keyword_match={},raw_jd_text=raw,resume_profile={},retrieval_mode_override='off')
        with self.assertRaisesRegex(ValueError,'defaults OFF'):p.build_metadata_preview(**kwargs)
        first=build(raw);second=build(raw)
        self.assertEqual(first,second)
        self.assertEqual(first['scoring_version'],p.SCORER_VERSION)
        old=v22.build_metadata_preview(developer_enabled=True,**kwargs)
        self.assertNotEqual(first['input_fingerprint'],old['input_fingerprint'])
        self.assertNotEqual(first['input_fingerprint'],build(raw+'\nLocation: West')['input_fingerprint'])
        self.assertIsNone(v22.ACTIVE.get())
        with patch('analysis_stability.coordinated_integration.build_coordinated_analysis',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):build(raw)
        self.assertIsNone(v22.ACTIVE.get())

    def test_publication_summary_ranking_refresh_and_persistence_reject_before_io(self):
        from analysis_stability.coordinated_runtime import assert_analysis_publishable
        from database import analysis_cache_manager as cache,job_match_manager as matches
        from job_discovery.matching import summarize_stable_match
        from job_discovery.match_ranking import best_match_sort_key
        from tailoring.jd_user_input_overrides import refresh_application_session_analysis_report
        bare={'scoring_version':p.SCORER_VERSION}
        for fn in (assert_analysis_publishable,summarize_stable_match,best_match_sort_key):
            with self.assertRaises(ValueError):fn(bare)
        with self.assertRaises(ValueError):refresh_application_session_analysis_report({'stable_analysis':bare})
        conn=Mock()
        with self.assertRaises(ValueError):cache.insert_analysis_snapshot_with_connection(conn,application_id=1,input_fingerprint='synthetic',report={'stable_analysis':bare},analysis_model='offline',resume_filename='synthetic',analysis_id='synthetic',created_at='synthetic')
        conn.execute.assert_not_called()
        with patch.object(matches,'_connect',side_effect=AssertionError('No database')):
            with self.assertRaises(ValueError):matches.save_job_match_snapshot(discovered_job_id=1,job_content_hash='synthetic',evidence_fingerprint='synthetic',match_version='synthetic',scoring_version=p.SCORER_VERSION,taxonomy_version='synthetic',jd_profile={},evidence_snapshot=[],stable_analysis=bare,summary={})

    def test_all_83_human_review_sources_stay_exact_and_are_not_detector_oracles(self):
        fixture=json.loads((FIXTURE.parent/'jd_metadata_v123_span_review.json').read_text())['cases']
        self.assertEqual(len(fixture),83)
        self.assertEqual(len({c['job_id'] for c in fixture}),19)
        for case in fixture:self.assertEqual(jobs()[case['job_id']].splitlines()[case['line']-1],case['original_text'])

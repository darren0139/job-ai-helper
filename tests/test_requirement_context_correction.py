"""Independent classification expectations, synthetic evidence, frozen defaults."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from analysis_stability import stable_evidence_scoring as native
from analysis_stability.requirement_context_policy import (
    requirement_context_correction, SCORING_IDENTITY, POLICY_VERSION,
)


class RequirementContextCorrectionTests(unittest.TestCase):
    def canonical(self, text, section='Requirements'):
        return native.canonicalise_requirements({}, raw_jd_text=f'{section}:\n- {text}')

    def test_all_requested_examples_independent_expectations(self):
        cases = [
            ('Hands-on experience managing database systems required', 'required'),
            ('You will gain hands-on experience managing database systems', None),
            ('You will develop a traffic-control platform', 'core'),
            ('Experience developing traffic-control systems is required', 'required'),
            ('Ability to learn quickly', 'supporting'),
            ('Public Service Spirit', None),
            ('Plan and guide the professional growth of your team', None),
        ]
        with requirement_context_correction():
            for text, expected in cases:
                with self.subTest(text=text):
                    result = self.canonical(text)
                    if expected is None:
                        self.assertFalse(result['requirements'])
                        receipt = result['filtered_non_requirement_rows'][0]
                        self.assertFalse(receipt['score_eligible'])
                        self.assertEqual(receipt['source_provenance'][0]['grounding']['sentence_text'], text)
                    else:
                        self.assertEqual(len(result['requirements']), 1)
                        self.assertEqual(result['requirements'][0]['importance'], expected)

    def test_hard_qualification_and_preference_precedence(self):
        with requirement_context_correction():
            for text, section, expected in [
                ('Ability to learn quickly is mandatory', 'Requirements', 'required'),
                ('Ability to learn quickly', 'Required Qualifications', 'required'),
                ('Public Service Spirit', 'Required Qualifications', 'required'),
                ('Must demonstrate Public Service Spirit', 'Requirements', 'required'),
                ('Mentoring experience is required', 'Requirements', 'required'),
                ('Ability to learn quickly', 'Preferred Skills', 'preferred'),
                ('Ability to learn quickly is preferred', 'Requirements', 'preferred'),
                ('Must communicate clearly during emergency incident response', 'Requirements', 'required'),
            ]:
                with self.subTest(text=text, section=section):
                    self.assertEqual(self.canonical(text, section)['requirements'][0]['importance'], expected)

    def test_context_cannot_swallow_compound_technical_obligation(self):
        controls = [
            'You will gain hands-on experience and develop REST APIs',
            'You will gain hands-on experience or develop REST APIs',
            'Public Service Spirit: Design and implement secure database systems',
            'Public Service Spirit: Design secure database systems',
            'Public Service Spirit: Experience managing database systems',
            'Ability to learn quickly and implement secure REST APIs',
            'Plan and guide your team’s professional growth and maintain production services',
        ]
        for text in controls:
            before = self.canonical(text)
            with self.subTest(text=text), requirement_context_correction():
                after = self.canonical(text)
                self.assertEqual([r['text'] for r in after['requirements']],
                                 [r['text'] for r in before['requirements']])
                self.assertEqual([r['importance'] for r in after['requirements']],
                                 [r['importance'] for r in before['requirements']])
                self.assertFalse(after['filtered_non_requirement_rows'])

    def test_technical_duties_are_role_relevance_not_prior_experience_claims(self):
        with requirement_context_correction():
            result = self.canonical('You will develop a traffic-control platform', 'Responsibilities')
            row = result['requirements'][0]
            self.assertTrue(row['score_eligible'])
            self.assertEqual(row['importance'], 'core')
            self.assertEqual(row['assessment_basis'], 'role_relevance_not_prior_experience_prerequisite')
            self.assertEqual(row['group_weight_fraction'], 1)

    def test_generic_learning_is_supporting_not_an_evidence_grant(self):
        jd = 'Requirements:\n- Ability to learn quickly\n- Experience with SQL'
        with requirement_context_correction():
            analysis = native.build_stable_analysis(jd_profile={}, keyword_match={}, raw_jd_text=jd)
        self.assertTrue(all(r['match_label'] == 'none' for r in analysis['canonical_requirements']))
        self.assertEqual(analysis['required_core_requirement_count'], 1)
        self.assertEqual(analysis['supporting_requirement_count'], 1)
        self.assertEqual(analysis['deterministic_alignment_score'], 0)

    def test_context_only_jd_has_no_invented_zero_alignment(self):
        with requirement_context_correction():
            result = native.build_stable_analysis(jd_profile={}, keyword_match={},
                raw_jd_text='Requirements:\nPublic Service Spirit')
        self.assertIsNone(result['deterministic_alignment_score'])
        self.assertIsNone(result['required_core_coverage_score'])
        self.assertEqual(result['score_publication_status'], 'UNAVAILABLE_NO_SCORING_REQUIREMENTS')
        self.assertEqual(result['canonicalisation_debug']['semantic_eligibility_version'], POLICY_VERSION)

    def test_exclusion_conserves_remaining_allocations_and_source(self):
        text = 'You will gain hands-on experience managing database systems. You will develop REST APIs.'
        with requirement_context_correction():
            result = native.canonicalise_requirements({}, raw_jd_text=text)
        self.assertTrue(result['requirements'])
        self.assertAlmostEqual(sum(r['group_weight_fraction'] for r in result['requirements']), 1)
        for row in result['requirements']:
            self.assertIn('You will develop REST APIs', row['source_provenance'][0]['grounding']['sentence_text'])
        self.assertTrue(result['decomposition_debug']['unheaded_raw_exclusions'])

    def test_shared_workflows_authority_identity_determinism_and_persistence(self):
        from job_discovery.matching import _default_stable_builder, build_profile_evidence_context
        from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
        from tailoring.phase8_verification import build_current_baseline_analysis
        from analysis_stability.coordinated_runtime import assert_analysis_publishable
        from database import analysis_cache_manager as cache
        claim = 'Implemented Java REST API endpoints for database operations.'
        jd = 'Requirements:\n- Experience developing REST APIs\n- Ability to learn quickly\n- Public Service Spirit'
        profile = {'projects': [{'title': 'Synthetic service', 'bullets': [claim]}]}
        frozen = deepcopy(profile)
        context = build_profile_evidence_context([
            {'id': 71, 'category': 'Project', 'title': 'Synthetic service', 'bullets': [claim]}])
        before = _default_stable_builder(raw_jd_text=jd, jd_profile={}, context=context)
        with requirement_context_correction():
            finder = _default_stable_builder(raw_jd_text=jd, jd_profile={}, context=context)
            initial = analyze_actual_resume_against_jd(
                resume_text=claim, jd_text=jd, jd_profile={}, resume_profile=profile)['stable_analysis']
            phase8 = build_current_baseline_analysis(baseline_report={
                'jd_profile': {}, 'resume_profile': profile, 'keyword_match': {}}, raw_jd_text=jd)
            absent = analyze_actual_resume_against_jd(resume_text='Unrelated document only.',
                jd_text=jd, jd_profile={}, resume_profile=profile)['stable_analysis']
            self.assertTrue(all(r['match_label'] == 'none' for r in absent['canonical_requirements']))
            self.assertEqual(finder['input_fingerprint'], _default_stable_builder(
                raw_jd_text=jd, jd_profile={}, context=context)['input_fingerprint'])
        for result in (finder, initial, phase8):
            self.assertEqual(result['scoring_version'], SCORING_IDENTITY)
            self.assertEqual(result['requirement_context_policy_version'], POLICY_VERSION)
            self.assertEqual(len(result['canonical_requirements']), 2)
            with self.assertRaises(ValueError):
                assert_analysis_publishable(result)
        self.assertNotEqual(before['input_fingerprint'], finder['input_fingerprint'])
        self.assertEqual(before, _default_stable_builder(raw_jd_text=jd, jd_profile={}, context=context))
        self.assertEqual(profile, frozen)
        connection = Mock()
        with self.assertRaises(ValueError):
            cache.insert_analysis_snapshot_with_connection(connection, application_id=1,
                input_fingerprint='x', report={'stable_analysis': {'scoring_version': SCORING_IDENTITY}},
                analysis_model='offline', resume_filename='x', analysis_id='x', created_at='x')
        connection.execute.assert_not_called()

    def test_gate_off_corpus_geometry_and_saved_inputs_unchanged(self):
        data = json.loads(Path('tests/fixtures/per_jd_scoring_audit.json').read_text(encoding='utf8'))
        jobs = data['snapshot']['audit']['corpus']['jobs']
        frozen = deepcopy(jobs)
        counts = []
        corrected_counts = []
        removed = set()
        for job in jobs:
            raw = job['frozen_inputs']['raw_jd_text']
            before = native.canonicalise_requirements({}, raw_jd_text=raw)
            with requirement_context_correction():
                corrected = native.canonicalise_requirements({}, raw_jd_text=raw)
                self.assertEqual(corrected, native.canonicalise_requirements({}, raw_jd_text=raw))
            self.assertEqual(before, native.canonicalise_requirements({}, raw_jd_text=raw))
            counts.append(len(before['requirements']))
            corrected_counts.append(len(corrected['requirements']))
            original_ids = {r['requirement_id'] for r in before['requirements']}
            corrected_ids = {r['requirement_id'] for r in corrected['requirements']}
            self.assertFalse(corrected_ids - original_ids)
            removed.update((job['job_id'], rid) for rid in original_ids - corrected_ids)
        self.assertEqual(len(jobs), 30)
        self.assertEqual(sum(counts), 716)
        self.assertEqual(sum(corrected_counts), 714)
        self.assertEqual(removed, {(15, 'req_7b667a24f1e0'), (158, 'req_0c34f8e720fe')})
        self.assertEqual(jobs, frozen)

    def test_other_preview_policies_cannot_be_silently_composed(self):
        from analysis_stability.coordinated_runtime import approved_alias_surface_preview
        with approved_alias_surface_preview(), self.assertRaises(ValueError):
            with requirement_context_correction():
                pass
        with self.assertRaises(RuntimeError):
            with requirement_context_correction():
                raise RuntimeError('synthetic failure')
        self.assertEqual(self.canonical('Ability to learn quickly')['requirements'][0]['importance'], 'core')


if __name__ == '__main__':
    unittest.main()

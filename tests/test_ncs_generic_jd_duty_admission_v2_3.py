"""NCS 2.3.2: generic JD duties, technical-dot boundaries, and truth ceilings."""
from __future__ import annotations
import unittest

from analysis_stability.stable_evidence_scoring import (
    _raw_jd_content_spans,
    _normalise_requirement_surface,
    _split_requirement_sentences,
    canonicalise_requirements,
)


class NCSGenericJDDutyAdmissionV23(unittest.TestCase):
    def test_explicit_bulleted_tasks_survive_generic_job_description(self):
        from tests.test_fresh_scorer_evidence_rediscovery import JD_PROFILE, RAW_JD
        result = canonicalise_requirements(JD_PROFILE, RAW_JD)
        texts = [r['text'].casefold() for r in result['requirements']]
        self.assertTrue(any('quality assurance' in t for t in texts), texts)
        self.assertTrue(any('daily operations' in t for t in texts), texts)
        self.assertTrue(any('coordinate configuration' in t for t in texts), texts)
        spans = _raw_jd_content_spans(RAW_JD)
        relevant = [s for s in spans if s['text'].startswith('Operate and maintain')]
        self.assertEqual(1, len(relevant))
        self.assertTrue(relevant[0]['is_bullet'])
        self.assertEqual('structural_unheaded', relevant[0]['section_detection'])

    def test_fresh_capability_truth_ceiling_rediscovery_works(self):
        from tests.test_fresh_scorer_evidence_rediscovery import _analyses
        _, base, fresh = _analyses()
        ids = {r.get('capability_id') for r in fresh['canonical_requirements']}
        for expected in ('quality.qa_testing', 'operations.daily'):
            self.assertIn(expected, ids)
        self.assertGreaterEqual(fresh['deterministic_alignment_score'],
                                base['deterministic_alignment_score'])
        self.assertTrue(all(r.get('match_label') == 'none' for r in
            fresh['canonical_requirements'] if r.get('capability_id') == 'operations.daily'))

    def test_unheaded_explicit_responsibilities_sentence_kept(self):
        raw = 'Job Description\nResponsibilities include implementing production monitoring workflows.\n'
        rows = canonicalise_requirements({}, raw)['requirements']
        self.assertIn('Responsibilities include implementing production monitoring workflows',
                      [r['text'] for r in rows])

    def test_recruiting_benefits_and_unbulleted_marketing_still_rejected(self):
        raw = """Job Description
- Join our team to experience a supportive workplace.
- Competitive salary and benefits for employees.
We're a collaborative company building exciting opportunities.
- Operate production monitoring workflows.

Benefits
- Free transport and healthcare.
"""
        result = canonicalise_requirements({}, raw)
        texts = [r['text'] for r in result['requirements']]
        self.assertTrue(any('Operate production monitoring workflows' in t for t in texts), texts)
        self.assertFalse(any('Join our team' in t or 'Competitive salary' in t
                             or 'Free transport' in t or "We're a collaborative" in t
                             for t in texts), texts)

    def test_dotnet_and_ncs_format_regressions_stay_fixed(self):
        self.assertEqual('.NET', _normalise_requirement_surface('.NET'))
        self.assertEqual(['.NET'], _split_requirement_sentences('.NET'))
        self.assertEqual('.Net', _normalise_requirement_surface('.Net'))
        self.assertEqual(['.Net'], _split_requirement_sentences('.Net'))
        rows = canonicalise_requirements({}, 'Requirements\n.NET')['requirements']
        self.assertEqual(1, len(rows))
        self.assertEqual('.NET', rows[0]['atomic_focus'])
        from tests.test_phase9f_ncs_jd_source_repair_v1 import NCS_JD
        result = canonicalise_requirements({}, NCS_JD)
        self.assertEqual(12, len(result['requirements']))


if __name__ == '__main__':
    unittest.main()

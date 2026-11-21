import unittest
from analysis_stability.stable_evidence_scoring import (
    canonicalise_requirements, _raw_jd_content_spans, _REVIEW419_LEGACY_PARSER,
)


class GenericJDUnbulletedTaskRunV11(unittest.TestCase):
    def test_garena_independent_task_run_and_atomic_decomposition(self):
        raw = ("Job Description\n"
               "Operate and maintain the daily operations of the gaming product from configuration, quality assurance, live environment handling (including bugs and hacks), and operational evaluation.\n"
               "Coordinate configuration & QA tasks between different offices.\n"
               "Collaborate with both local and global stakeholders in resolving product-related problems.\n"
               "Job Requirements\nMinimum 1 year of experience in quality assurance.")
        parsed = canonicalise_requirements({}, raw)
        rows = parsed['requirements']
        first = [r for r in rows if 'daily operations of the gaming product' in r.get('parent_text','')]
        self.assertEqual(len(first), 6)
        self.assertEqual(len({r['requirement_id'] for r in first}), 6)
        self.assertTrue(all('raw_jd.unheaded_explicit_role_obligation' in r.get('sources',[]) for r in first))
        for term in ('gaming product configuration', 'gaming product quality assurance',
                     'live environment handling', 'bugs and hacks handling', 'operational evaluation'):
            self.assertTrue(any(term in r['text'].lower() for r in rows), term)
        self.assertTrue(any(r['text'].startswith('Coordinate configuration') for r in rows))
        self.assertTrue(any(r['text'].startswith('Collaborate with') for r in rows))

    def test_single_unheaded_imperative_is_still_excluded(self):
        raw = 'Job Description\nBuild scalable APIs for customers using Python and FastAPI.'
        parsed = canonicalise_requirements({},raw)
        self.assertFalse(parsed['requirements'])

    def test_blank_break_does_not_create_a_task_run(self):
        raw = ('Job Description\nDevelop scalable APIs for enterprise clients.\n\n'
               'Build automated reporting tools for internal operations.')
        self.assertFalse(canonicalise_requirements({},raw)['requirements'])

    def test_marketing_imperatives_cannot_form_task_run(self):
        raw = ('Job Description\nBuild your future with our exciting opportunities in technology.\n'
               'Develop your career with our supportive colleagues and mentors.')
        self.assertFalse(canonicalise_requirements({},raw)['requirements'])

    def test_true_consecutive_unbulleted_duties_are_admitted(self):
        raw = ('Job Description\nDevelop scalable REST APIs for internal enterprise clients.\n'
               'Build reliable internal tools that automate financial reports.')
        rows = canonicalise_requirements({},raw)['requirements']
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['semantic_type']=='role_responsibility' for r in rows))

    def test_reviewed_419_context_unchanged(self):
        raw = ('Job Description\nDevelop scalable REST APIs for internal enterprise clients.\n'
               'Build reliable internal tools that automate financial reports.')
        token=_REVIEW419_LEGACY_PARSER.set(True)
        try:
            from analysis_stability.stable_evidence_scoring import _mark_generic_jd_unbulleted_task_runs
            spans=_raw_jd_content_spans(raw)
            _mark_generic_jd_unbulleted_task_runs(spans)
            self.assertFalse(any(s.get('inferred_unbulleted_task_run') for s in spans))
        finally:
            _REVIEW419_LEGACY_PARSER.reset(token)


if __name__=='__main__':
    unittest.main()

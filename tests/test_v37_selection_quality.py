import unittest

from resume_builder.evidence_aware_fitting import build_evidence_aware_project_reductions
from scripts.v37_selection_quality import append_test_bullet
from tailoring.combined_project_bullet_sources_v2_7 import source_bullet_records


class SelectionQualityTests(unittest.TestCase):
    lead = 'Built a résumé tool and implemented project selection.'
    testing = 'Added automated tests and ran them in CI.'

    def slate(self):
        return {'words': len(self.lead.split()), 'word_cap': 30, 'proposal': {'projects': [{
            'project': 'Résumé tool', 'after': [self.lead], 'after_count': 1,
            'sources': [['Evidence Library']], 'supported_jd_ids': [[]], 'supporting_bullets': [],
        }]}}

    def candidate(self):
        return {'project': 'Résumé tool', 'text': self.testing, 'words': len(self.testing.split()),
                'source_labels': ['Evidence Library'], 'ids': set()}

    def test_forced_trial_preserves_lead_and_original_slate(self):
        original = self.slate()
        proposal = append_test_bullet(original, self.candidate(), total_limit=2, project_limit=2)
        row = proposal['projects'][0]
        self.assertEqual(row['after'], [self.lead, self.testing])
        self.assertEqual(row['after_count'], 2)
        self.assertEqual(row['supporting_bullets'], [self.testing])
        self.assertEqual(row['supported_jd_ids'], [[], []])
        self.assertEqual(original['proposal']['projects'][0]['after'], [self.lead])

    def test_forced_trial_respects_each_selection_limit(self):
        for total, project, words in ((1, 2, 30), (2, 1, 30), (2, 2, 10)):
            with self.subTest(total=total, project=project, words=words):
                slate = {**self.slate(), 'word_cap': words}
                with self.assertRaisesRegex(ValueError, 'constraint'):
                    append_test_bullet(slate, self.candidate(), total_limit=total, project_limit=project)

    def test_mixed_pool_first_record_is_lexical_not_a_role_contract(self):
        result = source_bullet_records({'resume_evidence': {'bullets': [self.lead]},
                                        'evidence_library_evidence': {'bullets': [self.testing]}})
        self.assertEqual([row['text'] for row in result], [self.testing, self.lead])

    def test_legacy_fitter_generates_removal_of_the_first_bullet_under_pressure(self):
        projects = {'recommended_projects': [{'title': 'Résumé tool', 'draft_bullets': [self.lead, self.testing],
                     'bullet_evidence_priorities': [{'bullet_index': 0, 'protect_during_fitting': True}]}]}
        alternatives = build_evidence_aware_project_reductions(projects)
        matching = [(state, change) for state, change in alternatives if change['removed_bullet'] == self.lead]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0][0]['recommended_projects'][0]['draft_bullets'], [self.testing])
        self.assertEqual(projects['recommended_projects'][0]['draft_bullets'][0], self.lead)

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import MagicMock

from tailoring.phase9f_v37_selection_evidence import project_weak_testing_links
from tailoring.phase9f_v37_trial_view import controlled_trial_rows, render_controlled_trials


class RepairedSelectionTests(unittest.TestCase):
    good = 'Added automated unit tests for checkout.'
    bad = 'Testing, testing, unit tests.'
    requirement = {'requirement_id': 'qa', 'text': 'Implement and test software', 'importance': 'core',
                   'capability_id': 'quality.qa_testing', 'semantic_type': 'role_responsibility',
                   'match_label': 'weak', 'evidence_strength': 2, 'group_weight_fraction': .5}

    def test_projection_reclaims_only_exact_performed_evidence_at_partial_weight(self):
        profile = {'projects': [{'title': 'Project', 'bullets': [self.good, self.bad]}]}
        model = {'bullets': [{'project': 'Project', 'text': text, 'source_labels': ['Evidence Library'],
                              'ids': {'qa'}} for text in (self.good, self.bad)]}
        evidence = [{'section': 'projects', 'source': f'resume_profile.projects[0].bullets[{i}]', 'text': text}
                    for i, text in enumerate((self.good, self.bad))]
        row = {**self.requirement, 'evidence': evidence + evidence[:1]}
        projected = project_weak_testing_links(model, {'qa': row}, [row], {'qa'}, profile, '\n'.join((self.good, self.bad)))
        self.assertEqual(len(projected['links']), 1)
        self.assertEqual(model['bullets'][0]['weak_ids'], {'qa'})
        self.assertNotIn('weak_ids', model['bullets'][1])
        self.assertEqual([b['ids'] for b in model['bullets']], [set(), set()])
        self.assertEqual(model['weak_weights'], {'qa': 4.5})

    def test_projection_rejects_overallocated_parent(self):
        req = {**self.requirement, 'atomic_group_id': 'parent', 'group_weight_fraction': .6,
               'evidence': [{'section': 'projects', 'source': 'resume_profile.projects[0].bullets[0]',
                             'text': self.good}]}
        catalog = {'qa': req, 'other': {**req, 'requirement_id': 'other'}}
        profile = {'projects': [{'title': 'Project', 'bullets': [self.good]}]}
        model = {'bullets': [{'project': 'Project', 'text': self.good, 'source_labels': ['Evidence Library'],
                              'ids': {'qa'}}]}
        result = project_weak_testing_links(model, catalog, [req], {'qa'}, profile, self.good)
        self.assertEqual(result['links'], [])
        self.assertEqual(model['weak_weights'], {})

    def trial_context(self):
        identities = {'jd_sha256': 'a'*64, 'scoring_version': 'scorer', 'layout_reference_sha256': 'b'*64,
                      'status': 'verified', 'pages': 1, 'docx_leads_verified': True}
        req = {'id': 'qa', 'text': self.requirement['text'], 'importance': 'core', 'match_label': 'none'}
        before = {**identities, 'score': 10, 'docx_sha256': 'c'*64, 'requirements': [req],
                  'docx_project_order': [{'project': 'Project', 'after': ['Lead']}]}
        after = {**identities, 'score': 12, 'docx_sha256': 'd'*64,
                 'requirements': [{**req, 'match_label': 'weak', 'evidence': [self.good], 'evidence_strength': 2}],
                 'docx_project_order': [{'project': 'Project', 'after': ['Lead', self.good]}]}
        decisions = [{'project': 'Project', 'wording': self.good, 'requirement_id': 'qa',
                      'requirement': req['text'], 'importance': 'core', 'included': True,
                      'provenance': ['Evidence Library'], 'shared': False, 'reason': 'Selected for weak coverage.'}]
        inputs = {'jd_sha256': 'a'*64, 'scoring_version': 'scorer', 'baseline_sha256': 'c'*64,
                  'trial_sha256': 'd'*64, 'catalog': {'qa': self.requirement},
                  'audit': {'docx_sha256': 'b'*64, 'verified': True, 'projects': [
                      {'project': 'Project', 'base': [], 'library': [{'text': self.good}]}]}}
        return {'baseline': before, 'trial': after, 'decisions': decisions}, inputs

    def verify(self, receipt, inputs):
        data = json.dumps(receipt).encode()
        return controlled_trial_rows(data, receipt_sha256=sha256(data).hexdigest(), **inputs)

    def test_read_only_view_requires_verified_identity_and_matching_exact_trial(self):
        receipt, inputs = self.trial_context()
        rows = self.verify(receipt, inputs)
        self.assertEqual(rows[0]['native_delta'], 2)
        for key, value in (('jd_sha256', '0'*64), ('trial_sha256', '0'*64),
                           ('baseline_sha256', '0'*64), ('scoring_version', 'wrong')):
            with self.subTest(key=key):
                self.assertEqual(self.verify(receipt, {**inputs, key: value}), [])
        for field, value in (('provenance', ['Selected Base']), ('importance', 'preferred'), ('wording', self.bad)):
            with self.subTest(field=field):
                changed = deepcopy(receipt)
                changed['decisions'][0][field] = value
                self.assertEqual(self.verify(changed, inputs), [])
        receipt['trial']['docx_project_order'][0]['after'].append('Another edit')
        self.assertIsNone(self.verify(receipt, inputs)[0]['native_delta'])
        st = MagicMock()
        render_controlled_trials(st, rows, [], 'Other project')
        st.caption.assert_any_call('Native bullet impact unmeasured.')

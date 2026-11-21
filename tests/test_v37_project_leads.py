from contextlib import nullcontext
import unittest
from unittest.mock import patch

from tailoring.phase9f_v37_neutral_selection import select_shadow
from tailoring.phase9f_v37_project_leads import (
    bind_project_leads, evaluate_lead_document, lead_first, validate_fitted_order, wording_digest,
)


def fixture():
    canonical = 'Built a dashboard for billing and led frontend delivery.'
    equivalent = 'Led interface delivery for a customer billing dashboard.'
    support = 'Implemented regression tests.'
    audit = {'verified': True, 'docx_sha256': 'document', 'projects': [{
        'project': 'Dashboard', 'base': [{'text': equivalent}, {'text': support}],
        'library': [{'text': canonical}, {'text': support}],
    }]}
    review = {'source_docx_sha256': 'document', 'projects': {'Dashboard': [
        {'source': 'library', 'position': 1, 'sha256': wording_digest(canonical), 'basis': 'Purpose and contribution'},
        {'source': 'base', 'position': 1, 'sha256': wording_digest(equivalent), 'basis': 'Same opening role'},
    ]}}
    model = {'groups': [({'project': 'Dashboard'}, {}, [0, 1, 2], [2, 1])],
             'max_words': 28, 'weights': {'test': 9}, 'bullets': [
        {'project': 'Dashboard', 'text': text, 'source_labels': sources,
         'ids': ids, 'words': len(text.split())}
        for text, sources, ids in [
            (canonical, ['Evidence Library'], set()), (equivalent, ['Selected Base'], set()),
            (support, ['Selected Base', 'Evidence Library'], {'test'}),
        ]
    ]}
    return model, audit, review, canonical, equivalent, support


class ProjectLeadTests(unittest.TestCase):
    def test_preference_is_canonical_then_verified_in_source_equivalent(self):
        _, audit, review, canonical, equivalent, _ = fixture()
        self.assertEqual(bind_project_leads(audit, review, {'base', 'library'})['leads']['Dashboard']['wording'], canonical)
        base = bind_project_leads(audit, review, {'base'})['leads']['Dashboard']
        self.assertEqual((base['wording'], base['role']), (equivalent, 'reviewed_equivalent'))

    def test_no_borrowing_and_stale_review_refused(self):
        model, audit, review, _, _, _ = fixture()
        review['projects']['Dashboard'].pop()
        self.assertEqual(select_shadow(model, audit, review, 'base_only')['status'], 'structurally_infeasible')
        audit['projects'][0]['library'][0]['text'] = 'Changed source'
        with self.assertRaisesRegex(ValueError, 'stale'):
            bind_project_leads(audit, review, {'library'})

    def test_lead_spends_budget_and_stays_ahead_of_higher_jd_evidence(self):
        model, audit, review, canonical, _, support = fixture()
        trial = select_shadow(model, audit, review, 'mixed')
        row = trial['proposal']['projects'][0]
        self.assertEqual(row['after'], [canonical, support])
        self.assertEqual(row['supporting_bullets'], [support])
        self.assertEqual(trial['words'], len(canonical.split()) + len(support.split()))
        only_lead = select_shadow(model, audit, review, 'mixed', max_words=len(canonical.split()))
        self.assertEqual(only_lead['proposal']['projects'][0]['after'], [canonical])
        too_tight = select_shadow(model, audit, review, 'mixed', max_words=len(canonical.split()) - 1)
        self.assertEqual(too_tight['failure'], 'word_or_count_budget')

    def test_shadow_selection_ignores_prior_membership_and_order(self):
        model, audit, review, _, _, _ = fixture()
        first = select_shadow(model, audit, review, 'mixed')
        model['groups'][0] = ({'project': 'Dashboard'}, {}, [2, 1, 0], [1, 0])
        model['baseline_indices'] = {0, 1}
        model['baseline_ids'] = {'different'}
        replay = select_shadow(model, audit, review, 'mixed')
        self.assertEqual(replay['indices'], first['indices'])
        self.assertEqual(replay['proposal']['projects'][0]['after'], first['proposal']['projects'][0]['after'])

    def test_reports_candidate_absence_separately_from_missing_intro(self):
        model, audit, review, _, _, _ = fixture()
        for row in model['bullets']:
            row['source_labels'] = [label for label in row['source_labels'] if label != 'Selected Base']
        self.assertEqual(select_shadow(model, audit, review, 'base_only')['failure'], 'insufficient_candidates')

    def test_validate_order_rejects_removed_reordered_and_duplicate_leads(self):
        _, audit, review, canonical, _, support = fixture()
        leads = bind_project_leads(audit, review, {'library'})['leads']
        self.assertEqual(lead_first('Dashboard', [support, canonical], leads), [canonical, support])
        for words in ([support], [support, canonical], [canonical, canonical]):
            with self.subTest(words=words), self.assertRaises(ValueError):
                validate_fitted_order([{'project': 'Dashboard', 'after': words}], leads)

    def test_docx_readback_and_one_page_are_both_required(self):
        _, audit, review, canonical, _, _ = fixture()
        leads = bind_project_leads(audit, review, {'library'})['leads']
        proposal = {'projects': [{'project': 'Dashboard', 'after': [canonical]}]}
        paragraph = type('P', (), {'text': '• ' + canonical})()
        for page_count in (1, 2):
            def trial(case, proposal, *, renderer, work_root):
                renderer('copy.docx', 'isolated')
                return {'status': 'verified' if page_count == 1 else 'fit_failed', 'pages': page_count}

            with patch('docx.Document', return_value=nullcontext()), patch(
                'tailoring.phase9f_joint_resume_optimizer_v2_6._bullet_locations', return_value=[[paragraph]],
            ), patch('tailoring.phase9f_v37_document_trial.evaluate_document_trial', side_effect=trial):
                result = evaluate_lead_document({}, proposal, leads, renderer=lambda *_: 'copy.pdf')
            self.assertEqual(result['docx_leads_verified'], page_count == 1)
            self.assertEqual(result['docx_project_order'][0]['after'], [canonical])

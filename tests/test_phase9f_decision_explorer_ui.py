import copy
import json
import unittest
from contextlib import nullcontext

from tailoring.phase9f_decision_explorer_ui import (
    build_explorer, render_project_tailoring_explorers, render_raw_json,
)
from tailoring.phase9f_prefit_dedupe_v39 import VERSION as PREFIT_VERSION
from tailoring.stable_tailoring_ranking import select_complementary_projects


def fixture():
    base = {'title': 'Tool', 'project_id': 'tool', 'currently_in_resume': True,
            'resume_evidence': {'bullets': ['Base wording']},
            'evidence_library_evidence': {'bullets': ['Alternate wording']}}
    other = {'title': 'Other', 'project_id': 'other', 'in_evidence_library': True,
             'evidence_library_evidence': {'bullets': ['Unselected wording']}}
    candidate = {'title': 'Extra', 'project_id': 'extra',
                 'resume_evidence': {'bullets': ['Frozen wording']}, 'currently_in_resume': True}
    ranks = [
        {'title': 'Tool', 'project_id': 'tool', 'selection_rank': 1, 'final_score': 30, 'recommendation': 'include'},
        {'title': 'Other', 'project_id': 'other', 'final_score': 0, 'recommendation': 'exclude'},
    ]
    plan = {'title': 'Tool', 'project_id': 'tool', 'allocated_bullet_count': 1, 'max_bullets_per_project': 3,
            'bullet_decision_receipts': [
                {'bullet_id': 'base', 'bullet': 'Base wording', 'selected': True,
                 'sources': ['base'], 'evidence_value': 0, 'word_count': 2,
                 'decision_context': {'selected': {'weak_evidence_value': 9}}},
                {'bullet_id': 'alt', 'bullet': 'Alternate wording', 'selected': False,
                 'sources': ['library'], 'reason': 'Not allocated'},
            ]}
    allocation = {'allocation_mode': 'adaptive', 'projects': [plan], 'selection_trace': [
        {'project_id': 'tool', 'bullet_id': 'base'}]}
    projects = {'recommended_projects': [{'project_id': 'tool', 'title': 'Tool'}],
                'candidate_project_ranking': ranks, 'deterministic_rule_debug': {'bullet_allocation': allocation},
                'projects_to_remove_or_deprioritize': [{'title': 'Other', 'reason': 'Saved exclusion'}],
                'metadata': {'version': 'original', 'optional': None, 'flag': False, 'number': 0, 'raw': ['x', {'one': 1}]}}
    return projects, [base, other, candidate]


class FakeStreamlit:
    def __init__(self, filtered=False):
        self.filtered = filtered
        self.downloads = {}
        self.raw = []
        self.tables = []

    def expander(self, *args, **kwargs):
        return nullcontext()

    def json(self, value, **kwargs):
        self.raw.append(value)

    def download_button(self, label, data, *, file_name, **kwargs):
        self.downloads[file_name] = (data, kwargs['on_click'])

    def dataframe(self, records, **kwargs):
        self.tables.append(records)

    def multiselect(self, label, choices, **kwargs):
        if self.filtered and 'filter_Decision' in kwargs['key']:
            return [choices[0]]
        return []

    def selectbox(self, label, choices, *, key, index=0, **kwargs):
        return None if index is None else choices[-1] if self.filtered else choices[0]

    def caption(self, *args):
        pass

    def markdown(self, *args):
        pass


class DecisionExplorerTests(unittest.TestCase):
    def test_complete_raw_payloads_preserved_across_filtering_and_sorting(self):
        projects, pool = fixture()
        original = copy.deepcopy(projects)
        expected = [projects['projects_to_remove_or_deprioritize'], projects['candidate_project_ranking'],
                    projects['deterministic_rule_debug']['bullet_allocation'], projects]
        runs = [FakeStreamlit(), FakeStreamlit(filtered=True)]
        for st in runs:
            render_project_tailoring_explorers(st, projects, pool, application_id=22, generation_id='frozen')
            self.assertEqual(st.raw, expected)
            self.assertEqual([json.loads(data) for data, _ in st.downloads.values()], expected)
            self.assertTrue(all(action == 'ignore' for _, action in st.downloads.values()))
        self.assertNotEqual(runs[0].tables, runs[1].tables)
        self.assertEqual(runs[0].downloads, runs[1].downloads)
        self.assertEqual(projects, original)

    def test_phase8_keeps_existing_filename_and_complete_trace(self):
        saved = {'schema': 'original', 'resume_changes': [{'status': 'Absent'}],
                 'decision_trace': {'wordings': [{'selected': False}, {'selected': True}]}}
        st = FakeStreamlit(filtered=True)
        name = 'phase9f_app_22_e4bf0c38_resume_changes.json'
        render_raw_json(st, saved, key='scope', filename=name, label='Download résumé decision trace (JSON)')
        self.assertEqual(json.loads(st.downloads[name][0]), saved)

    def test_explicit_zero_and_missing_points_remain_distinct(self):
        projects, pool = fixture()
        report = {'project_stages': [{'project': 'Tool', 'fitter_start': 1, 'actual_readback': 1}],
                  'bullet_stages': [{'project': 'Tool', 'wording': 'Base wording', 'fitter_start': 1,
                                     'actual_readback': 0}],
                  'independent_bullet_scores': {'status': 'available', 'bullets': [
                      {'project': 'Tool', 'wording': 'Base wording', 'standalone_weighted_points': 0}]}}
        fit = {'v39_auto_dedupe': {'version': PREFIT_VERSION, 'removals': [{
            'project': 'Tool', 'removed': 'Base wording', 'retained': 'Alternate wording',
            'removed_saved_evidence_points': 9, 'retained_saved_evidence_points': 9}]}}
        unbound = build_explorer(projects, pool, report=report, fit=fit)
        self.assertTrue(all(row['Pre-fit deduplication points'] is None for row in unbound['bullets']))
        explorer = build_explorer(projects, pool, report={**report, 'fit_bound': True}, fit=fit)
        bullets = {row['Wording']: row for row in explorer['bullets']}
        self.assertEqual(0, bullets['Base wording']['Independent saved-link points'])
        self.assertEqual(9, bullets['Base wording']['Weak allocation evidence'])
        self.assertEqual(9, bullets['Base wording']['Pre-fit deduplication points'])
        self.assertEqual('Absent', bullets['Base wording']['Final DOCX'])
        self.assertIsNone(bullets['Alternate wording']['Independent saved-link points'])
        self.assertEqual('Frozen, no allocation receipt', bullets['Frozen wording']['Decision'])
        self.assertIn('Unselected wording', bullets)

    def test_portfolio_exclusion_preserves_initial_allocation(self):
        projects, pool = fixture()
        projects['portfolio_quality_selection'] = {'excluded_project_ids': ['id:tool']}
        explorer = build_explorer(projects, pool)
        project = next(row for row in explorer['projects'] if row['Project'] == 'Tool')
        bullet = next(row for row in explorer['bullets'] if row['Wording'] == 'Base wording')
        self.assertEqual('Excluded before fitting', project['Decision'])
        self.assertEqual(1, project['Allocated'])
        self.assertEqual('Excluded by portfolio before fitting', bullet['Portfolio decision'])
        self.assertEqual('Allocated', bullet['Decision'])

    def test_competition_capture_does_not_change_selection_or_original_debug(self):
        ranks = [{'title': 'One', 'project_id': 'one', 'final_score': 42},
                 {'title': 'Two', 'project_id': 'two', 'final_score': 10}]
        expected = select_complementary_projects(ranked_rows=ranks, selected_count=1)
        receipt = []
        self.assertEqual(expected, select_complementary_projects(
            ranked_rows=ranks, selected_count=1, competition_trace=receipt))
        self.assertEqual(['selected', 'outside_near_tie_window'], [
            item['decision'] for item in receipt[0]['candidates']])
        self.assertEqual([42, 10], [row['selection_score'] for row in receipt[0]['candidates']])


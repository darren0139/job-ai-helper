"""UI display only: show each native category as earned / allocated points."""
from __future__ import annotations

from copy import deepcopy
import unittest

from tailoring.score_component_tables_ui import (
    _native_category_points_label, build_component_tables, component_exports,
    render_component_tables,
)
from tests.test_score_component_tables_ui import _sample


class _Capture:
    def __init__(self):
        self.headers = []
        self.tables = []
        self.captions = []
    def markdown(self, message, **kwargs):
        self.headers.append(message)
    def caption(self, message, **kwargs):
        self.captions.append(message)
    def dataframe(self, display, **kwargs):
        self.tables.append(display)
    def divider(self):
        pass
    def download_button(self, *args, **kwargs):
        pass
    def info(self, *args, **kwargs):
        pass
    def warning(self, message, **kwargs):
        raise AssertionError(message)


class NativeCategoryMaxDisplayTests(unittest.TestCase):
    def test_saved_native_weights_drive_headings_and_total_rows(self):
        receipt, breakdown = _sample()
        before = component_exports(build_component_tables(receipt, breakdown=breakdown))
        ui = _Capture()
        self.assertTrue(render_component_tables(ui, receipt, breakdown=breakdown,
                            key_prefix="native_category_v123", origin="unit"))
        self.assertIn('##### Required/Core coverage · 7.765 / 80 pts', ui.headers)
        self.assertIn('##### Preferred coverage · 2.200 / 10 pts', ui.headers)
        self.assertIn('##### Evidence strength · 6.000 / 10 pts', ui.headers)
        self.assertIn('##### Overall Job Match · 16/100', ui.headers)
        self.assertEqual(ui.tables[0][-1]['Requirement'],
            'TOTAL Required/Core coverage (15 requirements) · 7.765 / 80 pts')
        self.assertEqual(ui.tables[1][-1]['Requirement'],
            'TOTAL Preferred coverage (5 requirements) · 2.200 / 10 pts')
        self.assertEqual(ui.tables[2][-1]['Requirement'],
            'TOTAL evidence strength · 6.000 / 10 pts')
        self.assertEqual(ui.tables[0][-1]['Reference allocation (pts)'], 80)
        self.assertEqual(ui.tables[1][-1]['Reference allocation (pts)'], 10)
        self.assertIn('Category allocation (pts)', ui.tables[3][-1])
        self.assertEqual(before, component_exports(build_component_tables(receipt, breakdown=breakdown)))

    def test_nondefault_native_weights_do_not_display_fixed_80_10(self):
        receipt, breakdown = _sample()
        original = deepcopy(receipt)
        for row in receipt['jd_requirements']:
            change = (0.7 / 0.8) if row['importance'] != 'preferred' else (0.2 / 0.1)
            row['coverage_max_final_points'] *= change
            row['current_final_points'] = (
                row['coverage_max_final_points'] * row['match_value']
                + (1.5 if row['match_value'] else 0))
        for component in receipt['components']:
            if component['kind'] == 'required_core':
                component['weight'] = 0.7
            elif component['kind'] == 'preferred':
                component['weight'] = 0.2
            component['weighted_points'] = component['score'] * component['weight']
        receipt['subtotal_before_rounding'] = sum(c['weighted_points'] for c in receipt['components'])
        receipt['stored_scorer_score'] = round(receipt['subtotal_before_rounding'])
        ui = _Capture()
        self.assertTrue(render_component_tables(ui, receipt, breakdown=breakdown,
                            key_prefix='nondefault_v123', origin='unit'))
        self.assertTrue(any('/ 70 pts' in h for h in ui.headers), ui.headers)
        self.assertTrue(any('/ 20 pts' in h for h in ui.headers), ui.headers)
        self.assertTrue(any('/ 10 pts' in h for h in ui.headers), ui.headers)
        self.assertIn('/ 70 pts', ui.tables[0][-1]['Requirement'])
        self.assertIn('/ 20 pts', ui.tables[1][-1]['Requirement'])
        self.assertNotEqual(receipt['stored_scorer_score'], original['stored_scorer_score'])
        self.assertEqual(original['stored_scorer_score'], 16)

    def test_label_uses_existing_receipt_max_without_computing_new_score(self):
        receipt, _ = _sample()
        self.assertEqual(_native_category_points_label(receipt, receipt['components'][0]),
                         '7.765 / 80 pts')
        self.assertEqual(receipt['components'][0]['weighted_points'],
                         _sample()[0]['components'][0]['weighted_points'])


if __name__ == '__main__':
    unittest.main()

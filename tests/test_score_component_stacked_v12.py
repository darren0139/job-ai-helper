"""Pure contract checks: V1.2 stacked UI and stale identity explanation."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

from tailoring.receipt_currentness_ui import compare_receipt_identity, receipt_refresh_guidance
from tailoring.score_component_tables_ui import build_component_tables, render_component_tables
from tests.test_score_component_tables_ui import _sample


class _Ui:
    def __init__(self):
        self.tables = []
        self.notices = []
    def markdown(self, *args, **kwargs): pass
    def caption(self, *args, **kwargs): self.notices.append(args[0])
    def dataframe(self, rows, **kwargs): self.tables.append(rows)
    def download_button(self, *args, **kwargs): pass
    def divider(self): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): self.notices.append(args[0])


class StackedScoreUiTests(unittest.TestCase):
    def test_four_stacked_tables_total_rows_and_native_exports(self):
        receipt, breakdown = _sample()
        st = _Ui()
        self.assertTrue(render_component_tables(st, receipt, breakdown=breakdown,
                        key_prefix="test_v12", origin="test_v12"))
        self.assertEqual(len(st.tables), 4)
        required, preferred, evidence, overall = st.tables
        self.assertEqual(required[-1]['Requirement'], 'TOTAL Required/Core coverage (15 requirements) · 7.765 / 80 pts')
        self.assertEqual(preferred[-1]['Requirement'], 'TOTAL Preferred coverage (5 requirements) · 2.200 / 10 pts')
        self.assertEqual(evidence[-1]['Requirement'], 'TOTAL evidence strength · 6.000 / 10 pts')
        self.assertAlmostEqual(required[-1]['Coverage earned (pts)'], 7.765, places=3)
        self.assertAlmostEqual(preferred[-1]['Coverage earned (pts)'], 2.2)
        self.assertEqual(evidence[-1]['Evidence contribution (pts)'], 6.)
        self.assertEqual(overall[-1]['Weighted points earned'], 16)
        self.assertTrue(all(row['Match value'] is None or isinstance(row['Match value'], float) for row in required))

    def test_taxonomy_only_staleness_does_not_grant_currentness(self):
        old = {'jd_fingerprint':'same', 'taxonomy_fingerprint':'previous','scoring_version':'v'}
        now = {'jd_fingerprint':'same', 'taxonomy_fingerprint':'new','scoring_version':'v'}
        result = compare_receipt_identity(old, now)
        self.assertEqual(result['status'], 'taxonomy_changed')
        self.assertEqual(result['mismatched_fields'], ['taxonomy_fingerprint'])
        self.assertIn('Analyze Resume', receipt_refresh_guidance(result))
        self.assertNotEqual(result['status'], 'current')

    def test_unknown_mismatch_cannot_be_called_current(self):
        for saved,current in [({}, {}), ({'x':'1'},{'x':'2'}), ({'x':'1'},{'y':'2'})]:
            self.assertNotEqual(compare_receipt_identity(saved,current)['status'],'current')

    def test_no_nested_score_expanders_in_card(self):
        text = Path('job_discovery/ui.py').read_text(encoding='utf-8')
        self.assertIn('f"Full Match Analysis · #', text)
        self.assertNotIn('Show full saved score calculation for this card', text)
        # V1.1 allows several independently opened cards, not a singleton selector.
        self.assertIn('open_key = f"job_finder_inline_full_match_v1_{card_id}"', text)
        self.assertIn('st.session_state[open_key] = True', text)
        self.assertIn('inline_match_detail_slots.append((card_id, st.empty()))', text)
        self.assertIn('for selected_job_id, inline_match_detail_slot in inline_match_detail_slots:', text)
        self.assertIn('with inline_match_detail_slot.container():', text)
        self.assertNotIn('card_id == st.session_state[selected_job_key]', text)
        text = Path('tailoring/score_component_tables_ui.py').read_text(encoding='utf-8')
        self.assertNotIn('st.tabs(', text)
        app_source = Path('app.py').read_text(encoding='utf-8')
        self.assertIn('cached_authority.get("identity") == current_ab_identity(jd_text)', app_source)
        self.assertIn('cached_analysis = None', app_source)

if __name__ == '__main__': unittest.main()

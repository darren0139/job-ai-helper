import unittest
from unittest.mock import MagicMock, patch

from tailoring.phase8_row_ui import render_phase8_rows
from tailoring.phase8_score_explainability_ui import _jd_score_map_table
from tailoring.phase8_verification_ui import _render_final_improvement_verdict_v1


class Phase8VisualLabelsTest(unittest.TestCase):
    def test_selected_base_only_receipt_does_not_display_an_independent_initial(self):
        baseline = {'verified': True, 'before_score': 30, 'after_score': 31, 'delta': 1,
                    'hard_regressions': [], 'assessment': 'increased'}
        audit = {'status': 'improved_vs_both', 'comparisons': {
            'Initial': baseline, 'Selected Base': {**baseline, 'alias_of': 'Initial'},
        }}
        st = MagicMock()
        evidence = MagicMock()
        policy = MagicMock()
        st.expander.return_value = evidence
        evidence.expander.return_value = policy
        result = {'starting_document_contract': {'mode': 'selected_base_docx_only'}}
        with patch('tailoring.phase8_verification_ui.st', st), patch(
            'tailoring.phase8_final_improvement_verdict_v1.build_final_improvement_verdict', return_value=audit,
        ), patch('tailoring.phase8_verification_ui.render_phase8_rows') as table:
            _render_final_improvement_verdict_v1(result, baseline_mode='selected_base')
        st.markdown.assert_called_once_with('### Final check — Tailored vs Selected Base')
        self.assertIn('frozen Selected Base DOCX', st.success.call_args.args[0])
        rows = table.call_args.args[1]
        self.assertEqual([row['Baseline'] for row in rows], ['Selected Base'])
        self.assertEqual(rows[0]['Basis'], 'Frozen Selected Base DOCX')
        # Evidence must be written inside its own expander, not to the page.
        evidence.write.assert_called()
        evidence.expander.assert_called_once_with('Verification policy help', expanded=False)
        policy.caption.assert_called_once()

    def test_rows_keep_full_text_and_escape_saved_content(self):
        st = MagicMock()
        wording = 'Build and maintain ' + 'multidisciplinary application systems ' * 8 + '<script>alert(1)</script>'
        rows = _jd_score_map_table({'jd_requirements': [{'requirement': wording}]})
        self.assertEqual(rows[0]['JD requirement'], wording)
        render_phase8_rows(st, rows * 9, label='JD match detail')
        markup = st.html.call_args.args[0]
        self.assertIn('<h5>Build and maintain ', markup)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;</h5>', markup)
        self.assertIn('<dt>Earned</dt><dd>0.0</dd>', markup)
        self.assertIn('aria-label="JD match detail" tabindex="0"', markup)
        self.assertNotIn('<script>', markup)
        self.assertEqual(markup.count('<article>'), 9)

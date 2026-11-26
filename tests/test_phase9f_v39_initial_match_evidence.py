"""V3.9 initial / selected-source explanation is saved-only."""
from __future__ import annotations
import sys
import types
import unittest
from unittest.mock import patch
from tailoring.phase9f_v39_initial_match_evidence import requirement_explanation_rows

class InitialEvidenceRowsTests(unittest.TestCase):
    def test_uses_existing_match_strength_source_without_rescoring(self):
        mock = types.ModuleType('tailoring.initial_analysis_explainer')
        mock.explain_requirement = lambda row: {'explanation': 'Recorded direct evidence' if row['match_label']=='direct' else 'Review pending'}
        value={'canonical_requirements': [{
            'requirement_id': 'r1', 'text': 'Unit tests', 'importance': 'core',
            'match_label': 'weak', 'match_value': 0.2, 'evidence_strength': 2,
            'evidence': [{'text': 'Wrote automated tests', 'source': 'projects[0]'}]
        }]}
        with patch.dict(sys.modules, {'tailoring.initial_analysis_explainer': mock}):
            rows=requirement_explanation_rows(value)
        self.assertEqual(1, len(rows))
        self.assertEqual('Wrote automated tests', rows[0]['Selected evidence'])
        self.assertEqual(2, rows[0]['Evidence strength (0–5)'])
        self.assertEqual('Review pending', rows[0]['How it is matched'])
        self.assertEqual('r1', rows[0]['Requirement ID'])
    def test_malformed_and_duplicate_saved_ids_fail_closed(self):
        self.assertEqual([], requirement_explanation_rows({}))
        mock = types.ModuleType('tailoring.initial_analysis_explainer')
        mock.explain_requirement = lambda row: {'explanation': ''}
        with patch.dict(sys.modules, {'tailoring.initial_analysis_explainer': mock}):
            self.assertEqual([], requirement_explanation_rows({'canonical_requirements':[{'requirement_id':'r'}, {'requirement_id':'r'}]}))
if __name__=='__main__':unittest.main()

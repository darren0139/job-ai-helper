"""Phase 2B: independently specified later-report and frozen-generation controls.

Only synthetic records in disposable databases; never the copied development DB.
"""
from contextlib import closing
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from database import db_manager as db
from job_discovery import developer_real_comparison as real
from tailoring.phase9e_blueprint_selection import fingerprint_value
from tests import test_developer_real_comparison as support


class FrozenCompatibilityTests(unittest.TestCase):
    setUpClass = classmethod(support.RealComparisonTests.setUpClass.__func__)
    setUp = support.RealComparisonTests.setUp
    sql = support.RealComparisonTests.sql
    load = support.RealComparisonTests.load
    load_binding = support.RealComparisonTests.load_binding

    def initial_report(self):
        with closing(db._connect()) as conn:
            return json.loads(conn.execute(
                'SELECT report_json FROM application_analysis_versions WHERE application_id=?',
                (self.app_id,)).fetchone()[0])

    def legacy_generation(self):
        """Seed an explicit historical identity, never relabel current output as an oracle.

        This is an admission-only fixture. Its numeric rows are never scored or
        asserted to reproduce v1.16 research results.
        """
        binding = self.load_binding()
        source = binding['snapshot']
        source['scoring_version'] = 'stable-evidence-v1.16-phase6d20'
        source['taxonomy_version'] = 'phase6d-capability-taxonomy-v1.5'
        source['stable_analysis']['scoring_version'] = source['scoring_version']
        source['stable_analysis']['capability_taxonomy_version'] = source['taxonomy_version']
        self.sql('UPDATE job_match_snapshots SET scoring_version=?,taxonomy_version=?,stable_analysis_json=?',
                 (source['scoring_version'], source['taxonomy_version'], json.dumps(source['stable_analysis'])))
        binding['binding_fingerprint'] = fingerprint_value({k:v for k,v in binding.items() if k!='binding_fingerprint'})
        self.sql('UPDATE applications SET entry_binding_json=?', (json.dumps(binding),))
        report = self.initial_report()
        report['stable_analysis'] = deepcopy(source['stable_analysis'])
        report['meta']['initial_analysis_reference'] = deepcopy(binding)
        self.sql('UPDATE application_analysis_versions SET report_json=?,input_fingerprint=?',
                 (json.dumps(report), binding['binding_fingerprint']))
        return report

    def test_benign_later_metadata_alone_triggers_whole_report_guard(self):
        report = self.initial_report()
        changed = deepcopy(report)
        changed['meta']['jd_user_inputs'] = {'preferred_requirement_overrides': []}
        self.sql('UPDATE applications SET report_json=?', (json.dumps(changed),))
        before = self.path.read_bytes()
        with patch.object(real.preview, 'run_comparison') as run:
            with self.assertRaisesRegex(real.Blocked, 'current application report/local overrides'):
                self.load()
            run.assert_not_called()
        self.assertEqual(self.initial_report(), report)
        self.assertEqual(self.path.read_bytes(), before)

    def test_later_report_guard_masks_additional_historical_version_blocker(self):
        report = self.legacy_generation()
        changed = deepcopy(report)
        changed['raw_resume_text'] = 'Different synthetic current document'
        changed['meta'].pop('initial_analysis_reference')
        self.sql('UPDATE applications SET report_json=?', (json.dumps(changed),))
        before = self.path.read_bytes()
        with patch.object(real.preview, 'run_comparison') as run:
            with self.assertRaisesRegex(real.Blocked, 'current application report/local overrides'):
                self.load()
            run.assert_not_called()
        self.assertEqual(self.initial_report(), report)
        self.assertEqual(self.path.read_bytes(), before)

    def test_historical_generation_is_rejected_even_without_later_report(self):
        self.legacy_generation()
        before = self.path.read_bytes()
        with patch.object(real.preview, 'run_comparison') as run:
            with self.assertRaisesRegex(real.Blocked, 'STALE: saved match/scorer/taxonomy'):
                self.load()
            run.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)

    def test_later_metadata_cannot_mask_original_binding_corruption(self):
        changed = self.initial_report()
        changed['meta']['jd_user_inputs'] = {'preferred_requirement_overrides': []}
        self.sql('UPDATE applications SET report_json=?', (json.dumps(changed),))
        binding = self.load_binding()
        binding['raw_jd_sha256'] = 'invalid'
        self.sql('UPDATE applications SET entry_binding_json=?', (json.dumps(binding),))
        before = self.path.read_bytes()
        with self.assertRaisesRegex(real.Blocked, 'handoff identity is inconsistent'): self.load()
        self.assertEqual(self.path.read_bytes(), before)

    def test_original_receipt_input_change_is_not_a_later_report_annotation(self):
        report = self.initial_report()
        report['raw_resume_text'] = 'Tampered frozen original text'
        self.sql('UPDATE application_analysis_versions SET report_json=?', (json.dumps(report),))
        before = self.path.read_bytes()
        with self.assertRaisesRegex(real.Blocked, 'saved report inputs differ'): self.load()
        self.assertEqual(self.path.read_bytes(), before)

    def test_conflicting_original_reference_remains_rejected(self):
        report = self.initial_report()
        report['meta']['initial_analysis_reference']['initial_analysis_id'] = 'different-original'
        self.sql('UPDATE application_analysis_versions SET report_json=?', (json.dumps(report),))
        before = self.path.read_bytes()
        with self.assertRaisesRegex(real.Blocked, 'different source receipt'): self.load()
        self.assertEqual(self.path.read_bytes(), before)

"""Reject unexpected nested payloads even when an attacker reseals hashes."""
from copy import deepcopy
import unittest

from taxonomy_discovery import source_aware_inventory as inventory


class SourceInventorySafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        view=inventory.fixture_views(paths=[inventory.FIXTURES[0]])[0]
        view=deepcopy(view);view['requirements']=view['requirements'][:1]
        cls.export=inventory.build_export([view])

    def reject(self,mutate):
        data=deepcopy(self.export);mutate(data)
        for r in data['records']:
            r['exported_requirement_fingerprint']=inventory.digest(r['requirement'])
            r['original_requirement_fingerprint']=r['exported_requirement_fingerprint']
        data['export_fingerprint']=inventory.digest({k:v for k,v in data.items() if k!='export_fingerprint'})
        with self.assertRaises((ValueError, __import__('jsonschema').ValidationError)):
            inventory.validate_export(data)

    def test_unexpected_resume_text_inside_requirement(self):
        self.reject(lambda d:d['records'][0]['requirement'].update(resume_text='PRIVATE RESUME'))

    def test_selected_evidence_text_inside_stored_receipt(self):
        self.reject(lambda d:d['records'][0]['evidence']['stored_receipt'].update(selected_evidence_text='PRIVATE RESUME'))

    def test_sensitive_grounding_and_nested_diagnostic_objects(self):
        def inject(d):
            d['records'][0]['requirement']['source_provenance']=[dict(parent_occurrence_id='p',
                grounding={'secret_notes':{'body':'PRIVATE RESUME'}})]
        self.reject(inject)
        self.reject(lambda d:d['records'][0]['native_resolution']['taxonomy_diagnostics'].update(
            private_notes={'content':'PRIVATE RESUME'}))
        self.reject(lambda d:d['records'][0]['native_structure']['components'].append(
            {'text':'legitimate JD text','unknown_sensitive':{'resume':'PRIVATE'}}))

    def test_scalar_fields_cannot_hide_objects(self):
        self.reject(lambda d:d['records'][0]['requirement'].update(scope={'notes':'PRIVATE RESUME'}))
        self.reject(lambda d:d['records'][0]['evidence']['stored_receipt'].update(value={'body':'PRIVATE RESUME'}))

    def test_incomplete_records_and_tampered_fingerprint(self):
        self.reject(lambda d:d['records'][0].pop('readiness'))
        self.reject(lambda d:d['records'][0]['evidence'].update(stored_receipt={}))
        data=deepcopy(self.export);data['export_fingerprint']='0'*64
        with self.assertRaisesRegex(ValueError,'fingerprint'):
            inventory.validate_export(data)

    def test_unknown_source_grounding_is_rejected_before_export(self):
        view=deepcopy(inventory.fixture_views(paths=[inventory.FIXTURES[0]])[1])
        view['requirements']=view['requirements'][:1]
        view['requirements'][0]['source_provenance'][0]['grounding']['private_notes']='PRIVATE RESUME'
        with self.assertRaisesRegex(ValueError,'Unsupported nested'):
            inventory.build_export([view])

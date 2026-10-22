"""Closure boundaries: do not turn a diagnostic contract into a lexical grant."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from analysis_stability import stable_evidence_scoring as native
from taxonomy_discovery import governed_requirement_resolution as review
from taxonomy_discovery import resolver_improvement as resolver
from taxonomy_discovery import governed_publication as publication
from tailoring.capability_taxonomy import temporary_taxonomy_scope
from tests.test_reviewed_api_plural import source
from tests.test_governed_requirement_activation_v1_1 import isolated_lifecycle
from tests.governed_review_fixtures import isolated_taxonomy


class A1GovernanceClosureTests(unittest.TestCase):
    def test_complete_a1_sources_are_not_missing_but_existing_draft_contract_rejects_them(self):
        cases=[
            'Proven experience building efficient, secure RESTful APIs with frameworks such as Express.js, Fastify, FastAPI, Spring Boot, or equivalent enterprise-grade tools',
            'Develop and integrate RESTful APIs with front-end applications',
            'Experience developing and consuming RESTful APIs',
        ]
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'must-not-create.sqlite3'
            for text in cases:
                row,raw=source(text)
                self.assertTrue(review.api_plural_review(row,raw,explicit_execution=True)['recognition_changed'])
                with self.subTest(text=text),patch('sqlite3.connect',side_effect=AssertionError('No store needed')):
                    with self.assertRaisesRegex(ValueError,'No complete bounded REST'):
                        review.create_local_governed_draft(row,[{'job_id':'SYNTHETIC','snapshot_id':'SYNTHETIC',
                            'requirement_id':row['requirement_id']}],explicit_execution=True,db_path=db)
            self.assertFalse(db.exists())

    def test_generic_plural_overlay_does_not_implement_review_required_credit(self):
        text='Develop efficient, secure RESTful APIs'
        row,raw=source(text)
        receipt=review.api_plural_review(row,raw,explicit_execution=True)
        self.assertIsNone(receipt['parent_contribution'])
        self.assertIsNone(receipt['whole_jd_score'])
        frozen=deepcopy(row)
        overlay=resolver.additive_phrase_overlay('backend.api_development',['restful apis'],identity='synthetic-closure')
        with temporary_taxonomy_scope(overlay):
            numeric=native.build_stable_analysis(jd_profile={},keyword_match={},raw_jd_text=raw,
                resume_profile={'projects':[{'title':'Synthetic endpoint author',
                    'bullets':['Implemented custom Java REST API endpoints.']}]})
        self.assertIsNotNone(numeric['deterministic_alignment_score'])
        self.assertEqual(row,frozen)
        observation={'source':'SYNTHETIC ONLY','diagnostic_credit':None,
            'ordinary_native_score':numeric['deterministic_alignment_score'],
            'labels':[r['match_label'] for r in numeric['canonical_requirements']],
            'interpretation':'Generic phrase publication cannot carry null-credit review semantics.'}
        scratch=os.environ.get('JOB_MATCH_TEST_SCRATCH')
        if scratch:(Path(scratch)/'a1_governance_boundary.json').write_text(json.dumps(observation,indent=2)+'\n',encoding='utf-8')
        print('A1_GOVERNANCE_BOUNDARY',json.dumps(observation))

    def test_supported_legitimate_lifecycle_stops_without_human_approval_and_v1_is_stale(self):
        # The supported old bounded contract is a control, NOT an A1 artifact.
        # No reviewer approval is written, even in this disposable control.
        with isolated_taxonomy(),tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            _,saved,regression=isolated_lifecycle(root)
            self.assertFalse(saved['result']['approval'])
            self.assertTrue(saved['draft']['requires_human_approval'])
            self.assertTrue(regression['review_only'])
            before=publication.prepare_publication(saved['result']['research_result_id'],db_path=root/'review.sqlite3')
            self.assertFalse(before['ready'])
            stale=deepcopy(saved['draft'])
            stale['resolver_draft_version']='tqd3-resolver-improvement-h1.2-v1'
            stale.pop('draft_fingerprint');stale.pop('resolver_draft_id')
            stale['draft_fingerprint']=resolver.fingerprint(stale)
            stale['resolver_draft_id']='tqd3resolver_'+stale['draft_fingerprint'][:24]
            with self.assertRaisesRegex(ValueError,'Governed resolver draft required'):
                resolver.resolver_overlay(stale)
            self.assertEqual(publication.prepare_publication(saved['result']['research_result_id'],db_path=root/'review.sqlite3'),before)

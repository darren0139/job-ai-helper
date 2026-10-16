from copy import deepcopy
import io
import json
from pathlib import Path
import unittest
import zipfile
from unittest.mock import patch

from taxonomy_discovery import governed_requirement_resolution as g
from tailoring.capability_taxonomy import get_default_taxonomy, temporary_taxonomy_scope, _validate_capability
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge as resolve
from tailoring.phase6d_stable_scoring_adapter import cap_requirement_with_taxonomy
from tailoring.requirement_scope import bounded_api_development_scope
from tests.governed_review_fixtures import isolated_taxonomy


class GovernedResolutionTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(isolated_taxonomy())
        self.row={'requirement_id':'development-only','text':'Design and develop RESTful APIs',
                  'atomic_focus':'Design and develop RESTful APIs','importance':'core','group_weight_fraction':1.0}
        self.proposal=g.propose(self.row)

    def test_native_before_after_and_no_default_activation(self):
        base=get_default_taxonomy()
        self.assertEqual(resolve(self.row)['status'],'unresolved')
        report=g.preview(self.proposal,explicit_execution=True)
        self.assertEqual(report['selected_requirement']['after']['capability_id'],'backend.api_development')
        self.assertIs(get_default_taxonomy(),base)
        self.assertEqual(resolve(self.row)['status'],'unresolved')
        self.assertEqual(self.row['group_weight_fraction'],1.0)

    def test_controls_generalize_without_job_ids_and_fail_closed(self):
        report=g.preview(self.proposal,explicit_execution=True)
        self.assertTrue(report['validation_passed'])
        self.assertEqual(len(report['controls']),13)
        with self.assertRaises(ValueError):g.preview(self.proposal)
        self.assertFalse(report['activation_ready'])

    def test_scope_negative_parent_familiarity_optional_negation_and_alternatives(self):
        for text in ('Familiarity with RESTful APIs','RESTful APIs are preferred',
                     'Do not develop RESTful APIs','Develop RESTful APIs and SQL databases',
                     'Develop RESTful APIs or gRPC APIs','Build RESTful APIs for AWS'):
            with self.subTest(text=text):self.assertIsNone(bounded_api_development_scope({'text':text}))
        row={**self.row,'parent_text':'Design and develop RESTful APIs and maintain databases'}
        self.assertIsNone(bounded_api_development_scope(row))
        self.assertIsNone(bounded_api_development_scope({**self.row,'atomic_focus':'RESTful APIs'}))
        self.assertIsNone(bounded_api_development_scope({**self.row,'is_atomic':True}))

    def test_exact_v2_source_case_only_one_of_thirteen_changes(self):
        path=Path(__file__).resolve().parents[1]/'reports/unresolved_existing_predicate_investigation_v2_manifest.json'
        manifest=json.loads(path.read_text(encoding='utf-8'))
        row=next(x['input'] for x in manifest['cases'] if x['job_id']==146)
        proposal=g.propose(row)
        result=g.compare_inputs([x['input'] for x in manifest['cases']],proposal)
        changed=[x for x in result if x['knowledge_changed']]
        self.assertEqual([x['requirement_id'] for x in changed],['req_9270e95898c8'])
        self.assertEqual(changed[0]['after']['capability_id'],'backend.api_development')

    def test_parent_grounding_preserved_missing_or_conflicting_occurrence_rejected(self):
        source={'parent_occurrence_id':'development-parent','parent_text':self.row['text'],
                'raw_parent_text':self.row['text'],'source':'raw_jd.responsibilities'}
        row={**self.row,'parent_text':self.row['text'],'source_provenance':[source],'is_atomic':True}
        self.assertIsNotNone(bounded_api_development_scope(row))
        bad=deepcopy(row);bad['source_provenance'][0]['raw_parent_text']='Develop APIs and manage databases'
        self.assertIsNone(bounded_api_development_scope(bad))
        bad=deepcopy(row);bad['source_provenance'].append({})
        self.assertIsNone(bounded_api_development_scope(bad))

    def test_approval_cannot_bypass_existing_governor(self):
        validation=g.preview(self.proposal,explicit_execution=True)
        with self.assertRaisesRegex(ValueError,'Explicit human'):g.activate(self.proposal,validation)
        with self.assertRaisesRegex(ValueError,'Governed approval'):
            g.activate(self.proposal,validation,explicit_confirmation=True)
        invalid=deepcopy(validation);invalid['validation_passed']=False
        with self.assertRaisesRegex(ValueError,'Validation stale'):
            g.activate(self.proposal,invalid,explicit_confirmation=True)
        self.assertEqual(resolve(self.row)['status'],'unresolved')

    def test_edited_or_stale_preview_cannot_replay(self):
        bad=deepcopy(self.proposal);bad['proposed_change']['recognition_fallback_rules'][0]['kind']='arbitrary'
        with self.assertRaises(ValueError):g.preview_taxonomy(bad)
        with patch.object(g,'knowledge_fingerprint',return_value='new knowledge'):
            with self.assertRaises(ValueError):g.preview_taxonomy(self.proposal)

    def test_native_version_and_knowledge_currentness_use_existing_contract(self):
        before=g.current_match_versions();knowledge=g.knowledge_fingerprint()
        overlay=g.preview_taxonomy(self.proposal)
        with temporary_taxonomy_scope(overlay):
            after=g.current_match_versions()
            self.assertNotEqual(after['taxonomy_version'],before['taxonomy_version'])
            self.assertEqual(after['scoring_version'],before['scoring_version'])
            self.assertNotEqual(g.knowledge_fingerprint(),knowledge)
        self.assertEqual(g.current_match_versions(),before)

    def test_schema_rejects_arbitrary_scope_policies_and_other_capabilities(self):
        entry=deepcopy(get_default_taxonomy().by_id()['backend.api_development'])
        entry['requirement']['scope_policy']='arbitrary-rule'
        with self.assertRaises(ValueError):_validate_capability(entry,set())
        entry['requirement']['scope_policy']=g.API_DEVELOPMENT_SCOPE_POLICY
        entry['capability_id']='database.design'
        with self.assertRaises(ValueError):_validate_capability(entry,set())

    def test_native_evidence_caps_do_not_promote_unproven_implementation(self):
        row={**self.row,'match_label':'direct','match_value':1.0,'evidence_strength':5,
             'evidence':[{'text':'Listed RESTful APIs among tools.'}]}
        frozen=deepcopy(row)
        with temporary_taxonomy_scope(g.preview_taxonomy(self.proposal)):
            capped=cap_requirement_with_taxonomy(row,retrieval_mode_override='off')
        self.assertEqual(capped['match_label'],'none')
        self.assertEqual(capped['capability_id'],'backend.api_development')
        self.assertEqual(capped['importance'],'core')
        self.assertEqual(capped['group_weight_fraction'],1.0)
        self.assertEqual(row,frozen)

    def test_scoring_formula_runs_natively_not_in_preview(self):
        from analysis_stability.stable_evidence_scoring import build_stable_analysis, SCORING_VERSION
        inputs={'jd_profile':{'required_skills':[self.row['text']],'responsibilities':[], 'preferred_skills':[]},
                'keyword_match':{'present':[],'missing':[{'keyword':self.row['text']}]},
                'resume_profile':{'education':[],'experience':[],'projects':[], 'skills':{}},'raw_resume_text':''}
        before=build_stable_analysis(**inputs)
        with temporary_taxonomy_scope(g.preview_taxonomy(self.proposal)):
            after=build_stable_analysis(**inputs)
        self.assertEqual(before['scoring_version'],SCORING_VERSION)
        self.assertEqual(after['scoring_version'],SCORING_VERSION)
        self.assertEqual(after['deterministic_alignment_score'],0)
        self.assertEqual(before['deterministic_alignment_score'],0)
        self.assertTrue(all(r['match_label']=='none' for r in after['canonical_requirements']))
        self.assertEqual([r['requirement_id'] for r in before['canonical_requirements']],
                         [r['requirement_id'] for r in after['canonical_requirements']])
        self.assertEqual([r['importance'] for r in before['canonical_requirements']],
                         [r['importance'] for r in after['canonical_requirements']])
        self.assertEqual(sum(r['group_weight_fraction'] for r in after['canonical_requirements']),1)
        self.assertEqual(after['canonical_requirements'][0]['capability_id'],'backend.api_development')

    def test_debug_export_is_allowlisted_redacted_and_not_evidence_credit(self):
        diagnostic=g.diagnostic_view({**self.row,'text':'Contact person@example.com password=secret +65 8123 4567',
                                      'evidence':[{'text':'PRIVATE RESUME'}],
                                      'decomposition':{'raw_resume_text':'PRIVATE HIDDEN RESUME'}})
        with zipfile.ZipFile(io.BytesIO(g.debug_bundle(diagnostic))) as bundle:
            content=bundle.read('requirement_review.json').decode('utf-8')
        for secret in ('person@example.com','password=secret','8123 4567','PRIVATE RESUME','PRIVATE HIDDEN RESUME'):
            self.assertNotIn(secret,content)


if __name__=='__main__':unittest.main()

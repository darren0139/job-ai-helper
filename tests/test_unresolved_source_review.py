"""Offline source-grounding and review independence; test inputs are not gold."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from taxonomy_discovery import unresolved_source_review as source
from taxonomy_discovery import unresolved_gold_review as review


def example():
    case={'job_id':31,'requirement_id':'req_test','requirement_text':'MongoDB persistence'}
    raw='Requirements\nMongoDB persistence.\nOther independent obligation.'
    parent={'parent_occurrence_id':'test_parent','parent_text':'MongoDB persistence',
            'raw_parent_text':'MongoDB persistence.', 'source':'raw_jd.requirements',
            'grounding':{'span_id':'test_span','section_heading':'Requirements'}}
    snap={'id':1,'discovered_job_id':31,'job_content_hash':'test_hash','raw_jd_text':raw,
          'raw_jd_provenance':'stored_job_matching_snapshot_hash',
          'stable_analysis':{'canonical_requirements':[{'requirement_id':'req_test',
            'text':'MongoDB persistence','source_provenance':[parent],'evidence':[{'text':'PRIVATE APPLICANT'}]}]}}
    return case,snap


class SourceGroundingTests(unittest.TestCase):
    def test_exact_ids_text_and_grounded_parent_verify(self):
        case,snap=example();r=source.recover(case,snap)
        self.assertEqual(r['status'],'RECOVERED_AND_VERIFIED')
        self.assertEqual(r['raw_jd_sha256'],hashlib.sha256(snap['raw_jd_text'].encode()).hexdigest())
        self.assertNotIn('PRIVATE APPLICANT',json.dumps(r))
        self.assertTrue(all(x['anchor_raw_parent_line']==2 for x in r['nearby_lines']))

    def test_wrong_job_and_changed_content_fail_closed(self):
        case,snap=example();snap['discovered_job_id']=99
        self.assertEqual(source.recover(case,snap)['status'],'UNAVAILABLE')
        case,snap=example();snap['raw_jd_provenance']='unavailable'
        self.assertEqual(source.recover(case,snap)['status'],'UNAVAILABLE')

    def test_matching_text_does_not_reconstruct_missing_child_id(self):
        case,snap=example();case['requirement_id']='different_child'
        r=source.recover(case,snap)
        self.assertEqual(r['status'],'PARTIALLY_RECOVERED')
        self.assertIsNone(r['native_requirement'])
        self.assertEqual(r['parent_provenance'],[])
        self.assertEqual(r['exact_text_locations'][0]['line'],2)

    def test_matching_id_wrong_text_is_not_verified(self):
        case,snap=example();snap['stable_analysis']['canonical_requirements'][0]['text']='different text'
        self.assertEqual(source.recover(case,snap)['status'],'PARTIALLY_RECOVERED')

    def test_missing_or_unrelated_parent_not_inferred_from_nearby_rows(self):
        for raw_parent in ('Not present in original JD',''):
            case,snap=example();snap['stable_analysis']['canonical_requirements'][0]['source_provenance'][0]['raw_parent_text']=raw_parent
            r=source.recover(case,snap)
            self.assertEqual(r['status'],'PARTIALLY_RECOVERED')
            self.assertEqual(r['nearby_lines'],[])

    def test_conflicting_or_duplicate_canonical_ids_fail_closed(self):
        case,snap=example();snap['stable_analysis']['canonical_requirements']*=2
        self.assertEqual(source.recover(case,snap)['status'],'PARTIALLY_RECOVERED')

    def test_unverified_profile_parent_is_exposed_not_silently_trusted(self):
        case,snap=example();parents=snap['stable_analysis']['canonical_requirements'][0]['source_provenance']
        p=deepcopy(parents[0]);p.update(source='jd_profile.tools',raw_parent_text='paraphrased derived input')
        parents.append(p);r=source.recover(case,snap)
        self.assertEqual(r['status'],'PARTIALLY_RECOVERED')
        self.assertEqual([p['raw_parent_verified_in_jd'] for p in r['parent_provenance']],[True,False])


class DecisionArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # CI must not depend on a local database or an uncommitted review export.
        cls.report=source.build_report(snapshots=[])

    def test_all40_keys_text_fingerprints_and_original_gold_preserved(self):
        parent=review.original();rows=self.report['cases']
        self.assertEqual(len(rows),40)
        self.assertEqual([r['key'] for r in rows],[e['key'] for e in parent['expectations']])
        self.assertEqual([r['input_fingerprint'] for r in rows],[e['input_fingerprint'] for e in parent['expectations']])
        self.assertEqual([r['inherited_gold'] for r in rows],[e['acceptable_routes'] for e in parent['expectations']])
        self.assertTrue(all(r['human_decision']==r['reviewer']==r['reviewed_at']=='' for r in rows))

    def test_preliminary23_are_discussion_only_and_other17_investigated(self):
        rows=self.report['cases']
        self.assertEqual(sum(r['preliminary_route'] is not None for r in rows),23)
        self.assertEqual(self.report['summary']['additional_17_investigated'],17)
        self.assertEqual(self.report['summary']['independent_gold_labels'],2)
        self.assertEqual(self.report['summary']['new_human_labels'],0)
        self.assertEqual(self.report['summary']['quality_gate'],'BENCHMARK INCONCLUSIVE')

    def test_protected_controls_and_unsafe_mappings_no_global_relationship(self):
        rows=self.report['cases'];by_number={r['number']:r for r in rows}
        self.assertEqual(by_number[1]['recommendation'],'RELATIONSHIP')
        for i in (2,3): self.assertEqual(by_number[i]['inherited_gold'],['TRUE_GAP_CANDIDATE'])
        self.assertEqual(by_number[24]['recommendation'],'TECH_ID')
        for i in (17,18):self.assertEqual(by_number[i]['source_context']['status'],'UNAVAILABLE')
        for i in (14,28,39):self.assertEqual(source.DISCUSSION[i][1],source.CONTRADICTED)
        self.assertTrue(all(r['input_action'].startswith('Separate versioned') for r in rows))

    def test_predicates_exclusions_and_source_refs_visible(self):
        for row in self.report['cases']:
            self.assertTrue(row['predicate_records'])
            self.assertEqual(row['source_context']['source_references'],[])
            for p in row['predicate_records']:
                self.assertIn('requirement',p);self.assertIn('does_not_prove',p)
        text=source.markdown(self.report)
        self.assertIn('AI-assisted source audit, not independent gold',text)
        self.assertIn('not scoring eligibility',text)
        self.assertIn('ROS 2 coherent parent',text)
        case,snap=example()
        self.assertTrue(source.recover(case,snap)['source_references'])

    def test_builder_without_local_db_fails_closed_and_never_executes_model(self):
        before=review.ORIGINAL.read_bytes()
        with patch.object(source.a,'run_cases',side_effect=AssertionError('No inference')):
            r=source.build_report(snapshots=[])
        self.assertEqual(r['summary']['source_context'],{'RECOVERED_AND_VERIFIED':0,'PARTIALLY_RECOVERED':0,'UNAVAILABLE':40})
        self.assertEqual(r['summary']['verdict'],'GOLD_REVIEW_SOURCE_BLOCKED')
        self.assertEqual(review.ORIGINAL.read_bytes(),before)
        self.assertTrue(all(row['recommendation_state']==source.MORE for row in r['cases']))

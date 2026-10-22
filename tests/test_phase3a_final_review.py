"""Offline corpus recognition and pending-review companion invariants."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import preview_bulk_unresolved_v1 as review


def synthetic_sources():
    # Authored test data, deliberately not purported historical records/gold.
    text='Knowledge of REST APIs';digest=hashlib.sha256(text.encode()).hexdigest()
    cases=[];recovered=[];sources={}
    for i in range(38):
        key=[1000+i,'synthetic_'+str(i)];fp=review.fingerprint(key)
        cases.append({'key':key,'input_fingerprint':fp,'review_case_number':i+1,
            'frozen_input':{'requirement_text':text,'importance':'core','resolver':{'capability_id':None},
                'taxonomy_candidates':[{'capability_id':'backend.api_development'}]},
            'source_provenance':{'original_jd_sha256':digest}})
        recovered.append({'key':key,'input_fingerprint':fp,'exact_requirement':text,'number':i+1,
            'source_context':{'parent_provenance':[{'raw_parent_text':text,'parent_text':text,
                'raw_parent_verified_in_jd':True,'parent_occurrence_id':'p'+str(i),'grounding':{}}]}})
        sources[str(key[0])]={'raw_jd_text':text,'raw_jd_sha256':digest}
    packet={'source_fingerprint':'SYNTHETIC_ONLY','cases':cases}
    packet['packet_fingerprint']=review.fingerprint(packet)
    return packet,{'source_fingerprint':'SYNTHETIC_ONLY','cases':recovered,'sources':sources}


class FinalReviewTests(unittest.TestCase):
    def test_compound_strata_are_not_new_scoring_or_gold(self):
        controls=[('Python and SQL','EXPLICIT_AND_CUE'),('Python or SQL','EXPLICIT_OR_CUE'),
            ('Python and SQL or Java','MIXED_AND_OR_CUES'),('Knowledge of SQL / NoSQL','SLASH_OR_MIXED_SCOPE_REVIEW'),
            ('Experience with one or more of Python, SQL','EXPLICIT_ALTERNATIVE_CUE'),
            ('Experience with languages such as Python and Java','EXAMPLE_OR_COHERENT_PARENT_CUE')]
        for text,expected in controls:
            row={'job_id':1,'requirement_id':'s','original_requirement':text,'input':{'text':text},
                'input_fingerprint':review.fingerprint(text),'parent_source_available':False}
            frozen=deepcopy(row);result=review.compound_observation(row)
            self.assertEqual(result['review_stratum'],expected)
            self.assertFalse(result['interpretation_approved'])
            self.assertFalse(result['scoring_children_created'])
            self.assertEqual(row,frozen)

    def test_38_pending_are_preserved_and_context_is_explicitly_nonblind(self):
        packet,source=synthetic_sources();frozen=deepcopy((packet,source))
        result=review.review_companion(packet,source)
        self.assertEqual(len(result['cases']),38)
        self.assertFalse(result['eligible_for_gold_import'])
        self.assertFalse(result['is_independent_blind_review'])
        for row in result['cases']:
            self.assertEqual(row['review_state'],'PENDING')
            self.assertEqual(row['reviewer_judgment']['decision'],'')
            self.assertFalse(row['evidence_credit_decided'])
            self.assertTrue(row['question_requiring_human_judgment'])
            self.assertEqual(row['current_contracts_NOT_HISTORICAL'][0]['capability_id'],'backend.api_development')
        self.assertEqual((packet,source),frozen)
        self.assertEqual(result,review.review_companion(packet,source))
        self.assertIn('All 38 judgments remain PENDING',review.companion_markdown(result))

    def test_tampering_missing_identity_and_false_parent_grounding_fail(self):
        packet,source=synthetic_sources()
        for kind in ('packet','wording','jd','parent','missing'):
            p,s=deepcopy((packet,source))
            if kind=='packet':p['cases'][0]['input_fingerprint']='changed'
            if kind=='wording':s['cases'][0]['exact_requirement']='Different wording'
            if kind=='jd':s['sources']['1000']['raw_jd_text']='Modified source'
            if kind=='parent':s['cases'][0]['source_context']['parent_provenance'][0]['raw_parent_text']='Invented parent'
            if kind=='missing':p['cases'].pop();p['packet_fingerprint']=review.fingerprint({k:v for k,v in p.items() if k!='packet_fingerprint'})
            with self.subTest(kind=kind),self.assertRaises(ValueError):review.review_companion(p,s)

    def test_missing_ignored_originals_fail_closed_and_are_not_test_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary,patch.object(review,'ROOT',Path(temporary)):
            with self.assertRaisesRegex(ValueError,'Missing or unauthenticated'):
                review.verified_review_sources()

    def test_full_identical_input_corpus_recognition_and_scope_audit(self):
        result=review.final_corpus_review()
        self.assertEqual(result['saved_before'],{'rows':727,'knowledge':{'CAPABILITY_RESOLVED':191,'UNRESOLVED':536},
            'distinct_unresolved_ids':532,'distinct_unresolved_wordings':534})
        self.assertEqual(result['saved_after'],result['saved_before'])
        self.assertEqual(result['raw_before']['rows'],716)
        self.assertEqual(result['raw_before']['knowledge']['UNRESOLVED'],519)
        self.assertTrue(result['saved_input_geometry_unchanged'])
        self.assertEqual(sum(result['compound_counts'].values()),140)
        self.assertEqual({j['job_id'] for j in result['changed_raw_jobs']},{556,595})
        self.assertTrue(all(j['same_raw_source'] for j in result['changed_raw_jobs']))
        self.assertTrue(all(not j['historical_candidate_scores_compared'] for j in result['changed_raw_jobs']))
        self.assertFalse(result['human_gold_created']);self.assertFalse(result['historical_candidate_replay'])
        for case in result['predicate_candidates_pending_approval']:
            self.assertEqual(case['approval'],'REQUIRED_NOT_APPROVED')
        scratch=os.environ.get('JOB_MATCH_TEST_SCRATCH')
        if scratch:
            (Path(scratch)/'phase3a_final_corpus.json').write_text(json.dumps(review.safe(result),sort_keys=True,indent=2)+'\n',encoding='utf-8')
        print('PHASE3A_FINAL_CORPUS',json.dumps({k:result[k] for k in (
            'saved_before','saved_after','raw_before','raw_after','compound_counts')},sort_keys=True))


if __name__=='__main__':unittest.main()

"""Actual document ranking/Phase 8 parity and legacy controls."""
import copy
import hashlib
import io
import unittest
from unittest.mock import patch
from types import ModuleType
import sys
from docx import Document
from tailoring import phase9f_document_scoring_v312b216b as adapter

TEXT = ('Synthetic Software Engineer\nProjects\nDeveloped Python REST API endpoints and a React interface.\n'
        'Implemented database queries and documented the software architecture.\n'
        'Maintained internal technical documentation and resolved reported defects.\n')


def docx_bytes(text=TEXT):
    d = Document()
    for line in text.splitlines():
        d.add_paragraph(line)
    stream = io.BytesIO()
    d.save(stream)
    return stream.getvalue()


def synthetic_source(content):
    sha = hashlib.sha256(content).hexdigest()
    return {'source_type':'base_resume','source_id':'base','normalized_source_fingerprint':'source-fp',
            'resume_profile_snapshot':{'projects':[{'title':'Example','bullets':['Unrepresented Java claim']}], 'skills':{}},
            'provenance':{'artifact_type':'docx','artifact_sha256':sha}}, {'master_version_id':'base','authoritative':True,
                'artifact_bytes':content,'byte_size':len(content),'sha256':sha}


class PureDocumentAdapterTests(unittest.TestCase):
    def setUp(self):
        self.content = docx_bytes()
        self.source,self.artifact = synthetic_source(self.content)
        self.jd = {'semantic_identity':{},'application_local_jd_user_inputs':{},'raw_text':'Requirements\nPython'}
        self.parser = ModuleType('parse')
        self.parser.read_resume_docx = lambda path, preserve_complete_text: '\n'.join(p.text for p in Document(path).paragraphs)

    def test_authorized_readback_uses_serialized_document(self):
        prior=copy.deepcopy((self.source,self.artifact,self.jd))
        with patch.dict(sys.modules,{'parse':self.parser}):
            result=adapter.prepare_document_input(self.source,self.artifact,self.jd)
        self.assertEqual(result['resume_text'],TEXT.rstrip('\n'))
        self.assertEqual(result['identity']['artifact_sha256'],self.artifact['sha256'])
        self.assertEqual(result['identity_fingerprint'],adapter.digest(result['identity']))
        self.assertEqual((self.source,self.artifact,self.jd),prior)

    def test_tampered_artifact_rejected_before_readback(self):
        for change in ({'artifact_bytes':self.content+b'changed'}, {'sha256':'wrong'}, {'authoritative':False}, {'master_version_id':'other'}):
            with self.subTest(change=list(change)):
                with self.assertRaisesRegex(ValueError,'authority'):
                    adapter.prepare_document_input(self.source,{**self.artifact,**change},self.jd)

    def test_legacy_non_docx_and_custom_scope_not_promoted(self):
        source,artifact=synthetic_source(b'legacy opaque artifact')
        self.assertIsNone(adapter.prepare_document_input(source,artifact,self.jd))
        self.assertIsNone(adapter.prepare_document_input(self.source,self.artifact,{**self.jd,'application_local_jd_user_inputs':{'preferred_requirement_overrides':['Kotlin']}}))
        self.assertIsNone(adapter.prepare_document_input(self.source,self.artifact,{**self.jd,'semantic_identity':{'effective_requirement_scope':{'review':True}}}))
        self.assertIsNone(adapter.prepare_document_input({**self.source,'source_type':'global_blueprint'},self.artifact,self.jd))
        self.assertIn('Legacy',adapter.score_authority_label({}))

    def test_corrupt_word_package_not_promoted(self):
        import zipfile
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('not_word.txt','test')
        source,artifact=synthetic_source(b.getvalue())
        with self.assertRaisesRegex(ValueError,'not a Word DOCX'):
            adapter.prepare_document_input(source,artifact,self.jd)

    def test_tampered_readback_is_rejected_before_scoring(self):
        with patch.dict(sys.modules,{'parse':self.parser}):
            result=adapter.prepare_document_input(self.source,self.artifact,self.jd)
        result['resume_text']+=' unrelated claim'
        with self.assertRaisesRegex(ValueError,'inconsistent'):
            adapter.score_document_input({**self.source,'_document_score_input':result},self.jd)

    def test_missing_receipt_cannot_claim_document_authority(self):
        with self.assertRaisesRegex(ValueError,'Missing'):
            adapter.validate_ranked_document_receipt({}, {'document_score_authority':adapter.VERSION})


class NativeDocumentParityTests(unittest.TestCase):
    def rank(self, raw=None, profile=None, *, text=TEXT):
        from tests.test_phase9f_starting_source_ranking import make_base,make_exact_jd
        from tailoring.phase9f_jd_intake import build_transient_exact_jd_snapshot
        from tailoring.phase9f_starting_source_ranking import prepare_ranking_context,rank_prepared_context
        base,artifact=make_base(strong=True,artifact_bytes=docx_bytes(text))
        exact=make_exact_jd() if raw is None else build_transient_exact_jd_snapshot(raw_text=raw,jd_profile=copy.deepcopy(profile),source_type='pasted',model_calls=[])
        context=prepare_ranking_context(exact_jd=exact,current_base_resume=base,current_base_artifact=artifact,global_blueprints=[])
        self.assertEqual(context['status'],'ready',context.get('integrity_issues'))
        prior=copy.deepcopy((base,artifact,exact))
        with patch('tailoring.phase9f_starting_source_ranking.build_fresh_target_analysis',side_effect=AssertionError('Fresh target must not execute for document scoring')):
            result=rank_prepared_context(context)
        self.assertEqual(result['status'],'ranked',result.get('integrity_issues'))
        self.assertEqual((base,artifact,exact),prior)
        return result,base,artifact

    def test_actual_master_rank_matches_actual_phase8_base(self):
        from tailoring.phase9f_starting_source_ranking import validate_ranked_candidate_analysis_snapshot,validate_ranked_result_contract
        from tailoring.phase9f_v364_document_reverify import build_frozen_selected_base_document_report
        from tailoring.document_grounded_analysis import document_outcomes
        result,base,artifact=self.rank()
        candidate=result['recommended_source'];self.assertEqual(candidate['document_score_authority'],adapter.VERSION)
        snapshot=validate_ranked_candidate_analysis_snapshot(candidate)['candidate_analysis_snapshot']
        validate_ranked_result_contract(result,expected_ranking_input_fingerprint=result['ranking_input_fingerprint'])
        self.assertFalse(result['semantic_identity']['scoring']['fresh_target_only'])
        self.assertEqual(snapshot['resume_profile_snapshot'],base['structured_profile'])
        self.assertEqual(snapshot['resume_text_snapshot'],base['resume_text'])
        receipt=snapshot['document_score_receipt']
        # Strong frozen profile contains this absent skill; it must not get credit.
        self.assertNotIn('PostgreSQL',str(receipt['bounded_profile']))
        report={'raw_jd_text':snapshot['raw_jd_text_snapshot'],'raw_resume_text':snapshot['resume_text_snapshot'],
            'jd_profile':snapshot['jd_profile_snapshot'],'resume_profile':snapshot['resume_profile_snapshot'],
            'stable_analysis':snapshot['stable_analysis_snapshot'],'meta':{}}
        sealed,contract=build_frozen_selected_base_document_report(baseline_report=report,jd_text=report['raw_jd_text'],source_artifact={**artifact,'artifact_type':'docx'})
        self.assertEqual(contract['selected_base_docx_sha256'],receipt['identity']['artifact_sha256'])
        self.assertEqual(contract['selected_base_resume_text_sha256'],receipt['identity']['resume_text_sha256'])
        self.assertEqual(document_outcomes(sealed['stable_analysis']),document_outcomes(snapshot['stable_analysis_snapshot']))
        self.assertEqual(sealed['meta']['document_analysis'],receipt['document_analysis'])
        for row in snapshot['stable_analysis_snapshot']['canonical_requirements']:
            for evidence in row.get('evidence') or []:
                self.assertNotIn('PostgreSQL',evidence.get('text',''))
        from tailoring.phase9f_application_confirmation import build_application_baseline_report
        baseline=build_application_baseline_report({'selected_candidate':candidate,
            'confirmation_content_fingerprint':'synthetic-confirmation',
            'confirmation_content_identity':{'phase9f_b':{'ranking_input_fingerprint':result['ranking_input_fingerprint'],
                'ranking_fingerprint':result['ranking_fingerprint']}}})
        self.assertEqual(baseline['resume_profile'],base['structured_profile'])
        self.assertEqual(baseline['overall_score'],candidate['deterministic_alignment_score'])
        self.assertEqual(baseline['meta']['phase9f_b_document_score_provenance']['receipt_fingerprint'],receipt['fingerprint'])
        self.assertNotIn('document_analysis',baseline['meta'])

    def test_tampered_ranked_receipt_rejected_even_with_outer_checksum(self):
        from tailoring.phase9f_starting_source_ranking import validate_ranked_candidate_analysis_snapshot,fingerprint_value,Phase9FBRankingError
        result,_,_=self.rank();candidate=copy.deepcopy(result['recommended_source']);snap=candidate['candidate_analysis_snapshot']
        snap['document_score_receipt']['bounded_profile']['skills']={'Languages':['Invented']}
        receipt=snap['document_score_receipt'];receipt['fingerprint']=adapter.digest({k:v for k,v in receipt.items() if k!='fingerprint'})
        candidate['candidate_analysis_snapshot_fingerprint']=fingerprint_value(snap)
        with self.assertRaises(Phase9FBRankingError):validate_ranked_candidate_analysis_snapshot(candidate)

    def test_ncs_with_and_without_footer_has_same_material_native_outcomes(self):
        from tests.test_v312b215_jd_eligibility import JD,PROFILE
        from tailoring.document_grounded_analysis import document_outcomes
        short=JD.split('Additional information',1)[0].rstrip()
        self.assertNotEqual(short,JD)
        a,_,_=self.rank(short,PROFILE);b,_,_=self.rank(JD,PROFILE)
        rows=[x['recommended_source']['candidate_analysis_snapshot']['stable_analysis_snapshot'] for x in (a,b)]
        self.assertEqual([len(r['canonical_requirements']) for r in rows],[12,12])
        self.assertEqual(document_outcomes(rows[0]),document_outcomes(rows[1]))


if __name__=='__main__':unittest.main()

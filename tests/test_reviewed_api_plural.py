"""A1 native review admission; synthetic controls are not human approvals."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock

from analysis_stability import stable_evidence_scoring as n, coordinated_runtime as runtime
from taxonomy_discovery import governed_requirement_resolution as review, resolver_improvement as draft
from tailoring import capability_taxonomy as taxonomy
from scripts import preview_bulk_unresolved_v1 as corpus


def source(text):
    raw = 'Requirements:\n'+text
    row = dict(text=text, atomic_focus=text, parent_text=text, importance='core',
        score_eligible=True, group_weight_fraction=1.0, requirement_id='synthetic',
        source_provenance=[dict(source='raw_jd.requirements', parent_text=text,
            raw_parent_text=text, parent_occurrence_id='synthetic-parent',source_group_fraction=1.0,
            grounding=dict(kind='explicit_raw_section',span_id='synthetic-span',sentence_index=1,sentence_text=text))])
    return row,raw


class ReviewedPluralTests(unittest.TestCase):
    def test_governance_rejects_unreviewed_plural_route_without_fake_receipts(self):
        from tests.tqd3_publication_fixture_support import PublicationFixture
        from tests.test_tqd3_taxonomy_evolution import candidate
        from taxonomy_discovery import governed_research as governor
        with PublicationFixture() as f:
            c=candidate('RESTful APIs')  # authored synthetic gap, not a real review
            # A lexical review packet is not a governed research authorization.
            # Preserve this boundary rather than forcing its route/approval.
            with self.assertRaisesRegex(ValueError,'not eligible for research'):
                governor.research_plan([c],selected_candidate_ids=[c['candidate_id']])
            self.assertFalse((f.tmp/'review.sqlite3').exists())

    def test_additive_overlay_preserves_all_published_rules_and_is_idempotent(self):
        before = taxonomy.get_default_taxonomy()
        old = deepcopy(before.capabilities)
        overlay = draft.additive_phrase_overlay('backend.api_development',['restful apis'],identity='test-only')
        entry = overlay.by_id()['backend.api_development']
        native = before.by_id()['backend.api_development']
        for k,v in native['requirement'].items():
            if k=='contextual_phrase_variants':
                self.assertEqual(entry['requirement'][k][:len(v)],v)
            else:self.assertEqual(entry['requirement'][k],v)
        self.assertEqual(entry['evidence_tiers'],native['evidence_tiers'])
        with taxonomy.temporary_taxonomy_scope(overlay):
            twice=draft.additive_phrase_overlay('backend.api_development',['restful apis'],identity='test-twice')
            self.assertEqual(overlay.capabilities,twice.capabilities)
        self.assertEqual(before.capabilities,old)
        with self.assertRaises(ValueError):draft.additive_phrase_overlay('backend.api_development',['api skills'],identity='invalid')

    def test_admission_counterexamples_and_null_credit(self):
        cases=[('Develop efficient, secure RESTful APIs',True),
            ('Develop and integrate RESTful APIs with front-end applications',True),
            ('Experience developing and consuming RESTful APIs',True),
            ('Develop RESTful APIs and maintain databases',True), # intact concept, NOT full credit
            ('Build reports using RESTful APIs',False),('Consume RESTful APIs',False),
            ('Knowledge of RESTful APIs',False),('Read RESTful APIs documentation',False),
            ('Do not develop RESTful APIs',False),('No experience developing RESTful APIs required',False),
            ('Develop RESTful APIs or maintain MongoDB',False),
            ('Develop and consume RESTful APIs',True),
            ('Develop RESTful APIs and gRPC services',True), # mandatory protocols retained
            ('Experience with Amazon Web Services',False)]
        for text, expected in cases:
            row,raw=source(text); frozen=deepcopy(row)
            result=review.api_plural_review(row,raw,explicit_execution=True)
            with self.subTest(text=text):
                self.assertEqual(result['recognition_changed'],expected)
                self.assertIsNone(result['evidence_credit']);self.assertIsNone(result['parent_contribution'])
                self.assertIsNone(result['whole_jd_score'])
                self.assertEqual(row,frozen);self.assertEqual(result['input']['group_weight_fraction'],1)
                with self.assertRaises(ValueError):runtime.assert_analysis_publishable(result)
        row,raw=source('Develop efficient RESTful APIs')
        with self.assertRaises(ValueError):review.api_plural_review(row,raw)

    def test_missing_conflicting_source_and_optional_inputs_fail_closed(self):
        row,raw=source('Develop secure RESTful APIs')
        for kind in ('missing','conflict','jd','sentence','duplicate','allocation','optional','negated_parent'):
            r=deepcopy(row);jd=raw
            if kind=='missing':r.pop('source_provenance')
            if kind=='conflict':r['source_provenance'][0]['parent_text']='Consume RESTful APIs'
            if kind=='jd':jd='Different JD'
            if kind=='sentence':r['source_provenance'][0]['grounding']['sentence_text']='Different sentence'
            if kind=='duplicate':r['source_provenance']*=2
            if kind=='allocation':r['source_provenance'][0]['source_group_fraction']=2
            if kind=='optional':r['importance']='preferred'
            if kind=='negated_parent':
                jd='Do not '+r['text'];r['source_provenance'][0]['raw_parent_text']=jd
            with self.subTest(kind=kind):
                self.assertFalse(review.api_plural_review(r,jd,explicit_execution=True)['recognition_changed'])

    def test_existing_identities_and_numeric_workflows_remain_unchanged(self):
        from job_discovery.matching import _default_stable_builder,build_profile_evidence_context
        from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
        from tailoring.phase8_verification import build_current_baseline_analysis
        from database import analysis_cache_manager as cache
        row,raw=source('Develop and consume RESTful APIs')
        profile={'projects':[{'title':'Synthetic','bullets':['Implemented Java REST API endpoints.']}]}
        context=build_profile_evidence_context([{'id':7,'category':'Project','title':'Synthetic','bullets':profile['projects'][0]['bullets']}])
        def run():
            return [_default_stable_builder(raw_jd_text=raw,jd_profile={},context=context),
                analyze_actual_resume_against_jd(resume_text='Unrelated document only.',jd_text=raw,jd_profile={},resume_profile=profile)['stable_analysis'],
                build_current_baseline_analysis(baseline_report={'jd_profile':{},'resume_profile':profile,'keyword_match':{}},raw_jd_text=raw)]
        before=run(); result=review.api_plural_review(row,raw,explicit_execution=True)
        self.assertEqual(before,run())
        self.assertTrue(all(r['scoring_version']==n.SCORING_VERSION for r in before))
        connection=Mock()
        with self.assertRaises(ValueError):cache.insert_analysis_snapshot_with_connection(connection,
            application_id=1,input_fingerprint='x',report={'stable_analysis':result},analysis_model='offline',
            resume_filename='x',analysis_id='x',created_at='x')
        connection.execute.assert_not_called()
        for text in ('Develop REST APIs','Experience building RESTful APIs','Implement web services',
                     'Good written and verbal communication with stakeholders',
                     'Experience in cross-functional collaboration'):
            r,jd=source(text); out=review.api_plural_review(r,jd,explicit_execution=True)
            self.assertEqual(out['disposition'],'UNCHANGED',text)
            self.assertFalse(out['recognition_changed'])

    def test_s1_schema_cannot_encode_unapproved_stakeholder_scope(self):
        entry=deepcopy(taxonomy.get_default_taxonomy().by_id()['collaboration.stakeholder'])
        entry['requirement']['scope_policy']='explicit_stakeholder_collaboration'
        with self.assertRaises(ValueError):taxonomy._validate_capability(entry,set())
        self.assertNotIn('stakeholders',taxonomy.get_default_taxonomy().by_id()['collaboration.stakeholder']['requirement']['any_terms'])

    def test_corpus_saved_raw_and_v126_are_separate(self):
        jobs,_=corpus.load_jobs(); inventory=corpus.build_inventory(jobs)
        raw={v['job']['job_id']:v['job']['frozen_inputs']['raw_jd_text'] for v in jobs}
        views={'saved':inventory['saved_rows'],'raw':inventory['raw_jd_only_rows']}
        with runtime.approved_alias_surface_preview():
            views['v126']=[]
            for view in jobs:
                jid=view['job']['job_id']
                rows=n.canonicalise_requirements({},raw_jd_text=raw[jid])['requirements']
                views['v126'].extend(dict(job_id=jid,requirement_id=r['requirement_id'],input=r) for r in rows)
        result={}
        for name,rows in views.items():
            changed=[];unchanged_aws=[]
            for r in rows:
                # A finite phrase is a necessary admission condition; don't replay
                # candidate scores or unrelated reviewed experiments.
                if 'restful apis' not in r['input']['text'].lower() and r['job_id']!=566:continue
                receipt=review.api_plural_review(r['input'],raw[r['job_id']],explicit_execution=True)
                if receipt['recognition_changed']:
                    changed.append(dict(job_id=r['job_id'],requirement_id=r['requirement_id'],receipt=receipt))
                if r['requirement_id']=='req_b34860727bff':unchanged_aws.append(receipt)
            result[name]=dict(rows=len(rows),changed=changed,aws_control=unchanged_aws)
            self.assertEqual(len(changed),0 if name=='saved' else 3)
            if name!='saved':
                self.assertEqual({c['job_id'] for c in changed},{31,479})
                self.assertEqual({c['requirement_id'] for c in changed},{'req_d0a20edbb7ae','req_5eabf1000188','req_fc4e6757e8e4'})
            self.assertTrue(all(not r['recognition_changed'] for r in unchanged_aws))
        scratch=os.environ.get('JOB_MATCH_TEST_SCRATCH')
        if scratch:(Path(scratch)/'reviewed_api_impact.json').write_text(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print('REVIEWED_API_IMPACT',json.dumps({k:{'rows':v['rows'],'changes':len(v['changed'])} for k,v in result.items()}))

"""Independent eligibility counterexamples, synthetic sources, native workflows."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from analysis_stability import stable_evidence_scoring as n
from analysis_stability import coordinated_runtime as runtime
from job_discovery import coordinated_preview as base, developer_comparison as gate
from job_discovery import evidence_relevance_preview as experiment

REQUIREMENT = 'Coordinate project milestones schedules delivery budgets resources risks approvals'
CLAIM = 'Coordinated project milestones for the annual synthetic infrastructure migration with colleagues.'


class EligibleEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {gate.GATE:'1'}))

    def enabled(self):
        token = runtime.ELIGIBLE_WEAK_FALLBACK.set(True)
        self.addCleanup(runtime.ELIGIBLE_WEAK_FALLBACK.reset, token)

    def records(self, *texts):
        return [{'text':t,'section':'projects','source':f'resume_profile.projects[0].bullets[{i}]',
                 'evidence_id':f'synthetic_{i}'} for i,t in enumerate(texts)]

    def test_independent_counterexample_uses_existing_thresholds_and_one_record(self):
        row = {'text':REQUIREMENT}
        records = self.records('project atlas', CLAIM)
        expected = [(0.391, 1/9, 1, False), (0.3, 3/9, 3, True)]
        for record, (score, coverage, overlap, eligible) in zip(records, expected):
            _,s,c,o = n._best_resume_evidence(row,'',[record],{})
            self.assertAlmostEqual(s,score); self.assertAlmostEqual(c,coverage)
            self.assertEqual(o,overlap)
            self.assertEqual(n._deterministic_weak_evidence_is_sufficient(
                score=s,focus_coverage=c,overlap_count=o),eligible)
        self.assertIsNone(n._fallback_weak_evidence(row,records,{}))
        self.enabled()
        selected = n._fallback_weak_evidence(row,records,{})
        self.assertEqual(selected['evidence_id'],'synthetic_1')
        self.assertEqual(selected['text'],CLAIM)
        self.assertIsNone(n._fallback_weak_evidence(row,self.records('project','milestones'),{}))
        # Two individually insufficient records never become one qualifying row.

    def test_explicit_preview_geometry_owner_weak_ceiling_and_determinism(self):
        request = base.prepare_comparison(raw_jd_text='Requirements:\n- '+REQUIREMENT,
            jd_profile={}, evidence_items=[{'id':71,'category':'Project','title':'Synthetic migration',
                'bullets':['project atlas',CLAIM]}])
        baseline = base.run_comparison(request,developer_enabled=True)
        frozen = deepcopy(baseline)
        self.assertEqual(baseline.gated.requirements[0].label.value,'NONE')
        result = experiment.evaluate_eligible_recovery(request,session_enabled=True,baseline=baseline)
        self.assertEqual(result['experimental_view'].requirements[0].label.value,'WEAK')
        self.assertEqual(result['experimental_view'].scoring_version,runtime.ELIGIBLE_WEAK_SCORER)
        receipt = result['changes'][0]
        self.assertEqual(receipt['library_item_id'],71)
        self.assertFalse(receipt['combined_support_records'])
        self.assertFalse(receipt['canonical_identity_inferred'])
        self.assertEqual(result,experiment.evaluate_eligible_recovery(request,session_enabled=True,baseline=baseline))
        self.assertEqual(baseline,frozen)
        self.assertFalse(runtime.ELIGIBLE_WEAK_FALLBACK.get())
        with self.assertRaises(ValueError): experiment.evaluate_eligible_recovery(request,baseline=baseline)
        self.assertEqual(base.run_comparison(request,developer_enabled=True),baseline)
        with patch.object(base.gated,'build_coordinated_analysis',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                experiment.evaluate_eligible_recovery(request,session_enabled=True,baseline=baseline)
        self.assertFalse(runtime.ELIGIBLE_WEAK_FALLBACK.get())

    def test_native_source_guards_none_ceiling_and_known_capabilities_unchanged(self):
        scenarios = [
            ('Develop REST APIs',['API','Integrated PostgREST database access.']),
            ('Data Structures and Algorithms',['data','Implemented database data access using PostgREST.']),
            ('Design databases',['database','Used SQLite to store generated reports.']),
            ('Use Angular and Node.js',['React','Built a React UI.']),
            ('Agile development concepts',['GitHub','Implemented GitHub Actions CI.']),
        ]
        for text, bullets in scenarios:
            with self.subTest(text=text):
                request = base.prepare_comparison(raw_jd_text='Requirements:\n- '+text,jd_profile={},
                    evidence_items=[{'id':71,'category':'Project','title':'Synthetic control','bullets':bullets}])
                baseline = base.run_comparison(request,developer_enabled=True)
                result = experiment.evaluate_eligible_recovery(request,session_enabled=True,baseline=baseline)
                self.assertEqual(result['changes'],[])
                self.assertEqual([r.label for r in result['experimental_view'].requirements],
                                 [r.label for r in baseline.gated.requirements])
        self.enabled()
        row = {'text':REQUIREMENT}
        with patch.object(n,'_evidence_source_is_requirement_compatible',return_value=False):
            self.assertIsNone(n._fallback_weak_evidence(row,self.records(CLAIM),{}))

    def test_coordinated_parent_native_none_ceiling_is_not_reinterpreted(self):
        from analysis_stability.coordinated_integration import targeted
        from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge as resolve
        row = {'text':'Design develop and maintain quantum calibration modules libraries scheduling receipts'}
        self.assertTrue(targeted(row))
        self.assertIsNone(resolve(row)['decision']['capability_id'])
        records = self.records('modules atlas',
            'Implemented quantum calibration modules with an independently authored synthetic control system.')
        self.assertIsNone(n._fallback_weak_evidence(row,records,{}))
        self.enabled()
        self.assertIsNone(n._fallback_weak_evidence(row,records,{}))

    def test_inherited_quality_and_review_withholding(self):
        from scripts.coordinated_job_match_preview_inputs import preview_inputs
        inputs = preview_inputs('E04')
        inputs['raw_jd_text'] += '\n- '+REQUIREMENT+'\n- Attention to detail and quality is a desired attribute'
        inputs['evidence_items'].append({'id':901,'category':'Project','title':'Synthetic import tool',
            'bullets':['project atlas',CLAIM,'Implemented import checks ensuring data integrity.']})
        request = base.prepare_comparison(**inputs)
        baseline = base.run_comparison(request,developer_enabled=True)
        result = experiment.evaluate_eligible_recovery(request,session_enabled=True,baseline=baseline)
        self.assertTrue(result['inherited_changes'])
        self.assertGreater(result['experimental_view'].review_count,0)
        self.assertIsNone(result['experimental_view'].alignment)
        for row in result['experimental_view'].requirements:
            if row.label.value=='REVIEW_REQUIRED': self.assertIsNone(row.contribution)

    def test_bare_version_persistence_rejected_and_direct_native_calls_stamped(self):
        from database import analysis_cache_manager as cache
        connection = Mock()
        bare = {'scoring_version':runtime.ELIGIBLE_WEAK_SCORER,'canonical_requirements':[]}
        with self.assertRaises(ValueError): runtime.assert_analysis_publishable(bare)
        with self.assertRaises(ValueError): cache.insert_analysis_snapshot_with_connection(connection,
            application_id=1,input_fingerprint='x',report={'stable_analysis':bare},analysis_model='offline',
            resume_filename='x',analysis_id='x',created_at='x')
        connection.execute.assert_not_called()
        self.enabled()
        output = n.build_stable_analysis(jd_profile={},keyword_match={},raw_jd_text='Requirements:\n- '+REQUIREMENT,
            resume_profile={'projects':[{'bullets':['project atlas',CLAIM]}]},retrieval_mode_override='off')
        self.assertEqual(output['scoring_version'],runtime.ELIGIBLE_WEAK_SCORER)
        with self.assertRaises(ValueError): runtime.assert_analysis_publishable(output)

    def test_actual_shared_workflow_builders_keep_evidence_authorities_separate(self):
        from job_discovery.matching import _default_stable_builder, build_profile_evidence_context
        from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
        from tailoring.phase8_verification import build_current_baseline_analysis
        jd = 'Requirements:\n- '+REQUIREMENT
        profile = {'projects':[{'title':'Synthetic migration','bullets':['project atlas',CLAIM]}], 'skills':{}}
        document = 'Synthetic migration\nproject atlas\n'+CLAIM
        context = build_profile_evidence_context([{'id':71,'category':'Project',
            'title':'Synthetic migration','bullets':['project atlas',CLAIM]}])
        native_inputs = {'jd_profile':{},'resume_profile':profile,'keyword_match':{'present':[],'missing':[]}}
        before = build_current_baseline_analysis(baseline_report=native_inputs,raw_jd_text=jd)
        self.enabled()
        finder = _default_stable_builder(raw_jd_text=jd,jd_profile={},context=context)
        initial = analyze_actual_resume_against_jd(resume_text=document,jd_text=jd,
            jd_profile={},resume_profile=profile)
        phase8 = build_current_baseline_analysis(baseline_report=native_inputs,raw_jd_text=jd)
        self.assertEqual(before['canonical_requirements'][0]['match_label'],'none')
        for result in (finder,initial['stable_analysis'],phase8):
            self.assertEqual(result['scoring_version'],runtime.ELIGIBLE_WEAK_SCORER)
            self.assertEqual(result['canonical_requirements'][0]['match_label'],'weak')
            self.assertEqual(result['canonical_requirements'][0]['evidence'][0]['text'],CLAIM)
            with self.assertRaises(ValueError): runtime.assert_analysis_publishable(result)
        # The document path may only use literal document claims; library data
        # is never supplied as a fallback to this execution path.
        absent = analyze_actual_resume_against_jd(resume_text='A separate unrelated document.',
            jd_text=jd,jd_profile={},resume_profile=profile)
        self.assertEqual(absent['stable_analysis']['canonical_requirements'][0]['match_label'],'none')

    def test_six_unsupported_regression_scopes_do_not_gain_credit(self):
        controls = [
            'Work closely with project manager technical lead and architect',
            'Analyze and troubleshoot software issues',
            'Generate relevant documentations reports etc',
            'Keeping up-to-date with industry trends and technology developments',
            'Learn new software quickly',
            'Critical analytical and creative problem solving skills',
        ]
        for text in controls:
            request = base.prepare_comparison(raw_jd_text='Requirements:\n- '+text,jd_profile={},
                evidence_items=[{'id':71,'category':'Project','title':'Synthetic app',
                    'bullets':['Built a chatbot with SQLite storage and React pages.']}])
            result = experiment.evaluate_eligible_recovery(request,session_enabled=True)
            self.assertEqual(result['changes'],[],text)
            self.assertTrue(all(r.label.value=='NONE' for r in result['experimental_view'].requirements),text)

    def test_full_corpus_native_synthetic_probe_separates_recognition_and_credit(self):
        from scripts.preview_bulk_unresolved_v1 import load_jobs
        from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge as resolve
        jobs, sources = load_jobs()
        profile = {'projects':[{'title':'Synthetic engineering project','bullets':[
            'software', 'Implemented software applications and automated tests for a synthetic inventory system.']}], 'skills':{}}
        summary = {'jobs':len(jobs),'source_sha256':sources[0]['sha256'],
            'synthetic_only':True,'historical_candidate_replay':False,'rows':0,'changed_rows':[],
            'recognition_changes':0,'before_labels':{},'after_labels':{}}
        for job in jobs:
            raw = job['job']['frozen_inputs']['raw_jd_text']
            kwargs = dict(jd_profile={},keyword_match={},raw_jd_text=raw,resume_profile=profile,retrieval_mode_override='off')
            before = n.build_stable_analysis(**kwargs)
            token = runtime.ELIGIBLE_WEAK_FALLBACK.set(True)
            try: after = n.build_stable_analysis(**kwargs)
            finally: runtime.ELIGIBLE_WEAK_FALLBACK.reset(token)
            a,b = before['canonical_requirements'],after['canonical_requirements']
            self.assertEqual([(r['requirement_id'],r['source_provenance']) for r in a],
                             [(r['requirement_id'],r['source_provenance']) for r in b])
            for old,new in zip(a,b):
                summary['rows'] += 1
                self.assertEqual(resolve(old)['knowledge_status'],resolve(new)['knowledge_status'])
                for key,row in [('before_labels',old),('after_labels',new)]:
                    label=row['match_label'];summary[key][label]=summary[key].get(label,0)+1
                if old['match_label']!=new['match_label']:
                    self.assertEqual(old['match_label'],'none')
                    self.assertEqual(new['match_label'],'weak')
                    self.assertEqual(len(new['evidence']),1)
                    self.assertIsNone(new.get('capability_id'))
                    summary['changed_rows'].append({'job_id':job['job']['job_id'],
                        'requirement_id':old['requirement_id'],'before':old['match_label'],'after':new['match_label']})
        self.assertEqual(summary['jobs'],30)
        self.assertEqual(summary['rows'],716)
        # Diagnostic counts are observations, never an independent credit oracle.
        scratch = os.environ.get('JOB_MATCH_TEST_SCRATCH')
        if scratch:
            (Path(scratch)/'phase3a_corpus_synthetic_summary.json').write_text(
                json.dumps(summary,sort_keys=True,indent=2)+'\n',encoding='utf-8')
        print('PHASE3A_SYNTHETIC_CORPUS',json.dumps(summary,sort_keys=True))


if __name__=='__main__': unittest.main()

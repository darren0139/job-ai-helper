"""B1.4.1 conservative cross-project prefilter and native-selection tests."""
from __future__ import annotations
import unittest
from copy import deepcopy
from unittest.mock import patch
from tailoring.portfolio_quality_v312b141 import (
    VERSION, _redundancy, plan_quality_swaps, compare_and_select,
)
from tailoring.portfolio_quality_v312b14 import B1_TAG


def project(name, text_ids):
    bullets=[t for t, _ in text_ids]
    return {'project_id':name, 'display_title':name,
            'draft_bullets':bullets,
            'bullet_evidence_priorities':[
                {'bullet_index':i,'bullet_text':t,'supported_requirement_ids':list(ids),
                 'protect_during_fitting':i==0, 'protected_requirement_ids':[],
                 'unique_required_core_count':0,'evidence_value':5+i}
                for i,(t,ids) in enumerate(text_ids)]}


def scenario(*,globally_new=True,overlap=False):
    a=project('Fullstack App',[
        ('Built a React and Python web service for customer workflows.', ['core']),
        ('Implemented automated testing and CI pipelines using Github Actions and Docker.', ['ci']),
        ('Designed role access and protected routes in the web application.', ['core']),
        ('Integrated PostgreSQL storage with FastAPI backend endpoints.', ['core']),
        ('Monitored service metrics through Prometheus telemetry dashboards.', ['ci']),
    ])
    b=project('Cloud App',[
        ('Configured an AWS VPC and database connectivity for a team web application.', ['cloud']),
        ('Configured AWS VPC networking and database connectivity for a cloud web application.'
         if overlap else 'Implemented security group restrictions and blocked public database access on Amazon RDS.',
         ['core'] if not globally_new else ['security']),
    ])
    c=project('Game App',[
        ('Built C++ custom game engine and authored Lua scripts.', []),
        ('Added dynamic enemy navigation using A star.', []),
    ])
    source={'portfolio_quality_b1_active':B1_TAG,'recommended_projects':[a,b,c]}
    fitted=deepcopy(source)
    fitted['recommended_projects'][1]['draft_bullets']=b['draft_bullets'][:1]
    fitted['recommended_projects'][1]['bullet_evidence_priorities']=b['bullet_evidence_priorities'][:1]
    fitted['recommended_projects'][2]['draft_bullets']=c['draft_bullets'][:1]
    fitted['recommended_projects'][2]['bullet_evidence_priorities']=c['bullet_evidence_priorities'][:1]
    return source, {'tailored_projects_used':fitted,'fit_one_page':True,'page_count':1}


def verified(score=32,core=3,claims=0):
    return {'comparison_valid':True,'job_match_ab':{'comparable':True},
        'after_stable_analysis':{'scoring_version':'stable-evidence-test',
          'deterministic_alignment_score':score,
          'canonical_requirements':[
            {'requirement_id':'core','importance':'core','match_label':'direct',
             'evidence_strength':core},
            {'requirement_id':'security','importance':'preferred','match_label':'weak',
             'evidence_strength':2}]},
         'claim_lineage':{'claim_review_required_count':claims}}


class B141Tests(unittest.TestCase):
    def test_keith_style_equal_jd_id_but_depth_increase_blocked_before_native_or_render(self):
        source,fit=scenario(globally_new=False)
        hit={'render':0,'verify':0}
        def render(*_):hit['render']+=1;raise AssertionError('no render')
        def verify(*_):hit['verify']+=1;raise AssertionError('no verify')
        with patch('tailoring.portfolio_quality_v312b141._docx_authority',return_value=True):
            chosen,receipt=compare_and_select(source_projects=source,incumbent_fit=fit,
                                              render=render,verify=verify)
        self.assertIs(chosen,fit)
        self.assertEqual(receipt['status'],'NO_ELIGIBLE_SOURCE_GROUNDED_SWAP')
        self.assertEqual(hit,{'render':0,'verify':0})
        self.assertGreater(receipt['prefilter']['rejected_no_global_jd_novelty'],0)
        self.assertEqual(receipt['render_probes_attempted'],0)

    def test_actual_globally_novel_bullet_proposed(self):
        source,fit=scenario()
        probes,counts,status=plan_quality_swaps(source_projects=source,incumbent_fit=fit)
        self.assertEqual(status,'PASS')
        self.assertEqual(len(probes),1)
        self.assertEqual(probes[0]['added_global_requirement_ids'],['security'])
        self.assertEqual(probes[0]['recipient'],'Cloud App')
        self.assertLess(probes[0]['addition_overlap_fraction'],0.55)

    def test_native_safe_novel_swap_selected_at_most_one_render(self):
        source,fit=scenario()
        calls={'render':0,'verify':0}
        def render(candidate):
            calls['render']+=1
            return {'tailored_projects_used':candidate,'fit_one_page':True,'page_count':1}
        def verify(_):calls['verify']+=1;return verified()
        with patch('tailoring.portfolio_quality_v312b141._docx_authority',return_value=True):
            selected,receipt=compare_and_select(source_projects=source,incumbent_fit=fit,
                                                 render=render,verify=verify)
        self.assertIsNot(selected,fit)
        self.assertEqual(receipt['status'],'SELECTED_NATIVE_SAFE_DEPTH_IMPROVEMENT')
        self.assertEqual(calls,{'render':1,'verify':2})
        self.assertIn('comparison_elapsed_seconds',receipt)
        self.assertIn('render_elapsed_seconds',receipt['probes'][0])
        self.assertEqual(receipt['render_probes_attempted'],1)

    def test_native_score_regression_preserves_incumbent(self):
        source,fit=scenario()
        calls=iter([verified(score=32),verified(score=31)])
        with patch('tailoring.portfolio_quality_v312b141._docx_authority',return_value=True):
            selected,receipt=compare_and_select(source_projects=source,incumbent_fit=fit,
                    render=lambda p:{'tailored_projects_used':p}, verify=lambda _:next(calls))
        self.assertIs(selected,fit)
        self.assertEqual(receipt['probes'][0]['reason'],'NATIVE_SCORE_REGRESSION')

    def test_core_regression_preserves_incumbent(self):
        source,fit=scenario()
        calls=iter([verified(core=3),verified(core=2)])
        with patch('tailoring.portfolio_quality_v312b141._docx_authority',return_value=True):
            selected,receipt=compare_and_select(source_projects=source,incumbent_fit=fit,
                    render=lambda p:{'tailored_projects_used':p}, verify=lambda _:next(calls))
        self.assertIs(selected,fit)
        self.assertEqual(receipt['probes'][0]['reason'],'REQUIRED_CORE_REGRESSION')

    def test_increased_claim_risk_preserves_incumbent(self):
        source,fit=scenario()
        calls=iter([verified(claims=0),verified(claims=1)])
        with patch('tailoring.portfolio_quality_v312b141._docx_authority',return_value=True):
            selected,receipt=compare_and_select(source_projects=source,incumbent_fit=fit,
                    render=lambda p:{'tailored_projects_used':p}, verify=lambda _:next(calls))
        self.assertIs(selected,fit)
        self.assertEqual(receipt['probes'][0]['reason'],'CLAIM_REVIEW_RISK_INCREASED')

    def test_overlap_gate_even_when_metadata_novel(self):
        source,fit=scenario(overlap=True)
        probes,counts,_=plan_quality_swaps(source_projects=source,incumbent_fit=fit)
        self.assertEqual(probes,[])
        self.assertGreater(counts['rejected_bullet_overlap'],0)

    def test_unique_removed_evidence_protected(self):
        source,fit=scenario()
        donor=source['recommended_projects'][0]
        donor['bullet_evidence_priorities'][4]['supported_requirement_ids']=['uniq']
        fit['tailored_projects_used']['recommended_projects'][0]['bullet_evidence_priorities'][4]['supported_requirement_ids']=['uniq']
        probes,counts,_=plan_quality_swaps(source_projects=source,incumbent_fit=fit)
        self.assertGreater(counts['rejected_removed_unique_jd_evidence'],0)
        if probes:
            self.assertNotEqual(probes[0]['removed_bullet'],donor['draft_bullets'][4])

    def test_incorrect_source_metadata_fails_closed(self):
        source,fit=scenario()
        source['recommended_projects'][1]['bullet_evidence_priorities'][1]['bullet_text']='tampered'
        probes,counts,reason=plan_quality_swaps(source_projects=source,incumbent_fit=fit)
        self.assertEqual(probes,[])
        self.assertEqual(reason,'SOURCE_METADATA_UNVERIFIED')

    def test_darren_deep_no_one_bullet_no_render_or_native(self):
        source,fit=scenario()
        for i in (1,2):
            fit['tailored_projects_used']['recommended_projects'][i]=deepcopy(source['recommended_projects'][i])
        with patch('tailoring.portfolio_quality_v312b141._docx_authority',return_value=True):
            selected,receipt=compare_and_select(source_projects=source,incumbent_fit=fit,
                  render=lambda _:self.fail('render'),verify=lambda _:self.fail('native'))
        self.assertIs(selected,fit)
        self.assertEqual(receipt['render_probes_attempted'],0)

    def test_no_valid_incumbent_docx_holds(self):
        source,fit=scenario()
        with patch('tailoring.portfolio_quality_v312b141._docx_authority',return_value=False):
            selected,receipt=compare_and_select(source_projects=source,incumbent_fit=fit,
                 render=lambda _:self.fail('render'),verify=lambda _:self.fail('native'))
        self.assertIs(selected,fit)
        self.assertEqual(receipt['reason'],'INCUMBENT_DOCX_NOT_AUTHENTICATED')

    def test_no_candidate_docx_holds(self):
        source,fit=scenario()
        def authority(candidate):return candidate is fit
        with patch('tailoring.portfolio_quality_v312b141._docx_authority',side_effect=authority):
            selected,receipt=compare_and_select(source_projects=source,incumbent_fit=fit,
                render=lambda p:{'tailored_projects_used':p},verify=lambda _:verified())
        self.assertIs(selected,fit)
        self.assertEqual(receipt['probes'][0]['reason'],'ONE_PAGE_OR_DOCX_READBACK_FAILED')

    def test_soft_budget_prevents_launch_not_hard_timeout(self):
        source,fit=scenario()
        with patch('tailoring.portfolio_quality_v312b141.SOFT_COMPARISON_BUDGET_SECONDS',0.0),\
             patch('tailoring.portfolio_quality_v312b141._docx_authority',return_value=True):
            selected,receipt=compare_and_select(source_projects=source,incumbent_fit=fit,
                    render=lambda _:self.fail('render'),verify=lambda _:self.fail('native'))
        self.assertIs(selected,fit)
        self.assertEqual(receipt['reason'],'COMPARISON_BUDGET_EXHAUSTED_PRE_VERIFY')

    def test_balanced_vs_portfolio_holds(self):
        source,fit=scenario()
        source.pop('portfolio_quality_b1_active')
        candidates,_,reason=plan_quality_swaps(source_projects=source,incumbent_fit=fit)
        self.assertEqual(candidates,[])
        self.assertEqual(reason,'SOURCE_METADATA_UNVERIFIED')

    def test_no_mutation(self):
        source,fit=scenario()
        old_source=deepcopy(source)
        old_fit=deepcopy(fit)
        plan_quality_swaps(source_projects=source,incumbent_fit=fit)
        self.assertEqual(source,old_source)
        self.assertEqual(fit,old_fit)

    def test_novelty_is_global_not_recipient_local(self):
        source,fit=scenario(globally_new=True)
        source['recommended_projects'][0]['bullet_evidence_priorities'][0]['supported_requirement_ids'].append('security')
        fit['tailored_projects_used']['recommended_projects'][0]['bullet_evidence_priorities'][0]['supported_requirement_ids'].append('security')
        candidates,counts,_=plan_quality_swaps(source_projects=source,incumbent_fit=fit)
        self.assertEqual(candidates,[])
        self.assertGreater(counts['rejected_no_global_jd_novelty'],0)

    def test_version_receipt(self):
        source,fit=scenario(globally_new=False)
        with patch('tailoring.portfolio_quality_v312b141._docx_authority',return_value=True):
            _,receipt=compare_and_select(source_projects=source,incumbent_fit=fit,
                render=lambda _:None,verify=lambda _:None)
        self.assertEqual(receipt['version'],VERSION)
        self.assertEqual(receipt['render_probe_limit'],1)
        self.assertTrue(receipt['no_approval_or_scorer_changes'])


if __name__=='__main__':unittest.main()

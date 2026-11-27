import unittest
from copy import deepcopy
from types import SimpleNamespace, ModuleType
from unittest.mock import patch, Mock
import sys
from tailoring.phase9f_workspace_restore_v312b216c2 import (
    accepted_draft, current_owned_draft, show_unapproved_workspace, draft_to_preserve,
    queue_accepted_restore, restore_accepted_workspace)


def fixture():
    binding={'decision_fingerprint':'decision','starting_snapshot_fingerprint':'snapshot','workflow_action_fingerprint':'action'}
    gen={'application_id':158,'generation_id':'accepted','status':'draft','phase9e_decision_fingerprint':'decision',
         'generation_settings':{'phase9e_binding':binding},'fit_result':{'fit_one_page':True}}
    receipt={'application_id':158,'generation_id':'accepted','verification_id':'receipt','verification_fingerprint':'vf',
         'verified_generation_snapshot_fingerprint':'gs','comparison_valid':True,'document_analysis':{'final_document_sha256':'sha'}}
    accept={'acceptance_fingerprint':'successor','generation_id':'accepted','verification_id':'receipt','verification_fingerprint':'vf',
         'verified_generation_snapshot_fingerprint':'gs','final_docx_sha256':'sha','previous_acceptance_fingerprint':'old'}
    decision={'application_id':158,'decision_fingerprint':'decision','starting_snapshot':{'starting_snapshot_fingerprint':'snapshot'},
              'scope_activation_status':'active','current_scope_status':'current','scoring_policy_transition':accept}
    other={**deepcopy(gen),'generation_id':'newer'}
    return {'phase9e_binding':decision,'current_drafts':[other,gen],'loaded_mode':'none','loaded_generation':None},gen,receipt


class RecoveryTests(unittest.TestCase):
    def choose(self,w,r,s=None,gate=True):
        return accepted_draft(158,w,s if s is not None else {},receipt_loader=lambda a,g:r,current_gate=lambda r,g:gate)[0]
    def test_exact_accepted_not_latest(self):
        w,g,r=fixture(); before=deepcopy(w);self.assertEqual(self.choose(w,r),g);self.assertEqual(w,before)
    def test_manual_browser_no_approval(self):
        w,g,r=fixture();self.assertTrue(show_unapproved_workspace(158,w));w['application_approved_generation']=g;self.assertFalse(show_unapproved_workspace(158,w))
    def test_stale_binding_hidden_and_not_restored(self):
        w,g,r=fixture();w['phase9e_binding']['current_scope_status']='stale';self.assertFalse(show_unapproved_workspace(158,w));self.assertIsNone(self.choose(w,r))
    def test_cross_app_and_snapshot_rejected(self):
        for k,v in [('application_id',159),('phase9e_decision_fingerprint','different'),('status','archived')]:
            w,g,r=fixture();g[k]=v;self.assertIsNone(self.choose(w,r))
        w,g,r=fixture();g['generation_settings']['phase9e_binding']['starting_snapshot_fingerprint']='other';self.assertIsNone(self.choose(w,r))
    def test_old_or_missing_receipt_rejected(self):
        for k in ('verification_id','verification_fingerprint','verified_generation_snapshot_fingerprint','document_analysis','comparison_valid'):
            w,g,r=fixture();r.pop(k);self.assertIsNone(self.choose(w,r))
        w,g,r=fixture();self.assertIsNone(self.choose(w,r,gate=False))
    def test_no_override_of_manual_selection_or_unsaved_content(self):
        w,g,r=fixture();w['loaded_generation']=w['current_drafts'][0];self.assertIsNone(self.choose(w,r))
        w,g,r=fixture();self.assertIsNone(self.choose(w,r,{'tailored_projects_result_158':{}}))
        self.assertIsNone(self.choose(w,r,{'tailored_generation_id_158':'other'}))
    def test_explicit_acceptance_queue_selects_reviewed_draft(self):
        w,g,r=fixture();w['loaded_generation']=w['current_drafts'][0];s={};queue_accepted_restore(s,158,w['phase9e_binding']['scoring_policy_transition']);self.assertEqual(self.choose(w,r,s),g)
        w['application_approved_generation']=w['current_drafts'][0];self.assertIsNone(self.choose(w,r,s))
    def test_no_reopen_after_manual_clear_same_session(self):
        w,g,r=fixture();self.assertIsNone(self.choose(w,r,{'b216c2_attempted_158':'successor'}));self.assertEqual(self.choose(w,r,{}),g)
    def test_no_substitution_after_deleted_or_duplicate(self):
        w,g,r=fixture();w['current_drafts'].remove(g);self.assertIsNone(self.choose(w,r));w['current_drafts'] += [g,g];self.assertIsNone(self.choose(w,r))
    def test_marker_preserves_only_matching_workflow_action(self):
        w,g,r=fixture();w['loaded_generation']=g;b=g['generation_settings']['phase9e_binding'];self.assertEqual(draft_to_preserve(158,w,b),g);self.assertIsNone(draft_to_preserve(158,w,{**b,'workflow_action_fingerprint':'changed'}))
        w['phase9e_binding']['current_scope_status']='stale';self.assertIsNone(draft_to_preserve(158,w,b))
    def test_normal_execution_has_no_workflow_action_fingerprint(self):
        w,g,r=fixture();w['loaded_generation']=g;b=g['generation_settings']['phase9e_binding'];b.pop('workflow_action_fingerprint');self.assertIsNone(draft_to_preserve(158,w,b))
        execution={k:'id-'+k for k in ('execution_id','execution_fingerprint','confirmation_fingerprint','phase9e_decision_fingerprint','starting_snapshot_fingerprint','exact_jd_identity_fingerprint','evidence_snapshot_fingerprint','section_scope_fingerprint')};execution.update(phase9e_decision_fingerprint='decision',starting_snapshot_fingerprint='snapshot')
        g['generation_settings'].update(phase9f_f_provenance=deepcopy(execution),phase9f_f_normal_lifecycle={'provenance':deepcopy(execution)})
        self.assertEqual(draft_to_preserve(158,w,b,execution),g);self.assertIsNone(draft_to_preserve(158,w,b,{**execution,'execution_fingerprint':'changed'}))
    def test_restore_session_actual_adapter_call_and_no_approval(self):
        w,g,r=fixture();s={};st=SimpleNamespace(session_state=s);restore=Mock()
        mods={}
        for name,attr,fn in [('database.tailoring_verification_manager','get_latest_tailoring_verification',lambda a,g:r),('tailoring.phase8_auto_verification','phase8_verification_is_current',lambda r,g:True),('tailoring.generation_controls_ui','restore_generation_to_session',restore)]:
            m=ModuleType(name);setattr(m,attr,fn);mods[name]=m
        with patch.dict(sys.modules,mods):
            result=restore_accepted_workspace(st,158,w);restore.assert_called_once_with(158,g);self.assertEqual(result['loaded_mode'],'working_draft');self.assertIsNone(result.get('approved_generation'));self.assertEqual(s['b216c2_attempted_158'],'successor')
    def test_acceptance_floor_not_approval(self):
        w,g,r=fixture();w['phase9e_binding']['scoring_policy_transition']['approval_floor_ready_at_acceptance']=False;self.assertEqual(self.choose(w,r),g)


class SourceWiringTests(unittest.TestCase):
    def test_app_restores_before_projection_and_exposes_drafts(self):
        from pathlib import Path
        app=Path('app.py').read_text(encoding='utf-8'); self.assertLess(app.index('score_workspace = restore_accepted_workspace'),app.index('active_score_projection = load_active_score'))
        self.assertIn('if not has_current_legacy_result:',app);self.assertIn('if show_unapproved_workspace(',app);self.assertIn('if retained_draft is not None:',app)
        transition=Path('tailoring/phase9f_policy_transition_v312b215c.py').read_text(encoding='utf-8');self.assertLess(transition.index('accepted = accept_policy_transition'),transition.index('queue_accepted_restore(st.session_state'))


class StaleGuidanceTests(unittest.TestCase):
    def overview(self, reasons, execution=None):
        import ast
        from pathlib import Path
        from typing import Any
        source = Path('tailoring/phase9e1_workflow_ui.py').read_text(encoding='utf-8')
        names = {'_clean', '_first', '_page_label', '_decision_source_label',
                 '_stale_scope_guidance', 'build_application_workflow_overview'}
        tree = ast.parse(source)
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.assertEqual({n.name for n in nodes}, names)
        ns = {'Any':Any, 'PHASE9E1_WORKFLOW_UI_VERSION':'test',
              'STATUS_REUSED_APPROVED':'reused_approved',
              'STATUS_REUSED_UNCHANGED_PENDING':'reused_unchanged_pending_application_verification',
              'PHASE9F_E_RESULT_STATUS':'phase9f_e_result', 'DECISION_LABELS':{}}
        exec(compile(ast.Module(body=nodes,type_ignores=[]), 'workflow_overview', 'exec'), ns)
        return ns['build_application_workflow_overview'](application_id=158,
            application_record={}, baseline_report={}, exact_jd={}, current_result=None,
            current_decision={'scope_activation_status':'active','current_scope_status':'stale',
                              'stale_reasons':reasons}, phase9f_f_execution=execution)

    def test_ordinary_stale_requires_reevaluation(self):
        for reasons in ([], ["The application's exact JD changed."],
                        ["The exact bound Base Resume version is missing."]):
            overview=self.overview(reasons)
            self.assertIn('Re-evaluate', overview['next_action'])
            self.assertIn('Do not approve or generate', overview['next_action'])

    def test_policy_only_guidance_recheck_not_replacement(self):
        for reason in ("The scoring policy changed. The exact JD scope is unchanged; recheck the existing document and explicitly accept the updated scoring policy.",
                       "The application's canonical JD scope changed. The exact JD text is unchanged; review the current scoring scope and explicitly reconfirm before generating or approving."):
            action=self.overview([reason], {'status':'waiting_for_approval','confirmed_intensity':'full'})['next_action']
            self.assertIn('Recheck the existing fitted résumé if eligible', action)
            self.assertNotIn('Re-evaluate', action)
            self.assertIn('Do not approve or generate', action)

    def test_mixed_staleness_never_claims_policy_only(self):
        action=self.overview(["The scoring policy changed. The exact JD scope is unchanged; recheck.",
                              "The selected starting-source content or identity changed."],
                             {'status':'waiting_for_approval'})['next_action']
        self.assertIn('Re-evaluate', action)
        self.assertIn('Do not approve or generate', action)

    def test_invalid_acceptance_requires_diagnostics(self):
        action=self.overview(['Accepted scoring policy transition is unavailable: invalid checksum'],
                             {'status':'waiting_for_approval'})['next_action']
        self.assertIn('acceptance diagnostics', action)
        self.assertNotIn('Recheck the existing fitted', action)
        self.assertIn('Do not approve or generate', action)

from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from contextlib import ExitStack
from streamlit.testing.v1 import AppTest
from taxonomy_discovery import governed_requirement_resolution as g
from tests.governed_review_fixtures import isolated_taxonomy


def application():
    app=AppTest.from_file(Path(__file__).with_name('governed_requirement_review_harness.py'),default_timeout=30)
    app.session_state['view']={'identity':{'discovered_job_id':146},'provenance':'TEST_ONLY',
        'requirements':[{'native':{'requirement_id':'development-only','text':'Design and develop RESTful APIs',
                         'importance':'core','parent_text':'Design and develop RESTful APIs'}}]}
    return app


class ReviewUITests(unittest.TestCase):
    def setUp(self):self.enterContext(isolated_taxonomy())
    def button(self,app,label):return next(b for b in app.button if b.label==label)

    def test_explicit_preview_no_rerender_execution_and_rejection(self):
        app=application()
        with patch.object(g,'preview',wraps=g.preview) as preview:
            app.run();self.assertFalse(app.exception);preview.assert_not_called()
            self.button(app,'Preview proposed correction').click().run()
            self.assertFalse(app.exception);self.assertEqual(preview.call_count,1)
            self.assertTrue(self.button(app,'Approve validated draft').disabled)
            app.run();self.assertEqual(preview.call_count,1)
            self.button(app,'Reject proposed correction').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any('Preview rejected' in x.value for x in app.info))
        self.assertEqual(g.resolve_requirement_with_production_knowledge({'text':'Design and develop RESTful APIs'})['status'],'unresolved')

    def test_inspect_diagnostics_does_not_propose_or_approve(self):
        app=application()
        with patch.object(g,'propose',side_effect=AssertionError('Inspect is not proposal execution')):
            app.run();self.button(app,'Inspect diagnostics').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Current native classification' in x.value for x in app.markdown))

    def test_selection_or_knowledge_change_invalidates_preview_state(self):
        app=application();app.run();self.button(app,'Preview proposed correction').click().run()
        view=deepcopy(app.session_state['view']);view['requirements'][0]['native']['text']='Knowledge of REST APIs'
        app.session_state['view']=view;app.run()
        self.assertFalse(app.exception)
        self.assertFalse(any(b.label=='Reject proposed correction' for b in app.button))
        with patch.object(g,'knowledge_fingerprint',return_value='changed knowledge'):
            app.run();self.assertFalse(app.exception)


class AutomaticStatusTests(unittest.TestCase):
    """Real Streamlit reruns with mocked governance actions; no live writes."""
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(isolated_taxonomy())
        self.saved={'result':{'research_result_id':'result-1','result_fingerprint':'result-fp'},
                    'draft':{'resolver_draft_id':'draft-1'}}
        self.regression={'draft_fingerprint':'draft-fp','regression_fingerprint':'reg-fp',
                         'publication_blockers':[],'unexpectedly_changed_requirements':[]}
        self.ready={'ready':True,'blockers':[],'version_before':'tax-v1','version_after':'tax-v2'}
        self.create=self.stack.enter_context(patch.object(g,'create_local_governed_draft',return_value=self.saved))
        self.validate=self.stack.enter_context(patch.object(g,'validate_governed_draft',return_value=self.regression))
        self.stack.enter_context(patch('taxonomy_discovery.regression_corpus.export_saved_corpus',return_value={}))
        self.approve=self.stack.enter_context(patch('database.taxonomy_discovery_review_manager.save_governed_research_review',return_value={'review_id':1}))
        self.preflight=self.stack.enter_context(patch.object(g,'approval_readiness',return_value=self.ready))
        self.publish=self.stack.enter_context(patch('taxonomy_discovery.governed_publication.publish_approved_change',
            return_value={'publication_id':'pub-1','status':'published','version_after':'tax-v2'}))
        self.app=application()
        self.app.run();self.click('Preview proposed correction');self.click('Validate draft')
        self.assertFalse(self.app.exception)

    def button(self,label):return next(b for b in self.app.button if b.label==label)
    def click(self,label):self.button(label).click().run();self.assertFalse(self.app.exception)
    def authorize(self):
        next(x for x in self.app.text_input if x.label=='Reviewer').set_value('Human reviewer').run()
        next(x for x in self.app.checkbox if 'approve this exact' in x.label).check().run()
    def messages(self,kind):return '\n'.join(x.value for x in getattr(self.app,kind))

    def test_immediate_success_auto_readiness_and_no_duplicate_mutations(self):
        self.assertIn('Draft validated',self.messages('success'))
        self.preflight.assert_not_called();self.approve.assert_not_called()
        self.authorize();self.click('Approve validated draft')
        self.assertIn('Draft approval saved successfully',self.messages('success'))
        self.assertIn('Approved — Ready for publication',self.messages('success'))
        self.assertIn('tax-v2',self.messages('markdown'))
        self.assertIn('Blockers: 0',self.messages('markdown'))
        self.preflight.assert_called_once_with('result-1');self.approve.assert_called_once()
        self.assertTrue(self.button('Approve validated draft').disabled)
        self.assertTrue(self.button('Publish approved correction').disabled)
        for _ in range(2):self.app.run()
        self.assertIn('Approved — Ready for publication',self.messages('success'))
        self.assertEqual(self.create.call_count,1);self.assertEqual(self.validate.call_count,1)
        self.assertEqual(self.approve.call_count,1);self.assertEqual(self.preflight.call_count,1)
        self.publish.assert_not_called()

    def test_stale_not_ready_replaced_after_approval(self):
        self.preflight.return_value={'ready':False,'blockers':['missing approval receipt']}
        self.click('Review approval readiness')
        self.assertIn('missing approval receipt',self.messages('warning'))
        self.preflight.return_value=self.ready;self.authorize();self.click('Approve validated draft')
        self.assertNotIn('missing approval receipt',self.messages('warning'))
        self.assertIn('Approved — Ready for publication',self.messages('success'))

    def test_approval_failure_removes_stale_readiness_and_rerun_does_not_retry(self):
        self.click('Review approval readiness')
        self.approve.side_effect=ValueError('receipt rejected')
        self.authorize();self.click('Approve validated draft')
        self.assertIn('Approval failed: receipt rejected',self.messages('error'))
        self.assertNotIn('Approved — Ready for publication',self.messages('success'))
        self.assertFalse(any(b.label=='Publish approved correction' for b in self.app.button))
        self.app.run();self.assertEqual(self.approve.call_count,1)
        self.assertIn('receipt rejected',self.messages('error'));self.publish.assert_not_called()

    def test_requirement_switch_and_knowledge_change_invalidate_results(self):
        self.authorize();self.click('Approve validated draft')
        view=deepcopy(self.app.session_state['view'])
        other=deepcopy(view['requirements'][0]);other['native']['requirement_id']='other'
        view['requirements'].append(other);self.app.session_state['view']=view;self.app.run()
        self.app.selectbox[0].select('other').run()
        self.assertNotIn('Draft approval saved',self.messages('success'))
        self.assertFalse(any(b.label=='Publish approved correction' for b in self.app.button))
        self.app.selectbox[0].select('development-only').run()
        self.assertNotIn('Draft validated',self.messages('success'))
        self.click('Preview proposed correction');self.click('Validate draft')
        with patch.object(g,'knowledge_fingerprint',return_value='externally changed'):
            self.app.run()
            self.assertNotIn('Draft validated',self.messages('success'))
        self.assertEqual(self.approve.call_count,1);self.publish.assert_not_called()

    def test_new_preview_invalidates_approval_and_draft_confirmation(self):
        self.authorize();self.click('Approve validated draft');self.click('Preview proposed correction')
        self.assertNotIn('Approved — Ready',self.messages('success'))
        self.click('Validate draft');self.assertTrue(self.button('Approve validated draft').disabled)
        self.assertFalse(next(x for x in self.app.checkbox if 'approve this exact' in x.label).value)

    def test_changed_draft_receipt_invalidates_approval_readiness(self):
        self.authorize();self.click('Approve validated draft')
        key=next(k for k in self.app.session_state.filtered_state if k.endswith('_packet'))
        packet=deepcopy(self.app.session_state[key])
        packet['governed_regression']['draft_fingerprint']='different-draft'
        self.app.session_state[key]=packet;self.app.run()
        self.assertFalse(self.app.exception)
        self.assertNotIn('Approved — Ready',self.messages('success'))
        self.assertNotIn('Draft validated',self.messages('success'))
        self.assertFalse(any(b.label=='Publish approved correction' for b in self.app.button))
        self.approve.assert_called_once();self.publish.assert_not_called()

    def test_workflow_statuses_and_collapsed_diagnostics(self):
        self.click('Inspect diagnostics')
        self.assertIn('Inspect: completed → Preview: completed → Validate: completed',self.messages('caption'))
        self.assertIn('Approve: pending → Publish: blocked',self.messages('caption'))
        advanced=next(x for x in self.app.expander if x.label=='Advanced diagnostics')
        self.assertFalse(advanced.proto.expanded)
        self.assertGreater(len(advanced.json),0)
        self.assertTrue(any(x.label=='Download privacy-sanitized debug bundle' for x in self.app.get('download_button')))
        self.authorize();self.click('Approve validated draft')
        self.assertIn('Approve: completed → Publish: pending',self.messages('caption'))

    def test_readiness_error_keeps_approval_success_and_requires_explicit_retry(self):
        self.preflight.side_effect=OSError('read unavailable')
        self.authorize();self.click('Approve validated draft')
        self.assertIn('Draft approval saved',self.messages('success'))
        self.assertIn('Readiness check failed',self.messages('error'))
        self.app.run();self.assertEqual(self.preflight.call_count,1)
        self.preflight.side_effect=None;self.click('Review approval readiness')
        self.assertIn('Approved — Ready',self.messages('success'));self.assertEqual(self.approve.call_count,1)

    def test_separate_publication_confirmation_receipt_and_version_survive_rerun(self):
        self.authorize();self.click('Approve validated draft');self.publish.assert_not_called()
        self.assertTrue(self.button('Publish approved correction').disabled)
        next(x for x in self.app.checkbox if 'authorize publication' in x.label).check().run()
        self.publish.assert_not_called()
        # Publication itself changes knowledge; the receipt must survive this transition.
        knowledge=['old']
        with patch.object(g,'knowledge_fingerprint',side_effect=lambda:knowledge[0]):
            self.app.run()  # External change correctly invalidates old approval first.
            self.click('Preview proposed correction');self.click('Validate draft');self.authorize()
            self.click('Approve validated draft')
            next(x for x in self.app.checkbox if 'authorize publication' in x.label).check().run()
            def published(*args,**kwargs):
                knowledge[0]='published'
                return {'publication_id':'pub-1','status':'published','version_after':'tax-v2'}
            self.publish.side_effect=published;self.click('Publish approved correction')
            self.assertIn('Published knowledge version tax-v2',self.messages('success'))
            self.assertIn('pub-1',self.messages('markdown'))
            self.app.run();self.assertIn('Published knowledge version tax-v2',self.messages('success'))
            self.assertTrue(self.button('Publish approved correction').disabled)
            self.publish.assert_called_once_with('result-1',explicit_publish=True,refresh_jobs=False)
            knowledge[0]='later external change';self.app.run()
            self.assertNotIn('Published knowledge version',self.messages('success'))

    def test_validation_and_publication_failures_show_direct_errors(self):
        self.validate.side_effect=RuntimeError('controls failed');self.click('Validate draft')
        self.assertIn('Validation failed: controls failed',self.messages('error'))
        self.assertTrue(self.button('Approve validated draft').disabled)
        self.validate.side_effect=None;self.click('Validate draft');self.authorize();self.click('Approve validated draft')
        next(x for x in self.app.checkbox if 'authorize publication' in x.label).check().run()
        self.publish.side_effect=ValueError('version mismatch');self.click('Publish approved correction')
        self.assertIn('Publication failed: version mismatch',self.messages('error'))
        self.app.run();self.assertEqual(self.publish.call_count,1)


if __name__=='__main__':unittest.main()

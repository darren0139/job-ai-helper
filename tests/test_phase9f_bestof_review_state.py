"""Disposable receipt lifecycle: neither native scorer nor approval is called."""
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from database import phase9f_bestof_review_state as review


class SavedDisplayReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        path = Path(self.temporary.name) / 'test.sqlite'
        def connect():
            connection = sqlite3.connect(path)
            connection.row_factory = sqlite3.Row
            return connection
        self.connection = connect
        self.patcher = patch.object(review, '_connect', self.connection)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.kwargs = dict(application_id=156, generation_id='gen-1', context='hash-1',
                           docx_sha256='a'*64, raw_jd_text='Frozen JD A',
                           scorer_version='stable-version-a', run_mode='v35-relevance',
                           mode_receipt={'generation_id':'gen-1','mode':'v35-relevance'})

    def save(self, result=None):
        return review.save_bestof_display_receipt(**self.kwargs, result=result or {'status':'verified','winner':'existing_final'})

    def load(self, **overrides):
        kwargs = {k:self.kwargs[k] for k in ('application_id','generation_id','docx_sha256','raw_jd_text','scorer_version')}
        return review.load_bestof_display_receipt(**(kwargs | overrides))

    def test_new_result_survives_independent_connection(self):
        self.assertTrue(self.save())
        self.assertTrue(review.has_bestof_display_receipt(156, 'gen-1'))
        item = self.load()
        self.assertEqual(item['result']['winner'], 'existing_final')
        self.assertEqual(item['run_mode'], 'v35-relevance')

    def test_never_reuse_changed_generation_docx_jd_scorer(self):
        self.save()
        for delta in ({'application_id':157}, {'generation_id':'gen-2'},
                      {'docx_sha256':'b'*64}, {'raw_jd_text':'JD B'},
                      {'scorer_version':'stable-version-b'}):
            with self.subTest(delta=delta):
                self.assertIsNone(self.load(**delta))

    def test_checksum_rejects_tampered_display_receipt(self):
        self.save()
        db=self.connection()
        try:
            db.execute("UPDATE phase9f_bestof_display_receipts SET result_json='{}'")
            db.commit()
        finally:
            db.close()
        self.assertIsNone(self.load())

    def test_private_session_withheld_or_not_run_not_misreported(self):
        self.assertFalse(review.save_bestof_display_receipt(**self.kwargs,result={'status':'not_run'}))
        self.assertFalse(review.has_bestof_display_receipt(156,'gen-1'))
        self.assertTrue(review.save_bestof_display_receipt(**self.kwargs,result={'status':'withheld','reason':'guard'}))
        self.assertEqual(self.load()['result']['status'],'withheld')

    def test_historical_cyclic_candidate_is_detached(self):
        result={'status':'verified','proposal':{}}
        result['proposal']['candidate_variants']=[result['proposal']]
        self.assertTrue(self.save(result))
        loaded=self.load()['result']
        self.assertEqual(loaded['proposal']['candidate_variants'][0],{'cyclic_display_reference_omitted':True})

    def test_delete_application_does_not_touch_other_apps(self):
        self.save()
        review.save_bestof_display_receipt(**(self.kwargs|{'application_id':157}),result={'status':'withheld'})
        self.assertEqual(review.delete_bestof_display_receipts(156),1)
        self.assertIsNone(self.load())
        self.assertTrue(review.has_bestof_display_receipt(157,'gen-1'))


if __name__ == '__main__':
    unittest.main()


class ViewStateTests(SavedDisplayReceiptTests):
    def test_saved_project_checks_and_radios_restore_after_connection_reopen(self):
        value={'selected_projects':['Job AI Helper','QueryAI'],
               'bullets':{'Job AI Helper_base_choice':'hashA', 'QueryAI_library_choice':'hashB'}}
        self.assertTrue(review.save_bestof_view_preferences(156,'gen-1','scope-1',value))
        self.assertEqual(review.load_bestof_view_preferences(156,'gen-1','scope-1'),value)
        self.assertEqual(review.load_bestof_view_preferences(156,'gen-2','scope-1'),{})
        self.assertEqual(review.load_bestof_view_preferences(156,'gen-1','scope-2'),{})
        self.assertTrue(review.save_bestof_view_preferences(156,'gen-1','scope-1',{'selected_projects':[]}))
        self.assertEqual(review.load_bestof_view_preferences(156,'gen-1','scope-1')['selected_projects'],[])

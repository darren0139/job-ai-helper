"""No score changes: reuse pure frozen profiles; never cache document authority."""
import unittest
from unittest.mock import patch
from tailoring import phase9e_blueprint_selection as selection

class PreviewReuse(unittest.TestCase):
 def setUp(self):
  selection._cached_profile_starting_analysis.cache_clear()
 def tearDown(self):
  selection._cached_profile_starting_analysis.cache_clear()
 def test_same_inputs_reuse_with_copy_isolation_and_source_jd_preference_invalidation(self):
  with patch.object(selection,'_build_phase9e_starting_analysis',return_value=({'nested':[]},{},{})) as build, patch('tailoring.job_match_ab_analysis.current_ab_identity',return_value={'scorer':'current'}):
   a=selection._reusable_starting_analysis({'resume_text_snapshot':'A'},{'raw_text':'JD'},[])
   a[0]['nested'].append('not shared')
   b=selection._reusable_starting_analysis({'resume_text_snapshot':'A'},{'raw_text':'JD'},[])
   self.assertEqual(b[0]['nested'],[]);self.assertEqual(build.call_count,1)
   selection._reusable_starting_analysis({'resume_text_snapshot':'B'},{'raw_text':'JD'},[])
   selection._reusable_starting_analysis({'resume_text_snapshot':'A'},{'raw_text':'changed JD'},[])
   selection._reusable_starting_analysis({'resume_text_snapshot':'A'},{'raw_text':'JD'},['SQL'])
   self.assertEqual(build.call_count,4)
 def test_identity_change_invalidates_and_documents_are_always_reverified(self):
  with patch.object(selection,'_build_phase9e_starting_analysis',return_value=({}, {}, {})) as build, patch('tailoring.job_match_ab_analysis.current_ab_identity',side_effect=[{'scorer':'old'},{'scorer':'new'}]):
   for _ in range(2):selection._reusable_starting_analysis({'resume_text_snapshot':'A'},{'raw_text':'JD'},[])
   self.assertEqual(build.call_count,2)
   for _ in range(2):selection._reusable_starting_analysis({'document_analysis_mode':'actual_docx'},{'raw_text':'JD'},[])
   self.assertEqual(build.call_count,4)

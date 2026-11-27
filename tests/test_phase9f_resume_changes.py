from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from docx import Document

from tailoring.phase9f_resume_changes import build_resume_changes, read_base_projects, read_selected_base_artifact


class ResumeChangesTests(TestCase):
    def test_normal_workflow_resolves_owner_even_when_it_has_no_generation_pointer(self):
        from database import phase9f_tailoring_execution_manager as manager

        owner = {'execution_fingerprint': 'frozen-execution', 'generation_id': None,
                 'confirmation_id': 'original-confirmation', 'source_artifact': {'sha256': 'base'}}
        decision = {'decision_fingerprint': 'decision'}
        confirmation = {'confirmation_id': 'original-confirmation'}
        with (patch.object(manager, 'get_phase9f_tailoring_execution', return_value=owner) as lookup,
              patch.object(manager, 'get_phase9f_application_confirmation', return_value=confirmation) as confirm,
              patch.object(manager, '_resolve_prepared_source_artifact', return_value={'sha256': 'base'}) as artifact):
            self.assertEqual({'sha256': 'base'}, read_selected_base_artifact(22, 'fitted', owner, decision))
            lookup.assert_called_once_with(22, generation_id='fitted')
            confirm.assert_called_once_with(22, confirmation_id='original-confirmation')
            artifact.assert_called_once_with(decision=decision, confirmation=confirmation,
                                             expected_identity=owner['source_artifact'])
            with self.assertRaisesRegex(ValueError, 'frozen execution'):
                read_selected_base_artifact(22, 'fitted', {'execution_fingerprint': 'different'}, decision)

    def test_exact_documents_identify_absent_and_added_wordings(self):
        doc = Document()
        doc.add_paragraph('PROJECTS')
        doc.add_paragraph('RequestFlow\t2026')
        doc.add_paragraph('Configured role-based access.', style='List Bullet')
        doc.add_paragraph('Built request workflows.', style='List Bullet')
        doc.add_paragraph('Legacy Tool\t2024')
        doc.add_paragraph('Built an internal tool.', style='List Bullet')
        doc.add_paragraph('SKILLS')
        stream = BytesIO()
        doc.save(stream)
        decision = {'starting_snapshot': {'resume_profile_snapshot': {
            'projects': [{'title': 'RequestFlow'}, {'title': 'Legacy Tool'}],
        }}}
        base = read_base_projects({'artifact_bytes': stream.getvalue()}, decision)
        audit = {'verified': True, 'docx_sha256': 'a'*64, 'projects': [
            {'project': 'RequestFlow', 'present_in_docx': True,
             'final': [{'text': 'Built request workflows.'}, {'text': 'Wrote RESTful APIs.'}],
             'library': [{'text': 'Wrote RESTful APIs.'}]},
            {'project': 'Legacy Tool', 'present_in_docx': False, 'final': []},
            {'project': 'Status Monitor', 'present_in_docx': True, 'final': []},
        ]}
        scores = {'status': 'available', 'bullets': [
            {'project': 'RequestFlow', 'wording': 'Wrote RESTful APIs.',
             'standalone_weighted_points': 9, 'saved_jd_ids': ['api']},
        ]}
        retained, removed, added = build_resume_changes(base, audit, {}, scores)
        self.assertEqual(('Retained', 2, 2), (retained['status'], retained['base_count'], retained['final_count']))
        self.assertEqual(('Removed', 1, 0), (removed['status'], removed['base_count'], removed['final_count']))
        self.assertEqual(('Added', 0, 0), (added['status'], added['base_count'], added['final_count']))
        old, new = retained['bullets'][1:]
        self.assertEqual(('Original wording absent', None, None),
                         (old['status'], old['lineage'], old['saved_link_points']))
        self.assertEqual(('Added Library wording', None, 9),
                         (new['status'], new['lineage'], new['saved_link_points']))
        self.assertEqual(['api'], new['saved_jd_ids'])
        decision['starting_snapshot']['resume_profile_snapshot']['projects'].pop()
        with self.assertRaisesRegex(ValueError, 'recognized project'):
            read_base_projects({'artifact_bytes': stream.getvalue()}, decision)

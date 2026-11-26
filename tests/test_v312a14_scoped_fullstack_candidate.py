"""V3.12-A1.4 opt-in native candidate safety and negative controls."""
from __future__ import annotations
import unittest
from copy import deepcopy
from analysis_stability import stable_evidence_scoring as scoring
from tailoring.fullstack_direct_evidence_v312a14 import independent_fullstack_implementation as accepts

FULL = "Built a full-stack IT service request tracker with React, TypeScript, FastAPI, and PostgreSQL, spanning application development, database design, and RESTful APIs."
CI = "Automated frontend builds, backend tests, GHCR image publishing, and Trivy security scans with GitHub Actions; added Prometheus metrics, alerts, and Grafana dashboards."
TESTS = "Created automated backend and frontend tests covering authentication, requests, RBAC, comments, authentication pages, request forms, and role-based navigation."
FOCUS = "Experience in frontend and backend web application development will be an added advantage"


def row(label='transferable', **kw):
    result = {
        'requirement_id': 'req_candidate_synthetic', 'text': FOCUS, 'atomic_focus': FOCUS,
        'importance': 'preferred', 'score_eligible': True, 'explicit_only_requirement': False,
        'capability_id': 'fullstack.integration', 'capability_resolution_source': 'canonical_taxonomy',
        'match_label': label, 'match_value': scoring.MATCH_VALUES[label],
        'evidence_strength': 3 if label == 'transferable' else 5,
        'match_source': 'present', 'evidence': [
            {'evidence_id':'ev-ci','section':'projects','source':'resume_profile.projects[0].bullets[1]','text': CI, 'reason':'existing preliminary match'}
        ],
    }
    result.update(kw)
    return result


def evidence(text, source='resume_profile.projects[0].bullets[0]', section='projects'):
    return {'evidence_id':'ev-real','section':section,'source':source,'text':text}


class ScopedFullstackCandidate(unittest.TestCase):
    def test_direct_real_implementation_and_exact_single_row(self):
        result, audit = scoring._apply_v312a14_fullstack_candidate(
            [row()], evidence_index=[evidence(CI,source='resume_profile.projects[0].bullets[1]'), evidence(FULL)], raw_resume_text=FULL+'\n'+CI)
        self.assertEqual(result[0]['match_label'],'direct')
        self.assertEqual(result[0]['match_value'],1.0)
        self.assertEqual(result[0]['evidence_strength'],5)
        self.assertEqual(len(result[0]['evidence']),1)
        self.assertEqual(result[0]['evidence'][0]['text'],FULL)
        self.assertEqual(len(audit),1)
        self.assertFalse(audit[0]['combined_evidence_rows'])
        self.assertEqual(audit[0]['previous_match_label'],'transferable')
    def test_ci_and_tests_not_standalone_fullstack(self):
        for text in (CI,TESTS,
          'Implemented backend and frontend tests for a full-stack application.',
          'Built full-stack backend and frontend integration tests for a service platform.',
          'Engineered backend and frontend CI pipelines for a web application.'):
            with self.subTest(text=text):
                self.assertFalse(accepts(text))
                result, audit=scoring._apply_v312a14_fullstack_candidate(
                    [row()], evidence_index=[evidence(text)], raw_resume_text=text)
                self.assertEqual(result[0]['match_label'],'transferable')
                self.assertEqual(audit,[])
    def test_no_cross_document_or_raw_text_bypass(self):
        for source, section, raw in [
            ('resume_profile.projects[0].bullets[0]', 'projects','No project implementation here'),
            ('raw_resume_text[0]','raw_text',FULL),
            ('resume_profile.skills.Languages[0]','skills',FULL),
            ('resume_profile.experience[0].bullets[0]','experience',FULL),
            ('resume_profile.projects[0]','projects',FULL),
        ]:
            with self.subTest(source=source,section=section,raw=raw):
                x,a=scoring._apply_v312a14_fullstack_candidate(
                    [row()], evidence_index=[evidence(FULL,source,section)],raw_resume_text=raw)
                self.assertEqual(x[0]['match_label'],'transferable')
                self.assertFalse(a)
    def test_requirement_scope_and_negation(self):
        for kw in [
            {'capability_id':'backend.api_development'},
            {'capability_resolution_source':'technology_registry'},
            {'importance':'required'},
            {'score_eligible':False},
            {'explicit_only_requirement':True},
            {'text':'Frontend testing and backend testing','atomic_focus':'Frontend testing and backend testing'},
            {'match_label':'direct','match_value':1.0,'evidence_strength':5},
        ]:
            with self.subTest(kw=kw):
                x,a=scoring._apply_v312a14_fullstack_candidate([row(**kw)],evidence_index=[evidence(FULL)],raw_resume_text=FULL)
                self.assertEqual(a,[])
                self.assertEqual(x[0],row(**kw))
        self.assertFalse(accepts('Built a React frontend but the backend was not implemented.'))
    def test_default_disabled_and_context_cleanup(self):
        self.assertFalse(scoring._V312A14_NATIVE_REPLAY_SCOPE.get())
        try:
            with scoring.temporary_v312a14_candidate_scope():
                self.assertTrue(scoring._V312A14_NATIVE_REPLAY_SCOPE.get())
                raise RuntimeError('scope exit test')
        except RuntimeError:
            pass
        self.assertFalse(scoring._V312A14_NATIVE_REPLAY_SCOPE.get())
    def test_no_original_mutation(self):
        original=[row()]; before=deepcopy(original)
        scoring._apply_v312a14_fullstack_candidate(original,evidence_index=[evidence(FULL)],raw_resume_text=FULL)
        self.assertEqual(original,before)

if __name__ == '__main__':
    unittest.main()
